/*
  CardDisarm.ino — reed + RC522 + buzzer. The real anti-theft moment.

  THE TEST:
     take the magnet away   -> it rings, continuously
     tap a card             -> it shuts up
     wait for the quiet to expire, lid still off -> it rings again

  That last part matters: the card does not switch the alarm off forever,
  it buys a QUIET PERIOD. A technician gets time to work, and the box
  re-arms itself afterwards with nobody having to remember to do it.

  On the bench the quiet period is 30 SECONDS so you can watch it expire.
  In the real box it is ONE HOUR (your rule). One constant, changed below.

  No MPU, no screen, no WiFi. Every card tap is logged with its UID, so
  this doubles as the tool that collects your card numbers.

  ------------------------------------------------------------------
  WIRING
  ------------------------------------------------------------------
    RC522                    ESP32
      3.3V  ->  3V3     !! 3.3V ONLY - 5V DESTROYS THIS BOARD !!
      GND   ->  GND
      SDA   ->  GPIO 16       (chip select)
      SCK   ->  GPIO 18
      MOSI  ->  GPIO 23
      MISO  ->  GPIO 19
      RST   ->  GPIO 17
      IRQ   ->  leave empty

    REED      one leg -> GPIO 32,  other leg -> GND   (no resistor)
    BUZZER    I/O -> GPIO 27,  VCC -> 5V,  GND -> GND

    Nothing on GPIO 12. Ever.
  ------------------------------------------------------------------

  WHITELIST: with ACCEPT_ANY_CARD 1 (the bench default) ANY card works,
  so you can test before we know your numbers. Tap all your cards, send
  me the UIDs it prints, and we switch it to 0 - then only YOUR cards
  work and a thief's card does nothing.
*/

#include <SPI.h>
#include <MFRC522.h>

// ---- pins ----
#define PIN_SS    16
#define PIN_RST   17
#define PIN_REED  32
#define PIN_BUZZ  27

// ---- behaviour ----
// 0 = ONLY the cards in ALLOWED[] below can silence the alarm. This is the
//     real behaviour, and it is on now that we know your card's number.
// 1 = bench mode, any card works (used before we knew any UIDs).
#define ACCEPT_ANY_CARD 0

const uint32_t QUIET_MS = 30000;   // BENCH: 30s. REAL BOX: 3600000 = 1 hour
const uint32_t DEBOUNCE_MS = 60;
const uint32_t SWAP_MS  = 300;     // how fast the two siren notes alternate
const uint16_t TONE_A_HZ = 2000;
const uint16_t TONE_B_HZ = 4250;   // this buzzer's loudest note
#define REED_CLOSED_LEVEL LOW      // magnet near = LOW = lid ON

// Your cards. Format exactly as the tap log prints them.
// Add every card/keyfob you want to work, then set ACCEPT_ANY_CARD to 0.
const char* ALLOWED[] = {
  "67 91 8F 63",        // first card read on the bench, 2026-07-29
};
const int ALLOWED_COUNT = sizeof(ALLOWED) / sizeof(ALLOWED[0]);

MFRC522 rfid(PIN_SS, PIN_RST);

bool     lidOff      = false;
int      lastRaw     = -1, stableRaw = -1;
uint32_t changedAt   = 0;
uint32_t quietUntil  = 0;      // no sound at all until this time
uint32_t swapAt      = 0;
bool     sirenAlt    = false;
bool     ringing     = false;
String   lastUid     = "";
uint32_t lastCardAt  = 0;

void quiet() {
  noTone(PIN_BUZZ);
  pinMode(PIN_BUZZ, OUTPUT);
  digitalWrite(PIN_BUZZ, LOW);
  ringing = false;
}

void ringOn() {
  sirenAlt = !sirenAlt;
  tone(PIN_BUZZ, sirenAlt ? TONE_A_HZ : TONE_B_HZ);
  swapAt = millis();
  ringing = true;
}

void chirp(uint16_t hz, uint16_t ms) {
  tone(PIN_BUZZ, hz);
  delay(ms);
  noTone(PIN_BUZZ);
  pinMode(PIN_BUZZ, OUTPUT);
  digitalWrite(PIN_BUZZ, LOW);
}

String uidToString(MFRC522::Uid* uid) {
  String s = "";
  for (byte i = 0; i < uid->size; i++) {
    if (uid->uidByte[i] < 0x10) s += "0";
    s += String(uid->uidByte[i], HEX);
    if (i + 1 < uid->size) s += " ";
  }
  s.toUpperCase();
  return s;
}

bool cardAllowed(const String& uid) {
#if ACCEPT_ANY_CARD
  return true;
#else
  for (int i = 0; i < ALLOWED_COUNT; i++)
    if (uid == ALLOWED[i]) return true;
  return false;
#endif
}

