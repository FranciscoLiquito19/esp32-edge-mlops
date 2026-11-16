#!/usr/bin/env python3
"""Pretend to be a camera node: post events to the ingest service.

Useful to check a running service (and your firewall) before the board is
involved, and to fill the store with test data. Speaks the same protocol as
the firmware (docs/PROTOCOL.md). Standard library only, unless --synthetic is
used, which draws test images with the training tooling.

    python tools/fake_device.py --url http://localhost:8000/v1/events --token secret --count 3
    python tools/fake_device.py --url ... --token ... --image photo.jpg
    python tools/fake_device.py --url ... --token ... --synthetic --count 30
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Smallest valid JPEG that decoders accept: a 1x1 grey pixel.
TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c19"
    "12130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b08"
    "0001000101011100ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b51000"
    "02010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f0"
    "2433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768"
    "696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3"
    "c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fb"
    "fcffd9"
)


def build_meta(device: str, session: str, seq: int, image: bytes | None, width: int, height: int) -> str:
    meta = {
        "v": 1,
        "device": device,
        "fw": "fake",
        "session": session,
        "seq": seq,
        "wake": "pir",
        "mode": "collect",
        "ts": 0,
        "dropped": 0,
        "rssi": -50,
        "image": image is not None,
        "t_ms": {"cam_init": 0, "grab": 0, "wifi": 0, "awake": 0},
    }
    if image is not None:
        meta["frame"] = {"w": width, "h": height, "bytes": len(image)}
    return json.dumps(meta, separators=(",", ":"))


def post(url: str, token: str, meta: str, image: bytes | None, timeout: float = 10.0) -> tuple[int, str]:
    headers = {"Authorization": f"Bearer {token}", "X-Event-Meta": meta}
    if image is not None:
        headers["Content-Type"] = "image/jpeg"
    request = urllib.request.Request(url, data=image or b"", headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True, help="events endpoint, e.g. http://localhost:8000/v1/events")
    parser.add_argument("--token", required=True)
    parser.add_argument("--device", default="fake-000001")
    parser.add_argument("--count", type=int, default=1)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--image", type=Path, help="send this JPEG instead of the built-in 1x1 image")
    source.add_argument("--synthetic", action="store_true", help="send drawn test scenes (needs training/ deps)")
    source.add_argument("--no-image", action="store_true", help="send metadata only")
    args = parser.parse_args()

    render = None
    if args.synthetic:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
        import numpy as np
        from edgeml import config, synth

        rng = np.random.default_rng()
        render = lambda i: synth.render(config.LABELS[i % len(config.LABELS)], rng)

    session = secrets.token_hex(4)
    failures = 0
    for seq in range(args.count):
        if args.no_image:
            image, width, height = None, 0, 0
        elif render is not None:
            image, width, height = render(seq), 1024, 768
        elif args.image:
            image, width, height = args.image.read_bytes(), 1024, 768
        else:
            image, width, height = TINY_JPEG, 1, 1

        status, body = post(args.url, args.token, build_meta(args.device, session, seq, image, width, height), image)
        print(f"{session}/{seq:06d}: HTTP {status} {body.strip()}")
        failures += status not in (200, 201)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as exc:
        sys.exit(f"could not reach the service: {exc.reason}")
