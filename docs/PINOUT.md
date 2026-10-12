# Pinout

This table comes from a KiCad 10 XML netlist exported from
`hardware/astracompanion/astracompanion.kicad_sch`. It replaces the old,
single-display hand-written map.

## Displays and SPI

| Net | ESP32-S3 GPIO | Connected parts |
| --- | ---: | --- |
| `SPI_MOSI` | 11 | DS1 + DS2 SDA/MOSI, microSD CMD |
| `SPI_CLK` | 12 | DS1 + DS2 SCL, microSD CLK |
| `TFT_DC` | 10 | DS1 + DS2 DC |
| `TFT1_CS` | 14 | DS1 CS |
| `TFT2_CS` | 15 | DS2 CS |
| `SPI_MISO` | 47 | microSD DAT0 |
| `SD_CS` | 21 | microSD DAT3/CS |
| `DISP_PWR_EN` | 17 | Q4 display-rail enable |

Both displays share clock, MOSI, DC, power, and reset. Only chip select differs.
The firmware must keep both CS lines high before starting SPI.

### Reset warning

`ESP_RST` connects the ESP32 DevKit reset pin and both display reset pins. That
means the display reset is **not** a spare GPIO; use `-1` for the GC9A01 reset
argument in firmware. This is electrically unusual and deserves another look
before fabrication.

## Motor driver

| Net | GPIO | DRV8833 pin |
| --- | ---: | --- |
| `MOTOR_L_DIR` | 40 | BIN1 |
| `MOTOR_L_PWM` | 39 | BIN2 |
| `MOTOR_R_DIR` | 42 | AIN1 |
| `MOTOR_R_PWM` | 41 | AIN2 |
| `M_SLP` | 4 | nSLEEP |
| `M_FAULT` | not connected to ESP32 | nFAULT |

The firmware uses phase/enable-style drive: DIR selects polarity and PWM drives
the second bridge input. Keep nSLEEP low until setup is complete.

## I2C and sensors

| Net | GPIO | Devices |
| --- | ---: | --- |
| `I2C_SDA` | 8 | MPU6050, DS3231M, MAX17048, VL53L0X, J7 |
| `I2C_SCL` | 9 | MPU6050, DS3231M, MAX17048, VL53L0X, J7 |
| `IMU_INT` | 13 | MPU6050 INT |
| `RTC_INT` | not connected to ESP32 | DS3231M interrupt |
| `FG_INT` | not connected to ESP32 | MAX17048 alert |
| `TOF_XSHUT` | not connected to ESP32 | VL53L0X shutdown |

## I2S audio

| Net | GPIO | Connected parts |
| --- | ---: | --- |
| `I2S_BCLK` | 45 | INMP441 SCK + MAX98357A BCLK |
| `I2S_LRCK` | 48 | INMP441 WS + MAX98357A LRCLK |
| `I2S_DIN` | 46 | INMP441 SD → ESP32 |
| `I2S_DOUT` | 43 | ESP32 → MAX98357A DIN |

## Controls and extras

| Net | GPIO | Use |
| --- | ---: | --- |
| `BTN_UP` | 1 | Up button |
| `BTN_SELECT` | 2 | Select button |
| `BTN_DOWN` | 3 | Down button |
| `SERVO_PWM` | 5 | Servo headers J3/J10 |
| `ENC_L_A` | 6 | Left encoder A |
| `ENC_L_B` | 7 | Left encoder B |
| `ENC_R_A` | 16 | Right encoder A |
| `ENC_R_B` | 18 | Right encoder B |
| `RGB_DATA` | 38 | WS2812 data |
| `USB_D-` | 19 | Native USB D- |
| `USB_D+` | 20 | Native USB D+ |
| Boot | 0 | Boot button |

## Power

The current schematic uses **AP2112K-3.3**, not AMS1117:

```text
USB-C / TP4056 → Li-ion battery → MT3608 → +5V motor/peripheral rail
                                      └─ AP2112K-3.3 → +3V3 logic rail
```

Check both rails with a multimeter before inserting the DevKit. The schematic
currently leaves the DevKit's two 3V3 header pins unconnected, so verify exactly
how the DevKit is meant to be powered before sending this board to fab.
