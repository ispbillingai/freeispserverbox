# Resistive touch on ESP32 + ILI9486 — escalation / request for help

**What we want from you:** a way to make a 6-row touch UI select the row under
the finger, reliably, on a shield whose touch reading is dominated by what the
LCD is displaying. Or a clear verdict that this is not solvable in firmware on
this wiring, so we stop and commit to the hardware fix.

You have access to the codebase. Every number below is measured on the bench,
by hand, on the real device. Interpretations are flagged as hypotheses —
several of our confident diagnoses have already been disproved by later
measurements, and those are recorded here too so you do not repeat them.

---

## 1. The single most important measurement

`firmware/ABTrace/ABTrace.ino`. **One finger held still at screen centre**,
never lifted. Each case paints the screen, waits, then performs one
`zRead() -> 110 ms -> yRead()`:

```
1 no draw             :  z= 638 y= 672 | z= 646 y= 674 | z= 679 y= 675 | z= 689 y= 703
2 small draw BEFORE z :  z= 240 y= 242 | z= 247 y= 243 | z= 243 y= 246 | z= 246 y= 245
3 small draw z..y     :  z= 247 y= 245 | z= 246 y= 243 | z= 246 y= 244 | z= 252 y= 240
4 FULL repaint before :  z= 683 y= 685 | z= 688 y= 672 | z= 655 y= 653 | z= 597 y=   0
5 screen DARK  +300ms :  z=   0 y=   0 | z=   0 y=   0 | z=   0 y=   0 | z=   0 y=   0
6 screen WHITE +300ms :  z=4095 y=4095 | z=4095 y=4095 | z=4095 y=4095 | z=4095 y=4095
7 screen DARK  +2000  :  z=   0 y=   0 | z=   0 y=   0 | z=   0 y=   0 | z=   0 y=   0
8 screen WHITE +2000  :  z=4095 y=4095 | z=4095 y=4095 | z=4095 y=4095 | z=4095 y=4095
```

Reproduced across several presses. Every sample. No exceptions.

**A white screen rails the reading to 4095. A black screen drives it to 0.**
Identical finger, identical position. Still true a full **two seconds** after
painting, so this is the steady-state displayed image, **not** the write burst
decaying.

Secondary, also repeatable: a **small** (80x20 px) write immediately before the
read suppresses the value to ~40% (240–270), and does so very consistently,
while a **full-screen** repaint does not — we assume because a full repaint
takes ~200 ms and so supplies its own settle time.

## 2. Why that breaks everything

Same panel, same primitives, same person, inside one hour:

| Sketch / screen context | Range a real press returns |
|---|---|
| `BoxCal.ino` — standalone, near-black screen. **Resolved 16 rows, 15/16 taps correct** | **149 – 1011** |
| `FaceUI.ino` calibration screen (dark grid) | **2607 – 3792** |
| `FaceUI.ino` Home screen (bright cards) | **~3960 – 3990** |
| `FaceUI.ino` with a small repaint 12 ms before the read | **66 – 658** |

So the calibration walk produces a clean monotonic table, and then the product
UI reads **~350 counts above the entire table** because Home is brighter — and
every tap maps to the bottom row.

The owner's own framing is exact: *"if the grid touch is perfect, why is this
other thing hard?"* Because the grid never has to answer **where** the finger
is — it records a number for the box it told him to press. The UI must do the
inverse, and that requires the number to still mean the same thing on a
different screen. It does not.

## 3. Hardware — frozen, cannot be rewired at this stage

- Classic **ESP32 dev board**, Arduino-ESP32 core 3.3.10, FQBN
  `esp32:esp32:esp32`, COM6, Serial 115200. **No WiFi is linked in any sketch
  discussed here**, so ADC2 is nominally available.
- **3.5" 480x320 ILI9486**, 8-bit parallel, mcufriend-style shield, driven by a
  hand-rolled driver (not MCUFRIEND_kbv). Landscape, MADCTL 0x28.
