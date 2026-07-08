# FIR_Faceplate.py - Autodesk Fusion 360 script
# Builds the FREEISPRADIUS front faceplate to match the approved concept render:
# rounded corners, embossed "FreeISP" logo, light-bar slot, recessed screen window
# + bezel, two LED bezels (POWER / INTERNET), recessed RFID TAP zone, access-door
# recess with grip notch, and a spec-label recess.
#
# Single body (works in a Part Design document). All dims in mm - edit + re-run.
# The render's glow / soft-dome body / cable glands are box-level, not this plate.

import adsk.core, adsk.fusion, adsk.cam, traceback

# ---------------- PANEL ----------------
FP_W, FP_H, FP_TH = 135.0, 120.0, 4.0     # width(X) x height(Y) x thickness(Z)
CORNER_R = 7.0                             # rounded corners
FRONT_EDGE_R = 1.5                         # soft rounded front edge (molded look)
MOUTH_CHAMFER = 0.4                        # crisp chamfer on every cutout mouth
PANEL_INSET, PANEL_W, PANEL_DEPTH = 6.0, 1.0, 0.6   # recessed perimeter panel-line
LENS_W, LENS_PROUD = 2.0, 0.8                        # raised screen "glass lens" surround

# ---------------- MOUNTING SCREWS (counterbored, flush heads) ----------------
SCREW_XY = [(-(FP_W / 2 - 9), (FP_H / 2 - 10)), ((FP_W / 2 - 9), (FP_H / 2 - 10)),
            (-(FP_W / 2 - 9), -(FP_H / 2 - 10)), ((FP_W / 2 - 9), -(FP_H / 2 - 10))]
SCREW_CLEAR_D = 3.4                         # M3 clearance through hole
SCREW_CB_D, SCREW_CB_DEPTH = 7.0, 2.2      # counterbore so the head sits below the face

# ---------------- LOGO ----------------
LOGO_TEXT, LOGO_Y, LOGO_H, LOGO_EMBOSS = 'FreeISP', 46.0, 11.0, 0.6

# ---------------- LIGHT BAR (through slot, diffuser behind) ----------------
BAR_Y, BAR_L, BAR_T = 33.0, 68.0, 4.0

# ---------------- SCREEN (1.8" window + recessed bezel) ----------------
SCR_Y = 12.0
SCR_W, SCR_H = 32.0, 26.0                  # through window
SCR_BW, SCR_BH, BEZEL_DEPTH = 42.0, 34.0, 1.2   # bezel pocket

# ---------------- STATUS LEDs ----------------
LED_Y = -14.0
LED1_X, LED2_X = -16.0, 10.0               # POWER, INTERNET
LED_D, LED_BEZEL_D, LED_BEZEL_DEPTH = 11.0, 15.0, 1.0
LED_LABEL_H, LED_LABEL_DY = 3.0, -10.0

# ---------------- RFID TAP ZONE (smaller, less dominant) ----------------
TAP_X, TAP_Y, TAP_D, TAP_DEPTH = 46.0, 6.0, 28.0, 1.0
TAP_TEXT_H, TAP_TEXT_DY = 3.2, -8.0
WAVE_DY, WAVE_RADII, WAVE_W = 6.0, [2.5, 4.0, 5.5], 0.6

# ---------------- ACCESS DOOR (recessed flap + grip notch) ----------------
DOOR_X, DOOR_Y, DOOR_W, DOOR_H, DOOR_DEPTH = -24.0, -42.0, 44.0, 22.0, 1.5
GRIP_D, GRIP_DEPTH = 10.0, 2.5

# ---------------- SPEC LABEL (recess for printed sticker) ----------------
LBL_X, LBL_Y, LBL_W, LBL_H, LBL_DEPTH = 32.0, -42.0, 36.0, 22.0, 0.6
LBL_LINES = ['FREEISPRADIUS', 'Model FIR-HS250', '12V 2A']

