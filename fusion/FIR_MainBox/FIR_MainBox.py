# FIR_MainBox.py - Autodesk Fusion 360 script
# The MAIN enclosure (the bought ~300 x 250 x 120 IP65 box, represented for assembly
# viewing). Open front (where the faceplate mounts), side vent louvres, corner mounting
# bosses for the faceplate, and a bottom mounting strip for the bottom box.
# Built with its FRONT at z=0 so the faceplate (built at z=0..4) lands on it.
# Run this + FIR_Faceplate + FIR_BottomBox in ONE design to see the product come together.

import adsk.core, adsk.fusion, adsk.cam, traceback

MBW, MBH, MBD = 300.0, 250.0, 120.0      # outer width x height x depth (MEASURE real box)
WALL, BACK_TH, CORNER_R = 3.0, 3.0, 14.0
FACE_BOSS_XY = [(-(MBW / 2 - 12), (MBH / 2 - 12)), ((MBW / 2 - 12), (MBH / 2 - 12)),
                (-(MBW / 2 - 12), -(MBH / 2 - 12)), ((MBW / 2 - 12), -(MBH / 2 - 12))]
BOSS_D, BOSS_PILOT, BOSS_H = 9.0, 3.0, 12.0
VENT_N, VENT_LEN, VENT_W, VENT_PITCH = 7, 70.0, 3.0, 8.0   # side vent louvres

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
        SKIPPED.append('fillet: {}'.format(e))


def build_box(comp):
    # body from z=-MBD (back) to z=0 (front opening at the XY plane)
    body = box(comp, 0, 0, -MBD, MBW, MBH, MBD, NEW).bodies.item(0)
    body.name = 'FIR Main Box'
    fillet_vertical(comp, body, CORNER_R)
    # hollow it - open FRONT (z=0), keep the back wall
    box(comp, 0, 0, -MBD + BACK_TH, MBW - 2 * WALL, MBH - 2 * WALL, MBD, CUT, [body])

    # corner mounting bosses on the front rim (the faceplate screws into these)
    for (x, y) in FACE_BOSS_XY:
        cyl(comp, x, y, -BOSS_H, BOSS_D, BOSS_H, JOIN, [body])
        cyl(comp, x, y, -BOSS_H, BOSS_PILOT, BOSS_H + 1, CUT, [body])

    # side vent louvres (both ±X walls)
    z0 = -MBD + 20
    for side in (-1, 1):
        for i in range(VENT_N):
            box(comp, side * MBW / 2, 0, z0 + i * VENT_PITCH, WALL * 3, VENT_LEN, VENT_W, CUT, [body])

    # bottom mounting strip (where the bottom box bolts on) - 4 holes along the bottom
    for bx in (-110, -40, 40, 110):
        cyl(comp, bx, -MBH / 2 + WALL, -25, 4.2, 10, CUT, [body])
    return body


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
        build_box(design.rootComponent)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Main box built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_MainBox failed:\n{}'.format(traceback.format_exc()))
