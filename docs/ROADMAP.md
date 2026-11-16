# Roadmap

Each milestone ends with something that runs and a commit that updates this
file. ✅ done · 🟡 written and verified without hardware, waiting for the board · ⬜ not started

## 🟡 M0 — Board bring-up
- ✅ Firmware builds locally and in CI.
- ✅ Reports chip, flash, PSRAM and partition table; PSRAM self-test (checked in the emulator).
- ⬜ First boot on the real board: 8 MB flash, 8 MB PSRAM, `M0 RESULT: PASS`.

## 🟡 M1 — Wake, capture, upload
- ✅ PIR on GPIO14 wakes from deep sleep; warm-up and re-check timers.
- ✅ Camera captures a 1024×768 JPEG; Wi-Fi joins in parallel.
- ✅ One HTTP POST per event to the ingest service; timings in the metadata.
- ✅ Ingest service with local and GCS storage, tested; device simulator.
- ⬜ On the board: walking past the sensor produces an image on the PC.
- ⬜ Measure wake → uploaded time.

## 🟡 M2 — Dataset
- ✅ `edgeml.ingest` pulls new captures into `data/raw/unlabeled/`.
- ✅ Group-wise split, preprocessing identical to the device, DVC pipeline.
- ⬜ Collect and label real captures; tag dataset v1.

## 🟡 M3 — Train and quantise
- ✅ Model, training, int8 quantisation, evaluation gate, report (tested on synthetic images).
- ⬜ Train on dataset v1; float vs int8 confusion matrices.
- ⬜ ESP-DL comparison (ADR 0003).

## 🟡 M4 — Inference on the device
- ✅ Model package format, validation on the device, TFLite Micro integration.
- ✅ Bench mode; in the emulator the device matches the PC (same classes,
  runtime outputs within 1 int8 step, preprocessing within 2 grey levels).
- ⬜ On the board: latency with the optimised kernels, RAM, wake → decision time.

## ⬜ M5 — OTA with rollback
- Firmware and model updated over Wi-Fi.
- A deliberately broken firmware rolls back automatically.

## ⬜ M6 — Monitoring and polish
- Drift report from the reported scores and sampled images.
- Battery operation and deep-sleep current measurement.
- README final pass: results, demo GIF, lessons learned.
