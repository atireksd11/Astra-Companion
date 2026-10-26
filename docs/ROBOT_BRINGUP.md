# Robot and bridge bring-up

Use this checklist the first time you connect the ESP32 to the laptop bridge, or after you change Wi-Fi, auth, or firmware networking code.

## What you need

Same Wi-Fi for laptop and robot. USB cable for flash. `firmware/include/secrets.h` (never commit it). Python env with server dependencies installed. Optional: health on port 8766 if enabled in `server/config.json`.

## 1. Prepare secrets.h

Copy `firmware/include/secrets.h.example` to `firmware/include/secrets.h`.

Set `WIFI_SSID` and `WIFI_PASSWORD` to your 2.4 GHz network.

Set `BRIDGE_HOST` to the laptop IPv4 from `ipconfig`.

Set `BRIDGE_PORT` to `8765` unless you changed the bridge.

If `security.require_auth` is true in config, set `BRIDGE_TOKEN` to the same value as `ASTRA_AUTH_TOKEN` in your `.env`.

Leave `BRIDGE_USE_TLS` at `0` for local Wi-Fi unless you have TLS set up on the bridge.

## 2. Start the bridge on the laptop

```powershell
cd "C:\The XyZ Plan\Astra Companion\server"
python bridge.py
```

Wait for `bridge ready`. Leave the window open.

If port 8765 is blocked, allow it in Windows Firewall for private networks.

Optional health check when `health.enabled` is true:

```powershell
curl http://127.0.0.1:8766/health
```

You should see JSON with `"ok": true`.

## 3. Flash firmware

```powershell
cd "C:\The XyZ Plan\Astra Companion\firmware"
pio run -t upload
pio device monitor
```

On boot look for Wi-Fi IP and `net: bridge connected`. If you see `no secrets.h`, go back to step 1.

## 4. Sanity on serial

Run `beep`, then `wifi`, then `listen on`. Talk to the robot. With bridge running you should get a spoken reply after the utterance ends.

For laptop-only testing without hardware, use `python tools/laptop_voice.py` from the `server` folder with the same bridge running. See [VOICE_SETUP.md](VOICE_SETUP.md).

## 5. Robot actions (Phase 6)

Ensure `robot.enabled` is true in `server/config.json`. Owner must be verified (focus or wake) for actions to appear in `done`.

Trigger a stop intent as the enrolled owner. In the serial monitor you should see `net: action stop_playback` when the bridge sends actions in the done message.

To preview JSON the firmware expects:

```powershell
cd server
python tools/robot_contract_check.py --pretty
```

## Common errors

**Wi-Fi failed.** Wrong SSID or password, or phone hotspot using 5 GHz only. Use 2.4 GHz.

**Bridge disconnected or no echo.** `BRIDGE_HOST` is not the laptop IP, firewall blocks 8765, or bridge is not running.

**Auth rejected.** Token in `secrets.h` does not match `ASTRA_AUTH_TOKEN`.

**No actions in done.** Owner not verified, `robot.enabled` false, or antispoof blocked the turn. Check bridge logs.

**Playback never stops on stop intent.** Re-flash after Phase 6 firmware; confirm actions in done JSON via `robot_contract_check.py` and enroll owner per [VOICE_SETUP.md](VOICE_SETUP.md).

## Next

Direction of arrival and wheels: [FEATURE3_DOA.md](FEATURE3_DOA.md). Phase 6 test script: `scripts/RUN-PHASE6-TESTS.ps1`. Feature summary: [FEATURE19_PHASE6.md](FEATURE19_PHASE6.md).
