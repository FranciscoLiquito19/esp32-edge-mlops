#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"
#include "model_manifest.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint8_t num_labels;
    uint8_t top;                                 /* index of the highest score */
    int8_t q[MODEL_MANIFEST_MAX_LABELS];         /* raw int8 outputs, for parity checks */
    uint8_t prob[MODEL_MANIFEST_MAX_LABELS];     /* probability scaled to 0..255 */
    uint32_t decode_us;                          /* JPEG decode + preprocessing */
    uint32_t invoke_us;                          /* interpreter invoke */
    uint32_t gray_crc;                           /* CRC-32 of the preprocessed image */
} inference_result_t;

/**
 * Load the model from the model partition and prepare the interpreter.
 *
 * @return ESP_OK, ESP_ERR_NOT_FOUND if no model is installed, or another error
 *         if the model is damaged or does not match what this firmware supports.
 */
esp_err_t inference_init(void);

/** Manifest of the loaded model, or NULL if inference_init() has not succeeded. */
const model_manifest_t *inference_model(void);

/** Bytes of the tensor arena in use after allocation, 0 if not initialised. */
size_t inference_arena_used(void);

/** Decode a JPEG at 1/8 scale, preprocess it and run the model. */
esp_err_t inference_run_jpeg(const uint8_t *jpeg, size_t len, inference_result_t *out);

/** The preprocessed grey image from the last run (input_width x input_height). */
const uint8_t *inference_last_gray(size_t *len);

#ifdef __cplusplus
}
#endif
