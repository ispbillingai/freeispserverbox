/*  TftShieldDemo.ino -- ILI9486 3.5" shield: graphics + REAL 2D touch.
 *
 *  TOUCH PINOUT -- from the MCUFRIEND_kbv library, not from guessing.
 *  Its docs state these shields "tend to have a resistive TouchScreen on
 *  A1, 7, A2, 6", i.e. in shield-label terms:
 *
 *        X plate :  LCD_D6  <---->  LCD_RS      (XP .. XM)
 *        Y plate :  LCD_WR  <---->  LCD_D7      (YP .. YM)
 *
 *  My earlier pin-sniffing probe reported LCD_D0+LCD_RS and LCD_D3+LCD_D4.
 *  Only LCD_RS was right. Driving LCD_D3/D4 meant driving ordinary data
 *  lines and reading a phantom gradient -- which is exactly why the numbers
 *  went non-linear and flattened at mid-glass. Lesson: probe results are a
 *  hypothesis; the shield's documented pinout is the fact.
 *
 *  On our wiring all four touch lines land on usable ESP32 pins, and BOTH
 *  analog reads land on ADC-capable ones, so full 2D touch needs NO
 *  rewiring:
 *        XP = LCD_D6 -> GPIO23        XM = LCD_RS -> GPIO12  (ADC2)
 *        YP = LCD_WR -> GPIO14 (ADC2) YM = LCD_D7 -> GPIO5
 *
 *  Reading rule (standard 4-wire): to measure one axis, drive that plate's
 *  two ends HIGH/LOW and analogRead a pin on the OTHER plate.
 *
 *  ⚠ CS is raised during every touch read. The touch borrows LCD_WR, and a
 *  WR edge with CS low would latch garbage into the display controller.
 *
 *  WIRING -- unchanged, see TftShieldID.ino's header.
 *  Board = "ESP32 Dev Module", COM6. No WiFi here: the touch reads use ADC2,
 *  which a classic ESP32 cannot use while WiFi is running. The final board
 *  must move these onto ADC1 -- a PCB-rev note, not a bench problem.
 */

#include <Adafruit_GFX.h>
#include "soc/gpio_struct.h"

// ---- display bus pins ----
static const uint8_t PIN_D[8] = {16, 17, 18, 19, 2, 22, 23, 5};  // LCD_D0..D7
#define PIN_RD  21
#define PIN_WR  14
#define PIN_RS  12
#define PIN_CS  33
#define PIN_RST 4

// ---- touch pins (documented shield pinout, see header) ----
#define T_XP 23   // LCD_D6
#define T_XM 12   // LCD_RS   <- analog read for the Y axis
#define T_YP 14   // LCD_WR   <- analog read for the X axis
#define T_YM 5    // LCD_D7
#define Z_TOUCH 150          // z1 above this = a real press

#define MADCTL_VAL 0x28   // landscape 480x320. try 0xE8 if upside down
#define USE_INVERT 0

#define RGB(r,g,b) ((uint16_t)((((r)&0xF8)<<8)|(((g)&0xFC)<<3)|((b)>>3)))

// ------------------------------------------------- fast 8-bit parallel bus --
static uint32_t lutSet[256], lutClr[256];
static uint32_t WR_MASK, RS_MASK;

static inline void wrByte(uint8_t v) {
  GPIO.out_w1ts = lutSet[v];
  GPIO.out_w1tc = lutClr[v];
  GPIO.out_w1tc = WR_MASK;          // WR low
  __asm__ __volatile__("nop; nop");
  GPIO.out_w1ts = WR_MASK;          // rising edge latches the byte
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
    writeCmd(0x11); delay(120);          // sleep out
    writeCmd(0x3A); writeData(0x55);     // 16-bit RGB565 pixels
    writeCmd(0x36); writeData(MADCTL_VAL);
    writeCmd(USE_INVERT ? 0x21 : 0x20);
    writeCmd(0x29); delay(20);           // display on
  }

  void select()   { digitalWrite(PIN_CS, LOW);  }
  void deselect() { digitalWrite(PIN_CS, HIGH); }

  // touch borrows D6, D7, WR and RS; this hands them back to the LCD
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
    setWindow(x, y, x, y);
    writeData(c >> 8); writeData(c);
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
// Every read raises CS first (so stray WR edges cannot reach the display),
// then restores the bus and re-selects the panel.
static void touchDone() { tft.busPinsToOutput(); tft.select(); }

