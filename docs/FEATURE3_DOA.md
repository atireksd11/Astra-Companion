# Feature 3 — Hear you, find you, turn toward you

The robot has two ears. The laptop brain notices when you start talking, checks which ear heard you first, then the robot turns after the echo finishes.

**v1 turn:** N20 wheels (whole body). Type `head on` only if you want the SG90 on GPIO5 to aim instead.

**One laptop mic cannot do this.** `python laptop_voice.py` will always say direction was not measured.

## Wire the second ear (MK2)

The board only has MK1. Add one more INMP441 on wires. See also the MK2 row in `hardware/BOM2.md`.

| INMP441 pin | MK1 (on the board) | MK2 (wires) |
|-------------|--------------------|-------------|
| VDD | 3.3 V | 3.3 V |
| GND | GND | GND |
| SCK | GPIO45 | same wire |
| WS | GPIO48 | same wire |
| SD | GPIO46 | same wire |
| L/R | GND (left ear) | 3.3 V (right ear) |

Put the mic centers about **40 mm** apart. If the shared SD wire floats, add a **100 kΩ** resistor from SD to GND.

If the robot turns the wrong way, set `kSwapStereoChannels` to `true` in `firmware/include/audio_config.h` and flash again. Then set `doa.offset_deg` (below).

## Laptop brain

1. Copy `firmware/include/secrets.h.example` to `firmware/include/secrets.h`.
2. Put your Wi-Fi name, password, and the laptop's IPv4 in `BRIDGE_HOST`. Port stays `8765`.
3. Start the bridge from the repo root: `python bridge.py`.
4. Flash: `cd firmware` then `pio run -t upload` and `pio device monitor`.

Direction math lives in `server/core/doa.py`. **Positive degrees means the voice is to the robot's left.** The wheels turn left for a positive angle. Both the bridge and the robot ignore a guess weaker than **0.20** confidence.

## Test ladder (do these in order)

| Step | What you do | You pass when |
|------|-------------|---------------|
| 1 | Flash with `secrets.h`, bridge running | Serial shows Wi-Fi IP and `bridge connected` |
| 2 | Type `beep`, `record`, `play` | You hear the speaker |
| 3 | Type `mic` and talk on the left, then the right | Level jumps. After MK2 is on, both ears must have sound (not one silent ear) |
| 4 | Say a sentence | Bridge prints `utterance ok` and the robot echoes you |
| 5 | `python doa_sim.py --synthetic --angle 25 --bridge` | Printed `aim` is close to the expected angle |
| 6 | Stand at a known side. Record or watch `doa:` on the bridge. Run `python tools/doa_calibrate.py --wav clip.wav --true-deg 30` from `server/` | Put the printed `offset_deg` in `server/config.json` and restart the bridge |
| 7 | Type `motors on` with **wheels off the desk**. Speak from the left, then the right | After the echo, Serial shows `aim: yaw` and the wheels twitch toward you |

`motors on` with wheels on the desk can fall over. The turn turns balance off for about 1.5 seconds.

## Head servo (optional, off by default)

GPIO5 is the SG90 header. Wheels are the default. Type `head on` to aim the head instead. Type `head off` to use the wheels again. If the head faces the wrong way, flip `kInvert` in `firmware/src/servo.cpp`.

## Fake direction test (no robot)

```powershell
cd "C:\The XyZ Plan\Astra Companion"
python bridge.py
python doa_sim.py --synthetic --angle 25 --bridge
```

That plays a fake stereo tone. It does not use your room microphone.
