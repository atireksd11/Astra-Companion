"""Read the intent the completion already returned. No second model call."""

from __future__ import annotations

from core.config import Limits
from core.memory_gates import extract_forget_query, extract_remember_fact
from core.safety_list import REFUSAL
from core.turn import Turn

_INTENTS = frozenset({"chat", "question", "remember", "stop", "unknown"})
STOP_LINE = "Okay, I'll stop."
_MEMORY_CHARS = 200
_EXPLICIT_REMEMBER_PREFIXES = (
    "remember that ",
    "remember to ",
    "don't forget that ",
    "dont forget that ",
    "do not forget that ",
    "please remember that ",
)


def _explicit_remember_request(transcript: str) -> str | None:
    lower = (transcript or "").casefold().strip()
    for prefix in _EXPLICIT_REMEMBER_PREFIXES:
        if lower.startswith(prefix):
            fact = extract_remember_fact(transcript)
            return fact.strip() if fact.strip() else None
    return None


def make_intent_step(limits: Limits | None = None):
    del limits

    def intent_step(turn: Turn) -> None:
        safety = turn.notes.get("safety")
        blocked = isinstance(safety, dict) and safety.get("blocked") is True
        if blocked or (turn.text_out or "").strip() == REFUSAL:
            # Stop and remember must not replace a refusal, even if the note was dropped.
            turn.text_out = REFUSAL
            turn.notes["intent"] = "unknown"
            turn.notes.pop("memory_request", None)
            return
        raw = turn.notes.get("intent")
        if isinstance(raw, str) and raw.strip().casefold() in _INTENTS:
            intent = raw.strip().casefold()
        else:
            intent = "unknown"
        turn.notes["intent"] = intent
        if intent == "stop":
            turn.text_out = STOP_LINE
        elif intent == "remember":
            fact = extract_remember_fact(turn.text_in or "")
            turn.notes["memory_request"] = fact[:_MEMORY_CHARS]
        elif "memory_request" not in turn.notes:
            explicit = _explicit_remember_request(turn.text_in or "")
            if explicit:
                turn.notes["memory_request"] = explicit[:_MEMORY_CHARS]
        forget = extract_forget_query(turn.text_in or "")
        if forget:
            turn.notes["memory_forget"] = forget[:_MEMORY_CHARS]

    return intent_step
