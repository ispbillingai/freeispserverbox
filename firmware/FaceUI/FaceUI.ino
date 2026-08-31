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
int  Z_IDLE = 0;

// THE one way to poll for a press. zRead alone in a tight loop leaves the
// sense node charged from the previous done(), and the reading rails at
// 4095 -- the "dead panel / stuck press" symptom that cost a whole bench
// session (commit 5ec1126). yRead's value is thrown away; its job is
// reconfiguring all four lines so the node discharges before the next z
// conversion. Every repeated poll in this file goes through here, and every
// call site keeps a real delay() between rounds.
static inline int pollZ() { int z = zRead(); yRead(); return z; }

// TRUE press detection for the one-ADC-pin wiring -- the night's biggest
// lesson, learned when the glass went fully dead: "probe wait z=0 idle=0"
// under a real finger. The old zRead (XP low, YM high, read XM) IS the
// position gradient once a finger is down, so wherever that gradient
// itself reads ~idle (the XP corner, the bottom band) a press was
// INVISIBLE. No deviation threshold can see a press that reads exactly
// like no press. Fix by physics, not thresholds: sample the same node
// under BOTH polarities. Finger down, the two reads are complementary --
// their SUM is ~4095 wherever the finger is. Floating, the node reads its
// residual charge twice: sum ~0 or ~8190, never the middle. DOWN = sum in
// the middle window 2 rounds running; UP = out of a wider window 2 rounds.
// DIGITAL contact test -- the fix for the night's real bug, which Francis
// diagnosed from the bench: "press the points and z is 0, press anywhere
// else and it presses well". zRead IS the position gradient, and at one
// end of the glass that gradient reads 0 -- which is exactly what an
// untouched panel reads. A press there is not weak, it is INVISIBLE, so no
// analog threshold on that pin can ever see it. That end is the bottom,
// which is why SETTINGS -- and only SETTINGS -- refused all night while
// every other row worked.
//
// So detection stops using the position signal at all. Pull the X plate up
// and drive the Y plate low: a finger anywhere bridges the plates and drags
// X down. Position-independent, and the standard 4-wire wake-up test.
// Analog reads stay for POSITION only, where a 0 is just a legitimate
// coordinate at the end of the scale.
// This is Adafruit_TouchScreen's actual getPoint() pressure test, which we
// had never used: XP low, YM high, then read BOTH free corners --
// z1 = XM (X plate) and z2 = YP (Y plate) -- and take z = 4095 - (z2 - z1).
// Untouched the two plates sit at opposite rails, so z ~ 0 EVERYWHERE. A
// touch shorts them at the contact point, they converge, and z rises no
// matter WHERE the finger is. That is the property one-pin detection can
// never have, and why the bottom of the glass was invisible all night.
// z2 lives on GPIO14/ADC2 -- unusable in a WiFi sketch, perfectly fine
// here, because FaceUI deliberately links no radio.
// ONLY PROVEN PRIMITIVES. Everything invented tonight -- the inverted-
// polarity twin, the digital pullup test, the Adafruit two-pin pressure
// formula, a second-axis xRead -- misbehaved on this wiring: the pressure
// formula sat at z=2346 with nothing touching the glass (idle z2 reads
// 1749, not the 4095 rail its maths assumes) so the box "tapped" forever,
// and every position read came back 0 or railed. Meanwhile TouchProof.ino
// measured, on THIS panel, on THIS wiring: zRead and yRead BOTH read 0
// resting and ~830 under a finger.
//
// So detection uses exactly those two, and uses them TOGETHER: zRead goes
// blind at the XP end of the glass (that is the bottom -- the reason
// SETTINGS never answered), and yRead is the read that stays awake there.
// A press is either one waking up. Nothing new is configured.
int tZ1 = 0, tZ2 = 0;
#define T_ON  120                     // Francis, at the bench: "even a 200
#define T_OFF  60                     // touch should register". Idle traces
                                      // a clean 0, so 120 is still far above
                                      // the noise floor and catches the weak
                                      // presses the old 260 was dropping.
