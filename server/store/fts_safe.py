"""Sanitize user text before SQLite FTS5 MATCH."""

from __future__ import annotations

import re
import unicodedata

_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "to",
        "of",
        "in",
        "on",
        "for",
        "and",
        "or",
        "it",
        "i",
        "you",
        "me",
        "my",
        "your",
        "what",
        "who",
        "how",
        "when",
        "where",
        "why",
        "do",
        "did",
        "does",
        "that",
        "this",
    }
)


def fts_safe_terms(text: str, *, max_terms: int = 6, operator: str = "AND") -> str:
    """Build a quoted FTS query. Empty string means skip FTS."""
    op = (operator or "AND").upper()
    if op not in ("AND", "OR"):
        op = "AND"
    raw = unicodedata.normalize("NFKC", text or "")
    tokens = re.findall(r"[a-z0-9']{2,}", raw.casefold())
    picked: list[str] = []
    for tok in tokens:
        if tok in _STOP:
            continue
        if tok not in picked:
            picked.append(tok)
        if len(picked) >= max_terms:
            break
    if not picked:
        return ""
    joiner = f" {op} "
    return joiner.join(f'"{t}"' for t in picked)
