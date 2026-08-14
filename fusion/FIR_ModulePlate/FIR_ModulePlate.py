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
import sys
try:
    import adsk.core, adsk.fusion, adsk.cam, traceback
except ImportError:                      # running under plain python --check
    adsk = None

# ---------------- TRAY ----------------
PLATE_W, PLATE_H, PLATE_TH = 125.0, 125.0, 3.0
PLATE_TOP = PLATE_TH
CORNER_R = 6.0

# ---------------- the PCB ----------------
# freeisp_brain rev H: 115x115, M3 holes 4.5mm in from each corner
PCB_W = PCB_H = 115.0
PCB_HOLE_PITCH = PCB_W - 2 * 4.5          # 106.0 mm square
# cross-checked against pcb/build.py: BW=BH=115.0, H1..H4 at 4.5mm in.
PCB_CX, PCB_CY = 0.0, 0.0                 # PCB is centred on the tray
# 30mm (was 26): the relay joined the tray and the wire-tunnel RAISE lifted
# the modules 5mm, so the tallest top is now the relay at 27mm; the board
# underside sits at 33mm - 6mm of clear air over it, 12mm over the cell.
# ⚠️ KNOCK-ON: the box cavity gets 4mm taller than the 26mm-post draft.
POST_D, POST_H, POST_PILOT = 7.0, 30.0, 2.5

# ---------------- wire-in modules: name, w, l, h, cx, cy, mount ----------
# Mounting is now PER MODULE (Francis checked the real boards, 2026-08-13):
#   'screws'   the module has usable holes -> raised bosses + self-tappers
#              (buck: 2 holes; relay: 4 holes)
#   'corners'  NO holes (boost, TP4056) -> four full-height flex wedges,
#              each with its own tiny under-board ledge + one zip tie
#   'flat'     18650 holder: flat on the plate (it is the tall one), with
#              brackets, a body tie AND two ties over the cell itself
# Everything except the holder stands RAISE above the plate so the harness
# can run UNDER a module instead of being pinched beneath it; above, the
# PCB underside now sits at 33mm, so over-the-top runs have air too.
# Heights include the trimpot; set the buck to 5.4V and the boost to 5.0V
# BEFORE the board goes on - reaching them after means pulling 4 screws.
MODULES = [
    # BARE CELL, no plastic holder: a 14500, 52 long x 14.5 dia (corrected
    # 2026-08-14 - see CELL_D/CELL_L). Gets a curved SADDLE with an end
    # stop, not a rectangular pocket - see cell_trough.
    ('battery cell', 14.5, 52.0, 14.5, -35.0,   0.0, 'flat'),
    # buck vernier'd 2026-08-14: 43.2 x 21.4 (was 43 x 21 from the datasheet)
    ('LM2596 buck',  43.2, 21.4, 14.0,  20.0,  38.0, 'screws'),
    ('5V boost',     17.0, 36.0, 14.0,   5.0, -26.0, 'corners'),
    # moved out to x=40: at 35 its bracket foot sat 1.2mm INSIDE the boost's
    # zip-tie slot, and the two modules' facing slots merged into one hole.
    # LENGTH 28.2 (Francis, 2026-08-14) - was 26; there is also a ~1mm
    # extrusion overhanging one length side, and 28.2 is the real envelope
    # the brackets must clear. The grip bands sit at the CORNERS (8mm
    # legs), so a mid-edge extrusion is untouched - verify which side.
    ('TP4056',       28.2, 17.0,  6.0,  40.0, -25.0, 'corners'),
    # relay vernier'd: board 34 x 26, but the screw-terminal side overhangs
    # to 46 total - that extra 12mm hangs in free air toward +X (nothing may
    # stand under x 37..49 near y 11). Holes are on the 34 x 26 board.
    ('relay',        34.0, 26.0, 19.0,  20.0,  11.0, 'screws'),
]
# ---------------- the bare cell ----------------
# CORRECTED (2026-08-14, Francis re-measured): the cell is 14.5 dia x 52mm -
# a 14500, not an 18650. The old 18/59 saddle was cut for a fatter, longer
# cell than what's actually seated, so the bore sat oversize and the cell
# had play instead of a press fit ("just hanging"). Both ends stay OPEN so
# leads can leave either way; ONE end now gets a stop block (below) so the
# cell can't slide out along its length either.
CELL_D, CELL_L = 14.5, 52.0
CELL_CLR   = 0.6      # diametral slack once the cell is seated
# Saddle wall either side of the channel. Cut 2.5 -> 2.0 (2026-08-14):
# Francis on the render, "the thickness is big making it rigid, you can't
# even push something in - make it lighter". At 2.5 the wall was still
# 1.2mm thick at the centre line AFTER the outside relief, which is a
# structure, not a spring. 2.0 leaves 0.7mm there - two extrusions on a
# 0.4mm nozzle, so it still prints solid, but it gives.
TROUGH_W   = 2.0
# The saddle visibly CLOSES at its upper edge: the entrance is exactly
# 13.5mm wide - Francis's number, 2026-08-14, and the whole point of the
# part. The cell is 14.5mm, so the opening is deliberately 1.0mm NARROWER
# than what goes into it. Derive the wrap from that entrance rather than
# hand-tuning a wrap: if the cell, clearance or flare changes, the opening
# stays 13.5mm.
#
# ⚠️ DO NOT "FIX" THIS BY OPENING IT UP. I widened it to 15.5 once, on the
# reasoning that a lead-in must be wider than the part it guides. That
# reasoning does not apply here and Francis rejected it: the cell is a
# ROUND, rigid cylinder, so its own curvature is the wedge - a 14.5mm
# cylinder pressed onto a 13.5mm gap rides its own radius apart. It needs
# 0.5mm of spread per wall to enter, against the 2.0mm those same walls
# already give at the throat. The narrow entrance IS the retention.
#
# This makes a deliberately firm PETG clip: the 10.50mm throat flexes 2.0mm
# per wall around a 14.5mm cell. validate() recomputes the real strain on
# every build; do not trust this comment by memory.
CELL_TOP_OPEN = 13.5   # visible opening at the upper rim of the funnel
LEAD_H        = 1.5    # flared funnel above the clip throat
LEAD_FLARE    = 1.5    # how much wider the funnel is at its top, per side
CELL_MOUTH    = CELL_TOP_OPEN - 2.0 * LEAD_FLARE
CELL_WRAP     = math.sqrt(((CELL_D + CELL_CLR) / 2.0) ** 2
                          - (CELL_MOUTH / 2.0) ** 2)
