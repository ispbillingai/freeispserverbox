# PinTrace

Connection diagnostic for the fitted ESP32 parallel shield. Keep the glass
untouched. The current version scans LCD D0–D7, RS and CS in both directions
and polarities; LCD RD, WR and reset remain HIGH. Both bus strobes remain
inactive while CS is tested as a candidate electrode.

The test uses internal weak pulls and one candidate output at a time.
`low=0 high=8 FOLLOWS` means the sense input followed the driven candidate
despite an opposing weak pull. Reciprocal results suggest a conductive pair.
They do not measure ohms, prove a film connection rather than another circuit
path, or determine physical X/Y orientation. Check the no-drive baselines:
an unloaded node should read `up=8 down=0`. Unexpected baselines require
investigating loading before interpreting the pair table.

The [MCUFRIEND diagnostic](https://github.com/prenticedavid/MCUFRIEND_kbv/blob/master/examples/diagnose_Touchpins/diagnose_Touchpins.ino)
uses analog pull-up measurements. Its
[calibration example](https://github.com/prenticedavid/MCUFRIEND_kbv/blob/master/examples/TouchScreen_Calibr_native/TouchScreen_Calibr_native.ino)
skips automatic pin diagnosis on ESP32. This digital adaptation avoids assuming
AVR analog thresholds or a calibrated ESP32 internal pull-up resistance.

Compile and flash from the repository root, without `--output-dir`:

```powershell
& 'C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe' compile --upload -p COM6 --fqbn esp32:esp32:esp32 firmware/PinTrace
```

At 115200 baud send `s` to run a scan; it never starts automatically. The
sketch does not initialize or draw on the LCD, so its visual state is not a
status indicator. It does not use WiFi or write calibration to NVS.

After confirming two plausible isolated plate pairs, measure position under
proper excitation at known screen locations before changing the product map.
A stable accidental bias under the old map is not sufficient validation.

Bench logs, 9 September 2026:

- `scan-untouched.txt`: initial scan with CS/RD/reset held HIGH. D0–RS follows
  reciprocally; D1 remains HIGH even against its weak pull-down.
- `scan-untouched-rd.txt`: experimental scan releasing RD, keeping CS/reset
  HIGH. Several bus baselines and readings are disturbed. Do not infer
  electrode pairs from that uncontrolled result.
- `scan-untouched-cs.txt`: current scan, RD/WR/reset held HIGH. All ten
  baselines respond normally to both pulls. Exactly two reciprocal pairs:
  D0/GPIO16–RS/GPIO33, and D1/GPIO17–CS/GPIO21.
