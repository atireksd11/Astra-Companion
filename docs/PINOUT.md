# pinout + power

carrier board. ESP32-S3 DevKit v1 sits on female headers.

## gpio

| function | gpio | goes to |
| --- | --- | --- |
| I2C SDA | 8 | MPU6050 SDA |
| I2C SCL | 9 | MPU6050 SCL |
| SPI SCLK | 12 | GC9A01 SCL |
| SPI MOSI | 11 | GC9A01 SDA/MOSI |
| LCD CS | 10 | GC9A01 CS |
| LCD DC | 13 | GC9A01 DC |
| LCD RST | 14 | GC9A01 RST |
| LCD BL | 21 | GC9A01 backlight |
| I2S BCLK | 15 | mic + amp BCLK |
| I2S WS | 16 | mic + amp WS/LRCLK |
| I2S SD in | 17 | INMP441 SD |
| I2S SD out | 18 | MAX98357A DIN |
| AIN1 | 4 | DRV8833 AIN1 (left) |
| AIN2 | 5 | DRV8833 AIN2 (left) |
| BIN1 | 6 | DRV8833 BIN1 (right) |
| BIN2 | 7 | DRV8833 BIN2 (right) |

avoided usb pins 19/20 and the weird strapping ones.

i2c pullups: 4.7k on sda and scl to 3.3V.

## power

```
usb-c  -->  TP4056  -->  18650 (protected)
                              \
                               --> polyfuse --> slide switch --> MT3608 -- 6V --> DRV8833
                                                                   |
                                                                   --> AMS1117 -- 3.3V --> chips
```

470µF + 100µF on the 6V rail. 10µF on AMS1117 in/out. 0.1µF next to each ic and across each motor.

devkit gets 3.3V on the 3V3 pin. **not** 6V on the 5V pin.

flashing is still the usb-c on the devkit itself. tp4056 usb-c is just charging.

lcd is an 8-pin header, not a jst. devkit is 2×22 female.
