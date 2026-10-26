"""Speaker profile document (features 8 + 9)."""

from __future__ import annotations

import math
import secrets
import time
from typing import Any

import numpy as np

from core.mood import empty_mood
from core.speaker_id import cosine_similarity

SCHEMA = 1
VOWELS = [
    "AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW",
]
EMA_ALPHA = 0.15
MIN_LEARN_S = 0.8
MIN_SNR_DB = 6.0


def new_speaker_id() -> str:
    return "spk_" + secrets.token_hex(4)


def _match_method(embedding: list[float] | None) -> str:
    n = len(embedding or [])
    if n == 192:
        return "ecapa192"
    if n == 13:
        return "mfcc13"
    return "unknown"


def empty_profile(speaker_id: str, embedding: list[float] | None = None) -> dict[str, Any]:
    now = time.time()
    return {
        "schema": SCHEMA,
        "speaker_id": speaker_id,
        "updated_at": now,
        "match": {"method": _match_method(embedding), "embedding": embedding or []},
        "pronunciation": {
            "status": "needs_aligner",
            "aligner": "none",
            "scored_words": 0,
            "phones": {},
            "vowels": VOWELS,
            "lexicon": [],
        },
        "cadence": {
            "status": "ok",
            "utterances": 0,
            "speaking_rate": {
                "method": "energy_peaks",
                "peaks_per_s_ema": 0.0,
                "words_per_min": None,
            },
            "pauses": {
                "min_pause_ms": 200,
                "median_ms_ema": 0.0,
                "per_utterance_ema": 0.0,
            },
            "fillers": {
                "status": "needs_transcript",
                "method": "none",
                "per_minute_ema": None,
                "counts": {"uh": 0, "um": 0, "er": 0},
            },
        },
        "mood": empty_mood(),
        "context": {
            "display_name": "",
            "call_name": "",
            "core_facts": [],
            "voice_id": "",
        },
    }


def ema(old: float, new: float, alpha: float = EMA_ALPHA) -> float:
    if old <= 0:
        return new
    return (1.0 - alpha) * old + alpha * new


def find_speaker_id(
    profiles: list[dict[str, Any]],
    embedding: np.ndarray,
    min_similarity: float,
) -> str | None:
    best_id: str | None = None
    best_sim = min_similarity
    for doc in profiles:
        emb = doc.get("match", {}).get("embedding") or []
        if not emb:
            continue
        ref = np.array(emb, dtype=np.float32)
        if ref.size != embedding.size:
            continue
        sim = cosine_similarity(embedding, ref)
        if sim >= best_sim:
            best_sim = sim
            best_id = str(doc["speaker_id"])
    return best_id


def _finite_float(value: Any) -> float | None:
    """A real number. Booleans and NaN are not durations or SNR readings."""
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def should_learn_turn(turn) -> tuple[bool, str | None]:
    """Return (ok, skip_reason)."""
    seg = turn.notes.get("segment")
    if seg is None:
        seg = {}
    elif not isinstance(seg, dict):
        return False, "clip_too_short"
    if "trim_s" in seg:
        trim_s = _finite_float(seg.get("trim_s"))
        if trim_s is None:
            return False, "clip_too_short"
    else:
        try:
            trim_s = float(turn.audio_in_seconds())
        except (TypeError, ValueError, ZeroDivisionError, OverflowError):
            return False, "clip_too_short"
        if not math.isfinite(trim_s):
            return False, "clip_too_short"
    if trim_s < MIN_LEARN_S:
        return False, "clip_too_short"
    if turn.notes.get("focus_warn") == "enroll_contaminated":
        return False, "enroll_contaminated"
    focus = turn.notes.get("focus")
    if focus is None:
        focus = {}
    elif not isinstance(focus, dict):
        return False, "too_mixed"
    mixed_ms = _finite_float(focus.get("mixed_ms", 0))
    if mixed_ms is None:
        return False, "too_mixed"
    if mixed_ms > trim_s * 500:  # > half the clip rejected as other voice
        return False, "too_mixed"
    noise = turn.notes.get("noise_after")
    if noise is None:
        noise = turn.notes.get("noise_before")
    if noise is None:
        noise = {}
    elif not isinstance(noise, dict):
        return False, "low_snr"
    if "snr_db" in noise and noise.get("snr_db") is not None:
        snr = _finite_float(noise.get("snr_db"))
        if snr is None or snr < MIN_SNR_DB:
            return False, "low_snr"
    if turn.notes.get("barged"):
        return False, "barged"
    if turn.error:
        return False, "turn_error"
    seg_raw = turn.notes.get("segment") or {}
    if seg_raw.get("too_long"):
        return False, "too_long"
    return True, None


def _json_ready(value: Any) -> Any:
    """Plain JSON values only. Bytes and PCM arrays are dropped, not stored."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(item, (bytes, bytearray, memoryview, np.ndarray)):
                continue
            out[str(key)] = _json_ready(item)
        return out
    if isinstance(value, (list, tuple)):
        return [
            _json_ready(item)
            for item in value
            if not isinstance(item, (bytes, bytearray, memoryview, np.ndarray))
        ]
    if isinstance(value, np.generic):
        return _json_ready(value.item())
    if isinstance(value, float) and (
        value != value or value == float("inf") or value == float("-inf")
    ):
        return None
    return value


def sanitize_notes_for_storage(notes: dict[str, Any]) -> dict[str, Any]:
    """Drop wake audio and ephemeral analysis fields before SQLite."""
    out = dict(notes)
    meta = dict(out.get("meta") or {})
    meta.pop("enroll_b64", None)
    meta.pop("wake_b64", None)
    if meta:
        out["meta"] = meta
    else:
        out.pop("meta", None)
    out.pop("speaker_embedding", None)
    out.pop("pcm_pre_denoise", None)
    out.pop("vision_image", None)
    return _json_ready(out)
