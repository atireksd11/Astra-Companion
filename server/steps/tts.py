"""Piper speech. Echo gain is not applied to this audio."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from core.config import TtsConfig
from core.langutil import reply_language
from core.turn import Turn

SERVER_ROOT = Path(__file__).resolve().parent.parent
_TARGET_RATE = 16000
_VOICES: dict[str, object] = {}


def resolve_weights(cfg: TtsConfig) -> Path:
    raw = Path(cfg.weights)
    if raw.is_absolute():
        return raw
    rooted = SERVER_ROOT / raw
    if rooted.is_file() or not raw.is_file():
        return rooted
    return raw


def _resolve_weights_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    rooted = SERVER_ROOT / path
    if rooted.is_file() or not path.is_file():
        return rooted
    return path


def piper_sidecar(model: Path) -> Path:
    """Piper reads `<weights>.json` next to the onnx file."""
    return Path(str(model) + ".json")


def weights_ready_at(model: Path) -> bool:
    return model.is_file() and piper_sidecar(model).is_file()


def weights_ready(cfg: TtsConfig) -> bool:
    """True only when both the onnx file and the Piper json sidecar exist."""
    return weights_ready_at(resolve_weights(cfg))


def resolve_voice(cfg: TtsConfig, lang: str | None) -> tuple[Path, bool]:
    """Pick Piper onnx for ``lang``; fall back to default English weights."""
    code = (lang or cfg.fallback_lang or "en").strip().lower().split("-")[0]
    if code in ("", "en"):
        return resolve_weights(cfg), False
    mapped = (cfg.voices or {}).get(code)
    if mapped:
        candidate = _resolve_weights_path(mapped)
        if weights_ready_at(candidate):
            return candidate, False
    return resolve_weights(cfg), True


def _unavailable(turn: Turn) -> None:
    turn.error = "tts_unavailable"
    turn.notes["tts"] = {"available": False, "reason": "tts_unavailable"}


def resample_pcm16(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    if src_rate == dst_rate or not pcm or src_rate <= 0 or dst_rate <= 0:
        return pcm
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return b""
    n_out = int(round(samples.size * dst_rate / src_rate))
    if n_out <= 0:
        return b""
    src_idx = np.linspace(0.0, samples.size - 1, n_out)
    out = np.interp(src_idx, np.arange(samples.size), samples)
    return np.clip(np.rint(out), -32768, 32767).astype(np.int16).tobytes()


def _to_mono(pcm: bytes, channels: int) -> bytes:
    if channels <= 1 or not pcm:
        return pcm
    samples = np.frombuffer(pcm, dtype=np.int16)
    width = samples.size - (samples.size % channels)
    if width <= 0:
        return b""
    framed = samples[:width].reshape(-1, channels).astype(np.float32)
    mono = np.clip(np.rint(framed.mean(axis=1)), -32768, 32767).astype(np.int16)
    return mono.tobytes()


def _chunk_audio(chunk: object) -> tuple[bytes, int, int]:
    if isinstance(chunk, (bytes, bytearray)):
        return bytes(chunk), 22050, 1
    rate = int(getattr(chunk, "sample_rate", 22050) or 22050)
    channels = int(getattr(chunk, "sample_channels", 1) or 1)
    data = getattr(chunk, "audio_int16_bytes", None)
    if data:
        return bytes(data), rate, channels
    arr = getattr(chunk, "audio_int16_array", None)
    if arr is not None:
        return np.asarray(arr, dtype=np.int16).tobytes(), rate, channels
    raise RuntimeError("piper returned no audio")


def _load_voice(model: Path):
    path = str(model)
    voice = _VOICES.get(path)
    if voice is None:
        from piper import PiperVoice

        voice = PiperVoice.load(path)
        _VOICES[path] = voice
    return voice


def synthesize_pcm(text: str, cfg: TtsConfig, *, lang: str | None = None) -> bytes:
    """16 kHz mono PCM16. Tests patch this; live loads PiperVoice."""
    model, _fallback = resolve_voice(cfg, lang)
    voice = _load_voice(model)
    length = float(cfg.length_scale) if cfg.length_scale else 1.0
    syn_config = None
    try:
        from piper import SynthesisConfig
    except ImportError:
        try:
            from piper.config import SynthesisConfig  # type: ignore
        except ImportError:
            SynthesisConfig = None  # type: ignore
    if SynthesisConfig is not None:
        syn_config = SynthesisConfig(length_scale=length)
    if syn_config is not None:
        chunks = voice.synthesize(text, syn_config)
    else:
        chunks = voice.synthesize(text)
    parts: list[bytes] = []
    rate = 22050
    channels = 1
    for chunk in chunks:
        pcm, rate, channels = _chunk_audio(chunk)
        parts.append(pcm)
    pcm = b"".join(parts)
    pcm = _to_mono(pcm, channels)
    if rate != _TARGET_RATE:
        pcm = resample_pcm16(pcm, rate, _TARGET_RATE)
    return pcm


def warmup_tts(cfg: TtsConfig) -> None:
    if not cfg.enabled or not weights_ready(cfg):
        return
    _load_voice(resolve_weights(cfg))


def make_tts_step(cfg: TtsConfig):
    def tts_step(turn: Turn) -> None:
        if not cfg.enabled:
            return
        if not weights_ready(cfg):
            _unavailable(turn)
            return
        lang = reply_language(turn)
        model, fallback = resolve_voice(cfg, lang)
        voice_name = model.stem
        text = (turn.text_out or "").strip()
        if not text:
            turn.pcm_out = bytearray()
            turn.notes["tts"] = {
                "available": True,
                "backend": cfg.backend,
                "voice": voice_name,
                "lang": lang,
            }
            return
        try:
            pcm = synthesize_pcm(text, cfg, lang=lang)
        except Exception:
            _unavailable(turn)
            return
        turn.pcm_out = bytearray(pcm)
        note: dict = {
            "available": True,
            "backend": cfg.backend,
            "voice": voice_name,
            "lang": lang,
        }
        if fallback:
            note["fallback"] = True
        turn.notes["tts"] = note

    return tts_step
