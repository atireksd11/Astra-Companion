"""Hey Astra keyword spotter.

Wraps sherpa-onnx's KeywordSpotter. The only keyword is "hey astra".

Model files live in server/models/kws/ (English int8 Zipformer pack).
keywords.txt is built with sherpa-onnx-cli when that command is on PATH:

    sherpa-onnx-cli text2token ^
      --tokens tokens.txt ^
      --tokens-type bpe ^
      --bpe-model bpe.model ^
      keywords_raw.txt keywords.txt

keywords_raw.txt is a single line: HEY ASTRA
The CLI also needs sentencepiece and pypinyin (sherpa-onnx imports both).
If the CLI is missing, generate keywords.txt with that command and leave it
next to the model files.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from collections import deque
from pathlib import Path

import numpy as np

MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "kws"
ENCODER_NAME = "encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx"
DECODER_NAME = "decoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx"
JOINER_NAME = "joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx"
PHRASE = "hey astra"
# Extra spellings of the same name. The tiny Zipformer often misses ▁AS T RA.
RAW_LINES = ("HEY ASTRA", "HEY AS TRA", "HEYASTRA")
_ACCEPTED = frozenset({"heyastra", "heyastro", "heyaster"})
# int16 mono, 16 kHz, two seconds.
WINDOW_BYTES = 16000 * 2 * 2
_SPEECH_RMS = 300.0
_FRAME = 320  # 20 ms
_PREROLL = 1600  # 100 ms


def _package_installed() -> bool:
    return importlib.util.find_spec("sherpa_onnx") is not None


def model_paths(model_dir: Path | None = None) -> dict[str, Path]:
    root = Path(model_dir) if model_dir is not None else MODEL_DIR
    return {
        "encoder": root / ENCODER_NAME,
        "decoder": root / DECODER_NAME,
        "joiner": root / JOINER_NAME,
        "tokens": root / "tokens.txt",
        "bpe": root / "bpe.model",
        "raw": root / "keywords_raw.txt",
        "keywords": root / "keywords.txt",
    }


def files_present(model_dir: Path | None = None) -> bool:
    paths = model_paths(model_dir)
    return all(paths[name].is_file() for name in ("encoder", "decoder", "joiner", "tokens", "bpe"))


def _is_other_wake(text: str) -> bool:
    raw = (text or "").casefold().replace("▁", " ")
    return any(bad in raw for bad in ("jarvis", "siri", "alexa", "google"))


def _is_hey_astra(text: str) -> bool:
    """True only for the Hey Astra keyword, not Jarvis / Siri / fuzzy names."""
    raw = (text or "").casefold()
    if not raw.strip():
        return False
    cleaned: list[str] = []
    for ch in raw.replace("▁", " "):
        cleaned.append(ch if ch.isalnum() else " ")
    words = "".join(cleaned).split()
    joined = "".join(words).replace("_", "")
    if any(bad in joined for bad in ("jarvis", "siri", "alexa", "google", "esther", "extra")):
        return False
    if joined in _ACCEPTED or "heyastra" in joined:
        return True
    return words[:5] == ["he", "y", "as", "t", "ra"]


def _is_partial_hey(text: str) -> bool:
    """A prefix of the name, not a finished different word."""
    raw = (text or "").casefold().replace("▁", " ").replace("_", " ")
    words = "".join(ch if ch.isalnum() else " " for ch in raw).split()
    joined = "".join(words)
    if not joined or _is_hey_astra(text) or _is_other_wake(text):
        return False
    return joined in {"he", "hey", "heyas", "heya", "heyast"}


def _keywords_file_ok(path: Path) -> bool:
    if not _one_keyword_line(path):
        return False
    line = next(
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    )
    # Drop optional ":score #threshold @tag" so the token check sees the phrase.
    core = line.split(":", 1)[0].split("#", 1)[0].strip()
    return _is_hey_astra(core)


def available(model_dir: Path | None = None) -> bool:
    """True when sherpa-onnx imports and the int8 pack is on disk."""
    if not _package_installed() or not files_present(model_dir):
        return False
    keywords = model_paths(model_dir)["keywords"]
    if _keywords_file_ok(keywords):
        return True
    return (
        shutil.which("sherpa-onnx-cli") is not None
        and model_paths(model_dir)["bpe"].is_file()
    )


def _keyword_lines(path: Path) -> list[str]:
    if not path.is_file() or path.stat().st_size <= 0:
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _one_keyword_line(path: Path) -> bool:
    lines = _keyword_lines(path)
    if not lines or len(lines) > len(RAW_LINES):
        return False
    for line in lines:
        core = line.split(":", 1)[0].split("#", 1)[0].strip()
        if not _is_hey_astra(core):
            return False
    return True


def _raw_is_hey_astra(path: Path) -> bool:
    return _keyword_lines(path) == list(RAW_LINES)


def ensure_keywords(model_dir: Path | None = None) -> Path | None:
    """Write keywords.txt for 'hey astra' only.

    Uses sherpa-onnx-cli text2token when the file is missing or stale.
    Returns None when the CLI is missing and keywords.txt is not already there.
    """
    root = Path(model_dir) if model_dir is not None else MODEL_DIR
    paths = model_paths(root)
    raw = paths["raw"]
    out = paths["keywords"]
    if not paths["tokens"].is_file() or not paths["bpe"].is_file():
        return out if _keywords_file_ok(out) else None
    if not _raw_is_hey_astra(raw):
        raw.write_text("\n".join(RAW_LINES) + "\n", encoding="utf-8")
    if (
        out.is_file()
        and out.stat().st_mtime >= raw.stat().st_mtime
        and _keywords_file_ok(out)
    ):
        return out
    cli = shutil.which("sherpa-onnx-cli")
    if cli is None:
        return out if _keywords_file_ok(out) else None
    cmd = [
        cli,
        "text2token",
        "--tokens",
        str(paths["tokens"]),
        "--tokens-type",
        "bpe",
        "--bpe-model",
        str(paths["bpe"]),
        str(raw),
        str(out),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return out if _keywords_file_ok(out) else None
    return out if _keywords_file_ok(out) else None


def _rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    audio = samples.astype(np.float32, copy=False)
    return float(np.sqrt(np.mean(audio * audio)))


def trailing_speech(pcm: bytes, *, rms_threshold: float = _SPEECH_RMS) -> bytes:
    """Drop leading quiet samples. Keep a short preroll before speech."""
    if len(pcm) < 2:
        return b""
    samples = np.frombuffer(pcm, dtype=np.int16)
    start = 0
    found = False
    for i in range(0, int(samples.size), _FRAME):
        if _rms(samples[i : i + _FRAME]) >= rms_threshold:
            start = i
            found = True
            break
    if not found:
        return np.ascontiguousarray(samples).tobytes()
    start = max(0, start - _PREROLL)
    return np.ascontiguousarray(samples[start:]).tobytes()


class WakeKeywordSpotter:
    """Feed int16 mono 16 kHz frames. True means 'hey astra' was heard."""

    def __init__(self, model_dir: Path | None = None, phrase: str = PHRASE) -> None:
        self.model_dir = Path(model_dir) if model_dir is not None else MODEL_DIR
        # The pack is built for this phrase only. Other phrases are not added.
        self.phrase = PHRASE
        self._kws = None
        self._stream = None
        self._chunks: deque[bytes] = deque()
        self._buffered = 0
        self._phrase = b""

    def preload(self) -> bool:
        """Load the spotter. Returns False if the package or files are missing."""
        if self._kws is not None and self._stream is not None:
            return True
        if not _package_installed() or not files_present(self.model_dir):
            return False
        keywords = ensure_keywords(self.model_dir)
        if keywords is None or not _keywords_file_ok(keywords):
            return False
        try:
            import sherpa_onnx

            paths = model_paths(self.model_dir)
            # Per-line scores in keywords.txt override these defaults.
            # One trailing blank is required or the keyword never fires.
            # max_active_paths above 4 double-fires the same utterance.
            spotter = sherpa_onnx.KeywordSpotter(
                tokens=str(paths["tokens"]),
                encoder=str(paths["encoder"]),
                decoder=str(paths["decoder"]),
                joiner=str(paths["joiner"]),
                keywords_file=str(keywords),
                num_threads=1,
                provider="cpu",
                keywords_score=2.0,
                keywords_threshold=0.05,
                max_active_paths=4,
                num_trailing_blanks=1,
            )
            stream = spotter.create_stream()
        except Exception:
            self._kws = None
            self._stream = None
            return False
        if stream is None:
            self._kws = None
            self._stream = None
            return False
        self._kws = spotter
        self._stream = stream
        self._warm_stream()
        return True

    def _warm_stream(self) -> None:
        """Run one second of silence so the first spoken phrase is not the cold start."""
        if self._kws is None or self._stream is None:
            return
        try:
            zeros = np.zeros(16000, dtype=np.float32)
            self._stream.accept_waveform(16000, zeros)
            steps = 0
            while self._kws.is_ready(self._stream) and steps < 64:
                self._kws.decode_stream(self._stream)
                steps += 1
            self._kws.reset_stream(self._stream)
        except Exception:
            return

    def phrase_pcm(self) -> bytes:
        """Audio that contained the keyword, not the whole session."""
        return self._phrase

    def reset(self) -> None:
        self._clear_audio()
        self._phrase = b""
        if self._kws is not None and self._stream is not None:
            self._kws.reset_stream(self._stream)

    def feed(self, pcm: bytes, rate: int = 16000) -> bool:
        if rate != 16000 or not pcm or len(pcm) < 2 or len(pcm) % 2:
            return False
        self._push(pcm)
        if self._kws is None or self._stream is None:
            if not self.preload():
                return False
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        try:
            self._stream.accept_waveform(rate, samples)
            hit = False
            steps = 0
            while self._kws.is_ready(self._stream):
                steps += 1
                if steps > 32:
                    break
                self._kws.decode_stream(self._stream)
                text = self._kws.get_result(self._stream)
                if not isinstance(text, str) or not text.strip():
                    continue
                if _is_hey_astra(text):
                    hit = True
                    break
                # A partial "hey" must stay so the rest of the name can finish.
                # Any other finished word is consumed so the stream cannot stick.
                if _is_other_wake(text) or not _is_partial_hey(text):
                    self._kws.reset_stream(self._stream)
                    break
        except Exception:
            return False
        if not hit:
            return False
        self._phrase = trailing_speech(b"".join(self._chunks))
        self._clear_audio()
        self._kws.reset_stream(self._stream)
        return True

    def _push(self, pcm: bytes) -> None:
        self._chunks.append(pcm)
        self._buffered += len(pcm)
        while self._buffered > WINDOW_BYTES and len(self._chunks) > 1:
            dropped = self._chunks.popleft()
            self._buffered -= len(dropped)
        if self._buffered > WINDOW_BYTES and self._chunks:
            overflow = self._buffered - WINDOW_BYTES
            if overflow % 2:
                overflow -= 1
            head = self._chunks[0]
            if 0 < overflow < len(head):
                self._chunks[0] = head[overflow:]
                self._buffered -= overflow

    def _clear_audio(self) -> None:
        self._chunks.clear()
        self._buffered = 0
