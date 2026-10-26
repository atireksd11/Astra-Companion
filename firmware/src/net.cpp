#include "net.h"

#include "aim.h"
#include "audio.h"
#include "audio_config.h"
#include "net_actions.h"

#include <Arduino.h>
#include <WebSocketsClient.h>
#include <WiFi.h>

#include <cstring>

#if __has_include("secrets.h")
#include "secrets.h"
#define NET_HAVE_SECRETS 1
#else
#define NET_HAVE_SECRETS 0
#endif

namespace {

constexpr uint32_t kNetStack = 8192;
constexpr UBaseType_t kNetPriority = 2;
constexpr BaseType_t kNetCore = 1;

constexpr size_t kOutQueueDepth = 128;
constexpr size_t kChunkBytes =
    AudioConfig::kFrameSamples * sizeof(int16_t) * AudioConfig::kMicChannels;

enum class OutType : uint8_t {
  Start,
  Audio,
  End,
};

struct OutMsg {
  OutType type = OutType::Start;
  ListenerMeta meta{};
  bool truncated = false;
  size_t audioLen = 0;
  uint8_t audio[kChunkBytes]{};
};

WebSocketsClient webSocket;
QueueHandle_t outQueue = nullptr;
TaskHandle_t netTaskHandle = nullptr;

volatile bool wifiOk = false;
volatile bool bridgeOk = false;
volatile bool awaitingReply = false;
volatile bool replyDoneReceived = false;

constexpr size_t kInboundText = 8192;

bool startsWithType(const char *text, const char *typeName) {
  char compact[48];
  char spaced[48];
  snprintf(compact, sizeof(compact), "{\"type\":\"%s\"", typeName);
  snprintf(spaced, sizeof(spaced), "{\"type\": \"%s\"", typeName);
  return strstr(text, compact) == text || strstr(text, spaced) == text;
}

void sendHello() {
#if NET_HAVE_SECRETS && defined(BRIDGE_TOKEN)
  if (BRIDGE_TOKEN[0] != '\0') {
    char buf[256];
    snprintf(buf, sizeof(buf),
             "{\"type\":\"hello\",\"proto\":1,\"fw\":\"0.1\",\"token\":\"%s\"}",
             BRIDGE_TOKEN);
    webSocket.sendTXT(buf);
    return;
  }
#endif
  webSocket.sendTXT("{\"type\":\"hello\",\"proto\":1,\"fw\":\"0.1\"}");
}

void onWebSocketEvent(WStype_t type, uint8_t *payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      bridgeOk = false;
      awaitingReply = false;
      replyDoneReceived = false;
      audioNotifySpeaking(false);
      listenerNotifyReplyDone();
      Serial.println("net: bridge disconnected");
      break;
    case WStype_CONNECTED:
      bridgeOk = true;
      Serial.println("net: bridge connected");
      sendHello();
      listenerEnable(true);
      break;
    case WStype_TEXT: {
      if (!payload || length == 0) {
        break;
      }
      static char textBuf[kInboundText];
      const size_t n =
          length < sizeof(textBuf) - 1 ? length : sizeof(textBuf) - 1;
      memcpy(textBuf, payload, n);
      textBuf[n] = '\0';
      const char *text = textBuf;
      if (startsWithType(text, "stop")) {
        audioStopPlayback();
        awaitingReply = false;
        replyDoneReceived = false;
        listenerNotifyReplyDone();
        Serial.println("net: playback stopped (barge)");
      } else if (startsWithType(text, "volume")) {
        const char *fv = strstr(text, "\"firmware_vol\":");
        if (fv) {
          const float v =
              static_cast<float>(atof(fv + strlen("\"firmware_vol\":")));
          audioSetVolume(v);
        }
      } else if (startsWithType(text, "done")) {
        replyDoneReceived = true;
        netApplyDoneActions(text);
      } else if (startsWithType(text, "busy")) {
        Serial.println("net: bridge busy");
        awaitingReply = false;
        replyDoneReceived = false;
        listenerNotifyReplyDone();
      } else if (startsWithType(text, "error")) {
        Serial.printf("net: bridge error %s\n", text);
        awaitingReply = false;
        replyDoneReceived = false;
        audioNotifySpeaking(false);
        listenerNotifyReplyDone();
      }
      break;
    }
    case WStype_BIN:
      if (length > 0) {
        audioNotifySpeaking(true);
        audioWriteSpeaker(reinterpret_cast<const int16_t *>(payload),
                          length / sizeof(int16_t));
      }
      break;
    default:
      break;
  }
}

