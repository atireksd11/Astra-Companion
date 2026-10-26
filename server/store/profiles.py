from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

import numpy as np

from core.speech_profile import empty_profile, find_speaker_id, new_speaker_id
from core.speaker_id import embed_pcm16_mono
from store.sqlutil import configure_connection


class ProfileStore:
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
                CREATE TABLE IF NOT EXISTS speaker_profiles (
                    speaker_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    def get(self, speaker_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT profile_json FROM speaker_profiles WHERE speaker_id = ?",
                    (speaker_id,),
                ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def put(self, profile: dict[str, Any]) -> None:
        sid = profile["speaker_id"]
        updated = float(profile.get("updated_at", 0))
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO speaker_profiles
                    (speaker_id, profile_json, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (sid, json.dumps(profile), updated),
                )

    def list_all(self) -> list[dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT profile_json FROM speaker_profiles ORDER BY updated_at DESC"
                ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def resolve_speaker(
        self,
        *,
        meta_speaker_id: str | None,
        embedding: np.ndarray | None,
        enroll_pcm: bytes | None,
        rate: int,
        min_similarity: float,
        lock_owner: bool = False,
        owner_speaker_id: str = "",
    ) -> tuple[str, dict[str, Any]]:
        from core.owner import find_owner_doc

        if meta_speaker_id:
            existing = self.get(meta_speaker_id)
            if existing:
                return meta_speaker_id, existing

        profiles = self.list_all()
        if lock_owner:
            owner = find_owner_doc(profiles, owner_speaker_id)
            if owner:
                return str(owner["speaker_id"]), owner

        if embedding is None and enroll_pcm:
            embedding = embed_pcm16_mono(enroll_pcm, rate)
            if embedding.size == 13:
                embedding = None

        if embedding is not None and embedding.size:
            matched = find_speaker_id(profiles, embedding, min_similarity)
            if matched:
                doc = self.get(matched)
                assert doc is not None
                return matched, doc

        if lock_owner:
            owner = find_owner_doc(profiles, owner_speaker_id)
            if owner:
                return str(owner["speaker_id"]), owner

        sid = new_speaker_id()
        emb_list = embedding.tolist() if embedding is not None and embedding.size == 192 else []
        return sid, empty_profile(sid, emb_list)
