#include "audio.h"

#include "audio_config.h"
#include "listener.h"
#include "net.h"
#include "pins.h"

#include <Arduino.h>
#include <driver/i2s.h>
#include <esp_heap_caps.h>
#include <freertos/stream_buffer.h>

#include <cmath>
#include <cstring>

namespace {

constexpr uint32_t kAudioStack = 8192;
constexpr UBaseType_t kAudioPriority = 3;
constexpr BaseType_t kAudioCore = 1;

constexpr size_t kPlayStreamBytes = 320 * 1024;
constexpr size_t kRecordBytes = AudioConfig::kSampleRateHz * 3 * sizeof(int16_t);

TaskHandle_t audioTaskHandle = nullptr;
StreamBufferHandle_t playStream = nullptr;

bool initialized = false;
bool i2sOk = false;
float volume = AudioConfig::kDefaultVolume;
bool speaking = false;

constexpr float kMicGain = 4.0f;

struct DcFilter {
  int32_t lastIn = 0;
  int32_t lastOut = 0;
};

DcFilter dcLeft;
DcFilter dcRight;

int16_t ringLeft[AudioConfig::kPreRollSamples];
int16_t ringRight[AudioConfig::kPreRollSamples];
size_t ringWrite = 0;
size_t ringCount = 0;

struct BeepReq {
  volatile bool active = false;
  int hz = 1000;
  int samplesLeft = 0;
} beep;

int16_t *recordBuf = nullptr;
volatile size_t recordFill = 0;
volatile size_t recordTarget = 0;
volatile bool recordActive = false;
volatile bool recordReady = false;

int16_t processMicSample(int32_t raw32, DcFilter *dc) {
  int32_t s = raw32 >> 14;
  const int32_t filtered =
      s - dc->lastIn + static_cast<int32_t>(dc->lastOut * 0.995f);
  dc->lastIn = s;
  dc->lastOut = filtered;
  int32_t amplified = static_cast<int32_t>(filtered * kMicGain);
  if (amplified > 32767) {
    amplified = 32767;
  }
  if (amplified < -32768) {
    amplified = -32768;
  }
  return static_cast<int16_t>(amplified);
}

int32_t sampleToI2s(int16_t s) {
  int32_t v = static_cast<int32_t>(s * volume);
  if (v > 32767) {
    v = 32767;
  }
  if (v < -32768) {
    v = -32768;
  }
  return v << 16;
}

bool initI2s() {
  i2s_config_t cfg = {};
  cfg.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_TX | I2S_MODE_RX);
  cfg.sample_rate = AudioConfig::kSampleRateHz;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 8;
  cfg.dma_buf_len = 256;
  cfg.use_apll = false;
  cfg.tx_desc_auto_clear = true;

  if (i2s_driver_install(I2S_NUM_0, &cfg, 0, nullptr) != ESP_OK) {
    return false;
  }

  i2s_pin_config_t pins = {};
  pins.bck_io_num = Pins::i2sBitClock;
  pins.ws_io_num = Pins::i2sWordSelect;
  pins.data_out_num = Pins::i2sAmpData;
  pins.data_in_num = Pins::i2sMicData;
  if (i2s_set_pin(I2S_NUM_0, &pins) != ESP_OK) {
    return false;
  }
  i2s_zero_dma_buffer(I2S_NUM_0);
  return true;
}

void onListenerStart(const ListenerMeta *meta) {
  Serial.printf("listener: start noise=%d level=%d\n", meta->noiseFloor,
                meta->level);
  netOnUtteranceStart(meta);
}

int16_t lastLeft[AudioConfig::kFrameSamples];
int16_t lastRight[AudioConfig::kFrameSamples];

void applyChannelOrder(int16_t *left, int16_t *right) {
  if (!AudioConfig::kSwapStereoChannels) {
    return;
  }
  const int16_t tmp = *left;
  *left = *right;
  *right = tmp;
}

void pushStereoSample(int16_t left, int16_t right) {
  applyChannelOrder(&left, &right);
  ringLeft[ringWrite] = left;
  ringRight[ringWrite] = right;
  ringWrite = (ringWrite + 1) % AudioConfig::kPreRollSamples;
  if (ringCount < AudioConfig::kPreRollSamples) {
    ++ringCount;
  }
}

void sendStereoBlock(const int16_t *left, const int16_t *right, size_t count) {
  if (count == 0) {
    return;
  }
  int16_t interleaved[AudioConfig::kFrameSamples * 2];
  const size_t n =
      count > AudioConfig::kFrameSamples ? AudioConfig::kFrameSamples : count;
  for (size_t i = 0; i < n; ++i) {
    int16_t l = left[i];
    int16_t r = right[i];
    applyChannelOrder(&l, &r);
    interleaved[i * 2] = l;
    interleaved[i * 2 + 1] = r;
  }
  netOnUtteranceAudio(interleaved, n * AudioConfig::kMicChannels);
}

