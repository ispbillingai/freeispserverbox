/*
  LiveDashboard.ino — FIRST REAL DATA on the FreeISP box screen.

  No new wiring. Screen stays exactly as it is. This sketch:
    1. Connects to your WiFi
    2. Reads the RB951 MikroTik over its REST API (RouterOS v7, local LAN)
    3. Shows REAL port up/down + REAL live traffic speed on the TFT

  Pages (auto-rotate 5s, PORTS + TRAFFIC repaint live):
    Page 1  STATUS  — WiFi, IP address, router link OK/FAIL
    Page 2  PORTS   — ether1..5 real up/down + Mbps from the router
    Page 3  TRAFFIC — live scrolling DL/UL graph of the WAN port (ether1)

  ------------------------------------------------------------------
  BEFORE FIRST UPLOAD — three one-time steps:
  ------------------------------------------------------------------
  A) Copy secrets.example.h -> secrets.h (same folder), fill in your
     WiFi name/password and the router user below. secrets.h never
     goes to GitHub.

  B) Create a READ-ONLY user on the MikroTik (WinBox: New Terminal,
     or the web terminal at http://192.168.88.1):

       /user group add name=espread policy=read,rest-api,api
       /user add name=espbox group=espread password=PICK_A_PASSWORD

     Also make sure the www service is on (it is by default):
       /ip service print     -> "www" should not be disabled

     Use that name/password in secrets.h. NEVER put admin in here.

  C) Arduino IDE: Sketch > Include Library > Manage Libraries,
     install "ArduinoJson" (by Benoit Blanchon).

  Board = "ESP32 Dev Module", COM6, hold BOOT while uploading.
  Serial Monitor @ 115200 shows every step and every failure reason.
  ------------------------------------------------------------------
*/
#define SCREEN_TAB  INITR_GREENTAB   // match your working DemoDashboard
#define SCREEN_ROT  1

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <esp_wifi.h>
#include "secrets.h"

#define TFT_CS   5
#define TFT_DC   2
#define TFT_RST  4

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

const uint32_t PAGE_MS  = 5000;    // page rotate
const uint32_t POLL_MS  = 2000;    // MikroTik REST poll
const uint32_t LIVE_MS  = 500;     // screen live repaint

// ---- state ----
uint8_t  page = 0;
uint32_t lastPage = 0, lastPoll = 0, lastLive = 0;
bool     heartbeat = false;

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
bool     routerOk     = false;      // last REST call succeeded
uint32_t lastGoodPoll = 0;          // millis of last success
uint32_t pollFails    = 0;
String   lastErr      = "";

// traffic history for the graph (ether1 = WAN), newest at the end
const int HIST = 100;
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
    case 404: return "404 wrong URL (RouterOS v7? REST path right?)";
    case -1:  return "connection failed (router IP right? same network? www service on?)";
    case -11: return "read timeout (router busy or link flaky)";
    default:  return "HTTP " + String(code);
  }
}

// ---- screen helpers (same style as DemoDashboard) ----
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

// scan and print EVERY network the ESP32 can see — tells us instantly
// whether the problem is name, channel, or security type
bool scanForTarget() {
  logInfo("WIFI", "scanning for networks...");
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  int n = WiFi.scanNetworks(false, true);   // include hidden SSIDs
  if (n <= 0) {
    logErr("WIFI", "scan found NOTHING at all (antenna? try nearer the router)");
    return false;
  }
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
  if (!found) {
    logErr("WIFI", String("'") + WIFI_SSID + "' is NOT in the list above. "
           "Check: exact WiFi name (CAPS matter)? router WiFi enabled? "
           "channel 12/13 (set router to ch 1-11)?");
  }
  WiFi.scanDelete();
  return found;
}

