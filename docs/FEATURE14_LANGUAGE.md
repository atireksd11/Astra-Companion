# Feature 14 — Multi-language (Phase 4)

Whisper faster-whisper can detect language when `stt.auto_language` is true and `stt.model` is **not** a `*.en` checkpoint.

- Detected code is stored on the turn as `notes["language"]` and on `done` as `language`.
- `notes["stt"]["gate_lang"]` is used for TTS, LLM reply language, and English-only learning gates. If `language_probability` is below `stt.min_language_prob`, gates fall back to English while the raw detection is still logged.
- Piper voice: map ISO codes in `tts.voices` (e.g. `"es": "models/es_ES-sharvard-medium.onnx"`). Missing voices fall back to `tts.weights` with `notes["tts"]["fallback"]`.
- English-only: pronunciation CTC learn, filler counts, and pronunciation hints in the context builder are skipped for non-English turns.

Live laptop must use a multilingual model (`medium`, not `medium.en`) or Hindi transcripts stay wrong.
