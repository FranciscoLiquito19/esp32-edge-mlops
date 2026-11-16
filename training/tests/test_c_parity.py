"""The firmware's C code and the Python tooling must agree byte for byte."""

import json
import subprocess

import numpy as np
import pytest

from edgeml import manifest, preprocess


def run(exe, *args, stdin: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run([str(exe), *map(str, args)], input=stdin, capture_output=True, check=check)


def test_c_parser_reads_python_package(host_check, tmp_path):
    payload = b"\x1c\x00\x00\x00TFL3" + bytes(1000)
    blob = manifest.pack(
        payload,
        model_version=42,
        labels=("nothing", "person", "animal"),
        input_width=128,
        input_height=96,
        name="dataset-v3",
        created_unix=1_800_000_123,
    )
    path = tmp_path / "model.bin"
    path.write_bytes(blob)

    parsed = json.loads(run(host_check, "manifest", path).stdout)
    info, _ = manifest.parse(blob)

    assert parsed == {
        "ok": True,
        "model_version": 42,
        "payload_size": len(payload),
        "created_unix": 1_800_000_123,
        "input_width": 128,
        "input_height": 96,
        "input_channels": 1,
        "format": manifest.FORMAT_TFLITE_INT8,
        "name": "dataset-v3",
        "sha256": info.sha256.hex(),
        "labels": ["nothing", "person", "animal"],
    }


@pytest.mark.parametrize(
    "damage, message",
    [
        (lambda b: b"\xff" * len(b), "no model package found"),
        (lambda b: b[:20] + bytes([b[20] ^ 1]) + b[21:], "header checksum mismatch"),
        (lambda b: b[:100], "too short"),
    ],
)
def test_c_parser_rejects_damage(host_check, tmp_path, damage, message):
    blob = manifest.pack(b"payload", model_version=1, labels=("a", "b"), input_width=8, input_height=8)
    path = tmp_path / "bad.bin"
    path.write_bytes(damage(blob))

    result = run(host_check, "manifest", path, check=False)
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"ok": False, "error": message}


def test_gray_conversion_matches(host_check):
    rng = np.random.default_rng(0)
    rgb = rng.integers(0, 256, size=(75, 100, 3), dtype=np.uint8)

    out = run(host_check, "gray", 100, 75, 64, 48, stdin=rgb.tobytes()).stdout
    c_gray = np.frombuffer(out, dtype=np.uint8).reshape(48, 64)

    py_gray = preprocess.center_crop(preprocess.rgb_to_gray(rgb), 48, 64)
    assert np.array_equal(c_gray, py_gray)


def test_gray_conversion_refuses_small_source(host_check):
    result = run(host_check, "gray", 10, 10, 20, 20, stdin=bytes(300), check=False)
    assert result.returncode == 1


@pytest.mark.parametrize("scale, zero_point", [(1 / 255, -128), (0.00392156862, -128), (0.0078125, 0), (0.02, -5)])
def test_input_quantisation_matches(host_check, scale, zero_point):
    out = run(host_check, "quant", repr(scale), zero_point).stdout
    c_lut = [int(v) for v in out.split()]
    py_lut = preprocess.quantize(np.arange(256, dtype=np.uint8), scale, zero_point).tolist()
    assert c_lut == py_lut
