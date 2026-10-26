"""Shared SQLite pragmas."""

from __future__ import annotations

import sqlite3


def configure_connection(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
