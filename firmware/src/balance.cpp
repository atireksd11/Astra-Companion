#include "balance.h"

#include "pins.h"
#include "ui.h"

#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>

#include <cmath>

namespace {

constexpr uint32_t kBalancePeriodMs = 5;
constexpr uint32_t kMotorPwmFrequency = 20000;
constexpr uint8_t kMotorPwmResolution = 8;
constexpr uint8_t kLeftPwmChannel = 0;
constexpr uint8_t kRightPwmChannel = 1;
constexpr float kFallLimitDegrees = 35.0F;
constexpr int kCalibrationSamples = 150;

volatile bool motorOutputEnabled = false;
volatile int8_t yawSpinDir = 0;
volatile uint8_t yawSpinDuty = 0;
volatile uint32_t yawSpinUntilMs = 0;

Adafruit_MPU6050 imu;
bool imuReady = false;
float gyroBiasDegPerSec = 0.0F;
float angleSeedDegrees = 0.0F;

struct PidController {
  float kp = 18.0F;
  float ki = 0.0F;
  float kd = 0.8F;
  float integral = 0.0F;
  float previousError = 0.0F;

  void reset() {
    integral = 0.0F;
    previousError = 0.0F;
  }

  float update(float target, float measured, float dtSeconds) {
    const float error = target - measured;
    integral = constrain(integral + error * dtSeconds, -25.0F, 25.0F);
    const float derivative = (error - previousError) / dtSeconds;
    previousError = error;
    return kp * error + ki * integral + kd * derivative;
  }
};

void writeMotor(gpio_num_t directionPin, uint8_t pwmChannel,
                int16_t signedDuty) {
  signedDuty = constrain(signedDuty, -255, 255);

  if (!motorOutputEnabled || signedDuty == 0) {
    digitalWrite(directionPin, LOW);
    ledcWrite(pwmChannel, 0);
    return;
  }

  if (signedDuty > 0) {
    digitalWrite(directionPin, LOW);
    ledcWrite(pwmChannel, signedDuty);
  } else {
    digitalWrite(directionPin, HIGH);
    ledcWrite(pwmChannel, 255 - abs(signedDuty));
  }
}

void stopMotors() {
  writeMotor(Pins::motorLeftDirection, kLeftPwmChannel, 0);
  writeMotor(Pins::motorRightDirection, kRightPwmChannel, 0);
}

bool readImu(float *accelAngleDegrees, float *gyroRateDegPerSec) {
  sensors_event_t accel{};
  sensors_event_t gyro{};
  sensors_event_t temperature{};
  if (!imu.getEvent(&accel, &gyro, &temperature)) {
    return false;
  }

  *accelAngleDegrees =
      atan2f(accel.acceleration.x, accel.acceleration.z) * RAD_TO_DEG;
  *gyroRateDegPerSec = gyro.gyro.y * RAD_TO_DEG - gyroBiasDegPerSec;
  return true;
}

void balanceTask(void *) {
  TickType_t wakeTime = xTaskGetTickCount();
  PidController pid;
  float filteredAngleDegrees = angleSeedDegrees;
  uint32_t lastLogMs = 0;
  bool fallen = fabsf(filteredAngleDegrees) > kFallLimitDegrees;
  bool motorsWereEnabled = false;

  while (true) {
    const bool motorsOn = motorOutputEnabled;
    if (!motorsOn) {
      stopMotors();
      digitalWrite(Pins::motorSleep, LOW);
    } else if (!motorsWereEnabled) {
      pid.reset();
      digitalWrite(Pins::motorSleep, HIGH);
    }
    motorsWereEnabled = motorsOn;

    if (!imuReady) {
      vTaskDelayUntil(&wakeTime, pdMS_TO_TICKS(kBalancePeriodMs));
      continue;
    }

    float accelAngleDegrees = 0.0F;
    float gyroRateDegrees = 0.0F;
    if (!readImu(&accelAngleDegrees, &gyroRateDegrees)) {
      stopMotors();
      uiSetEyeState(EyeState::worried);
      vTaskDelayUntil(&wakeTime, pdMS_TO_TICKS(kBalancePeriodMs));
      continue;
    }

    constexpr float dtSeconds = kBalancePeriodMs / 1000.0F;
    filteredAngleDegrees =
        0.98F * (filteredAngleDegrees + gyroRateDegrees * dtSeconds) +
        0.02F * accelAngleDegrees;

    int16_t command = 0;
    const bool isFallen = fabsf(filteredAngleDegrees) > kFallLimitDegrees;
    if (isFallen) {
      stopMotors();
      pid.reset();
      if (!fallen) {
        uiSetEyeState(EyeState::worried);
      }
    } else if (motorsOn && yawSpinDir != 0 && millis() < yawSpinUntilMs) {
      const int16_t left = static_cast<int16_t>(yawSpinDir * yawSpinDuty);
      const int16_t right = static_cast<int16_t>(-yawSpinDir * yawSpinDuty);
      writeMotor(Pins::motorLeftDirection, kLeftPwmChannel, left);
      writeMotor(Pins::motorRightDirection, kRightPwmChannel, right);
      command = left;
    } else if (motorsOn) {
      if (yawSpinUntilMs != 0 && millis() >= yawSpinUntilMs) {
        balanceClearYawSpin();
      }
      command = static_cast<int16_t>(constrain(
          pid.update(0.0F, filteredAngleDegrees, dtSeconds), -255.0F, 255.0F));
      writeMotor(Pins::motorLeftDirection, kLeftPwmChannel, command);
      writeMotor(Pins::motorRightDirection, kRightPwmChannel, command);
      if (fallen) {
        uiSetEyeState(EyeState::awake);
      }
    } else {
      pid.reset();
    }
    fallen = isFallen;

    if (millis() - lastLogMs >= 500) {
      Serial.printf("angle=%.2f cmd=%d motors=%s\n", filteredAngleDegrees,
                    command, motorsOn ? "on" : "off");
      lastLogMs = millis();
    }

    vTaskDelayUntil(&wakeTime, pdMS_TO_TICKS(kBalancePeriodMs));
  }
}

}  // namespace

