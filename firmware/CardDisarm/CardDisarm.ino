/*
  CardDisarm.ino — reed + RC522 + buzzer, with cards stored IN THE BOX.

  THE TEST:
     take the magnet away   -> it rings, continuously
     tap a registered card  -> it shuts up for a while
     quiet expires, lid still off -> it rings again
     tap a stranger's card  -> nothing. It keeps ringing.

  ------------------------------------------------------------------
  WHY THE CARDS ARE NOT IN THE CODE ANY MORE
  ------------------------------------------------------------------
  These boxes are sold overseas and each one ships with its OWN 2 cards.
  So customer A's card must never open customer B's box - which rules out
  a shared list baked into the firmware. But compiling a different
  firmware per box is worse: it does not scale past a handful.

  So the cards live in the ESP32's own flash (NVS), not in the program:

     ONE firmware flashes EVERY box. No per-box build. No config file.
     Each box LEARNS its 2 cards once, and remembers them forever -
     through power cuts, reboots and firmware updates.

  ENROLMENT (do this before the box ships):
     A box with no cards stored boots into ENROL mode and says so. Tap
     the 2 cards going in the customer's envelope. It stores them, beeps
     to confirm each, and arms itself. That is the whole setup.

  IF A CUSTOMER LOSES BOTH CARDS:
     Send 'r' here on the bench, or the cards=clear command in the real
     firmware, and the box forgets its cards and re-enters ENROL mode so
     replacements can be paired. The alarm can also always be silenced
     remotely from the server, so nobody is ever locked out for good.

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

  SERIAL KEYS (bench only): 'r' = forget all cards,  'l' = list them
*/

#include <SPI.h>
#include <MFRC522.h>
#include <Preferences.h>

// ---- pins ----
#define PIN_SS    16
#define PIN_RST   17
#define PIN_REED  32
#define PIN_BUZZ  27

// ---- behaviour ----
const uint8_t  CARDS_PER_BOX = 2;      // how many ship with each box
const uint8_t  MAX_CARDS     = 4;      // room for replacements later
const uint32_t QUIET_MS      = 30000;  // BENCH 30s. REAL BOX 3600000 = 1 hour
const uint32_t DEBOUNCE_MS   = 60;
const uint32_t SWAP_MS       = 300;    // how fast the two siren notes alternate
const uint16_t TONE_A_HZ     = 2000;
const uint16_t TONE_B_HZ     = 4250;   // this buzzer's loudest note
#define REED_CLOSED_LEVEL LOW          // magnet near = LOW = lid ON

MFRC522     rfid(PIN_SS, PIN_RST);
Preferences store;                     // the ESP32's own permanent memory

String   cards[MAX_CARDS];
uint8_t  cardCount = 0;

bool     lidOff      = false;
int      lastRaw     = -1, stableRaw = -1;
uint32_t changedAt   = 0;
uint32_t quietUntil  = 0;
uint32_t swapAt      = 0;
bool     sirenAlt    = false;
bool     ringing     = false;
String   lastUid     = "";
uint32_t lastCardAt  = 0;

// ================= sound =================
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

// ================= stored cards =================
// NVS keys are "card0", "card1"... plus "n" for how many.
void loadCards() {
  store.begin("freeisp", true);              // read-only
  cardCount = store.getUChar("n", 0);
  if (cardCount > MAX_CARDS) cardCount = 0;  // corrupt -> start clean
  for (uint8_t i = 0; i < cardCount; i++)
    cards[i] = store.getString(("card" + String(i)).c_str(), "");
  store.end();
}

void saveCard(const String& uid) {
  if (cardCount >= MAX_CARDS) return;
  cards[cardCount] = uid;
  store.begin("freeisp", false);             // writable
  store.putString(("card" + String(cardCount)).c_str(), uid);
  cardCount++;
  store.putUChar("n", cardCount);
  store.end();
}

void forgetCards() {
  store.begin("freeisp", false);
  store.clear();
  store.end();
  cardCount = 0;
  Serial.println();
  Serial.println("**  ALL CARDS FORGOTTEN - box is back in ENROL mode  **");
  Serial.printf ("**  tap %d card(s) to pair this box                   **\n",
                 CARDS_PER_BOX);
  Serial.println();
}

void listCards() {
  Serial.printf("   %d card(s) registered to this box:\n", cardCount);
  for (uint8_t i = 0; i < cardCount; i++)
    Serial.printf("     %d: %s\n", i + 1, cards[i].c_str());
  if (cardCount == 0) Serial.println("     (none - ENROL mode)");
}

bool knownCard(const String& uid) {
  for (uint8_t i = 0; i < cardCount; i++)
    if (uid == cards[i]) return true;
  return false;
}

bool enrolling() { return cardCount < CARDS_PER_BOX; }

// ================= reader =================
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

