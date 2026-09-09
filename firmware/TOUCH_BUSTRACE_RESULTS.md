> **SUPERSEDED, 9 Sep 2026.** The electrode pin map this document reasons from was WRONG (3 of 4 pins). PinTrace measured the real pairs as GPIO16/33 and GPIO17/21 -- CS is a touch electrode -- and the ADC axis is horizontal in landscape. Every bus-level, image-coupling and parkBusLow() conclusion below was an artefact of driving real film electrodes as if they were idle data pins. Authoritative record: `TOUCH_PINTRACE_RESULTS.md` and `FaceUI/README.md`. Kept for the attempt log and as a record of the misdirection.

# BusTrace results — the reading follows the LCD bus levels, not the image

Run 9 September 2026, 00:13–00:18, `firmware/BusTrace/BusTrace.ino`, one finger
held still per press, 22 presses. This is the experiment proposed in
`TOUCH_REVIEW_REPORT.md` §2. **Its hypothesis is confirmed.**

## 1. Verdict in one line

**With the image fixed, parking LCD data pins D0–D5 HIGH rails the touch
reading to 4095; parking them LOW gives a position-like reading; and the
displayed image (dark vs white) makes no difference once the park state is
held equal.** The earlier "display content dominates" conclusion in
`TOUCH_HELP_REQUEST.md` §1–2 and `FACEUI_TOUCH_HANDOFF.md` §3 is **retracted**:
white and dark fills were leaving `0x3F` and `0x02` on D0–D5, and that — not
the picture — set the reading.

## 2. Method (exactly as the review specified)

- One image painted, never repainted during a press. CS HIGH, RD HIGH,
  **no WR strobe** at any point during a press, no display command — so the
  image cannot change.
- D0–D5 (GPIO 16, 17, 18, 19, 2, 22) parked in three states: all **LOW**, all
  **HIGH**, and **released** (INPUT, no pulls, output register pre-set LOW).
  The park is re-applied immediately before every conversion because
  `done()` re-outputs the bus after each read.
- D6 (XP), D7 (YM), RS (XM) and WR (YP) are left entirely to the unchanged
  `zRead()` / `yRead()` primitives.
- Each press: 3 `zRead → 110 ms → yRead` pairs per state, LOW first.
  Three presses per image, then the other image, cycling. A no-finger
  baseline per state is logged after every repaint.

## 3. The data

No-finger baselines (both images, every phase — 7 phases logged):

```
park=LOW    : 0/0 in 5 of 7 phases; two phases showed 120–225 (finger resting on the glass early)
park=HIGH   : 4095/4095   every sample, every phase, both images
park=INPUT  : 4095 or 3000–4095 floating, every phase, both images
```

Presses (z/y, three pairs each; `--` = 0/0 = contact lost):

