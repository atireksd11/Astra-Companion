"""Wake phrase detection.

A custom hey_astra.onnx file is used with openWakeWord when it exists.
Otherwise Hey Astra is heard by the sherpa-onnx keyword spotter when that
package and the int8 model files are present. The bundled hey_jarvis model
is not treated as a match. Enter still wakes through mark_wake().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

import core.wake_kws as wake_kws

try:
    from openwakeword.model import Model as _OwwModel

    _HAS_OWW = True
except ImportError:
    _OwwModel = None  # type: ignore[misc, assignment]
    _HAS_OWW = False


def _has_astra_file(path: Path | None) -> bool:
    return path is not None and path.is_file() and "astra" in path.name.casefold()


@dataclass
class WakeDetector:
    model_path: Path | None = None
    model_name: str = "hey_jarvis"
    phrase: str = "hey astra"
    threshold: float = 0.5
    phrase_transcribe: object | None = None
    _model: object | None = field(default=None, repr=False)
    _test_wake_pending: bool = field(default=False, repr=False)
    _spotter: object | None = field(default=None, repr=False)
    _kws: object | None = field(default=None, repr=False)
    _last_source: str = field(default="", repr=False)
    _last_phrase_pcm: bytes = field(default=b"", repr=False)

    def _has_astra_onnx(self) -> bool:
        return _has_astra_file(self.model_path)

    def uses_kws(self) -> bool:
        """Keyword spotter hears Hey Astra when no custom Astra ONNX is installed."""
        if self._has_astra_onnx():
            return False
        phrase = " ".join((self.phrase or "").casefold().split())
        if phrase != "hey astra":
            return False
        return wake_kws.available()

    def uses_phrase_spotter(self) -> bool:
        """Jarvis (or any non-Astra) ONNX cannot hear the Astra phrase.

        The keyword spotter replaces this path when it is available.
        """
        if self._has_astra_onnx() or self.uses_kws():
            return False
        phrase = (self.phrase or "").casefold()
        name = (self.model_name or "").casefold()
        return "astra" in phrase and "astra" not in name

    def available(self) -> bool:
        if self._has_astra_onnx():
            return self._load() is not None
        if self.uses_kws():
            return True
        return False

    def wake_ready(self) -> bool:
        if self._has_astra_onnx():
            return _HAS_OWW
        if self.uses_kws():
            return True
        return False

    def preload(self) -> bool:
        """Load the active backend. The keyword spotter prints nothing huge."""
        if self._has_astra_onnx():
            return self._load() is not None
        spotter = self._kws_spotter()
        if spotter is None:
            return False
        return bool(spotter.preload())

    def _kws_spotter(self):
        if not self.uses_kws():
            return None
        if self._kws is None:
            self._kws = wake_kws.WakeKeywordSpotter()
        return self._kws

    def _load(self):
        if self._model is not None:
            return self._model
        if not _HAS_OWW or _OwwModel is None:
            return None
        path = self.model_path
        if not _has_astra_file(path):
            return None
        try:
            self._model = _OwwModel(
                wakeword_models=[str(path)],
                inference_framework="onnx",
            )
        except Exception:
            self._model = None
        return self._model

    def reset(self) -> None:
        """Clear leftover scores so the next listen cannot instant-fire."""
        model = self._model
        if model is not None and hasattr(model, "reset"):
            model.reset()
        spotter = self._spotter
        if spotter is not None and hasattr(spotter, "reset"):
            spotter.reset()
        if self._kws is not None and hasattr(self._kws, "reset"):
            self._kws.reset()
        self._last_source = ""
        self._last_phrase_pcm = b""

    def last_phrase_pcm(self) -> bytes:
        """Keyword audio from the last kws hit. Empty until then."""
        return self._last_phrase_pcm

    def mark_wake(self) -> None:
        self._test_wake_pending = True

    def consume_test_wake(self) -> bool:
        if self._test_wake_pending:
            self._test_wake_pending = False
            return True
        return False

    def feed_pcm16_mono(self, pcm: bytes, rate: int = 16000) -> bool:
        if self.consume_test_wake():
            return True
        if not pcm or rate != 16000:
            return False
        if self._has_astra_onnx():
            return self._feed_openwakeword(pcm)
        spotter = self._kws_spotter()
        if spotter is not None:
            if spotter.feed(pcm, rate):
                self._last_source = "kws"
                self._last_phrase_pcm = bytes(spotter.phrase_pcm())
                return True
            return False
        return False

    def _feed_openwakeword(self, pcm: bytes) -> bool:
        model = self._load()
        if model is None:
            return False
        samples = np.frombuffer(pcm, dtype=np.int16)
        try:
            scores = model.predict(samples)
            if isinstance(scores, dict):
                hit = any(
                    float(v) >= self.threshold and "jarvis" not in str(key).casefold()
                    for key, v in scores.items()
                )
            else:
                hit = float(scores) >= self.threshold
        except Exception:
            return False
        if hit:
            self._last_source = "model"
        return hit
