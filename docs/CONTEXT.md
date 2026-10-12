# Astra Companion — full project context

> Drop this file into a new chat when you need the whole story.
> Last updated: 2026-10-05 (Mon night, KiCad schematic in progress).

---

## 1. What this is

**Astra Companion** = a 2-wheeled self-balancing desktop AI robot.

It sits next to a desk, balances on two N20 motors, has a round LCD “eye”, listens on a mic, talks on a speaker, WiFi to cloud STT → LLM → TTS.

**Hack Club:** On-Board / **Half Life** (halflife.hackclub.com), **Tier 2, $65 grant**.

**This week (Week 1) is only the PCB.** Not the 3D body, not firmware, not Extrude AI. A first custom board with motors + boost + I2S is *not* a 4-hour job. CAD of the full frame is **not** this week unless Gerbers are already out.

**Extrude AI** = later. LLM hardware-design harness. Astra is the dogfood board. Ignore until the PCB is ordered.

**Architecture:** custom **2-layer carrier PCB**. **ESP32-S3 DevKit v1 plugs into female headers.** Modules (gyro, DRV8833, mic, amp, charger, boost, LDO) plug in via headers/JST. Not a bare ESP32 chip on the board.

**Do NOT put 6V on the DevKit 5V pin.** 3.3V pin only.

---

## 2. Who / where

- Builder: Atirek (GitHub `atireksd11`)
- Local folder: `C:\The XyZ Plan\Astra Companion`
- GitHub: https://github.com/atireksd11/Astra-Companion
- Branch: `main`
- Half Life project id (in JOURNAL/BOM comments): `cmuvgfgnh00a901q9t8ie3rrb`
- KiCad: **10.0** on Windows
- Editor: Cursor

---

## 3. Repo layout

```
astracompanion.ato          # full wiring spec (atopile-style, not compiled)
BOM.md                      # Half Life sync — GETS OVERWRITTEN
JOURNAL.md                  # Half Life sync — GETS OVERWRITTEN. don’t type here
hardware/BOM.md             # real parts list — keep this one
hardware/README.md
hardware/src/               # export kicad/gerbers here later
hardware/astracompanion/    # likely KiCad project (or hardware/*.kicad_*)
docs/PINOUT.md
docs/BLUEPRINT.md
docs/BUILD_CHECKLIST.md
docs/CONTEXT.md             # this file
firmware/ README stub
cad/ README stub
extrude/ README stub
README.md
```

Half Life overwrites root `BOM.md` and `JOURNAL.md`. Personal checklist = `docs/BUILD_CHECKLIST.md`. Hours go on the **Half Life website**, not only in git.

---

## 4. Locked hardware (full robot, not just chips)

### Electronics (carrier + modules)

| Qty | Part | Role |
| --- | --- | --- |
| 1 | ESP32-S3 DevKit v1 (16MB flash, 8MB PSRAM) | Brain. Core 0 = PID balance, Core 1 = WiFi/voice |
| 1 | GY-521 MPU6050 | I2C gyro/accel |
| 1 | DRV8833 dual H-bridge | PWM motors |
| 2 | N20 6V gearmotors + 12mm N20-hub wheels | Drive |
| 1 | GC9A01 1.28" round IPS 240×240 SPI | Eye (not the old SSD1306 OLED) |
| 1 | INMP441 I2S mic | Listen |
| 1 | MAX98357A I2S amp | Talk |
| 1 | Treedix mini 8Ω speaker JST-PH1.25 | Sound |
| 1 | 18650 **protected** 3.7V + holder | Battery |
| 1 | TP4056 USB-C charger **with protection (DW01)** | Charge |
| 1 | MT3608 boost | ~6V for motors |
| 1 | AMS1117-3.3 | 6V → 3.3V for chips |
| 1 | SPDT/SPST slide switch | On/off |
| 1 | Polyfuse ~1.5A | Battery short |
| 1 | 470µF electrolytic | Motor-rail bulk (100µF alone is thin) |
| 1 | 100µF electrolytic | Extra bulk |
| 2 | 10µF | AMS1117 in + out |
| 8 | 0.1µF ceramic | Decoupling + 1 across each motor |
| 2 | 4.7kΩ | I2C pull-ups |
| 1 | ~100kΩ | MAX98357A gain if not on breakout |
| 4 | JST-PH 2-pin + pigtails | Battery, speaker, 2 motors |
| 1 | 8-pin header | GC9A01 |
| 1 | Female header **2×22**, 2.54mm | DevKit |
| bunch | 2.54mm headers | All the breakout modules |
| 5 | 2-layer PCB JLCPCB + shipping | The board (~$20) |

