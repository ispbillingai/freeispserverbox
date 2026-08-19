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
#   sides: two detents per wall at Y = +-45 (clear of the screw rows at
#   +-85 and of the crush rib at Y0);  back: two at X = +-45, where there are
#   no screws at all - the detents ARE the back-edge retention.
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
# Cap fastening: FOUR horizontal M3 at Z72 - TWO PER SIDE WALL (owner, 18 Aug:
# "two sides each, not four").  Nothing on the back: it cannot be driven with
# the box on a wall, and the back edge is held by its two snap detents.
# +-85 gives a 170mm clamping base while clearing the snap detents at Y+-45,
# the strap-anchor lugs at Y-118..-102 and the corner radius.
CAP_SCREW_Z = 72.0
CAP_SIDE_SCREW_Y = (-85.0, 85.0)
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
# Front-closure TAMPER SENSING: reed switch + press-fit magnet (owner, 18 Aug)
# ---------------------------------------------------------------------------
# The magnet (measured D12.1) press-fits into a pocket on the CurvedLid's
# inner front face; the reed lies in a recessed groove in the BottomLid shelf
# directly in the magnet's slide path.  Closed cover = magnet ~10.6mm from
# the reed, head-on; sliding the cover off opens the reed within millimetres
# of travel.  Removing the BottomLid itself first requires removing the cover
# (its 6 screws are inside the hood), so one reed covers the whole front.
# Position: shell X +15 - between the power notch (X-10) and the router
# notches (X>31), invisible from outside, clear of the magnet-pad sweep.
REED_X = 15.0                     # shell X of the reed/magnet pair
MAGNET_D = 12.1                   # measured
MAGNET_POCKET_D = 12.05           # light press; PETG rim is 2mm - do not
                                  # tighten this without a coupon test
MAGNET_TH = 4.7                   # measured (owner, 18 Aug)
MAGNET_TH_MEASURED = True
MAGNET_POCKET_DEPTH = MAGNET_TH + 0.6   # 0.6 recess keeps the press seated
MAGNET_PAD_SQ = 16.0              # square pad on the cover's inner face
MAGNET_PAD_H = 6.5                # proud of the 2.5 face (holds the 4.7 disc)
MAGNET_CY = -31.0                 # cover-local Y of magnet centre (shell Z12)
MAGNET_POCKET_FLOOR = 3.7         # cover-local Z: leaves 1.2mm over the
                                  # outer face - nothing shows outside
REED_SLOT_W = 3.2                 # groove in the shelf top, reed along X
REED_SLOT_DEPTH = 2.0             # into the 3mm shelf (1mm left under it)
REED_SLOT_LEN = 18.0
REED_SLOT_Z0 = 57.0               # BottomLid-local Z (shell Y194..197.2)
REED_WIRE_HOLE_XY = (-15.0, 8.0)  # BottomLid-local; shell (+15, Z8), between
                                  # the router frame wall and the port row
REED_WIRE_HOLE_D = 4.0


# ---------------------------------------------------------------------------
# TOP-CAP tamper sensing: second magnet + reed (owner, 18 Aug)
# ---------------------------------------------------------------------------
# Same D12.1 x 4.7 magnet, press-fit into a pillar hanging from the cap roof
# at assembled (X-60, Y+125) - over the switch bay, in front of the tub's top
# rail, clear of the brain case (Y<=77), the cradle hooks (Z<=48) and the
# rail itself (Y134..137).  The pocket opens DOWNWARD, which prints as a
# clean vertical bore in the roof-down cap.  The reed lies in a groove cut
# into the rail's FRONT face; lifting the cap pulls the magnet straight up
# and off.  Wires join the existing tub-to-cap service loop (horn lead).
# The pillar is asymmetric in X: build_top_lid must mirror it exactly once,
# like the brain-case bosses.
CAP_MAGNET_X = -60.0              # assembled shell X
CAP_MAGNET_Y = 125.0
CAP_MAG_PILLAR_SQ = 16.0
CAP_MAG_PILLAR_BOT_Z = 75.0       # pillar hangs from the roof (Z117) to here
CAP_REED_GROOVE_DEPTH = 2.0       # into the 3mm rail front face (1mm left)
CAP_REED_GROOVE_W = 3.2           # groove height (reed lies along X)
CAP_REED_GROOVE_LEN = 18.0
CAP_REED_GROOVE_Z0 = 74.8

