# FIR_ModuleOpen.py - Autodesk Fusion 360 script
# REAL-SIZE OPEN module chassis (no cover) for bench build + test. A shallow open
# tray with bolt-down standoffs already in place for every board, a reed clip,
# cable tie-downs + exit notch, and mounting ears to fix it into the big box.
# Print this, bolt your boards on, wire it up, test. Cover comes later.
#
#  >>> Standoff spacings = plan board sizes - VERIFY real boards with calipers. <<<

import adsk.core, adsk.fusion, adsk.cam, traceback

OUT_X, OUT_Y = 135.0, 120.0
WALL, FLOOR_TH, WALL_H = 2.5, 2.5, 9.0
IN_X, IN_Y = OUT_X - 2 * WALL, OUT_Y - 2 * WALL
CORNER_R = 8.0
TOP = FLOOR_TH + WALL_H

# board bolt-points:  name, w, l, h, cx, cy, posts
COMPONENTS = [
    ('ESP32-S3',     70.0, 26.0, 13.0,  0.0,   6.0, 4),
    ('LM2596 buck',  52.0, 27.0, 15.0,  0.0, -24.0, 4),
    ('18650 holder', 75.0, 20.0, 20.0,  0.0,  44.0, 2),
    ('TP4056',       26.0, 17.0,  6.0,  0.0, -46.0, 2),
    ('MPU-6050',     22.0, 17.0,  4.0, 48.0,  28.0, 2),
]
STANDOFF_OD, STANDOFF_H, STANDOFF_PILOT = 5.5, 5.0, 2.2
REED_C = (-50.0, 47.0)

EAR_W, EAR_L, EAR_T, EAR_HOLE = 18.0, 16.0, 4.0, 4.2     # mounting ears (bolt into box)
FLOOR_HOLE = 4.2                                          # alt: bolt chassis to a surface
CABLE_NOTCH_X, CABLE_NOTCH_W = 35.0, 16.0
SHOW_PARTS = False        # placeholders OFF - flip to True only to check board fit

CM = 0.1
def mm(v):
    return v * CM

NEW  = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation
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
        SKIPPED.append('corner fillet: {}'.format(e))


def standoffs(comp, body, cx, cy, w, l, n):
    pts = [(-1, -1), (1, -1), (-1, 1), (1, 1)] if n >= 4 else [(-1, 0), (1, 0)]
    for (sx, sy) in pts:
        x, y = cx + sx * (w / 2 - 3.5), cy + sy * (l / 2 - 3.5)
        cyl(comp, x, y, FLOOR_TH, STANDOFF_OD, STANDOFF_H, JOIN, [body])
        cyl(comp, x, y, FLOOR_TH, STANDOFF_PILOT, STANDOFF_H + 1, CUT, [body])


def build_chassis(comp):
    base = box(comp, 0, 0, 0, OUT_X, OUT_Y, TOP, NEW).bodies.item(0)
    base.name = 'FIR Module Open'
    fillet_vertical(comp, base, CORNER_R)
    box(comp, 0, 0, FLOOR_TH, IN_X, IN_Y, WALL_H + 1, CUT, [base])     # open-top cavity

    # board bolt-point standoffs
    for (name, w, l, h, cx, cy, n) in COMPONENTS:
        standoffs(comp, base, cx, cy, w, l, n)

    # reed clip on the top edge
    rx, ry = REED_C
    box(comp, rx - 3, ry, FLOOR_TH, 2, 8, 9, JOIN, [base])
    box(comp, rx + 3, ry, FLOOR_TH, 2, 8, 9, JOIN, [base])

    # cable tie-down + exit notch in the back wall
    box(comp, CABLE_NOTCH_X - 5, -8, FLOOR_TH, 3, 3, 6, JOIN, [base])
    box(comp, CABLE_NOTCH_X + 5, -8, FLOOR_TH, 3, 3, 6, JOIN, [base])
    box(comp, CABLE_NOTCH_X, -8, FLOOR_TH + 4, 13, 3, 2, JOIN, [base])
    box(comp, CABLE_NOTCH_X, -OUT_Y / 2, FLOOR_TH, CABLE_NOTCH_W, WALL * 3, WALL_H, CUT, [base])

    # mounting ears (bolt the chassis into the big box)
    for side in (1, -1):
        box(comp, side * (OUT_X / 2 + EAR_W / 2 - 1), 0, 0, EAR_W, EAR_L, EAR_T, JOIN, [base])
        cyl(comp, side * (OUT_X / 2 + EAR_W / 2 + 2), 0, -1, EAR_HOLE, EAR_T + 2, CUT, [base])

    # floor bolt holes (alt fixing to a bench/plate)
    for sx in (-(IN_X / 2 - 8), (IN_X / 2 - 8)):
        cyl(comp, sx, -(IN_Y / 2 - 8), -1, FLOOR_HOLE, FLOOR_TH + 2, CUT, [base])
    return base


def build_parts(comp):
    sz_top = FLOOR_TH + STANDOFF_H
    for (name, w, l, h, cx, cy, n) in COMPONENTS:
        b = box(comp, cx, cy, sz_top, w, l, h, NEW).bodies.item(0)
        b.name = 'PART: ' + name


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
        build_chassis(design.rootComponent)
        if SHOW_PARTS:
            build_parts(design.rootComponent)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Open module built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_ModuleOpen failed:\n{}'.format(traceback.format_exc()))
