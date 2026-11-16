/*
 * M0 - board bring-up.
 *
 * Confirms that the board matches what the rest of the project assumes:
 * 8 MB flash, 8 MB PSRAM and the custom partition table with a model slot.
 */
#include <stdbool.h>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "board_selftest.h"

#define PSRAM_TEST_BYTES (1024 * 1024)

static const char *TAG = "main";

void app_main(void)
{
    ESP_LOGI(TAG, "esp32-edge-mlops - M0 board bring-up");

    board_print_info();
    board_print_partitions();

    bool psram_ok = board_psram_selftest(PSRAM_TEST_BYTES);
    bool model_ok = board_model_partition_present();

    ESP_LOGI(TAG, "PSRAM self-test (1 MB): %s", psram_ok ? "PASS" : "FAIL");
    ESP_LOGI(TAG, "Model partition:        %s", model_ok ? "PASS" : "FAIL");

    if (psram_ok && model_ok) {
        ESP_LOGI(TAG, "M0 RESULT: PASS");
    } else {
        ESP_LOGE(TAG, "M0 RESULT: FAIL - see docs/ROADMAP.md");
    }

    while (true) {
        vTaskDelay(pdMS_TO_TICKS(10000));
    }
}
