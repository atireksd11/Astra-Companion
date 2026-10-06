# notes

not a pitch deck. just what this thing actually is.

## the robot

two wheels, balances next to a desk. gyro on core 0 so it doesnt fall while wifi is doing stuff on core 1. round lcd for the eye (GC9A01, not the oled i first wrote). talks through i2s mic/amp.

## the pcb (this week)

its a carrier for an ESP32-S3 DevKit v1. i am not putting a bare esp32 module on a 2-layer board with 2 hours a day, i will mess it up. headers, jst for motors/battery/speaker, lcd on a connector.

full wiring is in `/astracompanion.ato`. pin numbers in `PINOUT.md`.

## power, in english

battery charges off usb-c (tp4056). boost brings it up so the n20s have some torque. ldo makes 3.3v for everything that cant eat 6 volts. big cap on the motor side because pid reversing the wheels will otherwise reboot the esp32 and thats a really stupid way to spend $20 of gerbers.

## extrude

later. this board is the thing i want to throw at a schematic-linter. not this week.

## enclosure

fusion / onshape, not the pcb. round bezel for the 1.28" lcd, 18650 bay, n20 mounts. week 2+.
