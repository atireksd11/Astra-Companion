# AstraCompanion & Extrude AI: Master Technical Blueprint

> Full strategic blueprint for the dual-track hardware + AI initiative.
> See [README.md](../README.md) for the quick-start overview.

## 1. Executive Summary

Two complementary projects running concurrently:

1. **Extrude AI** — Frontier AI hardware engineering platform with ERC/DRC/SPICE verification harness targeting 80%+ schematic accuracy.
2. **AstraCompanion** — Physical 2-wheeled self-balancing desktop AI robot (Hack Club On-Board Tier 2, $65 grant) serving as the primary dogfooding testbed for Extrude AI.

## 2. Strategic Synergy

AstraCompanion stress-tests Extrude AI across:

- Pre-CAD schematic verification (I2C pull-ups, bulk decoupling caps)
- ERC/DRC linter rule testing (pin assignment errors, floating resets)
- SPICE power integrity simulation (motor brownout prevention)
- Hardware bug repair benchmarking (HWE-Bench integration)

## 3. Extrude AI Architecture

```
[ Natural Language Requirements ]
               │
               ▼
   [ Pre-CAD Intent Parser ]
               │
               ▼
[ Schema-Enforced Hardware-as-Code (atopile / SKiDL / KiCad Python) ]
               │
               ├────────────────────────┐
               ▼                        ▼
     [ PySpice / NGSPICE ]     [ KiCad ERC / DRC Linter ]
               │                        │
               └───────────┬────────────┘
                           ▼
              [ Closed-Loop Auto-Repair ]
                           │
                           ▼
          [ Verified Gerber / Fabrication Output ]
```

## 4. Voice & Motion Pipeline

1. Wake word ("Hey Astra") → INMP441 audio capture
2. Whisper STT → LLM (structured JSON: text, emotion, gesture) → TTS
3. OLED eye sync + Core 0 PID gesture (nod, spin)

## 5. Budget (Tier 2 — $65 Grant)

| Item | Est. Cost |
|------|-----------|
| ESP32-S3 module | ~$6 |
| N20 motors + wheels | ~$8 |
| DRV8833 + MPU6050 | ~$4.50 |
| INMP441 + MAX98357A + speaker | ~$6.50 |
| OLED display | ~$3 |
| JLCPCB 2-layer PCB | ~$20 |
| Passives | ~$5 |
| **Total** | **~$53** ( $12 buffer ) |

## 6. Immediate Next Step

**Week 1**: Begin PCB schematic in EasyEDA/KiCad — ESP32-S3, DRV8833, MPU6050, I2S headers, power filtering.
