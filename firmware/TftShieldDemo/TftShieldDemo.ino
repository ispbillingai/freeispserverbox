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

// Guided calibration: the film's raw curve turned out non-linear (it goes
// flat left of mid-glass), so no assumed window can map it. Instead the
// sketch asks for one held tap on each button, learns the film's real
// signature at those three spots, and classifies presses by nearest match.
int calR = -1, calM = -1, calL = -1;
int calState = 0;         // 0=learning RIGHT  1=MID  2=LEFT  3=running

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

// GPIO12 (LCD_RS) is the ONLY clean analog end this wiring gives us:
//   - GPIO19 (LCD_D3) has no ADC at all.
//   - GPIO2  (LCD_D4) carries the devkit's own blue LED. The LED clamps
//     that node above the logic-low threshold, so it can neither be
//     analogRead honestly nor ever "decay" -- that clamp, not a broken
//     joint, is what produced the phantom tY=5000 "open circuit" and the
//     dead rawX. Driving GPIO2 as an OUTPUT is perfectly fine; only
//     floating or reading it lies to us.
// So: drive the Y plate, always sense on GPIO12. That is exactly the
// combination that tracked a finger on the very first bench run (raw
// 459..715), and it needs no rewiring.
int touchAxis() {
  pinMode(TY_A, OUTPUT); digitalWrite(TY_A, HIGH);   // gradient across Y...
  pinMode(TY_B, OUTPUT); digitalWrite(TY_B, LOW);
  pinMode(TX_A, INPUT);  pinMode(TX_B, INPUT);
  delayMicroseconds(60);
  int v = medianOf3(analogRead(TX_B),                // ...read where it is clean
                    analogRead(TX_B), analogRead(TX_B));
  tft.busPinsToOutput();
  return v;
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

// One status paint: the press flags, the raw number, and a marker bar that
// slides with the stylus. Everything lives on the glass so the bench never
// has to race a serial monitor.
const char *CAL_PROMPTS[3] = {"HOLD stylus on RIGHT btn",
                              "HOLD stylus on MID btn  ",
                              "HOLD stylus on LEFT btn "};

void showStatus(bool pressed, int raw, int pos, int zone) {
  char line[48];
  snprintf(line, sizeof(line), "p16=%d p12=%d  raw=%4d    ",
           press16, press12, raw);
  tft.setTextSize(2);
  tft.setTextColor(pressed ? C_OK : C_TEXT, C_BG);
  tft.setCursor(8, PAINT_TOP + 6);
  tft.print(line);

  if (calState < 3)
    snprintf(line, sizeof(line), "%s", CAL_PROMPTS[calState]);
  else
    snprintf(line, sizeof(line), "L=%4d M=%4d R=%4d %s", calL, calM, calR,
             (abs(calL - calM) < 150 || abs(calM - calR) < 150) ? "OVLP!" : "     ");
  tft.setTextColor(calState < 3 ? C_ACCENT : C_TEXT, C_BG);
  tft.setCursor(8, PAINT_TOP + 24);
  tft.print(line);

  const int by = PAINT_TOP + 46, bh = 54;
  tft.fillRect(0, by, 480, bh, C_BG);
  tft.drawRect(0, by, 480, bh, C_EDGE);
  for (int i = 1; i < 3; i++) tft.drawFastVLine(i * 160, by, bh, C_EDGE);
  if (pressed && pos >= 0)
    tft.fillRect(constrain(pos - 7, 0, 466), by + 3, 14, bh - 6, C_OK);

  if (zone != lastBtn) {
    for (int i = 0; i < 3; i++) drawButton(i, i == zone);
    lastBtn = zone;
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> TftShieldDemo: ILI9486, guided touch calibration");
  tft.begin();
  drawChrome();
  showStatus(false, 0, -1, -1);
}

void loop() {
  static uint32_t lastIdle = 0;
  static bool needRelease = false;
  static int nSamp = 0;
  static int samp[12];

  if (!touchPressed()) {                    // idle: refresh twice a second
    needRelease = false;
    nSamp = 0;
    if (millis() - lastIdle > 500) { lastIdle = millis(); showStatus(false, 0, -1, -1); }
    delay(10);
    return;
  }
  if (needRelease) { delay(10); return; }   // wait for a fresh press

  int raw = touchAxis();
  if (!touchPressed()) return;              // squeeze out release glitches
  if (raw < 40 || raw > 4050) return;       // rail readings are not positions

  if (calState < 3) {                       // learning this button's signature
    samp[nSamp++] = raw;
    if (nSamp >= 12) {
      for (int i = 1; i < 12; i++)          // sort, take the median
        for (int j = i; j > 0 && samp[j] < samp[j - 1]; j--) {
          int t = samp[j]; samp[j] = samp[j - 1]; samp[j - 1] = t;
        }
      int med = samp[6];
      if      (calState == 0) calR = med;
      else if (calState == 1) calM = med;
      else                    calL = med;
      Serial.printf("calibrated %s = %d\n",
                    calState == 0 ? "RIGHT" : calState == 1 ? "MID" : "LEFT", med);
      calState++; nSamp = 0; needRelease = true;
      showStatus(false, med, -1, -1);       // shows the next prompt
    }
    delay(20);
    return;
  }

  // classify by nearest learned signature -- immune to the film's flat zone
  int dl = abs(raw - calL), dm = abs(raw - calM), dr = abs(raw - calR);
  int zone = (dl <= dm && dl <= dr) ? 0 : (dm <= dr) ? 1 : 2;
  int pos = constrain(map(raw, calL, calR, 80, 400), 0, 479);
  Serial.printf("raw %4d -> zone %d pos %3d\n", raw, zone, pos);
  showStatus(true, raw, pos, zone);
  delay(25);
}