WALL_THIN  = 1.3      # taken off the OUTSIDE of each wall above the centre
SLOT_W     = 2.0      # relief slots that turn the walls into fingers
SLOT_Y     = (-14.75, 0.0, 14.75)
SLOT_FLOOR = 2.0      # slots stop this far up, so the bed stays continuous
LIP_H      = 0.8      # height of the constant-width retention lip at the mouth
# CELL STOP: a single small block at the +Y end (the end marked beside CELL
# in the render) stops the cell sliding lengthwise.  It is deliberately only
# 8 x 3 x 6mm, not a wall across the cradle: leads can still leave around it.
END_STOP_W = 8.0         # transverse width of the small stop block
END_STOP_T = 3.0         # stop thickness, along the cell's length
END_STOP_H = 6.0         # requested stop height above the plate
# Slices approximating the half-round. 32 keeps the worst step at 0.67mm,
# and that worst case is the bottom-most slice where the circle is nearly
# vertical - the cell beds on the flanks either side of it, so it does not
# matter. More slices barely help (48 only reaches 0.55mm) and cost features.
TROUGH_SLI = 32
CELL_TIE_Y = (18.0, -18.0)   # where the two hold-down ties cross the cell

RAISE  = 5.0                              # wire tunnel under every module
BOSS_D = 7.0                              # screw boss diameter

# Offsets are from the module's centre, +x along its w, +y along its l.
#
# BUCK (Francis, 2026-08-13): the two holes are DIAGONALLY OPPOSITE, ~35-36mm
# apart - NOT stacked on one side as the first draft had them. On a 43x21
# board a 4.5mm inset puts them at (+-17.0, +-5.5): diagonal 35.7mm, which
# is the measurement. FOUR bosses are drawn, not two, because which diagonal
# the holes sit on cannot be told from a distance alone - a 180-degree turn
# maps each diagonal onto ITSELF, so guessing wrong is unfixable. With all
# four there, two take the screws and the other two just support the board.
#
# RELAY: 4 corner holes on the 34x26 board. Spacing still a GUESS - vernier.
# BUCK holes re-measured 2026-08-14 as EDGE-TO-CIRCUMFERENCE distances:
# 1.2mm from the LONG (43.2) side to the hole, 4.8mm from the SHORT (21.4)
# side. Converting to centres assumes the board hole is Ø3.0 (r=1.5,
# standard on LM2596 modules - VERIFY): from long edge 1.2+1.5=2.7 ->
# y = 21.4/2-2.7 = 8.0; from short edge 4.8+1.5=6.3 -> x = 43.2/2-6.3
# = 15.3. Diagonal 34.5mm, consistent with the earlier ~35mm measurement.
# All four positions still drawn (holes are on ONE diagonal - see above).
#
# RELAY holes were ~0.5mm tight both ways (Francis, 2026-08-14): spread
# outward 0.5mm on width and length. Was (+-14.2, +-10.2).
HOLES = {
    'LM2596 buck': {'at': [(-15.3, -8.0), (-15.3, 8.0),
                           (15.3, -8.0), (15.3, 8.0)], 'pilot': 2.5},
    'relay':       {'at': [(-14.7, -10.7), (-14.7, 10.7),
                           (14.7, -10.7), (14.7, 10.7)], 'pilot': 2.0},
}

# BRACKET_T/BRACKET_L deleted with the L-corners they described.

