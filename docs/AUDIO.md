# Audio and voice (Astra Companion)

Plain-language design notes. Stage 1: always-on listener on the robot, echo bridge on the laptop.

## Protocol v1

- Robot → laptop on connect: `{"type":"hello","proto":1,"fw":"…"}`
- Laptop → robot: `{"type":"hello","proto":1,"limits":{…},"denoise":{"enabled":false,"backend":"auto"}}` (Feature 4)
- Start of speech: `{"type":"start","rate":16000,"meta":{"noise":…,"level":…,"vol":…}}`
- Binary chunks: 640 bytes = 20 ms @ 16 kHz mono PCM16
- End: `{"type":"end"}`
- Reply: binary chunks, then `{"type":"done","utterance":{…,"noise":…,"denoise":…}}` (noise/denoise when enabled) or `{"type":"busy"}` / `{"type":"error","reason":"…"}`

Unknown JSON fields are ignored on both sides.

## Robot modules

- `audio.cpp` — I2S mic and speaker (Stage 1A)
- `listener.cpp` — always-on gate and utterance detection
- `net.cpp` — Wi-Fi and WebSocket

## Safety

- Default volume 0.2
- Half-duplex: mic ignored while speaking + 400 ms cooldown
- Max utterance 15 s

See [ROADMAP_AUDIO.md](ROADMAP_AUDIO.md) for the 16-feature order.
