# Astra Companion

This repo is the **Week 1** board: a carrier PCB for an ESP32-S3 DevKit that powers a small two wheeled desk robot with round eyes, a mic, a speaker, and motor drivers. It is my Hack Club Half Life / OnBoard project. The plastic body and mechanical parts live in a separate repo ([Astra-Companion-Cad](https://github.com/atireksd11/Astra-Companion-Cad)); this one is KiCad, BOM, and firmware for the PCB.

The board is built around a **ESP32-S3-DEVKITC-1** so the expensive module can stay on headers. If the first spin has a dumb mistake, I can swap the DevKit without rebuying everything.

**Where things stand:** schematic and layout are in the repo but the board is **not fab ready yet**. Power nets and the DevKit 3V3 tie still needed cleanup in the last pass. Do not order Gerbers until every net is routed and DRC is clean.

## The PCB

MPU-6050 for balance, DRV8833 for two N20 channels, TP4056 + MT3608 + AP2112K for battery and rails, dual GC9A01 round displays on SPI, INMP441 and MAX98357A for audio, plus fuel gauge, RTC, ToF, and microSD on the schematic. For what is actually on the board right now, use [hardware/BOM2.md](hardware/BOM2.md) (the older planning list drifted).

![KiCad PCB layout](docs/images/pcb-layout-kicad.png)

![PCB 3D top](docs/images/pcb-3d-top.png)

![PCB 3D angle](docs/images/pcb-3d-angle.png)

![PCB render](docs/images/pcb-render.png)

Open the project in KiCad 10: [hardware/astracompanion/](hardware/astracompanion/). Parts list for grants: [hardware/bom.csv](hardware/bom.csv). Notes on cost tiers: [hardware/BOM_SUMMARY.md](hardware/BOM_SUMMARY.md). When routing is done, plot Gerbers into [hardware/src/](hardware/src/).

## Firmware

Arduino on ESP32 already runs FreeRTOS, so the firmware splits work that way on purpose.

On **core 0**, a balance loop reads the MPU6050, estimates tilt, and drives the DRV8833. That task does not touch SPI or WiFi so networking or display work cannot starve the PID loop.

On **core 1**, the UI task owns SPI and both GC9A01 eyes. It only redraws when the expression changes so it is not repainting 115k pixels for no reason.

Audio hardware is wired; streaming voice over the board is not in this firmware yet. Motors stay **off** until you type `motors on` in the serial monitor at 115200. Lift the wheels before you do that.

```bash
cd firmware
pio run -t upload
pio device monitor
```

Pin map: [docs/PINOUT.md](docs/PINOUT.md). More context: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) and [firmware/README.md](firmware/README.md).

## What is in this repo

```
hardware/astracompanion/   KiCad schematic and PCB
hardware/bom.csv           grant import for the PCB parts
hardware/BOM2.md           BOM from the real schematic
firmware/                  PlatformIO project for the DevKit
docs/                      pinout, images, dev notes
```

## Power

USB C and the TP4056 charge an 18650. The MT3608 boosts for +5 V (motors, amp, LEDs). An AP2112K feeds +3.3 V logic. The displays use +3V3_DISP through a GPIO enable. Measure the rails with a multimeter before you seat the DevKit. Do not feed the boost output into the ESP32 3V3 pin.

The battery section can source enough current to make mistakes hot. Treat it like real hardware, not a breadboard toy.
