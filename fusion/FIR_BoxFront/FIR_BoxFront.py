# FIR_BoxFront.py - Autodesk Fusion 360 script
# The big-box FRONT panel, inverter-style: a window where the sealed module shows
# through (screen + LEDs), the RFID TAP pad, a low-front MAIN SWITCH cutout, a side
# vent group, branding - and a SELF-LOCKING access door (printed snap-latch now,
# with a hidden pocket for an RFID-released servo bolt later).
# Two bodies: the panel + the door. Mounts on the front of the bought IP65 box.
#
#  >>> MEASURE your real box front and set PANEL_W/H to it. This is a concept. <<<

import adsk.core, adsk.fusion, adsk.cam, traceback

# ---------------- PANEL ----------------
PANEL_W, PANEL_H, PANEL_TH = 290.0, 240.0, 4.0     # MEASURE the real box front
CORNER_R, FRONT_EDGE, MOUTH_CHAMFER = 14.0, 1.5, 0.4
FACE_TOP = PANEL_TH

# module window (the sealed module sits behind; its face shows through)
WIN_W, WIN_H, WIN_Y = 150.0, 120.0, 25.0
WIN_BEZEL, WIN_BEZEL_DEPTH = 6.0, 1.5              # front bezel frame around the window
WIN_LIP, WIN_LIP_DEPTH = 6.0, 6.0                 # back ledge the module rests against

# RFID TAP pad (reachable here on the front)
TAP_X, TAP_Y, TAP_D, TAP_DEPTH = 45.0, -72.0, 38.0, 1.5
WAVE_DY, WAVE_RADII, WAVE_W = 8.0, [3.5, 5.5, 7.5], 0.8

# main switch (rocker / MCB) cutout - low front
SW_W, SW_H, SW_X, SW_Y = 30.0, 22.0, 100.0, -75.0

# self-locking access door (hides reset/SIM/buttons)
DOOR_X, DOOR_Y, DOOR_W, DOOR_H, DOOR_TH = -80.0, -75.0, 60.0, 44.0, 3.0
DOOR_RECESS, DOOR_GAP = 3.4, 0.6
SERVO_W, SERVO_H, SERVO_D = 8.0, 14.0, 6.0        # hidden servo-bolt pocket (premium lock)

LOGO_TEXT, LOGO_Y, LOGO_H, LOGO_EMBOSS = 'FreeISP', 95.0, 18.0, 0.8
LABEL_LINES = ['FREEISPRADIUS  Model FIR-HS250', '12V/220V  S/N FHS250...']
LABEL_Y = -110.0
PANEL_INSET, PANEL_W_LINE, PANEL_DEPTH = 10.0, 1.2, 0.6
# side vent louvres (through the panel, lower-left group)
VENT_N, VENT_LEN, VENT_H, VENT_PITCH, VENT_X, VENT_Y0 = 6, 30.0, 2.0, 4.5, -120.0, -55.0
ENGRAVE = 0.5

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


def text(comp, body, s, cx, cy, h, depth, emboss=False, z_top=None):
    if z_top is None:
        z_top = FACE_TOP
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sts = sk.sketchTexts
        ti = sts.createInput2(s, mm(h))
        w = mm(h) * max(1, len(s)) * 0.62
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
        z0 = z_top if emboss else z_top - depth
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


def build_door(comp):
    # separate body: the self-locking access door, shown closed in its recess
    dw, dh = DOOR_W - 2 * DOOR_GAP, DOOR_H - 2 * DOOR_GAP
    z0 = FACE_TOP - DOOR_TH
    door = box(comp, DOOR_X, DOOR_Y, z0, dw, dh, DOOR_TH, NEW).bodies.item(0)
    door.name = 'FIR Access Door'
    fillet_vertical(comp, door, 4.0)
    # snap hook on the right edge (clicks behind the frame catch)
    hx = DOOR_X + dw / 2
    box(comp, hx, DOOR_Y, z0 - 2, 2.5, 12, 2.0, JOIN, [door])      # hook arm down
    box(comp, hx + 1.2, DOOR_Y, z0 - 2, 2.5, 12, 2.0, JOIN, [door])  # hook lip
    # living-hinge stub on the left edge
    box(comp, DOOR_X - dw / 2 - 1, DOOR_Y, z0 + DOOR_TH / 2 - 0.3, 2.5, 16, 0.6, JOIN, [door])
    # finger pull scoop on the right
    cyl(comp, hx - 3, DOOR_Y, FACE_TOP - 1.5, 9, 2.0, CUT, [door])
    return door


