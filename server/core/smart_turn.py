"""Pipecat Smart Turn v3 when the ONNX file is present."""

from __future__ import annotations

from pathlib import Path

import numpy as np

SERVER_ROOT = Path(__file__).resolve().parent.parent
_session = None
_model_path: Path | None = None


def _resolve_path(configured: str) -> Path:
    raw = Path(configured)
    if raw.is_absolute():
        return raw
    return SERVER_ROOT / raw


def available(configured: str) -> bool:
    return _resolve_path(configured).is_file()


def predict_turn_complete(pcm16: bytes, *, weights: str, sample_rate: int = 16000) -> bool | None:
    """True = done speaking, False = still talking, None = model unavailable."""
    global _session, _model_path
    path = _resolve_path(weights)
    if not path.is_file():
        return None
    if not pcm16:
        return True
    try:
        import onnxruntime as ort
    except ImportError:
        return None
    if _session is None or _model_path != path:
        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        _session = ort.InferenceSession(str(path), sess_options=so, providers=["CPUExecutionProvider"])
        _model_path = path
    samples = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
    max_s = 8 * sample_rate
    if samples.size > max_s:
        samples = samples[-max_s:]
    elif samples.size < max_s:
        samples = np.pad(samples, (max_s - samples.size, 0))
    try:
        from pipecat.audio.turn.smart_turn._whisper_features import compute_whisper_log_mel_features
    except ImportError:
        return None
    log_mel = compute_whisper_log_mel_features(samples, do_normalize=True)
    features = np.expand_dims(log_mel, axis=0).astype(np.float32)
    out = _session.run(None, {"input_features": features})[0]
    prob = float(out.reshape(-1)[0])
    return prob > 0.5
