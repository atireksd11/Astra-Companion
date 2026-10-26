from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from store.sqlutil import configure_connection


class Meter:
    def __init__(self, db_path: Path, daily_cap_usd: float) -> None:
        self.db_path = db_path
        self.daily_cap_usd = daily_cap_usd
        self._lock = threading.Lock()
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        configure_connection(conn)
        return conn

    def _ensure_table(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS daily_cost (
                        day TEXT PRIMARY KEY,
                        usd REAL NOT NULL DEFAULT 0
                    )
                    """
                )

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def try_reserve(self, amount_usd: float) -> bool:
        if amount_usd <= 0:
            return True
        day = self._today()
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT usd FROM daily_cost WHERE day = ?", (day,)
                ).fetchone()
                current = float(row[0]) if row else 0.0
                if current + amount_usd > self.daily_cap_usd:
                    conn.execute("ROLLBACK")
                    return False
                conn.execute(
                    "INSERT INTO daily_cost(day, usd) VALUES (?, ?) "
                    "ON CONFLICT(day) DO UPDATE SET usd = usd + excluded.usd",
                    (day, amount_usd),
                )
                conn.commit()
        return True

    def settle(self, reserved_usd: float, actual_usd: float) -> None:
        """Adjust daily total after a turn: usd += (actual - reserved)."""
        delta = actual_usd - reserved_usd
        if delta == 0:
            return
        day = self._today()
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT usd FROM daily_cost WHERE day = ?", (day,)
                ).fetchone()
                if row:
                    new_usd = max(0.0, float(row[0]) + delta)
                    conn.execute(
                        "UPDATE daily_cost SET usd = ? WHERE day = ?",
                        (new_usd, day),
                    )
                else:
                    conn.execute(
                        "INSERT INTO daily_cost(day, usd) VALUES (?, ?)",
                        (day, max(0.0, actual_usd)),
                    )
                conn.commit()

    def today_usd(self) -> float:
        day = self._today()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT usd FROM daily_cost WHERE day = ?", (day,)
                ).fetchone()
        return float(row[0]) if row else 0.0

    def over_cap(self) -> bool:
        return self.today_usd() >= self.daily_cap_usd