def build_front(comp):
    panel = box(comp, 0, 0, 0, PANEL_W, PANEL_H, PANEL_TH, NEW).bodies.item(0)
    panel.name = 'FIR Box Front'
    fillet_vertical(comp, panel, CORNER_R)

    # module window: front bezel + through opening + back ledge for the module
    box(comp, 0, WIN_Y, FACE_TOP - WIN_BEZEL_DEPTH, WIN_W + 2 * WIN_BEZEL,
        WIN_H + 2 * WIN_BEZEL, WIN_BEZEL_DEPTH + 0.5, CUT, [panel])
    box(comp, 0, WIN_Y, -1, WIN_W, WIN_H, PANEL_TH + 2, CUT, [panel])
    box(comp, 0, WIN_Y, -1, WIN_W + 2 * WIN_LIP, WIN_H + 2 * WIN_LIP,
        WIN_LIP_DEPTH, CUT, [panel])                                  # back ledge

    # RFID TAP pad
    cyl(comp, TAP_X, TAP_Y, FACE_TOP - TAP_DEPTH, TAP_D, TAP_DEPTH + 0.5, CUT, [panel])
    for r in WAVE_RADII:
        ring(comp, panel, TAP_X, TAP_Y + WAVE_DY, r, WAVE_W, FACE_TOP - TAP_DEPTH, 0.4)

    # (main switch moved to the bottom compartment box - FIR_BottomBox)

    # side vent louvres (lower group)
    for i in range(VENT_N):
        box(comp, VENT_X, VENT_Y0 + i * VENT_PITCH, -1, VENT_LEN, VENT_H, PANEL_TH + 2, CUT, [panel])

    # ---- self-locking access door: frame recess + catch + servo pocket ----
    box(comp, DOOR_X, DOOR_Y, FACE_TOP - DOOR_RECESS, DOOR_W, DOOR_H, DOOR_RECESS + 0.5, CUT, [panel])
    box(comp, DOOR_X, DOOR_Y, -1, DOOR_W - 16, DOOR_H - 16, PANEL_TH + 2, CUT, [panel])  # access hole
    cx = DOOR_X + DOOR_W / 2 - 1                                       # catch ledge (hook grabs it)
    box(comp, cx, DOOR_Y, FACE_TOP - DOOR_RECESS - 2, 2.0, 14, 2.0, JOIN, [panel])
    box(comp, cx + 2, DOOR_Y, -SERVO_D, SERVO_W, SERVO_H, SERVO_D, CUT, [panel])  # servo-bolt pocket (back)

    # branding + label + panel line
    text(comp, panel, LOGO_TEXT, 0, LOGO_Y, LOGO_H, LOGO_EMBOSS, emboss=True)
    for i, line in enumerate(LABEL_LINES):
        text(comp, panel, line, 0, LABEL_Y - i * 7, 4.0, ENGRAVE)
    frame_at(comp, panel, 0, 0, PANEL_W - 2 * PANEL_INSET, PANEL_H - 2 * PANEL_INSET,
             PANEL_W_LINE, FACE_TOP - PANEL_DEPTH, PANEL_DEPTH + 0.5, CUT)
    return panel


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
        build_front(design.rootComponent)
        build_door(design.rootComponent)
        vp = app.activeViewport
        try:
            cam = vp.camera
            cam.viewOrientation = adsk.core.ViewOrientations.TopViewOrientation
            vp.camera = cam
        except Exception:
            pass
        vp.fit()
        if SKIPPED:
            ui.messageBox('Box front built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_BoxFront failed:\n{}'.format(traceback.format_exc()))
