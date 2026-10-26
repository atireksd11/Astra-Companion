"""Pipeline step: score raw PCM before denoise. Soft gate, hard only when sure."""

from __future__ import annotations

from collections.abc import Callable

from core.antispoof import score_raw_pcm16
from core.config import AntispoofConfig
from core.turn import Turn
from core.vad_bridge import pcm16_to_mono


def _fail_open_note(reason: str) -> dict:
    return {
        "backend": reason,
        "spoof_score": None,
        "spoof_score_max": None,
        "n_windows": 0,
        "reliable": False,
        "echo_corr": None,
        "action": "allow",
        "raise_verify": 0.0,
    }


def make_antispoof_step(
    cfg: AntispoofConfig,
    get_last_playback: Callable[[], bytes | None],
):
    def antispoof_step(turn: Turn) -> None:
        if not cfg.enabled:
            return
        meta = turn.notes.get("meta") or {}
        if meta.get("source") == "vision_smoke":
            turn.notes["antispoof"] = _fail_open_note("vision_smoke_lab")
            return
        try:
            pcm = bytes(turn.pcm_in)
            channels = int(turn.notes.get("channels", 1))
            if channels == 2:
                pcm = pcm16_to_mono(pcm, 2)
            playback = get_last_playback()
            if playback is not None and not isinstance(playback, (bytes, bytearray)):
                playback = None
            note = score_raw_pcm16(
                pcm,
                int(turn.rate_hz),
                cfg,
                bytes(playback) if playback else None,
            )
            turn.notes["antispoof"] = note
            if note["action"] == "hard":
                turn.error = "spoof_suspected"
        except Exception as exc:
            # A scorer crash must not become turn.error internal and kill the reply.
            # A hard decision already recorded on this turn still stops the pipeline.
            if turn.error == "spoof_suspected":
                return
            existing = turn.notes.get("antispoof")
            if isinstance(existing, dict) and existing.get("action") == "hard":
                turn.error = "spoof_suspected"
                return
            turn.notes["antispoof"] = _fail_open_note(
                f"aasist_l_error: {exc.__class__.__name__}"
            )

    return antispoof_step
