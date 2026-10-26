from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from core.speech_profile import sanitize_notes_for_storage
from core.turn import Turn
from store.sqlutil import configure_connection


class TurnStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        configure_connection(conn)
        return conn

    def _column_names(self, conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute("PRAGMA table_info(turns)").fetchall()
        return {r[1] for r in rows}

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    text_in TEXT,
                    text_out TEXT,
                    notes_json TEXT,
                    timings_json TEXT,
                    cost_usd REAL,
                    error TEXT,
                    audio_in_bytes INTEGER,
                    audio_out_bytes INTEGER
                )
                """
            )
            cols = self._column_names(conn)
            migrations = {
                "raw_audio_bytes": "INTEGER",
                "trim_audio_bytes": "INTEGER",
                "segment_json": "TEXT",
                "speech_seconds": "REAL",
                "speaker_id": "TEXT",
            }
            for name, typ in migrations.items():
                if name not in cols:
                    conn.execute(f"ALTER TABLE turns ADD COLUMN {name} {typ}")

            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
                    turn_id UNINDEXED,
                    text_in,
                    text_out
                )
                """
            )

    def save_async(self, turn: Turn) -> None:
        threading.Thread(target=self._save, args=(turn,), daemon=True).start()

    def _save(self, turn: Turn) -> None:
        seg = turn.notes.get("segment", {})
        raw_b = turn.notes.get("raw_audio_bytes", len(turn.pcm_in))
        trim_b = turn.notes.get("trim_audio_bytes", len(turn.pcm_in))
        speech_s = seg.get("trim_s", turn.audio_in_seconds())

        sid = str(turn.notes.get("speaker_id") or "").strip() or None
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO turns
                    (id, created_at, text_in, text_out, notes_json, timings_json,
                     cost_usd, error, audio_in_bytes, audio_out_bytes,
                     raw_audio_bytes, trim_audio_bytes, segment_json, speech_seconds,
                     speaker_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        turn.id,
                        turn.created_at,
                        turn.text_in,
                        turn.text_out,
                        json.dumps(sanitize_notes_for_storage(turn.notes)),
                        json.dumps(turn.timings_ms),
                        turn.cost_usd,
                        turn.error,
                        len(turn.pcm_in),
                        len(turn.pcm_out),
                        raw_b,
                        trim_b,
                        json.dumps(seg),
                        speech_s,
                        sid,
                    ),
                )
                conn.execute(
                    "DELETE FROM turns_fts WHERE turn_id = ?",
                    (turn.id,),
                )
                conn.execute(
                    "INSERT INTO turns_fts(turn_id, text_in, text_out) VALUES (?, ?, ?)",
                    (turn.id, turn.text_in or "", turn.text_out or ""),
                )

    def recent_text_pairs(
        self, limit: int = 2, *, speaker_id: str | None = None
    ) -> list[tuple[str, str]]:
        """Newest text_in/text_out pairs first. Scoped to speaker_id when set."""
        limit = max(0, int(limit))
        if limit == 0:
            return []
        sid = (speaker_id or "").strip() or None
        with self._lock:
            with self._connect() as conn:
                if sid:
                    rows = conn.execute(
                        "SELECT text_in, text_out FROM turns "
                        "WHERE speaker_id = ? AND ("
                        "COALESCE(text_in, '') != '' OR COALESCE(text_out, '') != '') "
                        "ORDER BY created_at DESC LIMIT ?",
                        (sid, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT text_in, text_out FROM turns "
                        "WHERE COALESCE(text_in, '') != '' "
                        "OR COALESCE(text_out, '') != '' "
                        "ORDER BY created_at DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
        return [(row[0] or "", row[1] or "") for row in rows]

    def recent(self, limit: int = 10) -> list[sqlite3.Row]:
        with self._lock:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                return conn.execute(
                    "SELECT id, speech_seconds, raw_audio_bytes, trim_audio_bytes, "
                    "segment_json, error FROM turns ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
