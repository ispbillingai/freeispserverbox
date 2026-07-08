# FIR_Enclosure.py - Autodesk Fusion 360 script
# FreeISP enclosure, UPRIGHT, with the port section INTEGRATED into the lower box.
# The RB951 + 5-port PoE sit port-down; their ports exit a localized strip on the BOTTOM
# (z=0) so cables plug straight in - no couplers. A SMALL CURVED SHROUD is the only
# removable part: it clips over that bottom strip (squeeze-in Cat6 slots, weatherproof).
#   1 Enclosure Body   : upright shell, open top (lid), bottom port strip, wall keyholes.
#   2 Curved Shroud    : small removable bottom port cover (shown dropped for explode).
#   3 Top Lid          : shown lifted.
# ALL DIMS flagged - tell me the real ones and I lock it.

import adsk.core, adsk.fusion, adsk.cam, traceback

EW, ED, EH = 165.0, 92.0, 180.0          # width(X) x depth(Y) x height(Z)  - ADJUST
WALL, CORNER_R, LID_TH = 2.5, 8.0, 4.0

# --- bottom port strip (faces DOWN at z=0), localized + thinner than the box ---
RJ45_W, RJ45_H = 15.0, 12.0
MIK_ROW_Y = 19.0                          # RB951 row (standard: DC + 5x RJ45 + USB)
MIK_RJ45_X = [-32.0, -16.0, 0.0, 16.0, 32.0]
MIK_DC_X, MIK_USB_X = -54.0, 54.0
POE_ROW_Y = -19.0                         # PoE row (5x RJ45)
POE_RJ45_X = [-32.0, -16.0, 0.0, 16.0, 32.0]

# --- small curved removable shroud over the bottom strip ---
SHROUD_W, SHROUD_D, SHROUD_H = 150.0, 64.0, 26.0
SHROUD_DROP, SHROUD_CURVE = 32.0, 18.0
CAT6_X = [-50.0, -25.0, 0.0, 25.0, 50.0]
CAT6_D, CAT6_SLIT = 7.0, 4.5

LID_LIFT = 34.0
KEYHOLE_X, KEYHOLE_Z = [-50.0, 50.0], EH - 28.0

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
        SKIPPED.append('vfillet: {}'.format(e))


def fillet_edge(comp, body, r, at_y, at_z):
    # big fillet on the horizontal edge (along X) nearest (at_y, at_z) -> the curve
    try:
        coll = adsk.core.ObjectCollection.create()
        for e in body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                v = g.startPoint.vectorTo(g.endPoint)
                v.normalize()
                if abs(v.x) > 0.99:
                    my = (g.startPoint.y + g.endPoint.y) / 2.0
                    mz = (g.startPoint.z + g.endPoint.z) / 2.0
                    if abs(my - mm(at_y)) < mm(3) and abs(mz - mm(at_z)) < mm(3):
                        coll.add(e)
        if coll.count:
            fi = comp.features.filletFeatures.createInput()
            fi.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
            comp.features.filletFeatures.add(fi)
    except Exception as e:
        SKIPPED.append('curve fillet: {}'.format(e))


