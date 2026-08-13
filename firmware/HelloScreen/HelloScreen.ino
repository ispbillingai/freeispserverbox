/*
  LiveDashboardNext — the WORKING BENCH copy. This is where new features
  are added. firmware/LiveDashboard/LiveDashboard.ino is the proven v2 and
  is NEVER edited; it only gets replaced once THIS file passes on the bench.

  Everything comes straight from the MikroTik the ESP32 is connected
  to (its WiFi gateway, MT_HOST "auto").

  Pages (auto-rotate 5s, values repaint live):
    Page 1  HOME     — hotspot + pppoe users online, router UP, uptime
    Page 2  PORTS    — ether1..5 real up/down + live Mbps
    Page 3  TRAFFIC  — scrolling DL/UL graph of ether1 (WAN)
    Page 4  SYSTEM   — router CPU + memory bars, board, RouterOS, box IP
    Page 5  SECURITY — door state, armed state, times opened, siren

  On top of v2 this adds:
    - HEARTBEAT to your server (SRV_URL in secrets.h; "" = feature off)
    - DOOR ALARM: reed switch -> LEDs + buzzer + red screen, all LOCAL
      first, server second. OFF until you set ALARM_WIRED 1 below.
    - MOTION ALARM: MPU-6050 jolt/tilt, instant siren, no grace.
    - HORN RELAY on GPIO13 — the LOUD part. The little buzzer does the
      rhythm, the horn is the volume. OFF until HORN_WIRED 1.
    - RFID CARD QUIET: tap a paired card, everything goes quiet for an
      hour (door AND motion). Cards live in NVS, not in the firmware, so
      ONE binary flashes every box. OFF until RFID_WIRED 1.
    - POWER SENSING on GPIO34/35: mains present + battery volts, straight
      off the board's own dividers. OFF until POWER_WIRED 1.
    - MEMORY: armed state, open count and disarm count survive a reboot.
    - OTA: update over WiFi once OTA_PASS is set in secrets.h.
    - REMOTE COMMANDS from either the router note or the server:
        screen=on | screen=off | alarm=arm | alarm=disarm | alarm=clear
        siren=off (shut it up, stay alarmed) | siren=test
        motion=learn | quiet=off (end a card's quiet early) | cards=clear

  Needs: secrets.h next to this file, ArduinoJson + MFRC522 libraries.
  Board = "ESP32 Dev Module", COM6, hold BOOT while uploading.
  Serial Monitor @ 115200.

  EVERY new subsystem is behind its own *_WIRED switch and every one of
  them ships 0. A board with nothing new soldered to it behaves EXACTLY
  like the version that already works — wire one part, flip one flag,
  reboot, watch the self-test. Never flip two at once.
*/
#define SCREEN_TAB  INITR_GREENTAB
#define SCREEN_ROT  1

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <esp_wifi.h>
#include <Wire.h>
#include <math.h>
#include <Preferences.h>
#include <MFRC522.h>
#include <ArduinoOTA.h>
#include <HTTPUpdate.h>      // pull OTA: the box fetches its own firmware
#include <esp_task_wdt.h>    // a wedged loop() must reboot, not hang armed
#include "secrets.h"

// secrets.h from an older build may not have these yet — keep compiling.
#ifndef OTA_PASS
#define OTA_PASS ""      // set a real one in secrets.h to enable OTA
#endif

#define TFT_CS   5
#define TFT_DC   2
#define TFT_RST  4
#define TFT_BLK  33   // OPTIONAL: move the screen's BLK wire from 3V3 to
                      // GPIO 33 for a fully-dark screen-off (else faint glow)

// ================================================================
//  ALARM CONFIG — every alarm setting lives in this one block.
//  Change behaviour HERE, not down in the code.
// ================================================================

//  MASTER SWITCH — leave 0 until the alarm parts are wired!
//  0 = dashboard only, exactly like the version that already works.
//  1 = alarm active (needs the GPIO32 jumper/reed wired, else the
//      box thinks the door sensor was cut and boots into ALARM).
#define ALARM_WIRED 1

// ---- alarm hardware (wire one at a time, reboot = self-test) ----
#define PIN_LED_R 25  // red LED long leg -> 25, short -> 220R -> GND
#define PIN_LED_G 26  // green LED long leg -> 26, short -> 220R -> GND
#define PIN_BUZZ  27  // small kit buzzer (+) -> 27, (-) -> GND
#define PIN_REED  32  // reed one leg -> 32, other -> GND (or a plain jumper:
                      // wire in = door CLOSED, pulled out = OPEN)

// ---- sensor wiring style ----
// Reed to GND + internal pullup, so a CLOSED door pulls the pin LOW.
// If you fit a normally-CLOSED reed (opens when the magnet is near),
// flip this to HIGH and everything else still works.
#define REED_CLOSED_LEVEL  LOW

// PASSIVE buzzer = no oscillator inside, so a steady HIGH just makes it
// click once. It only sings if you feed it a frequency. That is what the
// blue 3-pin module on the bench turned out to be (BuzzTest: only test C
// made a sound). 1 = drive it with tone(), 0 = drive it with a level.
//
// NOTE (was wrong before rev E): this flag has NOTHING to do with the horn
// any more. The board gives the horn relay its OWN pin (GPIO13, K1), so the
// passive buzzer keeps its tone() drive and the relay gets a plain level.
// Leave this at 1 for the bench buzzer; see HORN_WIRED below for the horn.
#define BUZZER_PASSIVE 1

// Only used when BUZZER_PASSIVE is 0. Kit buzzers sound when the pin goes
// HIGH; some 3-pin modules (and most relay boards) sound/switch on LOW.
#define BUZZER_ACTIVE_HIGH 1

// Only used when BUZZER_PASSIVE is 1 — what it actually sounds like.
// A passive buzzer lets us pick the pitch, so the gentle grace chirp and
// the real siren sound different. The siren alternates two tones, which
// is what makes it sound like an alarm instead of a beeping microwave.
// 4250Hz measured LOUDEST on the bench buzzer (SirenTest sweep) — that is
// its resonant peak, so the siren's high note sits right on it. 2000Hz is
// the deliberately quieter low note; the jump between the two is what makes
// it a wail. The grace chirp uses the quiet note on purpose — a warning
// should not be as violent as the alarm.
const uint16_t TONE_CHIRP_HZ   = 2000;   // polite tick during the grace
const uint16_t TONE_SIREN_A_HZ = 2000;   // siren, low note
const uint16_t TONE_SIREN_B_HZ = 4250;   // siren, high note = loudest

// ================================================================
//  HORN — the LOUD one, on the relay (board K1 / J11, GPIO13).
//  The little buzzer does the RHYTHM; the horn does the VOLUME.
// ================================================================
#define HORN_WIRED 1          // 0 = relay pin never touched. The relay IS
                              // wired (2026-08-13) — do NOT reset this to 0
                              // when syncing the two sketches.

#define PIN_RELAY 13          // K1 "IN" via R7 1k — board rev E

// Relay boards differ: most cheap blue ones are ACTIVE LOW (IN pulled to
// GND = clack). Get this backwards and the horn sounds when all is well
// and goes quiet during the alarm — so TEST IT with siren=test before
// trusting it. PINOUT.md warns the 3-pin order also varies by brand.
#define RELAY_ACTIVE_HIGH 1

// The horn is held STEADY for the whole siren instead of being beeped with
// the buzzer. Two reasons: a mechanical relay clacking every 300ms for 3
// minutes is 600 operations it does not need, and a continuous horn is
// simply louder than a pulsed one. The buzzer still beeps, so the box
// still SOUNDS like an alarm rather than a stuck car.
// The horn stays silent during the GRACE period — grace is a polite
// warning, and the polite warning is not a 100dB horn.

// ================================================================
//  RFID — tap a paired card, the box goes quiet for an hour.
//  Ported from firmware/CardDisarm/CardDisarm.ino (proven on bench).
// ================================================================
#define RFID_WIRED 1          // 0 = reader never touched

#define PIN_RC522_SS  16      // J5 "SDA" (chip select) — board rev E
#define PIN_RC522_RST 17      // J5 "RST"
                              // SCK 18 / MOSI 23 / MISO 19 are SHARED with
                              // the TFT. Different CS pins, so they coexist
                              // — but the TFT must be started FIRST.

// ⚠️ RC522 runs on 3.3V ONLY. 5V destroys it. Board J5 pin 8 is the 3V3
//    rail on purpose, and J4 (TFT) pin 2 is 5V — do not swap the plugs.

const uint32_t CARD_QUIET_MS = 300000;    // 5 minutes of quiet per tap
                                          // (Francis, 2026-08-13 -- was 1h:
                                          // long enough to service the box,
                                          // short enough that it re-arms
                                          // before anyone forgets it)
const uint8_t  CARDS_PER_BOX = 2;         // how many ship with each box
const uint8_t  MAX_CARDS     = 4;         // room for replacements later

// The quiet period covers the DOOR **and** the MOTION sensor. Someone who
// taps a card is about to handle the box — open it, move it, pull cables.
// Quieting only the reed would let the siren fire the moment they lean on
// it, and the card would look broken. When the hour ends the box re-learns
// its tilt baseline, because by then it may legitimately hang differently.

// ================================================================
//  POWER SENSING — mains present + battery volts, off the board's
//  own dividers. Nothing here is a field wire: both nets are
//  on-board (review fix C1), so no GPIO can ever see 12V.
// ================================================================
#define POWER_WIRED 1         // rev-H board assembled: dividers live on GPIO34/35

#define PIN_SENSE_MAINS 34    // R5/R6 100k/27k off +12V — input-only, ADC1
#define PIN_SENSE_BATT  35    // R3/R4 100k/100k off VBAT — input-only, ADC1
                              // ADC1 on purpose: ADC2 stops working when
                              // WiFi is on, and this box is always on WiFi.

// What the divider does to the voltage, so we can undo it in software.
//   mains: 12V * 27/(100+27) = 2.55V at the pin  -> multiply by 127/27
//   batt:  VBAT * 100/(100+100) = VBAT/2         -> multiply by 2
const float MAINS_DIV = 127.0f / 27.0f;   // = 4.7037
const float BATT_DIV  = 2.0f;

// Below this the 12V rail is gone — the mains is out and the box is
// running off the 18650. Well under 12V so a sagging PSU is not a scare,
// well over 0V so it trips before the rail is fully dead.
const float MAINS_PRESENT_V = 7.0f;

// 18650 flat is ~3.0V, full is ~4.2V. Warn early enough to matter.
const float BATT_LOW_V = 3.4f;

const uint32_t POWER_MS = 2000;   // how often to read both ADCs

// TO BUILD — BATTERY PERCENTAGE ON THE SCREEN (Francis, 2026-08-02).
// The SYSTEM page shows raw volts today. A percentage is what anyone
// standing at the box actually understands, and it goes in the heartbeat
// too so the account can show "this box is running on 40% battery".
//
// Do NOT map 3.0-4.2V straight onto 0-100%. Four things make that lie:
//
//   1. The discharge curve is FLAT. A Li-ion cell sits between 3.6 and
//      3.8V for well over half its capacity, so a linear map shows 100%
//      for a minute, then sticks around 50% for hours, then falls off a
//      cliff. Use a small piecewise table (4.20/4.06/3.98/3.92/3.87/3.82/
//      3.79/3.70/3.60/3.40/3.00 -> 100/90/80/.../10/0) and interpolate.
//
//   2. Voltage SAGS under load. Read it while the horn is sounding and a
//      healthy cell looks nearly flat. Sample only when the box is quiet
//      (no siren, no horn), or hold the last reading while it sounds.
//
//   3. CHARGING lifts it. The TP4056 pushes the cell to 4.2V, so the
//      percentage reads full long before it is. While mainsOk is true,
//      show "CHARGING" or "MAINS" rather than a number - a percentage is
//      only meaningful on battery.
//
//   4. ADC noise makes it JUMP. Average several reads and add a little
//      hysteresis, or the screen flickers between 61% and 64% and looks
//      broken. A percentage that only ever falls (while discharging) is
//      more believable than an honest one that dances.
//
// Then: battPercent() on the SYSTEM page next to the volts, "batt%" in
// the heartbeat beside "batt", and a column in box.php's fleet table.

// ---- how the alarm behaves ----
#define ALARM_ARMED_AT_BOOT 1     // 1 = live the moment it powers up
                                  // 0 = boots quiet, arm it with a command
                                  // (only used the FIRST time — after that
                                  //  the box remembers, see NVS below)

const uint32_t DEBOUNCE_MS  = 60;      // reed settle time, ignore contact bounce
const uint32_t GRACE_MS     = 15000;   // polite chirping first, THEN the siren.
                                       // Gives you 15s to close it / disarm.
                                       // Set to 0 for an instant siren.
const uint32_t CHIRP_ON_MS  = 40;      // grace chirp: short tick...
const uint32_t CHIRP_GAP_MS = 1200;    // ...once every this long
const uint32_t BEEP_MS      = 300;     // full siren beep-beep rhythm
const uint32_t SIREN_MAX_MS = 180000;  // siren gives up after 3 min (battery +
                                       // neighbours). Red LED + red screen +
                                       // server alert STAY on until it closes.
                                       // 0 = never stop sounding.

// A MOTION alarm gets its OWN, longer timer. Someone tearing the box off
// the wall earns a harder alarm than a lid being lifted, so this runs
// instead of SIREN_MAX_MS whenever alarmReason == "MOTION".
const uint32_t MOTION_SIREN_MS = 120000;   // 2 minutes, continuous

// Stopping it ONLINE works for both: siren=off from the server (or the
// router note) silences ANY alarm, motion included. The only limit is
// timing - server commands ride the heartbeat, so a command lands within
// HEART_MS (20s). Shorten that if 20s is too long to wait.
//
// TURNING THE ALARM OFF COMPLETELY (for a site that does not want one) is
// alarm=disarm, and it now SURVIVES A REBOOT — see REMEMBER_STATE above.
// The remaining work is on the server: an on/off switch per box in the
// customer's account that sends disarm/arm and shows the state back.
//
// THE DISARMED STATE IS SHOWN, NEVER HIDDEN. A box that looks armed but is
// not is the worst state to be in, so:
//   - the SECURITY page shows OFF, or QUIET with the time LEFT counting
//     down ("QUIET 47:12"), so anyone standing there knows it is off and
//     for how much longer
//   - disarmCount sits next to openCount, so a box being silenced over and
//     over is obvious at a glance
//   - both ride the heartbeat, so the account shows the same thing and the
//     history lives on the server, not only on a screen nobody is watching

