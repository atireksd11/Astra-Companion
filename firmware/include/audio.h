#pragma once

#include <cstddef>
#include <cstdint>

bool audioInit();
void audioPoll();

void audioBeep(int hz, int ms);
void audioSetVolume(float volume);
float audioVolume();

int audioMicLevel();

bool audioIsSpeaking();
void audioNotifySpeaking(bool speaking);

size_t audioWriteSpeaker(const int16_t *samples, size_t count);
bool audioPlayStreamIdle();
void audioStopPlayback();

bool audioRecordTest(int ms);
bool audioPlayRecording();
