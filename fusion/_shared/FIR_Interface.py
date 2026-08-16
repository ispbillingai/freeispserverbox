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

INTERFACE_VERSION = '2026-08-16.3'

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
HORN_CX = -73.0                   # body centre; -124..-22 clears the wall bosses
HORN_MOUTH_Y = 79.5               # mouth face, 2 mm behind the switch cradle
HORN_FOOT_D = 69.0                # circular bracket foot, measured
HORN_HOLE_D = 6.0                 # measured holes in that foot
HORN_BASE_C2C, HORN_SIDE_C2C = 38.5, 50.0
# NOT MEASURED: how far back the foot's centre sits from the mouth face.  The
# three floor pads move with this one number, so it is worth a tape measure.
HORN_FOOT_FROM_MOUTH = 99.0
HORN_FOOT_MEASURED = False
# Floor mounting: three pads raise the foot clear of the floor fillets and give
# an M4 self-tapper 8 mm of material without breaking through the 3 mm floor.
HORN_PAD_D, HORN_PAD_H = 14.0, 5.0
HORN_PILOT_D, HORN_PILOT_DEPTH = 3.4, 6.0
# Sound exit: the mouth stares at the front panel, so both front parts carry a
# matching slotted window in the blank land above the switch.
HORN_GRILLE_CX = HORN_CX
HORN_GRILLE_W = 80.0
HORN_GRILLE_Z0, HORN_GRILLE_Z1 = 34.0, 66.0   # clear of the switch and the Z72 bolts
HORN_GRILLE_SLOTS = 5
HORN_GRILLE_SLOT_H = 4.0


def horn_body():
    """Return the horn's assembled envelope (x0, x1, y0, y1, z0, z1)."""
    z0 = 3.0 + HORN_PAD_H                      # floor top + mounting pads
    return (HORN_CX - HORN_W / 2.0, HORN_CX + HORN_W / 2.0,
            HORN_MOUTH_Y - HORN_L, HORN_MOUTH_Y,
            z0, z0 + HORN_H)


def horn_foot_centre():
    """Centre of the 69 mm bracket foot on the tub floor."""
    return (HORN_CX, HORN_MOUTH_Y - HORN_FOOT_FROM_MOUTH)


def horn_mount_points():
    """The three floor-pad centres, in assembled shell coordinates.

    The foot centre is the circumcentre of the measured isosceles triangle.
    Its single apex points toward the back of the box, so the two base bolts
    stay under the horn where a driver can still reach them.
    """
    cx, cy = horn_foot_centre()
    half_base = HORN_BASE_C2C / 2.0
    altitude = math.sqrt(HORN_SIDE_C2C ** 2 - half_base ** 2)
    base_y = (altitude ** 2 - half_base ** 2) / (2.0 * altitude)
    apex_y = altitude - base_y
    return (
        (cx, cy - apex_y),
        (cx - half_base, cy + base_y),
        (cx + half_base, cy + base_y),
    )


def horn_grille_slots():
    """Slot rectangles (z0, z1) for the front sound window, bottom-up."""
    span = HORN_GRILLE_Z1 - HORN_GRILLE_Z0
    gaps = HORN_GRILLE_SLOTS - 1
    rib = (span - HORN_GRILLE_SLOTS * HORN_GRILLE_SLOT_H) / gaps if gaps else 0.0
    out = []
    z = HORN_GRILLE_Z0
    for _ in range(HORN_GRILLE_SLOTS):
        out.append((z, z + HORN_GRILLE_SLOT_H))
        z += HORN_GRILLE_SLOT_H + rib
    return out


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
    slots = horn_grille_slots()
    if slots and slots[-1][1] > HORN_GRILLE_Z1 + 1e-9:
        errors.append('horn grille slots overrun their window')
    return errors


_errors = validate()
if _errors:
    raise ValueError('Invalid FreeISP shared interface: {}'.format(
        '; '.join(_errors)))
