/* FaceUI -- six full-width touch rows on the fitted ESP32 shield.
 * Untouched PinTrace scan measured electrode pairs GPIO16/33 and GPIO17/21.
 * LCD wiring stays unchanged. CS is a touch electrode, so WR/RD must remain
 * inactive during touch and CS output mode must be restored before drawing.
 * Only GPIO33 is an ADC input. Vertical accuracy requires the on-device
 * calibration and independent row checks; a correct pin map alone is not proof.
 * No WiFi is linked.
 */

#include <Adafruit_GFX.h>
#include <Preferences.h>
#include "driver/gpio.h"
#include "soc/gpio_struct.h"

static const uint8_t PIN_D[8] = {16, 17, 18, 19, 2, 22, 23, 5};
#define PIN_WR  14
#define PIN_RS  33
#define PIN_CS  21
#define PIN_RD  12
#define PIN_RST 4

#define T_XP 16        // LCD_D0, paired with GPIO33
#define T_XM PIN_RS    // LCD_RS / GPIO33, ADC1
#define T_YP PIN_CS    // LCD_CS / GPIO21, paired with GPIO17 (digital only)
#define T_YM 17        // LCD_D1

// 0 = normal product UI (the default).  1 = raw grid diagnostic only.
// The grid intentionally replaces the UI, so keep this switch explicit: a
// grid build cannot reach the Settings > Calibrate touch menu.
#define FACEUI_GRID_DIAGNOSTIC 0

#define RGB(r,g,b) ((uint16_t)((((r)&0xF8)<<8)|(((g)&0xFC)<<3)|((b)>>3)))
#define C_BG   RGB(13,17,23)
#define C_OK   RGB(63,185,80)
#define C_TXT  0xFFFF

static uint32_t lutSet[256], lutClr[256], WR_MASK;
#if PIN_RS >= 32
  #define RS_LOW()   GPIO.out1_w1tc.val = (1UL << (PIN_RS - 32))
  #define RS_HIGH()  GPIO.out1_w1ts.val = (1UL << (PIN_RS - 32))
#else
  #define RS_LOW()   GPIO.out_w1tc = (1UL << PIN_RS)
  #define RS_HIGH()  GPIO.out_w1ts = (1UL << PIN_RS)
#endif

static inline void wrByte(uint8_t v) {
  GPIO.out_w1ts = lutSet[v];
  GPIO.out_w1tc = lutClr[v];
  __asm__ __volatile__("nop;nop;nop;nop");
  GPIO.out_w1tc = WR_MASK;
  __asm__ __volatile__("nop;nop;nop;nop");
  GPIO.out_w1ts = WR_MASK;
  __asm__ __volatile__("nop;nop");
}
static inline void writeCmd(uint8_t c)  { RS_LOW(); wrByte(c); RS_HIGH(); }
static inline void writeData(uint8_t d) { wrByte(d); }

