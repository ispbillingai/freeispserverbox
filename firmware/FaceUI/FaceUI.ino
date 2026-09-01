/*  FaceUI.ino -- the FreeISP touch face, built UP from what works.
 *
 *  BigUI.ino was built top-down and its touch read froze at 4095 for
 *  reasons that survived every fix. TouchProof.ino, on the same wiring,
 *  reads 0 idle and ~830 pressed. So this file starts from TouchProof's
 *  EXACT display + touch core, byte for byte, and adds interface on top --
 *  one layer at a time, touch re-checked after each. No WiFi yet: that is
 *  the last layer to go on, not the first.
 *
 *  Layers on the core so far:
 *      1. HOME / SETTINGS / INFO screens in the product palette, bevelled
 *         cards, one accent colour.
 *      2. Y-only hit maps: touch is VERTICAL-ONLY (the horizontal axis
 *         would need GPIO14/ADC2, which the bus owns), so every screen
 *         tiles the full 0..319 height into full-width bands >=44px with
 *         shared edges -- no dead pixels, and no silent taps: everything
 *         flashes, even a miss.
 *      3. Calibration persisted to NVS (namespace "freeisp", FRESH key
 *         names -- the old keys hold junk from previous wirings).
 *
 *  WIRING (as fitted 20 Aug 2026, after the two rewires):
 *      LCD_D0..D7 -> 16, 17, 18, 19, 2, 22, 23, 5
 *      LCD_WR  -> 14        LCD_RS  -> 33  (J4 "BLK")
 *      LCD_CS  -> 21 (U4 "SDA")   LCD_RD -> 12 (J14 "D12")
 *      LCD_RST -> 4         5V + GND from J4
 *
 *  WHAT TO LOOK FOR:
 *      - the number changes when you press  -> the panel is fine, and the
 *        fault in BigUI is WiFi stealing ADC2. Fix: park the radio.
 *      - the number never moves             -> the press is not reaching
 *        GPIO33, so the wiring goes back to the proven map.
 */

#include <Adafruit_GFX.h>
#include <Preferences.h>
#include <esp_task_wdt.h>
#include "soc/gpio_struct.h"

static const uint8_t PIN_D[8] = {16, 17, 18, 19, 2, 22, 23, 5};
#define PIN_WR  14
#define PIN_RS  33
#define PIN_CS  21
#define PIN_RD  12
#define PIN_RST 4

#define T_XP 23        // LCD_D6
#define T_XM PIN_RS    // LCD_RS  (GPIO33, ADC1)
#define T_YP PIN_WR    // LCD_WR  (GPIO14, ADC2)
#define T_YM 5         // LCD_D7

// 0 = normal product UI (the default).  1 = raw grid diagnostic only.
// The grid intentionally replaces the UI, so keep this switch explicit: a
// grid build cannot reach the Settings > Calibrate touch menu.
#define FACEUI_GRID_DIAGNOSTIC 1

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
    for (int i = 0; i < 8; i++) pinMode(PIN_D[i], OUTPUT);
    pinMode(PIN_WR, OUTPUT); digitalWrite(PIN_WR, HIGH);
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
};
Lcd tft;

static void done() { tft.busOut(); tft.sel(); }

int zRead() {                       // XP low, YM high, read XM
  tft.desel();
  pinMode(T_XP, OUTPUT); digitalWrite(T_XP, LOW);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, HIGH);
  pinMode(T_XM, INPUT);  pinMode(T_YP, INPUT);
  delayMicroseconds(200);
  int v = analogRead(T_XM);
  done();
  return v;
}
int yRead() {                       // drive the Y plate, read the X plate
  tft.desel();
  pinMode(T_XP, INPUT);  pinMode(T_XM, INPUT);
  pinMode(T_YP, OUTPUT); digitalWrite(T_YP, HIGH);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, LOW);
  delayMicroseconds(200);
  int v = analogRead(T_XM);
  done();
  return v;
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

// FaceUI must use the same ADC sequence that proved the panel: zRead(), then
// yRead(), both on GPIO33/ADC1.  Do not read T_YP/GPIO14 here: that ADC2
// conversion was observed to rail the following ADC1 samples.  Each signal
// learns its own idle level at boot; a touch is a sustained departure from
// either level.
int tZ1 = 0, tZ2 = 0;
int iZ1 = 0, iY = 0;
// Set from bench measurement, at Francis's call ("we can have it as low as
// 40, I'm good with that"). On the Home screen a real press only moves the
// signal 12..82 -- nothing like the 800..1600 the same finger produces on
// the calibration screen -- so a gate of 200 could never fire there. 40 is
// safe because idle on Home is not merely low, it is EXACTLY 0: 108
// consecutive idle samples read dev=0 with no noise whatsoever. Two
// consecutive rounds are still required, so a lone spike cannot trigger.
// 40 was still too high: the next captured presses peaked at 30..34 and
// never fired. Home-screen presses land anywhere in 12..82, so the gate has
// to sit under the weakest of them. 20 does, and it is still safe because
// the idle floor is not "low" but exactly 0 across 108 consecutive samples,
// with two consecutive rounds required before anything latches.
#define T_ON    5                     // Francis: "the pressure should even be
#define T_OFF    3                    // 5". Safe only because idle measures
                                      // EXACTLY 0 here, never 1 or 2, across
                                      // 108 consecutive samples -- and two
                                      // consecutive rounds are still needed
                                      // before anything latches.
