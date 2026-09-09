import io, os
os.chdir(r'F:\freeispserverbox\firmware')
src = io.open('FaceUI/FaceUI.ino', encoding='utf-8', errors='surrogateescape').read()

def grab(start_pat, end_pat):
    a = src.index(start_pat); b = src.index(end_pat, a)
    return src[a:b]

# Reuse the product's exact pieces, verbatim, so the test measures the product path.
lcd  = grab('static const uint8_t PIN_D[8]', '#define T_XP')
elec = grab('#define T_XP', '// 0 = normal product UI')
rgb  = grab('#define RGB(r,g,b)', 'static uint32_t lutSet')
core = grab('static uint32_t lutSet[256]',
            '// ---------------------------------------------------------------- palette --')

head = r'''/* RowProof -- an accuracy series for the v13 touch path. READ-ONLY.
 *
 * FaceUI v13 works by the owner's confirmation, and its README says the one
 * thing not yet established is error-free performance across positions and
 * ordinary taps: the first independent check went 5/6 with the TOP row
 * selecting row 2 (ratios 1.216 vs 1.256, about 3% apart). This sketch
 * measures that margin instead of guessing at it.
 *
 * It uses the product's sampler VERBATIM (copied from FaceUI.ino by the
 * generator gen_rowproof.py at build time) and the product's SAVED anchors
 * from NVS. It never writes NVS, never calibrates, never adapts. Every tap
 * logs: target row, x, raw, matched row, distance to the nearest and the
 * second-nearest anchor, the margin between them, burst spread, PASS/FAIL.
 *
 * Phase 1: 18 scripted targets (rows 1..6 at x = 60, 240, 420). Tap each
 *          white square with an ordinary tap, not a hold.
 * Phase 2: free taps; the matched row fills. Serial 'r' reprints the summary.
 *
 * Everything between the GENERATED markers is lifted from FaceUI.ino unchanged.
 */

#include <Adafruit_GFX.h>
#include <Preferences.h>
#include "driver/gpio.h"
#include "soc/gpio_struct.h"

// ---- GENERATED from FaceUI.ino: pins, electrode map, colours, LCD, sampler ----
'''

