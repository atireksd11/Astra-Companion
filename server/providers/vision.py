"""Describe a JPEG/PNG for the LLM context (Groq vision, OpenRouter fallback)."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.2-11b-vision-preview:free"
_PROMPT = "Describe this image in one or two short sentences for a voice assistant. No markdown."

_HTTP: httpx.Client | None = None


def _client() -> httpx.Client:
    global _HTTP
    if _HTTP is None:
        _HTTP = httpx.Client(timeout=httpx.Timeout(connect=3.0, read=20.0, write=10.0, pool=3.0))
    return _HTTP


@dataclass
class VisionResult:
    ok: bool
    text: str
    provider: str
    detail: str = ""


def _groq_key() -> str:
    return os.environ.get("GROQ_API_KEY", "").strip()


def _openrouter_key() -> str:
    return os.environ.get("OPENROUTER_API_KEY", "").strip()


def describe_image(
    image_bytes: bytes,
    mime: str = "image/jpeg",
    *,
    provider: str | None = None,
    prompt: str = _PROMPT,
) -> VisionResult:
    if not image_bytes:
        return VisionResult(False, "", "", detail="empty_image")
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    choice = (provider or "groq").strip().casefold()
    routes: tuple[tuple[str, str, str], ...]
    if choice == "openrouter":
        routes = (("openrouter", OPENROUTER_URL, DEFAULT_OPENROUTER_MODEL),)
    else:
        routes = (
            ("groq", GROQ_URL, os.environ.get("GROQ_VISION_MODEL", DEFAULT_GROQ_MODEL)),
            ("openrouter", OPENROUTER_URL, DEFAULT_OPENROUTER_MODEL),
        )

    last_detail = "no_key"
    for name, url, model in routes:
        key = _groq_key() if name == "groq" else _openrouter_key()
        if not key:
            continue
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        if name == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/atireksd11/Astra-Companion"
        body = {"model": model, "messages": messages, "max_tokens": 120, "temperature": 0.2}
        try:
            resp = _client().post(url, headers=headers, json=body)
            if resp.status_code >= 400:
                last_detail = f"http_{resp.status_code}"
                continue
            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if content:
                return VisionResult(True, content, name)
            last_detail = "empty_content"
        except Exception as exc:
            last_detail = str(exc)
            continue
    return VisionResult(False, "", "", detail=last_detail)
