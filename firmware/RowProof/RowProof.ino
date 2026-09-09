/* RowProof -- an accuracy series for the v13 touch path. READ-ONLY.
 *
 * FaceUI v13 works by the owner's confirmation, and its README says the one
 * thing not yet established is error-free performance across positions and
 * ordinary taps: the first independent check went 5/6 with the TOP row
 * selecting row 2 (ratios 1.216 vs 1.256, about 3% apart). This sketch
 * measures that margin instead of guessing at it.
 *
 * It uses the product's sampler VERBATIM (copied from FaceUI.ino by the
 * generator gen_rowproof.py at build time) and the product's SAVED anchors
 * from NVS. It never writes NVS, never calibrates, never adapts. Every tap
 * logs: target row, x, raw, matched row, distance to the nearest and the
 * second-nearest anchor, the margin between them, burst spread, PASS/FAIL.
 *
 * Phase 1: 18 scripted targets (rows 1..6 at x = 60, 240, 420). Tap each
 *          white square with an ordinary tap, not a hold.
 * Phase 2: free taps; the matched row fills. Serial 'r' reprints the summary.
 *
 * Everything between the GENERATED markers is lifted from FaceUI.ino unchanged.
 */

#include <Adafruit_GFX.h>
#include <Preferences.h>
#include "driver/gpio.h"
#include "soc/gpio_struct.h"

// ---- GENERATED from FaceUI.ino: pins, electrode map, colours, LCD, sampler ----
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

#define RGB(r,g,b) ((uint16_t)((((r)&0xF8)<<8)|(((g)&0xFC)<<3)|((b)>>3)))
#define C_BG   RGB(242,243,248)
#define C_OK   RGB(40,154,86)
#define C_TXT  RGB(25,29,38)

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


// ---- end GENERATED ----

#define C_CARD  RGB(18,31,45)
#define C_LABEL RGB(139,161,179)
#define C_ACC   RGB(85,220,218)
#define C_PASS  RGB(63,185,80)
#define C_FAIL  RGB(235,80,80)

#define NANCH 6
#define BAND (320 / NANCH)
int anchorRaw[NANCH];
Preferences prefs;

// Contact debounce: two agreeing rounds flip the state, as in the product.
bool tDown = false; int tStreak = 0;
bool touchDown() {
  bool now = zRead() > 0;
  if (now == tDown) { tStreak = 0; return tDown; }
  if (++tStreak >= 2) { tDown = now; tStreak = 0; }
  return tDown;
}

// Product tap path: sample on press, one retry while contact remains,
// never a held press.
int readTapRaw() {
  int raw = yRead();
  if (raw < 0 && touchDown()) raw = yRead();
  return raw;
}
bool waitTap(int *raw) {
  static bool consumed = false;
  if (!touchDown()) { consumed = false; return false; }
  if (consumed) return false;
  consumed = true;
  *raw = readTapRaw();
  return *raw >= 0;
}

bool loadCal() {
  int t[NANCH];
  prefs.begin("freeisp", true);
  bool verOk = prefs.getUChar("vcal_ver", 0) == 13;
  size_t got = prefs.getBytes("anch6", t, sizeof(t));
  prefs.end();
  if (!verOk || got != sizeof(t)) return false;
  for (int i = 0; i < NANCH; i++) anchorRaw[i] = t[i];
  return true;
}

// Nearest anchor, plus the two distances the margin is made of.
int matchRow(int raw, int *dNear, int *dSecond) {
  int best = 0, bd = 0x7fffffff, sd = 0x7fffffff;
  for (int i = 0; i < NANCH; i++) {
    int d = abs(raw - anchorRaw[i]);
    if (d < bd) { sd = bd; bd = d; best = i; }
    else if (d < sd) sd = d;
  }
  *dNear = bd; *dSecond = sd;
  return best;
}

void textAt(int x, int y, uint8_t sz, uint16_t c, const String &s) {
  tft.setTextSize(sz); tft.setTextColor(c); tft.setCursor(x, y); tft.print(s);
}

void drawRows(int hot, int targetX, uint16_t hotColour, const String &note) {
  tft.fillScreen(C_BG);
  for (int r = 0; r < NANCH; r++) {
    int top = r * BAND, bottom = (r + 1) * BAND;
    tft.fillRect(1, top + 1, 478, bottom - top - 2, r == hot ? hotColour : C_CARD);
    textAt(8, top + 7, 2, r == hot ? 0xFFFF : C_TXT, String(r + 1));
    if (r == hot && targetX >= 0) {
      int cy = (top + bottom) / 2;
      tft.drawRect(targetX - 10, cy - 10, 20, 20, 0xFFFF);
      tft.drawRect(targetX - 11, cy - 11, 22, 22, 0xFFFF);
    }
  }
  textAt(80, 4, 1, C_LABEL, note);
}

