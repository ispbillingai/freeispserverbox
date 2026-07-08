# FIR_Frame.py - Autodesk Fusion 360 script
# ONE SIDE of the box at REAL size: a flat rectangular outline of the front face
# (165 wide x 180 tall), lying flat so it prints fast. Shows the true face size/height
# without printing the whole 3D box.

import adsk.core, adsk.fusion, adsk.cam, traceback

# Wide flat box: FOOTPRINT = the two big numbers 230 x 200; the 120 is just the height
# (not in this flat rectangle). This is the real full-size footprint.
SIDE_W, SIDE_H = 230.0, 200.0
RING_T = 4.0                             # outline line thickness (continuous loop)
PANEL_TH = 4.0                           # flat thickness (lies on the bed)

CM = 0.1
def mm(v):
    return v * CM

NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
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
        body = box(comp, 0, 0, 0, SIDE_W, SIDE_H, PANEL_TH, NEW).bodies.item(0)
        body.name = 'FIR Footprint Loop (230 x 200)'
        # hollow the middle -> ONE continuous rectangular loop (sharp solid corners)
        box(comp, 0, 0, -1, SIDE_W - 2 * RING_T, SIDE_H - 2 * RING_T, PANEL_TH + 2, CUT, [body])
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Side built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_Frame failed:\n{}'.format(traceback.format_exc()))
