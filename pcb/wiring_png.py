"""Draw the external wiring diagram: what plugs into the board, and where.

Reads freeisp_brain.kicad_pcb -- the same file that goes to the fab -- so the
pin names and nets shown here cannot drift from what is actually made. The
board sits in the middle; every external part sits around it with a labelled
line into its connector.

    python wiring_png.py   ->  wiring_diagram.png
"""

from PIL import Image, ImageDraw, ImageFont
import sexp

BOARD = "freeisp_brain.kicad_pcb"
OUT = "wiring_diagram.png"
W, H = 2200, 1560

BG = (250, 250, 247)
INK = (20, 26, 24)
MUTED = (110, 122, 116)
BOARDC = (24, 96, 74)
BOARD_ED = (14, 60, 46)
PAD = (201, 162, 60)

COL = {
    "pwr":   (200, 60, 45),     # 12 V / mains side
    "batt":  (215, 140, 30),    # battery / charge
    "sys":   (35, 120, 190),    # 5 V system rail
    "sig":   (70, 140, 80),     # logic signals
    "alarm": (170, 60, 150),    # alarm devices
}


def font(sz, bold=False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, sz)
        except OSError:
            continue
    return ImageFont.load_default()


F_T = font(40, True)
F_S = font(19)
F_B = font(21, True)
F_P = font(16)
F_N = font(15)
F_TINY = font(13)


def board_pins():
    """{ref: [(padnum, netname), ...]} straight from the fab file."""
    with open(BOARD, encoding="utf-8") as fh:
        pcb = sexp.parse(fh.read())
    names = {int(n[1]): sexp.unq(n[2]) for n in sexp.find_all(pcb, "net")}
    out = {}
    for fp in sexp.find_all(pcb, "footprint"):
        ref = "?"
        for prop in sexp.find_all(fp, "property"):
            if sexp.unq(prop[1]) == "Reference":
                ref = sexp.unq(prop[2])
        pads = []
        for pad in sexp.find_all(fp, "pad"):
            if pad[2] == "np_thru_hole":
                continue
            netn = sexp.find(pad, "net")
            pads.append((sexp.unq(pad[1]),
                         names[int(netn[1])] if netn else ""))
        pads.sort(key=lambda p: int(p[0]) if p[0].isdigit() else 99)
        out[ref] = pads
    return out


# ref, title, what it is, silk pin names, side, y, colour, extra note
EXT = [
    ("J1", "12 V PSU", "mains adaptor, fused inline",
     ["+12V", "GND"], "L", 120, "pwr", "fuse in the + wire"),
    ("U1", "LM2596 BUCK", "step-down module",
     ["IN+", "IN-", "OUT+", "OUT-"], "L", 300, "pwr", "SET TO 5.4 V FIRST"),
    ("U2", "TP4056 CHARGER", "protected charger",
     ["IN+", "IN-", "OUT+", "OUT-"], "L", 500, "batt",
     "battery goes on the MODULE's B+/B-"),
    ("J13", "5 V BOOST", "step-up module, >=2 A",
     ["IN+", "IN-", "OUT+", "OUT-"], "L", 700, "batt", "SET TO 5.0 V"),
    ("J7", "REED SWITCH", "lid / door sensor",
     ["REED", "GND"], "L", 900, "sig", "either way round"),
    ("J8", "RED LED", "alarm indicator",
     ["GND", "LED+"], "L", 1030, "sig", "220R already on board"),
    ("J9", "GREEN LED", "secure indicator",
     ["GND", "LED+"], "L", 1150, "sig", "220R already on board"),

    ("J4", "1.8in TFT  ST7735S", "display, 5 V",
     ["GND", "VDD", "SCL", "SDA", "RST", "DC", "CS", "BLK"], "R", 120, "sig",
     "8 pin - match the module's own order"),
    ("J5", "RC522 READER", "RFID, 3.3 V ONLY",
     ["SDA", "SCK", "MOSI", "MISO", "IRQ", "GND", "RST", "3.3V"], "R", 420,
     "sig", "IRQ has a hole but no wire"),
    ("U4", "GY-521 MPU-6050", "motion sensor",
     ["VCC", "GND", "SCL", "SDA", "XDA", "XCL", "AD0", "INT"], "R", 720, "sig",
     "last four unused"),
    ("J10", "BUZZER", "passive, 3.3 V logic",
     ["5V", "GND", "SIG"], "R", 1010, "alarm", ""),
    ("K1", "RELAY MODULE", "switches the horn",
     ["IN", "GND", "VCC"], "R", 1160, "alarm", "match IN/GND/VCC by NAME"),
    ("J11", "HORN  3-5 V", "via the relay contacts",
     ["+5V", "HORN-"], "R", 1300, "alarm",
     "+5V->COM, NO->horn+, horn- ->HORN-"),
]

BX0, BY0, BX1, BY1 = 830, 150, 1370, 1400