# ---------------------------------------------------------------------------
# INDOOR variant: 3.5" TFT + indicator LEDs in the cap roof (owner, 18 Aug)
# ---------------------------------------------------------------------------
# Two build variants exist and this ONE flag switches them:
#   True  = INDOOR: the Landzo 3.5" TFT shows through a roof window (module
#           sits in a shallow seat under the roof, glued/clamped from below,
#           wired to the brain PCB's J4), plus two 5mm LED holes (green/red,
#           push through + superglue).  The roof is NO LONGER top-rain-tight
#           - that is the owner's explicit trade for the indoor model.
#   False = WEATHERPROOF: sealed continuous roof, exactly as before; the
#           screen will later live inside the CurvedLid instead.
# Position (assembled): front-of-roof strip, clear of the brain case plan
# (Y<=77), its bosses, and the cap magnet pillar (X-68..-52 at Y125).
# ASYMMETRIC roof features -> build_top_lid mirrors X exactly once.
INDOOR_SCREEN = True
# Landzo "3.5 inch TFT Ultra HD (UNO/Mega256)" - typical UNO-shield numbers,
# NOT measured: PCB ~86.5 x 57, visible glass window 76 x 51 (active 73.4 x
# 49 + alignment margin).  MEASURE THE REAL BOARD before printing the cap.
SCREEN_MEASURED = False
SCREEN_PCB_W, SCREEN_PCB_H = 86.5, 57.0
SCREEN_VIS_W, SCREEN_VIS_H = 76.0, 51.0
SCREEN_SEAT_DEPTH = 1.0           # into the 3mm roof: module registers flat
SCREEN_CX, SCREEN_CY = 0.0, 108.0    # assembled shell X/Y of window centre
                                     # (centred in X, owner request 18 Aug)
LED_HOLE_D = 5.0                  # standard 5mm LED, push fit + superglue
LED_HOLES = ((78.0, 100.0), (78.0, 116.0))   # green, red (assembled X/Y)


def cap_reed_magnet_distance():
    """Centre-to-centre distance of the CAP pair with the cap seated, mm."""
    magnet_z = CAP_MAG_PILLAR_BOT_Z + 0.6 + MAGNET_TH / 2.0
    reed_y = 134.0 + 1.25                 # recessed into the rail front face
    reed_z = CAP_REED_GROOVE_Z0 + CAP_REED_GROOVE_W / 2.0
    return math.hypot(reed_y - CAP_MAGNET_Y, reed_z - magnet_z)


def reed_magnet_distance():
    """Centre-to-centre reed..magnet distance with the cover closed, mm."""
    magnet_y = 205.0 - (MAGNET_POCKET_FLOOR + MAGNET_TH / 2.0)   # shell Y
    magnet_z = 43.0 + MAGNET_CY
    reed_y = 137.0 + REED_SLOT_Z0 + REED_SLOT_W / 2.0            # slot centre
    reed_z = 3.0 - REED_SLOT_DEPTH + 1.25
    return math.hypot(magnet_y - reed_y, magnet_z - reed_z)

# ---------------------------------------------------------------------------
# THE PRINTER decides the outside dimensions
# ---------------------------------------------------------------------------
# Owner's machine is a Creality Ender 3 Plus: 300 x 300 x 340mm.  The tub is
# already 280 square, which leaves only 10mm of bed margin per side, so NO
# printed part may grow outside the 280 footprint.  This killed the previous
# mounting design: tabs projecting 24mm per side made the tub 328mm wide -
# unprintable on this machine, and nobody would have found out until the
# slicer refused it.  tools/fusion_offline_check.py now measures every
# printed body against this envelope on every run.
BED_X, BED_Y, BED_Z = 300.0, 300.0, 340.0
BED_MARGIN = 2.0                  # keep this much clear of the bed edge

