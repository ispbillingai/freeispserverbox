# FIR_ModulePlate.py - Autodesk Fusion 360 script
# The BOTTOM that closes the FIR_ModuleGadget shell. Fits up inside the shell's
# open bottom, screws up into the shell's 4 corner bosses, and carries the boards
# on standoffs. Run this in the SAME design as FIR_ModuleGadget to see it CLOSED.
#
#  shell (open bottom)  +  this plate (the floor)  =  sealed router unit
#  >>> Component sizes are plan defaults - VERIFY with calipers. <<<

import adsk.core, adsk.fusion, adsk.cam, traceback

# ---------------- PLATE (fits inside the shell's 130x115 cavity) ----------------
PLATE_W, PLATE_H, PLATE_TH = 130.0, 115.0, 3.0   # EXACT cover cavity size = press fit, no side play
PLATE_TOP = PLATE_TH                         # plate occupies z 0..3, top at z=3
CORNER_R = 7.5                               # EXACT cover inner cavity corner radius

# screws up into the shell bosses (must match FIR_ModuleGadget SCREW_XY)
SCREW_XY = [(-58.5, 50.0), (58.5, 50.0), (-58.5, -50.0), (58.5, -50.0)]
BOSS_D, BOSS_RISE, SCREW_CLEAR = 7.0, 3.0, 3.4
CB_D, CB_DEPTH = 6.0, 1.5                    # counterbore on the bottom for the screw head

STANDOFF_OD, STANDOFF_H, STANDOFF_PILOT = 5.5, 4.0, 2.2

# brain + power boards:  name, w, l, h, cx, cy, posts
COMPONENTS = [
    ('ESP32-S3',     70.0, 26.0, 13.0,  0.0,   6.0, 4),
    ('LM2596 buck',  52.0, 27.0, 15.0,  0.0, -24.0, 4),
    ('18650 holder', 75.0, 20.0, 20.0,  0.0,  44.0, 2),
    ('TP4056',       26.0, 17.0,  6.0,  0.0, -45.0, 2),
    ('MPU-6050',     22.0, 17.0,  4.0, 48.0,  28.0, 2),
]
REED_C = (-50.0, 47.0)                       # tamper reed near the top edge
LIGHTEN = [(-50.0, 10.0), (-50.0, -22.0), (44.0, -38.0), (44.0, -2.0)]
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
        cyl(comp, x, y, PLATE_TOP, STANDOFF_OD, STANDOFF_H, JOIN, [body])
        cyl(comp, x, y, PLATE_TOP, STANDOFF_PILOT, STANDOFF_H + 1, CUT, [body])


def build_plate(comp):
    plate = box(comp, 0, 0, 0, PLATE_W, PLATE_H, PLATE_TH, NEW).bodies.item(0)
    plate.name = 'FIR Bottom Plate'
    fillet_vertical(comp, plate, CORNER_R)

    for (vx, vy) in LIGHTEN:
        box(comp, vx, vy, -1, 14, 22, PLATE_TH + 2, CUT, [plate])

    # screw bosses (rise to meet the shell bosses) + counterbored clearance hole
    for (x, y) in SCREW_XY:
        cyl(comp, x, y, PLATE_TOP, BOSS_D, BOSS_RISE, JOIN, [plate])
        cyl(comp, x, y, -1, SCREW_CLEAR, PLATE_TH + BOSS_RISE + 2, CUT, [plate])
        cyl(comp, x, y, 0, CB_D, CB_DEPTH, CUT, [plate])         # head pocket on the bottom

    for (name, w, l, h, cx, cy, n) in COMPONENTS:
        standoffs(comp, plate, cx, cy, w, l, n)

    rx, ry = REED_C
    box(comp, rx - 3, ry, PLATE_TOP, 2, 8, 9, JOIN, [plate])
    box(comp, rx + 3, ry, PLATE_TOP, 2, 8, 9, JOIN, [plate])

    # cable tie-down: two solid posts - loop a zip tie around both to clamp the
    # harness. No bridging bar = no floating region, prints support-free.
    box(comp, 28, -8, PLATE_TOP, 3.5, 10, 7, JOIN, [plate])
    box(comp, 36, -8, PLATE_TOP, 3.5, 10, 7, JOIN, [plate])
    return plate


def build_parts(comp):
    sz_top = PLATE_TOP + STANDOFF_H
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
        build_plate(design.rootComponent)
        if SHOW_PARTS:
            build_parts(design.rootComponent)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Plate built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_ModulePlate failed:\n{}'.format(traceback.format_exc()))
