"""Wrap a quantised model in the package format the firmware loads.

Refuses to package a model whose evaluation gate did not pass, or whose
tensors do not match what the firmware expects.

    python -m edgeml.package --model models/model_int8.tflite --report models/eval_report.json \
        --version 1 --name dataset-v1 --out models/model.bin
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import manifest, tflite_utils

# Must match the `model` partition in firmware/partitions.csv.
PARTITION_BYTES = 0x200000


def package(
    model_path: Path,
    report_path: Path | None,
    out: Path,
    *,
    version: int,
    name: str,
    allow_failed_gate: bool = False,
) -> manifest.Manifest:
    model = model_path.read_bytes()
    details = tflite_utils.io_details(model)

    if details["input_dtype"] != "int8" or details["output_dtype"] != "int8":
        raise SystemExit("the firmware only runs models with int8 input and output")
    _, height, width, channels = details["input_shape"]

    if report_path is None:
        raise SystemExit("an evaluation report is required (--report)")
    report = json.loads(report_path.read_text())
    if not report["gate"]["passed"] and not allow_failed_gate:
        raise SystemExit("evaluation gate failed: " + "; ".join(report["gate"]["reasons"]))
    labels = tuple(report["labels"])
    if details["output_shape"][-1] != len(labels):
        raise SystemExit("the model's output size does not match the number of labels")

    blob = manifest.pack(
        model,
        model_version=version,
        labels=labels,
        input_width=width,
        input_height=height,
        input_channels=channels,
        name=name,
    )
    if len(blob) > PARTITION_BYTES:
        raise SystemExit(f"package is {len(blob)} bytes, the model partition holds {PARTITION_BYTES}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    parsed, _ = manifest.parse(blob)
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, default=Path("models/model_int8.tflite"))
    parser.add_argument("--report", type=Path, default=Path("models/eval_report.json"))
    parser.add_argument("--out", type=Path, default=Path("models/model.bin"))
    parser.add_argument("--version", type=int, required=True, help="model version, increase on every release")
    parser.add_argument("--name", default="model", help="short tag, e.g. the dataset version")
    parser.add_argument("--allow-failed-gate", action="store_true", help="for experiments only")
    args = parser.parse_args()

    m = package(
        args.model,
        args.report,
        args.out,
        version=args.version,
        name=args.name,
        allow_failed_gate=args.allow_failed_gate,
    )
    print(
        f"wrote {args.out}: model v{m.model_version} '{m.name}', {m.payload_size} bytes, "
        f"input {m.input_width}x{m.input_height}x{m.input_channels}, labels {', '.join(m.labels)}"
    )


if __name__ == "__main__":
    main()
