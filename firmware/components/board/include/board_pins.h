#pragma once

/*
 * Pin map for the Freenove ESP32-S3-WROOM CAM.
 *
 * Camera pins are the ESP32S3_EYE mapping that Freenove's own sketches select
 * for this board (see docs/HARDWARE.md for the source). The board has no
 * power-down or reset line to the sensor.
 */
#define BOARD_CAM_PIN_PWDN   (-1)
#define BOARD_CAM_PIN_RESET  (-1)
#define BOARD_CAM_PIN_XCLK   15
#define BOARD_CAM_PIN_SIOD   4
#define BOARD_CAM_PIN_SIOC   5
#define BOARD_CAM_PIN_D7     16 /* Y9 */
#define BOARD_CAM_PIN_D6     17 /* Y8 */
#define BOARD_CAM_PIN_D5     18 /* Y7 */
#define BOARD_CAM_PIN_D4     12 /* Y6 */
#define BOARD_CAM_PIN_D3     10 /* Y5 */
#define BOARD_CAM_PIN_D2     8  /* Y4 */
#define BOARD_CAM_PIN_D1     9  /* Y3 */
#define BOARD_CAM_PIN_D0     11 /* Y2 */
#define BOARD_CAM_PIN_VSYNC  6
#define BOARD_CAM_PIN_HREF   7
#define BOARD_CAM_PIN_PCLK   13

/* Same clock Freenove uses in its camera sketches. */
#define BOARD_CAM_XCLK_HZ    10000000