bool tDown = false; int tStreak = 0, tLastZ = 0, tLastB = 0;
int peakDev = 0, peakXM = 0, peakY = 0;   // evidence of a press
int lastTapRounds = 0;
int  touchDev() {                     // biggest deviation from rest
  // ONE round, exactly TouchProof's loop body: a z config, then a y config,
  // and the caller leaves ~120ms and a real draw before asking again.
  tZ1 = zRead();
  tZ2 = yRead();
  // A read of 4095 is the charged-node artifact this panel is famous for,
  // never a real position (genuine presses live in the hundreds). Counting
  // it as a deviation is what produced phantom presses -- "release timed
  // out" over and over with A=0 B=0 and no finger anywhere near the glass.
  int d1 = (tZ1 > 4000) ? 0 : abs(tZ1 - iZ1);
  int d2 = (tZ2 > 4000) ? 0 : abs(tZ2 - iY);
  int d  = max(d1, d2);
  if (d > peakDev) { peakDev = d; peakXM = tZ1; peakY = tZ2; }
  return d;
}
bool touchDown() {                    // one detection round + state update
  tLastZ = touchDev();
  tLastB = tDown;
  bool now = tLastZ > (tDown ? T_OFF : T_ON);
  if (now == tDown) { tStreak = 0; return tDown; }
  if (++tStreak >= 2) { tDown = now; tStreak = 0; }   // 2 rounds to flip
  return tDown;
}

// Three anchors, Francis's way: crosshair targets pressed top / middle /
// bottom, like a proper touchscreen setup. The middle anchor makes the map
// PIECEWISE -- two segments instead of one straight line -- because the
// 2-bar version calibrated "fine" and SETTINGS still wasn't hittable: one
// line through two soft presses squeezed the whole bottom of the glass.
long rawA = 1000, rawB = 500, rawC = 0;   // raw at screen y=40 / 160 / 280
bool calibrated = false;
bool calibrationRequired = false;
int  lastTapRaw = -1, lastTapY = -1;  // shown on the INFO screen

Preferences prefs;
#define CAL_VER 5                   // v5 anchors come from posRead() -- the
                                    // spaced z-then-y sequence; every older
                                    // anchor was measured back-to-back and
                                    // is on a different scale entirely

int screenY(int raw) {
  // Two segments hinged at the middle anchor, signed math throughout: this
  // panel's raws RUN BACKWARDS (bigger raw = higher on the glass) and both
  // directions must keep working after any recalibration.
  long y;
  if ((long)(raw - rawB) * (rawA - rawB) >= 0)        // rawB..rawA: top half
    y = 160 + (long)(raw - rawB) * (40 - 160) / (rawA - rawB);
  else                                                // rawB..rawC: bottom
    y = 160 + (long)(raw - rawB) * (280 - 160) / (rawC - rawB);
  return constrain((int)y, 0, 319);
}

