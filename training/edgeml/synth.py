"""Synthetic captures for testing the pipeline end to end without a camera.

The images are simple shapes on noisy backgrounds. They exist to prove that
every stage runs and that the device and the PC agree with each other; a model
trained on them says nothing about real-world accuracy.

    python -m edgeml.synth --out data/raw --per-class 60
    python -m edgeml.synth --golden ../firmware/main/golden
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import config

GOLDEN_SEED = 20261116


def _background(rng: np.random.Generator) -> Image.Image:
    """Low-frequency noise with a brightness gradient."""
    small = rng.integers(40, 200, size=(12, 16, 3), dtype=np.uint8)
    img = Image.fromarray(small, "RGB").resize((config.CAPTURE_WIDTH, config.CAPTURE_HEIGHT), Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(radius=24))
    grad = np.linspace(rng.uniform(0.6, 1.0), rng.uniform(0.6, 1.0), config.CAPTURE_HEIGHT)
    arr = np.asarray(img, dtype=np.float32) * grad[:, None, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _draw_person(draw: ImageDraw.ImageDraw, rng: np.random.Generator, shade: tuple[int, int, int]):
    cx = rng.integers(200, config.CAPTURE_WIDTH - 200)
    height = rng.integers(360, 620)
    width = int(height * rng.uniform(0.22, 0.32))
    top = rng.integers(40, config.CAPTURE_HEIGHT - height - 20)
    head = int(width * 0.75)
    draw.ellipse([cx - head // 2, top, cx + head // 2, top + head], fill=shade)
    draw.rounded_rectangle([cx - width // 2, top + head, cx + width // 2, top + height], radius=width // 3, fill=shade)


def _draw_animal(draw: ImageDraw.ImageDraw, rng: np.random.Generator, shade: tuple[int, int, int]):
    cx = rng.integers(260, config.CAPTURE_WIDTH - 260)
    width = rng.integers(300, 480)
    height = int(width * rng.uniform(0.32, 0.45))
    top = rng.integers(config.CAPTURE_HEIGHT // 2, config.CAPTURE_HEIGHT - height - 120)
    draw.ellipse([cx - width // 2, top, cx + width // 2, top + height], fill=shade)
    leg = max(18, width // 14)
    for dx in (-0.36, -0.18, 0.18, 0.36):
        x = cx + int(dx * width)
        draw.rectangle([x - leg // 2, top + height // 2, x + leg // 2, top + height + 90], fill=shade)
    head = int(height * 0.7)
    hx = cx + width // 2 - head // 3
    draw.ellipse([hx, top - head // 3, hx + head, top - head // 3 + head], fill=shade)


def render(label: str, rng: np.random.Generator) -> bytes:
    """One synthetic capture as JPEG bytes, in the format the camera produces."""
    img = _background(rng)
    if label != "nothing":
        draw = ImageDraw.Draw(img)
        # Subjects are clearly darker or lighter than the scene.
        level = int(rng.choice([rng.integers(0, 35), rng.integers(220, 255)]))
        shade = (level, level, level)
        if label == "person":
            _draw_person(draw, rng, shade)
        elif label == "animal":
            _draw_animal(draw, rng, shade)
        else:
            raise ValueError(f"unknown label {label!r}")
    arr = np.asarray(img, dtype=np.float32) + rng.normal(0, 4, size=(config.CAPTURE_HEIGHT, config.CAPTURE_WIDTH, 3))
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")

    buf = io.BytesIO()
    # 4:2:2 chroma subsampling, like the OV2640's JPEG output.
    img.save(buf, format="JPEG", quality=85, subsampling=1)
    return buf.getvalue()


def write_dataset(out: Path, per_class: int, seed: int = 0) -> int:
    """Write labelled captures under out/<label>/ with sidecar metadata."""
    rng = np.random.default_rng(seed)
    count = 0
    for label in config.LABELS:
        folder = out / label
        folder.mkdir(parents=True, exist_ok=True)
        for _ in range(per_class):
            # A new "session" every 5 frames, so group-wise splitting has groups to work with.
            session = f"{(seed * 1000 + count // 5) & 0xFFFFFFFF:08x}"
            stem = f"synth_{session}_{count:05d}"
            (folder / f"{stem}.jpg").write_bytes(render(label, rng))
            (folder / f"{stem}.json").write_text(
                json.dumps({"v": 1, "device": "synth", "session": session, "seq": count, "synthetic": True})
            )
            count += 1
    return count


def write_golden(out: Path) -> list[Path]:
    """Fixed test images embedded in the firmware's bench mode: one per class."""
    rng = np.random.default_rng(GOLDEN_SEED)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, label in enumerate(config.LABELS):
        path = out / f"g{i}.jpg"
        path.write_bytes(render(label, rng))
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, help="write a labelled synthetic dataset here")
    parser.add_argument("--per-class", type=int, default=60)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--golden", type=Path, help="write the firmware bench images here")
    args = parser.parse_args()

    if args.out:
        n = write_dataset(args.out, args.per_class, args.seed)
        print(f"wrote {n} synthetic captures to {args.out}")
    if args.golden:
        for path in write_golden(args.golden):
            print(f"wrote {path} ({path.stat().st_size} bytes)")
    if not args.out and not args.golden:
        parser.error("nothing to do: pass --out and/or --golden")


if __name__ == "__main__":
    main()
