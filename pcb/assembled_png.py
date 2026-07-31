"""Draw what the finished board looks like once everything is fitted.

Part positions and body outlines come from freeisp_brain.kicad_pcb, so this
is the real layout, not an impression. The three wire-in modules (buck,
charger, boost) are drawn beside the board at their true sizes with wires to
their terminals, because that is how the assembly actually sits.

    python assembled_png.py   ->  assembled.png
"""

import math
from PIL import Image, ImageDraw, ImageFont
import sexp

BOARD = "freeisp_brain.kicad_pcb"
OUT = "assembled.png"
W, H = 1760, 1420

PPMM = 8.0
BX, BY = 640, 250          # board top-left on canvas
OX, OY = 60.0, 40.0        # board origin in page coords

BG = (246, 246, 243)
INK = (22, 28, 26)
MUTED = (118, 128, 122)
PCB = (22, 92, 70)
PCB_ED = (12, 58, 44)
GOLD = (206, 168, 78)
TERM = (86, 176, 118)
BLACK = (34, 38, 42)
SILVER = (176, 182, 188)


def font(sz, bold=False):
    for nm in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf"):
        try:
            return ImageFont.truetype(nm, sz)
        except OSError:
            continue
    return ImageFont.load_default()


F_T, F_B, F_N, F_S = font(38, True), font(19, True), font(15, True), font(13)


def px(x):
    return BX + (x - OX) * PPMM


def py(y):
    return BY + (y - OY) * PPMM


def load():
    pcb = sexp.parse(open(BOARD, encoding="utf-8").read())
    out = {}
    for fp in sexp.find_all(pcb, "footprint"):
        ref = "?"
        for p in sexp.find_all(fp, "property"):
            if sexp.unq(p[1]) == "Reference":
                ref = sexp.unq(p[2])
        at = sexp.find(fp, "at")
        fx, fy = float(at[1]), float(at[2])
        rot = math.radians(float(at[3]) if len(at) > 3 else 0)
        c, s = math.cos(rot), math.sin(rot)

        pads, silk = [], []
        for pad in sexp.find_all(fp, "pad"):
            a = sexp.find(pad, "at")
            lx, ly = float(a[1]), float(a[2])
            pads.append((fx + lx * c + ly * s, fy - lx * s + ly * c))

        def walk(node):
            for ch in node:
                if isinstance(ch, list):
                    if ch and ch[0] in ("fp_line", "fp_rect", "fp_poly", "fp_arc"):
                        lay = sexp.find(ch, "layer")
                        if lay and "SilkS" in sexp.unq(lay[1]):
                            for k in ("start", "end", "mid"):
                                q = sexp.find(ch, k)
                                if q:
                                    lx, ly = float(q[1]), float(q[2])
                                    silk.append((fx + lx * c + ly * s,
                                                 fy - lx * s + ly * c))
                    walk(ch)
        walk(fp)
        out[ref] = {"pads": pads, "silk": silk}
    return out


def body(d, pts, fill, outline=None, pad=0.0, r=3):
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    box = [px(min(xs) - pad), py(min(ys) - pad), px(max(xs) + pad), py(max(ys) + pad)]
    d.rounded_rectangle(box, r, fill=fill, outline=outline or fill, width=2)
    return box


