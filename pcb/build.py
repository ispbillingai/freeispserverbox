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
import math
import os
import uuid as _uuid
import router
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
# Fab rules, not etching rules. PCBWay's cheap tier does 0.15 mm; 0.25 mm is
# a comfortable margin and buys real routing room over the 0.6 mm we needed
# when the board was going to be made with chemicals in a tray.
CLEARANCE = 0.25
TRACK_MIN = 0.4

# Library pad sizes are right for a fab -- their drilling is accurate to about
# 0.05 mm, so there is nothing to compensate for. 0 means "leave as drawn".
PAD_P254 = 0
PAD_P508 = 0
PAD_RES = 0

LIB_SOCKET = "Connector_PinSocket_2.54mm"
LIB_HEADER = "Connector_PinHeader_2.54mm"
LIB_TERM = "Connector_Phoenix_MC_HighVoltage"
LIB_RES = "Resistor_THT"
LIB_DIODE = "Diode_THT"
LIB_HOLE = "MountingHole"

FP_SOCKET15 = "PinSocket_1x15_P2.54mm_Vertical"
FP_TERM2 = "PhoenixContact_MCV_1,5_2-G-5.08_1x02_P5.08mm_Vertical"
FP_TERM4 = "PhoenixContact_MCV_1,5_4-G-5.08_1x04_P5.08mm_Vertical"
FP_RES = "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
FP_DIODE = "D_DO-201AD_P12.70mm_Horizontal"
FP_HOLE = "MountingHole_3.2mm_M3"


def hdr(n):
    return f"PinHeader_1x0{n}_P2.54mm_Vertical"


# ---------------------------------------------------------------- nets
NETS = [
    "", "GND", "+5V", "+5V_BAT", "+5V_SYS", "+3V3", "+12V", "VBAT", "SENSE_BATT",
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
    8: "LED_R", 9: "LED_G", 10: "BUZZ", 13: "HORN_IN", 14: "GND",
    15: "+5V_SYS",   # VIN eats from whichever diode is alive
}
U3B_NETS = {
    1: "MOSI", 2: "SCL", 5: "SDA", 6: "MISO", 7: "SCK", 8: "TFT_CS",
    9: "RC_RST", 10: "RC_SS", 11: "TFT_RST", 12: "TFT_DC", 14: "GND", 15: "+3V3",
}

