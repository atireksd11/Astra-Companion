"""
Record ~8 short phrases to build your owner voiceprint in astra.db.

Run once before laptop_voice when focus.require_owner_enroll is true.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import load_config  # noqa: E402
from core.env import load_dotenv  # noqa: E402
from core.denoise import denoise_pcm16_mono  # noqa: E402
from core.owner import find_owner_doc  # noqa: E402
from core.owner_enroll import (  # noqa: E402
    append_enroll_clip,
    finalize_owner_enroll,
    owner_enroll_complete,
)
from core.speaker_ecapa import embed_pcm16_mono, set_ecapa_source  # noqa: E402
from core.speech_profile import empty_profile, new_speaker_id  # noqa: E402
from detectors.noise_floor import analyze_mono_pcm  # noqa: E402
from store.profiles import ProfileStore  # noqa: E402
from tools.laptop_voice import record_one_utterance  # noqa: E402

PHRASES = [
    ("name", "Say your first name clearly."),
    ("hello", "Hello, I am setting up my voice on this device."),
    ("jarvis1", 'Say "Hey Astra" once, clearly.'),
    ("weather", "What is the weather today?"),
    ("numbers", "One two three four five six seven eight nine ten."),
    ("jarvis2", 'Say "Hey Astra" again.'),
    ("question", "Turn on the kitchen lights please."),
    ("thanks", "Thanks Astra, that is all for setup."),
]

MIN_SPEECH_MS = 400


def main() -> None:
    load_dotenv()
    cfg = load_config()
    db_path = Path(os.environ.get("ASTRA_DB", ROOT / "astra.db"))
    profiles = ProfileStore(db_path)
    set_ecapa_source(cfg.focus.ecapa_source)

    owner = find_owner_doc(profiles.list_all(), cfg.focus.owner_speaker_id)
    if owner_enroll_complete(owner):
        print("Owner voiceprint already complete. Run reset-owner.ps1 to re-enroll.")
        return

    sid = cfg.focus.owner_speaker_id or (
        str(owner["speaker_id"]) if owner else new_speaker_id()
    )
    doc = profiles.get(sid) or empty_profile(sid, [])
    doc["is_owner"] = True

    print("\n=== Owner voice enrollment (~1 minute) ===\n")
    print("After each prompt, speak the line then press Enter when done.\n")

    kept = 0
    for phrase_id, prompt in PHRASES:
        print(f"\n--- {prompt} ---")
        pcm = record_one_utterance(min_speech_ms=MIN_SPEECH_MS, noisy_room=True)
        if not pcm or len(pcm) < 8000:
            print("(Skipped — too short, try again on next line.)")
            continue
        if cfg.denoise.enabled:
            pcm = denoise_pcm16_mono(
                pcm, 16000, backend=cfg.denoise.backend, strength=cfg.denoise.strength
            ).pcm
        noise = analyze_mono_pcm(pcm, 16000)
        emb = embed_pcm16_mono(pcm, 16000)
        if float(np.linalg.norm(emb)) < 1e-6:
            print("(Skipped — no clear speech.)")
            continue
        append_enroll_clip(
            doc, emb, snr_db=float(noise.get("snr_db", 0)), phrase_id=phrase_id
        )
        kept += 1
        print(f"Saved clip {kept} (snr {noise.get('snr_db')} dB).")

    min_clips = max(4, cfg.focus.enroll_min_clips)
    if not finalize_owner_enroll(doc, min_clips=min_clips):
        print(f"\nNeed at least {min_clips} good clips; got {kept}. Run again.")
        raise SystemExit(1)

    doc["updated_at"] = time.time()
    profiles.put(doc)
    print(f"\nDone. Owner {sid} saved with {kept} clips.")
    print("Next: python laptop_voice.py --noisy\n")


if __name__ == "__main__":
    main()
