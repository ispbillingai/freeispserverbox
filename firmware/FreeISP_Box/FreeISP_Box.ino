/* ============================================================================
   FreeISP Box — ESP32-S3 Brain (v0.1 — FIRST COMPLETE PROGRAM)
   ----------------------------------------------------------------------------
   One program, many jobs (runs forever in loop()):
     - Senses the box open/closed (reed switch)        [ANTI-THEFT]
     - Rings the siren + lights red LED LOCALLY first  [GOLDEN RULE]
     - Pulls users/status from your server URL         [PULL IN — HTTP/JSON]
     - Reads port status + traffic SPEED from MikroTik  [LOCAL REST — RouterOS v7]
     - Pushes event results out to your server         [PUSH OUT — HTTP POST]
     - Sends a heartbeat so the server knows it's alive [DEAD-BOX DETECTION]
     - Shows an inverter-style status screen           [AUTO-ROTATE pages]
     - Lets you flip pages by finger (capacitive touch)[FULL TOUCH CONTROL]
     - Updates itself over WiFi                         [OTA — pull from server]

   IMPORTANT BUILD SETTING:
     In Arduino IDE -> Tools -> Partition Scheme, pick one WITH OTA
     (e.g. "Default 4MB with spiffs (1.2MB APP / OTA)").  <-- don't forget!

   Libraries to install (all free):
     - ArduinoJson           (JSON parse/build)
     - TFT_eSPI              (1.8" TFT screen)  -- configure for your display
     (HTTPClient, WiFi, HTTPUpdate, touch are built into the ESP32 core)

   NOTE: Pin numbers below are PLACEHOLDERS to confirm with the real wiring.
         Everything marked  // <-- CONFIRM PIN  must match how we wire it.
   ============================================================================ */

#include <WiFi.h>
#include <WiFiClientSecure.h>   // needed for https:// (setInsecure)
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>
#include <esp_wifi.h>          // for esp_wifi_set_ps() — disable WiFi power-save (see connectWiFi)

// ---------------------------------------------------------------------------
// 1) CONFIG — edit these for your setup
// ---------------------------------------------------------------------------
#define FW_VERSION        1                       // bump this each new build (OTA version check)
#define BOX_ID            "box1"                   // unique name per box

const char* WIFI_SSID     = "YOUR_WIFI";           // <-- set
const char* WIFI_PASS     = "YOUR_PASS";           // <-- set

// Your live server endpoints (you control these) — USERS + status come from here over the internet:
const char* URL_STATUS    = "https://yoursite.com/api/status";        // GET  -> display data (users, wifi...)
const char* URL_EVENT     = "https://yoursite.com/api/event";         // POST -> event results (door open, alarm)
const char* URL_HEARTBEAT = "https://yoursite.com/api/heartbeat";     // POST -> "I'm alive"
const char* URL_FIRMWARE  = "https://yoursite.com/firmware/box.bin";  // OTA firmware binary
const char* URL_FW_VER    = "https://yoursite.com/firmware/version";  // OTA: returns latest version number (plain int)

// --- MikroTik RB951 (LOCAL, over the LAN) — PORT STATUS + TRAFFIC SPEED come from here ---
// RouterOS v7 REST API. This is plain http on the local network (no internet, no cert needed).
// SECURITY: use a DEDICATED READ-ONLY MikroTik user here, NOT the admin account.
const char* MT_URL  = "http://192.168.88.1/rest/interface/ethernet/print";  // <-- set router IP
const char* MT_USER = "esp32ro";        // <-- a read-only RouterOS user (create on the router)
const char* MT_PASS = "READONLY_PASS";  // <-- its password (move to secrets.h later)

// How often things happen (milliseconds):
const unsigned long FETCH_EVERY      = 10000;   // pull users/status from server every 10s
const unsigned long PORTS_EVERY      = 2000;    // poll MikroTik ports/traffic every 2s (local = fine, gives smooth speed)
const unsigned long HEARTBEAT_EVERY  = 60000;   // heartbeat every 60s
const unsigned long OTA_CHECK_EVERY  = 3600000; // check for updates every 1h
const unsigned long PAGE_ROTATE_EVERY= 5000;    // auto-rotate screen every 5s

