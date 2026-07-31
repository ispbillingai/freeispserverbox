# FIR_ModulePlate.py - Autodesk Fusion 360 script
# The ELECTRONICS TRAY. Everything electrical bolts to this one flat plate,
# which then mounts into the big box.
#
# REDRAWN 2026-07-31 for the real brain PCB (freeisp_brain rev H).
# ---------------------------------------------------------------------------
# What changed and why:
#   The old plate was 130x115 and carried FIVE loose boards on standoffs -
#   ESP32, buck, charger, MPU, battery. That is obsolete. There is now a real
#   115x115mm PCB which already carries the ESP32, the MPU and all the
#   passives, so the tray only has to hold:
#       - the PCB itself, on 4 posts matching its M3 holes (106mm square)
#       - the three WIRE-IN modules that never touch the PCB
#         (LM2596 buck, TP4056 charger, 5V boost)
#       - the 18650 holder
#   The modules go UNDERNEATH the PCB, not beside it. They need only 26% of
#   the area under a 115x115 board, so spreading them out sideways was pure
#   waste - the first draft came out 150x180. Raising the PCB on 26mm posts
#   puts all four in space that was empty anyway, and the tray is 125x125.
#
# ⚠️ KNOCK-ON: the box-side mounting for this tray must be redrawn to match
#   TRAY_MOUNT below. The old FIR_ModuleGadget shell (130x115 cavity) can no
#   longer close over this - that shell is superseded.
#
# ⚠️ Module sizes are TYPICAL for these parts. Vernier the real three and
#   correct MODULES before printing - especially the heights, which are set
#   by the trimpots, not the board.

import adsk.core, adsk.fusion, adsk.cam, traceback

# ---------------- TRAY ----------------
PLATE_W, PLATE_H, PLATE_TH = 125.0, 125.0, 3.0
PLATE_TOP = PLATE_TH
CORNER_R = 6.0

# ---------------- the PCB ----------------
# freeisp_brain rev H: 115x115, M3 holes 4.5mm in from each corner
PCB_W = PCB_H = 115.0
PCB_HOLE_PITCH = PCB_W - 2 * 4.5          # 106.0 mm square
PCB_CX, PCB_CY = 0.0, 0.0                 # PCB is centred on the tray
# 26mm: tall enough to stand the PCB OVER every module. The battery holder
# is the tallest at 20mm, so its top sits at 23mm and the board underside at
# 29mm - 6mm of clear air, which also swallows the solder joints underneath.
POST_D, POST_H, POST_PILOT = 7.0, 26.0, 2.5

# ---------------- wire-in modules: name, w, l, h, cx, cy ----------------
# Held by corner brackets + a zip tie, NOT screws: the mounting holes on
# these cheap modules move between batches, the outline does not.
# All four live UNDER the PCB. Heights include the trimpot; set the buck to
# 5.4V and the boost to 5.0V BEFORE the board goes on, because reaching them
# afterwards means taking the four PCB screws out.
MODULES = [
    ('18650 holder', 20.0, 75.0, 20.0, -35.0,   0.0),
    ('LM2596 buck',  43.0, 21.0, 14.0,  20.0,  38.0),
    ('5V boost',     17.0, 36.0, 14.0,   5.0, -25.0),
    ('TP4056',       26.0, 17.0,  6.0,  35.0, -25.0),
]
BRACKET_T, BRACKET_L = 2.5, 8.0           # corner bracket thickness / leg length
TIE_SLOT = (3.0, 10.0)                    # zip-tie slot through the plate

# tray -> box.  ⚠️ the box side must be redrawn to match these.
TRAY_MOUNT = [(0.0, -58.0), (0.0, 58.0), (-58.0, 0.0), (58.0, 0.0)]
TRAY_CLEAR, TRAY_CB, TRAY_CB_D = 3.4, 6.0, 1.5

# harness tie-downs: loop a zip tie round each pair
TIE_POSTS = [(-58.0, 26.0), (-58.0, 36.0), (58.0, 26.0), (58.0, 36.0)]

# weight savings, kept clear of every post and bracket
LIGHTEN = [(-8.0, 8.0), (46.0, 12.0), (38.0, -46.0), (-40.0, 50.0)]
LIGHTEN_SZ = (14.0, 14.0)

