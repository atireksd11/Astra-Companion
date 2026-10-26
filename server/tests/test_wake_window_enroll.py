from __future__ import annotations

import base64
import math
import struct
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import DenoiseConfig, FocusConfig  # noqa: E402
from core.focus import FocusSession  # noqa: E402
from core.speech_profile import empty_profile  # noqa: E402
from core.turn import Turn  # noqa: E402
from steps.focus import make_focus_step  # noqa: E402
from store.profiles import ProfileStore  # noqa: E402

SR = 16000


def _tone(hz: float, seconds: float) -> bytes:
    n = int(SR * seconds)
    out = []
    for i in range(n):
        s = int(0.4 * 32767 * math.sin(2 * math.pi * hz * i / SR))
        out.append(struct.pack("<h", s))
    return b"".join(out)


@contextmanager
def _patch_ecapa(side_effect):
    with (
        mock.patch("core.speaker_ecapa.embed_pcm16_mono", side_effect=side_effect),
        mock.patch("core.focus.embed_pcm16_mono", side_effect=side_effect),
        mock.patch("steps.focus.embed_pcm16_mono", side_effect=side_effect),
    ):
        yield


def test_friend_wake_keeps_owner_embedding(tmp_path: Path) -> None:
    owner = np.zeros(192, dtype=np.float32)
    owner[0] = 1.0
    friend = np.zeros(192, dtype=np.float32)
    friend[1] = 1.0

    def side(pcm: bytes, rate: int = 16000) -> np.ndarray:
        return owner if pcm == _tone(200, 0.8) else friend

    from core.owner_enroll import append_enroll_clip, finalize_owner_enroll

    profiles = ProfileStore(tmp_path / "t.db")
    sid = "spk_owner01"
    doc = empty_profile(sid, [])
    doc["is_owner"] = True
    for _ in range(4):
        append_enroll_clip(doc, owner, snr_db=12.0)
    finalize_owner_enroll(doc, min_clips=4)
    profiles.put(doc)

    session = FocusSession()
    session.state.enrolled = owner.copy()
    session.state.armed = True

    wake = _tone(200, 0.8)
    sentence = _tone(200, 1.0)
    turn = Turn(rate_hz=SR)
    turn.pcm_in = bytearray(sentence)
    turn.notes["channels"] = 1
    turn.notes["meta"] = {
        "wake": True,
        "wake_b64": base64.b64encode(_tone(150, 0.8)).decode("ascii"),
        "wake_speech_ms": 600,
    }
    turn.notes["wake_turn"] = True

    cfg = FocusConfig(
        enabled=True,
        lock_owner=True,
        owner_speaker_id=sid,
        min_similarity=0.40,
        wake_min_speech_ms=500,
        require_owner_enroll=True,
    )
    step = make_focus_step(cfg, session, profiles, DenoiseConfig(enabled=False))
    with _patch_ecapa(side_effect=side):
        step(turn)

    assert turn.error == "not your voice"
    assert np.allclose(session.state.enrolled, owner)
    assert not turn.notes.get("focus_replaced")


def test_cold_start_first_wake_enrolls_whoever_speaks(tmp_path: Path) -> None:
    """Accepted limit: empty profile — first wake window becomes owner."""

    def side(pcm: bytes, rate: int = 16000) -> np.ndarray:
        v = np.zeros(192, dtype=np.float32)
        v[2] = 1.0
        return v

    profiles = ProfileStore(tmp_path / "t.db")
    session = FocusSession()
    wake = _tone(220, 0.9)
    turn = Turn(rate_hz=SR)
    turn.pcm_in = bytearray(_tone(220, 1.0))
    turn.notes["channels"] = 1
    turn.notes["meta"] = {
        "wake": True,
        "wake_b64": base64.b64encode(wake).decode("ascii"),
        "wake_speech_ms": 600,
    }
    turn.notes["wake_turn"] = True
    cfg = FocusConfig(
        enabled=True,
        lock_owner=True,
        wake_min_speech_ms=500,
        mask_other_voices=False,
        require_owner_enroll=False,
    )
    step = make_focus_step(cfg, session, profiles, DenoiseConfig(enabled=False))
    with _patch_ecapa(side_effect=side):
        step(turn)
    assert turn.error is None
    assert turn.notes.get("owner_enrolled")
    assert profiles.list_all()
