/*  BigUI.ino -- the FreeISP face on the 3.5" ILI9486, with TOUCH.
 *
 *  This is the Creality-printer-style front end: a dashboard you look at,
 *  and menus you drive with a finger -- including joining a WiFi network
 *  WITHOUT recompiling anything. Credentials land in NVS under the same
 *  "freeisp" namespace HelloScreen already uses, so the main firmware can
 *  read them once we merge.
 *
 *  Palette and layout language are lifted from HelloScreen deliberately:
 *  same near-black blue-grey, same card step, one accent colour pointing.
 *  It must read as the SAME product, only bigger.
 *
 *  ------------------------------------------------------------------
 *  ⚠ THE ONE HARDWARE CATCH -- WiFi vs the touch panel
 *  ------------------------------------------------------------------
 *  The touch film's two analog lines land on GPIO12 and GPIO14, which are
 *  ADC2. A classic ESP32 cannot analogRead ADC2 while WiFi is running.
 *  So this sketch:
 *     - turns WiFi OFF while you are typing on the keyboard (full 2D touch)
 *     - keeps menus as FULL-WIDTH ROWS, which need only the vertical axis
 *  and if TOUCH_Y_ON_ADC1 is set (see below) the vertical axis keeps
 *  working even with WiFi up, so the menus stay alive while connected.
 *
 *  PCB REV FIX (do this once and the whole problem disappears):
 *     route LCD_RS -> GPIO32 and LCD_WR -> GPIO33.
 *     Those are the only two pins that are BOTH ADC1 and output-capable,
 *     which is exactly what a 4-wire resistive panel needs.
 *
 *  BENCH HALF-FIX (two wire ends, both on reachable sockets):
 *     LCD_RS  -> J4 "BLK"  (GPIO33, ADC1)      <- was J14 D12
 *     LCD_CS  -> J14 "D12" (GPIO12)            <- was J4 BLK
 *     then set TOUCH_Y_ON_ADC1 to 1 below. Vertical touch then survives
 *     WiFi, so every menu works while online. Horizontal still needs
 *     WiFi off, which is why the keyboard drops WiFi while it is open.
 *
 *  Board = "ESP32 Dev Module", COM6. Wiring otherwise as TftShieldID.ino.
 */

#include <Adafruit_GFX.h>
#include <WiFi.h>
#include <Preferences.h>
#include "soc/gpio_struct.h"

// ---- set to 1 AFTER doing the bench half-fix described above ----
#define TOUCH_Y_ON_ADC1 0

// ---- display bus pins ----
static const uint8_t PIN_D[8] = {16, 17, 18, 19, 2, 22, 23, 5};  // LCD_D0..D7
#define PIN_RD  21
#define PIN_WR  14
#if TOUCH_Y_ON_ADC1
  #define PIN_RS  33
  #define PIN_CS  12
#else
  #define PIN_RS  12
  #define PIN_CS  33
#endif
#define PIN_RST 4

// ---- touch pins: the DOCUMENTED mcufriend arrangement, A1/A2/D6/D7 ----
#define T_XP 23      // LCD_D6
#define T_XM PIN_RS  // LCD_RS  -> analog read for the Y (vertical) axis
#define T_YP PIN_WR  // LCD_WR  -> analog read for the X (horizontal) axis
#define T_YM 5       // LCD_D7
#define Z_TOUCH 150

#define MADCTL_VAL 0x28
#define RGB(r,g,b) ((uint16_t)((((r)&0xF8)<<8)|(((g)&0xFC)<<3)|((b)>>3)))

// ---- palette: identical to HelloScreen so both screens are one product --
#define C_BG      0x0861          // #0d1117 near-black, faintly blue
#define C_BAR     0x10A2          // status bar, one step up
#define C_CARD    0x18E3          // #161b22 card fill
#define C_EDGE    0x2124          // hairline, barely there
#define C_DIM     0x4A69
#define C_LABEL   0x8C71
#define C_VALUE   0xFFFF
#define C_GOOD    0x07E8
#define C_BAD     0xF965
#define C_ACCENT  0x07FF
#define C_WARN    0xFFE0
#define C_METAL   0x8C51
#define C_METALD  0x39E7
#define C_GOLD    0xFEA0
#define C_BRONZE  0x8300
#define C_PLUGBODY 0xC618         // a plug seated in the socket mouth

Preferences store;

// ------------------------------------------------- fast 8-bit parallel bus --
static uint32_t lutSet[256], lutClr[256];
static uint32_t WR_MASK, RS_MASK;

