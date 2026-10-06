# Astra Companion

desktop robot that balances on two wheels and talks.

hack club onboard / hacklife, tier 2 ($65). custom 2-layer pcb this week.

the board is a carrier. ESP32-S3 DevKit v1 plugs into headers. motors, gyro, mic, speaker, round lcd, battery stuff all live on the pcb and connect with jst / headers so its not a rats nest.

## whats on it

- **brain:** ESP32-S3 DevKit v1 (core 0 = balance, core 1 = wifi/voice)
- **balance:** GY-521 MPU6050 on i2c
- **wheels:** DRV8833 + 2x N20 6V motors + 12mm rubber wheels
- **eyes:** GC9A01 1.28" round ips, 240x240, spi
- **voice:** INMP441 mic + MAX98357A amp + treedix 8ohm speaker
- **power:** 18650, TP4056 usb-c charger, MT3608 boost to ~6V for motors, AMS1117-3.3 for the chips

schematic-as-code is [`astracompanion.ato`](astracompanion.ato). real easyeda files go in `hardware/` once i actually draw it.

## repo

```
astracompanion.ato    # full netlist spec (start here)
hardware/             # easyeda, gerbers, bom
firmware/             # later, platformio
cad/                  # later, fusion body
docs/                 # pinout, checklist, notes
extrude/              # dogfooding later, ignore for now
```

## this week

pcb. schematic, layout, gerbers, jlcpcb cart. 2hrs a day.

pinout is in [`docs/PINOUT.md`](docs/PINOUT.md). parts in [`hardware/BOM.md`](hardware/BOM.md).

## later weeks

cad the body, print it, solder, pid, then the voice api. eyes are the round lcd now, not the tiny oled i originally wrote down.

## license

mit
