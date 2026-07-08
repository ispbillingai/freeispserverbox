/*
  DemoDashboard.ino — FreeISP box screen PREVIEW with FAKE data.

  Shows what the real box UI will look like: 4 pages that auto-rotate
  every 5 seconds, with live-updating (mock) numbers:
    Page 1  HOME    — users online, WiFi status, heartbeat dot
    Page 2  PORTS   — ether1..ether5 up/down + live Mbps
    Page 3  SYSTEM  — clock, uptime, battery bar
    Page 4  CLIMATE — temperature + humidity inside the box

  Wiring (same as FriendTest — screen label -> ESP32):
    GND->GND, VCC->5V, BLK->3V3
    SCL->18, SDA->23, CS->5, DC->2, RST->4

  Board = "ESP32 Dev Module", COM6, hold BOOT while uploading.

  >>> IF YOUR WORKING SKETCH USED A DIFFERENT TAB OR ROTATION,
  >>> CHANGE THESE TWO LINES TO MATCH IT: <<<
*/
#define SCREEN_TAB  INITR_GREENTAB   // or INITR_BLACKTAB
#define SCREEN_ROT  1                // 1 or 3 = landscape

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>

#define TFT_CS   5
#define TFT_DC   2
#define TFT_RST  4

Adafruit_ST7735 tft(TFT_CS, TFT_DC, TFT_RST);

// ---- colors (RGB565) ----
#define C_BG      ST77XX_BLACK
#define C_BAR     0x0339            // deep blue title bar
#define C_TITLE   ST77XX_WHITE
#define C_LABEL   0x8C71            // grey
#define C_VALUE   ST77XX_WHITE
#define C_GOOD    0x07E8            // green
#define C_BAD     0xF965            // red
#define C_ACCENT  0x07FF            // cyan
#define C_WARN    0xFFE0            // yellow

const uint32_t PAGE_MS   = 5000;    // page rotate interval
const uint32_t UPDATE_MS = 250;     // dynamic value refresh

uint8_t  page = 0;
uint32_t lastPage = 0, lastUpdate = 0;
bool     heartbeat = false;

// ---- fake data (random-walk so it looks alive) ----
int   usersOnline = 12;
float dlMbps = 18.4, ulMbps = 3.2;
int   battery = 78;
float tempC = 26.5, humid = 58.0;
bool  portUp[5] = { true, true, false, true, false };

void fakeDataStep() {
  usersOnline = constrain(usersOnline + random(-1, 2), 5, 40);
  dlMbps = constrain(dlMbps + random(-15, 16) / 10.0, 0.3, 95.0);
  ulMbps = constrain(ulMbps + random(-5, 6) / 10.0, 0.1, 20.0);
  if (random(0, 40) == 0) battery = constrain(battery + random(-2, 2), 20, 100);
  tempC = constrain(tempC + random(-2, 3) / 10.0, 18.0, 38.0);
  humid = constrain(humid + random(-3, 4) / 10.0, 30.0, 90.0);
  if (random(0, 60) == 0) portUp[random(0, 5)] ^= 1;   // rare port flip
}

// ---- small helpers ----
void titleBar(const char* t) {
  tft.fillScreen(C_BG);
  tft.fillRect(0, 0, tft.width(), 16, C_BAR);
  tft.setTextSize(1);
  tft.setTextColor(C_TITLE, C_BAR);
  tft.setCursor(4, 4);
  tft.print("FreeISP");
  tft.setTextColor(C_ACCENT, C_BAR);
  tft.setCursor(70, 4);
  tft.print(t);
}

void label(int x, int y, const char* s) {
  tft.setTextSize(1);
  tft.setTextColor(C_LABEL, C_BG);
  tft.setCursor(x, y);
  tft.print(s);
}

// print a value in a cleared box so old digits never linger
void value(int x, int y, uint8_t size, uint16_t color, const String& s, int boxW) {
  tft.fillRect(x, y, boxW, size * 8, C_BG);
  tft.setTextSize(size);
  tft.setTextColor(color, C_BG);
  tft.setCursor(x, y);
  tft.print(s);
}

