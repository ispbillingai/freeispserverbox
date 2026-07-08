# FIR_FullBox.py - Autodesk Fusion 360 script
# COMPLETE 280x280 box assembly with EVERY component placed + labelled, so you can see how
# it all fits and where the free space is. Internal blocks are labelled stand-ins (hide/
# delete the "(part)" bodies before printing the real shell).
#
# LAYOUT:
#   bottom-front : RB951 router + PoE switch (ports out the front)
#   bottom-back  : power EXTENSION lying flat, ADAPTERS standing up out of it
#   bottom-right : SIREN + mains strip (gland / fuse / terminals)
#   upper shelf  : the BRAIN module (screen/LEDs to the front)
#   + port plate at the front, + lid lifted off.

import adsk.core, adsk.fusion, adsk.cam, traceback

BOX_W, BOX_D, BOX_H = 280.0, 280.0, 95.0
WALL, FLOOR = 2.5, 3.0
HALF_W, HALF_D = BOX_W / 2, BOX_D / 2
FRONT_Y = HALF_D - WALL
SHELF_Z = 45.0

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


def label(comp, body, s, cx, cy, h, z_top):
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
            adsk.core.ValueInput.createByReal(mm(z_top - 0.8)))
        ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(1.3)))
        ei.participantBodies = [body]
        ff.add(ei)
    except Exception as e:
        SKIPPED.append('label {}: {}'.format(s, e))


def part(comp, name, cx, cy, z0, sx, sy, sz, lbl):
    b = box(comp, cx, cy, z0, sx, sy, sz, NEW).bodies.item(0)
    b.name = name
    label(comp, b, lbl, cx, cy, min(7.0, sx / max(1, len(lbl)) * 1.5), z0 + sz)
    return b


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

        # ---- SHELL: floor + 4 walls (front wall kept; ports/UI break through it) ----
        shell = box(comp, 0, 0, 0, BOX_W, BOX_D, FLOOR, NEW).bodies.item(0)
        shell.name = '0 BOX SHELL 280x280'
        fillet_vertical(comp, shell, 10.0)
        box(comp, -HALF_W + WALL / 2, 0, FLOOR, WALL, BOX_D, BOX_H, JOIN, [shell])   # left
        box(comp,  HALF_W - WALL / 2, 0, FLOOR, WALL, BOX_D, BOX_H, JOIN, [shell])   # right
        box(comp, 0, -HALF_D + WALL / 2, FLOOR, BOX_W, WALL, BOX_H, JOIN, [shell])   # back
        box(comp, 0,  HALF_D - WALL / 2, FLOOR, BOX_W, WALL, BOX_H, JOIN, [shell])   # front

        # ---- BOTTOM-FRONT: router + PoE, ports out the front ----
        part(comp, '1 RB951 router (part)', -78, FRONT_Y - 2 - 139 / 2, FLOOR + 3, 114, 139, 29, 'RB951')
        part(comp, '2 PoE switch (part)',    60, FRONT_Y - 2 - 100 / 2, FLOOR + 3, 100, 100, 28, 'PoE')

        # ---- BOTTOM-BACK: extension lying flat + adapters standing up ----
        ext_cy = -HALF_D + WALL + 47 / 2 + 4
        part(comp, '3 Extension (part)', 0, ext_cy, FLOOR, 240, 47, 28, 'EXTENSION 240')
        for ax in (-80, 0, 80):
            part(comp, '4 Adapter (part)', ax, ext_cy, FLOOR + 28, 46, 46, 52, 'ADPT')

        # ---- BOTTOM-RIGHT: siren + mains strip ----
        sir = cyl(comp, 95, -95, FLOOR, 70, 50, NEW).bodies.item(0)
        sir.name = '5 Siren 12V (part)'
        label(comp, sir, 'SIREN', 95, -95, 8, FLOOR + 50)
        part(comp, '6 Fuse (part)',        118, -25, FLOOR, 22, 12, 14, 'FUSE')
        part(comp, '7 L/N/E terminals (part)', 116, -55, FLOOR, 40, 16, 22, 'L N E')
        cyl(comp, HALF_W - WALL, -45, FLOOR, 20, FLOOR + 1, NEW)   # POWER IN gland marker

        # ===== RETENTION - the features that HOLD everything so nothing shifts =====
        def cap4(cx, cy, sx, sy, h):                                # 4 corner posts hug a footprint
            for dx in (-1, 1):
                for dy in (-1, 1):
                    box(comp, cx + dx * (sx / 2 + 3.5), cy + dy * (sy / 2 + 3.5), FLOOR, 6, 6, h, JOIN, [shell])
        cap4(-78, FRONT_Y - 2 - 139 / 2, 114, 139, 22)             # RB951 captured (drop-in; lid presses)
        cap4(60, FRONT_Y - 2 - 100 / 2, 100, 100, 22)              # PoE captured
        for ex in (-123, 123):                                     # extension end-clamps (240mm strip)
            box(comp, ex, ext_cy, FLOOR, 5, 55, 30, JOIN, [shell])
        box(comp, 0, ext_cy + 47 / 2 + 5, FLOOR, 252, 4, 60, JOIN, [shell])   # cradle wall keeps adapters from tipping
        cyl(comp, 95, -95, FLOOR, 82, 24, JOIN, [shell])           # siren ring clamp...
        cyl(comp, 95, -95, FLOOR - 1, 72, 26, CUT, [shell])
        for tx in (-22, 22):                                       # terminal-block cradle walls
            box(comp, 116 + tx, -55, FLOOR, 3, 18, 24, JOIN, [shell])

        # ---- UPPER SHELF + the BRAIN module BOLTED to it ----
        shelf = box(comp, -5, 70, SHELF_Z, 150, 130, 3, NEW).bodies.item(0)
        shelf.name = '8 SHELF'
        mcy = FRONT_Y - 2 - 120 / 2
        for bx in (-58.5, 58.5):                                   # 4 bolt standoffs - module screws onto these
            for byo in (-50, 50):
                cyl(comp, -5 + bx, mcy + byo, SHELF_Z + 3, 7, 4, JOIN, [shelf])
                cyl(comp, -5 + bx, mcy + byo, SHELF_Z + 3, 2.6, 5, CUT, [shelf])
        part(comp, '9 Brain module (part)', -5, mcy, SHELF_Z + 7, 135, 120, 40, 'BRAIN + SCREEN')

        # ---- PORT PLATE at the front (real openings live in FIR_PortPlate) ----
        pp = box(comp, -78, HALF_D - 1, 0, 126, 3, 41, NEW).bodies.item(0)
        pp.name = '10 PORT PLATE (FIR_PortPlate)'

        # ---- LID (lifted off) ----
        lid = box(comp, 0, 0, BOX_H + 26, BOX_W, BOX_D, 4, NEW).bodies.item(0)
        lid.name = '11 LID (lifted)'
        fillet_vertical(comp, lid, 10.0)

        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Full box built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_FullBox failed:\n{}'.format(traceback.format_exc()))
