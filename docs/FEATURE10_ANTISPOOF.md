# Feature 10 — Deepfake soft gate

The bridge scores each utterance **before denoise**, on the raw 16 kHz PCM16. Denoise strips the vocoder artifacts AASIST-L looks for, so the score has to see the uncleaned mic.

`spoof_score` is in `[0, 1]`. **Higher means more spoof-like.** It is a soft score from AASIST-L (class 0 = spoof). It is not a yes/no ID of the speaker. Focus still decides whether the voice is the owner.

## What it does

| `spoof_score` | What happens |
|---|---|
| model missing, silence, or below 0.80 | **allow** — pipeline continues, `raise_verify` is 0 |
| `>= 0.80` and not a hard reject | **soft** — no `turn.error`. This turn only, focus adds `raise_verify` (default 0.08) to the owner-verify thresholds. The global `FocusConfig` is not changed. |
| `>= 1.0` (saturated), model loaded, clip is at least 1.0 s, and self-echo did **not** fire | **hard** — `turn.error = "spoof_suspected"` and the turn stops |

Clips shorter than 1.0 s are tiled up to the model's 64600-sample window. Those short pads are not reliable, so they are never hard-rejected. A soft score on them can still tighten the owner check.

Self-echo means the mic resembles audio this session actually sent to the speaker in the last 30 seconds (absolute Pearson correlation, best lag 0–400 ms, on the loudest 1.0 s of that playback). If the mic is shorter than the template plus the lag, the overlapping piece still counts when at least 0.5 s lines up, so a delayed copy on a one-second clip is not dropped. Older playback is ignored, so a stale clip cannot hide a later hard score. **Self-echo never hard-rejects.** If the model score would have been hard and echo fires, the turn is downgraded to soft. `echo_cosine` is not part of that vote.

## What it does not detect

AASIST-L was trained as a 2019 logical-access countermeasure (TTS and voice-conversion traces in the waveform). A high score is a hint. It does **not** reliably detect:

- **Replay** — a phone or speaker in the room playing a recording
- **Modern clones** — recent zero-shot voice clones outside that training set
- a real person imitating the owner

Those still depend on the owner-voice check. A high score only makes that check stricter, unless the clip is a confident model hit with no self-echo.

## Fail-open

If `models/AASIST-L.pth` is missing, the sha256 does not match the pinned file, or the load fails, the backend is `aasist_l_unavailable`, `spoof_score` is null, the action is allow, and the rest of the pipeline runs. The echo check still runs. Hello reports `antispoof.ready` from the file existing on disk. The model loads on the first scored turn, not during hello.

## Echo cosine

v1 uses correlation only. Comparing speaker embeddings would load ECAPA on every turn, before focus has an embedding. `echo_cosine` is in config for later. It is not a vote yet.

## Calibrate

From `server/`:

```powershell
python tools/calibrate_antispoof.py your_voice.wav known_spoof.wav
python tools/calibrate_antispoof.py take.wav --playback last_reply.wav
```

Read `spoof_score` on your own voice and on clips you consider spoofs. p50 / p95 / p99 print when you pass more than one file. Hard defaults to 1.0. On this pinned checkpoint, studio speech (LJ Speech at 16 kHz) scored as high as 0.99999, and gaussian noise near speech loudness scored about 0.98, so a 0.97 gate would drop ordinary audio. A hard reject is a saturated score. Soft (0.80) only raises the owner match for that turn.

Weights: `server/models/AASIST-L.pth` (AASIST-L from the NAVER AASIST repo, MIT). The bridge does not train and does not run the upstream trainer.
