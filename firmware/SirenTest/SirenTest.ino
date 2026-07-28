/*
  SirenTest.ino — find the LOUDEST note this buzzer can make, then wail.

  Why this exists: a passive piezo buzzer has a RESONANT frequency. At
  that exact pitch the disc flexes furthest and it is far louder - the
  same 3.3V, several times the noise. Every buzzer's peak is different,
  so we sweep and let your EARS find it. No meter needed.

  ------------------------------------------------------------------
  WIRING (same as BuzzTest)
  ------------------------------------------------------------------
     buzzer VCC (or +)  ->  3V3      <-- try 5V too, see LOUDER below
     buzzer GND (or -)  ->  GND
     buzzer I/O (or S)  ->  GPIO 27

  !! Breadboard rails are SPLIT in the middle - keep both taps on the
  !! same half, GND on the blue rail only.
  ------------------------------------------------------------------

  HOW TO USE IT
  1. Upload, open Serial Monitor @115200, and LISTEN.
  2. PART 1 walks up the scale, announcing every frequency as it plays
     it. One of them will jump out as clearly louder and more piercing
     than its neighbours. THAT is resonance.
  3. Note that number and tell me - it becomes the siren's real pitch.
  4. PART 2 then wails using the presets below so you can hear what the
     finished alarm will sound like.

  LOUDER STILL (try in this order)
  - Move buzzer VCC from 3V3 to 5V. More volts = more swing = louder.
    Safe for these modules; the signal pin stays 3.3V either way.
  - Get it OUT of the breadboard when judging - a piezo sitting in
    plastic is muffled. In the real box it wants a hole in front of it.
  - Do NOT cover the little vent hole on top of the buzzer.
*/

#define PIN_BUZZ 27

// PART 2 presets — I will set these to your real peak once you tell me
// which frequency in PART 1 was loudest.
uint16_t WAIL_LO = 2000;
uint16_t WAIL_HI = 3100;

// PART 1 sweep range
const uint16_t SWEEP_FROM = 1000;
const uint16_t SWEEP_TO   = 5000;
const uint16_t SWEEP_STEP = 250;
const uint16_t HOLD_MS    = 700;   // long enough to judge each note

void quiet() {
  noTone(PIN_BUZZ);
  pinMode(PIN_BUZZ, OUTPUT);
  digitalWrite(PIN_BUZZ, LOW);
}

void banner(const char* what) {
  Serial.println();
  Serial.println("======================================");
  Serial.printf (" %s\n", what);
  Serial.println("======================================");
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("======================================");
  Serial.println(" SirenTest - find the loudest note");
  Serial.printf (" buzzer on GPIO %d\n", PIN_BUZZ);
  Serial.println(" LISTEN for the note that jumps out");
  Serial.println("======================================");
  pinMode(PIN_BUZZ, OUTPUT);
  quiet();
}

void loop() {
  // ---------- PART 1: which note is loudest? ----------
  banner("PART 1 - sweeping up. Which one is LOUDEST?");
  for (uint16_t f = SWEEP_FROM; f <= SWEEP_TO; f += SWEEP_STEP) {
    Serial.printf("   %5u Hz %s\n", f,
                  (f >= 2500 && f <= 4500) ? "  <- peak usually lives here" : "");
    tone(PIN_BUZZ, f);
    delay(HOLD_MS);
    quiet();
    delay(120);            // gap so each note is judged on its own
  }

  Serial.println();
  Serial.println("   ...that is the whole range. Remember the loudest number.");
  delay(2000);

  // ---------- PART 2: what the real alarm will sound like ----------
  banner("PART 2 - wail demo (two-tone yelp)");
  Serial.printf("   alternating %u Hz / %u Hz\n", WAIL_LO, WAIL_HI);
  for (int i = 0; i < 6; i++) {
    tone(PIN_BUZZ, WAIL_LO);  delay(300);
    tone(PIN_BUZZ, WAIL_HI);  delay(300);
  }
  quiet();
  delay(600);

  banner("PART 2b - rising sweep siren (the classic)");
  for (int r = 0; r < 3; r++) {
    for (uint16_t f = WAIL_LO; f <= WAIL_HI; f += 40) {
      tone(PIN_BUZZ, f);
      delay(8);
    }
  }
  quiet();

  banner("...5s of peace, then it all runs again");
  delay(5000);
}