PARTS = {
    # --- power in, top row. The buck and charger are wire-pad modules, not
    # pluggable headers, so they bolt alongside and land on screw terminals.
    # Fuse the 12 V feed inline in the wire (silkscreened as a reminder).
    "J1":  (LIB_TERM, FP_TERM2, 14, 15, 0, "12V IN",
            {1: "GND", 2: "+12V"}),
    "U1":  (LIB_TERM, FP_TERM4, 33, 15, 0, "BUCK  IN+ IN- OUT+ OUT-",
            {1: "+12V", 2: "GND", 3: "+5V", 4: "GND"}),
    "U2":  (LIB_TERM, FP_TERM4, 58, 15, 0, "CHARGER  IN+ IN- B+ B-",
            {1: "+5V", 2: "GND", 3: "VBAT", 4: "GND"}),

    # --- backup power: step-up + the diode-OR where the two 5V rails meet.
    # Mains alive: buck 5V wins through D1 (charger tops the cell up).
    # Mains cut: boost 5V takes over through D2. No code, no switching.
    # Charger IN+ stays on the BUCK rail on purpose -- feeding it from
    # 5V_SYS would let the battery charge itself through the boost.
    "J13": (LIB_TERM, FP_TERM4, 14, 24, 0, "BOOST  IN+ IN- OUT+ OUT-",
            {1: "VBAT", 2: "GND", 3: "+5V_BAT", 4: "GND"}),
    "D1":  (LIB_DIODE, FP_DIODE, 38, 25, 0, "1N5822",
            {1: "+5V_SYS", 2: "+5V"}),        # pad 1 = cathode (band)
    "D2":  (LIB_DIODE, FP_DIODE, 56, 25, 0, "1N5822",
            {1: "+5V_SYS", 2: "+5V_BAT"}),

    # --- the brain ---
    "U3A": (LIB_SOCKET, FP_SOCKET15, 32, 32, 0, "ESP32 L", U3A_NETS),
    "U3B": (LIB_SOCKET, FP_SOCKET15, 57.4, 32, 0, "ESP32 R", U3B_NETS),

    # --- peripherals. Pin ORDER is the module's own silkscreen order, and
    # every physical pin gets a hole even where we do not use the signal.
    # TFT (blue ST7735S): GND VDD SCL SDA RST DC CS BLK
    # All three stack down the right edge. U4 was briefly in the channel
    # between the ESP32 rows -- that channel is a dead end (a pin row cannot
    # be crossed), so every trace to it had to come the long way round and
    # curl past U4's own unused pins. Six nets ended up knotted in there.
    "J4":  (LIB_HEADER, hdr(8), 82, 12, 0, "TFT",
            {1: "GND", 2: "+5V_SYS", 3: "SCK", 4: "MOSI", 5: "TFT_RST",
             6: "TFT_DC", 7: "TFT_CS", 8: "TFT_BLK"}),
    # RC522: SDA SCK MOSI MISO IRQ GND RST 3.3V  (IRQ unused but present)
    "J5":  (LIB_HEADER, hdr(8), 82, 36, 0, "RC522",
            {1: "RC_SS", 2: "SCK", 3: "MOSI", 4: "MISO",
             6: "GND", 7: "RC_RST", 8: "+3V3"}),
    # GY-521: VCC GND SCL SDA XDA XCL AD0 INT  (last four unused but present)
    "U4":  (LIB_HEADER, hdr(8), 82, 60, 0, "MPU-6050",
            {1: "+3V3", 2: "GND", 3: "SCL", 4: "SDA"}),

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
    # buzzer + relay live on 5V_SYS: the alarm must sound with the mains cut
    "J10": (LIB_HEADER, hdr(3), 58, 86, 90, "BUZZER",
            {1: "+5V_SYS", 2: "GND", 3: "BUZZ"}),
    "K1":  (LIB_HEADER, hdr(3), 68, 86, 90, "HORN RLY",
            {1: "HORN_IN", 2: "GND", 3: "+5V_SYS"}),
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


def pad_grow(lib):
    if lib == LIB_RES:
        return PAD_RES
    if lib == LIB_TERM:
        return PAD_P508
    return PAD_P254


def pad_positions(spec):
    """Absolute pad centres in design coordinates, matching what place() emits.

    KiCad rotates a footprint counter-clockwise with Y running down, so a pad
    at local (lx, ly) lands at (px + lx.cos + ly.sin, py - lx.sin + ly.cos).
    """
    lib, name, dx, dy, rot, _value, netmap = spec
    fp = load_fp(lib, name)
    grow = pad_grow(lib)
    th = math.radians(rot)
    cos_t, sin_t = math.cos(th), math.sin(th)

    out = []
    for pad in sexp.find_all(fp, "pad"):
        if pad[2] == "np_thru_hole":
            continue
        num = sexp.unq(pad[1])
        at = sexp.find(pad, "at")
        lx, ly = float(at[1]), float(at[2])
        size = sexp.find(pad, "size")
        w = max(float(size[1]), grow)
        h = max(float(size[2]), grow)
        net = netmap.get(int(num)) if num.isdigit() else None
        out.append({
            "num": num,
            "x": dx + lx * cos_t + ly * sin_t,
            "y": dy - lx * sin_t + ly * cos_t,
            "half": max(w, h) / 2.0,
            "net": net,
        })
    return out


def seg(x1, y1, x2, y2, net, width, layer="F.Cu"):
    return [
        "segment",
        ["start", f"{OX + x1:.4f}", f"{OY + y1:.4f}"],
        ["end", f"{OX + x2:.4f}", f"{OY + y2:.4f}"],
        ["width", f"{width}"],
        ["layer", sexp.q(layer)],
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


# Routed power is kept modest: these rails carry a relay coil and a buzzer,
# not the horn, so 0.8 mm is ample and leaves lanes for the signals.
NET_WIDTH = {
    "GND": 1.2, "+5V": 0.8, "+5V_BAT": 0.8, "+5V_SYS": 0.8, "+3V3": 0.8,
    "+12V": 1.2, "VBAT": 0.8,
}
W_SIGNAL = 0.6


def _key(x, y):
    return (round(x * 100), round(y * 100))


def _on_segment(px, py, x1, y1, x2, y2, tol=0.15):
    return router.Router._seg_dist(px, py, x1, y1, x2, y2) <= tol


def auto_route(tracks, strategy):
    """Route every net that is not already connected.

    Two etched layers: F.Cu is tried first, and anything that cannot get
    through falls to B.Cu. Both are real copper and obstruct each other.
    All pads are through-hole, so a connection can live entirely on either
    layer and no vias are needed.
    """
    # Every pad is an obstacle, including the ESP32 pins we do not use --
    # an unconnected pin is still copper and a track across it is a short.
    all_pads = []
    for ref in sorted(PARTS):
        for p in pad_positions(PARTS[ref]):
            p["ref"] = ref
            all_pads.append(p)
    pads = [p for p in all_pads if p["net"]]

    rt = router.Router(BW, BH)
    for p in all_pads:
        rt.add_pad(p["x"], p["y"], p["half"], p["net"])
    for t in tracks:
        rt.add_track(t["x1"], t["y1"], t["x2"], t["y2"], t["w"], t["net"],
                     t["layer"])

    # ---- union-find seeded with what the base copper already joins ----
    parent = {}

    def find(k):
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    def seed():
        parent.clear()
        for t in tracks:
            union(_key(t["x1"], t["y1"]), _key(t["x2"], t["y2"]))
        # a stub landing mid-ring shares copper with it
        for t in tracks:
            for px, py in ((t["x1"], t["y1"]), (t["x2"], t["y2"])):
                for u in tracks:
                    if u is t or u["net"] != t["net"]:
                        continue
                    if _on_segment(px, py, u["x1"], u["y1"], u["x2"], u["y2"]):
                        union(_key(px, py), _key(u["x1"], u["y1"]))
        for p in pads:
            for t in tracks:
                if t["net"] != p["net"]:
                    continue
                if _on_segment(p["x"], p["y"], t["x1"], t["y1"], t["x2"], t["y2"]):
                    union(_key(p["x"], p["y"]), _key(t["x1"], t["y1"]))

    by_net = {}
    for p in pads:
        by_net.setdefault(p["net"], []).append(p)

    edges = []
    for net, group in by_net.items():
        if len(group) < 2:
            continue
        pts = [(p["x"], p["y"]) for p in group]
        for i, j in router.mst_edges(pts):
            span = abs(pts[i][0] - pts[j][0]) + abs(pts[i][1] - pts[j][1])
            edges.append((span, net, group[i], group[j]))

    # Routing order changes the result a lot and no heuristic wins every time,
    # so build() tries each and keeps whichever needs the fewest links.
    if strategy == "short":
        edges.sort(key=lambda e: e[0])
    elif strategy == "long":
        edges.sort(key=lambda e: -e[0])
    else:  # power rails first, then shortest
        edges.sort(key=lambda e: (e[1] not in NET_WIDTH, e[0]))

    vias = []
    failed = []
    for _span, net, pa, pb in edges:
        seed()
        a = (pa["x"], pa["y"])
        b = (pb["x"], pb["y"])
        if find(_key(*a)) == find(_key(*b)):
            continue

        width = NET_WIDTH.get(net, W_SIGNAL)
        path = rt.route(net, a, b, width / 2.0)
        if path is None:
            failed.append((net, pa["ref"], pb["ref"]))
            continue

        for k in range(len(path) - 1):
            x1, y1, l1 = path[k]
            x2, y2, l2 = path[k + 1]
            if l1 != l2:
                # the path stays put and changes layer: that is a via
                vias.append({"x": x1, "y": y1, "net": net})
                rt.add_pad(x1, y1, router.VIA_D / 2.0, net)
                continue
            tracks.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                           "w": width, "net": net, "layer": l1})
            rt.add_track(x1, y1, x2, y2, width, net, l1)

    return vias, failed


