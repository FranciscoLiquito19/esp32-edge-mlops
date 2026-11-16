# Hardware

## Bill of materials

| Part | Notes |
|---|---|
| Freenove ESP32-S3-WROOM CAM | ESP32-S3-WROOM-1, expected N8R8 (8 MB flash, 8 MB octal PSRAM). M0 confirms this. |
| OV2640 camera | Comes with the board, on the DVP connector. |
| microSD card | FAT32. Used to store captures for the dataset. |
| Mini PIR sensor (SR505 / AM312 type) | Wake-up trigger. |
| 0.96" OLED, I2C (SSD1306) | Optional, status display. |
| BMP280 | Optional, temperature/pressure in telemetry. |

## Wiring

### PIR sensor

| PIR pin | Board pin |
|---|---|
| VCC | 5V (USB VBUS) |
| GND | GND |
| OUT | GPIO — chosen in M1, see below |

* SR505-type sensors need at least 4.5 V, so they are powered from 5V, not 3V3.
* The OUT pin swings to about 3.3 V, so it is safe for an ESP32-S3 GPIO without
  a level shifter. Measure it with a multimeter before connecting.
* Check the silkscreen for pin order: it is not the same on every PIR board.
* Ignore the output for the first 30–60 s after power-up while the sensor settles.

### Choosing the PIR GPIO (M1)

The camera and the SD card already use many GPIOs on this board. The PIR pin must
be:

1. not used by the camera, SD card, PSRAM or flash, and
2. an **RTC-capable GPIO (0–21 on the ESP32-S3)**, so it can wake the chip from
   deep sleep.

The final pin is recorded here once checked against the Freenove pinout.
