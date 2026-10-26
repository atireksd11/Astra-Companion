from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.client_meta import sanitize_client_meta  # noqa: E402


def test_client_cannot_set_mood_label() -> None:
    out = sanitize_client_meta(
        {
            "source": "laptop",
            "mood": "happy",
            "label": "angry",
            "raw_label": "ANG",
            "confidence": 0.99,
            "mood_label": "sad",
        }
    )
    assert out == {"source": "laptop"}
    for key in ("mood", "label", "raw_label", "confidence", "mood_label"):
        assert key not in out


def test_strips_untrusted_speaker_and_teach() -> None:
    out = sanitize_client_meta(
        {
            "speaker_id": "spk_evil",
            "teach": {"word": "foo", "phones": "F UW1"},
            "source": "laptop",
            "wake": True,
        }
    )
    assert "speaker_id" not in out
    assert "teach" not in out
    assert out["source"] == "laptop"
    assert out["wake"] is True


def test_drops_inflated_wake_speech_ms() -> None:
    out = sanitize_client_meta({"wake_speech_ms": 99999, "wake_phrase_ok": True})
    assert "wake_speech_ms" not in out
    assert "wake_phrase_ok" not in out


def test_keeps_valid_wake_b64() -> None:
    raw = base64.b64encode(b"\x00\x01").decode("ascii")
    out = sanitize_client_meta({"wake_b64": raw})
    assert out["wake_b64"] == raw


def test_large_enroll_b64_keeps_wake_flag() -> None:
    blob = base64.b64encode(b"\x01\x02" * 8000).decode("ascii")
    out = sanitize_client_meta(
        {"wake": True, "enroll_b64": blob, "enroll_speech_ms": 3200}
    )
    assert out.get("wake") is True
    assert "enroll_b64" in out
