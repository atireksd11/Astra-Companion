#include "listener.h"

#include "audio_config.h"

#include <Arduino.h>
#include <cmath>
#include <cstring>

namespace {

constexpr uint32_t kMinSpeechFrames =
    (AudioConfig::kMinSpeechMs + AudioConfig::kFrameMs - 1) /
    AudioConfig::kFrameMs;
constexpr uint32_t kEndSilenceFrames =
    AudioConfig::kEndSilenceMs / AudioConfig::kFrameMs;
constexpr uint32_t kCooldownFrames =
    AudioConfig::kCooldownMs / AudioConfig::kFrameMs;
constexpr uint32_t kMaxUtteranceFrames =
    AudioConfig::kMaxUtteranceSec * 1000 / AudioConfig::kFrameMs;

ListenerMood mood = ListenerMood::Disabled;
bool enabled = false;
float volume = AudioConfig::kDefaultVolume;

int noiseFloor = AudioConfig::kNoiseFloorMin;
int lastLevel = 0;

ListenerStartFn onStart = nullptr;
ListenerAudioFn onAudio = nullptr;
ListenerEndFn onEnd = nullptr;

int16_t preRoll[AudioConfig::kPreRollSamples];
size_t preRollWrite = 0;
size_t preRollCount = 0;

int16_t frameBuf[AudioConfig::kFrameSamples];
size_t frameFill = 0;

uint32_t consecutiveSpeechFrames = 0;
uint32_t silenceFrames = 0;
uint32_t utteranceFrames = 0;
uint32_t cooldownFramesLeft = 0;

bool speechStarted = false;

int computeRms(const int16_t *samples, size_t count) {
  if (count == 0) {
    return 0;
  }
  int64_t sumSq = 0;
  for (size_t i = 0; i < count; ++i) {
    const int32_t s = samples[i];
    sumSq += static_cast<int64_t>(s) * s;
  }
  const int64_t meanSq = sumSq / static_cast<int64_t>(count);
  return static_cast<int>(sqrt(static_cast<double>(meanSq)));
}

int speechThreshold() {
  const int scaled = noiseFloor * AudioConfig::kSpeechMultiplier;
  return scaled > AudioConfig::kNoiseFloorMin ? scaled
                                              : AudioConfig::kNoiseFloorMin;
}

bool levelIsSpeech(int level) { return level >= speechThreshold(); }

void pushPreRollSample(int16_t sample) {
  preRoll[preRollWrite] = sample;
  preRollWrite = (preRollWrite + 1) % AudioConfig::kPreRollSamples;
  if (preRollCount < AudioConfig::kPreRollSamples) {
    ++preRollCount;
  }
}

void pushPreRollBlock(const int16_t *samples, size_t count) {
  for (size_t i = 0; i < count; ++i) {
    pushPreRollSample(samples[i]);
  }
}

void flushPreRoll() {
  if (!onAudio || preRollCount == 0) {
    return;
  }
  int16_t ordered[AudioConfig::kPreRollSamples];
  const size_t n = preRollCount;
  const size_t start =
      (preRollWrite + AudioConfig::kPreRollSamples - n) %
      AudioConfig::kPreRollSamples;
  for (size_t i = 0; i < n; ++i) {
    ordered[i] = preRoll[(start + i) % AudioConfig::kPreRollSamples];
  }
  size_t offset = 0;
  while (offset < n) {
    const size_t chunk =
        (n - offset > AudioConfig::kFrameSamples) ? AudioConfig::kFrameSamples
                                                  : (n - offset);
    onAudio(ordered + offset, chunk);
    offset += chunk;
  }
}

void emitMetaStart() {
  if (!onStart) {
    return;
  }
  ListenerMeta meta;
  meta.noiseFloor = noiseFloor;
  meta.level = lastLevel;
  meta.volume = volume;
  onStart(&meta);
}

void beginUtterance() {
  mood = ListenerMood::HearingYou;
  speechStarted = true;
  utteranceFrames = 0;
  silenceFrames = 0;
  emitMetaStart();
  flushPreRoll();
}

void finishUtterance(bool truncated) {
  if (onEnd) {
    onEnd(truncated);
  }
  speechStarted = false;
  consecutiveSpeechFrames = 0;
  silenceFrames = 0;
  utteranceFrames = 0;
  mood = ListenerMood::WaitingReply;
}

void updateNoiseFloor(int level) {
  if (level >= speechThreshold()) {
    return;
  }
  noiseFloor = (noiseFloor * 95 + level * 5) / 100;
  if (noiseFloor < AudioConfig::kNoiseFloorMin) {
    noiseFloor = AudioConfig::kNoiseFloorMin;
  }
}

void processFrame(const int16_t *samples, size_t count) {
  lastLevel = computeRms(samples, count);

  if (mood == ListenerMood::Cooldown) {
    // Stay muted for the full cooldown. Speaker tail is loud and used to
    // cancel the timer early, which started a new clip of our own echo.
    consecutiveSpeechFrames = 0;
    if (cooldownFramesLeft > 0) {
      --cooldownFramesLeft;
    }
    pushPreRollBlock(samples, count);
    if (cooldownFramesLeft == 0) {
      mood = ListenerMood::Listening;
    }
    return;
  }

  if (mood == ListenerMood::WaitingReply || mood == ListenerMood::Speaking) {
    // Playback can start mid-onset. Leaving the counter intact made the next
    // listen trip after only a few loud frames of speaker tail.
    consecutiveSpeechFrames = 0;
    return;
  }

  if (mood == ListenerMood::Listening) {
    pushPreRollBlock(samples, count);
    updateNoiseFloor(lastLevel);
    if (levelIsSpeech(lastLevel)) {
      ++consecutiveSpeechFrames;
      if (consecutiveSpeechFrames >= kMinSpeechFrames) {
        beginUtterance();
      }
    } else {
      consecutiveSpeechFrames = 0;
    }
    return;
  }

  if (mood == ListenerMood::HearingYou) {
    ++utteranceFrames;
    if (onAudio) {
      onAudio(samples, count);
    }
    if (levelIsSpeech(lastLevel)) {
      silenceFrames = 0;
    } else {
      ++silenceFrames;
    }
    const bool tooLong = utteranceFrames >= kMaxUtteranceFrames;
    const bool ended = silenceFrames >= kEndSilenceFrames;
    if (tooLong) {
      finishUtterance(true);
    } else if (ended && utteranceFrames > kMinSpeechFrames) {
      finishUtterance(false);
    }
  }
}

}  // namespace

