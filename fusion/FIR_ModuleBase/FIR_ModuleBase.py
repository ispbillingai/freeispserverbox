# FIR_ModuleBase.py - Autodesk Fusion 360 script
# The smart-module BASE (the box behind the faceplate). Holds the brain + power
# + alarm: ESP32-S3, LM2596 buck, 18650 + TP4056, MPU-6050 (motion), buzzer, and
# a reed-switch clip on the lid edge (tamper). Cable channel + single exit notch.
# 135 x 120 footprint = matches the faceplate and the tray's module bay.
# Thin walls/floor to stay light (filament budget). Single component, many bodies.
#
#  >>> Component sizes are plan defaults - VERIFY with calipers on arrival. <<<

import adsk.core, adsk.fusion, adsk.cam, traceback

# ---------------- BOX ----------------
IN_X, IN_Y, IN_Z = 130.0, 115.0, 40.0      # interior
WALL = 2.5
BASE_TH = 2.5                               # thin floor (weight)
OUT_X, OUT_Y = IN_X + 2 * WALL, IN_Y + 2 * WALL    # 135 x 120
OUT_Z = IN_Z + BASE_TH
CORNER_R = 6.0                              # rounded vertical corners (premium look)
BEVEL = 1.2                                 # bevelled top + bottom outer edges

# faceplate screw bosses (match FIR_Faceplate SCREW_XY)
SCREW_XY = [(-58.5, 50.0), (58.5, 50.0), (-58.5, -50.0), (58.5, -50.0)]
BOSS_D, BOSS_PILOT = 7.0, 2.6

STANDOFF_OD, STANDOFF_H, STANDOFF_PILOT = 5.5, 4.0, 2.2

# brain + power boards:  name, w, l, h, cx, cy, posts
COMPONENTS = [
    ('ESP32-S3',     70.0, 26.0, 13.0,  0.0,   5.0, 4),
    ('LM2596 buck',  52.0, 27.0, 15.0,  0.0, -25.0, 4),
    ('18650 holder', 75.0, 20.0, 20.0,  0.0,  45.0, 2),
    ('TP4056',       26.0, 17.0,  6.0,  0.0, -48.0, 2),
    ('MPU-6050',     22.0, 17.0,  4.0, 49.0,  30.0, 2),
]
# ---- ALARM SENSORS (the loud 12V siren lives in the BIG box, not here) ----
REED_C = (-52.0, 49.0)             # tamper reed on lid edge (MPU motion is in COMPONENTS;
                                   # ESP drives the big-box siren via a wire/connector)

CABLE_NOTCH_X, CABLE_NOTCH_W = 40.0, 16.0                   # single cable bundle exit
SHOW_PARTS = True

CM = 0.1
def mm(v):
    return v * CM

NEW  = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation

SKIPPED = []


def _extrude(comp, prof, z0, sz, op, parts):
    feats = comp.features.extrudeFeatures
    ei = feats.createInput(prof, op)
    if abs(z0) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(z0)))
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(sz)))
    if parts:
        ei.participantBodies = parts
    return feats.add(ei)


def box(comp, cx, cy, z0, sx, sy, sz, op, parts=None):
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchLines.addCenterPointRectangle(
        adsk.core.Point3D.create(mm(cx), mm(cy), 0),
        adsk.core.Point3D.create(mm(cx + sx / 2.0), mm(cy + sy / 2.0), 0))
    return _extrude(comp, sk.profiles.item(0), z0, sz, op, parts)


def cyl(comp, cx, cy, z0, d, sz, op, parts=None):
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(d / 2.0))
    return _extrude(comp, sk.profiles.item(0), z0, sz, op, parts)


def fillet_vertical(comp, body, r):
    # round the 4 outer vertical corners (call while the box is still a clean solid)
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
            fin = comp.features.filletFeatures.createInput()
            fin.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
            comp.features.filletFeatures.add(fin)
    except Exception as e:
        SKIPPED.append('corner fillet: {}'.format(e))