// ================================================================
//  MOTION CONFIG — the MPU-6050 "torn off the wall" sensor.
//  Same rule as the alarm: leave 0 until it is actually wired, or
//  the box will read nonsense from an absent sensor.
// ================================================================
#define MOTION_WIRED 1        // MPU-6050 plugged into the rev-H board's U4

#define PIN_SDA   21          // MPU-6050 SDA -> GPIO 21
#define PIN_SCL   22          // MPU-6050 SCL -> GPIO 22
#define MPU_ADDR  0x68        // 0x68 normally; 0x69 if you tie AD0 to 3V3

// A thief ripping the box off the wall gets NO grace period — the plan
// says instant siren, and that is what these do.
//
// JOLT = a sudden knock. At rest the sensor reads 1.0g (just gravity);
// anything this far off 1.0g is a real impact. Lower = twitchier.
const float MOTION_JOLT_G = 0.35f;

// TILT = the box is no longer hanging the way it was. Measured against a
// baseline it learns at boot. Must last MOTION_TILT_MS so that a passing
// knock or someone leaning on it does not set it off — only a box that
// is actually now at a new angle counts.
const uint8_t  MOTION_TILT_DEG = 25;
const uint32_t MOTION_TILT_MS  = 1500;

const uint32_t MOTION_MS       = 50;    // how often to read the sensor
const uint32_t MOTION_SETTLE_MS = 2000; // ignore everything this long after
                                        // boot/learn, while it stops swinging

// ---- what the alarm reports ----
#define ALARM_BEAT_ON_CHANGE 1    // 1 = push an instant heartbeat to the server
                                  //     the moment the door opens/closes

// ================================================================
//  MEMORY (NVS) — what the box must NOT forget when the power dies.
//
//  A power cut that silently re-arms a box the customer switched off is
//  the worst kind of bug: it looks like the alarm "went off by itself".
//  So the armed state is stored, not assumed. Same for the two counts —
//  a box that resets its history on every blackout can never show that
//  it is being opened, or silenced, over and over.
//
//  Stored in namespace "freeisp" (the same one CardDisarm uses, so a box
//  paired on the bench stays paired here):
//     armed    the last arm/disarm decision
//     opens    how many times the door has been opened, ever
//     disarms  how many times someone silenced or disarmed it, ever
//     n,card0..cardN   the cards paired to THIS box
// ================================================================
#define REMEMBER_STATE 1      // 0 = go back to forgetting on every boot

Adafruit_ST7735 tft(TFT_CS, TFT_DC, TFT_RST);

// ---- colors (RGB565) ----
#define C_BG      ST77XX_BLACK
#define C_BAR     0x10E4          // near-black header, content stands out
#define C_CARD    0x18E3          // card panels: a step above the bg
#define C_EDGE    0x39C7          // card outline
#define C_TITLE   ST77XX_WHITE
#define C_LABEL   0x8C71
#define C_VALUE   ST77XX_WHITE
#define C_GOOD    0x07E8
#define C_BAD     0xF965
#define C_ACCENT  0x07FF
#define C_WARN    0xFFE0

// ================================================================
//  SCREEN SETTINGS — remotely adjustable from the panel, kept in NVS.
//  The screen is the product's face; the owner tunes it from the fleet
//  page like a phone: hold a page, choose which pages rotate, how fast,
//  and how bright. (Layout reads tft.width()/height() — the 3.5" panel
//  that is coming inherits all of this.)
// ================================================================
extern bool screenOn;              // defined with the rest of the state below
extern Preferences store;          // the NVS handle, defined below

uint8_t  scrHold   = 255;          // 255 = auto-rotate, else page to hold
uint8_t  scrMask   = 0b11111;      // bit n = page n joins the rotation
uint32_t scrRotMs  = 5000;         // ms per page
uint8_t  scrBright = 100;          // backlight %, PWM on TFT_BLK
#define  BLK_LEDC_CH 7             // clear of tone()'s channel

void blkWrite(uint8_t duty) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(TFT_BLK, duty);          // core 3.x addresses the PIN
#else
  ledcWrite(BLK_LEDC_CH, duty);      // core 2.x addresses the CHANNEL
#endif
}

void applyBright() {
  // screen off = backlight hard off, whatever the setting says
  blkWrite(screenOn ? map(scrBright, 0, 100, 0, 255) : 0);
}

void nvsSaveScreen() {
#if REMEMBER_STATE
  store.begin("freeisp", false);
  store.putUChar("shold", scrHold);
  store.putUChar("smask", scrMask);
  store.putULong("srot",  scrRotMs);
  store.putUChar("sbri",  scrBright);
  store.end();
#endif
}

// FAST POLL — while the owner is driving the screen from the panel, a
// 20s command latency feels broken. poll=fast drops the heartbeat gap to
// 2s for five minutes, then it decays back to normal on its own.
uint32_t fastPollUntil = 0;
bool fastPolling() {
  return fastPollUntil && (int32_t)(millis() - fastPollUntil) < 0;
}

const uint32_t PAGE_MS   = 5000;   // default rotate; scrRotMs is the live value
const uint32_t POLL_MS   = 2000;   // ethernet counters (drives the graph)
const uint32_t USERS_MS  = 5000;   // hotspot active users
const uint32_t SYS_MS    = 10000;  // cpu/memory/uptime
const uint32_t CMD_MS    = 3000;   // remote-command check (router system note)
const uint32_t HEART_MS  = 20000;  // heartbeat to Francis's server
const uint32_t LIVE_MS   = 500;    // screen repaint
const uint32_t STATUS_MS = 30000;  // "how is every part doing" block on serial

const uint8_t NUM_PAGES = 5;

// ---- state ----
uint8_t  page = 0;
uint32_t lastPage = 0, lastPoll = 0, lastUsers = 0, lastSys = 0, lastLive = 0, lastCmd = 0, lastBeat = 0;
uint32_t lastStatus = 0;
bool     heartbeat = false;
bool     screenOn  = true;

// ---- door / alarm state ----
// SECURE  = door shut, all quiet
// GRACE   = door just opened, polite chirp, siren is coming
// SIREN   = full beep-beep-beep
// SILENT  = door still open but the sound stopped (timed out, or you
//           sent siren=off). Screen + LED + server stay alarmed.
enum AlarmState { AS_SECURE, AS_GRACE, AS_SIREN, AS_SILENT };

bool       doorOpen      = false;
bool       alarmArmed    = ALARM_ARMED_AT_BOOT;
AlarmState alarmState    = AS_SECURE;
int        lastReedRaw   = -1;
uint32_t   reedChangedAt = 0;
uint32_t   openedAt      = 0;   // when this opening started
uint32_t   beepAt        = 0;
bool       beepOn        = false;
uint32_t   openCount     = 0;
uint32_t   disarmCount   = 0;   // times someone silenced/disarmed it, ever
uint8_t    bootRaisedWhy = 0;   // NVS: alarm raised at power-off? 1=DOOR 2=MOTION
uint32_t   bootCount     = 0;   // NVS: total boots — a crash-looping box shows here
uint32_t   crashCount    = 0;   // NVS: boots caused by brownout/panic/watchdog
const char* resetText    = "?"; // why THIS boot happened, for the heartbeat
uint16_t   buzzHz        = TONE_SIREN_A_HZ;  // pitch the next buzz() will use
bool       sirenAlt      = false;            // flips the two siren notes
String     alarmReason   = "";               // "DOOR" / "MOTION" - why it rang
bool       hornOn        = false;            // relay state, so we only click it on a change
bool       beatPending   = false;            // "send a heartbeat at the next safe moment"

// ---- card quiet state ----
uint32_t quietUntil = 0;        // 0 = not quiet. millis() deadline otherwise.

// ---- power state ----
bool  mainsOk    = true;        // is the 12V rail (and so the mains) there
bool  powerOk    = false;       // have we actually read the ADCs yet
float railV      = 0;           // measured 12V rail
float battV      = 0;           // measured battery

// ---- motion state (MPU-6050) ----
bool     mpuOk       = false;   // did the sensor answer at boot
bool     motionAlarm = false;   // motion is what raised the alarm
float    baseX = 0, baseY = 0, baseZ = 1;   // the "hanging quietly" direction
float    lastG = 1.0f;          // last magnitude, for the screen
float    lastTiltDeg = 0;
uint32_t motionReadyAt = 0;     // ignore readings until this time
uint32_t tiltSince     = 0;     // when the tilt first went over the limit
uint32_t lastMotionAt  = 0;     // last time it saw real movement

// ---- RFID state ----
MFRC522     rfid(PIN_RC522_SS, PIN_RC522_RST);
Preferences store;              // the ESP32's own permanent memory (NVS)

String   cards[MAX_CARDS];
uint8_t  cardCount  = 0;
bool     rc522Ok    = false;
String   lastUid    = "";
uint32_t lastCardAt = 0;
// what the fleet needs to answer "who opened my box, and when": the tap
// itself, whether the box accepted it, and how long ago.
String   lastTapUid = "";
bool     lastTapOk  = false;
uint32_t lastTapAt  = 0;      // 0 = no tap since boot
uint32_t rejectCount = 0;     // strangers' cards, ever (NVS)

const char* alarmStateName() {
  switch (alarmState) {
    case AS_GRACE:  return "GRACE";
    case AS_SIREN:  return "SIREN";
    case AS_SILENT: return "SILENT";
    default:        return "SECURE";
  }
}

// ---- router data ----
const int NPORTS = 5;
struct Port {
  String   name;
  bool     running = false;
  uint64_t rxBytes = 0, txBytes = 0;
  float    rxMbps  = 0, txMbps  = 0;
  bool     seen    = false;
};
Port     ports[NPORTS];
bool     routerOk     = false;
uint32_t lastGoodPoll = 0;
uint32_t pollFails    = 0;
String   lastErr      = "";

int    usersOnline = -1;        // hotspot active, -1 = not read yet
int    pppoeOnline = -1;        // ppp active sessions
int    cpuLoad     = -1;        // %
float  freeMemMB   = -1, totMemMB = -1;
String rosVersion  = "-", boardName = "-", rosUptime = "-";

// traffic history (ether1), newest at the end
const int HIST = 160;
float rxHist[HIST] = {0}, txHist[HIST] = {0};

// ---- logging ----
void logLine(const char* lvl, const char* tag, const String& msg) {
  Serial.printf("[%6lus] %s [%s] %s\n", millis() / 1000, lvl, tag, msg.c_str());
}
#define logInfo(tag, msg) logLine("..", tag, msg)
#define logOK(tag, msg)   logLine("OK", tag, msg)
#define logErr(tag, msg)  logLine("!!", tag, msg)

// things defined further down that this block needs to call
void buzz(bool on);
void drawStatic();
void motionLearn(const char* why);
void startSiren(const char* reason);
bool alarmRaised();

// ================================================================
//  NVS — the handful of things that must outlive a power cut.
//  Every write is a flash write, so these are only ever called when
//  something ACTUALLY changed, never on a timer.
// ================================================================
void nvsLoadState() {
#if REMEMBER_STATE
  store.begin("freeisp", true);                  // read-only
  alarmArmed  = store.getBool ("armed",   ALARM_ARMED_AT_BOOT);
  openCount   = store.getULong("opens",   0);
  disarmCount = store.getULong("disarms", 0);
  // was an alarm RAISED when power died? 0 = no, 1 = DOOR, 2 = MOTION.
  // Without this a thief who trips the siren and yanks power (or pokes
  // the exposed EN button) reboots into a fresh polite grace period.
  bootRaisedWhy = store.getUChar("raised", 0);
  bootCount   = store.getULong("boots",   0);
  crashCount  = store.getULong("crashes", 0);
  rejectCount = store.getULong("rejects", 0);
  scrHold   = store.getUChar("shold", 255);
  scrMask   = store.getUChar("smask", 0b11111);
  scrRotMs  = store.getULong("srot",  PAGE_MS);
  scrBright = store.getUChar("sbri",  100);
  if (scrRotMs < 2000 || scrRotMs > 60000) scrRotMs = PAGE_MS;
  if ((scrMask & 0b11111) == 0) scrMask = 0b11111;   // never all-off
  store.end();
  logOK("NVS", String("remembered: ") + (alarmArmed ? "ARMED" : "DISARMED") +
               ", " + String(openCount) + " opens, " +
               String(disarmCount) + " disarms");
#else
  logInfo("NVS", "REMEMBER_STATE=0 - starting from defaults every boot");
#endif
}

void nvsPut(const char* key, uint32_t v) {
#if REMEMBER_STATE
  store.begin("freeisp", false);
  store.putULong(key, v);
  store.end();
#endif
}

void nvsPutArmed(bool v) {
#if REMEMBER_STATE
  store.begin("freeisp", false);
  store.putBool("armed", v);
  store.end();
#endif
}

// 0 = all clear, 1 = DOOR raised, 2 = MOTION raised. NVS skips writes of
// an unchanged value, so re-fires during one long alarm cost no flash wear.
void nvsPutRaised(uint8_t why) {
#if REMEMBER_STATE
  store.begin("freeisp", false);
  store.putUChar("raised", why);
  store.end();
#endif
}

// ================================================================
//  HORN — one place that knows the relay's polarity.
//  Everything else just says horn(true) / horn(false).
// ================================================================
void horn(bool on) {
  if (on == hornOn) return;              // never click the relay for nothing
  hornOn = on;
#if HORN_WIRED
  digitalWrite(PIN_RELAY, (on == (RELAY_ACTIVE_HIGH != 0)) ? HIGH : LOW);
  logErr("HORN", on ? "RELAY ON - horn sounding" : "relay off - horn quiet");
#endif
}

