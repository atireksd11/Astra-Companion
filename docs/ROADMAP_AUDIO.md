# Voice feature roadmap (16 items)

Build order and where each piece runs. Details in the audio Stage 1 plan.

| # | Feature | Stage |
|---|---------|-------|
| 1 | Mic in / speaker out | 1 |
| 2 | Size limits + trim + segment stats (bridge); 2 s pause still same sentence | **Done (laptop)** |
| 3a | Start/stop detection (listener) | 1 |
| 3b | Sound direction + aim (GCC-PHAT, stereo upload) | **In progress** — see [FEATURE3_DOA.md](FEATURE3_DOA.md) |
| 4 | Background noise reduction (bridge denoise step) | **Done (laptop)** — see [FEATURE4_NOISE.md](FEATURE4_NOISE.md) |
| 5 | Your-voice-only filter (with focus session) | **Done (laptop v1)** — [FEATURE5_FOCUS.md](FEATURE5_FOCUS.md) |
| 6 | Loudness-based playback gain | **Done (laptop v1)** — same doc |
| 7 | Wake + barge-in stop | **Done (laptop v1)** — [FEATURE5_FOCUS.md](FEATURE5_FOCUS.md). Known limits: [AUDIT_FEATURES_1-7.md](AUDIT_FEATURES_1-7.md) |
| 8 | Pronunciation & custom words | **Done (laptop v1)** — [FEATURE8_PRONUNCIATION.md](FEATURE8_PRONUNCIATION.md) |
| 9 | Cadence, pauses, fillers | **Done (laptop v1)** — [FEATURE9_CADENCE.md](FEATURE9_CADENCE.md) |
| 10 | Deepfake detection | **Done (laptop v1)** — see [FEATURE10_ANTISPOOF.md](FEATURE10_ANTISPOOF.md) |
| 11 | Mood | **Done (laptop v1)** — [FEATURE11_MOOD.md](FEATURE11_MOOD.md) |
| 12 | Intent | **Done (laptop v1)** — [FEATURE12_INTENT.md](FEATURE12_INTENT.md) |
| 13 | Personality | **Done (laptop v1)** — persona prompt, not a separate step. [FEATURE13_PERSONALITY.md](FEATURE13_PERSONALITY.md) |
| 14 | Multi-language | **Done (laptop v1)** — [FEATURE14_LANGUAGE.md](FEATURE14_LANGUAGE.md) |
| 15 | Cross-language emotion | **Done (laptop v1)** — [FEATURE15_CROSSLANG_EMOTION.md](FEATURE15_CROSSLANG_EMOTION.md) |
| 16 | Safety filter | **Done (laptop v1)** — [FEATURE16_SAFETY.md](FEATURE16_SAFETY.md) |

## Later — conversation quality (post–Stage 5)

Not started; order can shift after robot bring-up.

| Theme | Goal |
|-------|------|
| **Live knowledge** | Tool step before/after LLM (web search / Context.dev or similar), inject snippets into `build_context`, Groq still speaks the answer |
| **Latency** | STT model tier, parallel steps where safe, streaming TTS, keep Piper warm (partially done) |
| **Listening UX** | Raise `max_clip_s`, longer `merge_gap_ms` / `end_silence_ms` so 1–2 s thinking pauses do not end the clip; optional “still listening” cue |
| **Voice** | Cuter / more natural TTS (Piper voice swap, Kokoro, or small cloud voice with cache); prosody tied to mood |
| **True “Hey Astra” wake** | Train or ship `server/models/hey_astra.onnx`; retire `hey_jarvis` stand-in ([AUDIT_FEATURES_1-7.md](AUDIT_FEATURES_1-7.md)) |
