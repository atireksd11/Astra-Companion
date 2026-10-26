#include <Arduino.h>

#include <cctype>
#include <cstring>

#include "aim.h"
#include "audio.h"
#include "balance.h"
#include "listener.h"
#include "net.h"
#include "pins.h"
#include "ui.h"

namespace {

constexpr uint32_t kSerialBaud = 115200;

void printHelp() {
  Serial.println("commands:");
  Serial.println("  motors on|off");
  Serial.println("  eyes boot|awake|worried|sleeping");
  Serial.println("  beep");
  Serial.println("  volume 0.2");
  Serial.println("  mic");
  Serial.println("  record");
  Serial.println("  play");
  Serial.println("  wifi");
  Serial.println("  listen on|off");
  Serial.println("  head on|off");
  Serial.println("  status");
}

void handleCommand(char *line) {
  while (*line == ' ') {
    ++line;
  }

  if (line[0] == '\0' || strcmp(line, "help") == 0) {
    printHelp();
    return;
  }

  if (strcmp(line, "motors off") == 0) {
    balanceSetMotorsEnabled(false);
    balanceStopMotorsNow();
    digitalWrite(Pins::motorSleep, LOW);
    Serial.println("motors off");
    return;
  }

  if (strcmp(line, "motors on") == 0) {
    if (!balanceImuReady()) {
      Serial.println("MPU6050 missing; motors stay off");
      return;
    }
    balanceSetMotorsEnabled(true);
    digitalWrite(Pins::motorSleep, HIGH);
    Serial.println("motors on — wheels should be off the desk");
    return;
  }

  if (strncmp(line, "eyes ", 5) == 0) {
    EyeState requested = EyeState::boot;
    if (!uiParseEyeState(line + 5, &requested)) {
      Serial.println("unknown eye state");
      return;
    }
    uiSetEyeState(requested);
    return;
  }

  if (strcmp(line, "beep") == 0) {
    audioBeep(1000, 200);
    Serial.println("beep");
    return;
  }

  if (strcmp(line, "listen on") == 0) {
    listenerEnable(true);
    return;
  }
  if (strcmp(line, "listen off") == 0) {
    listenerEnable(false);
    return;
  }
  if (strcmp(line, "head on") == 0) {
    aimSetHeadServo(true);
    return;
  }
  if (strcmp(line, "head off") == 0) {
    aimSetHeadServo(false);
    return;
  }
  if (strcmp(line, "wifi") == 0) {
    char buf[96];
    netFormatStatus(buf, sizeof(buf));
    Serial.println(buf);
    return;
  }
  if (strcmp(line, "status") == 0) {
    char buf[96];
    listenerFormatStatus(buf, sizeof(buf));
    Serial.println(buf);
    netFormatStatus(buf, sizeof(buf));
    Serial.println(buf);
    return;
  }
  if (strncmp(line, "volume ", 7) == 0) {
    const float v = static_cast<float>(atof(line + 7));
    audioSetVolume(v);
    Serial.printf("volume %.2f\n", static_cast<double>(audioVolume()));
    return;
  }
  if (strcmp(line, "mic") == 0) {
    Serial.println("mic level 5s");
    const uint32_t until = millis() + 5000;
    while (millis() < until) {
      Serial.printf("level=%d floor=%d\n", audioMicLevel(), listenerNoiseFloor());
      vTaskDelay(pdMS_TO_TICKS(200));
    }
    return;
  }
  if (strcmp(line, "record") == 0) {
    if (audioRecordTest(3000)) {
      Serial.println("recording 3s...");
      vTaskDelay(pdMS_TO_TICKS(3100));
      Serial.println("record done");
    } else {
      Serial.println("record failed");
    }
    return;
  }
  if (strcmp(line, "play") == 0) {
    Serial.println(audioPlayRecording() ? "play" : "nothing recorded");
    return;
  }

  Serial.println("unknown command");
  printHelp();
}

void pollSerial() {
  static char line[48];
  static size_t used = 0;

  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r') {
      continue;
    }
    if (c != '\n') {
      if (used + 1 < sizeof(line)) {
        line[used++] = static_cast<char>(tolower(static_cast<unsigned char>(c)));
      }
      continue;
    }
    line[used] = '\0';
    used = 0;
    handleCommand(line);
  }
}

}  // namespace

void setup() {
  Serial.begin(kSerialBaud);
  delay(500);
  Serial.println("\nAstra Companion booting");
  printHelp();

  uiSetDisplayPower(true);
  balanceInitMotors();
  balanceStartImu();

  uiStartTask();
  balanceStartTask();

  if (!audioInit()) {
    Serial.println("audio init failed");
  }
  netInit();
  aimInit();

  uiSetEyeState(balanceImuReady() ? EyeState::awake : EyeState::worried);
}

void loop() {
  pollSerial();
  audioPoll();
  netPoll();
  vTaskDelay(pdMS_TO_TICKS(20));
}