# SNAP FINGERS (2026-08-14 v2, after Francis reviewed the render: "those
# walls are straight... the thickness is big making it rigid, you can't
# even push something in, make it lighter"). He was right twice over: the
# 2.5mm L-corners were rigid BY CONSTRUCTION - a right angle cannot flex -
# and the wedge cut into them was a 0.2mm staircase invisible at any
# scale. Both gone. Each 'corners' module now gets what the cell saddle
# already has: THIN, FREE-STANDING FLEX FINGERS, one centred on each of
# the four sides, shaped like a proper wedge - a mouth that flares WIDE
# open at the top, funnels the board down, and an EMBOSS bump just above
# the seated board's top face that the board CLICKS under as it is
# pressed home. Self-locking before it rests; the zip tie stays as the
# retention of record.
BOARD_T    = 1.6   # module PCB thickness - the emboss sits just above this
# These are actual cantilevers, not bracket walls: thin the root in the
# bending direction AND narrow the band across the board.  The little head
# above the board is wider only where it has to bridge in to form the click.
SNAP_T     = 1.1   # thin flexing stem (was 1.3); PETG prints as 3 walls
SNAP_W     = 7.0   # narrow band across the board edge (was 9.0)
SNAP_GAP   = 0.25  # side clearance at the seat (the bump holds it DOWN)
SNAP_B     = 0.55  # emboss overhang past the board edge - the click
SNAP_H     = 1.2   # emboss height
SNAP_FLARE = 1.8   # full outward travel of BOTH wedge faces above the emboss
SNAP_LEAD  = 2.6   # height of the flared wedge mouth above the emboss
SNAP_ROOT_FLARE = 1.8  # lower wedge tapers this far IN from its plate root
# The board stays RAISE above the plate for its wire tunnel, but no longer
# sits on four rigid corner cubes.  These small ledges are part of the four
# flex wedges, not separate brackets.
SNAP_SEAT_H   = 0.6  # vertical thickness of each under-board ledge
SNAP_SEAT_IN  = 0.8  # how far its upper shelf reaches under the board edge
# Per-module, per-axis override of the SEAT-level face offset from the
# board edge (+ = clearance, - = pinch). BOOST (Francis): the VIN+/VOUT+
# ends - its l axis - had visible space; compressed 1.5mm total from the
# old 0.7/side slack, landing the faces 0.05 INTO the board: a snug press.
GRIP_P = {'5V boost': {'l': -0.05}}
# Click-over deflection is the emboss reach on a ~6.7mm finger.  The checker
# computes the actual strain for each module; print the plate in PETG.
TIE_SLOT = (3.0, 10.0)                    # zip-tie slot through the plate
# How far a tie slot sits outside its module. 5.0 left only a 0.30mm web
# between the slot and the bracket foot beside it - the brackets now grow
# from the plate, so that web is load-bearing and 0.3mm would simply snap.
TIE_OFF = 6.5


def finger_offsets(name, axis):
    """Centre locations along one board edge for the flex wedges.

    TP4056 is wide (28.2mm), so its long edges get two wedges each, 14mm
    apart: six in total, without crowding the USB/terminal end areas.

    BOOST doubled up 2026-08-14 ("on the boost add more wedges, like one
    extra on each side"): EIGHT wedges, two per side. A single 7mm band was
    holding a 36mm edge, which lets the board pivot about that one point -
    two bands 18mm apart cannot. Spacing per edge, given SNAP_W = 7.0:
      36mm edges (the w axis, +-X) -> +-9.0, so 5.5mm of clear air between
      17mm edges (the l axis, +-Y) -> +-4.5, 2.0mm between, 0.5mm at each
        end. Tight but they stay separate fingers, which is the point: two
        merged bands would be one stiff block again.
    """
    if name == 'TP4056' and axis == 'l':
        return (-7.0, 7.0)
    if name == '5V boost':
        return (-9.0, 9.0) if axis == 'w' else (-4.5, 4.5)
    return (0.0,)

# tray -> box.  ⚠️ the box side must be redrawn to match these.
TRAY_MOUNT = [(0.0, -58.0), (0.0, 58.0), (-58.0, 0.0), (58.0, 0.0)]
TRAY_CLEAR, TRAY_CB, TRAY_CB_D = 3.4, 6.0, 1.5

# Harness tie-downs, ALL on the -X edge: the +X side is the J4/J5 edge
# (TFT + RC522 ribbons drop past the plate there) and stays completely
# clear - mount the PCB with its J4/J5 edge facing +X.
#
# These are SLOTS, in pairs. Rev F drew raised 3.5x10 blocks instead, which
# retain nothing - there was no aperture to thread a tie through - and the
# 26/36 pair touched end-to-end at y=31 and fused into one 20mm block.
# Thread up through one slot, over the harness, back down the other.
HARNESS_TIE = [(-58.0, 20.0), (-58.0, 28.0), (-58.0, -20.0), (-58.0, -28.0)]
HARNESS_SLOT = (3.0, 6.0)

# Which modules take their ties across Y instead of X (see tie_slots).
TIE_AXIS = {'TP4056': 'y'}

# LIGHTEN pockets DELETED. Four 14x14x3 pockets save 588mm3 each - about
# 2.8g of filament across all four, against a 500g budget. That is nothing,
# and every one of them was a fresh chance to undermine a boss, a bracket or
# a tie slot. Solid plate is worth more than 0.6% of a spool.

SHOW_PARTS = False        # True = draw the PCB and modules to check the fit

