# FIR_ModuleGadget.py - Autodesk Fusion 360 script
# The smart-module as a PREMIUM little device - an edge-router-style gadget:
# rounded body, chamfered top, fine side vent louvres, and a clean integrated
# top panel (screen lens + LEDs + RFID TAP + logo). Open bottom = drops over the
# carrier plate (FIR_ModulePlate). This is the HERO exterior of the brain unit.

import adsk.core, adsk.fusion, adsk.cam, traceback

# ---------------- BODY ----------------
W, H, BODY_Z = 135.0, 120.0, 38.0
WALL, FACE_TH = 2.5, 4.0
CORNER_R, TOP_CHAMFER, MOUTH_CHAMFER = 10.0, 2.0, 0.4  # cleaner oval corners + simple top chamfer
GROOVE_Z = []                                          # step-lines removed (were too busy)
ENTRY_W, ENTRY_H, ENTRY_Z = 18.0, 10.0, 7.0           # cable entry slot (back wall)
REAR_LED_D, REAR_LED_Z = 3.5, 22.0                    # small rear power/internet LEDs
FACE_TOP = BODY_Z
CAV_TOP = BODY_Z - FACE_TH
IN_W, IN_H = W - 2 * WALL, H - 2 * WALL

SCREW_XY = [(-58.5, 50.0), (58.5, 50.0), (-58.5, -50.0), (58.5, -50.0)]
BOSS_D, BOSS_PILOT = 7.0, 2.6
LEDGE_W, LEDGE_H, PLATE_SEAT_Z = 1.5, 2.0, 3.0   # internal ledge the carrier plate seats on (plate is 3mm)

# top panel features  (screen window matched to a real 1.8" TFT - VERIFY your board)
SCR_Y, SCR_W, SCR_H = 8.0, 33.0, 26.0
SCR_BW, SCR_BH, BEZEL_DEPTH = 42.0, 35.0, 1.2
LENS_W, LENS_PROUD = 2.0, 0.8
SCR_HOLE_X, SCR_HOLE_Y, SCR_STANDOFF = 40.0, 30.0, 3.0   # PCB hole spacing + glass standoff
LED_Y, LED1_X, LED2_X = -22.0, -15.0, 15.0
LED_D, LED_BEZEL_D, LED_BEZEL_DEPTH = 5.5, 12.0, 1.0      # 5mm-LED hole + raised bezel
LOGO_TEXT, LOGO_Y, LOGO_H, LOGO_EMBOSS = 'FreeISP', 40.0, 10.0, 1.0   # deeper = crisp face-down
PANEL_INSET, PANEL_W, PANEL_DEPTH = 8.0, 1.0, 0.6
ENGRAVE = 0.8        # deeper engrave so text/labels print crisp when face-down
SPEC_LINES = ['FIR-HS250', '12V DC 2A', 'SN FHS250-__']   # small spec in a top corner

# cross-flow grilles (VERTICAL slots so they print support-free): back = intake, front = exhaust
GRILLE_N, GRILLE_W, GRILLE_LEN, GRILLE_PITCH, GRILLE_Z0 = 9, 3.0, 16.0, 6.0, 12.0

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


def fillet_corners_at(comp, body, positions, r):
    # fillet only the vertical edges whose XY is near one of the given corner positions
    try:
        coll = adsk.core.ObjectCollection.create()
        for e in body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                v = g.startPoint.vectorTo(g.endPoint)
                v.normalize()
                if abs(v.z) > 0.99:
                    p = g.startPoint
                    for (px, py) in positions:
                        if abs(p.x - mm(px)) < mm(1.5) and abs(p.y - mm(py)) < mm(1.5):
                            coll.add(e)
                            break
        if coll.count:
            fin = comp.features.filletFeatures.createInput()
            fin.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
            comp.features.filletFeatures.add(fin)
    except Exception as e:
        SKIPPED.append('corner fillet r{}: {}'.format(r, e))


def _top_face(body):
    face, best = None, -1.0
    for f in body.faces:
        g = f.geometry
        if isinstance(g, adsk.core.Plane) and g.normal.z > 0.99:
            bb = f.boundingBox
            if abs((bb.minPoint.z + bb.maxPoint.z) / 2 - mm(FACE_TOP)) < mm(0.05) and f.area > best:
                best, face = f.area, f
    return face


def chamfer_top(comp, body, c):
    # simple chamfer on the top outer edge - robust, no corner-blend gaps
    try:
        face = _top_face(body)
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
        SKIPPED.append('top chamfer: {}'.format(e))


