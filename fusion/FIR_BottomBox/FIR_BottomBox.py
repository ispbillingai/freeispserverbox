# FIR_BottomBox.py - Autodesk Fusion 360 script
# NanoStation-M2-style power/cable module - a CLAMSHELL:
#   BASE (fixed)  : flat tray holding the ports (downward glands + RJ45), terminals,
#                   a perimeter rim, and mounting holes.
#   CURVED COVER  : the big curved shell that SNAPS over the base - this is the
#                   removable part. Shown LIFTED up for an exploded view.
# Pop the curved cover off -> wire it -> snap it back. No hinge, no moving parts.

import adsk.core, adsk.fusion, adsk.cam, traceback

BW, BD, BHT = 280.0, 72.0, 58.0          # width x depth x height (MEASURE to your box)
WALL, CORNER_R = 2.5, 8.0
CURVE_R = 46.0                           # the big M2 FRONT CURVE - near full height so the
                                         # WHOLE front sweeps down in one curve (your red line)

# bottom recessed channel (opens DOWNWARD at z=0) - ports + cap live here
CH_W, CH_L, CH_DEPTH, CH_Y = 244.0, 46.0, 15.0, 2.0
CH_CEIL = CH_DEPTH                        # recess ceiling at z=15

POWER_GLANDS = [(-112.0, 'POWER IN', 20.0), (-82.0, 'POWER OUT', 16.0)]
RJ45_X = [-46.0, -22.0, 2.0, 26.0, 50.0]
RJ45_W, RJ45_H = 15.0, 16.5
GLAND_Y = CH_Y - 12.0
SW_W, SW_H, SW_X = 26.0, 18.0, 96.0

CAP_W, CAP_L, CAP_TH, CAP_DROP = 243.0, 45.0, 3.0, 28.0
ARM_X = [-90.0, 90.0]
ARM_W, ARM_T, ARM_H, HOOK_P = 6.0, 2.0, 11.0, 1.5

MOUNT_X = [-110.0, -40.0, 40.0, 110.0]
MOUNT_D = 4.2

# FIXED L-mount (flat top seats on the main box + flat back) and the REMOVABLE curved front
TOP_TH, BACK_TH = 6.0, 6.0
COVER_H = BHT - TOP_TH                    # curved front sits below the flat top plate
COVER_FWD = 38.0                          # removable front shown pulled FORWARD (exploded)
PASS_W, PASS_L = 70.0, 26.0               # cable pass-through slot up into the main box

# OPEN "squeeze-in" Cat6 cable entries (keyhole: narrow slit -> round pocket).
# Lay the cable in through the slit like a door; it grips in the pocket. No threading.
CAT6_X = [-90.0, -54.0, -18.0, 18.0, 54.0, 90.0]
CAT6_D, CAT6_SLIT, CAT6_H = 7.0, 4.5, 10.0   # cable Ø, squeeze slit (<Ø grips), slot height

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
    # THE M2 CURVE: big fillet on the horizontal edge (along X) nearest (at_y, at_z)
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
                    if abs(my - mm(at_y)) < mm(2.5) and abs(mz - mm(at_z)) < mm(2.5):
                        coll.add(e)
        if coll.count:
            fi = comp.features.filletFeatures.createInput()
            fi.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
            comp.features.filletFeatures.add(fi)
    except Exception as e:
        SKIPPED.append('curve fillet: {}'.format(e))


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
        SKIPPED.append('text: {}'.format(e))


def build_mount(comp):
    # FIXED L: flat TOP (seats on the main box; cables pass up through it) + flat BACK wall
    top = box(comp, 0, 0, COVER_H, BW, BD, TOP_TH, NEW).bodies.item(0)
    top.name = 'FIR Mount L (fixed: top + back)'
    box(comp, 0, -BD / 2 + BACK_TH / 2, 0, BW, BACK_TH, COVER_H, JOIN, [top])  # flat back wall
    # cable pass-through slot - cables roll UP through the top into the main box
    box(comp, 0, -2, COVER_H - 1, PASS_W, PASS_L, TOP_TH + 2, CUT, [top])
    # mounting holes through the flat top (bolt up to the enclosure)
    for mx in MOUNT_X:
        cyl(comp, mx, BD / 2 - 13, COVER_H - 1, MOUNT_D, TOP_TH + 2, CUT, [top])
    return top


def build_cover(comp):
    # REMOVABLE curved FRONT - clips onto the L. Shown pulled FORWARD (+Y) for the explode.
    yo = COVER_FWD
    cov = box(comp, 0, yo, 0, BW, BD, COVER_H, NEW).bodies.item(0)
    cov.name = 'FIR Curved Front (removable)'
    fillet_vertical(comp, cov, CORNER_R)
    fillet_edge(comp, cov, CURVE_R, BD / 2 + yo, COVER_H)              # the front-top curve
    # hollow it: open at the BACK (toward the L) and TOP (under the L's plate)
    cav_back = yo - BD / 2 - 5
    cav_front = yo + BD / 2 - WALL
    box(comp, 0, (cav_back + cav_front) / 2.0, WALL, BW - 2 * WALL,
        cav_front - cav_back, COVER_H + 10, CUT, [cov])
    # OPEN squeeze-in Cat6 entries on the front (slit opens at bottom rim -> round pocket)
    fy = yo + BD / 2 - WALL / 2
    for cx in CAT6_X:
        box(comp, cx, fy, -1, CAT6_SLIT, WALL + 4, CAT6_H + 2, CUT, [cov])
        cyl(comp, cx, fy, CAT6_H, CAT6_D, WALL + 4, CUT, [cov])
    return cov


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
        build_mount(design.rootComponent)
        build_cover(design.rootComponent)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Bottom box built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_BottomBox failed:\n{}'.format(traceback.format_exc()))