# ENGRAVED LABELS. Two modules' bosses look identical in a render - you
# cannot tell the buck's four from the relay's four by eye, and getting it
# wrong is discovered at assembly with a soldering iron in your hand. So the
# plate says which is which, and carries the two set-points as well, exactly
# like the PCB silkscreen does. Each label sits INSIDE its own module's
# footprint, so it is readable right up until the module covers it.
ENGRAVE_D = 0.6           # depth cut into the plate top
LABELS = [
    ('BUCK',   20.0,  41.5, 5.0),
    ('5.4V',   20.0,  34.5, 5.0),
    ('RELAY',  20.0,  11.0, 5.0),
    ('BOOST',   5.0, -21.0, 3.5),
    ('5.0V',    5.0, -30.0, 3.5),
    ('TP4056', 40.0, -25.0, 3.5),
    ('CELL',  -35.0,  36.0, 5.0),
]

# shown in a popup EVERY run: if you see an older version, the deployed copy
# under %APPDATA% is stale - re-copy the folder (the 28 Jun lesson)
VERSION = ('rev R 2026-08-14: boost doubled to eight wedges, two per side. '
           'Cell saddle entrance is 13.5mm as specified - narrower than the '
           '14.5mm cell, which is the retention; do not open it up. '
           'PRINT IN PETG.')

CM = 0.1


def mm(v):
    return v * CM


if adsk is not None:
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
else:
    NEW = JOIN = CUT = None
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


def lofted_slab(comp, body, cx, cy, axis, side, face_lo, face_hi,
                z0, height, thick, width):
    """A rectangular finger section that moves sideways as it rises.

    This is deliberately a LOFT, not stacked boxes: it creates two genuinely
    sloped, planar outside faces.  It is how the module fingers get a visible
    wedge all the way from the plate to the click lip.
    """
    def profile(z, face):
        pin = comp.constructionPlanes.createInput()
        pin.setByOffset(comp.xYConstructionPlane,
                        adsk.core.ValueInput.createByReal(mm(PLATE_TOP + z)))
        plane = comp.constructionPlanes.add(pin)
        sk = comp.sketches.add(plane)
        if axis == 'w':
            px, py, sx, sy = cx + side * (face + thick / 2.0), cy, thick, width
        else:
            px, py, sx, sy = cx, cy + side * (face + thick / 2.0), width, thick
        sk.sketchCurves.sketchLines.addCenterPointRectangle(
            adsk.core.Point3D.create(mm(px), mm(py), 0),
            adsk.core.Point3D.create(mm(px + sx / 2.0), mm(py + sy / 2.0), 0))
        try:
            plane.isLightBulbOn = False
            sk.isLightBulbOn = False
        except Exception:
            pass
        return sk.profiles.item(0)

    lo = profile(z0, face_lo)
    hi = profile(z0 + height, face_hi)
    inp = comp.features.loftFeatures.createInput(JOIN)
    inp.loftSections.add(lo)
    inp.loftSections.add(hi)
    inp.isSolid = True
    try:
        inp.participantBodies = [body]
    except Exception:
        pass
    return comp.features.loftFeatures.add(inp)


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


