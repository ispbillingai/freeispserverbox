/*  RGBLight.ino  --  bring back the big onboard RGB LED blinking.
 *
 *  On the ESP32-S3-DevKitC (N16R8) the onboard addressable RGB LED is on
 *  GPIO 48. The ESP32 core has a built-in helper rgbLedWrite(pin, r, g, b).
 *  This cycles it RED -> GREEN -> BLUE -> WHITE -> off, forever = the bright
 *  ~3mm light blinking again, proving the board is alive and running our code.
 *
 *  No wiring needed -- the RGB LED is on the board itself.
 */

#define RGB_PIN 48

void setup() {
  Serial.begin(115200);
  delay(400);
  Serial.println();
  Serial.println(">>> RGB blink: GPIO48. You should see the big light cycle colors.");
}

void show(const char *name, uint8_t r, uint8_t g, uint8_t b) {
  Serial.print(">>> ");
  Serial.println(name);
  rgbLedWrite(RGB_PIN, r, g, b);   // built-in NeoPixel helper in the ESP32 core
  delay(600);
}

void loop() {
  show("RED",   60, 0, 0);
  show("GREEN", 0, 60, 0);
  show("BLUE",  0, 0, 60);
  show("WHITE", 40, 40, 40);
  show("OFF",   0, 0, 0);
  delay(300);
}
