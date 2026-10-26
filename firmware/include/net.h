#pragma once

#include "listener.h"

#include <cstddef>
#include <cstdint>

void netInit();
void netPoll();

bool netWifiConnected();
bool netBridgeConnected();

void netFormatStatus(char *buf, size_t buflen);

void netOnUtteranceStart(const ListenerMeta *meta);
void netOnUtteranceAudio(const int16_t *samples, size_t count);
void netOnUtteranceEnd(bool truncated);
