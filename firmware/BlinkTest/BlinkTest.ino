/*  BlinkTest.ino  --  PURE board test, NO screen, NO libraries.
 *
 *  Purpose: after a full flash erase, prove the ESP32-S3 boots and runs
 *  OUR code (not a boot loop). It touches NOTHING but Serial.
 *
 *  Expected in Serial Monitor @ 115200:
 *      >>> FreeISP board test booting...
 *      tick 1
 *      tick 2
 *      tick 3   ... counting up forever, ~1 per second
 *
 *  If you see the counting -> the board + toolchain are 100% good, and the
 *  earlier boot loop was caused by the SCREEN init (library/wiring), not the
 *  board. We then tackle the screen on its own.
 */

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println(">>> FreeISP board test booting...");
  Serial.println(">>> If you can read this, the board runs our code. Good.");
}

int tick = 0;

void loop() {
  tick++;
  Serial.print("tick ");
  Serial.println(tick);
  delay(1000);
}