void flushStereoPreRoll() {
  if (ringCount == 0) {
    return;
  }
  const size_t start =
      (ringWrite + AudioConfig::kPreRollSamples - ringCount) %
      AudioConfig::kPreRollSamples;
  int16_t interleaved[AudioConfig::kFrameSamples * 2];
  size_t filled = 0;
  for (size_t i = 0; i < ringCount; ++i) {
    const size_t idx = (start + i) % AudioConfig::kPreRollSamples;
    interleaved[filled * 2] = ringLeft[idx];
    interleaved[filled * 2 + 1] = ringRight[idx];
    ++filled;
    if (filled == AudioConfig::kFrameSamples) {
      netOnUtteranceAudio(interleaved, filled * AudioConfig::kMicChannels);
      filled = 0;
    }
  }
  if (filled > 0) {
    netOnUtteranceAudio(interleaved, filled * AudioConfig::kMicChannels);
  }
}

void onListenerAudio(const int16_t *samples, size_t count) {
  // Listener pre-roll is mono. Stereo history is flushed from the ring
  // in audioTask when HearingYou begins, so this callback must not upload
  // the current frame over and over.
  (void)samples;
  (void)count;
}

void onListenerEnd(bool truncated) {
  Serial.printf("listener: end truncated=%d\n", truncated ? 1 : 0);
  netOnUtteranceEnd(truncated);
}

void audioTask(void *) {
  int32_t inStereo[AudioConfig::kFrameSamples * 2];
  int32_t outStereo[AudioConfig::kFrameSamples * 2];
  int16_t mono[AudioConfig::kFrameSamples];

  for (;;) {
    size_t bytesRead = 0;
    if (i2sOk) {
      i2s_read(I2S_NUM_0, inStereo, sizeof(inStereo), &bytesRead,
               pdMS_TO_TICKS(50));
    }

    const size_t frames =
        bytesRead / (2 * sizeof(int32_t));  // stereo 32-bit slots
    for (size_t i = 0; i < frames && i < AudioConfig::kFrameSamples; ++i) {
      lastLeft[i] = processMicSample(inStereo[i * 2], &dcLeft);
      lastRight[i] = processMicSample(inStereo[i * 2 + 1], &dcRight);
      const int16_t a = lastLeft[i];
      const int16_t b = lastRight[i];
      mono[i] = (abs(a) > abs(b)) ? a : b;
    }
    if (recordActive && recordBuf && recordFill < recordTarget) {
      const size_t room = (recordTarget - recordFill) / sizeof(int16_t);
      const size_t copy = (frames < room) ? frames : room;
      memcpy(recordBuf + recordFill / sizeof(int16_t), mono,
             copy * sizeof(int16_t));
      recordFill += copy * sizeof(int16_t);
      if (recordFill >= recordTarget) {
        recordActive = false;
        recordReady = true;
      }
    }

    if (!speaking && frames > 0) {
      const bool wasHearing = listenerMood() == ListenerMood::HearingYou;
      if (!wasHearing) {
        for (size_t i = 0; i < frames && i < AudioConfig::kFrameSamples; ++i) {
          pushStereoSample(lastLeft[i], lastRight[i]);
        }
      }
      // A short I2S read must not be padded with zeros: those samples look like
      // silence and clear consecutiveSpeechFrames before speech can start.
      const size_t heard = frames < AudioConfig::kFrameSamples
                               ? frames
                               : AudioConfig::kFrameSamples;
      listenerFeedPcm16(mono, heard);
      const bool hearing = listenerMood() == ListenerMood::HearingYou;
      if (hearing && !wasHearing) {
        flushStereoPreRoll();
      } else if (hearing) {
        sendStereoBlock(lastLeft, lastRight, frames);
      }
    }

    size_t outFrames = 0;
    if (beep.active && beep.samplesLeft > 0) {
      static float phase = 0.0f;
      const float step =
          2.0f * 3.14159265f * static_cast<float>(beep.hz) /
          static_cast<float>(AudioConfig::kSampleRateHz);
      for (; outFrames < AudioConfig::kFrameSamples && beep.samplesLeft > 0;
           ++outFrames, --beep.samplesLeft) {
        const int16_t s =
            static_cast<int16_t>(8000.0f * sinf(phase) * volume);
        outStereo[outFrames * 2] = sampleToI2s(s);
        outStereo[outFrames * 2 + 1] = 0;
        phase += step;
      }
      if (beep.samplesLeft <= 0) {
        beep.active = false;
      }
    } else {
      int16_t playMono[AudioConfig::kFrameSamples];
      const size_t got =
          playStream
              ? xStreamBufferReceive(playStream, playMono, sizeof(playMono), 0)
              : 0;
      outFrames = got / sizeof(int16_t);
      for (size_t i = 0; i < outFrames; ++i) {
        outStereo[i * 2] = sampleToI2s(playMono[i]);
        outStereo[i * 2 + 1] = 0;
      }
    }

    for (size_t i = outFrames; i < AudioConfig::kFrameSamples; ++i) {
      outStereo[i * 2] = 0;
      outStereo[i * 2 + 1] = 0;
    }

    if (i2sOk && outFrames > 0) {
      size_t written = 0;
      i2s_write(I2S_NUM_0, outStereo,
                AudioConfig::kFrameSamples * 2 * sizeof(int32_t), &written,
                pdMS_TO_TICKS(50));
    }

    vTaskDelay(pdMS_TO_TICKS(AudioConfig::kFrameMs));
  }
}

}  // namespace

