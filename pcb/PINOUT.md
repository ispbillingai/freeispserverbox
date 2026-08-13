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

## U3 — ESP32 socket (**38-pin DevKitC — Francis counted 19 per side**)

Drop the ESP32 in with the **antenna toward ANTENNA SIDE** (top) and the
**USB toward USB SIDE** (bottom). Corner names on the silk must match the
devkit's own silk: **3V3** top-left, **5V** bottom-left, **GND** top-right,
**CLK** bottom-right. The pin order was confirmed against the photo of the
real board on the rev-D paper test.

⚠️ **Row spacing is assumed 25.4 mm** (DevKitC standard) — verify with the
vernier on the new paper print before ordering.

### U3A — left row (top → bottom)

| # | Devkit pin | Wired to |
|---|---|---|
| 1 | 3V3 | **3V3 rail** → RC522 + MPU only |
| 2 | EN | — |
| 3 | VP / D36 | — |
| 4 | VN / D39 | — |
| 5 | D34 | 12 V divider (R5/R6 middle) — on-board only, no field wire |
| 6 | D35 | battery divider (R3/R4 middle) |
| 7 | D32 | REED terminal via R8 1k |
| 8 | D33 | TFT BLK (backlight) |
| 9 | D25 | red LED via R1 220R |
| 10 | D26 | green LED via R2 220R |
| 11 | D27 | buzzer SIG |
| 12 | D14 | — |
| 13 | D12 | — (never use: boot strap) |
| 14 | GND | ground |
| 15 | D13 | horn relay drive via R7 1k |
| 16 | SD2 / GPIO9 | — **FLASH PIN, never connect** |
| 17 | SD3 / GPIO10 | — **FLASH PIN, never connect** |
| 18 | CMD / GPIO11 | — **FLASH PIN, never connect** |
| 19 | 5V | **5V_SYS** (after the diodes) |

### U3B — right row (top → bottom)

| # | Devkit pin | Wired to |
|---|---|---|
| 1 | GND | ground |
| 2 | D23 | SPI MOSI → TFT SDA + RC522 MOSI |
| 3 | D22 | I²C SCL → MPU SCL |
| 4 | TX0 | — (keep free: USB serial) |
| 5 | RX0 | — (keep free: USB serial) |
| 6 | D21 | I²C SDA → MPU SDA |
| 7 | GND | ground |
| 8 | D19 | SPI MISO → RC522 MISO |
| 9 | D18 | SPI SCK → TFT SCL + RC522 SCK |
| 10 | D5 | TFT CS |
| 11 | D17 | RC522 RST |
| 12 | D16 | RC522 SDA (chip select) |
| 13 | D4 | TFT RST |
| 14 | D0 | — (boot strap) |
| 15 | D2 | TFT DC |
| 16 | D15 | — (boot strap) |
| 17 | SD1 / GPIO8 | — **FLASH PIN, never connect** |
| 18 | SD0 / GPIO7 | — **FLASH PIN, never connect** |
| 19 | CLK / GPIO6 | — **FLASH PIN, never connect** |

---

## Power chain (top of board, left to right)

```
 mains 12V ──[INLINE FUSE]── J1 ── D3 ──+12V──┬── U1 BUCK ──5.4V──┬─/──D1 ─┐
                                              │                   │  ^    │
                                              └── R5/R6 → GPIO34  │  |    ├── 5V_SYS
                                                     U2 CHARGER ──┘  |    │   ESP32 VIN,
                                                         │      MASTER    │   TFT, buzzer,
                                                      battery ── J13 BOOST ─/─ D2 ─┘  relay,
                                                                          HORN (J11), C1 470µ
```

The two `/` marks are the master switch — one DPST breaking both OUT+ leads.
See **MASTER SWITCH** below; one pole alone cannot turn this box off.

| Ref | Terminal | Pin order (left → right / top → bottom) | Wire to |
|---|---|---|---|
| J1 | 12V IN | **+12V · GND** | PSU 12 V, **fuse inline in the + wire** |
| D3 | diode | band (K) toward the TOP | 1N5822 — reverse-polarity guard |
| U1 | BUCK | IN+ · IN− · OUT+ · OUT− | LM2596 module — **set to 5.4–5.5 V FIRST** (measure before wiring; 5.0 V lets the battery fight the mains) |
| U2 | CHARGER | IN+ · IN− · **OUT+ · OUT−** | TP4056 module's OUT pads — the load side, behind the protection FETs. **The 18650 wires straight to the module's own B+/B− pads and never touches this board.** Load on B+/B− would bypass the protection |
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

## MASTER SWITCH — a DPST in the two OUT+ leads

The box has **two** power sources that merge at the diode-OR, so one pole
cannot turn it off. Breaking the 12 V only looks like a mains cut and the
battery takes over — which is the whole design working correctly, and is
exactly NOT what a master switch should do.

So the switch is **double-pole**, and it breaks both feeds into 5V_SYS:

```
pole 1:   buck module OUT+  ──/ ──►  U1  "OUT+"     (kills the mains path)
pole 2:   boost module OUT+ ──/ ──►  J13 "OUT+"     (kills the battery path)
```

Both are wires you are already running into screw terminals, so this needs
**no board change**. Downstream of the two diodes nothing is left alive:
ESP32, TFT, buzzer, relay, horn and the charger's own input all go dark.
The cell stays wired to the TP4056's B+/B− and simply sits idle.

