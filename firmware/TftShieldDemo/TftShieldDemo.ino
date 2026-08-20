/*  TftShieldDemo.ino -- REAL graphics + touch on the 3.5" shield.
 *
 *  TftShieldID told us everything this sketch builds on:
 *    - controller = ILI9486 (reg 0xD3 -> 66 00 94 86), 320x480
 *    - touch plate X = shield LCD_D0 + LCD_RS   (GPIO 16 + 12)
 *    - touch plate Y = shield LCD_D3 + LCD_D4   (GPIO 19 + 2)
 *
 *  WIRING -- same as TftShieldID AFTER the RD/D4 swap (see its header).
 *  Quick check: J4 DC -> LCD_D4 and U4 SDA -> LCD_RD, everything else
 *  as first wired.
 *
 *  WHAT YOU SHOULD SEE:
 *    - color bars across the top (proves red/green/blue channels)
 *    - a paint area: press and drag, dots follow your finger
 *    - three buttons on the bottom row (LEFT / MID / RIGHT) that light
 *      up when tapped -- RIGHT is deliberately in the "weak" third so
 *      we can judge how usable that zone really is
 *    - tap CLR (top-right) to wipe the paint area
 *  Serial @ 115200 prints raw touch numbers for calibration.
 *
 *  If the picture is MIRRORED or UPSIDE DOWN: change MADCTL_VAL below
 *  (0x28 / 0xE8 / 0x48 / 0x88) -- one byte controls orientation.
 *  If colors look NEGATIVE (white where black should be): USE_INVERT 1.
 *
 *  Board = "ESP32 Dev Module", COM6, hold BOOT while uploading.
 *  No WiFi in this sketch ON PURPOSE: the touch reads use ADC2 pins,
 *  which classic ESP32s cannot analogRead while WiFi runs. The final
 *  firmware must put the two touch sense lines on ADC1 -- a note for
 *  the PCB rev, not a problem today.
 */

#include <Adafruit_GFX.h>
#include "soc/gpio_struct.h"

// ---- pins (all data/WR/RS below GPIO32 so single-register writes work) ----
static const uint8_t PIN_D[8] = {16, 17, 18, 19, 2, 22, 23, 5};  // LCD_D0..D7
#define PIN_RD  21
#define PIN_WR  14
#define PIN_RS  12
#define PIN_CS  33   // held LOW the whole time -- nothing shares the bus
#define PIN_RST 4

// ---- touch (measured by the probe, not assumed) ----
#define TX_A 16   // X plate ends
#define TX_B 12   //   (12 = ADC2 -> the X sense end)
#define TY_A 19   // Y plate ends
#define TY_B 2    //   (2  = ADC2 -> the Y sense end)

// ---- orientation + calibration -- tune from the serial numbers ----
#define MADCTL_VAL 0x28   // landscape 480x320. try 0xE8 if upside down
#define USE_INVERT 0
#define SWAP_AXES  0      // 1 if the dot moves up/down when your finger goes left/right
#define FLIP_X     0
#define FLIP_Y     0
int RAW_X_MIN = 300, RAW_X_MAX = 3700;   // stretched to fit as you calibrate
int RAW_Y_MIN = 300, RAW_Y_MAX = 3700;

#define RGB(r,g,b) ((uint16_t)((((r)&0xF8)<<8)|(((g)&0xFC)<<3)|((b)>>3)))

// ------------------------------------------------- fast 8-bit parallel bus --
// One 256-entry lookup: for every possible byte, which GPIOs go high and
// which go low. Writing a byte is then two register writes + the WR strobe.
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
    busPinsToOutput();
    pinMode(PIN_RD, OUTPUT);  digitalWrite(PIN_RD, HIGH);
    pinMode(PIN_CS, OUTPUT);  digitalWrite(PIN_CS, LOW);   // selected forever
    pinMode(PIN_RST, OUTPUT); digitalWrite(PIN_RST, HIGH);
    delay(5);
    digitalWrite(PIN_RST, LOW);  delay(20);
    digitalWrite(PIN_RST, HIGH); delay(120);

    writeCmd(0x11); delay(120);          // sleep out
    writeCmd(0x3A); writeData(0x55);     // 16-bit RGB565 pixels
    writeCmd(0x36); writeData(MADCTL_VAL);
    writeCmd(USE_INVERT ? 0x21 : 0x20);
    writeCmd(0x29); delay(20);           // display on
  }

  // touch borrows 4 bus lines; call this to hand them back to the LCD
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
// Plain 4-wire resistive reads on the measured plate pins. Each read
// borrows the lines for a moment, then busPinsToOutput() returns them.
int medianOf3(int a, int b, int c) {
  if (a > b) { int t = a; a = b; b = t; }
  if (b > c) { b = c; }
  return (a > b) ? a : b;
}

