"""Silero VAD helpers for the laptop client (16 kHz mono)."""

from __future__ import annotations

from typing import Any

import numpy as np

_MODEL: Any | None = None
_WINDOW = 512  # Silero @ 16 kHz


def load_model():
    global _MODEL
    if _MODEL is None:
        from silero_vad import load_silero_vad

        _MODEL = load_silero_vad()
    return _MODEL


def frame_speech_prob(pcm_frame: bytes) -> float:
    """Silero speech probability for one 512-sample (32 ms) mono PCM16 frame."""
    if len(pcm_frame) < _WINDOW * 2:
        return 0.0
    import torch

    model = load_model()
    chunk = pcm_frame[: _WINDOW * 2]
    samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
    wav = torch.from_numpy(samples)
    with torch.no_grad():
        return float(model(wav, 16000).item())


def frame_is_speech(pcm_frame: bytes, threshold: float = 0.5) -> bool:
    return frame_speech_prob(pcm_frame) >= threshold


def frame_is_speech_hysteresis(
    pcm_frame: bytes,
    *,
    capturing: bool,
    start_threshold: float = 0.5,
    continue_threshold: float = 0.62,
    end_threshold: float = 0.38,
) -> bool:
    """While capturing, require stronger speech to stay open (ignores faint chatter)."""
    prob = frame_speech_prob(pcm_frame)
    if not capturing:
        return prob >= start_threshold
    if prob >= continue_threshold:
        return True
    if prob <= end_threshold:
        return False
    return False


def speech_ms_in_pcm(pcm: bytes, threshold: float = 0.5) -> int:
    """Count speech frames for enroll length checks."""
    if not pcm:
        return 0
    n = 0
    for i in range(0, len(pcm) - _WINDOW * 2 + 1, _WINDOW * 2):
        if frame_is_speech(pcm[i : i + _WINDOW * 2], threshold):
            n += 1
    return n * 32
