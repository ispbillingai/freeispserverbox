# FIR_ShellTub.py - Autodesk Fusion 360 script
# The main SHELL TUB (step 1). Box = 280(W,X) x 280(H,Y) x 80(D,Z). The 280x280 face is the
# front(room)/back(wall); the 80mm is the depth. The BOTTOM face (Y=0, 280x80) is left OPEN - that
# opening is filled by the removable bottom lid (ports face down). 5 walls (3mm) + open bottom.
# Rounded outer corners for the premium look. NEXT: lid seat (rabbet) + 6 self-tap bolt bosses +
# device cradles. Run ALONE in a fresh design.

import adsk.core, adsk.fusion, adsk.cam, traceback

W, H, D = 280.0, 280.0, 80.0
WALL = 3.0

CM = 0.1
def mm(v):
    return v * CM

NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
SKIPPED = []


def box(comp, cx, cy, z0, sx, sy, sz, op, parts=None):
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchLines.addCenterPointRectangle(
        adsk.core.Point3D.create(mm(cx), mm(cy), 0),
        adsk.core.Point3D.create(mm(cx + sx / 2.0), mm(cy + sy / 2.0), 0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(z0) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(z0)))
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(sz)))
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def fillet_z(comp, body, r):
    # round the 4 vertical (Z-running) outer corners
    try:
        coll = adsk.core.ObjectCollection.create()
        for e in body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                v = g.startPoint.vectorTo(g.endPoint)
                v.normalize()
                if abs(v.z) > 0.99:
                    mx = (g.startPoint.x + g.endPoint.x) / 2.0
                    my = (g.startPoint.y + g.endPoint.y) / 2.0
                    if abs(abs(mx) - mm(W / 2)) < mm(1) and abs(abs(my - mm(H / 2)) - mm(H / 2)) < mm(1):
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

        # solid block, centred in X, Y 0..H, Z 0..D
        tub = box(comp, 0, H / 2, 0, W, H, D, NEW).bodies.item(0)
        tub.name = 'FIR Shell Tub'
        fillet_z(comp, tub, 8.0)                                    # rounded vertical corners

        # hollow: leave 5 walls (back Z0-3, front Z(D-3)-D, sides X, top Y(H-3)-H), OPEN bottom (Y=0)
        box(comp, 0, (H - WALL) / 2.0, WALL, W - 2 * WALL, H - WALL, D - 2 * WALL, CUT, [tub])

        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Shell tub built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_ShellTub failed:\n{}'.format(traceback.format_exc()))
