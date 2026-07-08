/*  LastTest.ino  --  the ONE untried path: Arduino_GFX library + clone drivers.
 *
 *  We only ever used the Adafruit library. This uses a DIFFERENT library
 *  (Arduino_GFX by moononournation) and tries the CLONE controllers that cheap
 *  red "128x160 ST7735" modules sometimes really are (GC9106 / ILI9163 / ST7735).
 *
 *  INSTALL FIRST: Arduino IDE -> Library Manager -> search "GFX Library for
 *  Arduino" (by moononournation) -> Install (and Install All dependencies).
 *
 *  Software-SPI bus on the proven pins: DC=5, CS=10, SCK=12, MOSI=11, RST=4.
 *
 *  TRY each driver below by leaving ONE line uncommented at a time, upload,
 *  watch the screen. If ANY shows real RED/GREEN/BLUE (even offset/garbled),
 *  it's a clone and we've revived it -> STOP and tell me which line worked.
 */

#include <Arduino_GFX_Library.h>

Arduino_DataBus *bus = new Arduino_SWSPI(5 /*DC*/, 10 /*CS*/, 12 /*SCK*/, 11 /*MOSI*/, GFX_NOT_DEFINED /*MISO*/);

// ---- Uncomment ONE of these at a time, upload, look at the screen ----
Arduino_GFX *gfx = new Arduino_ST7735(bus, 4 /*RST*/, 0, false, 128, 160, 0, 0, 0, 0, true /*bgr*/);
// Arduino_GFX *gfx = new Arduino_ILI9163(bus, 4 /*RST*/, 0, 128, 160);
// Arduino_GFX *gfx = new Arduino_GC9106(bus, 4 /*RST*/, 0, true /*IPS*/);

void setup() {
  Serial.begin(115200); delay(500); Serial.println();
  Serial.println(">>> Arduino_GFX last test. begin()...");
  if (!gfx->begin(8000000)) Serial.println(">>> gfx->begin FAILED");
  Serial.println(">>> begin done, cycling colors.");
}

void loop() {
  gfx->fillScreen(RED);   delay(900);
  gfx->fillScreen(GREEN); delay(900);
  gfx->fillScreen(BLUE);  delay(900);
  gfx->fillScreen(BLACK);
  gfx->setCursor(10, 40); gfx->setTextColor(YELLOW); gfx->setTextSize(3);
  gfx->println("Hello");
  delay(1500);
}