class Lcd : public Adafruit_GFX {
public:
  Lcd() : Adafruit_GFX(480, 320) {}
  void begin() {
    WR_MASK = 1UL << PIN_WR;
    for (int v = 0; v < 256; v++) {
      lutSet[v] = lutClr[v] = 0;
      for (int i = 0; i < 8; i++)
        ((v >> i) & 1) ? lutSet[v] |= 1UL << PIN_D[i] : lutClr[v] |= 1UL << PIN_D[i];
    }
    pinMode(PIN_RD, OUTPUT);  digitalWrite(PIN_RD, HIGH);
    pinMode(PIN_CS, OUTPUT);  digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_RST, OUTPUT); digitalWrite(PIN_RST, HIGH);
    busOut(); delay(5);
    digitalWrite(PIN_RST, LOW);  delay(20);
    digitalWrite(PIN_RST, HIGH); delay(120);
    sel();
    writeCmd(0x11); delay(120);
    writeCmd(0x3A); writeData(0x55);
    writeCmd(0x36); writeData(0x28);
    writeCmd(0x20);
    writeCmd(0x29); delay(20);
  }
  void sel()   { digitalWrite(PIN_CS, LOW);  }
  void desel() { digitalWrite(PIN_CS, HIGH); }
  void busOut() {
    // Restore both strobes first, then deselect while restoring the data bus.
    pinMode(PIN_WR, OUTPUT); digitalWrite(PIN_WR, HIGH);
    pinMode(PIN_RD, OUTPUT); digitalWrite(PIN_RD, HIGH);
    pinMode(PIN_CS, OUTPUT); digitalWrite(PIN_CS, HIGH);
    for (int i = 0; i < 8; i++) pinMode(PIN_D[i], OUTPUT);
    pinMode(PIN_RS, OUTPUT); digitalWrite(PIN_RS, HIGH);
  }
  void win(int x0, int y0, int x1, int y1) {
    writeCmd(0x2A); writeData(x0>>8); writeData(x0); writeData(x1>>8); writeData(x1);
    writeCmd(0x2B); writeData(y0>>8); writeData(y0); writeData(y1>>8); writeData(y1);
    writeCmd(0x2C);
  }
  void drawPixel(int16_t x, int16_t y, uint16_t c) override {
    if (x < 0 || y < 0 || x >= _width || y >= _height) return;
    win(x,y,x,y); writeData(c>>8); writeData(c);
  }
  void fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t c) override {
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x+w > _width)  w = _width - x;
    if (y+h > _height) h = _height - y;
    if (w <= 0 || h <= 0) return;
    win(x, y, x+w-1, y+h-1);
    uint8_t hi = c>>8, lo = c;
    for (uint32_t n = (uint32_t)w*h; n; n--) { writeData(hi); writeData(lo); }
  }
  void fillScreen(uint16_t c) override { fillRect(0,0,_width,_height,c); }
  // Without these, Adafruit_GFX draws every line pixel by pixel, and each
  // pixel re-sends a full window command -- about 13 bus writes for one
  // dot. A 64-box grid then costs ~170,000 writes and the panel gave up
  // mid-draw and sat WHITE. Routing lines through the windowed fillRect
  // makes the same grid a few hundred writes.
  void drawFastHLine(int16_t x, int16_t y, int16_t w, uint16_t c) override {
    fillRect(x, y, w, 1, c);
  }
  void drawFastVLine(int16_t x, int16_t y, int16_t h, uint16_t c) override {
    fillRect(x, y, 1, h, c);
  }
};
Lcd tft;

static void done() { tft.busOut(); tft.sel(); }

// Release every data electrode. Parking D0/D1 LOW would load the real film.
static void releaseTouchBus() {
  pinMode(PIN_WR, OUTPUT); digitalWrite(PIN_WR, HIGH);
  pinMode(PIN_RD, OUTPUT); digitalWrite(PIN_RD, HIGH);
  for (int i = 0; i < 8; i++) pinMode(PIN_D[i], INPUT);
  pinMode(T_XM, INPUT);
  pinMode(T_YP, INPUT);
}

// Separate contact detection from position: ground one complete plate, then
// check whether contact pulls the other plate LOW against its weak pull-up.
// No ADC threshold, rest calibration, or pressure formula is involved.
static bool contactActive() {
  releaseTouchBus();
  pinMode(T_YP, OUTPUT); digitalWrite(T_YP, LOW);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, LOW);
  pinMode(T_XM, INPUT_PULLUP);
  delayMicroseconds(300);
  for (int i = 0; i < 3; i++) {
    if (digitalRead(T_XM) != LOW) return false;
    delayMicroseconds(100);
  }
  return true;
}

int zRead() {  // Binary contact score retained for the existing status display.
  bool down = contactActive();
  done();
  return down ? 1024 : 0;
}

int touchRawMin = -1, touchRawMax = -1;

// The measured ADC axis runs horizontally in landscape. For vertical rows,
// compare two sink strengths on XP and cancel the shared contact resistance:
// q = [Uw/(V-Uw)] / [Us/(V-Us)]. See DriveProof/README.md and bench results.
// This is a calibrated resistance proxy, not a direct ADC coordinate.
static float driveVoltage(gpio_drive_cap_t strength, bool &ok, bool &clipped) {
  ok = (gpio_set_drive_capability((gpio_num_t)T_XP, strength) == ESP_OK) && ok;
  delayMicroseconds(300);
  unsigned long total = 0;
  for (int i = 0; i < 8; i++) {
    int raw = analogRead(T_XM);
    if (raw <= 5 || raw >= 4090) clipped = true;
    total += analogReadMilliVolts(T_XM);
  }
  return total / 8.0f;
}

