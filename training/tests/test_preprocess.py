import io

import numpy as np
import pytest
from PIL import Image

from edgeml import config, preprocess, synth


def test_gray_formula_known_values():
    rgb = np.array([[[0, 0, 0], [255, 255, 255], [255, 0, 0], [0, 255, 0], [0, 0, 255]]], dtype=np.uint8)
    # (77 R + 150 G + 29 B + 128) >> 8
    assert preprocess.rgb_to_gray(rgb).tolist() == [[0, 255, 77, 149, 29]]


def test_center_crop_takes_the_middle():
    image = np.arange(6 * 8).reshape(6, 8)
    assert preprocess.center_crop(image, 2, 4).tolist() == [[18, 19, 20, 21], [26, 27, 28, 29]]


def test_center_crop_refuses_to_enlarge():
    with pytest.raises(ValueError):
        preprocess.center_crop(np.zeros((4, 4)), 5, 4)


def test_capture_becomes_model_input_without_resampling():
    jpeg = synth.render("person", np.random.default_rng(1))
    assert preprocess.decode_eighth(jpeg).shape == (config.INPUT_HEIGHT, config.INPUT_WIDTH, 3)
    gray = preprocess.jpeg_to_gray(jpeg)
    assert gray.shape == (config.INPUT_HEIGHT, config.INPUT_WIDTH)
    assert gray.dtype == np.uint8


def test_eighth_scale_is_the_block_average():
    """Each output pixel should be close to the mean of its 8x8 block."""
    rng = np.random.default_rng(2)
    blocks = rng.integers(30, 220, size=(12, 16), dtype=np.uint8)
    full = np.kron(blocks, np.ones((8, 8), dtype=np.uint8))
    buf = io.BytesIO()
    Image.fromarray(np.stack([full] * 3, axis=-1), "RGB").save(buf, format="JPEG", quality=95, subsampling=0)
    gray = preprocess.jpeg_to_gray(buf.getvalue(), out_w=16, out_h=12)
    assert np.abs(gray.astype(int) - blocks.astype(int)).max() <= 3


def test_smaller_image_is_rejected():
    buf = io.BytesIO()
    Image.new("RGB", (320, 240)).save(buf, format="JPEG")
    with pytest.raises(ValueError):
        preprocess.jpeg_to_gray(buf.getvalue())


def test_png_is_rejected():
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768)).save(buf, format="PNG")
    with pytest.raises(ValueError):
        preprocess.decode_eighth(buf.getvalue())


def test_quantize_with_the_usual_input_scale():
    """Trained on pixel/255 with scale 1/255 and zero point -128: q = pixel - 128."""
    gray = np.arange(256, dtype=np.uint8)
    q = preprocess.quantize(gray, 1 / 255, -128)
    assert q.dtype == np.int8
    assert q.tolist() == [v - 128 for v in range(256)]


def test_quantize_clamps():
    q = preprocess.quantize(np.array([0, 255], dtype=np.uint8), 1 / 1000, 0)
    assert q.tolist() == [0, 127]