ENGRAVE_DEPTH = 0.5

# ================= BACK-SIDE MOUNTING (behind the cover) =================
ADD_BACK = True
# 1.8" screen module mount  (VERIFY board size with calipers on arrival)
SCR_PCB_W, SCR_PCB_H, SCR_BOSS_INSET = 56.0, 34.0, 3.0
SCR_BOSS_D, SCR_BOSS_H, SCR_BOSS_PILOT = 6.0, 6.0, 1.7
# LED guide collars (behind each LED hole)
LED_COLLAR_OD, LED_COLLAR_H = 16.0, 5.0
# RFID RC522 cradle behind TAP (portrait; VERIFY + nudge to your real board)
RFID_CX, RFID_CY, RFID_W, RFID_H = 46.0, -15.0, 40.0, 58.0
RFID_BOSS_INSET, RFID_BOSS_D, RFID_BOSS_H, RFID_BOSS_PILOT = 4.0, 6.0, 5.0, 1.7
# cable tie-down bridges (loop a zip tie under each)
TIE_BRIDGE_XY = [(-20.0, -40.0), (20.0, -40.0)]
# locating lip / rim (nests into the box - tune to the base at integration)
LIP_OW, LIP_OH, LIP_WALL, LIP_H = 119.0, 89.0, 2.5, 4.0

CM = 0.1
def mm(v):
    return v * CM

NEW  = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation

SKIPPED = []


def _extrude(comp, prof, z0, sz, op, participants):
    feats = comp.features.extrudeFeatures
    ei = feats.createInput(prof, op)
    if abs(z0) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(z0)))
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(sz)))
    if participants:
        ei.participantBodies = participants
    return feats.add(ei)


def box(comp, cx, cy, z0, sx, sy, sz, op, participants=None):
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchLines.addCenterPointRectangle(
        adsk.core.Point3D.create(mm(cx), mm(cy), 0),
        adsk.core.Point3D.create(mm(cx + sx / 2.0), mm(cy + sy / 2.0), 0))
    return _extrude(comp, sk.profiles.item(0), z0, sz, op, participants)


def cyl(comp, cx, cy, z0, d, sz, op, participants=None):
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(d / 2.0))
    return _extrude(comp, sk.profiles.item(0), z0, sz, op, participants)


def pocket_box(comp, body, cx, cy, sx, sy, depth):
    box(comp, cx, cy, FP_TH - depth, sx, sy, depth + 0.5, CUT, [body])


def pocket_cyl(comp, body, cx, cy, d, depth):
    cyl(comp, cx, cy, FP_TH - depth, d, depth + 0.5, CUT, [body])


def fillet_corners(comp, body, r):
    try:
        coll = adsk.core.ObjectCollection.create()
        for e in body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                v = g.startPoint.vectorTo(g.endPoint)
                v.normalize()
                if abs(v.z) > 0.99:
                    coll.add(e)
        if coll.count == 0:
            return
        fin = comp.features.filletFeatures.createInput()
        fin.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
        comp.features.filletFeatures.add(fin)
    except Exception as e:
        SKIPPED.append('corner fillet: {}'.format(e))


def fillet_front_edge(comp, body, r):
    # soften the front perimeter (the molded, manufactured look)
    try:
        front, best = None, -1.0
        for f in body.faces:
            g = f.geometry
            if isinstance(g, adsk.core.Plane) and abs(g.normal.z) > 0.99:
                bb = f.boundingBox
                if abs((bb.minPoint.z + bb.maxPoint.z) / 2 - mm(FP_TH)) < mm(0.05):
                    if f.area > best:
                        best, front = f.area, f
        if not front:
            return
        coll = adsk.core.ObjectCollection.create()
        for loop in front.loops:
            if loop.isOuter:
                for e in loop.edges:
                    coll.add(e)
        if coll.count == 0:
            return
        fin = comp.features.filletFeatures.createInput()
        fin.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
        comp.features.filletFeatures.add(fin)
    except Exception as e:
        SKIPPED.append('front edge fillet: {}'.format(e))


