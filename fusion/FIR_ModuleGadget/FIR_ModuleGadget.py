# FIR_ModuleGadget.py - Autodesk Fusion 360 script
# The finished BRAIN CASE.  The 125 x 125 electronics tray (FIR_ModulePlate)
# carries the wire-in power modules and cell; this case closes around that tray
# and holds the 115 x 115 brain PCB above it.  This is the finished product
# shell: a clean, future-facing control deck with concealed mounting.

import importlib.util
import os
import sys

import adsk.core, adsk.fusion, adsk.cam, traceback


def _load_shared_interface():
    """Load the one mechanical-interface contract in workspace or Fusion."""
    script_file = globals().get('__file__', '')
    script_dir = (os.path.dirname(os.path.abspath(script_file))
                  if script_file else os.getcwd())
    candidates = []
    override = os.environ.get('FIR_INTERFACE_PATH')
    if override:
        candidates.append(override if override.lower().endswith('.py')
                          else os.path.join(override, 'FIR_Interface.py'))
    workspace_source = globals().get('_workspace_source')
    if workspace_source:
        candidates.append(os.path.join(
            os.path.dirname(os.path.abspath(workspace_source)), '..',
            '_shared', 'FIR_Interface.py'))
    candidates.extend((
        os.path.join(script_dir, 'FIR_Interface.py'),
        os.path.join(script_dir, '..', '_shared', 'FIR_Interface.py'),
    ))

    seen = set()
    for candidate in candidates:
        path = os.path.realpath(os.path.abspath(candidate))
        if path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        # Fusion can retain modules between Runs.  The mechanical contract is
        # intentionally reloaded so a revised tray fit cannot be hidden by a
        # stale in-memory FIR_Interface.py.
        sys.modules.pop('_freeisp_shared_interface', None)
        spec = importlib.util.spec_from_file_location(
            '_freeisp_shared_interface', path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules['_freeisp_shared_interface'] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError(
        'FIR_Interface.py not found. Deploy fusion/_shared beside the '
        'Fusion script folders, or set FIR_INTERFACE_PATH.')


INTERFACE = _load_shared_interface()

# ---------------- BODY ----------------
# The 129 mm internal pocket is intentionally matched to the tray with a
# 0.35 mm per-side FDM allowance: a snug hand-push fit, not the old loose
# 2 mm gap that let the tray rattle on the ledge.
# The brain PCB is COMPONENT-SIDE DOWN.  Its populated/silkscreen face sits
# 52 mm above the ModulePlate top face; the bare solder side faces the roof.
# The roof therefore needs only a short 10 mm fastening-post zone, not the
# former 25 mm ESP32-clearance volume.
# The outer envelope is shared: FIR_Shell needs the same numbers to know which
# tub features would rise into this case where it hangs under the cap.
W, H, BODY_Z = (INTERFACE.CASE_OUTER_W, INTERFACE.CASE_OUTER_H,
                INTERFACE.CASE_BODY_Z)
WALL, FACE_TH = 2.5, 3.0
CORNER_R, TOP_CHAMFER = 12.0, 2.0  # soft product corners + clean outer-edge chamfer
GROOVE_Z = []                                          # step-lines removed (were too busy)
FACE_TOP = BODY_Z
CAV_TOP = BODY_Z - FACE_TH
IN_W, IN_H = W - 2 * WALL, H - 2 * WALL

# ---------------- shared FIR_ModulePlate interface ----------------
# These values are loaded from fusion/_shared/FIR_Interface.py.  The tray
# slides in from the open bottom, stops on the ledge, and is fixed from below
# with four M3 self-tappers.  Each tray boss has a broad 11mm foot plus a
# 12mm-wide rib embedded into the case wall; it is not a thin free-standing
# post.
TRAY_W, TRAY_H, TRAY_TH = INTERFACE.TRAY_W, INTERFACE.TRAY_H, INTERFACE.TRAY_TH
TRAY_CORNER_R = INTERFACE.TRAY_CORNER_R
TRAY_POCKET_W, TRAY_POCKET_H = INTERFACE.TRAY_POCKET_W, INTERFACE.TRAY_POCKET_H
TRAY_POCKET_CORNER_R = INTERFACE.TRAY_POCKET_CORNER_R
TRAY_FIT_CLEAR_PER_SIDE = INTERFACE.TRAY_FIT_CLEAR_PER_SIDE
TRAY_MOUNT = INTERFACE.TRAY_MOUNT
TRAY_BOSS_D, TRAY_BOSS_PILOT, PLATE_BOSS_H = 9.0, 2.6, 10.0
TRAY_BOSS_FOOT_D, TRAY_BOSS_FOOT_H, TRAY_GUSSET_W = 11.0, 2.5, 12.0
TRAY_ENTRY_D, TRAY_ENTRY_H = 4.6, 1.5  # visible screw lead-in; threaded pilot continues above it
# The ledge is one continuous rounded ring.  It embeds into the cavity wall
# by 0.5mm, yet its inner profile is the tray outline inset by 1mm.  This
# gives every tray edge and rounded corner a complete support line without
# creating the old square-ring exterior corner tabs.
LEDGE_H, PLATE_SEAT_Z = 2.0, TRAY_TH
LEDGE_WALL_EMBED, LEDGE_TRAY_OVERLAP = 0.5, 1.0
LEDGE_OUT_W, LEDGE_OUT_H = (IN_W + 2.0 * LEDGE_WALL_EMBED,
                            IN_H + 2.0 * LEDGE_WALL_EMBED)
LEDGE_OUT_R = CORNER_R - WALL + LEDGE_WALL_EMBED
LEDGE_IN_W, LEDGE_IN_H = (TRAY_W - 2.0 * LEDGE_TRAY_OVERLAP,
                          TRAY_H - 2.0 * LEDGE_TRAY_OVERLAP)
LEDGE_IN_R = TRAY_CORNER_R - LEDGE_TRAY_OVERLAP

# ---------------- brain PCB -> small case cover ----------------
# The PCB belongs to this small case, not to the big outer shell.  Its
# component/silkscreen face points DOWN toward the power tray.  The bare solder
# face points UP toward the roof and has only <= 1 mm clipped solder tails.
# Nothing about the PCB outline, thickness, holes, or connector positions is
# changed here; this case is built around the existing board.
PCB_W, PCB_H, PCB_TH = INTERFACE.PCB_W, INTERFACE.PCB_H, INTERFACE.PCB_TH
PCB_HOLE_HALF = INTERFACE.PCB_HOLE_HALF       # rev-H: 106 mm M3-hole pitch
PCB_COMPONENT_FACE_Z = 55.0                  # populated downward-facing PCB face
PCB_TOP_Z = PCB_COMPONENT_FACE_Z + PCB_TH     # bare solder face = 56.6 mm
PCB_TO_PLATE_TARGET = 52.0
PCB_TO_PLATE_MIN, PCB_TO_PLATE_MAX = 50.0, 55.0
# These four short posts span 10 mm from the bare solder face to the roof.
# Their M3x10 screws enter from the component side through the existing PCB
# holes.  Each post uses a 9 mm core (3.2 mm plastic around the 2.6 mm pilot),
# a 13 mm roof collar, and two 3 mm wall ribs.  The collar/ribs deliberately
# embed 0.5 mm into the roof, leaving a continuous 2.5 mm exterior roof skin.
PCB_BOSS_D, PCB_PILOT = 9.0, 2.6
PCB_BOSS_H = CAV_TOP - PCB_TOP_Z
PCB_BOSS_ROOF_COLLAR_D, PCB_BOSS_ROOF_COLLAR_H = 13.0, 3.0
# A face-touch is not a dependable printed/Fusion structural join.  The roof
# collar and its two wall ribs therefore continue 0.5mm into the 3mm roof;
# this leaves a 2.5mm exterior roof skin and no outside protrusion.
PCB_BOSS_ROOF_EMBED = 0.5
PCB_BOSS_RIB_T, PCB_BOSS_RIB_CLEAR = 3.0, 2.0
PCB_BOSS_RIB_Z0 = PCB_TOP_Z + PCB_BOSS_RIB_CLEAR
PCB_BOSS_RIB_H = CAV_TOP + PCB_BOSS_ROOF_EMBED - PCB_BOSS_RIB_Z0
PCB_BOSS_RIB_WALL_EMBED = 1.0
PCB_SOCKET_H, PCB_DEVKIT_H = 8.5, 13.0
PCB_COMPONENT_H = PCB_SOCKET_H + PCB_DEVKIT_H # PCB face -> lowest ESP32 point
PCB_SOLDER_TAIL_MAX = 1.0
# Four PCB screws enter from the COMPONENT side below the board.  An M3x10
# screw crosses the 1.6 mm PCB and has 8.4 mm thread engagement in the 10 mm
# roof post.  Its 2.6 mm pilot ends 1.0 mm beyond the screw tip and still
# leaves 0.6 mm of solid post before the roof underside.
PCB_SCREW_LEN = 10.0
PCB_THREAD_ENGAGEMENT = PCB_SCREW_LEN - PCB_TH
PCB_SCREW_TIP_Z = PCB_COMPONENT_FACE_Z + PCB_SCREW_LEN
PCB_PILOT_TIP_CLEAR = 1.0
PCB_PILOT_Z0 = PCB_TOP_Z
PCB_PILOT_H = PCB_SCREW_TIP_Z + PCB_PILOT_TIP_CLEAR - PCB_PILOT_Z0

# ---------------- fastening systems (do not interchange) ----------------
# 1) TRAY: four M3 self-tappers come from below through FIR_ModulePlate and
#    thread into the wall-embedded tray bosses.  They hold the lower power tray.
# 2) PCB: four M3 x 10 board screws come from the PCB component side and
#    thread 8.4 mm into the short reinforced roof posts. They hold only the
#    brain PCB.
# 3) CASE -> CAP: four low-profile M3x12 screws start inside the EMPTY brain
#    case, pass upward through roof clearance holes, and thread into FIR_Shell
#    top-cap bosses.  They hold the complete brain case to the large top shell.

# ---------------- small case -> existing large TOP CAP --------------------
# The top cap has four reinforced 9mm M3 self-tap bosses at X=+/-58.5 and
# Y=-30/+50 (see FIR_Shell.build_top_lid).  The brain case hangs from the
# BOTTOMS of those bosses, not flush against the cap roof.  The shared
# contract owns both the local case holes and their +Y installation offset,
# then derives the cap-boss pattern from them.  All four screws are therefore
# well away from the case corners.  Low-profile M3x12 self-tapping screws go
# UP from inside this empty case: 3mm through this roof + 9mm into cap pilots.
CASE_TO_CAP_Y = INTERFACE.CASE_TO_CAP_Y
CAP_BOSS_PATTERN = INTERFACE.CAP_BOSS_PATTERN
CASE_MOUNT = INTERFACE.CASE_MOUNT
CASE_MOUNT_CLEAR = 3.4
CASE_HEAD_CB_D, CASE_HEAD_CB_H = 6.4, 2.25
CASE_MOUNT_PAD_D, CASE_MOUNT_PAD_H, CASE_MOUNT_PAD_EMBED = 9.5, 1.5, 0.5
# Start both cuts just below the inner pad face.  The earlier cut started
# 0.5mm too high and left a solid cap across the real case-to-cap hole.
# The counterbore still leaves 0.75mm of the external roof skin intact.
CASE_MOUNT_CUT_Z = CAV_TOP - CASE_MOUNT_PAD_H - 0.10
CASE_HEAD_CB_CUT_H = CASE_MOUNT_PAD_H + CASE_HEAD_CB_H + 0.10
CASE_MOUNT_CLEAR_CUT_H = CASE_MOUNT_PAD_H + FACE_TH + 0.20
SHOW_TRAY = False    # True = transparent case plus tray/PCB clearance models
VERSION = ('v23: snug 128.3mm ModulePlate push-fit (0.35mm/side) + component-side-down PCB at Z55 + '
           'short 10mm roof posts + M3x10 PCB screws + mid-gap J4/J5 wire exit + continuous rounded tray ledge + '
           'real case-to-cap holes open through embedded roof pads / interface {}'
           .format(INTERFACE.INTERFACE_VERSION))

# J4/TFT spans PCB-relative Y -45.5..-27.4 and J5/RC522 spans -21.5..-3.7.
# One slim +X-side slot covers the J4/J5 wire run.  The user confirmed that
# only individual Dupont wires pass here, so the opening is 50 x 5 mm--not a
# large connector bay.  It is deliberately centred in the 52mm gap between
# the ModulePlate top and the downward PCB component face.  This lets the
# J4/J5 wires descend first, then leave sideways without a sharp bend at PCB
# height.  It remains completely clear: no LED holes, lettering, divider or
# decorative lip can catch the wires as they leave the case.
JUMPER_Y, JUMPER_W = -26.0, 50.0
JUMPER_H = 5.0
JUMPER_CENTER_Z = (PLATE_SEAT_Z + PCB_COMPONENT_FACE_Z) / 2.0
JUMPER_Z0 = JUMPER_CENTER_Z - JUMPER_H / 2.0
J4_J5_Y_MIN, J4_J5_Y_MAX = -45.5, -3.7

# Airflow is an intentional "signal pulse" array instead of a generic row of
# holes.  Each narrow vertical slot stays support-free and the taller central
# bars make the side look engineered even before the electronics are fitted.
VENT_W = 2.4
VENTS = [(-24, 20, 13), (-18, 18, 17), (-12, 16, 21), (-6, 15, 23),
         (0, 14, 25), (6, 15, 23), (12, 16, 21), (18, 18, 17), (24, 20, 13)]

CM = 0.1
def mm(v):
    return v * CM

NEW  = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation
SKIPPED = []


def validate():
    """Arithmetic checks for the tray, PCB and outer-case mounting stack."""
    bad = []
    tray_clear_x = IN_W - TRAY_W
    tray_clear_y = IN_H - TRAY_H
    tray_clear_per_side_x = tray_clear_x / 2.0
    tray_clear_per_side_y = tray_clear_y / 2.0
    # This is the specified face-to-face clearance: ModulePlate flat top to
    # the PCB's populated, downward-facing component face.  It deliberately
    # does not measure from a boss, screw head, ledge, or the bare solder face.
    plate_to_pcb_component = PCB_COMPONENT_FACE_Z - PLATE_SEAT_Z
    if not PCB_TO_PLATE_MIN <= plate_to_pcb_component <= PCB_TO_PLATE_MAX:
        bad.append('plate-top to PCB component-face clearance {:.1f}mm is outside {:.1f}..{:.1f}mm'
                   .format(plate_to_pcb_component,
                           PCB_TO_PLATE_MIN, PCB_TO_PLATE_MAX))
    if abs(IN_W - TRAY_POCKET_W) > 0.01 or \
            abs(IN_H - TRAY_POCKET_H) > 0.01 or \
            abs((CORNER_R - WALL) - TRAY_POCKET_CORNER_R) > 0.01:
        bad.append('case cavity no longer matches the shared ModulePlate pocket')
    if abs(tray_clear_per_side_x - TRAY_FIT_CLEAR_PER_SIDE) > 0.01 or \
            abs(tray_clear_per_side_y - TRAY_FIT_CLEAR_PER_SIDE) > 0.01:
        bad.append('ModulePlate does not have the specified snug push-fit clearance')
    if not 0.25 <= min(tray_clear_per_side_x, tray_clear_per_side_y) <= 0.50:
        bad.append('ModulePlate side clearance is outside the printable 0.25..0.50mm push-fit range')
    if LEDGE_IN_W >= TRAY_W or LEDGE_IN_H >= TRAY_H:
        bad.append('rounded tray ledge does not project under the tray edge')
    if min(LEDGE_TRAY_OVERLAP, (TRAY_W - LEDGE_IN_W) / 2.0,
           (TRAY_H - LEDGE_IN_H) / 2.0) < 0.75:
        bad.append('rounded tray ledge has under 0.75mm edge support')
    if LEDGE_IN_R <= 0.0:
        bad.append('rounded tray ledge inner corner radius is invalid')
    # The inner ledge opening follows the tray's rounded outline exactly,
    # inset by the support overlap.  The outer contour shares the cavity's
    # corner centres, embeds into that wall, and stays within the R12 exterior.
    tray_corner_c = TRAY_W / 2.0 - TRAY_CORNER_R
    ledge_inner_c = LEDGE_IN_W / 2.0 - LEDGE_IN_R
    if abs(tray_corner_c - ledge_inner_c) > 0.01:
        bad.append('rounded tray ledge does not follow the tray corner centres')
    cavity_corner_r = CORNER_R - WALL
    cavity_corner_c = IN_W / 2.0 - cavity_corner_r
    ledge_outer_c = LEDGE_OUT_W / 2.0 - LEDGE_OUT_R
    if abs(cavity_corner_c - ledge_outer_c) > 0.01:
        bad.append('rounded tray ledge does not follow the cavity corner centres')
    if LEDGE_OUT_R <= cavity_corner_r or LEDGE_OUT_R >= CORNER_R:
        bad.append('rounded tray ledge fails cavity embed / exterior clearance')
    if (TRAY_BOSS_D - TRAY_ENTRY_D) / 2.0 < 2.0:
        bad.append('tray-boss lead-in leaves under 2mm radial material')
    for x, y in TRAY_MOUNT:
        if abs(x) + TRAY_BOSS_FOOT_D / 2.0 > IN_W / 2.0 or \
                abs(y) + TRAY_BOSS_FOOT_D / 2.0 > IN_H / 2.0:
            bad.append('tray boss at ({:.1f}, {:.1f}) breaks into the cavity'.format(x, y))
    if PLATE_SEAT_Z + PLATE_BOSS_H >= PCB_TOP_Z - PCB_TH:
        bad.append('tray bosses reach the brain PCB')
    for x in (-PCB_HOLE_HALF, PCB_HOLE_HALF):
        for y in (-PCB_HOLE_HALF, PCB_HOLE_HALF):
            if abs(x) + PCB_BOSS_D / 2.0 > IN_W / 2.0 or \
                    abs(y) + PCB_BOSS_D / 2.0 > IN_H / 2.0:
                bad.append('brain PCB boss at ({:.1f}, {:.1f}) breaks into the cavity'.format(x, y))
            if abs(x) + PCB_BOSS_ROOF_COLLAR_D / 2.0 > IN_W / 2.0 or \
                    abs(y) + PCB_BOSS_ROOF_COLLAR_D / 2.0 > IN_H / 2.0:
                bad.append('brain PCB roof collar at ({:.1f}, {:.1f}) breaks into the cavity'
                           .format(x, y))
    if (PCB_BOSS_D - PCB_PILOT) / 2.0 < 3.0:
        bad.append('brain PCB boss leaves under 3mm radial material around its pilot')
    if not 9.5 <= PCB_BOSS_H <= 10.5:
        bad.append('PCB roof post is {:.1f}mm instead of the short ~10mm design'
                   .format(PCB_BOSS_H))
    if PCB_SCREW_LEN != 10.0:
        bad.append('short PCB roof posts require M3x10 board screws')
    if PCB_THREAD_ENGAGEMENT < 8.0:
        bad.append('M3 PCB screw has under 8mm thread engagement')
    if PCB_SCREW_TIP_Z + PCB_PILOT_TIP_CLEAR > PCB_PILOT_Z0 + PCB_PILOT_H:
        bad.append('M3 PCB pilot does not leave 1mm tip clearance')
    pilot_root_h = CAV_TOP - (PCB_PILOT_Z0 + PCB_PILOT_H)
    if pilot_root_h < 0.5:
        bad.append('M3 PCB pilot leaves under 0.5mm solid post root below the roof')
    if PCB_BOSS_ROOF_COLLAR_D < PCB_BOSS_D + 4.0 or PCB_BOSS_ROOF_COLLAR_H < 3.0:
        bad.append('brain PCB roof collar is too small to reinforce the short roof posts')
    if PCB_BOSS_ROOF_EMBED <= 0.0 or PCB_BOSS_ROOF_EMBED >= FACE_TH:
        bad.append('brain PCB roof support must embed inside the roof')
    roof_support_top = CAV_TOP + PCB_BOSS_ROOF_EMBED
    if not (CAV_TOP < roof_support_top < FACE_TOP):
        bad.append('brain PCB roof collar does not overlap the roof correctly')
    if FACE_TOP - roof_support_top < 2.5 - 0.01:
        bad.append('brain PCB roof support leaves under 2.5mm outer roof skin')
    if PCB_BOSS_RIB_Z0 <= PCB_TOP_Z or \
            PCB_BOSS_RIB_Z0 + PCB_BOSS_RIB_H <= CAV_TOP:
        bad.append('brain PCB ribs are not connected into the roof')
    if PCB_BOSS_RIB_Z0 + PCB_BOSS_RIB_H >= FACE_TOP:
        bad.append('brain PCB ribs break through the outer roof')
    if PCB_BOSS_RIB_WALL_EMBED <= 0.0 or PCB_BOSS_RIB_WALL_EMBED >= WALL:
        bad.append('brain PCB ribs are not correctly embedded in the case walls')
    # Real top-cap mount: four roof clearance holes must map onto the existing
    # cap boss pattern after the documented +Y installation offset.  They also
    # need a clear gap from the brain-PCB roof bosses and enough outer roof
    # material above the low-profile screw heads.
    mapped_mounts = sorted((round(x, 1), round(y + CASE_TO_CAP_Y, 1))
                           for x, y in CASE_MOUNT)
    if mapped_mounts != sorted(CAP_BOSS_PATTERN):
        bad.append('case roof-hole pattern does not match the existing top-cap bosses')
    if FACE_TH - CASE_HEAD_CB_H < 0.65:
        bad.append('roof counterbore leaves under 0.65mm outer skin')
    if CASE_MOUNT_PAD_EMBED <= 0.0:
        bad.append('case-mount pad must overlap the roof, not only touch it')
    if CASE_MOUNT_CUT_Z >= CAV_TOP - CASE_MOUNT_PAD_H:
        bad.append('case-mount cuts leave a cap across the inside pad face')
    counterbore_outer_skin = FACE_TOP - (CASE_MOUNT_CUT_Z + CASE_HEAD_CB_CUT_H)
    if counterbore_outer_skin < 0.65:
        bad.append('case-mount counterbore leaves under 0.65mm outer roof skin')
    for x, y in CASE_MOUNT:
        if abs(x) + CASE_HEAD_CB_D / 2.0 > W / 2.0 or \
                abs(y) + CASE_HEAD_CB_D / 2.0 > H / 2.0:
            bad.append('top-cap mount at ({:.1f}, {:.1f}) leaves the roof'.format(x, y))
        if H / 2.0 - abs(y) < 20.0:
            bad.append('top-cap mount at ({:.1f}, {:.1f}) is too close to a case corner'
                       .format(x, y))
        # Keep the load-spreading pad completely inside the rounded exterior.
        # This prevents any mount reinforcement from forming a corner tab.
        cx = W / 2.0 - CORNER_R
        cy = H / 2.0 - CORNER_R
        if abs(x) > cx and abs(y) > cy:
            corner_distance = ((abs(x) - cx) ** 2 + (abs(y) - cy) ** 2) ** 0.5
            if corner_distance + CASE_MOUNT_PAD_D / 2.0 > CORNER_R:
                bad.append('top-cap reinforcement pad at ({:.1f}, {:.1f}) leaves the rounded shell'
                           .format(x, y))
        for px in (-PCB_HOLE_HALF, PCB_HOLE_HALF):
            for py in (-PCB_HOLE_HALF, PCB_HOLE_HALF):
                gap = ((x - px) ** 2 + (y - py) ** 2) ** 0.5 - \
                    (CASE_MOUNT_PAD_D + PCB_BOSS_ROOF_COLLAR_D) / 2.0
                if gap < 1.5:
                    bad.append('top-cap mount at ({:.1f}, {:.1f}) is too close to a PCB roof collar'
                               .format(x, y))
    roof_solder_clearance = CAV_TOP - PCB_TOP_Z
    pcb_component_low_z = PCB_COMPONENT_FACE_Z - PCB_COMPONENT_H
    if roof_solder_clearance < PCB_SOLDER_TAIL_MAX + 1.0:
        bad.append('only {:.1f}mm above the bare PCB solder side'.format(roof_solder_clearance))
    if pcb_component_low_z <= PLATE_SEAT_Z:
        bad.append('downward PCB component envelope reaches the ModulePlate top face')
    jumper_lo, jumper_hi = JUMPER_Y - JUMPER_W / 2.0, JUMPER_Y + JUMPER_W / 2.0
    if jumper_lo > J4_J5_Y_MIN or jumper_hi < J4_J5_Y_MAX:
        bad.append('J4/J5 jumper opening does not cover both headers')
    # User-confirmed cable path: only flexible individual Dupont wires pass
    # through this 5mm slot.  It must stay in the middle of the plate-to-PCB
    # component gap so wires can drop vertically before turning outward.
    jumper_center = JUMPER_Z0 + JUMPER_H / 2.0
    expected_jumper_center = (PLATE_SEAT_Z + PCB_COMPONENT_FACE_Z) / 2.0
    if JUMPER_H < 5.0 or abs(jumper_center - expected_jumper_center) > 0.01:
        bad.append('J4/J5 Dupont-wire slot is not centred in the PCB-to-plate gap')
    if not (PLATE_SEAT_Z + PLATE_BOSS_H < JUMPER_Z0 and
            JUMPER_Z0 + JUMPER_H < pcb_component_low_z):
        bad.append('J4/J5 Dupont-wire slot does not leave a clear vertical wire descent')
    if JUMPER_Z0 + JUMPER_H > PCB_BOSS_RIB_Z0 - 1.0:
        bad.append('J4/J5 Dupont-wire slot is too close to the short roof-post ribs')
    return bad, ('tray push-fit clearance {:.2f} x {:.2f}mm per side; tray bosses end Z{:.1f}; '
                 'plate-top to PCB component face {:.1f}mm (target {:.1f}, allowed {:.1f}..{:.1f}); '
                 'PCB solder face Z{:.1f}; PCB fastening M3x{:.0f}, {:.1f}mm grip; reinforced posts: D{:.1f}, '
                 'H{:.1f}, collar D{:.1f}, ribs Z{:.1f}..{:.1f}; roof clearance above bare solder side {:.1f}mm; '
                 'J4/J5 side opening Y{:.1f}..{:.1f}, Z{:.1f}..{:.1f}, centred Z{:.1f}; '
                 'top-cap M3 holes map at +Y{:.1f}; fasteners: tray-from-below, '
                 'PCB-to-roof-posts, case-to-cap-upward'
                 .format(tray_clear_per_side_x, tray_clear_per_side_y,
                         PLATE_SEAT_Z + PLATE_BOSS_H,
                         plate_to_pcb_component, PCB_TO_PLATE_TARGET,
                         PCB_TO_PLATE_MIN, PCB_TO_PLATE_MAX,
                         PCB_TOP_Z, PCB_SCREW_LEN, PCB_THREAD_ENGAGEMENT, PCB_BOSS_D,
                         PCB_BOSS_H, PCB_BOSS_ROOF_COLLAR_D, PCB_BOSS_RIB_Z0,
                         PCB_BOSS_RIB_Z0 + PCB_BOSS_RIB_H, roof_solder_clearance,
                         jumper_lo, jumper_hi,
                         JUMPER_Z0, JUMPER_Z0 + JUMPER_H, jumper_center,
                         CASE_TO_CAP_Y))


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


def rounded_rect_volume(comp, body, cx, cy, w, h, r, z0, sz, op):
    """Add or cut a rounded rectangle using reliable box/circle primitives.

    The two crossing rectangles and four corner cylinders form one rounded
    profile without relying on a fragile sketch-arc loop.  ``body`` remains
    the only participant for both JOIN and CUT operations.
    """
    if r <= 0.0 or min(w, h) <= 2.0 * r:
        raise ValueError('invalid rounded rectangle: {} x {} R{}'.format(w, h, r))
    box(comp, cx, cy, z0, w - 2.0 * r, h, sz, op, [body])
    box(comp, cx, cy, z0, w, h - 2.0 * r, sz, op, [body])
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            cyl(comp, cx + sx * (w / 2.0 - r),
                cy + sy * (h / 2.0 - r), z0, 2.0 * r, sz, op, [body])


def frame_at(comp, body, cx, cy, ow, oh, t, z0, h, op):
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        L = sk.sketchCurves.sketchLines
        L.addCenterPointRectangle(adsk.core.Point3D.create(mm(cx), mm(cy), 0),
                                  adsk.core.Point3D.create(mm(cx + ow / 2), mm(cy + oh / 2), 0))
        L.addCenterPointRectangle(adsk.core.Point3D.create(mm(cx), mm(cy), 0),
                                  adsk.core.Point3D.create(mm(cx + ow / 2 - t), mm(cy + oh / 2 - t), 0))
        for p in sk.profiles:
            if p.profileLoops.count == 2:
                _ext(comp, p, z0, h, op, [body])
                return
    except Exception as e:
        SKIPPED.append('frame: {}'.format(e))


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
            fi.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
            comp.features.filletFeatures.add(fi)
    except Exception as e:
        SKIPPED.append('corner fillet: {}'.format(e))


def fillet_corners_at(comp, body, positions, r):
    # fillet only the vertical edges whose XY is near one of the given corner positions
    try:
        coll = adsk.core.ObjectCollection.create()
        for e in body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                v = g.startPoint.vectorTo(g.endPoint)
                v.normalize()
                if abs(v.z) > 0.99:
                    p = g.startPoint
                    for (px, py) in positions:
                        if abs(p.x - mm(px)) < mm(1.5) and abs(p.y - mm(py)) < mm(1.5):
                            coll.add(e)
                            break
        if coll.count:
            fin = comp.features.filletFeatures.createInput()
            fin.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
            comp.features.filletFeatures.add(fin)
    except Exception as e:
        SKIPPED.append('corner fillet r{}: {}'.format(r, e))


def _top_face(body):
    face, best = None, -1.0
    for f in body.faces:
        g = f.geometry
        if isinstance(g, adsk.core.Plane) and g.normal.z > 0.99:
            bb = f.boundingBox
            if abs((bb.minPoint.z + bb.maxPoint.z) / 2 - mm(FACE_TOP)) < mm(0.05) and f.area > best:
                best, face = f.area, f
    return face


def chamfer_top(comp, body, c):
    # simple chamfer on the top outer edge - robust, no corner-blend gaps
    try:
        face = _top_face(body)
        if not face:
            return
        coll = adsk.core.ObjectCollection.create()
        for loop in face.loops:
            if loop.isOuter:
                for e in loop.edges:
                    coll.add(e)
        if coll.count:
            cf = comp.features.chamferFeatures
            ci = cf.createInput2()
            ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                coll, adsk.core.ValueInput.createByReal(mm(c)), False)
            cf.add(ci)
    except Exception as e:
        SKIPPED.append('top chamfer: {}'.format(e))


