#pragma once

void servoInit();
/** Point the optional head servo. +azimuthDeg = voice to the robot's left. */
void servoAimAzimuth(float azimuthDeg);
void servoCenter();
