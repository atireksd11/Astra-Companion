# Astra Companion

This repo holds the carrier PCB, the voice stack on the laptop, and notes for building Astra. Week 1 was the KiCad board. This week we are finishing the **audio module** on the printed body: a side speaker box, a neck that can pan, and a clean path for wires through the pivot. The plastic lives in [Astra-Companion-Cad](https://github.com/atireksd11/Astra-Companion-Cad). Mic and amp are still on the PCB (INMP441 and MAX98357A).

The board is built around a **ESP32-S3-DEVKITC-1** so the expensive module can stay on headers. If the first spin has a dumb mistake, I can swap the DevKit without rebuying everything.

**Where things stand:** schematic and layout are in the repo but the board is **not fab ready yet**. Power nets and the DevKit 3V3 tie still needed cleanup in the last pass. Do not order Gerbers until every net is routed and DRC is clean.

## The PCB

MPU-6050 for balance, DRV8833 for two N20 channels, TP4056 + MT3608 + AP2112K for battery and rails, dual GC9A01 round displays on SPI, INMP441 and MAX98357A for audio, plus fuel gauge, RTC, ToF, and microSD on the schematic. For what is actually on the board right now, use [hardware/BOM2.md](hardware/BOM2.md) (the older planning list drifted).

![KiCad PCB layout](docs/images/pcb-layout-kicad.png)

![PCB 3D top](docs/images/pcb-3d-top.png)

![PCB 3D angle](docs/images/pcb-3d-angle.png)

![PCB render](docs/images/pcb-render.png)

Open the project in KiCad 10: [hardware/astracompanion/](hardware/astracompanion/). Parts list for grants: [hardware/bom.csv](hardware/bom.csv). Notes on cost tiers: [hardware/BOM_SUMMARY.md](hardware/BOM_SUMMARY.md). When routing is done, plot Gerbers into [hardware/src/](hardware/src/).

## This week: audio module and neck

The CAD shows how the speaker panel bolts to the side of the torso, how the driver sits behind the grille, and how the head stack sits on bearings so it can turn without chewing up PETG.

**Parts we ordered ($27.94 before tax and shipping)**

| Part | Qty | Unit | Total | Where |
|------|-----|------|-------|-------|
| PGN 608-ZZ ball bearings, 10 pack (8 by 22 by 7 mm) | 1 pack | $12.95 | $12.95 | Amazon.ca |
| MG90S metal gear micro servo, 2 pack | 1 pack | $14.99 | $14.99 | Amazon.ca |
| Tax and shipping | | | about $5 | Prime / domestic |

The bearing pack gives you spares after you use two on the neck. The MG90S pack gives you one pan servo and one spare (or a future tilt). Full writeup and grant CSV: [hardware/BOM_AUDIO_MODULE.md](hardware/BOM_AUDIO_MODULE.md) and [hardware/bom-audio-module.csv](hardware/bom-audio-module.csv).

Exploded view of the head, speaker side panel, and neck stack:

![Audio module exploded](docs/images/audio-module-exploded.png)

Rear view with the vented speaker box on the body:

![Audio module rear](docs/images/audio-module-rear.png)

Inside the torso showing the speaker and board bay:

![Audio module internal](docs/images/audio-module-internal.png)

Side panel, gasket plates, and speaker mount detail:

![Audio module side detail](docs/images/audio-module-side-detail.png)

Voice on the laptop (wake word, STT, TTS) is documented under [docs/VOICE_SETUP.md](docs/VOICE_SETUP.md) and [server/README.md](server/README.md). The robot firmware streams audio to that bridge when you are ready to test on hardware.

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
