from __future__ import annotations

from core.config import DenoiseConfig
from core.denoise import denoise_pcm16_mono
from core.turn import Turn
from core.vad_bridge import pcm16_to_mono
from detectors.noise_floor import analyze_mono_pcm


def make_denoise_step(cfg: DenoiseConfig):
    def denoise_step(turn: Turn) -> None:
        if not cfg.enabled:
            return

        pcm = bytes(turn.pcm_in)
        channels = int(turn.notes.get("channels", 1))
        if channels == 2:
            pcm = pcm16_to_mono(pcm, 2)
            turn.notes["channels"] = 1

        turn.pcm_pre_denoise = pcm
        turn.notes["noise_before"] = analyze_mono_pcm(pcm, turn.rate_hz)

        result = denoise_pcm16_mono(
            pcm,
            turn.rate_hz,
            backend=cfg.backend,
            strength=cfg.strength,
        )
        turn.pcm_in = bytearray(result.pcm)
        turn.notes["noise_after"] = analyze_mono_pcm(result.pcm, turn.rate_hz)
        turn.notes["denoise"] = {
            "backend": result.backend,
            "snr_before_db": round(result.snr_before_db, 2),
            "snr_after_db": round(result.snr_after_db, 2),
            "bytes": len(result.pcm),
        }

    return denoise_step
