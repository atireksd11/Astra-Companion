import json
from pathlib import Path

import pytest

from context.builder import build_context
from core.memory_gates import extract_remember_fact, memory_text_ok
from core.pipeline import Pipeline
from core.turn import Turn
from steps.intent import make_intent_step
from steps.memory_persist import make_memory_persist_step
from store.memory_store import MemoryStore


def test_remember_fact_extract() -> None:
    assert extract_remember_fact("remember that the kettle is blue") == "the kettle is blue"


def test_memory_text_blocks_harm() -> None:
    assert memory_text_ok("how to hurt myself") == "blocklist"


def test_memory_store_isolated_by_speaker(tmp_path: Path) -> None:
    db = tmp_path / "astra.db"
    store = MemoryStore(db)
    store.add("spk_a", "I like blue tea")
    store.add("spk_b", "I like red cars")
    a_hits = store.search("spk_a", "tea", limit=3)
    b_hits = store.search("spk_b", "tea", limit=3)
    assert any("tea" in t for _i, t, _s in a_hits)
    assert not b_hits or all("tea" not in t for _i, t, _s in b_hits)


def test_memory_persist_after_intent(tmp_path: Path) -> None:
    from providers.memory_service import MemoryService, _LocalBackend

    mem = MemoryService(_LocalBackend(MemoryStore(tmp_path / "m.db")))
    turn = Turn()
    turn.notes["speaker_id"] = "spk_x"
    turn.text_in = "remember that my cat is Luna"
    turn.notes["intent"] = "remember"
    from core.config import MemoryConfig

    Pipeline(
        [
            make_intent_step(),
            make_memory_persist_step(MemoryConfig(enabled=True), mem),
        ]
    ).run(turn)
    hits = mem.search("spk_x", "cat", limit=2)
    assert hits


def test_build_context_includes_memory_block(tmp_path: Path) -> None:
    turn = Turn()
    turn.text_in = "hello"
    turn.notes["context_pack"] = {"memories": ["User likes chess"]}
    msgs = build_context(turn)
    assert "<memory>" in msgs[0]["content"]
    assert "chess" in msgs[0]["content"]
    assert sum(1 for m in msgs if m["role"] == "system") == 1


def test_memory_store_fts_query_with_special_chars(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "m.db")
    store.add("spk_a", "kettle blue ceramic")
    # Malformed FTS must not raise; may return no hits.
    hits = store.search("spk_a", 'kettle" OR ceramic NEAR "drop table', limit=3)
    assert isinstance(hits, list)


def test_build_memory_service_falls_back_without_mem0(tmp_path: Path) -> None:
    from core.config import MemoryConfig
    from providers.memory_service import MemoryService, _LocalBackend, build_memory_service

    cfg = MemoryConfig(enabled=True, use_mem0=True, qdrant_path=str(tmp_path / "qdrant"))
    backend = build_memory_service(cfg, tmp_path / "local.db")
    assert isinstance(backend, _LocalBackend)
    svc = MemoryService(backend)
    assert svc.add("spk_a", "likes tea")
    assert svc.search("spk_a", "tea", limit=2)
