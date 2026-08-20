/*  TftShieldID.ino -- FIRST CONTACT with the 3.5" TFT LCD Shield (the blue
 *  Uno-style board). Three jobs, all over Serial @ 115200:
 *
 *    1. Read the LCD controller's ID registers and print them. The chip on
 *       these shields varies by batch (ILI9486 / ILI9488 / ST7796 / clones)
 *       and the DRIVER MUST MATCH -- so we ask the chip who it is first.
 *    2. Flash the panel using the "all pixels on" trick (works on every
 *       MIPI-style controller, no driver needed). Screen lights up whitish
 *       = panel + wiring alive, even before we know the chip.
 *    3. Probe for the resistive TOUCH film. It has no chip of its own --
 *       it is two resistive plates wired onto four of the same LCD lines.
 *       We find which four, then stream raw press readings.
 *
 *  WIRING -- shield label -> ESP32 GPIO. DevKit sits on the EXPANSION BOARD
 *  (or the rev-H brain board with EVERYTHING else unplugged -- screen, RFID,
 *  LEDs, buzzer, relay, reed all off their headers; same GPIOs, read the
 *  socket labels). Female-female dupont wires, 15 total:
 *
 *    5V      -> 5V / VIN     (the AMS1117 on the shield makes its own 3.3V)
 *    GND     -> GND
 *    LCD_D0  -> 16      LCD_D1  -> 17      LCD_D2  -> 18      LCD_D3 -> 19
 *    LCD_D4  -> 21      LCD_D5  -> 22      LCD_D6  -> 23      LCD_D7 -> 25
 *    LCD_RD  -> 26      LCD_WR  -> 27      LCD_RS  -> 32      LCD_CS -> 33
 *    LCD_RST -> 4
 *
 *    NOT CONNECTED: 3V3, SD_SCK, SD_DO, SD_DI, SD_SS (the SD slot -- only
 *    matters if we ever use the microSD card), and any unlabeled pins.
 *
 *  Board = "ESP32 Dev Module", COM6, hold BOOT while uploading.
 *  ESP32's 3.3V logic drives the shield fine -- no level shifter.
 *  The backlight is hardwired on the shield; there is no BL wire.
 */

const uint8_t PIN_D[8] = {16, 17, 18, 19, 21, 22, 23, 25};  // LCD_D0..D7
#define PIN_RD  26
#define PIN_WR  27
#define PIN_RS  32   // "register select" = data/command, the shield calls it RS
#define PIN_CS  33
#define PIN_RST 4

// Every signal line, for the touch probe (touch plates hide among these).
const uint8_t ALL_PINS[13] = {16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33, 4};

// Classic-ESP32 pins that can analogRead. 32/33 are ADC1 (work even with
// WiFi on later); 25/26/27/4 are ADC2 (bench only, WiFi off -- which it is).
bool adcCapable(uint8_t p) {
  return p == 32 || p == 33 || p == 25 || p == 26 || p == 27 || p == 4;
}

// ---------------------------------------------------------------- 8080 bus --
void busMode(uint8_t mode) { for (uint8_t i = 0; i < 8; i++) pinMode(PIN_D[i], mode); }
void busWrite(uint8_t v) {
  for (uint8_t i = 0; i < 8; i++) digitalWrite(PIN_D[i], (v >> i) & 1);
}
uint8_t busRead() {
  uint8_t v = 0;
  for (uint8_t i = 0; i < 8; i++) if (digitalRead(PIN_D[i])) v |= (1 << i);
  return v;
}
void wrStrobe() { digitalWrite(PIN_WR, LOW); digitalWrite(PIN_WR, HIGH); }
void writeCmd(uint8_t c) {
  digitalWrite(PIN_RS, LOW); busWrite(c); wrStrobe(); digitalWrite(PIN_RS, HIGH);
}
void writeData(uint8_t d) { busWrite(d); wrStrobe(); }
uint8_t readByte() {
  digitalWrite(PIN_RD, LOW);  delayMicroseconds(2);
  uint8_t v = busRead();
  digitalWrite(PIN_RD, HIGH); delayMicroseconds(2);
  return v;
}

