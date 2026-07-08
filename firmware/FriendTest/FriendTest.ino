/*  FriendTest.ino -- your friend's WORKING sketch (Arduino "TFT text example",
 *  docs.arduino.cc/retired/library-examples/tft-library/TFTDisplayText),
 *  translated line-for-line to run on YOUR board.
 *
 *  Why the translation: the original uses TFT.h, which only exists for old
 *  AVR Arduinos (Uno/Leonardo) -- it will not compile for an ESP32. But
 *  TFT.h is just a wrapper around Adafruit_ST7735, so every line below is
 *  the same command, same driver chip, same behavior.
 *
 *  WIRING (identical to NewPairHello.ino -- screen label -> ESP32):
 *    GND -> GND
 *    VDD -> 3V3
 *    SCL -> GPIO 18   (hardware SPI clock; the Uno's hidden pin 13)
 *    SDA -> GPIO 23   (hardware SPI data;  the Uno's hidden pin 11)
 *    RST -> GPIO 4
 *    DC  -> GPIO 2    (onboard blue LED flickers with data -- normal)
 *    CS  -> GPIO 5
 *    BLK -> 3V3       (backlight)
 *
 *  Board = "ESP32 Dev Module", Port = COM6, Serial @ 115200.
 *  Nothing is connected to the sensor pin, so the number on screen will
 *  jump around randomly -- on the Uno with nothing on A0 it does the same.
 */

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>

// pin definition for the ESP32 (was: cs 10, dc 9, rst 8 on the Uno)
#define cs   5
#define dc   2
#define rst  4

// the Uno's A0 -- on a classic ESP32 use an ADC pin like GPIO 34
#define sensorPin 34

// create an instance of the library
Adafruit_ST7735 TFTscreen = Adafruit_ST7735(cs, dc, rst);

// char array to print to the screen (ESP32 reads 0-4095 = up to 4 digits)
char sensorPrintout[5];

void setup() {
  Serial.begin(115200);
  Serial.println(">>> FriendTest: Uno TFT text example, ESP32 edition");

  // = TFTscreen.begin() in the Uno library
  TFTscreen.initR(INITR_BLACKTAB);   // colors wrong? -> try INITR_GREENTAB
  TFTscreen.setRotation(1);          // landscape, like the Uno library default

  // clear the screen with a black background  (= background(0, 0, 0))
  TFTscreen.fillScreen(ST77XX_BLACK);

  // set the font color to white  (= stroke(255, 255, 255))
  TFTscreen.setTextColor(ST77XX_WHITE);
  // set the font size
  TFTscreen.setTextSize(2);
  // write the text to the top left corner of the screen
  TFTscreen.setCursor(0, 0);
  TFTscreen.print("Sensor Value:");
  // set the font size very large for the loop
  TFTscreen.setTextSize(5);

  Serial.println(">>> init done, updating value every 250ms");
}

void loop() {
  // Read the value of the sensor
  String sensorVal = String(analogRead(sensorPin));

  // convert the reading to a char array
  sensorVal.toCharArray(sensorPrintout, 5);

  // print the sensor value in white
  TFTscreen.setTextColor(ST77XX_WHITE);
  TFTscreen.setCursor(0, 20);
  TFTscreen.print(sensorPrintout);
  // wait for a moment
  delay(250);
  // erase the text you just wrote (redraw it in black)
  TFTscreen.setTextColor(ST77XX_BLACK);
  TFTscreen.setCursor(0, 20);
  TFTscreen.print(sensorPrintout);
}
