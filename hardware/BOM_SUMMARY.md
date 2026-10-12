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

CAD goods in USD ≈ **$38.63**. All parts ≈ **$82.00 USD** if you convert everything for yourself.

## Tax & shipping — Half Life field (USD)

Half Life adds this **one number** to your parts total toward the tier cap.

### If you pay shipping yourself (recommended if tight on $100)

Put **only tax** in the form:

| | Amount |
|--|--------|
| **Half Life field** | **`5.00` USD** |
| What that is | **13% HST** on **CAD 52.56** of Canadian parts = **CAD 6.83** (× 0.735 ≈ USD 5.02) |
| You pay out of pocket | **~USD 26** ship (LCSC + Adafruit + DigiKey) + **~CAD 42** ship (Mouser, Universal, Amazon, Addison, PiShop) |

LCSC / Adafruit / DigiKey usually do **not** charge Canadian HST at US checkout; border fees on small LCSC parcels are often **CAD 0** — not in this estimate.

### If Hack Club pays shipping + tax

| | Amount |
|--|--------|
| **Half Life field** | **`62.00` USD** (round plan; receipts may differ) |
| Shipping | **USD 26** + **CAD 41.69** (≈ USD 31) |
| Tax | **CAD 6.83** HST (≈ USD 5) |

**Do not use $56** unless you redo the math; full separate-parcel shipping + HST is **~USD 62**.

### Breakdown by basket (planning)

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

Assumes **13% HST** (Ontario-style) on Canadian taxable goods. Update from invoices after checkout.

## What to compare to the $100 tier

Hack Club counts the import the way their UI sums **Total Price** (may ignore **Currency**). After import, check their total.

For planning:

- **USD grant checkout:** ~**$43.36** parts + **$56** tax/shipping ≈ **$99** on USD vendors.
- **CAD checkout (your card):** ~**CAD 52.56** parts + ~**CAD 48** ship/tax ≈ **CAD 100** on Canadian vendors.

You are placing **both** USD and CAD orders; the tier limit applies to what Half Life counts on the form.

## Not in `bom.csv`

Week 2 motors/battery, LCSC passives packs (~$15 USD), DNP optional — add manually or separate tier.

Printing: teacher printer at school.