def snap_fingers(comp, body, cx, cy, w, l, name=None):
    """THIN FLEX FINGERS - one or more on each side - that the board
    is PRESSED into and clicks under. Replaces the L-corner brackets.

    Why the L-corners had to go (Francis, on the rev-I render): a right
    angle is a stiffener. Two 2.5mm walls meeting at 90 degrees cannot
    flex in either direction, so no amount of taper cut into them would
    ever let a board push in - "you can't even push something in". And
    the taper itself was a 0.2mm staircase, invisible at any scale.

    Each finger is a free-standing 1.1mm wall, rooted on the plate.  It is a
    REAL wedge for its ENTIRE height: a lofted lower spring tapers in from a
    wide plate root to the clear line alongside the board, and a lofted upper
    lead-in tapers back out to catch the board.  There is no straight vertical
    retaining wall and no staircase of boxes.  A tiny ledge built into each
    wedge supports the board at RAISE; the click lip alone juts SNAP_B inside
    the board edge.  Pressing a board down bends the thin finger outward, then
    it springs back with the lip over the board's top face.

    BOOST has four fingers.  TP4056 has six: two on each long edge and one
    on each short edge.  The tie remains the retention of record; the fingers
    stop rattle and hold the board captive while the tie goes on.
    """
    board_top = RAISE + BOARD_T          # top face of the seated board
    ov = GRIP_P.get(name) or {}

    def slab(axis, s, face, z, hgt, thick, along):
        """One slab of one finger. `face` = the slab's INNER face, as a
        distance from the module centre-line along `axis`."""
        if axis == 'w':
            box(comp, cx + s * (face + thick / 2.0), cy + along,
                PLATE_TOP + z, thick, SNAP_W, hgt, JOIN, [body])
        else:
            box(comp, cx + along, cy + s * (face + thick / 2.0),
                PLATE_TOP + z, SNAP_W, thick, hgt, JOIN, [body])

    for axis, half in (('w', w / 2.0), ('l', l / 2.0)):
        seat = half + ov.get(axis, SNAP_GAP)   # stem face: clear of the board
        tip = half - SNAP_B                    # emboss tip: INSIDE that edge
        for along in finger_offsets(name, axis):
            for s in (-1, 1):
                finger_cx = cx + (along if axis == 'l' else 0.0)
                finger_cy = cy + (along if axis == 'w' else 0.0)
                # 1. LOWER WEDGE / SPRING.  No upright stem: a single loft
                #    shifts BOTH faces in from a broad plate root to the
                #    board's clear line. It never intrudes into the board.
                lofted_slab(comp, body, finger_cx, finger_cy, axis, s,
                            seat + SNAP_ROOT_FLARE, seat,
                            -0.01, board_top + 0.01, SNAP_T, SNAP_W)
                # The board is held 5mm off the plate by a SMALL shelf built
                # into this same wedge - no four rigid corner pedestals.
                shelf_tip = half - SNAP_SEAT_IN
                shelf_outer = seat + SNAP_T
                slab(axis, s, shelf_tip, RAISE - SNAP_SEAT_H, SNAP_SEAT_H,
                     shelf_outer - shelf_tip, along)
                # 2. CLICK LIP.  The board pushes this inside overhang aside,
                #    then it springs back over the board's top face.
                slab(axis, s, tip, board_top, SNAP_H, SNAP_T, along)
                # 3. UPPER WEDGE / LEAD-IN.  A continuous loft shifts BOTH
                #    faces out from the lip and gives an obvious funnel.
                lofted_slab(comp, body, finger_cx, finger_cy, axis, s,
                            tip, tip + SNAP_FLARE,
                            board_top + SNAP_H - 0.01, SNAP_LEAD + 0.01,
                            SNAP_T, SNAP_W)


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

    # ---- funnel above the throat: catches the cell and walks it in.  Its
    # upper rim is CELL_TOP_OPEN (13.5mm), not a separately guessed width. ----
    mouth = hw(wall_h)
    for i in range(4):
        z_lo = wall_h + i * LEAD_H / 4.0
        z_hi = wall_h + (i + 1) * LEAD_H / 4.0
        half = mouth + LEAD_FLARE * (i + 1) / 4.0
        box(comp, cx, cy, PLATE_TOP + z_lo, 2 * half, CELL_L + 2,
            z_hi - z_lo + 0.01, CUT, [body])

    # ---- a real LIP: the top LIP_H of the bore held at the true mouth width.
    # Without it the mouth is set by the topmost slice's WIDER (lower) edge,
    # which came out 17.16mm instead of the 16.79mm the wrap was sized for -
    # a third less retention than intended, and the comments said otherwise.
    box(comp, cx, cy, PLATE_TOP + wall_h - LIP_H, 2 * hw(wall_h), CELL_L + 2,
        LIP_H + 0.01, CUT, [body])

    # ---- thin the walls so they can actually give ----
    # From the SLOT FLOOR, not from the centre line. A cantilever bends where
    # it is thinnest, and the wall below the centre line is 3-6mm thick, so
    # starting the relief at the centre left all the deflection in the top
    # 5.5mm: 3.6% strain, which cracks PLA and leaves PETG no margin.
    # Relieving the full slotted height spreads it over ~12.8mm instead.
    for sx in (-1, 1):
        box(comp, cx + sx * (outer_w / 2.0 - WALL_THIN / 2.0), cy,
            PLATE_TOP + SLOT_FLOOR, WALL_THIN, CELL_L + 2,
            wall_h + LEAD_H - SLOT_FLOOR + 1.0, CUT, [body])

    # ---- relief slots: the walls become fingers, which is what lets a wrap
    # this deep still be a push rather than a fight. They stop SLOT_FLOOR
    # above the plate so the cell still beds on one continuous bottom.
    # A full-width cut is safe: everything between the walls is bore already.
    for sy in SLOT_Y:
        box(comp, cx, cy + sy, PLATE_TOP + SLOT_FLOOR, outer_w + 2, SLOT_W,
            wall_h + LEAD_H - SLOT_FLOOR + 1.0, CUT, [body])

    # ---- small +Y end stop: just enough to stop longitudinal cell movement,
    # without becoming another rigid end wall or trapping the lead wires. ----
    stop_y = cy + CELL_L / 2.0 - END_STOP_T / 2.0
    box(comp, cx, stop_y, PLATE_TOP, END_STOP_W, END_STOP_T, END_STOP_H,
        JOIN, [body])

    return outer_w


def screw_bosses(comp, body, cx, cy, holes):
    """Raised bosses matching a module's own holes: RAISE tall, so a screwed
    module gets the same wire tunnel underneath as a bracketed one. The
    pilot runs through the boss into the plate, stopping 1mm short."""
    for (dx, dy) in holes['at']:
        cyl(comp, cx + dx, cy + dy, PLATE_TOP, BOSS_D, RAISE, JOIN, [body])
        cyl(comp, cx + dx, cy + dy, 1.0, holes['pilot'],
            PLATE_TH - 1.0 + RAISE, CUT, [body])


def tie_slots(comp, body, cx, cy, w, l=0.0, dy=0.0, axis='x'):
    """A pair of slots either side of a module: one zip tie straps it down.

    axis='y' puts them above and below instead of left and right. That is not
    cosmetic: the boost and the TP4056 are close enough that their facing
    X-slots overlapped by 1.5mm and merged into one 4.5mm aperture, so both
    ties came up the same hole and neither could be tensioned. Turning one
    module's pair through 90 degrees separates them properly.
    """
    sw, sl = TIE_SLOT
    if axis == 'y':
        for sy in (-1, 1):
            box(comp, cx, cy + sy * (l / 2.0 + TIE_OFF), -1, sl, sw,
                PLATE_TH + 2, CUT, [body])
    else:
        for sx in (-1, 1):
            box(comp, cx + sx * (w / 2.0 + TIE_OFF), cy + dy, -1, sw, sl,
                PLATE_TH + 2, CUT, [body])


