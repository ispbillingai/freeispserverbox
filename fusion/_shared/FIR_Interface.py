"""Shared mechanical interface dimensions for the active FreeISP brain stack.

This module intentionally has no Fusion API imports.  It is the one source of
truth for dimensions that must agree between:

* ``FIR_ModulePlate`` -- the electronics tray,
* ``FIR_ModuleGadget`` -- the small brain case, and
* ``FIR_Shell`` -- the large top-cap bosses.

All values are millimetres and use the centre of the tray / brain case as the
XY origin.  ``CASE_TO_CAP_Y`` is the small case's installed translation in the
large-cap coordinate system.  The four cap-boss centres are deliberately
derived from the four case-hole centres, rather than maintained as a second
hand-entered pattern.

Deployment note: copy this ``_shared`` folder alongside the Fusion script
folders (for example, ``.../API/Scripts/_shared/FIR_Interface.py``).  The
three consuming scripts also accept ``FIR_INTERFACE_PATH`` for a nonstandard
deployment location.
"""

import math

INTERFACE_VERSION = '2026-08-18.12'

# Electronics tray: FIR_ModulePlate
#
# This tray is a snug, hand-push fit in the printable ModuleGadget pocket.
# A zero-clearance CAD fit would fuse/jam on normal FDM prints, so retain a
# small 0.35mm allowance on every side.  The rounded corners share the pocket
# centres, which makes the clearance uniform on both the flats and arcs.
TRAY_POCKET_W = 129.0
TRAY_POCKET_H = 129.0
TRAY_POCKET_CORNER_R = 9.5
TRAY_FIT_CLEAR_PER_SIDE = 0.35
TRAY_W = TRAY_POCKET_W - 2.0 * TRAY_FIT_CLEAR_PER_SIDE
TRAY_H = TRAY_POCKET_H - 2.0 * TRAY_FIT_CLEAR_PER_SIDE
TRAY_TH = 3.0
# The printable tray's four vertical corners are filleted.  The small case
# uses this value to create a matching continuous support ledge, so a future
# tray-corner change cannot silently reopen unsupported gaps.
TRAY_CORNER_R = TRAY_POCKET_CORNER_R - TRAY_FIT_CLEAR_PER_SIDE
TRAY_MOUNT = (
    (0.0, -58.0),
    (0.0, 58.0),
    (-58.0, 0.0),
    (58.0, 0.0),
)

# Brain PCB: freeisp_brain rev H
PCB_W = 115.0
PCB_H = 115.0
PCB_TH = 1.6
PCB_HOLE_EDGE = 4.5
PCB_HOLE_PITCH = PCB_W - 2.0 * PCB_HOLE_EDGE
PCB_HOLE_HALF = PCB_HOLE_PITCH / 2.0
PCB_CX = 0.0
PCB_CY = 0.0
PCB_HOLE_PATTERN = tuple(
    (PCB_CX + sx * PCB_HOLE_HALF, PCB_CY + sy * PCB_HOLE_HALF)
    for sx in (-1.0, 1.0)
    for sy in (-1.0, 1.0)
)

# Small brain case -> large top cap.
# The case is installed 10 mm toward +Y and 47 mm toward +X.  The +X move is
# what opens the full-height column on the switch side that the alarm horn
# lives in; without it there is no 102 mm-wide space anywhere in the box.
# Its symmetric local holes therefore land on the cap bosses at X=-11.5/+105.5
# and Y=-30/+50.
#
# WARNING: the cap-boss pattern is no longer symmetric in X.  FIR_Shell prints
# the cap roof-down and flips it left/right on assembly, so it must mirror
# these X values when placing them.  While the pattern was symmetric that bug
# was invisible.
CASE_TO_CAP_X = 47.0
CASE_TO_CAP_Y = 10.0
CASE_MOUNT = (
    (-58.5, -40.0),
    (58.5, -40.0),
    (-58.5, 40.0),
    (58.5, 40.0),
)
CAP_BOSS_PATTERN = tuple(
    (x + CASE_TO_CAP_X, y + CASE_TO_CAP_Y) for x, y in CASE_MOUNT
)

# Small brain case outer envelope.  ``FIR_ModuleGadget`` builds to these, and
# ``FIR_Shell`` needs the same numbers to know which tub features would rise
# into the hanging case, so they live here instead of in one part file.
CASE_OUTER_W = 134.0
CASE_OUTER_H = 134.0
CASE_BODY_Z = 69.6

