// Experimental one-ADC test; GPIO drive settings are not precision resistors.
// Correct pairs remain 16/33 and 17/21. Alternate GPIO16 sink strength while
// measuring GPIO33; both 21/17 endpoints source HIGH. Keep landscape/wires.
#include "Lcd.h"
#include "driver/gpio.h"

static int target = 0;
static bool consumed = false, released = false;
static uint32_t releaseAt = 0;
static float lastStrong[6], lastWeak[6], lastRatio[6];

static void releaseBus() {
  pinMode(PIN_WR, OUTPUT); digitalWrite(PIN_WR, HIGH);
  pinMode(PIN_RD, OUTPUT); digitalWrite(PIN_RD, HIGH);
  for (int i = 0; i < 8; ++i) pinMode(PIN_D[i], INPUT);
  pinMode(PIN_RS, INPUT); pinMode(PIN_CS, INPUT);
}
static bool contact() {
  releaseBus();
  pinMode(21, OUTPUT); digitalWrite(21, LOW);
  pinMode(17, OUTPUT); digitalWrite(17, LOW);
  pinMode(33, INPUT_PULLUP); delayMicroseconds(300);
  for (int i = 0; i < 3; ++i) {
    if (digitalRead(33) != LOW) return false;
    delayMicroseconds(100);
  }
  return true;
}
static void paint() {
  pinMode(PIN_CS, OUTPUT); digitalWrite(PIN_CS, HIGH);
  tft.busOut(); tft.sel(); tft.fillScreen(C_BG);
  for (int i = 0; i < 6; ++i) {
    int top = i * 320 / 6, bottom = (i + 1) * 320 / 6;
    if (i == target) tft.fillRect(1, top + 1, 478, bottom - top - 2, C_OK);
    tft.setTextColor(i == target ? C_BG : C_TXT); tft.setTextSize(1);
    tft.setCursor(8, top + 5); tft.printf("ROW %d - drive test", i + 1);
    if (i == target) tft.fillRect(230, (top + bottom) / 2 - 10, 20, 20, C_TXT);
  }
  Serial.printf("DRV TARGET row=%d x=240\n", target + 1);
}
static float measure(gpio_drive_cap_t strength, bool *ok, bool *clipped = nullptr) {
  *ok = (gpio_set_drive_capability(GPIO_NUM_16, strength) == ESP_OK) && *ok;
  delayMicroseconds(300);
  unsigned long sum = 0;
  for (int i = 0; i < 8; ++i) {
    int raw = analogRead(33);
    if (clipped && (raw <= 5 || raw >= 4090)) *clipped = true;
    sum += analogReadMilliVolts(33);
  }
  return sum / 8.0f;
}
void setup() {
  Serial.begin(115200); tft.begin();
  Serial.println("DriveProof: experimental sink-strength measurement, not a calibrated position");
  paint();
}
void loop() {
  if (Serial.available() && Serial.read() == 'p') {
    for (int i = 0; i < 6; ++i)
      Serial.printf("DRV STORED row=%d strong=%.3f weak=%.3f ratio=%.5f\n", i + 1, lastStrong[i], lastWeak[i], lastRatio[i]);
  }
  if (!contact()) {
    if (!released) { released = true; releaseAt = millis(); }
    if (consumed && millis() - releaseAt >= 30) {
      consumed = false;
      if (++target == 6) {
        Serial.println("DRV RUN COMPLETE");
        for (int i = 0; i < 6; ++i)
          Serial.printf("DRV STORED row=%d strong=%.3f weak=%.3f ratio=%.5f\n", i + 1, lastStrong[i], lastWeak[i], lastRatio[i]);
        target = 0;
      }
      paint();
    }
  } else {
    released = false;
    if (!consumed) {
      releaseBus();
      pinMode(21, OUTPUT); digitalWrite(21, HIGH);
      pinMode(17, OUTPUT); digitalWrite(17, HIGH);
      pinMode(16, OUTPUT); digitalWrite(16, LOW);
      gpio_drive_cap_t oldStrength;
      bool ok = gpio_get_drive_capability(GPIO_NUM_16, &oldStrength) == ESP_OK;
      if (!ok) oldStrength = GPIO_DRIVE_CAP_2;
      analogReadMilliVolts(33);
      // This sketch owns the sole ADC channel. The global API also rebuilds
      // the millivolt calibration handle in Arduino-ESP32 3.3.10; the per-pin
      // API changes hardware attenuation without recalibrating that handle.
      analogSetAttenuation(ADC_11db);
      float pilot = measure(GPIO_DRIVE_CAP_0, &ok);
      adc_attenuation_t attenuation = pilot < 850 ? ADC_0db : pilot < 1150 ? ADC_2_5db : pilot < 1600 ? ADC_6db : ADC_11db;
      analogSetAttenuation(attenuation);
      float s[5], w[4], q[4];
      bool clipped = false;
      // Use a milder sink so the low end stays above the ADC dead zone.
      // Bracket each weak sample with strong samples to track contact drift.
      s[0] = measure(GPIO_DRIVE_CAP_1, &ok, &clipped);
      for (int i = 0; i < 4; ++i) {
        w[i] = measure(GPIO_DRIVE_CAP_0, &ok, &clipped);
        s[i + 1] = measure(GPIO_DRIVE_CAP_1, &ok, &clipped);
        float centre = (s[i] + s[i + 1]) * 0.5f;
        q[i] = centre > 0 && w[i] < 3250 ? w[i] * (3300 - centre) / (centre * (3300 - w[i])) : 0;
      }
      gpio_set_drive_capability(GPIO_NUM_16, oldStrength);
      if (contact()) {
        consumed = true;
        float sm = 0, wm = 0;
        for (int i = 0; i < 5; ++i) sm += s[i];
        for (int i = 0; i < 4; ++i) wm += w[i];
        lastStrong[target] = sm / 5; lastWeak[target] = wm / 4;
        Serial.printf("DRV SAMPLE row=%d ok=%d clipped=%d atten=%d s=%.2f,%.2f,%.2f,%.2f,%.2f w=%.2f,%.2f,%.2f,%.2f q=%.5f,%.5f,%.5f,%.5f\n",
                      target + 1, ok, clipped, attenuation, s[0], s[1], s[2], s[3], s[4], w[0], w[1], w[2], w[3], q[0], q[1], q[2], q[3]);
        for (int i = 1; i < 4; ++i)
          for (int j = i; j > 0 && q[j] < q[j - 1]; --j) { float v = q[j]; q[j] = q[j - 1]; q[j - 1] = v; }
        lastRatio[target] = clipped || !ok ? -1 : (q[1] + q[2]) * 0.5f;
      }
    }
  }
  delay(3);
}
