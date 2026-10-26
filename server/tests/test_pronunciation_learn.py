from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import PronunciationConfig  # noqa: E402
from core.phones import set_ctc_fn, set_g2p_fn  # noqa: E402
from core.pronunciation_learn import merge_pronunciation_into, run_pronunciation_learn  # noqa: E402
from core.speech_profile import empty_profile  # noqa: E402
from core.turn import Turn  # noqa: E402
from steps.pronunciation import make_pronunciation_step  # noqa: E402
from core.config import FocusConfig, ProfileConfig  # noqa: E402
from store.profiles import ProfileStore  # noqa: E402


def test_hr_mishear_does_not_seed_lexicon() -> None:
    set_g2p_fn(lambda w: ["HH", "R"])
    set_ctc_fn(lambda pcm, rate: ["HH", "R"])
    try:
        doc = empty_profile("spk_x", [0.0] * 192)
        turn = Turn(rate_hz=16000)
        turn.pcm_in = bytearray(b"\x00\x01" * 8000)
        turn.notes = {
            "channels": 1,
            "words": [{"word": "hr", "start": 0.0, "end": 0.2, "probability": 0.95}],
            "focus": {"match": 0.9},
            "segment": {"trim_s": 1.0},
            "noise_after": {"snr_db": 12.0},
        }
        cfg = PronunciationConfig(enabled=True, aligner="ctc", min_word_confidence=0.85)
        out = run_pronunciation_learn(turn, doc, cfg)
        assert not doc["pronunciation"]["lexicon"]
        assert out["skipped_words"] == 1
    finally:
        set_g2p_fn(None)
        set_ctc_fn(None)


def test_promote_only_after_n_consistent_hearings() -> None:
    heard = ["P", "IH", "NG", "OW", "L", "OW"]

    set_g2p_fn(lambda w: ["P", "IH", "NG", "G", "OW", "L", "OW"])
    set_ctc_fn(lambda pcm, rate: heard)
    try:
        doc = empty_profile("spk_y", [0.0] * 192)
        cfg = PronunciationConfig(
            enabled=True, aligner="ctc", promote_count=5, min_word_confidence=0.5
        )
        for _ in range(4):
            turn = Turn(rate_hz=16000)
            turn.pcm_in = bytearray(b"\x00\x01" * 16000)
            turn.notes = {
                "channels": 1,
                "words": [
                    {
                        "word": "say",
                        "start": 0.0,
                        "end": 0.2,
                        "probability": 0.99,
                    },
                    {
                        "word": "pingolo",
                        "start": 0.3,
                        "end": 0.8,
                        "probability": 0.99,
                    },
                ],
                "focus": {"match": 0.9},
                "segment": {"trim_s": 1.0},
                "noise_after": {"snr_db": 12.0},
            }
            run_pronunciation_learn(turn, doc, cfg)
        entry = doc["pronunciation"]["lexicon"][0]
        assert entry["status"] != "promoted"
        turn = Turn(rate_hz=16000)
        turn.pcm_in = bytearray(b"\x00\x01" * 16000)
        turn.notes = {
            "channels": 1,
            "words": [
                {"word": "say", "start": 0.0, "end": 0.2, "probability": 0.99},
                {"word": "pingolo", "start": 0.3, "end": 0.8, "probability": 0.99},
            ],
            "focus": {"match": 0.9},
            "segment": {"trim_s": 1.0},
            "noise_after": {"snr_db": 12.0},
        }
        run_pronunciation_learn(turn, doc, cfg)
        entry = next(e for e in doc["pronunciation"]["lexicon"] if e["word"] == "pingolo")
        assert entry["status"] == "promoted"
        assert entry["phones"] == heard
    finally:
        set_g2p_fn(None)
        set_ctc_fn(None)


def test_aligner_none_skips_model_and_keeps_teach(tmp_path: Path) -> None:
    profiles = ProfileStore(tmp_path / "t.db")
    step = make_pronunciation_step(
        PronunciationConfig(enabled=True, aligner="none"),
        ProfileConfig(),
        profiles,
        FocusConfig(enabled=False),
    )
    turn = Turn(rate_hz=16000)
    turn.pcm_in = bytearray(b"\x00" * 1000)
    turn.notes = {
        "channels": 1,
        "meta": {"teach": {"word": "tomato", "phones": ["T", "AH", "M", "EY", "T", "OW"]}},
        "segment": {"trim_s": 1.0},
        "noise_after": {"snr_db": 10.0},
        "focus": {"match": 0.9},
    }
    step(turn)
    assert not turn.notes.get("pronunciation_learn_pending")
    sid = turn.notes["speaker_id"]
    doc = profiles.get(sid)
    assert doc is not None
    lex = doc["pronunciation"]["lexicon"]
    assert lex[0]["word"] == "tomato"


def test_merge_pronunciation_preserves_fresh_embedding() -> None:
    fresh = empty_profile("spk_x", [1.0] * 192)
    fresh["match"]["embedding"] = [2.0] * 192
    learned = empty_profile("spk_x", [0.0] * 192)
    learned["pronunciation"] = {
        "lexicon": [
            {
                "word": "tomato",
                "phones": ["T", "AH", "M", "EY", "T", "OW"],
                "updated_at": 99.0,
            }
        ],
        "confusion": {"AH>AE": 2},
        "status": "ok",
        "aligner": "ctc",
    }
    learned["updated_at"] = 99.0
    merge_pronunciation_into(fresh, learned)
    assert fresh["match"]["embedding"] == [2.0] * 192
    assert fresh["pronunciation"]["lexicon"][0]["word"] == "tomato"
    assert fresh["pronunciation"]["confusion"]["AH>AE"] == 2