### Mechanical / wiring / tools (grant may not pay)

PLA or PETG; 4× M3 6mm + 4× M3 standoffs (PCB); 4× M3 for motor brackets; M2/M1.6 for N20s; silicone 26–28 AWG; USB-C cable; heat shrink; solder; iron; strippers; **multimeter — check 3.3V and 6V before the ESP32 goes in**; breadboard for week 3 gyro test.

Skip unless it hurts later: N20 encoders, MP1584 buck instead of AMS1117, ferrite, extra cell.

---

## 5. Power tree

```
USB-C → TP4056 → 18650 (protected)
                    → polyfuse → slide switch → MT3608 → 6V → DRV8833 VM
                                                         → AMS1117 → 3.3V → DevKit 3V3, gyro, mic, amp, LCD, DRV logic, I2C pull-ups
```

Amp on 3.3V (less motor hash in the speaker). Flashing = USB-C **on the DevKit**. Carrier TP4056 USB-C = charge only.

---

## 6. Pinout (ESP32-S3 DevKit v1) — do not invent a second map

| Function | GPIO | Goes to |
| --- | --- | --- |
| I2C SDA | 8 | MPU6050 SDA |
| I2C SCL | 9 | MPU6050 SCL |
| SPI SCLK | 12 | GC9A01 SCL |
| SPI MOSI | 11 | GC9A01 MOSI |
| LCD CS | 10 | GC9A01 CS |
| LCD DC | 13 | GC9A01 DC |
| LCD RST | 14 | GC9A01 RST |
| LCD BL | 21 | GC9A01 backlight |
| I2S BCLK | 15 | mic + amp BCLK |
| I2S WS | 16 | mic + amp WS |
| I2S SD in | 17 | INMP441 SD |
| I2S SD out | 18 | MAX98357A DIN |
| AIN1 / AIN2 | 4 / 5 | DRV8833 left |
| BIN1 / BIN2 | 6 / 7 | DRV8833 right |

Avoid USB pins 19/20 and strapping pins. I2C pull-ups 4.7k to 3.3V. DRV8833 nSLEEP tied high (3.3V).

Canonical copy: `docs/PINOUT.md`. Wiring spec: `astracompanion.ato`.

---

## 7. Firmware (later — not this week)

FreeRTOS dual-core:

- **Core 0:** MPU6050 100–200 Hz, PID, DRV8833 PWM. Never waits on WiFi.
- **Core 1:** WiFi, INMP441 → Whisper STT, LLM JSON `{text, emotion, gesture}`, TTS → MAX98357A, GC9A01 eyes. Gestures = small PID pitch offset (nod/spin).

Wake word idea: “Hey Astra”.

---

## 8. HackLife / hours (read this)

**Week 1 deliverable:** unique PCB, Gerbers, schematic PDF, design sources, JLCPCB cart screenshot (5 pcs, FR-4, 1.6 mm). ~17 hours logged before they care about the grant.

**Journal vs Timelapse (Lapse):** there is **no official “timelapse = more points”**. Reviewers **trust** a Lapse more, so those hours get **approved** more easily. Journal hours still count if screenshots match the time; fluffy/AI journals get hours **cut**.

Runtime-style PCB programs say: journal **or** Lookout/Lapse, **both is better**.

**Half Life entry UI:** hours field **or** attach a Lapse. If you only attach a 24-min Lapse, that’s all that session counts.

**Practice every work block:**

