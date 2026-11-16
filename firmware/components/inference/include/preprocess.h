#pragma once

/*
 * Image preprocessing shared by the device and (re-implemented in Python) the
 * training pipeline. Keep this file and training/edgeml/preprocess.py in step:
 * tests compare the two. No ESP-IDF dependencies.
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Convert an RGB888 image to 8-bit grey, centre-cropping to out_w x out_h.
 *
 * grey = (77 R + 150 G + 29 B + 128) >> 8
 *
 * @return false if the source is smaller than the requested output.
 */
bool preprocess_rgb888_to_gray(const uint8_t *rgb, uint16_t w, uint16_t h,
                               uint8_t *gray, uint16_t out_w, uint16_t out_h);

/**
 * Quantise grey pixels into an int8 input tensor.
 *
 * The model is trained on pixel / 255, so q = round(pixel / 255 / scale) + zero_point,
 * clamped to the int8 range.
 */
void preprocess_quantize(const uint8_t *gray, size_t n, float scale, int zero_point, int8_t *out);

#ifdef __cplusplus
}
#endif