# ---------------------------------------------------------------------------
# Wall mounting: TWO KEYHOLES, exactly like a router or an extension strip
# ---------------------------------------------------------------------------
# ORIENTATION - read before touching any mounting geometry.  The box mounts
# like a wall panel: the flat 280 x 280 FLOOR lies against the wall and the
# box stands 120mm out into the room, so the cap - with the 3.5" screen and
# the LEDs - faces the viewer.  In model coordinates:
#
#     model +Z  = straight OUT of the wall (NOT up)
#     model X/Y = the plane of the wall
#     model +Y  = DOWN the wall (the port face runs downward so cables hang)
#
# The owner asked for the simplest possible mount - "the one in extensions or
# even in the 951, where there is a hole and we just fit our box in".  So:
# drive two wall screws, leave the heads standing proud, offer the box up so
# the heads pass through the round ends, drop it 15mm, done.  No extra part
# to print, no bracket, nothing to align.
#
# The head sits in a POCKET recessed into the floor's outer face, so the box
# still lies flat against the wall - the same trick every consumer device
# uses.  That pocket is a cavity, not a bump, so the floor still prints
# face-down flat on the bed; the 3mm skin over it just bridges.
KEYHOLE_XY = ((-129.0, -125.0), (129.0, -125.0))
KEY_TRAVEL = 15.0                 # how far the box drops to lock
KEY_ENTRY_D = 12.0                # passes a screw head up to ~11mm
KEY_SLOT_W = 5.5                  # passes the shank, traps the head
KEY_POCKET_D = 16.0               # head pocket in the OUTER (wall) face
KEY_POCKET_DEPTH = 3.5            # so the box still lies flat on the wall
KEY_PAD_D = 22.0                  # local floor thickening around it all
KEY_PAD_H = 3.5                   # -> 6.5mm of floor, 3.0mm skin over the pocket
WALL_SCREW_SHANK = 4.5            # a normal 4.5 x 40 wall-plug screw
WALL_SCREW_HEAD_D = 8.5
MIK_UNDERSIDE_Z = 6.5
MIK_STANDOFF_XY = ((129.0, 122.5), (129.0, 5.5), (27.0, 122.5), (27.0, 5.5))
MIK_STANDOFF_D = 7.0


def mount_plane_z():
    """The face that touches the wall: the tub floor's underside."""
    return 0.0


