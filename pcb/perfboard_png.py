"""The perfboard TEST RIG -- where every part goes on the 7x9cm board.

This is NOT the PCB. It is the throwaway rig for proving the parts work
together before the real boards land, so it is drawn for "easy to fix",
not for looks: rails as bare wire, big modules on Dupont leads off the
board, everything on sockets so it all comes back out again.

Pin destinations are the SAME as rev E (see PINOUT.md) on purpose --
firmware proven on this rig then runs on the real board unchanged.

    python perfboard_png.py   ->  perfboard_layout.png
"""

from PIL import Image, ImageDraw, ImageFont

OUT = "perfboard_layout.png"
W, H = 2340, 1400

# The board Francis has: 7x9cm, holes lettered A..Y across and 1..35 down,
# exactly as printed on its own silkscreen. Count yours before you solder.
COLS, ROWS = 25, 35
PITCH = 30
BX, BY = 120, 170

BG = (250, 250, 247)
INK = (20, 26, 24)
MUTED = (112, 124, 118)
FAINT = (172, 182, 176)
BOARD = (206, 170, 120)      # phenolic brown
BOARD_ED = (150, 116, 74)
PADC = (214, 176, 74)
CHIP = (30, 42, 50)
CHIP_ED = (14, 22, 28)

GNDC = (90, 100, 96)
V5C = (200, 60, 45)
V33C = (215, 140, 30)
BLOCKC = (48, 122, 66)
WARN = (170, 60, 40)

# rails: which column each one runs down, and its colour
RAILS = [("L", GNDC, "GND"), ("J", V5C, "5V"), ("H", V33C, "3V3")]

# ESP32 38-pin DevKitC: rows 25.4mm apart = exactly 10 holes.
ESP_L, ESP_R = "N", "X"
ESP_TOP, ESP_BOT = 16, 34            # 19 hole rows

LEFT_ROW = ["3V3", "EN", "VP", "VN", "D34", "D35", "D32", "D33", "D25", "D26",
            "D27", "D14", "D12", "GND", "D13", "SD2", "SD3", "CMD", "5V"]
RIGHT_ROW = ["GND", "D23", "D22", "TX0", "RX0", "D21", "GND", "D19", "D18",
             "D5", "D17", "D16", "D4", "D0", "D2", "D15", "SD1", "SD0", "CLK"]
FLASH = {"SD0", "SD1", "SD2", "SD3", "CMD", "CLK"}
USED = {"D34", "D35", "D32", "D33", "D25", "D26", "D27", "D13",
        "D23", "D22", "D21", "D19", "D18", "D5", "D17", "D16", "D4", "D2",
        "3V3", "5V", "GND"}

# breakout blocks in the free area: (n, label, col, row_top, row_bot)
BLOCKS = [
    (1, "TFT",   "B", 3, 10),
    (2, "RC522", "E", 3, 10),
    (3, "MPU",   "B", 14, 17),
    (4, "LEDS",  "E", 14, 16),
    (5, "BUZZ",  "B", 21, 23),
    (6, "REED",  "E", 21, 22),
    (7, "RELAY", "B", 27, 29),
]

# the wire list, keyed to the numbered blocks
WIRES = [
    (1, "TFT  1.8in ST7735", "8-way, module order", [
        ("GND", "GND rail", 0), ("VDD", "5V rail", 0),
        ("SCL", "D18", 1), ("SDA", "D23", 1), ("RST", "D4", 0),
        ("DC", "D2", 0), ("CS", "D5", 0), ("BLK", "D33", 0)]),
    (2, "RC522 reader", "8-way, module order", [
        ("SDA", "D16", 0), ("SCK", "D18", 1), ("MOSI", "D23", 1),
        ("MISO", "D19", 0), ("IRQ", "not connected", 0),
        ("GND", "GND rail", 0), ("RST", "D17", 0), ("3.3V", "3V3 rail", 2)]),
    (3, "MPU-6050", "4 of its 8 pins", [
        ("VCC", "3V3 rail", 2), ("GND", "GND rail", 0),
        ("SCL", "D22", 0), ("SDA", "D21", 0)]),
    (4, "LEDs", "220R already in the leg", [
        ("RED +", "D25 via 220R", 0), ("GRN +", "D26 via 220R", 0),
        ("both -", "GND rail", 0)]),
    (5, "Buzzer", "passive, 3-pin", [
        ("SIG", "D27", 0), ("VCC", "5V rail", 0), ("GND", "GND rail", 0)]),
    (6, "Reed", "no resistor needed", [
        ("one leg", "D32", 0), ("other leg", "GND rail", 0)]),
    (7, "Relay", "horn switches in ITS terminals", [
        ("IN", "D13 via 1k", 0), ("VCC", "5V rail", 0),
        ("GND", "GND rail", 0)]),
]