static inline void wrByte(uint8_t v) {
  GPIO.out_w1ts = lutSet[v];
  GPIO.out_w1tc = lutClr[v];
  GPIO.out_w1tc = WR_MASK;
  __asm__ __volatile__("nop; nop");
  GPIO.out_w1ts = WR_MASK;
}
static inline void writeCmd(uint8_t c)  { GPIO.out_w1tc = RS_MASK; wrByte(c); GPIO.out_w1ts = RS_MASK; }
static inline void writeData(uint8_t d) { wrByte(d); }

class Ili9486Par8 : public Adafruit_GFX {
public:
  Ili9486Par8() : Adafruit_GFX(480, 320) {}

  void begin() {
    WR_MASK = 1UL << PIN_WR;  RS_MASK = 1UL << PIN_RS;
    for (int v = 0; v < 256; v++) {
      lutSet[v] = lutClr[v] = 0;
      for (int i = 0; i < 8; i++)
        ((v >> i) & 1) ? lutSet[v] |= 1UL << PIN_D[i]
                       : lutClr[v] |= 1UL << PIN_D[i];
    }
    pinMode(PIN_RD, OUTPUT);  digitalWrite(PIN_RD, HIGH);
    pinMode(PIN_CS, OUTPUT);  digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_RST, OUTPUT); digitalWrite(PIN_RST, HIGH);
    busPinsToOutput();
    delay(5);
    digitalWrite(PIN_RST, LOW);  delay(20);
    digitalWrite(PIN_RST, HIGH); delay(120);
    select();
    writeCmd(0x11); delay(120);
    writeCmd(0x3A); writeData(0x55);
    writeCmd(0x36); writeData(MADCTL_VAL);
    writeCmd(0x20);
    writeCmd(0x29); delay(20);
  }
  void select()   { digitalWrite(PIN_CS, LOW);  }
  void deselect() { digitalWrite(PIN_CS, HIGH); }
  void busPinsToOutput() {
    for (int i = 0; i < 8; i++) pinMode(PIN_D[i], OUTPUT);
    pinMode(PIN_WR, OUTPUT); digitalWrite(PIN_WR, HIGH);
    pinMode(PIN_RS, OUTPUT); digitalWrite(PIN_RS, HIGH);
  }
  void setWindow(int x0, int y0, int x1, int y1) {
    writeCmd(0x2A); writeData(x0 >> 8); writeData(x0); writeData(x1 >> 8); writeData(x1);
    writeCmd(0x2B); writeData(y0 >> 8); writeData(y0); writeData(y1 >> 8); writeData(y1);
    writeCmd(0x2C);
  }
  void drawPixel(int16_t x, int16_t y, uint16_t c) override {
    if (x < 0 || y < 0 || x >= _width || y >= _height) return;
    setWindow(x, y, x, y); writeData(c >> 8); writeData(c);
  }
  void fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t c) override {
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > _width)  w = _width  - x;
    if (y + h > _height) h = _height - y;
    if (w <= 0 || h <= 0) return;
    setWindow(x, y, x + w - 1, y + h - 1);
    uint8_t hi = c >> 8, lo = c;
    for (uint32_t n = (uint32_t)w * h; n; n--) { writeData(hi); writeData(lo); }
  }
  void fillScreen(uint16_t c) override { fillRect(0, 0, _width, _height, c); }
};

Ili9486Par8 tft;

// ------------------------------------------------------------------- touch --
static void touchDone() { tft.busPinsToOutput(); tft.select(); }

int tsRawX() {                      // needs ADC2 -> WiFi must be OFF
  tft.deselect();
  pinMode(T_YP, INPUT);  pinMode(T_YM, INPUT);
  pinMode(T_XP, OUTPUT); digitalWrite(T_XP, HIGH);
  pinMode(T_XM, OUTPUT); digitalWrite(T_XM, LOW);
  delayMicroseconds(150);
  int v = analogRead(T_YP);
  touchDone();
  return v;
}
int tsRawY() {
  tft.deselect();
  pinMode(T_XP, INPUT);  pinMode(T_XM, INPUT);
  pinMode(T_YP, OUTPUT); digitalWrite(T_YP, HIGH);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, LOW);
  delayMicroseconds(150);
  int v = analogRead(T_XM);
  touchDone();
  return v;
}
// z1 rises and z2 FALLS under a real press. Reading both tells a genuine
// press apart from a line that is simply stuck high -- they look identical
// if you only ever look at z1.
int tsZ2 = 0;
int tsZ() {
  tft.deselect();
  pinMode(T_XP, OUTPUT); digitalWrite(T_XP, LOW);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, HIGH);
  pinMode(T_XM, INPUT);  pinMode(T_YP, INPUT);
  delayMicroseconds(150);
  int z = analogRead(T_XM);
  tsZ2 = analogRead(T_YP);
  touchDone();
  return z;
}
static int med5(int *s) {
  for (int i = 1; i < 5; i++)
    for (int j = i; j > 0 && s[j] < s[j-1]; j--) { int t = s[j]; s[j] = s[j-1]; s[j-1] = t; }
  return s[2];
}

