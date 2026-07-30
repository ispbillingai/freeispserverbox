"""Export the PCBWay-ready Gerber + drill zip, and prove nothing stray got in.

Deliberately omits Dwgs.User: the print-calibration ruler lives there and
must never be etched onto a real board.

    python export_gerbers.py     ->  gerbers/  and  freeisp_brain_gerbers.zip
"""

import glob
import math
import os
import re
import shutil
import subprocess
import sys
import zipfile

import sexp

KICAD = r"F:\kicad\bin\kicad-cli.exe"
BOARD = "freeisp_brain.kicad_pcb"
OUTDIR = "gerbers"
ZIPNAME = "freeisp_brain_gerbers.zip"

# What the fab makes. Dwgs.User is NOT here on purpose.
LAYERS = "F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"

# Board outline in page coordinates, so we can spot anything drawn off-board.
X0, Y0, SIDE = 60.0, 40.0, 115.0


def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
        sys.exit(f"FAILED: {' '.join(args)}")


def extents(path):
    xs, ys = [], []
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = re.match(r"^X(-?\d+)Y(-?\d+)D0[123]\*$", line.strip())
        if m:
            xs.append(int(m.group(1)) / 1e6)
            ys.append(int(m.group(2)) / 1e6)
    return (min(xs), max(xs), min(ys), max(ys)) if xs else None


def main():
    if os.path.isdir(OUTDIR):
        shutil.rmtree(OUTDIR)
    os.makedirs(OUTDIR)

    run([KICAD, "pcb", "export", "gerbers", "--output", OUTDIR,
         "--layers", LAYERS, "--subtract-soldermask", "--no-protel-ext", BOARD])
    run([KICAD, "pcb", "export", "drill", "--output", OUTDIR,
         "--format", "excellon", "--excellon-units", "mm",
         "--drill-origin", "absolute", "--excellon-separate-th",
         "--generate-map", "--map-format", "gerberx2", BOARD])

    # ---- prove nothing sits outside the board outline ----
    bad = []
    for f in sorted(glob.glob(f"{OUTDIR}/*.gbr")):
        if "drl_map" in f:
            continue
        e = extents(f)
        if not e:
            continue
        x0, x1, y0, y1 = e
        if not (x0 >= X0 - 0.5 and x1 <= X0 + SIDE + 0.5
                and y0 >= -(Y0 + SIDE) - 0.5 and y1 <= -Y0 + 0.5):
            bad.append((os.path.basename(f), e))

    # ---- every pad in the board must have a hole in the drill file ----
    # Catches the worst silent failure: a stale export that predates the
    # last change, so a connector exists in KiCad but not in the zip.
    pcb = sexp.parse(open(BOARD, encoding="utf-8").read())
    pads = []
    for fp in sexp.find_all(pcb, "footprint"):
        ref = "?"
        for p in sexp.find_all(fp, "property"):
            if sexp.unq(p[1]) == "Reference":
                ref = sexp.unq(p[2])
        at = sexp.find(fp, "at")
        fx, fy = float(at[1]), float(at[2])
        rot = math.radians(float(at[3]) if len(at) > 3 else 0)
        c, s = math.cos(rot), math.sin(rot)
        for pad in sexp.find_all(fp, "pad"):
            a = sexp.find(pad, "at")
            lx, ly = float(a[1]), float(a[2])
            # drill files negate Y, same convention as gerber
            pads.append((ref, round(fx + lx * c + ly * s, 2),
                         round(-(fy - lx * s + ly * c), 2)))

    holes = set()
    for f in glob.glob(f"{OUTDIR}/*.drl"):
        for line in open(f, encoding="utf-8", errors="ignore"):
            m = re.match(r"^X([\d.-]+)Y([\d.-]+)$", line.strip())
            if m:
                holes.add((round(float(m.group(1)), 2), round(float(m.group(2)), 2)))
    undrilled = [(r, x, y) for r, x, y in pads if (x, y) not in holes]

    edge = extents(f"{OUTDIR}/freeisp_brain-Edge_Cuts.gbr")
    w, h = edge[1] - edge[0], edge[3] - edge[2]

    pth = open(f"{OUTDIR}/freeisp_brain-PTH.drl", encoding="utf-8").read()
    npth = open(f"{OUTDIR}/freeisp_brain-NPTH.drl", encoding="utf-8").read()
    holes = len(re.findall(r"^X", pth, re.M)), len(re.findall(r"^X", npth, re.M))

    with zipfile.ZipFile(ZIPNAME, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(f"{OUTDIR}/*")):
            z.write(f, os.path.basename(f))

    print(f"outline      {w:.3f} x {h:.3f} mm")
    print(f"holes        {holes[0]} plated, {holes[1]} unplated (the M3 mounts)")
    print(f"off-board    {'CLEAN' if not bad else bad}")
    print(f"pads drilled {len(pads) - len(undrilled)}/{len(pads)}"
          + ("" if not undrilled else f"   MISSING: {undrilled}"))
    print(f"zip          {ZIPNAME}  "
          f"({os.path.getsize(ZIPNAME) / 1024:.0f} kB, "
          f"{len(glob.glob(f'{OUTDIR}/*'))} files)")
    if bad or undrilled or abs(w - SIDE) > 0.01 or abs(h - SIDE) > 0.01:
        sys.exit("*** DO NOT ORDER - check the failures above ***")
    print("\nREADY TO UPLOAD")


if __name__ == "__main__":
    main()
