from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.owner_enroll import (  # noqa: E402
    append_enroll_clip,
    finalize_owner_enroll,
    owner_enroll_complete,
    verify_owner_robust,
)
from core.speech_profile import empty_profile  # noqa: E402


def _vec(i: int) -> np.ndarray:
    v = np.zeros(192, dtype=np.float32)
    v[i % 192] = 1.0
    return v


def test_enroll_mean_and_verify_same_speaker() -> None:
    doc = empty_profile("spk_a", [])
    for _ in range(4):
        append_enroll_clip(doc, _vec(0), snr_db=10.0, phrase_id="a")
    assert finalize_owner_enroll(doc, min_clips=4)
    assert owner_enroll_complete(doc)
    ok, score, which = verify_owner_robust(doc, _vec(0))
    assert ok
    assert score > 0.9
    assert which in ("mean", "clip")


def test_stranger_rejected() -> None:
    doc = empty_profile("spk_a", [])
    for _ in range(4):
        append_enroll_clip(doc, _vec(0), snr_db=10.0)
    finalize_owner_enroll(doc, min_clips=4)
    ok, score, _ = verify_owner_robust(doc, _vec(5))
    assert not ok
    assert score < 0.5


def test_best_clip_accepts_tired_voice() -> None:
    doc = empty_profile("spk_a", [])
    append_enroll_clip(doc, _vec(0), snr_db=10.0)
    append_enroll_clip(doc, _vec(0), snr_db=10.0)
    append_enroll_clip(doc, _vec(0), snr_db=10.0)
    append_enroll_clip(doc, _vec(0), snr_db=10.0)
    finalize_owner_enroll(doc, min_clips=4)
    tired = _vec(0) * 0.7 + _vec(1) * 0.3
    tired = tired / np.linalg.norm(tired)
    ok, _, which = verify_owner_robust(doc, tired, min_mean=0.99, min_best_clip=0.45)
    assert ok
    assert which in ("clip", "mean")