# ================================================================
#  SELF-CHECK - pure arithmetic, no Fusion API. Runs on every build and
#  reports in the popup. Written after a review found two blockers that
#  a drawing simply does not show you: brackets floating 5mm in mid-air
#  because their footprint was flush with (not overlapping) the pedestal,
#  and post pilot holes sealed at both ends so no screw could enter.
#  Both were invisible in a render and obvious in arithmetic.
#      python FIR_ModulePlate.py --check
# ================================================================
def _rect(owner, name, cx, cy, sx, sy):
    return (owner, name, cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2)


def _module_rects():
    return [_rect(n, n + ' body', cx, cy, w, l)
            for (n, w, l, h, cx, cy, mt) in MODULES]


def _feature_rects():
    """Every bit of PRINTED geometry, modelled as it is actually built -
    bracket LEGS, not their bounding box, or the checker cries wolf."""
    F = []
    for (name, w, l, h, cx, cy, mount) in MODULES:
        if mount == 'screws':
            for (dx, dy) in HOLES[name]['at']:
                F.append(_rect(name, name + ' boss', cx + dx, cy + dy,
                               BOSS_D, BOSS_D))
        elif mount == 'corners':
            # The four snap fingers, at the side CENTRES.  The true wedge
            # is widest at its plate root, while its shelf reaches slightly
            # inside the board edge; include all of that in the clearance check.
            ov = GRIP_P.get(name) or {}
            for axis, half, sz in (('w', w / 2, 'x'), ('l', l / 2, 'y')):
                seat = half + ov.get(axis, SNAP_GAP)
                tip = half - SNAP_B
                shelf_tip = half - SNAP_SEAT_IN
                root_outer = seat + SNAP_ROOT_FLARE + SNAP_T
                lead_outer = tip + SNAP_T + SNAP_FLARE
                outer = max(root_outer, lead_outer)
                inner = min(tip, shelf_tip)
                mid, thick = (inner + outer) / 2, outer - inner
                for along in finger_offsets(name, axis):
                    for s in (-1, 1):
                        if sz == 'x':
                            F.append(_rect(name, name + ' finger',
                                           cx + s * mid, cy + along,
                                           thick, SNAP_W))
                        else:
                            F.append(_rect(name, name + ' finger',
                                           cx + along, cy + s * mid,
                                           SNAP_W, thick))
            sw, sl = TIE_SLOT
            if TIE_AXIS.get(name, 'x') == 'y':
                for sy in (-1, 1):
                    F.append(_rect(name, name + ' tie', cx,
                                   cy + sy * (l / 2 + TIE_OFF), sl, sw))
            else:
                for sx in (-1, 1):
                    F.append(_rect(name, name + ' tie',
                                   cx + sx * (w / 2 + TIE_OFF), cy, sw, sl))
        else:
            ow = CELL_D + CELL_CLR + 2 * TROUGH_W
            F.append(_rect(name, name + ' saddle', cx, cy, ow, CELL_L))
            sw, sl = TIE_SLOT
            for ty in CELL_TIE_Y:
                for sx in (-1, 1):
                    F.append(_rect(name, name + ' tie',
                                   cx + sx * (ow / 2 + TIE_OFF), cy + ty,
                                   sw, sl))
    half = PCB_HOLE_PITCH / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            F.append(_rect('tray', 'PCB post', sx * half, sy * half,
                           POST_D, POST_D))
    for (x, y) in TRAY_MOUNT:
        F.append(_rect('tray', 'tray mount', x, y, TRAY_CB, TRAY_CB))
    for (x, y) in HARNESS_TIE:
        F.append(_rect('tray', 'harness tie', x, y, *HARNESS_SLOT))
    return F


