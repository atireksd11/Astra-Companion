# Astra Companion — parts

hacklife also mirrors a copy at the repo root (`BOM.md`). that one gets overwritten on sync so this is the list i actually keep.

budget: tier 2, $65. pcb fab eats a lot of that.

| qty | part | what it does | ~$ |
| --- | --- | --- | --- |
| 1 | ESP32-S3 DevKit v1 | brain. 16MB flash, 8MB psram, usb on the kit | 6 |
| 1 | GY-521 MPU6050 | gyro/accel, i2c, so it can stay upright | 2 |
| 1 | DRV8833 dual h-bridge | pwm the two motors | 2 |
| 2 | N20 6V micro metal gearmotors | the wheels | 8 |
| 2 | 12mm rubber wheels | grip | (w/ motors) |
| 1 | GC9A01 1.28" round IPS 240x240 | the eye, spi | 5 |
| 1 | INMP441 i2s mic | listen | 2 |
| 1 | MAX98357A i2s amp | talk | 2 |
| 1 | Treedix mini 8Ω speaker (JST-PH1.25) | actual sound | 3 |
| 1 | 3.7V 18650 cell | battery | 3 |
| 1 | 18650 holder | so it isnt taped on | 1 |
| 1 | TP4056 USB-C charger module | charge the cell | 1 |
| 1 | MT3608 boost | battery -> ~6V for motors | 1 |
| 1 | AMS1117-3.3 LDO | 6V -> 3.3V for chips | 0.50 |
| 1 | 100µF electrolytic | bulk on the motor rail | 0.20 |
| 6 | 0.1µF ceramic | decoupling next to ics | 0.30 |
| 2 | 4.7kΩ resistors | i2c pullups | 0.10 |
| 1 | USB-C connector (or just use the tp4056 one) | charging | 0.50 |
| 4 | JST-PH 2-pin | battery, speaker, 2 motors | 1 |
| 2 | female header rows | so the devkit can unplug | 1 |
| 5 | 2-layer PCB from jlcpcb + shipping | the actual board | ~20 |

total is around $55 if shipping doesnt explode. leave a few bucks for extra caps/headers.

not on the pcb (cad later): 3d printed body, screen bezel, motor mounts.

dont put the 6V boost into the devkit 5V pin. 3.3V pin only. i will fry it if i mix those up.
