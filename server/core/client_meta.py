"""Sanitize untrusted client `start.meta` payloads."""

from __future__ import annotations

import base64
import json
from typing import Any

# Keys the laptop / robot may send. Everything else is dropped.
_ALLOWED_SCALAR_KEYS = frozenset(
    {
        "noise",
        "level",
        "vol",
        "source",
        "wake",
        "enter_wake",
        "channels",
        "wake_pcm_separate",
    }
)
_MAX_META_JSON_BYTES = 8192
_MAX_WAKE_B64_CHARS = 512_000  # ~384 KB audio


def _clip_wake_b64(value: str) -> str:
    if len(value) > _MAX_WAKE_B64_CHARS:
        value = value[:_MAX_WAKE_B64_CHARS]
    try:
        base64.b64decode(value, validate=True)
    except Exception:
        return ""
    return value


def sanitize_client_meta(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    try:
        slim = {
            k: v
            for k, v in raw.items()
            if k not in ("wake_b64", "enroll_b64")
        }
        encoded = json.dumps(slim, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError):
        return {}
    if len(encoded) > _MAX_META_JSON_BYTES:
        return {}

    out: dict[str, Any] = {}
    for key, val in raw.items():
        if key == "wake_b64" and isinstance(val, str):
            clipped = _clip_wake_b64(val)
            if clipped:
                out["wake_b64"] = clipped
            continue
        if key == "enroll_b64" and isinstance(val, str):
            clipped = _clip_wake_b64(val)
            if clipped:
                out["enroll_b64"] = clipped
            continue
        if key in ("speaker_id", "teach"):
            continue
        if key not in _ALLOWED_SCALAR_KEYS:
            continue
        if isinstance(val, (str, int, float, bool)):
            out[key] = val
    return out
