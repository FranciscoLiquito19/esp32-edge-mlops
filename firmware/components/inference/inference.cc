#include "inference.h"

#include <cstring>

#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "jpeg_decoder.h"
#include "sdkconfig.h"

#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/schema/schema_generated.h"

#include "model_store.h"
#include "preprocess.h"

namespace {

const char *TAG = "inference";

constexpr size_t kArenaBytes = static_cast<size_t>(CONFIG_APP_TENSOR_ARENA_KB) * 1024;

/*
 * Operators the firmware can run. training/tests/test_firmware_ops.py checks
 * that every exported model only uses operators from this list.
 */
constexpr int kNumOps = 12;

model_store_t s_store;
tflite::MicroInterpreter *s_interpreter = nullptr;
TfLiteTensor *s_input = nullptr;
TfLiteTensor *s_output = nullptr;
uint8_t *s_gray = nullptr;
size_t s_gray_len = 0;
bool s_ready = false;

void *alloc_prefer_psram(size_t bytes, size_t align)
{
    void *p = heap_caps_aligned_alloc(align, bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (p == nullptr) {
        p = heap_caps_aligned_alloc(align, bytes, MALLOC_CAP_8BIT);
    }
    return p;
}

tflite::MicroMutableOpResolver<kNumOps> &resolver()
{
    static tflite::MicroMutableOpResolver<kNumOps> r;
    static bool registered = false;
    if (!registered) {
        r.AddConv2D();
        r.AddDepthwiseConv2D();
        r.AddFullyConnected();
        r.AddMean();
        r.AddSoftmax();
        r.AddReshape();
        r.AddAveragePool2D();
        r.AddMaxPool2D();
        r.AddPad();
        r.AddAdd();
        r.AddQuantize();
        r.AddDequantize();
        registered = true;
    }
    return r;
}

} // namespace

esp_err_t inference_init(void)
{
    if (s_ready) {
        return ESP_OK;
    }

    esp_err_t err = model_store_open(&s_store);
    if (err != ESP_OK) {
        return err;
    }
    const model_manifest_t &m = s_store.manifest;

    if (m.format != MODEL_FORMAT_TFLITE_INT8 || m.input_channels != 1) {
        ESP_LOGE(TAG, "Unsupported model: format %u, %u channels", m.format, m.input_channels);
        return ESP_ERR_NOT_SUPPORTED;
    }

    const tflite::Model *model = tflite::GetModel(s_store.payload);
    if (model->version() != TFLITE_SCHEMA_VERSION) {
        ESP_LOGE(TAG, "TFLite schema %u, firmware supports %d",
                 static_cast<unsigned>(model->version()), TFLITE_SCHEMA_VERSION);
        return ESP_ERR_NOT_SUPPORTED;
    }

    uint8_t *arena = static_cast<uint8_t *>(alloc_prefer_psram(kArenaBytes, 16));
    if (arena == nullptr) {
        ESP_LOGE(TAG, "Cannot allocate %u KB tensor arena", static_cast<unsigned>(kArenaBytes / 1024));
        return ESP_ERR_NO_MEM;
    }

    s_interpreter = new tflite::MicroInterpreter(model, resolver(), arena, kArenaBytes);
    if (s_interpreter->AllocateTensors() != kTfLiteOk) {
        ESP_LOGE(TAG, "AllocateTensors failed (arena too small or unsupported operator)");
        return ESP_FAIL;
    }

    s_input = s_interpreter->input(0);
    s_output = s_interpreter->output(0);

    const bool input_ok = s_input->type == kTfLiteInt8 && s_input->dims->size == 4 &&
                          s_input->dims->data[1] == m.input_height &&
                          s_input->dims->data[2] == m.input_width &&
                          s_input->dims->data[3] == m.input_channels;
    const bool output_ok = s_output->type == kTfLiteInt8 &&
                           s_output->dims->data[s_output->dims->size - 1] == m.num_labels;
    if (!input_ok || !output_ok) {
        ESP_LOGE(TAG, "Model tensors do not match the manifest");
        return ESP_ERR_INVALID_ARG;
    }

    s_gray_len = static_cast<size_t>(m.input_width) * m.input_height;
    s_gray = static_cast<uint8_t *>(alloc_prefer_psram(s_gray_len, 4));
    if (s_gray == nullptr) {
        return ESP_ERR_NO_MEM;
    }

    ESP_LOGI(TAG, "Interpreter ready, arena %u of %u KB used",
             static_cast<unsigned>(s_interpreter->arena_used_bytes() / 1024),
             static_cast<unsigned>(kArenaBytes / 1024));
    s_ready = true;
    return ESP_OK;
}

const model_manifest_t *inference_model(void)
{
    return s_ready ? &s_store.manifest : nullptr;
}

size_t inference_arena_used(void)
{
    return s_ready ? s_interpreter->arena_used_bytes() : 0;
}

const uint8_t *inference_last_gray(size_t *len)
{
    if (len != nullptr) {
        *len = s_ready ? s_gray_len : 0;
    }
    return s_ready ? s_gray : nullptr;
}

esp_err_t inference_run_jpeg(const uint8_t *jpeg, size_t len, inference_result_t *out)
{
    if (!s_ready) {
        return ESP_ERR_INVALID_STATE;
    }
    if (jpeg == nullptr || out == nullptr || len == 0) {
        return ESP_ERR_INVALID_ARG;
    }
    const model_manifest_t &m = s_store.manifest;
    std::memset(out, 0, sizeof(*out));

    const int64_t t0 = esp_timer_get_time();

    /* Decode at 1/8 scale: one output pixel per 8x8 JPEG block. */
    esp_jpeg_image_cfg_t cfg = {};
    cfg.indata = const_cast<uint8_t *>(jpeg);
    cfg.indata_size = static_cast<uint32_t>(len);
    cfg.out_format = JPEG_IMAGE_FORMAT_RGB888;
    cfg.out_scale = JPEG_IMAGE_SCALE_1_8;

    esp_jpeg_image_output_t info = {};
    esp_err_t err = esp_jpeg_get_image_info(&cfg, &info);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Not a decodable JPEG");
        return err;
    }

