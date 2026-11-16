#include "model_store.h"

#include <string.h>

#include "esp_log.h"
#include "esp_partition.h"
#include "mbedtls/sha256.h"

static const char *TAG = "model_store";

esp_err_t model_store_open(model_store_t *out)
{
    const esp_partition_t *part = esp_partition_find_first(MODEL_STORE_PARTITION_TYPE,
                                                           MODEL_STORE_PARTITION_SUBTYPE,
                                                           MODEL_STORE_PARTITION_LABEL);
    if (part == NULL) {
        ESP_LOGE(TAG, "No '%s' partition", MODEL_STORE_PARTITION_LABEL);
        return ESP_ERR_NOT_FOUND;
    }

    const void *mapped = NULL;
    esp_partition_mmap_handle_t handle;
    esp_err_t err = esp_partition_mmap(part, 0, part->size, ESP_PARTITION_MMAP_DATA, &mapped, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "mmap failed: %s", esp_err_to_name(err));
        return err;
    }
    const uint8_t *base = (const uint8_t *)mapped;

    model_manifest_err_t merr = model_manifest_parse(base, part->size, &out->manifest);
    if (merr != MODEL_MANIFEST_OK) {
        ESP_LOGW(TAG, "Model partition: %s", model_manifest_err_str(merr));
        esp_partition_munmap(handle);
        switch (merr) {
        case MODEL_MANIFEST_ERR_MAGIC:   return ESP_ERR_NOT_FOUND;
        case MODEL_MANIFEST_ERR_VERSION: return ESP_ERR_NOT_SUPPORTED;
        default:                         return ESP_ERR_INVALID_CRC;
        }
    }

    if (out->manifest.payload_size > part->size - MODEL_MANIFEST_SIZE) {
        ESP_LOGE(TAG, "Payload size %u does not fit the partition", (unsigned)out->manifest.payload_size);
        esp_partition_munmap(handle);
        return ESP_ERR_INVALID_SIZE;
    }

    const uint8_t *payload = base + MODEL_MANIFEST_SIZE;
    uint8_t digest[MODEL_MANIFEST_SHA256_LEN];
    if (mbedtls_sha256(payload, out->manifest.payload_size, digest, 0) != 0 ||
        memcmp(digest, out->manifest.sha256, sizeof(digest)) != 0) {
        ESP_LOGE(TAG, "Payload SHA-256 mismatch");
        esp_partition_munmap(handle);
        return ESP_ERR_INVALID_CRC;
    }

    /* The mapping is kept on purpose: the model is executed in place from flash. */
    out->payload = payload;
    ESP_LOGI(TAG, "Model v%u '%s', %u bytes, input %ux%ux%u, %u labels",
             (unsigned)out->manifest.model_version, out->manifest.name,
             (unsigned)out->manifest.payload_size, (unsigned)out->manifest.input_width,
             (unsigned)out->manifest.input_height, (unsigned)out->manifest.input_channels,
             (unsigned)out->manifest.num_labels);
    return ESP_OK;
}
