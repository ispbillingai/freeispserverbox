/*
  BenchAlarm.ino — STEP 1 of the real FreeISP box build.

  This is DemoDashboard + the first REAL hardware behavior:
    - REED SWITCH  = the door sensor  (open door -> ALARM)
    - RED LED      = alarm / door open
    - GREEN LED    = secure / door closed
    - BUZZER       = beeps while the door is open
    - SCREEN       = a red ALARM banner takes over any page while open

  When the door closes again everything returns to normal and the
  dashboard pages keep rotating. All of it is logged on Serial @115200.

  ------------------------------------------------------------------
  WIRING  (board = classic ESP32 WROOM on COM6, hold BOOT to upload)
  ------------------------------------------------------------------
  SCREEN (unchanged, exactly like DemoDashboard / FriendTest):
    GND->GND, VCC->5V, BLK->3V3
    SCL->18, SDA->23, CS->5, DC->2, RST->4

  NEW PARTS:
    RED LED    long leg -> GPIO 25, short leg -> 220 ohm resistor -> GND
    GREEN LED  long leg -> GPIO 26, short leg -> 220 ohm resistor -> GND
    BUZZER     (+) -> GPIO 27, (-) -> GND        (small kit buzzer only!)
    REED SWITCH  one leg -> GPIO 32, other leg -> GND
                 (no resistor needed - we use the ESP32 internal pullup)

    No reed switch on the bench yet? Use a plain jumper wire from
    GPIO 32 to GND: wire connected = door CLOSED, pull it out = OPEN.

  !! BREADBOARD WARNING: the power rails are SPLIT in the middle.
  !! Keep every GND tap on the SAME half of the blue rail (or bridge
  !! the gap), and never put a GND wire on the red rail.
  ------------------------------------------------------------------
*/
#define SCREEN_TAB  INITR_GREENTAB   // match whatever worked in DemoDashboard
#define SCREEN_ROT  1

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>

// ---- pins ----
#define TFT_CS    5
#define TFT_DC    2
#define TFT_RST   4
#define PIN_LED_R 25
#define PIN_LED_G 26
#define PIN_BUZZ  27
#define PIN_REED  32   // INPUT_PULLUP: LOW = magnet near / wire in = door CLOSED

Adafruit_ST7735 tft(TFT_CS, TFT_DC, TFT_RST);

// ---- colors (RGB565) ----
#define C_BG      ST77XX_BLACK
#define C_BAR     0x0339
#define C_TITLE   ST77XX_WHITE
#define C_LABEL   0x8C71
#define C_VALUE   ST77XX_WHITE
#define C_GOOD    0x07E8
#define C_BAD     0xF965
#define C_ACCENT  0x07FF
#define C_WARN    0xFFE0

const uint32_t PAGE_MS     = 5000;
const uint32_t UPDATE_MS   = 250;
const uint32_t DEBOUNCE_MS = 60;     // reed switch settle time
const uint32_t BEEP_MS     = 300;    // buzzer on/off rhythm during alarm

uint8_t  page = 0;
uint32_t lastPage = 0, lastUpdate = 0;
bool     heartbeat = false;

// ---- door / alarm state ----
bool     doorOpen      = false;      // debounced, true = OPEN
bool     alarmDrawn    = false;      // is the red banner currently on screen
int      lastReedRaw   = -1;
uint32_t reedChangedAt = 0;
uint32_t beepAt        = 0;
bool     beepOn        = false;
uint32_t openCount     = 0;          // how many times the door was opened

// ---- fake data (same as DemoDashboard, until real sources arrive) ----
int   usersOnline = 12;
float dlMbps = 18.4, ulMbps = 3.2;
int   battery = 78;
float tempC = 26.5, humid = 58.0;
bool  portUp[5] = { true, true, false, true, false };

void fakeDataStep() {
  usersOnline = constrain(usersOnline + random(-1, 2), 5, 40);
  dlMbps = constrain(dlMbps + random(-15, 16) / 10.0, 0.3, 95.0);
  ulMbps = constrain(ulMbps + random(-5, 6) / 10.0, 0.1, 20.0);
  if (random(0, 40) == 0) battery = constrain(battery + random(-2, 2), 20, 100);
  tempC = constrain(tempC + random(-2, 3) / 10.0, 18.0, 38.0);
  humid = constrain(humid + random(-3, 4) / 10.0, 30.0, 90.0);
  if (random(0, 60) == 0) portUp[random(0, 5)] ^= 1;
}

