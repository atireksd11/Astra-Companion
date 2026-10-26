from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import DenoiseConfig  # noqa: E402
from core.denoise import denoise_pcm16_mono  # noqa: E402
from core.turn import Turn  # noqa: E402
from steps.denoise import make_denoise_step  # noqa: E402

SAMPLE_RATE = 16000


def _tone_with_noise(seconds: float = 0.5, noise_amp: float = 0.08) -> bytes:
    n = int(SAMPLE_RATE * seconds)
    rng = np.random.default_rng(42)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        s = 0.35 * math.sin(2 * math.pi * 440 * t) + noise_amp * rng.standard_normal()
        out.append(struct.pack("<h", int(max(-32768, min(32767, s * 32767)))))
    return b"".join(out)


def test_denoise_disabled_noop() -> None:
    pcm = _tone_with_noise()
    turn = Turn(rate_hz=SAMPLE_RATE)
    turn.pcm_in = bytearray(pcm)
    step = make_denoise_step(DenoiseConfig(enabled=False))
    step(turn)
    assert "denoise" not in turn.notes
    assert bytes(turn.pcm_in) == pcm


def test_denoise_noop_backend_and_zero_strength() -> None:
    pcm = _tone_with_noise()
    r1 = denoise_pcm16_mono(pcm, SAMPLE_RATE, backend="noop", strength=0.5)
    assert r1.pcm == pcm
    assert r1.backend == "noop"
    r2 = denoise_pcm16_mono(pcm, SAMPLE_RATE, backend="auto", strength=0.0)
    assert r2.pcm == pcm
    assert r2.backend == "noop"


def test_rnnoise_preserves_length_and_backend() -> None:
    pytest.importorskip("pyrnnoise")
    pcm = _tone_with_noise()
    for backend in ("rnnoise", "auto"):
        result = denoise_pcm16_mono(pcm, SAMPLE_RATE, backend=backend, strength=0.5)
        assert len(result.pcm) == len(pcm)
        assert result.backend in ("rnnoise", "deepfilternet")


def test_deepfilternet_preserves_length() -> None:
    try:
        from df.enhance import init_df  # noqa: F401
    except ImportError:
        pytest.skip("deepfilternet (df) not installed")
    pcm = _tone_with_noise()
    result = denoise_pcm16_mono(pcm, SAMPLE_RATE, backend="deepfilternet", strength=0.5)
    assert len(result.pcm) == len(pcm)
    assert result.backend == "deepfilternet"


def test_denoise_step_updates_turn() -> None:
    pytest.importorskip("pyrnnoise")
    pcm = _tone_with_noise()
    turn = Turn(rate_hz=SAMPLE_RATE)
    turn.pcm_in = bytearray(pcm)
    turn.notes["channels"] = 1
    step = make_denoise_step(DenoiseConfig(enabled=True, backend="auto", strength=0.5))
    step(turn)
    assert turn.notes.get("denoise")
    assert turn.notes["denoise"]["backend"] in ("rnnoise", "deepfilternet", "bypass")
    assert "snr_before_db" in turn.notes["denoise"]
    assert "snr_after_db" in turn.notes["denoise"]
    assert len(turn.pcm_in) == len(pcm)
    assert turn.notes.get("noise_before")
    assert turn.notes.get("noise_after")
