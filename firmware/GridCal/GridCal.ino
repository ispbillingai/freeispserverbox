/*  BoxCal.ino -- Francis's calibration, built his way and nothing else.
 *
 *      "we can start with 8 boxes so that we name them A B C D E F G H,
 *       so we know if I press the middle of box this, the x and z should
 *       register this and this -- that is how we calibrate"
 *
 *  Exactly that. Eight full-width boxes A..H down the glass. It walks you
 *  through them one at a time: press the middle of the highlighted box, it
 *  records the number that box produces and prints it IN the box. After H,
 *  you have a measured table -- what each part of the screen actually reads
 *  -- and it flips into TEST mode where pressing any box fills that box.
 *
 *  WHY EIGHT ANCHORS INSTEAD OF THREE: with a reading measured for every
 *  box, a tap is matched to the NEAREST anchor. No straight-line fit, no
 *  extrapolation past the ends, no piecewise hinge -- the arithmetic that
 *  kept mapping presses into the wrong row simply is not needed. If the
 *  panel is non-linear, a per-box table absorbs it for free.
 *
 *  Built on TouchProof.ino's display + touch core, byte for byte, because
 *  that is the only code proven on this hardware. Everything below it is
 *  new; nothing inside it has been touched.
 *
 *  THE THREE RULES THIS SKETCH OBEYS (all measured on this bench):
 *    1. Position is zRead -> wait 110ms -> yRead. A yRead taken straight
 *       after a zRead comes back collapsed, worst on a light press, which
 *       is what made quick taps report a bottom-of-screen position wherever
 *       the finger was.
 *    2. A sample under 30 is NO CONTACT, not a low position. A sample costs
 *       ~220ms and a quick tap ends before its own read, giving 0 -- and 0
 *       maps to the bottom of the glass. Drop them; never map them.
 *    3. Idle reads exactly 0 with no noise, so the press gate is 5.
 *
 *  Wiring is the frozen one:
 *      LCD_D0..D7 -> 16, 17, 18, 19, 2, 22, 23, 5
 *      LCD_WR -> 14   LCD_RS -> 33   LCD_CS -> 21   LCD_RD -> 12
 *      LCD_RST -> 4
 */

#include <Adafruit_GFX.h>
#include "soc/gpio_struct.h"

static const uint8_t PIN_D[8] = {16, 17, 18, 19, 2, 22, 23, 5};
#define PIN_WR  14
#define PIN_RS  33
#define PIN_CS  21
#define PIN_RD  12
#define PIN_RST 4

#define T_XP 23        // LCD_D6
#define T_XM PIN_RS    // LCD_RS  (GPIO33, ADC1)
#define T_YP PIN_WR    // LCD_WR  (GPIO14, ADC2) -- never analogRead here
#define T_YM 5         // LCD_D7

#define RGB(r,g,b) ((uint16_t)((((r)&0xF8)<<8)|(((g)&0xFC)<<3)|((b)>>3)))
#define C_BG    RGB(13,17,23)
#define C_EDGE  RGB(48,54,61)
#define C_LABEL RGB(140,140,150)
#define C_ACC   RGB(31,111,235)
#define C_OK    RGB(63,185,80)
#define C_TXT   0xFFFF

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

// ---------------------------------------------------------------- touch --
// RULE 1: the two configs must be 110ms apart or the position collapses.
int posRead() { zRead(); delay(110); return yRead(); }

// THE SECOND AXIS -- the question this sketch exists to answer. Drive the X
// plate and read the Y plate: the mirror of yRead. It reads GPIO14, which
// is ADC2; there is no WiFi in this sketch so ADC2 is available in
// principle, and an earlier attempt at this returned a flat 4095 -- but
// that was during the era when every read was corrupted by taking the two
// configs back to back. With the 110ms spacing that fixed everything else,
// it deserves one honest re-test. If every column calibrates to the same
// number, the axis genuinely does not read and the grid stays rows-only.
int xRead() {
  tft.desel();
  pinMode(T_YP, INPUT);  pinMode(T_YM, INPUT);
  pinMode(T_XP, OUTPUT); digitalWrite(T_XP, HIGH);
  pinMode(T_XM, OUTPUT); digitalWrite(T_XM, LOW);
  delayMicroseconds(200);
  int v = analogRead(T_YP);
  done();
  return v;
}
int posReadX() { zRead(); delay(110); return xRead(); }