// Position of the current press: median of TouchProof-style rounds spanning
// the whole contact.  The previous code nested five extra ADC rounds inside
// every sample, so one tap could make 35 rapid conversions and recreate the
// 4095 charged-node failure.  tZ2 is yRead() from touchDown()'s current,
// already-settled round, so no extra pin juggling is needed.
// Returns -1 for a graze too short for 3 rounds or a railed result.
// PROVEN BY SettleTest.ino, and it is the whole bug. A yRead taken
// immediately after a zRead comes back collapsed -- badly so for a light
// press, which is why holding firmly used to mask it and why every quick
// tap reported a position near the bottom of the scale no matter where the
// finger was. Give the two configs 110ms apart and a LIGHT press reads
// true: measured 1070 top / 533 middle / 176 bottom, a clean gradient.
//
// (Settle delay inside yRead is NOT the mechanism: 200us to 20ms moved the
// same reading by 2%. It is the spacing between the two configs.)
int posRead() {
  zRead();
  delay(110);
  return yRead();
}
int readTapRaw() {
  int cap[7], m = 0;
  while (touchDown() && m < 7) { cap[m++] = posRead(); delay(110); }
  lastTapRounds = m;
  // Back down to 2 rounds: hold-to-select was a workaround for the
  // back-to-back read bug, and posRead() removes the need for it.
  if (m < 2) return -1;
  // PEAK, not median. Contact error on this panel is one-directional: a
  // firm press reads high, a poor one collapses toward 0 -- which is also
  // where the BOTTOM of the glass lives. So the best-contact sample is the
  // highest one, and a median just blends in the bad ones.
  // DISCARD NO-CONTACT SAMPLES. Measured: pressing the same row twice gives
  // raw=538 then raw=0. Zero is not a position, it is the finger having
  // already lifted -- each sample costs 220ms, so a quick tap is over
  // before its own reading is taken. Believing those zeros is what made
  // every other press jump to Info, since 0 maps to the bottom of the
  // scale. 30 is far below the real bottom anchor (~253), so a genuine
  // bottom-of-glass press is never rejected by this.
  int raw = -1;
  int good = 0;
  for (int a = 0; a < m; a++) {
    if (cap[a] < 30) continue;        // no contact, not a low position
    good++;
    if (cap[a] > raw) raw = cap[a];   // peak of the samples that had contact
  }
  if (good == 0) {
    Serial.printf("TAP dropped: %d samples, all no-contact\n", m);
    return -1;                        // do nothing beats acting on garbage
  }

  // The old "reject anything below the calibrated span" floor is GONE. It
  // was a plaster over the back-to-back read bug, and it was correctly
  // criticised in review: a genuine press below the bottom anchor
  // legitimately extrapolates under it, so the floor made the real bottom
  // strip of the glass untouchable. With posRead() the readings are honest,
  // so nothing needs to be thrown away.
  return (raw > 4000) ? -1 : raw;
}

void textAt(int x,int y,uint8_t sz,uint16_t c,const String&s){
  tft.setTextSize(sz); tft.setTextColor(c); tft.setCursor(x,y); tft.print(s);
}

// Calibration deliberately waits for a human.  It is invoked from loop(),
// but it can legitimately wait longer than the loop task's watchdog period.
static inline void calibrationDelay(uint32_t ms) {
  esp_task_wdt_reset();
  delay(ms);
}

// Wait for a complete tap and return where it landed vertically.
bool waitTap(int *sy) {
  // A press that outlives the 2.5s escape below still fires once -- but the
  // NEXT tap needs an observed release first. Without this latch a long hold
  // re-fired its band every ~2.6s (Alarm toggling itself under one finger).
  static bool stuckDown = false;
  if (stuckDown) {
    if (touchDown()) return false;
    stuckDown = false;
    delay(60);
    return false;
  }
  if (!touchDown()) return false;
  int raw = readTapRaw();               // seat, then median across the press
  if (raw < 0) {                        // graze, dab, or railed read
    Serial.printf("TAP discarded: rounds=%d XM=%d y=%d dev=%d\n",
                  lastTapRounds, tZ1, tZ2, tLastZ);
    while (touchDown()) delay(10);
    delay(60);
    return false;
  }
  uint32_t t0 = millis();
  while (touchDown() && millis() - t0 < 2500) delay(10);
  stuckDown = (millis() - t0 >= 2500);   // escaped with the finger still on
  delay(60);
  *sy = screenY(raw);
  lastTapRaw = raw; lastTapY = *sy;
  Serial.printf("TAP raw=%d -> y=%d\n", raw, *sy);
  return true;
}

