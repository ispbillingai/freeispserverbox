/*
  RawTest.ino - TFT OFF/SLEEP command diagnostic.

  This tests whether the display controller accepts commands at all.

  Important:
    LED/backlight is wired directly to 3V3, so code CANNOT turn the backlight off.
    If the panel accepts DISPOFF/SLEEP, you may see the white/grey glass change,
    dim, flash, or go darker, but the backlight will still glow.

  Current intended wiring:
    LED   -> 3V3
    SCK   -> GPIO 12
    SDA   -> GPIO 11
    A0/DC -> GPIO 5
    RESET -> GPIO 4
    CS    -> GPIO 10
    GND   -> GND
    VCC   -> 3V3
*/

uint8_t PIN_CS = 10;
uint8_t PIN_DC = 5;
uint8_t PIN_RST = 4;
uint8_t PIN_SCK = 12;
uint8_t PIN_MOSI = 11;

const uint16_t CLK_US = 20;

void tick() {
  digitalWrite(PIN_SCK, HIGH);
  delayMicroseconds(CLK_US);
  digitalWrite(PIN_SCK, LOW);
  delayMicroseconds(CLK_US);
}

void wr8(uint8_t b) {
  for (int i = 7; i >= 0; --i) {
    digitalWrite(PIN_MOSI, (b >> i) & 1);
    tick();
  }
}

void cmd(uint8_t c) {
  digitalWrite(PIN_DC, LOW);
  digitalWrite(PIN_CS, LOW);
  wr8(c);
  digitalWrite(PIN_CS, HIGH);
}

void dat(uint8_t d) {
  digitalWrite(PIN_DC, HIGH);
  digitalWrite(PIN_CS, LOW);
  wr8(d);
  digitalWrite(PIN_CS, HIGH);
}

void allCandidatePinsSafe() {
  const uint8_t pins[] = {4, 5, 10, 11, 12};
  for (uint8_t i = 0; i < sizeof(pins); ++i) {
    pinMode(pins[i], OUTPUT);
    digitalWrite(pins[i], HIGH);
  }
  digitalWrite(11, LOW);
  digitalWrite(12, LOW);
}

void resetPanel() {
  digitalWrite(PIN_CS, HIGH);
  digitalWrite(PIN_DC, HIGH);
  digitalWrite(PIN_SCK, LOW);
  digitalWrite(PIN_MOSI, LOW);

  digitalWrite(PIN_RST, HIGH);
  delay(80);
  digitalWrite(PIN_RST, LOW);
  delay(250);
  digitalWrite(PIN_RST, HIGH);
  delay(300);
}

void initMinimal() {
  cmd(0x01); delay(150); // SWRESET
  cmd(0x11); delay(255); // SLPOUT
  cmd(0x3A); dat(0x05);  // RGB565
  cmd(0x36); dat(0xC0);  // MADCTL
  cmd(0x20);             // INVOFF
  cmd(0x13); delay(20);  // NORON
  cmd(0x29); delay(120); // DISPON
}

void displayOffSleep() {
  cmd(0x28); delay(200); // DISPOFF
  cmd(0x10); delay(500); // SLPIN
}

void displayOnWake() {
  cmd(0x11); delay(255); // SLPOUT
  cmd(0x29); delay(200); // DISPON
}

void fillGreenSmall() {
  // Tiny write after wake, just in case color works on one mapping.
  cmd(0x2A); dat(0x00); dat(0x00); dat(0x00); dat(0x7F);
  cmd(0x2B); dat(0x00); dat(0x00); dat(0x00); dat(0x9F);
  cmd(0x2C);
  digitalWrite(PIN_DC, HIGH);
  digitalWrite(PIN_CS, LOW);
  for (uint32_t i = 0; i < 128UL * 160UL; ++i) {
    wr8(0x07); wr8(0xE0);
  }
  digitalWrite(PIN_CS, HIGH);
}

void tryOff(uint8_t sck, uint8_t mosi, uint8_t cs, uint8_t dc, uint8_t rst) {
  PIN_SCK = sck;
  PIN_MOSI = mosi;
  PIN_CS = cs;
  PIN_DC = dc;
  PIN_RST = rst;

  allCandidatePinsSafe();
  Serial.println();
  Serial.printf("OFF-TRY SCK=%u SDA/MOSI=%u CS=%u A0/DC=%u RESET=%u\n",
                PIN_SCK, PIN_MOSI, PIN_CS, PIN_DC, PIN_RST);
  Serial.println("Watch for ANY change: flash, dim, darker, black, or wake-up change.");

  resetPanel();
  initMinimal();
  Serial.println("Sending DISPOFF + SLEEP IN for 5 seconds...");
  displayOffSleep();
  delay(5000);

  Serial.println("Waking display and attempting GREEN for 3 seconds...");
  displayOnWake();
  fillGreenSmall();
  delay(3000);
}

void setup() {
  Serial.begin(115200);
  delay(800);
  Serial.println();
  Serial.println("FreeISP TFT OFF/SLEEP DIAGNOSTIC v4");
  Serial.println("Backlight LED is on 3V3, so code cannot switch the backlight off.");
}

void loop() {
  const uint8_t control[][3] = {
    {10, 5, 4},
    {10, 4, 5},
    {5, 10, 4},
    {5, 4, 10},
    {4, 10, 5},
    {4, 5, 10}
  };

  const uint8_t dataClock[][2] = {
    {12, 11},
    {11, 12}
  };

  for (uint8_t bus = 0; bus < 2; ++bus) {
    for (uint8_t c = 0; c < 6; ++c) {
      tryOff(dataClock[bus][0], dataClock[bus][1],
             control[c][0], control[c][1], control[c][2]);
    }
  }

  Serial.println();
  Serial.println("All OFF/SLEEP permutations tried. Repeating.");
  delay(3000);
}
