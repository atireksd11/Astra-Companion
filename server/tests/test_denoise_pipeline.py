from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import DenoiseConfig  # noqa: E402
from core.turn import Turn  # noqa: E402
from steps.denoise import make_denoise_step  # noqa: E402
from steps.echo import echo_step  # noqa: E402

SR = 16000


def _tone_pcm(seconds: float = 0.6) -> bytes:
    n = int(SR * seconds)
    out = []
    for i in range(n):
        s = int(8000 * np.sin(2 * np.pi * 440 * i / SR))
        out.append(struct.pack("<h", s))
    return b"".join(out)


def _rms(pcm: bytes) -> float:
    a = np.frombuffer(pcm, dtype=np.int16).astype(np.float64)
    return float(np.sqrt(np.mean(a**2)))


def test_denoise_before_echo_changes_playback() -> None:
    pcm = _tone_pcm()
    turn = Turn(rate_hz=SR)
    turn.pcm_in = bytearray(pcm)
    turn.notes["channels"] = 1
    make_denoise_step(DenoiseConfig(enabled=True, backend="auto", strength=0.5))(turn)
    echo_step(turn)
    assert bytes(turn.pcm_out) == bytes(turn.pcm_in)


def test_echo_before_denoise_leaves_stale_pcm_out() -> None:
    """Document why config normalizes step order."""
    pcm = _tone_pcm()
    turn = Turn(rate_hz=SR)
    turn.pcm_in = bytearray(pcm)
    turn.notes["channels"] = 1
    echo_step(turn)
    out_before = bytes(turn.pcm_out)
    make_denoise_step(DenoiseConfig(enabled=True, backend="auto", strength=0.5))(turn)
    assert bytes(turn.pcm_out) == out_before
    assert "denoise" in turn.notes
