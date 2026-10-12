#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>

#include <Adafruit_GC9A01A.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

#include "pins.h"

namespace {

constexpr uint32_t serialBaud = 115200;
constexpr uint32_t balancePeriodMs = 5;  // 200 Hz
constexpr uint32_t motorPwmFrequency = 20000;
constexpr uint8_t motorPwmResolution = 8;
constexpr uint8_t leftPwmChannel = 0;
constexpr uint8_t rightPwmChannel = 1;

// Leave this false until the IMU axes, motor direction, and emergency stop have
// been checked with the wheels off the desk.
constexpr bool motorOutputEnabled = false;

Adafruit_MPU6050 imu;
Adafruit_GC9A01A leftEye(Pins::displayLeftCs, Pins::displayDc,
                         Pins::displayReset);
Adafruit_GC9A01A rightEye(Pins::displayRightCs, Pins::displayDc,
                          Pins::displayReset);

enum class EyeState : uint8_t {
  boot,
  awake,
  worried,
  sleeping,
};

QueueHandle_t eyeStateQueue = nullptr;
bool imuReady = false;

struct PidController {
  float kp = 18.0F;
  float ki = 0.0F;
  float kd = 0.8F;
  float integral = 0.0F;
  float previousError = 0.0F;

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
    // With DRV8833 phase/enable drive, reverse is IN1 high while IN2 is
    // inverted PWM. Verify this direction on the bench before balancing.
    digitalWrite(directionPin, HIGH);
    ledcWrite(pwmChannel, 255 - abs(signedDuty));
  }
}

void stopMotors() {
  writeMotor(Pins::motorLeftDirection, leftPwmChannel, 0);
  writeMotor(Pins::motorRightDirection, rightPwmChannel, 0);
}

void setEyeState(EyeState state) {
  if (eyeStateQueue != nullptr) {
    xQueueOverwrite(eyeStateQueue, &state);
  }
}

void drawEye(Adafruit_GC9A01A &display, EyeState state) {
  constexpr int16_t center = 120;
  display.fillScreen(GC9A01A_BLACK);

  switch (state) {
    case EyeState::boot:
      display.drawCircle(center, center, 58, GC9A01A_CYAN);
      display.drawCircle(center, center, 59, GC9A01A_CYAN);
      break;

    case EyeState::awake:
      display.fillCircle(center, center, 68, GC9A01A_WHITE);
      display.fillCircle(center, center, 30, GC9A01A_CYAN);
      display.fillCircle(center, center, 13, GC9A01A_BLACK);
      display.fillCircle(center - 8, center - 8, 5, GC9A01A_WHITE);
      break;

    case EyeState::worried:
      display.fillCircle(center, center + 12, 62, GC9A01A_WHITE);
      display.fillCircle(center, center + 20, 25, GC9A01A_BLUE);
      display.fillTriangle(55, 48, 185, 48, center, 86, GC9A01A_BLACK);
      break;

    case EyeState::sleeping:
      display.drawLine(62, center, 178, center, GC9A01A_WHITE);
      display.drawLine(70, center + 1, 170, center + 1, GC9A01A_WHITE);
      break;
  }
}

void balanceTask(void *) {
  TickType_t wakeTime = xTaskGetTickCount();
  PidController pid;
  float filteredAngleDegrees = 0.0F;
  uint32_t lastLogMs = 0;

  while (true) {
    if (!imuReady) {
      stopMotors();
      vTaskDelayUntil(&wakeTime, pdMS_TO_TICKS(balancePeriodMs));
      continue;
    }

    sensors_event_t accel{};
    sensors_event_t gyro{};
    sensors_event_t temperature{};
    imu.getEvent(&accel, &gyro, &temperature);

    // This assumes the board balances around the Y gyro axis. Confirm the
    // physical MPU6050 orientation before enabling motors.
    const float accelAngleDegrees =
        atan2f(accel.acceleration.x, accel.acceleration.z) * RAD_TO_DEG;
    const float gyroRateDegrees = gyro.gyro.y * RAD_TO_DEG;
    constexpr float dtSeconds = balancePeriodMs / 1000.0F;

    filteredAngleDegrees =
        0.98F * (filteredAngleDegrees + gyroRateDegrees * dtSeconds) +
        0.02F * accelAngleDegrees;

    if (fabsf(filteredAngleDegrees) > 35.0F) {
      stopMotors();
      setEyeState(EyeState::worried);
    } else {
      const int16_t command =
          static_cast<int16_t>(constrain(pid.update(0.0F, filteredAngleDegrees,
                                                    dtSeconds),
                                         -255.0F, 255.0F));
      writeMotor(Pins::motorLeftDirection, leftPwmChannel, command);
      writeMotor(Pins::motorRightDirection, rightPwmChannel, command);
    }

    if (millis() - lastLogMs >= 250) {
      Serial.printf("angle=%.2f motors=%s\n", filteredAngleDegrees,
                    motorOutputEnabled ? "ENABLED" : "disabled");
      lastLogMs = millis();
    }

    vTaskDelayUntil(&wakeTime, pdMS_TO_TICKS(balancePeriodMs));
  }
}

