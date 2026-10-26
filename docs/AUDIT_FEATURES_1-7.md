# Audit — voice features 1 through 9

Features 8–9 add `speaker_profiles` in `astra.db`, cadence/pronunciation pipeline steps, and strip `enroll_b64` from turn notes. **STT** (`faster-whisper tiny`) is on the bridge when enabled in config; cadence fillers use the transcript. See [FEATURE8_PRONUNCIATION.md](FEATURE8_PRONUNCIATION.md) and [FEATURE9_CADENCE.md](FEATURE9_CADENCE.md).

---

# Audit — voice features 1 through 7 (original pass)

Reviewed against the code in `firmware/` and `server/` (laptop is the testbed; the robot shares the same bridge). Each item is either **fixed in this pass** or an **accepted limit** (needs hardware, a trained model, or a later feature).

## Fixed in this pass

| # | Feature | Problem | What we changed |
|---|---------|---------|-----------------|
| 1 | 1 | After the robot spoke, cooldown ended **as soon as the mic got loud**. The speaker tail opened a new clip of Astra’s own echo. | [`firmware/src/listener.cpp`](../firmware/src/listener.cpp) now waits out the full cooldown. |
| 2 | 7 | Barge-in only counted while the bridge was still **sending** bytes. On localhost that window is a few milliseconds; the speaker is still playing after `done`. | Bridge keeps a barge window for the length of the clip plus 0.5 s and sends `{"type":"stop"}`. |
| 3 | 7 | Laptop interrupt watched the mic but **did not stop** `sounddevice` playback, and one loud frame (often the speakers) was enough. | [`server/tools/laptop_voice.py`](../server/tools/laptop_voice.py) stops playback after ~300 ms of speech. |
| 4 | 1–7 | A crash inside a turn left `busy` true, so every later sentence got `busy`. | [`server/bridge.py`](../server/bridge.py) always clears `busy` when the turn ends, and sends `internal` on a crash. |
| 5 | 1 | Firmware parsed JSON with `strstr` on a buffer that is **not guaranteed to end with a zero**. | [`firmware/src/net.cpp`](../firmware/src/net.cpp) copies the text and adds a terminator. |

## Accepted limits (not bugs we can close in software alone)

| # | Feature | Limit | Why it stays |
|---|---------|-------|----------------|
| 6 | 3 | Direction needs **two mics**. A laptop mic reports no aim. | Physics. Use `doa_sim.py` or the robot. |
| 7 | 3 | Azimuth is coarse at a 40 mm mic spacing. | Geometry. Wide ±35° gate in focus on purpose. |
| 8 | 4 | Denoise quiets **steady** noise (fan, hum). It does not remove other people. | RNNoise / DeepFilterNet cannot unmix voices. Feature 5 is the voice filter. |
| 9 | 5 | Two people talking **at the same instant** are not separated. Overlap is dropped and the echo can sound choppy. | Needs a neural separator. Out of scope. |
| 10 | 5 | Focus uses **SpeechBrain ECAPA** (192-d). Similar voices and very short clips can still be wrong. Wake enroll needs **~3 s** of speech. Old 13-d MFCC profiles in DB are ignored. | Cosine gate **0.40** (not the old 0.72 MFCC threshold). |
| 11 | 5 | A new “Hey Astra” **replaces** who we follow. | Last wake wins, by design. |
| 12 | 6 | “Distance” is **how loud you sound** versus the wake clip, clamped. A whisper is not a measured meter value. | No ranging sensor. |
| 13 | 7 | **Hey Astra** ONNX is not in the repo. Laptop uses openWakeWord **`hey_jarvis`** until `server/models/hey_astra.onnx` exists; **Enter** remains fallback. | Custom wake training is a separate task. |
| 14 | 7 | The **robot mic is muted while Astra talks** (half duplex). The robot will not interrupt itself. The laptop can, with headphones. | Industry note: without acoustic echo cancellation, an open mic during playback treats the speaker as a person and stops itself in a loop. Headphones, or mute-while-speaking, are the safe choices until AEC exists. |
| 15 | 7 | Laptop barge can still false-trigger if the speakers are loud and the mic hears them for ~300 ms. | Same missing AEC. Use headphones. |
| 16 | 4 | Denoise needs **`pyrnnoise`** (or optional DeepFilterNet in a 3.11 venv). If missing, the bridge **passes audio through** (`noop`). | Run `pip install -r server/requirements.txt` on a fresh machine. |

## How to re-check

```powershell
cd "C:\The XyZ Plan\Astra Companion\server"
python -m pytest tests/ -q
```

Laptop, focus off (features 1–4): `python bridge.py` then `python laptop_voice.py`.

Focus on (features 5–7): set `"focus": {"enabled": true}` in `server/config.json`, restart the bridge, press Enter to wake, use headphones if you try interrupt.