    uint8_t *rgb = static_cast<uint8_t *>(alloc_prefer_psram(info.output_len, 4));
    if (rgb == nullptr) {
        return ESP_ERR_NO_MEM;
    }

    esp_jpeg_image_cfg_t dec = {};
    dec.indata = const_cast<uint8_t *>(jpeg);
    dec.indata_size = static_cast<uint32_t>(len);
    dec.outbuf = rgb;
    dec.outbuf_size = static_cast<uint32_t>(info.output_len);
    dec.out_format = JPEG_IMAGE_FORMAT_RGB888;
    dec.out_scale = JPEG_IMAGE_SCALE_1_8;

    esp_jpeg_image_output_t decoded = {};
    err = esp_jpeg_decode(&dec, &decoded);
    if (err != ESP_OK) {
        heap_caps_free(rgb);
        ESP_LOGE(TAG, "JPEG decode failed");
        return err;
    }

    const bool fits = preprocess_rgb888_to_gray(rgb, decoded.width, decoded.height, s_gray,
                                                m.input_width, m.input_height);
    heap_caps_free(rgb);
    if (!fits) {
        ESP_LOGE(TAG, "Image %ux%u at 1/8 scale is smaller than the model input %ux%u",
                 decoded.width, decoded.height, m.input_width, m.input_height);
        return ESP_ERR_INVALID_SIZE;
    }

    preprocess_quantize(s_gray, s_gray_len, s_input->params.scale, s_input->params.zero_point,
                        s_input->data.int8);

    const int64_t t1 = esp_timer_get_time();
    if (s_interpreter->Invoke() != kTfLiteOk) {
        ESP_LOGE(TAG, "Invoke failed");
        return ESP_FAIL;
    }
    const int64_t t2 = esp_timer_get_time();

    out->num_labels = m.num_labels;
    for (int i = 0; i < m.num_labels; i++) {
        const int8_t q = s_output->data.int8[i];
        out->q[i] = q;

        float p = (static_cast<float>(q) - s_output->params.zero_point) * s_output->params.scale;
        p = p < 0.0f ? 0.0f : (p > 1.0f ? 1.0f : p);
        out->prob[i] = static_cast<uint8_t>(p * 255.0f + 0.5f);

        if (q > out->q[out->top]) {
            out->top = static_cast<uint8_t>(i);
        }
    }
    out->decode_us = static_cast<uint32_t>(t1 - t0);
    out->invoke_us = static_cast<uint32_t>(t2 - t1);
    out->gray_crc = model_manifest_crc32(s_gray, s_gray_len);
    return ESP_OK;
}
