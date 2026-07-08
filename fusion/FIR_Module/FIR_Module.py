# FIR_Module.py - Autodesk Fusion 360 script
# Generates the FREEISPRADIUS smart-module: base tray + screw-down lid faceplate.
# Native Fusion solids, two components (FIR Base / FIR Lid).
# Mirrors build_module.py (trimesh) feature-for-feature.
# All dimensions in mm - edit the PARAMETERS block and re-run to regenerate.

import adsk.core, adsk.fusion, adsk.cam, traceback

# ---------------- PARAMETERS (mm) ----------------
IN_X, IN_Y, IN_Z = 120.0, 90.0, 45.0      # interior
WALL    = 2.5
LID_TH  = 3.0
BASE_TH = 3.0
OUT_X = IN_X + 2 * WALL
OUT_Y = IN_Y + 2 * WALL
OUT_Z = IN_Z + BASE_TH                     # base height (lid sits on top)

SCREEN_W, SCREEN_H = 30.0, 24.0            # screen window
LED_D = 5.2                                # status LED holes
TAP_D = 40.0                               # RFID tap recess dia
TAP_RECESS = 1.0                           # thin wall left so it reads through

M3 = 3.2                                   # clearance hole
BOSS_D = 7.0                               # corner screw boss OD
PILOT_D = M3 - 0.6                          # self-tap pilot (2.6)

STANDOFF_OD = 6.0
STANDOFF_H  = 4.0
STANDOFF_PILOT = 2.6

EAR_W, EAR_L, EAR_T = 18.0, 14.0, 4.0      # mounting ear
EAR_HOLE_D = 4.2
GLAND_D = 12.0                             # cable gland hole dia
GLAND_Z = BASE_TH + 12                      # gland centre height

EXPLODE_GAP = 18.0                         # float lid above base (preview)

# feature placements (mm) - match build_module.py
BOSS_XY = [(-(IN_X / 2 - 6), -(IN_Y / 2 - 6)),
           ( (IN_X / 2 - 6), -(IN_Y / 2 - 6)),
           (-(IN_X / 2 - 6),  (IN_Y / 2 - 6)),
           ( (IN_X / 2 - 6),  (IN_Y / 2 - 6))]
STANDOFFS = [(-50, -10), (-50, 10), (8, -10), (8, 10),   # ESP32-S3
             (30, -30), (30, -8),                          # LM2596 buck
             (35, 28), (-5, 28)]                           # 18650 + TP4056
SCREEN_XY = (-22, 12)
LED_XY    = [(-38, -22), (-18, -22)]
TAP_XY    = (30, 5)

CM = 0.1                                    # mm -> cm (Fusion internal unit)
def mm(v):
    return v * CM

NEW  = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation


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


def tube(comp, cx, cy, z0, od, inner_d, h, body):
    cyl(comp, cx, cy, z0, od, h, JOIN, [body])             # post
    cyl(comp, cx, cy, z0, inner_d, h + 0.5, CUT, [body])   # bore


def build_base(comp):
    base = box(comp, 0, 0, 0, OUT_X, OUT_Y, OUT_Z, NEW).bodies.item(0)
    base.name = 'FIR Base'
    box(comp, 0, 0, BASE_TH, IN_X, IN_Y, IN_Z + 1, CUT, [base])     # open-top cavity

    for (x, y) in BOSS_XY:                                  # corner screw bosses
        tube(comp, x, y, BASE_TH, BOSS_D, PILOT_D, IN_Z, base)
    for (x, y) in STANDOFFS:                                # board standoffs
        tube(comp, x, y, BASE_TH, STANDOFF_OD, STANDOFF_PILOT, STANDOFF_H, base)

    for side in (1, -1):                                    # mounting ears
        box(comp, side * (OUT_X / 2 + 6), 0, 0, EAR_W, EAR_L, EAR_T, JOIN, [base])
        cyl(comp, side * (OUT_X / 2 + 9), 0, -1, EAR_HOLE_D, EAR_T + 2, CUT, [base])

    # cable gland in the back (-Y) wall. If it lands on the wrong wall, flip the
    # sign of the distance below (xZ-plane normal direction varies by setup).
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(0), mm(GLAND_Z), 0), mm(GLAND_D / 2.0))
    feats = comp.features.extrudeFeatures
    ei = feats.createInput(sk.profiles.item(0), CUT)
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(-(OUT_Y / 2 + 2))))
    ei.participantBodies = [base]
    feats.add(ei)
    return base


def build_lid(comp, zoff=0.0):
    # zoff floats the whole lid above the base for an exploded preview
    lid = box(comp, 0, 0, zoff, OUT_X, OUT_Y, LID_TH, NEW).bodies.item(0)
    lid.name = 'FIR Lid'
    box(comp, SCREEN_XY[0], SCREEN_XY[1], zoff - 1, SCREEN_W, SCREEN_H, LID_TH + 2, CUT, [lid])
    for (x, y) in LED_XY:
        cyl(comp, x, y, zoff - 1, LED_D, LID_TH + 2, CUT, [lid])
    # RFID tap recess - blind pocket from the inside face, leaving TAP_RECESS wall
    cyl(comp, TAP_XY[0], TAP_XY[1], zoff + TAP_RECESS, TAP_D, LID_TH - TAP_RECESS + 1, CUT, [lid])
    for (x, y) in BOSS_XY:                                  # screw holes match bosses
        cyl(comp, x, y, zoff - 1, M3, LID_TH + 2, CUT, [lid])
    return lid


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

        # Part Design documents allow only one component, so build both parts
        # as two bodies inside the single root component (no sub-components).
        root = design.rootComponent
        build_base(root)
        build_lid(root, OUT_Z + EXPLODE_GAP)

        app.activeViewport.fit()
    except:  # noqa
        if ui:
            ui.messageBox('FIR_Module failed:\n{}'.format(traceback.format_exc()))
