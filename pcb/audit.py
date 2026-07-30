"""Independent electrical audit of freeisp_brain.kicad_pcb.

Deliberately does NOT reuse build.py's data structures -- it parses the board
file KiCad reads, so a bug in the generator cannot hide itself. Two checks:

1. SHORTS ("wires intermarrying"): every pair of copper items on different
   nets, same layer, must be at least CLEARANCE apart. Pads and vias are
   through-hole, so they live on both layers.

2. CONNECTIVITY: for every net, all of its pads must form ONE connected
   island through tracks and vias. A net in two islands means a wire that
   looks routed but is not.

    python audit.py
"""

import math
import sys
import sexp

CLEARANCE = 0.25
TOUCH_EPS = 0.01        # endpoints closer than this are the same point

BOARD = "freeisp_brain.kicad_pcb"


def dist_pt_seg(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def dist_seg_seg(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    def ccw(px, py, qx, qy, rx, ry):
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)

    d1 = ccw(bx1, by1, bx2, by2, ax1, ay1)
    d2 = ccw(bx1, by1, bx2, by2, ax2, ay2)
    d3 = ccw(ax1, ay1, ax2, ay2, bx1, by1)
    d4 = ccw(ax1, ay1, ax2, ay2, bx2, by2)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0  # they cross
    return min(
        dist_pt_seg(ax1, ay1, *b), dist_pt_seg(ax2, ay2, *b),
        dist_pt_seg(bx1, by1, *a), dist_pt_seg(bx2, by2, *a),
    )


def load():
    with open(BOARD, encoding="utf-8") as fh:
        pcb = sexp.parse(fh.read())

    nets = {}
    for n in sexp.find_all(pcb, "net"):
        nets[int(n[1])] = sexp.unq(n[2])

    pads = []       # x, y, half, net, ref, pin  (through-hole: both layers)
    for fp in sexp.find_all(pcb, "footprint"):
        fat = sexp.find(fp, "at")
        fx, fy = float(fat[1]), float(fat[2])
        frot = float(fat[3]) if len(fat) > 3 else 0.0
        ref = "?"
        for prop in sexp.find_all(fp, "property"):
            if sexp.unq(prop[1]) == "Reference":
                ref = sexp.unq(prop[2])
        th = math.radians(frot)
        c, s = math.cos(th), math.sin(th)
        for pad in sexp.find_all(fp, "pad"):
            if pad[2] == "np_thru_hole":
                continue
            pat = sexp.find(pad, "at")
            lx, ly = float(pat[1]), float(pat[2])
            # KiCad footprint rotation: +rot rotates CCW, y axis points down
            px = fx + lx * c + ly * s
            py = fy - lx * s + ly * c
            size = sexp.find(pad, "size")
            half = max(float(size[1]), float(size[2])) / 2.0
            netn = sexp.find(pad, "net")
            net = int(netn[1]) if netn else -1
            pads.append((px, py, half, net, ref, sexp.unq(pad[1])))

    segs = []       # x1,y1,x2,y2,half,net,layer
    for sg in sexp.find_all(pcb, "segment"):
        st, en = sexp.find(sg, "start"), sexp.find(sg, "end")
        segs.append((
            float(st[1]), float(st[2]), float(en[1]), float(en[2]),
            float(sexp.find(sg, "width")[1]) / 2.0,
            int(sexp.find(sg, "net")[1]),
            sexp.unq(sexp.find(sg, "layer")[1]),
        ))

    vias = []       # x, y, half, net (both layers)
    for v in sexp.find_all(pcb, "via"):
        at = sexp.find(v, "at")
        vias.append((float(at[1]), float(at[2]),
                     float(sexp.find(v, "size")[1]) / 2.0,
                     int(sexp.find(v, "net")[1])))

    return nets, pads, segs, vias


def check_shorts(nets, pads, segs, vias):
    """Minimum copper-to-copper distance between different nets."""
    bad = []
    rounds = pads + [(x, y, h, n, "via", "") for x, y, h, n in vias]

    # segment vs segment (same layer only)
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a, b = segs[i], segs[j]
            if a[5] == b[5] or a[6] != b[6]:
                continue
            d = dist_seg_seg(a[:4], b[:4]) - a[4] - b[4]
            if d < CLEARANCE - 1e-6:
                bad.append((d, f"track {nets[a[5]]} vs track {nets[b[5]]} "
                            f"on {a[6]} near ({a[0]:.1f},{a[1]:.1f})"))

    # round things (pads, vias) vs segments -- both layers for pads/vias
    for px, py, ph, pn, ref, pin in rounds:
        for x1, y1, x2, y2, sh, sn, _layer in segs:
            if sn == pn or pn == -1 and False:
                pass
            if sn == pn:
                continue
            d = dist_pt_seg(px, py, x1, y1, x2, y2) - ph - sh
            if d < CLEARANCE - 1e-6:
                pname = nets.get(pn, "<none>") if pn >= 0 else "<no net>"
                bad.append((d, f"{ref} pad {pin} [{pname}] vs track "
                            f"{nets[sn]} near ({px:.1f},{py:.1f})"))

    # round vs round
    for i in range(len(rounds)):
        for j in range(i + 1, len(rounds)):
            a, b = rounds[i], rounds[j]
            if a[3] == b[3]:
                continue
            d = math.hypot(a[0] - b[0], a[1] - b[1]) - a[2] - b[2]
            if d < CLEARANCE - 1e-6:
                an = nets.get(a[3], "<none>") if a[3] >= 0 else "<no net>"
                bn = nets.get(b[3], "<none>") if b[3] >= 0 else "<no net>"
                bad.append((d, f"{a[4]} pad {a[5]} [{an}] vs {b[4]} pad "
                            f"{b[5]} [{bn}] at ({a[0]:.1f},{a[1]:.1f})"))
    return bad


def check_connectivity(nets, pads, segs, vias):
    """Per net: do all pads form one island through copper?"""
    parent = {}

    def find(k):
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        parent[find(a)] = find(b)

    def key(x, y, tag):
        return (round(x, 2), round(y, 2), tag)

    # per-net registry of copper nodes so we can join by geometry
    by_net_items = {}
    for idx, (x1, y1, x2, y2, h, n, layer) in enumerate(segs):
        by_net_items.setdefault(n, []).append(("seg", idx))
    for idx, (x, y, h, n) in enumerate(vias):
        by_net_items.setdefault(n, []).append(("via", idx))
    for idx, (x, y, h, n, ref, pin) in enumerate(pads):
        if n >= 0:
            by_net_items.setdefault(n, []).append(("pad", idx))

    problems = []
    for n, items in sorted(by_net_items.items()):
        name = nets.get(n, "?")
        if not name:
            continue
        # nodes: each item is a vertex; join when geometry touches
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                ta, ia = items[i]
                tb, ib = items[j]
                if touches(ta, ia, tb, ib, pads, segs, vias):
                    union((ta, ia), (tb, ib))
        pad_items = [it for it in items if it[0] == "pad"]
        if len(pad_items) < 2:
            continue
        roots = {find(it) for it in pad_items}
        if len(roots) > 1:
            # name the stranded pads
            comps = {}
            for it in pad_items:
                comps.setdefault(find(it), []).append(
                    f"{pads[it[1]][4]}.{pads[it[1]][5]}")
            problems.append((name, list(comps.values())))
    return problems


def touches(ta, ia, tb, ib, pads, segs, vias):
    def geo(t, i):
        if t == "seg":
            return segs[i]
        if t == "via":
            x, y, h, n = vias[i]
            return (x, y, h)
        x, y, h, n, ref, pin = pads[i]
        return (x, y, h)

    ga, gb = geo(ta, ia), geo(tb, ib)
    if ta == "seg" and tb == "seg":
        a, b = segs[ia], segs[ib]
        if a[6] != b[6]:
            return False        # different layers never touch without a via
        return dist_seg_seg(a[:4], b[:4]) <= a[4] + b[4] + TOUCH_EPS
    if ta == "seg" or tb == "seg":
        if ta == "seg":
            sgm, rnd, rt = segs[ia], gb, tb
        else:
            sgm, rnd, rt = segs[ib], ga, ta
        # pads and vias span both layers, so layer always matches
        return (dist_pt_seg(rnd[0], rnd[1], *sgm[:4])
                <= rnd[2] + sgm[4] + TOUCH_EPS)
    return (math.hypot(ga[0] - gb[0], ga[1] - gb[1])
            <= ga[2] + gb[2] + TOUCH_EPS)


def main():
    nets, pads, segs, vias = load()
    print(f"parsed: {len(pads)} pads, {len(segs)} segments, "
          f"{len(vias)} vias, {sum(1 for v in nets.values() if v)} nets")

    print("\n== 1. SHORT CHECK (different nets too close / crossing) ==")
    bad = check_shorts(nets, pads, segs, vias)
    if bad:
        bad.sort()
        for d, msg in bad[:25]:
            print(f"   {'OVERLAP' if d < 0 else f'{d:.3f}mm':>8}  {msg}")
        print(f"   -> {len(bad)} problems")
    else:
        print("   CLEAN - no two nets closer than "
              f"{CLEARANCE} mm anywhere, no crossings")

    print("\n== 2. CONNECTIVITY (every net one island) ==")
    probs = check_connectivity(nets, pads, segs, vias)
    if probs:
        for name, comps in probs:
            print(f"   {name}: {len(comps)} separate islands: {comps}")
        print(f"   -> {len(probs)} broken nets")
    else:
        print("   CLEAN - every net's pads form a single connected island")

    ok = not bad and not probs
    print(f"\nAUDIT {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
