"""Hear the configured wake phrase when the ONNX model is a different word.

openWakeWord's bundled hey_jarvis model does not fire on "hey astra". Until a
custom hey_astra.onnx exists, short speech bursts are transcribed and matched.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

_whisper = None


# Tiny Whisper often writes Astra as a near word. Whole words only — "astr" as a
# prefix would also accept "astronomy" and "Australia".
_HEY = {"hey", "hay", "hi"}
_ASTRA = {"astra", "astro", "aster", "esther", "estra", "extra"}
_A_STAR = {"star", "straw", "stra"}


def phrase_in_transcript(transcript: str, phrase: str) -> bool:
    """True when the transcript is the wake phrase, allowing small STT slips."""
    heard = _fold_words(transcript)
    want = _words(phrase)
    if not heard or not want:
        return False
    if want == heard[: len(want)] or _contains(heard, want):
        return True
    if want == ["hey", "astra"]:
        has_hey = any(w in _HEY for w in heard)
        has_name = any(w in _ASTRA for w in heard)
        return has_hey and has_name and len(heard) <= 6
    return False


def _words(text: str) -> list[str]:
    cleaned = []
    for ch in (text or "").casefold():
        cleaned.append(ch if ch.isalnum() else " ")
    return [w for w in "".join(cleaned).split() if w]


def _fold_words(text: str) -> list[str]:
    raw = _words(text)
    folded: list[str] = []
    i = 0
    while i < len(raw):
        word = raw[i]
        nxt = raw[i + 1] if i + 1 < len(raw) else ""
        if word in {"heyastra", "hayastra", "hiastra"}:
            folded.extend(("hey", "astra"))
            i += 1
            continue
        if word == "a" and nxt in _A_STAR:
            folded.append("astra")
            i += 2
            continue
        if word in _HEY and nxt in _A_STAR:
            folded.extend(("hey", "astra"))
            i += 2
            continue
        folded.append(word)
        i += 1
    return folded


def _contains(heard: list[str], want: list[str]) -> bool:
    n = len(want)
    return any(heard[i : i + n] == want for i in range(len(heard) - n + 1))


def _rms(pcm: bytes) -> float:
    if len(pcm) < 2:
        return 0.0
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples * samples)))


def _float_audio(pcm: bytes) -> np.ndarray:
    """Boost quiet mics and pad short clips so tiny Whisper has a full second."""
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return np.zeros(16000, dtype=np.float32)
    rms = float(np.sqrt(np.mean(samples * samples)))
    if rms >= 1.0:
        gain = min(3000.0 / rms, 8.0)
        if gain > 1.0:
            samples *= gain
    samples = np.clip(samples, -32768, 32767)
    if samples.size < 16000:
        samples = np.pad(samples, (0, 16000 - int(samples.size)))
    return samples / 32768.0


def warmup_phrase_model() -> None:
    """Load tiny.en before the mic loop so the first wake is not a silent stall."""
    print("Loading Hey Astra listener…", flush=True)
    transcribe_pcm16(b"\x00\x00" * 1600)
    print("Listener ready.", flush=True)


def transcribe_pcm16(pcm: bytes, rate: int = 16000) -> str:
    """CPU tiny English whisper. The first call loads (and may download) the model."""
    global _whisper
    if not pcm or rate != 16000:
        return ""
    if _whisper is None:
        from faster_whisper import WhisperModel

        print("wake: loading speech model for Hey Astra...", flush=True)
        _whisper = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    segments, _info = _whisper.transcribe(
        _float_audio(pcm),
        language="en",
        task="transcribe",
        vad_filter=False,
        beam_size=1,
        best_of=1,
        temperature=0.0,
        condition_on_previous_text=False,
        without_timestamps=True,
        hotwords="Hey Astra",
        log_prob_threshold=-2.0,
        no_speech_threshold=0.85,
    )
    return " ".join(seg.text.strip() for seg in segments if seg.text).strip()


class PhraseSpotter:
    """Buffer mic frames, then match the wake phrase once speech pauses."""

    def __init__(
        self,
        phrase: str,
        *,
        transcribe: Callable[[bytes], str] | None = None,
        speech_rms: float = 450.0,
        min_speech_frames: int = 6,
        end_silence_frames: int = 5,
        max_frames: int = 40,
    ) -> None:
        self.phrase = phrase
        self._transcribe = transcribe or transcribe_pcm16
        self.speech_rms = speech_rms
        self.min_speech_frames = min_speech_frames
        self.end_silence_frames = end_silence_frames
        self.max_frames = max_frames
        self._chunks: list[bytes] = []
        self._speech_frames = 0
        self._silence_frames = 0
        self.last_pcm = b""

    def reset(self) -> None:
        self._chunks.clear()
        self._speech_frames = 0
        self._silence_frames = 0

    def feed(self, pcm: bytes, rate: int = 16000) -> bool:
        if rate != 16000 or not pcm:
            return False
        loud = _rms(pcm) >= self.speech_rms
        if not self._chunks and not loud:
            return False
        self._chunks.append(pcm)
        if loud:
            self._speech_frames += 1
            self._silence_frames = 0
        else:
            self._silence_frames += 1
        ended = self._silence_frames >= self.end_silence_frames
        full = len(self._chunks) >= self.max_frames
        if not ended and not full:
            return False
        if self._speech_frames < self.min_speech_frames:
            self.reset()
            return False
        audio = b"".join(self._chunks)
        self.last_pcm = audio
        self.reset()
        print("Checking Hey Astra...", flush=True)
        try:
            text = self._transcribe(audio)
        except Exception:
            return False
        if phrase_in_transcript(text, self.phrase):
            return True
        heard = (text or "").strip()
        if heard:
            print(
                f'wake: heard "{heard}" - still waiting for "{self.phrase}".',
                flush=True,
            )
        return False
