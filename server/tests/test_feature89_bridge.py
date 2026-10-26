from __future__ import annotations

import asyncio
import json
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


@pytest.fixture(scope="module")
def habits_bridge(tmp_path_factory):
    test_port = pick_free_port()
    cfg_path = tmp_path_factory.mktemp("cfg") / "habits.json"
    cfg_path.write_text(
        json.dumps(
            {
                "port": test_port,
                "steps": ["cadence", "echo"],
                "antispoof": {"enabled": False},
                "cadence": {"enabled": True},
                "pronunciation": {"enabled": True},
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.Popen(
        [sys.executable, "bridge.py", "--port", str(test_port), "--config", str(cfg_path)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
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
        pytest.fail("habits bridge failed to start")
    yield uri
    proc.terminate()
    proc.wait(timeout=5)


async def _ping(uri: str) -> None:
    async with websockets.connect(uri, open_timeout=2) as ws:
        await ws.send(json.dumps({"type": "hello", "proto": 1}))
        msg = json.loads(await ws.recv())
        assert msg.get("cadence", {}).get("enabled") is True


async def _send(uri: str, pcm: bytes) -> dict:
    async with websockets.connect(uri, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "hello", "proto": 1}))
        await ws.recv()
        await ws.send(json.dumps({"type": "start", "rate": 16000}))
        for i in range(0, len(pcm), CHUNK):
            await ws.send(pcm[i : i + CHUNK])
        await ws.send(json.dumps({"type": "end"}))
        out_len = 0
        last = {}
        while True:
            msg = await ws.recv()
            if isinstance(msg, str):
                last = json.loads(msg)
                if last.get("type") in ("done", "error"):
                    break
            else:
                out_len += len(msg)
        last["pcm_out_len"] = out_len
        return last


@pytest.mark.asyncio
async def test_cadence_on_done(habits_bridge: str, tmp_path: Path) -> None:
    wav = tmp_path / "long.wav"
    write_tone(wav, seconds=1.2)
    with wave.open(str(wav), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
    res = await _send(habits_bridge, pcm)
    assert res.get("type") == "done", res.get("reason")
    assert "cadence" in res
    assert res.get("pcm_out_len") == len(pcm)
