# Chassis and CAD (Half Life Week 2)

Mechanical side of Astra Companion: PETG shells, N20 drive, rear caster, and hardware to bolt the carrier PCB in. Modeled in Fusion / Onshape-style workflow; exports live in your CAD project outside this repo unless you add `cad/` later.

Half Life **Tier 1** (~**$30**, **6 hours**) uses **`hardware/bom-cad.csv`**, not the PCB `bom.csv`.

## What the model is

- **Head:** twin round eye housings (GC9A01 modules plug in from the PCB), optional **SG90** for tilt or ears.
- **Body:** vented shell; room for 18650 path, speaker, and wiring.
- **Chassis plate:** motor brackets, **M3** inserts, standoffs for the KiCad carrier.
- **Locomotion:** two **N20** + **43 mm** wheels; **12 mm ball caster** at the rear.

## Renders in the repo

| File | What it shows |
|------|----------------|
| [`cad-front.png`](images/cad-front.png) | Front shell, eye rings, ears |
| [`cad-exploded.png`](images/cad-exploded.png) | Head / mid plate / chassis stack |
| [`cad-iso.png`](images/cad-iso.png) | Iso view before wheels |
| [`cad-pcb-stack.png`](images/cad-pcb-stack.png) | PCB + motors + eyes in context |
| [`cad-wheels.png`](images/cad-wheels.png) | Side view with wheels and caster |

## BOM and budget

Import **`hardware/bom-cad.csv`** for the Week 2 parts grant.

Rough totals (Half Life adds `Total Price` as printed):

| Currency | Subtotal |
|----------|----------|
| USD | **$18.60** |
| CAD | **$10.00** (filament pro-rate) |

Mixed sum ≈ **$28.60** before tax/shipping — fits **Tier 1 ~$30** with a little margin. Pay shipping yourself; tax field on the form is usually small for mechanical-only carts.

## Print notes

- Material: **PETG** (impact and modest heat vs PLA).
- Inserts: **M3 heat-set** after drilling/printing holes; do not overtighten into thin walls.
- Motors: confirm **left/right** wire order against firmware when wheels are in the air (`motors on` in serial monitor).

## PCB interface

- Carrier board: [`hardware/astracompanion/`](../hardware/astracompanion/)
- Motor driver: DRV8833 on PCB; N20 leads land on motor terminals **J1/J2** (see [`PINOUT.md`](PINOUT.md)).
- Encoder headers on PCB align with N20 gearbox encoders if you populate them later.
