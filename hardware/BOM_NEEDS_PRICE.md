# Needs price

Every line in the split BOM files has a price.

- **Week 1 Half Life import:** `hardware/bom.csv` only.
- **Week 2 mechanical tier:** import `hardware/bom-week2.csv` when that tier opens (or add parts manually).
- **Passives:** `hardware/bom-passives-lcsc.csv` — pay with LCSC, not the PCB tier import.
- **DNP optional:** `hardware/bom-optional-dnp.csv` — reference only until you populate those parts.

R23 and R24: bridge with solder (DRV8833 sense to GND). Not a buy line.
