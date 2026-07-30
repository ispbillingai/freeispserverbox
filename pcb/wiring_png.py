"""Draw the external wiring: ONE LINE PER WIRE, landing on its real hole.

Reads freeisp_brain.kicad_pcb -- the file the fab receives -- and uses the
actual pad coordinates, so each wire is drawn to the hole it truly enters.
The board in the middle is to scale; connector pads sit where they sit.

Each row:  pin no. | name PRINTED ON THE MODULE | the ESP32 pin it reaches

    python wiring_png.py   ->  wiring_diagram.png
"""

from PIL import Image, ImageDraw, ImageFont
import sexp

BOARD = "freeisp_brain.kicad_pcb"
OUT = "wiring_diagram.png"
W, H = 2600, 1420

BG = (250, 250, 247)
INK = (20, 26, 24)
MUTED = (112, 124, 118)
FAINT = (170, 180, 174)
BOARDC = (24, 96, 74)
BOARD_ED = (12, 56, 42)
PADC = (214, 176, 74)
GPIOC = (150, 60, 30)

COL = {
    "pwr":   (200, 60, 45),
    "batt":  (215, 140, 30),
    "sig":   (55, 125, 70),
    "alarm": (170, 60, 150),
}

DEVKIT = {
    "U3A": ["3V3", "EN", "VP", "VN", "D34", "D35", "D32", "D33", "D25", "D26",
            "D27", "D14", "D12", "GND", "D13", "SD2", "SD3", "CMD", "5V"],
    "U3B": ["GND", "D23", "D22", "TX0", "RX0", "D21", "GND", "D19", "D18",
            "D5", "D17", "D16", "D4", "D0", "D2", "D15", "SD1", "SD0", "CLK"],
}

INDIRECT = {
    "LED_R_A": "via R1 220R -> D25",
    "LED_G_A": "via R2 220R -> D26",
    "REED_F":  "via R8 1k -> D32",
    "HORN_DRV": "via R7 1k -> D13",
    "+12V_IN": "-> D3 guard",
    "+12V":    "buck in, R5/R6 sense",
    "+5V":     "buck out -> D1",
    "+5V_BAT": "boost out -> D2",
    "VBAT":    "battery, R3/R4 sense",
}


def font(sz, bold=False):
    for nm in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf"):
        try:
            return ImageFont.truetype(nm, sz)
        except OSError:
            continue
    return ImageFont.load_default()


F_T, F_S = font(40, True), font(19)
F_B, F_P = font(20, True), font(17)
F_N, F_TINY = font(15, True), font(13)


def board_data():
    with open(BOARD, encoding="utf-8") as fh:
        pcb = sexp.parse(fh.read())
    names = {int(n[1]): sexp.unq(n[2]) for n in sexp.find_all(pcb, "net")}
    import math
    pads = {}
    for fp in sexp.find_all(pcb, "footprint"):
        ref = "?"
        for prop in sexp.find_all(fp, "property"):
            if sexp.unq(prop[1]) == "Reference":
                ref = sexp.unq(prop[2])
        fat = sexp.find(fp, "at")
        fx, fy = float(fat[1]), float(fat[2])
        rot = math.radians(float(fat[3]) if len(fat) > 3 else 0.0)
        c, s = math.cos(rot), math.sin(rot)
        lst = []
        for pad in sexp.find_all(fp, "pad"):
            if pad[2] == "np_thru_hole":
                continue
            at = sexp.find(pad, "at")
            lx, ly = float(at[1]), float(at[2])
            netn = sexp.find(pad, "net")
            lst.append((sexp.unq(pad[1]),
                        names[int(netn[1])] if netn else "",
                        fx + lx * c + ly * s, fy - lx * s + ly * c))
        lst.sort(key=lambda p: int(p[0]) if p[0].isdigit() else 99)
        pads[ref] = lst
    esp = {}
    for ref in ("U3A", "U3B"):
        for i, p in enumerate(pads.get(ref, [])):
            if p[1]:
                esp.setdefault(p[1], []).append(DEVKIT[ref][i])
    return pads, esp