def _front_face(body):
    front, best = None, -1.0
    for f in body.faces:
        g = f.geometry
        if isinstance(g, adsk.core.Plane) and abs(g.normal.z) > 0.99:
            bb = f.boundingBox
            if abs((bb.minPoint.z + bb.maxPoint.z) / 2 - mm(FP_TH)) < mm(0.05):
                if f.area > best:
                    best, front = f.area, f
    return front


def chamfer_mouths(comp, body, c):
    # crisp chamfer on every cutout / hole mouth = the molded, manufactured edge
    try:
        front = _front_face(body)
        if not front:
            return
        coll = adsk.core.ObjectCollection.create()
        for loop in front.loops:
            if not loop.isOuter:
                for e in loop.edges:
                    coll.add(e)
        if coll.count == 0:
            return
        cf = comp.features.chamferFeatures
        ci = cf.createInput2()
        ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            coll, adsk.core.ValueInput.createByReal(mm(c)), False)
        cf.add(ci)
    except Exception as e:
        SKIPPED.append('mouth chamfer: {}'.format(e))


def text(comp, body, s, cx, cy, h, z_top, depth, emboss=False):
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sts = sk.sketchTexts
        ti = sts.createInput2(s, mm(h))
        w = mm(h) * max(1, len(s)) * 0.72
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
        feats = comp.features.extrudeFeatures
        op = JOIN if emboss else CUT
        z0 = z_top if emboss else z_top - depth
        sz = depth if emboss else depth + 0.5
        try:
            ei = feats.createInput(st, op)
        except Exception:
            profs = adsk.core.ObjectCollection.create()
            for p in sk.profiles:
                profs.add(p)
            ei = feats.createInput(profs, op)
        if abs(z0) > 1e-9:
            ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
                adsk.core.ValueInput.createByReal(mm(z0)))
        ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(sz)))
        ei.participantBodies = [body]
        feats.add(ei)
    except Exception as e:
        SKIPPED.append('text "{}": {}'.format(s, e))


def ring(comp, body, cx, cy, r_out, width, z_top, depth):
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        cc = sk.sketchCurves.sketchCircles
        cc.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(r_out))
        cc.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(r_out - width))
        prof = None
        for p in sk.profiles:
            if p.profileLoops.count == 2:
                prof = p
                break
        if not prof:
            return
        _extrude(comp, prof, z_top - depth, depth + 0.5, CUT, [body])
    except Exception as e:
        SKIPPED.append('wave ring: {}'.format(e))


def back_post(comp, body, x, y, d, h, pilot):
    # boss extending back (-Z) with a pilot hole for a self-tapping screw
    cyl(comp, x, y, 0, d, -h, JOIN, [body])
    cyl(comp, x, y, -h, pilot, h + 0.3, CUT, [body])


def tie_bridge(comp, body, x, y, gap=6.0, leg=3.0, h=6.0, bar=2.0):
    # two legs + a top bar = a loop to thread a zip tie under (gap to plate)
    box(comp, x - (gap + leg) / 2, y, 0, leg, leg, -h, JOIN, [body])
    box(comp, x + (gap + leg) / 2, y, 0, leg, leg, -h, JOIN, [body])
    box(comp, x, y, -(h - bar), gap + 2 * leg, leg, -bar, JOIN, [body])


