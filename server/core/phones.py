"""G2P seed and CTC phone recognition (lazy-loaded)."""

from __future__ import annotations

import re
from typing import Callable

_G2P = None
_CTC = None
_TOKENIZER = None
_G2P_FN: Callable[[str], list[str]] | None = None
_CTC_FN: Callable[[bytes, int], list[str]] | None = None

SKIP_PHONES = frozenset({"[SIL]", "[UNK]", "[PAD]", ""})


def set_g2p_fn(fn: Callable[[str], list[str]] | None) -> None:
    global _G2P_FN
    _G2P_FN = fn


def set_ctc_fn(fn: Callable[[bytes, int], list[str]] | None) -> None:
    global _CTC_FN
    _CTC_FN = fn


def strip_stress(phone: str) -> str:
    p = phone.strip().upper()
    p = re.sub(r"\d+$", "", p)
    return p


def normalize_phones(phones: list[str]) -> list[str]:
    out: list[str] = []
    for p in phones:
        n = strip_stress(p)
        if n and n not in SKIP_PHONES:
            out.append(n)
    return out


def _get_g2p():
    global _G2P
    if _G2P is None:
        from g2p_en import G2p

        _G2P = G2p()
    return _G2P


def g2p_word(word: str) -> list[str]:
    if _G2P_FN is not None:
        return normalize_phones(_G2P_FN(word))
    w = word.lower().strip()
    if not w:
        return []
    raw = _get_g2p()(w)
    tokens: list[str] = []
    for x in raw:
        s = str(x).strip().upper()
        if re.match(r"^[A-Z]{2,3}\d?$", s):
            tokens.append(s)
    return normalize_phones(tokens)


def _get_ctc(model_id: str, tokenizer_id: str):
    global _CTC, _TOKENIZER
    if _CTC is None:
        from transformers import AutoModelForCTC, AutoTokenizer

        _TOKENIZER = AutoTokenizer.from_pretrained(tokenizer_id)
        _CTC = AutoModelForCTC.from_pretrained(model_id)
        _CTC.eval()
    return _CTC, _TOKENIZER


def recognize_phones(pcm: bytes, rate: int, *, model: str, tokenizer: str) -> list[str]:
    if _CTC_FN is not None:
        return normalize_phones(_CTC_FN(pcm, rate))
    if not pcm or rate <= 0:
        return []
    import numpy as np
    import torch

    model_obj, tok = _get_ctc(model, tokenizer)
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    wav = torch.from_numpy(samples).unsqueeze(0)
    with torch.no_grad():
        logits = model_obj(wav).logits
    ids = torch.argmax(logits, dim=-1)[0].tolist()
    prev = None
    phones: list[str] = []
    for i in ids:
        if i == prev:
            continue
        prev = i
        p = tok.convert_ids_to_tokens(i)
        if p in SKIP_PHONES:
            continue
        phones.append(strip_stress(str(p)))
    return phones


def align_phone_sequences(expected: list[str], heard: list[str]) -> list[tuple[str | None, str | None]]:
    """Simple Levenshtein backtrace for confusion counts."""
    n, m = len(expected), len(heard)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if expected[i - 1] == heard[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    pairs: list[tuple[str | None, str | None]] = []
    i, j = n, m
    while i > 0 or j >  0:
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + (
            0 if expected[i - 1] == heard[j - 1] else 1
        ):
            pairs.append((expected[i - 1], heard[j - 1]))
            i -= 1
            j -= 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + 1:
            pairs.append((None, heard[j - 1]))
            j -= 1
        else:
            pairs.append((expected[i - 1], None))
            i -= 1
    pairs.reverse()
    return pairs
