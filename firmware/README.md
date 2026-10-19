# Firmware

PlatformIO + Arduino-ESP32. Pin numbers are copied from the KiCad netlist in [`docs/PINOUT.md`](../docs/PINOUT.md). Chassis and N20 mounting: [`docs/CAD.md`](../docs/CAD.md).

## What it actually runs

- **Core 0, priority 4.** 200 Hz MPU-6050 read, gyro bias subtracted, complementary filter, PID, DRV8833. Motors stay off until the serial command `motors on`.
- **Core 1, priority 2.** Both GC9A01 displays on one SPI bus, one chip-select at a time. Redraws only when the eye state changes.
- **Arduino loop.** Reads serial commands. It does not run the balance math.

Audio, the fuel gauge, the RTC, the distance sensor, and the SD card are wired on the schematic and unused here.

## Build

```bash
pio run
pio run -t upload
pio device monitor
```

Monitor baud is 115200. Commands are `motors on`, `motors off`, and `eyes boot|awake|worried|sleeping`.

## Before you type motors on

1. MPU-6050 shows up at `0x68` or `0x69`, and the boot log prints a gyro bias.
2. Tilting the board moves `angle` the way you expect. The code assumes the Y gyro axis.
3. Wheels are off the desk. Left and right use the same command, so one of them may be backwards until the wiring is checked.
4. Replace `kp`, `ki`, and `kd` with measured gains. `ki` is 0 on purpose.

Display power is active low. GPIO17 has to be low for Q4 to pass +3V3 to the panels.
