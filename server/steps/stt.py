"""Speech-to-text via faster-whisper."""

from __future__ import annotations

from typing import Any, Callable

from core.config import SttConfig
from core.turn import Turn
from core.vad_bridge import pcm16_to_mono

_MODEL: Any | None = None
_MODEL_KEY: tuple[str, str, str] | None = None
_DECODE_FN: Callable[[bytes, int], str] | None = None
_DECODE_LANG: tuple[str, float] | None = None


def set_stt_decoder(fn: Callable[[bytes, int], str] | None) -> None:
    """Test hook: bypass Whisper when set."""
    global _DECODE_FN
    _DECODE_FN = fn


def set_stt_decoder_language(language: str | None, probability: float = 0.92) -> None:
    """Test hook: fake Whisper language detection when the decoder hook is active."""
    global _DECODE_LANG
    if language is None:
        _DECODE_LANG = None
        return
    _DECODE_LANG = (language.strip().lower().split("-")[0], float(probability))


def _transcribe_language(cfg: SttConfig) -> str | None:
    if cfg.auto_language:
        return None
    return cfg.language or None


def _apply_language_notes(
    turn: Turn,
    cfg: SttConfig,
    *,
    detected: str | None,
    probability: float | None,
) -> None:
    forced = not cfg.auto_language
    gate_lang = (cfg.language or "en").lower().split("-")[0] if forced else "en"
    det = (detected or "").strip().lower().split("-")[0] if detected else ""
    prob = float(probability) if probability is not None else None

    if cfg.auto_language and det:
        turn.notes["language"] = det
        if prob is not None:
            turn.notes["language_probability"] = prob
        floor = float(cfg.min_language_prob)
        if prob is None or prob >= floor:
            gate_lang = det
    elif forced:
        turn.notes["language"] = gate_lang
        if prob is not None:
            turn.notes["language_probability"] = prob

    turn.notes["stt"] = {
        "backend": "faster_whisper",
        "model": cfg.model,
        "language": turn.notes.get("language"),
        "language_probability": turn.notes.get("language_probability"),
        "auto": bool(cfg.auto_language),
        "forced": forced,
        "gate_lang": gate_lang,
    }


def _get_model(cfg: SttConfig):
    global _MODEL, _MODEL_KEY
    key = (cfg.model, cfg.device, cfg.compute_type)
    if _MODEL is None or _MODEL_KEY != key:
        from faster_whisper import WhisperModel

        _MODEL = WhisperModel(cfg.model, device=cfg.device, compute_type=cfg.compute_type)
        _MODEL_KEY = key
    return _MODEL


def warmup_stt(cfg: SttConfig) -> None:
    """Load Whisper at bridge startup so the first utterance does not block for minutes."""
    if not cfg.enabled or _DECODE_FN is not None:
        return
    _get_model(cfg)


def _decode_pcm_with_words(
    pcm: bytes, rate: int, cfg: SttConfig
) -> tuple[str, list[dict], str | None, float | None]:
    if _DECODE_FN is not None:
        text = _DECODE_FN(pcm, rate)
        if _DECODE_LANG:
            lang, prob = _DECODE_LANG
            return text, [], lang, prob
        return text, [], None, None
    if not pcm or rate <= 0:
        return "", [], None, None
    import numpy as np

    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    model = _get_model(cfg)
    segments, info = model.transcribe(
        samples,
        language=_transcribe_language(cfg),
        beam_size=cfg.beam_size,
        vad_filter=cfg.vad_filter,
        word_timestamps=True,
    )
    parts: list[str] = []
    words: list[dict] = []
    for seg in segments:
        if seg.text.strip():
            parts.append(seg.text.strip())
        if seg.words:
            for w in seg.words:
                token = (w.word or "").strip()
                if not token:
                    continue
                words.append(
                    {
                        "word": token,
                        "start": float(w.start),
                        "end": float(w.end),
                        "probability": float(w.probability)
                        if w.probability is not None
                        else None,
                    }
                )
    lang = getattr(info, "language", None)
    lang_prob = getattr(info, "language_probability", None)
    return " ".join(parts).strip(), words, lang, lang_prob


def make_stt_step(cfg: SttConfig):
    def stt_step(turn: Turn) -> None:
        if not cfg.enabled:
            return
        pcm = turn.pcm_for_analysis
        if pcm is None:
            pcm = bytes(turn.pcm_in)
        else:
            pcm = bytes(pcm)
        ch = int(turn.notes.get("channels", 1))
        if ch == 2:
            pcm = pcm16_to_mono(pcm, 2)
        text, words, lang, lang_prob = _decode_pcm_with_words(pcm, turn.rate_hz, cfg)
        turn.notes["transcript"] = text
        turn.text_in = text
        if words:
            turn.notes["words"] = words
        _apply_language_notes(
            turn,
            cfg,
            detected=lang,
            probability=float(lang_prob) if lang_prob is not None else None,
        )

    return stt_step
