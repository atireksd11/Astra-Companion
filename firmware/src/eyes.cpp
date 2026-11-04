#define LGFX_USE_V1
#include <LovyanGFX.hpp>

#include "eye_config.h"
#include "eyes.h"
#include "pins.h"

#include <Arduino.h>

namespace {

static_assert(eyesDisplayPowerLevel(true) == 0, "display power is active low");
static_assert(eyesDisplayPowerLevel(false) == 1, "display power off is high");
static_assert(static_cast<int>(Pins::displayPowerEnable) == 17, "GPIO17");
static_assert(static_cast<int>(Pins::displayLeftCs) == 14, "left CS");
static_assert(static_cast<int>(Pins::displayRightCs) == 15, "right CS");
static_assert(static_cast<int>(Pins::sdChipSelect) == 21, "SD CS");
static_assert(Pins::displayReset == -1, "panels share ESP reset");

// GC9A01 has no GPIO reset on this board. Adafruit sends SWRESET in that
// case; Panel_GC9A01's command list does not. Prepend it, then the stock list.
struct EyePanel : lgfx::Panel_GC9A01 {
 protected:
  const uint8_t *getInitCommands(uint8_t listno) const override {
    static constexpr uint8_t kSoftwareReset[] = {
        0x01, CMD_INIT_DELAY, 150, 0xFF, 0xFF,
    };
    if (listno == 0) {
      return kSoftwareReset;
    }
    return lgfx::Panel_GC9A01::getInitCommands(static_cast<uint8_t>(listno - 1));
  }
};

lgfx::Bus_SPI bus;
EyePanel panelLeft;
EyePanel panelRight;
lgfx::LGFX_Device deviceLeft;
lgfx::LGFX_Device deviceRight;

bool leftReady = false;
bool rightReady = false;
bool configured = false;

void configureBus() {
  auto cfg = bus.config();
  cfg.spi_host = SPI2_HOST;
  cfg.spi_mode = 0;
  cfg.freq_write = kEyeSpiHz;
  cfg.freq_read = 16000000;
  cfg.spi_3wire = false;
  cfg.use_lock = true;
  cfg.dma_channel = SPI_DMA_CH_AUTO;
  cfg.pin_sclk = Pins::spiClock;
  cfg.pin_mosi = Pins::spiMosi;
  cfg.pin_miso = Pins::spiMiso;
  cfg.pin_dc = Pins::displayDc;
  bus.config(cfg);
}

lgfx::Panel_GC9A01::config_t panelConfig(int cs, int rotationOffset) {
  auto cfg = panelLeft.config();
  cfg.pin_cs = cs;
  cfg.pin_rst = Pins::displayReset;
  cfg.pin_busy = -1;
  cfg.memory_width = 240;
  cfg.memory_height = 240;
  cfg.panel_width = 240;
  cfg.panel_height = 240;
  cfg.offset_x = 0;
  cfg.offset_y = 0;
  cfg.offset_rotation = rotationOffset;
  cfg.dummy_read_pixel = 16;
  cfg.readable = false;
  cfg.invert = true;
  cfg.rgb_order = false;
  cfg.dlen_16bit = false;
  cfg.bus_shared = true;
  return cfg;
}

void bindPanels() {
  panelLeft.config(panelConfig(Pins::displayLeftCs, 0));
  panelRight.config(panelConfig(Pins::displayRightCs, 2));
  panelLeft.setBus(&bus);
  panelRight.setBus(&bus);
  deviceLeft.setPanel(&panelLeft);
  deviceRight.setPanel(&panelRight);
  configured = true;
}

void drawOn(lgfx::LGFX_Device &display, EyeState state) {
  constexpr int16_t center = 120;
  display.fillScreen(TFT_BLACK);
  switch (state) {
    case EyeState::boot:
      display.drawCircle(center, center, 58, TFT_CYAN);
      display.drawCircle(center, center, 59, TFT_CYAN);
      break;
    case EyeState::awake:
      display.fillCircle(center, center, 68, TFT_WHITE);
      display.fillCircle(center, center, 30, TFT_CYAN);
      display.fillCircle(center, center, 13, TFT_BLACK);
      display.fillCircle(center - 8, center - 8, 5, TFT_WHITE);
      break;
    case EyeState::worried:
      display.fillCircle(center, center + 12, 62, TFT_WHITE);
      display.fillCircle(center, center + 20, 25, TFT_BLUE);
      display.fillTriangle(55, 48, 185, 48, center, 86, TFT_BLACK);
      break;
    case EyeState::sleeping:
      display.drawLine(62, center, 178, center, TFT_WHITE);
      display.drawLine(70, center + 1, 170, center + 1, TFT_WHITE);
      break;
  }
}

}  // namespace

EyePanels eyesInit() {
  if (!configured) {
    configureBus();
    bindPanels();
  }
  EyePanels ready{};
  ready.left = deviceLeft.init();
  if (!ready.left) {
    Serial.println("left eye begin failed");
  }
  ready.right = deviceRight.init();
  if (!ready.right) {
    Serial.println("right eye begin failed");
  }
  if (ready.left && ready.right) {
    Serial.println("both eyes ready");
  }
  leftReady = ready.left;
  rightReady = ready.right;
  // init() may have claimed SPI2 even when both panels returned false.
  // Drop it so the Adafruit fallback can call SPI.begin on the same host.
  if (!ready.left && !ready.right) {
    bus.release();
  }
  return ready;
}

void eyesShow(EyeState state) {
  if (leftReady) {
    drawOn(deviceLeft, state);
  }
  if (rightReady) {
    drawOn(deviceRight, state);
  }
}

bool eyesDriveGlass() { return leftReady || rightReady; }