int tsRawX() {                      // drive X plate, sense on the Y plate
  tft.deselect();
  pinMode(T_YP, INPUT);  pinMode(T_YM, INPUT);
  pinMode(T_XP, OUTPUT); digitalWrite(T_XP, HIGH);
  pinMode(T_XM, OUTPUT); digitalWrite(T_XM, LOW);
  delayMicroseconds(150);
  int v = analogRead(T_YP);
  touchDone();
  return v;
}

int tsRawY() {                      // drive Y plate, sense on the X plate
  tft.deselect();
  pinMode(T_XP, INPUT);  pinMode(T_XM, INPUT);
  pinMode(T_YP, OUTPUT); digitalWrite(T_YP, HIGH);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, LOW);
  delayMicroseconds(150);
  int v = analogRead(T_XM);
  touchDone();
  return v;
}

// Pressure: with XP low and YM high, an untouched panel leaves XM near 0.
// A press bridges the plates and lifts it. Bigger z = firmer press.
int tsZ() {
  tft.deselect();
  pinMode(T_XP, OUTPUT); digitalWrite(T_XP, LOW);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, HIGH);
  pinMode(T_XM, INPUT);  pinMode(T_YP, INPUT);
  delayMicroseconds(150);
  int z1 = analogRead(T_XM);
  touchDone();
  return z1;
}

static int med5(int *s) {           // 5 samples, take the middle one
  for (int i = 1; i < 5; i++)
    for (int j = i; j > 0 && s[j] < s[j - 1]; j--) { int t = s[j]; s[j] = s[j - 1]; s[j - 1] = t; }
  return s[2];
}

bool readTouch(int *rx, int *ry, int *rz) {
  int z = tsZ();
  if (z < Z_TOUCH) { *rz = z; return false; }
  int xs[5], ys[5];
  for (int i = 0; i < 5; i++) { xs[i] = tsRawX(); ys[i] = tsRawY(); }
  if (tsZ() < Z_TOUCH) { *rz = 0; return false; }    // released mid-read
  *rx = med5(xs); *ry = med5(ys); *rz = z;
  return true;
}

// ------------------------------------------------------------ calibration --
// Three taps are enough: two along the top decide which raw axis is screen
// X (and its direction), one down the left side does the same for Y. That
// also removes the guesswork about rotation.
const int CX[3] = {40, 440,  40};
const int CY[3] = {40,  40, 280};
int calRX[3], calRY[3];
int calStep = 0;                    // 0..2 collecting, 3 = running
bool swapAxes = false;
long xBase, xSpan, yBase, ySpan;

void finishCalibration() {
  long dX_rx = calRX[1] - calRX[0], dX_ry = calRY[1] - calRY[0];
  long dY_rx = calRX[2] - calRX[0], dY_ry = calRY[2] - calRY[0];
  swapAxes = (labs(dX_rx) < labs(dX_ry));      // which raw axis tracked screen X?
  if (!swapAxes) { xBase = calRX[0]; xSpan = dX_rx; yBase = calRY[0]; ySpan = dY_ry; }
  else           { xBase = calRY[0]; xSpan = dX_ry; yBase = calRX[0]; ySpan = dY_rx; }
  if (xSpan == 0) xSpan = 1;
  if (ySpan == 0) ySpan = 1;
  Serial.printf("CAL swap=%d xBase=%ld xSpan=%ld yBase=%ld ySpan=%ld\n",
                swapAxes, xBase, xSpan, yBase, ySpan);
  calStep = 3;
}

void mapTouch(int rx, int ry, int *sx, int *sy) {
  long forX = swapAxes ? ry : rx, forY = swapAxes ? rx : ry;
  *sx = constrain(40 + (int)((forX - xBase) * 400 / xSpan), 0, 479);
  *sy = constrain(40 + (int)((forY - yBase) * 240 / ySpan), 0, 319);
}

// ---------------------------------------------------------------- demo UI --
#define C_BG     RGB(13, 17, 23)
#define C_BAR    RGB(22, 27, 34)
#define C_EDGE   RGB(48, 54, 61)
#define C_TEXT   0xFFFF
#define C_ACCENT RGB(31, 111, 235)
#define C_OK     RGB(63, 185, 80)

const int PAINT_TOP = 46, PAINT_BOT = 258, BTN_TOP = 262;
int lastBtn = -1;

