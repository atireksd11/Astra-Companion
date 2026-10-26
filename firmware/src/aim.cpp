#include "aim.h"

#include "audio.h"
#include "audio_config.h"
#include "balance.h"
#include "servo.h"

#include <Arduino.h>
#include <cmath>

namespace {

constexpr float kMinTurnDeg = 12.0f;
constexpr uint32_t kMaxYawMs = 1500;
constexpr uint8_t kYawDuty = 90;

volatile bool pending = false;
volatile float targetAzimuth = 0.0f;
volatile float targetConfidence = 0.0f;
bool headServo = false;

int8_t azimuthToYawDirection(float azimuthDeg) {
  if (fabsf(azimuthDeg) < kMinTurnDeg) {
    return 0;
  }
  // doa.py: +azimuth = source to the left. Turn left (yaw dir -1).
  return azimuthDeg > 0 ? -1 : 1;
}

}  // namespace

void aimInit() { servoInit(); }

void aimSetHeadServo(bool enabled) {
  headServo = enabled;
  if (!enabled) {
    servoCenter();
  }
  Serial.println(enabled ? "aim: head servo" : "aim: wheel yaw");
}

bool aimHeadServo() { return headServo; }

void aimOnTurnDone(float azimuthDeg, float confidence) {
  if (confidence < AudioConfig::kAimMinConfidence) {
    Serial.printf("aim: skip low confidence %.2f\n",
                  static_cast<double>(confidence));
    return;
  }
  targetAzimuth = azimuthDeg;
  targetConfidence = confidence;
  pending = true;
}

void aimPoll() {
  if (!pending || audioIsSpeaking()) {
    return;
  }

  if (headServo) {
    if (fabsf(targetAzimuth) < kMinTurnDeg) {
      pending = false;
      Serial.println("aim: within center cone");
      servoCenter();
      return;
    }
    servoAimAzimuth(targetAzimuth);
    pending = false;
    Serial.printf("aim: head az=%.1f conf=%.2f\n",
                  static_cast<double>(targetAzimuth),
                  static_cast<double>(targetConfidence));
    return;
  }

  if (!balanceMotorsEnabled() || !balanceImuReady() || balanceYawSpinActive()) {
    return;
  }

  const int8_t yawDirection = azimuthToYawDirection(targetAzimuth);
  pending = false;
  if (yawDirection == 0) {
    Serial.println("aim: within center cone");
    return;
  }

  balanceSetYawSpin(yawDirection, kYawDuty, kMaxYawMs);
  Serial.printf("aim: yaw dir=%d az=%.1f conf=%.2f\n", yawDirection,
                static_cast<double>(targetAzimuth),
                static_cast<double>(targetConfidence));
}
