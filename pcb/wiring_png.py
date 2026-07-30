"""Which module pin reaches which ESP32 pin -- one clean line per wire.

Reads freeisp_brain.kicad_pcb (the file the fab receives), so every pin,
net and destination is taken from what is actually manufactured.

This is a LOGICAL view on purpose: it answers "where does this wire end up",
not "what shape is the copper". The real traces zig-zag round the board and
drawing them is unreadable spaghetti -- board.png shows those.

    python wiring_png.py   ->  wiring_diagram.png
"""

from PIL import Image, ImageDraw, ImageFont
import sexp

BOARD = "freeisp_brain.kicad_pcb"
OUT = "wiring_diagram.png"
W, H = 2600, 2010

BG = (250, 250, 247)
INK = (20, 26, 24)
MUTED = (112, 124, 118)
FAINT = (172, 182, 176)
CHIP = (30, 42, 50)
CHIP_ED = (14, 22, 28)
PADC = (214, 176, 74)
GPIOC = (150, 60, 30)
GNDC = (146, 158, 150)

COL = {"pwr": (200, 60, 45), "batt": (215, 140, 30),
       "sig": (48, 122, 66), "alarm": (170, 60, 150)}

DEVKIT = {
    "U3A": ["3V3", "EN", "VP", "VN", "D34", "D35", "D32", "D33", "D25", "D26",
            "D27", "D14", "D12", "GND", "D13", "SD2", "SD3", "CMD", "5V"],
    "U3B": ["GND", "D23", "D22", "TX0", "RX0", "D21", "GND", "D19", "D18",
            "D5", "D17", "D16", "D4", "D0", "D2", "D15", "SD1", "SD0", "CLK"],
}
FLASH = {"SD0", "SD1", "SD2", "SD3", "CMD", "CLK"}

# Power rails are not GPIO connections. A sense divider does bridge some of
# them to a pin, so describe what really happens instead of naming a GPIO.
OFFBOARD = {
    "+12V_IN": "-> D3 guard diode",
    "+12V":    "12 V rail   D34 senses it via R5/R6",
    "+5V":     "-> D1 -> 5V_SYS -> ESP32 5V",
    "+5V_BAT": "-> D2 -> 5V_SYS -> ESP32 5V",
    "VBAT":    "battery rail   D35 senses it via R3/R4",
}
VIA_PART = {"LED_R_A": "R1 220R", "LED_G_A": "R2 220R",
            "REED_F": "R8 1k", "HORN_DRV": "R7 1k"}


def font(sz, bold=False):
    for nm in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf"):
        try:
            return ImageFont.truetype(nm, sz)
        except OSError:
            continue
    return ImageFont.load_default()


F_T, F_S = font(40, True), font(19)
F_B, F_P = font(20, True), font(17)
F_N, F_TINY = font(15, True), font(14)


def board_data():
    with open(BOARD, encoding="utf-8") as fh:
        pcb = sexp.parse(fh.read())
    names = {int(n[1]): sexp.unq(n[2]) for n in sexp.find_all(pcb, "net")}
    pads = {}
    for fp in sexp.find_all(pcb, "footprint"):
        ref = "?"
        for prop in sexp.find_all(fp, "property"):
            if sexp.unq(prop[1]) == "Reference":
                ref = sexp.unq(prop[2])
        lst = []
        for pad in sexp.find_all(fp, "pad"):
            if pad[2] == "np_thru_hole":
                continue
            netn = sexp.find(pad, "net")
            lst.append((sexp.unq(pad[1]),
                        names[int(netn[1])] if netn else ""))
        lst.sort(key=lambda p: int(p[0]) if p[0].isdigit() else 99)
        pads[ref] = lst

    esp = {}                       # net -> [(row index, side)]
    for ref, side in (("U3A", "L"), ("U3B", "R")):
        for i, p in enumerate(pads.get(ref, [])):
            if p[1]:
                esp.setdefault(p[1], []).append((i, side))

    bridge = {}                    # series parts joining a net to a GPIO net
    for ref, lst in pads.items():
        if len(lst) == 2 and ref[0] in "RCD":
            (_a, na), (_b, nb) = lst
            bridge.setdefault(na, []).append(nb)
            bridge.setdefault(nb, []).append(na)
    return pads, esp, bridge


