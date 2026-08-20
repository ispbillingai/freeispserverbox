/*  FaceUI.ino -- the FreeISP touch face, built UP from what works.
 *
 *  BigUI.ino was built top-down and its touch read froze at 4095 for
 *  reasons that survived every fix. TouchProof.ino, on the same wiring,
 *  reads 0 idle and ~830 pressed. So this file starts from TouchProof's
 *  EXACT display + touch core, byte for byte, and adds interface on top --
 *  one layer at a time, touch re-checked after each. No WiFi yet: that is
 *  the last layer to go on, not the first.
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


// ---------------------------------------------------------------- palette --
#define C_BAR   RGB(22,27,34)
#define C_CARD  RGB(22,27,34)
#define C_EDGE  RGB(48,54,61)
#define C_LABEL RGB(140,140,150)
#define C_ACC   RGB(31,111,235)
#define C_WARN  RGB(255,210,0)

// ------------------------------------------------------------- touch state --
int  Z_IDLE = 0;
#define Z_MARGIN 400
static inline bool isDown(int z) { return abs(z - Z_IDLE) > Z_MARGIN; }

long yBase = 0, ySpan = 1;          // raw at screen y=40, delta over 240px
bool calibrated = false;

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
  return constrain(40 + (int)((long)(raw - yBase) * 240 / ySpan), 0, 319);
}

void textAt(int x,int y,uint8_t sz,uint16_t c,const String&s){
  tft.setTextSize(sz); tft.setTextColor(c); tft.setCursor(x,y); tft.print(s);
}

// Wait for a complete tap and return where it landed vertically.
bool waitTap(int *sy) {
  if (!isDown(zRead())) return false;
  int raw = readRawY();
  if (!isDown(zRead())) return false;
  uint32_t t0 = millis();
  while (isDown(zRead()) && millis() - t0 < 2500) delay(10);
  delay(60);
  *sy = screenY(raw);
  Serial.printf("TAP raw=%d -> y=%d\n", raw, *sy);
  return true;
}

// ------------------------------------------------------------ calibration --
void calibrate() {
  int got[2];
  const int band[2] = {20, 260};        // centres = screen y 40 and 280
  for (int i = 0; i < 2; i++) {
    tft.fillScreen(C_BG);
    textAt(70, 140, 2, C_TXT, i == 0 ? "TAP THE TOP BAR" : "TAP THE BOTTOM BAR");
    textAt(70, 172, 2, C_LABEL, "one-time setup");
    tft.fillRect(0, band[i], 480, 40, C_ACC);
    while (!isDown(zRead())) delay(10);
    got[i] = readRawY();
    Serial.printf("cal %d raw=%d\n", i, got[i]);
    while (isDown(zRead())) delay(10);
    delay(250);
  }
  yBase = got[0];
  ySpan = (got[1] - got[0]) ? (got[1] - got[0]) : 1;
  calibrated = true;
  Serial.printf("CAL yBase=%ld ySpan=%ld\n", yBase, ySpan);
}

// ------------------------------------------------------------------ screens --
enum { SCR_HOME, SCR_MENU } screen = SCR_HOME;

const int ROW_TOP = 52, ROW_H = 52;
void row(int i, const String& name, const String& val, uint16_t vc) {
  int y = ROW_TOP + i * ROW_H;
  tft.fillRect(8, y, 464, ROW_H - 6, C_CARD);
  tft.drawRect(8, y, 464, ROW_H - 6, C_EDGE);
  textAt(22, y + 14, 2, C_TXT, name);
  textAt(444 - val.length() * 12, y + 14, 2, vc, val);
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
  tft.fillRoundRect(360, 10, 108, 24, 12, C_WARN);
  textAt(372, 15, 2, C_BG, "OFFLINE");

  tft.fillRect(12, 56, 220, 88, C_CARD); tft.drawRect(12, 56, 220, 88, C_EDGE);
  textAt(26, 64, 1, C_LABEL, "USERS ONLINE");
  textAt(26, 84, 5, RGB(0,255,255), "42");
  tft.fillRect(248, 56, 220, 88, C_CARD); tft.drawRect(248, 56, 220, 88, C_EDGE);
  textAt(262, 64, 1, C_LABEL, "PPPoE");
  textAt(262, 84, 5, C_OK, "17");

  textAt(12, 158, 1, C_LABEL, "PORTS");
  const uint8_t st[5] = {1,1,1,0,1};
  for (int i = 0; i < 5; i++) drawJack(12 + i*66, 174, st[i]);

  tft.fillRect(0, 268, 480, 52, C_CARD);
  tft.drawFastHLine(0, 268, 480, C_ACC);
  textAt(178, 284, 2, C_ACC, "SETTINGS");
}

void drawMenu() {
  tft.fillScreen(C_BG);
  tft.fillRect(0, 0, 480, 44, C_BAR);
  textAt(16, 15, 2, C_ACC, "< BACK");
  textAt(180, 15, 2, C_TXT, "Settings");
  row(0, "WiFi",            "not set",  C_WARN);
  row(1, "Screen",          "100%",     C_LABEL);
  row(2, "Alarm",           "armed",    C_OK);
  row(3, "Calibrate touch", "",         C_LABEL);
  row(4, "Info",            "",         C_LABEL);
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
    textAt(90, 180, 2, C_LABEL, ".");
    delay(120);
  }

  int s[24];                            // now measure the resting level
  for (int i = 0; i < 24; i++) { s[i] = zRead(); yRead(); delay(20); }
  for (int i = 1; i < 24; i++)
    for (int j = i; j > 0 && s[j] < s[j-1]; j--) { int t=s[j]; s[j]=s[j-1]; s[j-1]=t; }
  Z_IDLE = s[12];
  Serial.printf("idle z=%d, press = %d+ away\n", Z_IDLE, Z_MARGIN);
  if (Z_IDLE > 3500) {                  // still railed: keep waiting, say so
    Serial.println("WARN: resting level still railed - warming up longer");
    for (int i = 0; i < 30; i++) { zRead(); yRead(); delay(60); }
    for (int i = 0; i < 24; i++) { s[i] = zRead(); yRead(); delay(20); }
    for (int i = 1; i < 24; i++)
      for (int j = i; j > 0 && s[j] < s[j-1]; j--) { int t=s[j]; s[j]=s[j-1]; s[j-1]=t; }
    Z_IDLE = s[12];
    Serial.printf("idle z (2nd try)=%d\n", Z_IDLE);
  }

  calibrate();
  drawHome();
}

void loop() {
  int sy;
  if (!waitTap(&sy)) { delay(15); return; }
  if (screen == SCR_HOME) {
    if (sy >= 268) { screen = SCR_MENU; drawMenu(); }
  } else {
    if (sy < 44) { screen = SCR_HOME; drawHome(); }
    else {
      int r = (sy - ROW_TOP) / ROW_H;
      Serial.printf("menu row %d\n", r);
      if (r == 3) { calibrate(); drawMenu(); }
      else if (r >= 0 && r < 5) {       // flash the row so a tap is visible
        int y = ROW_TOP + r * ROW_H;
        tft.fillRect(8, y, 464, ROW_H - 6, C_ACC);
        delay(160);
        drawMenu();
      }
    }
  }
}
