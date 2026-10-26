from __future__ import annotations

import math
import struct
from dataclasses import dataclass

FRAME_MS = 20
NOISE_FLOOR_MIN = 80
SPEECH_MULT = 3


@dataclass
class SegmentStats:
    raw_s: float
    trim_s: float
    speech_ratio: float
    leading_trim_ms: int
    trailing_trim_ms: int

    def to_dict(self) -> dict:
        return {
            "raw_s": round(self.raw_s, 3),
            "trim_s": round(self.trim_s, 3),
            "speech_ratio": round(self.speech_ratio, 3),
            "leading_trim_ms": self.leading_trim_ms,
            "trailing_trim_ms": self.trailing_trim_ms,
        }


def _frame_bytes(sample_rate: int) -> int:
    return sample_rate * FRAME_MS // 1000 * 2


def _frame_rms(pcm: bytes, offset: int, fb: int) -> int:
    n = fb // 2
    if n <= 0:
        return 0
    samples = struct.unpack(f"<{n}h", pcm[offset : offset + fb])
    acc = sum(s * s for s in samples)
    return int(math.sqrt(acc / n))


def trim_pcm16(
    pcm: bytes,
    sample_rate: int = 16000,
    aggressiveness: int = 2,  # kept for API; maps to threshold tweak
) -> tuple[bytes, SegmentStats]:
    """Strip leading/trailing silence using RMS (same idea as firmware VAD)."""
    del aggressiveness  # reserved
    raw_s = len(pcm) / (2 * sample_rate) if sample_rate else 0.0
    if not pcm:
        return b"", SegmentStats(raw_s, 0.0, 0.0, 0, 0)

    fb = _frame_bytes(sample_rate)
    if len(pcm) < fb:
        return pcm, SegmentStats(raw_s, raw_s, 1.0, 0, 0)

    n_frames = len(pcm) // fb
    levels = [_frame_rms(pcm, i * fb, fb) for i in range(n_frames)]
    win = max(5, int(300 / FRAME_MS))
    if len(levels) >= win:
        totals = [0]
        for level in levels:
            totals.append(totals[-1] + level)
        window_means = [
            (totals[i + win] - totals[i]) / win for i in range(len(levels) - win + 1)
        ]
        quiet = min(window_means)
        loud = max(window_means)
    else:
        ordered = sorted(levels)
        quiet = ordered[len(ordered) // 5]
        loud = ordered[min(len(ordered) - 1, (len(ordered) * 4) // 5)]

    # Drop only the quiet head and tail. A 2 s room tail is a long quiet
    # window; short dips inside the sentence stay in the clip.
    if loud > max(quiet, 1) * 1.55:
        boundary = max(NOISE_FLOOR_MIN, int(math.sqrt(max(quiet, 1) * loud)))
        speech_flags = [level >= boundary for level in levels]
    else:
        noise_floor = NOISE_FLOOR_MIN
        speech_flags = []
        for level in levels:
            thr = max(NOISE_FLOOR_MIN, noise_floor * SPEECH_MULT)
            is_speech = level >= thr
            speech_flags.append(is_speech)
            if not is_speech and level < thr:
                noise_floor = (noise_floor * 95 + level * 5) // 100
                if noise_floor < NOISE_FLOOR_MIN:
                    noise_floor = NOISE_FLOOR_MIN

    if not any(speech_flags):
        return b"", SegmentStats(raw_s, 0.0, 0.0, int(raw_s * 1000), 0)

    first = speech_flags.index(True)
    last = len(speech_flags) - 1 - speech_flags[::-1].index(True)
    start_byte = first * fb
    end_byte = min(len(pcm), (last + 1) * fb)
    trimmed = pcm[start_byte:end_byte]
    trim_s = len(trimmed) / (2 * sample_rate)
    ratio = trim_s / raw_s if raw_s > 0 else 0.0
    leading_ms = start_byte // 2 * 1000 // sample_rate
    trailing_ms = (len(pcm) - end_byte) // 2 * 1000 // sample_rate
    return trimmed, SegmentStats(raw_s, trim_s, ratio, leading_ms, trailing_ms)


def speech_seconds(pcm: bytes, sample_rate: int = 16000) -> float:
    trimmed, stats = trim_pcm16(pcm, sample_rate)
    return stats.trim_s if trimmed else 0.0
