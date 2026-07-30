"""Generate the FreeISP brain board as a standalone KiCad PCB.

Single copper layer, 100 x 100 mm, home-etchable. Stock KiCad footprints are
loaded from the installed library and embedded with placement + net data, so
pad geometry is KiCad's own rather than hand-rolled.

What this writes:  placement, nets, board outline, mounting holes, the
perimeter ground ring and its stubs, and the fused 12 V hops.
What it leaves:    signal routing -- that is done interactively in KiCad,
                   where the router enforces clearance properly.

    python build.py
"""

import json
import os
import uuid as _uuid
import sexp

FPLIB = r"F:\kicad\share\kicad\footprints"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "freeisp_brain.kicad_pcb")

# board origin on the page: design (0,0) maps here
OX, OY = 60.0, 40.0
BW = BH = 100.0

RING = 9.0           # ground ring inset from the board edge
W_GND = 2.0          # perimeter ring, out in open copper
W_PWR = 1.5
W_HV = 2.5           # offered for the long 12 V horn run
# Stubs leave pads on 2.54 mm pitch, so they must stay narrow enough to clear
# the neighbouring pin: 1.9 mm pad + 0.6 mm clearance leaves 1.98 mm of room.
W_STUB = 1.5
CLEARANCE = 0.6      # etchant undercuts; tight gaps bridge
TRACK_MIN = 0.6

# Pads are enlarged for hand drilling, but a pad can never exceed
# (pitch - clearance) or neighbouring pins short. On 2.54 mm pitch that
# caps us at 1.94 mm, which is why these differ per footprint pitch.
PAD_P254 = 1.9       # headers and sockets
PAD_P508 = 2.4       # terminal blocks
PAD_RES = 2.2        # resistors, 7.62 mm pitch

LIB_SOCKET = "Connector_PinSocket_2.54mm"
LIB_HEADER = "Connector_PinHeader_2.54mm"
LIB_TERM = "Connector_Phoenix_MC_HighVoltage"
LIB_RES = "Resistor_THT"
LIB_HOLE = "MountingHole"

FP_SOCKET15 = "PinSocket_1x15_P2.54mm_Vertical"
FP_TERM2 = "PhoenixContact_MCV_1,5_2-G-5.08_1x02_P5.08mm_Vertical"
FP_RES = "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
FP_HOLE = "MountingHole_3.2mm_M3"


def hdr(n):
    return f"PinHeader_1x0{n}_P2.54mm_Vertical"


# ---------------------------------------------------------------- nets
NETS = [
    "", "GND", "+5V", "+3V3", "+12V", "+12V_RAW", "VBAT", "SENSE_BATT",
    "SENSE_MAINS", "REED", "LED_R", "LED_R_A", "LED_G", "LED_G_A", "BUZZ",
    "HORN_IN", "HORN_RET", "MOSI", "MISO", "SCK", "TFT_CS", "TFT_DC",
    "TFT_RST", "TFT_BLK", "RC_SS", "RC_RST", "SDA", "SCL",
]
NET_ID = {name: i for i, name in enumerate(NETS)}

# ---------------------------------------------------------------- parts
# ref: (lib, footprint, x, y, rot, value, {pad_number: net})
#
# ESP32 rows use the standard 30-pin DevKit V1 order. U3A is the EN/VP side,
# U3B is the D23/3V3 side. Confirm against the silkscreen of the real board.
U3A_NETS = {
    4: "SENSE_MAINS", 5: "SENSE_BATT", 6: "REED", 7: "TFT_BLK",
    8: "LED_R", 9: "LED_G", 10: "BUZZ", 13: "HORN_IN", 14: "GND", 15: "+5V",
}
U3B_NETS = {
    1: "MOSI", 2: "SCL", 5: "SDA", 6: "MISO", 7: "SCK", 8: "TFT_CS",
    9: "RC_RST", 10: "RC_SS", 11: "TFT_RST", 12: "TFT_DC", 14: "GND", 15: "+3V3",
}

