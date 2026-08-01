"""Bill of materials + placement file, read from the board that goes to the fab.

Two outputs:
  BOM.csv  - what to buy, grouped by value (also a PCBWay assembly BOM)
  CPL.csv  - reference, X, Y, rotation, layer (PCBWay centroid format)

Modules that PLUG IN (ESP32, TFT, RC522, MPU, relay, buzzer, buck, charger,
boost) are deliberately NOT on the board BOM -- the board carries their
sockets. They are listed separately at the end as "plugs in later".

    python bom.py
"""

import collections
import csv
import math
import sexp

BOARD = "freeisp_brain.kicad_pcb"

# what each reference actually is, in shop language
DESC = {
    "J1": ("Screw terminal 2-way 5.08mm", "KF301 / MCV 1,5-2-G-5.08"),
    "J7": ("Screw terminal 2-way 5.08mm", "KF301 / MCV 1,5-2-G-5.08"),
    "J8": ("Screw terminal 2-way 5.08mm", "KF301 / MCV 1,5-2-G-5.08"),
    "J9": ("Screw terminal 2-way 5.08mm", "KF301 / MCV 1,5-2-G-5.08"),
    "J11": ("Screw terminal 2-way 5.08mm", "KF301 / MCV 1,5-2-G-5.08"),
    "U1": ("Screw terminal 4-way 5.08mm", "KF301 / MCV 1,5-4-G-5.08"),
    "U2": ("Screw terminal 4-way 5.08mm", "KF301 / MCV 1,5-4-G-5.08"),
    "J13": ("Screw terminal 4-way 5.08mm", "KF301 / MCV 1,5-4-G-5.08"),
    "U3A": ("Female header socket 1x19, 2.54mm", "cut from a 40-pin strip"),
    "U3B": ("Female header socket 1x19, 2.54mm", "cut from a 40-pin strip"),
    "J4": ("Male pin header 1x8, 2.54mm", "TFT socket"),
    "J5": ("Male pin header 1x8, 2.54mm", "RC522 socket"),
    "U4": ("Male pin header 1x8, 2.54mm", "MPU-6050 socket"),
    "J10": ("Male pin header 1x3, 2.54mm", "buzzer"),
    "K1": ("Male pin header 1x3, 2.54mm", "relay control"),
    "J14": ("Male pin header 2x5, 2.54mm", "EXPANSION"),
    "D1": ("Schottky diode 3A DO-201AD", "1N5822 (or SR340/SB360)"),
    "D2": ("Schottky diode 3A DO-201AD", "1N5822 (or SR340/SB360)"),
    "D3": ("Schottky diode 3A DO-201AD", "1N5822 (or SR340/SB360)"),
    "C1": ("Electrolytic capacitor 470uF 16V", "8mm dia, 3.5mm pitch"),
    "C2": ("Ceramic capacitor 100nF", "5mm disc"),
    "C3": ("Ceramic capacitor 100nF", "5mm disc"),
    "R1": ("Resistor 220R 1/4W", "red LED"),
    "R2": ("Resistor 220R 1/4W", "green LED"),
    "R3": ("Resistor 100k 1/4W", "battery divider"),
    "R4": ("Resistor 100k 1/4W", "battery divider"),
    "R5": ("Resistor 100k 1/4W", "12V divider"),
    "R6": ("Resistor 27k 1/4W", "12V divider"),
    "R7": ("Resistor 1k 1/4W", "relay drive"),
    "R8": ("Resistor 1k 1/4W", "reed input"),
    "H1": ("M3 mounting hole", "no part"),
    "H2": ("M3 mounting hole", "no part"),
    "H3": ("M3 mounting hole", "no part"),
    "H4": ("M3 mounting hole", "no part"),
}

# these are NOT soldered to the board -- they plug into it
PLUGS_IN = [
    ("ESP32 DevKitC 38-pin", "into U3A/U3B sockets", "you have it"),
    ("1.8in TFT ST7735S", "into J4", "you have it"),
    ("RC522 RFID reader", "into J5", "you have it"),
    ("GY-521 MPU-6050", "into U4", "you have it"),
    ("Passive buzzer module", "into J10", "you have it"),
    ("Relay module", "into K1 + its own screw terminals", "you have it"),
    ("LM2596 buck module", "wired to U1 terminal", "you have it"),
    ("TP4056 charger (protected)", "wired to U2 terminal", "you have it"),
    # Francis has 2x MT3608 (2026-08-01). They work, but a MT3608's 2A is a
    # SWITCH rating -- from a 3.7V cell it is only about 1A out at 5V, and on
    # battery this module carries the ESP32's WiFi bursts, the TFT, the relay
    # coil AND the sounding horn together. Fine for the bench, thin for the
    # real build: expect the rail to sag when the horn fires on battery.
    ("5V boost module, >=2A", "wired to J13 terminal",
     "have 2x MT3608 - bench OK, UNDERSIZED for the horn"),
    ("18650 cell + holder", "onto the TP4056's own B+/B-", "you have it"),
    ("Horn 3-5V", "via the relay contacts to J11", "you have it"),
    ("Reed switch + neodymium magnet", "to J7", "magnet TO BUY"),
    ("Red + green LEDs 5mm", "to J8 / J9", "you have it"),
    ("12V PSU + inline fuse 2A", "to J1", "TO BUY fuse"),
]


def main():
    pcb = sexp.parse(open(BOARD, encoding="utf-8").read())
    parts = []
    for fp in sexp.find_all(pcb, "footprint"):
        ref = val = "?"
        for p in sexp.find_all(fp, "property"):
            n = sexp.unq(p[1])
            if n == "Reference":
                ref = sexp.unq(p[2])
            elif n == "Value":
                val = sexp.unq(p[2])
        at = sexp.find(fp, "at")
        parts.append((ref, val, float(at[1]), float(at[2]),
                      float(at[3]) if len(at) > 3 else 0.0))

    # ---- CPL: PCBWay wants board-relative mm, origin bottom-left ----
    with open("CPL.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for ref, _v, x, y, rot in sorted(parts):
            if ref.startswith("H"):
                continue
            w.writerow([ref, f"{x - 60.0:.3f}", f"{155.0 - y:.3f}",
                        "top", f"{rot:.0f}"])

    # ---- BOM grouped by what you actually buy ----
    groups = collections.OrderedDict()
    for ref, _v, *_ in sorted(parts):
        d = DESC.get(ref)
        if not d or d[1] == "no part":
            continue
        groups.setdefault(d, []).append(ref)

    with open("BOM.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Item", "Qty", "Designators", "Description", "Notes"])
        for i, ((desc, note), refs) in enumerate(sorted(groups.items()), 1):
            w.writerow([i, len(refs), " ".join(refs), desc, note])

    print("SOLDERED TO THE BOARD -> BOM.csv\n")
    print(f"{'QTY':>4}  {'DESIGNATORS':<26}{'PART':<38}NOTE")
    total = 0
    for (desc, note), refs in sorted(groups.items()):
        total += len(refs)
        print(f"{len(refs):>4}  {' '.join(refs):<26}{desc:<38}{note}")
    print(f"\n{total} parts in {len(groups)} lines\n")

    print("PLUGS IN LATER - not part of any assembly quote\n")
    for name, where, status in PLUGS_IN:
        print(f"      {name:<32}{where:<40}{status}")
    print(f"\nwrote BOM.csv and CPL.csv ({len(parts) - 4} placements)")


if __name__ == "__main__":
    main()
