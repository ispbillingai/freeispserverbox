# FIR_PortPlate.py - Autodesk Fusion 360 script
# The RB951 PORT PLATE: a flat panel carrying the exact measured port openings so the
# router's ports protrude/align straight through it. Prints FLAT (face up) -> crisp holes,
# no vertical-wall distortion. Mounts onto the box where the MikroTik sits.
#
# Measured port face = 114 wide x 29 tall. Openings = measured size + 0.5mm clearance.
# All feature positions are CENTRES, from the port-face bottom-left corner (verified).

import adsk.core, adsk.fusion, adsk.cam, traceback

PLATE_W, PLATE_H, PLATE_TH = 126.0, 41.0, 3.0     # plate (port face 114x29 + border)
CORNER_R = 4.0
PF_W, PF_H = 114.0, 29.0                            # the RB951 port-face region
BOTTOM_MARGIN = 6.0                                 # gap below the port region on the plate
CLR = 0.5                                           # opening clearance (added per dimension)

# port-face bottom-left corner, in plate coordinates (plate centred at origin)
PF_X0 = -PF_W / 2.0
PF_Y0 = -PLATE_H / 2.0 + BOTTOM_MARGIN

# (name, centre_x, centre_z, shape 'c'/'r', dia or width, height) - x,z from port-face origin
FEATURES = [
    ('JACK',  11.0,  15.0, 'c', 6.0,  0.0),
    ('RESET', 19.0,  10.0, 'c', 2.0,  0.0),
    ('PWR',   25.0,  9.5,  'r', 4.0,  3.0),
    ('ACT',   33.0,  9.5,  'r', 4.0,  3.0),
    ('LAN1',  44.5,  16.0, 'r', 13.0, 12.0),
    ('LAN2',  58.5,  16.0, 'r', 13.0, 12.0),
    ('LAN3',  72.5,  16.0, 'r', 13.0, 12.0),
    ('LAN4',  86.5,  16.0, 'r', 13.0, 12.0),
    ('LAN5', 100.5,  16.0, 'r', 13.0, 12.0),
]
MOUNT = [(-(PLATE_W / 2 - 5), (PLATE_H / 2 - 5)), ((PLATE_W / 2 - 5), (PLATE_H / 2 - 5)),
         (-(PLATE_W / 2 - 5), -(PLATE_H / 2 - 5)), ((PLATE_W / 2 - 5), -(PLATE_H / 2 - 5))]
MOUNT_D = 3.5

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


def text(comp, body, s, cx, cy, h, z_top, depth):
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sts = sk.sketchTexts
        ti = sts.createInput2(s, mm(h))
        w = mm(h) * max(1, len(s)) * 1.3
        ti.setAsMultiLine(
            adsk.core.Point3D.create(mm(cx) - w / 2, mm(cy) - mm(h), 0),
            adsk.core.Point3D.create(mm(cx) + w / 2, mm(cy) + mm(h), 0),
            adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
            adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0)
        st = sts.add(ti)
        ff = comp.features.extrudeFeatures
        try:
            ei = ff.createInput(st, CUT)
        except Exception:
            pc = adsk.core.ObjectCollection.create()
            for p in sk.profiles:
                pc.add(p)
            ei = ff.createInput(pc, CUT)
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(z_top - depth)))
        ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(depth + 0.5)))
        ei.participantBodies = [body]
        ff.add(ei)
    except Exception as e:
        SKIPPED.append('text {}: {}'.format(s, e))


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
        plate = box(comp, 0, 0, 0, PLATE_W, PLATE_H, PLATE_TH, NEW).bodies.item(0)
        plate.name = 'FIR Port Plate (RB951)'
        fillet_vertical(comp, plate, CORNER_R)

        # cut every measured opening (size + clearance)
        for (name, x, z, shape, a, b) in FEATURES:
            px, py = PF_X0 + x, PF_Y0 + z
            if shape == 'c':
                cyl(comp, px, py, -1, a + CLR, PLATE_TH + 2, CUT, [plate])
            else:
                box(comp, px, py, -1, a + CLR, b + CLR, PLATE_TH + 2, CUT, [plate])

        # LAN labels engraved above each port (face-up = crisp)
        for k in range(5):
            px = PF_X0 + FEATURES[4 + k][1]
            text(comp, plate, 'LAN{}'.format(k + 1), px, PF_Y0 + 16 + 9, 2.6, PLATE_TH, 0.6)

        # mounting holes (border corners) - screw the plate to the box
        for (mx, my) in MOUNT:
            cyl(comp, mx, my, -1, MOUNT_D, PLATE_TH + 2, CUT, [plate])

        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Port plate built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_PortPlate failed:\n{}'.format(traceback.format_exc()))
