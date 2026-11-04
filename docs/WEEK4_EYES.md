# Week 4: dual round eyes

Two 1.28 inch GC9A01 round screens are the robot's eyes. They are already on the carrier board as DS1 and DS2, and firmware already paints four simple states (boot, awake, worried, sleeping) in `firmware/src/ui.cpp`. This week is the face: smooth look, blink, and a pupil that can also carry a tiny status mark.

Audio stays as it is. Do not change the listener, the bridge, or the mic path for this week.

## What the face should do

Both eyes share SPI (MOSI, clock, DC) and each has its own chip select so the left eye and the right eye can differ.

Pupils should glide. The later code will use linear interpolation so a look target eases into place instead of jumping.

Frames should be drawn in PSRAM, then sent to the panel, so the glass does not tear. The board already has PSRAM. The current eye code does not use it yet.

When the robot is listening or speaking, the eyes can narrow or settle. That hook waits until the face itself works. Do not wire it to audio this week.

The iris can hold a small mark (a dot, a battery tick, a listen icon) without stopping the eye from reading as an eye.

## Pins already on the board

| Name | GPIO | Job |
|------|------|-----|
| SPI MOSI | 11 | Shared data |
| SPI clock | 12 | Shared clock |
| TFT DC | 10 | Shared data/command |
| Left CS | 14 | Left eye |
| Right CS | 15 | Right eye |
| Display power | 17 | Active low enable |
| Reset | none | Panels share the ESP32 reset |

## Where the later code goes

Leave `ui.cpp` as the task that owns SPI, power, and the boot draw. New files sit beside it and get called from there when the face is written:

```text
firmware/include/eye_types.h    look, blink, pupil size
firmware/include/eye_config.h   radii and timing
firmware/include/eyes.h         later API
firmware/src/eyes.cpp           later draw
```

Those files are placeholders. They do not draw anything yet.

## Where the later CAD goes

Printed rings and screen pockets are mechanical. Fusion stays in [Astra-Companion-Cad](https://github.com/atireksd11/Astra-Companion-Cad). Drop exports here when they exist:

```text
cad/eyes/bezels/          rings that hide the module bezel
cad/eyes/screen-mounts/   clips and pockets for the 1.28 inch modules
cad/eyes/pupil-art/       png or svg references for the iris
docs/images/eyes/         photos and renders
```

## What not to add

No second KiCad project. No second SPI bus. No new display task. No audio changes.
