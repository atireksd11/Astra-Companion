"""Lexicon and phone-confusion stats (feature 8)."""

from __future__ import annotations

import time
from typing import Any

from core.aligner import WordAlignment
from core.speech_profile import VOWELS


def teach_word(profile: dict[str, Any], word: str, phones: list[str]) -> None:
    pron = profile.setdefault("pronunciation", {})
    lex: list[dict] = pron.setdefault("lexicon", [])
    word_l = word.lower().strip()
    for entry in lex:
        if entry.get("word") == word_l:
            entry["expected_phones"] = phones
            entry["updated_at"] = time.time()
            return
    lex.append(
        {
            "word": word_l,
            "expected_phones": phones,
            "source": "user",
            "heard_phones": [],
            "score": None,
            "updated_at": time.time(),
        }
    )


def apply_alignments(
    profile: dict[str, Any],
    alignments: list[WordAlignment],
    lexicon_only: bool = True,
) -> int:
    """Update phone confusion counts; return words scored."""
    if not alignments:
        return 0
    pron = profile.setdefault("pronunciation", {})
    phones_map: dict[str, dict] = pron.setdefault("phones", {})
    lex = {e["word"]: e for e in pron.get("lexicon", [])}
    scored = 0
    for wa in alignments:
        entry = lex.get(wa.word.lower())
        if lexicon_only and entry is None:
            continue
        expected = entry["expected_phones"] if entry else [p.phone for p in wa.phones]
        heard = [p.phone for p in wa.phones]
        for i, exp in enumerate(expected):
            heard_p = heard[i] if i < len(heard) else exp
            bucket = phones_map.setdefault(exp, {"expected": 0, "heard_as": {}})
            bucket["expected"] = int(bucket.get("expected", 0)) + 1
            ha = bucket.setdefault("heard_as", {})
            ha[heard_p] = int(ha.get(heard_p, 0)) + 1
        if entry and heard:
            matches = sum(
                1 for i, e in enumerate(expected) if i < len(heard) and heard[i] == e
            )
            entry["heard_phones"] = heard
            entry["score"] = round(matches / max(len(expected), 1), 3)
            entry["updated_at"] = time.time()
            scored += 1
    pron["scored_words"] = int(pron.get("scored_words", 0)) + scored
    pron["status"] = "ok" if scored else pron.get("status", "needs_aligner")
    return scored