1. Start **Lapse** *before* KiCad/Cursor  
2. Do the day’s one job  
3. Stop Lapse  
4. Short journal + 2 screenshots + attach that lapse  

**Already happened Mon 2026-10-05:** week 1 video published; `.ato` + BOM + pinout + GitHub; planning. Lapse only caught ~24 min later. **That missed time = Journal entry with screenshots of GitHub/ato/BOM/KiCad**, honest hours (e.g. 2 or 2.5), **don’t** submit the 24-min clip as the whole session.

Don’t log idle chat time. Log sitting-and-working time. Half hours like `2.5`.

---

## 9. Why KiCad (and what failed)

Need **Gerbers** for JLCPCB. KiCad 10 (or EasyEDA) produces them.

`astracompanion.ato` is a **spec**, not a compiled board. Modules are interfaces, not JLCPCB footprints.

Atopile on this PC:

- `pip install atopile` on Python 3.14 failed (`zstd` needs MSVC Build Tools)
- `uv tool install atopile` installed **old** `ato 0.2.69`
- `atopile==0.15.9` also failed on `zstd`

**Do not rabbit-hole atopile this week.** Draw the circuit in KiCad by hand from the pinout/BOM.

**Correct KiCad order:** Schematic **first** → **Tools → Update PCB from Schematic (F8)** → then outline, place, route, DRC, Gerbers.

Someone started Edge.Cuts on an empty PCB first (other-agent script). That’s later. **Schematic Editor now.**

KiCad 10 traps (learned the hard way):

- Bottom status bar (`grid 0.5000 mm`) is **not clickable**. Grid = **top toolbar** dropdown, or right-click canvas → Grid, or `n` / `N`.
- **No** `Place → Graphic Rectangle`. Draw rectangle = **right toolbar** square icon, or **Ctrl+Shift+L** (lines), **Ctrl+Shift+P** (polygon).
- Click-click to draw; **click-drag is a selection box** and draws nothing.
- Big pink frame = **paper / title block**, not the board. Board = smaller closed shape on **Edge.Cuts**.
- Add schematic part: **A** (Place → Symbol). Wire: **W**. Power port: **P**. Edit: **E**.

EasyEDA is a valid backup if KiCad keeps blocking. Same Gerbers at the end.

---

## 10. Board size

**55×55 mm is too small** (DevKit alone is ~48×28 mm). Use **80×60 mm** (or 70×70). 2-layer, 1.6 mm FR-4. 4× M3 holes, **3.2 mm drill**, **3.5 mm in from each corner** (at 80×60: 3.5/3.5, 76.5/3.5, 3.5/56.5, 76.5/56.5). Footprint: `MountingHole_3.2mm_M3`.

Place later: DevKit center; motors/DRV8833/JST **bottom**; LCD header **top**; gyro near MCU not next to motors; mic/amp on a side; power near battery JST. Fat traces on 6V/motors. GND pour. DRC before fab.

---

## 11. This week (2 hours/day, no breaks in the block)

Must finish: schematic → ERC → PCB place → route → DRC → `gerber.zip` + `schematic.pdf` + JLCPCB cart screenshot.

CAD of the pretty shell = **only if Gerbers are already out**. Then: import real outline, motor mounts + LCD hole. Not Fusion art.

| Day | Job |
| --- | --- |
| **Mon 10/5** | KiCad project + start **power schematic only**. (Outline can wait.) |
| **Tue** | Finish power: battery → fuse → switch → TP4056 → MT3608 6V → AMS1117 3.3V + caps. |
| **Wed** | DevKit 2×22 header + MPU6050 I2C GPIO 8/9 + 4.7k pull-ups. 3V3 pin only. |
| **Thu** | DRV8833 + motor JSTs (GPIO 4–7); I2S mic/amp (15–18); GC9A01 8-pin (SPI). ERC. |
| **Fri** | F8 update PCB. Place parts. Holes + 80×60 outline if not done. |
| **Sat** | Route. GND pour. DRC. |
| **Sun** | Gerbers, cart screenshot, export sources to `hardware/src/`. Buffer / start CAD only if sent. |