// ================================================================
//  CARD QUIET PERIOD — an hour of silence bought with a card tap.
//  Covers the door AND the motion sensor, deliberately.
// ================================================================

// A box that has not been given its cards yet must NOT scream at the
// person setting it up — they have nothing to tap to stop it.
bool enrolling() {
#if RFID_WIRED
  return cardCount < CARDS_PER_BOX;
#else
  return false;                          // no reader = nothing to enrol
#endif
}

// The alarm-suppression question is NOT "is it still enrolling" — it is
// "does the person at the box have anything to tap". With even ONE card
// paired they do, so the box must arm. Before this split, a rushed install
// that paired 1 of 2 cards left a box that NEVER alarmed (door and motion
// both suppressed) while the screen showed ARMED and the heartbeat said
// armed:true — the "looks armed but is not" state, forever, 200km away.
bool unprotected() {
#if RFID_WIRED
  return cardCount == 0;
#else
  return false;                          // no reader = card can't be the gate
#endif
}

// millis() rolls over after ~49 days, so compare as a SIGNED difference
// rather than "now < deadline" — otherwise a box that has been up that
// long goes permanently quiet at exactly the wrong moment.
bool inQuietPeriod() {
  return quietUntil != 0 && (int32_t)(millis() - quietUntil) < 0;
}

uint32_t quietSecsLeft() {
  if (!inQuietPeriod()) return 0;
  return (uint32_t)((int32_t)(quietUntil - millis())) / 1000;
}

void startQuiet(const char* why) {
  buzz(false);                           // silence FIRST, explain after
  horn(false);
  if (alarmState == AS_GRACE || alarmState == AS_SIREN) alarmState = AS_SILENT;
  quietUntil = millis() + CARD_QUIET_MS;
  if (quietUntil == 0) quietUntil = 1;   // never land on "off" by accident
  disarmCount++;
  nvsPut("disarms", disarmCount);
  logOK("QUIET", String(why) + " - quiet for " +
                 String(CARD_QUIET_MS / 60000) + " minutes (disarm #" +
                 String(disarmCount) + ")");
  beatPending = true;
}

// the hour running out is an EVENT, not just a flag going false
void pollQuiet() {
  if (!quietUntil || inQuietPeriod()) return;
  quietUntil = 0;

  // the box may legitimately be hanging at a new angle after an hour of
  // someone working in it — re-learn, or it alarms on the new normal
  if (mpuOk) motionLearn("quiet period ended");

  if (doorOpen && alarmArmed) {
    logErr("QUIET", "quiet period OVER and the door is still open - siren");
    startSiren("DOOR");
  } else {
    // Door shut and the quiet ran out: the card has done its job, so
    // FINISH the clear. Before this, a card-quieted MOTION alarm stayed
    // AS_SILENT forever (red LED, ALARM banner, heartbeat stuck) because
    // only a door-close or a remote clearAlarm() ever reset the state —
    // and a motion alarm's door was never open in the first place.
    if (alarmState == AS_SILENT) {
      alarmState  = AS_SECURE;
      alarmReason = "";
      motionAlarm = false;
      nvsPutRaised(0);
      digitalWrite(PIN_LED_R, LOW);
      digitalWrite(PIN_LED_G, HIGH);
      logOK("QUIET", "quiet period over, door shut - alarm cleared, box secure");
      drawStatic();
    } else {
      logOK("QUIET", "quiet period over - box armed again");
      if (!alarmRaised()) drawStatic();
    }
  }
  beatPending = true;
}

String httpExplain(int code) {
  switch (code) {
    case 200: return "OK";
    case 401: return "401 wrong user/password (check secrets.h + router user)";
    case 403: return "403 user not allowed (group needs read,rest-api,api policy)";
    case 404: return "404 no such REST path on this router";
    case -1:  return "connection failed (router reachable? www service on?)";
    case -11: return "read timeout (router busy or link flaky)";
    default:  return "HTTP " + String(code);
  }
}

String routerHost() {
  return (strcmp(MT_HOST, "auto") == 0) ? WiFi.gatewayIP().toString()
                                        : String(MT_HOST);
}

// ---- how loudly the router is allowed to complain ----
// The four fetchers poll every 2-10s. When the router is unreachable that
// used to be a wall of identical timeout lines, several per second, and it
// buried everything else on the monitor. So: say it properly ONCE, then
// stay quiet about the SAME error until it changes, it recovers, or this
// long has passed. Nothing is hidden, it just stops repeating itself.
// 30 min (was 60s): on Francis's bench the router deliberately blocks the
// box, so even one line a minute per fetcher was four lines a minute of
// known news. The STATUS block still shows ROUTER !! with the fail count
// every cycle, so the state is never invisible -- it just stops narrating.
const uint32_t REST_REPEAT_MS = 1800000;

uint32_t restFailStreak  = 0;
uint32_t restLastLogAt   = 0;
String   restLastLogMsg  = "";

// ---- BACKOFF: why an unreachable router used to eat card taps ----
// Every restGet BLOCKS the loop for up to 8s waiting on a timeout, and
// four fetchers poll every 2-10s. With the router unreachable that adds
// up to more time blocked than running -- and pollCards() only runs
// between calls. A card tapped during the block is simply never seen,
// which is why CardTest reads a card instantly and the dashboard would
// not pair one. So: once the router has failed a few times in a row,
// stop hammering it. Retry on a widening interval instead, capped, and
// go straight back to normal the moment one request succeeds.
const uint32_t REST_BACKOFF_AFTER = 3;        // failures before backing off
const uint32_t REST_BACKOFF_MIN_MS = 15000;   // first retry gap
const uint32_t REST_BACKOFF_MAX_MS = 300000;  // never wait longer than 5 min
uint32_t restNextTryAt = 0;                   // millis() gate, 0 = try now

// one shared REST GET: fills doc, returns true on success, logs failures
bool restGet(const char* tag, const String& path, JsonDocument& doc) {
  if (WiFi.status() != WL_CONNECTED) { lastErr = "no WiFi"; return false; }

  // Signed compare: millis() rollover must not unblock or freeze the gate.
  if (restNextTryAt && (int32_t)(millis() - restNextTryAt) < 0) {
    lastErr = "router backoff (still down, not retrying yet)";
    return false;
  }

  HTTPClient http;
  String host = routerHost();
  // Short timeouts on purpose: this runs on the same thread as the card
  // reader and the reed. A router that needs longer than this is down as
  // far as the box is concerned, and the box's job is to stay responsive.
  http.setConnectTimeout(1500);
  http.setTimeout(2500);
  http.begin(String("http://") + host + path);
  http.setAuthorization(MT_USER, MT_PASS);
  uint32_t t0 = millis();
  int code = http.GET();
  uint32_t took = millis() - t0;

  if (code != 200) {
    lastErr = httpExplain(code);
    String peek = (code > 0) ? http.getString().substring(0, 120) : "";
    restFailStreak++;

    uint32_t nowMs = millis();
    bool changed = (lastErr != restLastLogMsg);
    if (changed || restFailStreak == 1 || nowMs - restLastLogAt >= REST_REPEAT_MS) {
      logErr(tag, "GET " + path + " on " + host + " failed after " +
                  String(took) + "ms: " + lastErr +
                  (peek.length() ? ("  reply: " + peek) : "") +
                  (restFailStreak > 1 ? "  (x" + String(restFailStreak) + ")" : "") +
                  "  [further identical errors suppressed]");
      restLastLogAt  = nowMs;
      restLastLogMsg = lastErr;
    }
    // Widen the retry gap: 15s, 30s, 60s ... capped. Keeps the loop free
    // for the reed, the reader and the screen while the router is out.
    if (restFailStreak >= REST_BACKOFF_AFTER) {
      uint32_t gap = REST_BACKOFF_MIN_MS << (restFailStreak - REST_BACKOFF_AFTER);
      if (gap > REST_BACKOFF_MAX_MS || gap < REST_BACKOFF_MIN_MS)
        gap = REST_BACKOFF_MAX_MS;           // also catches the shift overflow
      restNextTryAt = nowMs + gap;
      if (restNextTryAt == 0) restNextTryAt = 1;
    }
    http.end();
    return false;
  }
  String body = http.getString();
  http.end();

  restNextTryAt = 0;                    // answered: drop the backoff at once
  if (restFailStreak) {                 // recovery is always worth one line
    logOK("ROUTER", "router answering again after " + String(restFailStreak) +
                    " failed request(s)");
    restFailStreak = 0;
    restLastLogMsg = "";
  }

  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    lastErr = String("JSON parse: ") + err.c_str();
    logErr(tag, lastErr);
    return false;
  }
  return true;
}

// ---- fetchers ----
void fetchPorts() {
  JsonDocument doc;
  if (!restGet("PORTS",
      "/rest/interface/ethernet?.proplist=name,rx-bytes,tx-bytes,running", doc)) {
    routerOk = false;
    pollFails++;
    return;
  }

  uint32_t now = millis();
  float dt = (lastGoodPoll > 0) ? (now - lastGoodPoll) / 1000.0f : 0;

  int i = 0;
  for (JsonObject o : doc.as<JsonArray>()) {
    if (i >= NPORTS) break;
    Port& p = ports[i];
    p.name    = o["name"].as<String>();
    p.running = (strcmp(o["running"] | "false", "true") == 0);
    uint64_t rx = strtoull(o["rx-bytes"] | "0", nullptr, 10);
    uint64_t tx = strtoull(o["tx-bytes"] | "0", nullptr, 10);
    if (p.seen && dt > 0.2f) {
      p.rxMbps = (rx - p.rxBytes) * 8.0f / dt / 1e6f;
      p.txMbps = (tx - p.txBytes) * 8.0f / dt / 1e6f;
      if (p.rxMbps < 0) p.rxMbps = 0;
      if (p.txMbps < 0) p.txMbps = 0;
    }
    p.rxBytes = rx; p.txBytes = tx; p.seen = true;
    i++;
  }

  memmove(rxHist, rxHist + 1, sizeof(float) * (HIST - 1));
  memmove(txHist, txHist + 1, sizeof(float) * (HIST - 1));
  rxHist[HIST - 1] = ports[0].rxMbps;
  txHist[HIST - 1] = ports[0].txMbps;

  if (!routerOk) logOK("PORTS", "router " + routerHost() + " link UP, " +
                                String(i) + " ports read");
  routerOk = true;
  lastGoodPoll = now;
  lastErr = "";
}

void fetchUsers() {
  // hotspot active sessions = customers online RIGHT NOW
  JsonDocument doc;
  if (restGet("USERS", "/rest/ip/hotspot/active?.proplist=user", doc)) {
    int n = doc.as<JsonArray>().size();
    if (n != usersOnline) logOK("USERS", String(n) + " hotspot users online");
    usersOnline = n;
  }
  // pppoe/ppp active sessions
  JsonDocument doc2;
  if (restGet("USERS", "/rest/ppp/active?.proplist=name", doc2)) {
    int n = doc2.as<JsonArray>().size();
    if (n != pppoeOnline) logOK("USERS", String(n) + " pppoe users online");
    pppoeOnline = n;
  }
}

// screen power: pixels off via panel command + backlight off if on TFT_BLK
void setScreen(bool on) {
  if (on == screenOn) return;
  screenOn = on;
  tft.enableDisplay(on);
  tft.enableSleep(!on);
  applyBright();                   // PWM: honours the brightness setting
  if (on) drawStatic();            // repaint fresh when waking
  logOK("CMD", on ? "screen ON" : "screen OFF");
}

// REMOTE COMMANDS via the router's system note — set from WinBox terminal:
//   /system note set note="screen=off"      (or screen=on, alarm=disarm,
//                                            alarm=arm, siren=off, siren=test)
// The box reads it every 3s and obeys. No server needed.
void fetchCommand() {
  JsonDocument doc;
  if (!restGet("CMD", "/rest/system/note", doc)) return;
  String note = (const char*)(doc["note"] | "");
  // Execute a note ONCE, on change — not every 3s forever. Before this,
  // an owner who set note="siren=off" after a false alarm and never
  // cleared it had silently killed every future alarm: each new siren
  // was silenced within 3s of raising (and bumped disarmCount, poisoning
  // the counter meant to reveal exactly that). A note that is deleted
  // and re-set re-arms once, which is also the intuitive behaviour.
  static String lastNote = "\x01unset";   // never equals a real note
  if (note == lastNote) return;
  lastNote = note;
  // only treat the note as a command if it looks like one ("thing=value"),
  // so a normal note left on the router doesn't spam the log
  if (note.indexOf('=') >= 0) runCommand(note);   // same list as the server
}

// ---- door alarm (GOLDEN RULE: fires locally FIRST, server second) ----

// the siren's two notes, alternating, so it wails instead of just beeping
void nextSirenNote() {
  sirenAlt = !sirenAlt;
  buzzHz = sirenAlt ? TONE_SIREN_A_HZ : TONE_SIREN_B_HZ;
}

// one place that knows HOW this buzzer makes noise. Everything else in
// the alarm just says buzz(true) / buzz(false) and never worries about it.
void buzz(bool on) {
  beepOn = on;
#if BUZZER_PASSIVE
  if (on) {
    tone(PIN_BUZZ, buzzHz);            // a passive buzzer needs a frequency
  } else {
    noTone(PIN_BUZZ);
    pinMode(PIN_BUZZ, OUTPUT);         // noTone releases the pin - hold it low
    digitalWrite(PIN_BUZZ, LOW);
  }
#else
  digitalWrite(PIN_BUZZ, (on == (BUZZER_ACTIVE_HIGH != 0)) ? HIGH : LOW);
#endif
}