def chamfer_mouths(comp, body, c):
    try:
        face = _top_face(body)
        if not face:
            return
        coll = adsk.core.ObjectCollection.create()
        for loop in face.loops:
            if not loop.isOuter:
                for e in loop.edges:
                    coll.add(e)
        if coll.count:
            cf = comp.features.chamferFeatures
            ci = cf.createInput2()
            ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                coll, adsk.core.ValueInput.createByReal(mm(c)), False)
            cf.add(ci)
    except Exception as e:
        SKIPPED.append('mouth chamfer: {}'.format(e))


def ring(comp, body, cx, cy, r_out, width, z_top, depth):
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        cc = sk.sketchCurves.sketchCircles
        cc.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(r_out))
        cc.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(r_out - width))
        for p in sk.profiles:
            if p.profileLoops.count == 2:
                _ext(comp, p, z_top - depth, depth + 0.5, CUT, [body])
                return
    except Exception as e:
        SKIPPED.append('wave ring: {}'.format(e))


def text(comp, body, s, cx, cy, h, depth, emboss=False):
    try:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sts = sk.sketchTexts
        ti = sts.createInput2(s, mm(h))
        w = mm(h) * max(1, len(s)) * 1.3       # generous box width so lines never wrap
        ti.setAsMultiLine(
            adsk.core.Point3D.create(mm(cx) - w / 2, mm(cy) - mm(h), 0),
            adsk.core.Point3D.create(mm(cx) + w / 2, mm(cy) + mm(h), 0),
            adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
            adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0)
        try:
            ti.fontName = 'Arial'
            ti.textStyle = adsk.fusion.TextStyles.TextStyleBold
        except Exception:
            pass
        st = sts.add(ti)
        op = JOIN if emboss else CUT
        z0 = FACE_TOP if emboss else FACE_TOP - depth
        sz = depth if emboss else depth + 0.5
        ff = comp.features.extrudeFeatures
        try:
            ei = ff.createInput(st, op)
        except Exception:
            pc = adsk.core.ObjectCollection.create()
            for p in sk.profiles:
                pc.add(p)
            ei = ff.createInput(pc, op)
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(z0)))
        ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(sz)))
        ei.participantBodies = [body]
        ff.add(ei)
    except Exception as e:
        SKIPPED.append('text "{}": {}'.format(s, e))