def build_body(comp):
    body = box(comp, 0, 0, 0, EW, ED, EH, NEW).bodies.item(0)
    body.name = '1 Enclosure Body'
    fillet_vertical(comp, body, CORNER_R)
    # hollow it - open TOP (lid goes on top), keep the bottom floor for the ports
    box(comp, 0, 0, WALL, EW - 2 * WALL, ED - 2 * WALL, EH, CUT, [body])

    # --- BOTTOM PORT STRIP (z=0, facing DOWN) ---
    for rx in MIK_RJ45_X:
        box(comp, rx, MIK_ROW_Y, -1, RJ45_W, RJ45_H, WALL + 2, CUT, [body])     # RB951 RJ45
    cyl(comp, MIK_DC_X, MIK_ROW_Y, -1, 7.0, WALL + 2, CUT, [body])              # RB951 DC jack
    box(comp, MIK_USB_X, MIK_ROW_Y, -1, 8.0, 12.0, WALL + 2, CUT, [body])       # RB951 USB
    for rx in POE_RJ45_X:
        box(comp, rx, POE_ROW_Y, -1, RJ45_W, RJ45_H, WALL + 2, CUT, [body])     # PoE RJ45

    # shroud catch-ridge around the bottom strip (shroud hooks grab under it)
    for sy in (SHROUD_D / 2, -SHROUD_D / 2):
        box(comp, 0, sy, 3.0, SHROUD_W - 6, 1.4, 1.6, JOIN, [body])

    # wall-mount keyholes on the back wall (-Y)
    for kx in KEYHOLE_X:
        cyl(comp, kx, -ED / 2 - 1, KEYHOLE_Z, 11, WALL + 2, CUT, [body])
        box(comp, kx, -ED / 2 - 1, KEYHOLE_Z - 9, 5, 18, WALL + 2, CUT, [body])

    # top lid bosses (screw the lid on)
    for (x, y) in [(-(EW / 2 - 10), (ED / 2 - 10)), ((EW / 2 - 10), (ED / 2 - 10)),
                   (-(EW / 2 - 10), -(ED / 2 - 10)), ((EW / 2 - 10), -(ED / 2 - 10))]:
        cyl(comp, x, y, EH - 14, 8, 14, JOIN, [body])
        cyl(comp, x, y, EH - 14, 2.6, 15, CUT, [body])
    return body


def build_shroud(comp):
    # the ONLY removable part: small curved shroud over the bottom ports. Dropped for explode.
    z0 = -SHROUD_H - SHROUD_DROP
    sh = box(comp, 0, 0, z0, SHROUD_W, SHROUD_D, SHROUD_H, NEW).bodies.item(0)
    sh.name = '2 Curved Shroud (removable)'
    fillet_vertical(comp, sh, 6.0)
    fillet_edge(comp, sh, SHROUD_CURVE, SHROUD_D / 2, z0)            # curved front-bottom
    fillet_edge(comp, sh, SHROUD_CURVE, -SHROUD_D / 2, z0)          # curved back-bottom
    # hollow, open TOP (fits up over the port strip)
    box(comp, 0, 0, z0 + WALL, SHROUD_W - 2 * WALL, SHROUD_D - 2 * WALL, SHROUD_H, CUT, [sh])
    # OPEN squeeze-in Cat6 slots on the front (slit -> round pocket)
    fy = SHROUD_D / 2 - WALL / 2
    for cx in CAT6_X:
        box(comp, cx, fy, z0 - 1, CAT6_SLIT, WALL + 4, 11, CUT, [sh])
        cyl(comp, cx, fy, z0 + 9, CAT6_D, WALL + 4, CUT, [sh])
    # inward snap hooks (grab the body's catch-ridge)
    for hx in (-55, 0, 55):
        for side in (1, -1):
            box(comp, hx, side * (SHROUD_D / 2 - WALL), z0 + SHROUD_H - 4, 10, 1.6, 2.0, JOIN, [sh])
    return sh


def build_lid(comp):
    z = EH + LID_LIFT
    lid = box(comp, 0, 0, z, EW, ED, LID_TH, NEW).bodies.item(0)
    lid.name = '3 Top Lid'
    fillet_vertical(comp, lid, CORNER_R)
    for (x, y) in [(-(EW / 2 - 10), (ED / 2 - 10)), ((EW / 2 - 10), (ED / 2 - 10)),
                   (-(EW / 2 - 10), -(ED / 2 - 10)), ((EW / 2 - 10), -(ED / 2 - 10))]:
        cyl(comp, x, y, z - 1, 3.4, LID_TH + 2, CUT, [lid])
    return lid


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
        build_body(design.rootComponent)
        build_shroud(design.rootComponent)
        build_lid(design.rootComponent)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Enclosure built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_Enclosure failed:\n{}'.format(traceback.format_exc()))
