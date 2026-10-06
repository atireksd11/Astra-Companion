# Astra Companion — parts

hacklife also mirrors a copy at the repo root (`BOM.md`). that one gets overwritten on sync so this is the list i actually keep.

tier 2 is $65 and thats for the pcb + electronics they let you order. screws, filament, iron, etc you probably already have or scrounge. still listing them because you cannot finish the robot without them.

dont put 6V into the devkit 5V pin. 3.3V pin only.

---

## 1. electronics (on / plugged into the pcb)

| qty | part | what it does | ~$ |
| --- | --- | --- | --- |
| 1 | ESP32-S3 DevKit v1 | brain. 16MB flash, 8MB psram | 6 |
| 1 | GY-521 MPU6050 | gyro/accel, i2c | 2 |
| 1 | DRV8833 dual h-bridge (breakout) | pwm the two motors | 2 |
| 2 | N20 6V micro metal gearmotors | wheels | 8 |
| 2 | 12mm rubber wheels (N20 hub) | grip. get ones that actually fit the d-shaft | (w/ motors) |
| 1 | GC9A01 1.28" round IPS 240x240 | the eye, spi | 5 |
| 1 | INMP441 i2s mic | listen | 2 |
| 1 | MAX98357A i2s amp | talk | 2 |
| 1 | Treedix mini 8Ω speaker (JST-PH1.25) | actual sound | 3 |
| 1 | 3.7V 18650 **protected** cell | battery. unprotected cells + cheap tp4056 = bad time | 3 |
| 1 | 18650 holder | so it isnt taped on | 1 |
| 1 | TP4056 USB-C charger **with protection** (DW01) | charge the cell | 1 |
| 1 | MT3608 boost | battery -> ~6V for motors | 1 |
| 1 | AMS1117-3.3 LDO (module is fine) | 6V -> 3.3V for chips | 0.50 |
| 1 | SPDT slide switch | on/off between battery and boost. otherwise you yank the jst | 0.30 |
| 1 | polyfuse ~1.5A | on the battery so a short doesnt cook the cell | 0.20 |
| 1 | 470µF electrolytic (or 220µF min) | motor rail bulk. 100µF is thin for two n20s reversing | 0.30 |
| 1 | 100µF electrolytic | extra bulk on 6V / ldo input | 0.20 |
| 2 | 10µF electrolytic or tantalum | AMS1117 in + out. datasheet wants these | 0.20 |
| 8 | 0.1µF ceramic | 6 next to ics + 1 across each motor | 0.40 |
| 2 | 4.7kΩ resistors | i2c pullups | 0.10 |
| 1 | ~100kΩ resistor | MAX98357A gain pin, skip if the breakout already has it | 0.05 |
| 1 | USB-C on the TP4056 is enough | carrier doesnt need a second usb-c | — |
| 4 | JST-PH 2-pin + pigtails | battery, speaker, 2 motors | 1 |
| 1 | 8-pin header (male/female) | GC9A01. not a 2-pin jst | 0.20 |
| 1 | female header 2×22, 2.54mm | ESP32-S3 DevKit v1. not two random strips | 1 |
| bunch | male/female 2.54mm headers | GY-521, DRV8833, mic, amp, tp4056, mt3608, ldo | 1 |
| 5 | 2-layer PCB from jlcpcb + shipping | the board | ~20 |

pcb + electronics lands around $55–60 if you already own headers/wire. grant will not cover the iron.

---

## 2. mechanical

| qty | part | what it does |
| --- | --- | --- |
| ~200g | PLA or PETG filament | body, motor brackets, wheel hubs, screen bezel |
| 4 | M3 6mm screws | pcb onto chassis standoffs |
| 4 | M3 standoffs | pcb height |
| 4 | M3 screws + nuts (or heat-set inserts) | n20 motor brackets |
| 4 | M2 or M1.6 screws | n20 motors themselves, they are tiny |
| 2 | set screws / proper N20 wheel hubs | if the 12mm wheels dont press-fit the shaft |

---

## 3. wiring + consumables

| qty | part | what it does |
| --- | --- | --- |
| 1m | silicone wire 26–28 AWG | motor terminals to jst pigtails |
| 1 | USB-C cable | flash the devkit + charge tp4056 |
| pack | heat shrink | motor and speaker joints |
| — | solder (rosin core) | headers, connectors, passives |

---

## 4. tools (not grant parts, you still need them)

| thing | why |
| --- | --- |
| soldering iron | headers, jsTs, passives |
| wire strippers | silicone wire |
| multimeter | **check 3.3V and 6V before the esp32 goes in** |
| breadboard + dupont wires | week 3 gyro test, before the pcb is back |
| hex / screwdriver for M3 | chassis |

---

## skip unless it gets painful later

- N20s with encoders (imu-only can balance, encoders just make pid nicer)
- MP1584 buck instead of AMS1117 if the ldo runs too hot
- ferrite bead on 3.3V
- extra 18650
