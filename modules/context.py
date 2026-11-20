"""Shared, read-only data passed to dashboard modules for each frame."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Geometry:
    cols: int
    lines: int
    left_inner: int
    right_inner: int
    body_h: int
    day_h: int


@dataclass(frozen=True)
class Frame:
    now: datetime
    geo: Geometry
    weather: Any
    status: str
    stale: bool
    padding: int
    location: str
    version: str
    rain_full: float
