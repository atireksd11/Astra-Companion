# BOM summary

Updated 2026-10-12. Half Life only reads **hardware/bom.csv** for the Week 1 PCB tier. Do not import the other CSV files into the same $100 bucket.

## Week 1 — PCB tier (`hardware/bom.csv`)

Board electronics: ESP32-S3, IMU, DRV8833, displays, mic, audio ICs, power modules wired to the PCB, connectors, headers, switches, LCSC line items on the board.

- Subtotal: **$90.06** (26 lines)
- Leaves room under **$100** before tax and shipping (Half Life uses a small margin)

Passives (resistor and capacitor assortments, **$15.20**) are in **hardware/bom-passives-lcsc.csv**. Order them with your LCSC shipment; they are not on the PCB tier import.

Optional populate-later parts (RTC, ToF, SD socket, backup cell) are in **hardware/bom-optional-dnp.csv**. Do not import that file into Half Life unless you actually populate those footprints.

## Week 2 — CAD / enclosure tier (`hardware/bom-week2.csv`)

Mechanical and off-board power: N20 motors, wheels, 18650 cell and holder, MG90S servos, microSD card (when you use SD).

- Subtotal: **$67.29** (6 lines)
- Shell printing: teacher printer and filament at school (not on this list)

## Full project (all priced files)

Week 1 + Week 2 + passives LCSC ≈ **$171.55** before optional DNP and before PCB fab/assembly/shipping/HST.

Printing: my teacher has a printer and filament at school. He might also lend or give some parts. I have not asked yet; I would guess better than 70% chance, but I am not counting on it.

Teacher note lives here only.