// ---- small helpers ----
void titleBar(const char* t) {
  tft.fillScreen(C_BG);
  tft.fillRect(0, 0, tft.width(), 16, C_BAR);
  tft.setTextSize(1);
  tft.setTextColor(C_TITLE, C_BAR);
  tft.setCursor(4, 4);
  tft.print("FreeISP");
  tft.setTextColor(C_ACCENT, C_BAR);
  tft.setCursor(70, 4);
  tft.print(t);
}

void label(int x, int y, const char* s) {
  tft.setTextSize(1);
  tft.setTextColor(C_LABEL, C_BG);
  tft.setCursor(x, y);
  tft.print(s);
}

void value(int x, int y, uint8_t size, uint16_t color, const String& s, int boxW) {
  tft.fillRect(x, y, boxW, size * 8, C_BG);
  tft.setTextSize(size);
  tft.setTextColor(color, C_BG);
  tft.setCursor(x, y);
  tft.print(s);
}

String clockStr() {
  uint32_t s = 8UL * 3600 + millis() / 1000;
  char b[9];
  snprintf(b, sizeof(b), "%02lu:%02lu:%02lu", (s / 3600) % 24, (s / 60) % 60, s % 60);
  return String(b);
}

String upStr() {
  uint32_t s = millis() / 1000;
  char b[12];
  snprintf(b, sizeof(b), "%lud %02lu:%02lu", s / 86400, (s / 3600) % 24, (s / 60) % 60);
  return String(b);
}

// ---- dashboard pages ----
void drawStatic() {
  switch (page) {
    case 0:
      titleBar("HOME");
      label(10, 26, "USERS ONLINE");
      label(10, 70, "WIFI");
      label(80, 70, "DOOR");
      tft.setTextSize(1);
      tft.setTextColor(C_GOOD, C_BG);
      tft.setCursor(10, 82);  tft.print("CONNECTED");
      label(10, 110, "freeisp.net  *paka box*");
      break;
    case 1:
      titleBar("PORTS");
      for (int i = 0; i < 5; i++) {
        label(14, 24 + i * 20, ("ether" + String(i + 1)).c_str());
      }
      break;
    case 2:
      titleBar("SYSTEM");
      label(10, 26, "TIME");
      label(10, 62, "UPTIME");
      label(10, 92, "BATTERY");
      tft.drawRect(10, 104, 104, 14, C_LABEL);
      tft.fillRect(114, 107, 4, 8, C_LABEL);
      break;
    case 3:
      titleBar("SECURITY");
      label(10, 26, "DOOR");
      label(10, 62, "TIMES OPENED");
      label(10, 98, "SIREN");
      break;
  }
}

void drawLive() {
  heartbeat = !heartbeat;
  tft.fillCircle(tft.width() - 8, 8, 3, heartbeat ? C_GOOD : C_BAR);

  switch (page) {
    case 0:
      value(10, 38, 3, C_ACCENT, String(usersOnline), 60);
      value(80, 82, 1, doorOpen ? C_BAD : C_GOOD, doorOpen ? "OPEN" : "CLOSED", 45);
      break;
    case 1:
      for (int i = 0; i < 5; i++) {
        int y = 24 + i * 20;
        tft.fillCircle(7, y + 3, 3, portUp[i] ? C_GOOD : C_BAD);
        if (portUp[i]) {
          float m = (i == 0) ? dlMbps : ulMbps / (i + 1) + i;
          value(66, y, 1, C_VALUE, String(m, 1) + " Mbps", 70);
        } else {
          value(66, y, 1, C_BAD, "down", 70);
        }
      }
      break;
    case 2: {
      value(10, 38, 2, C_VALUE, clockStr(), 110);
      value(10, 74, 1, C_VALUE, upStr(), 90);
      int w = battery;
      uint16_t bc = battery > 50 ? C_GOOD : (battery > 25 ? C_WARN : C_BAD);
      tft.fillRect(12, 106, w, 10, bc);
      tft.fillRect(12 + w, 106, 100 - w, 10, C_BG);
      value(78, 92, 1, bc, String(battery) + "%", 30);
      break;
    }
    case 3:
      value(10, 38, 2, doorOpen ? C_BAD : C_GOOD, doorOpen ? "OPEN" : "CLOSED", 90);
      value(10, 74, 2, C_VALUE, String(openCount), 60);
      value(10, 110, 1, doorOpen ? C_BAD : C_LABEL, doorOpen ? "SOUNDING" : "quiet", 70);
      break;
  }
}

