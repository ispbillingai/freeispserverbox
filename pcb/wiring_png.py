"""Draw the external wiring diagram: what plugs in, and which ESP32 pin it reaches.

Reads freeisp_brain.kicad_pcb -- the same file that goes to the fab -- so every
pin name, net and GPIO shown here comes from what is actually manufactured.

Each row reads left to right:
    pin no. | name PRINTED ON THE MODULE | net on the board | ESP32 pin it lands on

    python wiring_png.py   ->  wiring_diagram.png
"""

from PIL import Image, ImageDraw, ImageFont
import sexp

BOARD = "freeisp_brain.kicad_pcb"
OUT = "wiring_diagram.png"
W, H = 2600, 1620

BG = (250, 250, 247)
INK = (20, 26, 24)
MUTED = (112, 124, 118)
FAINT = (168, 178, 172)
BOARDC = (24, 96, 74)
BOARD_ED = (14, 60, 46)
PAD = (201, 162, 60)
GPIOC = (150, 60, 30)

COL = {
    "pwr":   (200, 60, 45),
    "batt":  (215, 140, 30),
    "sig":   (60, 130, 75),
    "alarm": (170, 60, 150),
}

# The devkit's own printed pin names, top to bottom, antenna up.
DEVKIT = {
    "U3A": ["3V3", "EN", "VP", "VN", "D34", "D35", "D32", "D33", "D25", "D26",
            "D27", "D14", "D12", "GND", "D13", "SD2", "SD3", "CMD", "5V"],
    "U3B": ["GND", "D23", "D22", "TX0", "RX0", "D21", "GND", "D19", "D18",
            "D5", "D17", "D16", "D4", "D0", "D2", "D15", "SD1", "SD0", "CLK"],
}

# Nets that never touch a GPIO -- say what they are instead of leaving a blank.
INDIRECT = {
    "LED_R_A": "via R1 220R from D25",
    "LED_G_A": "via R2 220R from D26",
    "REED_F":  "via R8 1k to D32",
    "HORN_DRV": "via R7 1k from D13",
    "+12V_IN": "into D3 guard diode",
    "+12V":    "buck in + R5/R6 sense",
    "+5V":     "buck out into D1",
    "+5V_BAT": "boost out into D2",
    "VBAT":    "battery + R3/R4 sense",
}


def font(sz, bold=False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, sz)
        except OSError:
            continue
    return ImageFont.load_default()


F_T, F_S = font(42, True), font(20)
F_B, F_P = font(22, True), font(19)
F_N, F_TINY = font(16), font(14)
F_PIN = font(15, True)


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

    # net -> the devkit pin(s) it lands on
    esp = {}
    for ref in ("U3A", "U3B"):
        for i, (_num, net) in enumerate(pads.get(ref, [])):
            if net:
                esp.setdefault(net, []).append(DEVKIT[ref][i])
    return pads, esp


EXT = [
    ("J1", "12 V PSU", "mains adaptor", ["+12V", "GND"], "L", 120, "pwr",
     "fuse inline in the + wire"),
    ("U1", "LM2596 BUCK", "step-down", ["IN+", "IN-", "OUT+", "OUT-"],
     "L", 265, "pwr", "SET TO 5.4 V BEFORE WIRING"),
    ("U2", "TP4056 CHARGER", "protected", ["IN+", "IN-", "OUT+", "OUT-"],
     "L", 460, "batt", "18650 goes on the MODULE's B+/B-"),
    ("J13", "5 V BOOST", "step-up, >=2 A", ["IN+", "IN-", "OUT+", "OUT-"],
     "L", 655, "batt", "SET TO 5.0 V"),
    ("J7", "REED SWITCH", "lid sensor", ["REED", "GND"], "L", 850, "sig",
     "either way round"),
    ("J8", "RED LED", "alarm", ["GND", "LED+"], "L", 995, "sig",
     "220R already on the board"),
    ("J9", "GREEN LED", "secure", ["GND", "LED+"], "L", 1140, "sig",
     "220R already on the board"),

    ("J4", "1.8in TFT ST7735S", "display, 5 V",
     ["GND", "VDD", "SCL", "SDA", "RST", "DC", "CS", "BLK"], "R", 120, "sig",
     "match the module's own printed order"),
    ("J5", "RC522 READER", "RFID, 3.3 V ONLY",
     ["SDA", "SCK", "MOSI", "MISO", "IRQ", "GND", "RST", "3.3V"], "R", 420,
     "sig", "shares SCK+MOSI with the TFT"),
    ("U4", "GY-521 MPU-6050", "motion",
     ["VCC", "GND", "SCL", "SDA", "XDA", "XCL", "AD0", "INT"], "R", 720, "sig",
     "last four have holes, no wires"),
    ("J10", "BUZZER", "passive", ["5V", "GND", "SIG"], "R", 1020, "alarm", ""),
    ("K1", "RELAY MODULE", "switches the horn", ["IN", "GND", "VCC"],
     "R", 1165, "alarm", "match IN/GND/VCC BY NAME"),
    ("J11", "HORN 3-5 V", "through the relay", ["+5V", "HORN-"], "R", 1330,
     "alarm", "+5V->COM,  NO->horn+,  horn- ->HORN-"),
]

