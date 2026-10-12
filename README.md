# Astra Companion

A two-wheeled desktop robot with an ESP32-S3, two round eyes, a microphone,
a speaker, and enough motor control to (eventually) stop falling over.

This is my Hack Club Half Life / OnBoard project. The PCB is a carrier for an
ESP32-S3 DevKitC-1, which means I can unplug the expensive bit if the first board
has a dumb mistake. Very possible at this hour.

> **Current state:** the schematic and first PCB route are in the repo. The board
> is **not fab-ready yet**: DRC still has open power connections and silkscreen
> cleanup. Please do not order these Gerbers because there aren't any final ones.

![Astra Companion PCB](docs/images/pcb-render.png)

## Hardware

| Block | Part | Notes |
| --- | --- | --- |
| Brain | ESP32-S3-DEVKITC-1-N8R8 | Wi-Fi/BLE, 8 MB flash + 8 MB PSRAM |
| Eyes | 2× GC9A01 240×240 round TFT | Shared SPI clock/data, separate GPIO14/GPIO15 chip select |
| Motion | MPU-6050 | I2C on GPIO8/GPIO9, interrupt on GPIO13 |
| Motors | DRV8833 | Two N20 channels, GPIO39–GPIO42 |
| Audio in | INMP441 | I2S microphone |
| Audio out | MAX98357A | I2S class-D speaker amp |
| Power | TP4056 + MT3608 + AP2112K-3.3 | Li-ion charging, motor boost, 3.3 V logic |
| Extras | MAX17048, DS3231M, VL53L0X, microSD | Fuel gauge, RTC, distance sensor, storage |

The actual schematic grew past the original BOM. For what is physically placed
right now, use [`hardware/BOM2.md`](hardware/BOM2.md), not the old planning list.

## How the firmware is split

The Arduino core already runs on FreeRTOS, so I am using it instead of building
another scheduler for fun:

- `balanceTask` - Core 0, high priority, 5 ms period. MPU6050 read, angle
  estimate, PID, and DRV8833 LEDC output. It never touches SPI or Wi-Fi.
- `uiTask` - Core 1. Owns the shared SPI bus and both GC9A01 displays. It only
  redraws when the eye state changes, because repainting 115,200 pixels for no
  reason is a great way to steal time from everything else.

The task boundary is deliberate. A network timeout or a big eye animation should
not turn the robot into a falling Wi-Fi status light.

## Repository

```text
hardware/astracompanion/   KiCad schematic, PCB, and project
hardware/BOM2.md           BOM generated from the real schematic
firmware/                  PlatformIO / Arduino-ESP32 firmware
docs/PINOUT.md             pin map exported from the KiCad netlist
cad/                       enclosure work (later)
astracompanion.ato         early hardware-as-code experiment; not authoritative
```

## Firmware build

1. Install [PlatformIO](https://platformio.org/) in VS Code or Cursor.
2. Open the `firmware/` folder as the PlatformIO project.
3. Connect the ESP32-S3 DevKitC-1 over USB.
4. Build and upload:

```bash
cd firmware
pio run
pio run -t upload
pio device monitor
```

Motors remain disabled in the starter firmware (`MOTOR_OUTPUT_ENABLED = false`).
Test the IMU and serial output first, then lift the wheels off the desk before
turning motor output on. Seriously.

## PCB build

1. Open `hardware/astracompanion/astracompanion.kicad_pro` in KiCad 10.
2. Finish every ratsnest line, especially `+3V3`, `+5V`, and `VBUS`.
3. Run DRC and get **unconnected items to zero**.
4. Move/hide overlapping reference text.
5. Plot Gerbers and drill files only after DRC is clean.
6. Upload to JLCPCB as 2-layer FR-4, 1.6 mm, minimum quantity.

## Power warning

The battery and boost section can source enough current to make mistakes hot.
Check the 3.3 V and 5 V rails with a multimeter before plugging in the DevKit.
Do not feed the MT3608 output into the ESP32 3V3 pin.

