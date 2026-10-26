from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.segment import trim_pcm16  # noqa: E402
from tools.make_test_wav import write_tone  # noqa: E402


def test_trim_keeps_tone(tmp_path: Path) -> None:
    wav = tmp_path / "t.wav"
    write_tone(wav, seconds=1.0)
    import wave

    with wave.open(str(wav), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
    trimmed, stats = trim_pcm16(pcm, 16000)
    assert len(trimmed) > 0
    assert stats.trim_s > 0.5
    assert stats.speech_ratio > 0.5


def test_trim_drops_room_tail_after_speech() -> None:
    import math
    import struct

    import numpy as np

    sr = 16000
    n = sr * 2
    tone = bytearray()
    for i in range(n):
        s = int(6000 * math.sin(2 * math.pi * 180 * i / sr))
        tone.extend(struct.pack("<h", s))
    rng = np.random.default_rng(0)
    tail = (rng.standard_normal(sr) * 400).astype("<i2").tobytes()
    trimmed, stats = trim_pcm16(bytes(tone) + tail, sr)
    assert stats.trailing_trim_ms > 500
    assert abs(len(trimmed) - len(tone)) < sr * 2 // 5


def test_trim_silence_only_empty() -> None:
    pcm = b"\x00\x00" * (16000 // 50)  # 20 ms frames of silence
    trimmed, stats = trim_pcm16(pcm * 5, 16000)
    assert trimmed == b""
    assert stats.trim_s == 0.0
