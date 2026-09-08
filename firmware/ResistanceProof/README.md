# ResistanceProof: experimental landscape-only route

This is an experiment, not a working row detector. It keeps the measured
electrodes and existing display orientation. GPIO16 drives HIGH, both
GPIO17/21 ends drive LOW, and GPIO33 measures the remaining plate endpoint.

Unlike a normal coordinate read, that unloaded voltage depends on the
contact resistance as well as the position. The experiment also measures
the voltage with the ESP32's internal weak pull-down and pull-up enabled.
It brackets those readings with unloaded samples to expose contact drift.
If the load-induced change is smaller than drift/noise, it is not a usable
position signal and should not be calibrated as one.

In an ideal resistor model, with supply V, plate resistance R, distance
resistance B from GPIO16 to the contact, and contact-to-ground resistance S:

```
unloaded U = V*S/(B+S)
Thevenin resistance T = R-B + B*S/(B+S) = R-B*(1-U/V)
with pull-down P: D = U*P/(P+T), hence T/P = U/D-1
```

This is a proposed inference for this experiment, not a documented fix.
Recovering position would require estimating/calibrating R/P and validating
that the tiny loaded/unloaded difference survives normal tap variation.
Internal pull resistance, GPIO output resistance, ADC nonlinearity and
contact movement limit the ideal model. A monotonic-looking voltage alone
does not establish success.

The [ESP-IDF RTC GPIO API](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/gpio.html)
provides the pull controls. The sketch primes the ADC before enabling each
load, logs API success, and includes a startup pull-response check.

Tap each white square in the six highlighted rows. Logs report averaged
millivolts for unloaded, pull-down, unloaded, pull-up, unloaded. No NVS or
product settings are written. The LCD driver is copied from AxisProof.