def main():
    fp = load()
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((56, 34), "FreeISP brain board  -  what it looks like built", INK, font=F_T)
    d.text((58, 84), "positions taken from freeisp_brain.kicad_pcb. The ESP32 stands "
           "on sockets and covers the middle; everything else lives round the edge.",
           MUTED, font=F_S)

    # ---------------- bare board ----------------
    d.rounded_rectangle([BX, BY, BX + 115 * PPMM, BY + 115 * PPMM], 8,
                        fill=PCB, outline=PCB_ED, width=3)
    for mx, my in ((4.5, 4.5), (110.5, 4.5), (4.5, 110.5), (110.5, 110.5)):
        cx, cy = px(OX + mx), py(OY + my)
        d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=(210, 214, 210))
        d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=BG)

    # ---------------- parts, drawn as their real bodies ----------------
    TERMS = ("J1", "U1", "U2", "J13", "J7", "J8", "J9", "J11")
    HDRS = ("J4", "J5", "U4", "J10", "K1", "J14")
    for ref in TERMS:
        b = body(d, fp[ref]["silk"], TERM, (52, 132, 88), r=4)
        for x, y in fp[ref]["pads"]:                       # screw heads
            d.ellipse([px(x) - 9, py(y) - 9, px(x) + 9, py(y) + 9], fill=(40, 46, 44))
            d.line([(px(x) - 5, py(y)), (px(x) + 5, py(y))], fill=(150, 160, 155), width=3)
    for ref in HDRS:
        body(d, fp[ref]["pads"], BLACK, (16, 18, 20), pad=1.3, r=2)
        for x, y in fp[ref]["pads"]:
            d.rectangle([px(x) - 3, py(y) - 3, px(x) + 3, py(y) + 3], fill=GOLD)

    for ref in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"):
        p = fp[ref]["pads"]
        (x1, y1), (x2, y2) = p[0], p[1]
        d.line([(px(x1), py(y1)), (px(x2), py(y2))], fill=(150, 150, 145), width=3)
        d.rounded_rectangle([px(x1) + 12, py(y1) - 9, px(x2) - 12, py(y2) + 9], 5,
                            fill=(226, 208, 168), outline=(150, 132, 96), width=2)
    for ref in ("D1", "D2", "D3"):
        p = fp[ref]["pads"]
        (x1, y1), (x2, y2) = p[0], p[1]
        d.line([(px(x1), py(y1)), (px(x2), py(y2))], fill=(150, 150, 145), width=3)
        vert = abs(y2 - y1) > abs(x2 - x1)
        if vert:
            box = [px(x1) - 13, py(y1) + 14, px(x1) + 13, py(y2) - 14]
        else:
            box = [px(x1) + 14, py(y1) - 13, px(x2) - 14, py(y1) + 13]
        d.rounded_rectangle(box, 3, fill=(38, 38, 40))
        if vert:            # cathode band at the pad-1 end
            d.rectangle([box[0], box[1] + 5, box[2], box[1] + 13], fill=(238, 238, 235))
        else:
            d.rectangle([box[0] + 5, box[1], box[0] + 13, box[3]], fill=(238, 238, 235))
    for ref, col in (("C2", (214, 126, 58)), ("C3", (214, 126, 58))):
        p = fp[ref]["pads"]
        cx = (px(p[0][0]) + px(p[1][0])) / 2
        cy = (py(p[0][1]) + py(p[1][1])) / 2
        d.ellipse([cx - 17, cy - 21, cx + 17, cy + 21], fill=col, outline=(150, 88, 40), width=2)
    p = fp["C1"]["pads"]
    cx = (px(p[0][0]) + px(p[1][0])) / 2
    cy = (py(p[0][1]) + py(p[1][1])) / 2
    d.ellipse([cx - 32, cy - 32, cx + 32, cy + 32], fill=(46, 96, 178), outline=(24, 56, 118), width=3)
    d.pieslice([cx - 32, cy - 32, cx + 32, cy + 32], 100, 260, fill=(206, 214, 224))
    d.text((cx - 26, cy - 9), "470u", (240, 244, 250), font=F_S)

    # ---------------- the ESP32, standing on its sockets ----------------
    a = fp["U3A"]["pads"]
    b = fp["U3B"]["pads"]
    x0, x1 = a[0][0] - 1.5, b[0][0] + 1.5
    y0, y1 = a[0][1] - 5.5, a[-1][1] + 10.0
    ex0, ey0, ex1, ey1 = px(x0), py(y0), px(x1), py(y1)
    d.rectangle([ex0 + 10, ey0 + 12, ex1 + 14, ey1 + 14], fill=(0, 0, 0, 40))
    d.rounded_rectangle([ex0, ey0, ex1, ey1], 6, fill=(26, 30, 34), outline=(10, 12, 14), width=3)
    for yy in (a[0][1], a[-1][1]):
        pass
    for pad in a + b:                                   # its own pin strips
        d.rectangle([px(pad[0]) - 4, py(pad[1]) - 4, px(pad[0]) + 4, py(pad[1]) + 4],
                    fill=(190, 160, 90))
    mw = (ex1 - ex0) * 0.62
    d.rounded_rectangle([ex0 + (ex1 - ex0 - mw) / 2, ey0 + 26,
                         ex0 + (ex1 - ex0 + mw) / 2, ey0 + 150], 4,
                        fill=SILVER, outline=(120, 128, 134), width=2)
    d.text((ex0 + (ex1 - ex0) / 2 - 42, ey0 + 76), "WROOM-32", (70, 76, 82), font=F_S)
    d.rounded_rectangle([ex0 + (ex1 - ex0) / 2 - 34, ey1 - 26,
                         ex0 + (ex1 - ex0) / 2 + 34, ey1 - 2], 4, fill=SILVER)
    d.text((ex0 + 16, ey1 - 62), "USB", (200, 206, 210), font=F_S)
    d.text((ex0 + 10, ey0 - 30), "ESP32 DevKitC  (plugs into the sockets)",
           INK, font=F_N)

    # ---------------- the three wire-in modules ----------------
    MODS = [
        ("LM2596 BUCK", 43, 21, 70, 300, "U1", (58, 96, 170)),
        ("TP4056 CHARGER", 26, 17, 70, 560, "U2", (58, 96, 170)),
        ("MT3608 BOOST", 36, 17, 70, 780, "J13", (58, 96, 170)),
    ]
    for name, mw_, mh_, mx, my, term, col in MODS:
        w_, h_ = mw_ * PPMM, mh_ * PPMM
        d.rectangle([mx + 8, my + 8, mx + w_ + 8, my + h_ + 8], fill=(226, 226, 222))
        d.rounded_rectangle([mx, my, mx + w_, my + h_], 5, fill=col, outline=(30, 56, 110), width=3)
        d.text((mx + 10, my + 8), name, (236, 240, 246), font=F_N)
        d.text((mx + 10, my + h_ - 26), f"{mw_} x {mh_} mm", (196, 212, 236), font=F_S)
        d.ellipse([mx + w_ - 40, my + h_ / 2 - 14, mx + w_ - 12, my + h_ / 2 + 14],
                  fill=(230, 226, 210), outline=(120, 116, 100), width=2)
        d.line([(mx + w_ - 32, my + h_ / 2), (mx + w_ - 20, my + h_ / 2)],
               fill=(90, 88, 80), width=3)
        # wires to its terminal
        pads = fp[term]["pads"]
        for i, (tx, ty) in enumerate(pads):
            sy = my + 20 + i * (h_ - 40) / max(1, len(pads) - 1)
            d.line([(mx + w_, sy), (mx + w_ + 40, sy),
                    (px(tx), py(ty) - 46), (px(tx), py(ty))],
                   fill=(190, 80, 60) if i == 0 else (110, 116, 120), width=3)

    d.text((70, 250), "wired alongside - NOT on the board", INK, font=F_B)
    d.text((70, 1010), "trimpots must stay reachable:", INK, font=F_N)
    d.text((70, 1036), "set the buck to 5.4 V and the boost to 5.0 V", MUTED, font=F_S)
    d.text((70, 1062), "BEFORE either is wired in.", MUTED, font=F_S)

    d.text((BX, BY + 115 * PPMM + 26),
           "The middle is deliberately empty - that is the ESP32's body keep-out. "
           "Only flat parts could ever go there, and none do.", MUTED, font=F_S)
    d.text((BX, BY + 115 * PPMM + 52),
           "30 parts solder to the board. Everything else plugs in or screws down.",
           INK, font=F_N)

    img.save(OUT)
    print(f"wrote {OUT} ({W}x{H})")


if __name__ == "__main__":
    main()
