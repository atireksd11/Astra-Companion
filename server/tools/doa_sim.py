"""Test GCC-PHAT direction on a stereo WAV or a synthetic delayed pair."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import struct
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.doa import (  # noqa: E402
    DEFAULT_BASELINE_M,
    estimate_azimuth_deg,
    split_stereo_interleaved,
)

CHUNK_BYTES = 640
WS_URI_DEFAULT = "ws://127.0.0.1:8765"


def _write_stereo_wav(
    path: Path,
    rate: int,
    seconds: float,
    hz: float,
    delay_samples: int,
    baseline_m: float,
) -> float:
    n = int(rate * seconds)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            t = i / rate
            sample = int(7000 * math.sin(2 * math.pi * hz * t))
            j = max(0, i - delay_samples)
            t_r = j / rate
            sample_r = int(7000 * math.sin(2 * math.pi * hz * t_r))
            frames.extend(struct.pack("<hh", sample, sample_r))
        wf.writeframes(frames)
    tau_s = delay_samples / rate
    expected = math.degrees(
        math.asin(max(-1.0, min(1.0, 343.0 * tau_s / baseline_m)))
    )
    print(f"wrote {path} (expected azimuth ~ {expected:.1f}°)")
    return expected


def _read_pcm(path: Path) -> tuple[bytes, int, int]:
    with wave.open(str(path), "rb") as wf:
        ch = wf.getnchannels()
        rate = wf.getframerate()
        if wf.getsampwidth() != 2:
            raise SystemExit("only 16-bit PCM WAV supported")
        pcm = wf.readframes(wf.getnframes())
    if ch == 1:
        raise SystemExit("WAV is mono; use --synthetic or a stereo file")
    if ch != 2:
        raise SystemExit(f"expected 1 or 2 channels, got {ch}")
    return pcm, rate, ch


def angle_to_delay_samples(angle_deg: float, rate: int, baseline_m: float) -> int:
    """Positive angle = source to the right → right mic delayed."""
    rad = math.radians(angle_deg)
    tau_s = (baseline_m / 343.0) * math.sin(rad)
    return int(round(tau_s * rate))


async def send_stereo_to_bridge(uri: str, pcm: bytes, rate: int) -> dict:
    import websockets

    async with websockets.connect(uri, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "hello", "proto": 1, "fw": "doa_sim"}))
        await ws.recv()
        await ws.send(
            json.dumps(
                {
                    "type": "start",
                    "rate": rate,
                    "channels": 2,
                    "meta": {"channels": 2, "source": "doa_sim"},
                }
            )
        )
        for i in range(0, len(pcm), CHUNK_BYTES):
            await ws.send(pcm[i : i + CHUNK_BYTES])
        await ws.send(json.dumps({"type": "end"}))

        done: dict = {"type": "done"}
        while True:
            msg = await ws.recv()
            if isinstance(msg, str):
                obj = json.loads(msg)
                if obj.get("type") == "done":
                    done = obj
                    break
                if obj.get("type") in ("error", "busy"):
                    raise SystemExit(f"bridge: {obj}")
            # ignore echo binary chunks
    return done


def _print_bridge_result(done: dict, expected_deg: float | None) -> None:
    print("bridge done:", json.dumps(done, indent=2))
    aim = done.get("aim")
    if not aim:
        print(
            "No aim in response (confidence too low or clip too short). "
            "Check bridge terminal for doa: lines."
        )
        return
    az = aim.get("azimuth_deg")
    conf = aim.get("confidence", 0)
    print(f"Bridge thinks source is at azimuth_deg={az} (confidence={conf:.3f})")
    if expected_deg is not None and az is not None:
        err = abs(float(az) - expected_deg)
        print(f"Expected ~{expected_deg:.1f}° — error {err:.1f}°")


def main() -> None:
    p = argparse.ArgumentParser(
        description="DOA GCC-PHAT simulator (local math and/or full bridge test)"
    )
    p.add_argument("wav", nargs="?", type=Path, help="stereo WAV path")
    p.add_argument("--baseline-m", type=float, default=DEFAULT_BASELINE_M)
    p.add_argument(
        "--synthetic",
        action="store_true",
        help="generate a test stereo WAV with known inter-channel delay",
    )
    p.add_argument("--out", type=Path, default=Path(__file__).parent / "doa-test.wav")
    p.add_argument("--rate", type=int, default=16000)
    p.add_argument("--seconds", type=float, default=1.0)
    p.add_argument("--hz", type=float, default=440.0)
    p.add_argument(
        "--delay-us",
        type=float,
        default=None,
        help="right channel delay vs left (microseconds)",
    )
    p.add_argument(
        "--angle",
        type=float,
        default=None,
        help="synthetic source angle in degrees (+ = right); sets delay from baseline",
    )
    p.add_argument(
        "--bridge",
        action="store_true",
        help="send stereo clip through bridge.py and print aim in done JSON",
    )
    p.add_argument("--uri", default=WS_URI_DEFAULT)
    args = p.parse_args()

    expected_deg: float | None = None

    if args.synthetic:
        if args.angle is not None:
            delay_samples = angle_to_delay_samples(
                args.angle, args.rate, args.baseline_m
            )
        elif args.delay_us is not None:
            delay_samples = int(args.rate * args.delay_us / 1_000_000)
        else:
            delay_samples = int(args.rate * 120.0 / 1_000_000)
        expected_deg = _write_stereo_wav(
            args.out, args.rate, args.seconds, args.hz, delay_samples, args.baseline_m
        )
        pcm, rate, _ = _read_pcm(args.out)
    elif args.wav:
        pcm, rate, _ = _read_pcm(args.wav)
    else:
        p.error("provide a stereo wav path or --synthetic")

    left, right = split_stereo_interleaved(pcm)
    angle, conf = estimate_azimuth_deg(left, right, rate, baseline_m=args.baseline_m)
    print(
        f"local estimate: azimuth_deg={angle:.2f} confidence={conf:.3f} "
        f"rate={rate} baseline_m={args.baseline_m}"
    )

    if args.bridge:
        print(
            "\n=== SYNTHETIC LAB TEST ===\n"
            "This sends a fake stereo tone through the bridge.\n"
            "It does NOT use your room microphone.\n"
            "For real voice + echo, use:  python laptop_voice.py\n"
            "================================\n"
        )
        try:
            done = asyncio.run(send_stereo_to_bridge(args.uri, pcm, rate))
        except (OSError, TimeoutError, ConnectionRefusedError) as exc:
            raise SystemExit(
                f"Cannot reach {args.uri}\n"
                "Start the bridge first (repo root):  python bridge.py\n"
                f"Details: {exc}"
            ) from exc
        _print_bridge_result(done, expected_deg)


if __name__ == "__main__":
    main()