bool inQuietPeriod() {
  return quietUntil != 0 && (int32_t)(millis() - quietUntil) < 0;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("==========================================");
  Serial.println(" CardDisarm - reed + card + buzzer");
  Serial.println(" lid off = ring.  tap card = quiet.");
  Serial.printf ("  quiet period = %lu seconds\n", (unsigned long)(QUIET_MS / 1000));
#if ACCEPT_ANY_CARD
  Serial.println(" ANY card is accepted (bench mode)");
#else
  Serial.printf ("  %d card(s) on the list\n", ALLOWED_COUNT);
#endif
  Serial.println("==========================================");

  pinMode(PIN_BUZZ, OUTPUT);
  quiet();
  pinMode(PIN_REED, INPUT_PULLUP);

  SPI.begin();
  rfid.PCD_Init();
  delay(50);
  byte v = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  if (v == 0x00 || v == 0xFF) {
    Serial.println("!! RC522 NOT ANSWERING - check 3.3V (not 5V), MISO 19,");
    Serial.println("   SDA 16, RST 17, and that the header is SOLDERED.");
  } else {
    Serial.printf("OK RC522 alive, version 0x%02X\n", v);
    // Clone RC522s often come up with the receiver gain turned right down,
    // so the chip talks to us perfectly over SPI but its radio field is too
    // weak to wake a card. Wind it up to maximum and kick the antenna.
    rfid.PCD_SetAntennaGain(rfid.RxGain_max);
    rfid.PCD_AntennaOff();
    delay(20);
    rfid.PCD_AntennaOn();
    Serial.println("   antenna gain set to MAX");
  }

  lastRaw = stableRaw = digitalRead(PIN_REED);
  changedAt = millis();
  lidOff = (stableRaw != REED_CLOSED_LEVEL);
  Serial.printf("start: lid is %s\n", lidOff ? "OFF" : "ON");
  Serial.println();
  if (lidOff) { Serial.println("!! LID OFF - RINGING. Tap a card."); ringOn(); }
}

void loop() {
  uint32_t now = millis();

  // ---------- the reed ----------
  int raw = digitalRead(PIN_REED);
  if (raw != lastRaw) {
    lastRaw = raw;
    changedAt = now;
  } else if (now - changedAt > DEBOUNCE_MS && raw != stableRaw) {
    stableRaw = raw;
    bool nowOff = (raw != REED_CLOSED_LEVEL);
    if (nowOff != lidOff) {
      lidOff = nowOff;
      if (lidOff) {
        if (inQuietPeriod()) {
          Serial.println(">> LID OFF - but a card bought quiet, staying silent");
        } else {
          Serial.println("!! LID OFF - RINGING. Tap a card to stop it.");
          ringOn();
        }
      } else {
        Serial.println("OK LID BACK ON - quiet, box secure");
        quiet();
        quietUntil = 0;            // lid shut ends the quiet period early
      }
    }
  }

  // ---------- the quiet period running out ----------
  static bool warned = false;
  if (quietUntil && !inQuietPeriod()) {
    quietUntil = 0;
    warned = false;
    if (lidOff) {
      Serial.println("!! QUIET PERIOD OVER, lid still off - RINGING AGAIN");
      ringOn();
    } else {
      Serial.println("   quiet period over, box re-armed");
    }
  } else if (inQuietPeriod() && !warned) {
    uint32_t left = (quietUntil - now) / 1000;
    if (left <= 5) {
      warned = true;
      Serial.println("   ...quiet ends in 5s");
    }
  }

  // ---------- keep the siren going, unbroken ----------
  if (ringing && now - swapAt >= SWAP_MS) {
    swapAt = now;
    sirenAlt = !sirenAlt;
    tone(PIN_BUZZ, sirenAlt ? TONE_A_HZ : TONE_B_HZ);
  }

  // ---------- reader watchdog ----------
  // Prove it is actually polling, and re-assert the field. Some clones let
  // the antenna drift off after a while and then silently see nothing.
  // Now that reading is proven, this only SPEAKS UP when something is
  // wrong - a chatty log hides the lines that matter.
  static uint32_t lastPoke = 0;
  if (now - lastPoke >= 5000) {
    lastPoke = now;
    byte tx = rfid.PCD_ReadRegister(MFRC522::TxControlReg);
    if ((tx & 0x03) == 0) {               // bits 0-1 = the two antenna drivers
      rfid.PCD_AntennaOn();
      rfid.PCD_SetAntennaGain(rfid.RxGain_max);
      Serial.println("   [reader] RF field had dropped - turned back on");
    }
  }

  // ---------- the card reader ----------
  if (!rfid.PICC_IsNewCardPresent()) return;

  // A card the reader can start talking to but cannot finish reading (a
  // different card family, or one snatched away mid-read) leaves the RC522
  // stuck in the middle of a conversation. If we just gave up here it would
  // then ignore EVERY card - including the right one - until a reboot.
  // So: always close the conversation, and re-initialise if it keeps failing.
  static uint8_t failCount = 0;
  if (!rfid.PICC_ReadCardSerial()) {
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    if (++failCount >= 3) {
      failCount = 0;
      rfid.PCD_Init();                          // full reset of the reader
      rfid.PCD_SetAntennaGain(rfid.RxGain_max);
      rfid.PCD_AntennaOn();
      Serial.println("   [reader] a card confused it - reader reset, ready again");
    }
    return;
  }
  failCount = 0;

  String uid = uidToString(&rfid.uid);
  if (uid == lastUid && now - lastCardAt < 1500) {   // card left sitting on it
    rfid.PICC_HaltA();
    return;
  }
  lastUid = uid;
  lastCardAt = now;

  Serial.println("------------------------------------------");
  Serial.printf ("  CARD TAPPED: %s\n", uid.c_str());
  Serial.printf ("  add to the list as:   \"%s\",\n", uid.c_str());

  if (cardAllowed(uid)) {
    quiet();                              // silence FIRST, then talk
    quietUntil = now + QUIET_MS;
    if (quietUntil == 0) quietUntil = 1;   // never land on "off"
    Serial.printf ("  ACCEPTED - quiet for %lu seconds\n",
                   (unsigned long)(QUIET_MS / 1000));
    Serial.println("------------------------------------------");
    chirp(TONE_B_HZ, 70); delay(60); chirp(TONE_B_HZ, 70);   // two happy beeps
  } else {
    Serial.println("  REJECTED - not on the list. Alarm continues.");
    Serial.println("------------------------------------------");
    // deliberately no reassuring beep for a stranger's card
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}
