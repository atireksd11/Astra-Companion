"""Drop old turn rows when store_audio_days is set."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from store.sqlutil import configure_connection


def _delete_fts(conn: sqlite3.Connection, turn_ids: list[str]) -> None:
    for turn_id in turn_ids:
        if not turn_id:
            continue
        conn.execute("DELETE FROM turns_fts WHERE turn_id = ?", (turn_id,))


def purge_old_turns(db_path: Path, *, keep_days: int) -> int:
    """Delete old turn rows and the full-text copies search still reads."""
    if keep_days <= 0 or not db_path.is_file():
        return 0
    cutoff = time.time() - keep_days * 86400
    conn = sqlite3.connect(db_path)
    configure_connection(conn)
    try:
        try:
            stale = [
                row[0]
                for row in conn.execute(
                    "SELECT id FROM turns WHERE created_at < ?",
                    (cutoff,),
                )
            ]
        except sqlite3.OperationalError:
            return 0
        try:
            live = {row[0] for row in conn.execute("SELECT id FROM turns")}
            indexed = [row[0] for row in conn.execute("SELECT turn_id FROM turns_fts")]
            orphans = [turn_id for turn_id in indexed if turn_id not in live]
            _delete_fts(conn, list(stale) + orphans)
        except sqlite3.OperationalError:
            pass
        cur = conn.execute("DELETE FROM turns WHERE created_at < ?", (cutoff,))
        conn.commit()
        return int(cur.rowcount or 0)
    finally:
        conn.close()
