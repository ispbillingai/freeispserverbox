/*  PinCheck.ino  --  test each screen terminal FROM CODE.
 *
 *  Tests the wire path for all 5 signal lines + watches the screen react to a
 *  RESET pulse. For each pin it BLINKS at ~2 Hz for 8 seconds and announces it
 *  on Serial. Confirm each with a multimeter (probe the SCREEN's terminal):
 *      - should swing between 0V and 3.3V about twice a second.
 *  If a screen terminal does NOT swing while its pin is "under test", that
 *  wire is the bad one.
 *
 *  Pins:  SCK=12  SDA=11  A0/DC=5  RESET=4  CS=10
 */

struct Line { int gpio; const char* name; };
Line lines[] = {
  {12, "SCK  (screen SCK)"},
  {11, "SDA  (screen SDA)"},
  { 5, "A0   (screen A0/DC)"},
  { 4, "RESET(screen RESET)"},
  {10, "CS   (screen CS)"},
};
const int N = 5;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("==========================================");
  Serial.println(" PIN CHECK -- probe each SCREEN terminal.");
  Serial.println(" Multimeter: black=GND, red=screen terminal");
  Serial.println(" A working wire SWINGS 0V <-> 3.3V ~2x/sec.");
  Serial.println("==========================================");
  for (int i = 0; i < N; i++) {
    pinMode(lines[i].gpio, OUTPUT);
    digitalWrite(lines[i].gpio, LOW);
  }
}

void loop() {
  for (int i = 0; i < N; i++) {
    // all others LOW
    for (int j = 0; j < N; j++) digitalWrite(lines[j].gpio, LOW);

    Serial.println();
    Serial.print(">>> TESTING ");
    Serial.print(lines[i].name);
    Serial.print("  on GPIO ");
    Serial.print(lines[i].gpio);
    Serial.println("  -> probe its screen terminal now (should blink 0/3.3V)");

    // blink this one pin ~2 Hz for 8 seconds
    unsigned long start = millis();
    while (millis() - start < 8000) {
      digitalWrite(lines[i].gpio, HIGH);
      delay(250);
      digitalWrite(lines[i].gpio, LOW);
      delay(250);
    }
  }
  Serial.println();
  Serial.println(">>> Full pass done. Repeating from SCK.");
}