int yRead() {
  if (!contactActive()) { done(); return -1; }
  releaseTouchBus();
  pinMode(T_YP, OUTPUT); digitalWrite(T_YP, HIGH);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, HIGH);
  pinMode(T_XP, OUTPUT); digitalWrite(T_XP, LOW);
  gpio_drive_cap_t oldStrength = GPIO_DRIVE_CAP_2;
  bool ok = gpio_get_drive_capability((gpio_num_t)T_XP, &oldStrength) == ESP_OK;
  // The global setter also rebuilds the millivolt calibration handle in
  // Arduino-ESP32 3.3.10. No other ADC channel is used by this sketch.
  analogSetAttenuation(ADC_11db);
  analogReadMilliVolts(T_XM);
  bool pilotClipped = false;
  float pilot = driveVoltage(GPIO_DRIVE_CAP_0, ok, pilotClipped);
  adc_attenuation_t attenuation = pilot < 850 ? ADC_0db :
                                 pilot < 1150 ? ADC_2_5db :
                                 pilot < 1600 ? ADC_6db : ADC_11db;
  analogSetAttenuation(attenuation);
  bool clipped = false;
  float q[8];
  float before = driveVoltage(GPIO_DRIVE_CAP_1, ok, clipped);
  for (int i = 0; i < 8; i++) {
    float weak = driveVoltage(GPIO_DRIVE_CAP_0, ok, clipped);
    float after = driveVoltage(GPIO_DRIVE_CAP_1, ok, clipped);
    float strong = (before + after) * 0.5f;
    q[i] = strong > 0 && weak < 3250 ?
           weak * (3300 - strong) / (strong * (3300 - weak)) : 0;
    before = after;
  }
  ok = (gpio_set_drive_capability((gpio_num_t)T_XP, oldStrength) == ESP_OK) && ok;
  bool stillDown = contactActive();
  done();
  if (!stillDown || clipped || !ok) return -1;
  for (int i = 1; i < 8; i++)
    for (int j = i; j > 0 && q[j] < q[j - 1]; j--) {
      float v = q[j]; q[j] = q[j - 1]; q[j - 1] = v;
    }
  float ratio = (q[3] + q[4]) * 0.5f;
  if (!(ratio > 1.0f && ratio < 10.0f)) return -1;
  touchRawMin = (int)((q[0] - 1) * 10000);
  touchRawMax = (int)((q[7] - 1) * 10000);
  return (int)((ratio - 1) * 10000 + 0.5f);
}

// ---------------------------------------------------------------- palette --
#define C_BAR   RGB(22,27,34)
#define C_CARD  RGB(22,27,34)
#define C_EDGE  RGB(48,54,61)
#define C_LABEL RGB(140,140,150)
#define C_ACC   RGB(31,111,235)
#define C_WARN  RGB(255,210,0)
#define C_BEVEL RGB(58,64,72)       // 1px inner top-light line on every card

// ------------------------------------------------------------- touch state --

// Two short contact checks debounce edges; they do not require a held press.
int tZ1 = 0, tZ2 = -1;
#define T_ON 5
#define T_OFF 3
bool tDown = false;
int tStreak = 0, tLastZ = 0, tLastB = 0;
int peakDev = 0, peakXM = 0, peakY = 0;
int lastTapRounds = 0;
int touchDev() {
  tZ1 = zRead();
  if (tZ1 > peakDev) { peakDev = tZ1; peakXM = tZ1; peakY = tZ2; }
  return tZ1;
}
bool touchDown() {
  tLastZ = touchDev();
  tLastB = tDown;
  bool now = tLastZ > (tDown ? T_OFF : T_ON);
  if (now == tDown) { tStreak = 0; return tDown; }
  if (++tStreak >= 2) { tDown = now; tStreak = 0; }
  return tDown;
}

// One anchor per product row. These anchors belong to the measured pin map.
#define NANCH 6
#define BAND (320 / NANCH)
int anchorRaw[NANCH];
bool calibrated = false;
bool calibrationRequired = false;
int lastTapRaw = -1, lastTapY = -1;
Preferences prefs;
#define CAL_VER 13

int screenY(int raw) {
  int best = 0, bd = 2147483647;
  for (int i = 0; i < NANCH; i++) {
    int d = abs(raw - anchorRaw[i]);
    if (d < bd) { bd = d; best = i; }
  }
  return best * BAND + BAND / 2;    // centre of the nearest measured band
}