bool inQuietPeriod() {
  return quietUntil != 0 && (int32_t)(millis() - quietUntil) < 0;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("==========================================");
  Serial.println(" CardDisarm - cards stored IN THE BOX");
  Serial.printf ("  quiet period = %lu seconds\n", (unsigned long)(QUIET_MS / 1000));
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
    // clones often boot with the receiver turned right down: SPI works
    // perfectly while the radio is too weak to wake a card
    rfid.PCD_SetAntennaGain(rfid.RxGain_max);
    rfid.PCD_AntennaOff();
    delay(20);
    rfid.PCD_AntennaOn();
    Serial.println("   antenna gain set to MAX");
  }

  loadCards();
  listCards();
  if (enrolling()) {
    Serial.println();
    Serial.println("******************************************");
    Serial.printf ("  ENROL MODE - tap the %d cards that ship\n", CARDS_PER_BOX);
    Serial.println("  with THIS box. They are remembered for good.");
    Serial.println("******************************************");
  }
  Serial.println("   ('r' = forget all cards, 'l' = list them)");

  lastRaw = stableRaw = digitalRead(PIN_REED);
  changedAt = millis();
  lidOff = (stableRaw != REED_CLOSED_LEVEL);
  Serial.println();
  Serial.printf("start: lid is %s\n", lidOff ? "OFF" : "ON");
  // an unenrolled box must not scream at the person setting it up
  if (lidOff && !enrolling()) {
    Serial.println("!! LID OFF - RINGING. Tap a card.");
    ringOn();
  }
}

void loop() {
  uint32_t now = millis();

  // ---------- bench keys ----------
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'r' || c == 'R') { quiet(); quietUntil = 0; forgetCards(); }
    if (c == 'l' || c == 'L') listCards();
  }

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
        if (enrolling()) {
          Serial.println(">> LID OFF - but this box has no cards yet (ENROL)");
        } else if (inQuietPeriod()) {
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
  if (quietUntil && !inQuietPeriod()) {
    quietUntil = 0;
    if (lidOff) {
      Serial.println("!! QUIET PERIOD OVER, lid still off - RINGING AGAIN");
      ringOn();
    } else {
      Serial.println("   quiet period over, box re-armed");
    }
  }

  // ---------- keep the siren going, unbroken ----------
  if (ringing && now - swapAt >= SWAP_MS) {
    swapAt = now;
    sirenAlt = !sirenAlt;
    tone(PIN_BUZZ, sirenAlt ? TONE_A_HZ : TONE_B_HZ);
  }

  // ---------- reader field watchdog (only speaks up if wrong) ----------
  static uint32_t lastPoke = 0;
  if (now - lastPoke >= 5000) {
    lastPoke = now;
    byte tx = rfid.PCD_ReadRegister(MFRC522::TxControlReg);
    if ((tx & 0x03) == 0) {              // bits 0-1 = the antenna drivers
      rfid.PCD_AntennaOn();
      rfid.PCD_SetAntennaGain(rfid.RxGain_max);
      Serial.println("   [reader] RF field had dropped - turned back on");
    }
  }

  // ---------- the card reader ----------
  if (!rfid.PICC_IsNewCardPresent()) return;

  // A card the reader can start talking to but cannot finish reading
  // leaves the RC522 stuck mid-conversation - after which it ignores
  // EVERY card, including the right one, until a reboot. So always close
  // the conversation, and reset the reader if it keeps failing.
  static uint8_t failCount = 0;
  if (!rfid.PICC_ReadCardSerial()) {
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    if (++failCount >= 3) {
      failCount = 0;
      rfid.PCD_Init();
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

  if (enrolling()) {
    if (knownCard(uid)) {
      Serial.printf("  %s is already paired to this box\n", uid.c_str());
    } else {
      saveCard(uid);
      Serial.printf("  PAIRED card %d of %d: %s\n", cardCount, CARDS_PER_BOX,
                    uid.c_str());
      chirp(TONE_B_HZ, 90);
      if (!enrolling()) {
        Serial.println("  >> BOX IS NOW PAIRED AND ARMED. Ship it.");
        delay(120);
        chirp(TONE_A_HZ, 90); delay(60); chirp(TONE_B_HZ, 200);
      }
    }
  } else if (knownCard(uid)) {
    quiet();                              // silence FIRST, then talk
    quietUntil = now + QUIET_MS;
    if (quietUntil == 0) quietUntil = 1;   // never land on "off"
    Serial.printf ("  ACCEPTED %s - quiet for %lu seconds\n", uid.c_str(),
                   (unsigned long)(QUIET_MS / 1000));
    chirp(TONE_B_HZ, 70); delay(60); chirp(TONE_B_HZ, 70);
  } else {
    Serial.printf ("  REJECTED %s - not this box's card. Alarm continues.\n",
                   uid.c_str());
    // deliberately no reassuring beep for a stranger's card
  }

  Serial.println("------------------------------------------");
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}
