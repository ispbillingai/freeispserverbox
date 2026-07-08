# ST7735 1.8" TFT White-Screen Debug — Full Handoff Report

**Purpose:** Hand this to another AI/engineer. It contains the exact hardware, software,
wiring, everything already tried, the precise current symptom, the diagnosis from a
multi-agent research pass, and the recommended next steps. Goal: make a 1.8" SPI TFT
show color ("Hello") driven by an ESP32-S3. This is the display for a sealed anti-theft
"FreeISP" box; the screen is step one of a larger firmware (status pages, anti-theft, etc.).

---

## 1. HARDWARE (exact)

- **MCU board:** ESP32-S3-DevKitC, **N16R8** variant (16MB flash, 8MB **Octal** PSRAM,
  WROOM-2). Dual USB-C (one native-USB, one UART/FTDI). Onboard addressable RGB LED on **GPIO48**.
- **Display module:** cheap red-PCB, silkscreen reads **"1.8 TFT SPI 128*160"**.
  Pin header order (as printed): **LED  SCK  SDA  A0  RESET  CS  GND  VCC**.
  - `A0` = the **DC (data/command)** pin. `LED` = backlight. Controller = ST7735 family
    (128×160). It is a **3.3V-native** module (5V on VCC does NOT power it; the only
    on-board jumper J1 is a 3.3V/5V LDO-bypass power select, NOT an interface selector).
- **Connections:** breadboard + dupont jumper wires. Multimeter available (DC volts + continuity).

## 2. SOFTWARE / TOOLCHAIN (exact)

- Arduino IDE 2.3.10 (Windows 11).
- **esp32 Arduino core 3.3.10** (Espressif). (Note: this is a very new core — see step 3 below,
  there is a documented ST7735 white-screen regression that is core-version-sensitive.)
- Libraries installed: **Adafruit ST7735 and ST7789 Library**, Adafruit GFX, Adafruit BusIO.
  (The ST7735 lib folder also contains Adafruit_ST7789 and Adafruit_ST7796S classes.)
- Board selected: **"ESP32S3 Dev Module"** on **COM3**.
- **Critical Tools setting that was needed:** **USB CDC On Boot = DISABLED.** With it
  Enabled, `Serial` output went to the native-USB port (not connected); Serial Monitor on
  COM3 (the FTDI port) showed nothing. With it **Disabled, Serial works on COM3.** Keep it Disabled.
- Other Tools settings (all confirmed correct): Flash Mode QIO 80MHz, Flash Size 16MB,
  PSRAM **OPI PSRAM**, Upload Mode UART0/Hardware CDC, USB Mode Hardware CDC and JTAG,
  Partition "16M Flash". Upload speed 921600.

## 3. WIRING (current, by the screen's printed labels)

| Screen pin | Wired to ESP32-S3 | Notes |
|---|---|---|
| LED   | 3V3 | backlight |
| SCK   | GPIO 12 | SPI clock |
| SDA   | GPIO 11 | SPI data (MOSI) |
| A0    | GPIO 5  | = DC (data/command) |
| RESET | GPIO 4  | |
| CS    | GPIO 10 | |
| GND   | GND | |
| VCC   | 3V3 | |

- Power rails: a **breadboard power rail split in the middle** earlier caused problems; it
  was bridged. **Rule enforced:** RED rail = 3V3 only, BLUE rail = GND only (an earlier bug
  had GND on the red rail → 3V3↔GND short → rail sagged to 1.8V; fixed).
- GPIO 4,5,10,11,12 are all **normal usable GPIOs** on the S3 N16R8 — NOT strapping pins
  (those are 0/3/45/46), NOT flash/PSRAM (26-37), NOT JTAG (39-42). Confirmed safe.

## 4. WHAT IS PROVEN GOOD (do NOT re-suggest these)

