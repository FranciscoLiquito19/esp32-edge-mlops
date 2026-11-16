"""Model package: a 256-byte header followed by the model payload.

Layout documented in docs/MODEL_PACKAGE.md; the firmware parser is
firmware/components/model_store/model_manifest.c.
"""

from __future__ import annotations

import hashlib
import struct
import time
import zlib
from dataclasses import dataclass

MAGIC = b"EMLM"
HEADER_VERSION = 1
HEADER_SIZE = 256
MAX_LABELS = 8
LABEL_LEN = 16
NAME_LEN = 32
FORMAT_TFLITE_INT8 = 1

# magic, header_version, header_size, model_version, payload_size, created,
# input_width, input_height, input_channels, num_labels, format, reserved, sha256
_FIXED = struct.Struct("<4sHHIIIHHBBBB32s")
_OFF_LABELS = 60
_OFF_NAME = 188
_OFF_CRC = 252

assert _FIXED.size == _OFF_LABELS


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Manifest:
    model_version: int
    payload_size: int
    created_unix: int
    input_width: int
    input_height: int
    input_channels: int
    labels: tuple[str, ...]
    name: str
    sha256: bytes
    format: int = FORMAT_TFLITE_INT8


def _fixed_text(text: str, width: int, what: str) -> bytes:
    raw = text.encode("ascii")
    if not raw or len(raw) > width:
        raise ManifestError(f"{what} must be 1 to {width} ASCII characters: {text!r}")
    return raw.ljust(width, b"\0")


def pack(
    payload: bytes,
    *,
    model_version: int,
    labels: tuple[str, ...] | list[str],
    input_width: int,
    input_height: int,
    input_channels: int = 1,
    name: str = "model",
    created_unix: int | None = None,
    fmt: int = FORMAT_TFLITE_INT8,
) -> bytes:
    """Return header + payload."""
    if not payload:
        raise ManifestError("empty payload")
    if not 1 <= len(labels) <= MAX_LABELS:
        raise ManifestError(f"need 1 to {MAX_LABELS} labels")
    if not 0 < model_version < 2**32:
        raise ManifestError("model_version must fit in 32 bits and be positive")
    if created_unix is None:
        created_unix = int(time.time())

    header = bytearray(HEADER_SIZE)
    _FIXED.pack_into(
        header,
        0,
        MAGIC,
        HEADER_VERSION,
        HEADER_SIZE,
        model_version,
        len(payload),
        created_unix,
        input_width,
        input_height,
        input_channels,
        len(labels),
        fmt,
        0,
        hashlib.sha256(payload).digest(),
    )
    for i, label in enumerate(labels):
        off = _OFF_LABELS + i * LABEL_LEN
        header[off : off + LABEL_LEN] = _fixed_text(label, LABEL_LEN, "label")
    header[_OFF_NAME : _OFF_NAME + NAME_LEN] = _fixed_text(name, NAME_LEN, "name")
    struct.pack_into("<I", header, _OFF_CRC, zlib.crc32(bytes(header[:_OFF_CRC])))
    return bytes(header) + payload


def parse(package: bytes, *, verify_payload: bool = True) -> tuple[Manifest, bytes]:
    """Validate a package and return (manifest, payload)."""
    if len(package) < HEADER_SIZE:
        raise ManifestError("too short")
    header = package[:HEADER_SIZE]
    (magic, version, size, model_version, payload_size, created, in_w, in_h, in_c, n_labels, fmt, _reserved, sha) = (
        _FIXED.unpack_from(header, 0)
    )

    if magic != MAGIC:
        raise ManifestError("bad magic")
    if version != HEADER_VERSION or size != HEADER_SIZE:
        raise ManifestError("unsupported header version")
    (crc,) = struct.unpack_from("<I", header, _OFF_CRC)
    if crc != zlib.crc32(header[:_OFF_CRC]):
        raise ManifestError("header checksum mismatch")
    if not 1 <= n_labels <= MAX_LABELS or payload_size == 0:
        raise ManifestError("invalid header fields")

    labels = tuple(
        header[_OFF_LABELS + i * LABEL_LEN : _OFF_LABELS + (i + 1) * LABEL_LEN].rstrip(b"\0").decode("ascii")
        for i in range(n_labels)
    )
    name = header[_OFF_NAME : _OFF_NAME + NAME_LEN].rstrip(b"\0").decode("ascii")
    payload = package[HEADER_SIZE : HEADER_SIZE + payload_size]

    if verify_payload:
        if len(payload) != payload_size:
            raise ManifestError("payload truncated")
        if hashlib.sha256(payload).digest() != sha:
            raise ManifestError("payload SHA-256 mismatch")

    manifest = Manifest(
        model_version=model_version,
        payload_size=payload_size,
        created_unix=created,
        input_width=in_w,
        input_height=in_h,
        input_channels=in_c,
        labels=labels,
        name=name,
        sha256=sha,
        format=fmt,
    )
    return manifest, payload
