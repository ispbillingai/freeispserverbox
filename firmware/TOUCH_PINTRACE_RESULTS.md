# PinTrace: the declared touch map is wrong

Measured directly over COM6 on 9 September 2026 after the owner confirmed
the glass was untouched. Raw logs are in `firmware/PinTrace/`.

The final scan held RD/GPIO12, WR/GPIO14 and reset/GPIO4 HIGH, and tested
D0–D7, RS and CS. All ten unloaded inputs followed their own weak pulls
normally: eight HIGH samples with pull-up, zero with pull-down.

Exactly these connections followed a strong drive against the opposing
weak pull, in both polarities and both directions:

| Pair | Connection | LOW drive | HIGH drive |
|---|---|---|---|
| A | D0/GPIO16 to RS/GPIO33 | 0/8 HIGH samples | 8/8 HIGH samples |
| A reversed | RS/GPIO33 to D0/GPIO16 | 0/8 | 8/8 |
| B | D1/GPIO17 to CS/GPIO21 | 0/8 | 8/8 |
| B reversed | CS/GPIO21 to D1/GPIO17 | 0/8 | 8/8 |

No other tested combination followed its drive. See
`PinTrace/scan-untouched-cs.txt` for every reading.

This is strong evidence for two resistive-film plate pairs on **16/33 and
17/21**. It identifies conductive connections, not their resistance in ohms
or physical orientation. Contact and position measurements remain necessary
to confirm the functional electrode assignment.

The old map used 23/33 and 14/5. Three of those four GPIO assignments are
inconsistent with the measured pairs. The newly identified four-electrode
set is **GPIO16, GPIO33, GPIO17, GPIO21**; naming their polarities is a
software convention until the physical axis test.

The first scan held CS HIGH and found D1 permanently HIGH against its weak
pull-down. Releasing CS in the final scan removed this effect and exposed
the reciprocal D1–CS connection. This explains that initial anomaly.

The intermediate scan released RD. Several data inputs then became loaded
or unstable despite the MCU CS setting. Its results are not usable for
pair identification; the physical reason for that disturbance has not
been measured. The final scan keeps both read and write strobes inactive.

## Consequences for the firmware

The earlier `parkBusLow()` drives actual electrodes D0 and D1 LOW. The old
position routine drives WR and D7, which did not test as their plate pair.
It therefore does not implement the intended four-wire position divider.
The bus dependency now has a concrete explanation beyond a hypothetical
leakage bias. Further tuning of that sampling sequence is unwarranted.

Touch now shares **CS** as well as RS. Any new read sequence must keep WR
and RD HIGH throughout measurement. It must restore CS to output mode and
restore all bus pin modes before drawing. The old `busOut()` does not
restore CS mode because the old map assumed CS was never an electrode.

