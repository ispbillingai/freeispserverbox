// Experimental one-ADC resistance measurement, not a product touch driver.
// Pins remain fitted as measured: plate A=16/33, plate B=17/21.
// Excite A+ while grounding both B ends. Measure A- with no load and with
// internal weak loads to test whether plate resistance is measurable above
// noise/contact drift. A pressure-dependent voltage alone is not position.
#include "Lcd.h"
#include "driver/rtc_io.h"

static int rowIndex = 0;
static bool consumed = false, released = false;
static uint32_t releasedAt = 0;

static void releaseBus() {
  pinMode(PIN_WR, OUTPUT); digitalWrite(PIN_WR, HIGH);
  pinMode(PIN_RD, OUTPUT); digitalWrite(PIN_RD, HIGH);
  for (int i = 0; i < 8; i++) pinMode(PIN_D[i], INPUT);
  pinMode(PIN_RS, INPUT); pinMode(PIN_CS, INPUT);
}
static void restoreBus() {
  pinMode(PIN_CS, OUTPUT); digitalWrite(PIN_CS, HIGH);
  tft.busOut(); tft.sel();
}
static bool contact() {
  releaseBus();
  pinMode(21, OUTPUT); digitalWrite(21, LOW);
  pinMode(17, OUTPUT); digitalWrite(17, LOW);
  pinMode(33, INPUT_PULLUP); delayMicroseconds(300);
  for (int i = 0; i < 3; i++) {
    if (digitalRead(33) != LOW) return false;
    delayMicroseconds(100);
  }
  return true;
}
static float readMv() {
  unsigned long sum = 0;
  for (int i = 0; i < 24; i++) sum += analogReadMilliVolts(33);
  return sum / 24.0f;
}
static bool loadMode(int mode) {
  esp_err_t a = rtc_gpio_pullup_dis(GPIO_NUM_33);
  esp_err_t b = rtc_gpio_pulldown_dis(GPIO_NUM_33);
  if (mode == 1) b = rtc_gpio_pulldown_en(GPIO_NUM_33);
  if (mode == 2) a = rtc_gpio_pullup_en(GPIO_NUM_33);
  delayMicroseconds(300);
  return a == ESP_OK && b == ESP_OK;
}
static void paint() {
  restoreBus(); tft.fillScreen(C_BG);
  for (int i = 0; i < 6; i++) {
    int top = i * 320 / 6, bottom = (i + 1) * 320 / 6;
    if (i == rowIndex) tft.fillRect(1, top + 1, 478, bottom - top - 2, C_OK);
    tft.setTextColor(i == rowIndex ? C_BG : C_TXT); tft.setTextSize(1);
    tft.setCursor(8, top + 5); tft.printf("ROW %d - resistance test", i + 1);
    if (i == rowIndex) tft.fillRect(230, (top + bottom) / 2 - 10, 20, 20, C_TXT);
  }
  Serial.printf("RES TARGET row=%d x=240\n", rowIndex + 1);
}

void setup() {
  Serial.begin(115200); tft.begin();
  Serial.println("ResistanceProof: experimental loads on ADC33; unchanged landscape wiring");
  // Check that RTC pulls remain effective after the ADC is initialized.
  releaseBus(); analogReadMilliVolts(33);
  bool ok = loadMode(1); float low = readMv();
  ok = loadMode(2) && ok; float high = readMv();
  loadMode(0);
  Serial.printf("RES PULL CHECK ok=%d low_mV=%.2f high_mV=%.2f\n", ok, low, high);
  paint();
}

void loop() {
  if (!contact()) {
    if (!released) { released = true; releasedAt = millis(); }
    if (consumed && millis() - releasedAt >= 30) {
      consumed = false;
      if (++rowIndex == 6) { Serial.println("RES RUN COMPLETE"); rowIndex = 0; }
      paint();
    }
  } else {
    released = false;
    if (!consumed) {
      releaseBus();
      pinMode(16, OUTPUT); digitalWrite(16, HIGH);
      pinMode(21, OUTPUT); digitalWrite(21, LOW);
      pinMode(17, OUTPUT); digitalWrite(17, LOW);
      analogReadMilliVolts(33);
      bool ok = loadMode(0); float u0 = readMv();
      ok = loadMode(1) && ok; float d = readMv();
      ok = loadMode(0) && ok; float u1 = readMv();
      ok = loadMode(2) && ok; float p = readMv();
      ok = loadMode(0) && ok; float u2 = readMv();
      if (contact()) {
        consumed = true;
        Serial.printf("RES SAMPLE row=%d ok=%d u0=%.2f down=%.2f u1=%.2f up=%.2f u2=%.2f\n",
                      rowIndex + 1, ok, u0, d, u1, p, u2);
      }
    }
  }
  delay(3);
}