- 4-wire resistive film sharing the LCD pins:

```
LCD_D0..D7 -> 16, 17, 18, 19, 2, 22, 23, 5
LCD_WR -> 14    LCD_RS -> 33 (J4 "BLK")
LCD_CS -> 21 (U4 "SDA")    LCD_RD -> 12 (J14 "D12")    LCD_RST -> 4

Touch: T_XP = 23 (LCD_D6)          T_XM = 33 (LCD_RS, ADC1)  <-- the pin read
       T_YP = 14 (LCD_WR, ADC2)    T_YM = 5  (LCD_D7)
```

**`T_XM` is also `LCD_RS`.** `done()` calls `busOut()`, which makes GPIO33 an
LCD output and drives it HIGH — immediately before the next touch conversion
re-samples that same pin as a high-impedance ADC input. There is no isolation
between the display bus and the measurement.

The two read primitives, unchanged from the sketch that demonstrably works:

```c
int zRead() {                       // XP low, YM high, read XM
  tft.desel();
  pinMode(T_XP, OUTPUT); digitalWrite(T_XP, LOW);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, HIGH);
  pinMode(T_XM, INPUT);  pinMode(T_YP, INPUT);
  delayMicroseconds(200);
  int v = analogRead(T_XM);
  done();                           // busOut(); sel();  -> RS driven HIGH
  return v;
}
int yRead() {                       // drive the Y plate, read the X plate
  tft.desel();
  pinMode(T_XP, INPUT);  pinMode(T_XM, INPUT);
  pinMode(T_YP, OUTPUT); digitalWrite(T_YP, HIGH);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, LOW);
  delayMicroseconds(200);
  int v = analogRead(T_XM);
  done();
  return v;
}
```

No `analogSetPinAttenuation`, no `analogReadResolution`, no `driver/adc.h`
anywhere — plain `analogRead` on Arduino defaults, **identical in the working
and the failing sketches**.

## 4. Everything we have tried

Legend: `+` helped · `0` no effect · `-` made it worse · `!` actively misled us.

### 4a. Detection and thresholds

| # | Attempt | Result |
|---|---|---|
| 1 | Fixed deviation gate of 400 from a measured idle | `-` Wrote the weak bottom of the glass off the map entirely |
| 2 | Hysteresis 140 enter / 90 exit, 2-round confirm | `+` Better; still missed light presses |
| 3 | Exit threshold **below** the noise floor (60 vs ±80) | `!` Latched permanently down and hung the loop in wait-for-release — looked exactly like a dead panel |
| 4 | Gate swept 260 → 120 → 40 → 20 → 10 → **5** | `+` Idle measures **exactly 0** with no noise, so 5 is safe. Current value |
| 5 | Dual-polarity sum (sample the node under both drive polarities) | `0` The sum never separated a press from a float as theory predicted |
| 6 | Third electrode (`YP`/GPIO14, ADC2) as a detector | `-` Rest level 2834 with ±80 noise; drifted 1000+ counts within minutes |
| 7 | Treating 4095 as a valid deviation | `!` Invented phantom presses with position 0 |
| 8 | Railed-read cutoff 4000 → **4090** | `+` Home's bias lifts *genuine* reads to ~3990; the old cutoff silently discarded every real tap on Home |

### 4b. Position sampling

