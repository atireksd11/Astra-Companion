from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import (  # noqa: E402
    CadenceConfig,
    FocusConfig,
    MoodConfig,
    PronunciationConfig,
    ProfileConfig,
    SttConfig,
    TtsConfig,
)
from core.pronunciation_learn import run_pronunciation_learn  # noqa: E402
from core.turn import Turn  # noqa: E402
from steps import stt as stt_mod  # noqa: E402
from steps.cadence import make_cadence_step  # noqa: E402
from steps.pronunciation import make_pronunciation_step  # noqa: E402
from steps.stt import make_stt_step  # noqa: E402
from steps.tts import resolve_voice  # noqa: E402
from store.profiles import ProfileStore  # noqa: E402


def test_stt_auto_language_writes_notes() -> None:
    stt_mod.set_stt_decoder(lambda pcm, rate: "hola mundo")
    stt_mod.set_stt_decoder_language("es", 0.91)
    try:
        turn = Turn(rate_hz=16000)
        turn.pcm_in = bytearray(b"\x00\x01" * 4000)
        make_stt_step(SttConfig(enabled=True, auto_language=True))(turn)
        assert turn.notes["language"] == "es"
        assert turn.notes["stt"]["gate_lang"] == "es"
        assert turn.notes["language_probability"] == 0.91
    finally:
        stt_mod.set_stt_decoder(None)
        stt_mod.set_stt_decoder_language(None)


def test_stt_low_language_prob_falls_back_gate_to_en() -> None:
    stt_mod.set_stt_decoder(lambda pcm, rate: "bonjour")
    stt_mod.set_stt_decoder_language("fr", 0.2)
    try:
        turn = Turn(rate_hz=16000)
        turn.pcm_in = bytearray(b"\x00\x01" * 4000)
        make_stt_step(
            SttConfig(enabled=True, auto_language=True, min_language_prob=0.5)
        )(turn)
        assert turn.notes["language"] == "fr"
        assert turn.notes["stt"]["gate_lang"] == "en"
    finally:
        stt_mod.set_stt_decoder(None)
        stt_mod.set_stt_decoder_language(None)


def test_stt_forced_english_sets_gate_en() -> None:
    stt_mod.set_stt_decoder(lambda pcm, rate: "hello")
    try:
        turn = Turn(rate_hz=16000)
        turn.pcm_in = bytearray(b"\x00\x01" * 4000)
        make_stt_step(SttConfig(enabled=True, language="en", auto_language=False))(
            turn
        )
        assert turn.notes["language"] == "en"
        assert turn.notes["stt"]["forced"] is True
    finally:
        stt_mod.set_stt_decoder(None)


def test_load_config_rejects_auto_language_with_en_model(tmp_path: Path) -> None:
    from core.config import load_config

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        '{"stt": {"enabled": true, "model": "medium.en", "auto_language": true}}',
        encoding="utf-8",
    )
    try:
        load_config(cfg_path)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "auto_language" in str(exc)


def test_load_config_allows_english_model_when_auto_language_off(tmp_path: Path) -> None:
    from core.config import load_config

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        '{"stt": {"enabled": true, "model": "medium.en", "language": "en", "auto_language": false}}',
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert cfg.stt.model == "medium.en"
    assert cfg.stt.auto_language is False
    assert cfg.stt.language == "en"


def test_pronunciation_skips_learn_for_spanish(tmp_path: Path) -> None:
    profiles = ProfileStore(tmp_path / "lang.db")
    focus = FocusConfig(enabled=False)
    step = make_pronunciation_step(
        PronunciationConfig(enabled=True, aligner="ctc"),
        ProfileConfig(),
        profiles,
        focus,
    )
    turn = Turn(rate_hz=16000)
    turn.notes["language"] = "es"
    turn.notes["stt"] = {"gate_lang": "es"}
    turn.notes["transcript"] = "hola"
    step(turn)
    assert turn.notes.get("pronunciation_learn_pending") is None
    assert turn.notes["pronunciation_learn"] == {"skipped": "non_en"}


def test_run_pronunciation_learn_skips_non_en() -> None:
    turn = Turn(rate_hz=16000)
    turn.notes["language"] = "es"
    turn.notes["stt"] = {"gate_lang": "es"}
    turn.notes["words"] = [{"word": "hola", "probability": 0.99}]
    out = run_pronunciation_learn(turn, {"pronunciation": {"lexicon": []}}, PronunciationConfig(aligner="ctc"))
    assert out["skip"] == "non_en"


def test_cadence_skips_fillers_for_non_en(tmp_path: Path) -> None:
    profiles = ProfileStore(tmp_path / "cadence.db")
    step = make_cadence_step(
        CadenceConfig(enabled=True),
        ProfileConfig(),
        profiles,
        FocusConfig(enabled=False),
    )
    turn = Turn(rate_hz=16000)
    turn.pcm_in = bytearray(b"\x00\x80" * 8000)
    turn.notes["transcript"] = "uh hola um"
    turn.notes["language"] = "es"
    turn.notes["stt"] = {"gate_lang": "es"}
    step(turn)
    fillers = turn.notes["cadence"].get("fillers") or {}
    assert fillers.get("status") == "skipped_non_en"


def test_tts_resolve_voice_falls_back_without_map() -> None:
    cfg = TtsConfig(
        weights="models/en_US-lessac-medium.onnx",
        voices={"es": "models/no-such-spanish-voice.onnx"},
    )
    path, fallback = resolve_voice(cfg, "es")
    assert fallback is True
    assert path.name == "en_US-lessac-medium.onnx"
