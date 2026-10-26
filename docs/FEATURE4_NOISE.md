# Feature 4 — Background noise reduction

The laptop **cleans** each utterance after trim and direction-finding (if stereo). Fans, keyboard hiss, and traffic get quieter so echo and future speech-to-text hear **you**, not the room.

**Not in this feature:** removing “um/uh”, blocking other people’s voices (Feature 5), or canceling the robot’s own speaker echo (future AEC).

## How it works

```text
trim + VAD  →  DOA (stereo only)  →  denoise (mono)  →  echo / STT
```

Denoise runs on the **bridge** only, not on the ESP32.

## Turn it on

Copy settings from `server/config.example.json` into your local `server/config.json`:

```json
"steps": ["denoise", "echo"],
"denoise": {
  "enabled": true,
  "backend": "rnnoise",
  "strength": 0.5
}
```

Restart `python bridge.py`.

- **`backend`: `"rnnoise"`** — default for the prebuilt stack; one denoiser on the bridge (recommended on **Python 3.14**).
- **`backend`: `"auto"`** — picks RNNoise when `pyrnnoise` is installed; otherwise no-op.
- **`backend`: `"deepfilter"`** — optional **DeepFilterNet3** (heavier; see below).
- **`strength`**: 0–1. Scales how aggressively the chosen backend suppresses noise. Very low values behave like a light pass; `0` or `"noop"` skips processing.

Hello JSON includes `"denoise": {"enabled": …}` so clients know the setting.

## Dependencies

**Default path (Python 3.14):**

```powershell
cd server
pip install -r requirements.txt
```

`requirements.txt` lists **`pyrnnoise`** (RNNoise bindings). No spectral gate and no WebRTC noise suppressor.

**Optional DeepFilterNet3 (Python 3.11 venv):**

DeepFilterNet often needs an older Python and PyTorch stack. Use a separate venv if your main bridge runs on 3.14:

```powershell
py -3.11 -m venv .venv-dfn
.\.venv-dfn\Scripts\Activate.ps1
pip install deepfilternet torch torchaudio
```

Run the bridge from that venv only when you set `"backend": "deepfilter"`. Otherwise stay on the 3.14 + `pyrnnoise` environment.

## What you see

Bridge console after a turn:

```text
denoise: rnnoise snr 12.3 -> 18.1 dB
```

`done` JSON may include:

```json
"utterance": {
  "noise": { "snr_db": 18.1, "noise_floor_rms": … },
  "denoise": { "backend": "rnnoise", "snr_before_db": …, "snr_after_db": … }
}
```

## Laptop test

1. `python bridge.py`
2. Enable denoise in `config.json` as above.
3. `python laptop_voice.py` — talk with a fan or AC on; compare with `"enabled": false`.

## Robot

Same bridge path. Robot sends stereo for DOA; denoise downmixes to mono before echo.

## Limits (known gaps)

- **Steady** noise (fan, AC, hum) is what RNNoise handles best. Sudden bangs, keyboard clicks, and **other people talking** are not reliably removed.
- If denoise is enabled but no backend is available, the clip may pass through unchanged (`noop` / bypass).
- You only need `"enabled": true` — if `"denoise"` is missing from `steps` or listed after `"echo"`, the bridge **fixes order** at startup and prints a `config:` warning.
- Denoise does **not** replace a good mic or room setup; it cleans the clip you already captured.
