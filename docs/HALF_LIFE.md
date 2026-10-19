# Half Life checklist

Quick map of what to upload where. Site is source of truth for hours and devlog; repo holds BOM CSVs and images.

## Week 2 — CAD / mechanics (Tier ~$30, 6 h)

1. Import **`hardware/bom-cad.csv`** on the project.
2. Cart screenshots: motors, wheels, caster, servo, inserts, screws, filament (or one combined cart).
3. Attach CAD images from [`docs/images/cad-*.png`](images/) or fresh Fusion exports.
4. Log time on modeling, print prep, BOM — target **6 hours** for the tier.
5. Devlog: what the chassis does, how PCB mounts, print material (PETG).

## Week 1 — PCB (Tier ~$103)

1. Import **`hardware/bom.csv`** when submitting that tier (not mixed with CAD CSV in one import if the site expects one file per tier).
2. Cart screenshots per vendor (LCSC, Mouser, Amazon.ca, etc.).
3. **Gerbers** from KiCad after **unrouted = 0** and clean DRC → [`hardware/src/`](../hardware/src/).
4. Tax field planning: see [`hardware/BOM_SUMMARY.md`](../hardware/BOM_SUMMARY.md).

## Files Half Life overwrites

Root **`JOURNAL.md`** and **`BOM.md`** sync from the platform. Edit on Half Life; pull/sync to refresh the repo.