void uiTask(void *) {
  pinMode(Pins::displayPowerEnable, OUTPUT);
  digitalWrite(Pins::displayPowerEnable, HIGH);

  // Never let both displays listen at once.
  pinMode(Pins::displayLeftCs, OUTPUT);
  pinMode(Pins::displayRightCs, OUTPUT);
  digitalWrite(Pins::displayLeftCs, HIGH);
  digitalWrite(Pins::displayRightCs, HIGH);

  SPI.begin(Pins::spiClock, Pins::spiMiso, Pins::spiMosi);
  leftEye.begin(40000000);
  rightEye.begin(40000000);
  leftEye.setRotation(0);
  rightEye.setRotation(2);

  EyeState current = EyeState::boot;
  drawEye(leftEye, current);
  drawEye(rightEye, current);

  EyeState requested = EyeState::awake;
  while (true) {
    if (xQueueReceive(eyeStateQueue, &requested, pdMS_TO_TICKS(100)) ==
            pdTRUE &&
        requested != current) {
      // Both calls use the same SPI peripheral. They are intentionally
      // sequential and live in this one task, so CS ownership stays simple.
      drawEye(leftEye, requested);
      drawEye(rightEye, requested);
      current = requested;
    }
  }
}

}  // namespace

void setup() {
  Serial.begin(serialBaud);
  delay(500);
  Serial.println("\nAstra Companion booting");

  pinMode(Pins::motorSleep, OUTPUT);
  digitalWrite(Pins::motorSleep, LOW);
  pinMode(Pins::motorLeftDirection, OUTPUT);
  pinMode(Pins::motorRightDirection, OUTPUT);

  ledcSetup(leftPwmChannel, motorPwmFrequency, motorPwmResolution);
  ledcSetup(rightPwmChannel, motorPwmFrequency, motorPwmResolution);
  ledcAttachPin(Pins::motorLeftPwm, leftPwmChannel);
  ledcAttachPin(Pins::motorRightPwm, rightPwmChannel);
  stopMotors();

  Wire.begin(Pins::i2cSda, Pins::i2cScl, 400000);
  imuReady = imu.begin(0x68, &Wire);
  if (imuReady) {
    imu.setAccelerometerRange(MPU6050_RANGE_4_G);
    imu.setGyroRange(MPU6050_RANGE_500_DEG);
    imu.setFilterBandwidth(MPU6050_BAND_44_HZ);
    Serial.println("MPU6050 found");
  } else {
    Serial.println("MPU6050 missing; motor output locked off");
  }

  eyeStateQueue = xQueueCreate(1, sizeof(EyeState));

  xTaskCreatePinnedToCore(balanceTask, "balance", 4096, nullptr, 4, nullptr, 0);
  xTaskCreatePinnedToCore(uiTask, "ui", 8192, nullptr, 2, nullptr, 1);

  digitalWrite(Pins::motorSleep, motorOutputEnabled ? HIGH : LOW);
  setEyeState(imuReady ? EyeState::awake : EyeState::worried);
}

void loop() {
  // Arduino's loop task is unused. The work lives in the two pinned tasks.
  vTaskDelay(portMAX_DELAY);
}
