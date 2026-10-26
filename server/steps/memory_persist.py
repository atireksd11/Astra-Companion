"""Save remember / forget after safety_out."""

from __future__ import annotations

from core.config import MemoryConfig
from core.memory_gates import extract_forget_query, memory_text_ok
from core.turn import Turn
from providers.memory_service import MemoryService


def make_memory_persist_step(cfg: MemoryConfig, memory: MemoryService):
    def memory_persist_step(turn: Turn) -> None:
        if not cfg.enabled:
            return
        safety = turn.notes.get("safety")
        if isinstance(safety, dict) and safety.get("blocked") is True:
            turn.notes.pop("memory_request", None)
            turn.notes.pop("memory_forget", None)
            return
        sid = str(turn.notes.get("speaker_id") or "").strip()
        if not sid:
            return
        forget_q = turn.notes.pop("memory_forget", None)
        if isinstance(forget_q, str) and forget_q.strip():
            n = memory.forget(sid, forget_q.strip())
            turn.notes["memory_persist"] = {"action": "forget", "count": n}
            turn.notes.pop("memory_request", None)
            return
        req = turn.notes.pop("memory_request", None)
        if not isinstance(req, str) or not req.strip():
            return
        reason = memory_text_ok(req)
        if reason:
            turn.notes["memory_persist"] = {"action": "skip", "reason": reason}
            return
        ok = memory.add(sid, req.strip())
        turn.notes["memory_persist"] = {"action": "store", "ok": ok}

    return memory_persist_step
