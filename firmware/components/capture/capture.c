#include "capture.h"

#include <string.h>

#include "esp_camera.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sdkconfig.h"

#include "board_pins.h"

static const char *TAG = "capture";

static uint32_t s_init_ms;
static bool s_started;

esp_err_t capture_init(void)
{
    const camera_config_t cfg = {
        .pin_pwdn = BOARD_CAM_PIN_PWDN,
        .pin_reset = BOARD_CAM_PIN_RESET,
        .pin_xclk = BOARD_CAM_PIN_XCLK,
        .pin_sccb_sda = BOARD_CAM_PIN_SIOD,
        .pin_sccb_scl = BOARD_CAM_PIN_SIOC,
        .pin_d7 = BOARD_CAM_PIN_D7,
        .pin_d6 = BOARD_CAM_PIN_D6,
        .pin_d5 = BOARD_CAM_PIN_D5,
        .pin_d4 = BOARD_CAM_PIN_D4,
        .pin_d3 = BOARD_CAM_PIN_D3,
        .pin_d2 = BOARD_CAM_PIN_D2,
        .pin_d1 = BOARD_CAM_PIN_D1,
        .pin_d0 = BOARD_CAM_PIN_D0,
        .pin_vsync = BOARD_CAM_PIN_VSYNC,
        .pin_href = BOARD_CAM_PIN_HREF,
        .pin_pclk = BOARD_CAM_PIN_PCLK,
        .xclk_freq_hz = BOARD_CAM_XCLK_HZ,
        .ledc_timer = LEDC_TIMER_0,
        .ledc_channel = LEDC_CHANNEL_0,
        .pixel_format = PIXFORMAT_JPEG,
        .frame_size = FRAMESIZE_XGA,
        .jpeg_quality = CONFIG_APP_CAPTURE_JPEG_QUALITY,
        .fb_count = 1,
        .fb_location = CAMERA_FB_IN_PSRAM,
        .grab_mode = CAMERA_GRAB_WHEN_EMPTY,
    };

    int64_t t0 = esp_timer_get_time();
    esp_err_t err = esp_camera_init(&cfg);
    s_init_ms = (uint32_t)((esp_timer_get_time() - t0) / 1000);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Camera init failed: %s", esp_err_to_name(err));
        return err;
    }
    s_started = true;
    return ESP_OK;
}

esp_err_t capture_grab(capture_frame_t *out)
{
    if (!s_started) {
        return ESP_ERR_INVALID_STATE;
    }
    memset(out, 0, sizeof(*out));

    int64_t t0 = esp_timer_get_time();

    for (int i = 0; i < CONFIG_APP_CAPTURE_WARMUP_FRAMES; i++) {
        camera_fb_t *discard = esp_camera_fb_get();
        if (discard == NULL) {
            ESP_LOGE(TAG, "Warm-up frame %d failed", i);
            return ESP_FAIL;
        }
        esp_camera_fb_return(discard);
    }

    camera_fb_t *fb = esp_camera_fb_get();
    if (fb == NULL) {
        ESP_LOGE(TAG, "Frame capture failed");
        return ESP_FAIL;
    }
    if (fb->format != PIXFORMAT_JPEG || fb->len < 4) {
        ESP_LOGE(TAG, "Unexpected frame: format %d, %u bytes", (int)fb->format, (unsigned)fb->len);
        esp_camera_fb_return(fb);
        return ESP_FAIL;
    }

    out->jpeg = fb->buf;
    out->len = fb->len;
    out->width = (uint16_t)fb->width;
    out->height = (uint16_t)fb->height;
    out->init_ms = s_init_ms;
    out->grab_ms = (uint32_t)((esp_timer_get_time() - t0) / 1000);
    out->priv = fb;

    ESP_LOGI(TAG, "Frame %ux%u, %u bytes (init %u ms, grab %u ms)",
             (unsigned)out->width, (unsigned)out->height, (unsigned)out->len,
             (unsigned)out->init_ms, (unsigned)out->grab_ms);
    return ESP_OK;
}

void capture_release(capture_frame_t *frame)
{
    if (frame != NULL && frame->priv != NULL) {
        esp_camera_fb_return((camera_fb_t *)frame->priv);
        frame->priv = NULL;
        frame->jpeg = NULL;
        frame->len = 0;
    }
}

void capture_deinit(void)
{
    if (s_started) {
        esp_camera_deinit();
        s_started = false;
    }
}
