"""Coarse speech-mood cue from a quantized wav2vec2 emotion model.

Five labels only: happy, sad, angry, neutral, surprised. Disgust and fear stay
out of the set. Calm maps to neutral only when it wins and clears both gates.
A miss, a short clip, or a broken model leaves the label null and the pipeline
running. This is a cue from acted speech, not a clinical read.
"""

from __future__ import annotations

import json
import math
import threading
from pathlib import Path
from typing import Any

import numpy as np

from core.config import MoodConfig

SERVER_ROOT = Path(__file__).resolve().parent.parent
RAW_LABELS = ("ANG", "CAL", "DIS", "FEA", "HAP", "NEU", "SAD", "SUR")
MOOD_LABELS = ("happy", "sad", "angry", "neutral", "surprised")
_COARSE = {
    "ANG": "angry",
    "HAP": "happy",
    "SAD": "sad",
    "NEU": "neutral",
    "SUR": "surprised",
}
_MIN_SECONDS = 0.8
_MAX_SECONDS = 6.0
_VAR_EPS = np.float32(1e-7)

_session_lock = threading.Lock()
_session: Any = None
_session_path: str | None = None


class _ModelUnavailable(Exception):
    """Weights missing or the ONNX session could not be created."""


def empty_mood() -> dict[str, Any]:
    """Uniform 5-way distribution. ema() must not seed this: 0 is a real mass."""
    return {
        "distribution": {name: 0.2 for name in MOOD_LABELS},
        "last_label": None,
        "last_confidence": 0,
        "samples": 0,
    }


def weights_path(cfg: MoodConfig) -> Path:
    raw = cfg.weights
    if not isinstance(raw, str) or not raw.strip():
        return SERVER_ROOT / "models" / "speech_emotion_int8.onnx.missing"
    path = Path(raw)
    if not path.is_absolute():
        path = SERVER_ROOT / path
    return path


def threshold_value(value: Any) -> float | None:
    """Finite threshold at or above zero. A bool or NaN shuts the gate."""
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out < 0.0:
        return None
    return out


def raw_supports_label(raw: Any, label: str) -> bool:
    """True only when this raw winner is allowed to wear that coarse label."""
    if label not in MOOD_LABELS or not isinstance(raw, str):
        return False
    if raw == "CAL":
        return label == "neutral"
    if raw in ("DIS", "FEA"):
        return False
    return _COARSE.get(raw) == label


def hello_status(cfg: MoodConfig) -> dict[str, Any]:
    """Hello fields. ready is the file on disk, not a loaded session."""
    return {
        "enabled": bool(cfg.enabled),
        "backend": str(cfg.backend),
        "ready": bool(weights_path(cfg).is_file()),
    }


def map_label(
    raw: str | None,
    confidence: Any,
    margin: Any,
    min_confidence: Any,
    min_margin: Any,
) -> str | None:
    """Coarse label, or null when the winner is out of set or not decisive.

    A non-finite score or threshold does not pass. ``x < NaN`` is false in
    IEEE math, and that must not open the gate.
    """
    if raw in ("DIS", "FEA"):
        return None
    conf = threshold_value(confidence)
    gap = threshold_value(margin)
    floor = threshold_value(min_confidence)
    gap_floor = threshold_value(min_margin)
    if conf is None or gap is None or floor is None or gap_floor is None:
        return None
    if conf < floor or gap < gap_floor:
        return None
    if raw == "CAL":
        return "neutral"
    if raw is None:
        return None
    return _COARSE.get(raw)


def _prior_distribution(previous: dict[str, Any] | None) -> dict[str, float]:
    """Full 5-way prior. A stored 0 is real mass and is kept.

    Missing keys, negatives, or a vector that does not sum to 1 fall back to
    uniform. Filling a hole with 0.2 would push the total off 1.
    """
    uniform = {name: 0.2 for name in MOOD_LABELS}
    if not isinstance(previous, dict):
        return uniform
    vals: dict[str, float] = {}
    for name in MOOD_LABELS:
        if name not in previous:
            return uniform
        try:
            value = float(previous[name])
        except (TypeError, ValueError):
            return uniform
        if not math.isfinite(value) or value < 0.0:
            return uniform
        vals[name] = value
    if abs(sum(vals.values()) - 1.0) > 1e-3:
        return uniform
    return vals


def blend_distribution(
    previous: dict[str, Any],
    label: str,
    alpha: float,
) -> dict[str, float]:
    """p = (1 - alpha) * p + alpha * one_hot(label). Does not use speech_profile.ema.

    speech_profile.ema() treats a stored 0 as unset and would jump that class to 1.
    """
    prior = _prior_distribution(previous)
    if label not in MOOD_LABELS:
        return prior
    out: dict[str, float] = {}
    keep = 1.0 - float(alpha)
    gain = float(alpha)
    for name in MOOD_LABELS:
        hit = 1.0 if name == label else 0.0
        out[name] = keep * prior[name] + gain * hit
    return out


def _note(
    label: str | None,
    confidence: float,
    backend: str,
    raw_label: str | None,
) -> dict[str, Any]:
    label_out = label if isinstance(label, str) and label in MOOD_LABELS else None
    raw_out = raw_label if isinstance(raw_label, str) and raw_label in RAW_LABELS else None
    conf = threshold_value(confidence)
    if conf is None:
        conf_out: int | float = 0
        label_out = None
    elif conf == 0:
        conf_out = 0
        label_out = None
    else:
        conf_out = conf
    if isinstance(backend, str) and backend:
        backend_out = backend[:120]
    else:
        backend_out = "unavailable"
    return {
        "label": label_out,
        "confidence": conf_out,
        "backend": backend_out,
        "raw_label": raw_out,
    }


