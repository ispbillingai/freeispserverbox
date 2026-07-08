# FIR_Tray.py - Autodesk Fusion 360 script
# TWO-LAYER internal tray for the bought IP65 box.
#   LOWER tray  : RB951 router + 8-port PoE switch + power extension + adapter,
#                 tidy in cradles, wiring channelled (the commodity gear).
#   UPPER tray  : sits on columns ABOVE the lower gear - it HIDES the gear and
#                 carries the smart-module bay; vented so the gear below breathes.
# Single component, multiple bodies (Part Design friendly).
#
#  >>>  MEASURE the real box + parts with calipers and update "MEASURE THESE".
#       This is a LAYOUT CONCEPT - sizes are placeholders (router IS measured).  <<<

import adsk.core, adsk.fusion, adsk.cam, traceback

# ===================== MEASURE THESE (mm) =====================
BOX_IN_W, BOX_IN_L, BOX_IN_D = 285.0, 235.0, 110.0   # IP65 interior W x L x depth
ROUTER_W, ROUTER_L, ROUTER_H = 113.0, 138.0, 29.0    # MikroTik RB951 (measured)
SWITCH_W, SWITCH_L, SWITCH_H = 110.0, 75.0, 27.0     # 8-port reverse PoE switch (MEASURE)
EXT_W, EXT_L, EXT_H = 225.0, 46.0, 34.0              # power extension strip (MEASURE)
ADAPTER_W, ADAPTER_L, ADAPTER_H = 90.0, 50.0, 32.0   # 12V adapter brick (MEASURE)
MODULE_W, MODULE_L = 135.0, 120.0                     # smart-module faceplate footprint

# ===================== build params =====================
CLEAR = 2.0
TRAY_W, TRAY_L = BOX_IN_W - 2 * CLEAR, BOX_IN_L - 2 * CLEAR
FLOOR_TH = 3.0
WALL_T = 2.5
FOOT_H, FOOT_D = 6.0, 14.0
MOUNT_HOLE_D = 4.2
CRADLE_CLR = 1.5
COL_D, COL_PILOT = 12.0, 2.6                 # support/screw columns for the upper tray
SCREW_CLEAR = 3.4
MOD_POST_D, MOD_POST_H, MOD_PILOT = 8.0, 6.0, 2.6
CH_RIB_H = 8.0
EXIT_NOTCH_W = 26.0

# layer-2 height = tallest lower part + clearance
STACK_H = max(ROUTER_H, SWITCH_H, EXT_H, ADAPTER_H) + 6.0
WALL_H = STACK_H                              # perimeter wall rises to the upper tray
Z_UP = FLOOR_TH + STACK_H                     # underside of the upper tray floor
UPPER_W, UPPER_L = TRAY_W - 2 * (WALL_T + 1), TRAY_L - 2 * (WALL_T + 1)

# ---- LOWER zone centres (auto-placed; nudge freely) ----
ROUTER_C  = (-(TRAY_W / 2 - 6 - ROUTER_W / 2),  (TRAY_L / 2 - 6 - ROUTER_L / 2))
SWITCH_C  = ( (TRAY_W / 2 - 6 - SWITCH_W / 2),  (TRAY_L / 2 - 6 - SWITCH_L / 2))
ADAPTER_C = ( (TRAY_W / 2 - 6 - ADAPTER_W / 2), (SWITCH_C[1] - SWITCH_L / 2 - 8 - ADAPTER_L / 2))
EXT_C     = ( 0.0, -(TRAY_L / 2 - 6 - EXT_L / 2))
# columns sit in clear gaps in the central strip + beside the extension
COLUMN_XY = [(0.0, 95.0), (0.0, 0.0), (-125.0, -86.0), (125.0, -86.0)]
# cable entries/exits - align to your box's REAL glands. LEFT wall = X-, BOTTOM = Y-
PWR_IN_Y, NET_IN_Y = -45.0, 20.0                  # power-in & WAN-in gland heights (left)
NET_OUT_X = [-55.0, -18.0, 18.0, 55.0]            # internet-out glands (bottom, to APs)
ENTRY_NOTCH = 14.0
MCB_C = (-100.0, -45.0)                            # main switch / MCB + mains terminal mount
# upper-tray module bay
MODULE_C = ((UPPER_W / 2 - 6 - MODULE_W / 2), (UPPER_L / 2 - 6 - MODULE_L / 2))

# placeholder component blocks (visualise fit + service access; DELETE before printing)
SHOW_PARTS = True
MODULE_DEPTH = 45.0

CM = 0.1
def mm(v):
    return v * CM

NEW  = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation

SKIPPED = []


def _extrude(comp, prof, z0, sz, op, parts):
    feats = comp.features.extrudeFeatures
    ei = feats.createInput(prof, op)
    if abs(z0) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(z0)))
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(sz)))
    if parts:
        ei.participantBodies = parts
    return feats.add(ei)