Only GPIO33 among the four measured electrodes is ADC-capable on the classic
ESP32. GPIO21 can drive or detect digital contact but cannot be passed to
`analogRead()` for the second axis. See the
[Espressif pin-function table](https://documentation.espressif.com/esp32_datasheet_en.html).
Correct electrode identification does
not by itself prove that the accessible analog axis is vertical in the
current landscape display. The previous wrong-map axis experiment cannot
settle this question.

## Next bench stage

`firmware/AxisProof/AxisProof.ino` excites the 21/17 plate, leaves GPIO16
floating, and samples GPIO33. Contact detection grounds both 21/17 ends
and checks whether the opposing plate pulls a weakly pulled-up GPIO33 LOW.
It keeps both LCD strobes inactive while using CS as an electrode.

Five labelled targets are presented: top, centre, bottom, left, right.
Normal taps capture a short burst under unchanged excitation. There is no
110 ms inter-read gap, hold-to-select requirement, screen offset fit, or
calibration/NVS write. Results report both vertical and horizontal spans.
The physical taps must be supplied by the owner; software cannot verify
the finger's location independently.

The product FaceUI has not yet been modified. Its saved calibration belongs
to the wrong electrode map and must be invalidated if the corrected map is
integrated. Six-row accuracy and cross-screen behaviour remain unverified.

## First axis run: target positions confirmed by the owner

The owner confirmed tapping each green square in TOP, CENTRE, BOTTOM, LEFT,
RIGHT order. The firmware reported:

```
AXIS RESULT top=3472 centre=1693 bottom=2157 left=331 right=3282 verticalSpan=1315 horizontalSpan=2951
```

The captured bottom burst ranged 2143–2167, left 326–333, and right
3277–3287. The serial stream before those lines contained substantial
non-printable data; the final summary was readable. A clean repeat is needed.
The extracted readable lines are in `AxisProof/axis-first-summary.txt`.

This shows a strong left-to-right response, but the three centre-line
positions disagree more than expected for a clean horizontal-only axis.
Do not declare vertical accuracy, or a hardware-only verdict, from this one
run. COM6 subsequently failed to open with “A device attached to the system
is not functioning”; Windows PnP still reported the CP210x as OK. The owner
was asked to reconnect USB before the repeat.

The owner reconnected USB, but COM6 still failed with the same message in
PowerShell both inside and outside the sandbox, and independently in
Arduino CLI's serial monitor. A targeted `pnputil /restart-device` for the
CP210x was denied by Windows. No repeat samples were collected. AxisProof
remains the last successfully flashed sketch; FaceUI is not running.

Those errors described this agent's attempts to open COM6, not proof that
the module was disconnected or its cable faulty. The owner subsequently
reported successful readings in the IDE. On the next attempt, this agent
also opened COM6 and successfully flashed FaceUI. The original cause of the
serial-access errors remains undetermined.

## Product firmware pin correction and confirmed six-row run

FaceUI was subsequently corrected and flashed without changing a wire:

- XP=16, XM=33, YP=21, YM=17.
- Both strobes stay inactive while using CS as an electrode; CS output mode
  is restored before drawing.
- D0/D1 are released for measurement, not parked as unrelated bus outputs.
- Contact is checked separately; a short unchanged-excitation ADC burst
  captures position, with contact checked before and after.
- The 110 ms sequence and per-screen offset fit were removed. Old saved
  calibration is invalidated. The product captures on press instead of
  waiting for a held contact.
- Six centre targets are followed, if distinct, by independent row checks
  at alternating left/right positions. Failed maps are not saved.

The owner explicitly confirmed tapping all six centre targets. The readings
were 1637, 1681, 1619, 1555, 1806, 1674 from top to bottom. The table was
correctly rejected as non-monotonic and insufficiently separated. The
within-burst ranges for rows 2–6 were 1673–1690, 1616–1621, 1535–1561,
1798–1808, 1667–1675. See `FaceUI/corrected-map-summary.txt`.

The pin correction therefore works as an implementation change, but does
not satisfy vertical row selection in the current landscape orientation.
Together with the earlier left/right span of 2951 counts, the evidence
supports trying a portrait interface to align row progression with the
accessible axis. This is a proposed firmware alternative; it must be
validated on the actual screen before calling the UI fixed.

## Landscape solution and owner confirmation

The owner declined portrait. Weak internal pull loading did not separate
position from contact drift (`ResistanceProof/summary.txt`). A second
experiment switches GPIO16 between drive capabilities CAP_0 and CAP_1,
sources GPIO17/21 HIGH, and measures GPIO33. The ratio of the two voltage
divider odds approximately cancels shared contact resistance in an ideal
ohmic model. This is an empirical workaround; GPIO outputs are not precision
resistors. See `DriveProof/README.md` for the derivation and limitations.

An attenuation/calibration-cache mismatch introduced in that diagnostic was
corrected by using the global ADC attenuation setter in Arduino-ESP32
3.3.10. The corrected six centre ratios were 1.21647, 1.25565, 1.28419,
1.37515, 1.54705, 1.61889. FaceUI calibration version 13 uses eight bracketed
weak/strong pairs, a median ratio, clipping rejection and separate contact
detection. It retains six landscape rows and requires no wiring changes
or hold-to-select.

The first independent left/right verification passed 5/6: the top target
selected row 2. That calibration was rejected, not saved. The readable
measurements are in `FaceUI/ratio-validation-summary.txt`.

After further on-device attempts, the owner reported on 9 September 2026:
"now the touhes are working well please save and imprive the ai now".
The owner clarified that the requested improvement is the screen UI.
This is owner-confirmed working behaviour, not a new instrumented accuracy
series. Preserve the v13 sampling, calibration format and stored anchors
while polishing the UI. The earlier failed run remains part of the record;
we have not established error-free performance across all users and presses.

The current product sketch is FaceUI, not AxisProof or BitTrace. Historical
statements above about what was on the board apply only to those stages.