// Calibration. A unit must NEVER greet its owner with a calibration chore --
// it boots to the dashboard using these factory defaults, and "Calibrate
// touch" in Settings is there only if a panel turns out to sit differently.
#define DEF_SWAP  false
#define DEF_XBASE  500
#define DEF_XSPAN  3000      // raw delta from screen x=40 to x=440
#define DEF_YBASE  500
#define DEF_YSPAN  2600      // raw delta from screen y=40 to y=280

bool  swapAxes = DEF_SWAP;
long  xBase = DEF_XBASE, xSpan = DEF_XSPAN;
long  yBase = DEF_YBASE, ySpan = DEF_YSPAN;
bool  calDone = false;

void calLoad() {
  store.begin("freeisp", true);
  calDone  = store.getBool("tcal", false);
  swapAxes = store.getBool("tswap", DEF_SWAP);
  xBase = store.getLong("txb", DEF_XBASE); xSpan = store.getLong("txs", DEF_XSPAN);
  yBase = store.getLong("tyb", DEF_YBASE); ySpan = store.getLong("tys", DEF_YSPAN);
  store.end();
  if (xSpan == 0) xSpan = 1;
  if (ySpan == 0) ySpan = 1;
}
void calSave() {
  store.begin("freeisp", false);
  store.putBool("tcal", true);   store.putBool("tswap", swapAxes);
  store.putLong("txb", xBase);   store.putLong("txs", xSpan);
  store.putLong("tyb", yBase);   store.putLong("tys", ySpan);
  store.end();
  calDone = true;
}

int lastRawX = 0, lastRawY = 0, lastZ = 0;   // for the serial trace

bool readTouch(int *sx, int *sy) {
  lastZ = tsZ();
  if (lastZ < Z_TOUCH) return false;
  int xs[5], ys[5];
  for (int i = 0; i < 5; i++) { xs[i] = tsRawX(); ys[i] = tsRawY(); }
  if (tsZ() < Z_TOUCH) return false;
  int rx = med5(xs), ry = med5(ys);
  lastRawX = rx; lastRawY = ry;
  long forX = swapAxes ? ry : rx, forY = swapAxes ? rx : ry;
  *sx = constrain(40 + (int)((forX - xBase) * 400 / xSpan), 0, 479);
  *sy = constrain(40 + (int)((forY - yBase) * 240 / ySpan), 0, 319);
  return true;
}
// one tap, debounced, waits for the finger to lift
bool getTap(int *sx, int *sy) {
  if (!readTouch(sx, sy)) return false;
  uint32_t t0 = millis();
  while (tsZ() >= Z_TOUCH && millis() - t0 < 2000) delay(10);
  delay(60);
  return true;
}

// ------------------------------------------------------------- calibration --
const int CX[3] = {40, 440,  40};
const int CY[3] = {40,  40, 280};

void runCalibration() {
  int rx[3], ry[3];
  for (int i = 0; i < 3; i++) {
    tft.fillScreen(C_BG);
    tft.setTextSize(2); tft.setTextColor(C_VALUE);
    tft.setCursor(90, 150); tft.print("TAP THE CIRCLE");
    tft.setTextColor(C_LABEL);
    tft.setCursor(120, 180); tft.print(String(i + 1) + " of 3");
    tft.drawFastHLine(CX[i]-14, CY[i], 29, C_ACCENT);
    tft.drawFastVLine(CX[i], CY[i]-14, 29, C_ACCENT);
    tft.drawCircle(CX[i], CY[i], 9, C_ACCENT);
    while (tsZ() < Z_TOUCH) delay(10);
    int xs[5], ys[5];
    for (int k = 0; k < 5; k++) { xs[k] = tsRawX(); ys[k] = tsRawY(); }
    rx[i] = med5(xs); ry[i] = med5(ys);
    while (tsZ() >= Z_TOUCH) delay(10);
    delay(150);
  }
  long dX_rx = rx[1]-rx[0], dX_ry = ry[1]-ry[0];
  long dY_rx = rx[2]-rx[0], dY_ry = ry[2]-ry[0];
  swapAxes = (labs(dX_rx) < labs(dX_ry));
  if (!swapAxes) { xBase = rx[0]; xSpan = dX_rx; yBase = ry[0]; ySpan = dY_ry; }
  else           { xBase = ry[0]; xSpan = dX_ry; yBase = rx[0]; ySpan = dY_rx; }
  if (xSpan == 0) xSpan = 1;
  if (ySpan == 0) ySpan = 1;
  calSave();
}

