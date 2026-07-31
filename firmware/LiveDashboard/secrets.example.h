/*
  secrets.example.h â€” TEMPLATE ONLY, safe to keep on GitHub.

  HOW TO USE:
  1. Copy this file and rename the copy to  secrets.h  (same folder).
  2. Fill in your real values in secrets.h.
  3. secrets.h is in .gitignore, so your real passwords NEVER reach GitHub.
*/

// ---- WiFi (the network the ESP32 joins â€” can be the MikroTik's own WiFi) ----
#define WIFI_SSID  "YOUR_WIFI_NAME"
#define WIFI_PASS  "YOUR_WIFI_PASSWORD"

// ---- MikroTik REST API (RouterOS v7, plain http on the LAN) ----
// Create a READ-ONLY user on the router first â€” see LiveDashboard.ino header.
#define MT_HOST  "auto"                  // auto = use the WiFi gateway; or set an IP
#define MT_USER  "espbox"                // the read-only user you created
#define MT_PASS  "READ_ONLY_PASSWORD"


// ---- OTA (update the box over WiFi instead of over a cable, optional) ----
// Leave EMPTY to keep OTA switched off. An open OTA port hands a stranger
// your firmware, so there is deliberately no default: no password, no OTA.
#define OTA_PASS  ""                  // set one and the box appears as a
                                      // network port in the Arduino IDE

// ---- your server (heartbeat + remote commands, optional) ----
#define SRV_URL  ""                   // e.g. "https://yourserver.com/box.php"; "" = off
#define SRV_KEY  "CHANGE_ME"          // must MATCH $KEY inside box.php
#define BOX_ID   "box1"               // unique name per deployed box