| # | Attempt | Result |
|---|---|---|
| 9 | Reuse the `yRead` taken back-to-back with `zRead` in the detector | `-` Collapses badly on light presses; quick taps reported bottom-of-scale wherever the finger was |
| 10 | **`zRead` → 110 ms → `yRead`** (`posRead`) | `+` A light press then reads true: **1070 top / 533 middle / 176 bottom**. Kept |
| 11 | `yRead` settle delay 200 µs → 1 ms → 5 ms → 20 ms | `0` Same reading ±2%. **Settling is not the mechanism** |
| 12 | 50 ms "seat" delay before sampling | `-` All three calibration targets converged to one number — the firm phase reads *pressure*, not position |
| 13 | Median of 5 nested rounds per sample (35 conversions per tap) | `-` Recreated the 4095 charged-node failure |
| 14 | Discard the first sample of each press | `0` No improvement; alternating rails persisted |
| 15 | Peak instead of median | `+`/`0` Helped while contact error was one-directional; superseded |
| 16 | Drop samples < 30 as **no contact**, not as low positions | `+` A quick tap ends before its own 220 ms sample and returns 0, which maps to the bottom row. This was half of "every press selects Info" |
| 17 | Hold-to-select (require 4 rounds ≈ 0.44 s) | `+`/`-` Worked, but only as a workaround for #9, and unacceptable UX. Reverted |
| 18 | **Paint a fixed rect before every read** to standardise panel state | `-` **Flattened the entire scale to 48–126**, leaving no gradient to calibrate against |
| 19 | Reject taps reading below the calibrated span | `-` Correctly criticised in review: a genuine press below the bottom anchor legitimately extrapolates under it, so this made the real bottom strip untouchable |

### 4c. Calibration schemes

| # | Attempt | Result |
|---|---|---|
| 20 | 2-point linear (top and bottom bars) | `-` One line through two soft presses squeezed the bottom of the glass shut |
| 21 | 3-point piecewise with a middle hinge | `-` Better; still mapped taps into the wrong row |
| 22 | Validator demanding evenly-spaced halves (3x skew rule) | `!` Rejected *good* calibrations — the hinge exists precisely to absorb uneven halves |
| 23 | **8 anchors, one per row, nearest-neighbour match** | `+` Clean monotonic table every time. No fit, no extrapolation |
| 24 | **16 anchors** (`BoxCal.ino`) | `+` **Best result achieved: 15/16 test taps correct.** The one miss was a 20-count sliver at the panel's compressed top — the glass's own limit, not code |
| 25 | 4x4 grid, second axis (`GridCal.ino`) | `-` X spread **across** rows 5091 vs **down** columns 4596 → scatter. **No usable horizontal axis.** Rows only |
| 26 | Self-checking walk (reject a step that reverses or is < 40) | `+` The walk previously accepted a press *anywhere* and advanced, so a press at the wrong height silently became that row's anchor |
| 27 | Match the calibration screen's brightness to the UI's | `+` partial — narrowed the offset but did not remove it |
| 28 | Measure the offset with one known tap (SETTINGS) and shift the whole table | `?` Current approach. Logically sound; **not yet confirmed end-to-end** |

### 4d. Red herrings that cost hours

| # | Belief at the time | What was actually true |
|---|---|---|
| 29 | "WiFi steals ADC2" | Wrong here — no WiFi is linked. Inherited from an earlier sketch's notes |
| 30 | "The panel is force-dependent, press harder" | Wrong — a light press reads true position once #10 was applied |
| 31 | "The readable axis may be horizontal; rotate the UI to portrait" | Wrong — #25 settled it, and z/y return nearly the same number (221 vs 224) |
| 32 | "The poll loop lacks bus traffic, so the node rails" | Wrong — 108 consecutive idle samples on Home read a flat 0, never railed |
| 33 | Endless diagnostic loop called from `setup()` | Starved the loop-task watchdog → **silent reboots** that looked exactly like a dead panel |
| 34 | `calibrate()` also called from `setup()` | Blocks waiting for a press, so the glass sat on a stale screen with serial dead |
| 35 | Adafruit `TouchScreen` pressure formula `z = 4095-(z2-z1)` | Assumes z2 rests at the rail; here it rests 1749–2840, so it idles ~2346 = permanent press |
| 36 | Dense grid drawn with `drawRect` | Adafruit_GFX draws lines pixel-by-pixel, each pixel re-sending a window command (~13 bus writes). A 64-box grid = ~170,000 writes and the panel gave up mid-draw → **white screen**. Fixed by overriding `drawFastHLine`/`drawFastVLine` to use the windowed `fillRect` |