// ---------------------------------------------------------------- widgets --
void textAt(int x, int y, uint8_t size, uint16_t col, const String& s) {
  tft.setTextSize(size); tft.setTextColor(col); tft.setCursor(x, y); tft.print(s);
}

void header(const String& title, bool back) {
  tft.fillRect(0, 0, 480, 44, C_BAR);
  tft.drawFastHLine(0, 44, 480, C_EDGE);
  if (back) {                                  // a real chevron, not a letter
    for (int i = 0; i < 12; i++) {
      tft.drawFastVLine(18 + i, 22 - i, 2, C_ACCENT);
      tft.drawFastVLine(18 + i, 22 + i, 2, C_ACCENT);
    }
    textAt(40, 15, 2, C_ACCENT, "Back");
  }
  textAt(back ? 130 : 16, 15, 2, C_VALUE, title);
}

// a Creality-style settings row: full width, big target, chevron on the right
const int ROW_H = 52, ROW_TOP = 52;
void row(int i, const String& name, const String& val, uint16_t valCol = C_LABEL) {
  int y = ROW_TOP + i * ROW_H;
  tft.fillRect(8, y, 464, ROW_H - 6, C_CARD);
  tft.drawRect(8, y, 464, ROW_H - 6, C_EDGE);
  textAt(22, y + 14, 2, C_VALUE, name);
  int vw = val.length() * 12;
  textAt(444 - vw, y + 14, 2, valCol, val);
}
int rowHit(int sy) {                       // which row a tap landed on, -1 = none
  if (sy < ROW_TOP) return -1;
  int i = (sy - ROW_TOP) / ROW_H;
  return (i >= 0 && i < 5) ? i : -1;
}

void pill(int x, int y, const String& s, uint16_t bg) {
  int w = s.length() * 12 + 16;
  tft.fillRoundRect(x, y, w, 24, 12, bg);
  textAt(x + 8, y + 5, 2, C_BG, s);
}

// ------------------------------------------------------------ home screen --
// The dashboard's own language, scaled up: two big numbers on cards, a
// router state pill, and the five sockets drawn as sockets.
int  usersOnline = 42, pppoeOnline = 17;     // demo values until we merge
bool routerOk = true;
String rosUptime = "6d 04:11";
uint8_t portState[5] = {2, 2, 1, 0, 2};      // 0 empty, 1 link, 2 running

void drawJack(int x, int y, uint8_t st) {
  uint16_t shell = (st == 0) ? C_METALD : C_METAL;
  uint16_t pins  = (st == 0) ? C_BRONZE : C_GOLD;
  tft.fillRoundRect(x, y, 56, 46, 4, shell);
  tft.fillRect(x + 6, y + 8, 44, 30, C_BG);            // the mouth
  for (int i = 0; i < 8; i++)                          // eight contacts
    tft.fillRect(x + 9 + i * 5, y + 11, 3, 12, pins);
  tft.fillRect(x + 20, y + 38, 16, 8, shell);          // the latch notch
  if (st == 2) tft.fillRect(x + 8, y + 26, 40, 10, C_PLUGBODY);
}

