"""Relative loudness → playback gain (Feature 6, not true ranging)."""

from __future__ import annotations

import math
import struct


def pcm16_mono_rms(pcm: bytes) -> float:
    if len(pcm) < 2:
        return 1.0
    n = len(pcm) // 2
    samples = struct.unpack(f"<{n}h", pcm[: n * 2])
    acc = sum(s * s for s in samples)
    return max(math.sqrt(acc / n), 1.0)


def compute_playback_gain(
    ref_rms: float,
    current_rms: float,
    *,
    min_gain: float = 0.45,
    max_gain: float = 1.8,
) -> dict:
    ref = max(ref_rms, 1.0)
    cur = max(current_rms, 1.0)
    raw = ref / cur
    gain = max(min_gain, min(max_gain, raw))
    return {
        "gain": round(gain, 3),
        "distance_rel": round(ref / cur, 3),
        "loudness_rms": round(cur, 1),
        "ref_rms": round(ref, 1),
    }


def apply_gain_pcm16(pcm: bytes, gain: float) -> bytes:
    if abs(gain - 1.0) < 1e-6 or not pcm:
        return pcm
    out = bytearray()
    for i in range(0, len(pcm), 2):
        s = struct.unpack("<h", pcm[i : i + 2])[0]
        v = int(max(-32768, min(32767, s * gain)))
        out.extend(struct.pack("<h", v))
    return bytes(out)