## 5. Current implementation (`firmware/FaceUI/FaceUI.ino`)

```c
#define T_ON  5        // idle measures exactly 0, so this is safe
#define T_OFF 3        // 2 consecutive rounds required to latch either way
#define NANCH 8        // 8 anchors, one per 40px row
#define CAL_VER 10

int posRead() { zRead(); delay(110); return yRead(); }   // the proven sequence

int readTapRaw() {                        // BoxCal's capture(), verbatim
  int cap[6], m = 0;
  while (touchDown() && m < 6) {
    int v = posRead();
    if (v >= 30 && v < 4090) cap[m++] = v;   // <30 = no contact, >=4090 = artifact
    delay(60);
  }
  if (m < 1) return -1;
  /* median of cap[0..m-1] */
}

int screenY(int raw) {                    // nearest measured anchor wins
  int best = 0, bd = 32767;
  for (int i = 0; i < NANCH; i++) {
    int d = abs(raw - anchorRaw[i]);
    if (d < bd) { bd = d; best = i; }
  }
  return best * BAND + BAND / 2;
}
```

Calibration walks 8 rows, rejects any step that reverses or is under 40 counts,
then asks for one tap on the SETTINGS band **on the real Home screen** and
shifts the whole anchor table by `raw - anchorRaw[7]` to move it onto Home's
scale. Status: the walk passes; the end-to-end result is **not yet confirmed**.

## 6. What we are asking

1. **Is this display-content coupling expected for this class of shield, and is
   there a known firmware mitigation?** Everything we tried (attempts 10, 18,
   27, 28) either failed or destroyed the gradient. #18 is the most striking:
   standardising the panel state with a fixed pre-read paint flattened the
   scale to 48–126 and left nothing to calibrate.

2. **Is there a read sequence that isolates the film from the panel?** Given
   `T_XM` doubles as `LCD_RS`: is it legitimate and safe to put the LCD into
   display-off / sleep (0x28 / 0x10) around the touch sample, or to tri-state
   the data bus — and would either actually decouple the film? We have not
   tried this and would rather be told than guess.

3. **Is "per-screen calibration + one measured constant offset" sound**, or is
   the bias non-linear enough across the 0–4095 range that it can never be
   reliable? Note that white → 4095 and black → 0 are both *rails*, which
   suggests the usable region may be narrow and content-dependent in a way a
   single offset cannot capture.

4. **Would you go straight to hardware?** Our plan is an **XPT2046 / ADS7846**
   on the PCB we are already designing — it owns the four electrodes, controls
   excitation and sample timing, and does not share a pin with the LCD command
   line. Is that the right call, or is there a firmware route we have missed?

## 7. What "working" has to mean

A coarse UI only. **Six full-width rows, no columns** (the horizontal axis is
unmeasurable on this wiring — attempt #25). A press must select the row under
the finger, on any screen, every time. We do not need fine resolution. We need
it to be **correct**, without the user having to think about it.

## 8. Files

| Path | What it is |
|---|---|
| `firmware/FaceUI/FaceUI.ino` | The product UI — the one failing (966 lines) |
| `firmware/BoxCal/BoxCal.ino` | **Best working result**: 16 rows, 15/16 correct (301) |
| `firmware/TouchProof/TouchProof.ino` | Minimal known-good display + touch (174) |
| `firmware/ABTrace/ABTrace.ino` | The experiment that produced §1 (254) |
| `firmware/GridCal/GridCal.ino` | Two-axis test that ruled out columns (364) |
| `firmware/SettleTest/SettleTest.ino` | Settle-delay test, attempt #11 (234) |
| `firmware/FACEUI_TOUCH_HANDOFF.md` | Long-form history and earlier reasoning |

Build and flash (never use `--output-dir`; it leaves stale binaries):

```
"C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" \
  compile --upload -p COM6 --fqbn esp32:esp32:esp32 firmware/FaceUI
```

Uploads intermittently fail with "chip stopped responding" — retry once.
