# BOM summary

Updated 2026-10-12. Half Life imports only **`hardware/bom.csv`**.

## Currency

Half Life columns are labeled USD, but some lines are **checkout CAD** (amount in the column is **CAD dollars**, not converted).

| Rule | Rows |
|------|------|
| **USD** — use in **USD subtotal** | LCSC, DigiKey, Adafruit; Notes say `Currency USD` |
| **CAD** — **not** in USD subtotal | Notes say `Currency CAD` (Mouser DevKit, Universal Solder displays) |
| **USD planning** (CAD × 0.70) | Amazon.ca, Addison, Universal Solder mic, PiShop cable — still counted in USD subtotal until moved to raw CAD |

## Week 1 — PCB tier (`bom.csv`)

| Rollup | Amount |
|--------|--------|
| **USD subtotal** (grant math) | **$57.09** |
| **CAD subtotal** (paid at checkout) | **CAD 32.94** (ESP32 21.60 + 2× GC9A01 11.34) |
| **Tax & shipping (Half Life field)** | **$12.50 USD** |
| **USD tier check** | **$69.59 USD** (USD subtotal + tax/shipping; CAD lines paid separately) |

If Half Life sums every row in the import, it shows about **$90.03** — that mixes CAD into the USD column. Use the **USD subtotal** above for the grant cap; CAD lines are tagged in Notes.

Re-run totals after any edit: USD = every row whose Notes do **not** contain `Currency CAD`.

### Tax and shipping (enter in Half Life)

| Item | USD |
|------|-----|
| LCSC economy ship to Canada | 6.00 |
| Mouser Canada ship (DevKit) | 4.00 |
| Estimated HST on remaining CAD lines (planning) | 2.50 |
| **Total** | **12.50** |

## Week 2 — CAD / enclosure tier (manual in Half Life, not in `bom.csv`)

| Part | Qty | Total USD | Vendor |
|------|-----|-----------|--------|
| N20 encoder motor pair 6V ~300 RPM | 1 | 19.38 | Amazon.ca (CAD 27.69 × 0.70) |
| N20 wheels 43 mm | 1 | 3.50 | DFRobot |
| Molicel P30 18650 | 1 | 13.65 | Battery Canada (CAD 19.50 × 0.70) |
| 18650 holder with leads | 1 | 1.37 | BC Robotics |
| MG90S servo | 2 | 8.40 | BC Robotics |
| microSD card 8GB (if using SD) | 1 | 20.99 | Amazon.ca |

## LCSC passives (not in `bom.csv`)

~**$15.20 USD** — resistor and capacitor packs on the same LCSC order.

## DNP optional (reference only)

~**$15.39 USD** — DS3231, VL53, BAT54C, Molex SD socket, Keystone 3000, CR1220.

Printing: teacher printer and filament at school.
