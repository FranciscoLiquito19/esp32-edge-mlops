#pragma once

#include <stdint.h>

#include "esp_err.h"
#include "model_manifest.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Must match firmware/partitions.csv. */
#define MODEL_STORE_PARTITION_TYPE    0x40
#define MODEL_STORE_PARTITION_SUBTYPE 0x00
#define MODEL_STORE_PARTITION_LABEL   "model"

typedef struct {
    model_manifest_t manifest;
    const uint8_t *payload; /* memory-mapped flash, valid for the life of the app */
} model_store_t;

/**
 * Map the model partition and validate what is in it: header, size against the
 * partition, and SHA-256 of the payload.
 *
 * @return ESP_OK with `out` filled in,
 *         ESP_ERR_NOT_FOUND if the partition is missing or holds no model,
 *         ESP_ERR_INVALID_CRC / ESP_ERR_INVALID_SIZE / ESP_ERR_NOT_SUPPORTED if the
 *         package is damaged or not understood.
 */
esp_err_t model_store_open(model_store_t *out);

#ifdef __cplusplus
}
#endif