String clockStr() {           // fake clock: starts 08:00:00 at power-on
  uint32_t s = 8UL * 3600 + millis() / 1000;
  char b[9];
  snprintf(b, sizeof(b), "%02lu:%02lu:%02lu", (s / 3600) % 24, (s / 60) % 60, s % 60);
  return String(b);
}

String upStr() {
  uint32_t s = millis() / 1000;
  char b[12];
  snprintf(b, sizeof(b), "%lud %02lu:%02lu", s / 86400, (s / 3600) % 24, (s / 60) % 60);
  return String(b);
}

// ---- pages: drawStatic once, drawLive every 250ms ----
void drawStatic() {
  switch (page) {
    case 0:
      titleBar("HOME");
      label(10, 26, "USERS ONLINE");
      label(10, 70, "WIFI");
      label(80, 70, "SERVER");
      tft.setTextSize(1);
      tft.setTextColor(C_GOOD, C_BG);
      tft.setCursor(10, 82);  tft.print("CONNECTED");
      tft.setCursor(80, 82);  tft.print("OK");
      label(10, 110, "freeisp.net  *paka box*");
      break;
    case 1:
      titleBar("PORTS");
      for (int i = 0; i < 5; i++) {
        label(14, 24 + i * 20, ("ether" + String(i + 1)).c_str());
      }
      break;
    case 2:
      titleBar("SYSTEM");
      label(10, 26, "TIME");
      label(10, 62, "UPTIME");
      label(10, 92, "BATTERY");
      tft.drawRect(10, 104, 104, 14, C_LABEL);   // battery outline
      tft.fillRect(114, 107, 4, 8, C_LABEL);     // battery nub
      break;
    case 3:
      titleBar("CLIMATE");
      label(10, 26, "BOX TEMPERATURE");
      label(10, 74, "HUMIDITY");
      break;
  }
}

void drawLive() {
  // heartbeat dot, top-right, blinks on every page
  heartbeat = !heartbeat;
  tft.fillCircle(tft.width() - 8, 8, 3, heartbeat ? C_GOOD : C_BAR);

  switch (page) {
    case 0:
      value(10, 38, 3, C_ACCENT, String(usersOnline), 60);
      break;
    case 1:
      for (int i = 0; i < 5; i++) {
        int y = 24 + i * 20;
        tft.fillCircle(7, y + 3, 3, portUp[i] ? C_GOOD : C_BAD);
        if (portUp[i]) {
          float m = (i == 0) ? dlMbps : ulMbps / (i + 1) + i;   // vary per port
          value(66, y, 1, C_VALUE, String(m, 1) + " Mbps", 70);
        } else {
          value(66, y, 1, C_BAD, "down", 70);
        }
      }
      break;
    case 2: {
      value(10, 38, 2, C_VALUE, clockStr(), 110);
      value(10, 74, 1, C_VALUE, upStr(), 90);
      int w = battery;                                   // 0-100 -> 0-100px
      uint16_t bc = battery > 50 ? C_GOOD : (battery > 25 ? C_WARN : C_BAD);
      tft.fillRect(12, 106, w, 10, bc);
      tft.fillRect(12 + w, 106, 100 - w, 10, C_BG);
      value(78, 92, 1, bc, String(battery) + "%", 30);
      break;
    }
    case 3:
      value(10, 38, 3, tempC > 32 ? C_WARN : C_ACCENT, String(tempC, 1) + " C", 120);
      value(10, 86, 3, C_VALUE, String(humid, 0) + " %", 100);
      break;
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println(">>> DemoDashboard: fake FreeISP stats, 4 rotating pages");
  tft.initR(SCREEN_TAB);
  tft.setRotation(SCREEN_ROT);
  drawStatic();
}

void loop() {
  uint32_t now = millis();
  if (now - lastPage >= PAGE_MS) {
    lastPage = now;
    page = (page + 1) % 4;
    drawStatic();
  }
  if (now - lastUpdate >= UPDATE_MS) {
    lastUpdate = now;
    fakeDataStep();
    drawLive();
  }
}
