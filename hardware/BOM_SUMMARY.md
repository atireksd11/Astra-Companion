# BOM summary — what the numbers mean

Half Life only imports **`hardware/bom.csv`**.

## What to type in Half Life (direct)

| Field | Enter this | What it is |
|-------|------------|------------|
| **Parts** (from repo import) | whatever Half Life shows after import | Sum of the Total column on all rows |
| **Tax & shipping for the whole order** | **12.50** | One guessed number for LCSC ship + Mouser ship + a little HST. **Not $70.** Not a real invoice yet. |

After import, Half Life usually shows about **$90** for parts because it adds every line, including **CAD 21.60** and **CAD 11.34** as if they were USD. That is a display quirk; those two lines are **Canadian dollars** (see Notes: `Currency CAD`).

## The three totals (do not mix them up)

1. **~$90** — Half Life “parts” total if it sums the whole CSV (USD + CAD mixed in one column). **This is not tax/shipping.**

2. **$12.50** — **Only** the tax & shipping box. Shipping + tax **estimate** for Week 1, in **USD**.

3. **~$70** — If you saw something near 70, it was probably **$57 USD parts + $12.50 tax/shipping ≈ $70**, i.e. **parts + shipping together**, not shipping alone.

## USD grant bucket (Week 1, LCSC / DigiKey / Adafruit / etc.)

Rows **without** `Currency CAD` in Notes add to about **$57.09 USD** (real LCSC/DigiKey/Adafruit checkout currency).

## CAD you pay separately (not converted for that USD rollup)

| Part | CAD |
|------|-----|
| ESP32 on Mouser.ca | 21.60 |
| 2× GC9A01 Universal Solder | 11.34 |
| **Total CAD checkout** | **32.94** |

Plus HST on those Canadian orders at checkout (often ~13% in ON — not included above).

## Is $12.50 tax/shipping “real”?

**No.** It is a **planning guess** so the form is not blank:

- LCSC ship to Canada ~$6 USD  
- Mouser ship for the DevKit ~$4 USD  
- ~$2.50 USD toward tax  

When you actually check out, replace **12.50** with **real shipping + tax from your receipts** (or use **0** until you know).

## Week 2, passives, optional

Not in `bom.csv`. See earlier notes in git history or add motors/battery manually when that tier opens. LCSC resistor/cap packs ~**$15.20 USD** on the same LCSC order as the chips.

Printing: teacher printer at school (not on this list).
