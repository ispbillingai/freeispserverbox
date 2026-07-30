"""Functional trace of freeisp_brain.kicad_pcb.

audit.py proves the copper matches the netlist. THIS proves the netlist
matches the INTENT: the EXPECTED table below is written from first
principles -- the firmware pin defines (LiveDashboardNext/CardDisarm), the
modules' own pinouts, and the power architecture -- NOT imported from
build.py. The board file is then parsed and every net compared both ways:
a pad the intent demands but the board lacks, or a pad the board has that
the intent never asked for, is a finding.

    python trace.py
"""

import sys
import sexp

BOARD = "freeisp_brain.kicad_pcb"

# ---------------------------------------------------------------------------
# EXPECTED: net -> set of "REF.pad" -- derived from intent, not from build.py
#
# U3A = ESP32 left row  (1..15 = EN VP VN D34 D35 D32 D33 D25 D26 D27 D14
#                        D12 D13 GND VIN)
# U3B = ESP32 right row (1..15 = D23 D22 TX0 RX0 D21 D19 D18 D5 D17 D16
#                        D4 D2 D15 GND 3V3)
# J4 TFT module order:   1 GND, 2 VDD, 3 SCL(=SCK), 4 SDA(=MOSI), 5 RST,
#                        6 DC, 7 CS, 8 BLK
# J5 RC522 module order: 1 SDA(=SS), 2 SCK, 3 MOSI, 4 MISO, 5 IRQ(n/c),
#                        6 GND, 7 RST, 8 3.3V
# U4 GY-521 order:       1 VCC, 2 GND, 3 SCL, 4 SDA, 5-8 XDA/XCL/AD0/INT n/c
# ---------------------------------------------------------------------------
EXPECTED = {
    # ---- power spine ----
    "+12V_IN": {"J1.1", "D3.2"},                       # fused feed -> guard anode
    "+12V": {"D3.1", "U1.1", "R5.1"},                  # guarded 12V: buck in + sense
    "+5V": {"U1.3", "U2.1", "D1.2"},                   # buck out: charger in + D1
    "VBAT": {"U2.3", "J13.1", "R3.1"},                 # charger OUT+ : boost in + sense
    "+5V_BAT": {"J13.3", "D2.2"},                      # boost out -> D2 anode
    "+5V_SYS": {"D1.1", "D2.1", "C1.1",                # diode-OR rail
                "U3A.15",                              # ESP32 VIN
                "J4.2",                                # TFT VDD
                "J10.1",                               # buzzer 5V
                "K1.3",                                # relay VCC
                "J11.1"},                              # horn feed (3-5V horn)
    "+3V3": {"U3B.15", "J5.8", "U4.1"},                # ESP32 3V3 -> RC522 + MPU
    "GND": {"J1.2", "U1.2", "U1.4", "U2.2", "U2.4",
            "J13.2", "J13.4", "U3A.14", "U3B.14",
            "J4.1", "J5.6", "U4.2", "J7.2", "J8.1",
            "J9.1", "J10.2", "K1.2", "J11.2",
            "R4.1", "R6.1", "C1.2", "C2.2", "C3.2"},

    # ---- sensing (firmware: GPIO34 mains, GPIO35 battery) ----
    "SENSE_MAINS": {"R5.2", "R6.2", "C3.1", "U3A.4"},
    "SENSE_BATT": {"R3.2", "R4.2", "C2.1", "U3A.5"},

    # ---- door (firmware PIN_REED 32) ----
    "REED_F": {"J7.1", "R8.1"},
    "REED": {"R8.2", "U3A.6"},

    # ---- indicators / sound (firmware 25/26/27, horn 13) ----
    "LED_R": {"U3A.8", "R1.1"},
    "LED_R_A": {"R1.2", "J8.2"},
    "LED_G": {"U3A.9", "R2.1"},
    "LED_G_A": {"R2.2", "J9.2"},
    "BUZZ": {"U3A.10", "J10.3"},
    "HORN_IN": {"U3A.13", "R7.1"},
    "HORN_DRV": {"R7.2", "K1.1"},

    # ---- SPI bus (firmware SCK18 MOSI23 MISO19, TFT CS5 DC2 RST4 BLK33,
    #      RC522 SS16 RST17) ----
    "SCK": {"U3B.7", "J4.3", "J5.2"},
    "MOSI": {"U3B.1", "J4.4", "J5.3"},
    "MISO": {"U3B.6", "J5.4"},
    "TFT_CS": {"U3B.8", "J4.7"},
    "TFT_DC": {"U3B.12", "J4.6"},
    "TFT_RST": {"U3B.11", "J4.5"},
    "TFT_BLK": {"U3A.7", "J4.8"},
    "RC_SS": {"U3B.10", "J5.1"},
    "RC_RST": {"U3B.9", "J5.7"},

    # ---- I2C (firmware SDA21 SCL22) ----
    "SDA": {"U3B.5", "U4.4"},
    "SCL": {"U3B.2", "U4.3"},
}

