"""Per-speaker durable facts (SQLite + optional FastEmbed vectors)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

import numpy as np

from store.sqlutil import configure_connection

_EMBED_MODEL = "BAAI/bge-small-en-v1.5"
_embedder = None
_embed_lock = threading.Lock()


def _embedder_model():
    global _embedder
    with _embed_lock:
        if _embedder is None:
            from fastembed import TextEmbedding

            _embedder = TextEmbedding(model_name=_EMBED_MODEL)
        return _embedder


def _embed(text: str) -> np.ndarray | None:
    try:
        model = _embedder_model()
        vec = next(model.embed([text]))
        arr = np.asarray(vec, dtype=np.float32).reshape(-1)
        if arr.size == 0:
            return None
        norm = float(np.linalg.norm(arr))
        if norm > 1e-8:
            arr = arr / norm
        return arr
    except Exception:
        return None


class MemoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        configure_connection(conn)
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    speaker_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    vec BLOB
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    memory_id UNINDEXED,
                    speaker_id UNINDEXED,
                    text
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_speaker ON memory_items(speaker_id)"
            )

    @staticmethod
    def _hash(text: str) -> str:
        import hashlib

        return hashlib.sha256(text.strip().casefold().encode()).hexdigest()

    def add(self, speaker_id: str, text: str) -> bool:
        sid = (speaker_id or "").strip()
        fact = (text or "").strip()
        if not sid or not fact:
            return False
        h = self._hash(fact)
        vec = _embed(fact)
        blob = vec.tobytes() if vec is not None else None
        mid = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id FROM memory_items WHERE speaker_id = ? AND content_hash = ? AND revoked = 0",
                    (sid, h),
                ).fetchone()
                if row:
                    return False
                conn.execute(
                    """
                    INSERT INTO memory_items (id, speaker_id, text, content_hash, revoked, created_at, vec)
                    VALUES (?, ?, ?, ?, 0, ?, ?)
                    """,
                    (mid, sid, fact, h, now, blob),
                )
                conn.execute(
                    "DELETE FROM memory_fts WHERE memory_id = ?",
                    (mid,),
                )
                conn.execute(
                    "INSERT INTO memory_fts(memory_id, speaker_id, text) VALUES (?, ?, ?)",
                    (mid, sid, fact),
                )
        return True

    def revoke_matching(self, speaker_id: str, query: str, limit: int = 3) -> int:
        hits = self.search(speaker_id, query, limit=limit, min_score=0.35)
        if not hits:
            return 0
        ids = [h[0] for h in hits]
        with self._lock:
            with self._connect() as conn:
                for mid in ids:
                    conn.execute(
                        "UPDATE memory_items SET revoked = 1 WHERE id = ? AND speaker_id = ?",
                        (mid, speaker_id),
                    )
                    conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (mid,))
        return len(ids)

    def search(
        self,
        speaker_id: str,
        query: str,
        *,
        limit: int = 5,
        min_score: float = 0.55,
    ) -> list[tuple[str, str, float]]:
        sid = (speaker_id or "").strip()
        if not sid:
            return []
        qvec = _embed(query)
        scored: list[tuple[str, str, float]] = []
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, text, vec FROM memory_items WHERE speaker_id = ? AND revoked = 0",
                    (sid,),
                ).fetchall()
        if qvec is not None:
            for mid, text, blob in rows:
                if not blob:
                    continue
                vec = np.frombuffer(blob, dtype=np.float32)
                if vec.size != qvec.size:
                    continue
                score = float(np.dot(qvec, vec))
                if score >= min_score:
                    scored.append((mid, text, score))
        scored.sort(key=lambda x: x[2], reverse=True)
        if scored:
            return scored[:limit]

        from store.fts_safe import fts_safe_terms

        safe = fts_safe_terms(query)
        if not safe:
            return []
        with self._lock:
            with self._connect() as conn:
                try:
                    fts_rows = conn.execute(
                        "SELECT memory_id, text FROM memory_fts WHERE memory_fts MATCH ? AND speaker_id = ? LIMIT ?",
                        (safe, sid, limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    fts_rows = []
        return [(r[0], r[1], 0.5) for r in fts_rows]
