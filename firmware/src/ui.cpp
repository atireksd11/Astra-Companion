#include "ui.h"

#include "pins.h"

#include <Adafruit_GC9A01A.h>
#include <SPI.h>

#include <cstring>

namespace {

Adafruit_GC9A01A leftEye(Pins::displayLeftCs, Pins::displayDc,
                         Pins::displayReset);
Adafruit_GC9A01A rightEye(Pins::displayRightCs, Pins::displayDc,
                          Pins::displayReset);

QueueHandle_t eyeStateQueue = nullptr;

const char *eyeName(EyeState state) {
  switch (state) {
    case EyeState::boot:
      return "boot";
    case EyeState::awake:
      return "awake";
    case EyeState::worried:
      return "worried";
    case EyeState::sleeping:
      return "sleeping";
  }
  return "boot";
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

void pollButtons(EyeState *latched) {
  struct Button {
    gpio_num_t pin;
    EyeState state;
    bool wasDown;
  };
  static Button buttons[] = {
      {Pins::buttonUp, EyeState::awake, false},
      {Pins::buttonSelect, EyeState::sleeping, false},
      {Pins::buttonDown, EyeState::worried, false},
  };
  static uint32_t lastChangeMs = 0;

  for (Button &button : buttons) {
    const bool down = digitalRead(button.pin) == LOW;
    if (down && !button.wasDown && millis() - lastChangeMs > 200) {
      *latched = button.state;
      uiSetEyeState(button.state);
      lastChangeMs = millis();
    }
    button.wasDown = down;
  }
}

void uiTask(void *) {
  pinMode(Pins::displayLeftCs, OUTPUT);
  pinMode(Pins::displayRightCs, OUTPUT);
  digitalWrite(Pins::displayLeftCs, HIGH);
  digitalWrite(Pins::displayRightCs, HIGH);
  pinMode(Pins::buttonUp, INPUT_PULLUP);
  pinMode(Pins::buttonSelect, INPUT_PULLUP);
  pinMode(Pins::buttonDown, INPUT_PULLUP);

  SPI.begin(Pins::spiClock, Pins::spiMiso, Pins::spiMosi);
  leftEye.begin(40000000);
  rightEye.begin(40000000);
  leftEye.setRotation(0);
  rightEye.setRotation(2);
  Serial.println("displays started");

  EyeState current = EyeState::boot;
  drawEye(leftEye, current);
  drawEye(rightEye, current);

  EyeState requested = current;
  while (true) {
    pollButtons(&requested);
    if (xQueueReceive(eyeStateQueue, &requested, pdMS_TO_TICKS(50)) == pdTRUE &&
        requested != current) {
      drawEye(leftEye, requested);
      drawEye(rightEye, requested);
      current = requested;
      Serial.printf("eyes %s\n", eyeName(current));
    }
  }
}

}  // namespace

void uiSetDisplayPower(bool on) {
  pinMode(Pins::displayPowerEnable, OUTPUT);
  digitalWrite(Pins::displayPowerEnable, on ? LOW : HIGH);
}

void uiStartTask() {
  eyeStateQueue = xQueueCreate(1, sizeof(EyeState));
  xTaskCreatePinnedToCore(uiTask, "ui", 8192, nullptr, 2, nullptr, 1);
}

void uiSetEyeState(EyeState state) {
  if (eyeStateQueue != nullptr) {
    xQueueOverwrite(eyeStateQueue, &state);
  }
}

bool uiParseEyeState(const char *text, EyeState *out) {
  if (strcmp(text, "boot") == 0) {
    *out = EyeState::boot;
  } else if (strcmp(text, "awake") == 0) {
    *out = EyeState::awake;
  } else if (strcmp(text, "worried") == 0) {
    *out = EyeState::worried;
  } else if (strcmp(text, "sleeping") == 0) {
    *out = EyeState::sleeping;
  } else {
    return false;
  }
  return true;
}

const char *uiEyeStateName(EyeState state) { return eyeName(state); }
