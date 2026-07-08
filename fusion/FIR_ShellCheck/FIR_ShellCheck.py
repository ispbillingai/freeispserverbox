# FIR_ShellCheck.py - Autodesk Fusion 360 script
# REAL-PARTS ALIGNMENT ASSEMBLY (see-inside). Builds the actual parts in their assembled spots:
#   1 SHELL  - the real FIR_Shell tub (walls, 951+PoE cradles, AC/DC divider, lid seat + 6 bolt
#              bosses, keyholes, cable run)                                        -> transparent
#   2 LID    - the real FIR_BottomLid (all ports, holding frames, 6 bolts, shelf, top groove),
#              built in lid coords then ROTATED onto the front opening              -> transparent
#   3 951    - the MikroTik with its measured ports, seated in the cradle          -> SOLID
#   4 TOP CAP - the deep-cap top lid ASSEMBLED on the tub (front-open side at the front; the
#              bottom lid's 3mm top build-out closes that edge). CAP_LIFT hovers it -> transparent
# So you can see: 951 ports <-> lid ports <-> cradle + bolts all line up. Run ALONE in a fresh design.

import adsk.core, adsk.fusion, adsk.cam, traceback, math

# ---- shell frame (FIR_Shell) ----
BOX_W, BOX_D, BOX_H = 280.0, 280.0, 80.0
WALL, FLOOR, CORNER_R, HALF, FRONT_Y = 3.0, 3.0, 10.0, 140.0, 137.0
MIK_W, MIK_D, MIK_H, MIK_CX, ST_H = 114.0, 139.0, 29.0, 78.0, 3.5
POE_W, POE_D, POE_H, POE_CX = 100.0, 100.0, 28.0, -85.0
EXT_CY, DIV_Y, PLATE_TH = -110.0, -82.0, 3.0
EXT_W, EXT_D, EXT_H, EXT_FRONT_RETAINER_H = 240.0, 47.0, 29.0, 29.0
# ---- lid frame (FIR_BottomLid) ----
PW, PH, PT, SW_CX, MIK_X0, BASE = 280.0, 80.0, 3.0, 85.0, -135.0, 6.5
# ---- top cap (FIR_Shell build_top_lid, assembled) ----
CAP_LIFT = 0.0        # 0 = fully seated. Set to e.g. 40.0 to HOVER the cap above the tub and
                      # watch how it drops on (open edge stays at the front).
# ---- 951 measured ports (x from left edge, z from base) ----
MPORTS = [('c', 11, 15, 6.5, 0), ('c', 19, 10, 2.5, 0), ('r', 25, 9.5, 4, 3), ('r', 33, 9.5, 4, 3),
          ('r', 44.5, 16, 13.5, 12.5), ('r', 58.5, 16, 13.5, 12.5), ('r', 72.5, 16, 13.5, 12.5),
          ('r', 86.5, 16, 13.5, 12.5), ('r', 100.5, 16, 13.5, 12.5)]

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
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(adsk.core.ValueInput.createByReal(mm(z0)))
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
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(d / 2.0))
    return _ext(comp, sk.profiles.item(0), z0, sz, op, parts)


