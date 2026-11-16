#include "board_selftest.h"

#include <inttypes.h>
#include <stdint.h>

#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_heap_caps.h"
#include "esp_idf_version.h"
#include "esp_log.h"
#include "esp_partition.h"
#include "esp_system.h"
#include "sdkconfig.h"

#if CONFIG_SPIRAM
#include "esp_psram.h"
#endif

static const char *TAG = "board";

static const char *reset_reason_str(esp_reset_reason_t reason)
{
    switch (reason) {
    case ESP_RST_POWERON:   return "power-on";
    case ESP_RST_EXT:       return "external pin";
    case ESP_RST_SW:        return "software";
    case ESP_RST_PANIC:     return "panic";
    case ESP_RST_INT_WDT:   return "interrupt watchdog";
    case ESP_RST_TASK_WDT:  return "task watchdog";
    case ESP_RST_WDT:       return "other watchdog";
    case ESP_RST_DEEPSLEEP: return "deep-sleep wake";
    case ESP_RST_BROWNOUT:  return "brownout";
    case ESP_RST_USB:       return "USB";
    default:                return "unknown";
    }
}

static size_t psram_size_bytes(void)
{
#if CONFIG_SPIRAM
    if (esp_psram_is_initialized()) {
        return esp_psram_get_size();
    }
#endif
    return 0;
}

void board_print_info(void)
{
    esp_chip_info_t chip;
    esp_chip_info(&chip);

    ESP_LOGI(TAG, "ESP-IDF %s", esp_get_idf_version());
    ESP_LOGI(TAG, "Chip: %s, %d cores, silicon rev v%d.%d",
             CONFIG_IDF_TARGET, chip.cores, chip.revision / 100, chip.revision % 100);
    ESP_LOGI(TAG, "Reset reason: %s", reset_reason_str(esp_reset_reason()));

    uint32_t flash_bytes = 0;
    if (esp_flash_get_size(NULL, &flash_bytes) == ESP_OK) {
        ESP_LOGI(TAG, "Flash: %" PRIu32 " MB (%s)", flash_bytes / (1024 * 1024),
                 (chip.features & CHIP_FEATURE_EMB_FLASH) ? "embedded" : "external");
    } else {
        ESP_LOGE(TAG, "Flash: could not read size");
    }

    size_t psram = psram_size_bytes();
    if (psram > 0) {
        ESP_LOGI(TAG, "PSRAM: %u MB", (unsigned)(psram / (1024 * 1024)));
    } else {
        ESP_LOGW(TAG, "PSRAM: not detected");
    }

    ESP_LOGI(TAG, "Free heap: internal %u KB, PSRAM %u KB",
             (unsigned)(heap_caps_get_free_size(MALLOC_CAP_INTERNAL) / 1024),
             (unsigned)(heap_caps_get_free_size(MALLOC_CAP_SPIRAM) / 1024));
}

void board_print_partitions(void)
{
    ESP_LOGI(TAG, "Partition table:");
    esp_partition_iterator_t it =
        esp_partition_find(ESP_PARTITION_TYPE_ANY, ESP_PARTITION_SUBTYPE_ANY, NULL);
    for (; it != NULL; it = esp_partition_next(it)) {
        const esp_partition_t *p = esp_partition_get(it);
        ESP_LOGI(TAG, "  %-10s type 0x%02x sub 0x%02x  offset 0x%06" PRIx32 "  size %4" PRIu32 " KB",
                 p->label, p->type, p->subtype, p->address, p->size / 1024);
    }
    /* esp_partition_next() releases the iterator when it reaches the end. */
}

bool board_psram_selftest(size_t bytes)
{
    if (psram_size_bytes() == 0) {
        return false;
    }

    uint8_t *buf = heap_caps_malloc(bytes, MALLOC_CAP_SPIRAM);
    if (buf == NULL) {
        ESP_LOGE(TAG, "PSRAM self-test: could not allocate %u bytes", (unsigned)bytes);
        return false;
    }

    /* Address-dependent pattern, so stuck or shorted address lines show up. */
    for (size_t i = 0; i < bytes; i++) {
        buf[i] = (uint8_t)(i ^ (i >> 8) ^ (i >> 16));
    }

    size_t errors = 0;
    for (size_t i = 0; i < bytes; i++) {
        if (buf[i] != (uint8_t)(i ^ (i >> 8) ^ (i >> 16))) {
            errors++;
        }
    }
    heap_caps_free(buf);

    if (errors > 0) {
        ESP_LOGE(TAG, "PSRAM self-test: %u of %u bytes wrong", (unsigned)errors, (unsigned)bytes);
        return false;
    }
    return true;
}

bool board_model_partition_present(void)
{
    return esp_partition_find_first(BOARD_MODEL_PARTITION_TYPE,
                                    BOARD_MODEL_PARTITION_SUBTYPE,
                                    BOARD_MODEL_PARTITION_LABEL) != NULL;
}
