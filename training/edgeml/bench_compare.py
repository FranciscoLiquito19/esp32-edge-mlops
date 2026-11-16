"""Compare a firmware bench run with the same model on the PC.

The firmware's bench mode (emulator or real board) classifies fixed JPEGs and
prints its outputs. This tool runs the same JPEGs through the same model here
and answers three questions:

1. Preprocessing: how far is the device's grey image from the PC's?
2. Runtime: fed the device's own grey image, does TFLite on the PC give the
   same int8 outputs as TFLite Micro on the device?
3. End to end: do device and PC agree on the class?

    python -m edgeml.bench_compare --log bench.log --package models/model.bin \
        --golden ../firmware/main/golden
"""

from __future__ import annotations

import argparse
import json
import re
import zlib
from pathlib import Path

import numpy as np

from . import manifest, preprocess, tflite_utils

_BENCH = re.compile(r"^BENCH (\{.*\})\s*$")
_GRAY = re.compile(r"^GRAY (\w+) (\d+) ([0-9a-f]+)\s*$")
_DONE = re.compile(r"^BENCH_DONE (\{.*\})\s*$")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def parse_log(text: str) -> dict:
    """Extract bench results, grey-image dumps and the summary from a serial log."""
    results: dict[str, dict] = {}
    gray: dict[str, bytearray] = {}
    summary = None
    for raw in text.splitlines():
        line = _ANSI.sub("", raw).strip()
        if m := _BENCH.match(line):
            entry = json.loads(m.group(1))
            results[entry["image"]] = entry
        elif m := _GRAY.match(line):
            name, offset, data = m.group(1), int(m.group(2)), bytes.fromhex(m.group(3))
            buf = gray.setdefault(name, bytearray())
            if offset != len(buf):
                raise ValueError(f"grey dump for {name} has a gap at offset {offset}")
            buf.extend(data)
        elif m := _DONE.match(line):
            summary = json.loads(m.group(1))
    return {"results": results, "gray": {k: bytes(v) for k, v in gray.items()}, "summary": summary}


def compare(log_text: str, package: bytes, golden: Path) -> dict:
    parsed = parse_log(log_text)
    if not parsed["summary"] or not parsed["summary"].get("ok"):
        raise SystemExit("the bench run did not finish (no BENCH_DONE with ok=true)")

    info, model = manifest.parse(package)
    shape = (info.input_height, info.input_width)
    report = {"model_version": info.model_version, "summary": parsed["summary"], "images": []}

    for name, device in sorted(parsed["results"].items()):
        if device.get("error"):
            raise SystemExit(f"the device failed on image {name}")
        jpeg = (golden / f"{name}.jpg").read_bytes()
        pc_gray = preprocess.jpeg_to_gray(jpeg, info.input_width, info.input_height)
        pc_q = tflite_utils.run_int8(model, pc_gray[np.newaxis])[0]
        device_q = np.asarray(device["q"], dtype=np.int64)

        entry = {
            "image": name,
            "label_device": info.labels[device["top"]],
            "label_pc": info.labels[int(np.argmax(pc_q))],
            "q_device": device_q.tolist(),
            "q_pc": pc_q.astype(int).tolist(),
            "end_to_end_max_q_diff": int(np.abs(device_q - pc_q).max()),
            "decode_us": device["decode_us"],
            "invoke_us": device["invoke_us"],
        }

        dumped = parsed["gray"].get(name)
        if dumped is not None:
            if len(dumped) != shape[0] * shape[1]:
                raise SystemExit(f"grey dump for {name} has {len(dumped)} bytes")
            if f"{zlib.crc32(dumped):08x}" != device["gray_crc"]:
                raise SystemExit(f"grey dump for {name} does not match its checksum")
            device_gray = np.frombuffer(dumped, dtype=np.uint8).reshape(shape)
            diff = np.abs(device_gray.astype(np.int16) - pc_gray.astype(np.int16))
            same_input_q = tflite_utils.run_int8(model, device_gray[np.newaxis])[0]
            entry.update(
                gray_mean_abs_diff=round(float(diff.mean()), 3),
                gray_max_abs_diff=int(diff.max()),
                gray_pixels_differing_pct=round(float((diff > 0).mean() * 100), 1),
                runtime_max_q_diff=int(np.abs(device_q - same_input_q).max()),
            )
        report["images"].append(entry)

    report["classes_agree"] = all(e["label_device"] == e["label_pc"] for e in report["images"])
    runtime = [e["runtime_max_q_diff"] for e in report["images"] if "runtime_max_q_diff" in e]
    report["runtime_max_q_diff"] = max(runtime) if runtime else None
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log", type=Path, required=True, help="serial output of a bench run")
    parser.add_argument("--package", type=Path, required=True, help="the model.bin the device ran")
    parser.add_argument("--golden", type=Path, default=Path("../firmware/main/golden"))
    parser.add_argument(
        "--max-runtime-diff",
        type=int,
        default=1,
        help="allowed int8 output difference when both runtimes get the same input",
    )
    args = parser.parse_args()

    report = compare(args.log.read_text(errors="replace"), args.package.read_bytes(), args.golden)
    print(json.dumps(report, indent=2))

    problems = []
    if not report["classes_agree"]:
        problems.append("device and PC disagree on a class")
    if report["runtime_max_q_diff"] is not None and report["runtime_max_q_diff"] > args.max_runtime_diff:
        problems.append(f"runtime outputs differ by {report['runtime_max_q_diff']}")
    if problems:
        raise SystemExit("PARITY FAIL: " + "; ".join(problems))
    print("PARITY OK")


if __name__ == "__main__":
    main()
