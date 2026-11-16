/*
 * PC build of the firmware's hardware-independent code, driven by
 * training/tests/test_c_parity.py to check it against the Python tooling.
 *
 *   host_check manifest <package file>     print the parsed header as JSON
 *   host_check gray <w> <h> <out_w> <out_h>  RGB888 on stdin -> grey on stdout
 *   host_check quant <scale> <zero_point>  print the 256-entry input mapping
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "model_manifest.h"
#include "preprocess.h"

static int cmd_manifest(const char *path)
{
    static uint8_t buf[MODEL_MANIFEST_SIZE];
    FILE *fh = fopen(path, "rb");
    if (fh == NULL) {
        perror(path);
        return 2;
    }
    size_t n = fread(buf, 1, sizeof(buf), fh);
    fclose(fh);

    model_manifest_t m;
    model_manifest_err_t err = model_manifest_parse(buf, n, &m);
    if (err != MODEL_MANIFEST_OK) {
        printf("{\"ok\":false,\"error\":\"%s\"}\n", model_manifest_err_str(err));
        return 1;
    }

    printf("{\"ok\":true,\"model_version\":%u,\"payload_size\":%u,\"created_unix\":%u,"
           "\"input_width\":%u,\"input_height\":%u,\"input_channels\":%u,\"format\":%u,"
           "\"name\":\"%s\",\"sha256\":\"",
           (unsigned)m.model_version, (unsigned)m.payload_size, (unsigned)m.created_unix,
           (unsigned)m.input_width, (unsigned)m.input_height, (unsigned)m.input_channels,
           (unsigned)m.format, m.name);
    for (int i = 0; i < MODEL_MANIFEST_SHA256_LEN; i++) {
        printf("%02x", m.sha256[i]);
    }
    printf("\",\"labels\":[");
    for (int i = 0; i < m.num_labels; i++) {
        printf("%s\"%s\"", i ? "," : "", m.labels[i]);
    }
    printf("]}\n");
    return 0;
}

static int cmd_gray(int w, int h, int out_w, int out_h)
{
    size_t in_len = (size_t)w * h * 3, out_len = (size_t)out_w * out_h;
    uint8_t *rgb = malloc(in_len), *gray = malloc(out_len);
    if (rgb == NULL || gray == NULL || fread(rgb, 1, in_len, stdin) != in_len) {
        fprintf(stderr, "could not read %zu bytes of RGB\n", in_len);
        return 2;
    }
    if (!preprocess_rgb888_to_gray(rgb, (uint16_t)w, (uint16_t)h, gray, (uint16_t)out_w, (uint16_t)out_h)) {
        fprintf(stderr, "source smaller than output\n");
        return 1;
    }
    fwrite(gray, 1, out_len, stdout);
    free(rgb);
    free(gray);
    return 0;
}

static int cmd_quant(float scale, int zero_point)
{
    uint8_t gray[256];
    int8_t q[256];
    for (int i = 0; i < 256; i++) {
        gray[i] = (uint8_t)i;
    }
    preprocess_quantize(gray, 256, scale, zero_point, q);
    for (int i = 0; i < 256; i++) {
        printf("%d\n", q[i]);
    }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 3 && strcmp(argv[1], "manifest") == 0) {
        return cmd_manifest(argv[2]);
    }
    if (argc == 6 && strcmp(argv[1], "gray") == 0) {
        return cmd_gray(atoi(argv[2]), atoi(argv[3]), atoi(argv[4]), atoi(argv[5]));
    }
    if (argc == 4 && strcmp(argv[1], "quant") == 0) {
        return cmd_quant(strtof(argv[2], NULL), atoi(argv[3]));
    }
    fprintf(stderr, "usage: see the comment at the top of host_check.c\n");
    return 2;
}
