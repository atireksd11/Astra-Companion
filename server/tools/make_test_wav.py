"""Write a short mono 16-bit PCM WAV for sim_robot tests."""

from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path


def write_tone(path: Path, rate: int = 16000, seconds: float = 1.0, hz: float = 440.0) -> None:
    n = int(rate * seconds)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            t = i / rate
            sample = int(8000 * math.sin(2 * math.pi * hz * t))
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(frames)
    print("wrote", path, f"({seconds}s @ {rate} Hz, tone {hz} Hz)")


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "test-tone.wav"
    write_tone(out)


if __name__ == "__main__":
    main()
