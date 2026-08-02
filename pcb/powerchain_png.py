"""The power chain as a WIRING picture -- what is done, what is next.

board.png and wiring_diagram.png describe the finished PCB. This one is for
the bench: three modules on a base, three diodes inline in the wires, and
everything landing on the logic board's 5V and GND rails. Same nets as rev E
(see PINOUT.md), just built with heatshrink instead of copper.

Stages are colour-coded so the drawing tells you where you are:
    DONE    the mains half -- 12V through the buck and D1 onto the rail
    NOW     the charger and the cell
    LATER   the boost, D2, and the sense dividers

    python powerchain_png.py   ->  powerchain_wiring.png
"""

from PIL import Image, ImageDraw, ImageFont

OUT = "powerchain_wiring.png"
W, H = 2440, 1460

BG = (250, 250, 247)
INK = (20, 26, 24)
MUTED = (112, 124, 118)
FAINT = (172, 182, 176)
BOXF = (255, 255, 255)

DONE = (86, 140, 96)          # already built
NOW = (204, 92, 30)           # this is the step to do
LATER = (168, 178, 184)       # not yet
RAILC = (200, 60, 45)
GNDC = (90, 100, 96)
WARN = (170, 60, 40)

# boxes: ref -> (x0, y0, x1, y1, title, [pad lines], stage)
BOXES = {
    "PSU":  (70, 205, 250, 320, "12V PSU", ["+12V", "GND"], DONE),
    "FUSE": (300, 232, 420, 292, "FUSE 2A", [], DONE),
    "D3":   (470, 232, 590, 292, "D3", [], DONE),
    "BUCK": (640, 175, 900, 350, "LM2596 BUCK",
             ["IN+   IN-", "OUT+  OUT-", "set 5.4-5.5V"], DONE),
    "D1":   (1000, 232, 1120, 292, "D1", [], DONE),
    "TP":   (640, 600, 900, 790, "TP4056 CHARGER",
             ["IN+   IN-", "B+    B-", "OUT+  OUT-"], NOW),
    "BATT": (640, 880, 900, 1000, "18650 + HOLDER", ["in the holder,"
                                                     " never soldered"], NOW),
    "BOOST": (980, 600, 1210, 790, "MT3608 BOOST",
              ["VIN+  VIN-", "VOUT+ VOUT-", "set 5.0V"], LATER),
    "D2":   (1255, 682, 1360, 742, "D2", [], LATER),
    "RAIL": (1420, 175, 1590, 900, "LOGIC BOARD", [], RAILC),
}


def font(sz, bold=False):
    for nm in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf"):
        try:
            return ImageFont.truetype(nm, sz)
        except OSError:
            continue
    return ImageFont.load_default()


def arrow(d, pts, colr, w=6, head=17):
    """polyline with an arrowhead on the last segment"""
    d.line(pts, fill=colr, width=w, joint="curve")
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    if x1 == x0:
        s = 1 if y1 > y0 else -1
        d.polygon([(x1, y1), (x1 - head, y1 - s * head),
                   (x1 + head, y1 - s * head)], fill=colr)
    else:
        s = 1 if x1 > x0 else -1
        d.polygon([(x1, y1), (x1 - s * head, y1 - head),
                   (x1 - s * head, y1 + head)], fill=colr)


