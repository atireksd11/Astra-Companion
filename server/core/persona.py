"""Load the shared Astra character bible."""

from __future__ import annotations

from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parent.parent
_PERSONA_PATH = SERVER_ROOT / "persona" / "astra.md"
_cached: str | None = None


def load_persona_bible() -> str:
    global _cached
    if _cached is not None:
        return _cached
    if _PERSONA_PATH.is_file():
        _cached = _PERSONA_PATH.read_text(encoding="utf-8").strip()
    else:
        _cached = (
            "You are Astra, a small warm companion robot. "
            "Keep replies to one or two short sentences. "
            "You are playful and kind, not a doctor or lawyer."
        )
    return _cached
