"""Attach a vision caption to the turn when an image was supplied."""

from __future__ import annotations

from core.config import VisionConfig
from core.turn import Turn
from providers import vision as vision_provider

_JPEG = b"\xff\xd8"
_PNG = b"\x89PNG\r\n\x1a\n"


def image_bytes_ok(raw: bytes, mime: str) -> bool:
    """True when the bytes match the JPEG or PNG header for this MIME type."""
    kind = (mime or "").split(";", 1)[0].strip().lower()
    if kind in ("image/jpeg", "image/jpg"):
        return len(raw) >= 3 and raw.startswith(_JPEG)
    if kind == "image/png":
        return raw.startswith(_PNG)
    return False


def make_vision_step(cfg: VisionConfig):
    def vision_step(turn: Turn) -> None:
        if not cfg.enabled:
            return
        blob = turn.notes.get("vision_image")
        if not isinstance(blob, dict):
            return
        raw = blob.get("bytes")
        if not isinstance(raw, (bytes, bytearray)) or not raw:
            return
        mime = str(blob.get("mime") or "image/jpeg")
        try:
            limit = int(cfg.max_bytes)
        except (TypeError, ValueError):
            limit = 400_000
        if len(raw) > limit:
            turn.notes["vision"] = {"ok": False, "detail": "too_large"}
            return
        if not image_bytes_ok(bytes(raw), mime):
            turn.notes["vision"] = {"ok": False, "detail": "bad_image"}
            return
        try:
            result = vision_provider.describe_image(bytes(raw), mime, provider=cfg.provider)
        except Exception:
            turn.notes["vision"] = {"ok": False, "detail": "vision_failed"}
            return
        caption = result.text if result.ok else ""
        if caption:
            from core.safety_list import match_category

            if match_category(caption):
                turn.notes["vision"] = {"ok": False, "detail": "blocked_caption"}
                turn.notes["safety"] = {"blocked": True, "source": "vision_caption"}
                return
        turn.notes["vision"] = {
            "ok": result.ok,
            "caption": result.text,
            "provider": result.provider,
            "detail": result.detail,
        }

    return vision_step
