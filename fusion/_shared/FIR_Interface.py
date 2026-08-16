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

INTERFACE_VERSION = '2026-08-16.2'

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
# The case is installed 10 mm toward +Y.  Its symmetric local holes at
# Y=-40/+40 therefore land on the cap bosses at Y=-30/+50.
CASE_TO_CAP_Y = 10.0
CASE_MOUNT = (
    (-58.5, -40.0),
    (58.5, -40.0),
    (-58.5, 40.0),
    (58.5, 40.0),
)
CAP_BOSS_PATTERN = tuple(
    (x, y + CASE_TO_CAP_Y) for x, y in CASE_MOUNT
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
# External alarm horn on the large top cap
# ---------------------------------------------------------------------------
# All values are ASSEMBLED shell coordinates (origin at the footprint centre,
# +Y front, +Z up).  FIR_Shell prints the cap roof-down and physically flips it
# left/right on assembly, so it mirrors HORN_CX itself -- never mirror it twice.
HORN_CX, HORN_CY = -96.0, 28.0
HORN_FLANGE_D = 69.0
HORN_BODY_D, HORN_BODY_H = 104.0, 102.0
HORN_HOLE_D = 6.0                 # measured holes in the horn's own flange
HORN_BASE_C2C, HORN_SIDE_C2C = 38.5, 50.0
# Through-bolted, never self-tapped: a 104mm horn is far too heavy to hang off
# a 3mm printed roof.  Each bolt gets an internal load-spreading pad that is
# embedded into the roof so it prints as one fused solid.
HORN_BOLT_CLEAR_D = 6.5
HORN_PAD_D, HORN_PAD_H, HORN_PAD_EMBED = 14.0, 3.5, 0.5
# Wire entry: a PG7 gland (3-6.5mm cable) sitting under the 104mm body but
# outside the 69mm flange, so the horn shades it and the flange cannot cover it.
HORN_WIRE_D = 12.5
# Radius is measured to the gland CENTRE, but what matters is its edges: the
# whole hole has to clear the flange rim and still sit under the body rim.
HORN_WIRE_R = 43.0
HORN_WIRE_PAD_D, HORN_WIRE_PAD_H = 24.0, 2.0


def horn_mount_points():
    """Return the three horn bolt centres in assembled shell coordinates.

    The flange centre is the triangle circumcentre of the measured isosceles
    pattern.  Its single apex points outboard (-X), which keeps both inboard
    bolts, their washers and their locknuts clear of the hanging brain case.
    """
    half_base = HORN_BASE_C2C / 2.0
    altitude = math.sqrt(HORN_SIDE_C2C ** 2 - half_base ** 2)
    base_x = (altitude ** 2 - half_base ** 2) / (2.0 * altitude)
    apex_x = altitude - base_x
    return (
        (HORN_CX - apex_x, HORN_CY),
        (HORN_CX + base_x, HORN_CY - half_base),
        (HORN_CX + base_x, HORN_CY + half_base),
    )


def horn_wire_point():
    """Return the horn cable-gland centre in assembled shell coordinates.

    It is offset toward the box back so the wire drops into free air beside the
    brain case rather than onto its roof.
    """
    return (HORN_CX, HORN_CY - HORN_WIRE_R)


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
    expected_cap_pattern = tuple((x, y + CASE_TO_CAP_Y)
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
    # The isosceles horn triangle must actually close, and its bolt circle has
    # to sit inside the horn's own mounting flange.
    if HORN_SIDE_C2C <= HORN_BASE_C2C / 2.0:
        errors.append('horn triangle sides are too short to close on the measured base')
    bolt_radius = max(math.hypot(x - HORN_CX, y - HORN_CY)
                      for x, y in horn_mount_points())
    if bolt_radius + HORN_HOLE_D / 2.0 > HORN_FLANGE_D / 2.0:
        errors.append('horn bolt circle does not fit inside the measured 69mm flange')
    if HORN_PAD_D <= HORN_BOLT_CLEAR_D or HORN_BOLT_CLEAR_D < HORN_HOLE_D:
        errors.append('horn pad/bolt clearance diameters are inconsistent')
    if HORN_WIRE_R - HORN_WIRE_D / 2.0 <= HORN_FLANGE_D / 2.0:
        errors.append('horn wire gland overlaps the 69mm flange and would be blocked by it')
    if HORN_WIRE_R + HORN_WIRE_D / 2.0 >= HORN_BODY_D / 2.0:
        errors.append('horn wire gland reaches past the 104mm body and would be left exposed')
    return errors


_errors = validate()
if _errors:
    raise ValueError('Invalid FreeISP shared interface: {}'.format(
        '; '.join(_errors)))
