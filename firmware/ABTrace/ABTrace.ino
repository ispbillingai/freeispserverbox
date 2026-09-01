/*  TouchProof.ino -- ONE question, no distractions:
 *  does the touch panel respond on the wiring that is fitted RIGHT NOW?
 *
 *  No WiFi, no NVS, no menus, no calibration. Just the proven ILI9486
 *  driver, the proven touch read, and the pressure number in huge digits
 *  so the answer is readable from across the bench without a serial cable.
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



/*  ---------------------------------------------------------------------
 *  ABTrace -- one question, four cases.
 *
 *  Review's hypothesis, and it fits the evidence better than anything I
 *  proposed: the alternating 4095 samples are a STALE, PRE-CHARGED INPUT
 *  NODE, not an ADC reference shift (a reference change would scale every
 *  conversion, not rail every other one). GPIO33 is BOTH T_XM and LCD_RS.
 *  After every touch read, done() calls busOut(), which makes GPIO33 an
 *  LCD output and drives it HIGH. The next touch read flips that freshly
 *  charged pin into a high-impedance ADC input -- and sometimes samples
 *  the leftover charge instead of the panel.
 *
 *  If that is right, WHERE the LCD writes sit relative to the two reads
 *  should change the numbers. Four cases, same stationary finger:
 *
 *    1  zRead -> 110ms -> yRead, no drawing at all
 *    2  draw the 80x20 header rect BEFORE zRead
 *    3  draw it BETWEEN zRead and yRead
 *    4  full-screen repaint before zRead
 *
 *  No Preferences, no NVS, no calibration, no UI. Hold ONE finger still in
 *  the middle of the glass and let it run; it prints four pairs per case.
 *  --------------------------------------------------------------------- */

int iZ = 0, iY = 0;
bool tDown = false; int tStreak = 0;

bool touchDown() {                    // BoxCal's detector, unchanged
  int z = zRead(), y = yRead();
  int dz = (z > 4000) ? 0 : abs(z - iZ);
  int dy = (y > 4000) ? 0 : abs(y - iY);
  int dev = max(dz, dy);
  bool now = dev > (tDown ? 3 : 5);
  if (now == tDown) { tStreak = 0; return tDown; }
  if (++tStreak >= 2) { tDown = now; tStreak = 0; }
  return tDown;
}

static void drawSmall() { tft.fillRect(300, 18, 80, 20, RGB(22,27,34)); }
static void drawBig()   { tft.fillScreen(C_BG); }

// Cases 5 and 6 test SCREEN CONTENT, not timing. ABTrace and BoxCal show
// nearly blank screens and read 150..1000; FaceUI shows bright filled
// cards and reads 2700..4095 on the same glass, with no ADC config
// difference between them. The touch film is bonded straight onto the
// LCD, so a bright complex image means far more source-driver switching
// coupling into it. Both cases wait 300ms after painting, so any
// difference is the IMAGE, not the write burst.
// THE DECIDING PAIR. Cases 5/6 showed dark->0 and white->4095 at 300ms.
// What we still do not know is whether that is RECENCY (the write burst
// fading) or STEADY STATE (the image itself, permanently). Cases 7 and 8
// repeat them after a full TWO SECONDS of stillness:
//   both come back ~650  -> recency only. Fix = wait longer after drawing,
//                           and any UI colours are fine.
//   white still 4095     -> the displayed image itself biases the film, so
//                           the UI must stay uniformly dark, per screen.
const char *CASE[8] = {
  "1 no draw            ",
  "2 small draw BEFORE z",
  "3 small draw z..y    ",
  "4 FULL repaint before",
  "5 screen DARK  +300ms",
  "6 screen WHITE +300ms",
  "7 screen DARK  +2000 ",
  "8 screen WHITE +2000 "
};

void runCase(int c) {
  Serial.printf("%s : ", CASE[c]);
  if (c == 4) { tft.fillScreen(C_BG);  delay(300); }   // dark, settled
  if (c == 5) { tft.fillScreen(0xFFFF); delay(300); }  // white, settled
  if (c == 6) { tft.fillScreen(C_BG);  delay(2000); }  // dark, fully settled
  if (c == 7) { tft.fillScreen(0xFFFF); delay(2000); } // white, fully settled
  for (int i = 0; i < 4; i++) {
    if (c == 1) drawSmall();
    if (c == 3) drawBig();
    int z = zRead();
    if (c == 2) drawSmall();
    delay(110);
    int y = yRead();
    Serial.printf(" z=%4d y=%4d |", z, y);
    delay(60);
  }
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> ABTrace: hold ONE finger still at screen centre");
  tft.begin();
  tft.fillScreen(C_BG);
  tft.setTextSize(2); tft.setTextColor(C_TXT, C_BG);
  tft.setCursor(20, 60);  tft.print("ABTrace");
  tft.setCursor(20, 100); tft.print("HOLD a finger still");
  tft.setCursor(20, 130); tft.print("in the MIDDLE");
  for (int i = 0; i < 16; i++) { zRead(); yRead(); delay(120); }
  long sz = 0, sy = 0;
  for (int i = 0; i < 12; i++) { sz += zRead(); sy += yRead(); delay(40); }
  iZ = sz / 12; iY = sy / 12;
  Serial.printf("rest: z=%d y=%d\n", iZ, iY);
}

int run = 0;
void loop() {
  if (!touchDown()) { delay(90); return; }
  run++;
  Serial.printf("---- press %d ----\n", run);
  for (int c = 0; c < 8; c++) runCase(c);
  tft.fillScreen(C_BG);
  tft.setTextSize(2); tft.setTextColor(C_TXT, C_BG);
  tft.setCursor(20, 140); tft.printf("run %d done - lift", run);
  uint32_t t0 = millis();
  while (touchDown() && millis() - t0 < 4000) delay(90);
}