void drawAlarmBanner() {
  int w = tft.width(), h = tft.height();
  tft.fillScreen(C_BAD);
  // a dark band top and bottom so the white type has somewhere to sit
  tft.fillRect(0, 0, w, 20, 0x8000);
  tft.setTextSize(1);
  tft.setTextColor(ST77XX_WHITE, 0x8000);
  tft.setCursor(6, 6);
  tft.print(alarmReason == "MOTION" ? "MOTION" : "DOOR");
  tft.setCursor(w - 46, 6);
  tft.print(alarmStateName());

  tft.setTextSize(3);
  tft.setTextColor(ST77XX_WHITE, C_BAD);
  tft.setCursor((w - 5 * 18) / 2, h / 2 - 30);
  tft.print("ALARM");

  tft.setTextSize(1);
  const char* line = (alarmReason == "MOTION")
                     ? "BOX IS BEING MOVED" : "DOOR IS OPEN";
  tft.setCursor((w - (int)strlen(line) * 6) / 2, h / 2 + 4);
  tft.print(line);

  // what to DO about it — the card is the kill-switch, so say so
  tft.fillRect(0, h - 22, w, 22, 0x8000);
  tft.setTextColor(ST77XX_WHITE, 0x8000);
  const char* act = "TAP YOUR CARD";
  tft.setCursor((w - (int)strlen(act) * 6) / 2, h - 15);
  tft.print(act);
}

// The red banner used to LOCK the screen until the door closed, which
// meant an open door hid every other page — you could not see the users,
// the ports, or whether the router was even up while the box was crying.
// Now the banner is just page number NUM_PAGES: while the alarm is raised
// it joins the 5s rotation, so the red screen still comes round every
// cycle but the dashboard keeps showing what is happening.
void showAlarmBanner() {
  page = NUM_PAGES;                    // jump the rotation to the banner NOW
  lastPage = millis();                 // and give it its full 5 seconds
  drawAlarmBanner();
}

// Ask for a heartbeat — do NOT send one from here.
//
// sendHeartbeat() blocks while it waits on the network. This used to be
// called straight out of onDoorChange() and pollMotion(), i.e. from inside
// the alarm path, so a slow or dead server froze the siren's rhythm at the
// exact moment the alarm went off. The sound never stopped (tone() and the
// relay are both latched in hardware) but it sat on one note instead of
// wailing — the box sounded broken precisely when it mattered.
//
// So the alarm only ever raises a FLAG. loop() sends it a moment later,
// once the local response has already happened. That is the golden rule:
// locally first, server second.
void alarmBeat() {
#if ALARM_BEAT_ON_CHANGE
  beatPending = true;
#endif
}

// is the alarm currently raised? (used to decide who owns the screen)
bool alarmRaised() {
  return alarmArmed && alarmState != AS_SECURE;
}

// ONE place that starts the siren, whatever set it off. Motion skips the
// grace period on purpose — the plan says a box being torn off the wall
// does not get 15 polite seconds.
// how long THIS siren is allowed to sound. A box being torn off the wall
// gets the longer, continuous motion timer; a lifted lid gets the door one.
uint32_t sirenMaxMs() {
  return (alarmReason == "MOTION") ? MOTION_SIREN_MS : SIREN_MAX_MS;
}

void startSiren(const char* reason) {
  alarmReason = reason;
  alarmState  = AS_SIREN;
  nvsPutRaised(alarmReason == "MOTION" ? 2 : 1);  // survive a power yank
  openedAt    = millis();
  beepAt      = millis();
  nextSirenNote();
  buzz(true);
  horn(true);                          // the loud one, steady, until it stops
  digitalWrite(PIN_LED_R, HIGH);
  digitalWrite(PIN_LED_G, LOW);
  if (!screenOn) setScreen(true);      // alarm overrides screen-off
  showAlarmBanner();
}

void onDoorChange(bool open) {
  doorOpen = open;
  // 1) LOCAL response, instant, works with no WiFi at all
  digitalWrite(PIN_LED_R, open ? HIGH : LOW);
  digitalWrite(PIN_LED_G, open ? LOW : HIGH);

  if (open) {
    openCount++;
    nvsPut("opens", openCount);         // survives the next power cut
    openedAt = millis();
    beepAt   = millis();

    if (!alarmArmed) {                  // disarmed = you opened it on purpose
      alarmState = AS_SILENT;
      buzz(false);
      horn(false);
      logInfo("ALARM", "door OPEN but alarm is DISARMED - staying quiet");
    } else if (unprotected()) {         // ZERO cards paired = nothing to stop it
      alarmState = AS_SILENT;
      buzz(false);
      horn(false);
      logInfo("ALARM", "door OPEN but this box has no cards yet (ENROL) - quiet");
    } else if (inQuietPeriod()) {       // a card bought silence
      alarmState = AS_SILENT;
      buzz(false);
      horn(false);
      logInfo("ALARM", "door OPEN but a card bought quiet (" +
                       String(quietSecsLeft() / 60) + " min left) - staying quiet");
    } else if (GRACE_MS > 0) {          // chirp first, siren after the grace
      alarmReason = "DOOR";
      alarmState = AS_GRACE;
      nvsPutRaised(1);                  // a reboot resumes, not restarts
      buzzHz = TONE_CHIRP_HZ;
      buzz(true);
      if (!screenOn) setScreen(true);   // alarm overrides screen-off
      showAlarmBanner();
      logErr("ALARM", "door OPEN (count=" + String(openCount) + ") - " +
                      String(GRACE_MS / 1000) + "s grace, then siren");
    } else {                            // no grace configured = straight to it
      startSiren("DOOR");
      logErr("ALARM", "door OPEN (count=" + String(openCount) + ") - siren ON");
    }
  } else {
    alarmState  = AS_SECURE;
    alarmReason = "";
    motionAlarm = false;
    nvsPutRaised(0);
    buzz(false);
    horn(false);
    quietUntil = 0;              // lid shut ends a card's quiet early
    drawStatic();
    logOK("ALARM", "door CLOSED - siren OFF, box secure");
  }
  // 2) THEN tell the server (best effort, carried by an instant heartbeat)
  alarmBeat();
}

// ---- MOTION: the MPU-6050, talked to directly over I2C ----
// Deliberately NO library: all we need is "which way is down and how hard
// is it being shaken", which is 6 bytes out of one register. Nothing for
// him to install, nothing to go out of date.

bool mpuWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

// reads the 3 acceleration axes, in g (1.0 = gravity)
bool mpuReadAccel(float& x, float& y, float& z) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);                       // ACCEL_XOUT_H
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)6) != 6) return false;
  int16_t rx = (Wire.read() << 8) | Wire.read();
  int16_t ry = (Wire.read() << 8) | Wire.read();
  int16_t rz = (Wire.read() << 8) | Wire.read();
  x = rx / 16384.0f;                      // +-2g range = 16384 counts per g
  y = ry / 16384.0f;
  z = rz / 16384.0f;
  return true;
}

// remember which way the box is hanging RIGHT NOW as "normal"
void motionLearn(const char* why) {
  float x, y, z;
  if (!mpuReadAccel(x, y, z)) { logErr("MOTION", "learn failed - no sensor"); return; }
  float m = sqrtf(x * x + y * y + z * z);
  if (m < 0.1f) { logErr("MOTION", "learn failed - sensor reads zero"); return; }
  baseX = x / m; baseY = y / m; baseZ = z / m;   // direction only
  tiltSince = 0;
  motionReadyAt = millis() + MOTION_SETTLE_MS;
  logOK("MOTION", String("baseline learned (") + why + ") - this is now 'not moved'");
}

void motionBegin() {
  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x75);                       // WHO_AM_I
  if (Wire.endTransmission(false) != 0 ||
      Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)1) != 1) {
    logErr("MOTION", "no MPU-6050 at 0x" + String(MPU_ADDR, HEX) +
                     " - check SDA 21 / SCL 22 / VCC / GND (AD0 high = 0x69)");
    mpuOk = false;
    return;
  }
  uint8_t who = Wire.read();
  mpuWrite(0x6B, 0x00);                   // wake it up (clears sleep bit)
  delay(100);
  mpuWrite(0x1C, 0x00);                   // accel range +-2g, most sensitive

  float x, y, z;
  mpuOk = mpuReadAccel(x, y, z);
  if (!mpuOk) { logErr("MOTION", "sensor found but will not read"); return; }

  logOK("MOTION", "MPU-6050 alive (WHO_AM_I 0x" + String(who, HEX) + "), reading " +
                  String(x, 2) + "/" + String(y, 2) + "/" + String(z, 2) + " g");
  motionLearn("boot");
}

// the actual watchdog: a hard knock, or a sustained change of angle
void pollMotion() {
  if (!mpuOk) return;
  static uint32_t lastRead = 0;
  uint32_t now = millis();
  if (now - lastRead < MOTION_MS) return;
  lastRead = now;

  float x, y, z;
  if (!mpuReadAccel(x, y, z)) return;

  float m = sqrtf(x * x + y * y + z * z);
  lastG = m;
  if (fabsf(m - 1.0f) > 0.08f) lastMotionAt = now;   // anything but resting

  // signed diff like lines 529/622 — a raw "now < deadline" dies at the
  // 49.7-day millis() rollover and silently disables jolt+tilt for weeks
  if ((int32_t)(now - motionReadyAt) < 0) return;  // still settling

  // angle between where it hangs now and the learned baseline
  float dot = (m > 0.1f) ? (x * baseX + y * baseY + z * baseZ) / m : 1.0f;
  if (dot >  1.0f) dot =  1.0f;
  if (dot < -1.0f) dot = -1.0f;
  lastTiltDeg = acosf(dot) * 57.2957795f;

  if (!alarmArmed) return;                // disarmed = don't cry about it
  if (alarmState == AS_SIREN) return;     // already screaming
  // A card tap quiets MOTION as well as the door. Someone who tapped is
  // about to handle the box, and a siren the moment they lean on it would
  // make the card look broken. Same for a box that has ZERO cards yet —
  // but one paired card is a tappable card, so one card = armed.
  if (inQuietPeriod() || unprotected()) return;

  // 1) JOLT - a real impact. Instant, no grace.
  if (fabsf(m - 1.0f) > MOTION_JOLT_G) {
    motionAlarm = true;
    startSiren("MOTION");
    logErr("MOTION", "IMPACT " + String(m, 2) + "g - siren NOW (no grace)");
    alarmBeat();
    return;
  }

  // 2) TILT - it is hanging at a new angle, and stayed there
  if (lastTiltDeg > MOTION_TILT_DEG) {
    if (tiltSince == 0) tiltSince = now;
    else if (now - tiltSince > MOTION_TILT_MS) {
      motionAlarm = true;
      startSiren("MOTION");
      logErr("MOTION", "MOVED " + String((int)lastTiltDeg) +
                       " deg off baseline - siren NOW (no grace)");
      alarmBeat();
      tiltSince = 0;
    }
  } else {
    tiltSince = 0;                        // back where it belongs
  }
}

// ================================================================
//  RFID — cards live in the BOX, not in the firmware.
//  Ported from CardDisarm.ino. Each box learns the cards that ship
//  with it, so ONE binary flashes every box and customer A's card
//  never opens customer B's box.
// ================================================================

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

void loadCards() {
  store.begin("freeisp", true);                // read-only
  cardCount = store.getUChar("n", 0);
  if (cardCount > MAX_CARDS) cardCount = 0;    // corrupt -> start clean
  for (uint8_t i = 0; i < cardCount; i++)
    cards[i] = store.getString(("card" + String(i)).c_str(), "");
  store.end();
}

void saveCard(const String& uid) {
  if (cardCount >= MAX_CARDS) return;
  cards[cardCount] = uid;
  store.begin("freeisp", false);
  store.putString(("card" + String(cardCount)).c_str(), uid);
  cardCount++;
  store.putUChar("n", cardCount);
  store.end();
}

// Forget the cards WITHOUT forgetting the armed state or the counts —
// store.clear() would wipe the whole namespace and silently re-arm a box
// the customer had switched off.
void forgetCards() {
  store.begin("freeisp", false);
  for (uint8_t i = 0; i < MAX_CARDS; i++)
    store.remove(("card" + String(i)).c_str());
  store.putUChar("n", 0);
  store.end();
  cardCount = 0;
  logOK("CARD", "all cards forgotten - box is back in ENROL mode, tap " +
                String(CARDS_PER_BOX) + " card(s) to pair it");
  beatPending = true;   // the fleet must SEE cards drop to 0, immediately
}

bool knownCard(const String& uid) {
  for (uint8_t i = 0; i < cardCount; i++)
    if (uid == cards[i]) return true;
  return false;
}

void cardBegin() {
#if RFID_WIRED
  // SPI is shared with the TFT (SCK 18 / MOSI 23 / MISO 19, different CS).
  // The TFT has already called SPI.begin() by now; calling PCD_Init here
  // is safe because both drivers use SPI transactions.
  rfid.PCD_Init();
  delay(50);
  byte v = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  if (v == 0x00 || v == 0xFF) {
    rc522Ok = false;
    logErr("CARD", "RC522 NOT ANSWERING - check 3.3V (NOT 5V), MISO 19, "
                   "SDA 16, RST 17, and that the header is soldered");
  } else {
    rc522Ok = true;
    // Clones boot with the receiver turned right down: SPI answers
    // perfectly while the radio is too weak to wake a card. "Alive" is
    // not "working" — force the gain or it reads nothing.
    rfid.PCD_SetAntennaGain(rfid.RxGain_max);
    rfid.PCD_AntennaOff();
    delay(20);
    rfid.PCD_AntennaOn();
    logOK("CARD", "RC522 alive (version 0x" + String(v, HEX) +
                  "), antenna gain MAX");
  }

  // cards were already loaded in setup(), before the door's boot state was
  // decided — an unpaired box must not boot straight into a siren
  logOK("CARD", String(cardCount) + " card(s) paired to this box" +
                (enrolling() ? "  >> ENROL MODE: tap the " +
                               String(CARDS_PER_BOX) + " cards that ship with it"
                             : ""));
#else
  logInfo("CARD", "RFID_WIRED=0 - no card reader");
#endif
}

