from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.cadence import measure_cadence  # noqa: E402
from core.fillers import count_fillers, is_real_transcript  # noqa: E402


def _silence(seconds: float, rate: int = 16000) -> bytes:
    n = int(rate * seconds)
    return b"\x00\x00" * n


def _tone(seconds: float, rate: int = 16000) -> bytes:
    n = int(rate * seconds)
    out = []
    for i in range(n):
        s = int(8000 * math.sin(2 * math.pi * 440 * i / rate))
        out.append(struct.pack("<h", s))
    return b"".join(out)


def test_internal_pause_detected() -> None:
    pcm = _tone(0.5) + _silence(0.35) + _tone(0.5)
    stats = measure_cadence(pcm, 16000, min_pause_ms=200)
    assert stats["pause_count"] >= 1
    assert stats["pause_ms_median"] >= 200


def test_fillers_ignore_placeholder() -> None:
    assert not is_real_transcript("[audio 1.2s]")
    assert count_fillers("[audio 1.2s]")["uh"] == 0


def test_fillers_count_tokens() -> None:
    c = count_fillers("well uh I um think er yes")
    assert c["uh"] == 1
    assert c["um"] == 1
    assert c["er"] == 1
