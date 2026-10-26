"""Storage contract for Phase 5 (SQLite today; Postgres/Turso later).

TurnStore and ProfileStore are the live implementations. A remote adapter would
implement the same save/search methods and pass the tests in tests/test_memory_v2.py.
"""

from __future__ import annotations

from typing import Protocol

from core.turn import Turn


class TurnRepository(Protocol):
    def save_async(self, turn: Turn) -> None: ...

    def recent_text_pairs(self, limit: int, *, speaker_id: str | None = None): ...
