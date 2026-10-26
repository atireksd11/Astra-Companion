from __future__ import annotations

import math
import struct
import sys
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.focus_mask import mask_pcm_to_owner  # noqa: E402

SR = 16000


def _tone(hz: float, seconds: float, amp: float = 0.4) -> bytes:
    n = int(SR * seconds)
    out = []
    for i in range(n):
        s = int(amp * 32767 * math.sin(2 * math.pi * hz * i / SR))
        out.append(struct.pack("<h", s))
    return b"".join(out)


def _fake_ecapa(pcm: bytes, rate: int = 16000) -> np.ndarray:
    if not pcm:
        return np.zeros(192, dtype=np.float32)
    s = np.frombuffer(pcm, dtype=np.int16).astype(np.float64)
    bucket = int(abs(s[: min(len(s), 800)].mean()) % 192)
    v = np.zeros(192, dtype=np.float32)
    v[bucket] = 1.0
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-8 else v


def test_mask_keeps_owner_tone_zeros_other() -> None:
    t200 = _tone(200, 0.55)
    t900 = _tone(900, 0.55)
    owner = _fake_ecapa(t200)
    pcm = _tone(200, 1.0) + _tone(900, 1.0)
    calls = 0

    def side(pcm_in: bytes, rate: int = 16000) -> np.ndarray:
        nonlocal calls
        calls += 1
        if calls > 4:
            return _fake_ecapa(t900)
        return _fake_ecapa(t200)

    with mock.patch("core.focus_mask.embed_pcm16_mono", side_effect=side):
        masked, mixed_ms, keep_ratio = mask_pcm_to_owner(
            pcm, owner, SR, min_similarity=0.9
        )
    assert keep_ratio < 1.0
    assert keep_ratio > 0.05
    assert max(masked) > 0