void drawHome() {
  tft.fillScreen(C_BG);
  tft.fillRect(0, 0, 480, 44, C_BAR);
  textAt(16, 15, 2, C_VALUE, "FreeISP");
  bool wifiUp = (WiFi.status() == WL_CONNECTED);
  pill(360, 10, wifiUp ? "ONLINE" : "OFFLINE", wifiUp ? C_GOOD : C_BAD);
  tft.drawFastHLine(0, 44, 480, C_EDGE);

  // two headline numbers
  tft.fillRect(12, 56, 220, 92, C_CARD);
  tft.drawRect(12, 56, 220, 92, C_EDGE);
  textAt(26, 66, 1, C_LABEL, "USERS ONLINE");
  textAt(26, 88, 5, C_ACCENT, String(usersOnline));
  tft.fillRect(248, 56, 220, 92, C_CARD);
  tft.drawRect(248, 56, 220, 92, C_EDGE);
  textAt(262, 66, 1, C_LABEL, "PPPoE");
  textAt(262, 88, 5, C_GOOD, String(pppoeOnline));

  // router state row
  pill(12, 158, routerOk ? "UP" : "DOWN", routerOk ? C_GOOD : C_BAD);
  textAt(90, 163, 2, C_VALUE, rosUptime);

  // the faceplate
  textAt(12, 196, 1, C_LABEL, "PORTS");
  for (int i = 0; i < 5; i++) {
    int jx = 12 + i * 66;
    drawJack(jx, 210, portState[i]);
    textAt(jx + 20, 260, 1, portState[i] ? C_VALUE : C_DIM, String(i + 1));
  }

  // the one touch affordance on this screen
  tft.fillRoundRect(330, 208, 138, 56, 8, C_CARD);
  tft.drawRoundRect(330, 208, 138, 56, 8, C_ACCENT);
  textAt(352, 228, 2, C_ACCENT, "SETTINGS");
  tft.drawFastHLine(0, 286, 480, C_EDGE);
  textAt(12, 298, 1, C_DIM, wifiUp ? WiFi.SSID() + "   " + WiFi.localIP().toString()
                                   : String("not connected - tap SETTINGS > WiFi"));
}

// -------------------------------------------------------------- settings --
enum Screen { SCR_HOME, SCR_SETTINGS, SCR_WIFI, SCR_PASS, SCR_INFO };
Screen screen = SCR_HOME;

String wifiSsid, wifiPass;
void credsLoad() {
  store.begin("freeisp", true);
  wifiSsid = store.getString("wifi_ssid", "");
  wifiPass = store.getString("wifi_pass", "");
  store.end();
}
void credsSave() {
  store.begin("freeisp", false);
  store.putString("wifi_ssid", wifiSsid);
  store.putString("wifi_pass", wifiPass);
  store.end();
}

void drawSettings() {
  tft.fillScreen(C_BG);
  header("Settings", true);
  bool up = (WiFi.status() == WL_CONNECTED);
  row(0, "WiFi",      up ? WiFi.SSID() : (wifiSsid.length() ? wifiSsid : "not set"),
      up ? C_GOOD : C_WARN);
  row(1, "Screen",    "brightness", C_LABEL);
  row(2, "Alarm",     "armed", C_GOOD);
  row(3, "Info",      "", C_LABEL);
  row(4, "Calibrate touch", "", C_LABEL);
}

// ------------------------------------------------------------ WiFi screen --
int    netCount = 0;
String netSsid[12];
int    netRssi[12];
bool   netLock[12];
int    netTop = 0;                       // scroll offset

void wifiScan() {
  tft.fillScreen(C_BG);
  header("WiFi", true);
  textAt(150, 150, 2, C_LABEL, "scanning...");
  WiFi.mode(WIFI_STA);
  int n = WiFi.scanNetworks();
  netCount = min(n, 12);
  for (int i = 0; i < netCount; i++) {
    netSsid[i] = WiFi.SSID(i);
    netRssi[i] = WiFi.RSSI(i);
    netLock[i] = (WiFi.encryptionType(i) != WIFI_AUTH_OPEN);
  }
  netTop = 0;
}

void drawBars(int x, int y, int rssi) {          // 4-bar signal glyph
  int bars = rssi > -55 ? 4 : rssi > -65 ? 3 : rssi > -75 ? 2 : 1;
  for (int b = 0; b < 4; b++)
    tft.fillRect(x + b * 7, y + 14 - b * 4, 5, 4 + b * 4,
                 b < bars ? C_GOOD : C_EDGE);
}

void drawWifiList() {
  tft.fillScreen(C_BG);
  header("WiFi", true);
  if (netCount == 0) { textAt(120, 150, 2, C_WARN, "no networks found"); return; }
  for (int i = 0; i < 4 && netTop + i < netCount; i++) {
    int k = netTop + i, y = ROW_TOP + i * ROW_H;
    tft.fillRect(8, y, 464, ROW_H - 6, C_CARD);
    tft.drawRect(8, y, 464, ROW_H - 6, C_EDGE);
    String s = netSsid[k];
    if (s.length() > 24) s = s.substring(0, 24);
    textAt(22, y + 14, 2, s == wifiSsid ? C_ACCENT : C_VALUE, s);
    if (netLock[k]) textAt(408, y + 14, 2, C_LABEL, "*");
    drawBars(432, y + 12, netRssi[k]);
  }
  if (netCount > 4) {                            // a MORE row to page through
    int y = ROW_TOP + 4 * ROW_H;
    tft.fillRect(8, y, 464, ROW_H - 6, C_BAR);
    tft.drawRect(8, y, 464, ROW_H - 6, C_EDGE);
    textAt(196, y + 14, 2, C_ACCENT, "MORE");
  }
}

