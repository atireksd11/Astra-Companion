"""Join Feature 1 (speech) + Feature 2 (trim/limits) before echo or DOA."""

from __future__ import annotations

from core.config import Limits
from core.segment import SegmentStats
from core.turn import Turn
from detectors.speech_onset import run as speech_onset_run


def reject_reason(seg: SegmentStats, turn: Turn, lim: Limits) -> str | None:
    """Return error reason if this clip should not be echoed."""
    if not seg.trim_s:
        return "empty"
    if seg.trim_s < lim.min_speech_s:
        return "too short"
    if seg.trim_s < lim.min_clip_s:
        return "too short"

    speech_ms = int(turn.notes.get("speech_ms", 0))
    if speech_ms < int(lim.min_speech_s * 1000):
        return "no speech"

    min_ratio = getattr(lim, "min_speech_ratio", 0.15)
    if seg.speech_ratio < min_ratio:
        return "no speech"

    return None


def apply_trim_and_vad(
    turn: Turn, trimmed: bytes, seg: SegmentStats
) -> str | None:
    """Store trimmed PCM on turn, run VAD onset; return reject reason if any."""
    turn.pcm_in = bytearray(trimmed)
    turn.notes["segment"] = seg.to_dict()
    speech_onset_run(turn)
    return None
