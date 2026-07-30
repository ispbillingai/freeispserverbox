# FreeISP brain board — pin-by-pin confirmation sheet

Every connector, every pin, and where its wire goes. The same names are
printed on the board's silkscreen, using the names **printed on each module**
— so you confirm board-against-part, not board-against-notes.

Verified three ways on 2026-07-30 (rev D):
1. `audit.py` — independent geometric check, parsed from the board file:
   **no crossings, no two nets closer than 0.25 mm, every net one island**
2. KiCad DRC: **0 errors, 0 unconnected**
3. Front + back renders inspected, and this sheet cross-checked against the
   pin defines in `LiveDashboardNext.ino` and `CardDisarm.ino`

---

## U3 — ESP32 socket (30-pin DevKit V1)

Drop the ESP32 in with the **antenna toward ANTENNA SIDE** (top) and the
**USB toward USB SIDE** (bottom). Corner names on the silk must match the
devkit's own silk: **EN** top-left, **VIN** bottom-left, **D23** top-right,
**3V3** bottom-right. If your board shows anything else at those corners,
STOP — it is not the assumed 30-pin layout.

### U3A — left row (top → bottom)

| # | Devkit pin | Wired to |
|---|---|---|
| 1 | EN | — |
| 2 | VP / D36 | — |
| 3 | VN / D39 | — |
| 4 | D34 | SENSE header, MAINS |
| 5 | D35 | battery divider (R3/R4 middle) |
| 6 | D32 | REED terminal |
| 7 | D33 | TFT BLK (backlight) |
| 8 | D25 | red LED via R1 220R |
| 9 | D26 | green LED via R2 220R |
| 10 | D27 | buzzer SIG |
| 11 | D14 | — |
| 12 | D12 | — (never use: boot strap) |
| 13 | D13 | horn relay IN |
| 14 | GND | ground |
| 15 | VIN | **5V_SYS** (after the diodes) |

### U3B — right row (top → bottom)

| # | Devkit pin | Wired to |
|---|---|---|
| 1 | D23 | SPI MOSI → TFT SDA + RC522 MOSI |
| 2 | D22 | I²C SCL → MPU SCL |
| 3 | TX0 | — (keep free: USB serial) |
| 4 | RX0 | — (keep free: USB serial) |
| 5 | D21 | I²C SDA → MPU SDA |
| 6 | D19 | SPI MISO → RC522 MISO |
| 7 | D18 | SPI SCK → TFT SCL + RC522 SCK |
| 8 | D5 | TFT CS |
| 9 | TX2 / D17 | RC522 RST |
| 10 | RX2 / D16 | RC522 SDA (chip select) |
| 11 | D4 | TFT RST |
| 12 | D2 | TFT DC |
| 13 | D15 | — |
| 14 | GND | ground |
| 15 | 3V3 | **3V3 rail** → RC522 + MPU only |

---

## Power chain (top of board, left to right)

```
 mains 12V ──[INLINE FUSE]── J1 ── U1 BUCK ──5V──┬── D1 ─┐
                                                 │       ├── 5V_SYS ── ESP32 VIN,
                                    U2 CHARGER ──┘       │            TFT, buzzer,
                                        │                │            horn relay
                                     battery ── J13 BOOST ── D2 ─┘
```

| Ref | Terminal | Pin order (left → right / top → bottom) | Wire to |
|---|---|---|---|
| J1 | 12V IN | GND · +12V | PSU 12 V, **fuse inline in the + wire** |
| U1 | BUCK | IN+ · IN− · OUT+ · OUT− | LM2596 module (set to 5.0 V FIRST) |
| U2 | CHARGER | IN+ · IN− · B+ · B− | TP4056 module; B+/B− to the 18650 |
| J13 | BOOST (left edge, vertical) | IN+ · IN− · OUT+ · OUT− | 5 V step-up module |
| D1 | diode | band (K) toward the LEFT | 1N5822 — from buck |
| D2 | diode | band (K) toward the LEFT | 1N5822 — from boost |

**Diode bands:** both cathode bands face LEFT (marked K on the silk). Backwards
= that source is cut off. Check twice, solder once.

**Charger IN+ feeds from the buck rail on purpose** — from 5V_SYS the battery
would charge itself through its own boost.

---

## Right edge (top → bottom) — names as printed on each module

| Ref | Module | Pins in order |
|---|---|---|
| J4 | 1.8" TFT (blue ST7735S) | GND · VDD · SCL · SDA · RST · DC · CS · BLK |
| J5 | RC522 reader | SDA · SCK · MOSI · MISO · IRQ · GND · RST · 3.3V |
| U4 | GY-521 MPU-6050 | VCC · GND · SCL · SDA · XDA · XCL · AD0 · INT |

IRQ, XDA, XCL, AD0, INT have holes but no traces — unused by design.
**J4 VDD and J5 3.3V are different rails** (5 V vs 3.3 V) — do not swap the
two modules' plugs.

## Bottom row (left → right)

| Ref | Function | Pins | Wire to |
|---|---|---|---|
| J7 | door sensor | REED · GND | reed switch, either way round |
| J12 | SENSE header | MAINS · GND · VBAT | mains-detect + battery + |
| J8 | red LED | GND · LED+ | LED long leg to LED+ (220R is on the board) |
| J9 | green LED | GND · LED+ | same |
| J10 | BUZZ header | 5V · GND · SIG | passive buzzer module |
| K1 | RELAY header | IN · GND · VCC | horn relay board |
| J11 | horn power | +12V · HORN | relay switches this 12 V to the horn |

---

## Before ordering — your part

1. Print `fitcheck_1to1.pdf` at **100% scale** (no "fit to page").
2. Measure the printed outline: **exactly 100 × 100 mm** or the print scaled.
3. Sit every real module on the paper. Every pin lands on a hole, every
   module name matches the silk beside it.
4. **ESP32 row spacing**: the two socket rows are 25.4 mm apart. Verify
   against your actual devkit with the vernier.
