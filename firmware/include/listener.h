#pragma once

#include <cstddef>
#include <cstdint>

enum class ListenerMood : uint8_t {
  Disabled = 0,
  Listening,
  HearingYou,
  WaitingReply,
  Speaking,
  Cooldown,
};

struct ListenerMeta {
  int noiseFloor = 0;
  int level = 0;
  float volume = 0.0f;
};

using ListenerStartFn = void (*)(const ListenerMeta *meta);
using ListenerAudioFn = void (*)(const int16_t *samples, size_t count);
using ListenerEndFn = void (*)(bool truncated);

void listenerInit();
void listenerEnable(bool on);
bool listenerEnabled();

ListenerMood listenerMood();
const char *listenerMoodName(ListenerMood mood);

void listenerSetVolume(float volume);
float listenerVolume();

void listenerSetCallbacks(ListenerStartFn start, ListenerAudioFn audio,
                          ListenerEndFn end);

void listenerNotifySpeaking(bool speaking);
void listenerNotifyReplyDone();

void listenerFeedPcm16(const int16_t *samples, size_t count);

int listenerNoiseFloor();
int listenerLastLevel();
void listenerFormatStatus(char *buf, size_t buflen);
