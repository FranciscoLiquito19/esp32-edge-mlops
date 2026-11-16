# Roadmap

Each milestone ends with something that runs on the board and a commit that
updates this file.

## M0 — Board bring-up
- Toolchain installed, firmware builds locally and in CI.
- Firmware reports chip, flash size, PSRAM size and partition table at boot.
- PSRAM read/write self-test passes.

**Done when:** serial log confirms 8 MB flash, 8 MB PSRAM and the custom
partition table.

## M1 — Wake, capture, store
- PIR on an RTC GPIO wakes the chip from deep sleep.
- Camera captures a JPEG; it is saved to SD with a JSON sidecar
  (timestamp, wake reason, boot count, capture time).
- Wake → saved time measured.

**Done when:** walking past the sensor produces a file on the SD card and the
board goes back to sleep.

## M2 — Dataset
- `ingest.py` copies captures from the SD card into a dataset folder.
- Labels: person / animal / nothing, reviewed by hand.
- DVC initialised; first dataset version tagged.

**Done when:** `dvc pull` on a clean clone reproduces dataset v1.

## M3 — Train and quantise
- Small CNN trained on PC; float32 baseline evaluated.
- int8 post-training quantisation; accuracy drop measured.
- Runtime choice settled (ADR 0003).

**Done when:** evaluation report with confusion matrices for float and int8.

## M4 — Inference on the device
- Model loaded from the `model` partition and validated.
- Latency, RAM use and wake → decision time measured on the board.
- On-device predictions match PC predictions on the same images.

**Done when:** README results table has the M4 rows filled in.

## M5 — OTA with rollback
- Firmware and model updated over Wi-Fi.
- A deliberately broken firmware rolls back automatically.

**Done when:** rollback demonstrated and documented.

## M6 — Monitoring and polish
- Telemetry per event; drift report on PC.
- CI also lints and tests the Python code.
- README final pass: results, demo GIF, lessons learned.