SHOW_PARTS = False        # True = draw the PCB and modules to check the fit

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
            fi.addConstantRadiusEdgeSet(
                coll, adsk.core.ValueInput.createByReal(mm(r)), False)
            comp.features.filletFeatures.add(fi)
    except Exception as e:
        SKIPPED.append('corner fillet: {}'.format(e))


def corner_brackets(comp, body, cx, cy, w, l, h):
    """Four L-shaped corners that locate a module by its OUTLINE.

    Deliberately not screw posts: hole positions on these modules vary
    between batches, the outside dimensions do not. 0.4mm of slack per side
    so a printed part still accepts the board.
    """
    hw, hl = w / 2.0 + 0.4, l / 2.0 + 0.4
    for sx in (-1, 1):
        for sy in (-1, 1):
            x = cx + sx * (hw + BRACKET_T / 2.0)
            y = cy + sy * (hl + BRACKET_T / 2.0)
            # one leg along X, one along Y -> an L that traps the corner
            box(comp, x - sx * (BRACKET_L - BRACKET_T) / 2.0, y,
                PLATE_TOP, BRACKET_L, BRACKET_T, h, JOIN, [body])
            box(comp, x, y - sy * (BRACKET_L - BRACKET_T) / 2.0,
                PLATE_TOP, BRACKET_T, BRACKET_L, h, JOIN, [body])


def tie_slots(comp, body, cx, cy, w):
    """A pair of slots either side of a module: one zip tie straps it down."""
    sw, sl = TIE_SLOT
    for sx in (-1, 1):
        box(comp, cx + sx * (w / 2.0 + 5.0), cy, -1, sw, sl,
            PLATE_TH + 2, CUT, [body])


def build_plate(comp):
    plate = box(comp, 0, 0, 0, PLATE_W, PLATE_H, PLATE_TH, NEW).bodies.item(0)
    plate.name = 'FIR Electronics Tray'
    fillet_vertical(comp, plate, CORNER_R)

    for (vx, vy) in LIGHTEN:
        box(comp, vx, vy, -1, LIGHTEN_SZ[0], LIGHTEN_SZ[1],
            PLATE_TH + 2, CUT, [plate])

    # ---- the PCB: 4 posts on its own M3 pattern ----
    half = PCB_HOLE_PITCH / 2.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = PCB_CX + sx * half, PCB_CY + sy * half
            cyl(comp, x, y, PLATE_TOP, POST_D, POST_H, JOIN, [plate])
            # pilot for an M3 self-tapper, stopping short of the underside
            cyl(comp, x, y, PLATE_TOP, POST_PILOT, POST_H - 0.5, CUT, [plate])

    # ---- wire-in modules ----
    for (name, w, l, h, cx, cy) in MODULES:
        wall = 5.0 if h > 10 else 3.5
        corner_brackets(comp, plate, cx, cy, w, l, wall)
        tie_slots(comp, plate, cx, cy, w)

    # ---- tray -> box ----
    for (x, y) in TRAY_MOUNT:
        cyl(comp, x, y, -1, TRAY_CLEAR, PLATE_TH + 2, CUT, [plate])
        cyl(comp, x, y, 0, TRAY_CB, TRAY_CB_D, CUT, [plate])

    # ---- harness tie-down posts ----
    for (x, y) in TIE_POSTS:
        box(comp, x, y, PLATE_TOP, 3.5, 10, 7, JOIN, [plate])

    return plate


def build_parts(comp):
    """Placeholders, to eyeball the fit. Never printed."""
    b = box(comp, PCB_CX, PCB_CY, PLATE_TOP + POST_H, PCB_W, PCB_H, 1.6,
            NEW).bodies.item(0)
    b.name = 'PART: brain PCB 115x115'
    # the ESP32 stands on its sockets above the PCB
    e = box(comp, PCB_CX, PCB_CY, PLATE_TOP + POST_H + 1.6 + 8.5,
            28.0, 56.0, 13.0, NEW).bodies.item(0)
    e.name = 'PART: ESP32 DevKitC'
    for (name, w, l, h, cx, cy) in MODULES:
        m = box(comp, cx, cy, PLATE_TOP, w, l, h, NEW).bodies.item(0)
        m.name = 'PART: ' + name


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
        build_plate(design.rootComponent)
        if SHOW_PARTS:
            build_parts(design.rootComponent)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Tray built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_ModulePlate failed:\n{}'.format(
                traceback.format_exc()))