// ---------------------------------------------------------------------------
// 2) PINS — CONFIRM THESE against the real wiring before flashing
// ---------------------------------------------------------------------------
#define PIN_REED        4    // <-- CONFIRM PIN  reed switch (door/lid). Uses internal pullup.
#define PIN_SIREN       5    // <-- CONFIRM PIN  drives the 12V siren via a relay/MOSFET (NOT direct!)
#define PIN_LED_RED     6    // <-- CONFIRM PIN  red LED  = open/alarm
#define PIN_LED_GREEN   7    // <-- CONFIRM PIN  green LED = secure
#define TOUCH_NEXT      T1   // <-- CONFIRM PIN  capacitive touch pad: next page  (touch-capable GPIO)
#define TOUCH_PREV      T2   // <-- CONFIRM PIN  capacitive touch pad: prev page  (2nd pad, optional)
#define TOUCH_THRESHOLD 40   // tune: lower number = lighter touch needed (read serial to calibrate)

// ---------------------------------------------------------------------------
// 3) STATE
// ---------------------------------------------------------------------------
TFT_eSPI tft = TFT_eSPI();

bool boxOpen        = false;     // current reed state
bool alarmActive    = false;     // is the siren/alarm currently firing
int  currentPage    = 0;         // which screen page is showing
const int NUM_PAGES = 6;         // 0 home,1 users,2 uptime,3 status,4 ports,5 speed graph

// Live data we pull from the server (defaults until first fetch):
int    g_users   = 0;
String g_wifi    = "?";
String g_uptime  = "-";
bool   g_online  = false;        // did the last server fetch succeed?

// --- MikroTik port + traffic data (read locally from the router) ---
const int MAX_PORTS = 6;                 // RB951 has 5 ports; room for a couple extra
int      g_portCount = 0;                // how many ports the router reported
String   g_portName[MAX_PORTS];          // e.g. "ether1"
bool     g_portUp[MAX_PORTS];            // running = true means the port is active
bool     g_mtOnline = false;             // did the last MikroTik read succeed?

// For TRAFFIC SPEED we compare byte counters between two reads:
unsigned long long g_prevRx[MAX_PORTS] = {0};  // last rx-bytes per port
unsigned long long g_prevTx[MAX_PORTS] = {0};  // last tx-bytes per port
unsigned long      g_prevPortMs = 0;           // when we last read (for the time delta)
float    g_totRxMbps = 0;                 // total download speed across all ports
float    g_totTxMbps = 0;                 // total upload speed

// Rolling history for the on-screen speed graph (newest at the end)
const int HISTORY = 100;
float    g_rxHist[HISTORY] = {0};
float    g_txHist[HISTORY] = {0};
int      g_histLen = 0;

// Event queue for OFFLINE buffering (if internet is down when an event fires)
String pendingEvent = "";        // simple single-slot buffer for v0.1 (expand later)

// Timers
unsigned long tFetch = 0, tPorts = 0, tHeartbeat = 0, tOta = 0, tPage = 0;

// Remember the last error so we can also show it on the screen (page 3)
String g_lastError = "";

// ===========================================================================
// LOGGING  (this is what you watch on your PC: Tools -> Serial Monitor @115200)
//   Every line is TAGGED so you instantly know which part is talking:
//     [WIFI] [FETCH] [EVENT] [BEAT] [OTA] [ALARM] [TOUCH] [SYS]
//   Use:
//     logOK ("FETCH", "got users=10");      -> prints a normal "ok" line
//     logInfo("WIFI",  "connecting...");     -> prints an info line
//     logErr ("FETCH", "server said 500");   -> prints a clear ERROR line + remembers it
// ---------------------------------------------------------------------------
void logLine(const char* level, const char* tag, const String& msg) {
  // Format: [seconds] LEVEL  [TAG] message
  unsigned long s = millis() / 1000;
  Serial.printf("[%5lus] %-4s [%-5s] %s\n", s, level, tag, msg.c_str());
}
void logInfo(const char* tag, const String& msg) { logLine("..",  tag, msg); }
void logOK  (const char* tag, const String& msg) { logLine("OK",  tag, msg); }
void logErr (const char* tag, const String& msg) {
  logLine("ERR", tag, msg);
  g_lastError = String(tag) + ": " + msg;   // keep last error for the screen
}

