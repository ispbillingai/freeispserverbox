# FIR_FitCoupons.py - Autodesk Fusion 360 script
# FIT-TEST COUPONS (18 Aug 2026 two-AI review): print these BEFORE any full
# 280mm part.  Each pair must slide, click, screw and reopen cleanly in final
# PETG at final orientation; if a pair fails, fix the shared-contract number
# it derives from and reprint the coupon, never the big part.
#
#   Pair 1  CAP-FIT RING: a shallow ring of the real tub rim (280 outline)
#           and a shallow ring of the real cap skirt (281 inner, lead-in
#           chamfer).  Tests the 0.5mm/side slide fit at FULL perimeter,
#           where warp actually lives.  Print the cap ring chamfer-edge UP
#           (same edge orientation as the real roof-down cap print).
#   Pair 2  CAP WALL SECTION: 70mm of tub side wall with one snap detent and
#           one screw boss/pilot + the matching skirt strip with the window,
#           the visible seat pad/counterbore and the lead-in chamfer.
#           Tests: click feel, screw drive, seat look.
#   Pair 3  RAIL LOCK SECTION: 65mm-wide end slice of the BottomLid front
#           (shelf, rail, ORIENTATION KEY block, widened lock boss, groove)
#           and the matching CurvedLid slice (channel, key relief, anti-
#           rattle nub, locator tab, lock screw + dished seat).  Tests the
#           whole slide-and-lock story including that a reversed cover
#           refuses to seat.
#
# All interface numbers come from fusion/_shared/FIR_Interface.py.  Local
# section dimensions mirror FIR_Shell v32 / FIR_BottomLid v3 / FIR_CurvedLid
# v3; if those parts change shape, re-check this file.

import importlib.util
import math
import os
import sys

import adsk.core, adsk.fusion, adsk.cam, traceback


def _load_shared_interface():
    """Load the one mechanical-interface contract in workspace or Fusion."""
    script_file = globals().get('__file__', '')
    script_dir = (os.path.dirname(os.path.abspath(script_file))
                  if script_file else os.getcwd())
    candidates = []
    override = os.environ.get('FIR_INTERFACE_PATH')
    if override:
        candidates.append(override if override.lower().endswith('.py')
                          else os.path.join(override, 'FIR_Interface.py'))
    workspace_source = globals().get('_workspace_source')
    if workspace_source:
        candidates.append(os.path.join(
            os.path.dirname(os.path.abspath(workspace_source)), '..',
            '_shared', 'FIR_Interface.py'))
    candidates.extend((
        os.path.join(script_dir, 'FIR_Interface.py'),
        os.path.join(script_dir, '..', '_shared', 'FIR_Interface.py'),
    ))
    for candidate in candidates:
        path = os.path.realpath(os.path.abspath(candidate))
        if not os.path.isfile(path):
            continue
        sys.modules.pop('_freeisp_shared_interface', None)
        spec = importlib.util.spec_from_file_location(
            '_freeisp_shared_interface', path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules['_freeisp_shared_interface'] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError(
        'FIR_Interface.py not found. Deploy fusion/_shared beside the Fusion scripts.')


INTERFACE = _load_shared_interface()

CM = 0.1


def mm(v):
    return v * CM


NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
SKIPPED = []


def _ext(comp, prof, z0, sz, op, parts):
    f = comp.features.extrudeFeatures
    ei = f.createInput(prof, op)
    if abs(z0) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(z0)))
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(sz)))
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def box(comp, cx, cy, z0, sx, sy, sz, op, parts=None):
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchLines.addCenterPointRectangle(
        adsk.core.Point3D.create(mm(cx), mm(cy), 0),
        adsk.core.Point3D.create(mm(cx + sx / 2.0), mm(cy + sy / 2.0), 0))
    return _ext(comp, sk.profiles.item(0), z0, sz, op, parts)


def cyl(comp, cx, cy, z0, d, sz, op, parts=None):
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(d / 2.0))
    return _ext(comp, sk.profiles.item(0), z0, sz, op, parts)