def bevel_outer(comp, body, c, z_target, nz):
    # chamfer the outer perimeter of the top rim (nz=+1) or bottom (nz=-1)
    try:
        face, best = None, -1.0
        for f in body.faces:
            g = f.geometry
            if isinstance(g, adsk.core.Plane) and (g.normal.z * nz) > 0.99:
                bb = f.boundingBox
                if abs((bb.minPoint.z + bb.maxPoint.z) / 2 - mm(z_target)) < mm(0.05):
                    if f.area > best:
                        best, face = f.area, f
        if not face:
            return
        coll = adsk.core.ObjectCollection.create()
        for loop in face.loops:
            if loop.isOuter:
                for e in loop.edges:
                    coll.add(e)
        if not coll.count:
            return
        cf = comp.features.chamferFeatures
        ci = cf.createInput2()
        ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            coll, adsk.core.ValueInput.createByReal(mm(c)), False)
        cf.add(ci)
    except Exception as e:
        SKIPPED.append('bevel: {}'.format(e))


def standoffs(comp, body, cx, cy, w, l, n):
    if n >= 4:
        pts = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    else:
        pts = [(-1, 0), (1, 0)]
    for (sx, sy) in pts:
        x, y = cx + sx * (w / 2 - 3.5), cy + sy * (l / 2 - 3.5)
        cyl(comp, x, y, BASE_TH, STANDOFF_OD, STANDOFF_H, JOIN, [body])
        cyl(comp, x, y, BASE_TH, STANDOFF_PILOT, STANDOFF_H + 1, CUT, [body])


def build_base(comp):
    base = box(comp, 0, 0, 0, OUT_X, OUT_Y, OUT_Z, NEW).bodies.item(0)
    base.name = 'FIR Module Base'
    fillet_vertical(comp, base, CORNER_R)                            # rounded corners
    box(comp, 0, 0, BASE_TH, IN_X, IN_Y, IN_Z + 1, CUT, [base])      # open-front cavity

    # faceplate screw bosses
    for (x, y) in SCREW_XY:
        cyl(comp, x, y, BASE_TH, BOSS_D, IN_Z, JOIN, [base])
        cyl(comp, x, y, BASE_TH, BOSS_PILOT, IN_Z + 1, CUT, [base])

    # board standoffs
    for (name, w, l, h, cx, cy, n) in COMPONENTS:
        standoffs(comp, base, cx, cy, w, l, n)

    # ALARM SENSOR: reed-switch clip on the lid edge (siren itself is in the big box)
    rx, ry = REED_C
    box(comp, rx - 3, ry, BASE_TH, 2, 8, 9, JOIN, [base])
    box(comp, rx + 3, ry, BASE_TH, 2, 8, 9, JOIN, [base])

    # cable management: two channel ribs to the exit + a tie bridge
    for rxr in (CABLE_NOTCH_X - 9, CABLE_NOTCH_X + 9):
        box(comp, rxr, -30, BASE_TH, WALL, 40, 7, JOIN, [base])
    box(comp, CABLE_NOTCH_X - 5, -10, BASE_TH, 9, 3, 6, JOIN, [base])
    box(comp, CABLE_NOTCH_X + 5, -10, BASE_TH, 9, 3, 6, JOIN, [base])
    box(comp, CABLE_NOTCH_X, -10, BASE_TH + 4, 19, 3, 2, JOIN, [base])

    # single cable bundle exit notch (bottom wall)
    box(comp, CABLE_NOTCH_X, -OUT_Y / 2, BASE_TH, CABLE_NOTCH_W, WALL * 3, IN_Z, CUT, [base])

    # floor vents / lightening (also airflow) in clear strips
    for (vx, vy) in ((-52, 12), (-52, -18), (52, -38)):
        box(comp, vx, vy, -1, 12, 22, BASE_TH + 2, CUT, [base])

    # premium bevels on the top rim + bottom edge
    bevel_outer(comp, base, BEVEL, OUT_Z, 1)
    bevel_outer(comp, base, BEVEL, 0.0, -1)
    return base


def build_parts(comp):
    sz_top = BASE_TH + STANDOFF_H
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
            ui.messageBox('Open a Fusion Design (Design workspace) and run again.')
            return
        try:
            design.fusionUnitsManager.distanceDisplayUnits = \
                adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        except Exception:
            pass

        del SKIPPED[:]
        build_base(design.rootComponent)
        if SHOW_PARTS:
            build_parts(design.rootComponent)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Module built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_ModuleBase failed:\n{}'.format(traceback.format_exc()))