def validate():
    bad = []

    def gap(a, b):
        return max(max(a[2] - b[3], b[2] - a[3]),
                   max(a[4] - b[5], b[4] - a[5]))

    mods = _module_rects()
    for i in range(len(mods)):
        for j in range(i + 1, len(mods)):
            g = gap(mods[i], mods[j])
            if g < 0:
                bad.append('MODULES OVERLAP %.2fmm: %s x %s'
                           % (-g, mods[i][0], mods[j][0]))

    F = _feature_rects()
    for i in range(len(F)):
        for j in range(i + 1, len(F)):
            a, b = F[i], F[j]
            if a[0] == b[0]:              # same module's own features
                continue
            g = gap(a, b)
            if g < 0:
                bad.append('OVERLAP %.2fmm: %s x %s' % (-g, a[1], b[1]))
            elif g < 1.0:
                bad.append('gap only %.2fmm: %s x %s' % (g, a[1], b[1]))

    # a feature belonging to one module must not intrude on ANOTHER module
    for f in F:
        for m in mods:
            if f[0] == m[0] or f[0] == 'tray':
                continue
            if gap(f, m) < 0:
                bad.append('%s intrudes into %s' % (f[1], m[1]))

    half = PLATE_W / 2 - 1.5
    for a in F:
        if a[2] < -half or a[3] > half or a[4] < -half or a[5] > half:
            bad.append('off the plate: %s' % a[1])

    # ---- the snap fingers: do they CLICK, and do they survive it? ----
    # The old check here compared RAISE+wall against RAISE, which is true
    # for any positive wall - it could never fail and proved nothing. This
    # one asks the two questions that decide whether the part works.
    #
    # Click-over deflection is the emboss reach measured from the STEM
    # face, since that is where the wall starts from: the board pushes the
    # finger out by (seat - tip). Cantilever root is the plate, the load
    # lands at the emboss mid-height.
    snap_len = RAISE + BOARD_T + SNAP_H / 2.0
    for (name, w, l, h, cx, cy, mount) in MODULES:
        if mount != 'corners':
            continue
        ov = GRIP_P.get(name) or {}
        for axis, half in (('w', w / 2.0), ('l', l / 2.0)):
            seat = half + ov.get(axis, SNAP_GAP)
            over = half - (half - SNAP_B)      # emboss past the board edge
            defl_s = seat - (half - SNAP_B)    # stem face -> emboss tip
            if over <= 0.15:
                bad.append('%s %s emboss only %.2fmm over the board - no '
                           'click' % (name, axis, over))
            # straight cantilever, uniform section: e = 3*t*d / (2*L^2)
            st = 3.0 * SNAP_T * defl_s / (2.0 * snap_len ** 2)
            if st > 0.045:
                bad.append('%s %s finger strain %.2f%% - snaps even in PETG'
                           % (name, axis, st * 100))
            # Two fingers sharing one edge must stay SEPARATE fingers. The
            # main overlap sweep above skips same-module pairs, so nothing
            # else looks at this - and merged bands are not a cosmetic
            # problem, they fuse into one stiff block and the flexure is
            # gone. (Same failure as the tie slots that merged into one
            # 4.5mm aperture and could not be tensioned.)
            offs = sorted(finger_offsets(name, axis))
            edge = l if axis == 'w' else w      # the edge they sit along
            for p, q in zip(offs, offs[1:]):
                if q - p < SNAP_W + 1.0:
                    bad.append('%s %s fingers %.1fmm apart - only %.2fmm '
                               'between %.1fmm bands, they fuse'
                               % (name, axis, q - p, q - p - SNAP_W, SNAP_W))
            for o in offs:
                if abs(o) + SNAP_W / 2.0 > edge / 2.0:
                    bad.append('%s %s finger at %+.1f overhangs its %.1fmm '
                               'edge by %.2fmm' % (name, axis, o, edge,
                               abs(o) + SNAP_W / 2.0 - edge / 2.0))
    snap_worst = max(
        3.0 * SNAP_T * ((half + (GRIP_P.get(n) or {}).get(a, SNAP_GAP))
                        - (half - SNAP_B)) / (2.0 * snap_len ** 2)
        for (n, w, l, h, cx, cy, mt) in MODULES if mt == 'corners'
        for a, half in (('w', w / 2.0), ('l', l / 2.0)))

    # ---- the post pilot must break out of the post top ----
    if PLATE_TOP + 1.0 + (POST_H - 1.0) < PLATE_TOP + POST_H - 1e-9:
        bad.append('PCB post pilot is capped - no screw can enter')

    # ---- the cell clip: retention AND insertability ----
    r = (CELL_D + CELL_CLR) / 2.0
    ow = CELL_D + CELL_CLR + 2 * TROUGH_W
    wall_h = r + CELL_WRAP
    mouth = 2 * math.sqrt(max(r * r - (wall_h - r) ** 2, 0.0))
    top_open = mouth + 2.0 * LEAD_FLARE
    interf = CELL_D - mouth
    defl = interf / 2.0

    # TAPERED beam, integrated - NOT the uniform-section formula. The wall is
    # 4.7mm thick at the slot floor and 1.2mm at the centre line, and a beam
    # bends where it is thinnest, so the uniform formula understates the peak
    # by nearly half (0.85% vs 1.46%). Getting exactly this wrong is what put
    # rev F's fingers at 3.6% while its comments claimed 0.85%.
    def _hw(z):
        return math.sqrt(max(r * r - (z - r) ** 2, 0.0))

    def _t(z):
        t = ow / 2.0 - _hw(z) - (WALL_THIN if z >= SLOT_FLOOR else 0.0)
        return max(t, 0.05)

    span = wall_h - SLOT_FLOOR
    n, integ, peak = 2000, 0.0, 0.0
    width = (CELL_L - len(SLOT_Y) * SLOT_W) / (len(SLOT_Y) + 1)
    for i in range(n):
        s = (i + 0.5) * span / n
        t = _t(SLOT_FLOOR + s)
        inertia = width * t ** 3 / 12.0
        integ += (span - s) ** 2 / inertia * (span / n)
        peak = max(peak, (span - s) * t / (2.0 * inertia))
    strain = defl * peak / integ if integ else 1.0

    if interf <= 0.3:
        bad.append('cell clip has only %.2fmm interference - it will fall out'
                   % interf)
    if abs(top_open - CELL_TOP_OPEN) > 0.01:
        bad.append('cell top opening %.2fmm, expected %.2fmm'
                   % (top_open, CELL_TOP_OPEN))
    # This is a PETG-only plate: the snap fingers already need PETG, and
    # the requested 13.5mm cell entrance makes the cell fingers 3.31% too.
    # Do not label the intentional PLA limitation as a geometry failure, but
    # reject a clip that exceeds PETG's practical ~5% strain limit.
    if strain > 0.045:
        bad.append('cell finger strain %.2f%% - snaps even in PETG'
                   % (strain * 100))
    info = ('CELL: top opening %.2fmm, clip throat %.2fmm vs cell %.1f -> '
            '%.2fmm interference (%.2fmm per wall); %d fingers/side %.1fmm '
            'wide, %.1fmm free, TAPERED '
            'strain %.2f%% (PETG ~5%%, PLA ~2%%)\n'
            'SNAP: %.1fmm wall, %.2fmm emboss over the board, %.1fmm mouth '
            'flare, worst click strain %.2f%% (PETG ~5%%, PLA ~2%%)'
            % (top_open, mouth, CELL_D, interf, defl, len(SLOT_Y) + 1, width, span,
               strain * 100,
               SNAP_T, SNAP_B, SNAP_FLARE, snap_worst * 100))
    return bad, info


