# BOM from schematic

Pulled from `hardware/astracompanion/astracompanion.kicad_sch` on branch `full-chip-version`.
One row per Value + Footprint as stored in the file. Power symbols (GND, +3V3, +5V, VBUS, PWR_FLAG) are not parts, so they are left out.
Price and Link are blank on purpose.

| Qty | References | Value | Footprint | Price | Link |
| --- | --- | --- | --- | --- | --- |
| 1 | BT1 | Battery_Cell | Battery:BatteryHolder_Keystone_1042_1x18650 |  |  |
| 1 | BT2 | Battery_Cell | Battery:BatteryHolder_Keystone_3000_1x12mm |  |  |
| 1 | C1 | 1uF | Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm |  |  |
| 1 | C2 | 100uF | Capacitor_THT:CP_Radial_D10.0mm_P5.00mm |  |  |
| 1 | C3 | 1000uF | Capacitor_THT:CP_Radial_D6.3mm_P2.50mm |  |  |
| 4 | C4, C24, C26, C28 | 10uF | Capacitor_SMD:C_1206_3216Metric |  |  |
| 18 | C5, C6, C7, C9, C11, C16, C17, C21, C22, C25, C27, C29, C32, C33, C34, C35, C36, C37 | 0.1uF | Capacitor_SMD:C_0805_2012Metric |  |  |
| 1 | C8 | 0.1uF | Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm |  |  |
| 2 | C10, C19 | 10nF | Capacitor_SMD:C_0805_2012Metric |  |  |
| 1 | C12 | 2.2nF | Capacitor_SMD:C_0805_2012Metric |  |  |
| 1 | C13 | 0.1uF | Capacitor_SMD:C_0603_1608Metric |  |  |
| 2 | C14, C50 | 2.2uF | Capacitor_SMD:C_0805_2012Metric |  |  |
| 1 | C15 | 10uF | Capacitor_SMD:C_0805_2012Metric |  |  |
| 1 | C20 | 22uF | Capacitor_SMD:C_0805_2012Metric |  |  |
| 1 | C23 | 100uF | Capacitor_SMD:CP_Elec_6.3x5.4 |  |  |
| 1 | D1 | 1N5819 | Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal |  |  |
| 1 | D3 | LED | LED_SMD:LED_0805_2012Metric |  |  |
| 1 | D5 | BAT54C | Package_TO_SOT_SMD:SOT-23 |  |  |
| 1 | D7 | WS2812B-5050 | LED_SMD:LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm |  |  |
| 1 | D8 | WS2812B | LED_SMD:LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm |  |  |
| 2 | DS1, DS2 | 1.28" 240x240 LCD | Connector_PinHeader_2.54mm:PinHeader_1x07_P2.54mm_Vertical |  |  |
| 2 | J1, J2 | Screw_Terminal_01x02 | TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-2-5.0-H_1x02_P5.00mm_Horizontal |  |  |
| 2 | J3, J10 | Conn_01x03_Pin | Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical |  |  |
| 1 | J4 | USB_C_Receptacle_USB2.0 | Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12 |  |  |
| 1 | J5 | Conn_01x02_Socket | TerminalBlock_MetzConnect:TerminalBlock_MetzConnect_Type055_RT01502HDWU_1x02_P5.00mm_Horizontal |  |  |
| 1 | J6 | Micro_SD_Card | Connector_Card:microSD_HC_Molex_104031-0811 |  |  |
| 1 | J7 | Conn_01x04_Socket | Connector_JST:JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical |  |  |
| 1 | J8 | testpoint | Connector_PinHeader_2.54mm:PinHeader_1x01_P2.54mm_Vertical |  |  |
| 1 | J9 | Encoder_L | Connector:FanPinHeader_1x03_P2.54mm_Vertical |  |  |
| 1 | Jd1 | Encoder_R | Connector:FanPinHeader_1x03_P2.54mm_Vertical |  |  |
| 1 | MK1 | INMP441ACEZ-R7 | Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical |  |  |
| 1 | Q4 | AO3401A | Package_TO_SOT_SMD:SOT-23 |  |  |
| 14 | R1, R9, R12, R13, R14, R15, R16, R17, R18, R19, R20, R29, R30, R32 | 10k | Resistor_SMD:R_0805_2012Metric |  |  |
| 2 | R4, R5 | 5.1K | Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal |  |  |
| 2 | R10, R11 | 2.2k | Resistor_SMD:R_0805_2012Metric |  |  |
| 2 | R23, R24 | 0.2 | Resistor_SMD:R_1206_3216Metric |  |  |
| 1 | R25 | 1k | Resistor_SMD:R_0805_2012Metric |  |  |
| 4 | R27, R36, R37, R38 | 10k | Package_TO_SOT_SMD:SOT-23-6 |  |  |
| 1 | R28 | 100k | Resistor_SMD:R_0805_2012Metric |  |  |
| 1 | R39 | 330 | Package_TO_SOT_SMD:SOT-23-6 |  |  |
| 3 | SW1, SW3, SW6 | PTS645 | Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92 |  |  |
| 1 | SW2 | SW_SPST | Button_Switch_THT:SW_Slide_SPDT_Straight_CK_OS102011MS2Q |  |  |
| 1 | SW4 | Reset / EN button | Button_Switch_THT:SW_PUSH_6mm |  |  |
| 1 | SW5 | Boot / IO0 button | Button_Switch_THT:SW_PUSH_6mm |  |  |
| 1 | TP1 |  | Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical |  |  |
| 1 | U1 | MT3608_BOOSTER_MODULE | Connector:FanPinHeader_1x04_P2.54mm_Vertical |  |  |
| 1 | U2 | ESP32-S3-DEVKITC-1-N8R8 | Connector_PinHeader_2.54mm:PinHeader_2x19_P2.54mm_Vertical |  |  |
| 1 | U3 | DRV8833PWP | Package_SO:HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm |  |  |
| 1 | U4 | MAX98357A | Package_DFN_QFN:TQFN-16-1EP_3x3mm_P0.5mm_EP1.6x1.6mm |  |  |
| 1 | U5 | MPU-6050 | Sensor_Motion:InvenSense_QFN-24_4x4mm_P0.5mm |  |  |
| 1 | U6 | DS3231M | Package_SO:SOIC-16_3.9x9.9mm_P1.27mm |  |  |
| 1 | U7 | AP2112K-3.3 | Package_TO_SOT_SMD:SOT-23-5 |  |  |
| 1 | U8 | VL53L0CXV0DH1 | Sensor_Distance:ST_VL53L1x |  |  |
| 1 | U10 | MAX17048G+T10 | Package_DFN_QFN:DFN-8-1EP_2x2mm_P0.5mm_EP0.6x1.2mm |  |  |
| 1 | U11 | USBLC6-2SC6 | Package_TO_SOT_SMD:SOT-23-6 |  |  |
| 1 | U13 | USBLC6-4SC6 | Package_TO_SOT_SMD:SOT-23-6 |  |  |

102 placed parts, 56 distinct rows.