# ---------------------------------------------------------------------------
# Confirmed Tenda 5-port switch: DC jack
# ---------------------------------------------------------------------------
# The 82 x 52 x 23mm envelope and the 68.8 x 11.5mm front service slot are
# already carried by FIR_Shell / FIR_BottomLid / FIR_ShellCheck.  Only the
# barrel jack lives here, because the tub cradle (FIR_Shell) and the all-up
# clearance check (FIR_ShellCheck) must agree on exactly where the plug needs
# air, and getting that wrong is not visible until the switch is wired.
# Envelope and mounted position.  These used to be hand-entered separately in
# FIR_Shell, FIR_BottomLid, FIR_CurvedLid and FIR_ShellCheck; the switch cannot
# be moved safely while four files each hold their own copy of where it is.
POE_W, POE_D, POE_H = 82.0, 52.0, 23.0
# Moved inboard from -85 so a STRAIGHT barrel plug can go in from the side:
# that leaves 25.0mm off its end face instead of the old 11.0mm.
POE_CX = -71.0
POE_PORT_SIDE_LAND = 6.6          # measured land each side of the port opening
POE_PORT_W = POE_W - 2.0 * POE_PORT_SIDE_LAND
POE_PORT_H = 11.5
POE_PORT_FROM_BOTTOM = 3.2
POE_CABLE_NOTCH_PITCH = 16.0      # front-cover cable notches under the switch
POE_CABLE_NOTCH_COUNT = 5
POE_JACK_D = 6.0                  # measured hole in the switch case
POE_JACK_FROM_REAR = 8.3          # jack centre, measured from the switch REAR face
POE_JACK_FROM_BASE = 11.5         # ASSUMED mid-height -- this one is NOT measured
POE_JACK_MEASURED_HEIGHT = False  # flip to True once the real height is taken
# -1.0 = the switch's own RIGHT-hand end viewed from the front, which is shell
# -X (the wall side).  +1.0 = its left/inboard end, facing the MikroTik.
POE_JACK_SIDE = -1.0
POE_PLUG_D = 9.5                  # 5.5/2.1 barrel plug body
POE_PLUG_STRAIGHT_L = 14.0        # straight plug body
POE_PLUG_RIGHT_ANGLE_L = 10.0     # right-angle plug body
POE_PLUG_MIN_AIR = POE_PLUG_RIGHT_ANGLE_L + 1.0

# ---------------------------------------------------------------------------
# Cap-to-tub SELF-CLICK detents
# ---------------------------------------------------------------------------
# The owner wants the cap to positively CLICK home, not just rest until the
# screws go in.  Standard snap detent: a stepped bump on the tub's outer wall
# rides the descending skirt (which flexes ~0.7mm over it) and pops into a
# through-window in the skirt at full seat.  The bump's flat underside then
# catches the window's lower edge, so the cap resists lifting even with no
# screws fitted.  The 8 screws remain the permanent lock.
#   sides: two detents per wall at Y = +-45 (clear of the screw row at
#   -75/0/+75 and of the crush rib at Y0);  back: two at X = +-45 (clear of
#   the back screws at +-115 and the keyholes at +-60).
CAP_SNAP_SIDE_Y = (-45.0, 45.0)
CAP_SNAP_BACK_X = (-45.0, 45.0)
CAP_SNAP_W = 8.0                  # bump width along the wall
CAP_SNAP_PROUD = 1.2              # bump stand-off from the wall outer face
CAP_SNAP_Z0, CAP_SNAP_Z1 = 71.0, 76.0   # bump band (flat catch at the bottom)
CAP_SNAP_WIN_W = 10.0             # skirt window, 1mm clearance each side
CAP_SNAP_WIN_Z0, CAP_SNAP_WIN_Z1 = 70.0, 76.5

# ---------------------------------------------------------------------------
# Cap-to-tub screws + VISIBLE screw seats (owner complaint, 16 Aug 2026)
# ---------------------------------------------------------------------------
# The owner exported the model and could not find anywhere to screw the lids
# together: a flush 3.4mm hole on a 286mm face is invisible in a shaded render,
# so every outside screw now sits in a feature you can see and feel.
#   cap skirt: a 12mm round pad stands 2.5mm proud around each hole, with a
#     6.5mm counterbore cut back to the original skirt face - the M3 pan head
#     (2.4mm tall) seats on the skirt exactly as before, fully inside the pad,
#     so every documented engagement number is unchanged.
#   BottomLid: the same 12mm pad, 1.5mm proud, and the counterbore is re-cut
#     from the pad top - the head land grows from 0.8mm to 1.9mm of plate.
#   CurvedLid: it prints face-down, so a proud pad would lift it off the bed;
#     its two lock screws get a 10mm dished recess 1.0mm into the 2.5mm face.
M3_HEAD_H = 2.4                   # DIN 7985 pan head; button heads sit lower
M3_SEAT_PAD_D = 12.0
M3_SEAT_CBORE_D = 6.5
CAP_SEAT_PAD_H = 2.5
LID_SEAT_PAD_H = 1.5
LID_SEAT_CBORE_DEPTH = 2.6        # from pad top -> 1.9mm land in the 3mm plate
COVER_SEAT_D = 10.0
COVER_SEAT_DEPTH = 1.0            # leaves 1.5mm of the 2.5mm cover face
# Repeat-opening screws thread into printed plastic today.  Brass M3 heat-set
# inserts are the durable answer for lids opened many times; that is an OWNER
# DECISION not yet taken.  Per the 18 Aug two-AI review the conversion is
# PER CLOSURE, not global: the cap and the cover lock open often (insert
# candidates), the BottomLid rarely (self-tap stays fine).  Flip a closure's
# flag once Francis buys inserts - and set M3_INSERT_BORE_D from the actual
# insert's datasheet FIRST; 4.0 is a typical value, not a chosen one.
M3_SELF_TAP_PILOT_D = 2.6
M3_INSERT_BORE_D = 4.0            # PLACEHOLDER until a real insert is bought
CAP_BOSS_INSERTS = False
COVER_LOCK_INSERTS = False
BOTTOM_LID_INSERTS = False
CAP_BOSS_PILOT_D = M3_INSERT_BORE_D if CAP_BOSS_INSERTS else M3_SELF_TAP_PILOT_D
COVER_LOCK_BOSS_PILOT_D = (M3_INSERT_BORE_D if COVER_LOCK_INSERTS
                           else M3_SELF_TAP_PILOT_D)
