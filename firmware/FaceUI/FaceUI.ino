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
// SIXTEEN measured anchors, one per 20px band, replacing every fitted map
// this file has ever had. Francis's design, proven end to end in BoxCal.ino
// (15 of 16 test taps landed right; the one miss was a 20-count sliver at
// the panel's compressed top, i.e. the glass's own limit). A tap is matched
// to the NEAREST anchor -- no line fit, no extrapolation, no hinge. The
// arithmetic that kept sending presses to the wrong row is simply gone.
// 16 is also the panel's measured ceiling: span ~820 counts, tap error up
// to ~39, so 32 bands would be error-sized. The UI only needs 6.
// THE 32-BOX GRID -- Francis's foundation for the whole UI: "a grid that we
// will use to even add other pressing options, so we know this and this are
// pressable." 8 rows x 4 columns of 120x40 boxes, numbered 1..32. The 8
// rows are the pressable zones TODAY (the 8-row walk went 8 for 8 on the
// bench); the 4 columns are drawn and numbered so layouts can be planned on
// them now, and they become individually pressable when the motherboard PCB
// frees the second ADC pin -- GridCal measured today's X axis as scatter
// (spread 5091 across rows vs 4596 down columns, statistically nothing).
// Until then a press resolves to its row, and each row splits into its four
// boxes later with no redesign.
#define GRID_COLS 8                 // 8x8 = 64 boxes, Francis: "full work
#define NANCH 8                     // around". One anchor per ROW -- 8/8
#define BAND  (320 / NANCH)         // reliable; 40px per row, 60px per box
int  anchorRaw[NANCH];
bool calibrated = false;
bool calibrationRequired = false;
int  lastTapRaw = -1, lastTapY = -1;  // shown on the INFO screen

Preferences prefs;
#define CAL_VER 8                   // v8 = the 8-row grid walk

