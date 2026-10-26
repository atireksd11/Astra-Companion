# Astra laptop bridge

Your robot will send little voice clips to this program on your laptop. The laptop answers (right now it just repeats the clip back, like an echo).

## One-time setup

```powershell
cd server
pip install -r requirements.txt
```

You do **not** need Supabase. History is saved in **`astra.db`** on this folder (created automatically).

## Run the bridge (terminal 1)

```powershell
cd server
python bridge.py
```

Wait until you see **`bridge ready on ws://127.0.0.1:8765`**.  
If you see **port already in use**, you already have a bridge running — close that window, or run the `taskkill` line it prints, then try again.

Use a different port if you want:

```powershell
python bridge.py --port 8766
```

## Test without the robot (terminal 2)

Run **one command per line** (do not paste lines together):

```powershell
cd server
python tools/make_test_wav.py tools/test-tone.wav
python tools/sim_robot.py tools/test-tone.wav
python tools/report.py
```

You should get `tools/test-tone-echo.wav` and one row in the report.

If the bridge uses another port:

```powershell
python tools/sim_robot.py tools/test-tone.wav ws://127.0.0.1:8766
```

## Firewall

Port **8765** (or the port you chose) must be allowed on your home Wi‑Fi when the real robot connects.