// ------------------------------------------------- on-screen keyboard -----
// WiFi is switched OFF while this is open, because typing needs the
// horizontal touch axis, which is on ADC2.
const char* KB_ROWS[4] = {"1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm"};
bool kbShift = false;
String kbBuf;

void drawKeyboard() {
  tft.fillScreen(C_BG);
  header("Password", true);
  tft.fillRect(8, 50, 464, 34, C_CARD);
  tft.drawRect(8, 50, 464, 34, C_ACCENT);
  String shown = kbBuf;
  if (shown.length() > 36) shown = shown.substring(shown.length() - 36);
  textAt(16, 60, 2, C_VALUE, shown + "_");

  for (int r = 0; r < 4; r++) {
    int n = strlen(KB_ROWS[r]);
    int x0 = (480 - n * 47) / 2;
    for (int c = 0; c < n; c++) {
      int x = x0 + c * 47, y = 92 + r * 42;
      tft.fillRoundRect(x, y, 44, 38, 5, C_CARD);
      tft.drawRoundRect(x, y, 44, 38, 5, C_EDGE);
      char ch = KB_ROWS[r][c];
      if (kbShift && ch >= 'a' && ch <= 'z') ch -= 32;
      tft.setTextSize(2); tft.setTextColor(C_VALUE);
      tft.setCursor(x + 16, y + 11); tft.print(ch);
    }
  }
  // bottom function row
  struct { int x, w; const char* s; uint16_t c; } fn[4] = {
    {8, 100, "SHIFT", kbShift ? C_ACCENT : C_LABEL},
    {114, 150, "SPACE", C_LABEL},
    {270, 90, "DEL", C_WARN},
    {368, 104, "JOIN", C_GOOD}
  };
  for (int i = 0; i < 4; i++) {
    tft.fillRoundRect(fn[i].x, 264, fn[i].w, 44, 6, C_CARD);
    tft.drawRoundRect(fn[i].x, 264, fn[i].w, 44, 6, fn[i].c);
    int tw = strlen(fn[i].s) * 12;
    textAt(fn[i].x + (fn[i].w - tw) / 2, 278, 2, fn[i].c, fn[i].s);
  }
}

bool kbTap(int sx, int sy) {           // returns true when JOIN was pressed
  if (sy >= 264) {
    if (sx < 108)       kbShift = !kbShift;
    else if (sx < 264)  kbBuf += ' ';
    else if (sx < 360) { if (kbBuf.length()) kbBuf.remove(kbBuf.length() - 1); }
    else                return true;
    drawKeyboard();
    return false;
  }
  if (sy >= 92 && sy < 92 + 4 * 42) {
    int r = (sy - 92) / 42;
    int n = strlen(KB_ROWS[r]);
    int x0 = (480 - n * 47) / 2;
    int c = (sx - x0) / 47;
    if (c >= 0 && c < n && sx >= x0) {
      char ch = KB_ROWS[r][c];
      if (kbShift && ch >= 'a' && ch <= 'z') ch -= 32;
      kbBuf += ch;
      drawKeyboard();
    }
  }
  return false;
}

// ----------------------------------------------------------------- joining --
void joinWifi() {
  tft.fillScreen(C_BG);
  header("WiFi", false);
  textAt(60, 140, 2, C_LABEL, "joining " + wifiSsid + " ...");
  WiFi.mode(WIFI_STA);
  if (wifiPass.length()) WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
  else                   WiFi.begin(wifiSsid.c_str());
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) delay(250);
  tft.fillRect(0, 130, 480, 80, C_BG);
  if (WiFi.status() == WL_CONNECTED) {
    credsSave();
    textAt(60, 140, 2, C_GOOD, "connected");
    textAt(60, 170, 2, C_VALUE, WiFi.localIP().toString());
    // WiFi power-save OFF: the ESP32 otherwise dozes and misses the AP's ARP
    WiFi.setSleep(false);
  } else {
    textAt(60, 140, 2, C_BAD, "could not join");
    textAt(60, 170, 2, C_LABEL, "check the password and try again");
  }
  delay(2200);
}

