"""Multi-clip owner voiceprint (mean ECAPA + clip bank)."""

from __future__ import annotations

from typing import Any

import numpy as np

from core.speaker_id import cosine_similarity

MAX_ENROLL_CLIPS = 12
DEFAULT_MIN_MEAN = 0.45
DEFAULT_MIN_BEST_CLIP = 0.50


def owner_enroll_complete(doc: dict[str, Any] | None) -> bool:
    if not doc:
        return False
    oe = doc.get("owner_enroll") or {}
    if not oe.get("complete"):
        return False
    emb = doc.get("match", {}).get("embedding") or []
    return len(emb) == 192


def owner_reference(doc: dict[str, Any] | None) -> np.ndarray | None:
    if not doc:
        return None
    emb = doc.get("match", {}).get("embedding") or []
    if len(emb) != 192:
        return None
    ref = np.array(emb, dtype=np.float32)
    n = float(np.linalg.norm(ref))
    return ref / n if n > 1e-8 else ref


def _clip_vectors(doc: dict[str, Any]) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    for item in (doc.get("owner_enroll") or {}).get("clips") or []:
        emb = item.get("embedding") or []
        if len(emb) != 192:
            continue
        v = np.array(emb, dtype=np.float32)
        n = float(np.linalg.norm(v))
        if n > 1e-8:
            out.append(v / n)
    return out


def verify_owner_robust(
    doc: dict[str, Any],
    probe: np.ndarray,
    *,
    min_mean: float = DEFAULT_MIN_MEAN,
    min_best_clip: float = DEFAULT_MIN_BEST_CLIP,
) -> tuple[bool, float, str]:
    """Accept if mean or any enroll clip matches probe."""
    mean = owner_reference(doc)
    if mean is None or probe.size != 192:
        return False, 0.0, "no_owner"
    p = probe.astype(np.float32)
    pn = float(np.linalg.norm(p))
    if pn > 1e-8:
        p = p / pn
    sim_mean = cosine_similarity(mean, p)
    best = sim_mean
    which = "mean"
    for clip in _clip_vectors(doc):
        s = cosine_similarity(clip, p)
        if s > best:
            best = s
            which = "clip"
    ok = sim_mean >= min_mean or best >= min_best_clip
    return ok, best, which


def append_enroll_clip(
    doc: dict[str, Any],
    embedding: np.ndarray,
    *,
    snr_db: float = 0.0,
    phrase_id: str = "",
) -> None:
    oe = doc.setdefault("owner_enroll", {})
    clips: list[dict[str, Any]] = list(oe.get("clips") or [])
    v = embedding.astype(np.float32).reshape(-1)
    if v.size != 192:
        return
    n = float(np.linalg.norm(v))
    if n > 1e-8:
        v = v / n
    clips.append(
        {
            "embedding": v.tolist(),
            "snr_db": round(float(snr_db), 2),
            "phrase_id": phrase_id,
        }
    )
    oe["clips"] = clips[-MAX_ENROLL_CLIPS:]
    stack = np.stack([np.array(c["embedding"], dtype=np.float32) for c in oe["clips"]])
    mean = stack.mean(axis=0)
    mn = float(np.linalg.norm(mean))
    if mn > 1e-8:
        mean = mean / mn
    doc.setdefault("match", {})["method"] = "ecapa192"
    doc["match"]["embedding"] = mean.tolist()
    oe["phrase_count"] = len(oe["clips"])


def finalize_owner_enroll(doc: dict[str, Any], *, min_clips: int = 4) -> bool:
    oe = doc.get("owner_enroll") or {}
    clips = oe.get("clips") or []
    if len(clips) < min_clips:
        return False
    oe["complete"] = True
    doc["is_owner"] = True
    doc["owner_enroll"] = oe
    return True
