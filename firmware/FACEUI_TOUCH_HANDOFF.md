# FaceUI touch — handoff brief (rewritten 1 Sep 2026)

**One sentence:** the panel produces a clean, repeatable position gradient when
measured, but the *scale* of that reading shifts drastically depending on what
the firmware did in the milliseconds before the sample — so a calibration
captured in one code path does not transfer to another, and taps land on the
wrong row.

Everything below is measured on the bench. Please distrust the interpretations
and re-measure; several confident diagnoses in this file's history were wrong
and are listed as such so they are not repeated.

---

## 1. Hardware — frozen, do not propose rewiring

- Classic **ESP32 dev board**, `esp32:esp32:esp32`, **COM6**, Serial 115200.
- **3.5" 480x320 ILI9486**, 8-bit parallel, mcufriend-style shield, driven by a
  hand-rolled driver in the sketch (not MCUFRIEND_kbv). Landscape, MADCTL 0x28.
- 4-wire resistive touch film sharing the LCD pins.

```
LCD_D0..D7 -> 16, 17, 18, 19, 2, 22, 23, 5
LCD_WR -> 14   LCD_RS -> 33 (J4 "BLK")
LCD_CS -> 21 (U4 "SDA")   LCD_RD -> 12 (J14 "D12")   LCD_RST -> 4

Touch: T_XP = 23 (D6)        T_XM = 33 (RS, ADC1)  <- the pin we read
       T_YP = 14 (WR, ADC2)  T_YM = 5  (D7)
```

The owner has frozen the pin map; a motherboard PCB will reallocate later.
Work within this wiring.

## 2. Sketches

- `firmware/FaceUI/FaceUI.ino` — the product UI. **No WiFi** (deliberately the
  last layer to add).
- `firmware/TouchProof/TouchProof.ino` — the known-good reference: display +
  touch, nothing else. **When in doubt, flash this; it works.**
- `firmware/BoxCal/BoxCal.ino` — the owner's calibration idea, and the best
  result achieved: N labelled boxes, press each one's middle, match live taps
  to the *nearest measured anchor*. Went **15/16** on the bench.
- `firmware/SettleTest/SettleTest.ino` — the settle-delay experiment (below).
- `firmware/GridCal/GridCal.ino` — 4x4 two-axis test (below).
- `firmware/BigUI/BigUI.ino` — abandoned. Palette ideas only; **never copy its
  touch code**.

Build (never use `--output-dir`; it leaves stale binaries):

```
"C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" \
  compile --upload -p COM6 --fqbn esp32:esp32:esp32 f:\freeispserverbox\firmware\FaceUI
```

Uploads intermittently fail with "chip stopped responding" — just retry once.

## 3. THE QUESTION, stated as sharply as the bench allows

**The identical touch-read function returns a different SCALE in different
sketches and different code paths on the same hardware, same wiring, same
finger, minutes apart.**

| Where the sample is taken | Range a press returns |
|---|---|
| `BoxCal.ino` — standalone, **16 rows, 15/16 correct** | **149 – 1011** |
| `FaceUI.ino` calibration walk (8 rows, clean monotonic table) | **2688 – 3613** |
| `FaceUI.ino` live taps in the product loop | **3700 – 4095** (railing) |
| `FaceUI.ino` earlier build, repaint 12ms before the read | **66 – 658** |

All four use the same `zRead()` / `yRead()` primitives, the same 110ms
spacing, the same panel, within the same hour.

The owner's own framing, and he is right: *"when we had the rows, even 16 of
them, we were able to touch even the smaller ones — it's not about pressing
or the chip, the screen knows where we are touching it."* `BoxCal` proves the
panel resolves position finely and repeatably. The failure is not resolution,
not pressure, not calibration technique. **Something about the surrounding
firmware shifts the absolute scale of `analogRead(GPIO33)`.**

Specifically, in the failing case the live samples rail:

```
tap samples: 4095 4095                  -> dropped
tap samples: 3959 4095                  -> dropped
tap samples: 4095 3878 4095 3706 3713   -> median 3713
```

Note the **alternation** — every other sample pinned at 4095 — while the
calibration walk minutes earlier, in the same binary, read clean values.

**Questions for the next engineer:**
1. What differs between a small standalone sketch and a larger one that could
   move an ESP32 ADC1 reading's absolute scale by 3x? (Both are single-core
   Arduino loops with no WiFi. FaceUI additionally links `Preferences`/NVS and
   `esp_task_wdt`, and draws far more.)
2. Could NVS/flash activity, or the LCD write burst, be shifting the ADC
   reference or leaving the shared pins in a different state at sample time?
3. Is there an `analogRead` state (attenuation, width, calibration
   characteristics) being set differently or reset by another library?
4. Given the panel demonstrably resolves position well in isolation, is the
   pragmatic answer to move touch to a dedicated controller (XPT2046/ADS7846)
   on the PCB rather than keep chasing this?

## 4. THE OPEN PROBLEM — detail

The position read is **not a stable function of finger position**. It is a
function of position *and* of what the bus was doing just before the sample.
Three captures, same panel, same person, same glass:

| Context | Reading range |
|---|---|
| Calibration walk (calm; screen drawn once, then 80ms polls) | **2688 … 3613** |
| Product loop *with* a header repaint 12ms before sampling | **66 … 658** |
| Product loop *without* that repaint | **3678 … 3925** |

