"""Durable memory per speaker_id. Mem0 when configured, else local MemoryStore."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from core.config import MemoryConfig
from store.memory_store import MemoryStore


class MemoryBackend(Protocol):
    def search(self, speaker_id: str, query: str, *, limit: int = 5) -> list[str]: ...
    def add(self, speaker_id: str, text: str) -> bool: ...
    def forget(self, speaker_id: str, query: str) -> int: ...


class _LocalBackend:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def search(self, speaker_id: str, query: str, *, limit: int = 5) -> list[str]:
        hits = self._store.search(speaker_id, query, limit=limit)
        return [text for _mid, text, _score in hits]

    def add(self, speaker_id: str, text: str) -> bool:
        return self._store.add(speaker_id, text)

    def forget(self, speaker_id: str, query: str) -> int:
        return self._store.revoke_matching(speaker_id, query)


class _Mem0Backend:
    def __init__(self, memory: object) -> None:
        self._memory = memory

    def search(self, speaker_id: str, query: str, *, limit: int = 5) -> list[str]:
        try:
            raw = self._memory.search(query, user_id=speaker_id, limit=limit)
        except Exception:
            return []
        results = raw.get("results") if isinstance(raw, dict) else raw
        if not isinstance(results, list):
            return []
        out: list[str] = []
        for item in results:
            if isinstance(item, dict):
                mem = item.get("memory") or item.get("text") or ""
                if isinstance(mem, str) and mem.strip():
                    out.append(mem.strip())
        return out

    def add(self, speaker_id: str, text: str) -> bool:
        try:
            self._memory.add(
                [{"role": "user", "content": text}],
                user_id=speaker_id,
            )
            return True
        except Exception:
            return False

    def forget(self, speaker_id: str, query: str) -> int:
        del query
        return 0


def build_memory_service(cfg: MemoryConfig, db_path: Path) -> MemoryBackend:
    local = _LocalBackend(MemoryStore(db_path))
    if not cfg.enabled or not cfg.use_mem0:
        return local
    os.environ.setdefault("MEM0_TELEMETRY", "false")
    try:
        from mem0 import Memory
    except ImportError:
        return local
    if not os.environ.get("GROQ_API_KEY", "").strip():
        return local
    qdrant = Path(cfg.qdrant_path)
    if not qdrant.is_absolute():
        qdrant = Path(__file__).resolve().parent.parent / qdrant
    qdrant.mkdir(parents=True, exist_ok=True)
    hist = Path(cfg.history_db_path)
    if not hist.is_absolute():
        hist = Path(__file__).resolve().parent.parent / hist
    hist.parent.mkdir(parents=True, exist_ok=True)
    mem_cfg = {
        "history_db_path": str(hist),
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": cfg.collection_name,
                "path": str(qdrant),
                "embedding_model_dims": cfg.embedding_dims,
                "on_disk": True,
            },
        },
        "llm": {
            "provider": "groq",
            "config": {
                "model": cfg.groq_model,
                "temperature": 0.1,
                "max_tokens": 512,
            },
        },
        "embedder": {
            "provider": "fastembed",
            "config": {"model": cfg.embed_model},
        },
    }
    try:
        mem = Memory.from_config(mem_cfg)
        return _Mem0Backend(mem)
    except Exception:
        return local


class MemoryService:
    def __init__(self, backend: MemoryBackend) -> None:
        self._backend = backend

    def search(self, speaker_id: str, query: str, *, limit: int = 5) -> list[str]:
        return self._backend.search(speaker_id, query, limit=limit)

    def add(self, speaker_id: str, text: str) -> bool:
        return self._backend.add(speaker_id, text)

    def forget(self, speaker_id: str, query: str) -> int:
        return self._backend.forget(speaker_id, query)
