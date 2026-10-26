from __future__ import annotations

import sqlite3
from pathlib import Path

from store.fts_safe import fts_safe_terms
from store.sqlutil import configure_connection


def total_speech_seconds_saved(db_path: Path) -> float:
    """Sum of (raw - trim) duration implied by segment stats."""
    if not db_path.is_file():
        return 0.0
    conn = sqlite3.connect(db_path)
    configure_connection(conn)
    with conn:
        rows = conn.execute(
            "SELECT raw_audio_bytes, trim_audio_bytes FROM turns "
            "WHERE raw_audio_bytes IS NOT NULL"
        ).fetchall()
    saved = 0.0
    for raw_b, trim_b in rows:
        if raw_b and trim_b and raw_b > trim_b:
            saved += (raw_b - trim_b) / (2 * 16000)
    return saved


def search_turns(
    db_path: Path,
    query: str,
    limit: int = 5,
    *,
    speaker_id: str | None = None,
) -> list[tuple[str, str, str]]:
    if not db_path.is_file() or not query.strip():
        return []
    safe = fts_safe_terms(query, operator="OR")
    if not safe:
        return []
    sid = (speaker_id or "").strip() or None
    conn = sqlite3.connect(db_path)
    configure_connection(conn)
    with conn:
        try:
            if sid:
                rows = conn.execute(
                    """
                    SELECT fts.turn_id, fts.text_in, fts.text_out
                    FROM turns_fts fts
                    INNER JOIN turns t ON t.id = fts.turn_id
                    WHERE turns_fts MATCH ? AND t.speaker_id = ?
                    LIMIT ?
                    """,
                    (safe, sid, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT turn_id, text_in, text_out FROM turns_fts "
                    "WHERE turns_fts MATCH ? LIMIT ?",
                    (safe, limit),
                ).fetchall()
        except sqlite3.OperationalError:
            return []
    return rows
