/* ESP32 shield connection scan. No finger on the glass during 's'.
 * Inspired by MCUFRIEND_kbv/examples/diagnose_Touchpins, but uses digital
 * weak-pull tests in both polarities and both directions, not AVR ADC cutoffs.
 * This identifies conductive paths, not resistance in ohms or axis names.
 * Only one candidate pin is a strong output at a time. RD/WR/RST stay HIGH.
 * CS is included: both read/write strobes stay inactive throughout scan.
 * Serial 115200: s = scan. Does not auto-run, draw, use WiFi, or alter NVS.
 */
#include <Arduino.h>

static const uint8_t pins[] = {16, 17, 18, 19, 2, 22, 23, 5, 33, 21};
static const char *names[] = {"D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "RS", "CS"};
static const int count = sizeof(pins) / sizeof(pins[0]);
static const uint8_t rd = 12, wr = 14, rst = 4;

static void releaseBus() {
  for (int i = 0; i < count; ++i) pinMode(pins[i], INPUT);
}

static void controlsHigh() {
  // No candidate GPIO drives against another candidate output.
  pinMode(rd, OUTPUT); digitalWrite(rd, HIGH);
  pinMode(wr, OUTPUT); digitalWrite(wr, HIGH);
  pinMode(rst, OUTPUT); digitalWrite(rst, HIGH);
}

static int highCount(uint8_t pin) {
  int n = 0;
  for (int k = 0; k < 8; ++k) {
    n += digitalRead(pin) == HIGH;
    delay(1);
  }
  return n;
}

static void scan() {
  Serial.println("SCAN BEGIN -- NO TOUCH; counts are HIGH samples out of 8");
  Serial.println("baseline: isolated weak UP should be 8, weak DOWN should be 0");
  for (int sense = 0; sense < count; ++sense) {
    releaseBus();
    pinMode(pins[sense], INPUT_PULLUP); delay(5);
    int up = highCount(pins[sense]);
    pinMode(pins[sense], INPUT_PULLDOWN); delay(5);
    int down = highCount(pins[sense]);
    Serial.printf("BASE %s GPIO%d up=%d down=%d\n", names[sense], pins[sense], up, down);
  }
  for (int sense = 0; sense < count; ++sense) {
    for (int drive = 0; drive < count; ++drive) {
      if (sense == drive) continue;
      releaseBus();
      pinMode(pins[sense], INPUT_PULLUP);
      pinMode(pins[drive], OUTPUT); digitalWrite(pins[drive], LOW);
      delay(5);
      int low = highCount(pins[sense]);
      // Release the source before reversing bias.
      pinMode(pins[drive], INPUT);
      pinMode(pins[sense], INPUT_PULLDOWN);
      pinMode(pins[drive], OUTPUT); digitalWrite(pins[drive], HIGH);
      delay(5);
      int high = highCount(pins[sense]);
      Serial.printf("PAIR sense=%s/%d drive=%s/%d low=%d high=%d%s\n",
                    names[sense], pins[sense], names[drive], pins[drive],
                    low, high, low == 0 && high == 8 ? " FOLLOWS" : "");
    }
  }
  releaseBus();
  Serial.println("SCAN END -- send s to repeat; reciprocal FOLLOWS pairs need circuit/axis verification");
}

void setup() {
  Serial.begin(115200);
  controlsHigh();
  releaseBus();
  Serial.println("PinTrace ready. Leave glass untouched; send s for connection scan.");
}

void loop() {
  if (Serial.available() && Serial.read() == 's') scan();
  delay(10);
}
