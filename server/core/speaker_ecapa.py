"""SpeechBrain ECAPA speaker embeddings (lazy-loaded)."""

from __future__ import annotations

from typing import Any

import numpy as np

_CLASSIFIER: Any | None = None
_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"


def set_ecapa_source(source: str) -> None:
    global _SOURCE, _CLASSIFIER
    if source != _SOURCE:
        _SOURCE = source
        _CLASSIFIER = None


def _get_classifier():
    global _CLASSIFIER
    if _CLASSIFIER is None:
        from speechbrain.inference.speaker import EncoderClassifier

        _CLASSIFIER = EncoderClassifier.from_hparams(source=_SOURCE)
    return _CLASSIFIER


def embed_pcm16_mono(pcm: bytes, rate: int = 16000) -> np.ndarray:
    if not pcm or rate <= 0:
        return np.zeros(192, dtype=np.float32)
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    import torch

    wav = torch.from_numpy(samples).unsqueeze(0)
    with torch.no_grad():
        emb = _get_classifier().encode_batch(wav)
    out = emb.squeeze().cpu().numpy().astype(np.float32)
    return out.reshape(-1)