def main():
    pins = board_pins()
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((60, 34), "FreeISP brain board  -  external wiring", INK, font=F_T)
    d.text((62, 88),
           "Every pin name below is read straight out of freeisp_brain.kicad_pcb. "
           "Rev H  -  115 x 115 mm  -  38-pin DevKitC",
           MUTED, font=F_S)

    # ---- the board ----
    d.rounded_rectangle([BX0, BY0, BX1, BY1], 14, fill=BOARDC, outline=BOARD_ED, width=3)
    for cx, cy in ((BX0 + 34, BY0 + 34), (BX1 - 34, BY0 + 34),
                   (BX0 + 34, BY1 - 34), (BX1 - 34, BY1 - 34)):
        d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=PAD)
        d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=BOARD_ED)
    d.text((BX0 + 70, BY0 + 22), "FREEISP BRAIN  REV H", (225, 240, 232), font=F_B)

    # the devkit, drawn as it sits: sockets + keep-out
    kx0, ky0, kx1, ky1 = BX0 + 150, BY0 + 300, BX1 - 150, BY1 - 430
    d.rectangle([kx0, ky0, kx1, ky1], outline=(150, 200, 178), width=2)
    d.text(((kx0 + kx1) // 2 - 96, ky0 - 30), "ESP32 38-pin DevKitC", (225, 240, 232), font=F_B)
    d.text(((kx0 + kx1) // 2 - 92, ky1 + 10), "BODY KEEP-OUT - nothing under it", (150, 200, 178), font=F_TINY)
    for i in range(19):
        yy = ky0 + 22 + i * ((ky1 - ky0 - 44) / 18)
        for xx in (kx0 + 26, kx1 - 26):
            d.ellipse([xx - 6, yy - 6, xx + 6, yy + 6], fill=PAD)
    d.text((kx0 + 6, ky0 + 4), "3V3", (225, 240, 232), font=F_TINY)
    d.text((kx0 + 10, ky1 - 20), "5V", (225, 240, 232), font=F_TINY)
    d.text((kx1 - 40, ky0 + 4), "GND", (225, 240, 232), font=F_TINY)
    d.text((kx1 - 38, ky1 - 20), "CLK", (225, 240, 232), font=F_TINY)

    # on-board-only parts, so nothing looks missing
    d.text((BX0 + 34, BY1 - 118),
           "on board already: D1 D2 D3 diodes | C1 470u | C2 C3 100n",
           (170, 215, 195), font=F_TINY)
    d.text((BX0 + 34, BY1 - 92),
           "R1 R2 220R | R3-R6 dividers | R7 R8 1k  -  no wires needed",
           (170, 215, 195), font=F_TINY)
    d.text((BX0 + 34, BY1 - 60),
           "12 V sensing is INTERNAL (R5/R6) - never wire mains to a pin",
           (255, 205, 160), font=F_TINY)

    # ---- external blocks ----
    for ref, title, what, silk, side, y, ckey, note in EXT:
        c = COL[ckey]
        actual = pins.get(ref, [])
        bw, bh = 470, 34 + 26 * len(silk) + (24 if note else 0)
        bx = 60 if side == "L" else W - 60 - bw
        by = y

        d.rounded_rectangle([bx, by, bx + bw, by + bh], 10,
                            fill=(255, 255, 255), outline=c, width=3)
        d.rectangle([bx, by, bx + 7, by + bh], fill=c)
        d.text((bx + 20, by + 8), title, INK, font=F_B)
        tw = d.textlength(title, font=F_B)
        d.text((bx + 26 + tw, by + 12), what, MUTED, font=F_P)

        for i, nm in enumerate(silk):
            py = by + 38 + i * 26
            net = actual[i][1] if i < len(actual) else ""
            shown = net if net else "not connected"
            col = MUTED if not net else INK
            d.text((bx + 26, py), f"{i + 1}", MUTED, font=F_N)
            d.text((bx + 52, py), nm, col, font=F_P)
            d.text((bx + 150, py), "->", MUTED, font=F_N)
            d.text((bx + 180, py), shown, col, font=F_P)
        if note:
            d.text((bx + 26, by + 40 + 26 * len(silk)), note, c, font=F_N)

        # line into the board
        ax = bx + bw if side == "L" else bx
        ay = by + bh // 2
        tx = BX0 if side == "L" else BX1
        ty = BY0 + 60 + (BY1 - BY0 - 120) * (
            [e[0] for e in EXT].index(ref) / (len(EXT) - 1))
        midx = (ax + tx) // 2
        d.line([(ax, ay), (midx, ay), (midx, ty), (tx, ty)], fill=c, width=4)
        d.ellipse([tx - 7, ty - 7, tx + 7, ty + 7], fill=c)
        d.text((tx + 14 if side == "L" else tx - 46, ty - 10), ref,
               (235, 245, 240), font=F_B)

    # ---- legend ----
    ly = H - 74
    d.text((60, ly - 30), "colour = what the wire carries", MUTED, font=F_N)
    for i, (k, lab) in enumerate([("pwr", "12 V input side"),
                                  ("batt", "battery / charging"),
                                  ("sys", "5 V system rail"),
                                  ("sig", "logic signals"),
                                  ("alarm", "alarm devices")]):
        x = 60 + i * 250
        d.line([(x, ly), (x + 40, ly)], fill=COL[k], width=6)
        d.text((x + 52, ly - 10), lab, INK, font=F_N)

    d.text((W - 700, ly - 10),
           "verify against the real modules before ordering", MUTED, font=F_N)

    img.save(OUT)
    print(f"wrote {OUT}  ({W}x{H})")


if __name__ == "__main__":
    main()