def pocket(comp, body, cx, cy, w, l, d):
    box(comp, cx, cy, FACE_TOP - d, w, l, d + 0.5, CUT, [body])


def polygon(comp, points, z0, sz, op, parts=None):
    """Extrude a closed XY polygon; used for the faceted tech details."""
    sk = comp.sketches.add(comp.xYConstructionPlane)
    lines = sk.sketchCurves.sketchLines
    for a, b in zip(points, points[1:] + points[:1]):
        lines.addByTwoPoints(adsk.core.Point3D.create(mm(a[0]), mm(a[1]), 0),
                             adsk.core.Point3D.create(mm(b[0]), mm(b[1]), 0))
    return _ext(comp, sk.profiles.item(0), z0, sz, op, parts)


def beveled_pocket(comp, body, cx, cy, w, h, bevel, depth):
    """A recessed octagonal bezel: visibly modern, yet fully printable."""
    x, y = w / 2.0, h / 2.0
    pts = [(cx - x + bevel, cy - y), (cx + x - bevel, cy - y),
           (cx + x, cy - y + bevel), (cx + x, cy + y - bevel),
           (cx + x - bevel, cy + y), (cx - x + bevel, cy + y),
           (cx - x, cy + y - bevel), (cx - x, cy - y + bevel)]
    polygon(comp, pts, FACE_TOP - depth, depth + 0.5, CUT, [body])