RULES = [
    ("USB-C must hang off the board edge.", WARN,
     "Push a real cable in before you solder anything. Once the ESP32 is\n"
     "down you cannot move it, and the plug's shroud fouls the board."),
    ("Rails are BARE wire, soldered at every pad.", INK,
     "That turns every hole in the column into a tap point. Do not build a\n"
     "rail out of solder bridges -- it eats solder and lifts pads."),
    ("Female headers for the ESP32. Never solder it down.", INK,
     "It has to come out: for the real PCB, and to rule it out as a fault."),
    ("Big modules stay OFF the board, on Dupont leads.", INK,
     "RC522 is 40x60mm, TFT 34x56mm. They will not fit sensibly next to a\n"
     "devkit on 70x90. Solder male pins as breakouts and let them lie."),
    ("TFT is 5V. RC522 is 3.3V.", WARN,
     "Near-identical 8-pin headers side by side. 5V kills the reader on\n"
     "contact -- that is why the two rails are three columns apart."),
    ("Phenolic board: ~330C, under 3 seconds a joint.", WARN,
     "Dwell and the pad lifts off, which is unrepairable. Practice on a\n"
     "corner you will not use. Never desolder -- cut and use a new hole."),
    ("Beep it out before you plug in USB.", INK,
     "5V-GND, 3V3-GND and 5V-3V3 must all NOT beep. Thirty seconds, and it\n"
     "catches nearly every way a prototype dies on first power."),
]

ORDER = ["1. rails + ESP32 sockets -> BlinkTest",
         "2. TFT -> screen alive",
         "3. RC522 -> THE SPI SHARE TEST, stop here if it fails",
         "4. MPU, reed, LEDs, buzzer -> one flag per session",
         "5. relay + horn",
         "6. second board: buck / TP4056 / boost"]


def font(sz, bold=False):
    for nm in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf"):
        try:
            return ImageFont.truetype(nm, sz)
        except OSError:
            continue
    return ImageFont.load_default()


def cx(col):
    """centre x of a lettered column"""
    return BX + (ord(col) - 65) * PITCH + PITCH // 2


