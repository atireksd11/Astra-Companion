# Development guide

How the **Astra-Companion** repo is organized, how firmware modules fit together, and what to work on **this week** (audio + basic comms).

Audio, Wi-Fi, the voice bridge, and wheel aim are in the firmware now. Use [VOICE_SETUP.md](VOICE_SETUP.md) and [FEATURE3_DOA.md](FEATURE3_DOA.md). Copy `firmware/include/secrets.h.example` to `secrets.h`. The week-by-week checklist below is the original bring-up plan, not a list of missing files.

**Two GitHub repos:** PCB/firmware here; Week 2 mechanics in [Astra-Companion-Cad](https://github.com/atireksd11/Astra-Companion-Cad). Different Half Life projects — do not point both at one repo.

---

## Repository map (this workspace)

```text
Astra Companion/                    ← main repo (you are here)
├── README.md                       Project hub, tier table, quick links
├── JOURNAL.md                      Half Life devlog mirror (sync overwrites)
├── BOM.md                          Half Life parts mirror (sync overwrites)
├── BOM.csv                         Half Life CSV mirror (PCB tier)
├── .gitignore
│
├── docs/
│   ├── README.md                   Index of documentation
│   ├── DEVELOPMENT.md              This file — structure + weekly focus
│   ├── PINOUT.md                   GPIO / nets from KiCad netlist
│   ├── CAD.md                      Chassis notes (copy also on CAD repo)
│   ├── HALF_LIFE.md                Upload checklist Week 1 vs Week 2
│   └── images/
│       ├── pcb-render.png
│       └── cad-*.png               Renders for README / grants
│
├── cad/
│   ├── README.md                   STEP file description
│   └── astra-companion-chassis-assembly.step
│
├── hardware/
│   ├── README.md                   Which BOM file to import when
│   ├── astracompanion/             KiCad 10 — schematic + PCB
│   ├── bom.csv                     Week 1 Half Life import (PCB parts)
│   ├── bom-cad.csv                 Duplicate of mechanical BOM (CAD repo is canonical for Week 2)
│   ├── BOM2.md                     Schematic reference (not for HL import)
│   ├── BOM.md                      Local extended BOM notes
│   ├── BOM_SUMMARY.md              Tier 2 money / tax notes
│   ├── BOM_CAD_SUMMARY.md          Tier 1 money notes
│   ├── BOM_NEEDS_PRICE.md          Pointer to summaries
│   ├── generated/
│   │   └── astracompanion.xml      Exported netlist (regenerate after sch changes)
│   └── src/
│       └── .gitkeep                Gerbers land here after clean DRC plot
│
└── firmware/
    ├── platformio.ini              Board, libs, build flags
    ├── README.md                   Build, layout, safety
    ├── include/
    │   ├── pins.h                  Single source of GPIO constants
    │   ├── balance.h
    │   ├── ui.h
    │   ├── audio.h
    │   └── net.h
    └── src/
        ├── main.cpp                Boot, tasks, serial CLI only
        ├── balance.cpp             Core 0 — IMU + PID + motors
        ├── ui.cpp                  Core 1 — displays + eye queue
        ├── audio.cpp               I2S mic/amp (implement this week)
        └── net.cpp                 Wi-Fi / HTTP (implement this week)
```

### Category cheat sheet

| Area | Purpose | Change when |
|------|---------|-------------|
| **Root mirrors** | Half Life sync | Edit on Half Life site, pull to refresh |
| **docs/** | Human docs, pinout, process | Any architecture / week plan |
| **cad/** | Mechanical export for convenience | New Fusion STEP export |
| **hardware/** | KiCad + BOM + fab outputs | Schematic, layout, Gerbers |
| **firmware/** | All runtime software | Features, audio, Wi-Fi |

---

## Firmware architecture (current + target)

### Already implemented

| Module | Core / context | Responsibility |
|--------|----------------|----------------|
| `main.cpp` | setup + loop | Init order, serial commands, `audioPoll` / `netPoll` |
| `balance.cpp` | **Core 0**, pri 4 | 200 Hz IMU, filter, PID, DRV8833, fall → worried eyes |
| `ui.cpp` | **Core 1**, pri 2 | GC9A01 SPI, eye states, buttons (HW caveat on UP/SELECT) |
| `audio.cpp` | stub | Boot log only |
| `net.cpp` | stub | Boot log only |

### Target data flow (this week)

```text
INMP441 ──I2S RX──► audio.cpp (capture ring buffer)
                         │
                         ├──► net.cpp (HTTPS / WebSocket upload)  [later step]
                         │
MAX98357 ◄──I2S TX── audio.cpp (tone / playback buffer)

Wi-Fi ──► net.cpp ──► connected flag, minimal HTTP GET (health check)

Core 0: balance unchanged — do not block with Wi-Fi or heavy audio DSP
Core 1: ui unchanged — no new animations this week
loop(): netPoll(), audioPoll(), serial
```

### Suggested API growth (implement in headers as you go)

**`audio.h`**

- `audioInit()` — I2S duplex: BCLK/LRCK shared, mic DIN, amp DOUT (`pins.h`)
- `audioStartCapture()` / `audioReadSamples(int16_t* buf, size_t n)`
- `audioPlayTone(freq, ms)` or `audioPlayBuffer(...)` for bring-up
- Optional: FreeRTOS task on Core 1 at lower priority than balance

**`net.h`**

- `netInit()` — `WiFi.mode`, connect with credentials from `secrets.h` (gitignored) or compile flags
- `netIsConnected()`
- `netPoll()` — reconnect backoff, non-blocking
- `netHttpGet(url, callback)` — thin wrapper for first API test

**Do not add yet:** SD logging, VL53, RTC, fuel gauge, encoder tasks, cloud streaming assistant, wake word.

---

## This week — scope guardrails

### Touch first (in order)

1. **`firmware/include/pins.h`** — confirm I2S pins vs [`PINOUT.md`](PINOUT.md) after any PCB edit.
2. **`firmware/src/audio.cpp`** + **`audio.h`** — I2S init, mic read, speaker beep; serial command `beep` or `mic level`.
3. **`firmware/platformio.ini`** — only if you add libs (e.g. no extra lib needed for ESP-I2S Arduino API).
4. **`firmware/src/net.cpp`** + **`net.h`** — Wi-Fi join, print IP, one HTTPS request; keep stack off Core 0.
5. **`firmware/src/main.cpp`** — wire new serial commands; keep orchestration thin.
6. **`docs/PINOUT.md`** — update only if nets change.

### Stabilize but do not expand

| File | Rule |
|------|------|
| `balance.cpp` | Bugfixes only; no new features on Core 0 |
| `ui.cpp` | Keep four eye states; no animation engine |
| `hardware/astracompanion/*` | PCB fixes only if audio pins are wrong; no “full redesign” |
| `cad/`, `bom-cad.csv` | Week 2 done — sync via CAD repo |

### Ignore this week

- New KiCad peripherals (SD, ToF bring-up code)
- Servo / RGB / encoders in firmware
- Fancy eye graphics or LVGL
- Full voice assistant pipeline (record → after Wi-Fi works → one-shot upload)
- Root `JOURNAL.md` / `BOM.md` except Half Life copy-paste

---

## Step-by-step — structure the workspace *right now*

### Step 1 — One hour: repo hygiene (done once)

- [x] Firmware split into modules (see `firmware/README.md`).
- [x] Remove stray files (`hardware/src/Untitled` deleted).
- [ ] `git pull` / push main when ready; CAD work stays on **Astra-Companion-Cad**.
- [ ] Regenerate `hardware/generated/astracompanion.xml` from KiCad after schematic changes.

### Step 2 — Audio bring-up (days 1–2)

1. Implement `audioInit()` — 16 kHz or 48 kHz, 32-bit slot, verify shared clock to mic + amp.
2. Serial: `audio test` → 1 kHz tone on speaker (low volume).
3. Serial: `mic rms` → print RMS from INMP441 for a few seconds.
4. Document sample rate and wiring in `firmware/README.md`.

### Step 3 — Network skeleton (days 2–3)

1. Add `firmware/include/secrets.h.example` + gitignore `secrets.h` (Wi-Fi SSID/pass).
2. `netInit()` connect; `netPoll()` in loop.
3. Log `WiFi.localIP()`; optional `net ping` serial command → HTTPS GET to a known endpoint.

### Step 4 — Thin integration (day 4+)

1. Record N ms to PSRAM buffer in `audio.cpp`.
2. POST to a stub endpoint from `net.cpp` (or save for next week if time-boxed).
3. Map **one** eye state via existing `uiSetEyeState(EyeState::awake)` on connect — no new enum values required yet.

### Step 5 — Parallel (hardware)

- Bench-test **+3V3**, **+5V**, amp enable before loud playback.
- PCB: only if I2S lines are unrouted or wrong net.

---

## Related repo (not in this folder)

```text
Astra-Companion-Cad/
├── BOM.csv / hardware/bom-cad.csv
├── cad/astra-companion-chassis-assembly.step
├── docs/images/
└── JOURNAL.md          (Week 2 Half Life project)
```

Link from README; do not duplicate large STEP changes in both repos without syncing.
