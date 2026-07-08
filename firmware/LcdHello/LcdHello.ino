/*  LcdHello.ino  --  16x2 character LCD (1602A, HD44780) "Hello".
 *
 *  Uses the BUILT-IN LiquidCrystal library -- nothing to install.
 *  4-bit parallel mode (only D4-D7 used).
 *
 *  WIRING (LCD pin label -> ESP32-S3):
 *    VSS  -> GND
 *    VDD  -> 5V        (the LCD wants 5V; ESP32-S3 has a 5V/VIN pin from USB)
 *    V0   -> potentiometer wiper (knob middle pin); pot outer pins to 5V and GND
 *           (NO pot? connect V0 -> GND for a first test; you'll see blocks/text)
 *    RS   -> GPIO 4
 *    RW   -> GND       (write-only; also keeps 5V off the ESP32 pins -- safe)
 *    E    -> GPIO 5
 *    D0..D3 -> (leave unconnected, 4-bit mode)
 *    D4   -> GPIO 6
 *    D5   -> GPIO 7
 *    D6   -> GPIO 15
 *    D7   -> GPIO 16
 *    A (LED+) -> 5V    (backlight; module has onboard resistor R8)
 *    K (LED-) -> GND
 */

#include <LiquidCrystal.h>

// LiquidCrystal(RS, E, D4, D5, D6, D7)
LiquidCrystal lcd(4, 5, 6, 7, 15, 16);

void setup() {
  Serial.begin(115200);
  Serial.println(">>> LCD1602 Hello starting...");

  lcd.begin(16, 2);          // 16 columns, 2 rows
  lcd.setCursor(0, 0);
  lcd.print("FreeISP box");
  lcd.setCursor(0, 1);
  lcd.print("Hello! :)");

  Serial.println(">>> printed. If blank, adjust the contrast (V0).");
}

void loop() {
  // simple live demo: blink a status word on row 2
  delay(1500);
  lcd.setCursor(0, 1);
  lcd.print("SECURE   ");
  delay(1500);
  lcd.setCursor(0, 1);
  lcd.print("Hello! :) ");
}