// The sense plate appears to be CRACKED into two islands: one island only
// reaches the LCD_D0 end (GPIO16), the other only the LCD_RS end (GPIO12).
// Session one listened on 16 -> left side answered; the next build listened
// on 12 -> right side answered. So: listen on BOTH ends at once, and report
// them separately so each island can be seen announcing itself.
bool press16 = false, press12 = false;

bool touchPressed() {
  pinMode(TY_A, OUTPUT); digitalWrite(TY_A, LOW);   // ground the whole Y plate
  pinMode(TY_B, OUTPUT); digitalWrite(TY_B, LOW);
  pinMode(TX_A, INPUT_PULLUP);                      // both X ends float high...
  pinMode(TX_B, INPUT_PULLUP);
  delayMicroseconds(300);                           // long dupont run = slow rise
  press16 = (digitalRead(TX_A) == LOW);             // ...unless a finger joins
  press12 = (digitalRead(TX_B) == LOW);             //    their island to ground
  tft.busPinsToOutput();
  return press16 || press12;
}

int touchReadX() {   // gradient across the X plate, finger reports via Y plate
  pinMode(TX_A, OUTPUT); digitalWrite(TX_A, HIGH);
  pinMode(TX_B, OUTPUT); digitalWrite(TX_B, LOW);
  pinMode(TY_A, INPUT);  pinMode(TY_B, INPUT);
  delayMicroseconds(40);
  int v = medianOf3(analogRead(TY_B), analogRead(TY_B), analogRead(TY_B));
  tft.busPinsToOutput();
  return v;
}

int touchReadY() {   // gradient across the Y plate, sensed on the X plate
  pinMode(TY_A, OUTPUT); digitalWrite(TY_A, HIGH);
  pinMode(TY_B, OUTPUT); digitalWrite(TY_B, LOW);
  pinMode(TX_A, INPUT);  pinMode(TX_B, INPUT);
  delayMicroseconds(40);
  int v = medianOf3(analogRead(TX_B), analogRead(TX_B), analogRead(TX_B));
  tft.busPinsToOutput();
  return v;
}

// Software ohm-meter: charge one end of a plate, release it, time the drain
// through the plate to the grounded other end. Solid path = a few us. A bad
// dupont/solder joint = hundreds. 5000 = open. Catches the "gripping the
// plastic, barely touching metal" fault that a simple connected-test passes.
uint32_t decayMicros(uint8_t chargePin, uint8_t groundPin) {
  pinMode(groundPin, OUTPUT); digitalWrite(groundPin, LOW);
  pinMode(chargePin, OUTPUT); digitalWrite(chargePin, HIGH);
  delayMicroseconds(50);
  pinMode(chargePin, INPUT);
  uint32_t t0 = micros();
  while (digitalRead(chargePin) && (micros() - t0) < 5000) {}
  uint32_t dt = micros() - t0;
  tft.busPinsToOutput();
  return dt;
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
  tft.setCursor(8, 6);  tft.print("FreeISP  ILI9486  TOUCH TEST");
  // color bars: prove each channel separately
  uint16_t bars[6] = {RGB(255,0,0), RGB(0,255,0), RGB(0,0,255),
                      RGB(255,255,0), RGB(0,255,255), 0xFFFF};
  for (int i = 0; i < 6; i++) tft.fillRect(8 + i * 60, 26, 56, 12, bars[i]);
  // CLR zone
  tft.fillRect(432, 0, 48, 42, C_OK);
  tft.setCursor(438, 14); tft.print("CLR");
  for (int i = 0; i < 3; i++) drawButton(i, false);
  lastBtn = -1;
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> TftShieldDemo: ILI9486 + measured touch plates");
  Serial.println(">>> press around; raw numbers below feed the calibration");
  tft.begin();
  drawChrome();
}

