"""Checks that need TensorFlow: what the converter produces must be what the firmware can run."""

import re
from pathlib import Path

import numpy as np
import pytest

from edgeml import config

FIRMWARE = Path(__file__).resolve().parents[2] / "firmware"


def firmware_ops() -> tuple[set[str], int]:
    """Operators registered in inference.cc, as TFLite names, and the resolver capacity."""
    source = (FIRMWARE / "components/inference/inference.cc").read_text()
    names = re.findall(r"\br\.Add(\w+)\(\)", source)
    capacity = int(re.search(r"kNumOps\s*=\s*(\d+)", source).group(1))

    def tflite_name(camel: str) -> str:
        # AddDepthwiseConv2D -> DEPTHWISE_CONV_2D
        return re.sub(r"(?<=[a-z])(?=[A-Z0-9])", "_", camel).upper()

    return {tflite_name(n) for n in names}, capacity


@pytest.fixture(scope="module")
def int8_model() -> bytes:
    from edgeml.model import build_model
    from edgeml.quantize import convert_int8

    rng = np.random.default_rng(0)
    calibration = rng.random((16, config.INPUT_HEIGHT, config.INPUT_WIDTH, 1), dtype=np.float32)
    return convert_int8(build_model(), calibration)


def test_op_names_are_translated():
    ops, capacity = firmware_ops()
    assert {"CONV_2D", "DEPTHWISE_CONV_2D", "FULLY_CONNECTED", "AVERAGE_POOL_2D", "MEAN"} <= ops
    assert len(ops) <= capacity


def test_model_only_uses_operators_the_firmware_registers(int8_model):
    from edgeml import tflite_utils

    ops, _ = firmware_ops()
    assert set(tflite_utils.list_ops(int8_model)) <= ops


def test_model_io_matches_firmware_expectations(int8_model):
    from edgeml import tflite_utils

    d = tflite_utils.io_details(int8_model)
    assert d["input_shape"] == [1, config.INPUT_HEIGHT, config.INPUT_WIDTH, 1]
    assert d["input_dtype"] == "int8" and d["output_dtype"] == "int8"
    assert d["output_shape"] == [1, len(config.LABELS)]
    # Trained on pixel/255: the input maps one grey level to one int8 step.
    assert d["input_scale"] == pytest.approx(1 / 255, rel=1e-3)
    assert d["input_zero_point"] == -128


def test_model_fits_the_partition_with_room(int8_model):
    from edgeml.package import PARTITION_BYTES

    assert len(int8_model) < PARTITION_BYTES // 4


@pytest.mark.slow
def test_whole_pipeline_on_synthetic_data(tmp_path):
    from edgeml import manifest, smoke

    result = smoke.run(tmp_path, per_class=40, epochs=30)

    info, payload = manifest.parse(Path(result["package"]).read_bytes())
    assert info.labels == config.LABELS
    assert (info.input_width, info.input_height) == (config.INPUT_WIDTH, config.INPUT_HEIGHT)
    assert len(payload) == result["size_bytes"]
    for name in ("float.keras", "model_int8.tflite", "eval_report.json", "eval_report.md"):
        assert (tmp_path / "models" / name).exists()
    # The shapes are easy: failing to learn them means training is broken.
    assert result["float_accuracy"] >= 0.8
    assert result["int8_accuracy"] >= 0.8
