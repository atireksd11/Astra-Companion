# Astra Companion

A 2-wheeled, self-balancing desktop AI companion robot built for the [Hack Club On-Board](https://onboard.hackclub.com/) 10-week challenge. AstraCompanion serves as the primary real-world dogfooding environment for [Extrude AI](https://github.com/atireksd11/Astra-Companion) — an LLM-powered hardware design and verification platform.

## Overview

AstraCompanion sits vertically beside a desk, connects to WiFi, and acts as an expressive, voice-activated assistant. It balances on two N20 gear motors, displays animated pixel-art eyes on an OLED screen, and responds to its owner via cloud STT → LLM → TTS pipeline.

```
                   ┌────────────────────────────────────────┐
                   │         AstraCompanion Desktop         │
                   └───────────────────┬────────────────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
   [ Power & Processing ]    [ Motion & Sensing ]       [ Interface & Audio ]
   - ESP32-S3 Dual-Core      - MPU6050 6-Axis Gyro      - 0.96" I2C OLED Screen
   - 2S LiPo / USB-C         - DRV8833 H-Bridge Driver  - INMP441 I2S Digital Mic
   - 3.3V/5V Buck Regulators - 2× N20 Metal Gear Motors - MAX98357A I2S Amp + 2W Spk
```

## Hardware BOM

| Subsystem | Component |
|-----------|-----------|
| Brain | ESP32-S3 (dual-core, WiFi/BLE, I2S) |
| Orientation | MPU6050 6-axis IMU (I2C) |
| Motor drive | DRV8833 dual H-bridge |
| Actuation | 2× N20 metal gear motors (50:1) |
| Audio in | INMP441 I2S MEMS mic |
| Audio out | MAX98357A I2S amp + 2W speaker |
| Display | 0.96" SSD1306 OLED (128×64) |
| PCB | Custom 2-layer FR4 (JLCPCB) |
| Enclosure | 3D-printed Fusion 360 chassis |

## Firmware Architecture

Dual-core FreeRTOS task split on ESP32-S3:

- **Core 0** — Real-time balance loop: MPU6050 @ 100 Hz, PID control, DRV8833 PWM
- **Core 1** — Async cloud & UI: WiFi, Whisper STT, LLM API, TTS playback, OLED eyes

## Project Structure

```
├── firmware/          # ESP32-S3 PlatformIO / Arduino firmware
├── hardware/          # KiCad/EasyEDA schematics, Gerbers, BOM
├── cad/               # Fusion 360 enclosure & mechanical parts
├── docs/              # Blueprint, journal, design notes
└── extrude/           # Extrude AI verification harness (dogfooding)
```

## Hack Club Timeline

| Week | Milestone |
|------|-----------|
| W1 | PCB schematic & Gerber submission |
| W2 | 3D CAD wheel hubs & motor mounts |
| W3 | MPU6050 gyro breadboard test |
| W4 | OLED eye expression rendering |
| W5 | Full enclosure CAD assembly |
| W6 | PCB assembly & power rail verification |
| W7 | 3D print chassis |
| W8 | Motor wiring & DRV8833 calibration |
| W9 | WiFi + voice API integration |
| W10 | Final assembly & demo video |

## License

MIT