EXT = [
    ("J1", "12 V PSU", ["+12V", "GND"], "L", "pwr"),
    ("U1", "LM2596 BUCK   set 5.4 V", ["IN+", "IN-", "OUT+", "OUT-"], "L", "pwr"),
    ("U2", "TP4056 CHARGER", ["IN+", "IN-", "OUT+", "OUT-"], "L", "batt"),
    ("J13", "5 V BOOST   set 5.0 V", ["IN+", "IN-", "OUT+", "OUT-"], "L", "batt"),
    ("J7", "REED SWITCH", ["REED", "GND"], "L", "sig"),
    ("J8", "RED LED", ["GND", "LED+"], "L", "sig"),
    ("J9", "GREEN LED", ["GND", "LED+"], "L", "sig"),
    ("J4", "1.8in TFT ST7735S", ["GND", "VDD", "SCL", "SDA", "RST", "DC", "CS", "BLK"],
     "R", "sig"),
    ("J5", "RC522 READER   3.3 V only",
     ["SDA", "SCK", "MOSI", "MISO", "IRQ", "GND", "RST", "3.3V"], "R", "sig"),
    ("U4", "GY-521 MPU-6050",
     ["VCC", "GND", "SCL", "SDA", "XDA", "XCL", "AD0", "INT"], "R", "sig"),
    ("J10", "BUZZER", ["5V", "GND", "SIG"], "R", "alarm"),
    ("K1", "RELAY MODULE", ["IN", "GND", "VCC"], "R", "alarm"),
    ("J11", "HORN 3-5 V", ["+5V", "HORN-"], "R", "alarm"),
]

CX_L, CX_R = 1145, 1455
PY0, PSTEP = 205, 58
BW, ROW = 540, 24


def pin_y(i):
    return PY0 + i * PSTEP


def box(d, x, y, w, h, title, sub, c, fill=(255, 255, 255)):
    d.rounded_rectangle([x, y, x + w, y + h], 8, fill=fill, outline=c, width=3)
    d.text((x + 14, y + 9), title, INK, font=F_N)
    if sub:
        d.text((x + 14, y + 31), sub, MUTED, font=F_TINY)


def arrow(d, x1, y1, x2, y2, c, label=None):
    d.line([(x1, y1), (x2, y2)], fill=c, width=4)
    ang = 0 if y1 == y2 else (1 if y2 > y1 else -1)
    if ang == 0:
        d.polygon([(x2, y2), (x2 - 12, y2 - 7), (x2 - 12, y2 + 7)], fill=c)
    else:
        d.polygon([(x2, y2), (x2 - 7, y2 - 12 * ang), (x2 + 7, y2 - 12 * ang)], fill=c)
    if label:
        d.text(((x1 + x2) / 2 - d.textlength(label, font=F_TINY) / 2, y1 - 22),
               label, MUTED, font=F_TINY)


