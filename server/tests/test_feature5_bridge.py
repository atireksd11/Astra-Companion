from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

import pytest
import websockets

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.make_test_wav import write_tone  # noqa: E402
from tests.conftest import pick_free_port  # noqa: E402

CHUNK = 640


def _tone_pcm(hz: float = 440, seconds: float = 1.0) -> bytes:
    wav = Path(ROOT) / "tools" / "_f5_tmp.wav"
    write_tone(wav, seconds=seconds, hz=hz)
    with wave.open(str(wav), "rb") as wf:
        return wf.readframes(wf.getnframes())


@pytest.fixture(scope="module")
def focus_bridge(tmp_path_factory):
    test_port = pick_free_port()
    cfg_path = tmp_path_factory.mktemp("cfg") / "focus.json"
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    cfg_path.write_text(
        json.dumps(
            {
                "port": test_port,
                "steps": ["focus", "echo"],
                "antispoof": {"enabled": False},
                "focus": {
                    "enabled": True,
                    "min_similarity": 0.65,
                    "lock_owner": False,
                    "mask_other_voices": False,
                    "require_owner_enroll": False,
                },
            }
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "ASTRA_DB": str(db_path)}
    proc = subprocess.Popen(
        [sys.executable, "bridge.py", "--port", str(test_port), "--config", str(cfg_path)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=env,
    )
    uri = f"ws://127.0.0.1:{test_port}"
    for _ in range(40):
        if proc.poll() is not None:
            pytest.fail(proc.stderr.read().decode() if proc.stderr else "exit")
        try:
            asyncio.run(_ping(uri))
            break
        except OSError:
            time.sleep(0.15)
    else:
        proc.kill()
        pytest.fail("focus bridge failed to start")
    yield uri
    proc.terminate()
    proc.wait(timeout=5)


async def _ping(uri: str) -> None:
    async with websockets.connect(uri, open_timeout=2) as ws:
        await ws.send(json.dumps({"type": "hello", "proto": 1}))
        msg = json.loads(await ws.recv())
        assert msg.get("focus", {}).get("enabled") is True


async def _send(uri: str, pcm: bytes, meta: dict) -> dict:
    async with websockets.connect(uri, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "hello", "proto": 1}))
        await ws.recv()
        await ws.send(
            json.dumps({"type": "start", "rate": 16000, "meta": meta})
        )
        for i in range(0, len(pcm), CHUNK):
            await ws.send(pcm[i : i + CHUNK])
        await ws.send(json.dumps({"type": "end"}))
        last = {}
        while True:
            msg = await ws.recv()
            if isinstance(msg, str):
                last = json.loads(msg)
                if last.get("type") in ("done", "error"):
                    break
        return last


@pytest.mark.asyncio
async def test_asleep_rejected(focus_bridge: str) -> None:
    pcm = _tone_pcm()
    res = await _send(focus_bridge, pcm, {})
    assert res.get("type") == "error"
    assert res.get("reason") == "asleep"


@pytest.mark.asyncio
async def test_wake_then_echo(focus_bridge: str) -> None:
    enroll = _tone_pcm(hz=220, seconds=3.2)
    body = _tone_pcm(hz=220, seconds=1.0)
    pcm = enroll + body
    meta = {
        "wake": True,
        "enroll_b64": base64.b64encode(enroll).decode("ascii"),
        "enroll_speech_ms": 3200,
        "vol": 0.2,
    }
    res = await _send(focus_bridge, pcm, meta)
    assert res.get("type") == "done", res.get("reason")
    assert res.get("focus", {}).get("match") is not None
    assert res.get("volume", {}).get("gain") is not None
