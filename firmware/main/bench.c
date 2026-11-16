/*
 * Bench mode: model inference on fixed JPEGs, no hardware besides the chip.
 *
 * Output lines start with "BENCH", "GRAY" or "BENCH_DONE" and are parsed by
 * training/edgeml/bench_compare.py, which runs the same images through the
 * same model on the PC and compares.
 */
#include "bench.h"

#include <inttypes.h>
#include <stdio.h>

#include "esp_log.h"
#include "sdkconfig.h"

#include "inference.h"

#define GOLDEN(name) \
    extern const uint8_t name##_start[] asm("_binary_" #name "_jpg_start"); \
    extern const uint8_t name##_end[] asm("_binary_" #name "_jpg_end")

GOLDEN(g0);
GOLDEN(g1);
GOLDEN(g2);

static const char *TAG = "bench";

static void print_gray(const char *name)
{
#if CONFIG_APP_BENCH_DUMP_GRAY
    size_t len = 0;
    const uint8_t *gray = inference_last_gray(&len);
    for (size_t off = 0; off < len; off += 32) {
        printf("GRAY %s %u ", name, (unsigned)off);
        for (size_t i = off; i < off + 32 && i < len; i++) {
            printf("%02x", gray[i]);
        }
        printf("\n");
    }
#else
    (void)name;
#endif
}

static bool bench_image(const char *name, const uint8_t *start, const uint8_t *end,
                        inference_result_t *last)
{
    const size_t len = (size_t)(end - start);
    inference_result_t res;

    /* One untimed run first: the first invoke pays for cold caches. */
    if (inference_run_jpeg(start, len, &res) != ESP_OK) {
        printf("BENCH {\"image\":\"%s\",\"error\":true}\n", name);
        return false;
    }

    uint64_t decode_us = 0, invoke_us = 0;
    for (int i = 0; i < CONFIG_APP_BENCH_RUNS; i++) {
        if (inference_run_jpeg(start, len, &res) != ESP_OK) {
            printf("BENCH {\"image\":\"%s\",\"error\":true}\n", name);
            return false;
        }
        decode_us += res.decode_us;
        invoke_us += res.invoke_us;
    }

    printf("BENCH {\"image\":\"%s\",\"bytes\":%u,\"top\":%u,\"q\":[", name, (unsigned)len, res.top);
    for (int i = 0; i < res.num_labels; i++) {
        printf("%s%d", i ? "," : "", res.q[i]);
    }
    printf("],\"decode_us\":%" PRIu32 ",\"invoke_us\":%" PRIu32 ",\"gray_crc\":\"%08" PRIx32 "\"}\n",
           (uint32_t)(decode_us / CONFIG_APP_BENCH_RUNS), (uint32_t)(invoke_us / CONFIG_APP_BENCH_RUNS),
           res.gray_crc);

    print_gray(name);
    *last = res;
    return true;
}

bool bench_run(inference_result_t *last)
{
    esp_err_t err = inference_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "No usable model: %s", esp_err_to_name(err));
        printf("BENCH_DONE {\"ok\":false}\n");
        return false;
    }
    const model_manifest_t *m = inference_model();

    bool ok = bench_image("g0", g0_start, g0_end, last);
    ok = bench_image("g1", g1_start, g1_end, last) && ok;
    ok = bench_image("g2", g2_start, g2_end, last) && ok;

    printf("BENCH_DONE {\"ok\":%s,\"model_version\":%u,\"arena_used\":%u,\"runs\":%d}\n",
           ok ? "true" : "false", (unsigned)m->model_version, (unsigned)inference_arena_used(),
           CONFIG_APP_BENCH_RUNS);
    return ok;
}
