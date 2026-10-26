#!/usr/bin/env python3
"""Score wav or raw PCM16 files with the AASIST-L soft gate. Does not train.

Prints spoof_score and the self-echo fields. With more than one file, also
prints p50 / p95 / p99 of the numeric spoof scores.

Example (from server/):

    python tools/calibrate_antispoof.py clip.wav other.pcm
    python tools/calibrate_antispoof.py clip.wav --playback last_reply.wav
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.antispoof import score_raw_pcm16  # noqa: E402
from core.config import AntispoofConfig  # noqa: E402


def _resample(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate or samples.size == 0:
        return samples.astype(np.float32, copy=False)
    n_out = int(round(samples.size * dst_rate / src_rate))
    if n_out <= 0:
        return np.zeros(0, dtype=np.float32)
    old = np.linspace(0.0, 1.0, samples.size, endpoint=False)
    new = np.linspace(0.0, 1.0, n_out, endpoint=False)
    return np.interp(new, old, samples.astype(np.float64)).astype(np.float32)


def _float_to_pcm16(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes()


def _wav_chunks(data: bytes) -> tuple[bytes | None, bytes | None]:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None, None
    pos = 12
    fmt = None
    payload = None
    while pos + 8 <= len(data):
        cid = data[pos : pos + 4]
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        start = pos + 8
        end = start + size
        if end > len(data):
            break
        body = data[start:end]
        pos = end + (size & 1)
        if cid == b"fmt " and fmt is None:
            fmt = body
        elif cid == b"data" and payload is None:
            payload = body
    return fmt, payload


def _pcm_to_float(payload: bytes, audio_format: int, bits: int) -> np.ndarray | None:
    if audio_format == 1 and bits == 16:
        n = len(payload) // 2
        return np.frombuffer(payload[: n * 2], dtype="<i2").astype(np.float32) / 32768.0
    if audio_format == 1 and bits == 8:
        return (np.frombuffer(payload, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    if audio_format == 1 and bits == 24:
        n = len(payload) // 3
        raw = np.frombuffer(payload[: n * 3], dtype=np.uint8).reshape(n, 3)
        vals = (
            raw[:, 0].astype(np.int32)
            | (raw[:, 1].astype(np.int32) << 8)
            | (raw[:, 2].astype(np.int32) << 16)
        )
        vals = np.where(vals >= 0x800000, vals - 0x1000000, vals)
        return vals.astype(np.float32) / 8388608.0
    if audio_format == 1 and bits == 32:
        n = len(payload) // 4
        return np.frombuffer(payload[: n * 4], dtype="<i4").astype(np.float32) / 2147483648.0
    if audio_format == 3 and bits == 32:
        n = len(payload) // 4
        return np.frombuffer(payload[: n * 4], dtype="<f4").astype(np.float32)
    if audio_format == 3 and bits == 64:
        n = len(payload) // 8
        return np.frombuffer(payload[: n * 8], dtype="<f8").astype(np.float32)
    return None


def _wav_to_mono_float(path: Path) -> tuple[np.ndarray, int]:
    fmt, payload = _wav_chunks(path.read_bytes())
    if fmt is None or payload is None or len(fmt) < 16:
        raise SystemExit(f"{path}: WAV is missing a fmt or data chunk")
    audio_format, channels, rate, _br, _ba, bits = struct.unpack_from("<HHIIHH", fmt)
    if audio_format == 0xFFFE:
        if len(fmt) < 26:
            raise SystemExit(f"{path}: extensible WAV fmt is too small")
        audio_format = struct.unpack_from("<H", fmt, 24)[0]
    if channels < 1 or rate <= 0:
        raise SystemExit(f"{path}: bad WAV header")
    samples = _pcm_to_float(payload, int(audio_format), int(bits))
    if samples is None:
        raise SystemExit(
            f"{path}: unsupported WAV format {audio_format} / {bits}-bit"
        )
    if channels > 1:
        n = (samples.size // channels) * channels
        samples = samples[:n].reshape(-1, channels).mean(axis=1)
    return np.ascontiguousarray(samples, dtype=np.float32), int(rate)


def load_mono_pcm16(path: Path, rate: int = 16000) -> bytes:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        samples, src_rate = _wav_to_mono_float(path)
        if src_rate != rate:
            samples = _resample(samples, src_rate, rate)
            print(f"{path.name}: resampled {src_rate} Hz -> {rate} Hz")
        return _float_to_pcm16(samples)
    return path.read_bytes()


def _fmt(value) -> str:
    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score files with AASIST-L (no training)")
    parser.add_argument("paths", nargs="+", type=Path, help="wav or raw PCM16 mono files")
    parser.add_argument(
        "--playback",
        type=Path,
        default=None,
        help="optional previous playback wav/pcm for the self-echo check",
    )
    parser.add_argument("--rate", type=int, default=16000)
    parser.add_argument("--weights", default="models/AASIST-L.pth")
    parser.add_argument("--soft", type=float, default=0.80)
    parser.add_argument("--hard", type=float, default=AntispoofConfig().hard)
    args = parser.parse_args()

    cfg = AntispoofConfig(weights=args.weights, soft=args.soft, hard=args.hard)
    playback = None
    if args.playback is not None:
        playback = load_mono_pcm16(args.playback, args.rate)

    scores: list[float] = []
    for path in args.paths:
        if not path.is_file():
            print(f"{path}: missing")
            continue
        pcm = load_mono_pcm16(path, args.rate)
        note = score_raw_pcm16(pcm, args.rate, cfg, playback)
        if note["spoof_score"] is not None:
            scores.append(float(note["spoof_score"]))
        print(
            f"{path} spoof_score={_fmt(note['spoof_score'])} "
            f"spoof_score_max={_fmt(note['spoof_score_max'])} "
            f"n_windows={note['n_windows']} reliable={note['reliable']} "
            f"echo_corr={_fmt(note['echo_corr'])} action={note['action']} "
            f"raise_verify={_fmt(note['raise_verify'])} backend={note['backend']}"
        )

    if len(args.paths) > 1:
        if scores:
            arr = np.asarray(scores, dtype=np.float64)
            print(
                f"n={len(scores)} p50={np.percentile(arr, 50):.4f} "
                f"p95={np.percentile(arr, 95):.4f} p99={np.percentile(arr, 99):.4f}"
            )
        else:
            print("n=0 no spoof scores (silence or weights unavailable)")


if __name__ == "__main__":
    main()