def chamfer_mouths(comp, body, c):
    try:
        face = _top_face(body)
        if not face:
            return
        coll = adsk.core.ObjectCollection.create()
        for loop in face.loops:
            if not loop.isOuter:
                for e in loop.edges:
                    coll.add(e)
        if coll.count:
            cf = comp.features.chamferFeatures
            ci = cf.createInput2()
            ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                coll, adsk.core.ValueInput.createByReal(mm(c)), False)
            cf.add(ci)
    except Exception as e:
        SKIPPED.append('mouth chamfer: {}'.format(e))


def ring(comp, body, cx, cy, r_out, width, z_top, depth):
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        cc = sk.sketchCurves.sketchCircles
        cc.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(r_out))
        cc.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(r_out - width))
        for p in sk.profiles:
            if p.profileLoops.count == 2:
                _ext(comp, p, z_top - depth, depth + 0.5, CUT, [body])
                return
    except Exception as e:
        SKIPPED.append('wave ring: {}'.format(e))


def text(comp, body, s, cx, cy, h, depth, emboss=False):
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sts = sk.sketchTexts
        ti = sts.createInput2(s, mm(h))
        w = mm(h) * max(1, len(s)) * 1.3       # generous box width so lines never wrap
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


def pocket(comp, body, cx, cy, w, l, d):
    box(comp, cx, cy, FACE_TOP - d, w, l, d + 0.5, CUT, [body])


def pocket_c(comp, body, cx, cy, dia, d):
    cyl(comp, cx, cy, FACE_TOP - d, dia, d + 0.5, CUT, [body])


def thru(comp, body, cx, cy, w, l):
    box(comp, cx, cy, FACE_TOP - FACE_TH - 1, w, l, FACE_TH + 2, CUT, [body])


def thru_c(comp, body, cx, cy, dia):
    cyl(comp, cx, cy, FACE_TOP - FACE_TH - 1, dia, FACE_TH + 2, CUT, [body])


def side_text(comp, body, s, py, pz, h, depth):
    # engrave into the -X side wall. yZ plane: sketch-X = world Z, sketch-Y = world Y
    # (text runs vertically). py = Z-centre of the text run, pz = the line's Y position.
    try:
        sk = comp.sketches.add(comp.yZConstructionPlane)
        sts = sk.sketchTexts
        ti = sts.createInput2(s, mm(h))
        w = mm(h) * max(1, len(s)) * 0.62
        ti.setAsMultiLine(
            adsk.core.Point3D.create(mm(py) - w / 2, mm(pz) - mm(h), 0),
            adsk.core.Point3D.create(mm(py) + w / 2, mm(pz) + mm(h), 0),
            adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
            adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0)
        try:
            ti.fontName = 'Arial'
        except Exception:
            pass
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
            adsk.core.ValueInput.createByReal(mm(-W / 2)))
        ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(depth)))
        ei.participantBodies = [body]
        ff.add(ei)
    except Exception as e:
        SKIPPED.append('side text "{}": {}'.format(s, e))


def side_panel(comp, body, cy, cz, sy, sz, depth):
    # recessed spec-plate rectangle on the -X wall (yZ plane: sketch-X=world Z, sketch-Y=world Y)
    try:
        sk = comp.sketches.add(comp.yZConstructionPlane)
        sk.sketchCurves.sketchLines.addCenterPointRectangle(
            adsk.core.Point3D.create(mm(cz), mm(cy), 0),
            adsk.core.Point3D.create(mm(cz + sz / 2), mm(cy + sy / 2), 0))
        ff = comp.features.extrudeFeatures
        ei = ff.createInput(sk.profiles.item(0), CUT)
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(-W / 2)))
        ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(depth)))
        ei.participantBodies = [body]
        ff.add(ei)
    except Exception as e:
        SKIPPED.append('side panel: {}'.format(e))


def build_inside_mounts(comp, body):
    # SCREEN: 4 short standoffs at the PCB's real corner holes (outside the display),
    # so the screen screws on flat with its glass sitting at the window.
    for sx in (-SCR_HOLE_X / 2, SCR_HOLE_X / 2):
        for sy in (-SCR_HOLE_Y / 2, SCR_HOLE_Y / 2):
            x, y = sx, SCR_Y + sy
            cyl(comp, x, y, CAV_TOP - SCR_STANDOFF, 5.0, SCR_STANDOFF, JOIN, [body])
            cyl(comp, x, y, CAV_TOP - SCR_STANDOFF, 2.0, SCR_STANDOFF + 0.5, CUT, [body])
    # LEDs: collar that seats a 5mm LED flush behind its hole
    for lx in (LED1_X, LED2_X):
        cyl(comp, lx, LED_Y, CAV_TOP - 5, 8.0, 5.0, JOIN, [body])
        cyl(comp, lx, LED_Y, CAV_TOP - 5, 5.2, 5.5, CUT, [body])