tail = r'''
// ---- end GENERATED ----

#define C_CARD  RGB(18,31,45)
#define C_LABEL RGB(139,161,179)
#define C_ACC   RGB(85,220,218)
#define C_PASS  RGB(63,185,80)
#define C_FAIL  RGB(235,80,80)

#define NANCH 6
#define BAND (320 / NANCH)
int anchorRaw[NANCH];
Preferences prefs;

// Contact debounce: two agreeing rounds flip the state, as in the product.
bool tDown = false; int tStreak = 0;
bool touchDown() {
  bool now = zRead() > 0;
  if (now == tDown) { tStreak = 0; return tDown; }
  if (++tStreak >= 2) { tDown = now; tStreak = 0; }
  return tDown;
}

// Product tap path: sample on press, one retry while contact remains,
// never a held press.
int readTapRaw() {
  int raw = yRead();
  if (raw < 0 && touchDown()) raw = yRead();
  return raw;
}
bool waitTap(int *raw) {
  static bool consumed = false;
  if (!touchDown()) { consumed = false; return false; }
  if (consumed) return false;
  consumed = true;
  *raw = readTapRaw();
  return *raw >= 0;
}

bool loadCal() {
  int t[NANCH];
  prefs.begin("freeisp", true);
  bool verOk = prefs.getUChar("vcal_ver", 0) == 13;
  size_t got = prefs.getBytes("anch6", t, sizeof(t));
  prefs.end();
  if (!verOk || got != sizeof(t)) return false;
  for (int i = 0; i < NANCH; i++) anchorRaw[i] = t[i];
  return true;
}

// Nearest anchor, plus the two distances the margin is made of.
int matchRow(int raw, int *dNear, int *dSecond) {
  int best = 0, bd = 0x7fffffff, sd = 0x7fffffff;
  for (int i = 0; i < NANCH; i++) {
    int d = abs(raw - anchorRaw[i]);
    if (d < bd) { sd = bd; bd = d; best = i; }
    else if (d < sd) sd = d;
  }
  *dNear = bd; *dSecond = sd;
  return best;
}

void textAt(int x, int y, uint8_t sz, uint16_t c, const String &s) {
  tft.setTextSize(sz); tft.setTextColor(c); tft.setCursor(x, y); tft.print(s);
}

void drawRows(int hot, int targetX, uint16_t hotColour, const String &note) {
  tft.fillScreen(C_BG);
  for (int r = 0; r < NANCH; r++) {
    int top = r * BAND, bottom = (r + 1) * BAND;
    tft.fillRect(1, top + 1, 478, bottom - top - 2, r == hot ? hotColour : C_CARD);
    textAt(8, top + 7, 2, r == hot ? 0xFFFF : C_TXT, String(r + 1));
    if (r == hot && targetX >= 0) {
      int cy = (top + bottom) / 2;
      tft.drawRect(targetX - 10, cy - 10, 20, 20, 0xFFFF);
      tft.drawRect(targetX - 11, cy - 11, 22, 22, 0xFFFF);
    }
  }
  textAt(80, 4, 1, C_LABEL, note);
}

// ---- the series ----
const int XS[3] = {60, 240, 420};
int taps[NANCH], passes[NANCH], minMargin[NANCH], rawLo[NANCH], rawHi[NANCH];
long rawSum[NANCH];
int step = 0;                         // 0..17 scripted, then free
bool haveCal = false;

void resetStats() {
  for (int r = 0; r < NANCH; r++) {
    taps[r] = passes[r] = 0; minMargin[r] = 0x7fffffff;
    rawLo[r] = 0x7fffffff; rawHi[r] = -1; rawSum[r] = 0;
  }
}

void record(int targetRow, int x, int raw) {
  int dn, ds;
  int m = matchRow(raw, &dn, &ds);
  int margin = ds - dn;               // how far this tap was from flipping rows
  bool pass = (m == targetRow);
  taps[targetRow]++; if (pass) passes[targetRow]++;
  if (margin < minMargin[targetRow]) minMargin[targetRow] = margin;
  if (raw < rawLo[targetRow]) rawLo[targetRow] = raw;
  if (raw > rawHi[targetRow]) rawHi[targetRow] = raw;
  rawSum[targetRow] += raw;
  Serial.printf("SERIES target=%d x=%d raw=%d burst=%d..%d matched=%d dNear=%d dSecond=%d margin=%d %s\n",
                targetRow + 1, x, raw, touchRawMin, touchRawMax, m + 1, dn, ds, margin,
                pass ? "PASS" : "FAIL");
}

void summary() {
  Serial.println("SUMMARY row  taps pass  raw(min..mean..max)   minMargin");
  int total = 0, ok = 0, weakest = -1, weakestMargin = 0x7fffffff;
  for (int r = 0; r < NANCH; r++) {
    total += taps[r]; ok += passes[r];
    long mean = taps[r] ? rawSum[r] / taps[r] : 0;
    Serial.printf("SUMMARY  %d    %2d   %2d   %5d..%5ld..%5d   %d\n", r + 1, taps[r], passes[r],
                  taps[r] ? rawLo[r] : 0, mean, taps[r] ? rawHi[r] : 0, taps[r] ? minMargin[r] : 0);
    if (taps[r] && minMargin[r] < weakestMargin) { weakestMargin = minMargin[r]; weakest = r; }
  }
  Serial.print("SUMMARY anchors:");
  for (int i = 0; i < NANCH; i++) Serial.printf(" %d", anchorRaw[i]);
  Serial.println();
  Serial.printf("SUMMARY overall %d/%d correct; weakest row %d (min margin %d)\n",
                ok, total, weakest + 1, weakestMargin);
}

void showTarget() {
  int r = step / 3, x = XS[step % 3];
  drawRows(r, x, C_ACC, "SERIES " + String(step + 1) + "/18: tap the white square (normal tap)");
  Serial.printf("TARGET %d/18 row=%d x=%d\n", step + 1, r + 1, x);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n>>> RowProof: v13 sampler, saved anchors, read-only accuracy series");
  tft.begin();
  tft.fillScreen(C_BG);
  tDown = false; tStreak = 0;
  resetStats();
  haveCal = loadCal();
  if (!haveCal) {
    textAt(20, 120, 2, C_TXT, "No saved v13 calibration.");
    textAt(20, 150, 2, C_LABEL, "Run FaceUI and calibrate first.");
    Serial.println("NO CAL: vcal_ver != 13 or anch6 missing. Nothing to test.");
    return;
  }
  Serial.print("anchors:");
  for (int i = 0; i < NANCH; i++) Serial.printf(" %d=%d", i + 1, anchorRaw[i]);
  Serial.println();
  showTarget();
}

void loop() {
  if (!haveCal) { delay(50); return; }
  if (Serial.available()) { if (Serial.read() == 'r') summary(); }
  int raw;
  if (!waitTap(&raw)) { delay(3); return; }
  if (step < 18) {
    int r = step / 3, x = XS[step % 3];
    record(r, x, raw);
    int dn, ds; int m = matchRow(raw, &dn, &ds);
    drawRows(m, -1, m == r ? C_PASS : C_FAIL,
             String(m == r ? "PASS  " : "FAIL  ") + "matched row " + String(m + 1) +
             " (raw " + String(raw) + ")");
    delay(500);
    step++;
    if (step < 18) showTarget();
    else {
      summary();
      drawRows(-1, -1, C_CARD, "FREE MODE: tap any row - it fills. 'r' on serial reprints the summary");
    }
  } else {
    int dn, ds; int m = matchRow(raw, &dn, &ds);
    Serial.printf("FREE raw=%d burst=%d..%d matched=%d margin=%d\n",
                  raw, touchRawMin, touchRawMax, m + 1, ds - dn);
    drawRows(m, -1, C_ACC, "FREE MODE: row " + String(m + 1) + "  raw " + String(raw) +
             "  margin " + String(ds - dn));
  }
}
'''

os.makedirs('RowProof', exist_ok=True)
out = head + lcd + elec + rgb + core + tail
io.open('RowProof/RowProof.ino', 'w', encoding='utf-8', errors='surrogateescape').write(out)
print("RowProof written:", out.count('\n'), "lines; generated core", core.count('\n'), "lines")
