"""Image preprocessing, mirrored from firmware/components/inference/preprocess.c.

The device decodes the camera JPEG at 1/8 scale (one pixel per 8x8 block),
converts RGB to grey with an integer formula and centre-crops to the model
input. This module does the same on the PC so that training sees what the
device will see. The JPEG decoders differ (libjpeg here, TJpgDec on the
device); tools that compare the two report how large that difference is.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from . import config


def rgb_to_gray(rgb: np.ndarray) -> np.ndarray:
    """uint8 HxWx3 -> uint8 HxW, with the firmware's integer weights."""
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise ValueError("expected a uint8 HxWx3 array")
    c = rgb.astype(np.uint32)
    gray = (77 * c[..., 0] + 150 * c[..., 1] + 29 * c[..., 2] + 128) >> 8
    return gray.astype(np.uint8)


def center_crop(image: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    h, w = image.shape[:2]
    if h < out_h or w < out_w:
        raise ValueError(f"image {w}x{h} is smaller than the requested {out_w}x{out_h}")
    y0 = (h - out_h) // 2
    x0 = (w - out_w) // 2
    return image[y0 : y0 + out_h, x0 : x0 + out_w]


def decode_eighth(jpeg: bytes) -> np.ndarray:
    """Decode a JPEG at 1/8 scale to uint8 RGB."""
    img = Image.open(io.BytesIO(jpeg))
    if img.format != "JPEG":
        raise ValueError("not a JPEG")
    full_w, full_h = img.size
    # draft() selects the decoder's DCT scaling; asking for 1/8 of the size gets 1/8.
    img.draft("RGB", (max(1, full_w // 8), max(1, full_h // 8)))
    rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
    expected = (-(-full_h // 8), -(-full_w // 8))
    if rgb.shape[:2] != expected:
        raise ValueError(f"decoder returned {rgb.shape[:2]}, expected {expected}")
    return rgb


def jpeg_to_gray(jpeg: bytes, out_w: int = config.INPUT_WIDTH, out_h: int = config.INPUT_HEIGHT) -> np.ndarray:
    """Full device preprocessing: JPEG bytes -> uint8 grey (out_h, out_w)."""
    return center_crop(rgb_to_gray(decode_eighth(jpeg)), out_h, out_w)


def quantize(gray: np.ndarray, scale: float, zero_point: int) -> np.ndarray:
    """Grey pixels -> int8 input tensor values, as the firmware does it.

    The firmware uses single-precision floats and rounds half away from zero.
    """
    v = np.arange(256, dtype=np.float32) / np.float32(255.0) / np.float32(scale)
    rounded = np.where(v >= 0, np.floor(v + np.float32(0.5)), np.ceil(v - np.float32(0.5)))
    lut = np.clip(rounded.astype(np.int64) + int(zero_point), -128, 127).astype(np.int8)
    return lut[gray]
