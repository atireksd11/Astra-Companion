#pragma once

void aimInit();
void aimOnTurnDone(float azimuthDeg, float confidence);
void aimPoll();

/** v1 default is wheel yaw. `head on` uses the SG90 on GPIO5 instead. */
void aimSetHeadServo(bool enabled);
bool aimHeadServo();
