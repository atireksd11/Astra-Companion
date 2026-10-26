from __future__ import annotations

import time

import numpy as np

from core.config import FocusConfig, PronunciationConfig, ProfileConfig
from core.langutil import is_english_turn
from core.pronunciation import teach_word
from core.speech_profile import should_learn_turn
from core.turn import Turn
from store.profile_sync import push_profile
from store.profiles import ProfileStore


def make_pronunciation_step(
    cfg: PronunciationConfig,
    profile_cfg: ProfileConfig,
    profiles: ProfileStore,
    focus_cfg: FocusConfig,
):
    def pronunciation_step(turn: Turn) -> None:
        if not cfg.enabled:
            return

        meta = turn.notes.get("meta") or {}
        teach = meta.get("teach")
        if not is_english_turn(turn):
            if teach and isinstance(teach, dict):
                turn.notes["pronunciation_teach_skipped"] = "non_en"
            turn.notes["pronunciation"] = {
                "status": "skipped_non_en",
                "lexicon_size": 0,
                "scored_words": 0,
            }
            turn.notes["pronunciation_learn"] = {"skipped": "non_en"}
            return

        sid = turn.notes.get("speaker_id")
        emb = turn.notes.get("speaker_embedding")
        embedding = np.array(emb, dtype=np.float32) if emb else None

        if sid:
            doc = profiles.get(sid)
        else:
            sid, doc = profiles.resolve_speaker(
                meta_speaker_id=meta.get("speaker_id"),
                embedding=embedding,
                enroll_pcm=None,
                rate=turn.rate_hz,
                min_similarity=profile_cfg.match_min_similarity,
                lock_owner=focus_cfg.lock_owner,
                owner_speaker_id=focus_cfg.owner_speaker_id,
            )
            turn.notes["speaker_id"] = sid

        if doc is None:
            sid, doc = profiles.resolve_speaker(
                meta_speaker_id=sid,
                embedding=embedding,
                enroll_pcm=None,
                rate=turn.rate_hz,
                min_similarity=profile_cfg.match_min_similarity,
                lock_owner=focus_cfg.lock_owner,
                owner_speaker_id=focus_cfg.owner_speaker_id,
            )

        if teach and isinstance(teach, dict):
            word = str(teach.get("word", "")).strip()
            phones = list(teach.get("phones") or [])
            if word and phones:
                teach_word(doc, word, phones)
                entry = next(
                    (e for e in doc["pronunciation"]["lexicon"] if e["word"] == word.lower()),
                    None,
                )
                if entry:
                    entry["status"] = "taught"
                    entry["source"] = "user"
                    entry["seed"] = list(phones)
                    entry["phones"] = list(phones)
                    entry["candidates"] = []
                doc["updated_at"] = time.time()
                profiles.put(doc)
                turn.notes["pronunciation_taught"] = word

        pron = doc.setdefault("pronunciation", {})
        pron["aligner"] = cfg.aligner
        turn.notes["pronunciation"] = {
            "status": pron.get("status", "needs_aligner"),
            "lexicon_size": len(pron.get("lexicon", [])),
            "scored_words": pron.get("scored_words", 0),
        }

        ok, skip = should_learn_turn(turn)
        if cfg.aligner == "ctc" and ok and not turn.error:
            turn.notes["pronunciation_learn_pending"] = True
        elif not ok and not teach:
            turn.notes["pronunciation_learn"] = {"skipped": skip}

        if cfg.aligner == "none":
            turn.notes["pronunciation"]["needs_aligner"] = True
            profiles.put(doc)
            return

        profiles.put(doc)
        if not push_profile(profile_cfg.sync_url, doc, profile_cfg.sync_timeout_s):
            turn.notes["profile_sync_failed"] = True

    return pronunciation_step
