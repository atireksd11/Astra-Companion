"""Filler word counts from tokenized transcript only (feature 9)."""

from __future__ import annotations

import re

DEFAULT_FILLERS = ("uh", "um", "er")


def is_real_transcript(text: str) -> bool:
    if not text or not text.strip():
        return False
    if text.startswith("[audio"):
        return False
    if text.startswith("(echo"):
        return False
    return True


def count_fillers(text: str, tokens: tuple[str, ...] = DEFAULT_FILLERS) -> dict[str, int]:
    if not is_real_transcript(text):
        return {t: 0 for t in tokens}
    words = re.findall(r"[a-zA-Z']+", text.lower())
    counts = {t: 0 for t in tokens}
    for w in words:
        if w in counts:
            counts[w] += 1
    return counts
