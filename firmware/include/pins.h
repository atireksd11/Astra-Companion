#pragma once

#include <Arduino.h>

namespace Pins {

// Shared SPI bus
constexpr gpio_num_t spiMosi = GPIO_NUM_11;
constexpr gpio_num_t spiClock = GPIO_NUM_12;
constexpr gpio_num_t spiMiso = GPIO_NUM_47;
constexpr gpio_num_t displayDc = GPIO_NUM_10;
constexpr gpio_num_t displayLeftCs = GPIO_NUM_14;
constexpr gpio_num_t displayRightCs = GPIO_NUM_15;
constexpr gpio_num_t displayPowerEnable = GPIO_NUM_17;

// The displays share the ESP32 reset net. They do not have a GPIO reset.
constexpr int8_t displayReset = -1;

// I2C
constexpr gpio_num_t i2cSda = GPIO_NUM_8;
constexpr gpio_num_t i2cScl = GPIO_NUM_9;
constexpr gpio_num_t imuInterrupt = GPIO_NUM_13;

// DRV8833
constexpr gpio_num_t motorLeftDirection = GPIO_NUM_40;
constexpr gpio_num_t motorLeftPwm = GPIO_NUM_39;
constexpr gpio_num_t motorRightDirection = GPIO_NUM_42;
constexpr gpio_num_t motorRightPwm = GPIO_NUM_41;
constexpr gpio_num_t motorSleep = GPIO_NUM_4;

// Audio (not started by the current firmware)
constexpr gpio_num_t i2sBitClock = GPIO_NUM_45;
constexpr gpio_num_t i2sWordSelect = GPIO_NUM_48;
constexpr gpio_num_t i2sMicData = GPIO_NUM_46;
constexpr gpio_num_t i2sAmpData = GPIO_NUM_43;

// Controls / expansion
constexpr gpio_num_t buttonUp = GPIO_NUM_1;
constexpr gpio_num_t buttonSelect = GPIO_NUM_2;
constexpr gpio_num_t buttonDown = GPIO_NUM_3;
constexpr gpio_num_t servoPwm = GPIO_NUM_5;
constexpr gpio_num_t leftEncoderA = GPIO_NUM_6;
constexpr gpio_num_t leftEncoderB = GPIO_NUM_7;
constexpr gpio_num_t rightEncoderA = GPIO_NUM_16;
constexpr gpio_num_t rightEncoderB = GPIO_NUM_18;
constexpr gpio_num_t rgbData = GPIO_NUM_38;
constexpr gpio_num_t sdChipSelect = GPIO_NUM_21;

}  // namespace Pins
