"""Lightweight speaker embedding (MFCC-ish) for focus / chatter rejection."""

from __future__ import annotations

import math

import numpy as np

FRAME = 320
HOP = 160
N_FFT = 512
N_MELS = 20
N_COEFF = 13


def _hz_to_mel(hz: float) -> float:
    return 2595.0 * math.log10(1.0 + hz / 700.0)


def _mel_filterbank(n_mels: int, n_fft: int, rate: int) -> np.ndarray:
    low = _hz_to_mel(80.0)
    high = _hz_to_mel(min(7600.0, rate / 2 - 1))
    mels = np.linspace(low, high, n_mels + 2)
    hz = 700.0 * (10 ** (mels / 2595.0) - 1.0)
    bins = np.floor((n_fft + 1) * hz / rate).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for i in range(n_mels):
        left, center, right = bins[i], bins[i + 1], bins[i + 2]
        if center <= left or right <= center:
            continue
        for j in range(left, center):
            if 0 <= j < fb.shape[1]:
                fb[i, j] = (j - left) / max(center - left, 1)
        for j in range(center, right):
            if 0 <= j < fb.shape[1]:
                fb[i, j] = (right - j) / max(right - center, 1)
    return fb


_MEL_FB = _mel_filterbank(N_MELS, N_FFT, 16000)


def _frame_mfcc(frame: np.ndarray) -> np.ndarray:
    if frame.size < N_FFT:
        frame = np.pad(frame, (0, N_FFT - frame.size))
    window = np.hanning(N_FFT).astype(np.float32)
    spec = np.abs(np.fft.rfft(frame * window, n=N_FFT))
    mel = _MEL_FB @ spec
    mel = np.log(mel + 1e-6)
    k = np.arange(N_COEFF, dtype=np.float32)
    n = np.arange(N_MELS, dtype=np.float32)
    cos_table = np.cos(math.pi / N_MELS * (n[:, None] + 0.5) * k[None, :])
    dct = cos_table.T @ mel
    return dct.astype(np.float32)


def embed_pcm16_mono(pcm: bytes, rate: int = 16000) -> np.ndarray:
    """Single vector for a clip (mean MFCC over frames)."""
    if not pcm or rate <= 0:
        return np.zeros(N_COEFF, dtype=np.float32)
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if samples.size < FRAME:
        return _frame_mfcc(samples)
    coeffs = []
    for start in range(0, samples.size - FRAME + 1, HOP):
        coeffs.append(_frame_mfcc(samples[start : start + FRAME]))
    if not coeffs:
        return _frame_mfcc(samples)
    return np.mean(coeffs, axis=0).astype(np.float32)


def frame_embeddings(pcm: bytes, rate: int = 16000) -> list[np.ndarray]:
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    out: list[np.ndarray] = []
    for start in range(0, max(1, samples.size - FRAME + 1), HOP):
        chunk = samples[start : start + FRAME]
        if chunk.size < FRAME // 2:
            break
        out.append(_frame_mfcc(chunk))
    return out


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0 or a.size != b.size:
        return 0.0
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def clip_similarity(pcm: bytes, ref: np.ndarray, rate: int = 16000) -> float:
    emb = embed_pcm16_mono(pcm, rate)
    return cosine_similarity(emb, ref)