int posRead() { return yRead(); }
int readTapRaw() {
  int raw = posRead();
  // A clipped onset may settle during an ordinary tap. Retry once while
  // contact remains; never wait for a long hold or reuse a released sample.
  if (raw < 0 && touchDown()) raw = posRead();
  lastTapRounds = raw < 0 ? 0 : 8;
  if (raw >= 0) {
    tZ2 = raw;
    Serial.printf("tap raw=%d burst=%d..%d\n", raw, touchRawMin, touchRawMax);
  }
  return raw;
}

void textAt(int x,int y,uint8_t sz,uint16_t c,const String&s){
  tft.setTextSize(sz); tft.setTextColor(c); tft.setCursor(x,y); tft.print(s);
}

// Calibration deliberately waits for a human.  It is invoked from loop(),
// but it can legitimately wait longer than the loop task's watchdog period.
static inline void calibrationDelay(uint32_t ms) {
  // No esp_task_wdt_reset() here: loopTask is not subscribed to the task
  // WDT on this core, so the call just spammed "task not found" every 80ms.
  // delay() itself yields, which is all that is needed.
  delay(ms);
}

// Select on press, then require a debounced release before another action.
// No blocking wait-for-release or hold-to-select in the product input path.
bool waitTap(int *sy) {
  static bool consumed = false;
  if (!touchDown()) { consumed = false; return false; }
  if (consumed) return false;
  consumed = true;
  int raw = readTapRaw();
  if (raw < 0) return false;
  *sy = screenY(raw);
  lastTapRaw = raw; lastTapY = *sy;
  Serial.printf("TAP raw=%d -> y=%d\n", raw, *sy);
  return true;
}

// -------------------------------------------------------- NVS persistence --
// Keep the v13 key names stable: the working device's anchors survive UI updates.
// Calibration must describe distinct rows in one consistent direction.
bool calValid(const int *t) {
  int direction = t[NANCH - 1] >= t[0] ? 1 : -1;
  for (int i = 0; i < NANCH; i++) {
    if (t[i] < 0 || t[i] > 90000) return false;
    if (i && (t[i] - t[i - 1]) * direction < 40) return false;
  }
  return abs(t[0] - t[NANCH - 1]) > 300;
}
bool loadCal() {                    // boot path: true = stored cal is usable
  int t[NANCH];
  prefs.begin("freeisp", true);
  bool verOk = prefs.getUChar("vcal_ver", 0) == CAL_VER;
  size_t got = prefs.getBytes("anch6", t, sizeof(t));
  prefs.end();
  if (!verOk || got != sizeof(t) || !calValid(t)) return false;
  memcpy(anchorRaw, t, sizeof(t));
  calibrated = true;
  Serial.printf("CAL loaded band1=%d .. band%d=%d (%d anchors)\n",
                anchorRaw[0], NANCH, anchorRaw[NANCH - 1], NANCH);
  return true;
}
void saveCal() {                    // only ever called from calibrate()
  prefs.begin("freeisp", false);
  prefs.putUChar("vcal_ver", CAL_VER);
  prefs.putBytes("anch6", anchorRaw, sizeof(anchorRaw));
  prefs.end();
  Serial.print("CAL SAVED:");
  for (int i = 0; i < NANCH; i++) Serial.printf(" %d=%d", i + 1, anchorRaw[i]);
  Serial.println("  (factory-default candidates)");
}
void saveU8(const char *key, uint8_t v) {
  prefs.begin("freeisp", false);
  prefs.putUChar(key, v);
  prefs.end();
}

// -------------------------------------------------------- settings state --
const char *BRI[4] = {"100%", "75%", "50%", "25%"};
uint8_t brightIdx  = 0;
bool    alarmArmed = true;

void loadSettings() {               // fresh key names, same rule as the cal
  prefs.begin("freeisp", true);
  brightIdx  = prefs.getUChar("bri2", 0) & 3;
  alarmArmed = prefs.getUChar("alarm2", 1) != 0;
  prefs.end();
}