def pocket_c(comp, body, cx, cy, dia, d):
    cyl(comp, cx, cy, FACE_TOP - d, dia, d + 0.5, CUT, [body])


def thru(comp, body, cx, cy, w, l):
    box(comp, cx, cy, FACE_TOP - FACE_TH - 1, w, l, FACE_TH + 2, CUT, [body])


def thru_c(comp, body, cx, cy, dia):
    cyl(comp, cx, cy, FACE_TOP - FACE_TH - 1, dia, FACE_TH + 2, CUT, [body])


def side_text(comp, body, s, py, pz, h, depth):
    # engrave into the -X side wall. yZ plane: sketch-X = world Z, sketch-Y = world Y
    # (text runs vertically). py = Z-centre of the text run, pz = the line's Y position.
    try:
        sk = comp.sketches.add(comp.yZConstructionPlane)
        sts = sk.sketchTexts
        ti = sts.createInput2(s, mm(h))
        w = mm(h) * max(1, len(s)) * 0.62
        ti.setAsMultiLine(
            adsk.core.Point3D.create(mm(py) - w / 2, mm(pz) - mm(h), 0),
            adsk.core.Point3D.create(mm(py) + w / 2, mm(pz) + mm(h), 0),
            adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
            adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0)
        try:
            ti.fontName = 'Arial'
        except Exception:
            pass
        st = sts.add(ti)
        ff = comp.features.extrudeFeatures
        try:
            ei = ff.createInput(st, CUT)
        except Exception:
            pc = adsk.core.ObjectCollection.create()
            for p in sk.profiles:
                pc.add(p)
            ei = ff.createInput(pc, CUT)
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(-W / 2)))
        ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(depth)))
        ei.participantBodies = [body]
        ff.add(ei)
    except Exception as e:
        SKIPPED.append('side text "{}": {}'.format(s, e))