void lcdPinsToIdle() {
  pinMode(PIN_RD, OUTPUT);  digitalWrite(PIN_RD, HIGH);
  pinMode(PIN_WR, OUTPUT);  digitalWrite(PIN_WR, HIGH);
  pinMode(PIN_RS, OUTPUT);  digitalWrite(PIN_RS, HIGH);
  pinMode(PIN_CS, OUTPUT);  digitalWrite(PIN_CS, HIGH);
  pinMode(PIN_RST, OUTPUT); digitalWrite(PIN_RST, HIGH);
  busMode(OUTPUT); busWrite(0);
}

// Read n bytes back from register `reg` (modern MIPI style: 0x04, 0xD3, 0xBF)
void readRegN(uint8_t reg, uint8_t n, uint8_t *out) {
  digitalWrite(PIN_CS, LOW);
  writeCmd(reg);
  busMode(INPUT);
  for (uint8_t i = 0; i < n; i++) out[i] = readByte();
  busMode(OUTPUT);
  digitalWrite(PIN_CS, HIGH);
}

// Old-style 16-bit register read (ILI9325-era chips): index then 2 data bytes
uint16_t readReg16(uint16_t reg) {
  digitalWrite(PIN_CS, LOW);
  digitalWrite(PIN_RS, LOW);
  busWrite(reg >> 8);   wrStrobe();
  busWrite(reg & 0xFF); wrStrobe();
  digitalWrite(PIN_RS, HIGH);
  busMode(INPUT);
  uint16_t v = (uint16_t)readByte() << 8;
  v |= readByte();
  busMode(OUTPUT);
  digitalWrite(PIN_CS, HIGH);
  return v;
}

void printReg(const char *name, uint8_t reg, uint8_t n) {
  uint8_t buf[8];
  readRegN(reg, n, buf);
  Serial.printf("  reg 0x%02X (%s): ", reg, name);
  for (uint8_t i = 0; i < n; i++) Serial.printf("%02X ", buf[i]);
  // the useful ID is usually the LAST TWO bytes joined, first byte is a dummy
  uint16_t id = ((uint16_t)buf[n - 2] << 8) | buf[n - 1];
  switch (id) {
    case 0x9486: Serial.print("  <-- ILI9486, the usual chip on these ✓"); break;
    case 0x9488: Serial.print("  <-- ILI9488"); break;
    case 0x7796: Serial.print("  <-- ST7796S"); break;
    case 0x9341: Serial.print("  <-- ILI9341 (that would mean a smaller panel!)"); break;
    case 0x8357: Serial.print("  <-- HX8357"); break;
    case 0x1581: Serial.print("  <-- R61581"); break;
  }
  Serial.println();
}

// -------------------------------------------------------------- touch probe --
// The two touch plates are just resistors (~200-900 ohm) strapped across two
// of our 13 lines each. Internal pullup on one line + drive another LOW: if
// the pullup line reads LOW, they are joined through a plate. LCD inputs are
// high-impedance, so only real plates connect pairs.
bool pairConnected(uint8_t a, uint8_t b) {
  pinMode(a, INPUT_PULLUP);
  pinMode(b, OUTPUT); digitalWrite(b, LOW);
  delayMicroseconds(100);
  bool joined = (digitalRead(a) == LOW);
  pinMode(a, INPUT); pinMode(b, INPUT);
  return joined;
}

uint8_t planeA[2], planeB[2];   // the two discovered plates
bool touchFound = false;

void findTouchPlanes() {
  Serial.println("\n--- TOUCH PROBE (screen may show garbage now -- normal) ---");
  uint8_t found = 0;
  for (uint8_t i = 0; i < 13 && found < 2; i++) {
    for (uint8_t j = i + 1; j < 13 && found < 2; j++) {
      uint8_t a = ALL_PINS[i], b = ALL_PINS[j];
      if (pairConnected(a, b) && pairConnected(b, a)) {   // both directions = real
        Serial.printf("  plate found: GPIO %d <-> GPIO %d\n", a, b);
        if (found == 0) { planeA[0] = a; planeA[1] = b; }
        else            { planeB[0] = a; planeB[1] = b; }
        found++;
      }
    }
  }
  touchFound = (found == 2);
  if (!touchFound)
    Serial.println("  NO touch film found -- this shield is display-only "
                   "(or the film's 4 lines are not where expected). "
                   "Check the front for a thin 4-wire flex tail.");
  lcdPinsToIdle();
}

