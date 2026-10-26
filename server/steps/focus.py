from __future__ import annotations

import base64
import time

import numpy as np

from core.config import DenoiseConfig, FocusConfig
from core.denoise import denoise_pcm16_fresh
from core.distance_volume import compute_playback_gain, pcm16_mono_rms
from core.focus import FocusSession, clip_similarity_ecapa
from core.focus_mask import mask_pcm_to_owner
from core.owner import find_owner_doc, owner_embedding
from core.owner_enroll import (
    owner_enroll_complete,
    verify_owner_robust,
)
from core.speaker_ecapa import embed_pcm16_mono, set_ecapa_source
from core.speech_profile import empty_profile, new_speaker_id
from core.turn import Turn
from core.vad_bridge import pcm16_to_mono
from core.silero_client import speech_ms_in_pcm
from detectors.noise_floor import analyze_mono_pcm
from store.profiles import ProfileStore

SHORT_CLIP_S = 0.4


def _antispoof_boost(turn: Turn) -> float:
    """This-turn owner-verify raise. Does not read or write FocusConfig."""
    note = turn.notes.get("antispoof")
    if not isinstance(note, dict):
        return 0.0
    try:
        boost = float(note.get("raise_verify") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if boost != boost or boost < 0.0:
        return 0.0
    return boost


def _with_boost(threshold: float, boost: float) -> float:
    return max(threshold, threshold + boost)


def _denoised_wake_clip(pcm: bytes, rate: int, denoise: DenoiseConfig) -> bytes:
    """Match enroll_owner when denoise is on. Failures keep the raw clip.

    Uses `denoise_pcm16_fresh` so this clip does not reuse the process-wide
    RNNoise state left by the utterance denoise step.
    """
    if not pcm or not denoise.enabled:
        return pcm
    try:
        result = denoise_pcm16_fresh(
            pcm,
            rate,
            backend=denoise.backend,
            strength=denoise.strength,
        )
    except Exception:
        return pcm
    if isinstance(result, (bytes, bytearray)):
        cleaned = result
    else:
        cleaned = getattr(result, "pcm", b"")
    if not isinstance(cleaned, (bytes, bytearray)) or len(cleaned) == 0:
        return pcm
    return bytes(cleaned)


def _wake_pcm_from_meta(meta: dict, pcm_sentence: bytes) -> tuple[bytes, bool]:
    """Return (wake bytes, used_legacy_enroll)."""
    if meta.get("wake_b64"):
        return base64.b64decode(meta["wake_b64"]), False
    if meta.get("enroll_b64"):
        raw = base64.b64decode(meta["enroll_b64"])
        return pcm_sentence[: min(len(pcm_sentence), len(raw))], True
    return b"", False


def make_focus_step(
    cfg: FocusConfig,
    session: FocusSession,
    profiles: ProfileStore,
    denoise: DenoiseConfig,
):
    if cfg.embedding == "ecapa":
        set_ecapa_source(cfg.ecapa_source)

    def _sync_session_from_db() -> np.ndarray | None:
        doc = find_owner_doc(profiles.list_all(), cfg.owner_speaker_id)
        if not owner_enroll_complete(doc):
            return None
        ref = owner_embedding(doc)
        if ref is not None and session.state.enrolled is None:
            session.state.armed = True
            session.state.enrolled = ref.copy()
            session.state.enroll_pre_denoise = ref.copy()
        return ref

    def focus_step(turn: Turn) -> None:
        if not cfg.enabled:
            return
        # Hard spoof stops the turn in the antispoof step. If this step is
        # reached anyway, do not let the wake-verified bypass accept it.
        prior = turn.notes.get("antispoof")
        if isinstance(prior, dict) and prior.get("action") == "hard":
            turn.error = "spoof_suspected"
            return
        timed_out = session.tick_timeout(cfg.session_timeout_s)
        if timed_out:
            _sync_session_from_db()

        meta = turn.notes.get("meta") or {}
        if turn.notes.get("wake_turn"):
            meta = {**meta, "wake": True}

        # Local vision_smoke.py uses a test tone; skip owner gate (not for production clients).
        if meta.get("source") == "vision_smoke":
            turn.notes["focus"] = {
                "verified": True,
                "enrolled": True,
                "lab": "vision_smoke",
            }
            session.touch()
            return

        pcm = bytes(turn.pcm_in)
        verify_pcm = bytes(turn.pcm_pre_denoise or pcm)
        channels = int(turn.notes.get("channels", 1))
        if channels == 2:
            pcm = pcm16_to_mono(pcm, 2)
            verify_pcm = pcm16_to_mono(verify_pcm, 2)
            turn.notes["channels"] = 1

        turn.pcm_for_analysis = pcm
        stored_ref = _sync_session_from_db()
        owner_doc = find_owner_doc(profiles.list_all(), cfg.owner_speaker_id)
        enroll_ok = owner_enroll_complete(owner_doc)

        if cfg.require_owner_enroll and not enroll_ok:
            turn.error = "need_enroll"
            turn.notes["focus"] = {"reason": "run enroll_owner.py first"}
            return

        if meta.get("wake"):
            wake_raw, legacy = _wake_pcm_from_meta(meta, pcm)
            enter_only = meta.get("enter_wake") or (
                not meta.get("wake_b64") and not meta.get("enroll_b64")
            )
            if cfg.lock_owner and owner_doc is not None and enter_only:
                turn.error = "asleep"
                turn.notes["focus"] = {"reason": "need_wake_phrase"}
                return

            if enter_only and not owner_doc and not wake_raw and pcm:
                wake_raw = pcm[: min(len(pcm), int(0.8 * turn.rate_hz * 2))]

            if wake_raw:
                if legacy:
                    wake_speech_ms = speech_ms_in_pcm(wake_raw, 0.5)
                    min_ms = int(cfg.min_enroll_s * 1000)
                    dur_ms = int(len(wake_raw) / 2 / max(turn.rate_hz, 1) * 1000)
                    if wake_speech_ms < min_ms and dur_ms >= min_ms:
                        wake_speech_ms = dur_ms
                else:
                    wake_speech_ms = speech_ms_in_pcm(wake_raw, 0.5)
                    min_ms = int(cfg.wake_min_speech_ms)
                    dur_ms = int(len(wake_raw) / 2 / max(turn.rate_hz, 1) * 1000)
                    if wake_speech_ms < min_ms and dur_ms >= min_ms:
                        wake_speech_ms = dur_ms
                if wake_speech_ms < min_ms:
                    turn.error = "enroll_too_short"
                    return

                wake_pcm = _denoised_wake_clip(wake_raw, turn.rate_hz, denoise)
                probe = embed_pcm16_mono(wake_pcm, turn.rate_hz)
                if float(np.linalg.norm(probe)) < 1e-6:
                    turn.error = "enroll_too_short"
                    return

                if enroll_ok and owner_doc is not None:
                    boost = _antispoof_boost(turn)
                    wake_min_mean = _with_boost(
                        max(0.30, cfg.verify_min_mean - 0.12), boost
                    )
                    wake_min_best = _with_boost(
                        max(0.35, cfg.verify_min_best_clip - 0.12), boost
                    )
                    wake_ok, wake_sim, wake_via = verify_owner_robust(
                        owner_doc,
                        probe,
                        min_mean=wake_min_mean,
                        min_best_clip=wake_min_best,
                    )
                    if not wake_ok:
                        turn.error = "not your voice"
                        turn.notes["focus"] = {
                            "match": round(wake_sim, 3),
                            "wake_match": round(wake_sim, 3),
                            "verify_via": wake_via,
                            "gate": "wake",
                            "mixed_ms": 0,
                        }
                        return
                    ref = owner_embedding(owner_doc)
                    if ref is None:
                        turn.error = "need_enroll"
                        return
                    session.state.armed = True
                    session.state.enrolled = ref.copy()
                    session.state.enroll_pre_denoise = ref.copy()
                    session.state.ref_rms = pcm16_mono_rms(wake_pcm)
                    session.touch()
                    turn.notes["focus_wake"] = {
                        "match": round(wake_sim, 3),
                        "verified": True,
                        "verify_via": wake_via,
                    }
                elif not cfg.require_owner_enroll:
                    if owner_doc is not None and cfg.lock_owner:
                        turn.error = "not your voice"
                        turn.notes["focus"] = {
                            "reason": "owner_profile_incompatible",
                            "enrolled": True,
                            "mixed_ms": 0,
                        }
                        return
                    noise = analyze_mono_pcm(wake_pcm, turn.rate_hz)
                    warn = session.on_wake(
                        wake_pcm,
                        rate=turn.rate_hz,
                        azimuth_deg=turn.notes.get("azimuth_deg"),
                        snr_db=noise.get("snr_db"),
                        min_enroll_ms=min_ms,
                        speech_ms=wake_speech_ms,
                    )
                    if warn == "enroll_too_short":
                        turn.error = "enroll_too_short"
                        return
                    if warn:
                        turn.notes["focus_warn"] = warn
                    sid = cfg.owner_speaker_id or new_speaker_id()
                    if owner_doc:
                        sid = str(owner_doc["speaker_id"])
                        doc = owner_doc
                    else:
                        doc = empty_profile(
                            sid,
                            session.state.enrolled.tolist()
                            if session.state.enrolled is not None
                            else [],
                        )
                    doc["is_owner"] = True
                    doc["match"]["method"] = "ecapa192"
                    if session.state.enrolled is not None:
                        doc["match"]["embedding"] = session.state.enrolled.tolist()
                    doc["updated_at"] = time.time()
                    profiles.put(doc)
                    cfg.owner_speaker_id = sid
                    turn.notes["speaker_id"] = sid
                    turn.notes["owner_enrolled"] = True
                else:
                    turn.error = "need_enroll"
                    return

                if session.state.enrolled is not None:
                    turn.notes["speaker_embedding"] = session.state.enrolled.tolist()

        if not session.state.armed and not meta.get("wake"):
            turn.error = "asleep"
            return

        if session.state.enrolled is None:
            turn.error = "asleep"
            return

        ref = session.state.enrolled
        assert ref is not None
        if ref.size != 192:
            turn.error = "not your voice"
            turn.notes["focus"] = {"match": 0.0, "enrolled": True, "mixed_ms": 0}
            return

        seg_s = len(pcm) / 2 / turn.rate_hz
        az = turn.notes.get("azimuth_deg")
        short_ok = seg_s < SHORT_CLIP_S and session.azimuth_ok(
            az, cfg.azimuth_gate_deg
        )

        def _strip_wake_tail(raw: bytes) -> bytes:
            """Drop wake prefix only when sentence PCM includes the wake window.

            Laptop sends ``wake_b64`` separately from the utterance (see FEATURE5).
            """
            if meta.get("wake_pcm_separate") or meta.get("source") == "laptop":
                return raw
            out = raw
            if meta.get("wake_b64"):
                try:
                    wake_len = len(base64.b64decode(meta["wake_b64"]))
                    min_body = int(turn.rate_hz * 0.35) * 2
                    if len(raw) > wake_len + min_body:
                        out = raw[wake_len:]
                except Exception:
                    out = raw
            return out

        body_pcm = _strip_wake_tail(pcm)
        verify_body = _strip_wake_tail(verify_pcm)

        follow_up = session.state.armed and not meta.get("wake")
        cold_enroll = bool(turn.notes.get("owner_enrolled"))
        probe_body = embed_pcm16_mono(verify_body, turn.rate_hz)
        min_mean = cfg.verify_min_mean
        min_best = cfg.verify_min_best_clip
        if follow_up:
            min_mean = max(0.32, min_mean - 0.05)
            min_best = max(0.34, min_best - 0.06)
        boost = _antispoof_boost(turn)
        min_mean = _with_boost(min_mean, boost)
        min_best = _with_boost(min_best, boost)
        if enroll_ok and owner_doc is not None:
            body_ok, clip_sim, via = verify_owner_robust(
                owner_doc,
                probe_body,
                min_mean=min_mean,
                min_best_clip=min_best,
            )
            clip_sim = clip_sim
        else:
            body_ok = True
            clip_sim = clip_similarity_ecapa(ref, body_pcm, turn.rate_hz)
            via = "legacy"
        wake_verified = bool(turn.notes.get("focus_wake", {}).get("verified"))
        wake_sim = float(turn.notes.get("focus_wake", {}).get("match") or 0)
        # Same turn already proved the owner on the wake window. The sentence
        # embedding is a second guess and was rejecting the owner at ~0.07
        # after someone else had just been scored.
        if (
            not body_ok
            and enroll_ok
            and meta.get("wake")
            and wake_verified
            and wake_sim >= max(0.32, cfg.verify_min_mean - 0.08)
        ):
            body_ok = True
            via = "wake_verified_turn"

        if not cold_enroll and enroll_ok and not body_ok and not short_ok:
            turn.error = "not your voice"
            turn.notes["focus"] = {
                "match": round(clip_sim, 3),
                "wake_match": round(wake_sim, 3),
                "enrolled": True,
                "verify_via": via,
                "mixed_ms": 0,
                "gate": "sentence",
                "follow_up": follow_up,
            }
            return
        if (
            not cold_enroll
            and not enroll_ok
            and clip_sim < cfg.min_similarity
            and not short_ok
            and not (wake_verified and clip_sim >= cfg.min_similarity * 0.65)
        ):
            turn.error = "not your voice"
            turn.notes["focus"] = {
                "match": round(clip_sim, 3),
                "enrolled": True,
                "mixed_ms": 0,
            }
            return

        mixed_ms = 0
        keep_ratio = 1.0
        out_pcm = pcm
        if cfg.mask_other_voices and ref.size == 192 and not cold_enroll:
            mask_min = max(0.28, cfg.min_similarity * 0.75)
            out_pcm, mixed_ms, keep_ratio = mask_pcm_to_owner(
                pcm,
                ref,
                turn.rate_hz,
                min_similarity=mask_min,
                window_s=cfg.mask_window_s,
                hop_s=cfg.mask_hop_s,
            )
            if pcm16_mono_rms(out_pcm) < 80.0 and keep_ratio < 0.01:
                turn.error = "too_mixed"
                turn.notes["focus"] = {
                    "match": round(clip_sim, 3),
                    "enrolled": True,
                    "mixed_ms": mixed_ms,
                    "keep_ratio": round(keep_ratio, 3),
                }
                return
            if keep_ratio < 0.45:
                turn.notes["focus_warn"] = "noisy_room_partial"

        playback_pcm = out_pcm if cfg.echo_use_owner_mask else pcm
        turn.pcm_in = bytearray(playback_pcm)
        loud_rms = pcm16_mono_rms(playback_pcm)
        vol = compute_playback_gain(
            session.state.ref_rms,
            loud_rms,
            min_gain=cfg.min_gain,
            max_gain=cfg.max_gain,
        )
        base_vol = float(meta.get("vol", 0.2))
        vol["firmware_vol"] = round(
            min(cfg.firmware_volume_cap, base_vol * vol["gain"]), 3
        )
        turn.notes["volume"] = vol
        chatter_az = turn.notes.get("chatter_azimuth_deg")
        turn.notes["focus"] = {
            "match": round(clip_sim, 3),
            "enrolled": True,
            "verified": True,
            "target_azimuth_deg": session.state.target_azimuth_deg,
            "chatter_azimuth_deg": chatter_az,
            "mixed_ms": mixed_ms,
            "keep_ratio": round(keep_ratio, 3),
        }
        # Mood scores the owner mask. STT and cadence keep the full clip in
        # pcm_for_analysis. Echo keeps pcm_in unless echo_use_owner_mask is on.
        turn.pcm_mood = out_pcm
        session.touch()

    return focus_step