def write_project():
    """Project file carrying the home-etching design rules, so DRC checks
    against 0.6 mm rather than KiCad's 0.2 mm fab defaults."""
    pro = {
        "board": {
            "design_settings": {
                "rules": {
                    "min_clearance": CLEARANCE,
                    "min_track_width": TRACK_MIN,
                    # 0.3 mm drill / 0.25 mm hole-to-hole sits inside every
                    # fab's cheap tier; the old 0.8 was a hand-drilling limit.
                    "min_through_hole_diameter": 0.3,
                    "min_hole_to_hole": 0.25,
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

    # Both layers are etched now, so the wire-link exemption is gone.
    dru = OUT.replace(".kicad_pcb", ".kicad_dru")
    if os.path.exists(dru):
        os.remove(dru)


def build():
    pcb = [
        "kicad_pcb",
        ["version", "20241229"],
        ["generator", sexp.q("freeisp-build.py")],
        ["generator_version", sexp.q("9.0")],
        ["general", ["thickness", "1.6"], ["legacy_teardrops", "no"]],
        ["paper", sexp.q("A4")],
        ["layers",
         ["0", sexp.q("F.Cu"), "signal"],
         ["2", sexp.q("B.Cu"), "signal"],
         ["5", sexp.q("F.SilkS"), "user", sexp.q("F.Silkscreen")],
         ["7", sexp.q("B.SilkS"), "user", sexp.q("B.Silkscreen")],
         ["1", sexp.q("F.Mask"), "user"],
         ["3", sexp.q("B.Mask"), "user"],
         ["9", sexp.q("F.Adhes"), "user", sexp.q("F.Adhesive")],
         ["11", sexp.q("B.Adhes"), "user", sexp.q("B.Adhesive")],
         ["13", sexp.q("F.Paste"), "user"],
         ["15", sexp.q("B.Paste"), "user"],
         ["17", sexp.q("Dwgs.User"), "user", sexp.q("User.Drawings")],
         ["19", sexp.q("Cmts.User"), "user", sexp.q("User.Comments")],
         ["21", sexp.q("Eco1.User"), "user", sexp.q("User.Eco1")],
         ["23", sexp.q("Eco2.User"), "user", sexp.q("User.Eco2")],
         ["25", sexp.q("Edge.Cuts"), "user"],
         ["27", sexp.q("Margin"), "user"],
         ["31", sexp.q("F.CrtYd"), "user", sexp.q("F.Courtyard")],
         ["29", sexp.q("B.CrtYd"), "user", sexp.q("B.Courtyard")],
         ["35", sexp.q("F.Fab"), "user"],
         ["33", sexp.q("B.Fab"), "user"],
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

    # ---- base copper: laid out by hand, then handed to the router as fixed ----
    tracks = []

    def base(x1, y1, x2, y2, net, width):
        tracks.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                       "w": width, "net": net, "layer": "F.Cu"})

    a, b = RING, BW - RING
    for s in [(a, a, b, a), (b, a, b, b), (b, b, a, b), (a, b, a, a)]:
        base(*s, "GND", W_GND)

    # ground stubs: top row up, bottom row down, right headers across
    for x in (14, 38.08, 48.24, 63.08, 73.24):
        base(x, 15, x, a, "GND", W_STUB)
    for x in (18.08, 26.54, 36, 48, 60.54, 70.54):
        base(x, 86, x, b, "GND", W_STUB)
    for y in (12, 48.70, 62.54):        # J4 pin1, J5 pin6, U4 pin2
        base(82, y, b, y, "GND", W_STUB)

    # 12 V from the input terminal across to the buck
    base(19.08, 15, 33, 15, "+12V", W_STUB)

    base_tracks = list(tracks)
    n_base = len(tracks)

    best = None
    for strategy in ("power", "short", "long"):
        trial = [dict(t) for t in base_tracks]
        vias, failed = auto_route(trial, strategy)
        score = len(failed) * 1000 + len(vias)
        print(f"  strategy {strategy:<6} -> {len(vias)} vias, {len(failed)} unrouted")
        if best is None or score < best[0]:
            best = (score, trial, vias, failed, strategy)

    _, tracks, vias, failed, strategy = best
    print(f"  using '{strategy}'")

    for t in tracks:
        pcb.append(seg(t["x1"], t["y1"], t["x2"], t["y2"],
                       t["net"], t["w"], t["layer"]))
    for v in vias:
        pcb.append([
            "via",
            ["at", f"{OX + v['x']:.4f}", f"{OY + v['y']:.4f}"],
            ["size", f"{router.VIA_D}"],
            ["drill", f"{router.VIA_DRILL}"],
            ["layers", sexp.q("F.Cu"), sexp.q("B.Cu")],
            ["net", str(NET_ID[v["net"]])],
            ["uuid", uid()],
        ])

    # ---- silkscreen ----
    # Kept clear of the part silk: the ring gap at the bottom is the only
    # open strip wide enough for text.
    pcb.append(text("FREEISP BRAIN  REV D  -  2 LAYER", 50, 94, 1.8))
    pcb.append(text("FUSE THE 12V FEED INLINE", 50, 11.5, 1.1))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(sexp.dumps(pcb) + "\n")

    print(f"wrote {OUT}")
    print(f"  {len(PARTS)} footprints, {len(NETS) - 1} nets")
    print(f"  {n_base} base segments, {len(tracks) - n_base} routed segments")
    print(f"  {len(vias)} vias")
    if failed:
        print(f"  !! {len(failed)} UNROUTED:")
        for net, ra, rb in failed:
            print(f"      {net:<12} {ra} -> {rb}")
    write_project()


if __name__ == "__main__":
    build()