If a day slips, continue that row. Don’t route before the schematic is wired.

**Do not this week:** full enclosure, firmware, PID, voice APIs, Extrude, ordering without Gerbers.

---

## 12. 10-week HackLife shape (after PCB)

| Week | Theme |
| --- | --- |
| 1 | PCB (this file’s focus) |
| 2 | CAD parts: hubs, motor mounts, bezel |
| 3 | Gyro on breadboard, complementary filter |
| 4 | Display (GC9A01 eyes, not OLED) |
| 5 | Full enclosure CAD |
| 6 | PCB assemble, meter 3.3V/6V |
| 7 | 3D print |
| 8 | Motors in chassis, DRV8833 |
| 9 | WiFi + voice APIs + eyes |
| 10 | Final assemble, JOURNAL, demo video, 3D printer reward |

---

## 13. WHERE WE ARE RIGHT NOW (2026-10-05 ~22:00)

**Done in git (pushed):**

- Repo, README, blueprint, pinout, checklists
- `astracompanion.ato` full carrier spec (switch, fuse, caps, LCD header, gain resistor, JSTs)
- `hardware/BOM.md` electronics + mechanical + tools
- Week 1 video published on Half Life

**Done on disk (KiCad 10), may not all be committed:**

- Project `astracompanion` (under `hardware/` or `hardware/astracompanion/`)
- PCB editor: played with Edge.Cuts; possible stray segment; paper border is not the board. **Stop PCB for now.**
- Schematic Editor **open**. Placed:

  | Ref | Value | Symbol |
  | --- | --- | --- |
  | J1 | BAT | `Connector:Conn_01x02` |
  | F1 | 1.5A | `Device:Fuse` |
  | SW1 | PWR | `SW_SPST` or similar 2-pin switch |

- **Next schematic click:** U1 = `Connector:Conn_01x04`, Value `TP4056`, to the right of SW1. Then same pattern: U2 Conn_01x04 `MT3608`; U3 Conn_01x03 `AMS1117`; C1 470uF, C2 100uF, C3/C4 10uF `Device:C`; **P** for `GND`. Then wire with **W**:

```
J1 pin1 → F1 → SW1 → MT3608 VIN
USB / TP4056 ↔ battery
MT3608 VOUT → 6V → AMS1117 IN
AMS1117 OUT → 3.3V
470uF+100uF on 6V–GND
10uF on LDO in, 10uF on LDO out
```

Do **not** add ESP32, gyro, motors, mic, LCD **tonight**. Power column only.

**Tonight’s lock-in was 21:30–23:30.** If still in that window: finish placing power symbols + save + screenshot + journal. 23:30 close KiCad even if unwired.

---

## 14. How to talk to the builder in KiCad

He is new. **Do not** say “grid 1 mm bottom bar” or “Place → Graphic Rectangle”.

For each part: Press A → search exact string → click library:name → OK → click to place → Esc → E → Reference / Value → OK → Ctrl+S.

One component per message if he’s stuck. Confirm with a screenshot before jumping.

---

## 15. Git / commits (recent)

- `6d1ffa9` Initial scaffold
- Half Life sync `BOM.md` / `JOURNAL.md`
- `830bb9a` Complete ato netlist, pinout, docs
- `367b885` Expand BOM (fasteners, switch, fuse, caps, tools)

KiCad files may still be **uncommitted**. When schematic has the power chain, commit `*.kicad_pro` `*.kicad_sch` `*.kicad_pcb` (and `-backups` is gitignored). Don’t commit secrets.

---

## 16. What “done” means for Week 1

- [ ] Power + MCU + gyro + motors + I2S + LCD on schematic, ERC sane
- [ ] PCB 80×60 (or 70×70), 4 M3 holes, parts placed
- [ ] Routed, GND pour, DRC clean enough to fab
- [ ] `gerber.zip`, `schematic.pdf`, sources in `hardware/src/`
- [ ] JLCPCB 5× FR-4 1.6 mm, `cart.png`
- [ ] Hours on Half Life (Lapse + short journal)

Then week 2 CAD from the **real** board outline.