def diode(d, box, colr, f):
    """draw the diode body with its band, so the band side is unambiguous"""
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0, y0, x1, y1], 5, fill=(38, 44, 48), outline=colr,
                        width=3)
    d.rectangle([x1 - 20, y0 + 3, x1 - 6, y1 - 3], fill=(245, 245, 245))
    d.text(((x0 + x1) // 2 - 8, (y0 + y1) // 2), "1N5822", font=f,
           fill=(240, 244, 242), anchor="mm")


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_h1, f_h2 = font(42, True), font(26, True)
    f_b, f_s, f_xs = font(21), font(18), font(15)

    d.text((70, 55), "FreeISP power chain - bench build", font=f_h1, fill=INK)
    d.text((70, 112),
           "Three modules on a base, three diodes inline in the wires, "
           "everything landing on the logic board's rails.",
           font=f_s, fill=MUTED)

    # ---- boxes ----
    for ref, (x0, y0, x1, y1, title, lines, colr) in BOXES.items():
        if ref in ("D1", "D2", "D3"):
            diode(d, (x0, y0, x1, y1), colr, f_xs)
            d.text(((x0 + x1) // 2, y0 - 20), title, font=f_b, fill=colr,
                   anchor="mm")
            d.text((x1 - 12, y1 + 20), "band", font=f_xs, fill=colr,
                   anchor="mm")
            continue
        if ref == "RAIL":
            d.rounded_rectangle([x0, y0, x1, y1], 10, fill=BOXF,
                                outline=colr, width=4)
            d.text(((x0 + x1) // 2, y0 + 34), "LOGIC", font=f_b, fill=INK,
                   anchor="mm")
            d.text(((x0 + x1) // 2, y0 + 62), "BOARD", font=f_b, fill=INK,
                   anchor="mm")
            d.line([x0 + 46, y0 + 100, x0 + 46, y1 - 40], fill=RAILC, width=12)
            d.line([x0 + 120, y0 + 100, x0 + 120, y1 - 40], fill=GNDC, width=12)
            d.text((x0 + 46, y1 - 18), "5V", font=f_s, fill=RAILC, anchor="mm")
            d.text((x0 + 120, y1 - 18), "GND", font=f_s, fill=GNDC, anchor="mm")
            continue
        d.rounded_rectangle([x0, y0, x1, y1], 10, fill=BOXF, outline=colr,
                            width=4)
        d.text((x0 + 16, y0 + 14), title, font=f_b, fill=INK)
        yy = y0 + 48
        for ln in lines:
            d.text((x0 + 16, yy), ln, font=f_xs, fill=MUTED)
            yy += 24

    # ---- DONE: the mains path ----
    arrow(d, [(250, 262), (300, 262)], DONE)
    arrow(d, [(420, 262), (470, 262)], DONE)
    arrow(d, [(590, 262), (640, 262)], DONE)
    arrow(d, [(900, 262), (1000, 262)], DONE)
    arrow(d, [(1120, 262), (1420, 262)], DONE)
    d.text((905, 232), "OUT+ 5.4V", font=f_xs, fill=DONE)
    d.text((1160, 232), "5.02V on the rail", font=f_xs, fill=DONE)
    d.text((250, 300), "+12V", font=f_xs, fill=DONE)

    # Ground return, drawn once so it is obviously ONE net. Routed out to the
    # left bus rather than straight down, or it would cut through the boxes.
    d.line([(160, 320), (160, 1120), (1540, 1120), (1540, 900)],
           fill=GNDC, width=6)
    for y in (330, 770, 975):                       # buck, charger, cell
        d.line([(640 if y > 400 else 640, y), (160, y)], fill=GNDC, width=4)
    d.line([(1095, 790), (1095, 1120)], fill=GNDC, width=4)   # boost
    d.text((300, 1142), "GND is ONE net - PSU -, buck IN-/OUT-, "
                        "charger, boost and the board all share it",
           font=f_s, fill=GNDC)

    # ---- the junction: buck OUT+ feeds TWO things ----
    jx, jy = 950, 262
    d.ellipse([jx - 13, jy - 13, jx + 13, jy + 13], fill=NOW)
    arrow(d, [(jx, jy + 13), (jx, 520), (770, 520), (770, 600)], NOW, 8)
    d.text((990, 470), "THE SPLIT: buck OUT+ goes to BOTH", font=f_b, fill=NOW)
    d.text((990, 500), "D1 (done) and the charger's IN+ (now).", font=f_s,
           fill=NOW)
    d.text((990, 528), "NOT from the 5V rail - see step 1.", font=f_s, fill=NOW)

    # ---- NOW: battery ----
    arrow(d, [(770, 790), (770, 880)], NOW, 8)
    d.text((790, 820), "B+ / B-", font=f_s, fill=NOW)
    d.text((790, 846), "battery ONLY", font=f_xs, fill=WARN)

    # ---- LATER: boost + D2 ----
    arrow(d, [(900, 700), (980, 700)], LATER)
    d.text((940, 668), "VBAT", font=f_xs, fill=LATER, anchor="mm")
    arrow(d, [(1210, 712), (1255, 712)], LATER)
    arrow(d, [(1360, 712), (1420, 712)], LATER)
    d.text((1230, 762), "4.65V", font=f_xs, fill=LATER)

    # C1
    d.text((1290, 300), "C1 470uF across", font=f_xs, fill=MUTED)
    d.text((1290, 322), "5V <-> GND, stripe", font=f_xs, fill=MUTED)
    d.text((1290, 344), "leg to GND", font=f_xs, fill=MUTED)

    # sense dividers
    d.text((470, 330), "R5/R6 taps here", font=f_xs, fill=LATER)
    d.text((470, 352), "-> GPIO34", font=f_xs, fill=LATER)
    d.text((905, 830), "R3/R4 taps VBAT", font=f_xs, fill=LATER)
    d.text((905, 852), "-> GPIO35", font=f_xs, fill=LATER)

    # ---- legend ----
    lx, ly = 70, 1200
    for colr, lab in ((DONE, "DONE - proven, rail reads 5.02V"),
                      (NOW, "DO THIS NOW"),
                      (LATER, "LATER - after the charger works")):
        d.rounded_rectangle([lx, ly, lx + 46, ly + 26], 5, fill=colr)
        d.text((lx + 62, ly + 13), lab, font=f_s, fill=INK, anchor="lm")
        ly += 40

    # ---- right panel ----
    px = 1680
    d.text((px, 175), "THE CHARGER, STEP BY STEP", font=f_h2, fill=NOW)
    steps = [
        ("0", "Check which module you have.", INK,
         "Protected = 6 pads (IN+ IN- B+ B- OUT+ OUT-)\n"
         "and TWO 8-pin chips by the battery pads.\n"
         "Only 4 pads = unprotected, stop and ask."),
        ("1", "IN+ to the BUCK's OUT+.", WARN,
         "The same terminal D1's plain end is on -- NOT\n"
         "the 5V rail. From the rail the battery charges\n"
         "itself through its own boost and never ends."),
        ("2", "IN- to GND.", INK, "Same ground as everything else."),
        ("3", "Meter the cell BEFORE it touches the module.", WARN,
         "3.0-4.2V = healthy. Under 2.5V = deeply flat.\n"
         "0V = dead or tripped, do not use it.\n"
         "Flat end is negative, nub is positive."),
        ("4", "Cell to B+ / B-, in its holder.", WARN,
         "Only the battery goes there, ever. A load on\n"
         "B+/B- bypasses the protection and ruins the cell.\n"
         "Never solder straight to an 18650."),
        ("5", "Leave OUT+ / OUT- alone.", INK,
         "That is the boost's feed, the stage after this."),
        ("6", "Power up. Red LED = charging.", INK,
         "Warm module is normal at 1A. Hot is not --\n"
         "pull the power and check the wiring.\n"
         "Do not leave the first charge unattended."),
    ]
    y = 232
    for n, head, colr, body in steps:
        d.ellipse([px, y, px + 30, y + 30], fill=colr)
        d.text((px + 15, y + 15), n, font=f_s, fill=(255, 255, 255),
               anchor="mm")
        d.text((px + 44, y + 15), head, font=f_b, fill=colr, anchor="lm")
        y += 38
        for ln in body.split("\n"):
            d.text((px + 44, y), ln, font=f_xs, fill=MUTED)
            y += 21
        y += 16

    d.line([px, H - 96, W - 60, H - 96], fill=FAINT, width=2)
    d.text((px, H - 78), "then: boost to 5.0V, D2 band toward the rail,",
           font=f_xs, fill=FAINT)
    d.text((px, H - 56), "and pull the 12V -- it should not even blink.",
           font=f_xs, fill=FAINT)
    d.text((70, H - 40), "pcb/powerchain_png.py   nets from PINOUT.md rev E",
           font=f_xs, fill=FAINT)

    img.save(OUT)
    print(f"wrote {OUT}  ({W}x{H})")


if __name__ == "__main__":
    main()