def build(comp):
    body = box(comp, 0, 0, 0, W, H, BODY_Z, NEW).bodies.item(0)
    body.name = 'FIR Module'
    box(comp, 0, 0, -1, IN_W, IN_H, CAV_TOP + 1, CUT, [body])     # hollow, open bottom (sharp)
    # Round the CAVITY corners (R-WALL) then the OUTER corners (R) so the wall stays a
    # solid 2.5mm at the corners. THIS is what stops the cavity breaching the corner (the gap).
    inner = [(IN_W / 2, IN_H / 2), (-IN_W / 2, IN_H / 2), (IN_W / 2, -IN_H / 2), (-IN_W / 2, -IN_H / 2)]
    outer = [(W / 2, H / 2), (-W / 2, H / 2), (W / 2, -H / 2), (-W / 2, -H / 2)]
    fillet_corners_at(comp, body, inner, CORNER_R - WALL)
    fillet_corners_at(comp, body, outer, CORNER_R)
    chamfer_top(comp, body, TOP_CHAMFER)

    # screw bosses (hang from the top; carrier plate screws up into them)
    for (x, y) in SCREW_XY:
        cyl(comp, x, y, 6, BOSS_D, CAV_TOP - 6, JOIN, [body])
        cyl(comp, x, y, 5, BOSS_PILOT, CAV_TOP - 5, CUT, [body])

    # internal seating ledge: the plate slides up, its edges hit this, and STOP (no sinking)
    frame_at(comp, body, 0, 0, IN_W, IN_H, LEDGE_W, PLATE_SEAT_Z, LEDGE_H, JOIN)

    # cross-flow grilles: back wall (-Y) = INTAKE, front wall (+Y) = EXHAUST.
    # VERTICAL slots -> each only bridges ~3mm at its top -> prints support-free. Sides solid.
    gx0 = -(GRILLE_N - 1) * GRILLE_PITCH / 2.0
    for cy in (-H / 2, H / 2):
        for i in range(GRILLE_N):
            box(comp, gx0 + i * GRILLE_PITCH, cy, GRILLE_Z0,
                GRILLE_W, WALL * 3, GRILLE_LEN, CUT, [body])

    # cable entry as a NOTCH in the open rim (no bridge) - exits between cover + plate
    box(comp, 0, -H / 2, -1, ENTRY_W, WALL * 3, ENTRY_H + 1, CUT, [body])

    # ---- top panel features ----
    pocket(comp, body, 0, SCR_Y, SCR_BW, SCR_BH, BEZEL_DEPTH)      # screen bezel
    thru(comp, body, 0, SCR_Y, SCR_W, SCR_H)                       # screen window
    for lx in (LED1_X, LED2_X):
        pocket_c(comp, body, lx, LED_Y, LED_BEZEL_D, LED_BEZEL_DEPTH)
        thru_c(comp, body, lx, LED_Y, LED_D)

    chamfer_mouths(comp, body, MOUTH_CHAMFER)

    # premium details - all RECESSED so the top face prints FLAT face-down (no floating)
    frame_at(comp, body, 0, 0, W - 2 * PANEL_INSET, H - 2 * PANEL_INSET,
             PANEL_W, FACE_TOP - PANEL_DEPTH, PANEL_DEPTH + 0.5, CUT)   # panel line
    frame_at(comp, body, 0, SCR_Y, SCR_BW + 2 * LENS_W, SCR_BH + 2 * LENS_W,
             LENS_W, FACE_TOP - 0.6, 1.1, CUT)                          # recessed screen frame
    # (raised LED rings removed - the LEDs keep their recessed bezel pocket above)

    # lettering
    for (lx, nm) in [(LED1_X, 'POWER'), (LED2_X, 'INTERNET')]:
        text(comp, body, nm, lx, LED_Y - 10, 3.0, ENGRAVE)
    text(comp, body, LOGO_TEXT, 0, LOGO_Y, LOGO_H, LOGO_EMBOSS, emboss=False)  # engraved = flat top

    # small spec in the bottom-right corner of the TOP face (same reliable method as the logo)
    for i, line in enumerate(SPEC_LINES):
        text(comp, body, line, 38, -40 - i * 3.5, 2.0, ENGRAVE)

    build_inside_mounts(comp, body)
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
        build(design.rootComponent)
        vp = app.activeViewport
        try:
            cam = vp.camera
            cam.viewOrientation = adsk.core.ViewOrientations.TopViewOrientation
            vp.camera = cam
        except Exception:
            pass
        vp.fit()
        if SKIPPED:
            ui.messageBox('Module gadget built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_ModuleGadget failed:\n{}'.format(traceback.format_exc()))
