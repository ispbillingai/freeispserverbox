/*
  CardTest.ino — prove the RC522 reader and collect your card numbers.

  Every RFID card has a permanent unique number burned into it (the UID).
  The box will only obey cards whose UID we have put on its list, so the
  first job is simply to READ your cards and write those numbers down.

  Tap each card and each keyfob you own. This prints a line you can paste
  straight into the firmware. Cards NOT on the list will be ignored by the
  real box, which is the whole point.

  No screen, no WiFi. Buzzer optional (it chirps when a card is read).

  ------------------------------------------------------------------
  WIRING  (classic ESP32 WROOM, COM6, hold BOOT to upload)
  ------------------------------------------------------------------
     RC522            ESP32
      3.3V   ->   3V3      <-- !! 3.3V ONLY. 5V KILLS THIS BOARD !!
      GND    ->   GND
      SCK    ->   GPIO 18   (same wire the screen uses - they share)
      MOSI   ->   GPIO 23   (shared with the screen too)
      MISO   ->   GPIO 19   (the screen does not use this one)
      SDA    ->   GPIO 16   (this is really "chip select")
      RST    ->   GPIO 17
      IRQ    ->   leave empty

  Why 16 and 17: GPIO 13/14 work fine electrically, but they sit next to
  GPIO 12 - and GPIO 12 held HIGH at boot tells the ESP32 its flash runs
  at 1.8V, which stops the flash answering and gives an endless
  "invalid header: 0xffffffff" boot loop. One jumper in the wrong row is
  all it takes. 16 and 17 are nowhere near it, so that mistake cannot
  happen. (16/17 are free on WROOM-32 boards like this one. They are NOT
  free on WROVER boards, where PSRAM uses them.)

  The RC522 shares the SPI bus with the TFT. That is normal and fine -
  each device has its own SDA/CS line so only one listens at a time.

  Buzzer, if still wired:  I/O -> GPIO 27,  VCC -> 5V,  GND -> GND

  !! The RC522 usually ships with its header UNSOLDERED, like the screen
  !! did. Solder it before testing, or you will chase ghosts again.
  ------------------------------------------------------------------

  WHAT YOU SHOULD SEE ON BOOT (Serial @115200):

     OK RC522 firmware version 0x92 (v2.0) - reader is alive

  If it says 0x00 or 0xFF the reader is NOT talking: check 3.3V, the
  MISO wire, and the solder joints. Those two values mean "no answer",
  not "broken chip".
*/

#include <SPI.h>
#include <MFRC522.h>

#define PIN_SS    16
#define PIN_RST   17
#define PIN_BUZZ  27      // optional, comment out the chirps if not wired

MFRC522 rfid(PIN_SS, PIN_RST);

int cardsSeen = 0;
String lastUid = "";
uint32_t lastAt = 0;

void chirp(uint16_t hz, uint16_t ms) {
  tone(PIN_BUZZ, hz);
  delay(ms);
  noTone(PIN_BUZZ);
  pinMode(PIN_BUZZ, OUTPUT);
  digitalWrite(PIN_BUZZ, LOW);
}

// turn the raw UID bytes into a readable string like "A4 3F 19 7C"
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

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("==========================================");
  Serial.println(" CardTest - read your RFID cards");
  Serial.println(" tap each card/keyfob you want to use");
  Serial.println("==========================================");

  pinMode(PIN_BUZZ, OUTPUT);
  digitalWrite(PIN_BUZZ, LOW);

  SPI.begin();            // SCK 18, MISO 19, MOSI 23 by default on ESP32
  rfid.PCD_Init();
  delay(50);

  byte v = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  if (v == 0x00 || v == 0xFF) {
    Serial.println();
    Serial.println("!! RC522 NOT ANSWERING (version reads 0x00/0xFF)");
    Serial.println("   That means no reply, not a dead chip. Check:");
    Serial.println("   - 3.3V, NOT 5V (5V destroys this board)");
    Serial.println("   - MISO on GPIO 19, MOSI on 23, SCK on 18");
    Serial.println("   - SDA on 16, RST on 17");
    Serial.println("   - header pins actually SOLDERED, not pushed in");
    Serial.println();
  } else {
    Serial.printf("OK RC522 firmware version 0x%02X (%s) - reader is alive\n",
                  v, (v == 0x91 || v == 0x92) ? "v1.0/v2.0 genuine-style"
                                              : "clone, usually fine");
    chirp(2000, 80);
  }

  Serial.println();
  Serial.println("Hold a card flat on the reader...");
  Serial.println();
}

void loop() {
  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial())   return;

  String uid = uidToString(&rfid.uid);
  uint32_t now = millis();

  // the reader re-reads a card left sitting on it - do not spam
  if (uid == lastUid && now - lastAt < 2000) {
    rfid.PICC_HaltA();
    return;
  }
  lastUid = uid;
  lastAt = now;
  cardsSeen++;

  MFRC522::PICC_Type type = rfid.PICC_GetType(rfid.uid.sak);

  Serial.println("------------------------------------------");
  Serial.printf ("  CARD %d\n", cardsSeen);
  Serial.printf ("  UID  : %s   (%d bytes)\n", uid.c_str(), rfid.uid.size);
  Serial.printf ("  type : %s\n", rfid.PICC_GetTypeName(type));
  Serial.println();
  Serial.println("  To let this card into the box, add this line:");
  Serial.printf ("     \"%s\",\n", uid.c_str());
  Serial.println("------------------------------------------");
  Serial.println();

  chirp(4250, 60);
  delay(40);
  chirp(4250, 60);

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}