def side_panel(comp, body, cy, cz, sy, sz, depth):
    # recessed spec-plate rectangle on the -X wall (yZ plane: sketch-X=world Z, sketch-Y=world Y)
    try:
        sk = comp.sketches.add(comp.yZConstructionPlane)
        sk.sketchCurves.sketchLines.addCenterPointRectangle(
            adsk.core.Point3D.create(mm(cz), mm(cy), 0),
            adsk.core.Point3D.create(mm(cz + sz / 2), mm(cy + sy / 2), 0))
        ff = comp.features.extrudeFeatures
        ei = ff.createInput(sk.profiles.item(0), CUT)
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(-W / 2)))
        ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(depth)))
        ei.participantBodies = [body]
        ff.add(ei)
    except Exception as e:
        SKIPPED.append('side panel: {}'.format(e))


def build(comp):
    body = box(comp, 0, 0, 0, W, H, BODY_Z, NEW).bodies.item(0)
    body.name = 'FIR Brain Case'
    box(comp, 0, 0, -1, IN_W, IN_H, CAV_TOP + 1, CUT, [body])     # hollow, open bottom (sharp)
    # Round the CAVITY corners (R-WALL) then the OUTER corners (R) so the wall stays a
    # solid 2.5mm at the corners. THIS is what stops the cavity breaching the corner (the gap).
    inner = [(IN_W / 2, IN_H / 2), (-IN_W / 2, IN_H / 2), (IN_W / 2, -IN_H / 2), (-IN_W / 2, -IN_H / 2)]
    outer = [(W / 2, H / 2), (-W / 2, H / 2), (W / 2, -H / 2), (-W / 2, -H / 2)]
    fillet_corners_at(comp, body, inner, CORNER_R - WALL)
    fillet_corners_at(comp, body, outer, CORNER_R)
    chamfer_top(comp, body, TOP_CHAMFER)

    # Internal tray seating ledge: one complete rounded ring closes the four
    # former corner gaps.  Its outer contour is embedded 0.5mm into the
    # existing cavity wall; its inner opening follows the tray's R6 outline
    # inset by 1mm.  Therefore it has a continuous support line but stays
    # 2mm inside the smooth R12 external corner surface.
    rounded_rect_volume(comp, body, 0.0, 0.0,
                        LEDGE_OUT_W, LEDGE_OUT_H, LEDGE_OUT_R,
                        PLATE_SEAT_Z, LEDGE_H, JOIN)
    rounded_rect_volume(comp, body, 0.0, 0.0,
                        LEDGE_IN_W, LEDGE_IN_H, LEDGE_IN_R,
                        PLATE_SEAT_Z - 0.10, LEDGE_H + 0.20, CUT)

    # Tray screws come from below through FIR_ModulePlate.  These are robust,
    # wall-embedded mounts: a broad foot spreads the load, a 9mm boss keeps
    # 3.2mm of plastic around its 2.6mm pilot, and a 12mm-wide rib merges it
    # into the side wall.  Build all reinforcing material FIRST, then cut the
    # bolt entry LAST so the visible hole cannot be filled by a later join.
    for (x, y) in TRAY_MOUNT:
        cyl(comp, x, y, PLATE_SEAT_Z, TRAY_BOSS_FOOT_D, TRAY_BOSS_FOOT_H, JOIN, [body])
        cyl(comp, x, y, PLATE_SEAT_Z, TRAY_BOSS_D, PLATE_BOSS_H, JOIN, [body])
        if abs(x) > abs(y):
            sx = 1.0 if x > 0 else -1.0
            box(comp, sx * (IN_W / 2.0 - 1.0), y, PLATE_SEAT_Z,
                4.0, TRAY_GUSSET_W, PLATE_BOSS_H, JOIN, [body])
        else:
            sy = 1.0 if y > 0 else -1.0
            box(comp, x, sy * (IN_H / 2.0 - 1.0), PLATE_SEAT_Z,
                TRAY_GUSSET_W, 4.0, PLATE_BOSS_H, JOIN, [body])
        # Same final-cut sequence as the clearly visible brain-PCB bosses.
        # The 4.6mm mouth is visible from the open bottom; the 2.6mm pilot
        # continues upward for the M3 self-tapping threads.
        cyl(comp, x, y, PLATE_SEAT_Z - 1.0,
            TRAY_BOSS_PILOT, PLATE_BOSS_H + 1.0, CUT, [body])
        cyl(comp, x, y, PLATE_SEAT_Z - 0.05,
            TRAY_ENTRY_D, TRAY_ENTRY_H + 0.10, CUT, [body])

    # The brain PCB is component-side DOWN at Z55, with its bare solder face
    # at Z56.6.  Four short reinforced roof posts match its 106mm M3 pattern.
    # The 9mm cores, 13mm roof collars, and two wall-embedded ribs per post
    # resist sideways knocks without altering the outside surfaces. The collar
    # and ribs overlap 0.5mm into the roof for a true structural join; they do
    # not merely face-touch it. Ribs begin above the bare solder face so the
    # PCB stays completely flat. Each M3x10 pilot is blind below the roof,
    # leaving a solid root and the required 2.5mm external roof skin.
    # This system holds the board only, not the tray or the large outer shell.
    for x in (-PCB_HOLE_HALF, PCB_HOLE_HALF):
        for y in (-PCB_HOLE_HALF, PCB_HOLE_HALF):
            cyl(comp, x, y, PCB_TOP_Z, PCB_BOSS_D, PCB_BOSS_H, JOIN, [body])
            cyl(comp, x, y, CAV_TOP - PCB_BOSS_ROOF_COLLAR_H,
                PCB_BOSS_ROOF_COLLAR_D,
                PCB_BOSS_ROOF_COLLAR_H + PCB_BOSS_ROOF_EMBED, JOIN, [body])
            sx = 1.0 if x > 0 else -1.0
            sy = 1.0 if y > 0 else -1.0
            rib_x_len = IN_W / 2.0 - abs(x) + PCB_BOSS_RIB_WALL_EMBED
            rib_y_len = IN_H / 2.0 - abs(y) + PCB_BOSS_RIB_WALL_EMBED
            box(comp, sx * (abs(x) + rib_x_len / 2.0), y, PCB_BOSS_RIB_Z0,
                rib_x_len, PCB_BOSS_RIB_T, PCB_BOSS_RIB_H, JOIN, [body])
            box(comp, x, sy * (abs(y) + rib_y_len / 2.0), PCB_BOSS_RIB_Z0,
                PCB_BOSS_RIB_T, rib_y_len, PCB_BOSS_RIB_H, JOIN, [body])
            cyl(comp, x, y, PCB_PILOT_Z0, PCB_PILOT, PCB_PILOT_H, CUT, [body])

    # Real attachment to FIR_Shell's existing top-cap bosses.  These are M3
    # CLEARANCE holes, not plastic threads.  Each has a 9.5mm internal roof
    # pad for load spreading, fully contained inside the rounded outer shell.
    # The pad overlaps the roof by 0.5mm for a real Fusion join; BOTH cuts
    # begin below its inner face so the M3 opening is visibly and physically
    # open from the cavity all the way to the outside.  A low-profile M3x12
    # screw goes upward into the cap's 2.6mm pilot; its head is recessed inside.
    for x, y in CASE_MOUNT:
        cyl(comp, x, y, CAV_TOP - CASE_MOUNT_PAD_H,
            CASE_MOUNT_PAD_D, CASE_MOUNT_PAD_H + CASE_MOUNT_PAD_EMBED, JOIN, [body])
        cyl(comp, x, y, CASE_MOUNT_CUT_Z,
            CASE_HEAD_CB_D, CASE_HEAD_CB_CUT_H, CUT, [body])
        cyl(comp, x, y, CASE_MOUNT_CUT_Z,
            CASE_MOUNT_CLEAR, CASE_MOUNT_CLEAR_CUT_H, CUT, [body])

    # Cross-flow ventilation: a deliberate signal-pulse pattern on the two
    # Y-side walls, with all slots vertical and support-free.
    for cy in (-H / 2, H / 2):
        for x, z0, length in VENTS:
            box(comp, x, cy, z0, VENT_W, WALL * 3, length, CUT, [body])

    # J4/J5 are at the +X edge of the brain PCB.  This is only the user-sized
    # 50 x 5mm functional Dupont-wire exit: no decorative border or recess.
    box(comp, W / 2, JUMPER_Y, JUMPER_Z0, WALL * 3, JUMPER_W, JUMPER_H,
        CUT, [body])

    # ---- FLAT PRINT ROOF ----------------------------------------------
    # The complete top face intentionally remains unbroken and level: no
    # display window, panel recess, logo, RFID ring, rail or engraving.
    # This creates the cleanest possible top-layer finish when printed.

    return body