Rate it for the whole load including the horn — **≥3 A**, so an ordinary
6 A rocker is plenty. The battery is NOT disconnected by this switch, so it
neither charges nor discharges while off; a box left switched off for months
self-discharges normally and should be checked before it ships.

⚠️ **MOUNT IT INSIDE, behind the alarmed door.** A master switch reachable
from outside hands a thief the off button for the alarm, defeating the
battery backup, the horn and the reporting in one flick. Behind the door it
is safe: opening the door raises the alarm *before* the switch can be
reached, and that alarm is already on the air by then.

For bench work there is also a **zero-wiring alternative**: a switch across
**J14 pins 9 (EN) and 10 (GND)** holds the ESP32 in reset — the brain stops
but the peripherals stay powered. Useful for reflashing and testing, not a
substitute for the DPST.

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
| K1 | RELAY header | IN · GND · VCC | horn relay board's 3 control pins |
| J11 | horn power | +5V · HORN− | see the horn loop below |

**The PCB does not switch the horn.** K1 only feeds the relay module's
control pins; the switching happens in that module's own COM/NO screw
terminals. All four wires:

```
J11 "+5V"   ──►  relay COM
relay NO    ──►  horn +
horn −      ──►  J11 "HORN−"   (returns to ground through the board)
K1 IN·GND·VCC ─► relay board's own 3 pins
```

**J11 feeds from 5V_SYS, not 12 V** — the horn is a 3–5 V type, and 5V_SYS
is the diode-OR rail, so the horn keeps sounding on battery after a mains
cut and can never be fed 12 V by mistake. ⚠️ If a future build uses a true
12 V horn, that is a board change (J11 back to the 12 V rail) AND a battery
problem (12 V dies with the mains) — do not just wire it and hope.

J11 "+5V" is ALWAYS live — it only becomes an alarm because the relay sits
between it and the horn. Wire the horn straight across J11 and it will be
either permanently on or permanently silent, depending on which way you did it.

**Boost module sizing:** on battery the boost carries the ESP32's WiFi
bursts, the TFT, the relay coil AND the sounding horn — buy a **≥2 A**
step-up module, not a tiny 1 A one.

---

## J14 EXPANSION — the spare pins, kept reachable

A 2x5 header beside the ESP32 brings out every spare pin plus power and
ground, so a button, a sensor or anything else can be added later **without
a new board**. Odd pins are the left column, even pins the right.

| Pin | Name | What it is |
|---|---|---|
| 1 | 3V3 | 3.3 V, from the ESP32's own regulator |
| 2 | 5V | 5V_SYS — survives a mains cut |
| 3, 4, 10 | GND | ground |
| 5 | D36 | **input ONLY**, ADC1. No internal pull-up |
| 6 | D39 | **input ONLY**, ADC1. No internal pull-up |
| 7 | D14 | full GPIO with an internal pull-up — **best pin for a button** |
| 8 | D12 | works, but it is a strapping pin: must be LOW at boot |
| 9 | EN | reset. A button from here to GND reboots the box |

**For a button, use pin 7 (D14) to pin 3 (GND)** and enable
`INPUT_PULLUP` — no resistor needed. D36 and D39 have no internal pull-up,
so a button on those needs an external 10k to 3V3.

**Do not hold D12 high at boot**, and if you wire a button to EN remember it
is a hardware reset, not something firmware can read.

TX0 and RX0 are deliberately NOT on this header — they are the USB serial
port, and loading them breaks programming and the serial monitor.

## Match your modules by PRINTED NAME, never by pin position

The board's labels are correct for the common versions of each module, but
clones vary. At assembly, hold each module next to its terminal and match
the words:

- **Relay module** — 3-pin order differs between brands. Match IN, GND, VCC
  by the module's own silkscreen. Also confirm a 3.3 V signal triggers it
  (high-level-trigger boards can be marginal at 5 V VCC).
- **TP4056** — board terminal takes the module's **OUT+ / OUT−**. Battery
  goes on the module's **B+ / B−**. Four different pads, two different jobs.
- **Buzzer module** — SIG pin must accept 3.3 V logic (the kit one does).
- **TFT** — must be the 8-pin ST7735 type reading GND VDD SCL SDA RST DC CS
  BLK. A different pin order means rewiring the plug, not forcing it in.
- **Buck / boost** — set the trimmers with a multimeter BEFORE wiring:
  buck 5.4 V, boost 5.0 V (also printed on the board's top edge).

## Before ordering — your part

1. Print `fitcheck_1to1.pdf` at **100% scale** (no "fit to page").
2. Measure the printed outline: **exactly 115 × 115 mm** or the print scaled.
   (Rev G grew from 100 mm — Francis's call, so the 38-pin devkit's body
   overhang has room and nothing is cramped.)
3. Confirm the devkit: 19 pins per side drop into the 19 printed holes, row
   spacing 25.4 mm, and its body fits inside the printed "ESP32 BODY" box
   including the USB/Type-C end.
3. Sit every real module on the paper. Every pin lands on a hole, every
   module name matches the silk beside it.
4. **ESP32 row spacing**: the two socket rows are 25.4 mm apart. Verify
   against your actual devkit with the vernier.