BOTTOM_LID_BOSS_PILOT_D = (M3_INSERT_BORE_D if BOTTOM_LID_INSERTS
                           else M3_SELF_TAP_PILOT_D)
# The cover-lock boss was 7mm wide - fine around a 2.6 self-tap pilot, far
# too narrow to ever take a brass insert.  It is now 10mm wide, which forced
# the lock screws inboard from X+-125 to X+-122 so the boss clears the
# cover's channel rib (inner face at 129.1) with 2.1mm of air.
COVER_LOCK_X = 122.0
COVER_LOCK_BOSS_W = 10.0
# Cap fastening: EIGHT horizontal M3 at Z72, now ALL through the side walls.
# The old back pair at X=+-115 could not be driven with the box hanging on a
# wall (8mm of air behind it), so it moved to the side walls at Y=-118 - the
# back edge is held by its two snap detents plus these corner-adjacent screws.
CAP_SCREW_Z = 72.0
CAP_SIDE_SCREW_Y = (-118.0, -75.0, 0.0, 75.0)
# Lead-in: a 45-degree chamfer on the skirt's lower inner edge (two sides +
# back) so the 0.5mm-per-side slide fit starts itself instead of biting the
# tub rim.  Agreed in the 18 Aug two-AI design review.
CAP_LEADIN_CH = 1.2

# ---------------------------------------------------------------------------
# CurvedLid <-> BottomLid slide interface (18 Aug 2026 two-AI review)
# ---------------------------------------------------------------------------
# These numbers were hand-duplicated between FIR_BottomLid (rails) and
# FIR_CurvedLid (channels) - the same disease that broke the switch position
# once.  Now both derive from here, as do the fit-test coupons.
#   COVER_RAIL_CLR is the ONE slide clearance (the old scripts declared
#   CLR=0.4 and then hard-coded 0.3 - a real reviewer catch).
COVER_RAIL_X = 133.0              # rail centres, +- in BottomLid local X
COVER_RAIL_W = 4.0
COVER_RAIL_H = 5.0
COVER_RAIL_CLR = 0.3              # side/top guide clearance per face
COVER_CHANNEL_RIB_W = 1.6
# Anti-rattle: one nub under each channel web presses 0.15mm into the rail
# top, engaging only over the last ~5mm of travel so the slide stays free.
COVER_NUB_PROUD = 0.15
COVER_NUB_LEN = 5.0
# Locator tongue, split into four short tabs (a 249mm continuous tongue
# bows/shrinks on FDM and can jam; four 25mm tabs is the agreed answer).
COVER_TAB_X = (-90.0, -30.0, 30.0, 90.0)
COVER_TAB_LEN = 25.0
# ORIENTATION KEY: a block on top of the BottomLid rail that is at SHELL +X
# (lid-local -X, because the lid is turned over), plus a matching relief cut
# in the cover's shell +X channel web.  Correct cover: the relieved web stops
# 1.5mm short of the block.  Reversed cover: the unrelieved web hits the
# block and the cover stands ~7mm proud with its lock seats visibly open.
# Wordless, mirror-proof, and cheaper than trusting labels through three
# different assembly flips.
COVER_KEY_BLOCK_H = 2.5           # on the rail top
COVER_KEY_BLOCK_LEN = 9.0         # from the lid plate face
COVER_KEY_RELIEF_LEN = 9.5        # web shortened by this at the tub end

