"""Helpers around the TFLite interpreter for int8 models."""

from __future__ import annotations

import numpy as np

from . import preprocess


def _interpreter(model: bytes):
    import tensorflow as tf

    interpreter = tf.lite.Interpreter(model_content=model)
    interpreter.allocate_tensors()
    return interpreter


def io_details(model: bytes) -> dict:
    """Shapes, types and quantisation of the model's single input and output."""
    interpreter = _interpreter(model)
    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]
    return {
        "input_shape": [int(v) for v in inp["shape"]],
        "input_dtype": np.dtype(inp["dtype"]).name,
        "input_scale": float(inp["quantization"][0]),
        "input_zero_point": int(inp["quantization"][1]),
        "output_shape": [int(v) for v in out["shape"]],
        "output_dtype": np.dtype(out["dtype"]).name,
        "output_scale": float(out["quantization"][0]),
        "output_zero_point": int(out["quantization"][1]),
    }


def list_ops(model: bytes) -> list[str]:
    """Operator names used by the model, e.g. ['CONV_2D', 'MEAN']."""
    interpreter = _interpreter(model)
    ops = {op["op_name"] for op in interpreter._get_ops_details()}
    ops.discard("DELEGATE")
    return sorted(ops)


def run_int8(model: bytes, gray: np.ndarray) -> np.ndarray:
    """Run grey images (N, H, W) uint8 through an int8 model; returns raw int8 outputs (N, C)."""
    interpreter = _interpreter(model)
    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]
    scale, zero_point = inp["quantization"]

    results = []
    for image in gray:
        tensor = preprocess.quantize(image, scale, zero_point)[np.newaxis, ..., np.newaxis]
        interpreter.set_tensor(inp["index"], tensor)
        interpreter.invoke()
        results.append(interpreter.get_tensor(out["index"])[0].copy())
    return np.stack(results) if results else np.zeros((0, out["shape"][-1]), dtype=np.int8)