void drawInfo() {
  tft.fillScreen(C_BG);
  header("Info", true);
  const char* k[5] = {"Screen", "Controller", "Touch", "WiFi", "IP"};
  String v[5] = {"3.5\" 480x320", "ILI9486 par8",
                 calDone ? "calibrated" : "not calibrated",
                 WiFi.status() == WL_CONNECTED ? WiFi.SSID() : "offline",
                 WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : "-"};
  for (int i = 0; i < 5; i++) {
    int y = ROW_TOP + i * 50;
    textAt(22, y, 2, C_LABEL, k[i]);
    textAt(200, y, 2, C_VALUE, v[i]);
  }
}

// Idle reading of both sense pins, in the exact pin state tsZ() uses.
// Untouched, XM should sit LOW (it is tied to XP=LOW through the plate).
void adcProbe(const char* when) {
  tft.deselect();
  pinMode(T_XP, OUTPUT); digitalWrite(T_XP, LOW);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, HIGH);
  pinMode(T_XM, INPUT);  pinMode(T_YP, INPUT);
  delayMicroseconds(200);
  int a = analogRead(T_XM), b = analogRead(T_YP);
  tft.busPinsToOutput(); tft.select();
  Serial.printf("ADC probe %-9s XM(GPIO%d)=%4d  YP(GPIO%d)=%4d\n",
                when, T_XM, a, T_YP, b);
}

// Are these two pins joined by a few hundred ohms (a plate) or open?
// Pull one up, drive the other low: joined -> the pulled-up pin reads LOW.
bool joined(uint8_t a, uint8_t b) {
  tft.deselect();
  pinMode(b, OUTPUT); digitalWrite(b, LOW);
  pinMode(a, INPUT_PULLUP);
  delayMicroseconds(400);
  bool j = (digitalRead(a) == LOW);
  pinMode(a, INPUT); pinMode(b, INPUT);
  tft.busPinsToOutput(); tft.select();
  return j;
}

// The decisive test. X and Y plates must each read JOINED (that is the film
// itself). The two plates must read APART when nobody is touching, and
// JOINED only under a press. Anything else names the fault outright.
void plateCheck() {
  for (int i = 0; i < 5; i++) {
    bool xp = joined(T_XM, T_XP);     // is the X plate there at all?
    bool yp = joined(T_YP, T_YM);     // is the Y plate there at all?
    bool cross = joined(T_XM, T_YP);  // are the plates touching each other?
    Serial.printf("plates: Xplate=%-5s Yplate=%-5s cross=%-5s   %s\n",
                  xp ? "OK" : "OPEN", yp ? "OK" : "OPEN", cross ? "TOUCH" : "apart",
                  (!xp || !yp) ? "<-- a plate wire is not connected"
                  : cross      ? "<-- something is pressing the glass"
                               : "<-- healthy and idle");
    delay(600);
  }
}

