/*
  ReedTest.ino — prove the door sensor, and work out which kind it is.

  Reed switches come both ways round: most close their contacts when the
  magnet comes near (normally-open), but some open them instead. Get it
  backwards and the box thinks the door is hanging open while it is shut.
  Rather than guess, this WATCHES the pin and you tell it once which
  state is "door closed". It then prints the exact config line to use.

  Buzzer + MPU can stay wired, they are ignored here. No screen, no WiFi.

  ------------------------------------------------------------------
  WIRING
  ------------------------------------------------------------------
  BARE GLASS REED (two wires, no PCB) - the usual kind:
      one leg -> GPIO 32
      other leg -> GND
      No resistor. The ESP32's internal pull-up does the work.

  3-PIN REED MODULE (small PCB with an LED on it):
      VCC -> 3V3      GND -> GND      DO (or OUT) -> GPIO 32

  NO REED YET? A plain jumper wire works as a fake door:
      wire in = door CLOSED, pull it out = door OPEN.

  BUZZER (optional, for feedback without a screen):
      I/O -> GPIO 27,  VCC -> 5V,  GND -> GND
  ------------------------------------------------------------------

  HOW TO USE IT
  1. Upload, open Serial Monitor @115200.
  2. It prints the live pin state as you move the magnet. Watch it flip.
  3. Hold the magnet where it will sit when the DOOR IS SHUT, then type
     'c' + Enter. That is the calibration - it now knows which way round
     your sensor is, and prints the line for the real firmware.
  4. After that it behaves like the real door alarm: take the magnet away
     and you get a short grace chirp, then the wail.

  NOTE: the grace here is 3s so you are not stood waiting on the bench.
  The real firmware uses 15s (GRACE_MS in LiveDashboardNext).
*/

#define PIN_REED  32
#define PIN_BUZZ  27

const uint32_t DEBOUNCE_MS  = 60;
const uint32_t TEST_GRACE_MS = 3000;    // real firmware uses 15000
const uint32_t BEEP_MS      = 300;
const uint16_t TONE_A_HZ    = 2000;
const uint16_t TONE_B_HZ    = 4250;
const uint16_t TONE_CHIRP   = 2000;
const uint32_t CHIRP_ON_MS  = 40;
const uint32_t CHIRP_GAP_MS = 1200;

int      closedLevel = -1;      // -1 = not calibrated yet
int      lastRaw     = -1;
int      stableRaw   = -1;
uint32_t changedAt   = 0;
bool     doorOpen    = false;
bool     seenLow = false, seenHigh = false;

uint32_t openedAt = 0, beepAt = 0;
bool     beepOn = false, sirenAlt = false;
bool     wailing = false;

void quiet() {
  noTone(PIN_BUZZ);
  pinMode(PIN_BUZZ, OUTPUT);
  digitalWrite(PIN_BUZZ, LOW);
  beepOn = false;
}

void chirp(uint16_t hz, uint16_t ms) {
  tone(PIN_BUZZ, hz);
  delay(ms);
  quiet();
}

void showCalibration() {
  Serial.println();
  Serial.println("**********************************************");
  Serial.printf ("  CALIBRATED: door CLOSED = pin reads %s\n",
                 closedLevel == LOW ? "LOW" : "HIGH");
  Serial.println();
  Serial.println("  Put this in LiveDashboardNext.ino:");
  Serial.printf ("     #define REED_CLOSED_LEVEL  %s\n",
                 closedLevel == LOW ? "LOW" : "HIGH");
  if (closedLevel == LOW)
    Serial.println("  (that is already the default - nothing to change)");
  else
    Serial.println("  (the default is LOW, so this one DOES need changing)");
  Serial.println("**********************************************");
  Serial.println();
  Serial.println("Now take the magnet away to trigger the alarm.");
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("==========================================");
  Serial.println(" ReedTest - which way round is your reed?");
  Serial.printf ("  reed on GPIO %d, buzzer on GPIO %d\n", PIN_REED, PIN_BUZZ);
  Serial.println("==========================================");
  Serial.println();
  Serial.println("Move the magnet near/away and watch the pin flip.");
  Serial.println("Then hold it where the SHUT DOOR would hold it");
  Serial.println("and type 'c' + Enter to calibrate.");
  Serial.println();

  pinMode(PIN_BUZZ, OUTPUT);
  quiet();
  pinMode(PIN_REED, INPUT_PULLUP);

  lastRaw = stableRaw = digitalRead(PIN_REED);
  changedAt = millis();
  Serial.printf("start: pin reads %s\n", stableRaw == LOW ? "LOW" : "HIGH");
}

void loop() {
  uint32_t now = millis();

  // ---- calibrate on demand ----
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'c' || c == 'C') {
      closedLevel = stableRaw;
      doorOpen = false;
      wailing = false;
      quiet();
      showCalibration();
      chirp(TONE_B_HZ, 120);
    }
  }

  // ---- debounce the pin ----
  int raw = digitalRead(PIN_REED);
  if (raw != lastRaw) {
    lastRaw = raw;
    changedAt = now;
  } else if (now - changedAt > DEBOUNCE_MS && raw != stableRaw) {
    stableRaw = raw;
    if (raw == LOW) seenLow = true; else seenHigh = true;

    Serial.printf("[%6lus] pin -> %s\n", now / 1000, raw == LOW ? "LOW " : "HIGH");

    if (closedLevel < 0) {
      // still exploring - just chirp so he knows it registered
      chirp(TONE_A_HZ, 60);
      if (seenLow && seenHigh)
        Serial.println("         good - it moves both ways. Hold the magnet"
                       " as if the door were SHUT, then type 'c'.");
    } else {
      bool nowOpen = (raw != closedLevel);
      if (nowOpen != doorOpen) {
        doorOpen = nowOpen;
        if (doorOpen) {
          openedAt = now; beepAt = now; wailing = false;
          Serial.println("   !! DOOR OPEN - grace chirp, then the wail");
        } else {
          wailing = false;
          quiet();
          Serial.println("   OK DOOR CLOSED - quiet, box secure");
        }
      }
    }
  }

  if (closedLevel < 0 || !doorOpen) return;

  // ---- grace, then wail: same shape as the real alarm ----
  if (!wailing && now - openedAt >= TEST_GRACE_MS) {
    wailing = true;
    beepAt = now;
    Serial.println("   !! GRACE OVER - FULL SIREN");
  }

  if (!wailing) {                      // polite tick
    if (beepOn  && now - beepAt >= CHIRP_ON_MS)  { beepAt = now; quiet(); }
    if (!beepOn && now - beepAt >= CHIRP_GAP_MS) {
      beepAt = now; tone(PIN_BUZZ, TONE_CHIRP); beepOn = true;
    }
  } else {                             // two-note wail
    if (now - beepAt >= BEEP_MS) {
      beepAt = now;
      beepOn = !beepOn;
      if (beepOn) {
        sirenAlt = !sirenAlt;
        tone(PIN_BUZZ, sirenAlt ? TONE_A_HZ : TONE_B_HZ);
      } else {
        noTone(PIN_BUZZ);
      }
    }
  }
}
