from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pipeline import Pipeline  # noqa: E402
from core.turn import Turn  # noqa: E402


def _slow_step(turn: Turn) -> None:
    time.sleep(0.5)
    turn.text_out = "ok"


def _hang_step(turn: Turn) -> None:
    time.sleep(2.0)


def test_pipeline_step_timeout() -> None:
    turn = Turn()
    pipe = Pipeline([_hang_step], step_timeout_s=0.05)
    pipe.run(turn)
    assert turn.error == "timeout"
    assert turn.notes.get("timeout_step") == "_hang_step"


def test_pipeline_skips_steps_after_timeout() -> None:
    ran = {"second": False}

    def marker(turn: Turn) -> None:
        ran["second"] = True

    turn = Turn()
    pipe = Pipeline([_hang_step, marker], step_timeout_s=0.05)
    pipe.run(turn)
    assert turn.error == "timeout"
    assert not ran["second"]


def test_pipeline_completes_under_timeout() -> None:
    turn = Turn()
    pipe = Pipeline([_slow_step], step_timeout_s=2.0)
    pipe.run(turn)
    assert turn.error is None
    assert turn.text_out == "ok"
