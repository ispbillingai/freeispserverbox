/*
  secrets.example.h — TEMPLATE ONLY, safe to keep on GitHub.

  HOW TO USE:
  1. Copy this file and rename the copy to  secrets.h  (same folder).
  2. Fill in your real values in secrets.h.
  3. secrets.h is in .gitignore, so your real passwords NEVER reach GitHub.
*/

// ---- WiFi (the network the ESP32 joins — can be the MikroTik's own WiFi) ----
#define WIFI_SSID  "YOUR_WIFI_NAME"
#define WIFI_PASS  "YOUR_WIFI_PASSWORD"

// ---- MikroTik REST API (RouterOS v7, plain http on the LAN) ----
// Create a READ-ONLY user on the router first — see LiveDashboard.ino header.
#define MT_HOST  "192.168.88.1"          // router LAN IP
#define MT_USER  "espbox"                // the read-only user you created
#define MT_PASS  "READ_ONLY_PASSWORD"
