# Firmware

PlatformIO + Arduino-ESP32. Pin numbers are copied from the KiCad netlist in [`docs/PINOUT.md`](../docs/PINOUT.md). Chassis and N20 mounting: [`docs/CAD.md`](../docs/CAD.md).

## Layout

```text
include/
  pins.h      GPIO map
  balance.h   IMU + PID + motors (Core 0 task)
  ui.h        GC9A01 eyes (Core 1 task)
  audio.h     I2S mic/amp + stereo upload
  net.h       Wi-Fi + voice bridge
  aim.h       Turn toward a voice (wheels, or head servo)
  servo.h     Optional SG90 on GPIO5
src/
  main.cpp    setup, serial CLI, loop polls
  balance.cpp
  ui.cpp
  audio.cpp
  net.cpp
```

## What it actually runs

- **Core 0 (`balance.cpp`).** 200 Hz MPU-6050, complementary filter, PID, DRV8833. Motors off until `motors on`.
- **Core 1 (`ui.cpp`).** Dual GC9A01 on shared SPI; eye state queue from balance, buttons, and serial.
- **`loop()`.** Serial commands. Audio and Wi-Fi run on their own tasks.
- **Voice.** Always-on listener, stereo upload to the laptop bridge, echo playback, then wheel yaw (or `head on` for the SG90). Copy `include/secrets.h.example` to `secrets.h` before flash. Steps: [docs/VOICE_SETUP.md](../docs/VOICE_SETUP.md) and [docs/FEATURE3_DOA.md](../docs/FEATURE3_DOA.md).

Schematic extras (RTC, fuel gauge, ToF, SD) are not in code yet.

## Build

```bash
pio run
pio run -t upload
pio device monitor
```

Monitor baud is 115200. Commands include `motors on|off`, `eyes boot|awake|worried|sleeping`, `beep`, `listen on|off`, `head on|off`, `wifi`, and `status`.

## Before you type motors on

1. MPU-6050 shows up at `0x68` or `0x69`, and the boot log prints a gyro bias.
2. Tilting the board moves `angle` the way you expect. The code assumes the Y gyro axis.
3. Wheels are off the desk. Left and right use the same command, so one of them may be backwards until the wiring is checked.
4. Replace `kp`, `ki`, and `kd` with measured gains. `ki` is 0 on purpose.

Display power is active low. GPIO17 has to be low for Q4 to pass +3V3 to the panels.
