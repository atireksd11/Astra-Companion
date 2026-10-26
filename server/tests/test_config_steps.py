from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import (  # noqa: E402
    AntispoofConfig,
    CadenceConfig,
    DenoiseConfig,
    FocusConfig,
    MoodConfig,
    PronunciationConfig,
    SttConfig,
    normalize_steps,
)

_OFF_F = FocusConfig(enabled=False)
_OFF_C = CadenceConfig(enabled=False)
_OFF_P = PronunciationConfig(enabled=False)
_OFF_S = SttConfig(enabled=False)
_OFF_A = AntispoofConfig(enabled=False)
_OFF_M = MoodConfig(enabled=False)


def test_insert_denoise_when_enabled_missing() -> None:
    steps, warns = normalize_steps(
        ["echo"], DenoiseConfig(enabled=True), _OFF_F, _OFF_S, _OFF_C, _OFF_P, _OFF_A, _OFF_M
    )
    assert steps == ["denoise", "echo"]
    assert warns


def test_reorder_echo_before_denoise() -> None:
    steps, warns = normalize_steps(
        ["echo", "denoise"], DenoiseConfig(enabled=True), _OFF_F, _OFF_S, _OFF_C, _OFF_P, _OFF_A, _OFF_M
    )
    assert steps == ["denoise", "echo"]
    assert any("before" in w for w in warns)


def test_disabled_no_change() -> None:
    steps, warns = normalize_steps(
        ["echo", "denoise"], DenoiseConfig(enabled=False), _OFF_F, _OFF_S, _OFF_C, _OFF_P, _OFF_A, _OFF_M
    )
    assert steps == ["echo", "denoise"]
    assert not warns


def test_insert_focus_when_enabled() -> None:
    steps, warns = normalize_steps(
        ["echo"],
        DenoiseConfig(enabled=False),
        FocusConfig(enabled=True),
        _OFF_S,
        _OFF_C,
        _OFF_P,
        _OFF_A, _OFF_M,
    )
    assert steps == ["focus", "echo"]
    assert warns


def test_insert_stt_after_focus() -> None:
    steps, warns = normalize_steps(
        ["echo"],
        DenoiseConfig(enabled=False),
        FocusConfig(enabled=True),
        SttConfig(enabled=True),
        _OFF_C,
        _OFF_P,
        _OFF_A, _OFF_M,
    )
    assert steps.index("focus") < steps.index("stt") < steps.index("echo")