def draw_power_chain(d):
    """The journey the 12 V takes before anything on the board sees it."""
    P, B, S, G = COL["pwr"], COL["batt"], (35, 120, 180), COL["sig"]
    y0 = H - 448
    d.line([(60, y0 - 26), (W - 60, y0 - 26)], fill=(214, 218, 212), width=2)
    d.text((60, y0 - 16), "POWER CHAIN  -  what the 12 V passes through before it "
           "reaches anything", INK, font=F_B)
    d.text((62, y0 + 10), "the battery path joins the same rail, so a mains cut "
           "changes nothing the ESP32 can feel", MUTED, font=F_TINY)

    BW_, BH_, PITCH = 176, 58, 218
    ytop = y0 + 44
    mains = [
        ("12 V PSU", "mains adaptor", P),
        ("FUSE", "inline, in the + wire", P),
        ("J1", "12V IN terminal", P),
        ("D3  1N5822", "reverse-polarity guard", P),
        ("U1  BUCK", "set to 5.4 V", P),
        ("D1  1N5822", "one-way valve", S),
        ("5V_SYS", "the board's 5 V rail", S),
        ("ESP32 5V", "+ TFT, buzzer, relay, horn", S),
    ]
    xs = []
    for i, (t, s, c) in enumerate(mains):
        x = 66 + i * PITCH
        xs.append(x)
        box(d, x, ytop, BW_, BH_, t, s, c)
        if i:
            arrow(d, xs[i - 1] + BW_, ytop + BH_ / 2, x - 4, ytop + BH_ / 2, c)

    # the 12 V also feeds the sense divider
    xsense = xs[3] + 30
    ysense = ytop + BH_ + 62
    box(d, xsense, ysense, BW_ + 30, BH_, "R5 / R6 divider",
        "12 V -> 2.55 V so D34 can watch the mains", G)
    arrow(d, xs[3] + BW_ / 2, ytop + BH_, xsense + 60, ysense - 4, G)

    # battery path, merging into the same rail through D2
    ybat = ytop + BH_ + 150
    batt = [("U2  TP4056", "charges from the 5 V", B),
            ("18650 CELL", "on the module's B+/B-", B),
            ("J13  BOOST", "set to 5.0 V", B),
            ("D2  1N5822", "one-way valve", B)]
    for i, (t, s, c) in enumerate(batt):
        x = xs[3] + 60 + i * PITCH
        box(d, x, ybat, BW_, BH_, t, s, c)
        if i:
            arrow(d, x - PITCH + BW_, ybat + BH_ / 2, x - 4, ybat + BH_ / 2, c)
        if i == len(batt) - 1:
            mx = x + BW_ / 2
            d.line([(mx, ybat), (mx, ytop + BH_ + 26)], fill=B, width=4)
            arrow(d, mx, ytop + BH_ + 26, xs[6] + BW_ / 2, ytop + BH_ + 26, B)
            d.line([(xs[6] + BW_ / 2, ytop + BH_ + 26),
                    (xs[6] + BW_ / 2, ytop + BH_)], fill=B, width=4)
            d.polygon([(xs[6] + BW_ / 2, ytop + BH_),
                       (xs[6] + BW_ / 2 - 7, ytop + BH_ + 12),
                       (xs[6] + BW_ / 2 + 7, ytop + BH_ + 12)], fill=B)
    arrow(d, xs[4] + BW_ / 2, ytop + BH_, xs[3] + 60 + BW_ / 2, ybat - 4, B)

    d.text((xs[4] + 30, ytop + BH_ + 108),
           "D1 and D2 both point INTO the rail, so whichever side sits higher "
           "feeds it and the other simply waits.", MUTED, font=F_TINY)