void pollCards() {
#if RFID_WIRED
  if (!rc522Ok) return;
  uint32_t now = millis();

  // reader field watchdog — only speaks up when something is wrong
  static uint32_t lastPoke = 0;
  if (now - lastPoke >= 5000) {
    lastPoke = now;
    byte tx = rfid.PCD_ReadRegister(MFRC522::TxControlReg);
    if ((tx & 0x03) == 0) {                    // bits 0-1 = antenna drivers
      rfid.PCD_AntennaOn();
      rfid.PCD_SetAntennaGain(rfid.RxGain_max);
      logInfo("CARD", "RF field had dropped - turned back on");
    }
  }

  if (!rfid.PICC_IsNewCardPresent()) return;

  // A card the reader can start talking to but cannot finish reading
  // leaves the RC522 stuck mid-conversation - after which it ignores
  // EVERY card, the right one included, until a reboot. So always close
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
      logInfo("CARD", "a card confused the reader - reset, ready again");
    }
    return;
  }
  failCount = 0;

  String uid = uidToString(&rfid.uid);
  if (uid == lastUid && now - lastCardAt < 1500) {   // card left sitting on it
    rfid.PICC_HaltA();
    return;
  }
  lastUid    = uid;
  lastCardAt = now;
  // Every tap is reported, accepted or not. "Box 12 was opened Tuesday
  // 21:40 with card 2" is only possible if the box says WHICH card, and a
  // stranger standing at the pad trying cards is worth knowing about too.
  lastTapUid  = uid;
  lastTapOk   = knownCard(uid);
  lastTapAt   = now;
  beatPending = true;

  if (enrolling()) {
    if (knownCard(uid)) {
      logInfo("CARD", uid + " is already paired to this box");
    } else if (!doorOpen) {
      // Pairing needs PHYSICAL authority: the lid off. Otherwise whoever
      // taps first at first boot — through the closed lid, reader by the
      // wall — owns one of the box's 2 card slots.
      logErr("CARD", uid + " wants to pair - OPEN THE DOOR first (lid off = "
                     "you have the key, a passer-by does not)");
    } else {
      saveCard(uid);
      logOK("CARD", "PAIRED card " + String(cardCount) + " of " +
                    String(CARDS_PER_BOX) + ": " + uid);
      buzzHz = TONE_SIREN_B_HZ; buzz(true); delay(90); buzz(false);
      if (!enrolling()) logOK("CARD", ">> BOX IS PAIRED AND ARMED. Ship it.");
    }
  } else if (knownCard(uid)) {
    startQuiet(("card " + uid).c_str());
    buzzHz = TONE_SIREN_B_HZ;
    buzz(true); delay(70); buzz(false); delay(60);
    buzz(true); delay(70); buzz(false);
    if (!alarmRaised()) drawStatic();
  } else {
    // deliberately no reassuring beep for a stranger's card
    rejectCount++;
    nvsPut("rejects", rejectCount);
    logErr("CARD", "REJECTED " + uid + " - not this box's card, alarm continues");
    // Tapping strangers' cards at a screaming box must not run the clock
    // down: every rejected tap restarts the siren timer instead.
    if (alarmState == AS_SIREN) openedAt = millis();
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
#endif
}

// ================================================================
//  POWER — mains present + battery volts, straight off the board's
//  own dividers. Both nets are on-board, so no GPIO can see 12V.
// ================================================================
void powerBegin() {
#if POWER_WIRED
  // 11dB attenuation = the full ~0-3.1V span. The mains divider sits at
  // 2.55V and the battery at ~2.1V, so the default 0-1.1V range would
  // read both of them pinned at maximum and call a flat battery full.
  analogSetPinAttenuation(PIN_SENSE_MAINS, ADC_11db);
  analogSetPinAttenuation(PIN_SENSE_BATT,  ADC_11db);
  logOK("POWER", "sensing on GPIO34 (mains) + GPIO35 (battery)");
#else
  logInfo("POWER", "POWER_WIRED=0 - no mains or battery sensing");
#endif
}

void pollPower() {
#if POWER_WIRED
  static uint32_t lastRead = 0;
  uint32_t now = millis();
  if (now - lastRead < POWER_MS) return;
  lastRead = now;

  // analogReadMilliVolts applies the chip's own factory ADC calibration —
  // a raw analogRead() on an ESP32 is nonlinear enough to misjudge a
  // battery by several hundred mV.
  railV = analogReadMilliVolts(PIN_SENSE_MAINS) / 1000.0f * MAINS_DIV;
  battV = analogReadMilliVolts(PIN_SENSE_BATT)  / 1000.0f * BATT_DIV;
  powerOk = true;

  bool nowMains = (railV >= MAINS_PRESENT_V);
  if (nowMains != mainsOk) {
    mainsOk = nowMains;
    if (mainsOk) logOK ("POWER", "MAINS BACK - rail " + String(railV, 1) + "V");
    else         logErr("POWER", "MAINS LOST - running on battery, " +
                                 String(battV, 2) + "V");
    beatPending = true;            // a power cut is worth telling you about
  }

  static bool warnedLow = false;   // warn once per discharge, not every 2s
  if (!mainsOk && battV < BATT_LOW_V && !warnedLow) {
    warnedLow = true;
    logErr("POWER", "BATTERY LOW - " + String(battV, 2) + "V, box is about to die");
    beatPending = true;
  }
  if (mainsOk) warnedLow = false;
#endif
}

void pollDoor() {
  int raw = digitalRead(PIN_REED);
  if (raw != lastReedRaw) {
    lastReedRaw = raw;
    reedChangedAt = millis();
  } else if ((millis() - reedChangedAt) > DEBOUNCE_MS) {
    bool open = (raw != REED_CLOSED_LEVEL);
    if (open != doorOpen) onDoorChange(open);
  }
}

// drives the sound: chirp during grace, siren after it, then give up.
// NOTE: keyed off the alarm STATE, not the door — a motion alarm has to
// sound with the door still shut.
void pollBuzzer() {
  if (alarmState == AS_SECURE) return;
  uint32_t now = millis();

  switch (alarmState) {
    case AS_GRACE:
      if (now - openedAt >= GRACE_MS) {   // grace is over - escalate
        alarmState = AS_SIREN;
        beepAt = now;
        nextSirenNote();
        buzz(true);
        horn(true);                       // the horn only joins in for real
        logErr("ALARM", "grace expired - FULL SIREN");
        break;
      }
      // slow polite tick: short on, long off
      if (beepOn  && now - beepAt >= CHIRP_ON_MS)  { beepAt = now; buzz(false); }
      if (!beepOn && now - beepAt >= CHIRP_GAP_MS) {
        beepAt = now; buzzHz = TONE_CHIRP_HZ; buzz(true);
      }
      break;

    case AS_SIREN: {
      uint32_t maxMs = sirenMaxMs();      // motion runs on its own timer
      if (maxMs > 0 && now - openedAt >= maxMs) {
        alarmState = AS_SILENT;           // stop the noise, stay alarmed
        buzz(false);
        horn(false);
        logErr("ALARM", "siren timed out after " + String(maxMs / 1000) +
                        "s - still raised, screen + server stay red");
        // A box that was genuinely knocked to a new angle would otherwise
        // re-fire off the stale baseline every ~2 minutes forever. The
        // raised state is already persisted — the record is safe.
        if (motionAlarm && mpuOk) motionLearn("motion siren timed out");
        break;
      }
      if (now - beepAt >= BEEP_MS) {
        beepAt = now;
        if (motionAlarm) {
          // MOTION = continuous wail. The two notes swap with no silence
          // between them, so it never lets up. A box being torn off the
          // wall gets a harder sound than a lid being lifted.
          nextSirenNote();
          buzz(true);
        } else {
          if (!beepOn) nextSirenNote();   // each new beep = the other note
          buzz(!beepOn);
        }
      }
      break;
    }

    case AS_SILENT:
    default:
      break;                              // deliberately quiet
  }
}

void setArmed(bool on) {
  if (on == alarmArmed) return;
  alarmArmed = on;
  nvsPutArmed(on);                        // a power cut must not undo this
  if (!on) {                              // being switched off is worth counting
    disarmCount++;
    nvsPut("disarms", disarmCount);
  }
  logOK("CMD", on ? "alarm ARMED"
                  : "alarm DISARMED (disarm #" + String(disarmCount) + ")");
  // Disarming has to stop a MOTION siren too — that one rings with the
  // door still shut, so the old "only if the door is open" test left it
  // screaming after a disarm.
  if (!on) {
    alarmState = doorOpen ? AS_SILENT : AS_SECURE;
    if (alarmState == AS_SECURE) { alarmReason = ""; motionAlarm = false; }
    nvsPutRaised(0);                      // a disarmed box resumes nothing
    buzz(false);
    horn(false);
    drawStatic();
  } else if (doorOpen && !inQuietPeriod() && !unprotected()) {
    startSiren("DOOR");                   // arming onto an open door = alarm now
  }
  alarmBeat();
}

// shut the siren up but leave the alarm raised (door still logged OPEN)
void silenceSiren() {
  if (alarmState == AS_GRACE || alarmState == AS_SIREN) {
    alarmState = AS_SILENT;
    buzz(false);
    horn(false);
    disarmCount++;                        // silencing counts as a disarm
    nvsPut("disarms", disarmCount);
    logOK("CMD", "siren silenced (alarm still raised, disarm #" +
                 String(disarmCount) + ")");
  }
}

// a MOTION alarm has no "door closed" to reset it, so it needs an explicit
// all-clear. Refuses while the door is still open - that is the door's job.
void clearAlarm() {
  if (doorOpen) { logErr("CMD", "cannot clear - the door is still OPEN"); return; }
  alarmState  = AS_SECURE;
  alarmReason = "";
  motionAlarm = false;
  nvsPutRaised(0);
  buzz(false);
  horn(false);
  digitalWrite(PIN_LED_R, LOW);
  digitalWrite(PIN_LED_G, HIGH);
  if (mpuOk) motionLearn("alarm cleared");   // this angle is the new normal
  drawStatic();
  logOK("CMD", "alarm cleared - box secure again");
  alarmBeat();
}

// PULL OTA — the box fetches its own firmware from a URL the server sends.
// ArduinoOTA is push-from-the-IDE on the box's own LAN: useless for a box
// behind a customer's MikroTik 200km away. This rides the heartbeat command
// channel instead: the panel replies {"cmd":"update=https://.../fw.bin"},
// the box downloads, flashes the other OTA slot, reboots, and the next
// heartbeat's fw field proves the rollout landed.
void doPullUpdate(const String& url) {
  if (alarmRaised()) {           // never take the alarm down mid-incident
    logErr("OTA", "update refused - alarm is raised, try again when secure");
    return;
  }
  if (!url.startsWith("http")) { logErr("OTA", "bad update url: " + url); return; }
  logOK("OTA", "pull update from " + url);
  buzz(false);
  horn(false);
  esp_task_wdt_delete(NULL);     // the download takes longer than 30s
  httpUpdate.rebootOnUpdate(true);
  t_httpUpdate_return r;
  if (url.startsWith("https")) {
    WiFiClientSecure tls;
    tls.setInsecure();           // matches the heartbeat's ship-time posture
    r = httpUpdate.update(tls, url);
  } else {
    WiFiClient plain;
    r = httpUpdate.update(plain, url);
  }
  // success never returns (it reboots). Getting here = failure.
  logErr("OTA", "update failed (" + String((int)r) + "): " +
                httpUpdate.getLastErrorString());
  esp_task_wdt_add(NULL);        // back on watch
}

// run a command no matter where it came from (router note or server)
//   screen=on|off   alarm=arm|disarm|clear   siren=off|test
//   motion=learn    quiet=off    cards=clear   update=<url>
void runCommand(const String& cmdRaw) {
  String cmd = cmdRaw; cmd.toLowerCase(); cmd.trim();
  if (cmd.length() == 0) return;
  if      (cmd.indexOf("screen=off")   >= 0) setScreen(false);
  else if (cmd.indexOf("screen=on")    >= 0) setScreen(true);
  else if (cmd.indexOf("alarm=disarm") >= 0) setArmed(false);
  else if (cmd.indexOf("alarm=arm")    >= 0) setArmed(true);
  else if (cmd.indexOf("alarm=clear")  >= 0) clearAlarm();
  else if (cmd.indexOf("motion=learn") >= 0) motionLearn("command");
  // end a card's quiet hour early — the box goes straight back on guard
  else if (cmd.indexOf("quiet=off")    >= 0) {
    if (quietUntil) { quietUntil = 1; logOK("CMD", "quiet period cancelled"); }
    else            logInfo("CMD", "quiet=off but the box was not quiet");
  }
  // a customer who lost BOTH cards: forget them so replacements can pair.
  // Door-gated like clearAlarm(): a remote command (router note travels
  // over HTTP with router creds — default MikroTik passwords are endemic)
  // must not be able to turn an armed box into a silent shell from afar.
  else if (cmd.indexOf("cards=clear")  >= 0) {
    if (doorOpen) forgetCards();
    else logErr("CMD", "cards=clear refused - open the door first");
  }
  // ---- screen remote control (the panel's "android" mode) ----
  else if (cmd.indexOf("page=auto")    >= 0) {
    scrHold = 255; nvsSaveScreen();
    logOK("CMD", "screen back to auto-rotate");
  }
  else if (cmd.indexOf("page=")        >= 0) {
    int p = cmd.substring(cmd.indexOf("page=") + 5).toInt();
    if (p >= 0 && p < NUM_PAGES) {
      scrHold = p; page = p; nvsSaveScreen();
      if (screenOn) drawStatic();
      logOK("CMD", "screen HELD on page " + String(p));
    }
  }
  else if (cmd.indexOf("pages=")       >= 0) {
    // pages=10011 : one char per page, left = page 0
    String m = cmd.substring(cmd.indexOf("pages=") + 6);
    uint8_t mask = 0;
    for (uint8_t i = 0; i < NUM_PAGES && i < m.length(); i++)
      if (m[i] == '1') mask |= (1 << i);
    if (mask) {                        // never allow an all-off rotation
      scrMask = mask; nvsSaveScreen();
      logOK("CMD", "rotation pages set: " + m.substring(0, NUM_PAGES));
    } else logErr("CMD", "pages= would hide every page - ignored");
  }
  else if (cmd.indexOf("rotate=")      >= 0) {
    long s = cmd.substring(cmd.indexOf("rotate=") + 7).toInt();
    if (s >= 2 && s <= 60) {
      scrRotMs = (uint32_t)s * 1000; nvsSaveScreen();
      logOK("CMD", "page rotation every " + String(s) + "s");
    }
  }
  else if (cmd.indexOf("bright=")      >= 0) {
    long b = cmd.substring(cmd.indexOf("bright=") + 7).toInt();
    if (b >= 5 && b <= 100) {          // 5% floor: never invisibly dark
      scrBright = (uint8_t)b; nvsSaveScreen(); applyBright();
      logOK("CMD", "backlight " + String(b) + "%");
    }
  }
  else if (cmd.indexOf("poll=fast")    >= 0) {
    fastPollUntil = millis() + 300000UL;
    if (fastPollUntil == 0) fastPollUntil = 1;
    logOK("CMD", "fast poll: heartbeat every 2s for 5 min (panel is driving)");
  }
  else if (cmd.indexOf("poll=normal")  >= 0) {
    fastPollUntil = 0;
    logOK("CMD", "fast poll off");
  }
  else if (cmd.indexOf("update=")      >= 0) {
    // the URL must come from cmdRaw — cmd was lowercased and URLs care.
    // (cmd is also trimmed, so its indexes don't map back to cmdRaw.)
    String low = cmdRaw; low.toLowerCase();
    String url = cmdRaw.substring(low.indexOf("update=") + 7);
    url.trim();
    doPullUpdate(url);
  }
  else if (cmd.indexOf("siren=off")    >= 0) silenceSiren();
  else if (cmd.indexOf("siren=test")   >= 0) {
    logOK("CMD", "siren test - two notes");
    buzzHz = TONE_SIREN_A_HZ; buzz(true); delay(250);
    buzzHz = TONE_SIREN_B_HZ; buzz(true); delay(250);
    buzz(false);
  }
  else logErr("CMD", "unknown command: " + cmd);
}

