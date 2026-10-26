"""Pretrained mono denoisers for PCM16 @ 16 kHz (RNNoise, DeepFilterNet)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

_RNNOISE: Any | None = None
_DF: tuple[Any, Any] | None = None
_DF_IMPORT_OK: bool | None = None
_RNNOISE_IMPORT_OK: bool | None = None

_DF_SR = 48000


@dataclass
class DenoiseResult:
    pcm: bytes
    backend: str
    snr_before_db: float
    snr_after_db: float


def _pcm16_to_float(pcm: bytes) -> np.ndarray:
    if not pcm:
        return np.array([], dtype=np.float32)
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def _estimate_snr_db(samples: np.ndarray) -> float:
    if samples.size < 64:
        return 0.0
    frame = 320
    n = samples.size // frame
    if n == 0:
        rms = float(np.sqrt(np.mean(samples**2)))
        return 20.0 * math.log10(max(rms, 1e-6) / 1e-4)
    rmses = []
    for i in range(n):
        chunk = samples[i * frame : (i + 1) * frame]
        rmses.append(float(np.sqrt(np.mean(chunk**2))))
    rmses.sort()
    floor = max(rmses[max(0, len(rmses) // 10)], 1e-6)
    speech = max(rmses[min(len(rmses) - 1, (len(rmses) * 9) // 10)], floor)
    return 20.0 * math.log10(speech / floor)


def _df_available() -> bool:
    global _DF_IMPORT_OK
    if _DF_IMPORT_OK is None:
        try:
            from df.enhance import enhance, init_df  # noqa: F401

            _DF_IMPORT_OK = True
        except ImportError:
            _DF_IMPORT_OK = False
    return _DF_IMPORT_OK


def _rnnoise_available() -> bool:
    global _RNNOISE_IMPORT_OK
    if _RNNOISE_IMPORT_OK is None:
        try:
            from pyrnnoise import RNNoise  # noqa: F401

            _RNNOISE_IMPORT_OK = True
        except ImportError:
            _RNNOISE_IMPORT_OK = False
    return _RNNOISE_IMPORT_OK


def _get_rnnoise() -> Any:
    global _RNNOISE
    if _RNNOISE is None:
        from pyrnnoise import RNNoise

        _RNNOISE = RNNoise(sample_rate=16000)
    return _RNNOISE


def _get_df() -> tuple[Any, Any]:
    global _DF
    if _DF is None:
        from df.enhance import init_df

        model, df_state, _suffix = init_df()
        _DF = (model, df_state)
    return _DF


def _atten_lim_db(strength: float) -> float | None:
    if strength >= 0.95:
        return None
    s = max(0.0, min(1.0, strength))
    return 24.0 * (1.0 - s)


def _match_length_int16(out: np.ndarray, n_samples: int) -> np.ndarray:
    if out.size > n_samples:
        return out[:n_samples]
    if out.size < n_samples:
        pad = np.zeros(n_samples - out.size, dtype=np.int16)
        return np.concatenate([out, pad])
    return out


def _rnnoise_chunks(denoiser: Any, arr: np.ndarray) -> bytes:
    parts: list[np.ndarray] = []
    for _vad, audio in denoiser.denoise_chunk(arr, partial=True):
        parts.append(np.asarray(audio, dtype=np.int16).reshape(-1))
    if not parts:
        return b""
    out = np.concatenate(parts)
    return _match_length_int16(out, arr.size).tobytes()


def _denoise_rnnoise(pcm: bytes, rate: int) -> bytes:
    if rate != 16000:
        return pcm
    arr = np.frombuffer(pcm, dtype=np.int16)
    if arr.size == 0:
        return pcm
    denoiser = _get_rnnoise()
    denoiser.reset()
    cleaned = _rnnoise_chunks(denoiser, arr)
    return cleaned or pcm


def _denoise_rnnoise_fresh(pcm: bytes, rate: int) -> bytes:
    """One wake clip. A new RNNoise, never the process-wide `_RNNOISE`."""
    if rate != 16000:
        return pcm
    arr = np.frombuffer(pcm, dtype=np.int16)
    if arr.size == 0:
        return pcm
    from pyrnnoise import RNNoise

    denoiser = RNNoise(sample_rate=16000)
    denoiser.reset()
    return _rnnoise_chunks(denoiser, arr)


def _denoise_deepfilternet(pcm: bytes, rate: int, strength: float) -> bytes:
    import torch
    import torchaudio
    from df.enhance import enhance

    model, df_state = _get_df()
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    n_in = samples.size
    if n_in == 0:
        return pcm
    wav = torch.from_numpy(samples).unsqueeze(0)
    if rate != _DF_SR:
        wav = torchaudio.functional.resample(wav, rate, _DF_SR)
    atten = _atten_lim_db(strength)
    if atten is None:
        enhanced = enhance(model, df_state, wav, pad=True)
    else:
        enhanced = enhance(model, df_state, wav, pad=True, atten_lim_db=atten)
    if rate != _DF_SR:
        enhanced = torchaudio.functional.resample(enhanced, _DF_SR, rate)
    out = enhanced.squeeze(0).detach().cpu().numpy()
    if out.size > n_in:
        out = out[:n_in]
    elif out.size < n_in:
        out = np.pad(out, (0, n_in - out.size))
    clipped = np.clip(out, -1.0, 1.0)
    return (clipped * 32767.0).astype(np.int16).tobytes()


def _resolve_backend(backend: str) -> str:
    b = backend.strip().lower()
    if b == "auto":
        if _df_available():
            return "deepfilternet"
        if _rnnoise_available():
            return "rnnoise"
        return "bypass"
    return b


def _denoise_pcm16(
    pcm: bytes,
    rate: int,
    *,
    backend: str,
    strength: float,
    fresh_rnnoise: bool,
) -> DenoiseResult:
    """Denoise mono PCM16. Output length always matches input."""
    if not pcm or rate <= 0:
        return DenoiseResult(pcm, "noop", 0.0, 0.0)

    floats = _pcm16_to_float(pcm)
    snr_before = _estimate_snr_db(floats)

    if backend.strip().lower() == "noop" or strength <= 0:
        return DenoiseResult(pcm, "noop", snr_before, snr_before)

    chosen = _resolve_backend(backend)
    if chosen == "bypass":
        return DenoiseResult(pcm, "bypass", snr_before, snr_before)

    try:
        if chosen == "deepfilternet":
            if not _df_available():
                return DenoiseResult(pcm, "bypass", snr_before, snr_before)
            cleaned = _denoise_deepfilternet(pcm, rate, strength)
            used = "deepfilternet"
        elif chosen == "rnnoise":
            if not _rnnoise_available():
                return DenoiseResult(pcm, "bypass", snr_before, snr_before)
            if fresh_rnnoise:
                cleaned = _denoise_rnnoise_fresh(pcm, rate)
            else:
                cleaned = _denoise_rnnoise(pcm, rate)
            used = "rnnoise"
        else:
            return DenoiseResult(pcm, "bypass", snr_before, snr_before)
    except Exception:
        return DenoiseResult(pcm, "bypass", snr_before, snr_before)

    if not cleaned or len(cleaned) != len(pcm):
        cleaned = pcm

    snr_after = _estimate_snr_db(_pcm16_to_float(cleaned))
    return DenoiseResult(cleaned, used, snr_before, snr_after)


def denoise_pcm16_mono(
    pcm: bytes,
    rate: int,
    *,
    backend: str = "auto",
    strength: float = 0.5,
) -> DenoiseResult:
    """Denoise mono PCM16 with the shared RNNoise instance."""
    return _denoise_pcm16(
        pcm, rate, backend=backend, strength=strength, fresh_rnnoise=False
    )


def denoise_pcm16_fresh(
    pcm: bytes,
    rate: int,
    *,
    backend: str = "auto",
    strength: float = 0.5,
) -> DenoiseResult:
    """Denoise one clip without touching `_RNNOISE`.

    The shared RNNoise object keeps state from the utterance denoise step and
    warps a short wake clip into a near-zero owner score.
    """
    return _denoise_pcm16(
        pcm, rate, backend=backend, strength=strength, fresh_rnnoise=True
    )
