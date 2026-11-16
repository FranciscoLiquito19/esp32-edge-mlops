#!/usr/bin/env python3
"""Check that the metadata printed by the firmware is accepted by the ingest service.

Bench-mode firmware prints one "META {...}" line: the exact header value it
would send with an event. This validates it against the service's schema.

    python tools/check_meta.py bench.log
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from ingest_service.schema import EventMeta

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    lines = [_ANSI.sub("", line).strip() for line in Path(sys.argv[1]).read_text(errors="replace").splitlines()]
    metas = [line[5:] for line in lines if line.startswith("META ")]
    if not metas:
        sys.exit("no META line in the log")
    for raw in metas:
        meta = EventMeta.model_validate(json.loads(raw))
        print(f"META OK: {len(raw)} bytes, key {meta.key}, model {meta.model.label if meta.model else None}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
