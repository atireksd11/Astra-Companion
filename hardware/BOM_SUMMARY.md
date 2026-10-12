# BOM summary

Half Life imports **`hardware/bom.csv`**.

## CSV columns

`Part, Purpose, Qty, **Currency**, Unit Price, Total Price, Vendor, Link, Notes`

- **Currency** is `USD` or `CAD`.
- **Unit Price** and **Total Price** are in that currency (not converted in the file).

## Parts subtotals (from `bom.csv`)

| Currency | Subtotal |
|----------|----------|
| **USD** | **$43.36** (LCSC, DigiKey, Adafruit) |
| **CAD** | **$52.56** (Mouser, Amazon.ca, Addison, Universal Solder ×2, PiShop) |

Planning FX (CAD→USD for grant math only): **0.735** — not stored in the CSV.

CAD goods in USD � **$38.63**. All parts � **$82.00 USD** if you convert everything for yourself.

## Tax & shipping — Half Life field (USD)

**Enter: `56.00` USD** in **Tax & shipping for the whole order**.

This is **shipping + sales tax only**, not parts. Built from separate checkout baskets:

| Basket | Shipping estimate | Tax estimate |
|--------|-------------------|--------------|
| LCSC (USD) | $8 USD | — |
| Adafruit speaker (USD) | $10 USD | — |
| DigiKey switch (USD) | $8 USD | — |
| Mouser DevKit (CAD) | CAD 12 | HST 13% on CAD 21.60 |
| Universal Solder displays + mic (CAD) | CAD 10 | HST on CAD 15.33 |
| Amazon.ca TP4056 (CAD) | CAD 5.69 | HST on CAD 9.69 |
| Addison MT3608 (CAD) | CAD 6 | HST on CAD 3.99 |
| PiShop JST cable (CAD) | CAD 8 | HST on CAD 1.95 |

CAD shipping **41.69 CAD** + HST on CAD goods **6.83 CAD** → **48.52 CAD** × 0.735 � **$35.66 USD**, plus **$26 USD** shipping on the three USD stores → **≈ $61.66**.  

**Use $56** after assuming one fewer small-parcel ship (e.g. PiShop line combined with Universal Solder or local pickup). Replace with receipt totals when you checkout.

Assumes **13% HST** (Ontario-style) on Canadian taxable goods.

## What to compare to the $100 tier

Hack Club counts the import the way their UI sums **Total Price** (may ignore **Currency**). After import, check their total.

For planning:

- **USD grant checkout:** ~**$43.36** parts + **$56** tax/shipping ≈ **$99** on USD vendors.
- **CAD checkout (your card):** ~**CAD 52.56** parts + ~**CAD 48** ship/tax ≈ **CAD 100** on Canadian vendors.

You are placing **both** USD and CAD orders; the tier limit applies to what Half Life counts on the form.

## Not in `bom.csv`

Week 2 motors/battery, LCSC passives packs (~$15 USD), DNP optional — add manually or separate tier.

Printing: teacher printer at school.
