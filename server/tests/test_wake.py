from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.wake import WakeDetector  # noqa: E402


def test_wake_unavailable_without_model(monkeypatch) -> None:
    monkeypatch.setattr("core.wake_kws.available", lambda: False)
    det = WakeDetector(model_path=Path("/nonexistent/wake.onnx"), model_name="")
    assert det.available() is False
    assert det.wake_ready() is False
    assert det.feed_pcm16_mono(b"\x00\x00" * 1600) is False


def test_reset_without_model_is_safe() -> None:
    det = WakeDetector(model_path=Path("/nonexistent/wake.onnx"), model_name="")
    det.reset()


def test_astra_phrase_not_only_jarvis_label(monkeypatch) -> None:
    from core.wake_phrase import PhraseSpotter, phrase_in_transcript

    monkeypatch.setattr("core.wake_kws.available", lambda: False)
    det = WakeDetector(
        model_path=Path("/nonexistent/hey_jarvis.onnx"),
        model_name="hey_jarvis",
        phrase="hey astra",
    )
    assert det.uses_kws() is False
    assert det.uses_phrase_spotter() is True
    assert det.wake_ready() is False
    assert phrase_in_transcript("Hey, Astra.", "hey astra")
    assert phrase_in_transcript("hey aster", "hey astra")
    assert phrase_in_transcript("hey a star", "hey astra")
    assert not phrase_in_transcript("hey jarvis", "hey astra")
    assert not phrase_in_transcript("hey astronomy", "hey astra")

    calls = {"n": 0}

    def transcribe(_pcm: bytes) -> str:
        calls["n"] += 1
        return "hey astra"

    monkeypatch.setattr("core.wake_phrase.transcribe_pcm16", transcribe)
    loud = b"\xff\x0f" * 1280
    quiet = b"\x00\x00" * 1280
    det.phrase_transcribe = transcribe
    for _ in range(8):
        assert det.feed_pcm16_mono(loud) is False
    for _ in range(8):
        assert det.feed_pcm16_mono(quiet) is False
    assert calls["n"] == 0

    spot = PhraseSpotter("hey astra", transcribe=transcribe)
    for _ in range(8):
        assert spot.feed(loud) is False
    hit = False
    for _ in range(6):
        if spot.feed(quiet):
            hit = True
            break
    assert hit


def test_jarvis_score_alone_does_not_wake_astra(monkeypatch) -> None:
    """A Hey Jarvis score must not count as Hey Astra."""
    calls = {"predict": 0, "whisper": 0, "kws": 0}

    class _Jarvis:
        def predict(self, _samples):
            calls["predict"] += 1
            return {"hey_jarvis": 0.99}

    class _QuietKws:
        def preload(self) -> bool:
            return True

        def feed(self, _pcm: bytes, rate: int = 16000) -> bool:
            calls["kws"] += 1
            return False

        def phrase_pcm(self) -> bytes:
            return b""

        def reset(self) -> None:
            return None

    monkeypatch.setattr("core.wake_kws.available", lambda: True)
    monkeypatch.setattr("core.wake_kws.WakeKeywordSpotter", lambda *a, **k: _QuietKws())

    def transcribe(_pcm: bytes, rate: int = 16000) -> str:
        calls["whisper"] += 1
        return "hey astra"

    monkeypatch.setattr("core.wake_phrase.transcribe_pcm16", transcribe)
    det = WakeDetector(
        model_path=Path("/nonexistent/hey_jarvis.onnx"),
        model_name="hey_jarvis",
        phrase="hey astra",
    )
    det._model = _Jarvis()
    det.phrase_transcribe = transcribe
    loud = b"\xff\x0f" * 1280
    quiet = b"\x00\x00" * 1280
    heard = [det.feed_pcm16_mono(loud) for _ in range(8)]
    heard += [det.feed_pcm16_mono(quiet) for _ in range(8)]
    assert not any(heard)
    assert det._last_source != "model"
    assert calls["predict"] == 0
    assert calls["whisper"] == 0
    assert calls["kws"] == 16


