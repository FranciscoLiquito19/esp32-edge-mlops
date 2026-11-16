"""Run the whole pipeline on synthetic images.

Proves that every stage works and produces a real, loadable model package for
firmware tests. The model it produces recognises drawn shapes, not people.

    python -m edgeml.smoke --out /tmp/smoke
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import dataset, package, quantize, synth, train


def run(out: Path, per_class: int = 80, epochs: int = 25, seed: int = 0) -> dict:
    raw, processed, models = out / "raw", out / "processed", out / "models"

    synth.write_dataset(raw, per_class, seed)
    stats = dataset.build(raw, processed, group_size=10)
    metrics = train.train(processed / "dataset.npz", models, epochs=epochs, seed=seed)
    report = quantize.quantize(
        models / "float.keras",
        processed / "dataset.npz",
        models,
        max_accuracy_drop=0.10,  # tiny synthetic test split: one image is several percent
        seed=seed,
    )
    manifest = package.package(
        models / "model_int8.tflite",
        models / "eval_report.json",
        models / "model.bin",
        version=1,
        name="synthetic-smoke",
        allow_failed_gate=True,
    )
    return {
        "counts": stats["counts"],
        "params": metrics["params"],
        "float_accuracy": report["float"]["accuracy"],
        "int8_accuracy": report["int8"]["accuracy"],
        "size_bytes": report["int8"]["size_bytes"],
        "ops": report["int8"]["ops"],
        "gate_passed": report["gate"]["passed"],
        "package": str(models / "model.bin"),
        "model_version": manifest.model_version,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-class", type=int, default=80)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(run(args.out, args.per_class, args.epochs, args.seed), indent=2))


if __name__ == "__main__":
    main()
