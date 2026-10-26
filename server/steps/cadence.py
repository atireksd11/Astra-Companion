from __future__ import annotations

import time

import numpy as np

from core.cadence import measure_cadence
from core.config import CadenceConfig, FocusConfig, ProfileConfig
from core.fillers import count_fillers
from core.langutil import is_english_turn
from core.speech_profile import ema, should_learn_turn
from core.turn import Turn
from core.vad_bridge import pcm16_to_mono
from store.profile_sync import push_profile
from store.profiles import ProfileStore


def make_cadence_step(
    cfg: CadenceConfig,
    profile_cfg: ProfileConfig,
    profiles: ProfileStore,
    focus_cfg: FocusConfig | None = None,
):
    def cadence_step(turn: Turn) -> None:
        if not cfg.enabled:
            return

        pcm = turn.pcm_for_analysis
        if pcm is None:
            pcm = bytes(turn.pcm_in)
            if int(turn.notes.get("channels", 1)) == 2:
                pcm = pcm16_to_mono(pcm, 2)

        stats = measure_cadence(pcm, turn.rate_hz, min_pause_ms=cfg.min_pause_ms)
        turn.notes["cadence"] = stats
        if not is_english_turn(turn):
            turn.notes["cadence"]["fillers"] = {"status": "skipped_non_en"}
            return

        ok, skip = should_learn_turn(turn)
        if not ok:
            turn.notes["cadence_learn"] = {"skipped": skip}
            return

        meta = turn.notes.get("meta") or {}
        emb = turn.notes.get("speaker_embedding")
        embedding = np.array(emb, dtype=np.float32) if emb else None
        fc = focus_cfg
        sid, doc = profiles.resolve_speaker(
            meta_speaker_id=meta.get("speaker_id"),
            embedding=embedding,
            enroll_pcm=None,
            rate=turn.rate_hz,
            min_similarity=profile_cfg.match_min_similarity,
            lock_owner=bool(fc and fc.lock_owner),
            owner_speaker_id=fc.owner_speaker_id if fc else "",
        )
        turn.notes["speaker_id"] = sid

        cad = doc.setdefault("cadence", {})
        cad["utterances"] = int(cad.get("utterances", 0)) + 1
        rate_sec = doc["cadence"].setdefault("speaking_rate", {})
        rate_sec["method"] = "energy_peaks"
        rate_sec["peaks_per_s_ema"] = round(
            ema(float(rate_sec.get("peaks_per_s_ema", 0)), stats["peaks_per_s"]), 3
        )

        pauses = doc["cadence"].setdefault("pauses", {})
        pauses["min_pause_ms"] = cfg.min_pause_ms
        if stats["pause_ms_median"] > 0:
            pauses["median_ms_ema"] = round(
                ema(float(pauses.get("median_ms_ema", 0)), stats["pause_ms_median"]), 1
            )
        pauses["per_utterance_ema"] = round(
            ema(float(pauses.get("per_utterance_ema", 0)), stats["pause_count"]), 2
        )

        transcript = turn.notes.get("transcript") or ""
        if not transcript and turn.text_in:
            transcript = turn.text_in
        fillers = doc["cadence"].setdefault("fillers", {})
        counts = count_fillers(transcript, tuple(cfg.fillers))
        if any(counts.values()):
            fillers["status"] = "ok"
            fillers["method"] = "tokens"
            fc = fillers.setdefault("counts", {k: 0 for k in cfg.fillers})
            for k, v in counts.items():
                fc[k] = int(fc.get(k, 0)) + v
            duration_min = max(len(pcm) / 2 / turn.rate_hz / 60.0, 1 / 60.0)
            per_min = sum(counts.values()) / duration_min
            fillers["per_minute_ema"] = round(
                ema(float(fillers.get("per_minute_ema") or 0), per_min), 2
            )
        else:
            fillers.setdefault("status", "needs_transcript")

        if embedding is not None and embedding.size:
            doc.setdefault("match", {})
            doc["match"]["method"] = (
                "ecapa192" if embedding.size == 192 else "mfcc13"
            )
            doc["match"]["embedding"] = embedding.tolist()

        doc["updated_at"] = time.time()
        profiles.put(doc)
        if not push_profile(profile_cfg.sync_url, doc, profile_cfg.sync_timeout_s):
            turn.notes["profile_sync_failed"] = True

        turn.notes["cadence_learn"] = {"speaker_id": sid, "updated": True}

    return cadence_step