void connectWiFi() {
  scanForTarget();
  logInfo("WIFI", String("connecting to '") + WIFI_SSID + "' ...");
  tft.setTextSize(1);
  tft.setTextColor(C_WARN, C_BG);
  tft.setCursor(10, 60);
  tft.print("WiFi: connecting...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  esp_wifi_set_ps(WIFI_PS_NONE);   // CRITICAL: stops ESP32 dozing off MikroTik APs

  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    logOK("WIFI", "connected, IP = " + WiFi.localIP().toString() +
                  ", RSSI = " + String(WiFi.RSSI()) + " dBm");
  } else {
    logErr("WIFI", String("could NOT connect to '") + WIFI_SSID +
                   "'. Check: name/password in secrets.h? 2.4GHz? in range?");
  }
}

// ---- MikroTik REST ----
void pollRouter() {
  if (WiFi.status() != WL_CONNECTED) {
    routerOk = false;
    lastErr = "no WiFi";
    return;
  }

  HTTPClient http;
  String url = String("http://") + MT_HOST + "/rest/interface/ethernet/print";
  http.begin(url);
  http.setAuthorization(MT_USER, MT_PASS);
  http.addHeader("Content-Type", "application/json");
  // .proplist keeps the reply small enough for ArduinoJson
  int code = http.POST("{\".proplist\":[\"name\",\"rx-bytes\",\"tx-bytes\",\"running\"]}");

  if (code != 200) {
    routerOk = false;
    pollFails++;
    lastErr = httpExplain(code);
    logErr("PORTS", "poll failed: " + lastErr);
    http.end();
    return;
  }

  String body = http.getString();
  http.end();

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    routerOk = false;
    lastErr = String("JSON parse: ") + err.c_str();
    logErr("PORTS", lastErr);
    return;
  }

  uint32_t now = millis();
  float dt = (lastGoodPoll > 0) ? (now - lastGoodPoll) / 1000.0f : 0;

  JsonArray arr = doc.as<JsonArray>();
  int i = 0;
  for (JsonObject o : arr) {
    if (i >= NPORTS) break;
    Port& p = ports[i];
    p.name    = o["name"].as<String>();
    p.running = (strcmp(o["running"] | "false", "true") == 0);
    uint64_t rx = strtoull(o["rx-bytes"] | "0", nullptr, 10);
    uint64_t tx = strtoull(o["tx-bytes"] | "0", nullptr, 10);
    if (p.seen && dt > 0.2f) {
      p.rxMbps = (rx - p.rxBytes) * 8.0f / dt / 1e6f;   // bytes delta -> Mbps
      p.txMbps = (tx - p.txBytes) * 8.0f / dt / 1e6f;
      if (p.rxMbps < 0) p.rxMbps = 0;                   // counter reset guard
      if (p.txMbps < 0) p.txMbps = 0;
    }
    p.rxBytes = rx;
    p.txBytes = tx;
    p.seen = true;
    i++;
  }

  // shift graph history, append ether1 (index 0 = WAN)
  memmove(rxHist, rxHist + 1, sizeof(float) * (HIST - 1));
  memmove(txHist, txHist + 1, sizeof(float) * (HIST - 1));
  rxHist[HIST - 1] = ports[0].rxMbps;
  txHist[HIST - 1] = ports[0].txMbps;

  if (!routerOk) logOK("PORTS", "router link UP, " + String(i) + " ports read");
  routerOk = true;
  lastGoodPoll = now;
  lastErr = "";
}

// ---- pages ----
void drawStatic() {
  switch (page) {
    case 0:
      titleBar("STATUS");
      label(10, 26, "WIFI");
      label(10, 56, "IP ADDRESS");
      label(10, 86, "ROUTER LINK");
      break;
    case 1:
      titleBar("PORTS");
      // port names are drawn live (they come from the router)
      break;
    case 2:
      titleBar("TRAFFIC ether1");
      label(4, 20, "DL");
      label(60, 20, "UL");
      tft.drawRect(3, 34, tft.width() - 6, tft.height() - 38, C_LABEL);
      break;
  }
}

