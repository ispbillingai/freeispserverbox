/*
  MotionTest.ino — MPU-6050 + buzzer ONLY. No screen, no WiFi, no reed.

  This is the bench version of the motion alarm that now lives in
  LiveDashboardNext. Same sensor code, same thresholds, same wail — but
  with the numbers printed live so you can SEE what the sensor feels and
  tell me whether the trigger points are right for the real box.

  ------------------------------------------------------------------
  WIRING  (classic ESP32 WROOM, COM6, hold BOOT to upload)
  ------------------------------------------------------------------
    MPU-6050 (GY-521 / HW-123)          BUZZER (passive module)
      VCC -> 3V3                          VCC -> 5V   (louder than 3V3)
      GND -> GND                          GND -> GND
      SCL -> GPIO 22                      I/O -> GPIO 27
      SDA -> GPIO 21
      XDA, XCL, AD0, INT -> leave empty

    Grounds may share a pin - ground is one common node. Solder or screw
    them together properly; a loose ground is the worst fault to chase.
  ------------------------------------------------------------------

  WHAT YOU SEE (Serial @115200), about 3 lines a second:

     g=1.00  tilt=  2 deg   quiet

  g    = total force. 1.00 = sitting still, just gravity. Shake it and
         this swings away from 1.00.
  tilt = how far it is turned from the angle it learned at boot.

  IT WILL WAIL WHEN:
    - g goes more than 0.35 off 1.00        -> "IMPACT"  (a real knock)
    - tilt stays over 25 deg for 1.5s       -> "MOVED"   (rehung/ripped off)

  Both skip any grace period on purpose: the plan says a box being torn
  off the wall does not get 15 polite seconds.

  TUNING: watch the numbers while you handle the box the way a NORMAL
  person would (closing the lid, plugging a cable) and then the way a
  THIEF would. If normal handling trips it, the thresholds are too low -
  tell me the numbers you saw and I will set them properly.

  Type 'l' + Enter in the Serial Monitor to re-learn the baseline where
  it now sits (same as the motion=learn command in the real firmware).
*/

#include <Wire.h>
#include <math.h>

#define PIN_SDA   21
#define PIN_SCL   22
#define MPU_ADDR  0x68
#define PIN_BUZZ  27

// ---- same thresholds as the real alarm ----
const float    MOTION_JOLT_G    = 0.35f;
const uint8_t  MOTION_TILT_DEG  = 25;
const uint32_t MOTION_TILT_MS   = 1500;
const uint32_t MOTION_MS        = 50;
const uint32_t MOTION_SETTLE_MS = 2000;

// ---- same siren as the real alarm ----
const uint16_t TONE_SIREN_A_HZ = 2000;
const uint16_t TONE_SIREN_B_HZ = 4250;   // this buzzer's loudest note
const uint32_t BEEP_MS         = 300;
const uint32_t WAIL_FOR_MS     = 4000;   // how long the test wail lasts

bool     mpuOk = false;
float    baseX = 0, baseY = 0, baseZ = 1;
float    lastG = 1.0f, lastTiltDeg = 0;
uint32_t motionReadyAt = 0, tiltSince = 0;
uint32_t wailUntil = 0, beepAt = 0;
bool     beepOn = false, sirenAlt = false;

void quiet() {
  noTone(PIN_BUZZ);
  pinMode(PIN_BUZZ, OUTPUT);
  digitalWrite(PIN_BUZZ, LOW);
  beepOn = false;
}

bool mpuWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

bool mpuReadAccel(float& x, float& y, float& z) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)6) != 6) return false;
  int16_t rx = (Wire.read() << 8) | Wire.read();
  int16_t ry = (Wire.read() << 8) | Wire.read();
  int16_t rz = (Wire.read() << 8) | Wire.read();
  x = rx / 16384.0f;
  y = ry / 16384.0f;
  z = rz / 16384.0f;
  return true;
}

void learnBaseline(const char* why) {
  float x, y, z;
  if (!mpuReadAccel(x, y, z)) { Serial.println("!! learn failed - no sensor"); return; }
  float m = sqrtf(x * x + y * y + z * z);
  if (m < 0.1f) { Serial.println("!! learn failed - sensor reads zero"); return; }
  baseX = x / m; baseY = y / m; baseZ = z / m;
  tiltSince = 0;
  motionReadyAt = millis() + MOTION_SETTLE_MS;
  Serial.printf("OK baseline learned (%s) - THIS is now 'not moved'\n", why);
}