int screenY(int raw) {
  int best = 0, bd = 32767;
  for (int i = 0; i < NANCH; i++) {
    int d = abs(raw - anchorRaw[i]);
    if (d < bd) { bd = d; best = i; }
  }
  return best * BAND + BAND / 2;    // centre of the nearest measured band
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
  // MEDIAN of the samples that had contact -- BoxCal's exact statistic, the
  // one that put 15 of 16 test taps in the right box. Samples under 30 are
  // dropped as NO CONTACT, not believed as low positions: measured, the
  // same row pressed twice gave 538 then 0, because a sample costs ~220ms
  // and a quick tap ends before its own read -- and 0 maps to the bottom
  // of the glass, which is how every other press used to select Info.
  int s[7], n = 0;
  for (int a = 0; a < m; a++)
    if (cap[a] >= 30 && cap[a] <= 4000) s[n++] = cap[a];
  if (n == 0) {
    Serial.printf("TAP dropped: %d samples, all no-contact\n", m);
    return -1;                        // do nothing beats acting on garbage
  }
  for (int i = 1; i < n; i++)
    for (int j = i; j > 0 && s[j] < s[j-1]; j--) { int t=s[j]; s[j]=s[j-1]; s[j-1]=t; }
  return s[n / 2];
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
// Light-touch sanity: every anchor in a sane range, and the table clearly
// descending end to end (this panel runs backwards: big raw = high on the
// glass). Per-gap rules are deliberately absent -- the compressed top can
// legitimately produce near-equal neighbours, and nearest-anchor matching
// tolerates that; a validator that demands even spacing rejects the truth.
bool calValid(const int *t) {
  for (int i = 0; i < NANCH; i++)
    if (t[i] < 30 || t[i] > 4000) return false;
  // EITHER direction. The bench walk of 1 Sep read a clean ASCENDING table
  // (2627..3600) after every earlier session read descending (959..121) --
  // the panel's scale can flip between builds, and nearest-anchor matching
  // never cared which way it runs. Demanding "descending" threw away the
  // cleanest table this glass has ever produced. A real span is the only
  // requirement.
  return abs(t[0] - t[NANCH - 1]) > 300;
}
bool loadCal() {                    // boot path: true = stored cal is usable
  int t[NANCH];
  prefs.begin("freeisp", true);
  bool verOk = prefs.getUChar("vcal_ver", 0) == CAL_VER;
  size_t got = prefs.getBytes("anch16", t, sizeof(t));
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
  prefs.putBytes("anch16", anchorRaw, sizeof(anchorRaw));
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
// Francis's box walk, verbatim from BoxCal.ino where it went 15/16 on the
// bench: sixteen full-width bands A..P, press the middle of the highlighted
// one, the measured number becomes that band's anchor. Then prove the map
// with one real tap on SETTINGS before anything is saved.
// The full 32-box grid. During calibration ONE box is blue -- press its
// middle. Any column works electrically (rows are what is measured), and
// the hot box hops columns as the walk descends so it LOOKS and behaves
// like the grid Francis asked for, not like bars.
static void drawCalGrid(int hotRow) {
  int bw = 480 / GRID_COLS;
  tft.fillScreen(C_BG);
  for (int r = 0; r < NANCH; r++)
    for (int c = 0; c < GRID_COLS; c++) {
      int x = c * bw, y = r * BAND, n = r * GRID_COLS + c + 1;
      // Straight DOWN the left column: 1, 9, 17, 25... The old diagonal hop
      // ("press 1 and it goes to 10") read as the grid losing its mind, and
      // the measured number landing in a different box than the one pressed
      // finished the impression. Predictable beats clever.
      bool hot = (r == hotRow) && (c == 0);
      if (hot) tft.fillRect(x + 1, y + 1, bw - 2, BAND - 2, C_ACC);
      tft.drawRect(x, y, bw, BAND, C_EDGE);
      tft.setTextSize(1);
      tft.setTextColor(hot ? C_BG : C_TXT, hot ? C_ACC : C_BG);
      tft.setCursor(x + 5, y + 4); tft.print(n);
      if (anchorRaw[r] > 0 && c == 0) {
        tft.setTextColor(C_OK, C_BG);
        tft.setCursor(x + 5, y + 24); tft.print(anchorRaw[r]);
      }
    }
  if (hotRow >= 0) {
    tft.setTextSize(1); tft.setTextColor(C_BG, C_ACC);
    tft.setCursor(5, hotRow * BAND + 24);   // in the SAME box as the blue --
    tft.print("PRESS ME");                  // it lagged one column behind
  }
}
void calibrate() {
retry:
  for (int i = 0; i < NANCH; i++) anchorRaw[i] = 0;
  for (int i = 0; i < NANCH; ) {
    drawCalGrid(i);
    while (!touchDown()) calibrationDelay(80);
    int v = readTapRaw();             // the SAME statistic live taps use
    uint32_t t0 = millis();
    while (touchDown() && millis() - t0 < 2500) calibrationDelay(80);
    if (v < 0) {
      Serial.printf("cal row %d: no contact, again\n", i + 1);
      continue;                       // same row, another press
    }
    anchorRaw[i] = v;
    Serial.printf("cal row %d raw=%d\n", i + 1, v);
    i++;
  }
  if (!calValid(anchorRaw)) {
    Serial.println("CAL rejected: table not descending / out of range");
    tft.fillScreen(C_BG);
    textAt(66, 150, 2, C_WARN, "TABLE LOOKS WRONG - AGAIN");
    calibrationDelay(1200);
    goto retry;
  }
  calibrated = true;

  // PROVE it before saving it: one real tap must land on SETTINGS.
  tft.fillScreen(C_BG);
  textAt(144, 140, 2, C_TXT, "NOW TAP SETTINGS");
  drawSettingsBand(false);
  for (int tries = 0; tries < 200; tries++) {   // ~22s of patience, then redo
    if (!touchDown()) { calibrationDelay(110); continue; }
    int raw = readTapRaw();             // MUST read like real use does, or
    uint32_t t0 = millis();             // verify proves the wrong thing
    while (touchDown() && millis() - t0 < 2500) calibrationDelay(80);
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

// (The four-corner axis probe that used to live here is deleted. Its
// question was answered properly by GridCal.ino: X across rows spread 5091
// vs 4596 down columns -- statistically nothing. One readable axis,
// vertical, exactly as the working BoxCal assumes.)
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
                             "   cal A=" + String(anchorRaw[0]) +
                             " P=" + String(anchorRaw[NANCH - 1]));

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
  delay(160);                         // flash AND the post-draw settle
}
void flashHeader(const String& s) {
  tft.fillRect(0, 0, 480, 44, C_ACC);
  textAt(16, 15, 2, C_BG, s);
  delay(160);
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
  delay(150);                         // see settleAfterDraw note in drawMenu
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
  // QUIET AFTER A BIG DRAW, BEFORE ANY TOUCH READ. Measured twice now: a
  // read taken right after heavy bus traffic comes back on a totally
  // different scale (2688..3613 during the calm calibration walk versus
  // 66..658 in a loop that repainted first), and every tap then collapses
  // onto one row. Home worked and the menu did not for exactly this reason
  // -- entering the menu paints five rows, then polls immediately.
  delay(150);
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
  textAt(140, 192, 1, C_ACC, "r1=" + String(anchorRaw[0]) +
                             "  r4=" + String(anchorRaw[3]) +
                             "  r8=" + String(anchorRaw[NANCH - 1]));
  textAt(24, 224, 1, C_LABEL, "last tap");
  textAt(140, 224, 1, C_ACC, String(lastTapRaw) + " -> " + String(lastTapY));

  textAt(24, 288, 1, C_LABEL, "tap anywhere to go back");
  delay(150);                         // same settle rule as drawMenu
}

// ------------------------------------------------------------------ sketch --
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> FaceUI: built on the proven TouchProof core");
  tft.begin();                        // once; the white screen was the
                                      // draw cost, not a missed init

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
  // NO DRAW IMMEDIATELY BEFORE THE READ. This is what made the finished UI
  // disagree with its own calibration: the walk measured 2688..3613 and the
  // very same finger then read 66..658 in the product loop, so every tap
  // collapsed onto row 1. The difference was a header repaint 12ms before
  // sampling; calibration always had ~80ms of quiet first. The repaint was
  // added on a hunch that the bus needed work, and the evidence killed that
  // hunch anyway -- 108 idle samples read a flat 0 with no drawing at all.
  // Quiet before the read, and match calibration's cadence.
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