// HEARTBEAT: report to Francis's server + collect any queued command.
// Works with http and https (setInsecure for now, tighten at ship).
// The same fail-streak backoff restGet() has, for the server. Without it,
// the moment SRV_URL points at a server that is down (WiFi up, WAN cut —
// the normal failure at a hotspot site) every 20s heartbeat on a SECURE
// box would block the loop for seconds: eaten card taps and missed jolts
// through the heartbeat door this time. Urgent beats (alarm events, set
// via beatPending) bypass the gate once — tamper still reports instantly.
uint32_t srvFailStreak = 0;
uint32_t srvNextTryAt  = 0;

void sendHeartbeat(bool urgent) {
  if (strlen(SRV_URL) == 0) return;              // feature off until URL set
  if (WiFi.status() != WL_CONNECTED) return;
  if (!urgent && srvNextTryAt &&
      (int32_t)(millis() - srvNextTryAt) < 0) return;   // backing off

  JsonDocument d;
  d["key"]     = SRV_KEY;
  d["box"]     = BOX_ID;
  d["fw"]      = "live-3.4";   // bump on every release: the panel watches
                               // this field change to confirm a rollout
  d["door"]    = doorOpen ? "OPEN" : "CLOSED";
  d["opens"]   = openCount;
  d["armed"]   = alarmArmed;
  d["alarm"]   = alarmStateName();
  d["why"]     = alarmReason;
  d["motion"]  = motionAlarm;
  d["tilt"]    = (int)lastTiltDeg;
  d["uptime"]  = millis() / 1000;
  d["hotspot"] = usersOnline;
  d["pppoe"]   = pppoeOnline;
  d["router"]  = routerOk;
  d["ip"]      = WiFi.localIP().toString();
  d["rssi"]    = WiFi.RSSI();
  // a box that has been silenced must say so, loudly and on every beat —
  // one that looks armed on the dashboard but is not is the worst state
  d["quiet"]   = quietSecsLeft();          // 0 = not quiet
  d["disarms"] = disarmCount;
  d["cards"]   = cardCount;
  d["horn"]    = HORN_WIRED ? hornOn : false;   // never claim a horn we have not got
  // power: -1 means "not wired / never read", so the server can tell the
  // difference between a dead battery and a box that has no sensing
  d["mains"]   = POWER_WIRED ? (mainsOk ? 1 : 0) : -1;
  d["rail"]    = powerOk ? railV : -1;
  d["batt"]    = powerOk ? battV : -1;
  // fleet telemetry: the fields that make a sick box visible from 200km.
  // Same -1 convention as mains: "not fitted" is different from "dead".
  // screen settings, so the panel's remote mirrors what the box is doing
  d["shold"]  = scrHold;                   // 255 = auto
  { char m[NUM_PAGES + 1];
    for (uint8_t i = 0; i < NUM_PAGES; i++) m[i] = (scrMask & (1 << i)) ? '1' : '0';
    m[NUM_PAGES] = 0;
    d["smask"] = m; }
  d["srot"]   = scrRotMs / 1000;
  d["sbri"]   = scrBright;
  d["scron"]  = screenOn;
  d["fast"]   = fastPolling();
  d["reset"]   = resetText;
  d["boots"]   = bootCount;
  d["crashes"] = crashCount;
  d["heap"]    = ESP.getFreeHeap();
  d["enrol"]   = enrolling();              // half-paired boxes must show
  d["mpu"]     = MOTION_WIRED ? (mpuOk ? 1 : 0) : -1;
  d["rc522"]   = RFID_WIRED ? (rc522Ok ? 1 : 0) : -1;
#if RFID_WIRED
  // WHICH cards this box obeys, so the panel can name them and say who
  // opened it — a count alone cannot tell card 1 from card 2.
  JsonArray uids = d["uids"].to<JsonArray>();
  for (uint8_t i = 0; i < cardCount; i++) uids.add(cards[i]);
  d["rejects"] = rejectCount;
  if (lastTapAt) {
    d["tap"]    = lastTapUid;
    d["tapok"]  = lastTapOk;
    d["tapago"] = (millis() - lastTapAt) / 1000;   // seconds ago
  }
#endif
  String body;
  serializeJson(d, body);

  HTTPClient http;
  WiFiClientSecure tls;
  bool isHttps = String(SRV_URL).startsWith("https");
  if (isHttps) { tls.setInsecure(); http.begin(tls, SRV_URL); }
  else         { http.begin(SRV_URL); }
  // Short timeouts ALWAYS — this shares the loop with the reed, the card
  // reader and the siren rhythm. A server that needs more than 2.5s is
  // down as far as this box is concerned. (Same reasoning as restGet.)
  http.setConnectTimeout(1500);
  http.setTimeout(2500);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);

  if (code != 200) {
    srvFailStreak++;
    if (srvFailStreak >= 3) {            // widen: 15s, 30s, 60s ... 5min cap
      uint32_t gap = (srvFailStreak - 3 >= 5) ? 300000UL
                                              : (15000UL << (srvFailStreak - 3));
      srvNextTryAt = millis() + gap;
      if (srvNextTryAt == 0) srvNextTryAt = 1;
    }
    if (srvFailStreak <= 3)              // say it, then stop repeating it
      logErr("BEAT", "heartbeat failed: " + httpExplain(code) +
                     (srvFailStreak == 3 ? "  (backing off now)" : ""));
    http.end();
    return;
  }
  if (srvFailStreak) logOK("BEAT", "server answering again after " +
                                   String(srvFailStreak) + " failure(s)");
  srvFailStreak = 0;
  srvNextTryAt  = 0;
  String resp = http.getString();
  http.end();

  JsonDocument r;
  if (deserializeJson(r, resp) == DeserializationError::Ok) {
    String cmd = (const char*)(r["cmd"] | "");
    if (cmd.length()) {
      logOK("BEAT", "server sent command: " + cmd);
      runCommand(cmd);
    } else {
      logOK("BEAT", "heartbeat delivered");
    }
  }
}

void fetchSystem() {
  JsonDocument doc;
  if (!restGet("SYS",
      "/rest/system/resource?.proplist=uptime,cpu-load,free-memory,total-memory,version,board-name",
      doc)) return;
  cpuLoad    = atoi(doc["cpu-load"] | "-1");
  freeMemMB  = strtoull(doc["free-memory"]  | "0", nullptr, 10) / 1048576.0f;
  totMemMB   = strtoull(doc["total-memory"] | "0", nullptr, 10) / 1048576.0f;
  rosVersion = (const char*)(doc["version"]    | "-");
  boardName  = (const char*)(doc["board-name"] | "-");
  rosUptime  = (const char*)(doc["uptime"]     | "-");
}

// ---- WiFi ----
const char* authName(wifi_auth_mode_t m) {
  switch (m) {
    case WIFI_AUTH_OPEN:            return "OPEN";
    case WIFI_AUTH_WEP:             return "WEP";
    case WIFI_AUTH_WPA_PSK:         return "WPA";
    case WIFI_AUTH_WPA2_PSK:        return "WPA2";
    case WIFI_AUTH_WPA_WPA2_PSK:    return "WPA/WPA2";
    case WIFI_AUTH_WPA3_PSK:        return "WPA3";
    case WIFI_AUTH_WPA2_WPA3_PSK:   return "WPA2/WPA3";
    default:                        return "other";
  }
}

bool scanForTarget() {
  logInfo("WIFI", "scanning for networks...");
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  int n = WiFi.scanNetworks(false, true);
  if (n <= 0) { logErr("WIFI", "scan found nothing"); return false; }
  bool found = false;
  logOK("WIFI", String(n) + " networks visible:");
  for (int i = 0; i < n; i++) {
    String ssid = WiFi.SSID(i);
    bool isTarget = (ssid == WIFI_SSID);
    if (isTarget) found = true;
    Serial.printf("   %s '%s'  ch%d  %ddBm  %s\n",
                  isTarget ? ">>>" : "   ",
                  ssid.length() ? ssid.c_str() : "(hidden)",
                  WiFi.channel(i), WiFi.RSSI(i),
                  authName(WiFi.encryptionType(i)));
  }
  if (!found)
    logErr("WIFI", String("'") + WIFI_SSID + "' not seen. Exact name? ch 1-11?");
  WiFi.scanDelete();
  return found;
}

void connectWiFi() {
  scanForTarget();
  logInfo("WIFI", String("connecting to '") + WIFI_SSID + "' ...");
  WiFi.mode(WIFI_STA);
  if (strlen(WIFI_PASS) == 0) WiFi.begin(WIFI_SSID);
  else {
    WiFi.setMinSecurity(WIFI_AUTH_WPA_PSK);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
  }
  esp_wifi_set_ps(WIFI_PS_NONE);   // stops ESP32 dozing off MikroTik APs

  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED)
    logOK("WIFI", "connected, IP = " + WiFi.localIP().toString() +
                  ", RSSI = " + String(WiFi.RSSI()) + " dBm" +
                  ", MAC = " + WiFi.macAddress());
  else
    logErr("WIFI", String("could NOT connect to '") + WIFI_SSID + "'");
}

// ---- screen helpers ----
// The chrome is drawn from tft.width()/height(), so the coming 3.5"
// panel inherits the whole look — only the page bodies assume 128x160.

