"""Checks before durable memory is written."""

from __future__ import annotations

import re

from core.safety_list import match_category

_INJECTION = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior)\s+instructions|"
    r"you\s+are\s+now\s+the\s+system|"
    r"<\s*/?\s*transcript\s*>|"
    r"<\s*/?\s*system\s*>|"
    r"\{\s*\"role\"\s*:\s*\"system\")",
    re.IGNORECASE,
)


def memory_text_ok(text: str) -> str | None:
    """Return a skip reason, or None if the text may be stored."""
    cleaned = (text or "").strip()
    if len(cleaned) < 3:
        return "too_short"
    if match_category(cleaned):
        return "blocklist"
    if _INJECTION.search(cleaned):
        return "injection"
    return None


def extract_remember_fact(transcript: str) -> str:
    """Pull a short fact from a remember request."""
    t = (transcript or "").strip()
    lower = t.casefold()
    for prefix in (
        "remember that ",
        "remember to ",
        "don't forget that ",
        "dont forget that ",
        "do not forget that ",
        "please remember that ",
        "remember ",
    ):
        if lower.startswith(prefix):
            return t[len(prefix) :].strip()
    return t


def extract_forget_query(transcript: str) -> str | None:
    t = (transcript or "").strip()
    lower = t.casefold()
    for prefix in (
        "forget that ",
        "forget about ",
        "please forget that ",
        "please forget about ",
    ):
        if lower.startswith(prefix):
            q = t[len(prefix) :].strip()
            return q if q else None
    return None
