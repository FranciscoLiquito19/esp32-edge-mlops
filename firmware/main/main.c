/*
 * esp32-edge-mlops: motion-triggered camera node.
 *
 * Each wake-up is one pass through app_main(): find out why we woke, handle
 * it, go back to deep sleep. State that must survive deep sleep lives in RTC
 * memory. See docs/ARCHITECTURE.md for the event cycle.
 */
#include <inttypes.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>

#include "esp_app_desc.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

#include "bench.h"
#include "board_selftest.h"
#include "capture.h"
#include "inference.h"
#include "power.h"
#include "uplink.h"

#define STATE_MAGIC      0x454D4C31u /* "EML1" */
#define PSRAM_TEST_BYTES (1024 * 1024)
#define META_MAX         1024
#define NO_LABEL         0xFF

#if CONFIG_APP_MODE_INFER
#define MODE_NAME "infer"
#elif CONFIG_APP_MODE_BENCH
#define MODE_NAME "bench"
#else
#define MODE_NAME "collect"
#endif

static const char *TAG = "main";

/* Survives deep sleep, lost on power-off or reset. */
typedef struct {
    uint32_t magic;
    uint32_t session; /* random per power cycle; with seq it names an event */
    uint32_t seq;     /* events since power-on */
    uint32_t dropped; /* events that could not be uploaded since the last success */
} app_state_t;

static RTC_DATA_ATTR app_state_t s_state;

typedef struct {
    power_wake_t wake;
    bool have_frame;
    capture_frame_t frame;
    bool have_result;
    inference_result_t result;
    uint32_t wifi_ms;
    bool send_image;
} event_t;

static void state_start_session(void)
{
    s_state.magic = STATE_MAGIC;
    s_state.session = esp_random();
    s_state.seq = 0;
    s_state.dropped = 0;
}

static bool selftest(void)
{
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
    return psram_ok && model_ok;
}

#if CONFIG_APP_MODE_INFER
/* Index of the "nothing" class in the loaded model, or NO_LABEL. */
static uint8_t nothing_index(const model_manifest_t *m)
{
    for (uint8_t i = 0; i < m->num_labels; i++) {
        if (strcmp(m->labels[i], "nothing") == 0) {
            return i;
        }
    }
    return NO_LABEL;
}

/* Run the model and decide whether the image itself is worth uploading. */
static void classify(event_t *ev)
{
    ev->send_image = true; /* without a verdict, keep the evidence */

    if (inference_init() != ESP_OK) {
        ESP_LOGW(TAG, "No usable model, behaving as collect mode");
        return;
    }
    if (inference_run_jpeg(ev->frame.jpeg, ev->frame.len, &ev->result) != ESP_OK) {
        return;
    }
    ev->have_result = true;

    const model_manifest_t *m = inference_model();
    const inference_result_t *r = &ev->result;
    const unsigned confidence_pct = (unsigned)r->prob[r->top] * 100u / 255u;

    const bool is_nothing = r->top == nothing_index(m);
    const bool unsure = confidence_pct < CONFIG_APP_INFER_UPLOAD_BELOW_PCT;
    const bool sampled = CONFIG_APP_INFER_SAMPLE_EVERY > 0 &&
                         (s_state.seq % CONFIG_APP_INFER_SAMPLE_EVERY) == 0;

    ev->send_image = !is_nothing || unsure || sampled;

    ESP_LOGI(TAG, "Result: %s (%u%%), decode %" PRIu32 " us, invoke %" PRIu32 " us, image %s",
             m->labels[r->top], confidence_pct, r->decode_us, r->invoke_us,
             ev->send_image ? "kept" : "dropped");
}
#endif

/* Append formatted text, keeping track of truncation. */
static bool appendf(char *buf, size_t size, size_t *len, const char *fmt, ...)
    __attribute__((format(printf, 4, 5)));

static bool appendf(char *buf, size_t size, size_t *len, const char *fmt, ...)
{
    if (*len >= size) {
        return false;
    }
    va_list args;
    va_start(args, fmt);
    int n = vsnprintf(buf + *len, size - *len, fmt, args);
    va_end(args);
    if (n < 0 || (size_t)n >= size - *len) {
        *len = size;
        return false;
    }
    *len += (size_t)n;
    return true;
}