void drawButton(int i, bool lit) {
  int x = i * 160;
  tft.fillRect(x + 4, BTN_TOP, 152, 320 - BTN_TOP - 4, lit ? C_ACCENT : C_BAR);
  tft.drawRect(x + 4, BTN_TOP, 152, 320 - BTN_TOP - 4, C_EDGE);
  tft.setTextColor(C_TEXT); tft.setTextSize(2);
  const char *names[3] = {"LEFT", "MID", "RIGHT"};
  tft.setCursor(x + 45, BTN_TOP + 20);
  tft.print(names[i]);
}

void drawChrome() {
  tft.fillScreen(C_BG);
  tft.fillRect(0, 0, 480, 42, C_BAR);
  tft.setTextColor(C_TEXT); tft.setTextSize(2);
  tft.setCursor(8, 6);  tft.print("FreeISP  ILI9486  TOUCH");
  uint16_t bars[6] = {RGB(255,0,0), RGB(0,255,0), RGB(0,0,255),
                      RGB(255,255,0), RGB(0,255,255), 0xFFFF};
  for (int i = 0; i < 6; i++) tft.fillRect(8 + i * 60, 26, 56, 12, bars[i]);
  tft.fillRect(432, 0, 48, 42, C_OK);
  tft.setCursor(438, 14); tft.print("CLR");
  for (int i = 0; i < 3; i++) drawButton(i, false);
  lastBtn = -1;
}

void drawCross(int i, uint16_t c) {
  tft.drawFastHLine(CX[i] - 14, CY[i], 29, c);
  tft.drawFastVLine(CX[i], CY[i] - 14, 29, c);
  tft.drawCircle(CX[i], CY[i], 9, c);
}

void promptCalibration() {
  tft.fillScreen(C_BG);
  tft.setTextColor(C_TEXT); tft.setTextSize(2);
  tft.setCursor(60, 150); tft.print("TAP THE CIRCLE, 3 TIMES");
  tft.setCursor(60, 180); tft.setTextColor(C_ACCENT);
  tft.print("use the stylus, press firmly");
  drawCross(calStep, C_OK);
}

// ------------------------------------------------------------------ sketch --
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> TftShieldDemo: ILI9486 + documented MCUFRIEND touch pins");
  tft.begin();
  promptCalibration();
}

void loop() {
  int rx, ry, rz;

  if (calStep < 3) {                          // ---- collecting cal points ----
    if (!readTouch(&rx, &ry, &rz)) { delay(20); return; }
    calRX[calStep] = rx; calRY[calStep] = ry;
    Serial.printf("cal point %d at (%d,%d): raw %d,%d  z=%d\n",
                  calStep, CX[calStep], CY[calStep], rx, ry, rz);
    drawCross(calStep, C_BG);                 // erase it
    calStep++;
    while (tsZ() >= Z_TOUCH) delay(10);       // wait for lift
    delay(150);
    if (calStep < 3) drawCross(calStep, C_OK);
    else { finishCalibration(); drawChrome(); }
    return;
  }

  static uint32_t lastIdle = 0;               // ---- running ----
  if (!readTouch(&rx, &ry, &rz)) {
    if (millis() - lastIdle > 400) {
      lastIdle = millis();
      tft.setTextSize(2); tft.setTextColor(C_TEXT, C_BG);
      tft.setCursor(8, PAINT_TOP + 4);
      tft.print("touch the screen      ");
    }
    delay(15);
    return;
  }

  int sx, sy;
  mapTouch(rx, ry, &sx, &sy);
  Serial.printf("raw %4d,%4d z=%4d -> screen %3d,%3d\n", rx, ry, rz, sx, sy);

  char line[40];
  snprintf(line, sizeof(line), "x=%3d y=%3d z=%4d   ", sx, sy, rz);
  tft.setTextSize(2); tft.setTextColor(C_OK, C_BG);
  tft.setCursor(8, PAINT_TOP + 4);
  tft.print(line);

  if (sy >= BTN_TOP) {                        // the three buttons
    int b = sx / 160;
    if (b != lastBtn) {
      if (lastBtn >= 0) drawButton(lastBtn, false);
      drawButton(b, true);
      lastBtn = b;
      Serial.printf("BUTTON: %s\n", b == 0 ? "LEFT" : b == 1 ? "MID" : "RIGHT");
    }
  } else if (sy < 42 && sx >= 432) {          // CLR
    tft.fillRect(0, PAINT_TOP + 26, 480, PAINT_BOT - PAINT_TOP - 26, C_BG);
  } else if (sy >= PAINT_TOP + 26 && sy < PAINT_BOT) {
    tft.fillRect(sx - 3, sy - 3, 7, 7, C_OK); // paint under the stylus
  }
  delay(15);
}