def test_enter_test_wake(monkeypatch) -> None:
    monkeypatch.setattr("core.wake_kws.available", lambda: False)
    det = WakeDetector(model_path=Path("/nonexistent/wake.onnx"))
    assert det.feed_pcm16_mono(b"\x00\x00" * 1600) is False
    det.mark_wake()
    assert det.feed_pcm16_mono(b"\x00\x00" * 1600) is True


def test_last_phrase_pcm_preferred_over_long_buffer(monkeypatch) -> None:
    """Phrase audio is the wake clip. The rolling deque is only the ONNX path."""
    import struct

    from tools.laptop_voice import _wait_for_wake

    class _Mic:
        def __init__(self, **_kwargs):
            self.chunks: list[bytes] = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, n_samples: int):
            if len(self.chunks) > 40:
                raise RuntimeError("wake loop did not stop")
            chunk = struct.pack("<h", len(self.chunks) + 1) * n_samples
            self.chunks.append(chunk)
            return chunk, False

    mic = _Mic()

    def _stream(**_kwargs):
        mic.chunks.clear()
        return mic

    monkeypatch.setattr("tools.laptop_voice.sd.RawInputStream", _stream)
    monkeypatch.setattr("tools.laptop_voice._poll_enter_pressed", lambda: False)
    monkeypatch.setattr("tools.laptop_voice.speech_ms_in_pcm", lambda _pcm, _th: 600)
    monkeypatch.setattr(
        "tools.laptop_voice.time.sleep",
        lambda _s: (_ for _ in ()).throw(RuntimeError("wake loop did not stop")),
    )

    class _Wake:
        def __init__(self, phrase: bytes | None, source: str) -> None:
            self._phrase = phrase
            self._last_source = source

        def available(self) -> bool:
            return False

        def wake_ready(self) -> bool:
            return False

        def reset(self) -> None:
            return None

        def feed_pcm16_mono(self, _pcm: bytes, _rate: int = 16000) -> bool:
            return True

        def last_phrase_pcm(self) -> bytes | None:
            return self._phrase

    class _OnnxWake:
        """ONNX wake has no phrase clip, so the rolling deque is the audio."""

        _last_source = "model"

        def available(self) -> bool:
            return False

        def wake_ready(self) -> bool:
            return False

        def reset(self) -> None:
            return None

        def feed_pcm16_mono(self, _pcm: bytes, _rate: int = 16000) -> bool:
            return True

    phrase = b"\x02\x00" * int(0.5 * 16000)
    ok, pcm, _ms, enter_only = _wait_for_wake(_Wake(phrase, "phrase"))
    rolling = b"".join(mic.chunks)
    assert ok and enter_only is False
    assert pcm == phrase
    assert rolling != phrase
    assert len(rolling) > len(phrase)

    short = b"\x03\x00" * int(0.2 * 16000)
    _ok, pcm, _ms, enter_only = _wait_for_wake(_Wake(short, "phrase"))
    assert enter_only is False
    assert pcm == b"".join(mic.chunks)
    assert pcm != short

    _ok, pcm, _ms, enter_only = _wait_for_wake(_OnnxWake())
    assert enter_only is False
    assert pcm == b"".join(mic.chunks)
    assert len(pcm) >= int(0.4 * 16000) * 2