// ------------------------------------------------------------ calibration --
// Six centres are fitted first. A separate walk near alternating left/right
// edges must select the same rows without modifying any anchor.
static void drawCalGrid(int hotRow, int targetX = 240, bool verify = false) {
  tft.fillScreen(C_BG);
  for (int r = 0; r < NANCH; r++) {
    int top = r * 320 / NANCH, bottom = (r + 1) * 320 / NANCH;
    uint16_t colour = r == hotRow ? C_ACC : C_CARD;
    tft.fillRect(1, top + 1, 478, bottom - top - 2, colour);
    textAt(8, top + 7, 2, C_TXT, String(r + 1));
    if (r == hotRow) {
      int centre = (top + bottom) / 2;
      tft.drawRect(targetX - 10, centre - 10, 20, 20, C_TXT);
      textAt(80, top + 4, 1, C_TXT,
             verify ? "CHECK: tap white square" : "CALIBRATE: tap white square");
    }
  }
}

static int calibrationTap() {
  for (;;) {
    while (!touchDown()) calibrationDelay(3);
    int raw = readTapRaw();
    while (touchDown()) calibrationDelay(3);
    if (raw >= 0) return raw;
  }
}

void calibrate() {
  calibrated = false;
  for (;;) {
    // Do not reuse the press that opened calibration as its first sample.
    while (touchDown()) calibrationDelay(3);
    for (int i = 0; i < NANCH; i++) {
      drawCalGrid(i);
      Serial.printf("CAL target row=%d x=240 y=%d\n", i + 1, (i * 320 / NANCH + (i + 1) * 320 / NANCH) / 2);
      anchorRaw[i] = calibrationTap();
      Serial.printf("CAL row=%d raw=%d\n", i + 1, anchorRaw[i]);
    }
    bool valid = calValid(anchorRaw);
    if (valid) {
      for (int i = 0; i < NANCH; i++) {
        drawCalGrid(i, i % 2 ? 420 : 60, true);
        int raw = calibrationTap();
        int matched = screenY(raw) / BAND;
        Serial.printf("CAL CHECK row=%d raw=%d matched=%d\n", i + 1, raw, matched + 1);
        if (matched != i) valid = false;
      }
    }
    if (valid) {
      calibrated = true;
      saveCal();
      return;
    }
    Serial.println("CAL failed: vertical rows are not repeatably separated; anchors not saved");
    tft.fillScreen(C_BG);
    textAt(36, 100, 2, C_WARN, "Touch rows are not distinct");
    textAt(36, 140, 2, C_TXT, "Calibration was not saved");
    textAt(36, 200, 2, C_TXT, "Tap to repeat the check");
    calibrationTap();
  }
}

// Optional full-width row diagnostic, using the same saved map as the UI.
void gridChrome() { drawCalGrid(-1); }
void gridStep() {
  int sy;
  if (!waitTap(&sy)) { delay(3); return; }
  int row = constrain(sy / BAND, 0, NANCH - 1);
  drawCalGrid(row);
  Serial.printf("GRID row=%d raw=%d\n", row + 1, lastTapRaw);
}

// ------------------------------------------------------------------ screens --
enum { SCR_HOME, SCR_MENU, SCR_INFO } screen = SCR_HOME;

// A subtle top border separates cards from the background.
void bevel(int x, int y, int w) { tft.drawFastHLine(x + 1, y + 1, w - 2, C_BEVEL); }

static int bandTop(int band) { return band * 320 / NANCH; }
static int bandHeight(int band) { return bandTop(band + 1) - bandTop(band); }

void header(const String& title, bool back) {
  tft.fillRect(0, 0, 480, bandHeight(0), C_BAR);
  if (back) textAt(16, 18, 2, C_ACC, "< BACK");
  int x = back ? 240 - title.length() * 6 : 16;
  textAt(x, 18, 2, C_TXT, title);
  tft.drawFastHLine(0, bandTop(1) - 1, 480, C_EDGE);
}

void row(int i, const String& name, const String& val, uint16_t vc) {
  int y = bandTop(i + 1) + 3, h = bandHeight(i + 1) - 6;
  tft.fillRect(8, y, 464, h, C_CARD);
  tft.drawRect(8, y, 464, h, C_EDGE);
  bevel(8, y, 464);
  tft.fillRect(9, y + 1, 3, h - 2, C_ACC);
  int textY = y + (h - 16) / 2;
  textAt(24, textY, 2, C_TXT, name);
  if (val.length()) textAt(448 - val.length() * 12, textY, 2, vc, val);
  else textAt(444, textY, 2, C_ACC, ">");
}

