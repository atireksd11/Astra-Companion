#pragma once

#include <Arduino.h>

void balanceInitMotors();
bool balanceStartImu();
bool balanceImuReady();
void balanceSetMotorsEnabled(bool enabled);
bool balanceMotorsEnabled();
void balanceStopMotorsNow();
void balanceStartTask();

/** Short differential drive for voice aim (+1 = turn right / positive azimuth). */
void balanceSetYawSpin(int8_t direction, uint8_t duty, uint32_t durationMs);
void balanceClearYawSpin();
bool balanceYawSpinActive();
