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
 *  BusTrace -- the experiment the independent review asked for.
 *
 *  The review found a confound in ABTrace: painting a colour changes the
 *  IMAGE *and* the electrical levels left on LCD data pins D0..D5, because
 *  wrByte() drives all eight data GPIOs and busOut() only restores
 *  direction, never a value. A GPIO output holds its level indefinitely, so
 *  "still true two seconds later" never separated the two.
 *
 *      dark fill  0x0882 -> last byte 0x82 -> D0..D5 retained 0x02
 *      white fill 0xFFFF -> last byte 0xFF -> D0..D5 retained 0x3F
 *
 *  This sketch separates them. It paints ONE image and never repaints it
 *  during a press. With CS HIGH and RD HIGH, and WITHOUT any WR strobe, it
 *  parks D0..D5 in three states -- all LOW, all HIGH, and released (INPUT,
 *  no pulls) -- and reads z/y in each. The park is re-applied immediately
 *  before every conversion, because done() re-outputs the bus after each
 *  read. No display command is ever issued, so the image cannot change.
 *
 *  Three presses on the DARK image, then it paints WHITE and takes three
 *  more, then cycles. Each phase also logs a no-finger baseline per state.
 *
 *  Reading the result:
 *    - readings follow the PARK STATE with the image fixed  -> electrical
 *      bus dependency. Then toggle the six bits one at a time.
 *    - readings follow the IMAGE with identical park states -> the image
 *      (or a display-related supply/ground effect) is genuinely involved.
 *    - both move -> both contribute.
 *
 *  Serial only during capture. Nothing is drawn while a finger is down.
 *  --------------------------------------------------------------------- */

#define C_WHITE 0xFFFF
enum { PARK_LOW, PARK_HIGH, PARK_INPUT };
const char *PARKNAME[3] = {"LOW  ", "HIGH ", "INPUT"};

// D0..D5 only: pins 16,17,18,19,2,22. D6 (23) and D7 (5) are electrodes
// and are left to the read routines exactly as before.
static void park(int state) {
  tft.desel();                          // CS HIGH: controller deselected
  for (int i = 0; i < 6; i++) {
    int p = PIN_D[i];
    if (state == PARK_INPUT) {
      pinMode(p, OUTPUT); digitalWrite(p, LOW);   // known register value
      pinMode(p, INPUT);                          // released, no pulls
    } else {
      pinMode(p, OUTPUT);
      digitalWrite(p, state == PARK_HIGH ? HIGH : LOW);
    }
  }
  // RD is never touched here: begin() drove it HIGH and nothing changes it.
  // WR is never pulsed: the primitives set it HIGH as an output or leave it
  // as an input, and never strobe it, so no write can reach the panel.
}

// One controlled pair: park, z, wait, park again, y.
static void readPair(int state, int *z, int *y) {
  park(state);
  *z = zRead();                         // ends with done(): bus re-output
  delay(110);
  park(state);                          // re-apply before the conversion
  *y = yRead();
}

int iZ = 0, iY = 0;
bool tDown = false; int tStreak = 0;
bool touchDown() {                      // BoxCal's detector, unchanged
  int z = zRead(), y = yRead();
  int dz = (z >= 4090) ? 0 : abs(z - iZ);
  int dy = (y >= 4090) ? 0 : abs(y - iY);
  int dev = max(dz, dy);
  bool now = dev > (tDown ? 3 : 5);
  if (now == tDown) { tStreak = 0; return tDown; }
  if (++tStreak >= 2) { tDown = now; tStreak = 0; }
  return tDown;
}

bool white = false;
int  press = 0;

static void paintPhase() {
  tft.fillScreen(white ? C_WHITE : C_BG);
  tft.busOut(); tft.sel();
  delay(300);
  Serial.printf("==== IMAGE=%s painted; retained D0..D5 = 0x%02X ====\n",
                white ? "WHITE" : "DARK ", white ? 0x3F : 0x02);
  // No-finger baseline, every park state, three pairs each.
  for (int s = 0; s < 3; s++) {
    Serial.printf("baseline IMAGE=%s park=%s  z/y:", white ? "WHITE" : "DARK ", PARKNAME[s]);
    for (int i = 0; i < 3; i++) { int z, y; readPair(s, &z, &y); Serial.printf("  %4d/%4d", z, y); delay(60); }
    Serial.println();
  }
  Serial.println("hold ONE finger still on the glass");
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> BusTrace: fixed image, parked D0..D5, z/y per state");
  tft.begin();
  tft.fillScreen(C_BG);
  for (int i = 0; i < 16; i++) { zRead(); yRead(); delay(120); }
  long sz = 0, sy = 0;
  for (int i = 0; i < 12; i++) { sz += zRead(); sy += yRead(); delay(40); }
  iZ = sz / 12; iY = sy / 12;
  Serial.printf("rest: z=%d y=%d\n", iZ, iY);
  white = false;
  paintPhase();
}

void loop() {
  if (!touchDown()) { delay(90); return; }
  press++;
  Serial.printf("---- press %d  IMAGE=%s ----\n", press, white ? "WHITE" : "DARK ");
  for (int s = 0; s < 3; s++) {
    Serial.printf("  park=%s  z/y:", PARKNAME[s]);
    for (int i = 0; i < 3; i++) { int z, y; readPair(s, &z, &y); Serial.printf("  %4d/%4d", z, y); delay(60); }
    Serial.println();
  }
  uint32_t t0 = millis();
  while (touchDown() && millis() - t0 < 4000) delay(90);
  Serial.println("  (lifted)");
  if (press % 3 == 0) {                 // three presses per image, then swap
    white = !white;
    paintPhase();
  }
}
