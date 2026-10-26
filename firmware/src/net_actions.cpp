#include "net_actions.h"

#include "aim.h"
#include "audio.h"

#include <Arduino.h>
#include <cstring>

namespace {

const char *skipWs(const char *p) {
  while (p && (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n')) {
    ++p;
  }
  return p;
}

const char *findLiteral(const char *start, const char *end, const char *pat) {
  if (!start || !end || !pat || start >= end) {
    return nullptr;
  }
  const size_t n = strlen(pat);
  if (n == 0) {
    return nullptr;
  }
  for (const char *p = start; p + n <= end; ++p) {
    if (memcmp(p, pat, n) == 0) {
      return p;
    }
  }
  return nullptr;
}

const char *valueAfterLiteral(const char *start, const char *end, const char *keyLit) {
  const char *hit = findLiteral(start, end, keyLit);
  if (!hit) {
    return nullptr;
  }
  return skipWs(hit + strlen(keyLit));
}

const char *findKey(const char *objStart, const char *objEnd, const char *key) {
  if (!objStart || !objEnd || objStart >= objEnd || !key) {
    return nullptr;
  }
  const size_t keyLen = strlen(key);
  const char *p = objStart;
  while (p < objEnd) {
    p = skipWs(p);
    if (p >= objEnd) {
      break;
    }
    // Objects arrive as {"id":"...","name":"..."}. Skip the brace and the
    // commas between fields; stopping on either drops every action.
    if (*p == '{' || *p == ',') {
      ++p;
      continue;
    }
    if (*p != '"') {
      break;
    }
    ++p;
    const char *kStart = p;
    while (p < objEnd && *p != '"') {
      if (*p == '\\' && p + 1 < objEnd) {
        p += 2;
        continue;
      }
      ++p;
    }
    if (p >= objEnd) {
      break;
    }
    const size_t len = static_cast<size_t>(p - kStart);
    ++p;
    p = skipWs(p);
    if (p >= objEnd || *p != ':') {
      continue;
    }
    ++p;
    if (len == keyLen && strncmp(kStart, key, keyLen) == 0) {
      return skipWs(p);
    }
    p = skipWs(p);
    if (p < objEnd && *p == '"') {
      ++p;
      while (p < objEnd && *p != '"') {
        if (*p == '\\' && p + 1 < objEnd) {
          p += 2;
          continue;
        }
        ++p;
      }
      if (p < objEnd) {
        ++p;
      }
    } else if (p < objEnd && *p == '{') {
      int depth = 1;
      ++p;
      while (p < objEnd && depth > 0) {
        if (*p == '{') {
          ++depth;
        } else if (*p == '}') {
          --depth;
        }
        ++p;
      }
    } else if (p < objEnd && *p == '[') {
      int depth = 1;
      ++p;
      while (p < objEnd && depth > 0) {
        if (*p == '[') {
          ++depth;
        } else if (*p == ']') {
          --depth;
        }
        ++p;
      }
    } else {
      while (p < objEnd && *p != ',' && *p != '}') {
        ++p;
      }
    }
  }
  return nullptr;
}

bool readQuotedString(const char *p, char *out, size_t outLen) {
  if (!p || *p != '"' || !out || outLen == 0) {
    return false;
  }
  ++p;
  size_t i = 0;
  while (*p && *p != '"' && i + 1 < outLen) {
    out[i++] = *p++;
  }
  out[i] = '\0';
  return *p == '"';
}

float readFloatAt(const char *p) {
  if (!p) {
    return 0.0f;
  }
  return static_cast<float>(atof(p));
}

const char *findActionsArray(const char *text) {
  if (!text) {
    return nullptr;
  }
  const char *actions = strstr(text, "\"actions\":");
  if (!actions) {
    actions = strstr(text, "\"actions\" :");
  }
  if (!actions) {
    return nullptr;
  }
  const char *bracket = strchr(actions, '[');
  return bracket;
}

bool hasActionName(const char *text, const char *name) {
  if (!text || !name) {
    return false;
  }
  char compact[64];
  char spaced[64];
  snprintf(compact, sizeof(compact), "\"name\":\"%s\"", name);
  snprintf(spaced, sizeof(spaced), "\"name\": \"%s\"", name);
  return strstr(text, compact) != nullptr || strstr(text, spaced) != nullptr;
}

void applyLegacyTopLevelAim(const char *text) {
  const char *aim = strstr(text, "\"aim\":");
  if (!aim) {
    aim = strstr(text, "\"aim\" :");
  }
  if (!aim) {
    return;
  }
  const char *objStart = strchr(aim, '{');
  if (!objStart) {
    return;
  }
  const char *p = objStart + 1;
  int depth = 1;
  while (*p && depth > 0) {
    if (*p == '{') {
      ++depth;
    } else if (*p == '}') {
      --depth;
    }
    ++p;
  }
  const char *objEnd = p;
  const char *az = findKey(objStart, objEnd, "azimuth_deg");
  if (!az) {
    return;
  }
  const char *cf = findKey(objStart, objEnd, "confidence");
  const float azimuth = readFloatAt(skipWs(az));
  const float confidence = cf ? readFloatAt(skipWs(cf)) : 0.5f;
  aimOnTurnDone(azimuth, confidence);
  Serial.printf("net: legacy aim az=%.1f conf=%.2f\n",
                static_cast<double>(azimuth),
                static_cast<double>(confidence));
}

void applyOneAction(const char *objStart, const char *objEnd) {
  char name[32];
  const char *nameVal = findKey(objStart, objEnd, "name");
  if (!nameVal || !readQuotedString(nameVal, name, sizeof(name))) {
    return;
  }

  const char *paramsVal = findKey(objStart, objEnd, "params");
  const char *paramsStart = paramsVal;
  const char *paramsEnd = objEnd;
  if (paramsVal && *paramsVal == '{') {
    paramsStart = paramsVal;
    paramsEnd = paramsVal + 1;
    int depth = 1;
    while (*paramsEnd && depth > 0) {
      if (*paramsEnd == '{') {
        ++depth;
      } else if (*paramsEnd == '}') {
        --depth;
      }
      ++paramsEnd;
    }
  }

  if (strcmp(name, "stop_playback") == 0) {
    audioStopPlayback();
    Serial.println("net: action stop_playback");
  } else if (strcmp(name, "set_volume") == 0) {
    const char *fv = findKey(paramsStart, paramsEnd, "firmware_vol");
    if (!fv) {
      fv = valueAfterLiteral(objStart, objEnd, "\"firmware_vol\":");
    }
    if (!fv) {
      fv = valueAfterLiteral(objStart, objEnd, "\"firmware_vol\" :");
    }
    if (fv) {
      const float v = readFloatAt(skipWs(fv));
      audioSetVolume(v);
      Serial.printf("net: action set_volume %.3f\n", static_cast<double>(v));
    }
  } else if (strcmp(name, "aim") == 0) {
    const char *az = findKey(paramsStart, paramsEnd, "azimuth_deg");
    const char *cf = findKey(paramsStart, paramsEnd, "confidence");
    if (!az) {
      az = valueAfterLiteral(paramsStart, paramsEnd, "\"azimuth_deg\":");
    }
    if (!az) {
      az = valueAfterLiteral(objStart, objEnd, "\"azimuth_deg\":");
    }
    if (!cf) {
      cf = valueAfterLiteral(paramsStart, paramsEnd, "\"confidence\":");
    }
    if (!cf) {
      cf = valueAfterLiteral(objStart, objEnd, "\"confidence\":");
    }
    if (az) {
      const float azimuth = readFloatAt(skipWs(az));
      const float confidence = cf ? readFloatAt(skipWs(cf)) : 0.5f;
      aimOnTurnDone(azimuth, confidence);
      Serial.printf("net: action aim az=%.1f conf=%.2f\n",
                    static_cast<double>(azimuth),
                    static_cast<double>(confidence));
    }
  }
}

void scanActionsArray(const char *arrayStart) {
  if (!arrayStart || *arrayStart != '[') {
    return;
  }
  const char *p = arrayStart + 1;
  for (;;) {
    p = skipWs(p);
    if (*p == ']') {
      break;
    }
    if (*p != '{') {
      break;
    }
    const char *objStart = p;
    int depth = 0;
    do {
      if (*p == '{') {
        ++depth;
      } else if (*p == '}') {
        --depth;
      }
      ++p;
    } while (*p && depth > 0);
    const char *objEnd = p;
    applyOneAction(objStart, objEnd);
    p = skipWs(p);
    if (*p == ',') {
      ++p;
      continue;
    }
    if (*p == ']') {
      break;
    }
  }
}

}  // namespace

void netApplyDoneActions(const char *doneJson) {
  if (!doneJson) {
    return;
  }
  const char *arr = findActionsArray(doneJson);
  if (arr) {
    // Actions already include aim/stop when the bridge claimed them.
    // Falling through to the legacy matchers would turn and stop twice,
    // and a transcript can contain the same substrings.
    scanActionsArray(arr);
    return;
  }
  if (hasActionName(doneJson, "stop_playback")) {
    audioStopPlayback();
    Serial.println("net: legacy stop_playback");
  }
  applyLegacyTopLevelAim(doneJson);
}
