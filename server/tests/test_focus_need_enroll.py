from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import DenoiseConfig, FocusConfig  # noqa: E402
from core.focus import FocusSession  # noqa: E402
from core.turn import Turn  # noqa: E402
from steps.focus import make_focus_step  # noqa: E402
from store.profiles import ProfileStore  # noqa: E402


def test_require_enroll_blocks_without_voiceprint(tmp_path: Path) -> None:
    session = FocusSession()
    profiles = ProfileStore(tmp_path / "t.db")
    cfg = FocusConfig(enabled=True, require_owner_enroll=True)
    turn = Turn(rate_hz=16000)
    turn.pcm_in = bytearray(b"\x00\x01" * 8000)
    turn.notes = {"channels": 1, "meta": {}}
    with mock.patch("steps.focus.embed_pcm16_mono", return_value=np.ones(192)):
        make_focus_step(cfg, session, profiles, DenoiseConfig(enabled=False))(turn)
    assert turn.error == "need_enroll"