PARTS = {
    # --- power in, top row ---
    "J1":  (LIB_TERM, FP_TERM2, 12, 15, 0, "12V IN",
            {1: "GND", 2: "+12V_RAW"}),
    "F1":  (LIB_TERM, FP_TERM2, 25, 15, 0, "FUSE 2A",
            {1: "+12V_RAW", 2: "+12V"}),
    "U1":  (LIB_HEADER, hdr(4), 38, 15, 90, "LM2596 BUCK",
            {1: "+12V", 2: "GND", 3: "+5V", 4: "GND"}),
    "U2":  (LIB_HEADER, hdr(4), 52, 15, 90, "TP4056",
            {1: "+5V", 2: "GND", 3: "VBAT", 4: "GND"}),
    "J3":  (LIB_TERM, FP_TERM2, 65, 15, 0, "BATT",
            {1: "VBAT", 2: "GND"}),
    "J2":  (LIB_TERM, FP_TERM2, 78, 15, 0, "5V AUX",
            {1: "+5V", 2: "GND"}),

    # --- the brain ---
    "U3A": (LIB_SOCKET, FP_SOCKET15, 32, 32, 0, "ESP32 L", U3A_NETS),
    "U3B": (LIB_SOCKET, FP_SOCKET15, 57.4, 32, 0, "ESP32 R", U3B_NETS),

    # --- right edge: display, reader, motion ---
    "J4":  (LIB_HEADER, hdr(8), 82, 22, 0, "TFT",
            {1: "+5V", 2: "GND", 3: "SCK", 4: "MOSI", 5: "TFT_RST",
             6: "TFT_DC", 7: "TFT_CS", 8: "TFT_BLK"}),
    "J5":  (LIB_HEADER, hdr(7), 82, 46, 0, "RC522",
            {1: "+3V3", 2: "RC_RST", 3: "GND", 4: "MISO", 5: "MOSI",
             6: "SCK", 7: "RC_SS"}),
    "U4":  (LIB_HEADER, hdr(4), 82, 68, 0, "MPU-6050",
            {1: "+3V3", 2: "GND", 3: "SDA", 4: "SCL"}),

    # --- passives ---
    "R3":  (LIB_RES, FP_RES, 16, 72, 0, "100k", {1: "VBAT", 2: "SENSE_BATT"}),
    "R4":  (LIB_RES, FP_RES, 16, 78, 0, "100k", {1: "GND", 2: "SENSE_BATT"}),
    "R2":  (LIB_RES, FP_RES, 33, 72, 0, "220R", {1: "LED_G", 2: "LED_G_A"}),
    "R1":  (LIB_RES, FP_RES, 33, 78, 0, "220R", {1: "LED_R", 2: "LED_R_A"}),

    # --- field terminals, bottom row ---
    "J7":  (LIB_TERM, FP_TERM2, 13, 86, 0, "REED", {1: "REED", 2: "GND"}),
    "J12": (LIB_HEADER, hdr(3), 24, 86, 90, "SENSE",
            {1: "SENSE_MAINS", 2: "GND", 3: "VBAT"}),
    "J8":  (LIB_TERM, FP_TERM2, 36, 86, 0, "LED R", {1: "GND", 2: "LED_R_A"}),
    "J9":  (LIB_TERM, FP_TERM2, 48, 86, 0, "LED G", {1: "GND", 2: "LED_G_A"}),
    "J10": (LIB_HEADER, hdr(3), 58, 86, 90, "BUZZER",
            {1: "+5V", 2: "GND", 3: "BUZZ"}),
    "K1":  (LIB_HEADER, hdr(3), 68, 86, 90, "HORN RLY",
            {1: "HORN_IN", 2: "GND", 3: "+5V"}),
    "J11": (LIB_TERM, FP_TERM2, 78, 86, 0, "HORN",
            {1: "+12V", 2: "HORN_RET"}),

    # --- mechanical ---
    "H1":  (LIB_HOLE, FP_HOLE, 4.5, 4.5, 0, "M3", {}),
    "H2":  (LIB_HOLE, FP_HOLE, 95.5, 4.5, 0, "M3", {}),
    "H3":  (LIB_HOLE, FP_HOLE, 4.5, 95.5, 0, "M3", {}),
    "H4":  (LIB_HOLE, FP_HOLE, 95.5, 95.5, 0, "M3", {}),
}


def uid():
    return sexp.q(str(_uuid.uuid4()))


def load_fp(lib, name):
    path = os.path.join(FPLIB, lib + ".pretty", name + ".kicad_mod")
    with open(path, encoding="utf-8") as fh:
        return sexp.parse(fh.read())


