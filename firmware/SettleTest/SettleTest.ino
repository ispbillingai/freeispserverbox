/*  SettleTest.ino -- ONE question, no UI, no calibration, no NVS:
 *
 *      does yRead()'s SETTLE DELAY explain why a light press reads a
 *      position unrelated to the finger?
 *
 *  The hypothesis (not mine -- proposed in review, and it fits the bench
 *  data better than anything else so far): the panel is a high source
 *  impedance, and a light press raises the contact resistance further. The
 *  ADC's sample-and-hold then never charges to the real divider voltage in
 *  the 200us the code allows, so the conversion comes back LOW -- and low
 *  is also where the bottom of the glass lives. A firm press lowers the
 *  contact resistance, settles in time, and reads true. That is exactly the
 *  measured behaviour: held anchors span 282..997, quick taps anywhere on
 *  the glass come back 3..251.
 *
 *  If a longer settle fixes it, the fix is a delay constant and hold-to-
 *  select can be dropped. If the reading stays collapsed at 20ms, settling
 *  is not the mechanism and the panel is genuinely force-dependent on this
 *  wiring -- which makes it a hardware item for the PCB, not a firmware bug
 *  to keep chasing.
 *
 *  METHOD (deliberately minimal, per the review):
 *      - ONE ADC1 sample per measurement. No oversampling, no medians.
 *      - NO GPIO14/ADC2 read anywhere.
 *      - zRead() between conversions to honour the never-back-to-back law,
 *        and ~110ms between rounds, the only cadence proven on this panel.
 *      - Four settle delays per press: 200us, 1ms, 5ms, 20ms.
 *
 *  WHAT TO DO: press LIGHTLY and hold still, first near the TOP of the
 *  glass, then the MIDDLE, then the BOTTOM. Read the four numbers per
 *  press. If the 20ms column tracks height while the 200us column does
 *  not, the hypothesis is confirmed.
 *
 *  Wiring is FaceUI's, unchanged and frozen:
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
#define T_XM PIN_RS    // LCD_RS  (GPIO33, ADC1)  <- the only pin we read
#define T_YP PIN_WR    // LCD_WR  (GPIO14, ADC2)  <- never read here
#define T_YM 5         // LCD_D7

#define RGB(r,g,b) ((uint16_t)((((r)&0xF8)<<8)|(((g)&0xFC)<<3)|((b)>>3)))
#define C_BG   RGB(13,17,23)
#define C_OK   RGB(63,185,80)
#define C_ACC  RGB(31,111,235)
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

// yRead with the settle delay as a parameter -- THE variable under test.
// Everything else is TouchProof's yRead byte for byte.
int yReadSettle(uint32_t us) {
  tft.desel();
  pinMode(T_XP, INPUT);  pinMode(T_XM, INPUT);
  pinMode(T_YP, OUTPUT); digitalWrite(T_YP, HIGH);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, LOW);
  if (us >= 1000) delay(us / 1000); else delayMicroseconds(us);
  int v = analogRead(T_XM);          // ONE conversion. No oversampling.
  done();
  return v;
}

void textAt(int x, int y, uint8_t sz, uint16_t c, const String &s) {
  tft.setTextSize(sz); tft.setTextColor(c, C_BG); tft.setCursor(x, y); tft.print(s);
}

const uint32_t SETTLE[4] = {200, 1000, 5000, 20000};
const char *LABEL[4]     = {"200us", "1ms", "5ms", "20ms"};

int iZ = 0, iY = 0;                  // resting levels, measured at boot
bool down = false; int streak = 0;

// Contact test, using only the proven reads and the proven cadence.
bool contact() {
  int z = zRead();
  int y = yReadSettle(200);
  int dev = max(z > 4000 ? 0 : abs(z - iZ), y > 4000 ? 0 : abs(y - iY));
  bool now = dev > (down ? 3 : 5);
  if (now == down) { streak = 0; return down; }
  if (++streak >= 2) { down = now; streak = 0; }
  return down;
}

void banner() {
  tft.fillScreen(C_BG);
  textAt(10, 8,  2, C_TXT, "SETTLE TEST");
  textAt(10, 36, 1, C_ACC, "press LIGHTLY and hold still");
  textAt(10, 52, 1, C_ACC, "do it at TOP, then MIDDLE, then BOTTOM");
  tft.drawFastHLine(0, 74, 480, C_ACC);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> SettleTest: does a longer settle recover the position?");
  tft.begin();
  banner();

  // Warm-up in the proven pattern, then measure resting levels.
  for (int i = 0; i < 16; i++) {
    zRead(); yReadSettle(200);
    textAt(10 + i * 10, 92, 2, C_ACC, ".");
    delay(120);
  }
  long sz = 0, sy = 0;
  for (int i = 0; i < 12; i++) { sz += zRead(); sy += yReadSettle(200); delay(40); }
  iZ = sz / 12; iY = sy / 12;
  Serial.printf("rest: zRead=%d yRead=%d\n", iZ, iY);
  textAt(10, 92, 2, C_ACC, "ready            ");
}

int shot = 0;
void loop() {
  if (!contact()) { delay(110); return; }

  // A press is under way. Take ONE sample at each settle delay, spaced at
  // the proven cadence, with a zRead between to satisfy the interleave law.
  int v[4];
  for (int i = 0; i < 4; i++) {
    zRead();
    delay(110);
    v[i] = yReadSettle(SETTLE[i]);
  }
  while (contact()) delay(110);      // wait for release

  shot++;
  Serial.printf("SETTLE %2d:  200us=%4d   1ms=%4d   5ms=%4d   20ms=%4d\n",
                shot, v[0], v[1], v[2], v[3]);

  tft.fillRect(0, 110, 480, 210, C_BG);
  for (int i = 0; i < 4; i++) {
    textAt(20, 120 + i * 42, 3, C_TXT, String(LABEL[i]) + " ");
    textAt(190, 120 + i * 42, 3, v[i] > 300 ? C_OK : C_ACC, String(v[i]) + "   ");
  }
  textAt(10, 296, 1, C_ACC, "press #" + String(shot) + " - move to the next spot");
}
