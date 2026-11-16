# 0003 — Inference runtime: TFLite Micro vs ESP-DL

**Status:** TFLite Micro adopted for now; comparison with ESP-DL planned for M3

## Options
- **TFLite Micro (`esp-tflite-micro`)** — standard `.tflite` flatbuffer, widely
  used, ESP-NN optimised kernels for the S3 vector instructions.
- **ESP-DL** — Espressif's own runtime and quantisation toolchain, designed for
  the S3/P4 instruction sets.

## Current choice
TFLite Micro, because the PC can run the exact same flatbuffer with the TFLite
interpreter. That makes device-versus-PC checks possible from day one
(`training/edgeml/bench_compare.py`): in the emulator, fed the same image, the
two runtimes agree within 1 int8 step.

## How the final decision will be made
Same model, same test images, both runtimes on the board. Compare latency,
RAM, flash footprint, accuracy after quantisation and toolchain friction.
