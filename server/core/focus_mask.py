"""Drop non-owner speech windows before echo/STT (mono mic, no neural separator)."""

from __future__ import annotations

import struct

import numpy as np

from core.speaker_ecapa import embed_pcm16_mono
from core.speaker_id import cosine_similarity


def _frame_rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))


def mask_pcm_to_owner(
    pcm: bytes,
    ref: np.ndarray,
    rate: int,
    *,
    min_similarity: float,
    window_s: float = 0.55,
    hop_s: float = 0.25,
    speech_rms_mult: float = 2.2,
) -> tuple[bytes, int, float]:
    """
    Zero out windows that do not match the owner embedding.

    Returns (masked_pcm, mixed_ms, keep_ratio).
    mixed_ms = approximate ms of active speech attributed to other voices.
    keep_ratio = fraction of original RMS energy kept.
    """
    if ref.size != 192 or not pcm:
        return pcm, 0, 1.0

    samples = np.frombuffer(pcm, dtype=np.int16)
    n = samples.size
    win = max(int(window_s * rate), int(0.35 * rate))
    hop = max(int(hop_s * rate), int(0.15 * rate))
    if n < win:
        sim = cosine_similarity(ref, embed_pcm16_mono(pcm, rate))
        if sim >= min_similarity:
            return pcm, 0, 1.0
        return struct.pack(f"<{n}h", *([0] * n)), 0, 0.0

    levels = []
    for i in range(0, n - win + 1, hop):
        levels.append(_frame_rms(samples[i : i + win]))
    if not levels:
        return pcm, 0, 1.0
    median = float(np.median(levels))
    speech_floor = max(100.0, median * 0.72)

    keep = np.zeros(n, dtype=bool)
    mixed_ms = 0
    for start in range(0, n - win + 1, hop):
        chunk = samples[start : start + win]
        rms = _frame_rms(chunk)
        if rms < speech_floor:
            continue
        chunk_pcm = chunk.tobytes()
        probe = embed_pcm16_mono(chunk_pcm, rate)
        sim = cosine_similarity(ref, probe)
        if sim >= min_similarity:
            keep[start : start + win] = True
        else:
            mixed_ms += int(hop * 1000 / rate)

    if not keep.any():
        if mixed_ms == 0:
            return pcm, 0, 1.0
        return struct.pack(f"<{n}h", *([0] * n)), mixed_ms, 0.0

    out = np.where(keep, samples, 0).astype(np.int16)
    orig_energy = float(np.sum(samples.astype(np.float64) ** 2))
    kept_energy = float(np.sum(out.astype(np.float64) ** 2))
    keep_ratio = kept_energy / orig_energy if orig_energy > 0 else 0.0
    return out.tobytes(), mixed_ms, keep_ratio
