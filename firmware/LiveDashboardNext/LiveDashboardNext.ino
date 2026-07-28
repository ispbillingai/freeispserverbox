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
    - REMOTE COMMANDS from either the router note or the server:
        screen=on | screen=off | alarm=arm | alarm=disarm
        siren=off (shut it up, stay alarmed) | siren=test

  Needs: secrets.h next to this file, ArduinoJson library.
  Board = "ESP32 Dev Module", COM6, hold BOOT while uploading.
  Serial Monitor @ 115200.
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
#include "secrets.h"

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
#define ALARM_WIRED 0

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

// Kit buzzers sound when the pin goes HIGH. Some buzzer *modules*
// (3-pin, with a transistor) sound on LOW — set this to 0 for those.
#define BUZZER_ACTIVE_HIGH 1

// ---- how the alarm behaves ----
#define ALARM_ARMED_AT_BOOT 1     // 1 = live the moment it powers up
                                  // 0 = boots quiet, arm it with a command

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

// ---- what the alarm reports ----
#define ALARM_BEAT_ON_CHANGE 1    // 1 = push an instant heartbeat to the server
                                  //     the moment the door opens/closes
// ================================================================

Adafruit_ST7735 tft(TFT_CS, TFT_DC, TFT_RST);

// ---- colors (RGB565) ----
#define C_BG      ST77XX_BLACK
#define C_BAR     0x0339
#define C_TITLE   ST77XX_WHITE
#define C_LABEL   0x8C71
#define C_VALUE   ST77XX_WHITE
#define C_GOOD    0x07E8
#define C_BAD     0xF965
#define C_ACCENT  0x07FF
#define C_WARN    0xFFE0

const uint32_t PAGE_MS   = 5000;   // page rotate
const uint32_t POLL_MS   = 2000;   // ethernet counters (drives the graph)
const uint32_t USERS_MS  = 5000;   // hotspot active users
const uint32_t SYS_MS    = 10000;  // cpu/memory/uptime
const uint32_t CMD_MS    = 3000;   // remote-command check (router system note)
const uint32_t HEART_MS  = 20000;  // heartbeat to Francis's server
const uint32_t LIVE_MS   = 500;    // screen repaint

const uint8_t NUM_PAGES = 5;

// ---- state ----
uint8_t  page = 0;
uint32_t lastPage = 0, lastPoll = 0, lastUsers = 0, lastSys = 0, lastLive = 0, lastCmd = 0, lastBeat = 0;
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

// one shared REST GET: fills doc, returns true on success, logs failures
bool restGet(const char* tag, const String& path, JsonDocument& doc) {
  if (WiFi.status() != WL_CONNECTED) { lastErr = "no WiFi"; return false; }

  HTTPClient http;
  String host = routerHost();
  http.setConnectTimeout(3000);
  http.setTimeout(8000);
  http.begin(String("http://") + host + path);
  http.setAuthorization(MT_USER, MT_PASS);
  uint32_t t0 = millis();
  int code = http.GET();
  uint32_t took = millis() - t0;

  if (code != 200) {
    lastErr = httpExplain(code);
    String peek = (code > 0) ? http.getString().substring(0, 120) : "";
    logErr(tag, "GET " + path + " on " + host + " failed after " +
                String(took) + "ms: " + lastErr +
                (peek.length() ? ("  reply: " + peek) : ""));
    http.end();
    return false;
  }
  String body = http.getString();
  http.end();

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
  digitalWrite(TFT_BLK, on ? HIGH : LOW);
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
  // only treat the note as a command if it looks like one ("thing=value"),
  // so a normal note left on the router doesn't spam the log
  if (note.indexOf('=') >= 0) runCommand(note);   // same list as the server
}

// ---- door alarm (GOLDEN RULE: fires locally FIRST, server second) ----

// one place that knows which way round the buzzer is wired
void buzz(bool on) {
  beepOn = on;
  digitalWrite(PIN_BUZZ, (on == (BUZZER_ACTIVE_HIGH != 0)) ? HIGH : LOW);
}

void drawAlarmBanner() {
  tft.fillScreen(C_BAD);
  tft.setTextSize(3);
  tft.setTextColor(ST77XX_WHITE, C_BAD);
  tft.setCursor(18, 40);
  tft.print("ALARM");
  tft.setTextSize(1);
  tft.setCursor(28, 80);
  tft.print("DOOR IS OPEN");
}