def build_back(comp, body):
    # locating lip / rim around the back
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        L = sk.sketchCurves.sketchLines
        L.addCenterPointRectangle(adsk.core.Point3D.create(0, 0, 0),
                                  adsk.core.Point3D.create(mm(LIP_OW / 2), mm(LIP_OH / 2), 0))
        L.addCenterPointRectangle(adsk.core.Point3D.create(0, 0, 0),
                                  adsk.core.Point3D.create(mm(LIP_OW / 2 - LIP_WALL),
                                                           mm(LIP_OH / 2 - LIP_WALL), 0))
        prof = None
        for p in sk.profiles:
            if p.profileLoops.count == 2:
                prof = p
                break
        if prof:
            _extrude(comp, prof, 0, -LIP_H, JOIN, [body])
    except Exception as e:
        SKIPPED.append('back lip: {}'.format(e))

    # screen module bosses (around the window)
    sx, sy = SCR_PCB_W / 2 - SCR_BOSS_INSET, SCR_PCB_H / 2 - SCR_BOSS_INSET
    for dx in (-sx, sx):
        for dy in (-sy, sy):
            back_post(comp, body, dx, SCR_Y + dy, SCR_BOSS_D, SCR_BOSS_H, SCR_BOSS_PILOT)

    # LED guide collars (behind each LED hole)
    for lx in (LED1_X, LED2_X):
        cyl(comp, lx, LED_Y, 0, LED_COLLAR_OD, -LED_COLLAR_H, JOIN, [body])
        cyl(comp, lx, LED_Y, -LED_COLLAR_H, LED_D, LED_COLLAR_H + 0.3, CUT, [body])

    # RFID RC522 cradle bosses behind the TAP zone
    rx, ry = RFID_W / 2 - RFID_BOSS_INSET, RFID_H / 2 - RFID_BOSS_INSET
    for dx in (-rx, rx):
        for dy in (-ry, ry):
            back_post(comp, body, RFID_CX + dx, RFID_CY + dy,
                      RFID_BOSS_D, RFID_BOSS_H, RFID_BOSS_PILOT)

    # cable tie-down bridges
    for (tx, ty) in TIE_BRIDGE_XY:
        tie_bridge(comp, body, tx, ty)


def frame_at(comp, body, cx, cy, ow, oh, t, z0, h, op):
    # rectangular ring centred at (cx,cy): groove (CUT) or raised surround (JOIN)
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        L = sk.sketchCurves.sketchLines
        L.addCenterPointRectangle(adsk.core.Point3D.create(mm(cx), mm(cy), 0),
                                  adsk.core.Point3D.create(mm(cx + ow / 2), mm(cy + oh / 2), 0))
        L.addCenterPointRectangle(adsk.core.Point3D.create(mm(cx), mm(cy), 0),
                                  adsk.core.Point3D.create(mm(cx + ow / 2 - t), mm(cy + oh / 2 - t), 0))
        prof = None
        for p in sk.profiles:
            if p.profileLoops.count == 2:
                prof = p
                break
        if prof:
            _extrude(comp, prof, z0, h, op, [body])
    except Exception as e:
        SKIPPED.append('frame: {}'.format(e))


