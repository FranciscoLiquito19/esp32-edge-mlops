"""Convert the trained model to int8 TFLite, evaluate both, and apply the gate.

The gate is what stops a bad model from being packaged: the int8 model must
stay within a fixed accuracy drop of the float model and fit the size budget.

    python -m edgeml.quantize --model models/float.keras --data data/processed/dataset.npz --out models
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import dataset as ds
from . import tflite_utils
from .train import to_float


def convert_int8(model, calibration: np.ndarray) -> bytes:
    """Full-integer post-training quantisation, calibrated on real inputs."""
    import tensorflow as tf

    def representative():
        for sample in calibration:
            yield [sample[np.newaxis, ...]]

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    return bytes(converter.convert())


def confusion(y_true: np.ndarray, y_pred: np.ndarray, n: int) -> list[list[int]]:
    matrix = np.zeros((n, n), dtype=np.int64)
    for t, p in zip(y_true, y_pred, strict=True):
        matrix[int(t), int(p)] += 1
    return matrix.tolist()


def _accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    return float((y_true == y_pred).mean()) if len(y_true) else None


def _markdown(report: dict) -> str:
    labels = report["labels"]
    gate = report["gate"]
    lines = ["# Evaluation report", ""]
    lines += [
        "| | float32 | int8 |",
        "|---|---|---|",
        f"| Test accuracy | {report['float']['accuracy']} | {report['int8']['accuracy']} |",
        f"| Size (bytes) | - | {report['int8']['size_bytes']} |",
        "",
        f"Test images: {report['test_samples']}. Gate: **{'PASS' if gate['passed'] else 'FAIL'}**"
        f" (max accuracy drop {gate['max_accuracy_drop']}, max size {gate['max_size_bytes']} bytes).",
        "",
    ]
    for name in ("float", "int8"):
        lines += [f"## Confusion matrix, {name} (rows: truth, columns: prediction)", ""]
        lines.append("| | " + " | ".join(labels) + " |")
        lines.append("|---|" + "---|" * len(labels))
        for label, row in zip(labels, report[name]["confusion"], strict=True):
            lines.append(f"| **{label}** | " + " | ".join(str(v) for v in row) + " |")
        lines.append("")
    return "\n".join(lines)


def quantize(
    model_path: Path,
    data_path: Path,
    out: Path,
    *,
    calibration_samples: int = 200,
    max_accuracy_drop: float = 0.02,
    max_size_bytes: int = 1_500_000,
    seed: int = 0,
) -> dict:
    import keras

    data = ds.load(data_path)
    labels = [str(label) for label in data["labels"]]
    model = keras.saving.load_model(model_path)

    rng = np.random.default_rng(seed)
    x_train = data["x_train"]
    if len(x_train) == 0:
        raise SystemExit("no training images to calibrate the quantisation with")
    picks = rng.choice(len(x_train), size=min(calibration_samples, len(x_train)), replace=False)
    tflite_model = convert_int8(model, to_float(x_train[picks]))

    x_test, y_test = data["x_test"], data["y_test"]
    if len(x_test):
        float_pred = np.argmax(model.predict(to_float(x_test), verbose=0), axis=1)
        int8_pred = np.argmax(tflite_utils.run_int8(tflite_model, x_test), axis=1)
    else:
        float_pred = int8_pred = np.zeros(0, dtype=np.int64)

    float_acc = _accuracy(y_test, float_pred)
    int8_acc = _accuracy(y_test, int8_pred)
    drop = (float_acc - int8_acc) if float_acc is not None else None

    reasons = []
    if drop is None:
        reasons.append("no test images, accuracy unknown")
    elif drop > max_accuracy_drop:
        reasons.append(f"accuracy drop {drop:.4f} exceeds {max_accuracy_drop}")
    if len(tflite_model) > max_size_bytes:
        reasons.append(f"model is {len(tflite_model)} bytes, budget is {max_size_bytes}")

    report = {
        "labels": labels,
        "test_samples": int(len(x_test)),
        "float": {"accuracy": float_acc, "confusion": confusion(y_test, float_pred, len(labels))},
        "int8": {
            "accuracy": int8_acc,
            "confusion": confusion(y_test, int8_pred, len(labels)),
            "size_bytes": len(tflite_model),
            "ops": tflite_utils.list_ops(tflite_model),
            **tflite_utils.io_details(tflite_model),
        },
        "gate": {
            "passed": not reasons,
            "reasons": reasons,
            "accuracy_drop": drop,
            "max_accuracy_drop": max_accuracy_drop,
            "max_size_bytes": max_size_bytes,
        },
    }

    out.mkdir(parents=True, exist_ok=True)
    (out / "model_int8.tflite").write_bytes(tflite_model)
    (out / "eval_report.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "eval_report.md").write_text(_markdown(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, default=Path("models/float.keras"))
    parser.add_argument("--data", type=Path, default=Path("data/processed/dataset.npz"))
    parser.add_argument("--out", type=Path, default=Path("models"))
    parser.add_argument("--calibration-samples", type=int, default=200)
    parser.add_argument("--max-accuracy-drop", type=float, default=0.02)
    parser.add_argument("--max-size-bytes", type=int, default=1_500_000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    report = quantize(
        args.model,
        args.data,
        args.out,
        calibration_samples=args.calibration_samples,
        max_accuracy_drop=args.max_accuracy_drop,
        max_size_bytes=args.max_size_bytes,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                "float": report["float"]["accuracy"],
                "int8": report["int8"]["accuracy"],
                "size_bytes": report["int8"]["size_bytes"],
                "gate": report["gate"],
            },
            indent=2,
        )
    )
    if not report["gate"]["passed"]:
        raise SystemExit("evaluation gate failed: " + "; ".join(report["gate"]["reasons"]))


if __name__ == "__main__":
    main()
