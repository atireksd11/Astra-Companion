#pragma once

#include "ui.h"

struct EyePanels {
  bool left;
  bool right;
};

// Starts both GC9A01 panels on the shared SPI bus. A false side does not
// cancel the side that started. True from init means the command list was sent.
EyePanels eyesInit();

void eyesShow(EyeState state);

bool eyesDriveGlass();
