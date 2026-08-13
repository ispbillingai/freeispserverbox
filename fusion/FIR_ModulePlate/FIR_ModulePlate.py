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
#       - the WIRE-IN modules that never touch the PCB
#         (LM2596 buck, TP4056 charger, 5V boost, horn relay)
#       - the BARE lithium cell, in a printed half-round saddle
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

import math
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
# 30mm (was 26): the relay joined the tray and the wire-tunnel RAISE lifted
# the modules 5mm, so the tallest top is now the relay at 27mm; the board
# underside sits at 33mm - 6mm of clear air over it, 10mm over the battery.
# ⚠️ KNOCK-ON: the box cavity gets 4mm taller than the 26mm-post draft.
POST_D, POST_H, POST_PILOT = 7.0, 30.0, 2.5

# ---------------- wire-in modules: name, w, l, h, cx, cy, mount ----------
# Mounting is now PER MODULE (Francis checked the real boards, 2026-08-13):
#   'screws'   the module has usable holes -> raised bosses + self-tappers
#              (buck: 2 holes; relay: 4 holes)
#   'corners'  NO holes (boost, TP4056) -> four corner pedestals under the
#              board edge + L-brackets round the outline + one zip tie
#   'flat'     18650 holder: flat on the plate (it is the tall one), with
#              brackets, a body tie AND two ties over the cell itself
# Everything except the holder stands RAISE above the plate so the harness
# can run UNDER a module instead of being pinched beneath it; above, the
# PCB underside now sits at 33mm, so over-the-top runs have air too.
# Heights include the trimpot; set the buck to 5.4V and the boost to 5.0V
# BEFORE the board goes on - reaching them after means pulling 4 screws.
MODULES = [
    # BARE CELL, no plastic holder (Francis, 2026-08-13): 59 long x 18 dia.
    # So it gets a curved SADDLE, not a rectangular pocket - see cell_trough.
    ('battery cell', 18.0, 59.0, 18.0, -35.0,   0.0, 'flat'),
    ('LM2596 buck',  43.0, 21.0, 14.0,  20.0,  38.0, 'screws'),
    ('5V boost',     17.0, 36.0, 14.0,   5.0, -25.0, 'corners'),
    ('TP4056',       26.0, 17.0,  6.0,  35.0, -25.0, 'corners'),
    # relay vernier'd: board 34 x 26, but the screw-terminal side overhangs
    # to 46 total - that extra 12mm hangs in free air toward +X (nothing may
    # stand under x 37..49 near y 11). Holes are on the 34 x 26 board.
    ('relay',        34.0, 26.0, 19.0,  20.0,  11.0, 'screws'),
]
# ---------------- the bare cell ----------------
# ⚠️ A standard 18650 is 65mm. Francis measured 59 - if that was a slip, the
# saddle is 6mm short, so re-check before printing. Length is the only
# dimension that matters here: both ends are OPEN, so a longer cell simply
# overhangs, but the tie slots want to land on the cell, not past its ends.
CELL_D, CELL_L = 18.0, 59.0
CELL_CLR   = 0.6      # diametral slack once the cell is seated
TROUGH_W   = 2.5      # saddle wall either side of the channel
# How far the walls reach PAST the cell's centre line. This is what makes it
# CLIP IN instead of resting in an open half-pipe it can lift straight out
# of. 3.0mm narrows the mouth to 17.6mm against an 18.0mm cell = 0.4mm of
# interference: a light push, not a fight. Above the centre line the walls
# are thinned (see cell_trough) so they can actually give that 0.4mm.
CELL_WRAP  = 3.0
LEAD_H     = 1.5      # flared funnel above the mouth, guides the cell in
LEAD_FLARE = 1.2      # how much wider the funnel is at its top, per side
WALL_THIN  = 1.0      # taken off the OUTSIDE of each wall above the centre
# Slices approximating the half-round. 32 keeps the worst step at 0.67mm,
# and that worst case is the bottom-most slice where the circle is nearly
# vertical - the cell beds on the flanks either side of it, so it does not
# matter. More slices barely help (48 only reaches 0.55mm) and cost features.
TROUGH_SLI = 32
CELL_TIE_Y = (18.0, -18.0)   # where the two hold-down ties cross the cell

RAISE  = 5.0                              # wire tunnel under every module
BOSS_D = 7.0                              # screw boss diameter
PED_SZ = 7.0                              # corner pedestal square
# Modules SIT in their spots, they are never forced: 0.7mm of air per side
# at the brackets, and the zip tie - not friction - is what holds them.
SLACK  = 0.7

