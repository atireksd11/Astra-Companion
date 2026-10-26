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


async def _once(uri: str, send, recv_timeout: float = 5.0):
    async with websockets.connect(uri, open_timeout=3) as ws:
        for item in send:
            if isinstance(item, bytes):
                await ws.send(item)
            else:
                await ws.send(json.dumps(item))
        out = []
        deadline = time.monotonic() + recv_timeout
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if isinstance(raw, str):
                out.append(json.loads(raw))
            else:
                out.append(raw)
            if out and isinstance(out[-1], dict) and out[-1].get("type") in (
                "done",
                "error",
            ):
                break
        return out


@pytest.fixture(scope="module")
def bridge_echo(tmp_path_factory):
    test_port = pick_free_port()
    cfg = tmp_path_factory.mktemp("p0") / "cfg.json"
    cfg.write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": test_port,
                "steps": ["echo"],
                "antispoof": {"enabled": False},
                "security": {"require_auth": False},
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
            err = proc.stderr.read().decode() if proc.stderr else ""
            pytest.fail(f"bridge died: {err}")
        try:
            asyncio.run(
                _once(uri, [{"type": "hello", "proto": 1}], recv_timeout=2.0)
            )
            break
        except Exception:
            time.sleep(0.15)
    else:
        proc.kill()
        pytest.fail("bridge did not start")
    yield uri
    proc.terminate()
    proc.wait(timeout=5)


def test_bad_json_returns_error(bridge_echo: str) -> None:
    async def run():
        async with websockets.connect(bridge_echo) as ws:
            await ws.send("{not json")
            raw = await asyncio.wait_for(ws.recv(), timeout=3)
            obj = json.loads(raw)
            assert obj["type"] == "error"
            assert obj["reason"] == "bad json"

    asyncio.run(run())


def test_bad_channels_clears_session(bridge_echo: str) -> None:
    async def run():
        async with websockets.connect(bridge_echo) as ws:
            await ws.send(json.dumps({"type": "hello", "proto": 1}))
            await ws.recv()
            await ws.send(
                json.dumps({"type": "start", "rate": 16000, "channels": 9})
            )
            err = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            assert err["reason"] == "bad channels"
            await ws.send(json.dumps({"type": "start", "rate": 16000}))
            await ws.send(json.dumps({"type": "end"}))
            follow: dict = {}
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=1)
                if isinstance(raw, str):
                    follow = json.loads(raw)
                    if follow.get("type") in ("done", "error"):
                        break
            assert follow.get("type") != "busy"

    asyncio.run(run())


def test_bad_rate_rejected(bridge_echo: str) -> None:
    msgs = asyncio.run(
        _once(
            bridge_echo,
            [
                {"type": "hello", "proto": 1},
                {"type": "start", "rate": 48000},
                {"type": "end"},
            ],
        )
    )
    err = next(m for m in msgs if m.get("type") == "error")
    assert err["reason"] == "bad rate"


def test_meta_speaker_id_stripped_before_echo(bridge_echo: str) -> None:
    from tools.make_test_wav import write_tone
    import wave

    wav = ROOT / "tools" / "_p0_tmp.wav"
    write_tone(wav, seconds=0.6, hz=440)
    with wave.open(str(wav), "rb") as wf:
        tone = wf.readframes(wf.getnframes())
    msgs = asyncio.run(
        _once(
            bridge_echo,
            [
                {"type": "hello", "proto": 1},
                {
                    "type": "start",
                    "rate": 16000,
                    "meta": {"speaker_id": "spk_attacker", "source": "test"},
                },
                tone,
                {"type": "end"},
            ],
            recv_timeout=8.0,
        )
    )
    done = next(
        (m for m in msgs if isinstance(m, dict) and m.get("type") == "done"),
        None,
    )
    errors = [
        m
        for m in msgs
        if isinstance(m, dict) and m.get("type") == "error"
    ]
    assert done is not None or any(e.get("reason") == "no speech" for e in errors)