// WiFi strength as 4 bars, like a phone's status bar
void wifiBars(int x, int y) {
  int rssi = (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : -127;
  uint8_t bars = rssi > -55 ? 4 : rssi > -65 ? 3 : rssi > -75 ? 2
               : rssi > -88 ? 1 : 0;
  for (uint8_t i = 0; i < 4; i++) {
    int h = 2 + i * 2;
    tft.fillRect(x + i * 3, y + 8 - h, 2, h,
                 i < bars ? C_GOOD : C_EDGE);
  }
}

// one dot that tells the room how the box feels
void statusDot(int x, int y) {
  uint16_t c = alarmRaised() ? C_BAD
             : (!alarmArmed || enrolling()) ? C_WARN : C_GOOD;
  tft.fillCircle(x, y, 3, c);
}

void titleBar(const char* t) {
  tft.fillScreen(C_BG);
  int w = tft.width();
  tft.fillRect(0, 0, w, 17, C_BAR);
  tft.drawFastHLine(0, 17, w, C_EDGE);       // hairline under the bar
  tft.setTextSize(1);
  tft.setTextColor(C_TITLE, C_BAR);
  tft.setCursor(4, 5);
  tft.print("FreeISP");
  tft.setTextColor(C_ACCENT, C_BAR);
  tft.setCursor(56, 5);
  tft.print(t);
  statusDot(w - 22, 8);
  wifiBars(w - 15, 4);
}

// the little page indicator dots along the bottom, phone-style
void pageDots() {
  int n = NUM_PAGES, gap = 10;
  int x0 = (tft.width() - (n - 1) * gap) / 2;
  int y  = tft.height() - 5;
  for (int i = 0; i < n; i++) {
    bool inRot = (scrMask & (1 << i)) || scrHold == i;
    if (i == page)      tft.fillCircle(x0 + i * gap, y, 2, C_ACCENT);
    else if (inRot)     tft.fillCircle(x0 + i * gap, y, 1, C_LABEL);
    else                tft.drawPixel (x0 + i * gap, y, C_EDGE);
  }
  if (scrHold < NUM_PAGES) {                 // held: say so, small
    tft.setTextSize(1);
    tft.setTextColor(C_LABEL, C_BG);
    tft.setCursor(2, tft.height() - 8);
    tft.print("*");
  }
}

// a rounded card panel — content sits a step above the background
void cardBox(int x, int y, int w, int h) {
  tft.fillRoundRect(x, y, w, h, 5, C_CARD);
  tft.drawRoundRect(x, y, w, h, 5, C_EDGE);
}

void label(int x, int y, const char* s) {    // on the plain background
  tft.setTextSize(1);
  tft.setTextColor(C_LABEL, C_BG);
  tft.setCursor(x, y);
  tft.print(s);
}

void labelCd(int x, int y, const char* s) {  // on a card panel
  tft.setTextSize(1);
  tft.setTextColor(C_LABEL, C_CARD);
  tft.setCursor(x, y);
  tft.print(s);
}

void value(int x, int y, uint8_t size, uint16_t color, const String& s,
           int boxW, uint16_t bg = C_BG) {
  tft.fillRect(x, y, boxW, size * 8, bg);
  tft.setTextSize(size);
  tft.setTextColor(color, bg);
  tft.setCursor(x, y);
  tft.print(s);
}

// horizontal bar meter with border
void bar(int x, int y, int w, int h, float frac, uint16_t color) {
  if (frac < 0) frac = 0;
  if (frac > 1) frac = 1;
  int fill = (int)(frac * (w - 2));
  tft.drawRect(x, y, w, h, C_LABEL);
  tft.fillRect(x + 1, y + 1, fill, h - 2, color);
  tft.fillRect(x + 1 + fill, y + 1, w - 2 - fill, h - 2, C_BG);
}

// ---- pages ----
void drawStatic() {
  if (page >= NUM_PAGES) {             // the ALARM banner page
    if (alarmRaised()) { drawAlarmBanner(); return; }
    page = NUM_PAGES - 1;              // alarm over — land on SECURITY
  }
  switch (page) {
    case 0: {
      titleBar("HOME");
      int w = tft.width();
      cardBox(4, 23, w / 2 - 7, 52);           // WIFI users
      cardBox(w / 2 + 3, 23, w / 2 - 7, 52);   // PPPOE users
      labelCd(10, 29, "WIFI");
      labelCd(w / 2 + 9, 29, "PPPOE");
      cardBox(4, 80, w - 8, 34);               // router strip
      labelCd(10, 86, "ROUTER");
      labelCd(62, 86, "UPTIME");
      break;
    }
    case 1:
      titleBar("PORTS");
      break;
    case 2:
      titleBar("TRAFFIC");
      label(4, 20, "DL");
      label(64, 20, "UL");
      label(118, 20, "Mbps");
      tft.drawRect(3, 34, tft.width() - 6, tft.height() - 38, C_LABEL);
      break;
    case 3:
      titleBar("SYSTEM");
      label(10, 24, "CPU");
      label(10, 52, "MEMORY FREE");
      label(10, 84, "ROUTER");
      label(10, 108, "BOX IP");
      label(10, 118, "POWER");
      break;
    case 4: {
      titleBar("SECURITY");
      int w = tft.width();
      cardBox(4, 23, w - 8, 38);               // door + armed
      labelCd(10, 29, "DOOR");
      labelCd(84, 29, "ALARM");
      cardBox(4, 65, w - 8, 36);               // the counters
      labelCd(10, 71, "OPENS");
      labelCd(54, 71, "DISARM");
      labelCd(98, 71, "TILT");
      label(10, 108, "STATE");
      label(10, 132, "CARDS");
      break;
    }
  }
  pageDots();
}

void drawLive() {
  if (page >= NUM_PAGES) {             // ALARM banner: live state + timer,
    uint32_t s = (millis() - openedAt) / 1000;   // so it's not a frozen page
    char b[24];
    snprintf(b, sizeof(b), "%-6s %lu:%02lu", alarmStateName(),
             (unsigned long)(s / 60), (unsigned long)(s % 60));
    tft.setTextSize(1);
    tft.setTextColor(ST77XX_WHITE, C_BAD);
    tft.setCursor(28, 100);
    tft.print(b);
    return;
  }
  heartbeat = !heartbeat;
  tft.fillCircle(tft.width() - 8, 8, 3, heartbeat ? C_GOOD : C_BAR);

  // A mains cut is too important to live on one page nobody may be looking
  // at, so it rides the title bar on EVERY page.
#if POWER_WIRED
  if (!mainsOk) {
    tft.setTextSize(1);
    tft.setTextColor(C_BAD, C_BAR);
    tft.setCursor(106, 4);
    tft.print("BATT");
  } else {
    tft.fillRect(106, 4, 30, 8, C_BAR);
  }
#endif

  switch (page) {
    case 0: {
      // the two numbers customers care about, each on its own card
      int w = tft.width();
      value(10, 41, 3, C_ACCENT,
            usersOnline < 0 ? "-" : String(usersOnline), w / 2 - 19, C_CARD);
      value(w / 2 + 9, 41, 3, C_GOOD,
            pppoeOnline < 0 ? "-" : String(pppoeOnline), w / 2 - 19, C_CARD);
      value(10, 98, 1, routerOk ? C_GOOD : C_BAD,
            routerOk ? "UP" : "DOWN", 40, C_CARD);
      value(62, 98, 1, C_VALUE, rosUptime, w - 72, C_CARD);
      if (!routerOk && lastErr.length())
        value(6, 122, 1, C_WARN, lastErr.substring(0, 20), w - 12);
      else
        tft.fillRect(6, 122, w - 12, 8, C_BG);
      break;
    }
    case 1:
      for (int i = 0; i < NPORTS; i++) {
        int y = 24 + i * 20;
        Port& p = ports[i];
        tft.fillCircle(7, y + 3, 3, !p.seen ? C_LABEL : (p.running ? C_GOOD : C_BAD));
        value(14, y, 1, C_VALUE, p.seen ? p.name : "...", 48);
        if (!p.seen)         value(66, y, 1, C_LABEL, "-", 90);
        else if (!p.running) value(66, y, 1, C_BAD, "down", 90);
        else value(66, y, 1, C_VALUE,
                   String(p.rxMbps, 1) + "/" + String(p.txMbps, 1) + " M", 90);
      }
      break;
    case 2: {
      value(20, 20, 1, C_GOOD,   String(ports[0].rxMbps, 1), 40);
      value(80, 20, 1, C_ACCENT, String(ports[0].txMbps, 1), 36);
      // axis strip on the left for the scale numbers, plot to its right
      int ax = 3, aw = 25;                        // axis strip x/width
      int gx = ax + aw, gy = 35;
      int gw = tft.width() - gx - 4, gh = tft.height() - 40;

      // scale follows the data: peak of what's on screen, rounded to a
      // friendly step (1/2/5/10/20/50/100...) so labels read naturally
      float peak = 1.0f;
      for (int i = HIST - gw; i < HIST; i++) {
        if (i < 0) continue;
        if (rxHist[i] > peak) peak = rxHist[i];
        if (txHist[i] > peak) peak = txHist[i];
      }
      const float steps[] = {1, 2, 5, 10, 20, 50, 100, 200, 500, 1000};
      float top = 1000;
      for (float s : steps) if (peak <= s) { top = s; break; }

      // axis labels: top / half / 0 (redrawn each frame, scale is live)
      tft.fillRect(ax, gy - 4, aw - 2, gh + 10, C_BG);
      tft.setTextSize(1);
      tft.setTextColor(C_LABEL, C_BG);
      tft.setCursor(ax, gy - 3);           tft.print((int)top);
      tft.setCursor(ax, gy + gh / 2 - 3);  tft.print(top >= 2 ? String((int)(top / 2)) : String(top / 2, 1));
      tft.setCursor(ax, gy + gh - 7);      tft.print("0");
      tft.drawRect(gx - 1, gy - 1, gw + 2, gh + 2, C_LABEL);

      tft.fillRect(gx, gy, gw, gh, C_BG);
      // faint mid gridline (bars draw over it)
      for (int x = gx; x < gx + gw; x += 6)
        tft.drawPixel(x, gy + gh / 2, C_BAR);
      for (int x = 0; x < gw && x < HIST; x++) {
        int idx = HIST - gw + x;
        if (idx < 0) continue;
        int hr = (int)(rxHist[idx] / top * (gh - 2));
        int ht = (int)(txHist[idx] / top * (gh - 2));
        if (hr > 0) tft.drawFastVLine(gx + x, gy + gh - hr, hr, C_GOOD);
        if (ht > 0) tft.drawFastVLine(gx + x, gy + gh - ht, ht > hr ? ht - hr : 1, C_ACCENT);
      }
      break;
    }
    case 3: {
      uint16_t cc = cpuLoad > 80 ? C_BAD : (cpuLoad > 50 ? C_WARN : C_GOOD);
      value(40, 24, 1, cc, cpuLoad < 0 ? "-" : String(cpuLoad) + "%", 40);
      bar(10, 34, 140, 10, cpuLoad / 100.0f, cc);

      float usedFrac = (totMemMB > 0) ? 1.0f - freeMemMB / totMemMB : 0;
      value(90, 52, 1, C_VALUE,
            freeMemMB < 0 ? "-" : String(freeMemMB, 0) + "/" + String(totMemMB, 0) + "MB", 66);
      bar(10, 62, 140, 10, usedFrac, usedFrac > 0.85f ? C_BAD : C_GOOD);

      value(10, 94, 1, C_VALUE, boardName + "  v" + rosVersion, 150);
      value(56, 108, 1, C_VALUE,
            WiFi.status() == WL_CONNECTED
              ? WiFi.localIP().toString() + "  " + String(WiFi.RSSI()) + "dBm"
              : "no wifi", 104);
      value(56, 118, 1,
            !POWER_WIRED ? C_LABEL : (!mainsOk ? C_BAD :
                                      (battV > 0 && battV < BATT_LOW_V ? C_WARN : C_GOOD)),
            !POWER_WIRED ? "not wired"
                         : (!powerOk ? "reading..."
                                     : String(mainsOk ? "MAINS " : "BATTERY ") +
                                       String(battV, 2) + "V"), 104);
      break;
    }
    case 4: {
      value(10, 41, 2, doorOpen ? C_BAD : C_GOOD,
            doorOpen ? "OPEN" : "CLOSED", 72, C_CARD);
      value(84, 44, 1, alarmArmed ? C_GOOD : C_WARN,
            alarmArmed ? "ARMED" : "OFF", 38, C_CARD);
      value(10, 83, 2, C_VALUE, String(openCount), 40, C_CARD);
      value(54, 83, 2, disarmCount ? C_WARN : C_VALUE, String(disarmCount), 40, C_CARD);
      value(98, 85, 1, mpuOk ? (lastTiltDeg > MOTION_TILT_DEG ? C_BAD : C_VALUE) : C_LABEL,
            mpuOk ? (String((int)lastTiltDeg) + "d") : "--", 24, C_CARD);

      // The bottom line must never let a silenced box look armed. A quiet
      // period or a disarm outranks the siren state here on purpose: those
      // are the states someone standing at the box needs to see.
      String st; uint16_t stc;
      if (inQuietPeriod()) {
        uint32_t s = quietSecsLeft();
        char b[20];
        snprintf(b, sizeof(b), "QUIET %lu:%02lu",
                 (unsigned long)(s / 60), (unsigned long)(s % 60));
        st = b; stc = C_WARN;
      } else if (!alarmArmed)              { st = "DISARMED";     stc = C_WARN;  }
        else if (alarmState == AS_SIREN)   { st = "SOUNDING";     stc = C_BAD;   }
        else if (alarmState == AS_GRACE)   { st = "grace...";     stc = C_WARN;  }
        else if (alarmState == AS_SILENT)  { st = "silenced";     stc = C_WARN;  }
        else                               { st = "armed, quiet"; stc = C_LABEL; }
      value(10, 118, 1, stc, st, tft.width() - 20);
      // cards, because a half-paired box must never look ready
      value(10, 142, 1, enrolling() ? C_WARN : C_LABEL,
            String(cardCount) + "/" + String(CARDS_PER_BOX) +
            (enrolling() ? " ENROL" : " paired"), tft.width() - 20);
      break;
    }
  }
}

// ================================================================
//  OTA — update the box over WiFi instead of over a cable.
//
//  It stays OFF until OTA_PASS is set in secrets.h. An open OTA port on
//  a box sitting in someone else's shop is a way to hand a stranger the
//  firmware, and the whole point of these boxes is that the firmware is
//  the product. No password, no OTA — deliberately, not accidentally.
// ================================================================
bool otaReady    = false;
bool otaDisabled = false;   // decided once, so loop() stops asking

void otaBegin() {
  if (otaDisabled || otaReady) return;
  if (strlen(OTA_PASS) == 0) {
    otaDisabled = true;     // say it ONCE, not on every pass of loop()
    logInfo("OTA", "OTA_PASS empty in secrets.h - OTA off (cable only)");
    return;
  }
  if (WiFi.status() != WL_CONNECTED) return;   // retry after it connects
  ArduinoOTA.setHostname(BOX_ID);
  ArduinoOTA.setPassword(OTA_PASS);

  // The alarm must not be left mid-note by an update, and a half-written
  // flash must not leave a box that boots into a siren.
  ArduinoOTA.onStart([]() {
    buzz(false);
    horn(false);
    esp_task_wdt_delete(NULL);   // a slow upload must not trip the watchdog
    logOK("OTA", "update starting - alarm outputs released");
  });
  ArduinoOTA.onEnd([]()  { logOK("OTA", "update done, rebooting"); });
  ArduinoOTA.onError([](ota_error_t e) {
    logErr("OTA", "update failed, error " + String((int)e));
  });
  ArduinoOTA.begin();
  otaReady = true;
  logOK("OTA", String("ready as '") + BOX_ID + "' on " +
               WiFi.localIP().toString());
}

// ================================================================
//  STATUS BLOCK — every part of the box, in one place, every 30s.
//  The router is only ONE line of this; when it is down the rest of
//  the box is still working and you should be able to see that.
// ================================================================
void statusRow(const char* name, bool wired, bool ok, const String& detail) {
  Serial.printf("   %-7s %s  %s\n", name,
                !wired ? "--" : (ok ? "OK" : "!!"), detail.c_str());
}

void printStatus() {
  Serial.println();
  Serial.printf("---------- STATUS @ %lus ----------\n", millis() / 1000);

  bool wifiUp = (WiFi.status() == WL_CONNECTED);
  statusRow("WIFI", true, wifiUp,
            wifiUp ? WiFi.localIP().toString() + "  " + String(WiFi.RSSI()) + "dBm  ch" +
                     String(WiFi.channel()) + "  " + String(WIFI_SSID)
                   : "disconnected");

  statusRow("ROUTER", true, routerOk,
            routerOk ? routerHost() + "  " + boardName + " v" + rosVersion +
                       "  cpu " + String(cpuLoad) + "%  up " + rosUptime
                     : (restFailStreak ? "no reply (" + String(restFailStreak) +
                                         " failed, last: " + lastErr + ")"
                                       : "not read yet"));

  if (routerOk) {
    String pl = "";
    for (int i = 0; i < NPORTS; i++)
      if (ports[i].seen) pl += ports[i].name + (ports[i].running ? "=up " : "=DOWN ");
    statusRow("PORTS", true, true, pl.length() ? pl : "none read");
    statusRow("USERS", true, true, String(usersOnline) + " hotspot, " +
                                   String(pppoeOnline) + " pppoe");
  }

  statusRow("SCREEN", true, screenOn,
            screenOn ? (page >= NUM_PAGES
                          ? String("on, ALARM banner page")
                          : "on, page " + String(page + 1) + "/" + String(NUM_PAGES))
                     : "off (screen=on to wake it)");

  statusRow("DOOR", ALARM_WIRED, !doorOpen,
            !ALARM_WIRED ? "ALARM_WIRED=0, reed not read"
                         : String(doorOpen ? "OPEN" : "CLOSED") +
                           "  " + String(alarmArmed ? "ARMED" : "DISARMED") +
                           "  " + alarmStateName() +
                           "  opens=" + String(openCount) +
                           "  disarms=" + String(disarmCount));

  statusRow("MOTION", MOTION_WIRED, mpuOk,
            !MOTION_WIRED ? "MOTION_WIRED=0, no sensor"
                          : (mpuOk ? String(lastTiltDeg, 0) + " deg off baseline, " +
                                     String(lastG, 2) + "g"
                                   : "MPU-6050 not answering on 21/22"));

  statusRow("CARDS", RFID_WIRED, rc522Ok,
            !RFID_WIRED ? "RFID_WIRED=0, no reader"
                        : (!rc522Ok ? "RC522 not answering on 16/17"
                                    : String(cardCount) + "/" + String(CARDS_PER_BOX) +
                                      " paired" + (enrolling() ? "  >> ENROL MODE" : "")));

  statusRow("QUIET", RFID_WIRED, !inQuietPeriod(),
            !RFID_WIRED ? "no reader, nothing can buy quiet"
                        : (inQuietPeriod()
                             ? "SILENCED - " + String(quietSecsLeft() / 60) + "m" +
                               String(quietSecsLeft() % 60) + "s left"
                             : "armed, nothing silenced"));

  statusRow("POWER", POWER_WIRED, mainsOk,
            !POWER_WIRED ? "POWER_WIRED=0, no mains/battery sensing"
                         : (!powerOk ? "not read yet"
                                     : String(mainsOk ? "MAINS OK" : "ON BATTERY") +
                                       "  rail " + String(railV, 1) + "V" +
                                       "  batt " + String(battV, 2) + "V"));

  statusRow("HORN", HORN_WIRED, !hornOn,
            !HORN_WIRED ? "HORN_WIRED=0, relay pin idle"
                        : (hornOn ? "SOUNDING" : "quiet, relay released"));

  statusRow("SERVER", strlen(SRV_URL) > 0, !beatPending,
            strlen(SRV_URL) == 0 ? "SRV_URL empty in secrets.h - reporting off"
                                 : String(SRV_URL) + (beatPending ? "  (beat queued)" : ""));

  statusRow("MEMORY", true, ESP.getFreeHeap() > 40000,
            String(ESP.getFreeHeap() / 1024) + " KB heap free");

  Serial.println("------------------------------------");
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println("==========================================");
  Serial.println(" LiveDashboardNext - dashboard + alarm");
  Serial.println(" users + ports + traffic + system + door");
  Serial.println(" + horn + cards + power + memory + OTA");
  Serial.println("==========================================");

  // Backlight is PWM from day one: brightness is a remote setting.
  // Core 3.x dropped the channel-based LEDC calls for pin-based ones.
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(TFT_BLK, 5000, 8);
#else
  ledcSetup(BLK_LEDC_CH, 5000, 8);
  ledcAttachPin(TFT_BLK, BLK_LEDC_CH);
#endif
  blkWrite(255);                     // full bright until NVS is read

  // WHY did this boot happen? A box that brownouts on every siren, or
  // crash-loops on heap exhaustion, otherwise looks perfectly healthy —
  // small uptime is the only clue and nobody is watching for it.
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON:   resetText = "POWERON";  break;
    case ESP_RST_SW:        resetText = "SW";       break;
    case ESP_RST_PANIC:     resetText = "PANIC";    break;
    case ESP_RST_TASK_WDT:  resetText = "TASK_WDT"; break;
    case ESP_RST_INT_WDT:   resetText = "INT_WDT";  break;
    case ESP_RST_WDT:       resetText = "WDT";      break;
    case ESP_RST_BROWNOUT:  resetText = "BROWNOUT"; break;
    case ESP_RST_DEEPSLEEP: resetText = "SLEEP";    break;
    default:                resetText = "OTHER";    break;
  }
  Serial.printf("[BOOT] reset reason: %s\n", resetText);

  // What the box remembers comes FIRST: everything below (including the
  // boot self-test and the door's opening state) depends on whether this
  // box is supposed to be armed at all.
  nvsLoadState();
  bootCount++;
  nvsPut("boots", bootCount);
  applyBright();                     // the remembered brightness, now
  bool crashed = (esp_reset_reason() == ESP_RST_PANIC   ||
                  esp_reset_reason() == ESP_RST_TASK_WDT ||
                  esp_reset_reason() == ESP_RST_INT_WDT  ||
                  esp_reset_reason() == ESP_RST_WDT      ||
                  esp_reset_reason() == ESP_RST_BROWNOUT);
  if (crashed) { crashCount++; nvsPut("crashes", crashCount); }
  Serial.printf("[BOOT] boot #%lu, %lu crash-boots ever\n",
                (unsigned long)bootCount, (unsigned long)crashCount);
#if RFID_WIRED
  loadCards();          // needed before the door's boot state is decided
#endif

#if HORN_WIRED
  // Drive the relay to its OFF level BEFORE making the pin an output.
  // The other order leaves the pin briefly at 0 on an active-low board,
  // which is a horn blast every time the box powers up.
  digitalWrite(PIN_RELAY, RELAY_ACTIVE_HIGH ? LOW : HIGH);
  pinMode(PIN_RELAY, OUTPUT);
  digitalWrite(PIN_RELAY, RELAY_ACTIVE_HIGH ? LOW : HIGH);
  hornOn = false;
  Serial.println("[BOOT] HORN_WIRED=1 - relay on GPIO13, released");
#else
  Serial.println("[BOOT] HORN_WIRED=0 - horn relay pin not touched");
#endif

#if ALARM_WIRED
  // alarm hardware + POWER-ON SELF TEST: both LEDs light, buzzer chirps
  // once — so after wiring each part, a reboot instantly proves it works
  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_BUZZ,  OUTPUT);
  pinMode(PIN_REED,  INPUT_PULLUP);
  buzz(false);                       // make sure it starts quiet
  digitalWrite(PIN_LED_R, HIGH);
  digitalWrite(PIN_LED_G, HIGH);
  buzzHz = TONE_SIREN_A_HZ;  buzz(true);  delay(120);  buzz(false);
  delay(600);
  digitalWrite(PIN_LED_R, LOW);
  digitalWrite(PIN_LED_G, LOW);

  int raw = digitalRead(PIN_REED);
  Serial.printf("[BOOT] reed raw = %d  (%s)\n", raw,
                raw == REED_CLOSED_LEVEL ? "door CLOSED" : "door OPEN");