void loop() {
  // heartbeat: report the touch machinery's state twice a second -- on the
  // GLASS as well as serial, so the bench needs no timing games with the PC
  static uint32_t lastBeat = 0;
  if (millis() - lastBeat > 500) {
    lastBeat = millis();
    bool p = touchPressed();
    int hx = touchReadX(), hy = touchReadY();
    // path health, all four combinations so a one-ended fault shows itself:
    uint32_t tX  = decayMicros(16, 12);   // X plate, charge D0 end
    uint32_t tXr = decayMicros(12, 16);   // X plate, charge RS end
    uint32_t tY  = decayMicros(2, 19);    // Y plate, charge D4 end  <- suspect
    uint32_t tYr = decayMicros(19, 2);    // Y plate, charge D3 end
    Serial.printf("heartbeat: p16=%d p12=%d rawX=%4d rawY=%4d  "
                  "tX=%u/%u tY=%u/%u\n",
                  press16, press12, hx, hy, tX, tXr, tY, tYr);
    char line[48];
    snprintf(line, sizeof(line), "p16=%d p12=%d X=%4d Y=%4d   ",
             press16, press12, hx, hy);
    tft.setTextSize(2);
    tft.setTextColor(p ? C_OK : C_TEXT, C_BG);
    tft.setCursor(8, PAINT_TOP + 2);
    tft.print(line);
    snprintf(line, sizeof(line), "tX=%4u/%-4u tY=%4u/%-4u   ",
             tX, tXr, tY, tYr);
    tft.setTextColor(C_TEXT, C_BG);
    tft.setCursor(8, PAINT_TOP + 20);
    tft.print(line);
  }

  if (!touchPressed()) { delay(15); return; }
  int rx = touchReadX(), ry = touchReadY();
  if (!touchPressed()) return;              // squeeze out release glitches

  // stretch the calibration window live as bigger/smaller raws appear
  if (rx < RAW_X_MIN && rx > 50)   RAW_X_MIN = rx;
  if (rx > RAW_X_MAX && rx < 4050) RAW_X_MAX = rx;
  if (ry < RAW_Y_MIN && ry > 50)   RAW_Y_MIN = ry;
  if (ry > RAW_Y_MAX && ry < 4050) RAW_Y_MAX = ry;

  int px = map(rx, RAW_X_MIN, RAW_X_MAX, 0, 479);
  int py = map(ry, RAW_Y_MIN, RAW_Y_MAX, 0, 319);
#if SWAP_AXES
  int t = px; px = map(py, 0, 319, 0, 479); py = map(t, 0, 479, 0, 319);
#endif
#if FLIP_X
  px = 479 - px;
#endif
#if FLIP_Y
  py = 319 - py;
#endif
  px = constrain(px, 0, 479); py = constrain(py, 0, 319);

  Serial.printf("raw %4d %4d  ->  screen %3d %3d\n", rx, ry, px, py);

  if (py >= BTN_TOP) {                       // bottom row: the three buttons
    int b = px / 160;
    if (b != lastBtn) {
      if (lastBtn >= 0) drawButton(lastBtn, false);
      drawButton(b, true);
      lastBtn = b;
      Serial.printf("BUTTON: %s\n", b == 0 ? "LEFT" : b == 1 ? "MID" : "RIGHT");
    }
  } else if (py < 42 && px >= 432) {         // CLR zone
    tft.fillRect(0, PAINT_TOP, 480, PAINT_BOT - PAINT_TOP, C_BG);
    Serial.println("cleared");
  } else if (py >= PAINT_TOP && py < PAINT_BOT) {
    tft.fillRect(px - 3, py - 3, 7, 7, C_OK); // paint
  }
  delay(20);
}