def box(comp, cx, cy, z0, sx, sy, sz, op, parts=None):
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchLines.addCenterPointRectangle(
        adsk.core.Point3D.create(mm(cx), mm(cy), 0),
        adsk.core.Point3D.create(mm(cx + sx / 2.0), mm(cy + sy / 2.0), 0))
    return _extrude(comp, sk.profiles.item(0), z0, sz, op, parts)


def cyl(comp, cx, cy, z0, d, sz, op, parts=None):
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(d / 2.0))
    return _extrude(comp, sk.profiles.item(0), z0, sz, op, parts)


def frame(comp, ow, ol, t, z0, h, op, parts):
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        L = sk.sketchCurves.sketchLines
        L.addCenterPointRectangle(adsk.core.Point3D.create(0, 0, 0),
                                  adsk.core.Point3D.create(mm(ow / 2), mm(ol / 2), 0))
        L.addCenterPointRectangle(adsk.core.Point3D.create(0, 0, 0),
                                  adsk.core.Point3D.create(mm(ow / 2 - t), mm(ol / 2 - t), 0))
        prof = None
        for p in sk.profiles:
            if p.profileLoops.count == 2:
                prof = p
                break
        if prof:
            _extrude(comp, prof, z0, h, op, parts)
    except Exception as e:
        SKIPPED.append('frame: {}'.format(e))


def cradle(comp, body, cx, cy, w, l, h, open_side, base_z=FLOOR_TH):
    iw, il = w + 2 * CRADLE_CLR, l + 2 * CRADLE_CLR
    ow = iw + 2 * WALL_T
    if open_side != 'back':
        box(comp, cx, cy + il / 2 + WALL_T / 2, base_z, ow, WALL_T, h, JOIN, [body])
    if open_side != 'front':
        box(comp, cx, cy - il / 2 - WALL_T / 2, base_z, ow, WALL_T, h, JOIN, [body])
    if open_side != 'left':
        box(comp, cx - iw / 2 - WALL_T / 2, cy, base_z, WALL_T, il, h, JOIN, [body])
    if open_side != 'right':
        box(comp, cx + iw / 2 + WALL_T / 2, cy, base_z, WALL_T, il, h, JOIN, [body])


def module_bay(comp, body, cx, cy, w, l, base_z):
    px, py = w / 2 - 7, l / 2 - 7
    for dx in (-px, px):
        for dy in (-py, py):
            cyl(comp, cx + dx, cy + dy, base_z, MOD_POST_D, MOD_POST_H, JOIN, [body])
            cyl(comp, cx + dx, cy + dy, base_z, MOD_PILOT, MOD_POST_H + 1, CUT, [body])
    box(comp, cx, cy + l / 2 + WALL_T / 2, base_z, w, WALL_T, 8, JOIN, [body])
    box(comp, cx + w / 2 + WALL_T / 2, cy, base_z, WALL_T, l, 8, JOIN, [body])


def build_lower(comp):
    tray = box(comp, 0, 0, 0, TRAY_W, TRAY_L, FLOOR_TH, NEW).bodies.item(0)
    tray.name = 'FIR Lower Tray'
    frame(comp, TRAY_W, TRAY_L, WALL_T, FLOOR_TH, WALL_H, JOIN, [tray])

    # feet + tray-to-box mount holes
    for sx in (-(TRAY_W / 2 - 12), (TRAY_W / 2 - 12)):
        for sy in (-(TRAY_L / 2 - 12), (TRAY_L / 2 - 12)):
            cyl(comp, sx, sy, 0, FOOT_D, -FOOT_H, JOIN, [tray])
            cyl(comp, sx, sy, -FOOT_H, MOUNT_HOLE_D, FOOT_H + FLOOR_TH + 1, CUT, [tray])

    # commodity-gear cradles (ports/cables open toward centre/front)
    cradle(comp, tray, ROUTER_C[0],  ROUTER_C[1],  ROUTER_W,  ROUTER_L,  ROUTER_H,  'right')
    cradle(comp, tray, SWITCH_C[0],  SWITCH_C[1],  SWITCH_W,  SWITCH_L,  SWITCH_H,  'left')
    cradle(comp, tray, ADAPTER_C[0], ADAPTER_C[1], ADAPTER_W, ADAPTER_L, ADAPTER_H, 'left')
    cradle(comp, tray, EXT_C[0],     EXT_C[1],     EXT_W,     EXT_L,     EXT_H,     'front')

    # central cable channel ribs
    for rx in (-9.0, 9.0):
        box(comp, rx, 20, FLOOR_TH, WALL_T, 150, CH_RIB_H, JOIN, [tray])

    # support / screw columns for the upper tray
    for (x, y) in COLUMN_XY:
        cyl(comp, x, y, FLOOR_TH, COL_D, STACK_H, JOIN, [tray])
        cyl(comp, x, y, FLOOR_TH + STACK_H - 12, COL_PILOT, 13, CUT, [tray])

    # cable exit notch (main bundle) in the bottom wall
    box(comp, 0, -(TRAY_L / 2 - WALL_T), FLOOR_TH, EXIT_NOTCH_W, WALL_T * 3, WALL_H + 1, CUT, [tray])

    # --- power & internet I/O ---
    # entry notches: LEFT wall = power-in + WAN-in,  BOTTOM wall = internet-out to APs
    for y in (PWR_IN_Y, NET_IN_Y):
        box(comp, -TRAY_W / 2, y, FLOOR_TH, WALL_T * 3, ENTRY_NOTCH, WALL_H + 1, CUT, [tray])
    for x in NET_OUT_X:
        box(comp, x, -TRAY_L / 2, FLOOR_TH, ENTRY_NOTCH, WALL_T * 3, WALL_H + 1, CUT, [tray])

    # main switch / MCB + incoming-mains terminal pad (right where power enters)
    mx, my = MCB_C
    box(comp, mx, my, FLOOR_TH, 44, 26, 4, JOIN, [tray])              # platform
    box(comp, mx, my + 13 + WALL_T / 2, FLOOR_TH, 44, WALL_T, 16, JOIN, [tray])  # back rest
    for dx in (-16, 16):
        cyl(comp, mx + dx, my, FLOOR_TH, 6, 8, JOIN, [tray])
        cyl(comp, mx + dx, my, FLOOR_TH, 2.6, 9, CUT, [tray])
    return tray


