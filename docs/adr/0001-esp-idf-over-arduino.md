# 0001 — ESP-IDF instead of Arduino

**Status:** accepted

## Context
The firmware needs deep sleep with RTC GPIO wake-up, a custom partition table,
OTA with rollback, PSRAM configuration and precise control over what is
initialised on each wake-up.

## Decision
Use ESP-IDF directly (v5.5+), with FreeRTOS and CMake components.

## Consequences
- Full control over sdkconfig (PSRAM mode, bootloader rollback, log levels),
  which Arduino hides behind prebuilt libraries.
- Each module is an ESP-IDF component, testable and reusable.
- More boilerplate and a steeper setup than Arduino.
