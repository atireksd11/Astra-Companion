"""One chat completion per turn. Groq, then OpenRouter, then a canned line.

No SDK. No streaming. No retry loop: each provider is attempted once.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"
OPENROUTER_MODEL = "openai/gpt-oss-20b:free"

OFFLINE_LINE = "I can't reach my online voice right now."
LIMIT_LINE = "I've hit today's limit."

INPUT_USD_PER_TOKEN = 0.075 / 1_000_000
OUTPUT_USD_PER_TOKEN = 0.30 / 1_000_000

_GROQ_TIMEOUT = httpx.Timeout(connect=3.0, read=15.0, write=8.0, pool=3.0)
_OPENROUTER_TIMEOUT = httpx.Timeout(connect=3.0, read=12.0, write=12.0, pool=3.0)
_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_HTTP: httpx.Client | None = None
_RETRYABLE = frozenset({"empty_content", "timeout", "network", "http_429", "http_502", "http_503"})


def _http_client() -> httpx.Client:
    global _HTTP
    if _HTTP is None:
        _HTTP = httpx.Client()
    return _HTTP


@dataclass
class ChatResult:
    ok: bool
    content: str
    provider: str
    cost_usd: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    detail: str = ""


def _choice(provider: str | None) -> str:
    return (provider or "").strip().casefold()


def has_llm_key(provider: str | None = None) -> bool:
    """True when the selected route has a key.

    ``openrouter`` needs OPENROUTER_API_KEY. ``groq`` and any other name need
    Groq or OpenRouter. Another name is not a third backend.
    """
    if _choice(provider) == "openrouter":
        return bool(_openrouter_key())
    return bool(_groq_key() or _openrouter_key())


def _routes(provider: str | None) -> tuple[str, ...]:
    """Groq then OpenRouter, or OpenRouter alone. Never a new host."""
    if _choice(provider) == "openrouter":
        return ("openrouter",)
    return ("groq", "openrouter")


def json_object_text(text: str) -> dict | None:
    """One JSON object, or one markdown fence around one object. Prose is not scraped."""
    raw = (text or "").strip().lstrip("\ufeff").strip()
    if not raw:
        return None
    candidates = [raw]
    fenced = _FENCE.fullmatch(raw)
    if fenced:
        candidates.append(fenced.group(1).strip())
    seen: set[str] = set()
    for item in candidates:
        if not item or item in seen:
            continue
        seen.add(item)
        try:
            obj = json.loads(item)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _groq_key() -> str:
    return os.environ.get("GROQ_API_KEY", "").strip()


def _openrouter_key() -> str:
    return os.environ.get("OPENROUTER_API_KEY", "").strip()


def cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens * INPUT_USD_PER_TOKEN
        + completion_tokens * OUTPUT_USD_PER_TOKEN
    )


def _public_messages(messages: list[dict]) -> list[dict]:
    """One system message, then user and assistant turns. Extra system roles are dropped."""
    out: list[dict] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role not in ("system", "user", "assistant") or not isinstance(content, str):
            continue
        # Only the first message may be system. A later system role is dropped.
        if role == "system" and out:
            continue
        out.append({"role": role, "content": content})
    return out


def chat_completion(
    messages: list[dict],
    *,
    temperature: float = 0.6,
    max_completion_tokens: int = 256,
    provider: str | None = None,
) -> ChatResult:
    """Return the first selected route that answers. No key and no network → not ok.

    ``provider`` may only choose Groq or OpenRouter. Any other value, including
    ``openai``, keeps Groq then OpenRouter and is never used as a URL or model.
    """
    if not has_llm_key(provider):
        return ChatResult(False, "", "canned", 0.0)

    last_detail = ""
    for name in _routes(provider):
        if name == "groq":
            key = _groq_key()
            if not key:
                continue
            result, detail = _groq_with_retry(
                key,
                messages,
                temperature,
                max_completion_tokens,
            )
        else:
            key = _openrouter_key()
            if not key:
                continue
            result, detail = _once(
                OPENROUTER_URL,
                key,
                OPENROUTER_MODEL,
                messages,
                _OPENROUTER_TIMEOUT,
                "openrouter",
                temperature,
                max_completion_tokens,
                reasoning_effort=False,
            )
            if result is None and detail in _RETRYABLE:
                result, detail = _once(
                    OPENROUTER_URL,
                    key,
                    OPENROUTER_MODEL,
                    messages,
                    _OPENROUTER_TIMEOUT,
                    "openrouter",
                    temperature,
                    max_completion_tokens,
                    reasoning_effort=False,
                )
        if detail:
            last_detail = detail
        if result is not None:
            return result

    return ChatResult(False, "", "canned", 0.0, detail=last_detail)


def _groq_with_retry(
    key: str,
    messages: list[dict],
    temperature: float,
    max_completion_tokens: int,
) -> tuple[ChatResult | None, str]:
    result, detail = _once(
        GROQ_URL,
        key,
        GROQ_MODEL,
        messages,
        _GROQ_TIMEOUT,
        "groq",
        temperature,
        max_completion_tokens,
        json_mode=True,
    )
    if result is not None:
        return result, ""
    if detail not in _RETRYABLE:
        return None, detail
    return _once(
        GROQ_URL,
        key,
        GROQ_MODEL,
        messages,
        _GROQ_TIMEOUT,
        "groq",
        temperature,
        max_completion_tokens,
        reasoning_effort=False,
        json_mode=True,
    )


def _once(
    url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: httpx.Timeout,
    provider: str,
    temperature: float,
    max_completion_tokens: int,
    *,
    reasoning_effort: bool = True,
    json_mode: bool = False,
) -> tuple[ChatResult | None, str]:
    body: dict = {
        "model": model,
        "messages": _public_messages(messages),
        "temperature": temperature,
        "max_completion_tokens": max_completion_tokens,
    }
    if reasoning_effort:
        body["reasoning_effort"] = "low"
    if json_mode and provider == "groq":
        body["response_format"] = {"type": "json_object"}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    client = _http_client()
    try:
        resp = client.post(url, headers=headers, json=body, timeout=timeout)
        if resp.status_code == 400 and reasoning_effort:
            retry_body = {k: v for k, v in body.items() if k != "reasoning_effort"}
            resp = client.post(url, headers=headers, json=retry_body, timeout=timeout)
    except httpx.TimeoutException:
        return None, "timeout"
    except Exception:
        return None, "network"
    if resp.status_code != 200:
        return None, f"http_{resp.status_code}"
    try:
        data = resp.json()
    except Exception:
        return None, "bad_response"
    content = _content(data)
    if not content:
        content = _reasoning_json(data)
    if not content:
        return None, "empty_content"
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        usage = {}
    prompt = _as_int(usage.get("prompt_tokens"))
    completion = _as_int(usage.get("completion_tokens"))
    return (
        ChatResult(
            True,
            content,
            provider,
            cost_usd(prompt, completion),
            prompt,
            completion,
        ),
        "",
    )


def _reasoning_json(data: object) -> str:
    """Use the reasoning channel only when it is the reply JSON and content is empty.

    A thinking trace must not count as the completion. That would skip the
    OpenRouter fallback and could speak the trace.
    """
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    reasoning = message.get("reasoning")
    if not isinstance(reasoning, str):
        return ""
    obj = json_object_text(reasoning)
    if not isinstance(obj, dict) or not isinstance(obj.get("say"), str):
        return ""
    return reasoning.strip()


def _content(data: object) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    raw = message.get("content")
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list):
        parts: list[str] = []
        for item in raw:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts).strip()
    return ""


def _as_int(value: object) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0
