import csv
import json

import numpy as np

from edgeml import config, dataset, synth


def test_split_is_deterministic_and_roughly_proportional():
    groups = [f"dev:{i:08x}:0" for i in range(2000)]
    first = [dataset.split_of(g, 0.15, 0.15) for g in groups]
    assert first == [dataset.split_of(g, 0.15, 0.15) for g in groups]
    assert 0.11 < first.count("val") / len(groups) < 0.19
    assert 0.11 < first.count("test") / len(groups) < 0.19


def test_build_writes_arrays_manifest_and_stats(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "processed"
    synth.write_dataset(raw, per_class=10, seed=3)

    stats = dataset.build(raw, out, group_size=5)
    data = dataset.load(out / "dataset.npz")

    total = sum(len(data[f"y_{s}"]) for s in dataset.SPLITS)
    assert total == 30
    assert list(data["labels"]) == list(config.LABELS)
    for split in dataset.SPLITS:
        assert data[f"x_{split}"].shape[1:] == (config.INPUT_HEIGHT, config.INPUT_WIDTH)
        assert data[f"x_{split}"].dtype == np.uint8
    assert sum(sum(c.values()) for c in stats["counts"].values()) == 30
    assert json.loads((out / "stats.json").read_text()) == stats


def test_images_from_one_moment_stay_in_one_split(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "processed"
    synth.write_dataset(raw, per_class=15, seed=4)
    dataset.build(raw, out, group_size=5)

    split_by_group = {}
    with (out / "manifest.csv").open() as fh:
        for row in csv.DictReader(fh):
            meta = json.loads((raw / row["file"]).with_suffix(".json").read_text())
            group = (meta["session"], meta["seq"] // 5)
            assert split_by_group.setdefault(group, row["split"]) == row["split"]
    assert len(split_by_group) > 3


def test_duplicates_and_unlabelled_images_are_ignored(tmp_path):
    raw = tmp_path / "raw"
    synth.write_dataset(raw, per_class=2, seed=5)
    original = next((raw / "person").glob("*.jpg"))
    (raw / "person" / "copy.jpg").write_bytes(original.read_bytes())
    (raw / config.UNLABELED_DIR).mkdir()
    (raw / config.UNLABELED_DIR / "new.jpg").write_bytes(original.read_bytes())

    assert len(dataset.scan(raw)) == 6


def test_unreadable_image_is_skipped_not_fatal(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "processed"
    synth.write_dataset(raw, per_class=2, seed=6)
    (raw / "animal" / "broken.jpg").write_bytes(b"not a jpeg")

    stats = dataset.build(raw, out)
    assert stats["skipped"] == 1