// Turn a raw HTTPClient result code into a HUMAN explanation (huge help for a beginner)
String httpExplain(int code) {
  if (code > 0) {
    // Positive = the server actually answered with this HTTP status
    switch (code) {
      case 200: return "200 OK";
      case 201: return "201 Created";
      case 204: return "204 No Content";
      case 301:
      case 302: return String(code) + " Redirect (check the exact URL)";
      case 400: return "400 Bad Request (the box sent something the server didn't like)";
      case 401: return "401 Unauthorized (needs a key/login?)";
      case 403: return "403 Forbidden (server refused us)";
      case 404: return "404 Not Found (wrong URL / file missing)";
      case 500: return "500 Server Error (problem on YOUR server side)";
      case 502: return "502 Bad Gateway";
      case 503: return "503 Service Unavailable (server busy/down)";
      default:  return String(code) + " (HTTP status)";
    }
  }
  // Negative = couldn't even talk to the server (a connection problem, not a reply)
  switch (code) {
    case -1:  return "-1 Connection failed (URL wrong? no internet? HTTPS issue?)";
    case -2:  return "-2 Send header failed";
    case -3:  return "-3 Send payload failed";
    case -4:  return "-4 Not connected";
    case -5:  return "-5 Connection lost mid-request";
    case -11: return "-11 Read timeout (server too slow / no reply)";
    default:  return String(code) + " (connection-level error)";
  }
}

// ===========================================================================
// SETUP
// ===========================================================================
void setup() {
  Serial.begin(115200);
  delay(300);   // give the Serial Monitor a moment to connect so you don't miss the banner
  // --- friendly boot banner (helps you confirm the Serial Monitor is working) ---
  Serial.println();
  Serial.println("==================================================");
  Serial.printf ("  FreeISP Box  '%s'   firmware v%d\n", BOX_ID, FW_VERSION);
  Serial.println("  Serial Monitor working if you can read this.");
  Serial.println("  Watch the [TAG] lines below to see what fails.");
  Serial.println("==================================================");
  logInfo("SYS", "booting...");

  // I/O
  pinMode(PIN_REED, INPUT_PULLUP);     // reed: closed-to-GND when magnet present (tune logic below)
  pinMode(PIN_SIREN, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  digitalWrite(PIN_SIREN, LOW);
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_LED_GREEN, HIGH);   // assume secure at boot

  // Screen
  tft.init();
  tft.setRotation(1);
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  tft.setCursor(6, 6);
  tft.print("FreeISP starting");
  logOK("SYS", "screen initialised");

  // Show the current reed/touch readings ONCE so you can calibrate them.
  logInfo("SYS", String("reed raw=") + digitalRead(PIN_REED) +
                 "  (note this with box CLOSED vs OPEN to set the logic)");
  logInfo("TOUCH", String("idle readings  next=") + touchRead(TOUCH_NEXT) +
                   "  prev=" + touchRead(TOUCH_PREV) +
                   "   (a finger touch should DROP these below " + TOUCH_THRESHOLD + ")");

  // WiFi (non-blocking-ish: try, but don't hang the alarm forever)
  connectWiFi();

  // First OTA check on boot (so a freshly-deployed box can self-correct)
  checkForUpdate();
}