int  iZ = 0, iY = 0;                // resting levels, measured at boot
bool tDown = false; int tStreak = 0, tDev = 0;
bool touchDown() {                  // one detection round
  int z = zRead();
  int y = yRead();
  int dz = (z > 4000) ? 0 : abs(z - iZ);
  int dy = (y > 4000) ? 0 : abs(y - iY);
  tDev = max(dz, dy);
  bool now = tDev > (tDown ? 3 : 5);            // RULE 3
  if (now == tDown) { tStreak = 0; return tDown; }
  if (++tStreak >= 2) { tDown = now; tStreak = 0; }
  return tDown;
}

static int med(int *s, int n) {
  for (int i = 1; i < n; i++)
    for (int j = i; j > 0 && s[j] < s[j-1]; j--) { int t=s[j]; s[j]=s[j-1]; s[j-1]=t; }
  return s[n / 2];
}
// Captures BOTH axes across one press: Y and X sampled in alternating
// rounds, each preceded by its own spaced zRead. Returns false if the
// press produced no contact on the Y axis (the one known to work).
int capY = -1, capX = -1;
bool capture2() {
  int sy[4], sx[4]; int ny = 0, nx = 0;
  while (touchDown() && ny < 4) {
    int y = posRead();
    if (y >= 30) sy[ny++] = y;                  // RULE 2
    if (!touchDown()) break;
    int x = posReadX();
    if (x >= 30 && x <= 4000) sx[nx++] = x;     // 4095 = not attached
  }
  uint32_t t0 = millis();                       // bounded release wait
  while (touchDown() && millis() - t0 < 2500) delay(60);
  capY = ny ? med(sy, ny) : -1;
  capX = nx ? med(sx, nx) : -1;
  return capY > 0;
}

// ----------------------------------------------------------------- boxes --
// 16 boxes, at Francis's call. Worth knowing what the 8-box run measured
// first: A=943 B=917 C=823 D=688 E=601 F=458 G=273 H=149. The full span is
// ~794 counts, so 8 boxes had ~100 counts each and test taps landed off by
// up to 63. Halving the box height halves the budget to ~50, which is
// inside that error -- and the top is worse still, since A to B moved only
// 26 counts (which is exactly why pressing A selected B). The gaps printed
// after calibration say plainly which boxes this panel can actually tell
// apart; anything under ~60 counts is a box you cannot reliably hit.
// 4 x 4 = 16 boxes, laid out as a real grid. Rows come from the axis we
// know works; columns are the open question this sketch tests.
#define COLS 4
#define ROWS 4
#define NBOX (COLS * ROWS)
#define BW   (480 / COLS)           // 120px
#define BH   (320 / ROWS)           // 80px
const char *NAME = "ABCDEFGHIJKLMNOP";
int anchorY[NBOX], anchorX[NBOX];   // what each box measured, per axis
int idx = 0;                        // which box we are calibrating
bool testing = false;
bool xWorks = false;                // decided from the calibration data

void textAt(int x, int y, uint8_t sz, uint16_t c, const String &s) {
  tft.setTextSize(sz); tft.setTextColor(c, C_BG); tft.setCursor(x, y); tft.print(s);
}

void drawBoxes(int hot, const String &note) {
  tft.fillScreen(C_BG);
  for (int i = 0; i < NBOX; i++) {
    int cx = (i % COLS) * BW, cy = (i / COLS) * BH;
    if (i == hot) tft.fillRect(cx + 1, cy + 1, BW - 2, BH - 2, C_ACC);
    tft.drawRect(cx, cy, BW, BH, C_EDGE);
    uint16_t fg = (i == hot) ? C_BG : C_TXT, bg = (i == hot) ? C_ACC : C_BG;
    tft.setTextSize(3); tft.setTextColor(fg, bg);
    tft.setCursor(cx + 8, cy + 6); tft.print(NAME[i]);
    if (anchorY[i] > 0) {           // what this box measured, both axes
      tft.setTextSize(1);
      tft.setTextColor((i == hot) ? C_BG : C_OK, bg);
      tft.setCursor(cx + 8, cy + 40); tft.print("y "); tft.print(anchorY[i]);
      tft.setCursor(cx + 8, cy + 54); tft.print("x ");
      if (anchorX[i] > 0) tft.print(anchorX[i]); else tft.print("--");
    }
  }
  tft.setTextSize(1); tft.setTextColor(C_LABEL, C_BG);
  tft.setCursor(6, 310); tft.print(note);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> BoxCal: 8 boxes A..H, press the middle of each");
  for (int i = 0; i < NBOX; i++) { anchorY[i] = 0; anchorX[i] = 0; }
  tft.begin();
  tft.fillScreen(C_BG);
  textAt(120, 140, 2, C_TXT, "BoxCal starting");

  for (int i = 0; i < 16; i++) {    // warm-up in the proven pattern
    zRead(); yRead();
    textAt(120 + i * 12, 170, 2, C_ACC, ".");
    delay(120);
  }
  long sz = 0, sy = 0;
  for (int i = 0; i < 12; i++) { sz += zRead(); sy += yRead(); delay(40); }
  iZ = sz / 12; iY = sy / 12;
  Serial.printf("rest: z=%d y=%d  (press gate 5)\n", iZ, iY);

  drawBoxes(0, "press the MIDDLE of the blue box");
}

