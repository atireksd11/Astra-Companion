from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import Limits  # noqa: E402
from core.turn import Turn  # noqa: E402


def _clamp_turn_text(turn: Turn, lim: Limits) -> None:
    """Mirror bridge post-pipeline truncation."""
    if turn.text_in and len(turn.text_in) > lim.max_text_chars:
        turn.text_in = turn.text_in[: lim.max_text_chars]
        turn.notes["text_truncated"] = True
    if turn.text_out and len(turn.text_out) > lim.max_reply_chars:
        turn.text_out = turn.text_out[: lim.max_reply_chars]
        turn.notes["reply_text_truncated"] = True


def test_max_text_and_reply_chars_truncated() -> None:
    lim = Limits(max_text_chars=10, max_reply_chars=8)
    turn = Turn()
    turn.text_in = "a" * 20
    turn.text_out = "b" * 16
    _clamp_turn_text(turn, lim)
    assert len(turn.text_in) == 10
    assert len(turn.text_out) == 8
    assert turn.notes.get("text_truncated")
    assert turn.notes.get("reply_text_truncated")
