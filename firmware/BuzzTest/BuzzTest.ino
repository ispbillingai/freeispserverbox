/*
  BuzzTest.ino — "just make it buzz". Nothing else.

  No screen, no WiFi, no reed switch. If this stays silent, the problem
  is the wiring or the module — nothing else can be blamed.

  ------------------------------------------------------------------
  WIRING  (board = classic ESP32 WROOM on COM6, hold BOOT to upload)
  ------------------------------------------------------------------
     buzzer VCC (or +)  ->  3V3
     buzzer GND (or -)  ->  GND
     buzzer I/O (or S)  ->  GPIO 27

  !! BREADBOARD WARNING: the power rails are SPLIT in the middle.
  !! Keep both taps on the SAME half of the rail, and GND on the blue
  !! rail only - never the red one.
  ------------------------------------------------------------------

  WHAT IT DOES: there are three kinds of buzzer module and they need
  three different signals, so this tries each one for 3 seconds in a
  loop and prints which test is running. Watch Serial @115200 and note
  WHICH TEST makes the noise - that tells us exactly what you have:

    TEST A sounds -> active buzzer, normal.  BUZZER_ACTIVE_HIGH 1
    TEST B sounds -> active buzzer, inverted. BUZZER_ACTIVE_HIGH 0
    TEST C sounds -> PASSIVE buzzer (needs a tone, not a level).
                     Tell me - the alarm code needs a small change.
    nothing sounds -> wiring, or the module is dead. See the checklist.
*/

#define PIN_BUZZ 27      // same pin the real alarm uses

void banner(const char* what) {
  Serial.println();
  Serial.println("--------------------------------------");
  Serial.printf(" %s\n", what);
  Serial.println("--------------------------------------");
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("======================================");
  Serial.println(" BuzzTest - which buzzer do you have?");
  Serial.printf (" buzzer signal pin = GPIO %d\n", PIN_BUZZ);
  Serial.println(" listen, and note WHICH test beeps");
  Serial.println("======================================");

  pinMode(PIN_BUZZ, OUTPUT);
  digitalWrite(PIN_BUZZ, LOW);
}

void loop() {
  // ---- TEST A: plain HIGH. The common active buzzer module. ----
  banner("TEST A  - driving the pin HIGH  (active-high)");
  for (int i = 0; i < 5; i++) {
    digitalWrite(PIN_BUZZ, HIGH);  delay(200);
    digitalWrite(PIN_BUZZ, LOW);   delay(300);
  }
  digitalWrite(PIN_BUZZ, LOW);
  delay(1200);

  // ---- TEST B: plain LOW. Some 3-pin modules sound when pulled low. ----
  banner("TEST B  - driving the pin LOW   (active-low)");
  digitalWrite(PIN_BUZZ, HIGH);          // idle high for this one
  for (int i = 0; i < 5; i++) {
    digitalWrite(PIN_BUZZ, LOW);   delay(200);
    digitalWrite(PIN_BUZZ, HIGH);  delay(300);
  }
  digitalWrite(PIN_BUZZ, LOW);
  delay(1200);

  // ---- TEST C: a real tone. A PASSIVE buzzer only works this way. ----
  banner("TEST C  - feeding a 2kHz tone   (passive buzzer)");
  for (int i = 0; i < 3; i++) {
    tone(PIN_BUZZ, 2000);  delay(300);
    noTone(PIN_BUZZ);      delay(300);
  }
  // a little up-down sweep, unmistakable if it is a passive one
  for (int f = 800; f <= 3000; f += 100) { tone(PIN_BUZZ, f); delay(15); }
  for (int f = 3000; f >= 800; f -= 100) { tone(PIN_BUZZ, f); delay(15); }
  noTone(PIN_BUZZ);
  digitalWrite(PIN_BUZZ, LOW);

  banner("...silence for 3s, then round again");
  delay(3000);
}