// ===========================================================================
// MAIN LOOP — everything happens here, fast, over and over
// ===========================================================================
void loop() {
  unsigned long now = millis();

  // ---- 1) ANTI-THEFT: sense + react LOCALLY FIRST (never wait on internet) ----
  handleSecurity();

  // ---- 2) TOUCH: let finger taps flip pages (full touch control) ----
  handleTouch();

  // ---- 3) AUTO-ROTATE the screen pages on a timer (fallback if no touch) ----
  if (now - tPage >= PAGE_ROTATE_EVERY) {
    tPage = now;
    currentPage = (currentPage + 1) % NUM_PAGES;
  }
  drawScreen();   // always redraw so live data + state show instantly

  // ---- 4) Keep WiFi up (reconnect quietly if dropped) ----
  if (WiFi.status() != WL_CONNECTED) connectWiFi();

  // ---- 5) PULL users/status from your server every FETCH_EVERY ----
  if (now - tFetch >= FETCH_EVERY) {
    tFetch = now;
    fetchStatus();
  }

  // ---- 5b) PULL port status + traffic speed from the MikroTik LOCALLY (fast) ----
  if (now - tPorts >= PORTS_EVERY) {
    tPorts = now;
    fetchPorts();
  }

  // ---- 6) HEARTBEAT so the server can detect a dead/stolen box ----
  if (now - tHeartbeat >= HEARTBEAT_EVERY) {
    tHeartbeat = now;
    sendHeartbeat();
  }

  // ---- 7) Retry any event that failed to send while offline ----
  flushPendingEvent();

  // ---- 8) OTA: periodically check for a newer firmware ----
  if (now - tOta >= OTA_CHECK_EVERY) {
    tOta = now;
    checkForUpdate();
  }

  delay(20);  // small breather; loop still runs ~50x/sec
}

// ===========================================================================
// ANTI-THEFT  (GOLDEN RULE: ring locally first, tell server after)
// ===========================================================================
void handleSecurity() {
  // Reed: with INPUT_PULLUP, magnet-present (closed) typically reads LOW.
  // Adjust the comparison once we test the real reed+magnet orientation.
  bool nowOpen = (digitalRead(PIN_REED) == HIGH);

  if (nowOpen && !boxOpen) {
    // Box JUST opened -> fire the alarm IMMEDIATELY (no internet needed)
    boxOpen = true;
    alarmActive = true;
    digitalWrite(PIN_SIREN, HIGH);
    digitalWrite(PIN_LED_RED, HIGH);
    digitalWrite(PIN_LED_GREEN, LOW);
    logErr("ALARM", "BOX OPENED -> siren ON (local, no internet needed)");
    // THEN (secondary) tell the server. If offline, it gets buffered.
    sendEvent("door_opened");
    sendEvent("alarm");
  }
  else if (!nowOpen && boxOpen) {
    // Box closed again
    boxOpen = false;
    alarmActive = false;
    digitalWrite(PIN_SIREN, LOW);
    digitalWrite(PIN_LED_RED, LOW);
    digitalWrite(PIN_LED_GREEN, HIGH);
    logOK("ALARM", "box closed -> secure");
    sendEvent("door_closed");
  }
}

// ===========================================================================
// TOUCH  (capacitive pads, sensed through the sealed wall)
// ===========================================================================
unsigned long tLastTouch = 0;
void handleTouch() {
  if (millis() - tLastTouch < 300) return;  // simple debounce

  int next = touchRead(TOUCH_NEXT);
  int prev = touchRead(TOUCH_PREV);

  if (next < TOUCH_THRESHOLD) {
    currentPage = (currentPage + 1) % NUM_PAGES;
    tLastTouch = millis();
    tPage = millis();   // reset auto-rotate timer so it doesn't jump again instantly
    logOK("TOUCH", String("next page -> ") + currentPage + "  (reading=" + next + ")");
  } else if (prev < TOUCH_THRESHOLD) {
    currentPage = (currentPage - 1 + NUM_PAGES) % NUM_PAGES;
    tLastTouch = millis();
    tPage = millis();
    logOK("TOUCH", String("prev page -> ") + currentPage + "  (reading=" + prev + ")");
  }
}

