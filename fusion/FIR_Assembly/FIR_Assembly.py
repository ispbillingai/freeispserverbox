# FIR_Assembly.py - Autodesk Fusion 360 script
# ASSEMBLY VIEW: the real BOTTOM LID + the COVER, each in its true assembled position so you can
# see the finished look. Two separate bodies. The cover is built flipped/shifted so it sits ON the
# shelf and slides home against the lid's outside face (rails -> caps, bulges -> recesses line up).
# Run ALONE in a fresh design.

import adsk.core, adsk.fusion, adsk.cam, traceback

# ---- bottom lid (FIR_BottomLid coords: outside face +Z, shelf sticks out +Z) ----
PW, PH, PT = 280.0, 80.0, 3.0
SW_CX = 85.0
MIK_X0 = -135.0
BASE = 6.5

# ---- cover (FIR_CurvedLid coords) ----
LEN, HEIGHT, DEPTH = 280.0, 80.0, 65.0
WALL = 2.5
SKIN = 0.55
HOLE_D = 7.0
PWR_D = 7.0
NOTCH_H = 7.0
RJ45_X = [-90.5, -76.5, -62.5, -48.5, -34.5, 53.0, 69.0, 85.0, 101.0, 117.0]
CLR = 0.4
RAIL_X = 133.0
SHELF_TOP_Y = -HEIGHT / 2.0
RAIL_TOP_Y = SHELF_TOP_Y + 5.0
TZ0, TZ1 = WALL, DEPTH - 2.0                 # TZ0=WALL: catch grows off the face inner (3.0 floated 0.5mm)

# cover -> assembly transform: sit on the shelf (Y +43), flip Z about the shelf front (Z' = 68 - Z)
YS = 43.0
FZ = PT + 65.0                                   # shelf front edge = 68
EXPLODE = 0.0                                    # set to e.g. 35 to LIFT the cover off and see the joint
COVER_OPACITY = 0.35                             # cover is see-through so you can watch rails meet caps

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


def cyl_x(comp, cy, cz, x0, d, length, op, parts=None):
    sk = comp.sketches.add(comp.yZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cy), mm(cz), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(mm(x0)))
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(length)))
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


# cover helpers: same call signature, transformed into assembly coords (+EXPLODE lifts it off)
def cbox(comp, cx, cy, z0, sx, sy, sz, op, parts=None):
    return box(comp, cx, cy + YS + EXPLODE, FZ - z0 - sz, sx, sy, sz, op, parts)


def ccyl(comp, cx, cy, z0, d, sz, op, parts=None):
    return cyl(comp, cx, cy + YS + EXPLODE, FZ - z0 - sz, d, sz, op, parts)


def fillet_vertical(comp, body, r):
    try:
        coll = adsk.core.ObjectCollection.create()
        for e in body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                v = g.startPoint.vectorTo(g.endPoint)
                v.normalize()
                if abs(v.z) > 0.99:
                    coll.add(e)
        if coll.count:
            fi = comp.features.filletFeatures.createInput()
            fi.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
            comp.features.filletFeatures.add(fi)
    except Exception as e:
        SKIPPED.append('fillet: {}'.format(e))


def frame_grip(comp, plate, xl, xr, yb, yt, depth, wt):
    # walls clamped to |x| <= 136.7 so they clear the tub side walls (inner face 137) - see FIR_BottomLid
    clr = 0.5
    lim = PW / 2.0 - 3.3
    fh = (yt - yb) + 2 * clr
    fx0 = max(xl - clr - wt, -lim)
    fx1 = min(xr + clr + wt, lim)
    box(comp, (fx0 + fx1) / 2, yb - clr - wt / 2, -depth, fx1 - fx0, wt, depth, JOIN, [plate])
    box(comp, (fx0 + fx1) / 2, yt + clr + wt / 2, -depth, fx1 - fx0, wt, depth, JOIN, [plate])
    box(comp, (fx0 + xl - clr) / 2, (yb + yt) / 2, -depth, (xl - clr) - fx0, fh, depth, JOIN, [plate])
    box(comp, (xr + clr + fx1) / 2, (yb + yt) / 2, -depth, fx1 - (xr + clr), fh, depth, JOIN, [plate])


