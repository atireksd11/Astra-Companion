# Library test script (Features 1–9)

**Bring:** headphones, laptop mic allowed in Windows privacy settings.

**Config:** `server/config.json` — full stack (denoise, focus, STT, cadence, pronunciation, echo).

**Install once (same Python as `python bridge.py`):**
```powershell
cd "C:\The XyZ Plan\Astra Companion\server"
python -m pip install -r requirements.txt
```

## Start (two windows)

**Window 1 — bridge (leave open):**
```powershell
cd "C:\The XyZ Plan\Astra Companion"
python bridge.py
```
Wait for: `denoise=ON focus=ON stt=ON cadence=ON pronounce=ON`

**Window 2 — you:**
```powershell
cd "C:\The XyZ Plan\Astra Companion"
python laptop_voice.py
```

---

## Spoken checklist (prebuilt stack)

| # | You do | Success = |
|---|--------|-----------|
| 1 | Stay **quiet 10 s** after connect | No `Captured` lines |
| 2 | **“Hey Jarvis”** → full sentence → **2 s silence** | Bridge `transcript:` matches speech; full echo; `Finished playing.` |
| 3 | Second sentence **without** wake (within 90 s) | Listens and echoes |
| 4 | Wait **past 90 s**, speak with no wake | Stays asleep until **Hey Jarvis** or Enter |
| 5 | No ONNX / no openWakeWord | **Enter** still wakes; same echo behavior |

**Wake enroll:** first turn needs **~3 s of speech** in the clip (not the old 0.8 s timer).

**End-of-sentence:** Silero VAD + `UtteranceGate` — stay quiet **2 s** when done.

---

## Optional steps

| Step | You do | Success = |
|------|--------|-----------|
| Pause | *“Hello”* … **1 s** … *“still one sentence”* → 2 s silence | One echo; optional `Pause…` |
| Denoise | Same sentence twice with library hum | `denoise: rnnoise snr … -> … dB` |
| Cadence | Natural rhythm + fillers | `cadence: peaks=…` |
| Volume | Whisper vs normal | `volume: gain=` |

**Skip in the library:** second-person “not your voice”, direction (needs robot or `doa_sim.py`).

Quick automated check:
```powershell
cd server
python -m pytest tests/ -q
```

---

## If something breaks

| Message | Fix |
|---------|-----|
| Cannot reach ws://… | Start Window 1 `python bridge.py` |
| asleep | Hey Jarvis or Enter, then speak |
| enroll_too_short | Speak ~3 s on wake turn |
| not your voice | Wake again; only you talk |
| too short / no speech | Louder; sentence ≥ ~1 s |
| busy | Wait or restart bridge |
