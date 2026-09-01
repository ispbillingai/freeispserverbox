# Request for help — resistive touch on an ESP32 + ILI9486 shield

We are stuck and would value a second opinion. Everything here is measured on
the bench, and the interpretations are offered as hypotheses, not conclusions —
several confident diagnoses of ours have already turned out to be wrong.

---

## The one-line problem

The touch panel produces a clean, repeatable position gradient when we measure
it — but **the absolute value of that reading is set by what is displayed on
the LCD**, so a calibration captured on one screen does not work on another,
and taps land on the wrong row.

## Hardware (fixed — cannot be rewired at this stage)

- Classic **ESP32 dev board**, Arduino core 3.3.10, FQBN `esp32:esp32:esp32`,
  COM6, Serial 115200. **No WiFi is linked in any of these sketches.**
- **3.5" 480x320 ILI9486**, 8-bit parallel, mcufriend-style shield, driven by a
  hand-rolled driver (not MCUFRIEND_kbv). Landscape, MADCTL 0x28.
- 4-wire resistive touch film sharing the LCD pins:

```
LCD_D0..D7 -> 16, 17, 18, 19, 2, 22, 23, 5
LCD_WR -> 14   LCD_RS -> 33 (J4 "BLK")
LCD_CS -> 21 (U4 "SDA")   LCD_RD -> 12 (J14 "D12")   LCD_RST -> 4

Touch: T_XP = 23 (LCD_D6)        T_XM = 33 (LCD_RS, ADC1)  <- the pin read
       T_YP = 14 (LCD_WR, ADC2)  T_YM = 5  (LCD_D7)
```

Note `T_XM` is **also LCD_RS**, and the display code drives it HIGH as an
output (`busOut()`) immediately before each touch conversion re-samples it as
a high-impedance ADC input.

The two read primitives (from a sketch that demonstrably works):

