# 0002 — Model in its own flash partition

**Status:** accepted

## Context
The model changes more often than the firmware. Embedding it in the app binary
would mean a full firmware OTA (about 1–2 MB) for every retrain, and would tie
model versions to firmware versions.

## Decision
Store the model in a dedicated `model` data partition, preceded by a manifest
(magic, format version, model version, input shape, labels, SHA-256). The
firmware memory-maps the partition and validates the manifest before use.

## Consequences
- Model updates are small and independent of firmware updates.
- The firmware must handle a missing or invalid model (fall back to collect mode).
- One model slot only: a failed model update needs a re-download, there is no
  A/B slot for models. Acceptable for now; revisit in M5.