# ---------------------------------------------------------------------------
# Wall mounting: printed wall plate + French cleat (replaces the keyholes)
# ---------------------------------------------------------------------------
# The two 11mm keyholes could barely hold a 2-3kg loaded box, and their screw
# heads protruded into the 4mm gap in front of the adapter bank.  Both are
# gone.  The box now hangs on a separate printed FIR WALL PLATE:
#   * the plate screws to the wall with up to six 4.5mm screws whose heads sit
#     in pockets INSIDE the plate - nothing enters the box any more;
#   * a full-width 45-degree cleat bar on the tub's back wall drops onto the
#     plate's matching 45-degree face and wedges the box against the plate;
#   * a crest wall behind the bar stops the box being pulled straight off;
#   * two under-floor arms end below the tub floor, and two M4 x 10 screws
#     driven DOWN from inside the box clamp the floor to them.  With the cap
#     screwed on, those screws are unreachable: the box cannot leave the wall
#     without first unlocking and removing the cap.  That is the anti-theft.
# Everything below Z65 so the cap skirt (Z65..120) never touches the plate.
WALL_PLATE_TH = 9.0               # leaves a 2.4mm crest wall behind the bar tip
WALL_PLATE_X_HALF = 138.0
WALL_PLATE_TOP_Z = 61.0
WALL_PLATE_BOT_Z = -8.4
WALL_FACE_Y = -140.0 - WALL_PLATE_TH        # the building wall sits at -149
CLEAT_BAR_X_HALF = 95.0
CLEAT_FACE_Z0 = 50.8              # 45deg face height at the box-back plane
CLEAT_BAR_RUN = 5.8               # bar protrusion behind the box back
CLEAT_TIP_CLEAR = 0.8             # air between bar tip and the crest wall
CLEAT_CREST_TOP_Z = 61.0          # lift the box past this to unhook it
CLEAT_BAR_TOP_Z = 64.0
# In-box lock screws: straight-down driver corridors inside the back corner
# fillet pockets, clear of the extension strip (|X|<=120), the rear cap-screw
# bosses (Y-124..-112) and the strap-anchor lugs.  Same M4 x 10 as the horn.
WALL_LOCK_X = (-129.0, 129.0)
WALL_LOCK_Y = -130.0
WALL_LOCK_CLEAR_D = 4.5           # clearance hole through the 3mm tub floor
WALL_LOCK_PILOT_D = 3.4
WALL_LOCK_PILOT_DEPTH = 7.0       # M4 x 10: 3 floor + 0.4 lift + 6.6 bite
WALL_ARM_W = 14.0
WALL_ARM_TH = 8.0
WALL_ARM_TOP_Z = -0.4             # 0.4 under the floor: the cleat carries the
                                  # weight; the screws pre-load the arms up
WALL_ARM_Y0 = -118.0              # forward end of each under-floor arm
WALL_SCREW_D = 4.5
WALL_SCREW_HEAD_D = 11.0
WALL_SCREW_HEAD_DEPTH = 3.5       # head sits below the plate front face
WALL_SCREW_POS = ((-115.0, 40.0), (115.0, 40.0), (-115.0, 8.0),
                  (115.0, 8.0), (0.0, 44.0), (0.0, 8.0))


def cleat_crest_front_y():
    """Front face of the plate's crest wall, behind the bar tip."""
    return -140.0 - CLEAT_BAR_RUN - CLEAT_TIP_CLEAR


def cleat_bar_tip_z():
    """Underside height of the cleat bar at its tip (45-degree face)."""
    return CLEAT_FACE_Z0 + CLEAT_BAR_RUN


def cleat_interlock():
    """How far the box must LIFT before it can be pulled off the wall."""
    return CLEAT_CREST_TOP_Z - cleat_bar_tip_z()


# ---------------------------------------------------------------------------
# Alarm horn: INSIDE the box, on the floor behind the switch
# ---------------------------------------------------------------------------
# The bought part is a 12V 15W siren horn on a swivel foot.  Owner-measured
# bounding box, with the tightening bolts standing off the back of it.  It is
# mounted lying down, axis front-to-back, mouth facing the front panel; it
# cannot be tilted inside the box because a 20-degree tilt already needs more
# headroom than the 114 mm cavity has.
#
# All values are ASSEMBLED shell coordinates (origin at the footprint centre,
# +Y front, +Z up).
HORN_W, HORN_L, HORN_H = 102.0, 105.0, 102.0
HORN_BOLT_TAIL = 15.0             # tightening bolts standing off the back
# Owner-measured bell taper, rear -> mouth: the body is a flared cone, only
# reaching 102mm at the very mouth.  (fraction of length from the rear, dia)
HORN_PROFILE = ((0.0, 74.0), (0.5, 76.0), (0.75, 83.0), (1.0, 102.0))
HORN_ARM_W = 29.0                 # bracket stand width at the rear (approx)
HORN_CX = -73.0                   # body centre; -124..-22 clears the wall bosses
# 4 mm behind the switch cradle's back wall: the cradle's rear snap hooks need
# ~3 mm of backward flex to click the switch in or out, so the switch stays
# serviceable without unbolting the horn.  Was 79.5 (2 mm), which trapped it.
HORN_MOUTH_Y = 77.5
HORN_FOOT_D = 69.0                # circular bracket foot, measured
HORN_HOLE_D = 6.0                 # measured holes in that foot
HORN_BASE_C2C, HORN_SIDE_C2C = 38.5, 50.0
# NOT MEASURED: how far back the foot's centre sits from the mouth face.  The
# three floor pads move with this one number, so it is worth a tape measure.
HORN_FOOT_FROM_MOUTH = 99.0
HORN_FOOT_MEASURED = False
# Fastening rework (16 Aug 2026, after the owner rejected the peg): ALL THREE
# measured foot holes get real bolts again.  They are driven ON THE BENCH into
# a small printed SLED (adapter plate) where nothing hangs over them - the
# bracket arm and its tightening bolts sit right above the rear foot holes, so
# no in-box driver path to them exists in any orientation.  The bolted-up
# horn+sled then drops into a curb pocket on the tub floor and TWO M4 wing
# screws, on wings that stick out BEHIND everything, clamp it down.  Adapter
# plates are the standard answer to fastening under an unreachable overhang.
HORN_FOOT_PLATE_TH = 3.0          # the horn's own steel foot plate
HORN_SLED_TH = 3.0                # printed sled plate on the tub floor
HORN_SLED_BOSS_H = 3.0            # foot bosses on the sled -> foot plane Z9
HORN_SLED_X0, HORN_SLED_X1 = -111.0, -35.0
HORN_SLED_Y0, HORN_SLED_Y1 = -58.0, 30.0
HORN_SLED_PILOT_D = 3.4           # bench screws: M4 x 8 max (6mm of plastic)
HORN_SLED_PILOT_DEPTH = 5.5
HORN_WING_W, HORN_WING_L = 24.0, 14.0
HORN_WING_Y = -65.0               # wing screw line, behind the foot and bell
HORN_WING_SCREW_X = (-93.0, -53.0)
HORN_CURB_TH, HORN_CURB_H = 2.5, 5.5   # stays 0.5 under the bell envelope
HORN_CURB_CLEAR = 0.3
# Floor mounting: three pads raise the foot clear of the floor fillets.  Pad
# 6 mm + pilot 7 mm is sized so an M4 x 10 (3 mm foot plate + 7 mm of thread)
# bottoms exactly at the pilot floor with 2 mm of tub floor still under it;
# M4 x 8 also works.  Do not use longer than M4 x 10.
HORN_PAD_D, HORN_PAD_H = 14.0, 6.0
HORN_PILOT_D, HORN_PILOT_DEPTH = 3.4, 7.0
# NO SOUND VENTS, by owner decision (16 Aug 2026): this siren is loud enough
# that a plastic box will not meaningfully muffle it, so the front panel and the
# lid both stay closed.  Do not re-add a grille to FIR_BottomLid, FIR_CurvedLid
# or the cap without asking - it was tried and deliberately taken back out.
HORN_VENTS = False


