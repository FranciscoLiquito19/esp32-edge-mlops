#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

/*
 * Capture resolution. The model input is exactly 1/8 of this, so the JPEG
 * decoder's 1/8 scaling produces the model input with no resampling
 * (docs/adr/0005).
 */
#define CAPTURE_WIDTH  1024
#define CAPTURE_HEIGHT 768

typedef struct {
    const uint8_t *jpeg; /* valid until capture_release() */
    size_t len;
    uint16_t width;
    uint16_t height;
    uint32_t init_ms; /* time spent starting the sensor */
    uint32_t grab_ms; /* time spent getting the kept frame, warm-up included */
    void *priv;
} capture_frame_t;

/** Start the camera. */
esp_err_t capture_init(void);

/** Get one JPEG frame after discarding the warm-up frames. */
esp_err_t capture_grab(capture_frame_t *out);

/** Return the frame buffer to the driver. */
void capture_release(capture_frame_t *frame);

/** Stop the camera before sleeping. */
void capture_deinit(void);
