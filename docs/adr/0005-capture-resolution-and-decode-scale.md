# 0005 — Capture at 1024×768, decode at 1/8 scale for the model

**Status:** accepted

## Context
The camera produces JPEG. The model needs a small greyscale image. Resizing an
image in software on the microcontroller costs time and memory, and any
resizing code on the device must match what the training pipeline does.

## Decision
- Capture at XGA (1024×768).
- Decode with the JPEG decoder's built-in 1/8 scaling: it outputs one pixel per
  8×8 block from the DC coefficient, almost for free. 1024×768 / 8 = 128×96,
  which is the model input. No resampling step exists anywhere.
- Convert to grey with integer weights `(77R + 150G + 29B + 128) >> 8`, the
  same in C (`preprocess.c`) and Python (`preprocess.py`).
- Use the `esp_jpeg` decoder compiled from source instead of the copy in the
  ESP32-S3 ROM, so the decoder is a known version.

## Consequences
- Uploaded images are a useful size for a person to label.
- The PC decodes with libjpeg, the device with TJpgDec. They differ by at most
  2 grey levels per pixel on the test images (measured in the emulator, see
  README); the comparison tool reports this for every model.
- Changing the capture size means changing the model input; the model package
  carries its input size, and the firmware refuses a mismatch.