void drawLive() {
  heartbeat = !heartbeat;
  tft.fillCircle(tft.width() - 8, 8, 3, heartbeat ? C_GOOD : C_BAR);

  switch (page) {
    case 0: {
      bool wifi = (WiFi.status() == WL_CONNECTED);
      value(10, 38, 1, wifi ? C_GOOD : C_BAD,
            wifi ? "CONNECTED  " + String(WiFi.RSSI()) + " dBm" : "DOWN", 140);
      value(10, 68, 1, C_VALUE, wifi ? WiFi.localIP().toString() : "-", 110);
      value(10, 98, 1, routerOk ? C_GOOD : C_BAD, routerOk ? "OK" : "FAIL", 30);
      if (!routerOk && lastErr.length())
        value(10, 110, 1, C_WARN, lastErr.substring(0, 26), 150);
      else
        value(10, 110, 1, C_LABEL, "fails: " + String(pollFails), 150);
      break;
    }
    case 1:
      for (int i = 0; i < NPORTS; i++) {
        int y = 24 + i * 20;
        Port& p = ports[i];
        tft.fillCircle(7, y + 3, 3, !p.seen ? C_LABEL : (p.running ? C_GOOD : C_BAD));
        value(14, y, 1, C_VALUE, p.seen ? p.name : "...", 48);
        if (!p.seen)          value(66, y, 1, C_LABEL, "-", 90);
        else if (!p.running)  value(66, y, 1, C_BAD, "down", 90);
        else value(66, y, 1, C_VALUE,
                   String(p.rxMbps, 1) + "/" + String(p.txMbps, 1) + " M", 90);
      }
      break;
    case 2: {
      value(20, 20, 1, C_GOOD,   String(ports[0].rxMbps, 1), 36);
      value(76, 20, 1, C_ACCENT, String(ports[0].txMbps, 1), 36);
      // graph area
      int gx = 4, gy = 35, gw = tft.width() - 8, gh = tft.height() - 40;
      float peak = 1.0f;
      for (int i = 0; i < HIST; i++) {
        if (rxHist[i] > peak) peak = rxHist[i];
        if (txHist[i] > peak) peak = txHist[i];
      }
      tft.fillRect(gx, gy, gw, gh, C_BG);
      for (int x = 0; x < gw && x < HIST; x++) {
        int idx = HIST - gw + x;
        if (idx < 0) continue;
        int hr = (int)(rxHist[idx] / peak * (gh - 2));
        int ht = (int)(txHist[idx] / peak * (gh - 2));
        if (hr > 0) tft.drawFastVLine(gx + x, gy + gh - hr, hr, C_GOOD);
        if (ht > 0) tft.drawFastVLine(gx + x, gy + gh - ht, ht > hr ? ht - hr : 1, C_ACCENT);
      }
      break;
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println("==========================================");
  Serial.println(" LiveDashboard v1 - REAL MikroTik data");
  Serial.println(" WiFi + RouterOS v7 REST, no new wiring");
  Serial.println("==========================================");

  tft.initR(SCREEN_TAB);
  tft.setRotation(SCREEN_ROT);
  titleBar("BOOT");

  connectWiFi();
  drawStatic();
}

void loop() {
  uint32_t now = millis();

  // WiFi self-heal: if it drops, retry every 15s
  static uint32_t lastWifiTry = 0;
  if (WiFi.status() != WL_CONNECTED && now - lastWifiTry > 15000) {
    lastWifiTry = now;
    logInfo("WIFI", "link down, reconnecting...");
    WiFi.disconnect();
    WiFi.begin(WIFI_SSID, WIFI_PASS);
  }

  if (now - lastPoll >= POLL_MS) {
    lastPoll = now;
    pollRouter();
  }
  if (now - lastPage >= PAGE_MS) {
    lastPage = now;
    page = (page + 1) % 3;
    drawStatic();
  }
  if (now - lastLive >= LIVE_MS) {
    lastLive = now;
    drawLive();
  }
}
