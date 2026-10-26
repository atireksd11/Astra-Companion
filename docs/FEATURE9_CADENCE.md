# Feature 9 — Speech cadence & fillers

Astra tracks **how you talk**: energy peaks per second (pace proxy), pauses inside a sentence, and filler words when a **real transcript** exists.

## Enable

```json
"cadence": { "enabled": true, "min_pause_ms": 200, "fillers": ["uh", "um", "er"] }
```

With focus off, cadence still runs on trimmed mono audio. With focus on, timing uses audio **before** focus splices frames (so dropped chatter is not counted as stutter).

## What you see

Bridge `done` JSON may include:

```json
"cadence": { "peaks_per_s": 4.2, "pause_ms_median": 350, "pause_count": 2 },
"speaker_id": "spk_a1b2c3d4"
```

Console: `cadence: peaks=…/s median_pause=…ms`

## Fillers

Counts update only from `turn.notes["transcript"]` or a future STT step. Placeholder `[audio 1.2s]` is **ignored**.

## Learning rules

Profiles skip updates when: clip &lt; 0.8 s, low SNR, heavy `mixed_ms` from focus, or `enroll_contaminated`. Updates use a slow EMA so one bad clip does not reset you.

## Limits

- Peaks per second is **not** words per minute.
- Robot still needs the bridge (or a future cloud bridge) online to learn.

See [FEATURE8_PRONUNCIATION.md](FEATURE8_PRONUNCIATION.md) for shared profile storage.