// ------------------------------------------------------------------ sketch --
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> BigUI: FreeISP touch face on the 3.5\" ILI9486");
  tft.begin();
  calLoad();
  credsLoad();
  Serial.printf("touch pins: XP=%d XM=%d YP=%d YM=%d   cal:%s swap=%d "
                "x %ld+%ld  y %ld+%ld\n",
                T_XP, T_XM, T_YP, T_YM, calDone ? "stored" : "factory",
                swapAxes, xBase, xSpan, yBase, ySpan);

  // Both touch sense pins are ADC2, and ADC2 is shared with the radio.
  // Measure the same idle reading three times -- cold, with the radio up,
  // and after it is shut down -- so the effect is proven, not assumed.
  adcProbe("cold");
  WiFi.mode(WIFI_STA); delay(400);
  adcProbe("radio ON");
  WiFi.mode(WIFI_OFF); delay(400);
  adcProbe("radio OFF");
  plateCheck();
  // A resistive panel that reports "pressed" with nobody touching it makes
  // every real tap invisible -- the UI cannot tell the difference. Say so on
  // the glass rather than appearing dead.
  // The film's four wires land on the same header pins the LCD uses, so the
  // display can be perfect while the touch panel is electrically absent.
  // Check the plates themselves and, if they are open, say so on the glass
  // with a LIVE readout so the tail can be re-seated and watched.
  if (!joined(T_XM, T_XP) || !joined(T_YP, T_YM)) {
    Serial.println("TOUCH PANEL NOT CONNECTED: one or both plates open");
    tft.fillScreen(C_BG);
    header("Touch not connected", false);
    textAt(20,  62, 2, C_WARN, "The display is fine. The touch");
    textAt(20,  88, 2, C_WARN, "film is not reaching the board.");
    textAt(20, 128, 2, C_VALUE, "Look at the FRONT of the glass:");
    textAt(20, 154, 2, C_VALUE, "the thin 4-wire ribbon at its edge");
    textAt(20, 180, 2, C_VALUE, "has come loose. Press it gently");
    textAt(20, 206, 2, C_VALUE, "back into its slot and watch below.");
    while (true) {                        // live, so the fix is visible
      bool xp = joined(T_XM, T_XP), yp = joined(T_YP, T_YM);
      char l[44];
      snprintf(l, sizeof(l), "X plate %-4s   Y plate %-4s ",
               xp ? "OK" : "OPEN", yp ? "OK" : "OPEN");
      textAt(20, 250, 2, (xp && yp) ? C_GOOD : C_BAD, l);
      if (xp && yp) { textAt(20, 282, 2, C_GOOD, "CONNECTED - restarting"); delay(1000); ESP.restart(); }
      delay(250);
    }
  }

  if (wifiSsid.length()) {                 // silent auto-join with saved creds
    WiFi.mode(WIFI_STA);
    if (wifiPass.length()) WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
    else                   WiFi.begin(wifiSsid.c_str());
    uint32_t t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 8000) delay(200);
    if (WiFi.status() == WL_CONNECTED) WiFi.setSleep(false);
  }
  drawHome();
}

int pickedNet = -1;

void loop() {
  int sx, sy;

  // Touch trace: reports what the panel is really doing, pressed or not, so
  // a "it doesn't tap" report can be diagnosed from the numbers instead of
  // from theories. z is pressure; it must rise above Z_TOUCH for a tap.
  static uint32_t lastTrace = 0;
  if (millis() - lastTrace > 1000) {
    lastTrace = millis();
    int z = tsZ();
    Serial.printf("trace z1=%4d z2=%4d  %s\n", z, tsZ2,
                  (z >= Z_TOUCH && tsZ2 > 3500) ? "STUCK (z1 high but z2 also high)"
                  : (z >= Z_TOUCH)              ? "pressed"
                                                : "idle");
  }

  if (!getTap(&sx, &sy)) { delay(20); return; }
  Serial.printf("TAP raw %d,%d z=%d -> screen %d,%d  (on screen %d)\n",
                lastRawX, lastRawY, lastZ, sx, sy, screen);

  switch (screen) {
    case SCR_HOME:
      if (sx > 330 && sy > 208 && sy < 264) { screen = SCR_SETTINGS; drawSettings(); }
      break;

    case SCR_SETTINGS: {
      if (sy < 44) { screen = SCR_HOME; drawHome(); break; }
      int r = rowHit(sy);
      if (r == 0) {                        // WiFi: scan needs the radio on
        screen = SCR_WIFI; wifiScan(); drawWifiList();
      } else if (r == 3) {
        screen = SCR_INFO; drawInfo();
      } else if (r == 4) {
        runCalibration(); drawSettings();
      }
      break;
    }

    case SCR_WIFI: {
      if (sy < 44) { screen = SCR_SETTINGS; drawSettings(); break; }
      int r = rowHit(sy);
      if (r == 4 && netCount > 4) {        // MORE -> next page of networks
        netTop = (netTop + 4 >= netCount) ? 0 : netTop + 4;
        drawWifiList();
      } else if (r >= 0 && netTop + r < netCount) {
        pickedNet = netTop + r;
        wifiSsid  = netSsid[pickedNet];
        if (!netLock[pickedNet]) {         // open network: no password needed
          wifiPass = "";
          joinWifi(); screen = SCR_HOME; drawHome();
        } else {
          // typing needs the horizontal axis -> the radio must be off
          WiFi.mode(WIFI_OFF); delay(100);
          kbBuf = ""; kbShift = false;
          screen = SCR_PASS; drawKeyboard();
        }
      }
      break;
    }

    case SCR_PASS:
      if (sy < 44) { screen = SCR_WIFI; wifiScan(); drawWifiList(); break; }
      if (kbTap(sx, sy)) {
        wifiPass = kbBuf;
        joinWifi();
        screen = SCR_HOME; drawHome();
      }
      break;

    case SCR_INFO:
      screen = SCR_SETTINGS; drawSettings();
      break;
  }
}
