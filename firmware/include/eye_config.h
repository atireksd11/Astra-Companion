#pragma once

// Week 4 feature 1. Pins stay in pins.h. This file does not start SPI.

constexpr int eyesDisplayPowerLevel(bool on) { return on ? 0 : 1; }

constexpr int kEyePowerSettleMs = 150;
constexpr int kEyeSpiHz = 40000000;
// ESP32 xTaskCreate takes bytes, not FreeRTOS words. 8192 was the old UI stack.
constexpr int kUiTaskStackBytes = 16384;