void alarmBeat() {
#if ALARM_BEAT_ON_CHANGE
  sendHeartbeat();
#endif
}

void onDoorChange(bool open) {
  doorOpen = open;
  // 1) LOCAL response, instant, works with no WiFi at all
  digitalWrite(PIN_LED_R, open ? HIGH : LOW);
  digitalWrite(PIN_LED_G, open ? LOW : HIGH);

  if (open) {
    openCount++;
    openedAt = millis();
    beepAt   = millis();

    if (!alarmArmed) {                  // disarmed = you opened it on purpose
      alarmState = AS_SILENT;
      buzz(false);
      logInfo("ALARM", "door OPEN but alarm is DISARMED - staying quiet");
    } else if (GRACE_MS > 0) {          // chirp first, siren after the grace
      alarmState = AS_GRACE;
      buzz(true);
      if (!screenOn) setScreen(true);   // alarm overrides screen-off
      drawAlarmBanner();
      logErr("ALARM", "door OPEN (count=" + String(openCount) + ") - " +
                      String(GRACE_MS / 1000) + "s grace, then siren");
    } else {                            // no grace configured = straight to it
      alarmState = AS_SIREN;
      buzz(true);
      if (!screenOn) setScreen(true);
      drawAlarmBanner();
      logErr("ALARM", "door OPEN (count=" + String(openCount) + ") - siren ON");
    }
  } else {
    alarmState = AS_SECURE;
    buzz(false);
    drawStatic();
    logOK("ALARM", "door CLOSED - siren OFF, box secure");
  }
  // 2) THEN tell the server (best effort, carried by an instant heartbeat)
  alarmBeat();
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

// drives the sound: chirp during grace, siren after it, then give up
void pollBuzzer() {
  if (!doorOpen) return;
  uint32_t now = millis();

  switch (alarmState) {
    case AS_GRACE:
      if (now - openedAt >= GRACE_MS) {   // grace is over - escalate
        alarmState = AS_SIREN;
        beepAt = now;
        buzz(true);
        logErr("ALARM", "grace expired - FULL SIREN");
        break;
      }
      // slow polite tick: short on, long off
      if (beepOn  && now - beepAt >= CHIRP_ON_MS)  { beepAt = now; buzz(false); }
      if (!beepOn && now - beepAt >= CHIRP_GAP_MS) { beepAt = now; buzz(true);  }
      break;

    case AS_SIREN:
      if (SIREN_MAX_MS > 0 && now - openedAt >= SIREN_MAX_MS) {
        alarmState = AS_SILENT;           // stop the noise, stay alarmed
        buzz(false);
        logErr("ALARM", "siren timed out after " + String(SIREN_MAX_MS / 1000) +
                        "s - still OPEN, screen + server stay red");
        break;
      }
      if (now - beepAt >= BEEP_MS) { beepAt = now; buzz(!beepOn); }
      break;

    case AS_SILENT:
    default:
      break;                              // deliberately quiet
  }
}

void setArmed(bool on) {
  if (on == alarmArmed) return;
  alarmArmed = on;
  logOK("CMD", on ? "alarm ARMED" : "alarm DISARMED");
  if (!on && doorOpen) {                  // disarming shuts a running siren up
    alarmState = AS_SILENT;
    buzz(false);
    drawStatic();
  } else if (on && doorOpen) {            // arming onto an open door = alarm now
    alarmState = AS_SIREN;
    openedAt = millis();
    beepAt   = millis();
    buzz(true);
    if (!screenOn) setScreen(true);
    drawAlarmBanner();
  }
  alarmBeat();
}

// shut the siren up but leave the alarm raised (door still logged OPEN)
void silenceSiren() {
  if (alarmState == AS_GRACE || alarmState == AS_SIREN) {
    alarmState = AS_SILENT;
    buzz(false);
    logOK("CMD", "siren silenced (door still OPEN)");
  }
}

// run a command no matter where it came from (router note or server)
//   screen=on|off     alarm=arm|disarm     siren=off     siren=test
void runCommand(const String& cmdRaw) {
  String cmd = cmdRaw; cmd.toLowerCase(); cmd.trim();
  if (cmd.length() == 0) return;
  if      (cmd.indexOf("screen=off")   >= 0) setScreen(false);
  else if (cmd.indexOf("screen=on")    >= 0) setScreen(true);
  else if (cmd.indexOf("alarm=disarm") >= 0) setArmed(false);
  else if (cmd.indexOf("alarm=arm")    >= 0) setArmed(true);
  else if (cmd.indexOf("siren=off")    >= 0) silenceSiren();
  else if (cmd.indexOf("siren=test")   >= 0) {
    logOK("CMD", "siren test - one chirp");
    buzz(true); delay(200); buzz(false);
  }
  else logErr("CMD", "unknown command: " + cmd);
}

// HEARTBEAT: report to Francis's server + collect any queued command.
// Works with http and https (setInsecure for now, tighten at ship).
void sendHeartbeat() {
  if (strlen(SRV_URL) == 0) return;              // feature off until URL set
  if (WiFi.status() != WL_CONNECTED) return;

  JsonDocument d;
  d["key"]     = SRV_KEY;
  d["box"]     = BOX_ID;
  d["fw"]      = "live-3.0";
  d["door"]    = doorOpen ? "OPEN" : "CLOSED";
  d["opens"]   = openCount;
  d["armed"]   = alarmArmed;
  d["alarm"]   = alarmStateName();
  d["uptime"]  = millis() / 1000;
  d["hotspot"] = usersOnline;
  d["pppoe"]   = pppoeOnline;
  d["router"]  = routerOk;
  d["ip"]      = WiFi.localIP().toString();
  d["rssi"]    = WiFi.RSSI();
  String body;
  serializeJson(d, body);

  HTTPClient http;
  WiFiClientSecure tls;
  bool isHttps = String(SRV_URL).startsWith("https");
  if (isHttps) { tls.setInsecure(); http.begin(tls, SRV_URL); }
  else         { http.begin(SRV_URL); }
  http.setConnectTimeout(4000);
  http.setTimeout(8000);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);

  if (code != 200) {
    logErr("BEAT", "heartbeat failed: " + httpExplain(code));
    http.end();
    return;
  }
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
void titleBar(const char* t) {
  tft.fillScreen(C_BG);
  tft.fillRect(0, 0, tft.width(), 16, C_BAR);
  tft.setTextSize(1);
  tft.setTextColor(C_TITLE, C_BAR);
  tft.setCursor(4, 4);
  tft.print("FreeISP");
  tft.setTextColor(C_ACCENT, C_BAR);
  tft.setCursor(70, 4);
  tft.print(t);
}

void label(int x, int y, const char* s) {
  tft.setTextSize(1);
  tft.setTextColor(C_LABEL, C_BG);
  tft.setCursor(x, y);
  tft.print(s);
}

void value(int x, int y, uint8_t size, uint16_t color, const String& s, int boxW) {
  tft.fillRect(x, y, boxW, size * 8, C_BG);
  tft.setTextSize(size);
  tft.setTextColor(color, C_BG);
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
  switch (page) {
    case 0:
      titleBar("HOME");
      label(10, 24, "HOTSPOT");
      label(88, 24, "PPPOE");
      tft.drawFastVLine(80, 24, 44, C_BAR);
      label(10, 78, "ROUTER");
      label(70, 78, "UPTIME");
      break;
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
      break;
    case 4:
      titleBar("SECURITY");
      label(10, 26, "DOOR");
      label(88, 26, "ALARM");
      label(10, 62, "TIMES OPENED");
      label(10, 98, "SIREN");
      break;
  }
}

void drawLive() {
  heartbeat = !heartbeat;
  tft.fillCircle(tft.width() - 8, 8, 3, heartbeat ? C_GOOD : C_BAR);

  switch (page) {
    case 0: {
      // the two numbers customers care about: online via hotspot / via pppoe
      value(10, 36, 4, C_ACCENT, usersOnline < 0 ? "-" : String(usersOnline), 66);
      value(88, 36, 4, C_GOOD,   pppoeOnline < 0 ? "-" : String(pppoeOnline), 66);
      value(10, 90, 1, routerOk ? C_GOOD : C_BAD, routerOk ? "UP" : "DOWN", 40);
      value(70, 90, 1, C_VALUE, rosUptime, 86);
      if (!routerOk && lastErr.length())
        value(10, 110, 1, C_WARN, lastErr.substring(0, 26), 150);
      else
        tft.fillRect(10, 110, 150, 8, C_BG);
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
      break;
    }
    case 4:
      value(10, 38, 2, doorOpen ? C_BAD : C_GOOD, doorOpen ? "OPEN" : "CLOSED", 76);
      value(88, 40, 1, alarmArmed ? C_GOOD : C_WARN, alarmArmed ? "ARMED" : "OFF", 66);
      value(10, 74, 2, C_VALUE, String(openCount), 60);
      value(10, 110, 1,
            alarmState == AS_SIREN ? C_BAD : (alarmState == AS_GRACE ? C_WARN : C_LABEL),
            alarmState == AS_SIREN  ? "SOUNDING" :
            alarmState == AS_GRACE  ? "grace..."  :
            alarmState == AS_SILENT ? "silenced"  : "quiet", 80);
      break;
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println("==========================================");
  Serial.println(" LiveDashboardNext - dashboard + alarm");
  Serial.println(" users + ports + traffic + system + door");
  Serial.println("==========================================");

  pinMode(TFT_BLK, OUTPUT);
  digitalWrite(TFT_BLK, HIGH);

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
  buzz(true);  delay(120);  buzz(false);
  delay(600);
  digitalWrite(PIN_LED_R, LOW);
  digitalWrite(PIN_LED_G, LOW);

  int raw = digitalRead(PIN_REED);
  Serial.printf("[BOOT] reed raw = %d  (%s)\n", raw,
                raw == REED_CLOSED_LEVEL ? "door CLOSED" : "door OPEN");
  Serial.printf("[BOOT] alarm %s, grace %lus, siren max %lus\n",
                alarmArmed ? "ARMED" : "DISARMED",
                (unsigned long)(GRACE_MS / 1000),
                (unsigned long)(SIREN_MAX_MS / 1000));
  doorOpen = (raw != REED_CLOSED_LEVEL);
  lastReedRaw = raw;
  reedChangedAt = millis();
  openedAt = millis();
  alarmState = (doorOpen && alarmArmed)
                 ? (GRACE_MS > 0 ? AS_GRACE : AS_SIREN)
                 : (doorOpen ? AS_SILENT : AS_SECURE);
  digitalWrite(PIN_LED_R, doorOpen ? HIGH : LOW);
  digitalWrite(PIN_LED_G, doorOpen ? LOW : HIGH);
#else
  Serial.println("[BOOT] ALARM_WIRED=0 - dashboard only, alarm parts ignored");
#endif

  tft.initR(SCREEN_TAB);
  tft.setRotation(SCREEN_ROT);
  titleBar("BOOT");

  connectWiFi();

  // first data before the first page shows
  fetchPorts();
  fetchUsers();
  fetchSystem();
  if (doorOpen && alarmArmed) { drawAlarmBanner(); }
  else                        { drawStatic(); }
}

void loop() {
  uint32_t now = millis();

#if ALARM_WIRED
  // alarm checks run EVERY pass — never blocked by network calls
  pollDoor();
  pollBuzzer();
#endif

  static uint32_t lastWifiTry = 0;
  if (WiFi.status() != WL_CONNECTED && now - lastWifiTry > 15000) {
    lastWifiTry = now;
    logInfo("WIFI", "link down, reconnecting...");
    WiFi.disconnect();
    if (strlen(WIFI_PASS) == 0) WiFi.begin(WIFI_SSID);
    else                        WiFi.begin(WIFI_SSID, WIFI_PASS);
  }

  if (now - lastPoll  >= POLL_MS)  { lastPoll  = now; fetchPorts();   }
  if (now - lastUsers >= USERS_MS) { lastUsers = now; fetchUsers();   }
  if (now - lastSys   >= SYS_MS)   { lastSys   = now; fetchSystem();  }
  if (now - lastCmd   >= CMD_MS)   { lastCmd   = now; fetchCommand();  }
  if (now - lastBeat  >= HEART_MS) { lastBeat  = now; sendHeartbeat(); }

  if (!screenOn) return;           // data keeps flowing, drawing paused
  // the red banner owns the screen only while the alarm is actually raised;
  // if you disarmed it, the dashboard keeps running with the door open
  if (doorOpen && alarmArmed) return;

  if (now - lastPage >= PAGE_MS) {
    lastPage = now;
    page = (page + 1) % NUM_PAGES;
    drawStatic();
  }
  if (now - lastLive >= LIVE_MS) {
    lastLive = now;
    drawLive();
  }
}