bool audioInit() {
  if (initialized) {
    return true;
  }

  const size_t psram = ESP.getPsramSize();
  Serial.printf("audio: PSRAM bytes %u\n", static_cast<unsigned>(psram));

  playStream = xStreamBufferCreate(kPlayStreamBytes, 1);
  if (!playStream) {
    Serial.println("audio: play stream failed");
    return false;
  }

  recordBuf = static_cast<int16_t *>(
      heap_caps_malloc(kRecordBytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (!recordBuf) {
    recordBuf = static_cast<int16_t *>(malloc(kRecordBytes));
  }
  if (!recordBuf) {
    Serial.println("audio: record buffer failed");
    return false;
  }

  i2sOk = initI2s();
  if (!i2sOk) {
    Serial.println("audio: I2S init failed");
  } else {
    Serial.println("audio: I2S ready");
  }

  listenerInit();
  listenerSetVolume(volume);
  listenerSetCallbacks(onListenerStart, onListenerAudio, onListenerEnd);

  xTaskCreatePinnedToCore(audioTask, "audio", kAudioStack, nullptr,
                          kAudioPriority, &audioTaskHandle, kAudioCore);
  initialized = true;
  return true;
}

void audioPoll() {}

void audioBeep(int hz, int ms) {
  if (hz < 200) {
    hz = 200;
  }
  if (ms < 50) {
    ms = 50;
  }
  beep.hz = hz;
  beep.samplesLeft = (AudioConfig::kSampleRateHz * ms) / 1000;
  beep.active = true;
}

void audioSetVolume(float v) {
  if (v < 0.0f) {
    v = 0.0f;
  }
  if (v > 1.0f) {
    v = 1.0f;
  }
  volume = v;
  listenerSetVolume(v);
}

float audioVolume() { return volume; }

int audioMicLevel() { return listenerLastLevel(); }

bool audioIsSpeaking() { return speaking; }

void audioNotifySpeaking(bool on) {
  speaking = on;
  listenerNotifySpeaking(on);
}

size_t audioWriteSpeaker(const int16_t *samples, size_t count) {
  if (!playStream || !samples || count == 0) {
    return 0;
  }
  return xStreamBufferSend(playStream, samples, count * sizeof(int16_t),
                           pdMS_TO_TICKS(20)) /
         sizeof(int16_t);
}

bool audioPlayStreamIdle() {
  if (!playStream) {
    return true;
  }
  return xStreamBufferBytesAvailable(playStream) == 0;
}

void audioStopPlayback() {
  if (!playStream) {
    return;
  }
  xStreamBufferReset(playStream);
  audioNotifySpeaking(false);
}

bool audioRecordTest(int ms) {
  if (!recordBuf || recordActive) {
    return false;
  }
  if (ms < 500) {
    ms = 500;
  }
  if (ms > 8000) {
    ms = 8000;
  }
  recordTarget = static_cast<size_t>(ms) * AudioConfig::kSampleRateHz /
                 1000 * sizeof(int16_t);
  if (recordTarget > kRecordBytes) {
    recordTarget = kRecordBytes;
  }
  recordFill = 0;
  recordReady = false;
  recordActive = true;
  return true;
}

bool audioPlayRecording() {
  if (!recordBuf || !recordReady || recordFill == 0) {
    return false;
  }
  audioNotifySpeaking(true);
  const size_t sent =
      xStreamBufferSend(playStream, recordBuf, recordFill, pdMS_TO_TICKS(100));
  if (sent < recordFill) {
    Serial.println("audio: play buffer full");
  }
  const uint32_t until = millis() + 5000;
  while (!audioPlayStreamIdle() && millis() < until) {
    vTaskDelay(pdMS_TO_TICKS(10));
  }
  audioNotifySpeaking(false);
  listenerNotifyReplyDone();
  return sent > 0;
}