def set_at(node, x, y, rot=0):
    at = sexp.find(node, "at")
    vals = ["at", f"{x:.4f}", f"{y:.4f}"] + ([f"{rot:.0f}"] if rot else [])
    if at is None:
        node.insert(1, vals)
    else:
        at[:] = vals


def place(ref, spec):
    lib, name, dx, dy, rot, value, netmap = spec
    fp = load_fp(lib, name)

    # identify as a library footprint and position it on the page
    fp[1] = sexp.q(f"{lib}:{name}")
    for key in ("version", "generator", "generator_version"):
        node = sexp.find(fp, key)
        if node is not None:
            fp.remove(node)

    layer = sexp.find(fp, "layer")
    idx = fp.index(layer) + 1 if layer else 2
    fp.insert(idx, ["at", f"{OX + dx:.4f}", f"{OY + dy:.4f}"] + ([f"{rot:.0f}"] if rot else []))
    fp.insert(idx + 1, ["uuid", uid()])

    # reference + value text
    for prop in sexp.find_all(fp, "property"):
        pname = sexp.unq(prop[1])
        if pname == "Reference":
            prop[2] = sexp.q(ref)
            # mounting-hole labels sit in the corners and run off the edge
            if lib == LIB_HOLE:
                prop.append(["hide", "yes"])
        elif pname == "Value":
            prop[2] = sexp.q(value)
        if sexp.find(prop, "uuid") is None:
            prop.append(["uuid", uid()])

    # nets + etch-friendly pad sizes, capped by the footprint's own pitch
    if lib == LIB_RES:
        grow = PAD_RES
    elif lib == LIB_TERM:
        grow = PAD_P508
    else:
        grow = PAD_P254

    for pad in sexp.find_all(fp, "pad"):
        num = sexp.unq(pad[1])
        if pad[2] != "np_thru_hole":
            size = sexp.find(pad, "size")
            if size is not None:
                # oblong pads stay oblong -- only grow an axis, never shrink
                w, h = float(size[1]), float(size[2])
                size[1] = f"{max(w, grow):.4f}"
                size[2] = f"{max(h, grow):.4f}"
            net = netmap.get(int(num)) if num.isdigit() else None
            if net:
                pad.append(["net", str(NET_ID[net]), sexp.q(net)])
        if sexp.find(pad, "uuid") is None:
            pad.append(["uuid", uid()])

    return fp


def seg(x1, y1, x2, y2, net, width):
    return [
        "segment",
        ["start", f"{OX + x1:.4f}", f"{OY + y1:.4f}"],
        ["end", f"{OX + x2:.4f}", f"{OY + y2:.4f}"],
        ["width", f"{width}"],
        ["layer", sexp.q("F.Cu")],
        ["net", str(NET_ID[net])],
        ["uuid", uid()],
    ]


def edge(x1, y1, x2, y2):
    return [
        "gr_line",
        ["start", f"{OX + x1:.4f}", f"{OY + y1:.4f}"],
        ["end", f"{OX + x2:.4f}", f"{OY + y2:.4f}"],
        ["stroke", ["width", "0.1"], ["type", "default"]],
        ["layer", sexp.q("Edge.Cuts")],
        ["uuid", uid()],
    ]


def text(s, x, y, size=1.5):
    return [
        "gr_text", sexp.q(s),
        ["at", f"{OX + x:.4f}", f"{OY + y:.4f}"],
        ["layer", sexp.q("F.SilkS")],
        ["uuid", uid()],
        ["effects", ["font", ["size", f"{size}", f"{size}"], ["thickness", "0.25"]]],
    ]


def write_project():
    """Project file carrying the home-etching design rules, so DRC checks
    against 0.6 mm rather than KiCad's 0.2 mm fab defaults."""
    pro = {
        "board": {
            "design_settings": {
                "rules": {
                    "min_clearance": CLEARANCE,
                    "min_track_width": TRACK_MIN,
                    "min_through_hole_diameter": 0.8,
                    "min_hole_to_hole": 0.5,
                    "min_copper_edge_clearance": 0.5,
                    "min_text_height": 0.8,
                    "min_text_thickness": 0.08,
                },
                "track_widths": [0.0, TRACK_MIN, W_PWR, W_GND, W_HV],
            },
        },
        "net_settings": {
            "classes": [{
                "name": "Default",
                "clearance": CLEARANCE,
                "track_width": TRACK_MIN,
                "via_diameter": 0.8,
                "via_drill": 0.4,
                "priority": 2147483647,
            }],
        },
        "meta": {"filename": "freeisp_brain.kicad_pro", "version": 3},
    }
    path = OUT.replace(".kicad_pcb", ".kicad_pro")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(pro, fh, indent=2)
    print(f"wrote {path}")