1. **Board + toolchain 100% healthy.** Sketches compile, upload (esptool "Hash of data
   verified"), and run. A bare counter sketch prints "tick 1,2,3…" on Serial. Onboard RGB
   LED (GPIO48) blinks under our code. Boot is clean `rst:0x1 (POWERON)` (no boot loop;
   earlier "boot loop" was just USB-CDC dropping serial on reset).
2. **Power good.** Backlight is ON (screen glows white). Multimeter at the screen's VCC↔GND
   reads a **steady 3.3V, including during fillScreen** (no sag) → brownout ruled out.
3. **Correct library/controller family** (ST7735, 128×160 per the silkscreen).
4. **All 5 signal wires deliver signal to the screen.** A code-driven blink test toggled each
   GPIO (12,11,5,4,10) at ~2 Hz; multimeter probing **at the screen's own terminals** showed
   each one swinging 0V↔3.3V. So the full wire path (incl. the dupont connection to the
   screen) is good for each line.
5. **Serial debugging works** (after setting USB CDC On Boot = Disabled).

## 5. EVERYTHING TRIED (chronological) — all still white/grey, no color

- Adafruit_ST7735 **software/bit-bang SPI** constructor `(CS,DC,MOSI,SCLK,RST)`.
- Adafruit_ST7735 **hardware SPI**: `SPI.begin(12,-1,11,10)` then `Adafruit_ST7735(&SPI,CS,DC,RST)`.
- Adafruit_ST7735 **dedicated bus**: `SPIClass *hspi=new SPIClass(HSPI); hspi->begin(12,-1,11,10);`
  `new Adafruit_ST7735(hspi,10,5,4);` (this exact one may not have been confirmed-run yet — see open items).
- All **4 tab types**: `INITR_BLACKTAB`, `INITR_GREENTAB`, `INITR_REDTAB`, `INITR_144GREENTAB`.
- **SPI speeds** 8 MHz and 2 MHz (`setSPISpeed` called AFTER `initR`).
- `invertDisplay(true)` and `(false)`.
- `setRotation(1)`.
- A **manual reset pulse** before init: RST high 50ms → low 50ms → high 150ms (and a
  longer 120/120/200 variant).
- VCC briefly on **5V** → screen did not power at all → confirmed 3.3V-native; VCC back on 3.3V.
- Tried **ST7789** init (`init(240,240)` and `init(135,240)`) as a controller-mismatch check.

## 6. CURRENT SYMPTOM (precise — this is the crux)

- With **software SPI + manual reset + slow SPI**, the screen **RESPONDS**: it **DIMS
  slightly and RECOVERS in exact lockstep with each reset+initR+fillScreen cycle (~every 3s)**,
  but it shows **only shades of white/grey — never red/green/blue**.
- Earlier (hardware SPI, no manual reset) it was **static, pure, unchanging white**.
- So: adding the manual reset is what made it start *reacting*. But no real color ever appears.

## 7. DIAGNOSIS (from a 20-agent research+verification pass)

**Verdict: the screen is almost certainly NOT faulty.** The fact that the panel **dims and
recovers in lockstep with the reset/init cycle proves the controller is alive and decoding
commands** (a dead/DOA panel cannot modulate brightness in response to SWRESET/SLPOUT/DISPON).

**Most-likely root cause:** the **SPI command path works but the dense 16-bit RGB565 pixel
data is not landing as valid color** — i.e. the controller is alive and addressed, GRAM is
just never written with valid color bytes. Candidate mechanisms, in rough order:
1. **esp32 core 3.3.10 SPI/GPIO-matrix behavior on the S3.** There is a documented,
   version-sensitive ST7735 white-screen regression on the ESP32 family (reports: works on
   2.0.14 / 3.2.0, fails on 2.0.15 / 3.1.1). This board is on the very new **3.3.10**.
2. **Adafruit library SPI-path/init not driving this module correctly on core 3.x.**
3. **SPI bit-level timing / signal integrity** over breadboard dupont wires (less likely
   given it failed identically at 2 MHz and 8 MHz, but long wires can still corrupt the
   fast pixel burst).

**Note on the verification pass:** every *specific* single-cause hypothesis was adversarially
rejected as not fully explaining "identical clean white across BOTH SPI modes AND 2/8 MHz AND
all tabs" — which is *too consistent* to be random data corruption. That inconsistency is why
the recommended next step is a **decisive low-level test**, not another guessed config.

## 8. RULED OUT (with reason)

- ❌ Dead panel — it dims on reset (controller alive).
- ❌ Power/brownout — steady 3.3V at the screen under load (measured).
- ❌ Interface-mode jumper — this 8-pin module has none; J1 is only a power LDO-bypass.
- ❌ Strapping/PSRAM/JTAG pin conflict — pins 4,5,10,11,12 are clean GPIOs on S3 N16R8.
- ❌ Just the tab type — all 4 tried; wrong tab gives *wrong colors/offset*, not pure white.
- ❌ Wrong VCC voltage — 5V doesn't power it; 3.3V is correct (and lights the backlight).
- ❌ Serial/board fault — board runs code, prints serial, blinks RGB LED.

## 9. RECOMMENDED NEXT STEPS (ranked)

**STEP 1 — DECISIVE: raw bit-bang register test + chip-ID read (no library).**
Bypasses Adafruit entirely, hand-clocks SPI Mode 0 slowly, sends a minimal correct init,
fills SOLID RED, then **reads back the controller ID (RDDID 0x04)** over Serial. Code in §10.
Interpretation:
- Solid RED → controller + data path perfect; the library/core was the bug → go to Step 3 (Arduino_GFX).
- RED shows as BLUE → only color order; change MADCTL 0xC0 → 0xC8.
- Still grey → bit-level data corruption; slow `wr8` further (10µs/edge), shorten wires.
- **RDID returns non-00/non-FF bytes → controller ALIVE & addressable** (definitive). If the
  ID doesn't match ST7735/S, it may be a clone (GC9106 / ST7789) needing a different init.
- RDID all 00/FF AND no raster ever → only THEN suspect a bad/incompatible panel.

**STEP 2 — A/B test the core version.** Without changing wiring/sketch, install esp32 core
**3.2.0 or 2.0.14** via Boards Manager and re-flash an unchanged Adafruit hardware-SPI sketch
(keep the manual reset). If color appears → it was the core regression (stay on the good core).

**STEP 3 — Switch library to Arduino_GFX** ("GFX Library for Arduino" by *moononournation*).
Best support for core 3.x + generic red ST7735; complete ST7735R init. Code in §10.
⚠️ **Do NOT use TFT_eSPI** — current stable is broken on esp32 core 3.x (needs a 4-file patch
or a core downgrade).

**STEP 4 — Signal integrity** (if still failing): shorten ALL signal jumpers to <10cm, add
100–330Ω series resistors on SCK(12) and SDA(11), add 100nF (+optional 100µF) cap across
VCC/GND right at the module pins, retry at 4 MHz.

## 10. CODE

### 10a. Raw register + chip-ID diagnostic (STEP 1)
```cpp
#define CS 10
#define DC 5
#define RST 4
#define SCK 12
#define SDA 11
void wr8(uint8_t b){ for(int i=7;i>=0;i--){ digitalWrite(SCK,LOW); digitalWrite(SDA,(b>>i)&1); delayMicroseconds(2); digitalWrite(SCK,HIGH); delayMicroseconds(2);} }
void cmd(uint8_t c){ digitalWrite(DC,LOW);  digitalWrite(CS,LOW); wr8(c); digitalWrite(CS,HIGH); }
void dat(uint8_t d){ digitalWrite(DC,HIGH); digitalWrite(CS,LOW); wr8(d); digitalWrite(CS,HIGH); }
void setup(){
  Serial.begin(115200); delay(500); Serial.println();
  pinMode(CS,OUTPUT);pinMode(DC,OUTPUT);pinMode(RST,OUTPUT);pinMode(SCK,OUTPUT);pinMode(SDA,OUTPUT);
  digitalWrite(CS,HIGH); digitalWrite(SCK,LOW);
  digitalWrite(RST,HIGH); delay(50); digitalWrite(RST,LOW); delay(50); digitalWrite(RST,HIGH); delay(150);
  cmd(0x01); delay(150);            // SWRESET
  cmd(0x11); delay(255);            // SLPOUT
  cmd(0x3A); dat(0x05);             // COLMOD 16-bit 565
  cmd(0x36); dat(0xC0);             // MADCTL RGB (try 0xC8 if red<->blue)
  cmd(0x20);                        // INVOFF (try 0x21 if blacks look white)
  cmd(0x29); delay(100);            // DISPON
  cmd(0x2A); dat(0x00);dat(0x00); dat(0x00);dat(0x7F);  // CASET 0..127
  cmd(0x2B); dat(0x00);dat(0x00); dat(0x00);dat(0x9F);  // RASET 0..159
  cmd(0x2C);                        // RAMWR
  digitalWrite(DC,HIGH); digitalWrite(CS,LOW);
  for(long i=0;i<128L*160L;i++){ wr8(0xF8); wr8(0x00); }  // SOLID RED
  digitalWrite(CS,HIGH);
  Serial.println(">>> Sent SOLID RED.");
  // RDID liveness read (shared bidirectional SDA: release it and sample)
  digitalWrite(DC,LOW); digitalWrite(CS,LOW); wr8(0x04);
  digitalWrite(DC,HIGH); pinMode(SDA, INPUT);
  uint8_t id[4];
  for(int n=0;n<4;n++){ uint8_t v=0; for(int i=7;i>=0;i--){ digitalWrite(SCK,LOW); delayMicroseconds(2); digitalWrite(SCK,HIGH); delayMicroseconds(2); v=(v<<1)|digitalRead(SDA);} id[n]=v; }
  digitalWrite(CS,HIGH); pinMode(SDA, OUTPUT);
  Serial.printf(">>> RDID = %02X %02X %02X %02X\n", id[0],id[1],id[2],id[3]);
}
void loop(){}
```

### 10b. Arduino_GFX hardware-SPI (STEP 3)
```cpp
#include <Arduino_GFX_Library.h>
#define TFT_CS 10
#define TFT_DC  5
#define TFT_RST 4
#define TFT_SCK 12
#define TFT_MOSI 11
Arduino_DataBus *bus = new Arduino_ESP32SPI(TFT_DC, TFT_CS, TFT_SCK, TFT_MOSI, GFX_NOT_DEFINED);
Arduino_GFX *gfx = new Arduino_ST7735(bus, TFT_RST, 0, false, 128, 160, 0,0,0,0, true /*bgr*/);
void setup(){
  Serial.begin(115200);
  pinMode(TFT_RST,OUTPUT);
  digitalWrite(TFT_RST,HIGH); delay(50); digitalWrite(TFT_RST,LOW); delay(50); digitalWrite(TFT_RST,HIGH); delay(150);
  if(!gfx->begin(8000000)){ Serial.println("gfx->begin FAILED"); }
  gfx->fillScreen(RED);   delay(800);
  gfx->fillScreen(GREEN); delay(800);
  gfx->fillScreen(BLUE);  delay(800);
}
void loop(){}
// If a thin junk border appears -> offsets (2,1,2,1) [green-tab]. If red/blue swap -> flip last bgr arg.
```

### 10c. Adafruit dedicated-HSPI + manual reset (alt STEP, zero new install)
```cpp
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#define TFT_SCLK 12
#define TFT_MOSI 11
#define TFT_DC 5
#define TFT_RST 4
#define TFT_CS 10
SPIClass *hspi = new SPIClass(HSPI);
Adafruit_ST7735 *tft;
void mreset(){ pinMode(TFT_RST,OUTPUT); digitalWrite(TFT_RST,HIGH);delay(120); digitalWrite(TFT_RST,LOW);delay(120); digitalWrite(TFT_RST,HIGH);delay(200); }
void setup(){
  Serial.begin(115200);
  hspi->begin(TFT_SCLK,-1,TFT_MOSI,TFT_CS);
  tft = new Adafruit_ST7735(hspi, TFT_CS, TFT_DC, TFT_RST);
  mreset();
  tft->initR(INITR_BLACKTAB);
  tft->setSPISpeed(8000000);   // MUST be after initR (Adafruit issue #107)
  tft->fillScreen(ST77XX_RED);
}
void loop(){}
```

## 11. DATA STILL NEEDED (to give the next AI)

- The **RDID 4-byte chip ID** printed by §10a (proves alive + reveals real controller).
- Whether §10a shows **solid red / red-as-blue / still grey**.
- Result of the core A/B test (§ Step 2) if reached.
- A clear photo of the FRONT and BACK of the screen module (to confirm controller markings).

---
*Context: this display is the UI for an ESP32-based sealed anti-theft "FreeISP" box (status
pages, anti-theft sensing, MikroTik REST stats, OTA). Only the screen bring-up is blocked;
the rest of the firmware exists separately.*
