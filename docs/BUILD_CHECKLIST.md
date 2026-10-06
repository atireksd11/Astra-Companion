# week 1 checklist

official hacklife log is `JOURNAL.md` (dont type in that, it gets overwritten). log hours on the site.

target: 17h before they care. this week is pcb, ~2h a day.

## locked parts

see `hardware/BOM.md`. electronics + switch/fuse/caps/headers, plus screws, filament, wire, iron, meter.

## today-ish

- [x] repo + video
- [x] finish `astracompanion.ato` so the netlist is actually complete
- [ ] easyeda project
- [ ] drop every footprint on the schematic (dont wire yet)

## schematic

- [ ] power: usb-c -> tp4056 -> 18650 -> fuse -> switch -> mt3608 (6V) -> ams1117 (3.3V)
- [ ] 470uF+100uF on 6V, 10uF on ldo, 0.1uF by each chip + across motors
- [ ] i2c gyro + 4.7k pullups
- [ ] spi + dc/rst/bl for gc9a01
- [ ] i2s mic and amp
- [ ] drv8833 pwm + nSLEEP high
- [ ] jst for motors / battery / speaker
- [ ] female headers for the devkit
- [ ] erc clean

## layout

- [ ] board outline, 2 layer, 1.6mm
- [ ] place parts (motors/battery bottom, lcd toward the face)
- [ ] route. fat traces on motor power. ground plane.
- [ ] drc clean
- [ ] labels on silkscreen so i know what plug is what

## send it

- [ ] gerber.zip
- [ ] schematic.pdf
- [ ] easyeda json into `hardware/src/`
- [ ] jlcpcb cart screenshot (5 pcs, fr-4, 1.6mm)

hours: still basically 0 besides the video session. put the real number in hacklife, not here.