// ---- the series ----
const int XS[3] = {60, 240, 420};
int taps[NANCH], passes[NANCH], minMargin[NANCH], rawLo[NANCH], rawHi[NANCH];
long rawSum[NANCH];
int step = 0;                         // 0..17 scripted, then free
bool haveCal = false;

void resetStats() {
  for (int r = 0; r < NANCH; r++) {
    taps[r] = passes[r] = 0; minMargin[r] = 0x7fffffff;
    rawLo[r] = 0x7fffffff; rawHi[r] = -1; rawSum[r] = 0;
  }
}

void record(int targetRow, int x, int raw) {
  int dn, ds;
  int m = matchRow(raw, &dn, &ds);
  int margin = ds - dn;               // how far this tap was from flipping rows
  bool pass = (m == targetRow);
  taps[targetRow]++; if (pass) passes[targetRow]++;
  if (margin < minMargin[targetRow]) minMargin[targetRow] = margin;
  if (raw < rawLo[targetRow]) rawLo[targetRow] = raw;
  if (raw > rawHi[targetRow]) rawHi[targetRow] = raw;
  rawSum[targetRow] += raw;
  Serial.printf("SERIES target=%d x=%d raw=%d burst=%d..%d matched=%d dNear=%d dSecond=%d margin=%d %s\n",
                targetRow + 1, x, raw, touchRawMin, touchRawMax, m + 1, dn, ds, margin,
                pass ? "PASS" : "FAIL");
}

void summary() {
  Serial.println("SUMMARY row  taps pass  raw(min..mean..max)   minMargin");
  int total = 0, ok = 0, weakest = -1, weakestMargin = 0x7fffffff;
  for (int r = 0; r < NANCH; r++) {
    total += taps[r]; ok += passes[r];
    long mean = taps[r] ? rawSum[r] / taps[r] : 0;
    Serial.printf("SUMMARY  %d    %2d   %2d   %5d..%5ld..%5d   %d\n", r + 1, taps[r], passes[r],
                  taps[r] ? rawLo[r] : 0, mean, taps[r] ? rawHi[r] : 0, taps[r] ? minMargin[r] : 0);
    if (taps[r] && minMargin[r] < weakestMargin) { weakestMargin = minMargin[r]; weakest = r; }
  }
  Serial.print("SUMMARY anchors:");
  for (int i = 0; i < NANCH; i++) Serial.printf(" %d", anchorRaw[i]);
  Serial.println();
  Serial.printf("SUMMARY overall %d/%d correct; weakest row %d (min margin %d)\n",
                ok, total, weakest + 1, weakestMargin);
}

void showTarget() {
  int r = step / 3, x = XS[step % 3];
  drawRows(r, x, C_ACC, "SERIES " + String(step + 1) + "/18: tap the white square (normal tap)");
  Serial.printf("TARGET %d/18 row=%d x=%d\n", step + 1, r + 1, x);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> RowProof: v13 sampler, saved anchors, read-only accuracy series");
  tft.begin();
  tft.fillScreen(C_BG);
  tDown = false; tStreak = 0;
  resetStats();
  haveCal = loadCal();
  if (!haveCal) {
    textAt(20, 120, 2, C_TXT, "No saved v13 calibration.");
    textAt(20, 150, 2, C_LABEL, "Run FaceUI and calibrate first.");
    Serial.println("NO CAL: vcal_ver != 13 or anch6 missing. Nothing to test.");
    return;
  }
  Serial.print("anchors:");
  for (int i = 0; i < NANCH; i++) Serial.printf(" %d=%d", i + 1, anchorRaw[i]);
  Serial.println();
  showTarget();
}

void loop() {
  if (!haveCal) { delay(50); return; }
  if (Serial.available()) { if (Serial.read() == 'r') summary(); }
  int raw;
  if (!waitTap(&raw)) { delay(3); return; }
  if (step < 18) {
    int r = step / 3, x = XS[step % 3];
    record(r, x, raw);
    int dn, ds; int m = matchRow(raw, &dn, &ds);
    drawRows(m, -1, m == r ? C_PASS : C_FAIL,
             String(m == r ? "PASS  " : "FAIL  ") + "matched row " + String(m + 1) +
             " (raw " + String(raw) + ")");
    delay(500);
    step++;
    if (step < 18) showTarget();
    else {
      summary();
      drawRows(-1, -1, C_CARD, "FREE MODE: tap any row - it fills. 'r' on serial reprints the summary");
    }
  } else {
    int dn, ds; int m = matchRow(raw, &dn, &ds);
    Serial.printf("FREE raw=%d burst=%d..%d matched=%d margin=%d\n",
                  raw, touchRawMin, touchRawMax, m + 1, ds - dn);
    drawRows(m, -1, C_ACC, "FREE MODE: row " + String(m + 1) + "  raw " + String(raw) +
             "  margin " + String(ds - dn));
  }
}
