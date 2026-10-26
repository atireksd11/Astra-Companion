"""Language detection helpers for Phase 4 (Features 14–15)."""

from __future__ import annotations

from core.turn import Turn


def detected_lang(turn: Turn) -> str | None:
    raw = turn.notes.get("language")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower().split("-")[0]
    return None


def language_probability(turn: Turn) -> float | None:
    raw = turn.notes.get("language_probability")
    try:
        if raw is None:
            return None
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < 0 or value > 1:
        return None
    return value


def reply_language(turn: Turn) -> str:
    """Language for TTS, LLM reply, and English-only learn gates."""
    stt = turn.notes.get("stt")
    if isinstance(stt, dict):
        gate = stt.get("gate_lang")
        if isinstance(gate, str) and gate.strip():
            return gate.strip().lower().split("-")[0]
    lang = detected_lang(turn)
    if lang:
        return lang
    return "en"


def is_english_turn(turn: Turn) -> bool:
    return reply_language(turn) in ("", "en")