def key_skin():
    """Material left over the head pocket, i.e. what carries the box."""
    return 3.0 + KEY_PAD_H - KEY_POCKET_DEPTH


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
# horn+sled is then held by TWO M4 wing
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
# NO CURB (owner, 18 Aug: "we don't need this cage for horns, just the bolt
# is enough").  The four-sided curb pocket the sled used to drop into is gone;
# the two M4 x 10 wing screws hold the bolted-up horn+sled by themselves.
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
    # clear for a straight-down driver.
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
    # Reed/magnet: the pocket rim must survive a press fit, the pad must
    # sweep clear over the recessed reed, the pocket floor must keep the
    # outer face closed, and the closed-cover distance must stay inside a
    # 12mm disc magnet's realistic reed pull-in range.
    if (MAGNET_PAD_SQ - MAGNET_POCKET_D) / 2.0 < 1.8:
        errors.append('magnet pocket rim under 1.8mm would split on press-fit')
    if MAGNET_POCKET_D < MAGNET_D - 0.15 or MAGNET_POCKET_D > MAGNET_D + 0.1:
        errors.append('magnet pocket is not a press fit on the measured 12.1 magnet')
    if MAGNET_POCKET_FLOOR - 2.5 < 1.0:
        errors.append('magnet pocket floor leaves under 1mm over the cover face')
    pad_bottom_z = 43.0 + MAGNET_CY - MAGNET_PAD_SQ / 2.0
    reed_top_z = 3.0 - REED_SLOT_DEPTH + 2.5
    if pad_bottom_z - reed_top_z < 0.5:
        errors.append('magnet pad would crash into the recessed reed on slide-by')
    if reed_magnet_distance() > 13.0:
        errors.append('reed..magnet distance {:.1f}mm - too far for reliable pull-in'
                      .format(reed_magnet_distance()))
    if abs(REED_X - (-10.0)) < MAGNET_PAD_SQ / 2.0 + 4.5 or \
            REED_X + MAGNET_PAD_SQ / 2.0 > 30.0:
        errors.append('reed/magnet X crowds the power notch (X-10) or the router notches')
    wx, wy = REED_WIRE_HOLE_XY
    if abs(wx) != REED_X:
        errors.append('reed wire hole is not behind the reed (BottomLid is mirrored)')
    if 2.5 + MAGNET_PAD_H - MAGNET_POCKET_FLOOR < MAGNET_TH + 0.4:
        errors.append('cover magnet pocket too shallow for the {:.1f}mm disc'
                      .format(MAGNET_TH))
    # Cap pair: the pillar must hang clear of the brain case, the cradle
    # hooks and the rail; the recessed reed must clear the descending pillar;
    # and the seated distance must stay in reed pull-in range.
    if CAP_MAGNET_Y - CAP_MAG_PILLAR_SQ / 2.0 < CASE_TO_CAP_Y + CASE_OUTER_H / 2.0 + 2.0:
        errors.append('cap magnet pillar runs into the hanging brain case')
    if CAP_MAGNET_Y + CAP_MAG_PILLAR_SQ / 2.0 > 133.0:
        errors.append('cap magnet pillar hits the tub top rail (Y134)')
    if CAP_MAG_PILLAR_BOT_Z < 50.0:
        errors.append('cap magnet pillar descends into the cradle hook zone')
    reed_proud = 2.5 - CAP_REED_GROOVE_DEPTH
    if 134.0 - reed_proud - (CAP_MAGNET_Y + CAP_MAG_PILLAR_SQ / 2.0) < 0.4:
        errors.append('descending cap pillar would strike the rail-mounted reed')
    if CAP_REED_GROOVE_DEPTH > 2.0:
        errors.append('cap reed groove leaves under 1mm of rail behind it')
    if cap_reed_magnet_distance() > 13.0:
        errors.append('cap reed..magnet distance {:.1f}mm - too far for pull-in'
                      .format(cap_reed_magnet_distance()))
    # Roof screen + LEDs (checked whether or not the indoor variant is on,
    # so a bad number cannot hide behind the flag): the window must keep a
    # bezel land inside the seat, the seat must clear the brain-case plan,
    # its bosses and the magnet pillar, and the LEDs must clear the seat.
    if SCREEN_VIS_W > SCREEN_PCB_W - 6.0 or SCREEN_VIS_H > SCREEN_PCB_H - 5.0:
        errors.append('screen window leaves too little bezel land in its seat')
    seat_x0 = SCREEN_CX - SCREEN_PCB_W / 2.0
    seat_x1 = SCREEN_CX + SCREEN_PCB_W / 2.0
    seat_y0 = SCREEN_CY - SCREEN_PCB_H / 2.0
    if seat_y0 < CASE_TO_CAP_Y + CASE_OUTER_H / 2.0 + 2.0:
        errors.append('screen seat overlaps the hanging brain case in plan')
    for bx_, by_ in CAP_BOSS_PATTERN:
        if seat_x0 - 8.0 < bx_ < seat_x1 + 8.0 and \
                seat_y0 - 8.0 < by_ < SCREEN_CY + SCREEN_PCB_H / 2.0 + 8.0:
            errors.append('screen seat crowds a brain-case cap boss')
    if seat_x0 < CAP_MAGNET_X + CAP_MAG_PILLAR_SQ / 2.0 + 2.0 and \
            SCREEN_CY + SCREEN_PCB_H / 2.0 > CAP_MAGNET_Y - CAP_MAG_PILLAR_SQ / 2.0:
        errors.append('screen seat crowds the cap magnet pillar')
    if SCREEN_CY + SCREEN_PCB_H / 2.0 > 138.0 or abs(SCREEN_CX) + SCREEN_PCB_W / 2.0 > 135.0:
        errors.append('screen seat runs off the roof / into the cap walls')
    for lx_, ly_ in LED_HOLES:
        if seat_x0 - LED_HOLE_D < lx_ < seat_x1 + LED_HOLE_D and \
                seat_y0 - LED_HOLE_D < ly_ < SCREEN_CY + SCREEN_PCB_H / 2.0 + LED_HOLE_D:
            errors.append('LED hole at ({:.0f},{:.0f}) breaks into the screen seat'
                          .format(lx_, ly_))
        if abs(lx_) > 135.0 or ly_ > 138.0:
            errors.append('LED hole at ({:.0f},{:.0f}) runs off the roof'.format(lx_, ly_))
    if max(COVER_TAB_X) + COVER_TAB_LEN / 2.0 > 125.0 - 8.0:
        errors.append('a cover locator tab runs off the BottomLid groove')
    # Cap screw rows: all four on each side wall, clear of each other, of the
    # snap detents, and inside the straight wall (corner radius starts |Y|133).
    rows = sorted(CAP_SIDE_SCREW_Y)
    if len(rows) != 2 or rows[1] - rows[0] < 100.0:
        errors.append('cap needs exactly two screw rows per side, well separated')
    if any(abs(y) > 133.0 - M3_SEAT_PAD_D / 2.0 for y in CAP_SIDE_SCREW_Y):
        errors.append('a cap screw row runs into the corner radius')
    # Keyhole mount.  The box may not grow past its 280 footprint (the Ender
    # 3 Plus bed is 300 square); the keyholes must pass a screw head but trap
    # it; the head pocket must leave real material over it; and both must
    # land on floor that is free of internal hardware.
    if 280.0 + 2.0 * BED_MARGIN > BED_X:
        errors.append('the tub footprint no longer fits the printer bed')
    if KEY_ENTRY_D <= WALL_SCREW_HEAD_D + 1.5:
        errors.append('keyhole entry will not pass a normal screw head')
    if KEY_SLOT_W <= WALL_SCREW_SHANK + 0.5:
        errors.append('keyhole slot will not pass the screw shank')
    if KEY_SLOT_W >= WALL_SCREW_HEAD_D - 2.0:
        errors.append('keyhole slot is so wide the head would pull through')
    if KEY_POCKET_D <= WALL_SCREW_HEAD_D + 2.0:
        errors.append('head pocket is too tight around the screw head')
    if KEY_POCKET_D >= KEY_PAD_D - 4.0:
        errors.append('head pocket leaves no ring of floor around it')
    if key_skin() < 2.5:
        errors.append('only {:.1f}mm of floor left over the head pocket'
                      .format(key_skin()))
    if KEY_POCKET_DEPTH < 3.0:
        errors.append('head pocket is too shallow to let the box lie flat')
    if KEY_TRAVEL < KEY_ENTRY_D / 2.0 + KEY_SLOT_W:
        errors.append('keyhole travel is too short to trap the head')
    if len(KEYHOLE_XY) != 2 or len(set(KEYHOLE_XY)) != 2:
        errors.append('there must be exactly two keyholes')
    if abs(KEYHOLE_XY[0][0] - KEYHOLE_XY[1][0]) < 150.0:
        errors.append('the two keyholes are too close to stop the box rotating')
    for hx, hy in KEYHOLE_XY:
        if hy + KEY_TRAVEL > 133.0 or hy < -133.0:
            errors.append('keyhole at Y{:.0f} has no room for its travel'.format(hy))
        if abs(hx) + KEY_PAD_D / 2.0 > 140.0:
            errors.append('keyhole pad at X{:.0f} breaks the outer wall'.format(hx))
        if 3.0 + KEY_PAD_H > MIK_UNDERSIDE_Z - 0.5 and hy > -20.0:
            errors.append('keyhole pad at Y{:.0f} would foul the MikroTik'.format(hy))
        if abs(hx) <= 120.0 and -133.5 <= hy <= -86.5:
            errors.append('keyhole at ({:.0f},{:.0f}) lands under the extension strip'
                          .format(hx, hy))
        for sx, sy in MIK_STANDOFF_XY:
            if math.hypot(hx - sx, hy - sy) < (KEY_PAD_D + MIK_STANDOFF_D) / 2.0 + 1.0:
                errors.append('keyhole pad at ({:.0f},{:.0f}) hits a router standoff'
                              .format(hx, hy))
    return errors


_errors = validate()
if _errors:
    raise ValueError('Invalid FreeISP shared interface: {}'.format(
        '; '.join(_errors)))
