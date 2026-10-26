# TTS — Piper voice

When `tts` is in the pipeline, `echo` is not. The step speaks `text_out` with Piper (`piper-tts`), voice `en_US-lessac-medium`, `length_scale` 1.0.

Weights, if missing, download to `server/models/`:

- `en_US-lessac-medium.onnx`
- `en_US-lessac-medium.onnx.json`

Audio is resampled to 16 kHz mono PCM16. Focus echo gain (`apply_gain_pcm16`) is not applied.

Hello reports `tts.ready` when the onnx file is on disk. If the file is missing or `PiperVoice.load` fails, `text_out` stays the reply, `turn.error` is `tts_unavailable`, and `notes["tts"]` is `{available: false, reason: "tts_unavailable"}`. There is no beep and no espeak fallback.

Refusals and the canned offline line leave `turn.error` unset so Piper speaks them when the weights exist. The done message includes `reply`. A `tts_unavailable` error includes `reply` and `notes.tts` when that note is present. The laptop prints `Astra: {reply}` and a line that the voice is unavailable.

No API key means the model step returns `I can't reach my online voice right now.` and TTS speaks that line when the weights exist.
