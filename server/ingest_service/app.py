"""HTTP API for the camera nodes.

    INGEST_TOKEN=secret INGEST_STORAGE=local:./data uvicorn ingest_service.app:app --host 0.0.0.0 --port 8000

Protocol: docs/PROTOCOL.md.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .schema import EventMeta
from .storage import Storage, from_spec

MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_META_BYTES = 4096


def create_app(storage: Storage, token: str) -> FastAPI:
    if not token:
        raise ValueError("a device token is required")

    app = FastAPI(title="esp32-edge-mlops ingest", version="1")

    def check_token(request: Request) -> None:
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied.encode(), f"Bearer {token}".encode()):
            raise HTTPException(401, "invalid or missing token")

    def read_meta(request: Request) -> EventMeta:
        raw = request.headers.get("x-event-meta")
        if raw is None:
            raise HTTPException(400, "missing X-Event-Meta header")
        if len(raw) > MAX_META_BYTES:
            raise HTTPException(413, "metadata too large")
        try:
            return EventMeta.model_validate(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise HTTPException(400, f"X-Event-Meta is not JSON: {exc.msg}") from exc
        except ValidationError as exc:
            problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            raise HTTPException(422, f"invalid metadata: {problems}") from exc

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "storage": storage.describe()}

    @app.post("/v1/events")
    async def post_event(request: Request) -> JSONResponse:
        check_token(request)
        meta = read_meta(request)

        declared = int(request.headers.get("content-length") or 0)
        if declared > MAX_IMAGE_BYTES:
            raise HTTPException(413, f"image larger than {MAX_IMAGE_BYTES} bytes")
        body = await request.body()
        if len(body) > MAX_IMAGE_BYTES:
            raise HTTPException(413, f"image larger than {MAX_IMAGE_BYTES} bytes")

        if meta.image:
            if not (body.startswith(b"\xff\xd8") and body.rstrip(b"\x00").endswith(b"\xff\xd9")):
                raise HTTPException(400, "metadata says image=true but the body is not a complete JPEG")
        elif body:
            raise HTTPException(400, "metadata says image=false but a body was sent")

        now = time.time()
        reply = {"id": meta.key.removeprefix("captures/"), "stored_image": meta.image, "server_time": int(now)}

        # The metadata file is written last, so its presence means the event is complete.
        if storage.exists(f"{meta.key}.json"):
            return JSONResponse({**reply, "duplicate": True}, status_code=200)

        record = meta.model_dump(mode="json", exclude_none=True)
        record["received_at"] = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
        record["received_unix"] = int(now)
        if meta.image:
            record["image_bytes"] = len(body)
            record["image_sha256"] = hashlib.sha256(body).hexdigest()
            storage.put(f"{meta.key}.jpg", body, "image/jpeg")
        storage.put(f"{meta.key}.json", json.dumps(record, indent=2).encode(), "application/json")

        return JSONResponse(reply, status_code=201)

    return app


def _from_environment() -> FastAPI:
    token = os.environ.get("INGEST_TOKEN", "")
    if not token:
        raise RuntimeError("set INGEST_TOKEN to the token the devices are configured with")
    return create_app(from_spec(os.environ.get("INGEST_STORAGE", "local:./data")), token)


def __getattr__(name: str):
    # `uvicorn ingest_service.app:app` builds the app from the environment on first use,
    # while importing this module (as the tests do) needs no configuration.
    if name == "app":
        return _from_environment()
    raise AttributeError(name)