def cyl_y(comp, cx, cz, ycenter, d, span, op, parts=None):
    # MEASURED xZ convention (FIR_PlaneProbe v3): sketch-V is world -Z.
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cx), mm(-cz), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(ycenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(ycenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def cyl_x(comp, cy, cz, xcenter, d, span, op, parts=None):
    # cylinder along X (circle on the yZ plane).  MEASURED yZ convention
    # (FIR_PlaneProbe v3): sketch-U is world -Z, sketch-V is world +Y.
    sk = comp.sketches.add(comp.yZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(-cz), mm(cy), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(xcenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(xcenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def poly_x(comp, pts_yz, xcenter, span, op, parts=None):
    # closed polygon on the yZ plane, swept along X (measured convention).
    sk = comp.sketches.add(comp.yZConstructionPlane)
    lines = sk.sketchCurves.sketchLines
    n = len(pts_yz)
    for i in range(n):
        y0, z0 = pts_yz[i]
        y1, z1 = pts_yz[(i + 1) % n]
        lines.addByTwoPoints(adsk.core.Point3D.create(mm(-z0), mm(y0), 0),
                             adsk.core.Point3D.create(mm(-z1), mm(y1), 0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(xcenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(xcenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def build_cap_fit_rings(comp):
    """Pair 1: full-perimeter shallow rings of the tub rim and cap skirt."""
    # Tub rim ring: real 280 outline, 3mm walls, 10 tall.
    tub = box(comp, 0, 0, 0, 280, 280, 10, NEW).bodies.item(0)
    tub.name = 'COUPON 1a tub rim ring (280 outline, print as-is)'
    box(comp, 0, 0, -1, 274, 274, 12, CUT, [tub])
    # Cap skirt ring beside it: real 281 inner / 286 outer, 14 tall, with the
    # 1.2mm lead-in chamfer stepped on its test edge (a stepped approximation
    # is fine for a coupon; the real cap has the true 45-degree cut).
    ox = 320.0
    cap = box(comp, ox, 0, 0, 286, 286, 14, NEW).bodies.item(0)
    cap.name = 'COUPON 1b cap skirt ring (281 inner, chamfer edge UP)'
    box(comp, ox, 0, -1, 281, 281, 16, CUT, [cap])
    ch = INTERFACE.CAP_LEADIN_CH
    box(comp, ox, 0, 14 - ch, 281 + 2 * ch, 281 + 2 * ch, ch + 1, CUT, [cap])
    SKIPPED.append('rings: corners are square (real parts are R10); this pair '
                   'tests perimeter size + warp, not corner detail')
    return tub, cap


def build_cap_wall_section(comp):
    """Pair 2: 70mm of tub side wall + matching cap skirt strip.

    Local X spans shell Y-80..-10 (so it contains the Y-45 detent and the
    Y-75 screw row); local Z = shell Z - 52 on the wall piece.
    """
    oy = 200.0
    base = box(comp, 0, oy, 0, 80, 26, 3, NEW).bodies.item(0)
    base.name = 'COUPON 2a tub wall section (detent + boss + pilot)'
    # the wall: outer face at local y = oy+6, 3 thick, shell Z55..80 -> z3..28
    wy = oy + 4.5
    box(comp, 0, wy, 3, 70, 3, 25, JOIN, [base])
    # snap detent (shell Y-45 -> local x 0): stepped bump, band shell Z71..76
    z0, z1 = INTERFACE.CAP_SNAP_Z0 - 52.0, INTERFACE.CAP_SNAP_Z1 - 52.0
    zm = (z0 + z1) / 2.0
    bump_face = wy + 1.5
    box(comp, 0, bump_face + INTERFACE.CAP_SNAP_PROUD / 2.0, z0,
        INTERFACE.CAP_SNAP_W, INTERFACE.CAP_SNAP_PROUD, zm - z0, JOIN, [base])
    box(comp, 0, bump_face + INTERFACE.CAP_SNAP_PROUD / 4.0, zm,
        INTERFACE.CAP_SNAP_W, INTERFACE.CAP_SNAP_PROUD / 2.0, z1 - zm,
        JOIN, [base])
    # screw boss on the inner face (shell Y-75 -> local x -30), pilot at Z72
    box(comp, -30, wy - 7.5, 14, 12, 12, 12, JOIN, [base])
    cyl_y(comp, -30, 20, wy, INTERFACE.CAP_BOSS_PILOT_D, 30, CUT, [base])

    # Skirt strip in the SAME z frame (shell Z - 52) as the wall piece, so
    # sliding it down to full seat lines the window up with the bump and the
    # screw hole with the pilot: strip shell Z65..93 -> z13..41, base plate
    # ON TOP (z41..44).  Print it base-down = chamfer edge up, exactly the
    # edge orientation of the real roof-down cap print.
    sy = oy + 40.0
    ky = sy - 4.0
    skirt = box(comp, 0, ky, 13, 70, 2.5, 28, NEW).bodies.item(0)
    skirt.name = 'COUPON 2b cap skirt strip (window + seat pad + chamfer)'
    box(comp, 0, sy, 41, 80, 26, 3, JOIN, [skirt])          # base at the top
    # lead-in chamfer substitute on the INNER (wall-side) lower edge, stepped
    box(comp, 0, ky - 1.25 + INTERFACE.CAP_LEADIN_CH / 2.0, 13,
        70, INTERFACE.CAP_LEADIN_CH, INTERFACE.CAP_LEADIN_CH, CUT, [skirt])
    # snap window at local x 0 (shell Z70..76.5 -> z18..24.5)
    box(comp, 0, ky, INTERFACE.CAP_SNAP_WIN_Z0 - 52.0,
        INTERFACE.CAP_SNAP_WIN_W, 4.0,
        INTERFACE.CAP_SNAP_WIN_Z1 - INTERFACE.CAP_SNAP_WIN_Z0, CUT, [skirt])
    # screw hole + visible seat pad + counterbore at local x -30, z20 (=Z72)
    pad_h = INTERFACE.CAP_SEAT_PAD_H
    sz = INTERFACE.CAP_SCREW_Z - 52.0
    cyl_y(comp, -30, sz, ky + 1.25 + (pad_h - 1) / 2.0,
          INTERFACE.M3_SEAT_PAD_D, pad_h + 1, JOIN, [skirt])
    cyl_y(comp, -30, sz, ky, 3.4, 8, CUT, [skirt])
    cyl_y(comp, -30, sz, ky + 1.25 + pad_h, INTERFACE.M3_SEAT_CBORE_D,
          2 * pad_h, CUT, [skirt])
    return base, skirt


def build_rail_lock_sections(comp):
    """Pair 3: end slices of the BottomLid front and the CurvedLid.

    BottomLid slice covers lid-local X -145..-80 (the shell +X end: rail,
    KEY BLOCK, widened lock boss, groove).  Cover slice covers cover-local
    X +80..+145 (channel with KEY RELIEF, nub, +90 tab, lock screw + seat).
    Slide the cover slice onto the lid slice: it must stop flush on the boss,
    click over the nub, and take the screw.  Flip it left-for-right and it
    must stand ~7mm proud on the key block - that is the orientation test.
    """
    oy = 320.0
    PT = 3.0
    rail_x = INTERFACE.COVER_RAIL_X
    lock_x = INTERFACE.COVER_LOCK_X
    # ---- BottomLid slice: local x -145..-80 -> coupon x -32.5..32.5 -------
    def lx(v):
        return v + 112.5      # -145 -> -32.5
    lid = box(comp, 0, oy, 0, 65, 80, PT, NEW).bodies.item(0)
    lid.name = 'COUPON 3a BottomLid end slice (rail + KEY + boss + groove)'
    # plate strip local y0..80 -> coupon y oy-40..oy+40; shelf out at y0 side
    def ly(v):
        return oy - 40.0 + v
    # shelf + rail + key block + lock boss (geometry = FIR_BottomLid v3)
    box(comp, 0, ly(1.5), PT, 65, 3, 65, JOIN, [lid])
    box(comp, lx(-rail_x), ly(3 + INTERFACE.COVER_RAIL_H / 2.0), PT,
        INTERFACE.COVER_RAIL_W, INTERFACE.COVER_RAIL_H, 62, JOIN, [lid])
    box(comp, lx(-rail_x), ly(3 + INTERFACE.COVER_RAIL_H
                              + INTERFACE.COVER_KEY_BLOCK_H / 2.0), PT,
        INTERFACE.COVER_RAIL_W, INTERFACE.COVER_KEY_BLOCK_H,
        INTERFACE.COVER_KEY_BLOCK_LEN, JOIN, [lid])
    # rail detent bump (outboard face of this lid-local -X rail = its -x side)
    dz0, dlen = INTERFACE.COVER_DETENT_LID_Z0, INTERFACE.COVER_DETENT_LEN
    df = -rail_x - INTERFACE.COVER_RAIL_W / 2.0
    box(comp, lx(df - INTERFACE.COVER_DETENT_PROUD / 2.0),
        ly(3 + INTERFACE.COVER_RAIL_H / 2.0), dz0,
        INTERFACE.COVER_DETENT_PROUD, 4.0, dlen / 2.0, JOIN, [lid])
    box(comp, lx(df - INTERFACE.COVER_DETENT_STEP_PROUD / 2.0),
        ly(3 + INTERFACE.COVER_RAIL_H / 2.0), dz0 + dlen / 2.0,
        INTERFACE.COVER_DETENT_STEP_PROUD, 4.0, dlen / 2.0, JOIN, [lid])
    box(comp, lx(-lock_x), ly(9.5), PT + 54,
        INTERFACE.COVER_LOCK_BOSS_W, 13, 8.5, JOIN, [lid])
    cyl(comp, lx(-lock_x), ly(12), PT + 54,
        INTERFACE.COVER_LOCK_BOSS_PILOT_D, 8, CUT, [lid])
    # top build-out + groove segment (tab target)
    box(comp, 0, ly(81.5), 0, 65, 3, PT, JOIN, [lid])
    box(comp, 0, ly(81.5), PT - 1, 60, 1.6, 2, CUT, [lid])

    # ---- CurvedLid slice: cover-local x +80..+145 -> coupon x -32.5..32.5 -
    oy2 = oy + 110.0
    def cx(v):
        return v - 112.5      # +145 -> 32.5
    HEIGHT, WALL, DEPTH = 80.0, 2.5, 65.0
    cov = box(comp, 0, oy2, 0, 65, HEIGHT, WALL, NEW).bodies.item(0)
    cov.name = 'COUPON 3b CurvedLid end slice (channel + RELIEF + nub + tab)'
    def cy(v):
        return oy2 + v
    CLR = INTERFACE.COVER_RAIL_CLR
    SHELF_TOP_Y, RAIL_TOP_Y = -HEIGHT / 2.0, -HEIGHT / 2.0 + INTERFACE.COVER_RAIL_H
    TZ0, TZ1 = WALL, DEPTH - 2.0
    # top wall + the +90 locator tab
    box(comp, 0, cy(HEIGHT / 2.0 - WALL / 2.0), 0, 65, WALL, DEPTH, JOIN, [cov])
    box(comp, cx(90), cy(38.5), DEPTH, INTERFACE.COVER_TAB_LEN, 1.0, 0.7,
        JOIN, [cov])
    # end wall
    box(comp, cx(145 - WALL / 2.0 - 1.25), cy(0), 0, WALL, HEIGHT, DEPTH,
        JOIN, [cov])
    # channel (web + ribs) with key relief + nub, geometry = FIR_CurvedLid v3
    half = INTERFACE.COVER_RAIL_W / 2.0 + CLR
    rib_w = INTERFACE.COVER_CHANNEL_RIB_W
    rib_cy = (SHELF_TOP_Y + RAIL_TOP_Y + CLR) / 2.0
    rib_h = (RAIL_TOP_Y + CLR) - SHELF_TOP_Y
    web_cy = RAIL_TOP_Y + CLR + 1.5
    sx = cx(rail_x)
    box(comp, sx, cy(web_cy), TZ0, 2.0 * (half + rib_w), 3.0, TZ1 - TZ0,
        JOIN, [cov])
    for off in (-(half + rib_w / 2.0), half + rib_w / 2.0):
        box(comp, sx + off, cy(rib_cy), TZ0, rib_w, rib_h, TZ1 - TZ0,
            JOIN, [cov])
    nub_h = CLR + INTERFACE.COVER_NUB_PROUD
    box(comp, sx, cy(RAIL_TOP_Y + (CLR - INTERFACE.COVER_NUB_PROUD) / 2.0),
        46.0, 6.0, nub_h, INTERFACE.COVER_NUB_LEN, JOIN, [cov])
    # detent gap in the OUTBOARD rib (+x side of this +X channel slice)
    box(comp, sx + (half + rib_w / 2.0), cy(rib_cy),
        INTERFACE.COVER_DETENT_GAP_Z0, rib_w + 0.4, rib_h + 0.2,
        INTERFACE.COVER_DETENT_GAP_LEN, CUT, [cov])
    box(comp, sx, cy(web_cy + 0.1), TZ1 - INTERFACE.COVER_KEY_RELIEF_LEN,
        2.0 * (half + rib_w) + 0.4, 3.4,
        INTERFACE.COVER_KEY_RELIEF_LEN + 1.0, CUT, [cov])
    # lock screw + dished seat
    cyl(comp, cx(lock_x), cy(-31.0), -1.0, INTERFACE.COVER_SEAT_D,
        INTERFACE.COVER_SEAT_DEPTH + 1.0, CUT, [cov])
    cyl(comp, cx(lock_x), cy(-31.0), -1.0, 3.4, WALL + 2.0, CUT, [cov])
    # the curved shoulder segment, so pair 4b's roof edge can prove the
    # 0.3mm seamless landing (quarter ellipse, contract numbers)
    outer, inner_pts = [], []
    steps = INTERFACE.COVER_SHOULDER_STEPS
    for i in range(steps + 1):
        t = (math.pi / 2.0) * i / steps
        yy = HEIGHT / 2.0 + INTERFACE.COVER_SHOULDER_RISE * math.sin(t)
        zz = INTERFACE.COVER_SHOULDER_REACH * (1.0 - math.cos(t))
        dy = INTERFACE.COVER_SHOULDER_RISE * math.cos(t)
        dz = INTERFACE.COVER_SHOULDER_REACH * math.sin(t)
        ln = math.hypot(dy, dz) or 1.0
        outer.append((oy2 + yy, zz))
        inner_pts.append((oy2 + yy + WALL * (-dz / ln), zz + WALL * (dy / ln)))
    poly_x(comp, outer + list(reversed(inner_pts)), 0.0, 62.0, JOIN, [cov])
    cap_face = [(oy2 + HEIGHT / 2.0, 0.0)] + outer +                [(oy2 + HEIGHT / 2.0, INTERFACE.COVER_SHOULDER_REACH)]
    poly_x(comp, cap_face, (62.0 - WALL) / 2.0, WALL, JOIN, [cov])
    return lid, cov


def build_front_corner_pair(comp):
    """Pair 4 (owner, 21 Aug): tail-end slices of the TUB and the TOP LID.

    "A lot is going on at the bottom side" - the front closure.  These two
    corners plus pair 3 (BottomLid + CurvedLid end slices) let the whole
    front stack be assembled in miniature: screw the lid slice to the tub
    slice, slide the cover slice home, drop the cap slice over the wall -
    and check that everything fits and CLOSES before any 280mm print.

    Both slices live in real shell coordinates, x +75..+140(+145 cap), the
    +X front corner.
    """
    oy = 560.0
    # ---- 4a: tub front corner --------------------------------------------
    def ty(v):                       # shell Y -> coupon Y
        return oy + (v - 107.5)
    tub = box(comp, 107.5, oy, 0, 65.0, 65.0, 3.0, NEW).bodies.item(0)
    tub.name = 'COUPON 4a TUB front corner (lid seat + cap screw + rail)'
    # side wall segment, ending at the real wall end face Y137
    box(comp, 138.5, ty(106.0), 3.0, 3.0, 62.0, 77.0, JOIN, [tub])
    # top rail behind the lid plane (Y134..137, Z72..80)
    box(comp, 106.0, ty(135.5), 72.0, 62.0, 3.0, 8.0, JOIN, [tub])
    # two lid-seat bosses + through pilots, real pattern positions
    for (bx, bz) in ((120.0, 72.0), (132.0, 44.0)):
        bw = 10.0 if bx == 132.0 else 9.0
        box(comp, bx, ty(132.5), bz - 4.0, bw, 9.0, 8.0, JOIN, [tub])
        cyl_y(comp, bx, bz, ty(132.5), INTERFACE.BOTTOM_LID_BOSS_PILOT_D,
              16.0, CUT, [tub])
    # cap-screw boss on the wall inner + horizontal pilot (row Y+85, Z72)
    box(comp, 131.0, ty(85.0), 66.0, 12.0, 12.0, 12.0, JOIN, [tub])
    cyl_x(comp, ty(85.0), 72.0, 138.5, INTERFACE.CAP_BOSS_PILOT_D,
          30.0, CUT, [tub])

    # ---- 4b: top-lid front corner ----------------------------------------
    oy2 = oy + 110.0
    def cy2(v):                      # cap print Y -> coupon Y
        return oy2 + (v - 107.5)
    LW_HALF, inner_half = 143.0, 140.5
    cap = box(comp, 110.0, cy2(107.5), 0, 70.0, 70.0, 3.0, NEW).bodies.item(0)
    cap.name = 'COUPON 4b TOP LID front corner (skirt + seat pad + chamfer)'
    # side skirt segment (print z3..55) with the seat pad + counterbore +
    # hole at row Y85, print z48 - drops over 4a's wall with the real 0.5
    box(comp, (inner_half + LW_HALF) / 2.0, cy2(105.0), 3.0,
        LW_HALF - inner_half, 65.0, 52.0, JOIN, [cap])
    pad_h = INTERFACE.CAP_SEAT_PAD_H
    cyl_x(comp, cy2(85.0), 48.0, LW_HALF + (pad_h - 1) / 2.0,
          INTERFACE.M3_SEAT_PAD_D, pad_h + 1, JOIN, [cap])
    cyl_x(comp, cy2(85.0), 48.0, inner_half + 1.5, 3.4, 6.0, CUT, [cap])
    cyl_x(comp, cy2(85.0), 48.0, LW_HALF + pad_h,
          INTERFACE.M3_SEAT_CBORE_D, 2 * pad_h, CUT, [cap])
    # shortened FRONT wall segment (print z3..36.5) + the roof edge the
    # cover's shoulder must meet with its 0.3mm shadow line
    box(comp, 110.0, cy2(141.75), 3.0, 70.0, 2.5, 33.5, JOIN, [cap])
    # lead-in chamfer on the side skirt's top inner edge (stepped, as pair 2)
    ch = INTERFACE.CAP_LEADIN_CH
    box(comp, inner_half + ch / 2.0, cy2(105.0), 55.0 - ch,
        ch, 65.0, ch + 0.01, CUT, [cap])
    return tub, cap


VERSION = ('v2: FOUR coupon pairs - cap ring, cap wall section, rail-lock '
           'slices (now WITH the curved shoulder), and the NEW front-corner '
           'set of the tub + top lid, so the whole busy bottom-end stack '
           'can be test-assembled before any 280mm print / interface {}'
           .format(INTERFACE.INTERFACE_VERSION))


def clear_old(root):
    old = [b for b in root.bRepBodies if b.name.startswith('COUPON')]
    for b in old:
        try:
            b.deleteMe()
        except Exception as e:
            SKIPPED.append('clear: {}'.format(e))
    return len(old)


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('Open a Fusion Design and run again.')
            return
        try:
            design.fusionUnitsManager.distanceDisplayUnits = \
                adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        except Exception:
            pass
        del SKIPPED[:]
        removed = clear_old(design.rootComponent)
        build_cap_fit_rings(design.rootComponent)
        build_cap_wall_section(design.rootComponent)
        build_rail_lock_sections(design.rootComponent)
        build_front_corner_pair(design.rootComponent)
        app.activeViewport.fit()
        ui.messageBox(
            'FIR_FitCoupons {} built.\nCleared {} old body(ies).\n\n'
            'PASS CRITERIA: 1) cap ring slides fully onto tub ring by hand and '
            'comes off; 2) wall section clicks and takes an M3 that reopens 5x; '
            '3) cover slice slides to a FLUSH stop, clicks the nub, screws; '
            'flipped left-for-right it must STAND PROUD on the key block; '
            '4) FRONT CORNER SET: screw 3a onto 4a (two M3s into the real '
            'bosses), slide 3b home on 3a, drop 4b over 4a\'s wall - the cap '
            'screw must line up at Z72 and the cover shoulder must land on '
            '4b\'s roof edge with a hairline, nothing forcing, nothing loose.{}'
            .format(VERSION, removed,
                    ('\nSkipped:\n - ' + '\n - '.join(SKIPPED)) if SKIPPED else ''))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_FitCoupons failed:\n{}'.format(traceback.format_exc()))
