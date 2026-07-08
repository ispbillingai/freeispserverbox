# FIR_TestTile.py - Autodesk Fusion 360 script
# A 50 x 50 mm TEST COUPON of the main faceplate look - print this FIRST on the new
# printer to check the FreeISP logo + every detail type (emboss, engrave, chamfer,
# fillet, fine slots, a bezel hole, the panel-line) before printing the big parts.

import adsk.core, adsk.fusion, adsk.cam, traceback

TILE_W, TILE_H, TILE_TH = 50.0, 50.0, 3.0
FACE_TOP = TILE_TH
CORNER_R, EDGE_CHAMFER = 6.0, 1.0
PANEL_INSET, PANEL_W, PANEL_DEPTH = 4.0, 0.8, 0.5

LOGO_TEXT, LOGO_Y, LOGO_H, LOGO_EMBOSS = 'FreeISP', 13.0, 7.0, 0.6
SUB_TEXT, SUB_Y, SUB_H, ENGRAVE = 'FIR-HS250', 3.0, 2.6, 0.5

LED_C, LED_BEZEL_D, LED_HOLE_D = (-13.0, -11.0), 9.0, 4.0
LOUVRE_C, LOUVRE_N, LOUVRE_LEN, LOUVRE_W, LOUVRE_PITCH = (13.0, -11.0), 3, 12.0, 1.2, 3.0

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


def frame_at(comp, body, cx, cy, ow, oh, t, z0, h, op):
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        L = sk.sketchCurves.sketchLines
        L.addCenterPointRectangle(adsk.core.Point3D.create(mm(cx), mm(cy), 0),
                                  adsk.core.Point3D.create(mm(cx + ow / 2), mm(cy + oh / 2), 0))
        L.addCenterPointRectangle(adsk.core.Point3D.create(mm(cx), mm(cy), 0),
                                  adsk.core.Point3D.create(mm(cx + ow / 2 - t), mm(cy + oh / 2 - t), 0))
        for p in sk.profiles:
            if p.profileLoops.count == 2:
                _ext(comp, p, z0, h, op, [body])
                return
    except Exception as e:
        SKIPPED.append('frame: {}'.format(e))


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


def chamfer_top_edge(comp, body, c):
    try:
        face, best = None, -1.0
        for f in body.faces:
            g = f.geometry
            if isinstance(g, adsk.core.Plane) and g.normal.z > 0.99:
                bb = f.boundingBox
                if abs((bb.minPoint.z + bb.maxPoint.z) / 2 - mm(FACE_TOP)) < mm(0.05) and f.area > best:
                    best, face = f.area, f
        if not face:
            return
        coll = adsk.core.ObjectCollection.create()
        for loop in face.loops:
            if loop.isOuter:
                for e in loop.edges:
                    coll.add(e)
        if coll.count:
            cf = comp.features.chamferFeatures
            ci = cf.createInput2()
            ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                coll, adsk.core.ValueInput.createByReal(mm(c)), False)
            cf.add(ci)
    except Exception as e:
        SKIPPED.append('edge chamfer: {}'.format(e))


def text(comp, body, s, cx, cy, h, depth, emboss=False):
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sts = sk.sketchTexts
        ti = sts.createInput2(s, mm(h))
        w = mm(h) * max(1, len(s)) * 0.64
        ti.setAsMultiLine(
            adsk.core.Point3D.create(mm(cx) - w / 2, mm(cy) - mm(h), 0),
            adsk.core.Point3D.create(mm(cx) + w / 2, mm(cy) + mm(h), 0),
            adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
            adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0)
        try:
            ti.fontName = 'Arial'
            ti.textStyle = adsk.fusion.TextStyles.TextStyleBold
        except Exception:
            pass
        st = sts.add(ti)
        op = JOIN if emboss else CUT
        z0 = FACE_TOP if emboss else FACE_TOP - depth
        sz = depth if emboss else depth + 0.5
        ff = comp.features.extrudeFeatures
        try:
            ei = ff.createInput(st, op)
        except Exception:
            pc = adsk.core.ObjectCollection.create()
            for p in sk.profiles:
                pc.add(p)
            ei = ff.createInput(pc, op)
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(z0)))
        ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(sz)))
        ei.participantBodies = [body]
        ff.add(ei)
    except Exception as e:
        SKIPPED.append('text "{}": {}'.format(s, e))


def build_tile(comp):
    t = box(comp, 0, 0, 0, TILE_W, TILE_H, TILE_TH, NEW).bodies.item(0)
    t.name = 'FIR Test Tile'
    fillet_vertical(comp, t, CORNER_R)
    chamfer_top_edge(comp, t, EDGE_CHAMFER)

    # panel line
    frame_at(comp, t, 0, 0, TILE_W - 2 * PANEL_INSET, TILE_H - 2 * PANEL_INSET,
             PANEL_W, FACE_TOP - PANEL_DEPTH, PANEL_DEPTH + 0.5, CUT)

    # LED bezel + hole sample
    lx, ly = LED_C
    cyl(comp, lx, ly, FACE_TOP - 1.0, LED_BEZEL_D, 1.5, CUT, [t])      # bezel pocket
    cyl(comp, lx, ly, -1, LED_HOLE_D, FACE_TOP + 2, CUT, [t])          # through hole
    cyl(comp, lx, ly, FACE_TOP, LED_BEZEL_D + 2, 0.8, JOIN, [t])       # raised ring
    cyl(comp, lx, ly, FACE_TOP, LED_HOLE_D, 1.5, CUT, [t])

    # fine louvre slots sample
    vx, vy = LOUVRE_C
    x0 = -(LOUVRE_N - 1) * LOUVRE_PITCH / 2.0
    for i in range(LOUVRE_N):
        box(comp, vx, vy + x0 + i * LOUVRE_PITCH, FACE_TOP - 1.0, LOUVRE_LEN, LOUVRE_W, 1.5, CUT, [t])

    # logo (emboss) + sub text (engrave)
    text(comp, t, LOGO_TEXT, 0, LOGO_Y, LOGO_H, LOGO_EMBOSS, emboss=True)
    text(comp, t, SUB_TEXT, 0, SUB_Y, SUB_H, ENGRAVE)
    return t


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
        build_tile(design.rootComponent)
        vp = app.activeViewport
        try:
            cam = vp.camera
            cam.viewOrientation = adsk.core.ViewOrientations.TopViewOrientation
            vp.camera = cam
        except Exception:
            pass
        vp.fit()
        if SKIPPED:
            ui.messageBox('Test tile built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_TestTile failed:\n{}'.format(traceback.format_exc()))
