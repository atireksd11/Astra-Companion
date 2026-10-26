from __future__ import annotations

import asyncio
import json
import sys
import wave
from pathlib import Path

import websockets

CHUNK = 640


async def send_wav(uri: str, wav_path: Path) -> None:
    with wave.open(str(wav_path), "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            raise SystemExit("WAV must be mono 16-bit PCM")
        rate = wf.getframerate()
        pcm = wf.readframes(wf.getnframes())

    try:
        async with websockets.connect(uri, open_timeout=5) as ws:
            await ws.send(json.dumps({"type": "hello", "proto": 1, "fw": "sim"}))
            hello = json.loads(await ws.recv())
            print("hello:", hello)
            await ws.send(
                json.dumps(
                    {
                        "type": "start",
                        "rate": rate,
                        "meta": {"noise": 100, "level": 900, "vol": 0.2},
                    }
                )
            )
            for i in range(0, len(pcm), CHUNK):
                await ws.send(pcm[i : i + CHUNK])
            await ws.send(json.dumps({"type": "end"}))

            out = bytearray()
            while True:
                msg = await ws.recv()
                if isinstance(msg, str):
                    obj = json.loads(msg)
                    print("json:", obj)
                    if obj.get("type") == "done":
                        break
                    if obj.get("type") in ("error", "busy"):
                        raise SystemExit(obj)
                else:
                    out.extend(msg)
    except (OSError, TimeoutError, ConnectionRefusedError) as exc:
        raise SystemExit(
            f"cannot connect to {uri}\n"
            "Start the bridge first:  python bridge.py\n"
            f"Details: {exc}"
        ) from exc

    out_path = wav_path.with_name(wav_path.stem + "-echo.wav")
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(out)
    print("wrote", out_path, len(out), "bytes")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "usage: python tools/sim_robot.py clip.wav [ws://host:8765]\n"
            "  create a test file: python tools/make_test_wav.py tools/test-tone.wav"
        )
    wav_path = Path(sys.argv[1])
    if not wav_path.is_file():
        raise SystemExit(
            f"file not found: {wav_path}\n"
            "run: python tools/make_test_wav.py tools/test-tone.wav"
        )
    uri = sys.argv[2] if len(sys.argv) > 2 else "ws://127.0.0.1:8765"
    asyncio.run(send_wav(uri, wav_path))


if __name__ == "__main__":
    main()
