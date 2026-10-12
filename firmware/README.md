# Firmware

PlatformIO + Arduino-ESP32. The pin constants were copied from a KiCad netlist,
not from the old `.ato` draft.

## Tasks

- **Core 0 / priority 4:** 200 Hz MPU6050 complementary filter, PID, DRV8833.
- **Core 1 / priority 2:** the two GC9A01 displays on one SPI bus.

Only `uiTask` talks to SPI. “Two displays concurrently” does not mean asserting
both CS pins and blasting bytes at them; it means one UI owner updates each eye
in sequence while the balance loop keeps its own core.

## Build

```bash
pio run
pio run -t upload
pio device monitor
```

## Safety before motors

`motorOutputEnabled` is `false` in `src/main.cpp`. Leave it false until:

1. the MPU6050 is found at `0x68`;
2. tilting the PCB gives the expected sign and axis;
3. left/right motor polarity is checked with wheels in the air;
4. the hardware nSLEEP path and emergency stop work;
5. the PID gains are replaced with measured values.

The current code is a bring-up skeleton, not tuned balance firmware. It does
compile-time pin ownership and task splitting now so those details don't get
buried inside one 800-line `loop()` later.