void loop() {
  if (!testing) {
    // ---- CALIBRATE: walk A..P, one box at a time -------------------------
    if (!touchDown()) { delay(80); return; }
    if (!capture2()) {
      Serial.printf("box %c: no contact in that press, try again\n", NAME[idx]);
      drawBoxes(idx, "no contact - press a little longer");
      return;
    }
    anchorY[idx] = capY;
    anchorX[idx] = capX;
    Serial.printf("box %c  y=%d  x=%d\n", NAME[idx], capY, capX);
    idx++;
    if (idx < NBOX) {
      drawBoxes(idx, "good - now the MIDDLE of the blue box");
      return;
    }

    // ---- THE VERDICT ON THE SECOND AXIS --------------------------------
    // Columns are real only if X separates boxes that share a row. Compare
    // the spread of X ACROSS a row against the spread DOWN a column: if X
    // is a genuine horizontal coordinate the first is large and the second
    // is small. If X just tracks Y, or never reads, it fails this.
    Serial.println("TABLE (y / x):");
    for (int r = 0; r < ROWS; r++) {
      Serial.printf("  row %d:", r + 1);
      for (int c = 0; c < COLS; c++) {
        int i = r * COLS + c;
        Serial.printf("  %c=%d/%d", NAME[i], anchorY[i], anchorX[i]);
      }
      Serial.println();
    }
    long acrossRows = 0, downCols = 0; int nx = 0;
    for (int r = 0; r < ROWS; r++) {
      int lo = 9999, hi = -1;
      for (int c = 0; c < COLS; c++) { int v = anchorX[r*COLS+c];
        if (v > 0) { if (v < lo) lo = v; if (v > hi) hi = v; nx++; } }
      if (hi > 0) acrossRows += (hi - lo);
    }
    for (int c = 0; c < COLS; c++) {
      int lo = 9999, hi = -1;
      for (int r = 0; r < ROWS; r++) { int v = anchorX[r*COLS+c];
        if (v > 0) { if (v < lo) lo = v; if (v > hi) hi = v; } }
      if (hi > 0) downCols += (hi - lo);
    }
    xWorks = (nx >= NBOX / 2) && (acrossRows > downCols * 2) && (acrossRows > 200);
    Serial.printf("X axis: %d/%d boxes read, spread ACROSS rows=%ld, DOWN cols=%ld -> %s\n",
                  nx, NBOX, acrossRows, downCols,
                  xWorks ? "COLUMNS WORK - real 2D grid"
                         : "no usable X - rows only");
    testing = true;
    drawBoxes(-1, xWorks ? "TEST 2D: press any box" : "TEST: rows only (X unusable)");
    return;
  }

  // ---- TEST: nearest anchor wins. No fitting, no extrapolation. ---------
  if (!touchDown()) { delay(80); return; }
  if (!capture2()) { Serial.println("test tap: no contact"); return; }
  int best = 0; long bestd = 0x7fffffff;
  for (int i = 0; i < NBOX; i++) {
    if (anchorY[i] <= 0) continue;
    long dy = capY - anchorY[i];
    long d  = dy * dy;
    if (xWorks && capX > 0 && anchorX[i] > 0) {
      long dx = capX - anchorX[i];
      d += dx * dx;                 // 2D nearest neighbour
    }
    if (d < bestd) { bestd = d; best = i; }
  }
  Serial.printf("TEST y=%d x=%d -> box %c (anchor %d/%d)\n",
                capY, capX, NAME[best], anchorY[best], anchorX[best]);
  drawBoxes(best, "y " + String(capY) + "  x " + String(capX) +
                  "  -> box " + String(NAME[best]));
}
