import struct
import zlib

import pytest

from edgeml import manifest

PAYLOAD = bytes(range(256)) * 4


def make(**overrides) -> bytes:
    args = dict(
        model_version=7,
        labels=("nothing", "person", "animal"),
        input_width=128,
        input_height=96,
        name="dataset-v1",
        created_unix=1_800_000_000,
    )
    args.update(overrides)
    return manifest.pack(PAYLOAD, **args)


def test_round_trip():
    info, payload = manifest.parse(make())
    assert payload == PAYLOAD
    assert info.model_version == 7
    assert info.labels == ("nothing", "person", "animal")
    assert (info.input_width, info.input_height, info.input_channels) == (128, 96, 1)
    assert info.name == "dataset-v1"
    assert info.created_unix == 1_800_000_000


def test_header_is_256_bytes_and_payload_follows():
    blob = make()
    assert len(blob) == manifest.HEADER_SIZE + len(PAYLOAD)
    assert blob[:4] == b"EMLM"
    assert blob[manifest.HEADER_SIZE :] == PAYLOAD


def test_erased_flash_is_rejected():
    with pytest.raises(manifest.ManifestError, match="magic"):
        manifest.parse(b"\xff" * 1024)


def test_corrupted_header_is_rejected():
    blob = bytearray(make())
    blob[20] ^= 0x01  # input width
    with pytest.raises(manifest.ManifestError, match="checksum"):
        manifest.parse(bytes(blob))


def test_corrupted_payload_is_rejected():
    blob = bytearray(make())
    blob[-1] ^= 0x01
    with pytest.raises(manifest.ManifestError, match="SHA-256"):
        manifest.parse(bytes(blob))


def test_truncated_payload_is_rejected():
    with pytest.raises(manifest.ManifestError, match="truncated"):
        manifest.parse(make()[:-10])


def test_unknown_header_version_is_rejected():
    blob = bytearray(make())
    struct.pack_into("<H", blob, 4, 2)
    struct.pack_into("<I", blob, 252, zlib.crc32(bytes(blob[:252])))
    with pytest.raises(manifest.ManifestError, match="version"):
        manifest.parse(bytes(blob))


@pytest.mark.parametrize("labels", [(), tuple(f"c{i}" for i in range(9)), ("a" * 17,), ("",)])
def test_bad_labels_are_refused(labels):
    with pytest.raises(manifest.ManifestError):
        make(labels=labels)


def test_empty_payload_is_refused():
    with pytest.raises(manifest.ManifestError):
        manifest.pack(b"", model_version=1, labels=("a",), input_width=1, input_height=1)
