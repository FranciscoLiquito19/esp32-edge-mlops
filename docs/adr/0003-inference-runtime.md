# 0003 — Inference runtime: TFLite Micro vs ESP-DL

**Status:** open — to be decided in M3 with measurements

## Options
- **TFLite Micro (`esp-tflite-micro`)** — standard `.tflite` flatbuffer, widely
  used, ESP-NN optimised kernels for the S3 vector instructions.
- **ESP-DL** — Espressif's own runtime and quantisation toolchain, designed for
  the S3/P4 instruction sets.

## How it will be decided
Same model, same test images, both runtimes on the board. Compare latency,
RAM, flash footprint, accuracy after quantisation and toolchain friction.