void listenerInit() {
  mood = ListenerMood::Disabled;
  enabled = false;
  volume = AudioConfig::kDefaultVolume;
  noiseFloor = AudioConfig::kNoiseFloorMin;
  preRollWrite = 0;
  preRollCount = 0;
  frameFill = 0;
  consecutiveSpeechFrames = 0;
  silenceFrames = 0;
  utteranceFrames = 0;
  cooldownFramesLeft = 0;
  speechStarted = false;
}

void listenerEnable(bool on) {
  enabled = on;
  if (!enabled) {
    mood = ListenerMood::Disabled;
    frameFill = 0;
    consecutiveSpeechFrames = 0;
    return;
  }
  mood = ListenerMood::Listening;
  preRollCount = 0;
  preRollWrite = 0;
  consecutiveSpeechFrames = 0;
  Serial.println("listener: always-on (gate active)");
}

bool listenerEnabled() { return enabled; }

ListenerMood listenerMood() { return mood; }

const char *listenerMoodName(ListenerMood m) {
  switch (m) {
    case ListenerMood::Disabled:
      return "disabled";
    case ListenerMood::Listening:
      return "listening";
    case ListenerMood::HearingYou:
      return "hearing";
    case ListenerMood::WaitingReply:
      return "waiting";
    case ListenerMood::Speaking:
      return "speaking";
    case ListenerMood::Cooldown:
      return "cooldown";
  }
  return "?";
}

void listenerSetVolume(float v) {
  if (v < 0.0f) {
    v = 0.0f;
  }
  if (v > 1.0f) {
    v = 1.0f;
  }
  volume = v;
}

float listenerVolume() { return volume; }

void listenerSetCallbacks(ListenerStartFn start, ListenerAudioFn audio,
                          ListenerEndFn end) {
  onStart = start;
  onAudio = audio;
  onEnd = end;
}

void listenerNotifySpeaking(bool speaking) {
  if (speaking) {
    mood = ListenerMood::Speaking;
    return;
  }
  mood = ListenerMood::Cooldown;
  cooldownFramesLeft = kCooldownFrames;
}

void listenerNotifyReplyDone() { listenerNotifySpeaking(false); }

void listenerFeedPcm16(const int16_t *samples, size_t count) {
  if (!enabled || count == 0) {
    return;
  }
  size_t offset = 0;
  while (offset < count) {
    const size_t space = AudioConfig::kFrameSamples - frameFill;
    const size_t take = (count - offset < space) ? (count - offset) : space;
    memcpy(frameBuf + frameFill, samples + offset, take * sizeof(int16_t));
    frameFill += take;
    offset += take;
    if (frameFill >= AudioConfig::kFrameSamples) {
      processFrame(frameBuf, AudioConfig::kFrameSamples);
      frameFill = 0;
    }
  }
}

int listenerNoiseFloor() { return noiseFloor; }

int listenerLastLevel() { return lastLevel; }

void listenerFormatStatus(char *buf, size_t buflen) {
  if (!buf || buflen == 0) {
    return;
  }
  snprintf(buf, buflen,
           "listener %s en=%d floor=%d lvl=%d thr=%d vol=%.2f",
           listenerMoodName(mood), enabled ? 1 : 0, noiseFloor, lastLevel,
           speechThreshold(), static_cast<double>(volume));
}
