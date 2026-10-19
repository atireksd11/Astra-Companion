# Hardware

Two Half Life tracks live here:

| Track | Week | Grant | BOM file | Status |
|-------|------|-------|----------|--------|
| **PCB + electronics** | 1 | Tier 2 (~$103 parts) | [`bom.csv`](bom.csv) | KiCad in [`astracompanion/`](astracompanion/); routing in progress |
| **CAD + mechanics** | 2 | Tier 1 (~$30) | [`bom-cad.csv`](bom-cad.csv) | Chassis modeled; see [`../docs/CAD.md`](../docs/CAD.md) |

## Folders

```text
astracompanion/     KiCad 10 project (schematic + PCB)
bom.csv             Week 1 parts list for Half Life import
bom-cad.csv         Week 2 mechanical / print list
BOM2.md             Reference: parts on the schematic (not for HL import)
BOM_SUMMARY.md      Money math for PCB tier
BOM_CAD_SUMMARY.md  Money math for CAD tier
generated/          Netlist export from schematic
src/                Gerbers land here after a clean DRC plot
```

Root `BOM.md` is mirrored from Half Life and gets overwritten on sync. Edit **`bom.csv`** or **`bom-cad.csv`** in this folder for imports.
