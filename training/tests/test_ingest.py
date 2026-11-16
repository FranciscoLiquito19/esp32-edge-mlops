import json

import pytest

from edgeml import dataset, ingest


def add_event(store, seq, *, image=True, label=None, device="esp32s3-a1b2c3", session="0f3a9c21"):
    folder = store / "captures" / device / session
    folder.mkdir(parents=True, exist_ok=True)
    meta = {"v": 1, "device": device, "session": session, "seq": seq}
    if label:
        meta["model"] = {"version": 1, "label": label}
    (folder / f"{seq:06d}.json").write_text(json.dumps(meta))
    if image:
        (folder / f"{seq:06d}.jpg").write_bytes(b"\xff\xd8" + bytes([seq]) + b"\xff\xd9")


def test_new_images_go_to_unlabeled(tmp_path):
    store, raw = tmp_path / "store", tmp_path / "raw"
    add_event(store, 0)
    add_event(store, 1)
    add_event(store, 2, image=False)

    counts = ingest.ingest(store, raw)

    assert counts == {"copied": 2, "already_present": 0, "without_image": 1, "unreadable": 0}
    names = sorted(p.name for p in (raw / "unlabeled").iterdir())
    assert names == [
        "esp32s3-a1b2c3_0f3a9c21_000000.jpg",
        "esp32s3-a1b2c3_0f3a9c21_000000.json",
        "esp32s3-a1b2c3_0f3a9c21_000001.jpg",
        "esp32s3-a1b2c3_0f3a9c21_000001.json",
    ]


def test_running_twice_copies_nothing_new(tmp_path):
    store, raw = tmp_path / "store", tmp_path / "raw"
    add_event(store, 0)
    ingest.ingest(store, raw)
    assert ingest.ingest(store, raw)["copied"] == 0


def test_labelled_images_are_not_brought_back(tmp_path):
    store, raw = tmp_path / "store", tmp_path / "raw"
    add_event(store, 0)
    ingest.ingest(store, raw)

    (raw / "person").mkdir()
    for path in (raw / "unlabeled").iterdir():
        path.rename(raw / "person" / path.name)

    counts = ingest.ingest(store, raw)
    assert counts["copied"] == 0 and counts["already_present"] == 1
    assert not any((raw / "unlabeled").iterdir())


def test_presort_uses_the_device_prediction(tmp_path):
    store, raw = tmp_path / "store", tmp_path / "raw"
    add_event(store, 0, label="person")
    add_event(store, 1, label="../escape")
    add_event(store, 2)

    ingest.ingest(store, raw, presort=True)

    assert (raw / "unlabeled/pred_person/esp32s3-a1b2c3_0f3a9c21_000000.jpg").exists()
    assert (raw / "unlabeled/esp32s3-a1b2c3_0f3a9c21_000001.jpg").exists()
    assert (raw / "unlabeled/esp32s3-a1b2c3_0f3a9c21_000002.jpg").exists()


def test_sidecar_keeps_grouping_information(tmp_path):
    store, raw = tmp_path / "store", tmp_path / "raw"
    add_event(store, 7)
    ingest.ingest(store, raw)
    image = raw / "unlabeled/esp32s3-a1b2c3_0f3a9c21_000007.jpg"
    assert dataset._group_of(image, 20) == "esp32s3-a1b2c3:0f3a9c21:0"


def test_wrong_folder_is_reported(tmp_path):
    with pytest.raises(SystemExit, match="does not exist"):
        ingest.ingest(tmp_path / "nowhere", tmp_path / "raw")
