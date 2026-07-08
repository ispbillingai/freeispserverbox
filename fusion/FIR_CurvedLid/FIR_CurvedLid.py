# FIR_CurvedLid.py - Autodesk Fusion 360 script
# The snap-on LID COVER - 4 sides: FRONT face (280 x 80, holes) + TOP (280 x 65) + 2 ENDS
# (65 x 80). Open BACK (closed by the bottom lid) + open BOTTOM (closed by the 65mm shelf).
# Modelled with the FRONT face flat on Z=0 so the ports cut straight down (reliable). The
# top + ends extend back in +Z by the 65mm depth. 10 RJ45 + Ø3 power, each a 0.55mm pop-open skin.

import adsk.core, adsk.fusion, adsk.cam, traceback

LEN, HEIGHT, DEPTH = 280.0, 80.0, 65.0       # length x height x depth
WALL = 2.5
SKIN = 0.55
HOLE_D = 7.0                                 # cat6 notch width (cable slides in from the open bottom)
PWR_D = 7.0                                  # power cable notch width
NOTCH_H = 7.0                                # short, rounded - rises ~7mm then a semicircle top
RJ45_X = [-90.5, -76.5, -62.5, -48.5, -34.5, 53.0, 69.0, 85.0, 101.0, 117.0]

# ---- slide-and-click (researched): cover slides FRONT->BACK onto RAILS on the bottom-lid SHELF ----
# The clip is DOWN LOW on the shelf (the only part running under the cover in the slide direction).
CLR = 0.4                                     # slide clearance per side (FDM/PETG)
RAIL_X = 133.0                                # rail X (matches FIR_BottomLid shelf rails)
SHELF_TOP_Y = -HEIGHT / 2.0                   # cover sits on the shelf -> bottom edge = shelf top
RAIL_TOP_Y = SHELF_TOP_Y + 5.0                # rail is 5mm tall on the shelf
TZ0, TZ1 = WALL, DEPTH - 2.0                  # catch runs along Z; OPEN at the back (rail enters).
                                              # TZ0 MUST be WALL: the catch grows off the front face
                                              # inner (z=2.5) - at 3.0 it floated 0.5mm behind it

CM = 0.1
def mm(v):
    return v * CM

NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
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

        # FRONT face (280 x 80), flat on Z=0 - the ports cut straight DOWN through it
        front = box(comp, 0, 0, 0, LEN, HEIGHT, WALL, NEW).bodies.item(0)
        front.name = 'FIR Lid Cover (4 sides)'
        depth = (WALL - SKIN) + 1                          # leaves a 0.55mm pop-open skin
        bottom = -HEIGHT / 2.0                             # the open bottom edge of the face
        top_y = bottom + NOTCH_H                           # rounded top of each notch

        def notch(cx, w):
            # arch notch OPEN at the bottom edge: a slot up from below the edge + a rounded top
            box(comp, cx, (bottom - 2 + top_y) / 2.0, -1, w, (top_y - (bottom - 2)), depth, CUT, [front])
            cyl(comp, cx, top_y, -1, w, depth, CUT, [front])

        for rx in RJ45_X:
            notch(rx, HOLE_D)                              # 10 cat6 arch notches
        notch(10, PWR_D)                                   # power notch (7mm)

        # TOP wall (280 x 65) along the top edge, extending back +Z
        box(comp, 0, HEIGHT / 2 - WALL / 2, 0, LEN, WALL, DEPTH, JOIN, [front])
        # TOP TONGUE: a small 1mm rib on the top-wall back edge that seats into the lid's top groove.
        # Centred at y38.5 = the groove centre (tub Z81.5) -> ±0.3 play; riding at the wall centre
        # (38.75) left only 0.05mm top clearance = jam
        box(comp, 0, 38.5, DEPTH, 250, 1.0, 1.0, JOIN, [front])
        # 2 END walls (65 x 80) at each end, extending back +Z
        for sx in (-LEN / 2 + WALL / 2, LEN / 2 - WALL / 2):
            box(comp, sx, 0, 0, WALL, HEIGHT, DEPTH, JOIN, [front])

        # ---- SLIDE catch: a SLIDING-FIT inverted-U. The HOLD comes from the rounded detent, NOT
        #      from clamping the sides - so it slides in and pulls back out without jamming. ----
        half = 2.0 + 0.3                                  # rail half-width(2) + 0.3mm SLIDING clearance
        RIBW = 1.6
        rib_cy = (SHELF_TOP_Y + RAIL_TOP_Y + 0.3) / 2.0
        rib_h = (RAIL_TOP_Y + 0.3) - SHELF_TOP_Y
        for side in (-1, 1):
            sx = side * RAIL_X
            # CAP over the rail (0.3mm above - guides, doesn't clamp)
            box(comp, sx, RAIL_TOP_Y + 1.8, TZ0, 2 * (half + RIBW), 3.0, TZ1 - TZ0, JOIN, [front])
            # two guide ribs 0.3mm off the rail sides (slides smoothly, no wobble)
            for off in (-(half + RIBW / 2.0), half + RIBW / 2.0):
                box(comp, sx + off, rib_cy, TZ0, RIBW, rib_h, TZ1 - TZ0, JOIN, [front])

        # ---- LOCK SCREWS: slide it on, then 2 M3 screws (front, into the shelf bosses) hold it closed ----
        for sx in (-125, 125):
            cyl(comp, sx, -31.0, -1, 3.4, WALL + 2, CUT, [front])     # M3 clearance through the front face

        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Cover built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_CurvedLid failed:\n{}'.format(traceback.format_exc()))
