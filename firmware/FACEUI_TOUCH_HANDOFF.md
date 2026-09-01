# FaceUI touch — handoff brief

**Symptom to solve:** the 3.5" resistive panel calibrates fine, but once the
product UI is showing, taps do nothing. "It only worked when calibrating."

Everything below is measured on the bench, not assumed. Please distrust the
theories and re-measure; several confident-sounding diagnoses in this file's
history were wrong.

---

## 1. Hardware (fixed — do not propose rewiring)

- Classic **ESP32 dev board**, Arduino core, FQBN `esp32:esp32:esp32`, on **COM6**.
- **3.5" 480x320 ILI9486**, 8-bit parallel, mcufriend-style shield, driven by a
  hand-rolled driver (not MCUFRIEND_kbv). Landscape, MADCTL 0x28.
- 4-wire resistive touch film sharing the LCD pins.

```
LCD_D0..D7 -> 16, 17, 18, 19, 2, 22, 23, 5
LCD_WR -> 14   LCD_RS -> 33 (J4 "BLK")
LCD_CS -> 21 (U4 "SDA")   LCD_RD -> 12 (J14 "D12")
LCD_RST -> 4   5V + GND from J4

Touch: T_XP = 23 (D6)   T_XM = 33 (RS, ADC1)
       T_YP = 14 (WR, ADC2)   T_YM = 5 (D7)
```

**The pins are frozen by the owner.** A motherboard PCB will reallocate them
later. Do not suggest moving a wire; work with this map.

## 2. The sketch

`firmware/FaceUI/FaceUI.ino` — single file, **no WiFi** (deliberately the last
layer). Built up from `firmware/TouchProof/TouchProof.ino`, which is the
known-good reference: display + touch, nothing else.

- `firmware/BigUI/BigUI.ino` — abandoned top-down attempt. Palette ideas only.
  **Never copy its touch code.**
- `firmware/HelloScreen/HelloScreen.ino` — the old 1.8" ST7735 product build.
  Unrelated hardware; useful only for visual language.

Build/flash (never use `--output-dir`, it leaves stale binaries):

```
"C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" \
  compile --upload -p COM6 --fqbn esp32:esp32:esp32 f:\freeispserverbox\firmware\FaceUI
```

Serial is 115200. Uploads intermittently fail with "chip stopped responding";
just retry once.

## 3. What is confirmed WORKING

- Display: solid, no streaking.
- Touch detection during calibration: real, repeatable.
- 3-point calibration (top / middle / bottom crosshairs, press-and-hold),
  stored in NVS namespace `freeisp`, keys `vcal_ver`/`vcal_a`/`vcal_b`/`vcal_c`,
  `CAL_VER = 3`.
- Persistence across reboot. Last good map read back after a reset:
  **a=1639, b=919, c=256** (segments -720 and -663 — evenly spaced).
- Coordinate mapping arithmetic: a live tap logged `raw=613 -> y=215`, which is
  exact for those anchors under the piecewise map.

## 4. What is NOT working

Taps on the normal UI (Home / Settings / Info) do not register. The same finger
on the calibration screen registers reliably.

## 5. Measured facts about this panel (these cost a lot of bench time)

1. **Both reads are position-dependent, and both die at one end of the glass.**
   `zRead()` (XP low, YM high, read XM) IS a position gradient. At the XP end it
   reads ~0 — identical to an untouched panel. A press there is not weak, it is
   invisible. The owner spotted this: *"press the points and z is 0, press any
   other place and it presses well."* The bottom of the screen is that end,
   which is why the SETTINGS band specifically was unreachable for hours.

2. **Reads must not be taken back to back.** A tight loop of `zRead()` alone
   leaves the sense node charged and returns a frozen **4095** — indistinguishable
   from a dead panel. Interleave `zRead()` then `yRead()`; the y-config
   reconfigures all four lines and lets the node settle. (Repo commit 5ec1126.)

3. **The redraw is not cosmetic — it is part of the touch circuit's recovery.**
   With only a 3x3-pixel draw per poll round, both signals rail to 4095 within
   seconds. Repainting large text every round holds them at a flat **0 for
   minutes**. This is the current best explanation for the open bug: calibration
   repaints its live readout constantly, the product loop did not.

4. **Rest levels are measured, never assumed.** At boot, hands off the glass:
   `XM = 0`, `yRead = 0`. A genuine press lifts them to roughly **830**
   (TouchProof measured 833/826). Legitimate position values live in the
   hundreds-to-~1900 range. **4095 is always the artifact, never a real reading.**

5. **GPIO14 (T_YP) is ADC2.** There is no WiFi here so it *can* be read, but
   adding an `analogRead(T_YP)` alongside the ADC1 reads coincided with both
   ADC1 signals railing. Treat a second-axis read as suspect until proven.

6. **Adafruit's standard pressure formula does not work as written here.**
   `z = 4095 - (z2 - z1)` assumes z2 rests at the rail. On this panel z2 rests
   near **1749–2840**, so the formula idles around 2346 and reports a permanent
   press. If you use it, calibrate the rest level; do not assume rails.

## 6. Traps that produced fake "touch is broken" evidence

Much of the earlier debugging chased ghosts created by the harness itself:

- An endless diagnostic loop called from `setup()` starved the loop-task
  watchdog and **silently rebooted the board** mid-session.
- `calibrate()` was also called from `setup()` and blocks waiting for a press,
  so the glass sat on a stale screen with serial dead — which read as
  "the panel is dead" when nothing was wrong.
- A release threshold set *below* the noise floor latched the state down
  permanently and hung the loop in wait-for-release. **Bound every wait.**
- Counting 4095 as a deviation invented phantom presses with position 0.

**Before concluding anything about the hardware, confirm the board is alive and
not rebooting.** Reset it over RTS and watch for the boot banner.

## 7. Current hypothesis and the change just made

Hypothesis: fact 5.3 explains the open bug. The product loop polled every 15ms
while drawing ~4 pixels per second, which rails both signals; railed reads are
discarded upstream, so no press can ever be seen on Home. Calibration survived
because its own repaint kept the panel alive.

Change applied (untested by the owner at time of writing): every poll round in
`loop()` now repaints an invisible 80x20 header-coloured rect and waits 100ms,
matching calibration's cadence and workload.

**If that did not fix it, the next things to check, in order:**

1. Instrument `loop()`'s idle path to print `tZ1`/`tZ2` once a second. If they
   read 4095 there but 0 during calibration, hypothesis confirmed and the fix
   just needs more bus work per round. If they read 0 in both, the detector is
   fine and the fault is in `waitTap()`/`readTapRaw()` gating instead.
2. `readTapRaw()` requires **3+ rounds** of contact at 110ms each — roughly a
   third of a second of steady press. A quick tap returns -1 and is silently
   discarded. Consider accepting 2 rounds, and log every discard.
3. `waitTap()` has a `stuckDown` latch; verify it cannot get stuck asserted.
4. The HOME gate is `sy >= 240` for the SETTINGS band (drawn at 268-319),
   deliberately loose. Log every mapped `sy` to confirm taps land where the
   finger is before blaming detection.

## 8. Owner's preferences

- Pins frozen; PCB comes later.
- He wants **every part of the UI touchable**, and calibration by pressing
  targets/boxes he can see — his idea, and a good one.
- He is at the bench and can press on request; ask for one specific press and
  read the serial log rather than asking him to interpret numbers.
