"""Build interleaved stereo PCM16 in memory for DOA / bridge tests."""

from __future__ import annotations

import math
import struct

import numpy as np


def mono_tone_pcm16(
    sample_rate: int = 16000,
    seconds: float = 0.5,
    hz: float = 440.0,
    amplitude: int = 8000,
) -> bytes:
    n = int(sample_rate * seconds)
    out = bytearray()
    for i in range(n):
        t = i / sample_rate
        sample = int(amplitude * math.sin(2 * math.pi * hz * t))
        out.extend(struct.pack("<h", sample))
    return bytes(out)


def delay_mono_pcm(mono: bytes, delay_samples: int) -> bytes:
    if delay_samples <= 0:
        return mono
    pad = b"\x00\x00" * delay_samples
    return pad + mono[: len(mono) - delay_samples * 2]


def interleave_stereo(left: bytes, right: bytes) -> bytes:
    n = min(len(left), len(right)) // 2
    out = bytearray(n * 4)
    for i in range(n):
        out[i * 4 : i * 4 + 2] = left[i * 2 : i * 2 + 2]
        out[i * 4 + 2 : i * 4 + 4] = right[i * 2 : i * 2 + 2]
    return bytes(out)


def stereo_pcm_with_right_delay(
    mono: bytes,
    delay_samples: int,
) -> bytes:
    """Right channel lags left by ``delay_samples`` (sound arrives at left first)."""
    left = mono
    right = delay_mono_pcm(mono, delay_samples)
    return interleave_stereo(left, right)


def stereo_pcm_with_left_delay(
    mono: bytes,
    delay_samples: int,
) -> bytes:
    """Left channel lags right (sound arrives at right first)."""
    left = delay_mono_pcm(mono, delay_samples)
    right = mono
    return interleave_stereo(left, right)


def silence_pcm16(sample_rate: int, seconds: float) -> bytes:
    n = int(sample_rate * seconds)
    return b"\x00\x00" * n


def noise_burst_pcm16(
    sample_rate: int = 16000,
    seconds: float = 0.3,
    amplitude: float = 9000.0,
    seed: int = 42,
) -> bytes:
    """Wideband noise (stable seed) for GCC-PHAT tests without tone harmonics."""
    rng = np.random.default_rng(seed)
    n = int(sample_rate * seconds)
    samples = (rng.standard_normal(n) * amplitude).astype(np.int16)
    return samples.tobytes()
