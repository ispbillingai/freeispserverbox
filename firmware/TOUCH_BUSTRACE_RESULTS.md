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
