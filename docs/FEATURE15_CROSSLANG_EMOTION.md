# Feature 15 — Cross-language emotion (Phase 4)

Mood still uses the English-trained `speech_emotion_int8.onnx` wav2vec2 SER model on raw audio (no transcript language input).

- Scoring runs for all languages when `mood.score_non_en` is true (default).
- Owner mood EMA updates from non-English clips are **off** by default (`mood.learn_non_en: false`) so English-acted labels do not drift the profile.
- When `learn_non_en` is enabled, profile blends require `mood.non_en_min_confidence` (default 0.85).
- Low-confidence labels remain `uncertain` in the client view — same as Feature 11.

SenseVoice or other LID+SER stacks are optional later; they are not required for Phase 4.
