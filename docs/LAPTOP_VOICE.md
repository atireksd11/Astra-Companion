# Talk with your laptop (no robot)

Use your **PC microphone** and **speakers** with the same helper the robot will use later. Right now the helper **echoes** your voice back.

You do **not** need Wi‑Fi settings, USB, or the ESP32.

## One-time install

Open PowerShell:

```powershell
cd "C:\The XyZ Plan\Astra Companion\server"
pip install -r requirements.txt
```

If the mic is wrong, list devices:

```powershell
python tools/laptop_voice.py --list-devices
```

(Pick defaults in Windows **Settings → System → Sound** if needed.)

## Every time you want to try it

**Window 1 — start the helper** (leave open):

```powershell
cd "C:\The XyZ Plan\Astra Companion"
python bridge.py
```

Wait for **`bridge ready`**.

**Window 2 — talk**:

```powershell
cd "C:\The XyZ Plan\Astra Companion"
python laptop_voice.py
```

1. It says **Listening…**
2. **Speak** a sentence.
3. A pause of about **1 second** still counts as the same sentence. You will see `Pause… still listening`. Stop for about **2 seconds** when you are really done.
4. You should **hear yourself** back from the speakers (echo).
5. The client prints **Speech: echoed …s** (trim + VAD). Noise-only clips are rejected with `no clear speech`.

**Not the same as direction testing:** `python doa_sim.py --synthetic --bridge` sends a **fake** stereo tone (no mic). Use `laptop_voice.py` for real voice.

One sentence only, then quit:

```powershell
python tools/laptop_voice.py --once
```

## If it fails

| Problem | What to do |
|---------|------------|
| Cannot reach ws://… | Window 1: run `python bridge.py` |
| Port already in use | Bridge already running — use window 1, skip starting another |
| No sound back | Check Windows output volume; try headphones |
| Mic never picks up | Windows mic privacy: allow Python; speak louder |
| `No module named sounddevice` | Run `pip install -r requirements.txt` in `server` |

When this works, the robot path is the same helper — only the ears/mouth move from laptop to Astra.

## Features 8–9 (how you talk / pronunciation)

Optional. See [FEATURE9_CADENCE.md](FEATURE9_CADENCE.md) and [FEATURE8_PRONUNCIATION.md](FEATURE8_PRONUNCIATION.md). Enable `"cadence"` / `"pronunciation"` in config (default off). Profiles save in `server/astra.db`.

## Features 5–7 (focus / volume / interrupt)

Optional. See [FEATURE5_FOCUS.md](FEATURE5_FOCUS.md). Enable `"focus": {"enabled": true}` in config, restart bridge. Laptop simulates wake with **Enter** until you add `server/models/hey_astra.onnx`.

## Feature 4 (background noise)

Optional bridge cleanup before echo. Off by default; see [FEATURE4_NOISE.md](FEATURE4_NOISE.md). Enable in `server/config.json`:

```json
"steps": ["denoise", "echo"],
"denoise": { "enabled": true, "backend": "auto", "strength": 0.5 }
```

Restart `python bridge.py`. With a fan or AC on, echo should sound cleaner; the bridge may log `denoise: rnnoise snr … -> … dB` (backend name matches your `denoise.backend` setting).

## Feature 2 (limits + trim)

- Pauses up to about **2 s** end silence still counts as one clip (see bridge `hello` limits).
- Silence-only / too-brief clips → bridge says **`too short`** (no echo).
- Over **15 s** → **`too long`**.
- Quiet parts at the **start and end** are trimmed before echo.

```powershell
cd server
python -m pytest tests/ -v
python tools/report.py
```

Check **`trim_saved_s`** in the report.