// ===========================================================================
// SCREEN  (inverter-style; one page at a time)
// ===========================================================================
void drawScreen() {
  static int lastPage = -1;
  static bool lastAlarm = false;
  // Pages 4 (ports) and 5 (speed) show LIVE data -> let them repaint every loop.
  bool livePage = (currentPage == 4 || currentPage == 5);
  // Otherwise only repaint when something visible changes (avoids flicker)
  if (!livePage && currentPage == lastPage && alarmActive == lastAlarm && !alarmActive) return;
  lastPage = currentPage; lastAlarm = alarmActive;

  tft.fillScreen(TFT_BLACK);
  tft.setTextSize(2);

  if (alarmActive) {
    tft.setTextColor(TFT_RED, TFT_BLACK);
    tft.setCursor(10, 30); tft.print("** ALARM **");
    tft.setCursor(10, 60); tft.print("BOX OPEN!");
    return;
  }

  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  switch (currentPage) {
    case 0:
      tft.setTextColor(TFT_CYAN, TFT_BLACK);
      tft.setCursor(6, 6);  tft.print("FreeISP");
      tft.setTextColor(TFT_WHITE, TFT_BLACK);
      tft.setCursor(6, 40); tft.printf("WiFi: %s", g_wifi.c_str());
      tft.setCursor(6, 70); tft.printf("Users: %d", g_users);
      break;
    case 1:
      tft.setCursor(6, 20); tft.printf("Users online");
      tft.setTextSize(4);
      tft.setCursor(6, 55); tft.printf("%d", g_users);
      break;
    case 2:
      tft.setCursor(6, 20); tft.print("Uptime");
      tft.setCursor(6, 55); tft.print(g_uptime);
      break;
    case 3:
      tft.setCursor(6, 6);  tft.print("Status");
      tft.setTextColor(g_online ? TFT_GREEN : TFT_RED, TFT_BLACK);
      tft.setCursor(6, 30); tft.print(g_online ? "Server: OK" : "Server: --");
      tft.setTextColor(boxOpen ? TFT_RED : TFT_GREEN, TFT_BLACK);
      tft.setCursor(6, 55); tft.print(boxOpen ? "Box: OPEN" : "Box: SECURE");
      // Show the last error on-screen too (small) so you can debug without USB
      if (g_lastError.length()) {
        tft.setTextSize(1);
        tft.setTextColor(TFT_YELLOW, TFT_BLACK);
        tft.setCursor(6, 85); tft.print("Last err:");
        tft.setCursor(6, 96); tft.print(g_lastError.substring(0, 26));
        tft.setTextSize(2);
      }
      break;
    case 4:  // PORTS — which ports are active (green=up, grey=down)
      tft.setTextColor(TFT_CYAN, TFT_BLACK);
      tft.setCursor(6, 4); tft.print("Ports");
      if (!g_mtOnline) {
        tft.setTextColor(TFT_RED, TFT_BLACK);
        tft.setTextSize(1); tft.setCursor(6, 40); tft.print("No router data");
      } else {
        tft.setTextSize(1);
        for (int p = 0; p < g_portCount; p++) {
          int y = 26 + p * 18;
          tft.fillRoundRect(6, y, 12, 12, 2, g_portUp[p] ? TFT_GREEN : TFT_DARKGREY);
          tft.setTextColor(g_portUp[p] ? TFT_GREEN : TFT_DARKGREY, TFT_BLACK);
          tft.setCursor(24, y + 2);
          tft.printf("%s %s", g_portName[p].c_str(), g_portUp[p] ? "UP" : "down");
        }
      }
      tft.setTextSize(2);
      break;
    case 5:  // TRAFFIC SPEED — live numbers + a simple graph (customers love this)
      drawSpeedGraph();
      break;
  }
  // tiny page dots at the bottom
  tft.fillRect(0, 118, 160, 10, TFT_BLACK);
  for (int i = 0; i < NUM_PAGES; i++) {
    tft.fillCircle(20 + i * 14, 122, currentPage == i ? 4 : 2,
                   currentPage == i ? TFT_WHITE : TFT_DARKGREY);
  }
}

