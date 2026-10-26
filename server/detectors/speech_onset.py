from __future__ import annotations

from core.turn import Turn
from core.vad_bridge import detect_onset_in_pcm


def run(turn: Turn) -> None:
    """VAD onset detector; writes speech timing into turn.notes."""
    channels = int(turn.notes.get("channels", 1))
    stats = detect_onset_in_pcm(bytes(turn.pcm_in), turn.rate_hz, channels)
    turn.notes["speech_onset"] = stats
    turn.notes["onset_ms"] = stats["onset_ms"]
    turn.notes["speech_ms"] = stats["speech_ms"]
    turn.notes["vad_backend"] = stats["vad_backend"]
