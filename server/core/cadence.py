"""Pause and speaking-rate metrics from mono PCM16 (feature 9)."""

from __future__ import annotations

import struct

from core.vad_bridge import frame_vad

FRAME_MS = 20


def _frame_rms(pcm: bytes, offset: int, fb: int) -> float:
    n = fb // 2
    if n <= 0:
        return 0.0
    samples = struct.unpack(f"<{n}h", pcm[offset : offset + fb])
    acc = sum(s * s for s in samples)
    return (acc / n) ** 0.5


def measure_cadence(
    pcm: bytes,
    rate: int,
    *,
    min_pause_ms: int = 200,
) -> dict:
    fb = rate * FRAME_MS // 1000 * 2
    if len(pcm) < fb * 3:
        return {
            "peaks_per_s": 0.0,
            "pause_ms_median": 0.0,
            "pause_count": 0,
            "speech_frames": 0,
        }
    n_frames = len(pcm) // fb
    speech = []
    for i in range(n_frames):
        chunk = pcm[i * fb : (i + 1) * fb]
        speech.append(frame_vad(chunk, rate))

    pauses_ms: list[int] = []
    run = 0
    for is_sp in speech:
        if not is_sp:
            run += 1
        elif run > 0:
            ms = run * FRAME_MS
            if ms >= min_pause_ms:
                pauses_ms.append(ms)
            run = 0

    peaks = 0
    prev = False
    for is_sp in speech:
        if is_sp and not prev:
            peaks += 1
        prev = is_sp

    duration_s = max(len(pcm) / 2 / rate, 0.001)
    median_pause = float(sorted(pauses_ms)[len(pauses_ms) // 2]) if pauses_ms else 0.0
    return {
        "peaks_per_s": round(peaks / duration_s, 2),
        "pause_ms_median": round(median_pause, 1),
        "pause_count": len(pauses_ms),
        "speech_frames": sum(1 for s in speech if s),
    }