def poe_cable_notch_x():
    """Front-cover cable notch centres under the switch, in shell X."""
    span = (POE_CABLE_NOTCH_COUNT - 1) * POE_CABLE_NOTCH_PITCH
    return tuple(POE_CX - span / 2.0 + i * POE_CABLE_NOTCH_PITCH
                 for i in range(POE_CABLE_NOTCH_COUNT))


def poe_jack_air(wall_inner_x=137.0, mikrotik_inner_x=21.0):
    """Air off the switch's jack end face before something stops the plug."""
    face = POE_CX + POE_JACK_SIDE * POE_W / 2.0
    if POE_JACK_SIDE < 0:
        return face - (-wall_inner_x)
    return mikrotik_inner_x - face


def horn_body():
    """Return the horn's assembled envelope (x0, x1, y0, y1, z0, z1)."""
    z0 = horn_foot_plane_z()
    return (HORN_CX - HORN_W / 2.0, HORN_CX + HORN_W / 2.0,
            HORN_MOUTH_Y - HORN_L, HORN_MOUTH_Y,
            z0, z0 + HORN_H)


def horn_foot_centre():
    """Centre of the 69 mm bracket foot on the tub floor."""
    return (HORN_CX, HORN_MOUTH_Y - HORN_FOOT_FROM_MOUTH)


def horn_mount_points():
    """The three foot-hole centres, in assembled shell coordinates.

    The foot centre is the circumcentre of the measured isosceles triangle.
    The single APEX points FORWARD, under the horn body, and gets the peg
    (index 0).  The two BASE holes point toward the extension at the back,
    land behind the horn body, and take the real bolts (indices 1 and 2) -
    that is what makes them reachable with the horn still on its bracket.
    """
    cx, cy = horn_foot_centre()
    half_base = HORN_BASE_C2C / 2.0
    altitude = math.sqrt(HORN_SIDE_C2C ** 2 - half_base ** 2)
    base_y = (altitude ** 2 - half_base ** 2) / (2.0 * altitude)
    apex_y = altitude - base_y
    return (
        (cx, cy + apex_y),                     # apex, under the body
        (cx - half_base, cy - base_y),
        (cx + half_base, cy - base_y),
    )


def horn_wing_points():
    """The two in-box clamp screws, on wings clear of everything above."""
    return tuple((wx, HORN_WING_Y) for wx in HORN_WING_SCREW_X)


def horn_foot_plane_z():
    """Where the horn's steel foot sits: floor + sled + bosses."""
    return 3.0 + HORN_SLED_TH + HORN_SLED_BOSS_H


def horn_axis_z():
    """Bell axis height: the 102mm mouth just grazes the foot plane."""
    return horn_foot_plane_z() + HORN_H / 2.0


def horn_profile_segments():
    """Measured bell taper as (y0, y1, diameter) segments in shell Y.

    Each measured station's diameter carries the quarter of the length it was
    taken in, so the drawn shape stays conservative between stations without
    inflating the whole body to the 102mm mouth diameter.
    """
    rear = HORN_MOUTH_Y - HORN_L
    stations = HORN_PROFILE
    out = []
    prev_f = 0.0
    for index, (frac, dia) in enumerate(stations):
        next_f = (stations[index + 1][0] + frac) / 2.0             if index + 1 < len(stations) else 1.0
        seg0 = prev_f if index else 0.0
        out.append((rear + seg0 * HORN_L, rear + next_f * HORN_L, dia))
        prev_f = next_f
    return tuple(out)


