# Hardware

## Bill of materials

| Part | Notes |
|---|---|
| Freenove ESP32-S3-WROOM CAM | ESP32-S3-WROOM-1, expected N8R8 (8 MB flash, 8 MB octal PSRAM). The M0 self-test confirms this. |
| OV2640 camera | Comes with the board, on the DVP connector. |
| Mini PIR sensor (SR505 / AM312 type) | Wake-up trigger. |
| USB power supply or power bank | Battery operation comes later (M6). |

No SD card: captures go over Wi-Fi to the ingest service (ADR 0004).

## Pin map

From Freenove's pinout diagram (`ESP32S3_Pinout.png` in
[Freenove_ESP32_S3_WROOM_Board](https://github.com/Freenove/Freenove_ESP32_S3_WROOM_Board))
and the camera pins its own sketches select (`CAMERA_MODEL_ESP32S3_EYE`).
In code: `firmware/components/board/include/board_pins.h`.

| Function | GPIO |
|---|---|
| Camera SIOD / SIOC (SCCB) | 4 / 5 |
| Camera VSYNC / HREF / PCLK / XCLK | 6 / 7 / 13 / 15 |
| Camera Y2…Y9 | 11, 9, 8, 10, 12, 18, 17, 16 |
| SD card (not used) | 38, 39, 40 |
| PSRAM (do not touch) | 35, 36, 37 |
| On-board LED | 2 |
| On-board WS2812 | 48 |
| Strapping pins (avoid) | 0, 3, 45, 46 |
| USB D- / D+ | 19 / 20 |
| **PIR output** | **14** |

### Why GPIO14 for the PIR

To wake the chip from deep sleep the pin must be an RTC GPIO (0–21 on the
ESP32-S3). Of those, the camera takes 4–13 and 15–18, 0 and 3 are strapping
pins, 19–20 are USB and 2 drives the LED. That leaves 1, 14 and 21; GPIO14 sits
on the same header as the 5V pin, which keeps the PIR wiring short. The pin is
a `menuconfig` option (`APP_PIR_GPIO`) if you need another.

## Wiring the PIR

| PIR pin | Board pin |
|---|---|
| VCC | 5V |
| GND | GND |
| OUT | GPIO14 |

* SR505-type sensors need at least 4.5 V, so they are powered from 5V, not 3V3.
* OUT swings to about 3.3 V, safe for the ESP32-S3 without a level shifter.
  Measure it with a multimeter before connecting.
* Check the silkscreen for pin order: it differs between PIR boards.
* The firmware enables a pull-down on GPIO14, so an unplugged sensor reads
  "no motion" instead of waking the board at random.
* The output is unreliable for the first 30–60 s after power-up. The firmware
  ignores it for `APP_PIR_WARMUP_S` (45 s) after a cold boot.

## USB ports

The board has two USB-C ports. Flash and monitor through the one labelled
**UART** (CH343 bridge). The other is the chip's native USB.
