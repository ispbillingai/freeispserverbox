"""Print local pad coordinates of the stock footprints the brain board uses,
so placement and rotation in build.py are chosen from fact, not assumption."""

import os
import sexp

FPLIB = r"F:\kicad\share\kicad\footprints"

WANTED = [
    ("Connector_PinSocket_2.54mm", "PinSocket_1x15_P2.54mm_Vertical"),
    ("Connector_PinHeader_2.54mm", "PinHeader_1x03_P2.54mm_Vertical"),
    ("Connector_PinHeader_2.54mm", "PinHeader_1x04_P2.54mm_Vertical"),
    ("Connector_PinHeader_2.54mm", "PinHeader_1x07_P2.54mm_Vertical"),
    ("Connector_PinHeader_2.54mm", "PinHeader_1x08_P2.54mm_Vertical"),
    ("TerminalBlock_Phoenix",
     "PhoenixContact_MCV_1,5_2-G-5.08_1x02_P5.08mm_Vertical"),
    ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"),
    ("MountingHole", "MountingHole_3.2mm_M3"),
]


def load(lib, name):
    path = os.path.join(FPLIB, lib + ".pretty", name + ".kicad_mod")
    with open(path, encoding="utf-8") as fh:
        return sexp.parse(fh.read())


for lib, name in WANTED:
    try:
        fp = load(lib, name)
    except FileNotFoundError:
        print(f"MISSING  {lib}:{name}")
        continue

    pads = sexp.find_all(fp, "pad")
    print(f"\n{name}   ({len(pads)} pads)")
    for pad in pads[:4]:
        num = sexp.unq(pad[1])
        ptype = pad[2]
        shape = pad[3]
        at = sexp.find(pad, "at")
        size = sexp.find(pad, "size")
        drill = sexp.find(pad, "drill")
        print(f"   pad {num:>3}  {ptype:<9} {shape:<7} at={at[1:]}  "
              f"size={size[1:] if size else '-'}  drill={drill[1:] if drill else '-'}")
    if len(pads) > 4:
        last = pads[-1]
        print(f"   pad {sexp.unq(last[1]):>3}  ... at={sexp.find(last, 'at')[1:]}")
