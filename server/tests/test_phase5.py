from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from unittest.mock import patch

from core.config import VisionConfig
from core.health_http import serve_health  # noqa: E402
from core.robot_actions import plan_actions, with_ids  # noqa: E402
from core.turn import Turn  # noqa: E402
from providers.vision import VisionResult
from steps.vision import make_vision_step
from store.action_log import ActionLog  # noqa: E402


async def _fetch_health(port: int) -> dict:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    raw = await reader.read(4096)
    writer.close()
    await writer.wait_closed()
    body = raw.split(b"\r\n\r\n", 1)[-1]
    return json.loads(body.decode("utf-8"))


async def _fetch_raw(port: int, path: str) -> tuple[int, bytes]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    raw = await reader.read(4096)
    writer.close()
    await writer.wait_closed()
    status = int(raw.split(b" ", 2)[1])
    body = raw.split(b"\r\n\r\n", 1)[-1]
    return status, body


def test_health_endpoint() -> None:
    port = 9877

    async def run() -> None:
        server = await serve_health("127.0.0.1", port, {"ok": True, "service": "test"})
        try:
            data = await _fetch_health(port)
            assert data["ok"] is True
            assert data["service"] == "test"
            status, body = await _fetch_raw(port, "/healthcare")
            assert status == 404
            assert body == b""
            status_z, _body_z = await _fetch_raw(port, "/healthz")
            assert status_z == 404
            query_status, query_body = await _fetch_raw(port, "/health?x=1")
            assert query_status == 200
            assert json.loads(query_body.decode("utf-8"))["ok"] is True
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_action_log_idempotent(tmp_path: Path) -> None:
    log = ActionLog(tmp_path / "a.db")
    assert log.claim("t1:stop_playback", turn_id="t1", action_name="stop_playback")
    assert not log.claim("t1:stop_playback", turn_id="t1", action_name="stop_playback")


def test_vision_step_in_known_steps() -> None:
    from core.config_validate import KNOWN_STEPS, validate_step_contract

    steps = [
        "antispoof",
        "denoise",
        "focus",
        "stt",
        "vision",
        "safety_in",
        "mood",
        "cadence",
        "pronunciation",
        "context_retrieve",
        "research",
        "llm",
        "intent",
        "safety_out",
        "memory_persist",
        "tts",
    ]
    assert "vision" in KNOWN_STEPS
    validate_step_contract(steps)


def test_robot_actions_require_owner() -> None:
    turn = Turn()
    turn.notes["intent"] = "stop"
    assert plan_actions(turn, require_owner=True) == []
    turn.notes["focus"] = {"verified": True}
    actions = with_ids(turn, plan_actions(turn, require_owner=True))
    assert actions[0]["name"] == "stop_playback"
    assert actions[0]["id"] == f"{turn.id}:stop_playback"


def test_vision_step_uses_describe_image() -> None:
    turn = Turn()
    turn.notes["vision_image"] = {"bytes": b"\xff\xd8\xff", "mime": "image/jpeg"}
    cfg = VisionConfig(enabled=True, max_bytes=10_000)
    step = make_vision_step(cfg)
    fake = VisionResult(True, "a red cup on a desk", "groq")
    with patch("steps.vision.vision_provider.describe_image", return_value=fake) as mock:
        step(turn)
        mock.assert_called_once()
    assert turn.notes["vision"]["ok"] is True
    assert turn.notes["vision"]["caption"] == "a red cup on a desk"


def test_vision_step_rejects_bad_image_bytes() -> None:
    turn = Turn()
    turn.notes["vision_image"] = {"bytes": b"this is not a jpeg", "mime": "image/jpeg"}
    cfg = VisionConfig(enabled=True, max_bytes=10_000)
    step = make_vision_step(cfg)
    with patch("steps.vision.vision_provider.describe_image") as mock:
        step(turn)
        mock.assert_not_called()
    assert turn.error is None
    assert turn.notes["vision"]["ok"] is False
    assert turn.notes["vision"]["detail"] == "bad_image"


def test_retention_purges_search_text(tmp_path: Path) -> None:
    import time

    from store.db import TurnStore
    from store.memory import search_turns
    from store.retention import purge_old_turns

    db = tmp_path / "retain.db"
    store = TurnStore(db)
    old = Turn()
    old.text_in = "secret old passphrase"
    old.text_out = "kept secret"
    old.created_at = time.time() - 10 * 86400
    store._save(old)
    fresh = Turn()
    fresh.text_in = "hello today"
    fresh.text_out = "hi"
    store._save(fresh)

    assert search_turns(db, "secret passphrase")
    removed = purge_old_turns(db, keep_days=7)
    assert removed == 1
    assert search_turns(db, "secret passphrase") == []
    kept = search_turns(db, "hello today")
    assert kept and kept[0][0] == fresh.id

    # A previous purge that deleted the row but left the index must not linger.
    leaked = Turn()
    leaked.text_in = "orphan secret phrase"
    leaked.text_out = "still indexed"
    leaked.created_at = time.time() - 10 * 86400
    store._save(leaked)
    import sqlite3

    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM turns WHERE id = ?", (leaked.id,))
    conn.commit()
    conn.close()
    assert search_turns(db, "orphan secret")
    purge_old_turns(db, keep_days=7)
    assert search_turns(db, "orphan secret") == []


def test_owner_followup_plans_stop(tmp_path: Path) -> None:
    from core.config import DenoiseConfig, FocusConfig
    from core.focus import FocusSession
    from steps.focus import make_focus_step
    from store.profiles import ProfileStore
    from tests.test_focus import SR, _patch_ecapa, _tone

    session = FocusSession()
    profiles = ProfileStore(tmp_path / "focus.db")
    step = make_focus_step(
        FocusConfig(
            enabled=True,
            min_similarity=0.40,
            lock_owner=False,
            mask_other_voices=False,
            require_owner_enroll=False,
        ),
        session,
        profiles,
        DenoiseConfig(enabled=False),
    )
    with _patch_ecapa():
        session.on_wake(
            _tone(200, 3.2),
            rate=SR,
            azimuth_deg=None,
            speech_ms=3200,
            min_enroll_ms=3000,
        )
        turn = Turn(rate_hz=SR)
        turn.pcm_in = bytearray(_tone(200, 1.5))
        turn.notes["channels"] = 1
        turn.notes["meta"] = {"vol": 0.2}
        turn.notes["intent"] = "stop"
        step(turn)
    assert turn.error is None
    assert turn.notes["focus"]["verified"] is True
    actions = plan_actions(turn, require_owner=True)
    assert actions[0]["name"] == "stop_playback"


def test_duplicate_done_actions_filtered(tmp_path: Path) -> None:
    log = ActionLog(tmp_path / "dup.db")
    turn_id = "turn-a"
    planned = [{"id": f"{turn_id}:stop_playback", "name": "stop_playback"}]

    def claim(action: dict) -> bool:
        return log.claim(
            str(action["id"]),
            turn_id=turn_id,
            action_name=str(action["name"]),
        )

    first = [a for a in planned if claim(a)]
    second = [a for a in planned if claim(a)]
    assert len(first) == 1
    assert len(second) == 0