def build_lid(comp):
    plate = box(comp, 0, PH / 2, 0, PW, PH, PT, NEW).bodies.item(0)
    plate.name = 'BOTTOM LID'
    fillet_vertical(comp, plate, 6.0)

    def hole(cx, cy, shape, a, b):
        if shape == 'c':
            cyl(comp, cx, cy, -1, a, PT + 2, CUT, [plate])
        else:
            box(comp, cx, cy, -1, a, b, PT + 2, CUT, [plate])

    hole(MIK_X0 + 11, BASE + 15, 'c', 6.5, 0)
    hole(MIK_X0 + 19, BASE + 10, 'c', 2.5, 0)
    hole(MIK_X0 + 25, BASE + 9.5, 'r', 4, 3)
    hole(MIK_X0 + 33, BASE + 9.5, 'r', 4, 3)
    for rx in (44.5, 58.5, 72.5, 86.5, 100.5):
        hole(MIK_X0 + rx, BASE + 16, 'r', 13.5, 12.5)
    hole(MIK_X0 + 23, 42, 'c', 9, 0)                    # pass-through (synced: moved clear of the side bolt)
    for i in range(5):
        hole(SW_CX + (i - 2) * 16, BASE + 16, 'r', 13.5, 12.5)
    hole(-8, BASE + 18, 'r', 19, 13)
    hole(-3, BASE + 8, 'c', 7.0, 0)                     # power jack (synced: moved LEFT below the switch)
    hole(-14, BASE + 8, 'c', 10.0, 0)                   # 10mm cable (synced: moved LEFT below the switch)

    frame_grip(comp, plate, MIK_X0, MIK_X0 + 114, BASE, BASE + 29, 10, 2.0)
    frame_grip(comp, plate, SW_CX - 50, SW_CX + 50, BASE, BASE + 28, 10, 2.0)
    for tx in (-130, -40, 40, 130):
        box(comp, tx, PH - 2, 0, 10, 4, PT, JOIN, [plate])
    for (bx, by) in ((-120, 72), (-40, 72), (40, 72), (120, 72), (-132, 44), (132, 44)):  # synced: side pair at ±132
        cyl(comp, bx, by, -1, 3.5, PT + 2, CUT, [plate])
        cyl(comp, bx, by, PT - 2.2, 6.5, 3, CUT, [plate])
    box(comp, 0, 1.5, PT, PW, 3, 65, JOIN, [plate])                       # shelf
    for rx in (-133, 133):
        box(comp, rx, 5.5, PT, 4, 5, 62, JOIN, [plate])                   # rail (slide guide)
    for sx in (-125, 125):
        box(comp, sx, 9.5, PT + 54, 7, 13, 8, JOIN, [plate])              # lock-screw boss (stops 0.5 clear of the cover face)
        cyl(comp, sx, 12, PT + 54, 2.6, 8, CUT, [plate])                  # pilot hole
    box(comp, 0, PH + 1.5, 0, PW, 3, PT, JOIN, [plate])                   # TOP build-out 3mm
    box(comp, 0, PH + 1.5, PT - 1, 250, 1.6, 2, CUT, [plate])             # TOP 1mm groove
    return plate


def build_cover(comp):
    cf = cbox(comp, 0, 0, 0, LEN, HEIGHT, WALL, NEW).bodies.item(0)
    cf.name = 'COVER'
    depth = (WALL - SKIN) + 1
    bottom = -HEIGHT / 2.0
    top_y = bottom + NOTCH_H

    def notch(cx, w):
        cbox(comp, cx, (bottom - 2 + top_y) / 2.0, -1, w, (top_y - (bottom - 2)), depth, CUT, [cf])
        ccyl(comp, cx, top_y, -1, w, depth, CUT, [cf])

    for rx in RJ45_X:
        notch(rx, HOLE_D)
    notch(10, PWR_D)

    cbox(comp, 0, HEIGHT / 2 - WALL / 2, 0, LEN, WALL, DEPTH, JOIN, [cf])              # top wall
    cbox(comp, 0, 38.5, DEPTH, 250, 1.0, 1.0, JOIN, [cf])                              # top tongue centred in the lid groove
    for sx in (-LEN / 2 + WALL / 2, LEN / 2 - WALL / 2):
        cbox(comp, sx, 0, 0, WALL, HEIGHT, DEPTH, JOIN, [cf])                          # end walls

    half = 2.0 + 0.3                                  # rail half-width + 0.3mm SLIDING clearance
    RIBW = 1.6
    rib_cy = (SHELF_TOP_Y + RAIL_TOP_Y + 0.3) / 2.0
    rib_h = (RAIL_TOP_Y + 0.3) - SHELF_TOP_Y
    for side in (-1, 1):
        sx = side * RAIL_X
        cbox(comp, sx, RAIL_TOP_Y + 1.8, TZ0, 2 * (half + RIBW), 3.0, TZ1 - TZ0, JOIN, [cf])   # cap (guide)
        for off in (-(half + RIBW / 2.0), half + RIBW / 2.0):
            cbox(comp, sx + off, rib_cy, TZ0, RIBW, rib_h, TZ1 - TZ0, JOIN, [cf])               # guide ribs
    for sx in (-125, 125):
        ccyl(comp, sx, -31.0, -1, 3.4, WALL + 2, CUT, [cf])                                     # lock-screw clearance
    return cf


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
        comp = design.rootComponent
        build_lid(comp)
        cf = build_cover(comp)
        try:
            cf.opacity = COVER_OPACITY                 # make the cover see-through
        except Exception as e:
            SKIPPED.append('opacity: {}'.format(e))
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Assembly built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_Assembly failed:\n{}'.format(traceback.format_exc()))