# ref, title, silk pin names, column, y, colour, which board edge the wire enters
EXT = [
    ("J1", "12 V PSU", ["+12V", "GND"], "L", 150, "pwr", "T"),
    ("U1", "LM2596 BUCK  set 5.4V", ["IN+", "IN-", "OUT+", "OUT-"], "L", 250, "pwr", "T"),
    ("U2", "TP4056 CHARGER", ["IN+", "IN-", "OUT+", "OUT-"], "L", 395, "batt", "T"),
    ("J13", "5 V BOOST  set 5.0V", ["IN+", "IN-", "OUT+", "OUT-"], "L", 540, "batt", "L"),
    ("J7", "REED SWITCH", ["REED", "GND"], "L", 690, "sig", "B"),
    ("J8", "RED LED", ["GND", "LED+"], "L", 800, "sig", "B"),
    ("J9", "GREEN LED", ["GND", "LED+"], "L", 910, "sig", "B"),

    ("J4", "1.8in TFT ST7735S", ["GND", "VDD", "SCL", "SDA", "RST", "DC", "CS", "BLK"],
     "R", 150, "sig", "R"),
    ("J5", "RC522 READER  3.3V", ["SDA", "SCK", "MOSI", "MISO", "IRQ", "GND", "RST", "3.3V"],
     "R", 385, "sig", "R"),
    ("U4", "GY-521 MPU-6050", ["VCC", "GND", "SCL", "SDA", "XDA", "XCL", "AD0", "INT"],
     "R", 620, "sig", "R"),
    ("J10", "BUZZER", ["5V", "GND", "SIG"], "R", 855, "alarm", "B"),
    ("K1", "RELAY MODULE", ["IN", "GND", "VCC"], "R", 975, "alarm", "B"),
    ("J11", "HORN 3-5 V", ["+5V", "HORN-"], "R", 1095, "alarm", "B"),
]

BX0, BY0, SIDE = 950, 250, 700          # board box on the canvas
MM = SIDE / 115.0
BWID, ROW = 560, 22


def px(mm_x):
    return BX0 + mm_x * MM


def py(mm_y):
    return BY0 + mm_y * MM


