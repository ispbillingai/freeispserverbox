// Measured pairs: D0/GPIO16 <-> RS/GPIO33, D1/GPIO17 <-> CS/GPIO21.
// GPIO33 is the only ADC-capable electrode. Establish the physical axis
// it measures before applying this map to a six-row product UI.
#include "Lcd.h"

static const uint8_t sensePin = 33, senseOther = 16;
static const uint8_t drivePlus = 21, driveMinus = 17;
static const char *targetName[] = {"TOP", "CENTRE", "BOTTOM", "LEFT", "RIGHT"};
static const int targetX[] = {240, 240, 240, 30, 450};
static const int targetY[] = {26, 160, 294, 160, 160};
static int target = 0;
static bool latched = false;
static uint32_t releasedAt = 0;
static bool released = false;
static int values[5];

static void releaseTouchBus() {
  // Keep both strobes inactive BEFORE changing CS, which is an electrode.
  pinMode(PIN_WR, OUTPUT); digitalWrite(PIN_WR, HIGH);
  pinMode(PIN_RD, OUTPUT); digitalWrite(PIN_RD, HIGH);
  for (int i = 0; i < 8; ++i) pinMode(PIN_D[i], INPUT);
  pinMode(PIN_RS, INPUT);
  pinMode(PIN_CS, INPUT);
}

static void restoreDisplay() {
  // Deselect first. Restore all modes, including CS (absent in old busOut).
  pinMode(PIN_CS, OUTPUT); digitalWrite(PIN_CS, HIGH);
  tft.busOut();
  pinMode(PIN_RD, OUTPUT); digitalWrite(PIN_RD, HIGH);
  tft.sel();
}

static bool contact() {
  releaseTouchBus();
  pinMode(drivePlus, OUTPUT); digitalWrite(drivePlus, LOW);
  pinMode(driveMinus, OUTPUT); digitalWrite(driveMinus, LOW);
  pinMode(sensePin, INPUT_PULLUP);
  delayMicroseconds(300);
  int n = 0;
  for (int i = 0; i < 3; ++i) {
    n += digitalRead(sensePin) == LOW;
    delayMicroseconds(100);
  }
  return n == 3;
}

static int position(int *lo, int *hi) {
  releaseTouchBus();
  pinMode(drivePlus, OUTPUT); digitalWrite(drivePlus, HIGH);
  pinMode(driveMinus, OUTPUT); digitalWrite(driveMinus, LOW);
  delayMicroseconds(300);
  // One fixed excitation for this burst; no LCD restoration between samples.
  analogRead(sensePin);
  int a[5];
  for (int i = 0; i < 5; ++i) {
    a[i] = analogRead(sensePin);
    delayMicroseconds(150);
  }
  for (int i = 1; i < 5; ++i)
    for (int j = i; j > 0 && a[j] < a[j - 1]; --j) {
      int v = a[j]; a[j] = a[j - 1]; a[j - 1] = v;
    }
  *lo = a[0]; *hi = a[4];
  return a[2];
}

static void paintTarget() {
  restoreDisplay();
  tft.fillScreen(C_BG);
  tft.setTextSize(2); tft.setTextColor(C_TXT);
  tft.setCursor(105, 75); tft.print("AXIS CHECK: "); tft.print(targetName[target]);
  tft.setCursor(90, 220); tft.print("Tap the green square once");
  tft.fillRect(targetX[target] - 12, targetY[target] - 12, 24, 24, C_OK);
  Serial.printf("TARGET %d %s x=%d y=%d\n", target + 1, targetName[target], targetX[target], targetY[target]);
}

void setup() {
  Serial.begin(115200);
  tft.begin();
  Serial.println("AxisProof: corrected pairs 16/33 and 17/21; ADC33 senses plate driven by 21/17");
  paintTarget();
}

void loop() {
  bool down = contact();
  if (!down) {
    if (!released) { released = true; releasedAt = millis(); }
    if (latched && millis() - releasedAt >= 30) {
      latched = false;
      if (++target >= 5) {
        Serial.printf("AXIS RESULT top=%d centre=%d bottom=%d left=%d right=%d verticalSpan=%d horizontalSpan=%d\n",
                      values[0], values[1], values[2], values[3], values[4],
                      abs(values[0] - values[2]), abs(values[3] - values[4]));
        target = 0;
      }
      paintTarget();
    }
  } else {
    released = false;
    if (!latched) {
      int lo, hi;
      int v = position(&lo, &hi);
      if (contact()) {
        values[target] = v;
        latched = true;
        Serial.printf("SAMPLE %s median=%d min=%d max=%d\n", targetName[target], v, lo, hi);
      }
    }
  }
  delay(3);
}