#endif

#if MOTION_WIRED
  motionBegin();          // finds the sensor, wakes it, learns "not moved"
#else
  Serial.println("[BOOT] MOTION_WIRED=0 - no motion sensing");
#endif

#if ALARM_WIRED
  Serial.printf("[BOOT] alarm %s, grace %lus, siren max %lus\n",
                alarmArmed ? "ARMED" : "DISARMED",
                (unsigned long)(GRACE_MS / 1000),
                (unsigned long)(SIREN_MAX_MS / 1000));
  doorOpen = (raw != REED_CLOSED_LEVEL);
  lastReedRaw = raw;
  reedChangedAt = millis();
  openedAt = millis();
  // A box with ZERO cards paired must NOT boot into a siren — whoever is
  // setting it up has nothing to tap to stop it. One card IS tappable.
  alarmState = (doorOpen && alarmArmed && !unprotected())
                 ? (GRACE_MS > 0 ? AS_GRACE : AS_SIREN)
                 : (doorOpen ? AS_SILENT : AS_SECURE);
  if (doorOpen) alarmReason = "DOOR";
  // RESUME a raised alarm across a power cut. Yanking the battery or
  // poking the exposed EN button used to convert a screaming box into a
  // politely chirping one with a fresh grace — the grace was already
  // spent, so a raised flag in NVS means straight back to the siren.
  if (bootRaisedWhy && alarmArmed && !unprotected()) {
    alarmReason = (bootRaisedWhy == 2) ? "MOTION" : "DOOR";
    if (doorOpen || bootRaisedWhy == 2) {
      alarmState = AS_SIREN;             // no second grace
      openedAt = millis(); beepAt = millis();
      nextSirenNote(); buzz(true); horn(true);
      Serial.println("[BOOT] alarm was RAISED when power died - siren RESUMES");
    } else {
      alarmState = AS_SILENT;            // door shut again: silent but red
      Serial.println("[BOOT] alarm was RAISED when power died - staying red");
    }
    digitalWrite(PIN_LED_R, HIGH);
    digitalWrite(PIN_LED_G, LOW);
    beatPending = true;                  // the fleet hears about it at once
  } else {
    digitalWrite(PIN_LED_R, doorOpen ? HIGH : LOW);
    digitalWrite(PIN_LED_G, doorOpen ? LOW : HIGH);
  }
#else
  Serial.println("[BOOT] ALARM_WIRED=0 - dashboard only, alarm parts ignored");
#endif

  tft.initR(SCREEN_TAB);
  tft.setRotation(SCREEN_ROT);
  titleBar("BOOT");

  // AFTER the TFT: both share the SPI bus, and the reader's init is
  // cleaner once the display driver has already claimed and configured it.
  cardBegin();
  powerBegin();

  connectWiFi();
  otaBegin();

  // first data before the first page shows
  fetchPorts();
  fetchUsers();
  fetchSystem();
  printStatus();                   // one full picture before the pages start
  if (alarmRaised()) { showAlarmBanner(); }
  else               { drawStatic(); }

  // WATCHDOG last, after all the blocking boot work (WiFi scan, first
  // fetches). If loop() ever wedges — a trickling HTTP server, an I2C
  // lockup, heap exhaustion — the box reboots in 30s instead of hanging
  // forever as a dead alarm that still looks armed on the wall. The
  // reboot is loud in the heartbeat: reset=TASK_WDT, crashes+1.
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  { esp_task_wdt_config_t wcfg = { .timeout_ms = 30000,
      .idle_core_mask = 0, .trigger_panic = true };
    esp_task_wdt_reconfigure(&wcfg); }
#else
  esp_task_wdt_init(30, true);
#endif
  esp_task_wdt_add(NULL);
  Serial.println("[BOOT] task watchdog armed: 30s, panic = reboot");
}

void loop() {
  esp_task_wdt_reset();     // fed once per pass; a wedge anywhere = reboot
  uint32_t now = millis();

#if ALARM_WIRED
  // alarm checks run EVERY pass — never blocked by network calls
  pollDoor();
  pollBuzzer();
#endif
#if MOTION_WIRED
  pollMotion();
#endif
  pollCards();       // a card tap must land even while the siren is going
  pollQuiet();       // ...and the hour it buys has to be able to run out
  pollPower();       // mains/battery, cheap: two ADC reads every 2s

  static uint32_t lastWifiTry = 0;
  if (WiFi.status() != WL_CONNECTED && now - lastWifiTry > 15000) {
    lastWifiTry = now;
    logInfo("WIFI", "link down, reconnecting...");
    WiFi.disconnect();
    if (strlen(WIFI_PASS) == 0) WiFi.begin(WIFI_SSID);
    else                        WiFi.begin(WIFI_SSID, WIFI_PASS);
  }
  if (otaReady) ArduinoOTA.handle();
  else if (!otaDisabled && WiFi.status() == WL_CONNECTED) otaBegin();  // after a reconnect

  if (now - lastPoll  >= POLL_MS)  { lastPoll  = now; fetchPorts();   }
  if (now - lastUsers >= USERS_MS) { lastUsers = now; fetchUsers();   }
  if (now - lastSys   >= SYS_MS)   { lastSys   = now; fetchSystem();  }
  if (now - lastCmd   >= CMD_MS)   { lastCmd   = now; fetchCommand();  }

  // An alarm asked for an instant report. Send it HERE, not from inside
  // the alarm code, so the siren has already been running for a full pass
  // of the loop before we go anywhere near the network.
  // event beats are urgent: they bypass the server backoff gate once.
  // While the panel is driving the screen (poll=fast) the cadence drops
  // to 2s so a tap on the panel lands in ~2s, not ~20.
  uint32_t heartGap = fastPolling() ? 2000 : HEART_MS;
  if (beatPending) { beatPending = false; lastBeat = now; sendHeartbeat(true); }
  else if (now - lastBeat >= heartGap) { lastBeat = now; sendHeartbeat(false); }

  if (now - lastStatus >= STATUS_MS) { lastStatus = now; printStatus(); }

  if (!screenOn) return;           // data keeps flowing, drawing paused

  // While the alarm is raised the red banner joins the rotation as an
  // extra page instead of freezing the screen — the dashboard keeps
  // cycling so you can still see users/ports/router while it cries.
  // An alarm also overrides a held page and the page mask: nothing the
  // owner set from the panel may hide a box that is crying.
  uint8_t numPages = NUM_PAGES + (alarmRaised() ? 1 : 0);
  bool held = (scrHold < NUM_PAGES) && !alarmRaised();
  if (!held && now - lastPage >= scrRotMs) {
    lastPage = now;
    for (uint8_t hop = 0; hop < numPages; hop++) {   // skip masked-out pages
      page = (page + 1) % numPages;
      if (page >= NUM_PAGES || (scrMask & (1 << page))) break;
    }
    drawStatic();
  }
  if (now - lastLive >= LIVE_MS) {
    lastLive = now;
    drawLive();
  }
}