BX0, BY0, BX1, BY1 = 900, 150, 1700, 1450
BWID = 560


def main():
    pads, esp = board_data()
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((60, 32), "FreeISP brain board  -  external wiring", INK, font=F_T)
    d.text((62, 88),
           "Read each row:   pin no.  |  name printed ON THE MODULE  |  net on the board  |  "
           "the ESP32 pin it reaches", MUTED, font=F_S)
    d.text((62, 116),
           "J4 / U4 / R1 are the BOARD's labels for each socket.  D18 / D23 / GND are the "
           "ESP32's own pin names.  Rev H, 115 x 115 mm.", FAINT, font=F_N)

    # ---------------- the board ----------------
    d.rounded_rectangle([BX0, BY0, BX1, BY1], 14, fill=BOARDC, outline=BOARD_ED, width=3)
    for cx, cy in ((BX0 + 34, BY0 + 34), (BX1 - 34, BY0 + 34),
                   (BX0 + 34, BY1 - 34), (BX1 - 34, BY1 - 34)):
        d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=PAD)
        d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=BOARD_ED)
    d.text((BX0 + 74, BY0 + 22), "FREEISP BRAIN  REV H", (228, 242, 234), font=F_B)

    # devkit with its real pin names
    kx0, kx1 = BX0 + 190, BX1 - 190
    ky0, ky1 = BY0 + 250, BY1 - 260
    d.rectangle([kx0, ky0, kx1, ky1], outline=(150, 200, 178), width=2)
    d.text(((kx0 + kx1) // 2 - 118, ky0 - 62), "ESP32 38-pin DevKitC",
           (228, 242, 234), font=F_B)
    d.text(((kx0 + kx1) // 2 - 88, ky0 - 34), "antenna at the top",
           (150, 200, 178), font=F_TINY)

    step = (ky1 - ky0 - 40) / 18
    for i in range(19):
        yy = ky0 + 20 + i * step
        for ref, xx, anchor in (("U3A", kx0 + 34, "l"), ("U3B", kx1 - 34, "r")):
            net = pads[ref][i][1] if i < len(pads[ref]) else ""
            lit = bool(net)
            d.ellipse([xx - 7, yy - 7, xx + 7, yy + 7],
                      fill=PAD if lit else (90, 130, 112))
            lab = DEVKIT[ref][i]
            c = (235, 245, 240) if lit else (120, 160, 140)
            if anchor == "l":
                d.text((xx + 14, yy - 9), lab, c, font=F_PIN)
            else:
                d.text((xx - 14 - d.textlength(lab, font=F_PIN), yy - 9), lab, c, font=F_PIN)
    d.text(((kx0 + kx1) // 2 - 96, ky1 + 12), "greyed pins = no wire",
           (150, 200, 178), font=F_TINY)

    d.text((BX0 + 34, BY1 - 150),
           "already on the board: D1 D2 D3 | C1 470u | C2 C3 100n | R1 R2 220R",
           (172, 216, 196), font=F_TINY)
    d.text((BX0 + 34, BY1 - 126),
           "R3-R6 sense dividers | R7 R8 1k   -   none of these need wires",
           (172, 216, 196), font=F_TINY)
    d.text((BX0 + 34, BY1 - 92),
           "12 V sensing is INTERNAL (R5/R6) - there is no terminal for it,",
           (255, 208, 165), font=F_TINY)
    d.text((BX0 + 34, BY1 - 68),
           "and mains must NEVER be wired to any pin.", (255, 208, 165), font=F_TINY)

    # ---------------- external blocks ----------------
    order = [e[0] for e in EXT]
    for ref, title, what, silk, side, y, ckey, note in EXT:
        c = COL[ckey]
        actual = pads.get(ref, [])
        bh = 40 + 26 * len(silk) + (26 if note else 0)
        bx = 60 if side == "L" else W - 60 - BWID

        d.rounded_rectangle([bx, y, bx + BWID, y + bh], 10,
                            fill=(255, 255, 255), outline=c, width=3)
        d.rectangle([bx, y, bx + 7, y + bh], fill=c)
        d.text((bx + 20, y + 8), title, INK, font=F_B)
        d.text((bx + 30 + d.textlength(title, font=F_B), y + 12), what, MUTED, font=F_P)
        d.text((bx + BWID - 54, y + 10), ref, c, font=F_B)

        for i, nm in enumerate(silk):
            py = y + 40 + i * 26
            net = actual[i][1] if i < len(actual) else ""
            if not net:
                d.text((bx + 26, py), f"{i + 1}", FAINT, font=F_N)
                d.text((bx + 52, py), nm, FAINT, font=F_P)
                d.text((bx + 168, py), "no wire  (hole only)", FAINT, font=F_N)
                continue
            d.text((bx + 26, py), f"{i + 1}", MUTED, font=F_N)
            d.text((bx + 52, py), nm, INK, font=F_P)
            d.text((bx + 148, py), net, MUTED, font=F_N)
            gp = esp.get(net)
            if gp:
                uniq = sorted(set(gp), key=gp.index)
                d.text((bx + 330, py), "ESP32 " + "/".join(uniq), GPIOC, font=F_PIN)
            else:
                d.text((bx + 330, py), INDIRECT.get(net, ""), MUTED, font=F_N)

        if note:
            d.text((bx + 26, y + 42 + 26 * len(silk)), note, c, font=F_N)

        ax = bx + BWID if side == "L" else bx
        ay = y + bh // 2
        tx = BX0 if side == "L" else BX1
        ty = BY0 + 70 + (BY1 - BY0 - 140) * (order.index(ref) / (len(EXT) - 1))
        midx = (ax + tx) // 2
        d.line([(ax, ay), (midx, ay), (midx, ty), (tx, ty)], fill=c, width=4)
        d.ellipse([tx - 7, ty - 7, tx + 7, ty + 7], fill=c)
        d.text((tx + 14 if side == "L" else tx - 52, ty - 11), ref,
               (238, 246, 242), font=F_B)

    # ---------------- legend ----------------
    ly = H - 66
    d.text((60, ly - 32), "line colour = what that wire carries", MUTED, font=F_N)
    for i, (k, lab) in enumerate([("pwr", "12 V input side"),
                                  ("batt", "battery / charging"),
                                  ("sig", "logic signals"),
                                  ("alarm", "alarm devices")]):
        x = 60 + i * 270
        d.line([(x, ly), (x + 40, ly)], fill=COL[k], width=6)
        d.text((x + 52, ly - 10), lab, INK, font=F_N)
    d.text((1300, ly - 10), "ESP32 D18 = GPIO18 on the devkit's own silkscreen",
           GPIOC, font=F_N)
    d.text((1300, ly - 32), "generated from freeisp_brain.kicad_pcb - the file the fab receives",
           MUTED, font=F_N)

    img.save(OUT)
    print(f"wrote {OUT}  ({W}x{H})")


if __name__ == "__main__":
    main()
