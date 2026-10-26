from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Turn:
    """One thing you said and the robot's answer."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)
    rate_hz: int = 16000
    pcm_in: bytearray = field(default_factory=bytearray)
    pcm_out: bytearray = field(default_factory=bytearray)
    pcm_for_analysis: bytes | None = None
    pcm_mood: bytes | None = None
    pcm_pre_denoise: bytes | None = None
    text_in: str = ""
    text_out: str = ""
    notes: dict[str, Any] = field(default_factory=dict)
    timings_ms: dict[str, float] = field(default_factory=dict)
    cost_usd: float = 0.0
    error: str | None = None

    def audio_in_seconds(self) -> float:
        return len(self.pcm_in) / (2 * self.rate_hz)
