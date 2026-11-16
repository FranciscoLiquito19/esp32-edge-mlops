"""Bring uploaded captures into the dataset folder for labelling.

Reads the ingest service's store (a local folder, or a bucket synced to one)
and copies every new image into data/raw/unlabeled/. Label an image by moving
it, with its .json, into data/raw/<label>/.

    python -m edgeml.ingest --store ../server/data --raw data/raw
    python -m edgeml.ingest --store ../server/data --raw data/raw --presort

With --presort, images the device already classified go into
unlabeled/pred_<label>/, so reviewing becomes "check the folder, move the
mistakes" instead of sorting everything by hand.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from . import config


def _known_stems(raw: Path) -> set[str]:
    """Names already in the dataset, labelled or not."""
    return {p.stem for p in raw.rglob("*.jpg")}


def ingest(store: Path, raw: Path, presort: bool = False) -> dict[str, int]:
    captures = store / "captures"
    if not captures.is_dir():
        raise SystemExit(f"{captures} does not exist: is --store the ingest service's storage folder?")

    known = _known_stems(raw) if raw.exists() else set()
    counts = {"copied": 0, "already_present": 0, "without_image": 0, "unreadable": 0}

    for meta_path in sorted(captures.glob("*/*/*.json")):
        image_path = meta_path.with_suffix(".jpg")
        if not image_path.exists():
            counts["without_image"] += 1
            continue
        try:
            meta = json.loads(meta_path.read_text())
            stem = f"{meta['device']}_{meta['session']}_{int(meta['seq']):06d}"
        except (ValueError, KeyError, TypeError):
            counts["unreadable"] += 1
            continue
        if stem in known:
            counts["already_present"] += 1
            continue

        folder = raw / config.UNLABELED_DIR
        predicted = (meta.get("model") or {}).get("label")
        if presort and isinstance(predicted, str) and predicted.isidentifier():
            folder = folder / f"pred_{predicted}"
        folder.mkdir(parents=True, exist_ok=True)

        shutil.copyfile(image_path, folder / f"{stem}.jpg")
        shutil.copyfile(meta_path, folder / f"{stem}.json")
        known.add(stem)
        counts["copied"] += 1

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--store", type=Path, required=True, help="the ingest service's storage folder")
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--presort", action="store_true", help="group by the device's own prediction")
    args = parser.parse_args()

    counts = ingest(args.store, args.raw, args.presort)
    print(", ".join(f"{name.replace('_', ' ')}: {n}" for name, n in counts.items()))


if __name__ == "__main__":
    main()
