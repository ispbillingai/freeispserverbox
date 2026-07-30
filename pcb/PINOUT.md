# FreeISP brain board — pin-by-pin confirmation sheet (rev E)

Every connector, every pin, and where its wire goes. The same names are
printed on the board's silkscreen, using the names **printed on each module**
— so you confirm board-against-part, not board-against-notes.

**Rev E incorporates the independent electrical review (2026-07-30):**
- **C1 fixed** — the old J12 "MAINS" field pin went straight into GPIO34
  (3.3 V max). The header is GONE. Mains presence is now sensed on-board
  from the +12 V rail through R5/R6 (100k/27k → 2.55 V) + C3.
- **C2 fixed** — the horn return pad connected to nothing; the horn could
  never sound. J11 pin 2 is now GND and the horn loop is documented below.
- **M1** — set the buck to **5.4–5.5 V**, NOT 5.0 V, so mains always beats
  the battery boost at the diode-OR and the charger can terminate.
- **M2** — D3 (1N5822) in series after J1: a reversed 12 V hookup is now
  harmless. J1 pin order flipped to +12V · GND to match PSU convention.
- Minors: C1 470 µF bulk on 5V_SYS, C2/C3 100 nF on both ADC dividers,
  R7 1k in the relay drive line, R8 1k in series with the reed input.

Verified three ways (rev E):
1. `audit.py` — independent geometric check, parsed from the board file:
   **no crossings, no two nets closer than 0.25 mm, every net one island**
2. KiCad DRC: **0 errors, 0 unconnected**
3. Renders inspected; pin map cross-checked against the pin defines in
   `LiveDashboardNext.ino` and `CardDisarm.ino`

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
| 4 | D34 | 12 V divider (R5/R6 middle) — on-board only, no field wire |
| 5 | D35 | battery divider (R3/R4 middle) |
| 6 | D32 | REED terminal via R8 1k |
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
 mains 12V ──[INLINE FUSE]── J1 ── D3 ──+12V──┬── U1 BUCK ──5.4V──┬── D1 ─┐
                                              │                   │       │
                                              ├── J11-1 (horn)    │       ├── 5V_SYS
                                              └── R5/R6 → GPIO34  │       │   ESP32 VIN,
                                                     U2 CHARGER ──┘       │   TFT, buzzer,
                                                         │                │   horn relay,
                                                      battery ── J13 BOOST ── D2 ─┘  C1 470µ
```

| Ref | Terminal | Pin order (left → right / top → bottom) | Wire to |
|---|---|---|---|
| J1 | 12V IN | **+12V · GND** | PSU 12 V, **fuse inline in the + wire** |
| D3 | diode | band (K) toward the TOP | 1N5822 — reverse-polarity guard |
| U1 | BUCK | IN+ · IN− · OUT+ · OUT− | LM2596 module — **set to 5.4–5.5 V FIRST** (measure before wiring; 5.0 V lets the battery fight the mains) |
| U2 | CHARGER | IN+ · IN− · B+ · B− | TP4056 module; B+/B− to the 18650 |
| J13 | BOOST (left edge, vertical) | IN+ · IN− · OUT+ · OUT− | 5 V step-up module |
| D1 | diode | band (K) toward the LEFT | 1N5822 — from buck |
| D2 | diode | band (K) toward the LEFT | 1N5822 — from boost |
| C1 | capacitor | **+ mark matters** — stripe (−) toward GND | 470 µF ≥10 V electrolytic |

**Diode bands:** D1/D2 bands face LEFT, D3 band faces UP (all marked K on the
silk). Backwards = that source is simply cut off. Check twice, solder once.

**Charger IN+ feeds from the buck rail on purpose** — from 5V_SYS the battery
would charge itself through its own boost.

**Mains sensing is internal now.** There is NO terminal for it and none is
needed: GPIO34 watches the 12 V rail through the on-board R5/R6 divider.
Nothing above 3.3 V can ever be wired to a GPIO by mistake.

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
| J8 | red LED | GND · LED+ | LED long leg to LED+ (220R is on the board) |
| J9 | green LED | GND · LED+ | same |
| J10 | BUZZ header | 5V · GND · SIG | passive buzzer module |
| K1 | RELAY header | IN · GND · VCC | horn relay board |
| J11 | horn power | +12V · HORN− | see the horn loop below |

**The horn loop (four wires, all of them):**

```
J11 "+12V"  ──►  relay COM
relay NO    ──►  horn +
horn −      ──►  J11 "HORN−"   (returns to ground through the board)
K1 IN·GND·VCC ─► relay board's own 3 pins
```

J11 "+12V" is ALWAYS live — it only becomes an alarm because the relay sits
between it and the horn. Wire the horn straight across J11 and it will be
either permanently on or permanently silent, depending on which way you did it.

---

## Before ordering — your part

1. Print `fitcheck_1to1.pdf` at **100% scale** (no "fit to page").
2. Measure the printed outline: **exactly 100 × 100 mm** or the print scaled.
3. Sit every real module on the paper. Every pin lands on a hole, every
   module name matches the silk beside it.
4. **ESP32 row spacing**: the two socket rows are 25.4 mm apart. Verify
   against your actual devkit with the vernier.
