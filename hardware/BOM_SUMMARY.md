# BOM summary

Updated 2026-10-12. Half Life imports only **`hardware/bom.csv`**.

## Currency

- **All part prices in `bom.csv` are USD** (column headers match Half Life).
- **Hack Club tier funding is USD** ($100 PCB week).
- **LCSC, DigiKey, Adafruit, Makerfabs:** unit prices are USD from those checkout pages.
- **Mouser Canada, Amazon.ca, Addison, Universal Solder, PiShop:** list prices are CAD on the storefront; converted to USD at **0.70 USD/CAD** for this BOM (planning rate, not live FX).

Do not mix raw CAD numbers in the Unit/Total columns.

## Week 1 — PCB tier (`bom.csv`)

- Parts subtotal: **$89.48** (26 lines)
- **Tax and shipping (enter in Half Life): $12.50 USD**
- **Grand total for the tier check: $101.98 USD** (parts + tax/shipping)

### Tax and shipping breakdown (Week 1, one number for the form)

| Item | USD |
|------|-----|
| LCSC economy ship to Canada (one combined order) | 6.00 |
| Mouser Canada ship (DevKit) | 4.00 |
| Estimated HST 13% on ~CAD 40 domestic lines (× 0.70) | 2.50 |
| **Total (enter in Half Life)** | **12.50** |

Makerfabs and Adafruit ship with their own lines; if those invoices add more, keep the form at **12.50** only if the full total still fits the tier cap.

Half Life has a single field **“Tax & shipping for the whole order”** — type **12.50** (USD, same as parts).

If checkout comes in higher, trim a line or use teacher/school stock before raising this number.

## Week 2 — CAD / enclosure tier (manual in Half Life, not in `bom.csv`)

All **USD**, CAD sources at **0.70** where noted.

| Part | Qty | Total USD | Vendor |
|------|-----|-----------|--------|
| N20 encoder motor pair 6V ~300 RPM | 1 | 19.38 | Amazon.ca (CAD 27.69) |
| N20 wheels 43 mm | 1 | 3.50 | DFRobot (USD page) |
| Molicel P30 18650 | 1 | 13.65 | Battery Canada (CAD 19.50) |
| 18650 holder with leads | 1 | 1.37 | BC Robotics (CAD 1.95) |
| MG90S servo | 2 | 8.40 | BC Robotics (CAD 6.00 ea) |
| microSD card 8GB (if using SD) | 1 | 20.99 | Amazon.ca (CAD 29.99) |

Week 2 parts subtotal about **$67.29**. Plan separate tax/shipping when you submit that tier (not in `bom.csv`).

## LCSC passives (same LCSC order as Week 1 parts, not in `bom.csv`)

~**$15.20 USD** — resistor packs **$2.97**, capacitor/LED packs **$12.23** (LCSC USD checkout). Shipping counted in Week 1 LCSC line above.

## DNP optional (reference only)

~**$15.39 USD** — DS3231, VL53, BAT54C, Molex SD socket, Keystone 3000, CR1220.

Printing: teacher printer and filament at school. He might lend parts; not counted here.
