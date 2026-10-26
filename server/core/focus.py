"""Focus session: who said Hey Astra (Features 5 + 7 state)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from core.distance_volume import compute_playback_gain, pcm16_mono_rms
from core.speaker_ecapa import embed_pcm16_mono
from core.speaker_id import cosine_similarity


@dataclass
class FocusState:
    armed: bool = False
    enrolled: np.ndarray | None = None
    enroll_pre_denoise: np.ndarray | None = None
    target_azimuth_deg: float | None = None
    ref_rms: float = 1.0
    last_activity: float = field(default_factory=time.monotonic)
    following_new: bool = False


class FocusSession:
    def __init__(self) -> None:
        self.state = FocusState()

    def tick_timeout(self, timeout_s: float) -> bool:
        if not self.state.armed:
            return False
        if time.monotonic() - self.state.last_activity > timeout_s:
            self.state = FocusState()
            return True
        return False

    def on_wake(
        self,
        enroll_pcm: bytes,
        *,
        rate: int,
        azimuth_deg: float | None,
        snr_db: float | None = None,
        min_enroll_snr: float = 8.0,
        min_enroll_ms: int = 3000,
        speech_ms: int | None = None,
    ) -> str | None:
        """Enroll voice; return warning/error key or None."""
        if enroll_pcm and speech_ms is not None and speech_ms < min_enroll_ms:
            return "enroll_too_short"
        warn: str | None = None
        if enroll_pcm and snr_db is not None and snr_db < min_enroll_snr:
            warn = "enroll_contaminated"
        emb = embed_pcm16_mono(enroll_pcm, rate)
        if float(np.linalg.norm(emb)) < 1e-6:
            return "enroll_contaminated"
        was_armed = self.state.armed
        self.state.armed = True
        self.state.following_new = was_armed
        self.state.enrolled = emb
        self.state.enroll_pre_denoise = emb.copy()
        self.state.ref_rms = pcm16_mono_rms(enroll_pcm)
        self.state.target_azimuth_deg = azimuth_deg
        self.state.last_activity = time.monotonic()
        return warn

    def touch(self) -> None:
        if self.state.armed:
            self.state.last_activity = time.monotonic()

    def azimuth_ok(self, azimuth_deg: float | None, gate_deg: float = 35.0) -> bool:
        if self.state.target_azimuth_deg is None or azimuth_deg is None:
            return True
        return abs(azimuth_deg - self.state.target_azimuth_deg) <= gate_deg


def clip_similarity_ecapa(enrolled: np.ndarray, pcm: bytes, rate: int) -> float:
    if enrolled is None or not pcm:
        return 0.0
    if enrolled.size != 192:
        return 0.0
    probe = embed_pcm16_mono(pcm, rate)
    return cosine_similarity(enrolled, probe)


def sync_focus_from_owner(session: FocusSession, profiles, owner_speaker_id: str = "") -> bool:
    """Arm session when a valid owner ECAPA profile exists in the store."""
    from core.owner import find_owner_doc, owner_embedding
    from core.owner_enroll import owner_enroll_complete

    doc = find_owner_doc(profiles.list_all(), owner_speaker_id)
    if not owner_enroll_complete(doc):
        return False
    ref = owner_embedding(doc)
    if ref is None:
        return False
    session.state.armed = True
    session.state.enrolled = ref.copy()
    session.state.enroll_pre_denoise = ref.copy()
    session.touch()
    return True
