#include "model_manifest.h"

#include <string.h>

/* Field offsets, see docs/MODEL_PACKAGE.md. */
#define OFF_MAGIC          0
#define OFF_HEADER_VERSION 4
#define OFF_HEADER_SIZE    6
#define OFF_MODEL_VERSION  8
#define OFF_PAYLOAD_SIZE   12
#define OFF_CREATED        16
#define OFF_INPUT_WIDTH    20
#define OFF_INPUT_HEIGHT   22
#define OFF_INPUT_CHANNELS 24
#define OFF_NUM_LABELS     25
#define OFF_FORMAT         26
#define OFF_SHA256         28
#define OFF_LABELS         60
#define OFF_NAME           188
#define OFF_CRC            252

static uint16_t rd16(const uint8_t *p)
{
    return (uint16_t)(p[0] | (p[1] << 8));
}

static uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* Copy a fixed-width, NUL-padded field into a NUL-terminated string. */
static void copy_text(char *dst, const uint8_t *src, size_t width)
{
    memcpy(dst, src, width);
    dst[width] = '\0';
}

uint32_t model_manifest_crc32(const uint8_t *data, size_t len)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; bit++) {
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
        }
    }
    return ~crc;
}

model_manifest_err_t model_manifest_parse(const uint8_t *buf, size_t len, model_manifest_t *out)
{
    if (buf == NULL || out == NULL || len < MODEL_MANIFEST_SIZE) {
        return MODEL_MANIFEST_ERR_TOO_SHORT;
    }
    if (memcmp(buf + OFF_MAGIC, "EMLM", 4) != 0) {
        return MODEL_MANIFEST_ERR_MAGIC;
    }
    if (rd16(buf + OFF_HEADER_VERSION) != MODEL_MANIFEST_VERSION ||
        rd16(buf + OFF_HEADER_SIZE) != MODEL_MANIFEST_SIZE) {
        return MODEL_MANIFEST_ERR_VERSION;
    }
    if (rd32(buf + OFF_CRC) != model_manifest_crc32(buf, OFF_CRC)) {
        return MODEL_MANIFEST_ERR_CRC;
    }

    memset(out, 0, sizeof(*out));
    out->header_version = rd16(buf + OFF_HEADER_VERSION);
    out->model_version = rd32(buf + OFF_MODEL_VERSION);
    out->payload_size = rd32(buf + OFF_PAYLOAD_SIZE);
    out->created_unix = rd32(buf + OFF_CREATED);
    out->input_width = rd16(buf + OFF_INPUT_WIDTH);
    out->input_height = rd16(buf + OFF_INPUT_HEIGHT);
    out->input_channels = buf[OFF_INPUT_CHANNELS];
    out->num_labels = buf[OFF_NUM_LABELS];
    out->format = buf[OFF_FORMAT];
    memcpy(out->sha256, buf + OFF_SHA256, MODEL_MANIFEST_SHA256_LEN);

    if (out->payload_size == 0 || out->input_width == 0 || out->input_height == 0 ||
        out->input_channels == 0 || out->num_labels == 0 ||
        out->num_labels > MODEL_MANIFEST_MAX_LABELS) {
        return MODEL_MANIFEST_ERR_FIELDS;
    }

    for (int i = 0; i < out->num_labels; i++) {
        copy_text(out->labels[i], buf + OFF_LABELS + i * MODEL_MANIFEST_LABEL_LEN,
                  MODEL_MANIFEST_LABEL_LEN);
        if (out->labels[i][0] == '\0') {
            return MODEL_MANIFEST_ERR_FIELDS;
        }
    }
    copy_text(out->name, buf + OFF_NAME, MODEL_MANIFEST_NAME_LEN);

    return MODEL_MANIFEST_OK;
}

const char *model_manifest_err_str(model_manifest_err_t err)
{
    switch (err) {
    case MODEL_MANIFEST_OK:          return "ok";
    case MODEL_MANIFEST_ERR_TOO_SHORT: return "too short";
    case MODEL_MANIFEST_ERR_MAGIC:   return "no model package found";
    case MODEL_MANIFEST_ERR_VERSION: return "unsupported header version";
    case MODEL_MANIFEST_ERR_CRC:     return "header checksum mismatch";
    case MODEL_MANIFEST_ERR_FIELDS:  return "invalid header fields";
    default:                         return "unknown";
    }
}