def validate():
    """Return interface-definition errors; empty means the contract is sound."""
    errors = []
    if min(TRAY_POCKET_W, TRAY_POCKET_H, TRAY_POCKET_CORNER_R,
           TRAY_W, TRAY_H, TRAY_TH, TRAY_CORNER_R) <= 0.0:
        errors.append('tray dimensions must be positive')
    if TRAY_CORNER_R >= min(TRAY_W, TRAY_H) / 2.0:
        errors.append('tray corner radius is too large')
    if not 0.25 <= TRAY_FIT_CLEAR_PER_SIDE <= 0.50:
        errors.append('tray push-fit allowance must stay within 0.25..0.50mm per side')
    if abs((TRAY_POCKET_W - TRAY_W) / 2.0 - TRAY_FIT_CLEAR_PER_SIDE) > 1e-9 or \
            abs((TRAY_POCKET_H - TRAY_H) / 2.0 - TRAY_FIT_CLEAR_PER_SIDE) > 1e-9:
        errors.append('tray dimensions do not match the specified pocket clearance')
    pocket_corner_c = TRAY_POCKET_W / 2.0 - TRAY_POCKET_CORNER_R
    tray_corner_c = TRAY_W / 2.0 - TRAY_CORNER_R
    if abs(pocket_corner_c - tray_corner_c) > 1e-9:
        errors.append('tray and pocket rounded-corner centres do not match')
    if min(PCB_W, PCB_H, PCB_TH, PCB_HOLE_EDGE) <= 0.0:
        errors.append('PCB dimensions and hole edge must be positive')
    if PCB_HOLE_PITCH <= 0.0:
        errors.append('PCB M3-hole pitch must be positive')
    if PCB_HOLE_PITCH != PCB_H - 2.0 * PCB_HOLE_EDGE:
        errors.append('PCB is not square but its hole pitch assumes it is')
    if len(TRAY_MOUNT) != 4 or len(set(TRAY_MOUNT)) != 4:
        errors.append('tray mount pattern must contain four unique centres')
    if len(CASE_MOUNT) != 4 or len(set(CASE_MOUNT)) != 4:
        errors.append('case mount pattern must contain four unique centres')
    if len(CAP_BOSS_PATTERN) != 4 or len(set(CAP_BOSS_PATTERN)) != 4:
        errors.append('cap-boss pattern must contain four unique centres')
    expected_cap_pattern = tuple((x + CASE_TO_CAP_X, y + CASE_TO_CAP_Y)
                                 for x, y in CASE_MOUNT)
    if CAP_BOSS_PATTERN != expected_cap_pattern:
        errors.append('cap-boss pattern no longer maps from the case pattern')
    if len(PCB_HOLE_PATTERN) != 4 or len(set(PCB_HOLE_PATTERN)) != 4:
        errors.append('PCB M3-hole pattern must contain four unique centres')
    if min(CASE_OUTER_W, CASE_OUTER_H, CASE_BODY_Z) <= 0.0:
        errors.append('brain-case outer envelope must be positive')
    if CASE_OUTER_W <= TRAY_POCKET_W or CASE_OUTER_H <= TRAY_POCKET_H:
        errors.append('brain case cannot be smaller than the tray pocket it holds')
    if POE_JACK_SIDE not in (-1.0, 1.0):
        errors.append('switch jack side must be -1.0 or +1.0')
    if poe_jack_air() < POE_PLUG_STRAIGHT_L + 5.0:
        errors.append(
            'switch is too close to its end obstruction for a straight plug: '
            '{:.1f}mm'.format(poe_jack_air()))
    if len(set(poe_cable_notch_x())) != POE_CABLE_NOTCH_COUNT:
        errors.append('switch cable-notch pattern is degenerate')
    if POE_JACK_D <= 0.0 or POE_JACK_D > POE_PLUG_D:
        errors.append('switch jack hole must be positive and no larger than the plug body')
    if POE_JACK_FROM_REAR <= 0.0 or POE_JACK_FROM_BASE <= 0.0:
        errors.append('switch jack offsets must be positive')
    # The isosceles horn triangle must close, and its bolt circle has to sit
    # inside the horn's own bracket foot.
    if HORN_SIDE_C2C <= HORN_BASE_C2C / 2.0:
        errors.append('horn triangle sides are too short to close on the measured base')
    fx, fy = horn_foot_centre()
    bolt_radius = max(math.hypot(x - fx, y - fy) for x, y in horn_mount_points())
    if bolt_radius + HORN_HOLE_D / 2.0 > HORN_FOOT_D / 2.0:
        errors.append('horn bolt circle does not fit inside the measured 69mm foot')
    if HORN_PAD_D <= HORN_PILOT_D:
        errors.append('horn floor pad is not wider than its own pilot')
    if HORN_PILOT_DEPTH >= HORN_PAD_H + 3.0:
        errors.append('horn floor pilot would break through the 3mm tub floor')
    if min(HORN_W, HORN_L, HORN_H, HORN_BOLT_TAIL) <= 0.0:
        errors.append('horn envelope must be positive')
    # The sled layout only works if (a) every foot hole lands on the sled,
    # (b) both wing screws sit behind the horn body AND behind the sled plate,
    # clear for a straight-down driver, and (c) the curb stays under the bell.
    body_rear = HORN_MOUTH_Y - HORN_L
    for hx_, hy_ in horn_mount_points():
        if not (HORN_SLED_X0 + 7.0 <= hx_ <= HORN_SLED_X1 - 7.0
                and HORN_SLED_Y0 + 2.0 <= hy_ <= HORN_SLED_Y1 - 7.0):
            errors.append('horn foot hole ({:.1f},{:.1f}) misses the sled'
                          .format(hx_, hy_))
    for wx_, wy_ in horn_wing_points():
        if wy_ > body_rear - 2.0:
            errors.append('horn wing screw at Y{:.1f} is under the body'.format(wy_))
        if wy_ > HORN_SLED_Y0 - HORN_WING_L / 2.0 + 1e-9:
            errors.append('horn wing screw is not behind the sled plate')
    if 3.0 + HORN_CURB_H > horn_foot_plane_z() - 0.5:
        errors.append('horn curb rises into the bell envelope')
    if abs(HORN_PROFILE[-1][1] - HORN_W) > 1e-9 or HORN_PROFILE[-1][0] != 1.0:
        errors.append('horn profile must end at the measured 102mm mouth')
    if any(b[1] < a[1] for a, b in zip(HORN_PROFILE, HORN_PROFILE[1:])):
        errors.append('horn profile must flare outward toward the mouth')
    if HORN_SLED_PILOT_DEPTH > HORN_SLED_TH + HORN_SLED_BOSS_H - 0.5:
        errors.append('horn sled pilot would pierce the sled bottom')
    # Snap detents must stay clear of the screw rows and the crush ribs, and
    # their window must fully swallow the bump.  The back wall no longer has
    # screws or keyholes; its bumps must only clear the cleat bar's top edge.
    for sy in CAP_SNAP_SIDE_Y:
        if min(abs(sy - r) for r in CAP_SIDE_SCREW_Y) < 20.0:
            errors.append('side snap at Y{:.0f} crowds a screw row or crush rib'.format(sy))
    if CAP_SNAP_Z0 < CLEAT_BAR_TOP_Z + 1.0:
        errors.append('back snap bumps reach down into the cleat bar')
    if not (CAP_SNAP_WIN_Z0 < CAP_SNAP_Z0 and CAP_SNAP_Z1 < CAP_SNAP_WIN_Z1):
        errors.append('snap window does not swallow the bump')
    if CAP_SNAP_WIN_W < CAP_SNAP_W + 1.5:
        errors.append('snap window too narrow for the bump')
    # The horn only fits because the brain case moved; if someone dials that
    # shift back without moving the horn, say so here rather than in a print.
    horn_x1 = HORN_CX + HORN_W / 2.0
    case_x0 = -CASE_OUTER_W / 2.0 + CASE_TO_CAP_X
    if case_x0 < horn_x1:
        errors.append(
            'brain case (from X{:.1f}) overlaps the horn (to X{:.1f}): raise '
            'CASE_TO_CAP_X or move the horn'.format(case_x0, horn_x1))
    if case_x0 - horn_x1 < 2.0:
        errors.append('brain case leaves under 2mm beside the horn')
    if CASE_OUTER_W / 2.0 + CASE_TO_CAP_X > 137.0 - 15.0:
        errors.append('brain case is pushed so far +X that its J4/J5 wires have no room')
    # Screw seats: the head must fully disappear into its pad, the deepened
    # BottomLid counterbore must leave a real land, and the cover recess must
    # leave printable skin in its 2.5mm face.
    if CAP_SEAT_PAD_H < M3_HEAD_H:
        errors.append('cap screw pad is shallower than the M3 head it must swallow')
    if M3_SEAT_CBORE_D <= 3.6 or M3_SEAT_CBORE_D >= M3_SEAT_PAD_D - 3.0:
        errors.append('screw-seat counterbore leaves no pad ring around the head')
    lid_land = 3.0 + LID_SEAT_PAD_H - LID_SEAT_CBORE_DEPTH
    if lid_land < 1.5:
        errors.append('BottomLid counterbore leaves only {:.1f}mm under the head'
                      .format(lid_land))
    if COVER_SEAT_DEPTH > 1.2:
        errors.append('cover seat recess cuts too deep into the 2.5mm face')
    if not 3.8 <= M3_INSERT_BORE_D <= 4.8:
        errors.append('M3 insert bore outside the plausible 3.8..4.8 range')
    for name, pilot in (('cap', CAP_BOSS_PILOT_D),
                        ('cover-lock', COVER_LOCK_BOSS_PILOT_D),
                        ('BottomLid', BOTTOM_LID_BOSS_PILOT_D)):
        if pilot not in (M3_SELF_TAP_PILOT_D, M3_INSERT_BORE_D):
            errors.append('{} boss pilot is neither self-tap nor insert bore'.format(name))
    if COVER_LOCK_BOSS_W < COVER_LOCK_BOSS_PILOT_D + 5.0:
        errors.append('cover-lock boss too narrow around its pilot/insert')
    # The widened boss must clear the cover channel's inner rib (X129.1).
    if COVER_LOCK_X + COVER_LOCK_BOSS_W / 2.0 > COVER_RAIL_X - COVER_RAIL_W / 2.0 \
            - COVER_RAIL_CLR - COVER_CHANNEL_RIB_W - 1.5:
        errors.append('cover-lock boss runs into the cover channel rib')
    # Cover slide interface: the nub must bite less than the guide clearance,
    # the key relief must clear the key block when the cover is fully home
    # (the fully-home web tip sits 2.0mm behind the lid plate face), and a
    # reversed cover's unrelieved web must positively hit the block.
    if not 0.0 < COVER_NUB_PROUD < COVER_RAIL_CLR:
        errors.append('anti-rattle nub must bite less than the rail clearance')
    if 2.0 + COVER_KEY_RELIEF_LEN - COVER_KEY_BLOCK_LEN < 1.5:
        errors.append('cover key relief too short: the RIGHT cover would hit the block')
    if COVER_KEY_BLOCK_H - COVER_RAIL_CLR < 1.0:
        errors.append('cover key block too low: a REVERSED cover would ride over it')
    if len(COVER_TAB_X) != len(set(COVER_TAB_X)):
        errors.append('cover locator tabs are degenerate')
    if max(COVER_TAB_X) + COVER_TAB_LEN / 2.0 > 125.0 - 8.0:
        errors.append('a cover locator tab runs off the BottomLid groove')
    # Cap screw rows: all four on each side wall, clear of each other, of the
    # snap detents, and inside the straight wall (corner radius starts |Y|133).
    rows = sorted(CAP_SIDE_SCREW_Y)
    if len(rows) != 4 or any(b - a < 20.0 for a, b in zip(rows, rows[1:])):
        errors.append('cap side screw rows must be four, at least 20mm apart')
    if any(abs(y) > 133.0 - M3_SEAT_PAD_D / 2.0 for y in CAP_SIDE_SCREW_Y):
        errors.append('a cap screw row runs into the corner radius')
    # Wall mount: the cleat system must stay under the cap skirt (Z65), hook
    # deep enough to need a real lift, and keep the bar tip off the crest.
    if CLEAT_BAR_TOP_Z > 64.0:
        errors.append('cleat bar rises into the cap skirt (skirt bottom Z65)')
    if WALL_PLATE_TOP_Z > 63.0:
        errors.append('wall plate top is too close to the cap skirt')
    if cleat_interlock() < 3.0:
        errors.append('cleat interlock under 3mm: the box could be flicked off the wall')
    if CLEAT_TIP_CLEAR < 0.6:
        errors.append('cleat bar tip would scrape the crest wall on the way down')
    if WALL_PLATE_TH - CLEAT_BAR_RUN - CLEAT_TIP_CLEAR < 2.0:
        errors.append('crest wall thinner than 2mm: it could not resist a pull-off')
    if CLEAT_BAR_X_HALF > WALL_PLATE_X_HALF - 4.0:
        errors.append('cleat bar is wider than the plate that receives it')
    # Lock screws: the straight-down driver corridor (7mm shaft) must clear
    # the extension strip, the rear cap-screw bosses and stay inside the
    # cavity's R7 corner pocket; the pilot must not pierce the arm.
    rear_row = min(CAP_SIDE_SCREW_Y)
    for lx in WALL_LOCK_X:
        if abs(lx) - 3.5 < 121.0:
            errors.append('wall lock screw at X{:.0f} crowds the extension strip'.format(lx))
        if WALL_LOCK_Y + 3.5 > rear_row - 6.0 - 2.0:
            errors.append('wall lock corridor runs into the rear cap-screw boss')
        if math.hypot(abs(lx) - 130.0, WALL_LOCK_Y + 130.0) + 3.5 > 6.5:
            errors.append('wall lock corridor at X{:.0f} leaves the R7 corner pocket'.format(lx))
        if abs(lx) + WALL_ARM_W / 2.0 > WALL_PLATE_X_HALF - 2.0:
            errors.append('under-floor arm at X{:.0f} hangs off the wall plate'.format(lx))
    if WALL_LOCK_PILOT_DEPTH > WALL_ARM_TH - 0.8:
        errors.append('wall lock pilot would pierce the under-floor arm')
    if 10.0 - 3.0 - (0.0 - WALL_ARM_TOP_Z) > WALL_LOCK_PILOT_DEPTH:
        errors.append('an M4 x 10 lock screw bottoms out before clamping the floor')
    if WALL_ARM_Y0 < WALL_LOCK_Y + 5.0:
        errors.append('under-floor arm stops short of its own lock screw')
    for wx, wz in WALL_SCREW_POS:
        if wz + WALL_SCREW_HEAD_D / 2.0 > CLEAT_FACE_Z0 - 1.0:
            errors.append('wall screw at Z{:.0f} runs into the cleat face'.format(wz))
        if abs(wx) > WALL_PLATE_X_HALF - 10.0 or wz < WALL_PLATE_BOT_Z + 8.0:
            errors.append('wall screw at ({:.0f},{:.0f}) sits too near the plate edge'
                          .format(wx, wz))
    if WALL_SCREW_HEAD_DEPTH + 4.0 > WALL_PLATE_TH:
        errors.append('wall screw head pocket leaves under 4mm of plate')
    return errors


_errors = validate()
if _errors:
    raise ValueError('Invalid FreeISP shared interface: {}'.format(
        '; '.join(_errors)))