def engrave(comp, body, txt, cx, cy, size):
    """Cut a name into the plate top. Text features fail on some Fusion
    builds, so every label is independently guarded - a missing label must
    never cost you the whole tray."""
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        ti = sk.sketchTexts.createInput2(txt, mm(size))
        half_w = size * 0.75 * len(txt) / 2.0
        ti.setAsMultiLine(
            adsk.core.Point3D.create(mm(cx - half_w), mm(cy - size), 0),
            adsk.core.Point3D.create(mm(cx + half_w), mm(cy + size), 0),
            adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
            adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0)
        t = sk.sketchTexts.add(ti)
        f = comp.features.extrudeFeatures
        ei = f.createInput(t, CUT)
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(PLATE_TOP)))
        ei.setDistanceExtent(
            False, adsk.core.ValueInput.createByReal(mm(-ENGRAVE_D)))
        ei.participantBodies = [body]
        f.add(ei)
    except Exception as e:
        SKIPPED.append('label "%s": %s' % (txt, e))


def build_plate(comp):
    plate = box(comp, 0, 0, 0, PLATE_W, PLATE_H, PLATE_TH, NEW).bodies.item(0)
    plate.name = 'FIR Electronics Tray'
    fillet_vertical(comp, plate, CORNER_R)


    # ---- the PCB: 4 posts on its own M3 pattern ----
    half = PCB_HOLE_PITCH / 2.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = PCB_CX + sx * half, PCB_CY + sy * half
            cyl(comp, x, y, PLATE_TOP, POST_D, POST_H, JOIN, [plate])
            # Pilot for an M3 self-tapper. It must be OPEN AT THE TOP - the
            # screw comes down through the PCB. Rev F cut PLATE_TOP..+29.5
            # inside a post spanning PLATE_TOP..+30, which capped it with
            # 0.5mm of solid and sealed 145mm3 of air inside each post: the
            # screw had nowhere to enter. Cut from 1mm above the plate face
            # to the post top instead, same convention as screw_bosses().
            cyl(comp, x, y, PLATE_TOP + 1.0, POST_PILOT, POST_H - 1.0, CUT,
                [plate])

    # ---- wire-in modules, each held its own way ----
    for (name, w, l, h, cx, cy, mount) in MODULES:
        wall = 5.0 if h > 10 else 3.5
        if mount == 'screws':
            screw_bosses(comp, plate, cx, cy, HOLES[name])
        elif mount == 'corners':
            snap_fingers(comp, plate, cx, cy, w, l, name=name)
            tie_slots(comp, plate, cx, cy, w, l, axis=TIE_AXIS.get(name, 'x'))
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

    # ---- harness tie-down slots, in pairs ----
    for (x, y) in HARNESS_TIE:
        box(comp, x, y, -1, HARNESS_SLOT[0], HARNESS_SLOT[1],
            PLATE_TH + 2, CUT, [plate])

    # ---- names engraved last, so they cut into finished plate ----
    for (txt, lx, ly, sz) in LABELS:
        engrave(comp, plate, txt, lx, ly, sz)

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
        bad, info = validate()
        msg = VERSION + '\n\n' + info
        msg += '\n\nSELF-CHECK: ' + ('PASS' if not bad
                                     else '%d PROBLEM(S)' % len(bad))
        if bad:
            msg += '\n - ' + '\n - '.join(bad)
        if SKIPPED:
            msg += '\n\nSkipped:\n - ' + '\n - '.join(SKIPPED)
        ui.messageBox(msg)
    except:  # noqa
        if ui:
            ui.messageBox('FIR_ModulePlate failed:\n{}'.format(
                traceback.format_exc()))


if '--check' in sys.argv:
    problems, detail = validate()
    print(VERSION)
    print(detail)
    print('SELF-CHECK:', 'PASS' if not problems else
          '%d PROBLEM(S)' % len(problems))
    for p in problems:
        print('  -', p)
    sys.exit(1 if problems else 0)
