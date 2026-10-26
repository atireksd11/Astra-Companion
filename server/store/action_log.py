"""Idempotent robot action keys (replay-safe done messages)."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from store.sqlutil import configure_connection


class ActionLog:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        configure_connection(conn)
        return conn

    def _ensure(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS robot_actions (
                    idempotency_key TEXT PRIMARY KEY,
                    turn_id TEXT,
                    action_name TEXT,
                    created_at REAL NOT NULL
                )
                """
            )

    def claim(self, key: str, *, turn_id: str, action_name: str) -> bool:
        """Return True only the first time this key is seen."""
        key = (key or "").strip()
        if not key:
            return False
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO robot_actions (idempotency_key, turn_id, action_name, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (key, turn_id, action_name, now),
                    )
                    return True
                except sqlite3.IntegrityError:
                    return False
