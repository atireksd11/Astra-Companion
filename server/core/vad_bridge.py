"""Utterance onset / frame speech detection (WebRTC VAD optional, RMS fallback)."""

from __future__ import annotations

import math
import struct

FRAME_MS = 20
NOISE_FLOOR_MIN = 80
SPEECH_MULT = 3
_RMS_SPEECH_MIN = 240

try:
    import webrtcvad

    _VAD = webrtcvad.Vad(2)
    HAS_WEBRTCVAD = True
except ImportError:
    webrtcvad = None  # type: ignore[assignment,misc]
    _VAD = None
    HAS_WEBRTCVAD = False


def vad_backend() -> str:
    return "webrtc" if HAS_WEBRTCVAD else "rms"


def frame_bytes(sample_rate: int) -> int:
    return sample_rate * FRAME_MS // 1000 * 2


def frame_rms(pcm_frame: bytes) -> int:
    n = len(pcm_frame) // 2
    if n <= 0:
        return 0
    samples = struct.unpack(f"<{n}h", pcm_frame)
    acc = sum(s * s for s in samples)
    return int(math.sqrt(acc / n))


def rms_is_speech(pcm_frame: bytes, noise_floor: int | None = None) -> bool:
    floor = NOISE_FLOOR_MIN if noise_floor is None else noise_floor
    thr = max(NOISE_FLOOR_MIN, floor * SPEECH_MULT)
    return frame_rms(pcm_frame) >= thr


def frame_vad(pcm16_20ms: bytes, rate: int) -> bool:
    """True if this 20 ms mono PCM16 frame looks like speech."""
    fb = frame_bytes(rate)
    if len(pcm16_20ms) != fb:
        return rms_is_speech(pcm16_20ms)
    if HAS_WEBRTCVAD and _VAD is not None and rate in (8000, 16000, 32000, 48000):
        try:
            return bool(_VAD.is_speech(pcm16_20ms, rate))
        except Exception:
            pass
    return frame_rms(pcm16_20ms) >= _RMS_SPEECH_MIN


def webrtc_is_speech(pcm_frame: bytes, sample_rate: int, aggressiveness: int = 2) -> bool:
    if not HAS_WEBRTCVAD or webrtcvad is None:
        return rms_is_speech(pcm_frame)
    vad = webrtcvad.Vad(aggressiveness)
    return vad.is_speech(pcm_frame, sample_rate)


def is_speech_frame(
    pcm_frame: bytes,
    sample_rate: int = 16000,
    *,
    prefer_webrtc: bool = True,
    aggressiveness: int = 2,
    noise_floor: int | None = None,
) -> bool:
    fb = frame_bytes(sample_rate)
    if len(pcm_frame) != fb:
        return rms_is_speech(pcm_frame, noise_floor)
    if prefer_webrtc and HAS_WEBRTCVAD:
        return webrtc_is_speech(pcm_frame, sample_rate, aggressiveness)
    return rms_is_speech(pcm_frame, noise_floor)


def pcm16_to_mono(pcm: bytes, channels: int = 1) -> bytes:
    if channels <= 1:
        return pcm
    out = bytearray()
    for i in range(0, len(pcm) - 3, 4):
        left, right = struct.unpack_from("<hh", pcm, i)
        out.extend(struct.pack("<h", (left + right) // 2))
    return bytes(out)


def detect_onset_in_pcm(pcm: bytes, rate: int, channels: int = 1) -> dict:
    """Return {"onset_ms", "speech_ms", "vad_backend"} for trimmed or raw PCM."""
    mono = pcm16_to_mono(pcm, channels)
    fb = frame_bytes(rate)
    if len(mono) < fb:
        return {"onset_ms": 0, "speech_ms": 0, "vad_backend": vad_backend()}

    onset_ms: int | None = None
    speech_ms = 0
    noise_floor = NOISE_FLOOR_MIN
    n_frames = len(mono) // fb
    for i in range(n_frames):
        frame = mono[i * fb : (i + 1) * fb]
        level = frame_rms(frame)
        thr = max(NOISE_FLOOR_MIN, noise_floor * SPEECH_MULT)
        speech = frame_vad(frame, rate) if HAS_WEBRTCVAD else level >= thr
        if not speech and level < thr:
            noise_floor = (noise_floor * 95 + level * 5) // 100
            if noise_floor < NOISE_FLOOR_MIN:
                noise_floor = NOISE_FLOOR_MIN
        if speech:
            speech_ms += FRAME_MS
            if onset_ms is None:
                onset_ms = i * FRAME_MS

    return {
        "onset_ms": 0 if onset_ms is None else onset_ms,
        "speech_ms": speech_ms,
        "vad_backend": vad_backend(),
    }


def find_tone_onset_byte(
    pcm: bytes,
    sample_rate: int = 16000,
    *,
    prefer_webrtc: bool = True,
) -> int | None:
    """Byte offset of first speech frame, or None if none detected."""
    del prefer_webrtc  # frame_vad picks backend automatically
    stats = detect_onset_in_pcm(pcm, sample_rate, channels=1)
    if stats["speech_ms"] <= 0:
        return None
    return stats["onset_ms"] * sample_rate * 2 // 1000
