"""Blocklist before the model, and again on the words we would speak."""

from __future__ import annotations

import os

import httpx

from core.config import Limits, SafetyConfig
from core.safety_list import REFUSAL, match_category
from core.turn import Turn
from providers.llm import LIMIT_LINE, OFFLINE_LINE
from steps.intent import STOP_LINE

_MODERATION_URL = "https://api.openai.com/v1/moderations"
_MODERATION_TIMEOUT = httpx.Timeout(2.5)
# Only these flags refuse. Other categories fail open.
_MODERATION_HITS = (
    "sexual/minors",
    "self-harm/instructions",
    "illicit/violent",
)
# These lines are what we say. They are not requests, and they are not sent out.
_SAFE_LINES = frozenset(
    {
        REFUSAL.strip(),
        OFFLINE_LINE.strip(),
        LIMIT_LINE.strip(),
        STOP_LINE.strip(),
    }
)


def _refuse(turn: Turn, stage: str, source: str, category: str) -> None:
    turn.text_out = REFUSAL
    turn.notes["safety"] = {
        "blocked": True,
        "stage": stage,
        "source": source,
        "category": category,
    }
    turn.notes["intent"] = "unknown"
    turn.notes.pop("memory_request", None)
    # Leave turn.error unset so TTS can speak the refusal.


def _moderate(text: str) -> str | None:
    """Category id when OpenAI flags a watched class. Any error returns None."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or not text.strip():
        return None
    try:
        with httpx.Client(timeout=_MODERATION_TIMEOUT) as client:
            resp = client.post(
                _MODERATION_URL,
                headers={"Authorization": f"Bearer {key}"},
                json={"input": text},
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    results = data.get("results")
    if not isinstance(results, list) or not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    categories = first.get("categories")
    if not isinstance(categories, dict):
        return None
    for name in _MODERATION_HITS:
        if categories.get(name) is True:
            return name
    return None


def make_safety_in_step(cfg: SafetyConfig, limits: Limits | None = None):
    del limits

    def safety_in_step(turn: Turn) -> None:
        text = turn.text_in or ""
        category = match_category(text)
        if category:
            # A child-sexual blocklist hit is not sent to the moderation API.
            _refuse(turn, "safety_in", "blocklist", category)
            return
        if cfg.moderation != "openai":
            return
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            return
        flagged = _moderate(text)
        if flagged:
            _refuse(turn, "safety_in", "openai", flagged)

    return safety_in_step


def _already_blocked(turn: Turn) -> bool:
    safety = turn.notes.get("safety")
    return isinstance(safety, dict) and safety.get("blocked") is True


def make_safety_out_step(cfg: SafetyConfig, limits: Limits | None = None):
    del limits

    def safety_out_step(turn: Turn) -> None:
        text = turn.text_out or ""
        category = match_category(text)
        if category:
            # Blocklist hits, including child-sexual ones, are not sent to moderation.
            _refuse(turn, "safety_out", "blocklist", category)
            return
        if _already_blocked(turn) or text.strip() in _SAFE_LINES:
            return
        if cfg.moderation != "openai":
            return
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            return
        flagged = _moderate(text)
        if flagged:
            _refuse(turn, "safety_out", "openai", flagged)

    return safety_out_step
