from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import SttConfig  # noqa: E402
from core.turn import Turn  # noqa: E402
from steps import stt as stt_mod  # noqa: E402
from steps.stt import make_stt_step  # noqa: E402


def test_stt_writes_transcript() -> None:
    stt_mod.set_stt_decoder(lambda pcm, rate: "hello um world")
    try:
        turn = Turn(rate_hz=16000)
        turn.pcm_in = bytearray(b"\x00\x01" * 8000)
        turn.notes["channels"] = 1
        make_stt_step(SttConfig(enabled=True))(turn)
        assert turn.notes["transcript"] == "hello um world"
        assert turn.text_in == "hello um world"
    finally:
        stt_mod.set_stt_decoder(None)
        stt_mod.set_stt_decoder_language(None)


def test_stt_disabled_no_op() -> None:
    turn = Turn(rate_hz=16000)
    turn.pcm_in = bytearray(b"\x00\x01" * 100)
    make_stt_step(SttConfig(enabled=False))(turn)
    assert "transcript" not in turn.notes


def test_auto_language_does_not_force_transcribe_language() -> None:
    """auto_language true must pass language=None so Whisper can detect Hindi."""
    forced = SttConfig(enabled=True, model="medium.en", language="en", auto_language=False)
    auto = SttConfig(enabled=True, model="medium", language="en", auto_language=True)
    assert stt_mod._transcribe_language(forced) == "en"
    assert stt_mod._transcribe_language(auto) is None

    stt_mod.set_stt_decoder(lambda pcm, rate: "namaste")
    stt_mod.set_stt_decoder_language("hi", 0.93)
    try:
        turn = Turn(rate_hz=16000)
        turn.pcm_in = bytearray(b"\x00\x01" * 4000)
        make_stt_step(auto)(turn)
        assert turn.notes["stt"]["auto"] is True
        assert turn.notes["stt"]["forced"] is False
        assert turn.notes["language"] == "hi"
        assert stt_mod._transcribe_language(auto) is None
    finally:
        stt_mod.set_stt_decoder(None)
        stt_mod.set_stt_decoder_language(None)
