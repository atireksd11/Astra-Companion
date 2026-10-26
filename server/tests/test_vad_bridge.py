from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import vad_bridge  # noqa: E402
from tests.fixtures.stereo_pcm import (  # noqa: E402
    mono_tone_pcm16,
    silence_pcm16,
)

SAMPLE_RATE = 16000


def test_tone_onset_after_silence() -> None:
    lead = silence_pcm16(SAMPLE_RATE, 0.3)
    tone = mono_tone_pcm16(SAMPLE_RATE, seconds=0.4, hz=440.0, amplitude=10000)
    pcm = lead + tone
    onset = vad_bridge.find_tone_onset_byte(pcm, SAMPLE_RATE, prefer_webrtc=False)
    assert onset is not None
    expected = len(lead)
    fb = vad_bridge.frame_bytes(SAMPLE_RATE)
    assert abs(onset - expected) <= fb


def test_rms_fallback_without_webrtcvad() -> None:
    fb = vad_bridge.frame_bytes(SAMPLE_RATE)
    silence = b"\x00\x00" * (fb // 2)
    tone_frame = mono_tone_pcm16(SAMPLE_RATE, seconds=0.02, amplitude=12000)
    tone_frame = tone_frame[:fb]

    with mock.patch.object(vad_bridge, "HAS_WEBRTCVAD", False):
        assert vad_bridge.is_speech_frame(silence, SAMPLE_RATE, prefer_webrtc=True) is False
        assert vad_bridge.is_speech_frame(tone_frame, SAMPLE_RATE, prefer_webrtc=True) is True


def test_import_without_webrtcvad_module() -> None:
    """Module loads and RMS path works when webrtcvad import fails."""
    import importlib

    with mock.patch.dict(sys.modules, {"webrtcvad": None}):
        reloaded = importlib.reload(vad_bridge)
        try:
            assert reloaded.HAS_WEBRTCVAD is False
            fb = reloaded.frame_bytes(SAMPLE_RATE)
            tone = mono_tone_pcm16(SAMPLE_RATE, 0.02, amplitude=12000)[:fb]
            assert reloaded.is_speech_frame(tone, SAMPLE_RATE, prefer_webrtc=True)
        finally:
            importlib.reload(vad_bridge)


def test_silence_only_no_onset() -> None:
    pcm = silence_pcm16(SAMPLE_RATE, 0.5)
    assert (
        vad_bridge.find_tone_onset_byte(pcm, SAMPLE_RATE, prefer_webrtc=False) is None
    )
