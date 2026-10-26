from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pronunciation import teach_word  # noqa: E402
from core.speech_profile import empty_profile  # noqa: E402


def test_teach_word_score_null() -> None:
    doc = empty_profile("spk_x")
    teach_word(doc, "tomato", ["T", "AH", "M", "EY", "T", "OW"])
    entry = doc["pronunciation"]["lexicon"][0]
    assert entry["word"] == "tomato"
    assert entry["score"] is None
