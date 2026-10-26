"""Optional web snippets for fresh factual questions."""

from __future__ import annotations

import re
from datetime import date

from core.config import ResearchConfig
from core.safety_list import match_category
from core.turn import Turn
from providers.search import search_snippets

_TRIGGERS = re.compile(
    r"\b(latest|current|today|right now|look up|search for|who is the|who's the|"
    r"what happened|news about|president of|prime minister|weather in|price of)\b",
    re.IGNORECASE,
)


def _needs_research(text: str) -> bool:
    if not text.strip():
        return False
    if match_category(text):
        return False
    lower = text.casefold()
    if lower.startswith(("remember ", "forget ")):
        return False
    return bool(_TRIGGERS.search(text))


def _safety_blocked(turn: Turn) -> bool:
    safety = turn.notes.get("safety")
    return isinstance(safety, dict) and safety.get("blocked") is True


def make_research_step(cfg: ResearchConfig):
    def research_step(turn: Turn) -> None:
        if not cfg.enabled:
            return
        if _safety_blocked(turn):
            return
        text = turn.text_in or ""
        if not _needs_research(text):
            return
        try:
            hits = search_snippets(
                text,
                limit=cfg.max_results,
                wall_timeout=cfg.timeout_s,
            )
        except Exception:
            hits = []
        if not hits:
            turn.notes["research"] = {"ok": False, "snippets": []}
            return
        snippets: list[dict[str, str]] = []
        for hit in hits[: cfg.max_results]:
            body = (hit.get("body") or "")[: cfg.max_snippet_chars]
            title = (hit.get("title") or "")[:120]
            if body or title:
                snippets.append(
                    {
                        "title": title,
                        "body": body,
                        "href": (hit.get("href") or "")[:200],
                    }
                )
        turn.notes["research"] = {
            "ok": True,
            "as_of": date.today().isoformat(),
            "snippets": snippets,
        }

    return research_step