```c
int zRead() {                       // XP low, YM high, read XM
  tft.desel();
  pinMode(T_XP, OUTPUT); digitalWrite(T_XP, LOW);
  pinMode(T_YM, OUTPUT); digitalWrite(T_YM, HIGH);
  pinMode(T_XM, INPUT);  pinMode(T_YP, INPUT);
  delayMicroseconds(200);
  int v = analogRead(T_XM);
  done();                           // = busOut(); sel();  -> RS driven HIGH
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

No `analogSetPinAttenuation`, no `analogReadResolution`, no `driver/adc.h` —
plain `analogRead` with Arduino defaults, identical in every sketch below.

## THE KEY MEASUREMENT

`ABTrace.ino`. One finger held still at screen centre. Each case paints, waits,
then does `zRead → 110ms → yRead`. The waits are long enough that the write
burst itself has finished:

```
1 no draw             :  z= 638 y= 672 | z= 646 y= 674 | z= 679 y= 675 | z= 689 y= 703
2 small draw BEFORE z :  z= 240 y= 242 | z= 247 y= 243 | z= 243 y= 246 | z= 246 y= 245
3 small draw z..y     :  z= 247 y= 245 | z= 246 y= 243 | z= 246 y= 244 | z= 252 y= 240
5 screen DARK  +300ms :  z=   0 y=   0 | z=   0 y=   0 | z=   0 y=   0 | z=   0 y=   0
6 screen WHITE +300ms :  z=4095 y=4095 | z=4095 y=4095 | z=4095 y=4095 | z=4095 y=4095
7 screen DARK  +2000  :  z=   0 y=   0 | z=   0 y=   0 | z=   0 y=   0 | z=   0 y=   0
8 screen WHITE +2000  :  z=4095 y=4095 | z=4095 y=4095 | z=4095 y=4095 | z=4095 y=4095
```

Reproduced across several presses, every sample, no exceptions.

- **A white screen rails the reading to 4095. A black screen drives it to 0.**
  Same finger, same position, unchanged for 2 full seconds after painting — so
  it is the steady-state image, not the write burst decaying.
- A screen with **mixed/moderate content and no recent write** reads ~600–700,
  which we believe is the true value for that finger position.
- A **small** write (80x20 px) immediately before the read suppresses the value
  to ~40% (240–270), and does so very repeatably.
- A **full-screen** repaint before the read does *not* suppress it — we assume
  because it takes ~200ms and supplies its own settle time.

## How that plays out across sketches

Same panel, same primitives, same person, within one hour:

| Sketch / context | Reading range for a press |
|---|---|
| `BoxCal.ino` — standalone, near-black screen, **resolved 16 rows, 15/16 correct** | **149 – 1011** |
| `FaceUI.ino` calibration screen (dark grid) | **2607 – 3792** |
| `FaceUI.ino` Home screen (bright cards) | **~3960 – 3990** |
| `FaceUI.ino` with a small repaint 12ms before the read | **66 – 658** |

So a calibration walk yields a lovely monotonic table, and then the product UI
reads ~350 higher than the entire table because the Home screen is brighter —
and every tap maps to the bottom row.

## What we have already ruled out (please don't re-test these)

- **ADC settle time.** Varying `yRead`'s settle from 200µs → 1ms → 5ms → 20ms
  changed the same reading by **2%**.
- **ADC2 / GPIO14.** Removing the second-pin read entirely did not change the
  behaviour. (There is no WiFi, so ADC2 is nominally usable.)
- **ADC configuration.** No attenuation/resolution calls anywhere; defaults
  everywhere; identical between the working and failing sketches.
- **Pressure / force.** A light press reads true position (1070 / 533 / 176 for
  top / middle / bottom).
- **Adafruit's `TouchScreen` pressure formula** (`z = 4095 - (z2 - z1)`). It
  assumes z2 rests at the rail; here it rests near 1749–2840, so the formula
  idles ~2346 and reports a permanent press.
- **Thresholds.** Swept from 400 down to 5. The panel's idle is *exactly* 0
  with no noise, so detection is not the issue.
- **Calibration technique.** 2-point, 3-point piecewise, 8-anchor and 16-anchor
  nearest-neighbour lookup tables. Nearest-anchor with 8–16 anchors is clearly
  the best of these and works *within* one screen.

## Also worth knowing (cost us time)

- A **white screen is not a dead display** — but a **blank white screen after a
  dense draw** was: Adafruit_GFX draws lines pixel-by-pixel and each pixel
  re-sends a window command (~13 bus writes), so a 64-box grid cost ~170,000
  writes and the panel gave up mid-draw. Overriding `drawFastHLine` /
  `drawFastVLine` to use the windowed `fillRect` fixed that.
- `esp_task_wdt_reset()` from loopTask logs `task not found` — loopTask isn't
  subscribed; `delay()` already yields.
- Blocking waits called from `setup()` starve the loop-task watchdog and
  silently reboot the board, which looks exactly like a dead panel.

## Our questions

1. **Is the display-content coupling we measured expected for this class of
   shield, and is there a known firmware mitigation?** Everything we have tried
   (settling, standardising the pre-read paint, matching screen brightness
   between calibration and UI) either failed or destroyed the gradient. The
   one that destroyed it is notable: painting a fixed rectangle before *every*
   read flattened the whole scale to 48–126 with no usable gradient left.
2. **Is there a read sequence that isolates the film from the panel?** For
   example, is it legitimate/safe to put the LCD into sleep or display-off
   (0x28 / 0x10) around the touch sample, or to tri-state the data bus, given
   `T_XM` doubles as `LCD_RS`?
3. **Is a per-screen calibration plus a measured constant offset a sound
   approach**, or is the bias non-linear enough across the range that it will
   never be reliable? We currently measure the offset with a single known tap
   (on the SETTINGS band) and shift the whole anchor table by it.
4. **Would you go straight to hardware?** Our plan is a dedicated
   **XPT2046 / ADS7846** touch controller on the PCB we are designing, which
   would own the four electrodes, control excitation and sample timing, and
   not share a pin with the LCD command line. Is that the right call, or is
   there a firmware route we have missed?

## What "working" needs to look like

A coarse UI only: **six full-width rows**, no columns (the horizontal axis is
unmeasurable on this wiring — we tested it: X spread across rows 5091 vs down
columns 4596, i.e. scatter). A press must select the row under the finger,
reliably, on any screen. We do not need fine resolution — we need it to be
*correct*.

## Files

- `firmware/FaceUI/FaceUI.ino` — the product UI (the one failing).
- `firmware/BoxCal/BoxCal.ino` — the best working result (16 rows, 15/16).
- `firmware/TouchProof/TouchProof.ino` — minimal known-good display + touch.
- `firmware/ABTrace/ABTrace.ino` — the experiment that produced the table above.
- `firmware/GridCal/GridCal.ino` — the two-axis test that ruled out columns.
- `firmware/FACEUI_TOUCH_HANDOFF.md` — the long-form history.