// ---- alarm screen takeover ----
void drawAlarmBanner() {
  tft.fillScreen(C_BAD);
  tft.setTextSize(3);
  tft.setTextColor(ST77XX_WHITE, C_BAD);
  tft.setCursor(18, 40);
  tft.print("ALARM");
  tft.setTextSize(1);
  tft.setCursor(28, 80);
  tft.print("DOOR IS OPEN");
}

void onDoorChange(bool open) {
  doorOpen = open;
  digitalWrite(PIN_LED_R, open ? HIGH : LOW);
  digitalWrite(PIN_LED_G, open ? LOW : HIGH);

  if (open) {
    openCount++;
    beepOn = true;  beepAt = millis();
    digitalWrite(PIN_BUZZ, HIGH);
    drawAlarmBanner();
    alarmDrawn = true;
    Serial.printf("[%lus] !! [ALARM] door OPEN (count=%lu) - siren ON\n",
                  millis() / 1000, openCount);
  } else {
    beepOn = false;
    digitalWrite(PIN_BUZZ, LOW);
    drawStatic();                    // restore the dashboard
    alarmDrawn = false;
    Serial.printf("[%lus] OK [ALARM] door CLOSED - siren OFF, box secure\n",
                  millis() / 1000);
  }
}

// read + debounce the reed switch; report a change only when stable
void pollDoor() {
  int raw = digitalRead(PIN_REED);         // LOW = closed, HIGH = open
  if (raw != lastReedRaw) {
    lastReedRaw = raw;
    reedChangedAt = millis();
  } else if ((millis() - reedChangedAt) > DEBOUNCE_MS) {
    bool open = (raw == HIGH);
    if (open != doorOpen) onDoorChange(open);
  }
}

// beep-beep-beep rhythm while the alarm is active
void pollBuzzer() {
  if (!doorOpen) return;
  if (millis() - beepAt >= BEEP_MS) {
    beepAt = millis();
    beepOn = !beepOn;
    digitalWrite(PIN_BUZZ, beepOn ? HIGH : LOW);
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println("=====================================");
  Serial.println(" BenchAlarm v1 - FreeISP box, step 1");
  Serial.println(" screen + reed + LEDs + buzzer");
  Serial.println("=====================================");

  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_BUZZ,  OUTPUT);
  pinMode(PIN_REED,  INPUT_PULLUP);
  digitalWrite(PIN_BUZZ, LOW);

  // power-on self test: both LEDs + one short chirp so you KNOW they work
  digitalWrite(PIN_LED_R, HIGH);
  digitalWrite(PIN_LED_G, HIGH);
  digitalWrite(PIN_BUZZ, HIGH);  delay(120);  digitalWrite(PIN_BUZZ, LOW);
  delay(600);
  digitalWrite(PIN_LED_R, LOW);
  digitalWrite(PIN_LED_G, LOW);

  int raw = digitalRead(PIN_REED);
  Serial.printf("[BOOT] reed raw = %d  (%s)\n", raw,
                raw == LOW ? "LOW = door CLOSED" : "HIGH = door OPEN");

  tft.initR(SCREEN_TAB);
  tft.setRotation(SCREEN_ROT);
  drawStatic();

  // set LEDs to the real starting state
  doorOpen = (raw == HIGH);
  digitalWrite(PIN_LED_R, doorOpen ? HIGH : LOW);
  digitalWrite(PIN_LED_G, doorOpen ? LOW : HIGH);
  if (doorOpen) { drawAlarmBanner(); alarmDrawn = true; }
  lastReedRaw = raw;
  reedChangedAt = millis();
}

void loop() {
  pollDoor();
  pollBuzzer();

  if (doorOpen) return;   // alarm banner owns the screen while open

  uint32_t now = millis();
  if (now - lastPage >= PAGE_MS) {
    lastPage = now;
    page = (page + 1) % 4;
    drawStatic();
  }
  if (now - lastUpdate >= UPDATE_MS) {
    lastUpdate = now;
    fakeDataStep();
    drawLive();
  }
}
