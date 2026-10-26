"""Pipeline step: coarse mood cue, then a slow profile blend when every gate passes."""

from __future__ import annotations

import json
import math
import time
from typing import Any

import numpy as np

from core.config import FocusConfig, MoodConfig, ProfileConfig
from core.langutil import is_english_turn
from core.mood import (
    MOOD_LABELS,
    blend_distribution,
    client_view,
    empty_mood,
    raw_supports_label,
    score_mood,
    threshold_value,
)
from core.speech_profile import should_learn_turn
from core.turn import Turn
from core.vad_bridge import pcm16_to_mono
from store.profiles import ProfileStore


def _analysis_pcm(turn: Turn) -> bytes:
    """Owner-masked clip when focus made one, else the analysis clip. Never raw pre-denoise."""
    pcm = turn.pcm_mood if turn.pcm_mood is not None else turn.pcm_for_analysis
    if pcm is None:
        pcm = bytes(turn.pcm_in)
    else:
        pcm = bytes(pcm)
    if int(turn.notes.get("channels", 1)) == 2:
        pcm = pcm16_to_mono(pcm, 2)
    return pcm


def _sample_count(raw: Any) -> int:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return 0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(value) or value < 0:
        return 0
    return int(value)


def _maybe_update_profile(
    turn: Turn,
    note: dict,
    cfg: MoodConfig,
    profiles: ProfileStore,
    focus_cfg: FocusConfig | None,
    profile_cfg: ProfileConfig | None,
) -> None:
    if not is_english_turn(turn):
        if not cfg.learn_non_en:
            return
        confidence = threshold_value(note.get("confidence"))
        floor = threshold_value(cfg.non_en_min_confidence)
        if confidence is None or floor is None or confidence < floor:
            return

    label = note.get("label")
    if label not in MOOD_LABELS:
        return
    if note.get("backend") != cfg.backend:
        return
    if not raw_supports_label(note.get("raw_label"), str(label)):
        return
    confidence = threshold_value(note.get("confidence"))
    floor = threshold_value(cfg.min_confidence)
    margin_floor = threshold_value(cfg.min_margin)
    # The scorer already applied the margin. A broken floor must not fail open:
    # ``confidence < NaN`` is false and would otherwise store the label.
    if confidence is None or floor is None or margin_floor is None or confidence < floor:
        return
    alpha = threshold_value(cfg.ema_alpha)
    if alpha is None or alpha > 1.0:
        return
    if turn.error:
        return
    ok, _skip = should_learn_turn(turn)
    if not ok:
        return
    if "antispoof" in turn.notes:
        anti = turn.notes.get("antispoof")
        if not isinstance(anti, dict) or anti.get("action") not in (None, "allow"):
            return
    if focus_cfg is None or not focus_cfg.enabled:
        return

    meta = turn.notes.get("meta") or {}
    emb = turn.notes.get("speaker_embedding")
    embedding = np.array(emb, dtype=np.float32) if emb else None
    match_min = (
        profile_cfg.match_min_similarity if profile_cfg is not None else 0.72
    )
    sid, doc = profiles.resolve_speaker(
        meta_speaker_id=meta.get("speaker_id"),
        embedding=embedding,
        enroll_pcm=None,
        rate=turn.rate_hz,
        min_similarity=match_min,
        lock_owner=bool(focus_cfg.lock_owner),
        owner_speaker_id=focus_cfg.owner_speaker_id or "",
    )
    if not doc.get("is_owner"):
        return

    block = doc.get("mood")
    if not isinstance(block, dict):
        block = empty_mood()
    dist = block.get("distribution")
    if not isinstance(dist, dict):
        dist = empty_mood()["distribution"]
    blended = blend_distribution(dist, str(label), alpha)
    if any(
        (not math.isfinite(value)) or value < -1e-9 or value > 1.0 + 1e-6
        for value in blended.values()
    ):
        return
    if abs(sum(blended.values()) - 1.0) > 1e-3:
        return
    now = time.time()
    payload = {
        "distribution": blended,
        "last_label": label,
        "last_confidence": confidence,
        "updated_at": now,
        "samples": _sample_count(block.get("samples", 0)) + 1,
    }
    json.dumps(payload, allow_nan=False)
    doc["mood"] = payload
    doc["updated_at"] = now
    profiles.put(doc)
    turn.notes["speaker_id"] = sid


def make_mood_step(
    cfg: MoodConfig,
    profiles: ProfileStore,
    focus_cfg: FocusConfig | None = None,
    profile_cfg: ProfileConfig | None = None,
):
    def mood_step(turn: Turn) -> None:
        if not cfg.enabled:
            # A planted note must not ride out on a step that is not scoring.
            turn.notes.pop("mood", None)
            return
        if not cfg.score_non_en and not is_english_turn(turn):
            turn.notes["mood"] = {
                "label": None,
                "confidence": 0,
                "backend": "skipped_non_en",
                "raw_label": None,
            }
            return
        try:
            note = score_mood(_analysis_pcm(turn), int(turn.rate_hz), cfg)
        except Exception as exc:
            note = {
                "label": None,
                "confidence": 0,
                "backend": f"wav2vec2_ser_int8_error: {exc.__class__.__name__}",
                "raw_label": None,
            }
        clean = client_view(note) or {
            "label": None,
            "confidence": 0,
            "backend": "unavailable",
            "raw_label": None,
        }
        turn.notes["mood"] = clean
        # A profile-write failure must not become turn.error "internal".
        try:
            _maybe_update_profile(turn, clean, cfg, profiles, focus_cfg, profile_cfg)
        except Exception:
            return

    return mood_step