// ---------------------------------------------------------------------------
// Live traffic-speed page: current DL/UL numbers + a scrolling graph.
//   Green line = download (RX), Blue line = upload (TX). Auto-scales.
//   (Adapted from the esp32_graphing repo, sized for the small 1.8" screen.)
// ---------------------------------------------------------------------------
void drawSpeedGraph() {
  // Current numbers at the top
  tft.setTextSize(1);
  tft.setTextColor(TFT_GREEN, TFT_BLACK);
  tft.setCursor(4, 4);  tft.printf("DL %.2f Mbps   ", g_totRxMbps);
  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.setCursor(4, 16); tft.printf("UL %.2f Mbps   ", g_totTxMbps);

  // Graph area
  const int gx = 4, gy = 30, gw = 152, gh = 80;
  tft.drawRect(gx, gy, gw, gh, TFT_DARKGREY);

  if (!g_mtOnline || g_histLen < 2) {
    tft.setTextColor(TFT_RED, TFT_BLACK);
    tft.setCursor(gx + 6, gy + 34); tft.print("waiting for data...");
    tft.setTextSize(2);
    return;
  }

  // Find the peak so the graph auto-scales to fit
  float peak = 0.1;
  for (int k = 0; k < g_histLen; k++) {
    if (g_rxHist[k] > peak) peak = g_rxHist[k];
    if (g_txHist[k] > peak) peak = g_txHist[k];
  }

  // Plot the last gw points (one column per pixel), newest on the right
  int start = (g_histLen > gw) ? g_histLen - gw : 0;
  int prevRxY = -1, prevTxY = -1, col = 0;
  for (int k = start; k < g_histLen; k++, col++) {
    int x  = gx + col;
    int ry = gy + gh - 1 - (int)((g_rxHist[k] / peak) * (gh - 2));
    int ty = gy + gh - 1 - (int)((g_txHist[k] / peak) * (gh - 2));
    if (prevRxY >= 0) {
      tft.drawLine(x - 1, prevRxY, x, ry, TFT_GREEN);
      tft.drawLine(x - 1, prevTxY, x, ty, TFT_CYAN);
    }
    prevRxY = ry; prevTxY = ty;
  }
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  tft.setCursor(gx + 2, gy + 2); tft.printf("peak %.1f", peak);
  tft.setTextSize(2);
}

// ===========================================================================
// PULL IN — get display data from your server (HTTP GET + JSON)
// ===========================================================================
void fetchStatus() {
  if (WiFi.status() != WL_CONNECTED) {
    g_online = false;
    logErr("FETCH", "skipped - WiFi not connected");
    return;
  }

  logInfo("FETCH", String("GET ") + URL_STATUS);
  HTTPClient http;
  WiFiClientSecure client; client.setInsecure();   // quick HTTPS path (tighten later)
  http.begin(client, URL_STATUS);
  int code = http.GET();

  if (code == 200) {
    String body = http.getString();
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, body);
    if (!err) {
      g_users  = doc["users"]  | g_users;
      g_wifi   = String((const char*)(doc["wifi"]   | g_wifi.c_str()));
      g_uptime = String((const char*)(doc["uptime"] | g_uptime.c_str()));
      g_online = true;
      logOK("FETCH", String("users=") + g_users + " wifi=" + g_wifi + " uptime=" + g_uptime);
    } else {
      g_online = false;
      // Show WHAT the server sent so you can see why it isn't valid JSON
      logErr("FETCH", String("bad JSON (") + err.c_str() + "). Server sent: " +
                      body.substring(0, 120));
    }
  } else {
    g_online = false;
    logErr("FETCH", "GET failed -> " + httpExplain(code));
  }
  http.end();
}