# Pads that must connect to NOTHING (empty net) -- a wire here is a fault.
EXPECT_NC = {
    "U3A.1", "U3A.2", "U3A.3",            # EN, VP, VN
    "U3A.11", "U3A.12",                   # D14, D12(strap!)
    "U3B.3", "U3B.4", "U3B.13",           # TX0, RX0, D15
    "J5.5",                               # RC522 IRQ
    "U4.5", "U4.6", "U4.7", "U4.8",       # MPU XDA XCL AD0 INT
}


def load_board_nets():
    with open(BOARD, encoding="utf-8") as fh:
        pcb = sexp.parse(fh.read())
    netnames = {int(n[1]): sexp.unq(n[2]) for n in sexp.find_all(pcb, "net")}
    nets = {}
    nc = set()
    for fp in sexp.find_all(pcb, "footprint"):
        ref = "?"
        for prop in sexp.find_all(fp, "property"):
            if sexp.unq(prop[1]) == "Reference":
                ref = sexp.unq(prop[2])
        for pad in sexp.find_all(fp, "pad"):
            if pad[2] == "np_thru_hole":
                continue
            key = f"{ref}.{sexp.unq(pad[1])}"
            netn = sexp.find(pad, "net")
            if netn is None:
                nc.add(key)
            else:
                nets.setdefault(netnames[int(netn[1])], set()).add(key)
    return nets, nc


def main():
    actual, actual_nc = load_board_nets()
    problems = []

    print(f"{'NET':<12} {'PADS':>4}  MEMBERS")
    print("-" * 74)
    for net in EXPECTED:
        exp = EXPECTED[net]
        act = actual.get(net, set())
        ok = exp == act
        mark = "OK " if ok else "!! "
        print(f"{mark}{net:<11} {len(act):>3}  {' '.join(sorted(act))}")
        if not ok:
            missing = exp - act
            extra = act - exp
            if missing:
                problems.append(f"{net}: MISSING {sorted(missing)}")
            if extra:
                problems.append(f"{net}: EXTRA {sorted(extra)}")

    for net in sorted(set(actual) - set(EXPECTED)):
        if actual[net]:
            problems.append(f"UNEXPECTED NET {net}: {sorted(actual[net])}")

    print("\nno-connect pins (must be empty):")
    bad_nc = EXPECT_NC - actual_nc
    for k in sorted(EXPECT_NC):
        print(f"   {'OK' if k in actual_nc else '!!'} {k}")
    for k in sorted(bad_nc):
        problems.append(f"{k} should be unconnected but carries a net")

    print()
    if problems:
        print("FINDINGS:")
        for p in problems:
            print("  !!", p)
        print(f"\nTRACE FAIL - {len(problems)} problems")
        return 1
    total = sum(len(v) for v in EXPECTED.values())
    print(f"TRACE PASS - all {len(EXPECTED)} nets, {total} connections, "
          f"{len(EXPECT_NC)} no-connects: every one exactly as intended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