| Press | Image | park=LOW | park=HIGH | park=INPUT |
|---|---|---|---|---|
| 1 | DARK | 293/506 · 574/345 · -- | 4095 ×3 | 3855/4095 · 4095 · 4095 |
| 2 | DARK | 558/326 · -- · -- | 4095 ×3 | 3447/4095 · 4095/3461 · 3451/4095 |
| 3 | DARK | 624/828 · 815/476 · -- | 4095 ×3 | 4095 · 4095/3773 · 3917/4095 |
| 4 | WHITE | 621/656 · 656/304 · -- | 4095 ×3 | 4095/3230 · 3850/4095 · 4095 |
| 5 | WHITE | 380/535 · 543/560 · 554/565 | 4095 ×3 | 4095 · 4095 · 3226/4095 |
| 6 | WHITE | 368/0 · 0/362 · 0/222 | 4095 ×3 | 4095/4075 · 4076/4095 · 4095/3690 |
| 7 | DARK | **348/351 · 347/347 · 352/349** | 4095 ×3 | 4095 ×3 |
| 8 | DARK | 351/437 · 454/487 · 481/481 | 4095 ×3 | 4095 ×3 |
| 9 | DARK | 608/557 · 442/230 · 189/347 | 4095 ×3 | 3551/4095 · 4095 · 4095 |
| 10 | WHITE | 196/209 · 208/0 · -- | 4095 ×3 | 4095 ×3 |
| 11 | WHITE | **213/229 · 231/229 · 230/231** | 4095 ×3 | 4095 · 4095 · 4095/3314 |
| 12 | WHITE | 723/720 · 719/880 · 880/891 | 4095 ×3 | 4095 ×3 |
| 13 | DARK | 219/215 · -- · -- | 4095 ×3 | 3615/4095 · 4095/3517 · 3455/4095 |
| 14 | DARK | 59/88 · 112/112 · 122/123 | 4095 ×3 | 4095 ×3 |
| 15 | DARK | **155/161 · 157/165 · 171/174** | 4095 ×3 | 4095 ×3 |
| 16 | WHITE | **213/215 · 222/226 · 234/231** | 4095 ×3 | 4095 · 3024/4095 · 4095 |
| 17 | WHITE | **437/441 · 439/433 · 435/439** | 4095 ×3 | 4095 ×3 |
| 18 | WHITE | 112/158 · 184/227 · 185/149 | 4095 ×3 | 4095 ×3 |
| 19 | DARK | 117/128 · 127/93 · 89/0 | 4095 ×3 | 4095/3229 · 4095 · 4095 |
| 20 | DARK | **323/320 · 321/318 · 321/315** | 4095 ×3 | 4095 ×3 |
| 21 | DARK | 193/213 · 217/215 · 224/234 | 4095 ×3 | 4095 ×3 |
| 22 | WHITE | **179/181 · 180/179 · 185/186** | 4095 ×3 | 4095 ×3 |

Bold rows are the steadiest holds and show what the panel does when the bus
is parked LOW and the finger does not move: **three pairs within ±10 counts,
z and y within a few counts of each other.**

## 4. What this establishes

1. **The dependency is electrical, on the LCD data bus, not optical.** With
   park=HIGH the finger has no effect at all (4095 with or without it), and
   with park=LOW the dark and white images produce overlapping ranges
   (dark: 59–828, white: 112–891). Image is not a variable.
2. **Pins that are not declared electrodes pull the measured node.** D0–D5 are
   not `XP/XM/YP/YM`, yet driving them HIGH rails `XM`/GPIO33 to the top of
   scale. There is a DC path from those six outputs to the measured node. A
   released (INPUT) bus floats to the same rail, which points to something
   on the shield or panel side pulling toward VCC when the MCU lets go —
   consistent with a resistor network, a buffer, or an electrode actually
   being on one of D0–D5 rather than where the pin map says.
3. **Every earlier "scale" mystery is explained by this one variable.**
   - `BoxCal` (near-black screen, last byte `0x82`, D0–D5 = `0x02`) read
     149–1011 and resolved 16 rows: the bus was almost all LOW.
   - `FaceUI` calibration screen read 2607–3792 and Home read ~3990: those
     screens end their draws with brighter colours, leaving more of D0–D5
     HIGH.
   - `ABTrace` "small draw before read" (C_BAR `0x10C4`, D0–D5 = `0x04`) read
     240–270: one bit HIGH, partial pull.
   - The "alternating 4095" samples: consecutive reads with different
     retained states between them.
4. **The 15/16 BoxCal result was the bus being incidentally LOW, not a
   property of that sketch's code.**

## 5. What it does NOT establish yet