def cyl_y(comp, cx, cz, ycenter, d, span, op, parts=None):
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cz), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(ycenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(adsk.core.ValueInput.createByReal(mm(ycenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def box_y(comp, cx, cz, ycenter, sx, sz, span, op, parts=None):
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.sketchCurves.sketchLines.addCenterPointRectangle(
        adsk.core.Point3D.create(mm(cx), mm(cz), 0),
        adsk.core.Point3D.create(mm(cx + sx / 2.0), mm(cz + sz / 2.0), 0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(ycenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(adsk.core.ValueInput.createByReal(mm(ycenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def cyl_x(comp, cy, cz, xcenter, d, span, op, parts=None):
    # cylinder running along X (circle on yZ plane), SYMMETRIC about xcenter - side-wall bolt pilots
    sk = comp.sketches.add(comp.yZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(mm(cy), mm(cz), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(xcenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(adsk.core.ValueInput.createByReal(mm(xcenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def yport(comp, body, cx, cz, kind, a, b, y_face, span):
    # robust port cut into a +Y face: sketch on an offset plane AT the face, symmetric extrude
    try:
        pin = comp.constructionPlanes.createInput()
        pin.setByOffset(comp.xZConstructionPlane, adsk.core.ValueInput.createByReal(mm(y_face)))
        plane = comp.constructionPlanes.add(pin)
        sk = comp.sketches.add(plane)
        if kind == 'c':
            sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cz), 0), mm(a / 2.0))
        else:
            sk.sketchCurves.sketchLines.addCenterPointRectangle(
                adsk.core.Point3D.create(mm(cx), mm(cz), 0),
                adsk.core.Point3D.create(mm(cx + a / 2.0), mm(cz + b / 2.0), 0))
        ei = comp.features.extrudeFeatures.createInput(sk.profiles.item(0), CUT)
        ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
        ei.participantBodies = [body]
        comp.features.extrudeFeatures.add(ei)
    except Exception as e:
        SKIPPED.append('yport: {}'.format(e))


def fillet_vertical(comp, body, r):
    try:
        coll = adsk.core.ObjectCollection.create()
        for e in body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                v = g.startPoint.vectorTo(g.endPoint); v.normalize()
                if abs(v.z) > 0.99:
                    coll.add(e)
        if coll.count:
            fi = comp.features.filletFeatures.createInput()
            fi.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
            comp.features.filletFeatures.add(fi)
    except Exception as e:
        SKIPPED.append('fillet: {}'.format(e))


def frame_grip(comp, plate, xl, xr, yb, yt, depth, wt):
    # walls clamped to |x| <= 136.7 so they clear the tub side walls (inner 137) - mirrors FIR_BottomLid
    clr = 0.5
    lim = PW / 2.0 - 3.3
    fh = (yt - yb) + 2 * clr
    fx0 = max(xl - clr - wt, -lim); fx1 = min(xr + clr + wt, lim)
    box(comp, (fx0 + fx1) / 2, yb - clr - wt / 2, -depth, fx1 - fx0, wt, depth, JOIN, [plate])
    box(comp, (fx0 + fx1) / 2, yt + clr + wt / 2, -depth, fx1 - fx0, wt, depth, JOIN, [plate])
    box(comp, (fx0 + xl - clr) / 2, (yb + yt) / 2, -depth, (xl - clr) - fx0, fh, depth, JOIN, [plate])
    box(comp, (xr + clr + fx1) / 2, (yb + yt) / 2, -depth, fx1 - (xr + clr), fh, depth, JOIN, [plate])


def cradle_grip(comp, sh, cx, cy, w, d, h):
    wt, clr, P, HK = 2.5, 0.5, 14.0, 4.0
    hw, hd = w / 2 + clr, d / 2 + clr
    for px in (cx - hw + P / 2, cx, cx + hw - P / 2):
        box(comp, px, cy - hd - wt / 2, FLOOR, P, wt, h + 4, JOIN, [sh])
        box(comp, px, cy - hd + HK / 2, FLOOR + h, P, wt + HK, 3, JOIN, [sh])
    fyc = cy + hd - 11 - P / 2                # front arms 11mm back: the lid frames own Y127-137
    for s in (-1, 1):
        box(comp, cx + s * (hw + wt / 2), cy - hd + P / 2, FLOOR, wt, P, h, JOIN, [sh])
        box(comp, cx + s * (hw + wt / 2), fyc, FLOOR, wt, P, h + 5, JOIN, [sh])
        box(comp, cx + s * (hw - 0.75), fyc, FLOOR + h, HK + wt, P, 3, JOIN, [sh])
        box(comp, cx + s * w / 4, cy - hd + 2, FLOOR, 3, 3, 3, JOIN, [sh])


def set_opacity(body, o):
    try:
        body.opacity = o
    except Exception as e:
        SKIPPED.append('opacity: {}'.format(e))


def build_shell(comp):
    # FRONT OPEN TO Y137 (mirrors FIR_Shell v17): the lid fills the slab Y137-140, so floor +
    # side walls stop at 137, the front lip is gone and the top rail sits BEHIND the lid plane.
    sh = box(comp, 0, -WALL / 2, 0, BOX_W, BOX_D - WALL, FLOOR, NEW).bodies.item(0)
    sh.name = '1 SHELL (see-through)'
    fillet_vertical(comp, sh, CORNER_R)
    box(comp, -HALF + WALL / 2, -WALL / 2, FLOOR, WALL, BOX_D - WALL, BOX_H - FLOOR, JOIN, [sh])
    box(comp, HALF - WALL / 2, -WALL / 2, FLOOR, WALL, BOX_D - WALL, BOX_H - FLOOR, JOIN, [sh])
    box(comp, 0, -HALF + WALL / 2, FLOOR, BOX_W, WALL, BOX_H - FLOOR, JOIN, [sh])
    box(comp, 0, FRONT_Y - 1.5, BOX_H - 8, BOX_W - 2 * WALL, 3, 8, JOIN, [sh])   # top rail (Y134-137)
    # (divider frame removed - clean slate)
    m_back = FRONT_Y - 0.5                             # devices right against the lid inside
    for sx in (MIK_CX - (MIK_W / 2 - 6), MIK_CX + (MIK_W / 2 - 6)):
        for sy in (m_back - 14, m_back - MIK_D + 8):   # front row 14 back: clear of the lid frames
            cyl(comp, sx, sy, FLOOR, 7, ST_H, JOIN, [sh])
    cradle_grip(comp, sh, MIK_CX, m_back - MIK_D / 2, MIK_W, MIK_D, ST_H + MIK_H)
    for sx in (POE_CX - (POE_W / 2 - 6), POE_CX + (POE_W / 2 - 6)):
        for sy in (m_back - 14, m_back - POE_D + 8):   # front row 14 back: clear of the lid frames
            cyl(comp, sx, sy, FLOOR, 7, ST_H, JOIN, [sh])
    cradle_grip(comp, sh, POE_CX, m_back - POE_D / 2, POE_W, POE_D, ST_H + POE_H)
    box(comp, 17, EXT_CY + EXT_D / 2 + 1.5, FLOOR, EXT_W, WALL, EXT_FRONT_RETAINER_H, JOIN, [sh])
    for kx in (-60, 60):
        cyl_y(comp, kx, BOX_H - 24, -HALF + 1, 11, WALL + 2, CUT, [sh])
        box_y(comp, kx, BOX_H - 33, -HALF + 1, 5, 18, WALL + 2, CUT, [sh])
    for sx in (-HALF + WALL, HALF - WALL):             # top-lid side bosses (synced: horizontal pilots)
        s = 1.0 if sx > 0 else -1.0
        for sy in (-75, 0, 75):
            box(comp, sx - s * 6, sy, BOX_H - 14, 12, 12, 12, JOIN, [sh])
            cyl_x(comp, sy, BOX_H - 8, sx, 2.6, 30, CUT, [sh])
    for (bx, bz) in ((-120, 72), (120, 72), (-40, 72), (40, 72), (-132, 44), (132, 44)):
        bw = 10 if abs(bx) == 132 else 9               # ±132 widened to merge with the side wall
        box(comp, bx, FRONT_Y - 4.5, bz - 4, bw, 9, 8, JOIN, [sh])
        cyl_y(comp, bx, bz, FRONT_Y - 4.5, 2.6, 16, CUT, [sh])
    return sh


def build_lid_local(comp):
    plate = box(comp, 0, PH / 2, 0, PW, PH, PT, NEW).bodies.item(0)
    plate.name = '2 BOTTOM LID (see-through)'
    fillet_vertical(comp, plate, 6.0)

    def hole(cx, cy, shape, a, b):
        if shape == 'c':
            cyl(comp, cx, cy, -1, a, PT + 2, CUT, [plate])
        else:
            box(comp, cx, cy, -1, a, b, PT + 2, CUT, [plate])

    hole(MIK_X0 + 11, BASE + 15, 'c', 6.5, 0); hole(MIK_X0 + 19, BASE + 10, 'c', 2.5, 0)
    hole(MIK_X0 + 25, BASE + 9.5, 'r', 4, 3); hole(MIK_X0 + 33, BASE + 9.5, 'r', 4, 3)
    for rx in (44.5, 58.5, 72.5, 86.5, 100.5):
        hole(MIK_X0 + rx, BASE + 16, 'r', 13.5, 12.5)
    hole(MIK_X0 + 23, 42, 'c', 9, 0)
    for i in range(5):
        hole(SW_CX + (i - 2) * 16, BASE + 16, 'r', 13.5, 12.5)
    hole(-8, BASE + 18, 'r', 19, 13); hole(-3, BASE + 8, 'c', 7.0, 0); hole(-14, BASE + 8, 'c', 10.0, 0)
    frame_grip(comp, plate, MIK_X0, MIK_X0 + 114, BASE, BASE + 29, 10, 2.0)
    frame_grip(comp, plate, SW_CX - 50, SW_CX + 50, BASE, BASE + 28, 10, 2.0)
    for (bx, by) in ((-120, 72), (-40, 72), (40, 72), (120, 72), (-132, 44), (132, 44)):
        cyl(comp, bx, by, -1, 3.5, PT + 2, CUT, [plate])
        cyl(comp, bx, by, PT - 2.2, 6.5, 3, CUT, [plate])
    box(comp, 0, 1.5, PT, PW, 3, 65, JOIN, [plate])                  # 65mm shelf
    for rx in (-133, 133):
        box(comp, rx, 5.5, PT, 4, 5, 62, JOIN, [plate])             # SLIDE-GUIDE RAILS (cover slides on these)
    for sx in (-125, 125):
        box(comp, sx, 9.5, PT + 54, 7, 13, 8, JOIN, [plate])        # lock-screw bosses (0.5 clear of cover face)
        cyl(comp, sx, 12, PT + 54, 2.6, 8, CUT, [plate])
    for tx in (-130, -40, 40, 130):
        box(comp, tx, PH - 2, 0, 10, 4, PT, JOIN, [plate])          # clip tabs
    box(comp, 0, PH + 1.5, 0, PW, 3, PT, JOIN, [plate])             # top build-out
    box(comp, 0, PH + 1.5, PT - 1, 250, 1.6, 2, CUT, [plate])       # top groove
    return plate


def place_lid_on_front(comp, body):
    # rotate the lid (lid coords) onto the tub front face: 180 deg about (0,1,1) + move +Y 137
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.pi, adsk.core.Vector3D.create(0, 1, 1), adsk.core.Point3D.create(0, 0, 0))
    m.translation = adsk.core.Vector3D.create(0, mm(FRONT_Y), 0)
    coll = adsk.core.ObjectCollection.create(); coll.add(body)
    mi = comp.features.moveFeatures.createInput(coll, m)
    comp.features.moveFeatures.add(mi)


def build_top_cap(comp):
    # The TALL-CAP TOP LID in its ASSEMBLED spot (mirrors FIR_Shell v19). CLOSED BOX = 120mm
    # (12cm, per the plan's 300x250x120 reference + the original 80+50-10 design): the cap
    # overlaps the tub walls 15mm (skirt Z65-80, tub outer 140 / skirt inner 140.5 = 0.5 slide
    # clearance) then RISES to the plate at Z117-120, adding 37mm of headroom for the adapters
    # + the hanging brain. Side BOLTS mid-overlap: cap holes @Z72 <-> tub bosses Z66-78 /
    # pilots Z72. The FRONT wall only spans Z83.5-117: below it the bottom lid's build-out
    # (to Z83) + the cover top (Z83) close the front - the cover slides UNDER it, 0.5mm clear.
    zl = CAP_LIFT
    oh, ih = 143.0, 140.5                        # outer / inner half-width (286 / 281 cavity)
    cap = box(comp, 0, 0, 117 + zl, 2 * oh, 2 * oh, 3, NEW).bodies.item(0)   # top plate Z117-120
    cap.name = '4 TOP CAP (see-through)'
    for sxs in (-1, 1):                                                  # side skirt walls Z65-117
        box(comp, sxs * (oh - 1.25), 0, 65 + zl, 2.5, 2 * oh, 52, JOIN, [cap])
    box(comp, 0, -oh + 1.25, 65 + zl, 2 * oh, 2.5, 52, JOIN, [cap])      # back wall Z65-117
    box(comp, 0, oh - 1.25, 83.5 + zl, 2 * ih, 2.5, 33.5, JOIN, [cap])   # SHORT front wall Z83.5-117
    for dx, dy in ((1, 0), (-1, 0), (0, -1)):                            # 0.3mm crush click ribs
        box(comp, dx * (ih + 0.2), dy * (ih + 0.2), 73 + zl,
            2 if dx else 20, 20 if dx else 2, 2.0, JOIN, [cap])
    for sxs in (-1, 1):                                                  # 6 side-bolt clearance holes
        for byy in (-75, 0, 75):                                         # line up with the tub pilots @ Z72
            cyl_x(comp, byy, 72 + zl, sxs * (oh - 1), 3.4, 6, CUT, [cap])
    for bx in (-58.5, 58.5):                                             # brain bolt bosses under the plate
        for byo in (-50, 50):
            cyl(comp, bx, byo, 105 + zl, 7, 12, JOIN, [cap])
            cyl(comp, bx, byo, 104 + zl, 2.6, 13, CUT, [cap])
    return cap


def build_mikrotik(comp):
    m_back = FRONT_Y - 0.5                             # 951 port face right against the lid inside
    oy = m_back - MIK_D / 2.0
    dev = box(comp, MIK_CX, oy, FLOOR + ST_H, MIK_W, MIK_D, MIK_H, NEW).bodies.item(0)
    dev.name = '3 MikroTik 951'
    for (k, x, z, a, b) in MPORTS:
        cx = MIK_CX - (-MIK_W / 2.0 + x)                 # flipped in X to match the lid
        yport(comp, dev, cx, FLOOR + ST_H + z, k, a, b, m_back, 8.0)


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
            design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        except Exception:
            pass
        del SKIPPED[:]
        comp = design.rootComponent
        sh = build_shell(comp); set_opacity(sh, 0.30)
        lid = build_lid_local(comp); place_lid_on_front(comp, lid); set_opacity(lid, 0.30)
        build_mikrotik(comp)
        cap = build_top_cap(comp); set_opacity(cap, 0.30)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Real-parts check built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_ShellCheck failed:\n{}'.format(traceback.format_exc()))
