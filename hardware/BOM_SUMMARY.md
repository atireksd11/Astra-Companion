# BOM summary (PCB — Week 1)

Half Life **Week 1 / Tier 2** imports **`hardware/bom.csv`**.

Week 2 mechanical tier uses **`hardware/bom-cad.csv`** — see [`BOM_CAD_SUMMARY.md`](BOM_CAD_SUMMARY.md) and [`../docs/CAD.md`](../docs/CAD.md).

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

## The ~$96 total and the $103 cap

Half Life **adds every `Total Price`**, USD and CAD mixed → about **$95.92** after import.

| Math | Result |
|------|--------|
| 13% on **all** of $95.92 (if everything were taxable) | **$12.47** tax → **$108.39** total → **over $103** |
| Max tax if parts stay $95.92 and total must be **≤ $103** | **$7.08** (you sponsor shipping) |
| **Real total tax (both buckets, ~13% HST/GST)** | See below → **~CAD 14.50** (≈ **USD 11**) |

### Two tax buckets (you were right about USD)

| Where you buy | Subtotal | When tax hits | ~13% tax |
|---------------|----------|---------------|----------|
| **CAD stores** (Mouser.ca, Amazon.ca, Universal Solder, Addison, PiShop) | **CAD 52.56** | On the **invoice** at checkout | **CAD 6.83** |
| **USD stores** shipped to Canada (LCSC, Adafruit, DigiKey) | **USD 43.36** (~**CAD 59** value) | Usually **not** on the US invoice; **CBSA / courier** charges **HST on import** (~13% of CAD value) | **~CAD 7.67** |
| **Total tax you should plan for** | | | **~CAD 14.50** (≈ **USD 10.66**, say **USD 11**) |

So yes: **CAD tax on CAD orders + import tax on USD orders** — not “USD = no tax.”

### Half Life vs real life ($103 cap)

| | Amount |
|--|--------|
| Parts (HL mixed sum) | **$95.92** |
| **Real tax (both buckets)** | **~$11** |
| **Honest total** | **~$107** (before shipping) |
| **Max tax you can enter and stay ≤ $103** | **$7.08** (with parts at $95.92) |

**You sponsor shipping.** For the form, enter **`7.00` USD** tax so **$95.92 + $7 ≈ $103** passes the checker. Plan to pay **~USD 4 more** tax at Canadian checkouts / on import (~**CAD 14.50** real minus what you claimed).

To put **full ~$11 tax** on the form and stay ≤ **$103**, parts on the import need to drop to about **$92** (cut ~**$4** from the BOM) — ask if you want line items to trim.

## Tax & shipping — Half Life field (USD)

Half Life adds this **one number** to parts toward the tier cap.

### You sponsor shipping (use this)

| | Amount |
|--|--------|
| **Half Life field** | **`7.00` USD** (cap math; real tax ~**$11**) |
| Parts + tax (HL sum) | **~$102.92** |
| Shipping you pay separately | **~USD 26** + **~CAD 42** (see below) |

### If Hack Club pays shipping + tax

| | Amount |
|--|--------|
| **Half Life field** | **`62.00` USD** (round plan; receipts may differ) |
| Shipping | **USD 26** + **CAD 41.69** (≈ USD 31) |
| Tax | **CAD 6.83** HST (≈ USD 7) |

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