def cy(row):
    """centre y of a numbered row (1-based, like the board's own labels)"""
    return BY + (row - 1) * PITCH + PITCH // 2


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    f_h1 = font(40, True)
    f_h2 = font(25, True)
    f_b = font(20)
    f_s = font(17)
    f_xs = font(14)
    f_pin = font(13)

    # ---------------- the board itself ----------------
    bw, bh = COLS * PITCH, ROWS * PITCH
    d.rounded_rectangle([BX - 16, BY - 16, BX + bw + 16, BY + bh + 16],
                        10, fill=BOARD, outline=BOARD_ED, width=3)
    for hx, hy in ((BX - 4, BY - 4), (BX + bw + 4, BY - 4),
                   (BX - 4, BY + bh + 4), (BX + bw + 4, BY + bh + 4)):
        d.ellipse([hx - 7, hy - 7, hx + 7, hy + 7], fill=BG, outline=BOARD_ED)

    for j in range(ROWS):
        for i in range(COLS):
            x, y = BX + i * PITCH + PITCH // 2, BY + j * PITCH + PITCH // 2
            d.ellipse([x - 8, y - 8, x + 8, y + 8], outline=PADC, width=2)
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=BG)

    # the board's own coordinates, so a hole here maps to a hole there
    for i in range(COLS):
        d.text((BX + i * PITCH + PITCH // 2, BY - 34), chr(65 + i),
               font=f_xs, fill=MUTED, anchor="mm")
    for j in range(0, ROWS):
        if (j + 1) % 5 == 0 or j == 0:
            d.text((BX + bw + 34, BY + j * PITCH + PITCH // 2), str(j + 1),
                   font=f_xs, fill=MUTED, anchor="mm")

    # ---------------- rails ----------------
    for i, (col, colr, name) in enumerate(RAILS):
        x = cx(col)
        d.line([x, cy(1), x, cy(ROWS)], fill=colr, width=11)
        for r in range(1, ROWS + 1):
            d.ellipse([x - 5, cy(r) - 5, x + 5, cy(r) + 5], fill=colr)
        # Labels sit ABOVE the letter row so they never hide which column the
        # rail runs down. Two columns apart is narrower than the labels are
        # wide, so they alternate height instead of overlapping each other.
        yl = BY - 100 if i % 2 == 0 else BY - 64
        d.line([x, yl + 15, x, BY - 20], fill=colr, width=3)
        d.rounded_rectangle([x - 42, yl - 15, x + 42, yl + 15], 7, fill=colr)
        d.text((x, yl), f"{name} {col}", font=f_s,
               fill=(255, 255, 255), anchor="mm")

    # ---------------- ESP32 ----------------
    lx, rx = cx(ESP_L), cx(ESP_R)
    top, bot = cy(ESP_TOP), cy(ESP_BOT)
    d.rounded_rectangle([lx - 26, top - 34, rx + 26, bot + 30], 9,
                        fill=CHIP, outline=CHIP_ED, width=3)
    d.text(((lx + rx) // 2, top - 52), "ESP32 DevKitC 38-pin", font=f_s,
           fill=INK, anchor="mm")
    d.text(((lx + rx) // 2, top - 12), "antenna", font=f_xs,
           fill=(150, 160, 165), anchor="mm")

    for k in range(19):
        y = cy(ESP_TOP + k)
        for x, names in ((lx, LEFT_ROW), (rx, RIGHT_ROW)):
            nm = names[k]
            col = (70, 78, 84) if nm in FLASH else (
                PADC if nm in USED else (140, 150, 156))
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=col)
            tx = x - 20 if x == lx else x + 20
            d.text((tx, y), nm, font=f_pin,
                   fill=(235, 240, 238) if nm in USED else (120, 130, 136),
                   anchor="rm" if x == lx else "lm")

    # USB overhanging the bottom edge -- the point of the whole placement
    ux = (lx + rx) // 2
    d.rounded_rectangle([ux - 40, bot + 24, ux + 40, BY + bh + 62], 8,
                        fill=(160, 170, 176), outline=CHIP_ED, width=2)
    d.text((ux, BY + bh + 42), "USB-C", font=f_xs, fill=INK, anchor="mm")
    d.line([BX - 40, BY + bh + 16, BX + bw + 40, BY + bh + 16],
           fill=WARN, width=3)
    d.text((ux + 130, BY + bh + 48), "hangs PAST the edge", font=f_s,
           fill=WARN, anchor="lm")

    # ---------------- breakout blocks ----------------
    for n, lab, col, r0, r1 in BLOCKS:
        x = cx(col)
        y0, y1 = cy(r0), cy(r1)
        d.rounded_rectangle([x - 22, y0 - 20, x + 22, y1 + 20], 8,
                            fill=(238, 246, 240), outline=BLOCKC, width=3)
        for r in range(r0, r1 + 1):
            d.ellipse([x - 6, cy(r) - 6, x + 6, cy(r) + 6], fill=BLOCKC)
        # badge above, name below -- side by side they collided
        d.ellipse([x - 16, y0 - 48, x + 16, y0 - 16], fill=BLOCKC)
        d.text((x, y0 - 32), str(n), font=f_s, fill=(255, 255, 255),
               anchor="mm")
        d.text((x, y1 + 34), lab, font=f_xs, fill=BLOCKC, anchor="mm")

    d.text((BX, BY + bh + 96),
           "green = male pins soldered here, module on Dupont leads",
           font=f_s, fill=BLOCKC)
    d.text((BX, BY + bh + 124),
           "gold = an ESP32 pin this rig uses   grey = spare   dark = flash, never touch",
           font=f_s, fill=MUTED)

    # ---------------- right panel ----------------
    px = 1010
    d.text((px, 52), "FreeISP brain - perfboard test rig", font=f_h1, fill=INK)
    d.text((px, 104),
           "7 x 9 cm, 25 x 35 holes at 2.54mm. Same GPIOs as PCB rev E, so "
           "firmware proven here runs on the real board unchanged.",
           font=f_s, fill=MUTED)

    y = 152
    d.text((px, y), "WIRE LIST", font=f_h2, fill=INK)
    y += 40
    for n, name, note, pins in WIRES:
        d.ellipse([px, y + 1, px + 26, y + 27], fill=BLOCKC)
        d.text((px + 13, y + 14), str(n), font=f_s, fill=(255, 255, 255),
               anchor="mm")
        d.text((px + 38, y + 14), name, font=f_b, fill=INK, anchor="lm")
        d.text((px + 300, y + 15), note, font=f_xs, fill=FAINT, anchor="lm")
        y += 34
        for a, b, flag in pins:
            c = V33C if flag == 2 else (BLOCKC if flag == 1 else MUTED)
            d.text((px + 44, y), a, font=f_s, fill=c)
            d.text((px + 150, y), "->", font=f_s, fill=FAINT)
            d.text((px + 186, y), b, font=f_s, fill=c)
            if flag == 1:
                d.text((px + 320, y), "shared SPI bus - the thing to prove",
                       font=f_xs, fill=BLOCKC)
            if flag == 2:
                d.text((px + 320, y), "3.3V ONLY - 5V destroys it",
                       font=f_xs, fill=V33C)
            y += 23
        y += 12

    # the two ADC pins have no block: nothing on THIS board feeds them.
    # They come off the power board's dividers, which is step 6.
    d.line([px, y + 4, px + 820, y + 4], fill=FAINT, width=1)
    d.text((px, y + 18), "D34 / D35  power sensing", font=f_b, fill=MUTED)
    d.text((px + 44, y + 46),
           "no header on this board -- they come from the SECOND board's",
           font=f_s, fill=MUTED)
    d.text((px + 44, y + 69),
           "dividers (12V via 100k/27k, VBAT via 100k/100k). Leave "
           "POWER_WIRED 0", font=f_s, fill=MUTED)
    d.text((px + 44, y + 92), "until that board exists.", font=f_s, fill=MUTED)

    # ---------------- rules ----------------
    ry = 152
    rx2 = 1700
    d.text((rx2, ry), "RULES", font=f_h2, fill=INK)
    ry += 42
    for head, colr, body in RULES:
        d.line([rx2, ry + 2, rx2, ry + 20], fill=colr, width=4)
        d.text((rx2 + 14, ry), head, font=f_s, fill=colr)
        ry += 26
        for ln in body.split("\n"):
            d.text((rx2 + 14, ry), ln, font=f_xs, fill=MUTED)
            ry += 19
        ry += 14

    ry += 10
    d.text((rx2, ry), "BUILD ORDER", font=f_h2, fill=INK)
    ry += 40
    for step in ORDER:
        c = WARN if "STOP" in step.upper() else INK
        d.text((rx2 + 14, ry), step, font=f_s, fill=c)
        ry += 27

    d.line([px, H - 62, W - 60, H - 62], fill=FAINT, width=2)
    d.text((px, H - 48),
           "pcb/perfboard_png.py   pin destinations from PINOUT.md rev E",
           font=f_xs, fill=FAINT)

    img.save(OUT)
    print(f"wrote {OUT}  ({W}x{H})")


if __name__ == "__main__":
    main()
