#include "preprocess.h"

#include <math.h>

bool preprocess_rgb888_to_gray(const uint8_t *rgb, uint16_t w, uint16_t h,
                               uint8_t *gray, uint16_t out_w, uint16_t out_h)
{
    if (rgb == NULL || gray == NULL || w < out_w || h < out_h) {
        return false;
    }

    const uint16_t x0 = (uint16_t)((w - out_w) / 2);
    const uint16_t y0 = (uint16_t)((h - out_h) / 2);

    for (uint16_t y = 0; y < out_h; y++) {
        const uint8_t *src = rgb + ((size_t)(y + y0) * w + x0) * 3;
        uint8_t *dst = gray + (size_t)y * out_w;
        for (uint16_t x = 0; x < out_w; x++) {
            const uint32_t r = src[0], g = src[1], b = src[2];
            dst[x] = (uint8_t)((77u * r + 150u * g + 29u * b + 128u) >> 8);
            src += 3;
        }
    }
    return true;
}

void preprocess_quantize(const uint8_t *gray, size_t n, float scale, int zero_point, int8_t *out)
{
    /* Only 256 possible inputs: build the mapping once per call. */
    int8_t lut[256];
    for (int v = 0; v < 256; v++) {
        long q = lroundf(((float)v / 255.0f) / scale) + zero_point;
        if (q < -128) {
            q = -128;
        } else if (q > 127) {
            q = 127;
        }
        lut[v] = (int8_t)q;
    }
    for (size_t i = 0; i < n; i++) {
        out[i] = lut[gray[i]];
    }
}
