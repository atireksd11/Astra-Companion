"""Direction of arrival from stereo PCM16 (GCC-PHAT delay → azimuth)."""

from __future__ import annotations

import math
import struct

import numpy as np

SPEED_OF_SOUND_M_S = 343.0
DEFAULT_BASELINE_M = 0.04
DEFAULT_MIC_SPACING_M = DEFAULT_BASELINE_M  # legacy alias for tests/tools


def split_stereo_interleaved(pcm: bytes) -> tuple[bytes, bytes]:
    """Split LRLR… PCM16 into separate left and right channel byte blobs."""
    n_frames = len(pcm) // 4
    left = bytearray(n_frames * 2)
    right = bytearray(n_frames * 2)
    for i in range(n_frames):
        off = i * 4
        l, r = struct.unpack_from("<hh", pcm, off)
        struct.pack_into("<h", left, i * 2, l)
        struct.pack_into("<h", right, i * 2, r)
    return bytes(left), bytes(right)


def _pcm16_to_float(pcm: bytes) -> np.ndarray:
    if not pcm:
        return np.array([], dtype=np.float64)
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float64) / 32768.0


def _peak_confidence(window: np.ndarray) -> tuple[int, float]:
    peak_idx = int(np.argmax(window))
    peak = float(window[peak_idx])
    rest = np.delete(window, peak_idx)
    second = float(np.max(rest)) if rest.size else 1e-12
    confidence = float(min(1.0, max(0.0, (peak / (second + 1e-12) - 1.0) / 4.0)))
    return peak_idx, confidence


def _gcc_phat_tau(
    left: np.ndarray,
    right: np.ndarray,
    max_tau_samples: int,
) -> tuple[int, float]:
    """Positive tau ⇒ right lags left (GCC-PHAT peak + time-domain delay estimate)."""
    if left.size == 0 or right.size == 0:
        return 0, 0.0
    n_fft = int(2 ** math.ceil(math.log2(left.size + right.size)))
    f_left = np.fft.rfft(left, n=n_fft)
    f_right = np.fft.rfft(right, n=n_fft)
    cross = f_left * np.conj(f_right)
    denom = np.abs(cross)
    denom[denom < 1e-12] = 1e-12
    cc = np.fft.irfft(cross / denom, n=n_fft)
    cc = np.concatenate((cc[-max_tau_samples:], cc[: max_tau_samples + 1]))
    _, phat_conf = _peak_confidence(np.abs(cc))

    corr = np.correlate(right, left, mode="full")
    center = left.size - 1
    lo = max(0, center - max_tau_samples)
    hi = min(corr.size, center + max_tau_samples + 1)
    td_window = np.abs(corr[lo:hi])
    rel_peak, td_conf = _peak_confidence(td_window)
    tau = (lo + rel_peak) - center
    return tau, max(phat_conf, td_conf)


def delay_samples_to_azimuth_deg(
    delay_samples: int,
    sample_rate: int,
    mic_spacing_m: float = DEFAULT_BASELINE_M,
    *,
    speed_of_sound: float = SPEED_OF_SOUND_M_S,
) -> float:
    """Positive delay ⇒ right lags left ⇒ source to the left (+azimuth)."""
    if sample_rate <= 0 or mic_spacing_m <= 0:
        return 0.0
    tau = delay_samples / sample_rate
    s = (speed_of_sound * tau) / mic_spacing_m
    s = max(-1.0, min(1.0, s))
    return math.degrees(math.asin(s))


def estimate_azimuth_deg(
    left: bytes,
    right: bytes,
    rate: int,
    baseline_m: float = DEFAULT_BASELINE_M,
    speed_of_sound: float = SPEED_OF_SOUND_M_S,
) -> tuple[float, float]:
    """
    GCC-PHAT direction estimate for a horizontal mic pair.

    Returns (angle_deg, confidence 0–1). 0° = broadside (center).
    """
    if rate <= 0 or baseline_m <= 0:
        return 0.0, 0.0
    s_l = _pcm16_to_float(left)
    s_r = _pcm16_to_float(right)
    n = min(len(s_l), len(s_r))
    if n < max(rate // 10, 8):
        return 0.0, 0.0
    s_l = s_l[:n]
    s_r = s_r[:n]

    max_tau = max(1, int(rate * baseline_m / speed_of_sound) + 1)
    tau, confidence = _gcc_phat_tau(s_l, s_r, max_tau)
    angle = delay_samples_to_azimuth_deg(
        tau, rate, baseline_m, speed_of_sound=speed_of_sound
    )
    return angle, confidence


def estimate_azimuth_from_stereo_pcm(
    pcm_stereo: bytes,
    sample_rate: int = 16000,
    *,
    mic_spacing_m: float = DEFAULT_BASELINE_M,
) -> float | None:
    """Single interleaved blob → azimuth or None if too short."""
    left, right = split_stereo_interleaved(pcm_stereo)
    if len(left) < sample_rate // 5:
        return None
    angle, _conf = estimate_azimuth_deg(
        left, right, sample_rate, baseline_m=mic_spacing_m
    )
    return angle
