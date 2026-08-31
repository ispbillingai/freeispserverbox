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
#define Z_MARGIN 400
static inline bool isDown(int z) { return abs(z - Z_IDLE) > Z_MARGIN; }

// THE one way to poll for a press. zRead alone in a tight loop leaves the
// sense node charged from the previous done(), and the reading rails at
// 4095 -- the "dead panel / stuck press" symptom that cost a whole bench
// session (commit 5ec1126). yRead's value is thrown away; its job is
// reconfiguring all four lines so the node discharges before the next z
// conversion. Every repeated poll in this file goes through here, and every
// call site keeps a real delay() between rounds.
static inline int pollZ() { int z = zRead(); yRead(); return z; }

long yBase = 0, ySpan = 1;          // raw at screen y=40, delta over 240px
bool calibrated = false;
int  lastTapRaw = -1, lastTapY = -1;  // shown on the INFO screen

Preferences prefs;
#define CAL_VER 1                   // bump to orphan stored cal after a rewire

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
  // A press that outlives the 2.5s escape below still fires once -- but the
  // NEXT tap needs an observed release first. Without this latch a long hold
  // re-fired its band every ~2.6s (Alarm toggling itself under one finger).
  static bool stuckDown = false;
  if (stuckDown) {
    if (isDown(pollZ())) { delay(15); return false; }
    stuckDown = false;
    delay(60);
    return false;
  }
  if (!isDown(pollZ())) return false;
  int raw = readRawY();
  if (!isDown(pollZ())) return false;
  uint32_t t0 = millis();
  while (isDown(pollZ()) && millis() - t0 < 2500) delay(10);
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
bool calValid(long b, long s) {
  return b >= 0 && b <= 4095 && labs(s) >= 300 && labs(s) <= 4000;
}
bool loadCal() {                    // boot path: true = stored cal is usable
  prefs.begin("freeisp", true);
  bool verOk = prefs.getUChar("vcal_ver", 0) == CAL_VER;
  long b = prefs.getLong("vcal_base", -1), s = prefs.getLong("vcal_span", 0);
  prefs.end();
  if (!verOk || !calValid(b, s)) return false;
  yBase = b; ySpan = s; calibrated = true;
  Serial.printf("CAL loaded yBase=%ld ySpan=%ld\n", b, s);
  return true;
}
void saveCal() {                    // only ever called from calibrate()
  prefs.begin("freeisp", false);
  prefs.putUChar("vcal_ver", CAL_VER);
  prefs.putLong("vcal_base", yBase);
  prefs.putLong("vcal_span", ySpan);
  prefs.end();
  Serial.printf("CAL SAVED yBase=%ld ySpan=%ld  (factory-default candidates)\n", yBase, ySpan);
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
void calibrate() {
retry:
  int got[2];
  for (int i = 0; i < 2; i++) {
    tft.fillScreen(C_BG);
    // Bars are 60px tall and full width -- generous, because this is the
    // one screen the user must hit BEFORE any calibration exists. The
    // centres stay at screen y=40 and y=280, so screenY()'s 40/240 mapping
    // is untouched.
    tft.fillRect(0, i ? 250 : 10, 480, 60, C_ACC);
    textAt(70, 120, 2, C_TXT, i == 0 ? "TAP THE TOP BAR (1/2)"
                                     : "TAP THE BOTTOM BAR (2/2)");
    textAt(70, 148, 2, C_LABEL, "z=");
    textAt(300, 148, 2, C_LABEL, "idle=" + String(Z_IDLE));
    int z, n = 0;
    while (!isDown(z = pollZ())) {  // wait-for-press with a live readout;
      if (++n % 8 == 0) {           // the repaint doubles as real drawing
        tft.fillRect(200, 146, 90, 18, C_BG);   // between poll rounds
        textAt(200, 148, 2, C_OK, String(z));
      }
      delay(12);
    }
    got[i] = readRawY();            // capture DURING the press...
    while (isDown(pollZ())) delay(10);   // ...accept on RELEASE
    delay(250);                     // debounce before the next screen
    Serial.printf("cal %d raw=%d\n", i, got[i]);
  }
  // Accept with the SAME validator the boot path uses -- if they differ, a
  // railed tap (span > 4000, the charged-node signature) gets saved, mis-maps
  // every tap this session, then loadCal() silently rejects it next boot.
  if (!calValid(got[0], (long)got[1] - got[0])) {
    Serial.printf("CAL rejected: implausible pair (%d, %d)\n", got[0], got[1]);
    tft.fillScreen(C_BG);
    textAt(90, 150, 2, C_WARN, "BAD TAPS - TRY AGAIN");
    delay(900);
    goto retry;
  }
  yBase = got[0];
  ySpan = got[1] - got[0];
  calibrated = true;
  Serial.printf("CAL yBase=%ld ySpan=%ld\n", yBase, ySpan);
  saveCal();
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
  textAt(24, 192, 1, C_LABEL, "yBase");    textAt(140, 192, 1, C_ACC, String(yBase));
  textAt(24, 208, 1, C_LABEL, "ySpan");    textAt(140, 208, 1, C_ACC, String(ySpan));
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
  Serial.printf("idle z=%d, press = %d+ away\n", Z_IDLE, Z_MARGIN);
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
  if (!loadCal()) calibrate();          // stored cal survives reboots now;
  drawHome();                           // calibrate() re-saves itself
}

void loop() {
  int sy;
  if (!waitTap(&sy)) { delay(15); return; }

  if (screen == SCR_HOME) {
    // HOME tiles into two bands. 268-319 is the SETTINGS band (matches the
    // drawn rect exactly). Everything above it -- 0-267 -- is content with
    // no action, so a tap there flashes the SETTINGS band as a HINT: it
    // teaches where to tap and kills the orphan dead zone.
    if (sy >= 268) {
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
