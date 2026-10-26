"""Estimate how noisy a mono PCM16 clip is (metadata only, not a gate)."""

from __future__ import annotations

import math
import struct

FRAME_MS = 20


def _frame_rms(pcm: bytes, offset: int, fb: int) -> float:
    n = fb // 2
    if n <= 0:
        return 0.0
    samples = struct.unpack(f"<{n}h", pcm[offset : offset + fb])
    acc = sum(s * s for s in samples)
    return math.sqrt(acc / n)


def analyze_mono_pcm(pcm: bytes, sample_rate: int = 16000) -> dict:
    """Return noise metrics for trimmed speech (before or after denoise)."""
    fb = sample_rate * FRAME_MS // 1000 * 2
    if len(pcm) < fb:
        return {
            "noise_floor_rms": 0.0,
            "speech_rms": 0.0,
            "snr_db": 0.0,
            "frames": 0,
        }
    n_frames = len(pcm) // fb
    levels = [_frame_rms(pcm, i * fb, fb) for i in range(n_frames)]
    levels.sort()
    noise_floor = levels[max(0, len(levels) // 10)]
    speech_rms = levels[min(len(levels) - 1, (len(levels) * 9) // 10)]
    if noise_floor < 1.0:
        noise_floor = 1.0
    snr = 20.0 * math.log10(max(speech_rms, 1.0) / noise_floor)
    return {
        "noise_floor_rms": round(noise_floor, 1),
        "speech_rms": round(speech_rms, 1),
        "snr_db": round(snr, 2),
        "frames": n_frames,
    }