// PRESSED FLASH -- universal. Repaint the element in C_ACC with its text in
// C_BG, hold 140ms, then the caller acts / redraws. No silent taps anywhere.
void flashRow(int i, const String& name) {
  int y = bandTop(i + 1) + 3, h = bandHeight(i + 1) - 6;
  tft.fillRect(8, y, 464, h, C_ACC);
  textAt(24, y + (h - 16) / 2, 2, C_TXT, name);
  delay(160);                         // visible pressed-state feedback
}
void flashHeader(const String& s) {
  tft.fillRect(0, 0, 480, bandHeight(0), C_ACC);
  textAt(16, 18, 2, C_TXT, s);
  delay(160);
}
void drawSettingsBand(bool pressed) {
  int y = bandTop(5);
  tft.fillRect(0, y, 480, 320 - y, pressed ? C_ACC : C_CARD);
  if (!pressed) tft.drawFastHLine(0, y, 480, C_ACC);
  textAt(192, y + 19, 2, C_TXT, "SETTINGS");
  textAt(444, y + 19, 2, C_TXT, ">");
  if (pressed) delay(140);
}

void drawJack(int x, int y, uint8_t st) {
  uint16_t shell = st ? RGB(140,140,145) : RGB(60,60,70);
  uint16_t pins  = st ? RGB(255,210,0)   : RGB(130,100,0);
  tft.fillRoundRect(x, y, 56, 44, 4, shell);
  tft.fillRect(x + 6, y + 8, 44, 28, C_BG);
  for (int i = 0; i < 8; i++) tft.fillRect(x + 9 + i*5, y + 11, 3, 11, pins);
  tft.fillRect(x + 20, y + 36, 16, 8, shell);
}

void drawHome() {
  tft.fillScreen(C_BG);
  header("FreeISP", false);
  tft.fillRoundRect(368, 14, 100, 24, 12, C_WARN);
  textAt(376, 18, 2, C_BG, "OFFLINE");

  tft.fillRect(12, 56, 220, 88, C_CARD); tft.drawRect(12, 56, 220, 88, C_EDGE);
  bevel(12, 56, 220);
  textAt(26, 64, 1, C_LABEL, "USERS ONLINE");
  textAt(26, 84, 5, C_ACC, "42");
  tft.fillRect(248, 56, 220, 88, C_CARD); tft.drawRect(248, 56, 220, 88, C_EDGE);
  bevel(248, 56, 220);
  textAt(262, 64, 1, C_LABEL, "PPPoE");
  textAt(262, 84, 5, C_OK, "17");

  textAt(12, 154, 2, C_LABEL, "PORTS");
  const uint8_t st[5] = {1,1,1,0,1};
  for (int i = 0; i < 5; i++) {            // pitch 100: jack 5 ends at x=468,
    drawJack(12 + i*100, 174, st[i]);      // flush with the cards above
    textAt(12 + i*100 + 25, 224, 1, st[i] ? C_TXT : C_LABEL, String(i + 1));
  }

  textAt(12, 246, 1, C_LABEL, "Sample data - connect a router for live status");
  drawSettingsBand(false);
}

void drawMenu() {
  tft.fillScreen(C_BG);
  header("Settings", true);
  row(0, "WiFi",            "not set",      C_WARN);
  row(1, "Screen preset",   BRI[brightIdx], C_LABEL);
  row(2, "Alarm",           alarmArmed ? "armed" : "off",
                            alarmArmed ? C_OK : C_LABEL);
  row(3, "Calibrate touch", "",             C_LABEL);
  row(4, "About module",    "",             C_LABEL);
}

void drawInfo() {
  tft.fillScreen(C_BG);
  header("About", true);

  tft.fillRect(8, 60, 464, 252, C_CARD);
  tft.drawRect(8, 60, 464, 252, C_EDGE);
  bevel(8, 60, 464);

  textAt(24, 76, 3, C_TXT, "FreeISP module");
  textAt(24, 110, 1, C_LABEL, "FaceUI / " __DATE__);
  tft.drawFastHLine(24, 134, 432, C_EDGE);
  textAt(24, 150, 2, C_LABEL, "Connection");
  textAt(324, 150, 2, C_WARN, "Offline");
  textAt(24, 186, 2, C_LABEL, "Touch setup");
  textAt(348, 186, 2, C_OK, calibrated ? "Saved" : "Needed");
  textAt(24, 226, 1, C_LABEL, "Dashboard values are a preview.");
  textAt(24, 244, 1, C_LABEL, "Screen and alarm presets are stored locally.");
  textAt(24, 284, 2, C_ACC, "Tap anywhere to return");
}

