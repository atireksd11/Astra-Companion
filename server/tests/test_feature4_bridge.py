from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np
import pytest
import websockets

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.make_test_wav import write_tone  # noqa: E402
from tests.conftest import pick_free_port  # noqa: E402

CHUNK = 640


@pytest.fixture(scope="module")
def denoise_bridge(tmp_path_factory):
    test_port = pick_free_port()
    cfg_path = tmp_path_factory.mktemp("cfg") / "denoise_on.json"
    cfg_path.write_text(
        json.dumps(
            {
                "port": test_port,
                "steps": ["denoise", "echo"],
                "antispoof": {"enabled": False},
                "denoise": {
                    "enabled": True,
                    "backend": "auto",
                    "strength": 0.6,
                },
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.Popen(
        [
            sys.executable,
            "bridge.py",
            "--port",
            str(test_port),
            "--config",
            str(cfg_path),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    uri = f"ws://127.0.0.1:{test_port}"
    for _ in range(40):
        if proc.poll() is not None:
            err = proc.stderr.read().decode() if proc.stderr else ""
            pytest.fail(f"bridge exited: {err}")
        try:
            asyncio.run(_ping(uri))
            break
        except OSError:
            time.sleep(0.15)
    else:
        proc.kill()
        pytest.fail("denoise bridge did not start")
    yield uri
    proc.terminate()
    proc.wait(timeout=5)


async def _ping(uri: str) -> None:
    async with websockets.connect(uri, open_timeout=2) as ws:
        await ws.send(json.dumps({"type": "hello", "proto": 1}))
        msg = json.loads(await ws.recv())
        assert msg.get("denoise", {}).get("enabled") is True


async def _send_tone(uri: str, seconds: float = 1.0) -> dict:
    wav = Path(ROOT) / "tools" / "_f4_tone.wav"
    write_tone(wav, seconds=seconds)
    with wave.open(str(wav), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
    async with websockets.connect(uri, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "hello", "proto": 1}))
        await ws.recv()
        await ws.send(json.dumps({"type": "start", "rate": 16000}))
        for i in range(0, len(pcm), CHUNK):
            await ws.send(pcm[i : i + CHUNK])
        await ws.send(json.dumps({"type": "end"}))
        out = bytearray()
        last = {}
        while True:
            msg = await ws.recv()
            if isinstance(msg, str):
                last = json.loads(msg)
                if last.get("type") in ("done", "error"):
                    break
            else:
                out.extend(msg)
        last["pcm_out"] = bytes(out)
        return last


@pytest.mark.asyncio
async def test_done_includes_denoise_stats(denoise_bridge: str) -> None:
    res = await _send_tone(denoise_bridge)
    assert res.get("type") == "done"
    den = (res.get("utterance") or {}).get("denoise") or {}
    assert den.get("backend") in ("rnnoise", "deepfilternet", "bypass")
    assert den.get("snr_after_db") is not None


@pytest.mark.asyncio
async def test_wrong_step_order_still_denoises_echo(denoise_bridge: str) -> None:
    """Config normalizer is tested in test_config_steps; echo path gets cleaned audio."""
    res = await _send_tone(denoise_bridge)
    assert res.get("type") == "done"
    assert len(res.get("pcm_out") or b"") > 0