// -------------------------------------------------------- NVS persistence --
// All-new key names on purpose: the old keys hold calibration from previous
// wirings and must never be read again.  Touch resting levels are deliberately
// not stored because they are measured fresh at every boot.
bool calValid(long a, long b, long c) {
  long s1 = b - a, s2 = c - b;                  // top / bottom segment spans
  if (a < 0 || a > 4095 || b < 0 || b > 4095 || c < 0 || c > 4095) return false;
  if (labs(s1) < 80 || labs(s2) < 80) return false;     // squeezed segment
  if ((s1 > 0) != (s2 > 0)) return false;               // direction flip
  return true;
  // THE 3x SKEW RULE IS GONE, and it was rejecting good calibrations. On
  // the bench: 1241 / 1088 / 458 -- three presses, correctly ordered, real
  // varying numbers -- thrown out only because the lower half of the glass
  // spanned 630 counts against the upper half's 153. That is not a fault,
  // it is exactly the uneven panel the PIECEWISE map with its middle hinge
  // exists to absorb; demanding even halves defeats the hinge's whole
  // purpose. Railed reads are already caught upstream (>4000 -> discard),
  // so ordering plus a minimum span is all the sanity this needs.
}
bool loadCal() {                    // boot path: true = stored cal is usable
  prefs.begin("freeisp", true);
  bool verOk = prefs.getUChar("vcal_ver", 0) == CAL_VER;
  long a = prefs.getLong("vcal_a", -1), b = prefs.getLong("vcal_b", -1),
       c = prefs.getLong("vcal_c", -1);
  prefs.end();
  if (!verOk || !calValid(a, b, c)) return false;
  rawA = a; rawB = b; rawC = c; calibrated = true;
  Serial.printf("CAL loaded a=%ld b=%ld c=%ld\n", a, b, c);
  return true;
}
void saveCal() {                    // only ever called from calibrate()
  prefs.begin("freeisp", false);
  prefs.putUChar("vcal_ver", CAL_VER);
  prefs.putLong("vcal_a", rawA);
  prefs.putLong("vcal_b", rawB);
  prefs.putLong("vcal_c", rawC);
  prefs.end();
  Serial.printf("CAL SAVED a=%ld b=%ld c=%ld  (factory-default candidates)\n", rawA, rawB, rawC);
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
// Francis's spec: real targets you press -- top, middle, bottom, staggered
// across the glass like a proper corner calibration -- not bars. Touch is
// vertical-only, so only the target's HEIGHT feeds the math; the stagger is
// honest looks. Each point is press-and-HOLD: median reads are collected
// across the whole hold and the median of those is the anchor, so one soft
// contact cannot skew the map the way it did the 2-bar version. Then nothing
// is saved until a REAL tap proves the map: the last step is hitting
// SETTINGS itself. Calibrated-but-not-tappable can no longer be stored.
static void calTarget(int cx, int cy) {
  tft.drawCircle(cx, cy, 14, C_ACC);
  tft.drawCircle(cx, cy, 6,  C_ACC);
  tft.drawFastHLine(cx - 20, cy, 40, C_ACC);
  tft.drawFastVLine(cx, cy - 20, 40, C_ACC);
}
void calibrate() {
  const int CY[3] = {40, 160, 280};   // anchor rows on the glass
  const int CX[3] = {60, 240, 420};   // stagger: top-left, centre, bottom-right
  const int TY[3] = {196, 220, 84};   // instruction block, clear of the target
  long got[3];
retry:
  for (int i = 0; i < 3; i++) {
    tft.fillScreen(C_BG);
    calTarget(CX[i], CY[i]);
    textAt(90, TY[i], 2, C_TXT, "PRESS AND HOLD THE TARGET " + String(i + 1) + "/3");
    textAt(90, TY[i] + 28, 2, C_LABEL, "z=");
    textAt(300, TY[i] + 28, 2, C_LABEL, "gate=" + String(T_ON));
    while (!touchDown()) {            // wait-for-press with a live readout;
      // The repaint is part of the proven read cadence, not decoration.
      tft.fillRect(114, TY[i] + 26, 90, 18, C_BG);
      textAt(116, TY[i] + 28, 2, C_OK, (tLastB ? "DOWN " : "up ") + String(tLastZ));
      calibrationDelay(110);
    }
    // Sample for as long as the hold lasts, up to 7 median rounds from the
    // FIRST instant of contact -- no seat delay. The 50ms-delay experiment
    // proved the firm phase reads pressure, not position: all three targets
    // converged to the same number. First-contact-onward rounds with a
    // median across them is what produced the spread that mapped true.
    int cap[7], m = 0;
    while (touchDown() && m < 7) { cap[m++] = posRead(); calibrationDelay(110); }
    while (touchDown()) calibrationDelay(110);
    // posRead() and the peak statistic, matching readTapRaw EXACTLY. The
    // anchors must be measured the same way live taps are, or the map is
    // calibrated against numbers normal use never produces -- which is how
    // anchors of 1639/919/256 ended up judging taps arriving as 14..397.
    int best = -1;
    for (int a = 0; a < m; a++) if (cap[a] > best) best = cap[a];
    if (m < 3 || best > 4000) {
      Serial.printf("cal %d retry: rounds=%d\n", i, m);
      textAt(90, TY[i] + 56, 2, C_WARN, m < 3 ? "HOLD IT LONGER" : "BAD READ - AGAIN");
      calibrationDelay(900);
      i--;
      continue;
    }
    got[i] = best;                    // peak, same statistic as live taps
    Serial.printf("cal %d raw=%ld (%d rounds)\n", i, got[i], m);
    calibrationDelay(250);
  }
  // Accept with the SAME validator the boot path uses, or a map that loads
  // tomorrow differs from the map that saved today.
  if (!calValid(got[0], got[1], got[2])) {
    Serial.printf("CAL rejected: %ld %ld %ld\n", got[0], got[1], got[2]);
    tft.fillScreen(C_BG);
    textAt(66, 150, 2, C_WARN, "POINTS DON'T LINE UP - AGAIN");
    calibrationDelay(900);
    goto retry;
  }
  rawA = got[0]; rawB = got[1]; rawC = got[2];
  calibrated = true;
  Serial.printf("CAL candidate a=%ld b=%ld c=%ld\n", rawA, rawB, rawC);

  // PROVE it before saving it.
  tft.fillScreen(C_BG);
  textAt(144, 140, 2, C_TXT, "NOW TAP SETTINGS");
  textAt(180, 176, 2, C_LABEL, "z=");
  drawSettingsBand(false);
  for (int tries = 0; tries < 200; tries++) {   // ~22s of patience, then redo
    if (!touchDown()) {
      tft.fillRect(204, 174, 90, 18, C_BG);
      textAt(206, 176, 2, C_OK, (tLastB ? "DOWN " : "up ") + String(tLastZ));
      calibrationDelay(110);
      continue;
    }
    int raw = readTapRaw();             // MUST read like real use does, or
    while (touchDown()) calibrationDelay(110);  // verify proves the wrong thing
    if (raw < 0) continue;
    int sy = screenY(raw);
    Serial.printf("cal verify raw=%d -> y=%d\n", raw, sy);
    if (sy >= 240) {                            // the same gate loop() uses
      drawSettingsBand(true);
      saveCal();
      return;
    }
    textAt(96, 170, 2, C_WARN, "missed - try once more");
  }
  Serial.println("CAL verify failed - starting over");
  goto retry;
}

// ---- DIAGNOSTIC: which SCREEN axis does the readable raw actually track?
// Approach change (Francis: "try another approach"). Every calibration so
// far staggered its targets across BOTH width and height, so a clean
// gradient never proved the axis -- and every SETTINGS verify tap at the
// bottom-CENTRE mapped to mid-scale and missed. If the GPIO33 read runs
// along the native LONG side of this portrait-born panel, then in our
// landscape rotation it is HORIZONTAL, and the whole vertical-only belief
// inherited from the BigUI era is backwards. Four corners answer it:
// same-height pairs vs same-side pairs.
long probeOne(int cx, int cy, const char *label) {
  for (;;) {
    tft.fillScreen(C_BG);
    calTarget(cx, cy);
    int ty = cy < 160 ? 200 : 60;
    textAt(130, ty, 2, C_TXT, "HOLD: " + String(label));
    textAt(130, ty + 28, 2, C_LABEL, "z=");
    while (!touchDown()) {            // live readout: the repaint IS the bus
      tft.fillRect(154, ty + 26, 90, 18, C_BG);
      textAt(156, ty + 28, 2, C_OK, (tLastB ? "DOWN " : "up ") + String(tLastZ));
      calibrationDelay(110);
    }
    int cap[7], m = 0;
    while (touchDown() && m < 7) { cap[m++] = tZ2; calibrationDelay(110); }
    while (touchDown()) calibrationDelay(110);
    for (int a = 1; a < m; a++)
      for (int j = a; j > 0 && cap[j] < cap[j-1]; j--) { int t=cap[j]; cap[j]=cap[j-1]; cap[j-1]=t; }
    if (m >= 3 && cap[m / 2] <= 4000) {
      Serial.printf("probe %-12s raw=%d (%d rounds)\n", label, cap[m / 2], m);
      calibrationDelay(250);
      return cap[m / 2];
    }
    Serial.printf("probe %s retry (rounds=%d)\n", label, m);
    calibrationDelay(500);
  }
}
// ---- GRID MAP: Francis's calibration, and a better one than targets.
// Tile the glass in small boxes. Press any box and that spot's raw numbers
// are printed IN it. No point to hit, so nothing to miss -- the map builds
// itself from wherever a finger actually lands, and the running min/max of
// both axes IS the calibration: sweep the glass and the ends of the scale
// are learned. It is also the honest test of the mapping, because the box
// that lights up should be the box under the finger.
#define GC 12                         // columns, 40px ~ 6mm
#define GR 8                          // rows,    40px ~ 6mm
#define GW (480 / GC)
#define GH (320 / GR)

// NOTHING IS LEARNED HERE. The grid uses the SAVED calibration exactly as
// the product UI does, so it is a pure pass/fail test: press row 2, row 2
// must fill. An auto-calibrating grid would fit itself to whatever it was
// given and could never fail, which makes it useless as evidence.
void gridChrome() {
  tft.fillScreen(C_BG);
  for (int r = 0; r < GR; r++)
    for (int c = 0; c < GC; c++) {
      int n = r * GC + c + 1;         // 1..96, numbered as Francis asked
      tft.drawRect(c * GW, r * GH, GW, GH, C_EDGE);
      textAt(c * GW + 4, r * GH + 4, 1, C_LABEL, String(n));
    }
  for (int r = 0; r < GR; r++)        // row number, big, down the middle
    textAt(228, r * GH + 14, 2, C_EDGE, String(r + 1));
}
// ONE PASS, called from loop(). It used to be an endless for(;;) run from
// setup(), and that is why the box kept silently rebooting mid-session:
// setup() never returning starves the Arduino loop task's watchdog feed,
// so the panic handler restarted the board before a finger ever arrived.
// Diagnostics that reboot are worse than no diagnostics.
int gTaps = 0, gBeat = 0;
void gridStep() {
  {
    if (!touchDown()) {
      // Trace what the detector SEES, always -- the only way to tell a
      // finger that is not registering from a finger that never came.
      if (++gBeat % 8 == 0) {
        // PEAK is the important number: the largest movement seen since the
        // last line. A swipe that never reaches the threshold still leaves
        // its mark here, which tells us whether the glass moved at all.
        Serial.printf("watch now XM=%4d y=%4d dev=%3d | PEAK dev=%4d (XM=%4d y=%4d)\n",
                      tZ1, tZ2, tLastZ, peakDev, peakXM, peakY);
        tft.fillRect(250, 2, 226, 12, C_BG);
        textAt(252, 4, 1, peakDev > T_ON ? C_OK : C_LABEL,
               "peak " + String(peakDev) + "  now " + String(tLastZ));
        peakDev = 0;                  // fresh window each line
      }
      // TouchProof's cadence AND its workload. Both signals read a correct
      // 0 at boot and only rail to 4095 once the loop is running, so the
      // difference is how much bus traffic each round carries: TouchProof
      // repainted big live numbers every iteration, while my tick pushed
      // nine pixels. The file's own header says it -- the draw is not
      // cosmetic, it is what lets the sense node settle. So repaint the
      // readout EVERY round, in big text, exactly as the proven sketch did.
      tft.setTextSize(3); tft.setTextColor(C_TXT, C_BG);
      tft.setCursor(20, 120); tft.printf("XM %4d ", tZ1);
      tft.setCursor(20, 160); tft.printf("y  %4d ", tZ2);
      delay(110);
      return;
    }
    // Exactly the product UI's tap path -- same readTapRaw, same screenY,
    // same saved anchors. If the grid passes and the menu does not, the
    // fault is in the menu; if the grid fails, the map is wrong. That only
    // means something because nothing here adapts.
    int raw = readTapRaw();
    uint32_t rel = millis();          // bounded release wait, always
    while (touchDown() && millis() - rel < 2500) delay(110);
    if (raw < 0) {
      Serial.println("GRID: tap discarded (no contact samples)");
      return;
    }
    int sy  = screenY(raw);
    int row = constrain(sy / GH, 0, GR - 1);

    gridChrome();
    for (int c = 0; c < GC; c++) {    // fill every box in the mapped row
      tft.fillRect(c * GW + 1, row * GH + 1, GW - 2, GH - 2, C_ACC);
      textAt(c * GW + 4, row * GH + 4, 1, C_BG, String(row * GC + c + 1));
    }
    textAt(228, row * GH + 14, 2, C_BG, String(row + 1));
    textAt(6, 306, 1, C_TXT, "raw " + String(raw) + " -> y " + String(sy) +
                             " -> ROW " + String(row + 1) +
                             "   cal " + String(rawA) + "/" + String(rawB) +
                             "/" + String(rawC));

    gTaps++;
    Serial.printf("GRID %d: raw=%d -> y=%d -> ROW %d (boxes %d..%d)\n",
                  gTaps, raw, sy, row + 1, row * GC + 1, row * GC + GC);
  }
}

// ------------------------------------------------------------------ screens --
enum { SCR_HOME, SCR_MENU, SCR_INFO } screen = SCR_HOME;

// The premium cue: a 1px lighter line just inside the top edge of every
// card so the flat fill reads as a bevelled face (HelloScreen's trick).
void bevel(int x, int y, int w) { tft.drawFastHLine(x + 1, y + 1, w - 2, C_BEVEL); }

const int ROW_TOP = 52, ROW_H = 52;
void row(int i, const String& name, const String& val, uint16_t vc) {
  int y = ROW_TOP + i * ROW_H;
  tft.fillRect(8, y, 464, ROW_H - 6, C_CARD);
  tft.drawRect(8, y, 464, ROW_H - 6, C_EDGE);
  bevel(8, y, 464);
  textAt(22, y + 14, 2, C_TXT, name);
  textAt(444 - val.length() * 12, y + 14, 2, vc, val);
}

// PRESSED FLASH -- universal. Repaint the element in C_ACC with its text in
// C_BG, hold 140ms, then the caller acts / redraws. No silent taps anywhere.
void flashRow(int i, const String& name) {
  int y = ROW_TOP + i * ROW_H;
  tft.fillRect(8, y, 464, ROW_H - 6, C_ACC);
  textAt(22, y + 14, 2, C_BG, name);
  delay(140);
}
void flashHeader(const String& s) {
  tft.fillRect(0, 0, 480, 44, C_ACC);
  textAt(16, 15, 2, C_BG, s);
  delay(140);
}
void drawSettingsBand(bool pressed) {
  tft.fillRect(0, 268, 480, 52, pressed ? C_ACC : C_CARD);
  if (!pressed) tft.drawFastHLine(0, 268, 480, C_ACC);
  textAt(192, 284, 2, pressed ? C_BG : C_ACC, "SETTINGS");
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
  tft.fillRect(0, 0, 480, 44, C_BAR);
  textAt(16, 15, 2, C_TXT, "FreeISP");
  // Status pill, right edge pinned at x=468: w = len*12 + 16.
  // ("ONLINE" later: C_OK, w=88, x=380.)
  tft.fillRoundRect(368, 10, 100, 24, 12, C_WARN);
  textAt(376, 15, 2, C_BG, "OFFLINE");
  tft.drawFastHLine(0, 44, 480, C_EDGE);

  tft.fillRect(12, 56, 220, 88, C_CARD); tft.drawRect(12, 56, 220, 88, C_EDGE);
  bevel(12, 56, 220);
  textAt(26, 64, 1, C_LABEL, "USERS ONLINE");
  textAt(26, 84, 5, C_ACC, "42");
  tft.fillRect(248, 56, 220, 88, C_CARD); tft.drawRect(248, 56, 220, 88, C_EDGE);
  bevel(248, 56, 220);
  textAt(262, 64, 1, C_LABEL, "PPPoE");
  textAt(262, 84, 5, C_OK, "17");

  textAt(12, 158, 1, C_LABEL, "PORTS");
  const uint8_t st[5] = {1,1,1,0,1};
  for (int i = 0; i < 5; i++) {            // pitch 100: jack 5 ends at x=468,
    drawJack(12 + i*100, 174, st[i]);      // flush with the cards above
    textAt(12 + i*100 + 25, 224, 1, st[i] ? C_TXT : C_LABEL, String(i + 1));
  }

  drawSettingsBand(false);
}

void drawMenu() {
  tft.fillScreen(C_BG);
  tft.fillRect(0, 0, 480, 44, C_BAR);
  textAt(16, 15, 2, C_ACC, "< BACK");
  textAt(192, 15, 2, C_TXT, "Settings");   // centred: 240 - 8*12/2
  tft.drawFastHLine(0, 44, 480, C_EDGE);
  row(0, "WiFi",            "not set",      C_WARN);
  row(1, "Screen",          BRI[brightIdx], C_LABEL);
  row(2, "Alarm",           alarmArmed ? "armed" : "off",
                            alarmArmed ? C_OK : C_LABEL);
  row(3, "Calibrate touch", "",             C_LABEL);
  row(4, "Info",            "",             C_LABEL);
}

void drawInfo() {
  tft.fillScreen(C_BG);
  tft.fillRect(0, 0, 480, 44, C_BAR);
  textAt(16, 15, 2, C_ACC, "< BACK");
  textAt(216, 15, 2, C_TXT, "Info");       // centred: 240 - 4*12/2
  tft.drawFastHLine(0, 44, 480, C_EDGE);

  tft.fillRect(8, 52, 464, 260, C_CARD);
  tft.drawRect(8, 52, 464, 260, C_EDGE);
  bevel(8, 52, 464);

  textAt(24, 66, 2, C_TXT, "FaceUI");
  textAt(24, 92, 1, C_LABEL, "build " __DATE__ " " __TIME__);

  textAt(24, 116, 1, C_LABEL, "D0-D7: 16 17 18 19 2 22 23 5");
  textAt(24, 132, 1, C_LABEL, "WR 14  RS 33  CS 21  RD 12  RST 4");
  textAt(24, 148, 1, C_LABEL, "touch: GPIO33/ADC1, vertical only");

  textAt(24, 176, 1, C_LABEL, "touch gate"); textAt(140, 176, 1, C_ACC, String(T_ON));
  textAt(24, 192, 1, C_LABEL, "cal A/B/C");
  textAt(140, 192, 1, C_ACC, String(rawA) + " / " + String(rawB) + " / " + String(rawC));
  textAt(24, 224, 1, C_LABEL, "last tap");
  textAt(140, 224, 1, C_ACC, String(lastTapRaw) + " -> " + String(lastTapY));

  textAt(24, 288, 1, C_LABEL, "tap anywhere to go back");
}

// ------------------------------------------------------------------ sketch --
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> FaceUI: built on the proven TouchProof core");
  tft.begin();

  // Paint first, read second -- the order TouchProof.ino happens to use and
  // the only remaining difference from it. Empirically the panel reads
  // honestly after the bus has done real work, and rails if asked cold.
  tft.fillScreen(C_BG);
  textAt(90, 150, 2, C_TXT, "starting up...");

  // WARM-UP FIRST. The opening ADC conversions after boot come back
  // full-scale on this board -- TouchProof only ever looked healthy because
  // it drew a whole screen before its first read. Throw the early ones away
  // or the resting level is learned as 4095 and no press can ever differ
  // from it, which is exactly the "nothing is tappable" symptom.
  // Replicate TouchProof's loop body exactly -- z read, THEN a y read, then
  // a real draw, then a long pause. Reading z alone in a tight loop leaves
  // the sense node charged from the previous done(), which drives it high;
  // the y read reconfigures all four lines and lets it settle.
  for (int i = 0; i < 16; i++) {
    zRead(); yRead();
    textAt(90 + i * 12, 180, 2, C_LABEL, ".");   // a visible progress row
    delay(120);
  }

  // Learn the two TouchProof signals' own resting levels, hands off glass.
  int q1[15], q2[15];
  for (int i = 0; i < 15; i++) {
    q1[i] = zRead(); q2[i] = yRead(); delay(20);
  }
  for (int i = 1; i < 15; i++)
    for (int j = i; j > 0 && q1[j] < q1[j-1]; j--) { int t=q1[j]; q1[j]=q1[j-1]; q1[j-1]=t; }
  for (int i = 1; i < 15; i++)
    for (int j = i; j > 0 && q2[j] < q2[j-1]; j--) { int t=q2[j]; q2[j]=q2[j-1]; q2[j-1]=t; }
  iZ1 = q1[7]; iY = q2[7];
  Serial.printf("rest levels: XM=%d yRead=%d  (press = either moving %d+)\n",
                iZ1, iY, T_ON);

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
  // MEASURED, and it settles the "calibration works but SETTINGS does not"
  // bug. On Home a real press moved the signal to only 3..64 while the gate
  // is 200 -- the same finger reads 800..1600 on the calibration screen.
  // The panel is not the difference, the TIMING is: calibration draws, waits
  // 12ms, then reads. This loop drew a 1600-pixel block and read IMMEDIATELY
  // after, so every sample was taken while the bus was still settling from
  // the write, which crushes the reading to noise level.
  //
  // (The earlier theory in this spot -- "not enough drawing" -- is dead:
  // 108 idle lines on Home read a flat XM=0 y=0, never railed. Volume was
  // never the problem. Settling time after the draw is.)
  tft.fillRect(300, 18, 80, 20, C_BAR);
  delay(12);                          // let the bus settle before sampling
  if (!waitTap(&sy)) {
    // One line per second is enough to distinguish a healthy 0-idle panel
    // from the 4095 charged-node failure without changing the read cadence.
    if (millis() - lastPulse >= 1000) {
      lastPulse = millis();
      Serial.printf("UI idle: XM=%d y=%d dev=%d down=%d streak=%d\n",
                    tZ1, tZ2, tLastZ, tDown, tStreak);
    }
    delay(100);
    return;
  }

  if (screen == SCR_HOME) {
    // HOME tiles into two bands. 268-319 is the SETTINGS band (matches the
    // drawn rect exactly). Everything above it -- 0-267 -- is content with
    // no action, so a tap there flashes the SETTINGS band as a HINT: it
    // teaches where to tap and kills the orphan dead zone.
    // Gate at 240, not the band's drawn 268: with ~1.5 raw counts per pixel
    // on this panel, ADC noise is worth ±10px, and a SETTINGS tap that
    // misses by a hair should open the menu, not wink at the user.
    if (sy >= 240) {
      drawSettingsBand(true);           // flash...
      screen = SCR_MENU;
      drawMenu();                       // ...then act
    } else {
      drawSettingsBand(true);           // hint flash...
      drawSettingsBand(false);          // ...and restore
    }
  } else if (screen == SCR_MENU) {
    // Band map, edges shared exactly: 0-51 BACK, then 52px per row, row 4
    // running through the bottom margin to 319. This FIXES two live bugs:
    // sy 44-51 used to truncate (-8)/52 == 0 into row 0, and sy 312-319
    // was dead. BACK owning the 44-51 gutter also gives the extrapolated
    // territory above the top cal anchor to the bigger, safer target.
    int r = (sy <= 51) ? -1 : min((sy - ROW_TOP) / ROW_H, 4);
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
      flashRow(1, "Screen");
      row(1, "Screen", BRI[brightIdx], C_LABEL);
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
      flashRow(4, "Info");
      screen = SCR_INFO;
      drawInfo();
    }
  } else {                              // SCR_INFO: the whole screen is one
    flashHeader("< BACK");              // 320px band -- tap anywhere to go
    screen = SCR_MENU;                  // back; no gap possible
    drawMenu();
  }
}
