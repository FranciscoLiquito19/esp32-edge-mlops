#pragma once

/*
 * Model package header ("manifest").
 *
 * A model package is a 256-byte little-endian header followed by the model
 * payload. The layout is documented in docs/MODEL_PACKAGE.md and written by
 * training/edgeml/package.py. This file has no ESP-IDF dependencies so the
 * same code is compiled and tested on a PC.
 */

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MODEL_MANIFEST_SIZE        256
#define MODEL_MANIFEST_VERSION     1
#define MODEL_MANIFEST_MAX_LABELS  8
#define MODEL_MANIFEST_LABEL_LEN   16
#define MODEL_MANIFEST_NAME_LEN    32
#define MODEL_MANIFEST_SHA256_LEN  32

/* Payload formats. */
#define MODEL_FORMAT_TFLITE_INT8   1

typedef enum {
    MODEL_MANIFEST_OK = 0,
    MODEL_MANIFEST_ERR_TOO_SHORT,
    MODEL_MANIFEST_ERR_MAGIC,   /* not a model package (for example an erased partition) */
    MODEL_MANIFEST_ERR_VERSION, /* header version or size this firmware does not know */
    MODEL_MANIFEST_ERR_CRC,     /* header corrupted */
    MODEL_MANIFEST_ERR_FIELDS,  /* header intact but values out of range */
} model_manifest_err_t;

typedef struct {
    uint16_t header_version;
    uint32_t model_version;
    uint32_t payload_size;
    uint32_t created_unix;
    uint16_t input_width;
    uint16_t input_height;
    uint8_t input_channels;
    uint8_t num_labels;
    uint8_t format;
    uint8_t sha256[MODEL_MANIFEST_SHA256_LEN];
    char labels[MODEL_MANIFEST_MAX_LABELS][MODEL_MANIFEST_LABEL_LEN + 1];
    char name[MODEL_MANIFEST_NAME_LEN + 1];
} model_manifest_t;

/** Parse and validate a header. `len` is the number of readable bytes at `buf`. */
model_manifest_err_t model_manifest_parse(const uint8_t *buf, size_t len, model_manifest_t *out);

const char *model_manifest_err_str(model_manifest_err_t err);

/** CRC-32 (IEEE 802.3, the zlib polynomial). */
uint32_t model_manifest_crc32(const uint8_t *data, size_t len);

#ifdef __cplusplus
}
#endif