/* Single-line JSON metadata for one event (docs/PROTOCOL.md). */
static bool build_meta(char *buf, size_t size, const event_t *ev)
{
    uint8_t mac[6] = { 0 };
    esp_read_mac(mac, ESP_MAC_WIFI_STA);

    struct timeval now;
    gettimeofday(&now, NULL);
    /* The clock is only meaningful after the server has set it once. */
    const int64_t ts = now.tv_sec > 1700000000 ? (int64_t)now.tv_sec : 0;

    size_t len = 0;
    appendf(buf, size, &len,
            "{\"v\":1,\"device\":\"esp32s3-%02x%02x%02x\",\"fw\":\"%s\",\"session\":\"%08" PRIx32 "\","
            "\"seq\":%" PRIu32 ",\"wake\":\"%s\",\"mode\":\"%s\",\"ts\":%" PRId64 ",\"dropped\":%" PRIu32 ","
            "\"rssi\":%d,\"image\":%s",
            mac[3], mac[4], mac[5], esp_app_get_description()->version, s_state.session,
            s_state.seq, power_wake_str(ev->wake), MODE_NAME, ts, s_state.dropped,
            uplink_rssi(), (ev->have_frame && ev->send_image) ? "true" : "false");

    if (ev->have_frame) {
        appendf(buf, size, &len, ",\"frame\":{\"w\":%u,\"h\":%u,\"bytes\":%u}",
                (unsigned)ev->frame.width, (unsigned)ev->frame.height, (unsigned)ev->frame.len);
    }

    appendf(buf, size, &len, ",\"t_ms\":{\"cam_init\":%" PRIu32 ",\"grab\":%" PRIu32 ",\"wifi\":%" PRIu32
            ",\"awake\":%" PRId64 "}",
            ev->frame.init_ms, ev->frame.grab_ms, ev->wifi_ms, esp_timer_get_time() / 1000);

    if (ev->have_result) {
        const model_manifest_t *m = inference_model();
        const inference_result_t *r = &ev->result;
        appendf(buf, size, &len, ",\"model\":{\"version\":%" PRIu32 ",\"label\":\"%s\",\"top\":%u,\"q\":[",
                m->model_version, m->labels[r->top], (unsigned)r->top);
        for (int i = 0; i < r->num_labels; i++) {
            appendf(buf, size, &len, "%s%d", i ? "," : "", (int)r->q[i]);
        }
        appendf(buf, size, &len, "],\"decode_us\":%" PRIu32 ",\"invoke_us\":%" PRIu32 "}",
                r->decode_us, r->invoke_us);
    }

    return appendf(buf, size, &len, "}");
}

#if !CONFIG_APP_MODE_BENCH
static void upload(event_t *ev)
{
    static char meta[META_MAX];

    const int64_t t0 = esp_timer_get_time();
    esp_err_t err = uplink_wait_connected(CONFIG_APP_WIFI_CONNECT_TIMEOUT_MS);
    ev->wifi_ms = (uint32_t)((esp_timer_get_time() - t0) / 1000);

    if (err == ESP_OK) {
        if (!build_meta(meta, sizeof(meta), ev)) {
            ESP_LOGE(TAG, "Metadata does not fit in %d bytes", META_MAX);
            err = ESP_ERR_INVALID_SIZE;
        }
    }

    if (err == ESP_OK) {
        const bool with_image = ev->have_frame && ev->send_image;
        int status = 0;
        int64_t server_time = 0;

        err = uplink_post_event(meta, with_image ? ev->frame.jpeg : NULL,
                                with_image ? ev->frame.len : 0, &status, &server_time);
        if (err == ESP_OK) {
            ESP_LOGI(TAG, "Uploaded event %08" PRIx32 "/%" PRIu32 " (HTTP %d, %s image)",
                     s_state.session, s_state.seq, status, with_image ? "with" : "no");
            if (server_time > 0) {
                const struct timeval tv = { .tv_sec = (time_t)server_time };
                settimeofday(&tv, NULL);
            }
        }
    }

    if (err == ESP_OK) {
        s_state.dropped = 0;
    } else {
        s_state.dropped++;
        ESP_LOGW(TAG, "Event not uploaded (%" PRIu32 " lost since the last success)", s_state.dropped);
    }
}

static void run_event(power_wake_t wake)
{
    event_t ev = { .wake = wake, .send_image = true };
    const bool online = uplink_is_configured();

    /* Start joining the network first so it overlaps with the camera start-up. */
    if (online && uplink_start() != ESP_OK) {
        ESP_LOGW(TAG, "Wi-Fi did not start");
    }

    if (capture_init() == ESP_OK && capture_grab(&ev.frame) == ESP_OK) {
        ev.have_frame = true;
    }

#if CONFIG_APP_MODE_INFER
    if (ev.have_frame) {
        classify(&ev);
    }
#endif

    if (online) {
        upload(&ev);
    } else {
        ESP_LOGW(TAG, "Uplink not configured (idf.py menuconfig): event measured and discarded");
    }

    capture_release(&ev.frame);
    capture_deinit();
    uplink_stop();

    s_state.seq++;
    ESP_LOGI(TAG, "Event done, awake for %" PRId64 " ms", esp_timer_get_time() / 1000);
}

#endif /* !CONFIG_APP_MODE_BENCH */

void app_main(void)
{
    const power_wake_t wake = power_wake_reason();
    power_init();

    if (wake == POWER_WAKE_COLD_BOOT || s_state.magic != STATE_MAGIC) {
        ESP_LOGI(TAG, "esp32-edge-mlops %s, mode: " MODE_NAME, esp_app_get_description()->version);
        state_start_session();
        selftest();

#if CONFIG_APP_MODE_BENCH
        /*
         * Also print the metadata an event with this result would carry, so the
         * exact bytes the firmware sends can be checked against the service.
         */
        event_t ev = { .wake = POWER_WAKE_PIR, .have_frame = true, .send_image = false,
                       .frame = { .width = CAPTURE_WIDTH, .height = CAPTURE_HEIGHT, .len = 98765 } };
        ev.have_result = bench_run(&ev.result);
        static char meta[META_MAX];
        if (build_meta(meta, sizeof(meta), &ev)) {
            printf("META %s\n", meta);
        }
        while (true) {
            vTaskDelay(pdMS_TO_TICKS(10000));
        }
#else
        /* One event straight away, so a fresh flash shows the whole chain working. */
        run_event(POWER_WAKE_COLD_BOOT);
        power_sleep_for(CONFIG_APP_PIR_WARMUP_S);
#endif
    }

#if !CONFIG_APP_MODE_BENCH
    if (wake == POWER_WAKE_PIR) {
        run_event(wake);
    }

    /* PIR wake handled, or a timer wake that only re-checks the sensor. */
    power_sleep_auto();
#endif
}