def test_kws_preferred_over_phrase_spotter(monkeypatch) -> None:
    """A patched keyword spotter wins. Whisper and Jarvis are not loaded."""
    calls = {"whisper": 0, "load": 0}

    class _FakeKws:
        def preload(self) -> bool:
            return True

        def feed(self, _pcm: bytes, rate: int = 16000) -> bool:
            return True

        def phrase_pcm(self) -> bytes:
            return b"kwspcm" + b"\x01\x00" * 4000

        def reset(self) -> None:
            return None

    def transcribe(_pcm: bytes, rate: int = 16000) -> str:
        calls["whisper"] += 1
        return "hey astra"

    def _load(self):
        calls["load"] += 1
        raise AssertionError("hey_jarvis")

    monkeypatch.setattr("core.wake_kws.available", lambda: True)
    monkeypatch.setattr("core.wake_kws.WakeKeywordSpotter", lambda *a, **k: _FakeKws())
    monkeypatch.setattr("core.wake_phrase.transcribe_pcm16", transcribe)
    monkeypatch.setattr(WakeDetector, "_load", _load)

    det = WakeDetector(
        model_path=Path("/nonexistent/hey_jarvis.onnx"),
        model_name="hey_jarvis",
        phrase="hey astra",
    )
    assert det.uses_kws() is True
    assert det.uses_phrase_spotter() is False
    assert det.wake_ready() is True
    assert det.feed_pcm16_mono(b"\x01\x00" * 320) is True
    assert det._last_source == "kws"
    assert det.last_phrase_pcm().startswith(b"kwspcm")
    assert calls["whisper"] == 0
    assert calls["load"] == 0
    assert det._model is None


def test_missing_kws_does_not_call_whisper(monkeypatch) -> None:
    calls = {"whisper": 0}

    def transcribe(_pcm: bytes, rate: int = 16000) -> str:
        calls["whisper"] += 1
        return "hey astra"

    monkeypatch.setattr("core.wake_kws.available", lambda: False)
    monkeypatch.setattr("core.wake_phrase.transcribe_pcm16", transcribe)
    monkeypatch.setattr(
        "core.wake_phrase.warmup_phrase_model",
        lambda: calls.__setitem__("warm", calls.get("warm", 0) + 1),
    )
    det = WakeDetector(
        model_path=Path("/nonexistent/hey_jarvis.onnx"),
        model_name="hey_jarvis",
        phrase="hey astra",
    )
    det.phrase_transcribe = transcribe
    assert det.available() is False
    assert det.wake_ready() is False
    loud = b"\xff\x0f" * 1280
    quiet = b"\x00\x00" * 1280
    for _ in range(12):
        assert det.feed_pcm16_mono(loud) is False
    for _ in range(8):
        assert det.feed_pcm16_mono(quiet) is False
    assert calls["whisper"] == 0
    assert "warm" not in calls
    det.mark_wake()
    assert det.feed_pcm16_mono(quiet) is True


def test_partial_hey_is_kept_until_astra() -> None:
    from core.wake_kws import WakeKeywordSpotter

    class _Stream:
        def __init__(self) -> None:
            self.ready = True
            self.result = "HEY"
            self.resets = 0

        def accept_waveform(self, _rate: int, _samples) -> None:
            return None

    class _Spotter:
        def is_ready(self, stream: _Stream) -> bool:
            return stream.ready

        def decode_stream(self, stream: _Stream) -> None:
            stream.ready = False

        def get_result(self, stream: _Stream) -> str:
            return stream.result

        def reset_stream(self, stream: _Stream) -> None:
            stream.resets += 1
            stream.result = ""
            stream.ready = False

    spot = WakeKeywordSpotter(model_dir=Path("/nonexistent/kws"))
    stream = _Stream()
    spot._kws = _Spotter()
    spot._stream = stream
    assert spot.feed(b"\x01\x00" * 1600) is False
    assert stream.resets == 0
    stream.ready = True
    stream.result = "HEY ASTRA"
    assert spot.feed(b"\xff\x7f" * 8000) is True


def test_jarvis_keyword_text_does_not_wake() -> None:
    from core.wake_kws import WakeKeywordSpotter

    class _Stream:
        def __init__(self, text: str) -> None:
            self.ready = True
            self.result = text

        def accept_waveform(self, _rate: int, _samples) -> None:
            return None

    class _Spotter:
        def is_ready(self, stream: _Stream) -> bool:
            return stream.ready

        def decode_stream(self, stream: _Stream) -> None:
            stream.ready = False

        def get_result(self, stream: _Stream) -> str:
            return stream.result

        def reset_stream(self, stream: _Stream) -> None:
            stream.result = ""
            stream.ready = False

    spot = WakeKeywordSpotter(model_dir=Path("/nonexistent/kws"))
    spot._kws = _Spotter()
    spot._stream = _Stream("▁HE Y ▁J AR VIS")
    loud = b"\xff\x7f" * 8000
    assert spot.feed(loud) is False
    assert spot.phrase_pcm() == b""


