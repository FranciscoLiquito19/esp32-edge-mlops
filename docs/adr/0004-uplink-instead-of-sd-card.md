# 0004 — Send captures over Wi-Fi instead of storing them on an SD card

**Status:** accepted

## Context
The first plan stored every capture on the board's SD card and copied them to
the PC by hand. Pulling a card out is the bottleneck of the whole data loop, it
makes remote placement impractical, and it hides failures until someone looks.

## Decision
Every event is one HTTP `POST` to an ingest service: metadata in a header, the
JPEG as the raw body (docs/PROTOCOL.md). The service writes to a storage
backend chosen at start-up: a local folder or a Google Cloud Storage bucket.

## Consequences
- The data loop is automatic: ingest → label → train needs no physical access.
- The device needs Wi-Fi on every event. Joining the network is started first
  so it overlaps with the camera start-up, and the time is measured (`t_ms.wifi`).
- Without a network an event is lost; the device counts losses (`dropped`) and
  reports the count with the next successful upload. A small retry queue in
  RTC memory or flash is possible later if losses turn out to matter.
- Same event, same storage key: retries never create duplicates.
- Moving to the cloud is a deployment change (server/Dockerfile,
  `INGEST_STORAGE=gcs:<bucket>`), not a firmware change.