void startWail(const char* why, float g, int deg) {
  Serial.println();
  Serial.println("**********************************************");
  Serial.printf ("  ALARM - %s   (g=%.2f  tilt=%d deg)\n", why, g, deg);
  Serial.println("**********************************************");
  wailUntil = millis() + WAIL_FOR_MS;
  beepAt = millis();
  sirenAlt = !sirenAlt;
  tone(PIN_BUZZ, sirenAlt ? TONE_SIREN_A_HZ : TONE_SIREN_B_HZ);
  beepOn = true;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("==========================================");
  Serial.println(" MotionTest - MPU-6050 + buzzer only");
  Serial.println(" watch the numbers, then try to set it off");
  Serial.println("==========================================");

  pinMode(PIN_BUZZ, OUTPUT);
  quiet();

  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x75);                                  // WHO_AM_I
  if (Wire.endTransmission(false) != 0 ||
      Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)1) != 1) {
    Serial.println("!! no MPU-6050 answering at 0x68");
    Serial.println("   check: VCC on 3V3, GND joined, SDA->21, SCL->22,");
    Serial.println("   and that the header pins are SOLDERED, not just");
    Serial.println("   pushed in. Loose pins look exactly like a dead chip.");
    return;
  }
  uint8_t who = Wire.read();
  mpuWrite(0x6B, 0x00);          // wake up
  delay(100);
  mpuWrite(0x1C, 0x00);          // +-2g, most sensitive

  float x, y, z;
  mpuOk = mpuReadAccel(x, y, z);
  if (!mpuOk) { Serial.println("!! found it but cannot read it"); return; }

  Serial.printf("OK MPU-6050 alive, WHO_AM_I = 0x%02X\n", who);
  Serial.printf("   resting reading %.2f / %.2f / %.2f g\n", x, y, z);
  Serial.println("   KEEP IT STILL - learning the baseline...");
  delay(500);
  learnBaseline("boot");
  Serial.println();
  Serial.println("Now: knock it, or tilt it past 25 deg and hold.");
  Serial.println("Type 'l' + Enter to re-learn where it sits now.");
  Serial.println();
}

void loop() {
  uint32_t now = millis();

  // let him re-learn the baseline from the Serial Monitor
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'l' || c == 'L') learnBaseline("you asked");
  }

  // keep the wail going for its few seconds, alternating the two notes
  if (wailUntil) {
    if (now >= wailUntil) {
      wailUntil = 0;
      quiet();
      Serial.println("   ...wail over, watching again");
      learnBaseline("after alarm");
    } else if (now - beepAt >= BEEP_MS) {
      beepAt = now;
      beepOn = !beepOn;
      if (beepOn) {
        sirenAlt = !sirenAlt;
        tone(PIN_BUZZ, sirenAlt ? TONE_SIREN_A_HZ : TONE_SIREN_B_HZ);
      } else {
        noTone(PIN_BUZZ);
      }
    }
    return;                         // nothing else while it is screaming
  }

  if (!mpuOk) return;

  static uint32_t lastRead = 0, lastPrint = 0;
  if (now - lastRead < MOTION_MS) return;
  lastRead = now;

  float x, y, z;
  if (!mpuReadAccel(x, y, z)) return;

  float m = sqrtf(x * x + y * y + z * z);
  lastG = m;

  float dot = (m > 0.1f) ? (x * baseX + y * baseY + z * baseZ) / m : 1.0f;
  if (dot >  1.0f) dot =  1.0f;
  if (dot < -1.0f) dot = -1.0f;
  lastTiltDeg = acosf(dot) * 57.2957795f;

  // live readout, slow enough to actually read
  if (now - lastPrint >= 300) {
    lastPrint = now;
    const char* note = "quiet";
    if (now < motionReadyAt)                    note = "settling...";
    else if (lastTiltDeg > MOTION_TILT_DEG)     note = "TILTED - holding...";
    else if (fabsf(m - 1.0f) > MOTION_JOLT_G/2) note = "feeling movement";
    Serial.printf("g=%.2f  tilt=%3d deg   %s\n", m, (int)lastTiltDeg, note);
  }

  if (now < motionReadyAt) return;               // still settling

  if (fabsf(m - 1.0f) > MOTION_JOLT_G) {
    startWail("IMPACT", m, (int)lastTiltDeg);
    return;
  }

  if (lastTiltDeg > MOTION_TILT_DEG) {
    if (tiltSince == 0) tiltSince = now;
    else if (now - tiltSince > MOTION_TILT_MS) {
      startWail("MOVED", m, (int)lastTiltDeg);
      tiltSince = 0;
    }
  } else {
    tiltSince = 0;
  }
}
