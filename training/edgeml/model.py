"""Model architecture: a small depthwise-separable CNN for 96x128 grey images.

Sized for a microcontroller: every layer maps to an operator the firmware
registers (CONV_2D, DEPTHWISE_CONV_2D, MEAN, FULLY_CONNECTED, SOFTMAX), and the
largest activation is the first one (48x64x8, about 25 KB as int8).
"""

from __future__ import annotations

import keras
from keras import layers

from . import config

# (output channels, stride) of each depthwise-separable block.
# Small datasets mean few optimiser steps: a shorter average lets the batch-norm
# statistics used at inference time catch up with training.
BN_MOMENTUM = 0.9

BLOCKS = ((16, 2), (32, 2), (48, 2), (64, 2))


def _conv_bn_relu(x, filters: int, kernel: int, stride: int):
    x = layers.Conv2D(filters, kernel, strides=stride, padding="same", use_bias=False)(x)
    x = layers.BatchNormalization(momentum=BN_MOMENTUM)(x)
    return layers.ReLU(max_value=6.0)(x)


def _separable_block(x, filters: int, stride: int):
    x = layers.DepthwiseConv2D(3, strides=stride, padding="same", use_bias=False)(x)
    x = layers.BatchNormalization(momentum=BN_MOMENTUM)(x)
    x = layers.ReLU(max_value=6.0)(x)
    return _conv_bn_relu(x, filters, 1, 1)


def build_model(
    num_classes: int = len(config.LABELS),
    input_height: int = config.INPUT_HEIGHT,
    input_width: int = config.INPUT_WIDTH,
    width: float = 1.0,
    dropout: float = 0.2,
) -> keras.Model:
    """Input is grey pixels scaled to [0, 1]; output is class probabilities."""
    inputs = keras.Input((input_height, input_width, config.INPUT_CHANNELS), name="image")
    x = _conv_bn_relu(inputs, max(4, int(8 * width)), 3, 2)
    for filters, stride in BLOCKS:
        x = _separable_block(x, max(4, int(filters * width)), stride)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(dropout)(x)
    x = layers.Dense(num_classes)(x)
    outputs = layers.Softmax(name="scores")(x)
    return keras.Model(inputs, outputs, name="edge_cnn")