// ===========================================================================
// PULL IN (LOCAL) — read PORT STATUS + TRAFFIC SPEED from the MikroTik RB951
//   Uses the RouterOS v7 REST API over the LAN (plain http, no cert).
//   Jump-started from github.com/Druvis-Timma/Mikrotik esp32_graphing.
//   Returns interfaces with: name, rx-bytes, tx-bytes, running(up/down).
//   We turn byte counters into Mbps by diffing against the previous read.
// ===========================================================================
void fetchPorts() {
  if (WiFi.status() != WL_CONNECTED) { g_mtOnline = false; return; }

  HTTPClient http;
  http.begin(MT_URL);                       // plain http on LAN — no WiFiClientSecure needed
  http.setAuthorization(MT_USER, MT_PASS);  // RouterOS basic auth (read-only user!)
  // Ask only for the fields we need (smaller, faster response):
  http.addHeader("Content-Type", "application/json");
  int code = http.GET();

  if (code != 200) {
    g_mtOnline = false;
    logErr("PORTS", "MikroTik read failed -> " + httpExplain(code) +
                    "  (router IP? read-only user/pass? RouterOS v7 REST enabled?)");
    http.end();
    return;
  }

  // RouterOS returns a JSON ARRAY of interface objects.
  String body = http.getString();
  http.end();
  DynamicJsonDocument doc(4096);
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    g_mtOnline = false;
    logErr("PORTS", String("bad JSON from router (") + err.c_str() + ")");
    return;
  }

  // Time delta since last read (seconds) — needed to turn bytes into a speed
  unsigned long nowMs = millis();
  float dt = (g_prevPortMs == 0) ? 0 : (nowMs - g_prevPortMs) / 1000.0;
  g_prevPortMs = nowMs;

  JsonArray arr = doc.as<JsonArray>();
  int i = 0;
  float sumRx = 0, sumTx = 0;
  for (JsonObject port : arr) {
    if (i >= MAX_PORTS) break;
    g_portName[i] = String((const char*)(port["name"] | "?"));
    // RouterOS sends "running":"true"/"false" as a STRING on v7
    g_portUp[i]   = String((const char*)(port["running"] | "false")) == "true";

    // rx/tx-bytes are big numbers sent as strings -> parse to 64-bit
    unsigned long long rx = strtoull((const char*)(port["rx-bytes"] | "0"), nullptr, 10);
    unsigned long long tx = strtoull((const char*)(port["tx-bytes"] | "0"), nullptr, 10);

    if (dt > 0 && g_prevRx[i] > 0 && rx >= g_prevRx[i]) {
      // bytes/sec * 8 = bits/sec ; /1e6 = Mbps
      sumRx += ((rx - g_prevRx[i]) * 8.0 / dt) / 1e6;
      sumTx += ((tx - g_prevTx[i]) * 8.0 / dt) / 1e6;
    }
    g_prevRx[i] = rx;
    g_prevTx[i] = tx;
    i++;
  }
  g_portCount  = i;
  g_totRxMbps  = sumRx;
  g_totTxMbps  = sumTx;
  g_mtOnline   = true;

  // Push the totals into the rolling graph history
  if (g_histLen < HISTORY) {
    g_rxHist[g_histLen] = sumRx; g_txHist[g_histLen] = sumTx; g_histLen++;
  } else {
    for (int k = 1; k < HISTORY; k++) { g_rxHist[k-1] = g_rxHist[k]; g_txHist[k-1] = g_txHist[k]; }
    g_rxHist[HISTORY-1] = sumRx; g_txHist[HISTORY-1] = sumTx;
  }

  logOK("PORTS", String("ports=") + g_portCount +
                 "  DL=" + String(sumRx,2) + "Mbps  UL=" + String(sumTx,2) + "Mbps");
}

// ===========================================================================
// PUSH OUT — send an event result to the server (HTTP POST + JSON)
//   If offline, buffer it and retry later (flushPendingEvent).
// ===========================================================================
void sendEvent(const char* type) {
  String json = String("{\"box\":\"") + BOX_ID + "\",\"event\":\"" + type +
                "\",\"fw\":" + FW_VERSION + "}";
  if (postJson(URL_EVENT, json)) {
    logOK("EVENT", String("sent '") + type + "'");
  } else {
    pendingEvent = json;   // couldn't send now -> remember it
    logErr("EVENT", String("'") + type + "' could not be sent -> BUFFERED, will retry");
  }
}

void flushPendingEvent() {
  if (pendingEvent.length() == 0) return;
  if (WiFi.status() != WL_CONNECTED) return;
  if (postJson(URL_EVENT, pendingEvent)) {
    logOK("EVENT", "buffered event finally sent");
    pendingEvent = "";
  }
}