def build_preview_parts(comp):
    """Non-printing envelopes used only with SHOW_TRAY to inspect the stack."""
    tray = box(comp, 0, 0, 0, TRAY_W, TRAY_H, TRAY_TH, NEW).bodies.item(0)
    tray.name = 'CHECK: electronics tray {:.1f}x{:.1f} snug push-fit'.format(TRAY_W, TRAY_H)
    parts = [
        ('cell',        14.5, 52.0, 14.5, -35.0,   0.0, 3.0),
        ('LM2596 buck', 43.2, 21.4, 14.0,  20.0,  38.0, 8.0),
        ('5V boost',    17.0, 36.0, 14.0,   5.0, -26.0, 8.0),
        ('TP4056',      28.2, 17.0,  6.0,  40.0, -25.0, 8.0),
        ('relay',       34.0, 26.0, 19.0,  20.0,  11.0, 8.0),
    ]
    for name, w, h, z, x, y, z0 in parts:
        item = box(comp, x, y, z0, w, h, z, NEW).bodies.item(0)
        item.name = 'CHECK: ' + name
    pcb = box(comp, 0, 0, PCB_COMPONENT_FACE_Z, PCB_W, PCB_H, PCB_TH, NEW).bodies.item(0)
    pcb.name = 'CHECK: brain PCB rev H 115x115'
    # Board orientation is intentional: the populated ESP32 side hangs DOWN
    # toward the ModulePlate, while the upper face is bare solder only.
    sockets = box(comp, 0, 0, PCB_COMPONENT_FACE_Z - PCB_SOCKET_H,
                  30.0, 58.0, PCB_SOCKET_H, NEW).bodies.item(0)
    sockets.name = 'CHECK: ESP32 socket envelope (downward)'
    devkit = box(comp, 0, 0, PCB_COMPONENT_FACE_Z - PCB_COMPONENT_H,
                 28.0, 56.0, PCB_DEVKIT_H, NEW).bodies.item(0)
    devkit.name = 'CHECK: ESP32 clearance envelope (downward)'


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
        root = design.rootComponent
        # A rerun must not leave old opaque cases and check bodies piled up.
        for i in range(root.bRepBodies.count - 1, -1, -1):
            b = root.bRepBodies.item(i)
            if b.name.startswith(('FIR Module', 'FIR Brain Case', 'CHECK:')):
                b.deleteMe()
        body = build(root)
        if SHOW_TRAY:
            build_preview_parts(root)
            try:
                body.opacity = 0.30
            except Exception as e:
                SKIPPED.append('preview opacity: {}'.format(e))
        vp = app.activeViewport
        if not SHOW_TRAY:
            try:
                cam = vp.camera
                cam.viewOrientation = adsk.core.ViewOrientations.TopViewOrientation
                vp.camera = cam
            except Exception:
                pass
        vp.fit()
        bad, detail = validate()
        msg = VERSION + '\n\n' + detail + '\n\nSELF-CHECK: ' + \
              ('PASS' if not bad else '{} PROBLEM(S)'.format(len(bad)))
        if bad:
            msg += '\n - ' + '\n - '.join(bad)
        if SKIPPED:
            msg += '\n\nSkipped:\n - ' + '\n - '.join(SKIPPED)
        ui.messageBox(msg)
    except:  # noqa
        if ui:
            ui.messageBox('FIR_ModuleGadget failed:\n{}'.format(traceback.format_exc()))
