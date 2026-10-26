from __future__ import annotations

from core.distance_volume import apply_gain_pcm16
from core.safety_list import REFUSAL
from core.turn import Turn
from core.vad_bridge import pcm16_to_mono


def echo_step(turn: Turn) -> None:
    """Stage 1: send the same audio back (mono for speaker playback)."""
    pcm = bytes(turn.pcm_in)
    if int(turn.notes.get("channels", 1)) == 2:
        pcm = pcm16_to_mono(pcm, 2)
    vol = turn.notes.get("volume") or {}
    gain = float(vol.get("gain", 1.0))
    if gain != 1.0:
        pcm = apply_gain_pcm16(pcm, gain)
    turn.pcm_out = bytearray(pcm)
    safety = turn.notes.get("safety")
    blocked = isinstance(safety, dict) and safety.get("blocked") is True
    # A refusal stays the spoken line. Echo audio is separate and must not
    # put the microphone transcript back into text_out.
    if blocked or (turn.text_out or "").strip() == REFUSAL:
        turn.text_out = REFUSAL
        return
    if (turn.text_out or "").strip():
        return
    turn.text_out = turn.text_in or "(echo)"
