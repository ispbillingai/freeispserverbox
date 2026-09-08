# Independent review: ESP32 / ILI9486 resistive touch

Prepared 9 September 2026 for review by another AI or engineer.

**Verdict: I found a concrete confound in the diagnostic experiment and an unsupported calibration assumption. I have not confirmed the electrical root cause or a working fix.** The measurements establish that drawing changes the touch readings. They do not yet establish that the displayed image itself causes the change, or that firmware cannot solve it.

This review inspected ABTrace, TouchProof, BoxCal, and the relevant FaceUI driver, sampling, and calibration code. Bench results are supplied by the owner; no new measurements or firmware uploads were performed.

## 1. Main new finding: displayed image and retained GPIO state were not separated

`wrByte()` explicitly drives all eight LCD data GPIOs. After a fill, the bus retains the last byte of the final pixel. `busOut()` restores output direction but does not assign a fixed value to all data pins. During touch reads, only the four declared touch GPIOs are reconfigured. LCD D0–D5 remain outputs.

Consequently, changing a fill colour changes two things simultaneously:

- The image stored in the LCD.
- The sustained electrical levels on the other LCD data outputs.

Waiting two seconds does not distinguish these mechanisms: a GPIO output holds its level indefinitely. This is a different hypothesis from a decaying write burst or transient ADC charge.

The checked ABTrace source makes the confound particularly concrete:

| Operation | RGB565 colour | Last byte written | D0–D5 pattern retained through touch reads |
|---|---:|---:|---:|
| Dark fill, `RGB(13,17,23)` | `0x0882` | `0x82` | `0x02` |
| Small rectangle, `RGB(22,27,34)` | `0x10C4` | `0xC4` | `0x04` |
| White fill | `0xFFFF` | `0xFF` | `0x3F` |

The test labelled DARK uses a near-black colour, not literal `0x0000` black. The supplied measurements remain valid, but the distinction matters electrically.

**Hypothesis to test first:** a declared touch pin does not match the actual electrode connection, or a shield buffer, resistor network, leakage path, or wiring fault allows one of the retained outputs to influence the measured node. This would explain dependence on the last drawing operation without requiring optical brightness to be the cause. These possible paths are not established by the code alone.

An important limit: if the four declared electrode connections are correct and electrically isolated from all other driven nets, the retained D0–D5 levels should not dominate their DC reading. Finding retained levels is evidence of an uncontrolled variable, not proof of the coupling path.

## 2. The next decisive experiment

Use a separate diagnostic sketch and serial-only logging during capture. Keep the existing successful sampling sequence initially, so this is a controlled comparison.

1. Paint one fixed image and hold a finger still.
2. Deassert LCD CS and keep LCD RD HIGH.
3. Without pulsing WR or issuing a display command, change only D0–D5 between their existing all-low and all-high output states. Leave the four declared touch pins to the existing read routines.
4. Record raw z/y for each state, then repeat with no finger and at several heights. Reapply the chosen state before each read as necessary; do not draw between readings.
5. Repeat on dark and white images using identical parked D0–D5 states.