def client_view(note: Any) -> dict[str, Any] | None:
    """The four JSON fields a client may see. Extra keys, bytes, and NaN are dropped."""
    if not isinstance(note, dict):
        return None
    raw = note.get("raw_label")
    label = note.get("label")
    if not isinstance(label, str) or not raw_supports_label(raw, label):
        label = None
    backend = note.get("backend")
    cleaned = _note(
        label,
        note.get("confidence", 0),
        backend if isinstance(backend, str) else "unavailable",
        raw if isinstance(raw, str) else None,
    )
    try:
        json.dumps(cleaned, allow_nan=False)
    except (TypeError, ValueError):
        return _note(None, 0, "unavailable", None)
    return cleaned


def _cap_seconds(cfg: MoodConfig) -> float:
    """At most 6 s. A missing, non-finite, or non-positive cap does not lift the limit."""
    cap = threshold_value(cfg.max_seconds)
    if cap is None or cap <= 0.0:
        return _MAX_SECONDS
    return min(cap, _MAX_SECONDS)


def _softmax(logits: np.ndarray) -> np.ndarray:
    z = np.asarray(logits, dtype=np.float64).reshape(-1)
    if z.size != len(RAW_LABELS) or not np.all(np.isfinite(z)):
        raise ValueError("mood logits")
    z = z - np.max(z)
    exp = np.exp(z)
    total = float(exp.sum())
    if total <= 0.0 or not np.isfinite(total):
        raise ValueError("mood softmax")
    return exp / total


def note_from_logits(logits: np.ndarray, cfg: MoodConfig) -> dict[str, Any]:
    probs = _softmax(logits)
    order = np.argsort(probs)
    top = int(order[-1])
    second = int(order[-2])
    confidence = float(probs[top])
    margin = float(probs[top] - probs[second])
    raw = RAW_LABELS[top]
    label = map_label(
        raw,
        confidence,
        margin,
        cfg.min_confidence,
        cfg.min_margin,
    )
    return _note(label, confidence, cfg.backend, raw)


def prepare_samples(pcm: bytes, rate: int, cfg: MoodConfig) -> np.ndarray | None:
    """Int16 PCM to the wav2vec2 preprocessor: /32768, then zero mean and unit variance.

    Returns None when the clip is under 0.8 s after the cap. Longer clips are
    cut to at most 6 s from the start (96000 samples at 16 kHz). A configured
    max_seconds above 6, or a non-positive value, does not lift that cap.
    """
    if rate <= 0 or not pcm:
        return None
    n = len(pcm) // 2
    max_n = int(_cap_seconds(cfg) * int(rate))
    if max_n <= 0:
        return None
    n = min(n, max_n)
    if n < int(_MIN_SECONDS * rate):
        return None
    x = np.frombuffer(pcm[: n * 2], dtype="<i2").astype(np.float32)
    x = x / np.float32(32768.0)
    mean = np.mean(x)
    var = np.mean((x - mean) ** 2)
    x = (x - mean) / np.sqrt(var + _VAR_EPS)
    return np.ascontiguousarray(x, dtype=np.float32)


def _input_name(session: Any) -> str:
    names = [item.name for item in session.get_inputs()]
    if "input_values" in names:
        return "input_values"
    if not names:
        raise RuntimeError("mood model has no inputs")
    return names[0]


def _get_session(path: Path) -> Any:
    global _session, _session_path
    key = str(path)
    with _session_lock:
        if _session is not None and _session_path == key:
            return _session
        import onnxruntime as ort

        try:
            session = ort.InferenceSession(key, providers=["CPUExecutionProvider"])
        except Exception as exc:
            raise _ModelUnavailable(exc.__class__.__name__) from exc
        _session = session
        _session_path = key
        return session


def infer_logits(samples: np.ndarray, cfg: MoodConfig) -> np.ndarray:
    session = _get_session(weights_path(cfg))
    name = _input_name(session)
    feed = np.ascontiguousarray(samples, dtype=np.float32).reshape(1, -1)
    outputs = session.run(None, {name: feed})
    if not outputs:
        raise RuntimeError("mood model returned no outputs")
    return np.asarray(outputs[0]).reshape(-1)


def _logits_for(samples: np.ndarray, cfg: MoodConfig) -> np.ndarray:
    path = weights_path(cfg)
    if not path.is_file():
        raise _ModelUnavailable("missing")
    return infer_logits(samples, cfg)


def score_mood(pcm: bytes, rate: int, cfg: MoodConfig) -> dict[str, Any]:
    """Score one clip. Never raises. Missing weights and session failure stay unavailable."""
    try:
        samples = prepare_samples(pcm, rate, cfg)
        if samples is None:
            return _note(None, 0, "too_short", None)
        try:
            logits = _logits_for(samples, cfg)
        except _ModelUnavailable:
            return _note(None, 0, "unavailable", None)
        return note_from_logits(logits, cfg)
    except Exception as exc:
        return _note(
            None,
            0,
            f"wav2vec2_ser_int8_error: {exc.__class__.__name__}",
            None,
        )
