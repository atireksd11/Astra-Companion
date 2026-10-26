"""Web search snippets for time-sensitive questions (ddgs, no API key)."""

from __future__ import annotations

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

_CACHE: dict[str, tuple[float, list[dict[str, str]]]] = {}
_CACHE_TTL_S = 600.0


def _cache_key(query: str) -> str:
    return hashlib.sha256(query.strip().casefold().encode()).hexdigest()


def _run_ddgs(query: str, limit: int, http_timeout: float) -> list[dict[str, str]]:
    from ddgs import DDGS

    out: list[dict[str, str]] = []
    with DDGS(timeout=http_timeout) as client:
        for hit in client.text(query, max_results=limit, backend="duckduckgo"):
            if not isinstance(hit, dict):
                continue
            title = str(hit.get("title") or "").strip()
            body = str(hit.get("body") or hit.get("snippet") or "").strip()
            href = str(hit.get("href") or hit.get("link") or "").strip()
            if title or body:
                out.append({"title": title, "body": body, "href": href})
    return out


def search_snippets(
    query: str,
    *,
    limit: int = 4,
    http_timeout: float = 4.0,
    wall_timeout: float = 1.5,
) -> list[dict[str, str]]:
    q = (query or "").strip()
    if not q:
        return []
    key = _cache_key(q)
    now = time.time()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < _CACHE_TTL_S:
        return list(cached[1])

    def _work() -> list[dict[str, str]]:
        return _run_ddgs(q, limit, http_timeout)

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_work)
            hits = fut.result(timeout=wall_timeout)
    except (FuturesTimeout, Exception):
        hits = []

    _CACHE[key] = (now, hits)
    return hits