void sendHeartbeat() {
  String json = String("{\"box\":\"") + BOX_ID + "\",\"alive\":true,\"users\":" +
                g_users + ",\"open\":" + (boxOpen ? "true" : "false") + "}";
  if (postJson(URL_HEARTBEAT, json)) logOK ("BEAT", "heartbeat sent");
  else                               logErr("BEAT", "heartbeat NOT sent (server can't tell box is alive)");
}

// Returns true on success. Logs the exact reason on failure.
bool postJson(const char* url, const String& json) {
  if (WiFi.status() != WL_CONNECTED) {
    logErr("POST", "skipped - WiFi not connected");
    return false;
  }
  HTTPClient http;
  WiFiClientSecure client; client.setInsecure();
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(json);
  bool ok = (code == 200 || code == 201 || code == 204);
  if (!ok) logErr("POST", String("to ") + url + " failed -> " + httpExplain(code));
  http.end();
  return ok;
}

// ===========================================================================
// OTA — pull-from-server with version check + verify-before-switch
// ===========================================================================
void checkForUpdate() {
  if (WiFi.status() != WL_CONNECTED) { logErr("OTA", "skipped - WiFi not connected"); return; }

  // 1) Ask the server what the latest version is
  logInfo("OTA", "checking for updates...");
  HTTPClient http;
  WiFiClientSecure client; client.setInsecure();
  http.begin(client, URL_FW_VER);
  int code = http.GET();
  int latest = -1;
  if (code == 200) latest = http.getString().toInt();
  http.end();
  if (code != 200) { logErr("OTA", "version check failed -> " + httpExplain(code)); return; }

  // 2) Only update if the server's version is NEWER (no reflash loop)
  if (latest <= FW_VERSION) {
    logOK("OTA", String("up to date (have v") + FW_VERSION + ", server v" + latest + ")");
    return;
  }

  logInfo("OTA", String("NEW version found: v") + FW_VERSION + " -> v" + latest + ", downloading...");
  WiFiClientSecure ota; ota.setInsecure();
  // httpUpdate verifies the download before switching; keeps old fw if it fails.
  t_httpUpdate_return ret = httpUpdate.update(ota, URL_FIRMWARE);
  switch (ret) {
    case HTTP_UPDATE_FAILED:
      // Old firmware is kept; box keeps running. Shows the real reason.
      logErr("OTA", String("download FAILED (kept old fw): ") +
                    httpUpdate.getLastError() + " " + httpUpdate.getLastErrorString());
      break;
    case HTTP_UPDATE_NO_UPDATES: logInfo("OTA", "no update available"); break;
    case HTTP_UPDATE_OK:         logOK  ("OTA", "updated! rebooting into new firmware..."); break;
  }
}

// ===========================================================================
// WiFi
// ===========================================================================
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  logInfo("WIFI", String("connecting to '") + WIFI_SSID + "' ...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  // Try for ~8s, but DON'T block the alarm forever if WiFi is down
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 8000) {
    delay(250);
    handleSecurity();   // keep watching the box even while connecting!
  }
  if (WiFi.status() == WL_CONNECTED) {
    // ------------------------------------------------------------------
    // IMPORTANT FIX for MikroTik APs: turn OFF WiFi power-save.
    // By default the ESP32 dozes between beacons (WIFI_PS_MIN_MODEM) and
    // can MISS ARP broadcasts -> the AP loses track of us -> the box goes
    // unreachable / randomly drops. Our box is mains-powered and must stay
    // reachable for the 2s MikroTik REST polling + heartbeats, so keep the
    // radio fully awake. (Re-applied on every (re)connect to be safe.)
    // ------------------------------------------------------------------
    esp_wifi_set_ps(WIFI_PS_NONE);
    logOK("WIFI", "connected, IP " + WiFi.localIP().toString() + " (power-save OFF)");
  } else {
    // Explain the most likely reasons so a first-timer knows where to look
    logErr("WIFI", String("could NOT connect to '") + WIFI_SSID +
                   "'. Check: name/password correct? 2.4GHz network? in range?");
  }
}
