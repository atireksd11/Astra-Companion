"""Send one JPEG/PNG, then one WAV utterance, to test vision + pipeline."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import wave
from pathlib import Path

import websockets

CHUNK = 640
ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    for path in (ROOT.parent / ".env", ROOT / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


async def run(uri: str, image_path: Path, wav_path: Path, token: str) -> None:
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")

    with wave.open(str(wav_path), "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            raise SystemExit("WAV must be mono 16-bit PCM")
        rate = wf.getframerate()
        pcm = wf.readframes(wf.getnframes())

    hello: dict = {"type": "hello", "proto": 1, "fw": "vision-smoke"}
    if token:
        hello["token"] = token

    async with websockets.connect(uri, open_timeout=10) as ws:
        await ws.send(json.dumps(hello))
        print("hello:", await ws.recv())

        await ws.send(json.dumps({"type": "image", "mime": mime, "image_b64": b64}))
        print("image:", await ws.recv())

        await ws.send(
            json.dumps(
                {
                    "type": "start",
                    "rate": rate,
                    "meta": {"source": "vision_smoke", "vol": 0.2},
                }
            )
        )
        for i in range(0, len(pcm), CHUNK):
            await ws.send(pcm[i : i + CHUNK])
        await ws.send(json.dumps({"type": "end"}))

        while True:
            msg = await ws.recv()
            if isinstance(msg, str):
                obj = json.loads(msg)
                print("json:", json.dumps(obj, ensure_ascii=False)[:2000])
                if obj.get("type") == "done":
                    if obj.get("vision"):
                        print("vision:", obj["vision"])
                    print("reply:", obj.get("reply", ""))
                    break
                if obj.get("type") in ("error", "busy"):
                    raise SystemExit(obj)
            else:
                print("audio chunk:", len(msg), "bytes")


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser(description="Vision smoke test: image then WAV")
    ap.add_argument("image", type=Path, help="JPEG or PNG file")
    ap.add_argument(
        "wav",
        type=Path,
        nargs="?",
        default=ROOT / "tools" / "test-tone.wav",
        help="mono 16-bit PCM wav (default: tools/test-tone.wav)",
    )
    ap.add_argument("--uri", default="ws://127.0.0.1:8765")
    ap.add_argument(
        "--token",
        default=os.environ.get("ASTRA_CLIENT_TOKEN", "").strip(),
        help="hello token if bridge auth is on (or set ASTRA_CLIENT_TOKEN)",
    )
    args = ap.parse_args()
    if not args.image.is_file():
        raise SystemExit(f"image not found: {args.image}")
    if not args.wav.is_file():
        raise SystemExit(
            f"wav not found: {args.wav}\n"
            "create one:  python tools/make_test_wav.py tools/test-tone.wav"
        )
    asyncio.run(run(args.uri, args.image, args.wav, args.token))


if __name__ == "__main__":
    main()
