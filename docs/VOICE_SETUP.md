# Voice setup — easy steps

Do these in order. One box = one thing to do.

## A. Laptop (once per session)

1. Open PowerShell.
2. Paste each line, press Enter after each:

```powershell
cd "C:\The XyZ Plan\Astra Companion"
python bridge.py
```

3. Wait until you see **`bridge ready`**. Leave this window open.

4. Find your laptop IP: run `ipconfig` and copy **IPv4** (example `192.168.1.50`).

## B. Robot secrets (once ever)

1. In folder `firmware\include`, copy `secrets.h.example` to **`secrets.h`**.
2. Edit `secrets.h`:
   - `WIFI_SSID` = your Wi‑Fi name  
   - `WIFI_PASSWORD` = your Wi‑Fi password  
   - `BRIDGE_HOST` = laptop IPv4 from step A4  
   - `BRIDGE_PORT` = `8765`

## C. Flash the robot (when firmware changes)

1. Plug ESP32-S3 with USB.
2. PowerShell:

```powershell
cd "C:\The XyZ Plan\Astra Companion\firmware"
pio run -t upload
pio device monitor
```

3. On boot you should see **PSRAM** size about **8388608** (or similar big number).

## D. Test sound on the robot (serial monitor)

Type these in the monitor (one at a time):

| Command | What should happen |
|---------|-------------------|
| `beep` | Quiet tone from speaker |
| `mic` | Numbers jump when you talk (5 seconds) |
| `record` | Records ~3 s |
| `play` | Plays it back |
| `wifi` | Shows IP if Wi‑Fi OK |
| `listen on` | Always-on listening armed |
| `status` | Listener + Wi‑Fi line |

Talk after `listen on`. If Wi‑Fi and bridge are good, you hear your voice echoed back (same as the laptop test).

## E. If something fails

| Problem | Fix |
|---------|-----|
| Port already in use | Bridge already running — good. Or `taskkill /PID … /F` from the message. |
| No Wi‑Fi | Check `secrets.h`, 2.4 GHz Wi‑Fi, SSID/password |
| No echo | Laptop firewall: allow port **8765**; same Wi‑Fi; `BRIDGE_HOST` correct |
| Silent speaker | Check amp 5 V, wiring; try `volume 0.3` then `beep` |
| Mic always 0 | Mic wiring; try `beep` first to confirm upload worked |

## F. Direction (two mics)

Laptop voice cannot tell left from right. Follow the steps in [FEATURE3_DOA.md](FEATURE3_DOA.md): wire MK2, then the test ladder. Keep the wheels **off the desk** the first time you type `motors on`.