- The **physical path** from D0–D5 to the node. That still needs the six bits
  toggled individually (the review's next step) and a look at the shield's
  circuit / electrode continuity. The answer decides whether the current
  pin map is even correct.
- **Positional accuracy** under park=LOW: press positions in this run were
  not recorded, so this shows stability and a plausible range, not that a
  given reading maps to a given row. The review's six-row validation
  protocol (§4) still has to be run on the fixed firmware.
- Whether the residual spread on some presses (e.g. 9, 12, 18) is finger
  movement, contact, or a smaller second effect.

## 6. Firmware consequence — this looks fixable

Park D0–D5 **LOW** before every touch conversion, in both `zRead()` and
`yRead()`, regardless of what was last drawn, and leave them LOW while idle.
The LCD ignores data-line levels without a WR strobe, so this cannot corrupt
the image. This normalises the one variable the experiment isolated, and it
is the "normalising or releasing the bus" firmware path the review said to
pursue if the gradient came back stable across images. It has.

Applied to `firmware/FaceUI/FaceUI.ino` as `parkBusLow()` called at the top
of both primitives, with `CAL_VER` bumped so every stored anchor (all taken
on uncontrolled bus states) is discarded. **Not yet validated** — that is the
next bench step, per §5.

## 7. Questions for the reviewer

1. Given that six non-electrode data outputs pull the sense node to the rail
   and a released bus floats there too, what physical structure on a
   mcufriend-style ILI9486 shield would you expect to be responsible, and
   does it change which four pins we should believe are the electrodes?
2. Is parking LOW sufficient, or should D6/D7 (the declared XP/YM electrodes,
   also data pins) be treated with the same suspicion — i.e. should the
   next single-bit toggle sweep include them?
3. With the bus normalised, does anything in §4 of your review change about
   how to validate six rows, or is the protocol as written still right?

---

## 8. Validation after the fix — FAILED, and what the failure says

Run 9 Sep 2026, 00:22–00:29, `FaceUI.ino` with `parkBusLow()` in both
primitives (D0–D5 = `0x00` before every conversion), fresh calibration
(`CAL_VER 11`), the owner walking the 8-row calibration on the real UI.

### 8a. Raw log (every touch event in the window)

```
cal row 1: no contact, again
tap samples: 37              -> cal row 1 raw=37
cal row 2: no contact, again
tap samples: 32              -> cal row 2 rejected: raw=32, moved -5 from row 1
cal row 2: no contact, again
tap samples: 201             -> cal row 2 raw=201
tap samples: 207 149         -> cal row 3 rejected: raw=207, moved +6 from row 2
tap samples: 166             -> cal row 3 rejected: raw=166, moved -35 from row 2
cal row 3: no contact, again
tap samples: 499 288 87      -> cal row 3 raw=288
tap samples: 79 88           -> cal row 4 rejected: raw=88,  moved -200 from row 3
tap samples: 192             -> cal row 4 rejected: raw=192, moved -96 from row 3
cal row 4: no contact, again
tap samples: 80              -> cal row 4 rejected: raw=80,  moved -208 from row 3
tap samples: 158 56          -> cal row 4 rejected: raw=158, moved -130 from row 3
cal row 4: no contact, again
cal row 4: no contact, again
```

The walk never got past row 4 in seven minutes.

### 8b. What is different from before the fix — and what is not

**Gone:** the 4095 rail. Not one railed sample in the whole run. The bus
dependency isolated in §3 is genuinely removed by parking D0–D5 LOW.

**Not gone — now exposed:** the signal that remains under `0x00` is small and
unstable.

- **Amplitude.** Presses read 32–499. In `BoxCal` (bus incidentally `0x02`)
  the same glass read 149–1011 with ~100 counts per row; in BusTrace §3 under
  `park=LOW` steady holds read 155–891. Here the row-to-row steps that
  survived were 164 and 87, and the rejected ones were −5, +6, −35.
- **Within-press spread.** `499 288 87` inside one held press; `158 56`;
  `207 149`. A 5.7x swing while the finger does not move is not calibration
  error, and no filter can recover position from it.
- **Contact.** Eight "no contact" events — presses where every sample fell
  below the 30-count floor — and most successful presses yielded a single
  sample. Under `0x00` a real press frequently reads in the 30–90 range,
  which the code (tuned when presses read in the hundreds) treats as no
  contact.
- **Direction is not even stable.** Rows 1→2→3 read 37, 201, 288
  (increasing downward); every earlier gradient on this glass *decreased*
  downward (BoxCal A=943 … H=149; SettleTest 1070/533/176). Row 4's four
  attempts (80–192) all sat below row 3, i.e. decreasing again. Either row 1's
  single-sample 37 was a bad contact, or the polarity of the divider itself
  has changed with the bus state. Both are possible; neither is good.

The FaceUI validators (30-count contact floor, 40-count minimum step) make
this worse by discarding marginal samples, but they are not the cause:
`499 → 87` in one hold is the panel, not the software.

### 8c. Interpretation (hypothesis, not proven)

Put §3 and §8 together: D0–D5 HIGH rails the node; D0–D5 LOW leaves a weak,
noisy, possibly inverted signal; and the one bus state that ever produced a
clean 16-row gradient was `0x02` — D1 (GPIO17) HIGH, the rest LOW — reached
by accident in `BoxCal`.

That pattern fits a **bias network**: the six data outputs are not isolated
from the sense node, and their levels set both the offset and the effective
gain of the measurement. All-HIGH saturates it; all-LOW starves it; one
particular bit HIGH happened to bias it into the usable middle. If that is
right, the "fix" of parking everything LOW was the wrong park state, and the
correct one is whichever combination biases the node mid-scale — which the
per-bit sweep below will show directly.

The stronger reading of the same evidence is the one the reviewer raised:
**one or more of D0–D5 are electrically part of the touch circuit**, i.e. the
declared electrode map (`XP=D6, XM=RS, YP=WR, YM=D7`) is wrong or incomplete
for this shield, and "parking" them is actually driving a film electrode.
The polarity flip in §8b would be a natural consequence.

### 8d. The next experiment — staged on the board

`firmware/BitTrace/BitTrace.ino`, the review's own next step. Fixed dark
image, finger held still, no WR strobe. Per press it reads two `z/y` pairs
under each of eight park states, re-applied before every conversion:

```
0x00 (all low)   0x01 D0   0x02 D1 (BoxCal's state)   0x04 D2
0x08 D3          0x10 D4   0x20 D5                     0x3F (all high)
```

plus a no-finger baseline per state. Whichever bit(s) move the reading, and
by how much, identify the coupling path — and if `0x02` alone restores the
BoxCal-quality gradient, that is the park state FaceUI should use.

### 8e. Questions for the reviewer, updated

1. Given §8, do you read this as a bias network on a correctly-mapped node,
   or as a wrong electrode map? What in the per-bit sweep would distinguish
   them?
2. If a single bit HIGH turns out to be the "right" bias, is it legitimate to
   depend on that in production, or is it a fluke of this shield's leakage
   that a second unit would not share?
3. Is there any remaining firmware route you would still pursue if the sweep
   shows the electrodes are not where the pin map says — or does that make
   the dedicated controller (with the film re-wired to it) the only sound
   design?

---

## 9. HANDOFF — state of the board, and the owner's instructions to you

**Written 9 Sep 2026 at 00:40. The previous AI has stopped making changes.**
You are taking over the bench work: the owner's instruction is that you
should **research what other people do with this hardware, decide the fix,
apply it, compile it, flash it, and validate it yourself** — not hand
patches back for someone else to run.

### 9a. What is on the board right now

- Port **COM6** (Silicon Labs CP210x). Board is plugged in and enumerating.
- **Flashed: `firmware/BitTrace/BitTrace.ino`** — the per-bit bus sweep from
  §8d. This is a diagnostic, **not the product UI**. It paints a dark screen
  and waits; each held press logs two `z/y` pairs under each of eight D0–D5
  park patterns. **It has not yet been run with a finger** — the owner has
  not pressed since it was flashed. If you want its data, ask for one
  session of ~5 presses, holding still ~7 s each, and read serial at 115200.
- The product sketch is `firmware/FaceUI/FaceUI.ino` at commit `4805ae6`+:
  `parkBusLow()` drives D0–D5 LOW in both primitives, `CAL_VER 11`. Its
  validation failed as documented in §8. Re-flash it to get the UI back.

### 9b. Toolchain — everything needed to compile and flash

```
"C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" ^
  compile --upload -p COM6 --fqbn esp32:esp32:esp32 F:\freeispserverbox\firmware\<Sketch>
```

- Arduino-ESP32 core 3.3.10 is installed under the IDE; `Adafruit_GFX` is
  the only library dependency.
- Uploads intermittently fail with "chip stopped responding" — retry once.
- **Never pass `--output-dir`**: it leaves stale binaries named after the
  sketch, which has caused a wrong build to be flashed before.
- Serial 115200. Opening the port from PowerShell with `DtrEnable=$false;
  RtsEnable=$false` reads without resetting the board; toggling RTS resets it.
- If Windows shows no COM port: the CP210x will be listed as "Unknown" (i.e.
  remembered, not present) — that is a cable/socket problem, not a driver one.

### 9c. The lead to check first — the electrode map may simply be wrong

The standard library for these shields, **MCUFRIEND_kbv**, ships two examples
that exist *because* 3.5" mcufriend shields are sold with **different touch
electrode-to-pin wirings**: `diagnose_Touchpins.ino` (measures plate
resistance between candidate pin pairs and reports which four pins are the
real XP/XM/YP/YM) and `TouchScreen_Calibr_native.ino`. Documented variants
include electrode sets on the **D8/D9 header pins** — which in 8-bit mode are
the LCD data lines this project calls **D0 and D1**, i.e. **GPIO16 and
GPIO17**.

Hold that against the measurements:

- The only bus state that ever produced a clean 16-row gradient was **D1
  (GPIO17) HIGH**, all else LOW (`0x02`, BoxCal, §4.4).
- Driving D0–D5 HIGH rails the sense node; releasing them floats it to the
  rail (§3).
- Parking them LOW starves the signal and flips its polarity (§8).

If GPIO17 (and possibly GPIO16) are actual film electrodes, every one of
those results is what you would expect from driving an electrode while
believing it was an idle data pin — and "D1 HIGH" was not a bias fluke but the
correct excitation for that plate. **This is a hypothesis; confirm it with
the resistance test, not by assumption.** Porting `diagnose_Touchpins` to the
ESP32 pin numbers in §3 of `TOUCH_HELP_REQUEST.md` is a small job and
would settle the map in one run. The BitTrace sweep already on the board
answers a related question electrically (which bit moves the node).

### 9d. Suggested searches

- `MCUFRIEND_kbv diagnose_Touchpins` — how the plate-resistance test works
  and the list of known pin variants.
- `mcufriend 3.5 ILI9486 touch pins XP YP XM YM variants` — which shields use
  which pairs.
- `ESP32 mcufriend shield touchscreen analogRead shared pins` — others who
  moved these shields to ESP32 and what pin restore sequence they use after
  each read (this project's `done()`/`busOut()` restores direction only).
- `Adafruit TouchScreen library pressure ESP32 4095` — the `z2` rest-level
  issue in attempt #35 of `TOUCH_HELP_REQUEST.md`.

### 9e. Constraints from the owner (unchanged)

- **Pins are frozen** — no rewiring until the PCB. Work with the map as
  fitted, but *verify* what that map actually is.
- Deliverable is a **six-row, full-width UI** that selects the row under the
  finger, correctly, on every screen. Columns are not required.
- **Hold-to-select is not acceptable** as the final UX.
- Do not re-run anything in `TOUCH_HELP_REQUEST.md` §4 — 36 attempts are
  logged there with outcomes.
- Commit and push what you change; the owner's repos deploy from GitHub.
