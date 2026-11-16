"""Where events are kept. The service only needs three operations, so moving
from a local folder to a cloud bucket is a configuration change."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def exists(self, key: str) -> bool: ...

    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def describe(self) -> str: ...


class LocalStorage:
    """Files under a root folder. Writes are atomic: a reader never sees half a file."""

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError(f"key escapes the storage root: {key!r}")
        return path

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def describe(self) -> str:
        return f"local:{self.root}"


class GcsStorage:
    """Objects in a Google Cloud Storage bucket.

    `bucket` is a google.cloud.storage.Bucket (or anything with the same
    blob()/exists()/upload_from_string() calls, which is how the tests drive it).
    """

    def __init__(self, bucket, prefix: str = ""):
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    def _name(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def exists(self, key: str) -> bool:
        return bool(self.bucket.blob(self._name(key)).exists())

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.bucket.blob(self._name(key)).upload_from_string(data, content_type=content_type)

    def describe(self) -> str:
        return f"gcs:{getattr(self.bucket, 'name', '?')}/{self.prefix}".rstrip("/")


def from_spec(spec: str) -> Storage:
    """`local:<folder>` or `gcs:<bucket>[/prefix]`."""
    kind, _, rest = spec.partition(":")
    if kind == "local" and rest:
        return LocalStorage(rest)
    if kind == "gcs" and rest:
        from google.cloud import storage as gcs  # optional dependency

        bucket_name, _, prefix = rest.partition("/")
        return GcsStorage(gcs.Client().bucket(bucket_name), prefix)
    raise ValueError(f"unknown storage {spec!r}: use local:<folder> or gcs:<bucket>[/prefix]")
