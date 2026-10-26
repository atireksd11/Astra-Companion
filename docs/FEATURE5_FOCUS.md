# Features 5, 6, 7 — Focus on who said “Hey Astra”

One **focus session** covers:

- **5** — Ignore other people talking (SpeechBrain **ECAPA** match on the whole clip).
- **6** — Playback loudness follows how quiet/loud **you** sound vs your wake clip.
- **7** — Wake to arm; **barge-in** stops playback when you talk over Astra.

Feature 4 (denoise) still only removes steady background hum/fan noise.

## Enable

In `server/config.json`:

```json
"steps": ["denoise", "focus", "stt", "cadence", "pronunciation", "echo"],
"focus": {
  "enabled": true,
  "wake_phrase": "hey astra",
  "wake_model": "hey_jarvis",
  "wake_threshold": 0.5,
  "session_timeout_s": 90,
  "embedding": "ecapa",
  "min_similarity": 0.40,
  "min_enroll_s": 3.0,
  "wake_min_speech_ms": 500,
  "lock_owner": true,
  "owner_speaker_id": "",
  "min_gain": 0.45,
  "max_gain": 1.8,
  "firmware_volume_cap": 0.55
}
```

Restart `python bridge.py`. Bridge prints `focus=ON`.

## Owner voiceprint (enroll first)

Run once (~1 minute):

```powershell
cd "C:\The XyZ Plan\Astra Companion"
.\scripts\ENROLL-VOICE.ps1
```

That saves **4–8 ECAPA clips** and a **mean embedding** in `astra.db`. Wake phrase only **arms** the session; it does not replace that voiceprint.

Legacy one-shot wake enroll is disabled when `require_owner_enroll: true`.

## Owner lock

- After enrollment, you are **owner** (`is_owner: true`, 192-d mean + clip bank).
- With **`lock_owner: true`**, later wake turns **verify** the wake window against the owner; a friend saying “Hey Jarvis” does **not** replace the owner vector.
- **Enter-only wake** (laptop) is blocked when an owner already exists — use the wake phrase.
- **Legacy 13-d MFCC** rows are ignored for verify; with `lock_owner`, a wake turn cannot overwrite them — re-enroll after clearing or migrating the profile.
- **Robot / always-listening clients**: if a valid owner profile exists, the bridge **auto-arms** focus on connect (no `wake` meta required on every turn). After **session timeout**, say the wake phrase again (laptop sends `wake_b64` separately from the sentence).

Set `ASTRA_DB` to isolate the SQLite file in tests or multi-instance setups.

## Laptop test

1. Enable focus as above; install deps (`server/requirements.txt`).
2. `python laptop_voice.py`
3. **Asleep** → say **“Hey Jarvis”** (stand-in) or press **Enter** only on **first** setup (no owner yet).
4. Wake audio (~0.5 s+) is sent as **`wake_b64`**; then speak your sentence; stay quiet **2 s** at the end.
5. Bridge logs `transcript:` when STT is on; echo plays fully (`Finished playing.`).
6. Further sentences within **90 s** need no wake phrase; after timeout, wake again.

Custom wake: drop `server/models/hey_astra.onnx` (preferred over `hey_jarvis`).

## Robot

Bridge sends `{"type":"volume","firmware_vol":…}` before reply PCM and `{"type":"stop"}` on barge.

## Protocol

- Hello: `focus.wake_ready`, `focus.session_timeout_s`, `focus.min_enroll_s`, `stt.enabled`, `vad` (client Silero)
- Start meta: `wake: true`, `wake_b64` (+ `wake_speech_ms`), or legacy `enroll_b64` / `enroll_speech_ms`
- Done: `focus`, `volume`, `transcript`, optional `barged`

## Other people in the room (echo still has chatter?)

| Layer | What it does |
|-------|----------------|
| **RNNoise (Feature 4)** | Fan/hum only — **not** other voices. |
| **Focus gate** | Rejects clips that are mostly **not you**. |
| **Owner mask (`mask_other_voices`)** | After you pass the gate, the bridge **mutes** ~0.55 s windows that do not match your ECAPA print. Echo/STT see less bleed from people talking **before/after** or between your words. |
| **Hard limit** | Two people **at the same instant** on one mic cannot be separated without a heavy neural separator. Overlap may still leak; echo may sound **choppy** (silence where others were dropped). |

If the clip is mostly other speech: bridge returns **`too_mixed`** — wait for a quieter moment or press **Enter** right when **you** finish.

Config (in `focus`): `mask_other_voices`, `max_mixed_ratio`, `min_owner_keep_ratio`.

## Known limits

- **Hey Jarvis** is the default openWakeWord model until **hey_astra.onnx** exists.
- Cannot fully unmix simultaneous talkers on a **mono** mic.
- Stereo robot + DOA can gate by direction later; laptop mic has no aim.
