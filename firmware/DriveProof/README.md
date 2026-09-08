# DriveProof: stronger one-ADC experiment

Landscape and the physical wiring stay unchanged. This test is experimental;
GPIO drive settings are not specified as precision resistors.

GPIO21 and GPIO17 source HIGH into one complete plate. GPIO16 sinks LOW
through the other plate; GPIO33 senses its un-driven end. The test switches
GPIO16 between two drive settings and measures the contact-node voltage.
The initial run used weakest/strongest drive. The current version uses
weakest/stronger (`CAP_0`/`CAP_1`) and brackets each weak sample with stronger
samples to reduce the effect of contact drift. It selects an ADC range from
a pilot measurement and marks clipped samples invalid.
The original drive setting is restored before the next display operation.

For an ideal ohmic model, let B be the plate resistance from GPIO16 to the
contact, D the output sink resistance, S the remaining contact-to-source
resistance, and V the supply. Then the measured voltage U obeys:

```
U/(V-U) = (B+D)/S
ratio = [Uweak/(V-Uweak)] / [Ustrong/(V-Ustrong)]
      = (B+Dweak)/(B+Dstrong)
```

The proposed ratio cancels S only if the contact is unchanged between
samples and the output resistance behaves as assumed. This is this test's
hypothesis, not an established touchscreen technique. A useful result must
be monotonic across rows and repeat independently across horizontal
positions and ordinary tap variations. Supply error, ADC error, output
nonlinearity, and small weak/strong differences can invalidate it.

The [Espressif GPIO API](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/gpio.html)
documents setting and reading the pad drive capability. The sketch uses
valid `GPIO_DRIVE_CAP_0` and `GPIO_DRIVE_CAP_1` settings and records API
success. It does not alter any wire, NVS calibration, or product setting.

Tap the six white targets in order. The serial summary includes stored
averages for all six positions; send `p` to print them again. The display
driver is copied from AxisProof.

## Recorded runs

- `summary.txt`: initial widest-drive test. Ratios must be calculated from
  the recorded voltages; the low end was limited by the default ADC range.
- `refined-invalid-millivolts.txt`: invalid millivolt scales. The per-pin
  attenuation setter changed the hardware range without rebuilding the
  cached millivolt calibration handle in installed Arduino-ESP32 3.3.10.
  These reported voltages and computed ratios must not be used as physics
  measurements. This was a bug introduced in this diagnostic, not the
  cause of the original UI failures.
- `calibrated-summary.txt`: corrected with the global attenuation setter,
  which also rebuilds that handle. Ratios increase across six centre
  targets: 1.21647, 1.25565, 1.28419, 1.37515, 1.54705, 1.61889.
  That is a calibration candidate, not independent accuracy verification.

FaceUI v13 integrates an eight-pair burst and independently checks six row
assignments at alternating left/right positions. The first independent
check passed five rows; the top-row target selected row 2. Calibration was
not saved. See `../TOUCH_PINTRACE_RESULTS.md` for the current limitation.
