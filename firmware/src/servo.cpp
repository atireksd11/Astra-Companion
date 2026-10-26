#include "servo.h"

#include "pins.h"

#include <Arduino.h>

namespace {

constexpr uint8_t kChannel = 2;
constexpr uint32_t kFreqHz = 50;
constexpr uint8_t kBits = 16;
constexpr int kCenterUs = 1500;
constexpr int kUsPerDeg = 10;
constexpr int kMinUs = 800;
constexpr int kMaxUs = 2200;

/** Flip if the head turns away from the voice on the bench. */
constexpr bool kInvert = false;

bool ready = false;

void writeUs(int us) {
  if (!ready) {
    return;
  }
  if (us < kMinUs) {
    us = kMinUs;
  }
  if (us > kMaxUs) {
    us = kMaxUs;
  }
  const uint32_t maxDuty = (1u << kBits) - 1u;
  const uint32_t duty = static_cast<uint32_t>(us) * maxDuty / 20000u;
  ledcWrite(kChannel, duty);
}

}  // namespace

void servoInit() {
  ledcSetup(kChannel, kFreqHz, kBits);
  ledcAttachPin(Pins::servoPwm, kChannel);
  ready = true;
  servoCenter();
  Serial.println("servo: GPIO5 ready (head aim off until `head on`)");
}

void servoCenter() { writeUs(kCenterUs); }

void servoAimAzimuth(float azimuthDeg) {
  float az = azimuthDeg;
  if (az > 60.0f) {
    az = 60.0f;
  }
  if (az < -60.0f) {
    az = -60.0f;
  }
  if (kInvert) {
    az = -az;
  }
  const int us = kCenterUs - static_cast<int>(az * kUsPerDeg);
  writeUs(us);
  Serial.printf("servo: aim az=%.1f us=%d\n", static_cast<double>(azimuthDeg), us);
}