void balanceInitMotors() {
  pinMode(Pins::motorSleep, OUTPUT);
  digitalWrite(Pins::motorSleep, LOW);
  pinMode(Pins::motorLeftDirection, OUTPUT);
  pinMode(Pins::motorRightDirection, OUTPUT);

  ledcSetup(kLeftPwmChannel, kMotorPwmFrequency, kMotorPwmResolution);
  ledcSetup(kRightPwmChannel, kMotorPwmFrequency, kMotorPwmResolution);
  ledcAttachPin(Pins::motorLeftPwm, kLeftPwmChannel);
  ledcAttachPin(Pins::motorRightPwm, kRightPwmChannel);
  balanceStopMotorsNow();
}

bool balanceStartImu() {
  Wire.begin(Pins::i2cSda, Pins::i2cScl, 400000);
  imuReady = imu.begin(0x68, &Wire) || imu.begin(0x69, &Wire);
  if (!imuReady) {
    Serial.println("MPU6050 missing at 0x68 and 0x69; motors locked off");
    return false;
  }

  imu.setAccelerometerRange(MPU6050_RANGE_4_G);
  imu.setGyroRange(MPU6050_RANGE_500_DEG);
  imu.setFilterBandwidth(MPU6050_BAND_44_HZ);
  delay(50);

  Serial.println("hold the board still — calibrating gyro");
  double gyroSum = 0.0;
  double accelSum = 0.0;
  int good = 0;
  for (int sample = 0; sample < kCalibrationSamples; ++sample) {
    float accelAngle = 0.0F;
    float gyroRate = 0.0F;
    if (readImu(&accelAngle, &gyroRate)) {
      gyroSum += gyroRate;
      accelSum += accelAngle;
      ++good;
    }
    delay(5);
  }

  if (good < kCalibrationSamples / 2) {
    imuReady = false;
    Serial.println("MPU6050 reads failed during calibration");
    return false;
  }

  gyroBiasDegPerSec = static_cast<float>(gyroSum / good);
  angleSeedDegrees = static_cast<float>(accelSum / good);
  Serial.printf("MPU6050 ready, gyro bias %.2f deg/s, angle seed %.2f deg\n",
                gyroBiasDegPerSec, angleSeedDegrees);
  return true;
}

bool balanceImuReady() { return imuReady; }

void balanceSetMotorsEnabled(bool enabled) { motorOutputEnabled = enabled; }

bool balanceMotorsEnabled() { return motorOutputEnabled; }

void balanceStopMotorsNow() { stopMotors(); }

void balanceStartTask() {
  xTaskCreatePinnedToCore(balanceTask, "balance", 6144, nullptr, 4, nullptr, 0);
}

void balanceSetYawSpin(int8_t direction, uint8_t duty, uint32_t durationMs) {
  if (direction > 0) {
    yawSpinDir = 1;
  } else if (direction < 0) {
    yawSpinDir = -1;
  } else {
    yawSpinDir = 0;
    return;
  }
  yawSpinDuty = static_cast<uint8_t>(constrain(duty, 0, 255));
  yawSpinUntilMs = millis() + durationMs;
}

void balanceClearYawSpin() {
  yawSpinDir = 0;
  yawSpinDuty = 0;
  yawSpinUntilMs = 0;
}

bool balanceYawSpinActive() {
  return yawSpinDir != 0 && millis() < yawSpinUntilMs;
}
