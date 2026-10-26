#pragma once

#include <cstdint>

enum class EyeState : uint8_t {
  boot,
  awake,
  worried,
  sleeping,
};

void uiSetDisplayPower(bool on);
void uiStartTask();
void uiSetEyeState(EyeState state);
bool uiParseEyeState(const char *text, EyeState *out);
const char *uiEyeStateName(EyeState state);
