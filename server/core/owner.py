"""Owner profile (192-d ECAPA) for locked focus."""

from __future__ import annotations

from typing import Any

import numpy as np

from core.owner_enroll import owner_enroll_complete, owner_reference, verify_owner_robust
from core.speaker_id import cosine_similarity


def owner_embedding(doc: dict[str, Any] | None) -> np.ndarray | None:
    return owner_reference(doc)


def find_owner_doc(
    profiles: list[dict[str, Any]],
    owner_speaker_id: str = "",
) -> dict[str, Any] | None:
    if owner_speaker_id:
        for doc in profiles:
            if doc.get("speaker_id") == owner_speaker_id:
                return doc
    for doc in profiles:
        if doc.get("is_owner"):
            return doc
    return None


def verify_owner(ref: np.ndarray, probe: np.ndarray, min_similarity: float) -> float:
    if ref.size != probe.size:
        return 0.0
    return cosine_similarity(ref, probe)