def build():
    pcb = [
        "kicad_pcb",
        ["version", "20241229"],
        ["generator", sexp.q("freeisp-build.py")],
        ["generator_version", sexp.q("9.0")],
        ["general", ["thickness", "1.6"], ["legacy_teardrops", "no"]],
        ["paper", sexp.q("A4")],
        # KiCad's minimum is 2 copper layers, so B.Cu is declared but never
        # used -- every track is on F.Cu and only F.Cu gets plotted.
        ["layers",
         ["0", sexp.q("F.Cu"), "signal"],
         ["2", sexp.q("B.Cu"), "signal"],
         ["5", sexp.q("F.SilkS"), "user", sexp.q("F.Silkscreen")],
         ["1", sexp.q("F.Mask"), "user"],
         ["9", sexp.q("F.Adhes"), "user", sexp.q("F.Adhesive")],
         ["13", sexp.q("F.Paste"), "user"],
         ["17", sexp.q("Dwgs.User"), "user", sexp.q("User.Drawings")],
         ["19", sexp.q("Cmts.User"), "user", sexp.q("User.Comments")],
         ["21", sexp.q("Eco1.User"), "user", sexp.q("User.Eco1")],
         ["23", sexp.q("Eco2.User"), "user", sexp.q("User.Eco2")],
         ["25", sexp.q("Edge.Cuts"), "user"],
         ["27", sexp.q("Margin"), "user"],
         ["31", sexp.q("F.CrtYd"), "user", sexp.q("F.Courtyard")],
         ["35", sexp.q("F.Fab"), "user"],
         ],
        ["setup",
         ["pad_to_mask_clearance", "0.05"],
         ["allow_soldermask_bridges_in_footprints", "no"],
         ],
    ]

    for i, name in enumerate(NETS):
        pcb.append(["net", str(i), sexp.q(name)])

    for ref in sorted(PARTS):
        pcb.append(place(ref, PARTS[ref]))

    # board outline
    lo, hi = 0.0, BW
    pcb += [edge(lo, lo, hi, lo), edge(hi, lo, hi, hi),
            edge(hi, hi, lo, hi), edge(lo, hi, lo, lo)]

    # ---- perimeter ground ring ----
    a, b = RING, BW - RING
    for s in [(a, a, b, a), (b, a, b, b), (b, b, a, b), (a, b, a, a)]:
        pcb.append(seg(*s, "GND", W_GND))

    # ---- ground stubs: top row up, bottom row down, right headers across ----
    for x in (12, 40.54, 45.62, 54.54, 59.62, 70.08, 83.08):
        pcb.append(seg(x, 15, x, a, "GND", W_STUB))
    for x in (18.08, 26.54, 36, 48, 60.54, 70.54):
        pcb.append(seg(x, 86, x, b, "GND", W_STUB))
    for y in (24.54, 51.08, 70.54):
        pcb.append(seg(82, y, b, y, "GND", W_STUB))

    # ---- fused 12 V hops along the top row ----
    # 1.5 mm carries well over the horn's 1 A; wider would foul the pads
    # either side of these short runs.
    pcb.append(seg(17.08, 15, 25, 15, "+12V_RAW", W_STUB))
    pcb.append(seg(30.08, 15, 38, 15, "+12V", W_STUB))

    # ---- silkscreen ----
    # Kept clear of the part silk: the ring gap at the bottom is the only
    # open strip wide enough for text.
    pcb.append(text("FREEISP BRAIN  REV C  -  1 LAYER", 50, 94, 1.8))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(sexp.dumps(pcb) + "\n")

    print(f"wrote {OUT}")
    print(f"  {len(PARTS)} footprints, {len(NETS) - 1} nets")
    write_project()


if __name__ == "__main__":
    build()
