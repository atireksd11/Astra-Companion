"""Load profile card, memories, and turn excerpts before the LLM."""

from __future__ import annotations

from pathlib import Path

from core.config import MemoryConfig
from providers.memory_service import MemoryService
from core.turn import Turn
from store.memory import search_turns
from store.profiles import ProfileStore


def _referential(text: str) -> bool:
    lower = (text or "").casefold()
    hints = (
        "last time",
        "you said",
        "you told",
        "remember when",
        "what did i",
        "what did you",
        "earlier",
        "before",
    )
    return any(h in lower for h in hints)


def make_context_retrieve_step(
    cfg: MemoryConfig,
    profiles: ProfileStore,
    memory: MemoryService,
    db_path: Path,
):
    def context_retrieve_step(turn: Turn) -> None:
        if not cfg.enabled:
            return
        safety = turn.notes.get("safety")
        if isinstance(safety, dict) and safety.get("blocked"):
            return
        sid = str(turn.notes.get("speaker_id") or "").strip()
        pack: dict = {"memories": [], "turn_excerpts": []}
        if sid:
            doc = profiles.get(sid)
            if doc:
                pack["profile"] = doc.get("context") or {}
        query = turn.text_in or ""
        if sid and query.strip():
            pack["memories"] = memory.search(sid, query, limit=cfg.search_limit)[: cfg.search_limit]
        if len(pack["memories"]) < 2 and _referential(query):
            for turn_id, tin, tout in search_turns(
                db_path, query, limit=2, speaker_id=sid
            ):
                excerpt = f"user: {tin}\nastra: {tout}"[:240]
                pack["turn_excerpts"].append({"turn_id": turn_id, "text": excerpt})
        turn.notes["context_pack"] = pack

    return context_retrieve_step
