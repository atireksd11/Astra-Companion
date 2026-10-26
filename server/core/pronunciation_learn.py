"""Post-echo pronunciation learning from high-confidence STT words."""

from __future__ import annotations

import re
import time
from typing import Any

from core.config import PronunciationConfig
from core.phones import align_phone_sequences, g2p_word, recognize_phones
from core.speech_profile import should_learn_turn
from core.turn import Turn

ISOLATED_PROMOTE = 3
WORD_RE = re.compile(r"^[a-zA-Z]{3,}$")
MAX_LEXICON = 128
MAX_CONFUSION = 32


def _word_trusted(w: dict[str, Any], min_conf: float) -> bool:
    prob = w.get("probability")
    if prob is None:
        return False
    word = str(w.get("word", "")).strip()
    if not WORD_RE.match(word):
        return False
    return float(prob) >= min_conf


def _slice_word_pcm(pcm: bytes, rate: int, start: float, end: float) -> bytes:
    i0 = max(0, int(start * rate) * 2)
    i1 = min(len(pcm), int(end * rate) * 2)
    if i1 <= i0:
        return b""
    return pcm[i0:i1]


def _get_lex_entry(lex: list[dict], word: str) -> dict | None:
    wl = word.lower()
    for e in lex:
        if e.get("word") == wl:
            return e
    return None


def _ensure_entry(lex: list[dict], word: str) -> dict:
    e = _get_lex_entry(lex, word)
    if e:
        return e
    seed = g2p_word(word)
    e = {
        "word": word.lower(),
        "seed": seed,
        "phones": list(seed),
        "source": "g2p",
        "status": "seed",
        "candidates": [],
        "updated_at": time.time(),
    }
    lex.append(e)
    if len(lex) > MAX_LEXICON:
        lex.sort(key=lambda x: float(x.get("updated_at", 0)))
        del lex[0]
    return e


def _bump_candidate(entry: dict, heard: list[str], *, isolated: bool, promote_n: int) -> dict[str, Any]:
    heard_key = " ".join(heard)
    cands = entry.setdefault("candidates", [])
    found = None
    for c in cands:
        if " ".join(c.get("phones", [])) == heard_key:
            found = c
            break
    if found is None:
        if len(cands) >= 3:
            cands.pop(0)
        found = {"phones": heard, "isolated": 0, "in_sentence": 0}
        cands.append(found)
    if isolated:
        found["isolated"] = int(found.get("isolated", 0)) + 1
    else:
        found["in_sentence"] = int(found.get("in_sentence", 0)) + 1
    entry["updated_at"] = time.time()

    promoted = False
    if entry.get("status") == "taught" and entry.get("source") == "user":
        return {"learned": heard_key, "count": found["in_sentence"], "promoted": False}

    iso = int(found.get("isolated", 0))
    ins = int(found.get("in_sentence", 0))
    if iso >= ISOLATED_PROMOTE or ins >= promote_n:
        entry["phones"] = list(heard)
        entry["source"] = "heard"
        entry["status"] = "promoted"
        entry["candidates"] = [found]
        promoted = True
    need = ISOLATED_PROMOTE if isolated else promote_n
    got = iso if isolated else ins
    return {
        "learned": heard_key,
        "count": got,
        "need": need,
        "promoted": promoted,
        "word": entry["word"],
        "phones_display": heard_key,
    }


def run_pronunciation_learn(
    turn: Turn,
    doc: dict[str, Any],
    cfg: PronunciationConfig,
) -> dict[str, Any]:
    """Update profile in place; return summary for learn message."""
    from core.langutil import is_english_turn

    out: dict[str, Any] = {"lines": [], "skipped_words": 0}
    if not is_english_turn(turn):
        out["skip"] = "non_en"
        return out
    if cfg.aligner != "ctc":
        return out
    if turn.error:
        return out
    ok, skip = should_learn_turn(turn)
    if not ok:
        out["skip"] = skip
        return out
    if turn.notes.get("barged"):
        out["skip"] = "barged"
        return out

    words = turn.notes.get("words") or []
    pcm = turn.pcm_for_analysis or bytes(turn.pcm_in)
    trusted = [w for w in words if _word_trusted(w, cfg.min_word_confidence)]
    out["skipped_words"] = len(words) - len(trusted)
    if not trusted:
        return out

    pron = doc.setdefault("pronunciation", {})
    lex: list[dict] = pron.setdefault("lexicon", [])
    confusion: dict[str, int] = pron.setdefault("confusion", {})
    isolated_turn = len(trusted) == 1

    for w in trusted:
        word = str(w["word"]).lower()
        chunk = _slice_word_pcm(pcm, turn.rate_hz, float(w["start"]), float(w["end"]))
        if len(chunk) < turn.rate_hz // 5:
            continue
        heard = recognize_phones(
            chunk,
            turn.rate_hz,
            model=cfg.model,
            tokenizer=cfg.tokenizer,
        )
        if not heard:
            continue
        entry = _ensure_entry(lex, word)
        expected = entry.get("phones") or entry.get("seed") or []
        for exp, got in align_phone_sequences(expected, heard):
            if exp and got and exp != got:
                key = f"{exp}>{got}"
                confusion[key] = int(confusion.get(key, 0)) + 1
                if len(confusion) > MAX_CONFUSION:
                    break
        ev = _bump_candidate(
            entry,
            heard,
            isolated=isolated_turn,
            promote_n=cfg.promote_count,
        )
        if ev.get("promoted"):
            out["lines"].append(
                f"promoted: {ev['word']} → {ev['phones_display']}"
            )
        elif ev.get("learned"):
            out["lines"].append(
                f"learned: {ev['word']} → {ev['phones_display']} ({ev['count']}/{ev['need']})"
            )

    pron["status"] = "ok"
    pron["aligner"] = cfg.aligner
    doc["updated_at"] = time.time()
    return out


def merge_pronunciation_into(target: dict[str, Any], learned: dict[str, Any]) -> None:
    """Merge pronunciation lexicon/confusion from async learn into a fresh profile row."""
    lp = learned.get("pronunciation")
    if not lp:
        return
    tp = target.setdefault("pronunciation", {})
    by_word: dict[str, dict] = {
        str(e.get("word", "")).lower(): e for e in tp.get("lexicon", [])
    }
    for entry in lp.get("lexicon", []):
        w = str(entry.get("word", "")).lower()
        if not w:
            continue
        prev = by_word.get(w)
        if prev is None or float(entry.get("updated_at", 0)) >= float(
            prev.get("updated_at", 0)
        ):
            by_word[w] = entry
    tp["lexicon"] = list(by_word.values())
    tc = tp.setdefault("confusion", {})
    for key, count in lp.get("confusion", {}).items():
        tc[key] = max(int(tc.get(key, 0)), int(count))
    if lp.get("status"):
        tp["status"] = lp["status"]
    if lp.get("aligner"):
        tp["aligner"] = lp["aligner"]
    target["updated_at"] = max(
        float(target.get("updated_at", 0)), float(learned.get("updated_at", 0))
    )
