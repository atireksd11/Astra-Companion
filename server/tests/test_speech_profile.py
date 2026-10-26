from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

from core.speech_profile import (  # noqa: E402
    empty_profile,
    find_speaker_id,
    sanitize_notes_for_storage,
)
from store.profiles import ProfileStore  # noqa: E402


def test_sanitize_strips_enroll_b64() -> None:
    notes = {
        "meta": {"wake": True, "enroll_b64": "abc123"},
        "speaker_embedding": [1.0, 2.0],
    }
    clean = sanitize_notes_for_storage(notes)
    assert "enroll_b64" not in (clean.get("meta") or {})
    assert "speaker_embedding" not in clean


def test_find_speaker_skips_mismatched_embedding_dim() -> None:
    old = empty_profile("spk_old", [0.1] * 13)
    emb = np.ones(192, dtype=np.float32)
    assert find_speaker_id([old], emb, min_similarity=0.0) is None


def test_profile_sqlite_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    store = ProfileStore(db)
    doc = empty_profile("spk_test01", [0.1, 0.2])
    store.put(doc)
    got = store.get("spk_test01")
    assert got is not None
    assert got["speaker_id"] == "spk_test01"
    assert got["cadence"]["utterances"] == 0
    del store