def build_faceplate(comp):
    body = box(comp, 0, 0, 0, FP_W, FP_H, FP_TH, NEW).bodies.item(0)
    body.name = 'FIR Faceplate'
    fillet_corners(comp, body, CORNER_R)
    fillet_front_edge(comp, body, FRONT_EDGE_R)

    # ---- geometry first (cutouts, recesses, screws) ----
    # light bar - stadium-shaped through slot
    box(comp, 0, BAR_Y, -1, BAR_L - BAR_T, BAR_T, FP_TH + 2, CUT, [body])
    cyl(comp, -(BAR_L - BAR_T) / 2, BAR_Y, -1, BAR_T, FP_TH + 2, CUT, [body])
    cyl(comp,  (BAR_L - BAR_T) / 2, BAR_Y, -1, BAR_T, FP_TH + 2, CUT, [body])

    # screen - recessed bezel then through window
    pocket_box(comp, body, 0, SCR_Y, SCR_BW, SCR_BH, BEZEL_DEPTH)
    box(comp, 0, SCR_Y, -1, SCR_W, SCR_H, FP_TH + 2, CUT, [body])

    # status LEDs - bezel ring + through hole
    for lx in (LED1_X, LED2_X):
        pocket_cyl(comp, body, lx, LED_Y, LED_BEZEL_D, LED_BEZEL_DEPTH)
        cyl(comp, lx, LED_Y, -1, LED_D, FP_TH + 2, CUT, [body])

    # RFID TAP recess
    pocket_cyl(comp, body, TAP_X, TAP_Y, TAP_D, TAP_DEPTH)

    # access door - recessed flap + finger grip notch
    pocket_box(comp, body, DOOR_X, DOOR_Y, DOOR_W, DOOR_H, DOOR_DEPTH)
    pocket_cyl(comp, body, DOOR_X, DOOR_Y - DOOR_H / 2, GRIP_D, GRIP_DEPTH)

    # spec-label recess
    pocket_box(comp, body, LBL_X, LBL_Y, LBL_W, LBL_H, LBL_DEPTH)

    # mounting screws - counterbore (flush head) + clearance hole
    for (sx, sy) in SCREW_XY:
        pocket_cyl(comp, body, sx, sy, SCREW_CB_D, SCREW_CB_DEPTH)
        cyl(comp, sx, sy, -1, SCREW_CLEAR_D, FP_TH + 2, CUT, [body])

    # crisp chamfer on every cutout mouth (the manufactured edge)
    chamfer_mouths(comp, body, MOUTH_CHAMFER)

    # ---- premium details ----
    # recessed panel-line that frames the whole face (Ubiquiti-style seam)
    frame_at(comp, body, 0, 0, FP_W - 2 * PANEL_INSET, FP_H - 2 * PANEL_INSET,
             PANEL_W, FP_TH - PANEL_DEPTH, PANEL_DEPTH + 0.5, CUT)
    # raised "glass lens" surround around the screen
    frame_at(comp, body, 0, SCR_Y, SCR_BW + 2 * LENS_W, SCR_BH + 2 * LENS_W,
             LENS_W, FP_TH, LENS_PROUD, JOIN)

    # ---- lettering & icons (after chamfer) ----
    for (lx, name) in [(LED1_X, 'POWER'), (LED2_X, 'INTERNET')]:
        text(comp, body, name, lx, LED_Y + LED_LABEL_DY, LED_LABEL_H, FP_TH, ENGRAVE_DEPTH)

    tap_face = FP_TH - TAP_DEPTH
    for r in WAVE_RADII:
        ring(comp, body, TAP_X, TAP_Y + WAVE_DY, r, WAVE_W, tap_face, 0.4)
    text(comp, body, 'TAP', TAP_X, TAP_Y + TAP_TEXT_DY, TAP_TEXT_H, tap_face, 0.4)

    lbl_face = FP_TH - LBL_DEPTH
    for i, line in enumerate(LBL_LINES):
        text(comp, body, line, LBL_X, LBL_Y + 6 - i * 6, 2.2, lbl_face, 0.3)

    # logo - raised emboss (TOP of the plate)
    text(comp, body, LOGO_TEXT, 0, LOGO_Y, LOGO_H, FP_TH, LOGO_EMBOSS, emboss=True)

    # "TOP" mark engraved on the BACK near the top edge (assembly/print reference)
    text(comp, body, 'TOP', 0, FP_H / 2 - 7, 4.0, 0.0, ENGRAVE_DEPTH)

    # back-side mounting bosses, collars, cradle, ties, lip
    if ADD_BACK:
        build_back(comp, body)
    return body


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
        build_faceplate(design.rootComponent)

        vp = app.activeViewport
        try:
            cam = vp.camera
            cam.viewOrientation = adsk.core.ViewOrientations.TopViewOrientation
            vp.camera = cam
        except Exception:
            pass
        vp.fit()

        if SKIPPED:
            ui.messageBox('Faceplate built. Skipped (your Fusion version may not '
                          'support API text/fillet extrude):\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_Faceplate failed:\n{}'.format(traceback.format_exc()))
