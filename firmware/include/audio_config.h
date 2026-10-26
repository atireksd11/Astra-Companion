#pragma once

#include <cstdint>

namespace AudioConfig {

constexpr uint32_t kSampleRateHz = 16000;
constexpr uint32_t kFrameMs = 20;
constexpr uint32_t kFrameSamples =
    (kSampleRateHz * kFrameMs) / 1000;  // 320 @ 16 kHz

constexpr uint32_t kPreRollMs = 300;
constexpr uint32_t kPreRollSamples =
    (kSampleRateHz * kPreRollMs) / 1000;

constexpr uint32_t kMinSpeechMs = 250;
constexpr uint32_t kEndSilenceMs = 2000;
constexpr uint32_t kCooldownMs = 400;

constexpr uint32_t kMaxUtteranceSec = 15;

constexpr int kNoiseFloorMin = 80;
constexpr int kSpeechMultiplier = 3;

constexpr float kDefaultVolume = 0.2f;

constexpr uint32_t kMicChannels = 2;
constexpr float kMicBaselineM = 0.04f;

/** Set true if bench test shows MK2 energy on the left slot. */
constexpr bool kSwapStereoChannels = false;

/** Shared with server doa.min_confidence. Short tones often score ~0.24. */
constexpr float kAimMinConfidence = 0.20f;

}  // namespace AudioConfig