This gives a two-variable experiment: image colour versus electrical bus state. Under the documented ILI9486 interface, CS HIGH deselects the controller; changing data levels without a write strobe does not repaint the image. Actual shield wiring and any buffers still need checking. [ILI9486L datasheet, pin descriptions and parallel interface](https://files.waveshare.com/upload/7/78/ILI9486_Datasheet.pdf).

Interpretation:

- If readings change with D0–D5 while the image stays fixed, an electrical bus dependency is demonstrated. Toggle those six bits individually to identify the influential net, then verify electrode continuity and the shield circuit.
- If readings follow the image with identical bus states, displayed-image coupling or a display-related supply/ground effect remains plausible. Measure the supply, ground, and analog node; brightness alone still does not identify the physical path.
- Both mechanisms may contribute.

A second variant can make D0–D5 inputs with pulls disabled during capture. Keep CS HIGH and RD HIGH, configure only the intended excitation electrodes as outputs, and restore the bus before resuming LCD writes. First check whether the shield contains buffers that prevent MCU input mode from releasing the electrode-side signal.

This is different from painting a fixed rectangle before reading: it changes the electrical bus without changing the image.

## 3. What the current evidence does and does not establish

**Shared RS/ADC is not itself proof of an invalid design.** Multiplexing resistive touch onto display pins is an established technique when the electrical circuit permits the pins to be released. Adafruit explicitly documents sharing touch connections with TFT pins. [Adafruit touchscreen guide](https://learn.adafruit.com/adafruit-3-5-color-320x480-tft-touchscreen-breakout/touchscreen).

`done()` does drive GPIO33 HIGH again, but the next read configures it as an input. The code proves repeated driven-to-input transitions, not that residual charge is the dominant fault. Also, the 110 ms gap occurs after `done()`: it is spent with the LCD bus restored, not with the Y plate continuously excited. That delay's measured benefit must not be described as 110 ms of analog settling under the Y measurement configuration.

The two primitives returning similar values, and one axis failing, warrant checking the actual electrode pairs. They do not prove a wrong pin map. Likewise, the 15/16 BoxCal result is real evidence of useful positional information in that context, but one missed tap does not establish the glass's intrinsic resolution limit.

## 4. A single offset is currently unsupported

The FaceUI comment saying the bias is a constant overstates the evidence. One known tap can estimate an offset only after establishing that the entire position curve retains its shape and slope across contexts. It cannot establish that condition itself.

The code also uses that same SETTINGS tap to compute the correction and then saves the calibration. This is fitting one point, not an independent validation. It draws `NOW TAP SETTINGS` after `drawHome()`, so even the fitting screen differs from ordinary Home in both image and final bus writes.

An offset may work over a verified unsaturated region. A fully railed reading loses positional information; shifting anchors cannot recover it. If Home's reported 3960–3990 range covers different row positions, its compressed span is evidence against a simple translation of the much wider calibration range. If it covers repeated taps at one position, it says nothing about the whole-screen slope.

To validate six rows, collect repeated independent taps at all six row centres on every relevant screen, with varied normal touch pressure and duration. Check row boundaries too. Freeze the mapping before validation. Require enough separation between neighbouring row distributions to cover observed variation; do not accept a monotonic calibration walk alone as proof.

## 5. Display-off, sleep, and hardware

Display-off `0x28` and sleep-in `0x10` are legitimate controller commands, but neither physically disconnects shared copper, buffers, or resistors. Display-off preserves frame memory. Sleep changes internal operation and has entry/exit timing requirements. These can be controlled diagnostic experiments after bus state is normalized; they are not established touch fixes, and repeated sleep/wake is an unattractive tap path. Sending either command also changes bus levels, so an uncontrolled test could misattribute the result again. [ILI9486L datasheet, sections 8.2.12–13 and 8.2.18–19](https://files.waveshare.com/upload/7/78/ILI9486_Datasheet.pdf).

For the new PCB, a dedicated four-wire resistive controller is a sensible architecture. The ADS7846 provides electrode drive, conversion, and ratiometric measurement facilities intended for this job. [TI ADS7846 datasheet](https://www.ti.com/lit/ds/symlink/ads7846.pdf).

**The controller must connect to the actual four electrodes with the unwanted LCD-bus connections removed or properly isolated.** Adding an XPT2046/ADS7846 module in parallel with the existing shared nets would not automatically remove contention or loading. Verify the exact chosen controller's voltage, reference, timing, and layout requirements from its own datasheet.

## 6. Recommendation to the reviewing AI

I agree that the present calibration workaround is not demonstrated reliable enough for the product. I disagree that the experiments already prove permanent displayed-image coupling or firmware impossibility.

Before another calibration rewrite, perform the fixed-image / changed-bus-state experiment and verify the electrode map. If normalizing or releasing the bus restores a stable gradient across images, pursue that firmware path and validate all six rows. If correct electrode mapping and bus release still cannot produce repeatable row separation, proceed with the isolated controller hardware design.

Please independently review the retained D0–D5 confound, the 110 ms interval's actual pin states, and the offset fit being treated as verification. Those are the concrete findings; the physical fault remains to be measured.
