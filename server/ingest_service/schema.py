"""Event metadata sent by the device in the X-Event-Meta header (docs/PROTOCOL.md)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Frame(BaseModel):
    model_config = ConfigDict(extra="allow")

    w: int = Field(gt=0, le=4096)
    h: int = Field(gt=0, le=4096)
    bytes: int = Field(ge=0)


class ModelResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: int = Field(ge=0)
    label: str = Field(min_length=1, max_length=16)
    top: int = Field(ge=0, lt=8)
    q: list[int] = Field(min_length=1, max_length=8)


class EventMeta(BaseModel):
    # Unknown fields are kept, so newer firmware can add data without a server change.
    model_config = ConfigDict(extra="allow")

    v: Literal[1]
    # These three become part of the storage path: keep them to a safe alphabet.
    device: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,31}$")
    session: str = Field(pattern=r"^[0-9a-f]{8}$")
    seq: int = Field(ge=0, le=999_999)

    fw: str = Field(default="", max_length=32)
    wake: Literal["pir", "timer", "power_on"]
    mode: Literal["collect", "infer", "bench"]
    ts: int = Field(default=0, ge=0)
    dropped: int = Field(default=0, ge=0)
    rssi: int = 0
    image: bool
    frame: Frame | None = None
    t_ms: dict[str, int] = Field(default_factory=dict)
    model: ModelResult | None = None

    @property
    def key(self) -> str:
        """Storage key without extension. Same event, same key: retries are idempotent."""
        return f"captures/{self.device}/{self.session}/{self.seq:06d}"
