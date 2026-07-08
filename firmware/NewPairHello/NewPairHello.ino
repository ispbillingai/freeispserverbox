/*  NewPairHello.ino -- brand-new classic ESP32 (WROOM-32D devkit) + blue-PCB
 *  ST7735S TFT (back silkscreen "Driver IC: ST7735S", pins GND VDD SCL SDA RST DC CS BLK).
 *
 *  WIRING (screen label -> ESP32):
 *    GND -> GND
 *    VDD -> 3V3
 *    SCL -> GPIO 18   (hardware SPI clock)
 *    SDA -> GPIO 23   (hardware SPI data/MOSI)
 *    RST -> GPIO 4
 *    DC  -> GPIO 2    (onboard blue LED flickers with data -- normal)
 *    CS  -> GPIO 5
 *    BLK -> 3V3       (backlight)
 *
 *  NOTE: classic ESP32 pin rules differ from the S3 -- GPIO 6-11 are FLASH
 *  pins, never use them here. Board = "ESP32 Dev Module". Serial @ 115200.
 *  Upload stall at "Connecting....." -> hold BOOT button until writing starts.
 */
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>

#define TFT_CS   5
#define TFT_DC   2
#define TFT_RST  4

Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);  // hardware SPI: SCL=18, SDA=23

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println(">>> New pair test: classic ESP32 + ST7735S (BLACKTAB)");
  tft.initR(INITR_BLACKTAB);     // colors wrong later? -> try INITR_GREENTAB
  Serial.println(">>> init done, cycling colors...");
}

void loop() {
  Serial.println(">>> RED");
  tft.fillScreen(ST77XX_RED);    delay(1200);
  Serial.println(">>> GREEN");
  tft.fillScreen(ST77XX_GREEN);  delay(1200);
  Serial.println(">>> BLUE");
  tft.fillScreen(ST77XX_BLUE);   delay(1200);
  tft.fillScreen(ST77XX_BLACK);
  tft.setCursor(15, 60);
  tft.setTextColor(ST77XX_YELLOW);
  tft.setTextSize(3);
  tft.println("Hello");
  delay(1500);
}