# ⚠️ VERNIER THE HOLES before printing - these two are GUESSES.
# For each: hole-to-hole spacing, distance from the module edges, hole dia.
# Offsets are from the module's centre, +x along its w, +y along its l.
# Buck: Francis says 2 holes stacked "vertically" (across the 21mm side) -
# measured spacing/end-inset REQUIRED. Relay: 4 corner holes, ~M2.5.
HOLES = {
    'LM2596 buck': {'at': [(-15.0, 5.5), (-15.0, -5.5)], 'pilot': 2.5},
    'relay':       {'at': [(-14.2, -10.2), (-14.2, 10.2),
                           (14.2, -10.2), (14.2, 10.2)], 'pilot': 2.0},
}

BRACKET_T, BRACKET_L = 2.5, 8.0           # corner bracket thickness / leg length
TIE_SLOT = (3.0, 10.0)                    # zip-tie slot through the plate

# tray -> box.  ⚠️ the box side must be redrawn to match these.
TRAY_MOUNT = [(0.0, -58.0), (0.0, 58.0), (-58.0, 0.0), (58.0, 0.0)]
TRAY_CLEAR, TRAY_CB, TRAY_CB_D = 3.4, 6.0, 1.5

# harness tie-downs, ALL on the -X edge: the +X side is the J4/J5 edge
# (TFT + RC522 ribbons drop past the plate there) and stays completely
# clear - mount the PCB with its J4/J5 edge facing +X.
TIE_POSTS = [(-58.0, 26.0), (-58.0, 36.0), (-58.0, -26.0), (-58.0, -36.0)]

# weight savings, kept clear of every post, boss, bracket and slot
LIGHTEN = [(-16.0, -48.0), (52.0, 33.0), (38.0, -46.0), (-40.0, 50.0)]
LIGHTEN_SZ = (14.0, 14.0)

SHOW_PARTS = False        # True = draw the PCB and modules to check the fit

# shown in a popup EVERY run: if you see an older version, the deployed copy
# under %APPDATA% is stale - re-copy the folder (the 28 Jun lesson)
VERSION = 'rev E 2026-08-13: cell CLIPS in - walls wrap past centre, flexy top, funnel'

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


def corner_brackets(comp, body, cx, cy, w, l, h, z0=PLATE_TOP):
    """Four L-shaped corners that locate a module by its OUTLINE.

    For the no-hole modules (their hole patterns move between batches, the
    outside dimensions do not). SLACK per side: the board DROPS in and sits,
    it is never pressed - the zip tie is what holds it down. z0 lets the L
    sit on top of the pedestals.
    """
    hw, hl = w / 2.0 + SLACK, l / 2.0 + SLACK
    for sx in (-1, 1):
        for sy in (-1, 1):
            x = cx + sx * (hw + BRACKET_T / 2.0)
            y = cy + sy * (hl + BRACKET_T / 2.0)
            # one leg along X, one along Y -> an L that traps the corner
            box(comp, x - sx * (BRACKET_L - BRACKET_T) / 2.0, y,
                z0, BRACKET_L, BRACKET_T, h, JOIN, [body])
            box(comp, x, y - sy * (BRACKET_L - BRACKET_T) / 2.0,
                z0, BRACKET_T, BRACKET_L, h, JOIN, [body])


def corner_pedestals(comp, body, cx, cy, w, l):
    """Four small feet just inside the module's corners: the board rests on
    these, RAISE off the plate, so the harness can pass underneath instead
    of being crushed under the module. Corners only - the middle of these
    boards carries solder joints that must touch nothing."""
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(comp, cx + sx * (w / 2.0 - PED_SZ / 2.0 + SLACK),
                cy + sy * (l / 2.0 - PED_SZ / 2.0 + SLACK),
                PLATE_TOP, PED_SZ, PED_SZ, RAISE, JOIN, [body])