def build_upper(comp):
    floor = box(comp, 0, 0, Z_UP, UPPER_W, UPPER_L, FLOOR_TH, NEW).bodies.item(0)
    floor.name = 'FIR Upper Tray'

    # screw down onto the columns
    for (x, y) in COLUMN_XY:
        cyl(comp, x, y, Z_UP - 1, SCREW_CLEAR, FLOOR_TH + 2, CUT, [floor])

    # vent slots so the hidden gear below can breathe
    for x in (-110, -85, -60, 85, 110):
        box(comp, x, 10, Z_UP - 1, 6, 150, FLOOR_TH + 2, CUT, [floor])
    for x in (-80, -40, 0, 40, 80):
        box(comp, x, -92, Z_UP - 1, 28, 6, FLOOR_TH + 2, CUT, [floor])

    # cable pass-through from upper to lower layer
    box(comp, -30, -35, Z_UP - 1, 20, 60, FLOOR_TH + 2, CUT, [floor])

    # smart-module bay on top
    module_bay(comp, floor, MODULE_C[0], MODULE_C[1], MODULE_W, MODULE_L, Z_UP + FLOOR_TH)

    # single quick-disconnect parking bracket (unplug here when lifting the cover)
    dx, dy, dz = -30.0, 8.0, Z_UP + FLOOR_TH
    box(comp, dx, dy, dz, 22, 14, 4, JOIN, [floor])         # platform
    box(comp, dx - 10, dy, dz, 2, 14, 9, JOIN, [floor])     # retention nib
    box(comp, dx + 10, dy, dz, 2, 14, 9, JOIN, [floor])     # retention nib
    return floor


def part_block(comp, cx, cy, base_z, w, l, h, name):
    bd = box(comp, cx, cy, base_z, w, l, h, NEW).bodies.item(0)
    bd.name = name
    return bd


def build_parts(comp):
    # ghost components so you can SEE the fit - delete these before printing
    part_block(comp, ROUTER_C[0],  ROUTER_C[1],  FLOOR_TH, ROUTER_W,  ROUTER_L,  ROUTER_H,  'PART: RB951 router')
    part_block(comp, SWITCH_C[0],  SWITCH_C[1],  FLOOR_TH, SWITCH_W,  SWITCH_L,  SWITCH_H,  'PART: PoE switch')
    part_block(comp, ADAPTER_C[0], ADAPTER_C[1], FLOOR_TH, ADAPTER_W, ADAPTER_L, ADAPTER_H, 'PART: adapter')
    part_block(comp, EXT_C[0],     EXT_C[1],     FLOOR_TH, EXT_W,     EXT_L,     EXT_H,     'PART: extension')
    part_block(comp, MODULE_C[0],  MODULE_C[1],  Z_UP + FLOOR_TH, MODULE_W, MODULE_L, MODULE_DEPTH, 'PART: smart-module')


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
        build_lower(design.rootComponent)
        build_upper(design.rootComponent)
        if SHOW_PARTS:
            build_parts(design.rootComponent)

        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Tray built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_Tray failed:\n{}'.format(traceback.format_exc()))