def main():
    pads, esp, bridge = board_data()
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((60, 26), "FreeISP brain board  -  which wire reaches which ESP32 pin",
           INK, font=F_T)
    d.text((62, 78),
           "One line = one wire.  Read it as:  module pin  ->  the connector it "
           "plugs into  ->  the ESP32 pin it ends on.", MUTED, font=F_S)

    top, bot = PY0 - 58, pin_y(18) + 58
    d.rounded_rectangle([CX_L - 58, top, CX_R + 58, bot], 12,
                        fill=CHIP, outline=CHIP_ED, width=3)
    d.text(((CX_L + CX_R) // 2 - 106, top + 10), "ESP32 38-pin DevKitC",
           (235, 242, 240), font=F_B)
    d.text(((CX_L + CX_R) // 2 - 46, bot - 30), "antenna up",
           (140, 160, 172), font=F_TINY)

    for ref, cx, side in (("U3A", CX_L, "L"), ("U3B", CX_R, "R")):
        for i in range(19):
            y = pin_y(i)
            net = pads[ref][i][1] if i < len(pads[ref]) else ""
            lab = DEVKIT[ref][i]
            lit = bool(net)
            d.ellipse([cx - 8, y - 8, cx + 8, y + 8],
                      fill=PADC if lit else (76, 90, 98))
            col = (240, 246, 244) if lit else (118, 134, 144)
            if side == "L":
                d.text((cx + 18, y - 10), lab, col, font=F_N)
            else:
                d.text((cx - 18 - d.textlength(lab, font=F_N), y - 10),
                       lab, col, font=F_N)
            if not lit:
                note = "FLASH" if lab in FLASH else "spare"
                nc = (198, 120, 96) if lab in FLASH else (108, 124, 134)
                if side == "L":
                    d.text((cx + 74, y - 8), note, nc, font=F_TINY)
                else:
                    d.text((cx - 78 - d.textlength(note, font=F_TINY), y - 8),
                           note, nc, font=F_TINY)

    heights = {r: 34 + ROW * len(s) for r, _t, s, _c, _k in EXT}
    ys = {}
    for col in ("L", "R"):
        refs = [e[0] for e in EXT if e[3] == col]
        tot = sum(heights[r] for r in refs)
        gap = (bot - top - tot) / max(1, len(refs) - 1)
        y = top
        for r in refs:
            ys[r] = y
            y += heights[r] + gap

    lane_n = {"L": 0, "R": 0}
    cross_n = {"L": 0, "R": 0}
    for ref, title, silk, col, ckey in EXT:
        c = COL[ckey]
        lst = pads.get(ref, [])
        y0 = ys[ref]
        bx = 60 if col == "L" else W - 60 - BW

        d.rounded_rectangle([bx, y0, bx + BW, y0 + heights[ref]], 9,
                            fill=(255, 255, 255), outline=c, width=3)
        d.rectangle([bx, y0, bx + 7, y0 + heights[ref]], fill=c)
        d.text((bx + 20, y0 + 7), title, INK, font=F_B)
        d.text((bx + BW - 54, y0 + 8), ref, c, font=F_B)

        for i, nm in enumerate(silk):
            ry = y0 + 32 + i * ROW
            net = lst[i][1] if i < len(lst) else ""
            if not net:
                d.text((bx + 26, ry), f"{i + 1}", FAINT, font=F_N)
                d.text((bx + 54, ry), nm, FAINT, font=F_P)
                d.text((bx + 158, ry), "hole only - no wire", FAINT, font=F_N)
                continue

            target, via = esp.get(net), None
            if not target:
                for other in bridge.get(net, []):
                    if other in esp:
                        target, via = esp[other], VIA_PART.get(net)
                        break

            d.text((bx + 26, ry), f"{i + 1}", MUTED, font=F_N)
            d.text((bx + 54, ry), nm, INK, font=F_P)
            if not target:
                d.text((bx + 158, ry), OFFBOARD.get(net, net), MUTED, font=F_N)
                continue

            row, side = target[0]
            lab = DEVKIT["U3A" if side == "L" else "U3B"][row]
            rail = net in OFFBOARD
            txt = OFFBOARD[net] if rail else                 (f"ESP32 {lab}" + (f"   via {via}" if via else ""))
            d.text((bx + 158, ry), txt,
                   MUTED if rail else (GNDC if net == "GND" else GPIOC),
                   font=F_N)

            sx = bx + BW if col == "L" else bx
            sy = ry + 8
            ey = pin_y(row)
            lane_n[col] += 1
            lane = (630 + lane_n[col] * 15) if col == "L" \
                else (W - 630 - lane_n[col] * 14)
            wcol = GNDC if net == "GND" else c

            # The pin may sit on the OPPOSITE column from its module. Ending
            # the line at the near edge would point it at the wrong pins, so
            # go round the chip -- whichever end is closer -- and arrive on
            # the side the pin is really on.
            ex = (CX_L - 10) if side == "L" else (CX_R + 10)
            if side == col:
                pts = [(sx, sy), (lane, sy), (lane, ey), (ex, ey)]
            else:
                cross_n[col] += 1
                k = cross_n[col]
                around = (top - 14 - (k % 7) * 10) if abs(ey - top) < abs(ey - bot) \
                    else (bot + 14 + (k % 7) * 10)
                far = (CX_L - 30 - k * 9) if side == "L" else (CX_R + 30 + k * 9)
                pts = [(sx, sy), (lane, sy), (lane, around),
                       (far, around), (far, ey), (ex, ey)]

            d.line(pts, fill=wcol, width=2 if net == "GND" else 3)
            d.ellipse([sx - 4, sy - 4, sx + 4, sy + 4], fill=wcol)
            d.ellipse([ex - 4, ey - 4, ex + 4, ey + 4], fill=wcol)

    draw_power_chain(d)

    ly = H - 58
    for i, (k, lab) in enumerate([("pwr", "12 V input"), ("batt", "battery / charge"),
                                  ("sig", "logic"), ("alarm", "alarm")]):
        x = 60 + i * 210
        d.line([(x, ly), (x + 34, ly)], fill=COL[k], width=6)
        d.text((x + 44, ly - 9), lab, INK, font=F_N)
    d.line([(910, ly), (944, ly)], fill=GNDC, width=6)
    d.text((954, ly - 9), "ground", INK, font=F_N)
    d.text((1120, ly - 30),
           "grey devkit pins carry no wire.  SD0-SD3 / CMD / CLK are the flash pins "
           "- using one stops the board booting.", MUTED, font=F_N)
    d.text((1120, ly - 8),
           "Logical view: the real copper zig-zags round the board - board.png shows "
           "the actual traces.", MUTED, font=F_N)

    img.save(OUT)
    print(f"wrote {OUT}  ({W}x{H})")


if __name__ == "__main__":
    main()
