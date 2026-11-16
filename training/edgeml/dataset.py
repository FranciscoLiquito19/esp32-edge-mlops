"""Turn labelled captures into train/validation/test arrays.

Input layout (labels are folder names):

    data/raw/person/*.jpg
    data/raw/animal/*.jpg
    data/raw/nothing/*.jpg
    data/raw/unlabeled/...      ignored

Captures from the same moment look almost identical, so the split is made by
group (same device session, neighbouring sequence numbers), never by single
image. Otherwise near-duplicates land on both sides and inflate the scores.

    python -m edgeml.dataset --raw data/raw --out data/processed
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import config, preprocess

SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class Sample:
    path: Path
    label: str
    sha256: str
    group: str


def _group_of(path: Path, group_size: int) -> str:
    """Session plus sequence bucket from the sidecar, or the file itself."""
    sidecar = path.with_suffix(".json")
    if sidecar.exists():
        try:
            meta = json.loads(sidecar.read_text())
            return f"{meta.get('device', '')}:{meta['session']}:{int(meta['seq']) // group_size}"
        except (ValueError, KeyError, TypeError):
            pass
    return f"file:{path.stem}"


def split_of(group: str, val_fraction: float, test_fraction: float) -> str:
    """Deterministic split from a hash of the group name."""
    digest = hashlib.sha1(group.encode()).digest()
    u = int.from_bytes(digest[:8], "big") / 2**64
    if u < test_fraction:
        return "test"
    if u < test_fraction + val_fraction:
        return "val"
    return "train"


def scan(raw: Path, labels: tuple[str, ...] = config.LABELS, group_size: int = 20) -> list[Sample]:
    """Find labelled JPEGs, dropping exact duplicates."""
    samples: list[Sample] = []
    seen: set[str] = set()
    for label in labels:
        for path in sorted((raw / label).glob("*.jpg")):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            samples.append(Sample(path, label, digest, _group_of(path, group_size)))
    return samples


def build(
    raw: Path,
    out: Path,
    *,
    labels: tuple[str, ...] = config.LABELS,
    val_fraction: float = 0.15,
    test_fraction: float = 0.15,
    group_size: int = 20,
) -> dict:
    """Preprocess every labelled capture and write dataset.npz, manifest.csv and stats.json."""
    samples = scan(raw, labels, group_size)
    if not samples:
        raise SystemExit(f"no labelled images under {raw} (expected folders: {', '.join(labels)})")

    arrays: dict[str, list[np.ndarray]] = {s: [] for s in SPLITS}
    targets: dict[str, list[int]] = {s: [] for s in SPLITS}
    rows = []
    skipped = 0

    for sample in samples:
        split = split_of(sample.group, val_fraction, test_fraction)
        try:
            gray = preprocess.jpeg_to_gray(sample.path.read_bytes())
        except (ValueError, OSError) as exc:
            print(f"skipping {sample.path}: {exc}")
            skipped += 1
            continue
        arrays[split].append(gray)
        targets[split].append(labels.index(sample.label))
        rows.append((sample.path.relative_to(raw).as_posix(), sample.label, split, sample.sha256))

    out.mkdir(parents=True, exist_ok=True)
    shape = (0, config.INPUT_HEIGHT, config.INPUT_WIDTH)
    payload = {}
    for split in SPLITS:
        payload[f"x_{split}"] = np.stack(arrays[split]) if arrays[split] else np.zeros(shape, dtype=np.uint8)
        payload[f"y_{split}"] = np.asarray(targets[split], dtype=np.int64)
    np.savez_compressed(out / "dataset.npz", labels=np.asarray(labels), **payload)

    with (out / "manifest.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["file", "label", "split", "sha256"])
        writer.writerows(rows)

    stats = {
        "labels": list(labels),
        "skipped": skipped,
        "counts": {
            split: {label: int((payload[f"y_{split}"] == i).sum()) for i, label in enumerate(labels)}
            for split in SPLITS
        },
    }
    (out / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    return stats


def load(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("data/processed"))
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--test-fraction", type=float, default=0.15)
    parser.add_argument("--group-size", type=int, default=20)
    args = parser.parse_args()

    stats = build(
        args.raw,
        args.out,
        val_fraction=args.val_fraction,
        test_fraction=args.test_fraction,
        group_size=args.group_size,
    )
    print(json.dumps(stats["counts"], indent=2))
    for split in SPLITS:
        empty = [label for label, n in stats["counts"][split].items() if n == 0]
        if empty:
            print(f"warning: no {split} images for: {', '.join(empty)}")


if __name__ == "__main__":
    main()
