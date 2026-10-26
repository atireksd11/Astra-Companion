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
from tests.fixtures.stereo_pcm import stereo_pcm_with_right_delay  # noqa: E402

CHUNK = 640


@pytest.fixture(scope="module")
def bridge_proc(tmp_path_factory):
    test_port = pick_free_port()
    cfg_path = tmp_path_factory.mktemp("cfg") / "echo_only.json"
    cfg_path.write_text(
        json.dumps(
            {
                "port": test_port,
                "steps": ["echo"],
                "antispoof": {"enabled": False},
                "denoise": {"enabled": False},
                "focus": {"enabled": False},
                "cadence": {"enabled": False},
                "pronunciation": {"enabled": False},
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
    for _ in range(30):
        if proc.poll() is not None:
            err = proc.stderr.read().decode() if proc.stderr else ""
            pytest.fail(f"bridge exited during startup: {err}")
        try:
            asyncio.run(_ping(uri))
            break
        except OSError:
            time.sleep(0.2)
    else:
        proc.kill()
        err = proc.stderr.read().decode() if proc.stderr else ""
        pytest.fail(f"bridge did not start: {err}")
    yield proc, uri
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@pytest.fixture(scope="module")
def bridge_uri(bridge_proc) -> str:
    _proc, uri = bridge_proc
    return uri


@pytest.fixture(autouse=True)
def _bridge_alive(bridge_proc) -> None:
    proc, _uri = bridge_proc
    if proc.poll() is not None:
        err = proc.stderr.read().decode() if proc.stderr else ""
        pytest.fail(f"bridge process died: {err}")


async def _ping(uri: str) -> None:
    async with websockets.connect(uri, open_timeout=2) as ws:
        await ws.send(json.dumps({"type": "hello", "proto": 1}))
        await ws.recv()


async def _send_pcm(
    uri: str,
    pcm: bytes,
    rate: int = 16000,
    meta: dict | None = None,
    channels: int | None = None,
) -> dict:
    async with websockets.connect(uri, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "hello", "proto": 1}))
        await ws.recv()
        start = {"type": "start", "rate": rate}
        if channels is not None:
            start["channels"] = channels
        if meta is not None:
            start["meta"] = meta
        await ws.send(json.dumps(start))
        for i in range(0, len(pcm), CHUNK):
            await ws.send(pcm[i : i + CHUNK])
        await ws.send(json.dumps({"type": "end"}))
        out = bytearray()
        last_json = {}
        while True:
            msg = await ws.recv()
            if isinstance(msg, str):
                last_json = json.loads(msg)
                if last_json.get("type") == "done":
                    break
                if last_json.get("type") == "error":
                    return last_json
            else:
                out.extend(msg)
        last_json["pcm_out_len"] = len(out)
        return last_json


def _read_wav_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as wf:
        return wf.readframes(wf.getnframes())


@pytest.mark.asyncio
async def test_hello_limits(bridge_uri: str) -> None:
    async with websockets.connect(bridge_uri) as ws:
        await ws.send(json.dumps({"type": "hello", "proto": 1}))
        msg = json.loads(await ws.recv())
        lim = msg["limits"]
        assert lim["max_clip_s"] == 60
        assert "min_clip_s" in lim
        assert lim["end_silence_ms"] == 2000
        assert lim["pause_hold_ms"] == 2000


@pytest.mark.asyncio
async def test_echo_ok(bridge_uri: str, tmp_path: Path) -> None:
    wav = tmp_path / "one.wav"
    write_tone(wav, seconds=1.0)
    pcm = _read_wav_pcm(wav)
    res = await _send_pcm(bridge_uri, pcm)
    assert res.get("type") == "done"
    assert res["pcm_out_len"] == len(pcm)


@pytest.mark.asyncio
async def test_too_short(bridge_uri: str) -> None:
    pcm = b"\x00\x00" * 8000
    res = await _send_pcm(bridge_uri, pcm)
    assert res.get("type") == "error"
    assert res.get("reason") in ("too short", "empty", "no speech")


@pytest.mark.asyncio
async def test_too_long(bridge_uri: str, tmp_path: Path) -> None:
    wav = tmp_path / "long.wav"
    write_tone(wav, seconds=65.0)
    pcm = _read_wav_pcm(wav)
    res = await _send_pcm(bridge_uri, pcm)
    assert res.get("type") == "error"
    assert res.get("reason") == "too long"


@pytest.mark.asyncio
async def test_mono_regression_with_feature3_meta(bridge_uri: str, tmp_path: Path) -> None:
    """Mono echo path unchanged when optional stereo/DOA meta is present."""
    wav = tmp_path / "mono_meta.wav"
    write_tone(wav, seconds=1.0)
    pcm = _read_wav_pcm(wav)
    meta = {
        "noise": 100,
        "level": 900,
        "vol": 0.2,
        "channels": 1,
        "doa_deg": None,
    }
    res = await _send_pcm(bridge_uri, pcm, meta=meta)
    assert res.get("type") == "done"
    assert res["pcm_out_len"] == len(pcm)


@pytest.mark.asyncio
async def test_stereo_echo_downmix(bridge_uri: str, tmp_path: Path) -> None:
    wav = tmp_path / "mono_for_stereo.wav"
    write_tone(wav, seconds=1.0)
    mono = _read_wav_pcm(wav)
    stereo = stereo_pcm_with_right_delay(mono, 3)
    res = await _send_pcm(bridge_uri, stereo, channels=2, meta={"channels": 2})
    assert res.get("type") == "done"
    assert res["pcm_out_len"] == len(mono)
    assert "aim" in res


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_noise_only_rejected(bridge_uri: str) -> None:
    """Mostly silence with no sustained speech → no echo."""
    pcm = b"\x00\x00" * 16000 + b"\x00\x10" * 4000 + b"\x00\x00" * 12000
    res = await _send_pcm(bridge_uri, pcm)
    assert res.get("type") == "error"
    assert res.get("reason") in ("no speech", "too short", "empty")


@pytest.mark.asyncio
async def test_done_includes_utterance_stats(bridge_uri: str, tmp_path: Path) -> None:
    wav = tmp_path / "utt.wav"
    write_tone(wav, seconds=1.0)
    pcm = _read_wav_pcm(wav)
    res = await _send_pcm(bridge_uri, pcm)
    assert res.get("type") == "done"
    utt = res.get("utterance") or {}
    assert utt.get("speech_s", 0) >= 0.4
    assert "vad_backend" in utt


@pytest.mark.asyncio
async def test_empty_end(bridge_uri: str) -> None:
    async with websockets.connect(bridge_uri) as ws:
        await ws.send(json.dumps({"type": "hello", "proto": 1}))
        await ws.recv()
        await ws.send(json.dumps({"type": "start", "rate": 16000}))
        await ws.send(json.dumps({"type": "end"}))
        msg: dict = {}
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("type") in ("done", "error"):
                break
        assert msg.get("reason") in ("empty", "too short")
