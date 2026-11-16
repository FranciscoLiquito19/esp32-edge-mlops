# Model package format

What goes into the `model` flash partition: a 256-byte header followed by the
model itself. Written by `training/edgeml/manifest.py`, read by
`firmware/components/model_store/model_manifest.c`. All integers are
little-endian.

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0 | 4 | magic | `EMLM` |
| 4 | 2 | header_version | `1` |
| 6 | 2 | header_size | `256` |
| 8 | 4 | model_version | Increases with every released model |
| 12 | 4 | payload_size | Bytes of model after the header |
| 16 | 4 | created_unix | Build time |
| 20 | 2 | input_width | |
| 22 | 2 | input_height | |
| 24 | 1 | input_channels | |
| 25 | 1 | num_labels | 1–8 |
| 26 | 1 | format | `1` = TFLite flatbuffer, int8 input and output |
| 27 | 1 | reserved | 0 |
| 28 | 32 | sha256 | SHA-256 of the payload |
| 60 | 128 | labels | 8 × 16 bytes, NUL-padded ASCII, in output order |
| 188 | 32 | name | NUL-padded ASCII tag, e.g. the dataset version |
| 220 | 32 | reserved | 0 |
| 252 | 4 | crc32 | CRC-32 (zlib) of bytes 0–251 |

The payload starts at offset 256, which keeps the 16-byte alignment the
interpreter needs when the model is executed in place from memory-mapped flash.

## What the firmware checks before using a model

1. Magic, header version, header CRC.
2. Field ranges; payload fits in the partition.
3. SHA-256 of the payload.
4. TFLite schema version; input and output tensors match the header.

An erased partition fails step 1 and is reported as "no model installed", which
is a normal state: the device then behaves as in collect mode.

## Writing a package to the device

```bash
parttool.py --port COMx write_partition --partition-name model --input training/models/model.bin
```