The calibration walk itself is excellent — monotonic, evenly spaced,
repeatable, and it maps correctly *within* its own screen. The failure is
that the numbers do not survive the trip into a different code path. In the
last build the owner pressed the **top** of the screen and read 3678, which is
above the top anchor (3613), so nearest-anchor matching sent it to the
**bottom** row. Result: everything selects SETTINGS.

Two earlier calibration runs produced **descending** tables (959…121,
997…282); the most recent produced an **ascending** one (2688…3613). The
scale's direction is not stable between builds either, so no code should
assume a direction (`calValid` now accepts both).

**The question to answer:** what makes an `analogRead(GPIO33)` on this rig
return values on a different scale in one code path than another, and how do
we take a position sample whose absolute value is reproducible? Until that is
answered, no calibration scheme can work, because calibration and use are by
definition different code paths.

## 4. What IS solid (do not re-derive)

1. **Detection works.** Idle reads **exactly 0** with no noise across 108
   consecutive samples, so the press gate is 5 with 2-round confirmation.
2. **The panel resolves position well.** A light press at top / middle /
   bottom read 1070 / 533 / 176 — a clean gradient.
3. **Nearest-anchor beats curve fitting.** With a measured value per box, no
   line fit, hinge, or extrapolation is needed. BoxCal scored 15/16 this way.
   The one miss was physical: the top of the glass is compressed (two adjacent
   anchors only 26–47 counts apart, smaller than the ~30 tap error), so the
   very top boxes cannot be resolved. **~8 rows is this panel's honest limit.**
4. **Reads must not be back-to-back.** `zRead()` then `yRead()` immediately
   returns a collapsed value; the sequence that reads true is
   **`zRead()` → wait 110ms → `yRead()`** (`posRead()` in the sketch).
5. **A sample under ~30 is NO CONTACT**, not a low position. A sample costs
   ~220ms, so a quick tap ends before its own read and returns 0 — and 0 maps
   to the bottom of the glass. Never map those; drop them.
6. **One axis only.** GridCal measured the second axis as scatter: spread
   across rows 5091 vs down columns 4596 — statistically nothing. Rows work,
   columns do not. Don't re-open the axis question.

## 5. Ruled out — do not spend time here again

- **ADC settle delay.** Varying `yRead`'s settle from 200µs to 1ms, 5ms, 20ms
  changed the same reading by **2%**. Not a source-impedance settling issue.
- **Force dependence.** Light presses read true position (fact 4.2). Earlier
  "you must press hard" conclusions were artifacts of the back-to-back bug.
- **ADC2 / GPIO14 poisoning ADC1.** Removing the GPIO14 read did not stop the
  railing; the cause was elsewhere.
- **Adafruit's standard pressure formula** (`z = 4095 - (z2 - z1)`). It assumes
  z2 rests at the rail; here it rests near 1749–2840, so the formula idles
  around 2346 and reports a permanent press.
- **Threshold tuning.** Ranged from 400 down to 5. Not the issue.

## 6. Traps that generated fake "the touch is broken" evidence

Most of the wasted time came from the harness, not the panel:

- An endless diagnostic loop called from `setup()` starved the loop-task
  watchdog and **silently rebooted the board** mid-session.
- `calibrate()` called from `setup()` blocks waiting for a press, leaving a
  stale screen and dead serial — which reads exactly like a dead panel.
- A release threshold set *below* the noise floor latched down permanently and
  hung the loop in wait-for-release. **Bound every wait.**
- Counting 4095 as a deviation invented phantom presses at position 0.
- `esp_task_wdt_reset()` from loopTask spams `task not found`; loopTask isn't
  subscribed. `delay()` already yields.
- **White screen = too much drawing, not a dead display.** Adafruit_GFX draws
  lines pixel-by-pixel and each pixel re-sends a window command (~13 bus
  writes). A 64-box grid cost ~170,000 writes and the panel gave up mid-draw.
  Overriding `drawFastHLine`/`drawFastVLine` to use the windowed `fillRect`
  fixed it. Any new dense graphics must respect this.

**Before concluding anything about the hardware, confirm the board is alive
and not rebooting** — reset over RTS and watch for the boot banner.

## 7. Suggested next steps

1. **Characterise the scale shift directly.** One sketch, one screen, no UI:
   sample the same stationary press (a) after 500ms of silence, (b) 12ms after
   a large `fillRect`, (c) 150ms after one, (d) after a full-screen repaint.
   Print all four. That isolates the mechanism instead of inferring it from UI
   behaviour, which is how this went in circles.
2. **If the scale proves shift-prone, stop using absolute values.** Options:
   sample a *reference* alongside every position read and use the ratio; or
   re-measure the two endpoints periodically and normalise; or accept a
   coarse 3–4 zone UI where a 20% scale error still lands correctly.
3. **Keep the UI coarse until it is solved.** The panel's honest resolution is
   ~8 rows in the best case; the product UI needs 6 at most.
4. **Consider the hardware answer.** On the planned PCB, a dedicated touch
   controller (XPT2046/ADS7846, SPI) removes this entire class of problem and
   frees the shared pins. Given how much bench time this has taken, that is
   likely the right long-term call, and the owner should be told plainly.

## 8. Working with the owner (Francis)

- He is at the bench and will press on request. Ask for **one specific press**
  and read the serial log yourself rather than asking him to interpret numbers.
- Pins are frozen until the PCB.
- His grid/box calibration idea is good and produced the best result so far —
  keep it.
- **Change one thing per flash.** Most of the confusion in this log came from
  changing several things between uploads and being unable to attribute the
  result.