bool tDown = false; int tStreak = 0, tLastZ = 0, tLastB = 0;
bool touchDown() {                    // one detection round + state update
  tZ1 = zRead();                      // interleaved by construction: the
  tZ2 = yRead();                      // two configs alternate every round
  tLastZ = max(tZ1, tZ2);
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
int  lastTapRaw = -1, lastTapY = -1;  // shown on the INFO screen

Preferences prefs;
#define CAL_VER 2                   // v2 = 3-point piecewise. Bumping this
                                    // orphans every stored cal on purpose

int med5(int *s) {
  for (int i = 1; i < 5; i++)
    for (int j = i; j > 0 && s[j] < s[j-1]; j--) { int t=s[j]; s[j]=s[j-1]; s[j-1]=t; }
  return s[2];
}
// Same rule as the warm-up: never take these reads back to back. A zRead
// between them reconfigures all four lines, so the sense node is not still
// holding charge from the previous conversion. Without this the position
// rails at 4095 exactly the way the pressure line used to.
int readRawY() {
  int s[5];
  for (int i = 0; i < 5; i++) { zRead(); delayMicroseconds(400); s[i] = yRead(); }
  return med5(s);
}

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

// Position of the CURRENT press: median of rounds spanning the WHOLE
// contact, starting at first touch. Two bench lessons written in blood:
// (1) one immediate burst reads the unseated film -- high raw, taps land
// above the finger (the "SETTINGS refused" build); (2) waiting 50ms and
// sampling only the firm phase reads pressure, not position -- all three
// cal targets came back nearly the same number (848/775/540). The spread
// that worked (1392/766/432) came from rounds across ALL phases of the
// press with the median picking the honest middle. So: start immediately,
// keep sampling while the finger is down, median the lot.
// Returns -1 for a graze too short for 3 rounds or a railed result.
int readTapRaw() {
  int cap[7], m = 0;
  while (touchDown() && m < 7) { cap[m++] = readRawY(); delay(15); }
  if (m < 3) return -1;
  for (int a = 1; a < m; a++)
    for (int j = a; j > 0 && cap[j] < cap[j-1]; j--) { int t=cap[j]; cap[j]=cap[j-1]; cap[j-1]=t; }
  int raw = cap[m / 2];
  return (raw > 4000) ? -1 : raw;
}

void textAt(int x,int y,uint8_t sz,uint16_t c,const String&s){
  tft.setTextSize(sz); tft.setTextColor(c); tft.setCursor(x,y); tft.print(s);
}

// Wait for a complete tap and return where it landed vertically.
bool waitTap(int *sy) {
  // A press that outlives the 2.5s escape below still fires once -- but the
  // NEXT tap needs an observed release first. Without this latch a long hold
  // re-fired its band every ~2.6s (Alarm toggling itself under one finger).
  static bool stuckDown = false;
  if (stuckDown) {
    if (touchDown()) { delay(15); return false; }
    stuckDown = false;
    delay(60);
    return false;
  }
  if (!touchDown()) return false;
  int raw = readTapRaw();               // seat, then median across the press
  if (raw < 0) {                        // graze, dab, or railed read
    Serial.println("TAP discarded: unseated/railed");
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
// All-NEW key names on purpose: the old keys hold calibration from previous
// wirings and must never be read again. Z_IDLE is deliberately NOT stored --
// the resting level moved between wirings, so it stays the fresh per-boot
// median measurement.
bool calValid(long a, long b, long c) {
  long s1 = b - a, s2 = c - b;                  // top / bottom segment spans
  if (a < 0 || a > 4095 || b < 0 || b > 4095 || c < 0 || c > 4095) return false;
  if (labs(s1) < 120 || labs(s2) < 120) return false;   // squeezed segment
  if ((s1 > 0) != (s2 > 0)) return false;               // direction flip
  if (labs(s1) > 3 * labs(s2) || labs(s2) > 3 * labs(s1)) return false;
  return true;                                  // 3x skew = something railed
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
    textAt(300, TY[i] + 28, 2, C_LABEL, "idle=" + String(Z_IDLE));
    int n = 0;
    while (!touchDown()) {            // wait-for-press with a live readout;
      if (++n % 8 == 0) {             // the repaint doubles as real drawing
        tft.fillRect(114, TY[i] + 26, 90, 18, C_BG);  // between poll rounds
        textAt(116, TY[i] + 28, 2, C_OK, (tLastB ? "DOWN " : "up ") + String(tLastZ));
      }
      delay(12);
    }
    // Sample for as long as the hold lasts, up to 7 median rounds from the
    // FIRST instant of contact -- no seat delay. The 50ms-delay experiment
    // proved the firm phase reads pressure, not position: all three targets
    // converged to the same number. First-contact-onward rounds with a
    // median across them is what produced the spread that mapped true.
    int cap[7], m = 0;
    while (touchDown() && m < 7) { cap[m++] = readRawY(); delay(30); }
    while (touchDown()) delay(10);
    for (int a = 1; a < m; a++)
      for (int j = a; j > 0 && cap[j] < cap[j-1]; j--) { int t=cap[j]; cap[j]=cap[j-1]; cap[j-1]=t; }
    if (m < 3 || cap[m / 2] > 4000) {
      Serial.printf("cal %d retry: rounds=%d\n", i, m);
      textAt(90, TY[i] + 56, 2, C_WARN, m < 3 ? "HOLD IT LONGER" : "BAD READ - AGAIN");
      delay(900);
      i--;
      continue;
    }
    got[i] = cap[m / 2];
    Serial.printf("cal %d raw=%ld (%d rounds)\n", i, got[i], m);
    delay(250);
  }
  // Accept with the SAME validator the boot path uses, or a map that loads
  // tomorrow differs from the map that saved today.
  if (!calValid(got[0], got[1], got[2])) {
    Serial.printf("CAL rejected: %ld %ld %ld\n", got[0], got[1], got[2]);
    tft.fillScreen(C_BG);
    textAt(66, 150, 2, C_WARN, "POINTS DON'T LINE UP - AGAIN");
    delay(900);
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
  for (int tries = 0; tries < 400; tries++) {   // ~16s of patience, then redo
    if (!touchDown()) {                         // (100x40ms was a 4s window
      if ((tries & 7) == 0) {                   //  -- a live bug too).
        tft.fillRect(204, 174, 90, 18, C_BG);   // Repaint between rounds +
        textAt(206, 176, 2, C_OK, (tLastB ? "DOWN " : "up ") + String(tLastZ));   // live z, per the law:
      }                                         // this wait was BARE, which
      delay(40);                                // is plausibly why verify
      continue;                                 // refused all night.
    }
    int raw = readTapRaw();             // MUST read like real use does, or
    while (touchDown()) delay(10);  // verify proves the wrong thing
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
    int n = 0;
    while (!touchDown()) {            // live readout: the repaint IS the bus
      if (++n % 8 == 0) {             // traffic the sense line needs between
        tft.fillRect(154, ty + 26, 90, 18, C_BG);       // rounds. The bare
        textAt(156, ty + 28, 2, C_OK, (tLastB ? "DOWN " : "up ") + String(tLastZ));  // wait loop shipped
        if (n % 160 == 0)                               // here first went
          Serial.printf("probe wait contact=%d pos=%d\n", tLastB, tLastZ);
      }                                                 // on the bench.
      delay(12);
    }
    int cap[7], m = 0;
    while (touchDown() && m < 7) { cap[m++] = readRawY(); delay(30); }
    while (touchDown()) delay(10);
    for (int a = 1; a < m; a++)
      for (int j = a; j > 0 && cap[j] < cap[j-1]; j--) { int t=cap[j]; cap[j]=cap[j-1]; cap[j-1]=t; }
    if (m >= 3 && cap[m / 2] <= 4000) {
      Serial.printf("probe %-12s raw=%d (%d rounds)\n", label, cap[m / 2], m);
      delay(250);
      return cap[m / 2];
    }
    Serial.printf("probe %s retry (rounds=%d)\n", label, m);
    delay(500);
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
long loA = 4095, hiA = 0, loB = 4095, hiB = 0;   // learned extents

void gridChrome() {
  tft.fillScreen(C_BG);
  for (int c = 1; c < GC; c++) tft.drawFastVLine(c * GW, 0, 320, C_EDGE);
  for (int r = 1; r < GR; r++) tft.drawFastHLine(0, r * GH, 480, C_EDGE);
  textAt(6, 4, 1, C_LABEL, "press any box - it prints its own numbers");
}
void gridMap() {                      // never returns: this IS the build
  gridChrome();
  int taps = 0, beat = 0;
  for (;;) {
    if (!touchDown()) {
      // Trace what the detector SEES, always -- the only way to tell a
      // finger that is not registering from a finger that never came.
      if (++beat % 40 == 0) {
        Serial.printf("watch zRead=%4d yRead=%4d max=%4d (down at >%d)\n",
                      tZ1, tZ2, tLastZ, T_ON);
        tft.fillRect(300, 2, 176, 12, C_BG);
        textAt(302, 4, 1, C_OK, "z1 " + String(tZ1) + "  z2 " + String(tZ2) +
                                "  z " + String(tLastZ));
      }
      delay(12);
      continue;
    }
    int a[7], b[7], m = 0;            // median across the whole contact.
    while (touchDown() && m < 7) {    // A and B are the two proven reads,
      a[m] = tZ2; b[m] = tZ1; m++;    // captured by touchDown itself -- no
      delay(15);                      // extra pin juggling to go wrong
    }
    while (touchDown()) delay(10);
    if (m < 3) continue;
    for (int i = 1; i < m; i++)
      for (int j = i; j > 0 && a[j] < a[j-1]; j--) { int t=a[j]; a[j]=a[j-1]; a[j-1]=t; }
    for (int i = 1; i < m; i++)
      for (int j = i; j > 0 && b[j] < b[j-1]; j--) { int t=b[j]; b[j]=b[j-1]; b[j-1]=t; }
    long rawA = a[m/2], rawB = b[m/2];
    if (rawA > 4090 && rawB > 4090) continue;    // both railed = junk

    if (rawA < loA) loA = rawA;   if (rawA > hiA) hiA = rawA;
    if (rawB < loB) loB = rawB;   if (rawB > hiB) hiB = rawB;

    // ONE honest coordinate, not two. yRead (A) drives one plate and reads
    // the other -- a real position. zRead (B) is the pressure config and
    // only wobbles with position; using it as a column is what lit a box
    // nowhere near the finger. So light the whole BAND that A maps to and
    // claim nothing about the other axis. Which way the band moves under a
    // top-to-bottom sweep versus a left-to-right sweep is the answer we
    // still need: if left-right moves it, the readable axis is horizontal
    // and the UI turns portrait.
    int row = (hiA - loA > 150)
            ? constrain((int)((rawA - loA) * GR / (hiA - loA)), 0, GR-1) : 0;
    gridChrome();
    tft.fillRect(0, row * GH + 1, 480, GH - 1, C_ACC);
    textAt(150, row * GH + 12, 2, C_BG, "band " + String(row));
    textAt(8, 300, 2, C_TXT, "A=" + String(rawA) + "  B=" + String(rawB) +
                             "   A seen " + String(loA) + ".." + String(hiA));

    taps++;
    Serial.printf("GRID %d: A=%ld B=%ld -> band %d of %d | A %ld..%ld  B %ld..%ld\n",
                  taps, rawA, rawB, row, GR, loA, hiA, loB, hiB);
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

  textAt(24, 176, 1, C_LABEL, "Z_IDLE");   textAt(140, 176, 1, C_ACC, String(Z_IDLE));
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

  int s[24];                            // now measure the resting level
  for (int i = 0; i < 24; i++) { s[i] = pollZ(); delay(20); }
  for (int i = 1; i < 24; i++)
    for (int j = i; j > 0 && s[j] < s[j-1]; j--) { int t=s[j]; s[j]=s[j-1]; s[j-1]=t; }
  Z_IDLE = s[12];
  Serial.printf("idle z=%d (reference only); press = A+B sum ~4095, 2 rounds\n", Z_IDLE);
  if (Z_IDLE > 3500) {                  // still railed: keep waiting, say so
    Serial.println("WARN: resting level still railed - warming up longer");
    for (int i = 0; i < 30; i++) { pollZ(); delay(60); }
    for (int i = 0; i < 24; i++) { s[i] = pollZ(); delay(20); }
    for (int i = 1; i < 24; i++)
      for (int j = i; j > 0 && s[j] < s[j-1]; j--) { int t=s[j]; s[j]=s[j-1]; s[j-1]=t; }
    Z_IDLE = s[12];
    Serial.printf("idle z (2nd try)=%d\n", Z_IDLE);
  }

  loadSettings();
  gridMap();                            // DIAGNOSTIC BUILD: never returns --
                                        // map the glass, learn the extents
  if (!loadCal()) calibrate();          // stored cal survives reboots now;
  drawHome();                           // calibrate() re-saves itself
}

uint32_t lastPulse = 0;
void loop() {
  int sy;
  if (millis() - lastPulse > 900) {   // heartbeat: one real LCD write per
    lastPulse = millis();             // second, because waiting loops with
    tft.fillRect(0, 0, 2, 2, C_BAR);  // zero bus traffic go dead on this
  }                                   // panel (probe screen proved it)
  if (!waitTap(&sy)) { delay(15); return; }

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