void drainOutQueue() {
  if (!bridgeOk) {
    return;
  }
  OutMsg msg;
  while (xQueueReceive(outQueue, &msg, 0) == pdTRUE) {
    switch (msg.type) {
      case OutType::Start: {
        char buf[200];
        snprintf(buf, sizeof(buf),
                 "{\"type\":\"start\",\"rate\":%u,\"channels\":%u,\"meta\":{"
                 "\"noise\":%d,\"level\":%d,\"vol\":%.2f,\"channels\":%u}}",
                 static_cast<unsigned>(AudioConfig::kSampleRateHz),
                 static_cast<unsigned>(AudioConfig::kMicChannels),
                 msg.meta.noiseFloor, msg.meta.level,
                 static_cast<double>(msg.meta.volume),
                 static_cast<unsigned>(AudioConfig::kMicChannels));
        webSocket.sendTXT(buf);
        break;
      }
      case OutType::Audio:
        if (msg.audioLen > 0) {
          webSocket.sendBIN(msg.audio, msg.audioLen);
        }
        break;
      case OutType::End:
        if (msg.truncated) {
          webSocket.sendTXT("{\"type\":\"end\",\"truncated\":true}");
        } else {
          webSocket.sendTXT("{\"type\":\"end\"}");
        }
        awaitingReply = true;
        replyDoneReceived = false;
        break;
    }
  }
}

void netTask(void *) {
  for (;;) {
#if NET_HAVE_SECRETS
    if (WiFi.status() != WL_CONNECTED) {
      wifiOk = false;
      bridgeOk = false;
      WiFi.disconnect(true);
      WiFi.mode(WIFI_STA);
      WiFi.setSleep(false);
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
      const uint32_t start = millis();
      while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
        vTaskDelay(pdMS_TO_TICKS(250));
      }
      if (WiFi.status() == WL_CONNECTED) {
        wifiOk = true;
        Serial.print("net: Wi-Fi IP ");
        Serial.println(WiFi.localIP());
#if defined(BRIDGE_USE_TLS) && BRIDGE_USE_TLS
        webSocket.beginSSL(BRIDGE_HOST, BRIDGE_PORT, "/");
#else
        webSocket.begin(BRIDGE_HOST, BRIDGE_PORT, "/");
#endif
        webSocket.onEvent(onWebSocketEvent);
        webSocket.setReconnectInterval(2000);
        webSocket.enableHeartbeat(15000, 3000, 2);
      } else {
        Serial.println("net: Wi-Fi failed");
        vTaskDelay(pdMS_TO_TICKS(5000));
        continue;
      }
    }
    webSocket.loop();
    drainOutQueue();
    aimPoll();

    if (awaitingReply && replyDoneReceived && audioPlayStreamIdle()) {
      awaitingReply = false;
      replyDoneReceived = false;
      audioNotifySpeaking(false);
      listenerNotifyReplyDone();
      aimPoll();
    }
#else
    vTaskDelay(pdMS_TO_TICKS(1000));
#endif
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

bool enqueue(const OutMsg &msg) {
  if (!outQueue) {
    return false;
  }
  if (xQueueSend(outQueue, &msg, pdMS_TO_TICKS(200)) != pdTRUE) {
    Serial.println("net: out queue full — clip dropped");
    return false;
  }
  return true;
}

}  // namespace

void netInit() {
  outQueue = xQueueCreate(kOutQueueDepth, sizeof(OutMsg));
  if (!outQueue) {
    Serial.println("net: out queue failed");
    return;
  }
#if !NET_HAVE_SECRETS
  Serial.println("net: no secrets.h — copy secrets.h.example to secrets.h");
#endif
  xTaskCreatePinnedToCore(netTask, "net", kNetStack, nullptr, kNetPriority,
                          &netTaskHandle, kNetCore);
}

void netPoll() {}

bool netWifiConnected() { return wifiOk; }

bool netBridgeConnected() { return bridgeOk; }

void netFormatStatus(char *buf, size_t buflen) {
  if (!buf || buflen == 0) {
    return;
  }
#if NET_HAVE_SECRETS
  snprintf(buf, buflen, "net wifi=%d bridge=%d host=%s:%d", wifiOk ? 1 : 0,
           bridgeOk ? 1 : 0, BRIDGE_HOST, BRIDGE_PORT);
#else
  snprintf(buf, buflen, "net wifi=0 bridge=0 (no secrets.h)");
#endif
}

void netOnUtteranceStart(const ListenerMeta *meta) {
  OutMsg msg;
  msg.type = OutType::Start;
  if (meta) {
    msg.meta = *meta;
  }
  enqueue(msg);
}

void netOnUtteranceAudio(const int16_t *samples, size_t count) {
  if (!samples || count == 0) {
    return;
  }
  size_t offset = 0;
  const size_t maxSamples = kChunkBytes / sizeof(int16_t);
  while (offset < count) {
    const size_t take = (count - offset > maxSamples) ? maxSamples
                                                      : (count - offset);
    OutMsg msg;
    msg.type = OutType::Audio;
    msg.audioLen = take * sizeof(int16_t);
    memcpy(msg.audio, samples + offset, msg.audioLen);
    enqueue(msg);
    offset += take;
  }
}

void netOnUtteranceEnd(bool truncated) {
  OutMsg msg;
  msg.type = OutType::End;
  msg.truncated = truncated;
  enqueue(msg);
}
