from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
import websockets

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.conftest import pick_free_port  # noqa: E402


@pytest.fixture(scope="module")
def auth_bridge(tmp_path_factory):
    test_port = pick_free_port()
    cfg = tmp_path_factory.mktemp("auth") / "cfg.json"
    cfg.write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": test_port,
                "steps": ["echo"],
                "antispoof": {"enabled": False},
                "security": {
                    "auth_token": "test-secret-token",
                    "require_auth": True,
                },
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.Popen(
        [sys.executable, "bridge.py", "--port", str(test_port), "--config", str(cfg)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    uri = f"ws://127.0.0.1:{test_port}"
    for _ in range(40):
        if proc.poll() is not None:
            pytest.fail(proc.stderr.read().decode() if proc.stderr else "exit")
        try:
            asyncio.run(
                _hello(
                    uri,
                    token="test-secret-token",
                    expect_auth_fail=False,
                    skip_start=True,
                )
            )
            break
        except Exception:
            time.sleep(0.15)
    else:
        proc.kill()
        pytest.fail("auth bridge did not start")
    yield uri
    proc.terminate()
    proc.wait(timeout=5)


async def _hello(
    uri: str,
    *,
    token: str | None,
    expect_auth_fail: bool,
    skip_start: bool = False,
) -> dict:
    async with websockets.connect(uri, open_timeout=3) as ws:
        msg = {"type": "hello", "proto": 1}
        if token:
            msg["token"] = token
        await ws.send(json.dumps(msg))
        raw = await asyncio.wait_for(ws.recv(), timeout=3)
        obj = json.loads(raw)
        if expect_auth_fail:
            assert obj.get("type") == "error"
            assert obj.get("reason") == "auth"
            return obj
        assert obj.get("type") == "hello"
        if not skip_start:
            await ws.send(json.dumps({"type": "start", "rate": 16000}))
            raw2 = await asyncio.wait_for(ws.recv(), timeout=3)
            obj2 = json.loads(raw2)
            return obj2
        return obj


def test_auth_rejects_bad_token(auth_bridge: str) -> None:
    asyncio.run(
        _hello(auth_bridge, token="wrong", expect_auth_fail=True)
    )


def test_auth_start_blocked_without_hello_token(auth_bridge: str) -> None:
    async def run():
        async with websockets.connect(auth_bridge) as ws:
            await ws.send(json.dumps({"type": "hello", "proto": 1}))
            await ws.recv()
            await ws.send(json.dumps({"type": "start", "rate": 16000}))
            obj = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            assert obj.get("reason") == "auth"

    asyncio.run(run())


def test_auth_good_token_allows_start(auth_bridge: str) -> None:
    async def run():
        obj = await _hello(
            auth_bridge, token="test-secret-token", expect_auth_fail=False
        )
        assert obj.get("type") != "error"

    asyncio.run(run())