// pick an end of a plane that can analogRead, or 255 if neither can
uint8_t adcEnd(uint8_t *plane) {
  if (adcCapable(plane[0])) return plane[0];
  if (adcCapable(plane[1])) return plane[1];
  return 255;
}

// gradient across `drive` plane, finger carries the voltage to `sense` plane
int readAxis(uint8_t *drive, uint8_t *sense) {
  uint8_t s = adcEnd(sense);
  if (s == 255) return -1;
  pinMode(drive[0], OUTPUT); digitalWrite(drive[0], HIGH);
  pinMode(drive[1], OUTPUT); digitalWrite(drive[1], LOW);
  pinMode(sense[0], INPUT);  pinMode(sense[1], INPUT);
  delayMicroseconds(50);
  int v = analogRead(s);
  pinMode(drive[0], INPUT);  pinMode(drive[1], INPUT);
  return v;
}

// pressed = current can flow from one plane to the other through the finger
bool isPressed() {
  uint8_t sa = adcEnd(planeA);
  if (sa == 255) sa = adcEnd(planeB);
  if (sa == 255) return false;
  // ground all of plane B, pull the sense end of plane A up, press joins them
  uint8_t other = (sa == planeA[0] || sa == planeA[1]) ? 255 : 0;
  uint8_t *sensePlane = (other == 255) ? planeA : planeB;
  uint8_t *drivePlane = (other == 255) ? planeB : planeA;
  pinMode(drivePlane[0], OUTPUT); digitalWrite(drivePlane[0], LOW);
  pinMode(drivePlane[1], OUTPUT); digitalWrite(drivePlane[1], LOW);
  pinMode(sensePlane[0], INPUT_PULLUP);
  pinMode(sensePlane[1], INPUT_PULLUP);
  delayMicroseconds(100);
  bool pressed = (digitalRead(sensePlane[0]) == LOW);
  for (uint8_t k = 0; k < 2; k++) {
    pinMode(drivePlane[k], INPUT); pinMode(sensePlane[k], INPUT);
  }
  return pressed;
}

// ------------------------------------------------------------------- sketch --
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n>>> TftShieldID: who is this 3.5\" shield really?\n");

  lcdPinsToIdle();

  // hardware reset
  digitalWrite(PIN_RST, LOW);  delay(20);
  digitalWrite(PIN_RST, HIGH); delay(150);

  Serial.println("--- ID REGISTERS (send me these numbers) ---");
  printReg("RDDID",          0x04, 4);
  printReg("RDID4/chip id",  0xD3, 4);
  printReg("DDB / old Rens", 0xBF, 6);
  Serial.printf("  reg16 0x0000 (ILI9325-era id): %04X\n", readReg16(0x0000));

  // universal "are you alive": sleep-out, display on, ALL PIXELS ON.
  // No driver needed -- every MIPI-style chip understands these three.
  writeCmd(0x11); delay(150);   // sleep out
  writeCmd(0x29);               // display on
  writeCmd(0x23);               // all pixels on -> panel goes bright/whitish
  Serial.println("\n--- panel should now be LIT (whitish), not dark ---");

  findTouchPlanes();
  if (touchFound)
    Serial.println("Press the glass FIRMLY -- raw readings follow.\n");
}

void loop() {
  if (!touchFound) { delay(1000); return; }
  if (isPressed()) {
    int x = readAxis(planeA, planeB);   // which is X vs Y: calibration later
    int y = readAxis(planeB, planeA);
    Serial.printf("PRESSED  axis1=%4d  axis2=%4d\n", x, y);
    delay(60);
  } else {
    delay(20);
  }
}