def cell_trough(comp, body, cx, cy):
    """A half-round SADDLE for the bare cell - no plastic holder involved.

    A rectangular pocket would touch a round cell on two edges only; this
    beds it along its whole length instead, which is what stops it drumming
    against the plate every time the box is knocked.

    The walls carry on CELL_WRAP past the cell's centre line, so the mouth
    is narrower than the cell and it CLIPS IN. A plain half-deep channel
    (rev D) held nothing until the ties went on - the cell could lift
    straight out, which is what Francis caught on the render.

    Three things make that clip a push rather than a fight: the channel is
    oversize once seated, the walls are thinned above the centre line so
    they can flex the 0.2mm each that the mouth needs, and a flared funnel
    on top guides the cell in instead of catching its edge.

    BOTH ENDS ARE OPEN: on a bare cell the + button is at one end and the
    can (negative) at the other, so leads must leave both ways.

    The round is cut as stacked slices, each sized at its WIDER edge, so the
    removed volume always contains the true cylinder and the seated cell
    never binds. The steps that leaves are irrelevant on a printed part.

    Returns the outer width, so the tie slots know where to sit.
    """
    r = (CELL_D + CELL_CLR) / 2.0
    wall_h = r + CELL_WRAP
    outer_w = CELL_D + CELL_CLR + 2 * TROUGH_W

    def hw(z):                         # half-width of the bore at height z
        return math.sqrt(max(r * r - (z - r) ** 2, 0.0))

    box(comp, cx, cy, PLATE_TOP, outer_w, CELL_L, wall_h + LEAD_H, JOIN,
        [body])

    # ---- the bore, up past the centre line to the clip mouth ----
    for i in range(TROUGH_SLI):
        z_lo = i * wall_h / TROUGH_SLI
        z_hi = (i + 1) * wall_h / TROUGH_SLI
        if z_hi <= r:
            half = hw(z_hi)            # below centre: widest at the top
        elif z_lo >= r:
            half = hw(z_lo)            # above centre: widest at the bottom
        else:
            half = r                   # slice straddles the centre
        box(comp, cx, cy, PLATE_TOP + z_lo, 2 * half, CELL_L + 2,
            z_hi - z_lo + 0.01, CUT, [body])

    # ---- funnel above the mouth: catches the cell and walks it in ----
    mouth = hw(wall_h)
    for i in range(4):
        z_lo = wall_h + i * LEAD_H / 4.0
        z_hi = wall_h + (i + 1) * LEAD_H / 4.0
        half = mouth + LEAD_FLARE * (i + 1) / 4.0
        box(comp, cx, cy, PLATE_TOP + z_lo, 2 * half, CELL_L + 2,
            z_hi - z_lo + 0.01, CUT, [body])

    # ---- thin the walls above the centre line so they can actually give ----
    for sx in (-1, 1):
        box(comp, cx + sx * (outer_w / 2.0 - WALL_THIN / 2.0), cy,
            PLATE_TOP + r, WALL_THIN, CELL_L + 2,
            wall_h + LEAD_H - r + 1.0, CUT, [body])

    return outer_w


def screw_bosses(comp, body, cx, cy, holes):
    """Raised bosses matching a module's own holes: RAISE tall, so a screwed
    module gets the same wire tunnel underneath as a bracketed one. The
    pilot runs through the boss into the plate, stopping 1mm short."""
    for (dx, dy) in holes['at']:
        cyl(comp, cx + dx, cy + dy, PLATE_TOP, BOSS_D, RAISE, JOIN, [body])
        cyl(comp, cx + dx, cy + dy, 1.0, holes['pilot'],
            PLATE_TH - 1.0 + RAISE, CUT, [body])


def tie_slots(comp, body, cx, cy, w, dy=0.0):
    """A pair of slots either side of a module: one zip tie straps it down."""
    sw, sl = TIE_SLOT
    for sx in (-1, 1):
        box(comp, cx + sx * (w / 2.0 + 5.0), cy + dy, -1, sw, sl,
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

    # ---- wire-in modules, each held its own way ----
    for (name, w, l, h, cx, cy, mount) in MODULES:
        wall = 5.0 if h > 10 else 3.5
        if mount == 'screws':
            screw_bosses(comp, plate, cx, cy, HOLES[name])
        elif mount == 'corners':
            corner_pedestals(comp, plate, cx, cy, w, l)
            corner_brackets(comp, plate, cx, cy, w, l, wall,
                            z0=PLATE_TOP + RAISE)
            tie_slots(comp, plate, cx, cy, w)
        else:                                   # 'flat' - the bare cell
            ow = cell_trough(comp, plate, cx, cy)
            # the ties ARE the retention here: a jolt hard enough to raise
            # the motion alarm must not be able to lift the cell out
            for ty in CELL_TIE_Y:
                tie_slots(comp, plate, cx, cy, ow, dy=ty)

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
    for (name, w, l, h, cx, cy, mount) in MODULES:
        z = PLATE_TOP if mount == 'flat' else PLATE_TOP + RAISE
        m = box(comp, cx, cy, z, w, l, h, NEW).bodies.item(0)
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
        # old bodies from a previous run must go first, or failed geometry
        # stacks under the new build and the result lies to you
        root = design.rootComponent
        for i in range(root.bRepBodies.count - 1, -1, -1):
            b = root.bRepBodies.item(i)
            if b.name.startswith(('FIR Electronics Tray', 'PART:')):
                b.deleteMe()
        build_plate(root)
        if SHOW_PARTS:
            build_parts(root)
        app.activeViewport.fit()
        msg = VERSION
        if SKIPPED:
            msg += '\n\nSkipped:\n - ' + '\n - '.join(SKIPPED)
        ui.messageBox(msg)
    except:  # noqa
        if ui:
            ui.messageBox('FIR_ModulePlate failed:\n{}'.format(
                traceback.format_exc()))
