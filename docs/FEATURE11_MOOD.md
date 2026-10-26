# Feature 11 — Coarse mood

Astra keeps a **coarse cue** for how a line sounded: happy, sad, angry, neutral, or surprised. Each score includes a confidence. This is not a clinical mood assessment and it does not diagnose anyone.

The scorer is an **acted-speech** wav2vec2 emotion model (`wav2vec2_ser_int8`, INT8 ONNX). Acted corpora do not match a quiet room, so a low score stays unlabeled. The pipeline still answers. This model is often uncertain, and it can call anger sadness. That is a limit of these weights, not a reason to replace them.

## Labels

The model emits eight raw classes:

| Raw | Coarse label |
|---|---|
| ANG | angry |
| HAP | happy |
| SAD | sad |
| NEU | neutral |
| SUR | surprised |
| CAL | neutral, only when it wins and clears both gates below |
| DIS | dropped (not folded into angry) |
| FEA | dropped (not folded into sad) |

`notes["mood"]` is `{label, confidence, backend, raw_label}`. `label` is null when the winner is disgust, fear, under 0.70 confidence, or the top-two softmax gap is under 0.15. `raw_label` still names the winner when the net ran.

## When it runs

Mood sits **after stt** and **before cadence**. It reads `turn.pcm_for_analysis`, or `pcm_in` if focus has not set an analysis buffer. It does not read `pcm_pre_denoise`.

Clips are capped at **6.0 s** from the start (96000 samples at 16 kHz). A configured `max_seconds` above 6, or a value that is missing, zero, or not a positive number, still cuts at 6 seconds. The length check runs after that cut: under **0.8 s** the net does not run, `backend` is `too_short`, confidence is 0, and the profile is not written.

Waveforms match the wav2vec2 preprocessor: int16 divided by 32768, then zero mean and unit variance.

## Profile

The owner profile stores a **5-way distribution** under `doc["mood"]`, starting uniform at 0.2. A kept label blends with `p = 0.9 * p + 0.1 * one_hot(label)`. This is not `speech_profile.ema()` — that helper treats a stored 0 as “unset” and would wipe a class that correctly has no mass.

Also stored: `last_label`, `last_confidence`, `updated_at`, `samples`.

The blend runs only when **all** of these are true:

- `should_learn_turn(turn)` is true
- antispoof action is missing or `allow` (not `soft`, not `hard`)
- the turn has no `turn.error` (focus and hard spoof already stop the pipeline)
- focus is on and the resolved profile is the owner (`is_owner`), using the same speaker resolve as cadence
- the coarse label is one of the five, the raw winner is the one that maps to that label, confidence is at least 0.70, and the softmax gap is at least 0.15
- the confidence floor, the margin floor, and the blend weight are finite numbers. A NaN or negative floor does not count as "passed." The blend weight has to sit in 0 to 1 so a class cannot go negative
- antispoof, when present, is an object whose action is missing or `allow`. A string or other shape is not `allow`

Focus off, or no owner profile: measure the turn, do not write. Hard spoof sets `turn.error` in antispoof, so mood never runs. Soft spoof can still be scored and is not stored. When focus masks other voices, mood scores that masked buffer (`pcm_for_analysis`), not the unmasked clip echo may still play.

## Fail-open

Missing `models/speech_emotion_int8.onnx`, or an ONNX session that fails to load: `backend` is `unavailable`, label null, confidence 0, no profile write, no `turn.error`.

Any other runtime failure: `backend` is `wav2vec2_ser_int8_error: ExceptionName`, same null result, pipeline continues.

Hello reports `mood.ready` from the file existing on disk. The session loads on the first scored turn. CPU only.

Weights: [onnx-community/Speech-Emotion-Classification-ONNX](https://huggingface.co/onnx-community/Speech-Emotion-Classification-ONNX) `onnx/model_int8.onnx`, saved as `server/models/speech_emotion_int8.onnx`.
