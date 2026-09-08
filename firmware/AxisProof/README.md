# AxisProof

Uses the untouched PinTrace scan's plate pairs: GPIO16/33 and GPIO17/21.
The display driver in `Lcd.h` is copied from the existing TouchProof sketch.
No WiFi, calibration storage, or product settings are used.

Tap each green square once as it moves through TOP, CENTRE, BOTTOM, LEFT,
RIGHT. Lift between taps. The test then starts again at TOP. A normal tap
is enough; the firmware captures a short burst and checks contact before
and after it. The serial log reports each burst and a five-position summary.

At 115200 baud, capture the log while tapping. Compare repeated runs before
deciding which physical axis is usable. Labelling the targets does not
verify that the finger was on them; that confirmation comes from the owner.

```powershell
& 'C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe' compile --upload -p COM6 --fqbn esp32:esp32:esp32 firmware/AxisProof
```

Only GPIO33 of the measured four electrodes has an ADC input. Both LCD
strobes stay HIGH during touch; CS is an electrode, and its output mode
must be explicitly restored before drawing. This sketch measures one axis
and does not implement six-row calibration or product selection.