def test_astra_onnx_ignores_jarvis_score(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("core.wake_kws.available", lambda: True)
    model = tmp_path / "hey_astra.onnx"
    model.write_bytes(b"not a real onnx")

    class _Scores:
        def predict(self, _samples):
            return {"hey_jarvis": 0.99, "hey_astra": 0.2}

    det = WakeDetector(model_path=model, model_name="hey_astra", phrase="hey astra", threshold=0.5)
    det._model = _Scores()
    assert det.uses_kws() is False
    assert det.feed_pcm16_mono(b"\x01\x00" * 1600) is False
    det._model = type("A", (), {"predict": lambda self, _s: {"hey_astra": 0.8}})()
    assert det.feed_pcm16_mono(b"\x01\x00" * 1600) is True
    assert det._last_source == "model"


def test_astra_onnx_skips_kws(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("core.wake_kws.available", lambda: True)
    model = tmp_path / "hey_astra.onnx"
    model.write_bytes(b"x")
    det = WakeDetector(model_path=model, model_name="hey_astra", phrase="hey astra")
    assert det.uses_kws() is False
    assert det.uses_phrase_spotter() is False


def test_kws_preload_false_without_files(tmp_path: Path) -> None:
    from core.wake_kws import WakeKeywordSpotter

    spot = WakeKeywordSpotter(model_dir=tmp_path)
    assert spot.preload() is False


def test_kws_phrase_pcm_is_trailing_speech() -> None:
    from core.wake_kws import WINDOW_BYTES, WakeKeywordSpotter

    class _Stream:
        def __init__(self) -> None:
            self.ready = False
            self.result = ""

        def accept_waveform(self, _rate: int, samples) -> None:
            if samples.size and float(samples.max()) > 0.5:
                self.ready = True
                self.result = "HEY ASTRA"

    class _Spotter:
        def is_ready(self, stream: _Stream) -> bool:
            return stream.ready

        def decode_stream(self, stream: _Stream) -> None:
            stream.ready = False

        def get_result(self, stream: _Stream) -> str:
            return stream.result

        def reset_stream(self, stream: _Stream) -> None:
            stream.result = ""
            stream.ready = False

    spot = WakeKeywordSpotter(model_dir=Path("/nonexistent/kws"))
    spot._kws = _Spotter()
    spot._stream = _Stream()
    old = b"\x01\x02" * 16000
    silence = b"\x00\x00" * 16000
    recent = b"\x03\x00" * 16000
    speech = b"\xff\x7f" * 8000
    assert spot.feed(old) is False
    assert spot.feed(silence) is False
    assert spot.feed(recent) is False
    assert spot.feed(speech) is True
    phrase = spot.phrase_pcm()
    assert phrase
    assert len(phrase) <= WINDOW_BYTES
    assert len(phrase) < len(old)
    assert old not in phrase
    assert phrase.endswith(speech)
    assert spot._buffered == 0
    assert spot.feed(silence) is False
    assert spot.phrase_pcm() == phrase
    spot.reset()
    assert spot.phrase_pcm() == b""


def test_shipped_keywords_are_hey_astra_only() -> None:
    from core.wake_kws import MODEL_DIR

    raw = MODEL_DIR / "keywords_raw.txt"
    if not raw.is_file():
        return
    lines = [ln.strip() for ln in raw.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines == ["HEY ASTRA", "HEY AS TRA", "HEYASTRA"]
    keywords = MODEL_DIR / "keywords.txt"
    if not keywords.is_file():
        return
    klines = [ln.strip() for ln in keywords.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(klines) == 3
    upper = " ".join(klines).upper()
    for banned in ("AFTER", "ESTHER", "EXTRA", "JARVIS"):
        assert banned not in upper
