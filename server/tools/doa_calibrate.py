#!/usr/bin/env python3
"""Suggest doa.offset_deg from a known angle and a stereo recording.

Positive azimuth means the voice is to the robot's left (same as core/doa.py).
offset_deg = true_deg - measured_deg. Put that number in config.json.
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.doa import estimate_azimuth_deg, split_stereo_interleaved  # noqa: E402
from tests.fixtures.stereo_pcm import stereo_pcm_with_right_delay  # noqa: E402


def _synthetic_stereo(rate: int, baseline_m: float, true_deg: float) -> bytes:
    c = 343.0
    delay_s = (baseline_m / c) * math.sin(math.radians(true_deg))
    delay_samples = max(0, int(round(delay_s * rate)))
    mono = b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
        for i in range(rate)
    )
    return stereo_pcm_with_right_delay(mono, delay_samples)


def _load_stereo_wav(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as wf:
        if wf.getsampwidth() != 2:
            raise SystemExit("WAV must be 16-bit PCM")
        if wf.getnchannels() != 2:
            raise SystemExit("WAV must be stereo (2 channels). Mono cannot show direction.")
        rate = wf.getframerate()
        pcm = wf.readframes(wf.getnframes())
    return pcm, rate


def main() -> None:
    p = argparse.ArgumentParser(description="Suggest doa.offset_deg for config.json")
    p.add_argument(
        "--true-deg",
        type=float,
        required=True,
        help="Where you stood, degrees. + = left of robot front, - = right",
    )
    p.add_argument("--wav", type=Path, help="Stereo WAV recorded from the robot")
    p.add_argument("--baseline-m", type=float, default=0.04)
    p.add_argument("--rate", type=int, default=16000)
    args = p.parse_args()

    if args.wav:
        pcm, rate = _load_stereo_wav(args.wav)
    else:
        pcm = _synthetic_stereo(args.rate, args.baseline_m, args.true_deg)
        rate = args.rate
        print("No --wav given; using a synthetic tone (lab check only).")

    left, right = split_stereo_interleaved(pcm)
    measured, conf = estimate_azimuth_deg(
        left, right, rate, baseline_m=args.baseline_m
    )
    offset = args.true_deg - measured
    print(f"measured_deg={measured:.2f} confidence={conf:.3f}")
    print(f"suggested doa.offset_deg={offset:.2f}")
    print("Put this in server/config.json under doa.offset_deg, then restart the bridge.")
    if conf < 0.20:
        print("Confidence is low. Check both mics are live and about 40 mm apart.")


if __name__ == "__main__":
    main()