def main():
    pads, esp = board_data()
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((60, 30), "FreeISP brain board  -  every wire, and the hole it enters",
           INK, font=F_T)
    d.text((62, 84),
           "One line = one wire.  Board drawn to scale from freeisp_brain.kicad_pcb, "
           "so each line ends on the hole it really goes to.", MUTED, font=F_S)

    # ---------------- board ----------------
    d.rounded_rectangle([BX0, BY0, BX0 + SIDE, BY0 + SIDE], 10,
                        fill=BOARDC, outline=BOARD_ED, width=3)
    for mx, my in ((4.5, 4.5), (110.5, 4.5), (4.5, 110.5), (110.5, 110.5)):
        d.ellipse([px(mx) - 9, py(my) - 9, px(mx) + 9, py(my) + 9], fill=PADC)
        d.ellipse([px(mx) - 4, py(my) - 4, px(mx) + 4, py(my) + 4], fill=BOARD_ED)

    # devkit outline + its pins
    d.rectangle([px(42.5), py(28), px(70.9), py(91.7)], outline=(140, 195, 172), width=2)
    for ref, mx in (("U3A", 44.0), ("U3B", 69.4)):
        for i, p in enumerate(pads[ref]):
            yy = py(34 + i * 2.54)
            d.ellipse([px(mx) - 4, yy - 4, px(mx) + 4, yy + 4],
                      fill=PADC if p[1] else (95, 135, 116))
    d.text((px(46), py(24)), "ESP32 38-pin DevKitC", (228, 242, 234), font=F_N)
    d.text((px(45), py(94)), "body keep-out", (140, 195, 172), font=F_TINY)

    # every other pad, so nothing looks missing
    for ref, lst in pads.items():
        if ref in ("U3A", "U3B") or ref.startswith("H"):
            continue
        known = {e[0] for e in EXT}
        for p in lst:
            r = 5 if ref in known else 3.5
            d.ellipse([px(p[2]) - r, py(p[3]) - r, px(p[2]) + r, py(p[3]) + r],
                      fill=PADC if ref in known else (150, 190, 168))

    d.text((px(6), py(107)), "small dots = parts already soldered on (R, C, D)",
           (168, 214, 194), font=F_TINY)

    # box and name each connector on the board itself
    for ref, _t, _s, _c, _y, ckey, edge in EXT:
        lst = pads.get(ref, [])
        if not lst:
            continue
        xs = [p[2] for p in lst]
        ys = [p[3] for p in lst]
        m = 2.2
        d.rounded_rectangle([px(min(xs) - m), py(min(ys) - m),
                             px(max(xs) + m), py(max(ys) + m)], 4,
                            outline=COL[ckey], width=2)
        lx, ly_ = px((min(xs) + max(xs)) / 2), py((min(ys) + max(ys)) / 2)
        tw = d.textlength(ref, font=F_N)
        if edge == "T":
            pos = (lx - tw / 2, py(max(ys) + m) + 4)
        elif edge == "B":
            pos = (lx - tw / 2, py(min(ys) - m) - 20)
        elif edge == "L":
            pos = (px(max(xs) + m) + 6, ly_ - 8)
        else:
            pos = (px(min(xs) - m) - tw - 8, ly_ - 8)
        d.text(pos, ref, (240, 248, 244), font=F_N)

    # ---------------- modules + one line per wire ----------------
    lane_l, lane_r = 640, W - 640
    for idx, (ref, title, silk, col, y, ckey, edge) in enumerate(EXT):
        c = COL[ckey]
        lst = pads.get(ref, [])
        bh = 34 + ROW * len(silk)
        bx = 60 if col == "L" else W - 60 - BWID

        d.rounded_rectangle([bx, y, bx + BWID, y + bh], 9,
                            fill=(255, 255, 255), outline=c, width=3)
        d.rectangle([bx, y, bx + 7, y + bh], fill=c)
        d.text((bx + 20, y + 7), title, INK, font=F_B)
        d.text((bx + BWID - 52, y + 8), ref, c, font=F_B)

        lane = (lane_l + idx * 13) if col == "L" else (lane_r - idx * 13)

        for i, nm in enumerate(silk):
            ry = y + 32 + i * ROW
            net = lst[i][1] if i < len(lst) else ""
            wired = bool(net)
            tone = INK if wired else FAINT

            d.text((bx + 26, ry), f"{i + 1}", MUTED if wired else FAINT, font=F_N)
            d.text((bx + 52, ry), nm, tone, font=F_P)
            if wired:
                gp = esp.get(net)
                txt = ("ESP32 " + "/".join(sorted(set(gp), key=gp.index))) if gp \
                    else INDIRECT.get(net, net)
                d.text((bx + 168, ry), txt, GPIOC if gp else MUTED, font=F_N)
            else:
                d.text((bx + 168, ry), "no wire - hole only", FAINT, font=F_N)
                continue

            # ---- the wire itself ----
            sx = bx + BWID if col == "L" else bx
            sy = ry + 8
            tx, ty = px(lst[i][2]), py(lst[i][3])
            off = 26 + i * 11
            if edge == "T":
                ax, ay = tx, BY0 - off
            elif edge == "B":
                ax, ay = tx, BY0 + SIDE + off
            elif edge == "L":
                ax, ay = BX0 - off, ty
            else:
                ax, ay = BX0 + SIDE + off, ty

            pts = [(sx, sy), (lane, sy)]
            if edge in ("T", "B"):
                pts += [(lane, ay), (ax, ay), (tx, ty)]
            else:
                pts += [(lane, ay), (ax, ay), (tx, ty)]
            d.line(pts, fill=c, width=2)
            d.ellipse([tx - 4, ty - 4, tx + 4, ty + 4], fill=c)
            d.ellipse([sx - 3, sy - 3, sx + 3, sy + 3], fill=c)

    # ---------------- legend ----------------
    ly = H - 62
    for i, (k, lab) in enumerate([("pwr", "12 V input"), ("batt", "battery / charge"),
                                  ("sig", "logic"), ("alarm", "alarm")]):
        x = 60 + i * 230
        d.line([(x, ly), (x + 36, ly)], fill=COL[k], width=6)
        d.text((x + 46, ly - 9), lab, INK, font=F_N)
    d.text((1120, ly - 26), "ESP32 D18 = GPIO18 on the devkit's own silkscreen",
           GPIOC, font=F_N)
    d.text((1120, ly - 4),
           "grey rows have a hole but no wire - that is deliberate", MUTED, font=F_N)

    img.save(OUT)
    print(f"wrote {OUT}  ({W}x{H})")


if __name__ == "__main__":
    main()