// ------------------------------------------------------------------ sketch --
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> FaceUI: touch pairs 16/33 and 17/21, resistance ratio, calibration v13");
  tft.begin();
  tft.fillScreen(C_BG);
  textAt(90, 150, 2, C_TXT, "starting up...");
  tDown = false; tStreak = 0;
  loadSettings();
#if FACEUI_GRID_DIAGNOSTIC
  // The grid tests the SAVED map, so it needs one -- calibrate first if
  // none is stored, then never adapt again.
  calibrationRequired = !loadCal();
  if (!calibrationRequired) {
    gridChrome();
    Serial.println("GRID READY - press a row; that row must fill");
  }
#else
  calibrationRequired = !loadCal();
  if (calibrationRequired)
    Serial.println("No valid saved calibration; starting first-boot calibration from loop().");
  else
    drawHome();
#endif
}

uint32_t lastPulse = 0;
void loop() {
#if FACEUI_GRID_DIAGNOSTIC
  if (calibrationRequired) {          // from loop(), so the WDT stays fed
    calibrationRequired = false;
    calibrate();
    gridChrome();
    Serial.println("GRID READY - press a row; that row must fill");
    return;
  }
  gridStep();
  return;
#endif
  if (calibrationRequired) {
    calibrationRequired = false;
    calibrate();
    drawHome();
    return;
  }
  int sy;
  // Contact detection is independent of the last drawn colour.
  if (!waitTap(&sy)) {
    // Keep contact and the last position visible in the serial monitor.
    if (millis() - lastPulse >= 1000) {
      lastPulse = millis();
      Serial.printf("UI contact=%d lastRaw=%d score=%d down=%d streak=%d\n",
                    tZ1, tZ2, tLastZ, tDown, tStreak);
    }
    delay(3);
    return;
  }

  if (screen == SCR_HOME) {
    // The bottom calibrated row opens Settings.
    if (sy >= (NANCH - 1) * BAND) {
      drawSettingsBand(true);           // flash...
      screen = SCR_MENU;
      drawMenu();                       // ...then act
    } else {
      drawSettingsBand(true);           // hint flash...
      drawSettingsBand(false);          // ...and restore
    }
  } else if (screen == SCR_MENU) {
    // screenY returns one of six stable anchor centres: BACK, then five rows.
    int r = constrain(sy / BAND, 0, NANCH - 1) - 1;
    Serial.printf("menu row %d\n", r);
    if (r < 0) {
      flashHeader("< BACK");
      screen = SCR_HOME;
      drawHome();
    } else if (r == 0) {
      flashRow(0, "WiFi");              // deliberate stub -- the radio is
      Serial.println("WiFi row: stub, WiFi is the LAST layer");
      row(0, "WiFi", "not set", C_WARN);
    } else if (r == 1) {
      brightIdx = (brightIdx + 1) & 3;
      flashRow(1, "Screen preset");
      row(1, "Screen preset", BRI[brightIdx], C_LABEL);
      saveU8("bri2", brightIdx);
      Serial.printf("bright -> %s\n", BRI[brightIdx]);
    } else if (r == 2) {
      alarmArmed = !alarmArmed;
      flashRow(2, "Alarm");
      row(2, "Alarm", alarmArmed ? "armed" : "off",
                      alarmArmed ? C_OK : C_LABEL);
      saveU8("alarm2", alarmArmed ? 1 : 0);
      Serial.printf("alarm -> %s\n", alarmArmed ? "armed" : "off");
    } else if (r == 3) {
      flashRow(3, "Calibrate touch");
      calibrate();                      // re-saves itself, so re-run and
      drawMenu();                       // persist come free
    } else {
      flashRow(4, "About module");
      screen = SCR_INFO;
      drawInfo();
    }
  } else {                              // SCR_INFO: the whole screen is one
    flashHeader("< BACK");              // 320px band -- tap anywhere to go
    screen = SCR_MENU;                  // back; no gap possible
    drawMenu();
  }
}
