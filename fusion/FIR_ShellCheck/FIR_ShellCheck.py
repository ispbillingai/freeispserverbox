# FIR_ShellCheck.py - Autodesk Fusion 360 script
#
# ALL-UP INSPECTION ASSEMBLY ONLY -- never export this model for printing.
# It builds the assembled tub/cap plus the ACTUAL BottomLid, CurvedLid, brain
# case and tray builders, then adds transparent PCB, component, connector,
# cable and driver-access envelopes.  The intent is to catch interference and
# wrong assembly order before a print; printed part geometry remains in its
# own source files.

import importlib.util
import math
import os
import sys

import adsk.core, adsk.fusion, adsk.cam, traceback


def _load_shared_interface():
    """Load the one brain-stack interface contract in workspace or Fusion."""
    script_file = globals().get('__file__', '')
    script_dir = (os.path.dirname(os.path.abspath(script_file))
                  if script_file else os.getcwd())
    candidates = []
    override = os.environ.get('FIR_INTERFACE_PATH')
    if override:
        candidates.append(override if override.lower().endswith('.py')
                          else os.path.join(override, 'FIR_Interface.py'))
    candidates.extend((
        os.path.join(script_dir, 'FIR_Interface.py'),
        os.path.join(script_dir, '..', '_shared', 'FIR_Interface.py'),
    ))
    workspace_source = globals().get('_workspace_source')
    if workspace_source:
        candidates.append(os.path.join(
            os.path.dirname(os.path.abspath(workspace_source)), '..',
            '_shared', 'FIR_Interface.py'))
    for candidate in candidates:
        path = os.path.realpath(os.path.abspath(candidate))
        if not os.path.isfile(path):
            continue
        # Always reload the shared contract so this check cannot inspect an
        # older cached tray/cap interface after a source sync.
        sys.modules.pop('_freeisp_shared_interface', None)
        spec = importlib.util.spec_from_file_location(
            '_freeisp_shared_interface', path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules['_freeisp_shared_interface'] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError(
        'FIR_Interface.py not found. Deploy fusion/_shared beside the Fusion scripts.')


INTERFACE = _load_shared_interface()

# ---- shell frame (FIR_Shell) ----
BOX_W, BOX_D, BOX_H = 280.0, 280.0, 80.0
WALL, FLOOR, CORNER_R, HALF, FRONT_Y = 3.0, 3.0, 10.0, 140.0, 137.0
MIK_W, MIK_D, MIK_H, MIK_CX, ST_H = 114.0, 139.0, 29.0, 78.0, 3.5
# Confirmed Tenda switch: envelope and mounted position from the one contract.
POE_W, POE_D, POE_H = INTERFACE.POE_W, INTERFACE.POE_D, INTERFACE.POE_H
POE_CX = INTERFACE.POE_CX
EXT_CY, DIV_Y, PLATE_TH = -110.0, -82.0, 3.0
EXT_W, EXT_D, EXT_H, EXT_FRONT_RETAINER_H = 240.0, 47.0, 29.0, 29.0
# Shared brain-stack interface.  The cap-boss pattern is derived in
# FIR_Interface from the case holes + CASE_TO_CAP_X/Y, so this inspection model
# cannot silently use a different mounting pattern from the printed parts.
# The case is 47mm off centre toward the MikroTik: that is what makes room for
# the alarm horn on the switch side, and it is why the cap-boss pattern is no
# longer symmetric in X.
TRAY_W, TRAY_H, TRAY_TH = INTERFACE.TRAY_W, INTERFACE.TRAY_H, INTERFACE.TRAY_TH
TRAY_MOUNT = INTERFACE.TRAY_MOUNT
PCB_W, PCB_H, PCB_TH = INTERFACE.PCB_W, INTERFACE.PCB_H, INTERFACE.PCB_TH
PCB_HOLE_PATTERN = INTERFACE.PCB_HOLE_PATTERN
CASE_TO_CAP_X = INTERFACE.CASE_TO_CAP_X
CASE_TO_CAP_Y = INTERFACE.CASE_TO_CAP_Y
CASE_MOUNT = INTERFACE.CASE_MOUNT
BRAIN_CAP_MOUNT = INTERFACE.CAP_BOSS_PATTERN
BRAIN_CAP_BOSS_D, BRAIN_CAP_BOSS_H = 9.0, 10.8
BRAIN_CAP_FLANGE_D, BRAIN_CAP_FLANGE_H = 13.0, 3.0
BRAIN_CAP_PILOT = 2.6
# ---- front device reference positions (for connector envelopes only) ----
BASE = 6.5
SW_PORT_SIDE_LAND = INTERFACE.POE_PORT_SIDE_LAND
SW_PORT_W, SW_PORT_H = INTERFACE.POE_PORT_W, INTERFACE.POE_PORT_H
SW_PORT_FROM_BOTTOM = INTERFACE.POE_PORT_FROM_BOTTOM
SW_PORT_Z0 = BASE + SW_PORT_FROM_BOTTOM
# ---- top cap (FIR_Shell build_top_lid, assembled) ----
CAP_LIFT = 0.0        # 0 = fully seated. Set to e.g. 40.0 to HOVER the cap above the tub and
                      # watch how it drops on (open edge stays at the front).
COVER_TRAVEL = 0.0    # 0 = fully slid home; positive mm moves the cover outward (+Y) to inspect rail entry.
# ---- confirmed Tenda switch DC jack (shared contract) ----
# The barrel jack is on the switch's own RIGHT-hand end face (shell -X), 8.3mm
# forward of its rear.  Its height on that face is not measured yet.
POE_JACK_D = INTERFACE.POE_JACK_D
POE_JACK_FROM_REAR = INTERFACE.POE_JACK_FROM_REAR
POE_JACK_FROM_BASE = INTERFACE.POE_JACK_FROM_BASE
POE_JACK_SIDE = INTERFACE.POE_JACK_SIDE
POE_PLUG_D = INTERFACE.POE_PLUG_D
POE_PLUG_STRAIGHT_L = INTERFACE.POE_PLUG_STRAIGHT_L
POE_PLUG_RIGHT_ANGLE_L = INTERFACE.POE_PLUG_RIGHT_ANGLE_L
# ---- alarm horn: INSIDE, on the floor behind the switch ----
# The bought part is a flared siren horn on a swivel foot, not a drum.  It lies
# down with its axis front-to-back and its mouth facing the front panel; it
# cannot be tilted in here, because a 20 degree tilt already needs more than the
# 114mm cavity has.  The only reason a 102mm-wide part fits at all is that the
# brain case moved +47mm off centre - that is the whole point of this view.
HORN_W, HORN_L, HORN_H = INTERFACE.HORN_W, INTERFACE.HORN_L, INTERFACE.HORN_H
HORN_BOLT_TAIL = INTERFACE.HORN_BOLT_TAIL
HORN_CX = INTERFACE.HORN_CX
HORN_FOOT_D = INTERFACE.HORN_FOOT_D
HORN_HOLE_D = INTERFACE.HORN_HOLE_D
HORN_PAD_D, HORN_PAD_H = INTERFACE.HORN_PAD_D, INTERFACE.HORN_PAD_H
CAP_ROOF_OUTER_Z, CAP_ROOF_TH = 120.0, 3.0  # assembled cap roof faces
# These are transparent screwdriver-travel illustrations only, not printed
# posts.  Keep the normal all-up view clean; enable temporarily when checking
# the three assembly stages.
SHOW_DRIVER_ACCESS = False
# SHELLS ONLY: build just the four printed shells (tub, deep cap, BottomLid,
# CurvedLid) plus the screw/click markers, with NO internal components - for
# inspecting the enclosure and its closures without the clutter.  Set False
# to get the full all-up model back.
SHELLS_ONLY = True
# Screw-axis / click-point marker pins.  They deliberately stick out past the
# shells so a fastener cannot be missed, which also makes them read as loose
# bars floating beside the box.  OFF by default: the real clearance holes and
# 2.6mm pilots are in the printed parts either way.  Set True only when you
# want to see where every enclosure fastener runs.  Do not show loose hardware
# in the default view: ShellCheck's normal mode is deliberately the five
# printable shells only.
SHOW_SCREW_MARKERS = False
CHECK_PREFIX = 'CHECK: ALL-UP'
CHECK_VERSION = ('v42: clean five-shell wall-mount inspection - tub, '
                 'deep cap, BottomLid, CurvedLid, WALL PLATE) with every outside screw '
                 'in a visible seat. All 8 cap screws are on the side walls now; the '
                 'keyholes are gone. The printed plate mates to the tub cleat; its two '
                 'M4 floor-lock holes are in the real parts, not shown as floating screws. '
                 'SHELLS_ONLY=False restores the internals; SHOW_SCREW_MARKERS=True '
                 'adds the fastener marker pins.')
# ---- 951 measured ports (x from left edge, z from base) ----
MPORTS = [('c', 11, 15, 6.5, 0), ('c', 19, 10, 2.5, 0), ('r', 25, 9.5, 4, 3), ('r', 33, 9.5, 4, 3),
          ('r', 44.5, 16, 13.5, 12.5), ('r', 58.5, 16, 13.5, 12.5), ('r', 72.5, 16, 13.5, 12.5),
          ('r', 86.5, 16, 13.5, 12.5), ('r', 100.5, 16, 13.5, 12.5)]

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
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(adsk.core.ValueInput.createByReal(mm(z0)))
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
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(d / 2.0))
    return _ext(comp, sk.profiles.item(0), z0, sz, op, parts)


def cyl_y(comp, cx, cz, ycenter, d, span, op, parts=None):
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cz), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(ycenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(adsk.core.ValueInput.createByReal(mm(ycenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def cyl_x(comp, cy, cz, xcenter, d, span, op, parts=None):
    # cylinder along X (circle on the yZ plane), symmetric about xcenter -
    # used for the side screw-axis markers
    sk = comp.sketches.add(comp.yZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cy), mm(cz), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(xcenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(xcenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def yport(comp, body, cx, cz, kind, a, b, y_face, span):
    # robust port cut into a +Y face: sketch on an offset plane AT the face, symmetric extrude
    try:
        pin = comp.constructionPlanes.createInput()
        pin.setByOffset(comp.xZConstructionPlane, adsk.core.ValueInput.createByReal(mm(y_face)))
        plane = comp.constructionPlanes.add(pin)
        sk = comp.sketches.add(plane)
        if kind == 'c':
            sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cz), 0), mm(a / 2.0))
        else:
            sk.sketchCurves.sketchLines.addCenterPointRectangle(
                adsk.core.Point3D.create(mm(cx), mm(cz), 0),
                adsk.core.Point3D.create(mm(cx + a / 2.0), mm(cz + b / 2.0), 0))
        ei = comp.features.extrudeFeatures.createInput(sk.profiles.item(0), CUT)
        ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
        ei.participantBodies = [body]
        comp.features.extrudeFeatures.add(ei)
    except Exception as e:
        SKIPPED.append('yport: {}'.format(e))


def set_opacity(body, o):
    try:
        body.opacity = o
    except Exception as e:
        SKIPPED.append('opacity: {}'.format(e))


def _load_active_builder(script_name):
    """Load an active Fusion part builder from its sibling script folder.

    Both the workspace layout and Fusion deployment use
    ``../<script>/<script>.py`` from this ShellCheck folder.  This deliberately
    reuses the print-part builders for the brain case and tray instead of
    maintaining a second, drifting shape copy here.
    """
    script_file = globals().get('__file__', '')
    script_dir = (os.path.dirname(os.path.abspath(script_file))
                  if script_file else os.getcwd())
    source_file = script_name + '.py'
    candidates = [os.path.join(script_dir, '..', script_name, source_file)]
    source_root = os.environ.get('FIR_SOURCE_ROOT')
    if source_root:
        candidates.append(os.path.join(source_root, script_name, source_file))
    for candidate in candidates:
        path = os.path.realpath(os.path.abspath(candidate))
        if not os.path.isfile(path):
            continue
        # An all-up rerun must use the current printable builder, not an
        # earlier module cached by Fusion in the same Python session.
        cache_name = '_freeisp_allup_' + script_name.lower()
        sys.modules.pop(cache_name, None)
        spec = importlib.util.spec_from_file_location(cache_name, path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[cache_name] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError('{} builder not found beside FIR_ShellCheck'.format(script_name))


def translate_body(comp, body, dx, dy, dz):
    """Move one all-up body without rotating its local part geometry."""
    coll = adsk.core.ObjectCollection.create()
    coll.add(body)
    matrix = adsk.core.Matrix3D.create()
    matrix.translation = adsk.core.Vector3D.create(mm(dx), mm(dy), mm(dz))
    comp.features.moveFeatures.add(comp.features.moveFeatures.createInput(coll, matrix))


def make_check_box(comp, name, cx, cy, z0, sx, sy, sz, opacity=0.55):
    body = box(comp, cx, cy, z0, sx, sy, sz, NEW).bodies.item(0)
    body.name = CHECK_PREFIX + ' ' + name
    set_opacity(body, opacity)
    return body


def make_check_cyl(comp, name, cx, cy, z0, d, sz, opacity=0.30):
    body = cyl(comp, cx, cy, z0, d, sz, NEW).bodies.item(0)
    body.name = CHECK_PREFIX + ' ' + name
    set_opacity(body, opacity)
    return body


# NOTE: this file used to carry its own copy of the tub and the deep cap.  Both
# are gone: build_actual_shell_and_cap() imports FIR_Shell's real builders, so
# there is no second definition here that can silently drift from the print source.


def place_lid_on_front(comp, body):
    # rotate the lid (lid coords) onto the tub front face: 180 deg about (0,1,1) + move +Y 137
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.pi, adsk.core.Vector3D.create(0, 1, 1), adsk.core.Point3D.create(0, 0, 0))
    m.translation = adsk.core.Vector3D.create(0, mm(FRONT_Y), 0)
    coll = adsk.core.ObjectCollection.create(); coll.add(body)
    mi = comp.features.moveFeatures.createInput(coll, m)
    comp.features.moveFeatures.add(mi)


def place_cover_on_front(comp, body):
    """Rigidly place the printable cover in its real closed orientation.

    This is a +90 degree rotation about X, not the reflection used by the old
    presentation-only FIR_Assembly.  Source +Z becomes shell -Y (into the
    shelf) and source +Y becomes shell +Z (up the front face).
    """
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.pi / 2.0, adsk.core.Vector3D.create(1, 0, 0),
                    adsk.core.Point3D.create(0, 0, 0))
    # Closed cover: front face at Y=205, lower edge Z=3.  Positive travel
    # moves it outward so the user can inspect rail entry before it slides home.
    m.translation = adsk.core.Vector3D.create(
        0, mm(205.0 + COVER_TRAVEL), mm(43.0))
    coll = adsk.core.ObjectCollection.create(); coll.add(body)
    comp.features.moveFeatures.add(comp.features.moveFeatures.createInput(coll, m))


def build_actual_front_closure(comp):
    """Build the active BottomLid and CurvedLid, not copied approximations."""
    lid_source = _load_active_builder('FIR_BottomLid')
    cover_source = _load_active_builder('FIR_CurvedLid')

    lid = lid_source.build(comp)
    lid.name = CHECK_PREFIX + ' bottom lid (actual FIR_BottomLid)'
    place_lid_on_front(comp, lid)
    set_opacity(lid, 0.22)

    cover = cover_source.build(comp)
    cover.name = CHECK_PREFIX + ' curved cover (actual FIR_CurvedLid)'
    place_cover_on_front(comp, cover)
    set_opacity(cover, 0.35)

    # The cover is placed with a true rigid transform, never a reflection.
    # That is what exposed the old handedness fault, and it is what proves the
    # fix: CurvedLid's notches are now written in real shell X, so its router
    # notches must land over the router and its switch notches over the switch.
    check_cover_handedness(lid_source, cover_source)
    return lid, cover


def check_cover_handedness(lid_source, cover_source):
    """Verify the cover's notches sit under the device they belong to.

    The cover only tips up 90 degrees about X, so its source X is shell X.  The
    BottomLid is turned over, so its source X is shell -X.  A notch on the wrong
    half of the box is invisible in a rendered view and obvious here, which is
    exactly the failure this all-up model exists to catch.
    """
    router_span = (MIK_CX - MIK_W / 2.0, MIK_CX + MIK_W / 2.0)
    switch_span = (POE_CX - POE_W / 2.0, POE_CX + POE_W / 2.0)
    stray = [nx for nx in cover_source.RJ45_X
             if not (router_span[0] <= nx <= router_span[1]
                     or switch_span[0] <= nx <= switch_span[1])]
    if stray:
        SKIPPED.append(
            'front-cover notches at X {} sit under neither the router nor the switch: '
            'CurvedLid handedness is wrong'
            .format(', '.join('{:.1f}'.format(v) for v in stray)))
    lid_power_x = -lid_source.POWER_CABLE_X          # turned-over plate
    if abs(cover_source.POWER_CABLE_X - lid_power_x) > 1.0:
        SKIPPED.append(
            'front-cover power notch is at shell X{:.1f} but the BottomLid pass-through it '
            'has to line up with is at X{:.1f}'
            .format(cover_source.POWER_CABLE_X, lid_power_x))


def build_mikrotik(comp):
    m_back = FRONT_Y - 0.5                             # 951 port face right against the lid inside
    oy = m_back - MIK_D / 2.0
    dev = box(comp, MIK_CX, oy, FLOOR + ST_H, MIK_W, MIK_D, MIK_H, NEW).bodies.item(0)
    dev.name = CHECK_PREFIX + ' MikroTik RB951 (measured ports)'
    for (k, x, z, a, b) in MPORTS:
        cx = MIK_CX - (-MIK_W / 2.0 + x)                 # flipped in X to match the lid
        yport(comp, dev, cx, FLOOR + ST_H + z, k, a, b, m_back, 8.0)
    return dev


def build_brain_all_up(comp):
    """Build the real gadget + real tray, then current physical envelopes."""
    gadget = _load_active_builder('FIR_ModuleGadget')
    plate_source = _load_active_builder('FIR_ModulePlate')

    # Cap-boss bottoms are roof-inner-face minus boss height.  The brain-case
    # roof outer face is its local BODY_Z; deriving this keeps CAP_LIFT exact.
    roof_inside_z = 117.0 + CAP_LIFT
    case_z = roof_inside_z - BRAIN_CAP_BOSS_H - gadget.BODY_Z
    case_x = CASE_TO_CAP_X
    case_y = CASE_TO_CAP_Y

    # The case now follows the confirmed 52mm plate-to-PCB stack.  The cap
    # still supplies the same boss-bottom Z datum, so make any reduced lower
    # clearance explicit rather than hiding it in a transparent all-up view.
    router_top = FLOOR + ST_H + MIK_H
    poe_top = FLOOR + ST_H + POE_H
    router_gap = case_z - router_top
    poe_gap = case_z - poe_top
    if router_gap < 0.0:
        SKIPPED.append(
            'ALL-UP INTERFERENCE: brain case/tray lower face Z{:.1f} overlaps '
            'the MikroTik top Z{:.1f} by {:.1f}mm; resolve before printing.'
            .format(case_z, router_top, -router_gap))
    elif router_gap < 1.0:
        SKIPPED.append(
            'ALL-UP TIGHT CLEARANCE: brain case/tray lower face is only {:.1f}mm '
            'above the MikroTik; target at least 1.0mm.'
            .format(router_gap))
    if poe_gap < 1.0:
        SKIPPED.append(
            'ALL-UP TIGHT CLEARANCE: brain case/tray lower face is only {:.1f}mm '
            'above the PoE switch; target at least 1.0mm.'
            .format(poe_gap))

    brain_case = gadget.build(comp)
    brain_case.name = CHECK_PREFIX + ' brain case (actual FIR_ModuleGadget)'
    translate_body(comp, brain_case, case_x, case_y, case_z)
    set_opacity(brain_case, 0.24)

    # Use the actual printed tray builder.  Do NOT call ModulePlate.build_parts:
    # its PCB preview is intentionally at the old tray-post height, whereas the
    # current PCB belongs to the gadget roof.
    tray = plate_source.build_plate(comp)
    tray.name = CHECK_PREFIX + ' electronics tray (actual FIR_ModulePlate)'
    # The real tray spans local Z=0..3; its top face contacts the case ledge
    # that begins at local Z=3.  Do not add PLATE_SEAT_Z again here.
    translate_body(comp, tray, case_x, case_y, case_z)
    set_opacity(tray, 0.50)

    # The current PCB and electronics do not have imported manufacturer STEP
    # files.  These envelopes use the active Gadget/ModulePlate dimensions and
    # are deliberately named as inspection geometry, never printable parts.
    # Owner-confirmed orientation: the PCB's populated/silkscreen face points
    # DOWN toward the ModulePlate; only the bare solder side faces the roof.
    # Read the explicit datum from the active Gadget, with an orientation-safe
    # fallback for a pre-v21 builder.
    pcb_component_face = getattr(gadget, 'PCB_COMPONENT_FACE_Z',
                                 gadget.PCB_TOP_Z - PCB_TH)
    pcb_z0 = case_z + pcb_component_face
    make_check_box(comp, 'brain PCB 115x115 (component face DOWN)',
                   case_x, case_y, pcb_z0, PCB_W, PCB_H, PCB_TH, 0.62)
    socket_z0 = case_z + pcb_component_face - gadget.PCB_SOCKET_H
    devkit_z0 = socket_z0 - gadget.PCB_DEVKIT_H
    make_check_box(comp, 'ESP32 socket envelope (downward)', case_x, case_y,
                   socket_z0, 28.0, 56.0, gadget.PCB_SOCKET_H, 0.48)
    make_check_box(comp, 'ESP32 DevKitC envelope (downward)', case_x, case_y,
                   devkit_z0, 28.0, 56.0, gadget.PCB_DEVKIT_H, 0.55)

    for name, width, length, height, cx, cy, mount in plate_source.MODULES:
        z0 = plate_source.PLATE_TOP if mount == 'flat' else \
            plate_source.PLATE_TOP + plate_source.RAISE
        if name == 'battery cell':
            # 14500 cell axis is along the tray Y direction.
            feature = cyl_y(comp, case_x + cx, case_z + z0 + height / 2.0,
                            case_y + cy, width, length, NEW)
            item = feature.bodies.item(0)
            item.name = CHECK_PREFIX + ' 14500 cell envelope'
            set_opacity(item, 0.65)
        else:
            make_check_box(comp, 'module envelope: ' + name,
                           case_x + cx, case_y + cy, case_z + z0,
                           width, length, height, 0.58)
        if name == 'relay':
            # The real relay terminal block extends 12mm beyond the 34mm board
            # toward +X (source envelope reaches X=49 locally).  Include it so
            # the inspection view cannot falsely clear that terminal side.
            make_check_box(comp, 'relay terminal overhang envelope',
                           case_x + cx + width / 2.0 + 6.0, case_y + cy,
                           case_z + z0, 12.0, length, height, 0.58)

    # J4/J5 plugs descend through the free +X margin, then leave through the
    # 50x5 Dupont exit centred in the PCB-to-plate gap.
    for label, y0, y1 in (
            ('J4 TFT 5V connector', gadget.J4_J5_Y_MIN, -27.4),
            ('J5 RC522 3V3 connector', -21.5, gadget.J4_J5_Y_MAX)):
        cy = case_y + (y0 + y1) / 2.0
        span = y1 - y0
        # The J4/J5 header stacks are on the component face, so they hang
        # down into the plate-side gap rather than rising toward the roof.
        make_check_box(comp, label, case_x + PCB_W / 2.0 + 2.0, cy,
                       case_z + pcb_component_face - 4.0,
                       4.0, span, 4.0, 0.62)
        service_top = pcb_component_face - 4.0
        service_bottom = gadget.JUMPER_Z0 + gadget.JUMPER_H
        if service_top > service_bottom:
            make_check_box(comp, label + ' vertical service drop',
                           case_x + PCB_W / 2.0 + 3.5, cy,
                           case_z + service_bottom,
                           7.0, span, service_top - service_bottom, 0.30)
        make_check_box(comp, label + ' Dupont exit envelope',
                       case_x + PCB_W / 2.0 + 7.0, cy,
                       case_z + gadget.JUMPER_Z0, 10.0, span, gadget.JUMPER_H, 0.30)

    return {
        'gadget': gadget,
        'plate': plate_source,
        'case_x': case_x,
        'case_y': case_y,
        'case_z': case_z,
        'pcb_z0': pcb_z0,
    }


def build_poe_dc_jack(comp):
    """Show the Tenda's own DC jack and the volume its plug demands.

    Measured: a 6mm barrel jack on the switch's RIGHT-hand end face, 8.3mm
    forward of its rear.  Height on that face is not measured, so it is drawn
    at mid-height and reported as an assumption rather than shown as fact.
    """
    front = FRONT_Y - 0.5
    rear = front - POE_D
    face_x = POE_CX + POE_JACK_SIDE * POE_W / 2.0
    jack_y = rear + POE_JACK_FROM_REAR
    jack_z = FLOOR + ST_H + POE_JACK_FROM_BASE

    make_check_cyl(comp, 'switch DC jack (6mm, measured)',
                   face_x, jack_y, jack_z - POE_JACK_D / 2.0,
                   POE_JACK_D, 1.0, 0.70)
    # Straight plug first: if it fits, everything fits.  It is drawn as the
    # volume the plug body wants, sticking out of that end face.
    plug_x = face_x + POE_JACK_SIDE * POE_PLUG_STRAIGHT_L / 2.0
    make_check_box(comp, 'switch DC plug envelope (straight barrel)',
                   plug_x, jack_y, jack_z - POE_PLUG_D / 2.0,
                   POE_PLUG_STRAIGHT_L, POE_PLUG_D, POE_PLUG_D, 0.45)

    wall_inner = POE_JACK_SIDE * (HALF - WALL)
    air = abs(wall_inner - face_x)
    if POE_JACK_SIDE > 0:
        air = min(air, abs((MIK_CX - MIK_W / 2.0) - face_x))
    if air < POE_PLUG_STRAIGHT_L + 1.0:
        SKIPPED.append(
            'switch DC jack: only {:.1f}mm of air off its end face. A straight barrel plug '
            'needs ~{:.0f}mm and will NOT fit; a right-angle plug needs ~{:.0f}mm. Either '
            'use a right-angle DC plug or move the switch inboard (which also moves the '
            'BottomLid 68.8mm slot).'
            .format(air, POE_PLUG_STRAIGHT_L, POE_PLUG_RIGHT_ANGLE_L))
    if not INTERFACE.POE_JACK_MEASURED_HEIGHT:
        SKIPPED.append(
            'switch DC jack height is ASSUMED at {:.1f}mm above the switch base (mid-height); '
            'measure it so the cradle post beside it can be set exactly'
            .format(POE_JACK_FROM_BASE))
    return air


def build_poe_and_front_connectors(comp):
    """Confirmed PoE switch plus router/switch service envelopes."""
    front = FRONT_Y - 0.5
    poe = make_check_box(comp, 'PoE switch envelope', POE_CX,
                         front - POE_D / 2.0, FLOOR + ST_H,
                         POE_W, POE_D, POE_H, 0.58)

    # BottomLid local X is mirrored into the assembled shell.  The real
    # switch now has one measured 68.8 x 11.5mm service slot, not five guessed
    # individual RJ45 openings.  This is an external plug/service envelope,
    # not an additional cut in the printable parts.
    make_check_box(comp, 'PoE {:.1f} x {:.1f} long-port service envelope'
                   .format(SW_PORT_W, SW_PORT_H),
                   POE_CX, front + 4.0, SW_PORT_Z0,
                   SW_PORT_W, 8.0, SW_PORT_H, 0.40)

    build_poe_dc_jack(comp)

    # Router port envelopes use the same measured MPORTS values used by its
    # cut geometry.  Only the five RJ45 plugs are shown as external volumes.
    for index, (kind, px, pz, width, height) in enumerate(MPORTS):
        if kind != 'r' or width < 10.0:
            continue
        cx = MIK_CX - (-MIK_W / 2.0 + px)
        make_check_box(comp, 'MikroTik RJ45 plug {}'.format(index - 3), cx,
                       front + 4.0, FLOOR + ST_H + pz - height / 2.0,
                       width, 8.0, height, 0.40)
    return poe


def build_extension_and_adapters(comp):
    """Show the current shell-source extension and three adapters."""
    make_check_box(comp, 'extension strip envelope', 0.0, EXT_CY, FLOOR,
                   EXT_W, EXT_D, EXT_H, 0.50)
    for index, ax in enumerate((-80.0, 0.0, 80.0)):
        make_check_box(comp, 'adapter {} envelope'.format(index + 1), ax,
                       EXT_CY, FLOOR + EXT_H, 46.0, 46.0, 52.0, 0.48)
    # The old 48mm internal buzzer proxy is intentionally not shown.  The
    # owner supplied the real 104mm horn, which is previewed on the cap by
    # build_horn_preview() after the brain case is placed.


def horn_mount_points():
    """The three floor-pad centres, from the one shared solver."""
    return INTERFACE.horn_mount_points()


def build_horn_preview(comp, brain):
    """Draw the horn where it actually sits: on the floor behind the switch.

    FIR_Shell builds the three floor pads it bolts to; this view adds the
    bought part, its bracket foot, the volume its rear tightening bolts need,
    and the sound path out through the front window.  Every check below is a
    real interference the layout only just clears.
    """
    hx0, hx1, hy0, hy1, hz0, hz1 = INTERFACE.horn_body()
    # The bell drawn as the owner measured it: D74 rear, D76 middle, D83 at
    # three-quarters, D102 only at the mouth.  Stepped cylinders along the
    # axis - no more fat 102mm box pretending the whole horn is mouth-sized.
    axis_z = INTERFACE.horn_axis_z()
    for index, (sy0, sy1, dia) in enumerate(INTERFACE.horn_profile_segments()):
        seg = cyl_y(comp, HORN_CX, axis_z, (sy0 + sy1) / 2.0,
                    dia, sy1 - sy0, NEW).bodies.item(0)
        seg.name = (CHECK_PREFIX +
                    ' alarm horn bell D{:.0f} (Y{:.0f}..{:.0f}, measured taper)'
                    .format(dia, sy0, sy1))
        set_opacity(seg, 0.30)
    make_check_box(comp, 'alarm horn bracket stand (~29mm wide, unmeasured depth)',
                   HORN_CX, hy0 + 15.0, hz0, INTERFACE.HORN_ARM_W, 30.0,
                   axis_z - hz0, 0.30)
    fx, fy = INTERFACE.horn_foot_centre()
    make_check_cyl(comp, 'alarm horn 69mm bracket foot', fx, fy,
                   FLOOR + HORN_PAD_H, HORN_FOOT_D, 3.0, 0.45)
    # The sled: bench-assembled with ALL THREE measured foot bolts, then the
    # whole horn+sled drops into the tub's curb pocket and clamps with two
    # wing screws.  Show the assembled sled and prove the wing corridors open.
    sled_cx = (INTERFACE.HORN_SLED_X0 + INTERFACE.HORN_SLED_X1) / 2.0
    sled_cy = (INTERFACE.HORN_SLED_Y0 + INTERFACE.HORN_SLED_Y1) / 2.0
    make_check_box(comp, 'horn SLED (bench-bolted adapter plate)',
                   sled_cx, sled_cy, FLOOR,
                   INTERFACE.HORN_SLED_X1 - INTERFACE.HORN_SLED_X0,
                   INTERFACE.HORN_SLED_Y1 - INTERFACE.HORN_SLED_Y0,
                   INTERFACE.HORN_SLED_TH, 0.50)
    for index, (px, py) in enumerate(INTERFACE.horn_mount_points()):
        make_check_cyl(comp, 'horn foot bolt {} (driven on the BENCH into the sled)'
                       .format(index + 1), px, py,
                       INTERFACE.horn_foot_plane_z() - INTERFACE.HORN_SLED_BOSS_H,
                       HORN_HOLE_D, INTERFACE.HORN_SLED_BOSS_H
                       + INTERFACE.HORN_FOOT_PLATE_TH + 4.0, 0.30)
    for index, (px, py) in enumerate(INTERFACE.horn_wing_points()):
        make_check_cyl(comp, 'horn wing screw {} (M4x10, in-box clamp)'.format(index + 1),
                       px, py, FLOOR, 4.0, HORN_PAD_H + 12.0, 0.30)
        make_check_cyl(comp, 'horn wing screw {} driver corridor'.format(index + 1),
                       px, py, FLOOR + HORN_PAD_H + 12.0, 12.0, 85.0, 0.10)
        # the corridor must dodge the horn body AND the hanging brain case
        if hy0 < py < hy1 and hx0 < px < hx1:
            SKIPPED.append('horn wing screw {} is under the body - move the wing line'
                           .format(index + 1))
        case_y0 = brain['case_y'] - brain['gadget'].H / 2.0
        if py + 6.0 > case_y0 and brain['case_x'] - brain['gadget'].W / 2.0 < px + 6.0:
            SKIPPED.append('horn wing corridor {} runs into the hanging brain case'
                           .format(index + 1))
    # The bracket arm / tightening-bolt zone above the rear foot holes is NOT
    # measured; nothing of ours may claim that space.  This zone is exactly why
    # in-box foot bolts were impossible and the sled exists.
    make_check_box(comp, 'horn bracket arm + tightening bolts (UNMEASURED zone)',
                   (hx0 + hx1) / 2.0, hy0 - HORN_BOLT_TAIL / 2.0,
                   INTERFACE.horn_foot_plane_z(), 60.0, HORN_BOLT_TAIL, 60.0, 0.15)

    # ---- what the position has to survive -------------------------------
    gadget = brain['gadget']
    case_x0 = brain['case_x'] - gadget.W / 2.0
    switch_rear = FRONT_Y - 0.5 - POE_D
    # Radial clearances from the measured taper, evaluated where each
    # neighbour actually stands - not from the old bounding box.
    def bell_edge(py):
        for sy0, sy1, dia in INTERFACE.horn_profile_segments():
            if sy0 <= py <= sy1:
                return dia / 2.0
        return HORN_W / 2.0
    checks = []
    for by in INTERFACE.CAP_SIDE_SCREW_Y:   # wall boss rows (Z66-78, face X-125)
        if hy0 <= by <= hy1:
            checks.append(('cap side-bolt boss row at Y{:.0f}'.format(by),
                           (HORN_CX - bell_edge(by)) - (-HALF + WALL + 12.0)))
    case_span = [max(hy0, brain['case_y'] - gadget.H / 2.0),
                 min(hy1, brain['case_y'] + gadget.H / 2.0)]
    if case_span[0] < case_span[1]:
        worst = min(case_x0 - (HORN_CX + bell_edge(py))
                    for py in (case_span[0], case_span[1],
                               (case_span[0] + case_span[1]) / 2.0, hy1))
        checks.append(('the brain case (worst point of the taper)', worst))
    checks.append(('the switch cradle', (switch_rear - 3.0) - hy1))
    checks.append(('the cap roof underside (mouth top)',
                   (117.0 + CAP_LIFT) - (axis_z + HORN_W / 2.0)))
    for name, air in checks:
        if air < 1.0:
            SKIPPED.append('HORN INTERFERENCE: {:.1f}mm to {}'.format(air, name))
        elif air < 3.0:
            SKIPPED.append('horn is tight: {:.1f}mm to {}'.format(air, name))
        else:
            SKIPPED.append('horn clearance: {:.1f}mm to {}'.format(air, name))

    # ---- sound exit: none, on purpose ----------------------------------
    # A slotted window was cut through both front parts and then removed at the
    # owner's request: this siren is loud enough that a plastic box will not
    # meaningfully muffle it.  Stated here so a later pass does not helpfully
    # re-open the panel.
    if not INTERFACE.HORN_VENTS:
        SKIPPED.append(
            'horn fires into a closed box by owner decision - no vents in the front '
            'panel, the cover or the lid. Do not re-add a grille without asking.')
    # Owner requirement: rain from the TOP must never reach the components;
    # dripping out the bottom is fine.  Trace the top paths explicitly.
    SKIPPED.append(
        'top-rain check: roof is continuous (no holes at all); every roof edge sheds '
        'onto the OUTSIDE of the cap skirt; the skirt-to-tub gap opens DOWNWARD at '
        'Z65, below the tub rim at Z80, so top water cannot run into it; water on the '
        'cap front wall drips onto the cover top and runs off the front; anything '
        'that wicks through that 0.5mm seam lands inside the cover hood and drains '
        'out the downward cable notches. Top-tight by geometry, drips exit down.')

    if not INTERFACE.HORN_FOOT_MEASURED:
        SKIPPED.append(
            'horn foot is ASSUMED {:.0f}mm back from the mouth face; measure that and the '
            'three floor pads move with it'.format(INTERFACE.HORN_FOOT_FROM_MOUTH))
    return horn_mount_points()


def build_cable_paths(comp, brain):
    """Inspection-only cable envelopes, routed below the brain case.

    The old horizontal mains proxy entered the brain-case volume.  It is not
    reused here: mains routing is intentionally reported as unresolved rather
    than hidden behind a false-clearance drawing.
    """
    gadget = brain['gadget']
    front = FRONT_Y - 0.5
    low_z = FLOOR + 1.0
    make_check_box(comp, 'DC cable to MikroTik (low-floor route)', -40.0,
                   front - 70.0, low_z, 4.0, 120.0, 4.0, 0.24)
    # The switch is fed from its own end face, not from the middle of the box:
    # this run hugs the -X wall gap and turns in at the jack.
    jack_run_x = POE_CX + POE_JACK_SIDE * (POE_W / 2.0 + 5.0)
    make_check_box(comp, 'DC cable to switch jack (low-floor route)', jack_run_x,
                   front - 60.0, low_z, 4.0, 110.0, 4.0, 0.24)
    for index, px in enumerate((90.5, 76.5, 62.5, 48.5, 34.5)):
        make_check_box(comp, 'MikroTik LAN lead {}'.format(index + 1), px,
                       front + 20.0, FLOOR + ST_H + BASE + 16.0 - 3.0,
                       4.0, 42.0, 4.0, 0.22)
    # Short, non-committal internal runs show the actual J4/J5 exit direction
    # without claiming an unmeasured destination outside the brain case.
    make_check_box(comp, 'J4/J5 wire service loop envelope', brain['case_x'] + 76.0,
                   brain['case_y'] - 25.0,
                   brain['case_z'] + gadget.JUMPER_Z0,
                   18.0, 50.0, gadget.JUMPER_H, 0.22)
    SKIPPED.append(
        'mains route intentionally not drawn: the previous proxy intersected the brain case')


def build_driver_access(comp, brain):
    """Show which screws can be reached at each real assembly stage."""
    gadget = brain['gadget']
    case_z, case_y = brain['case_z'], brain['case_y']
    # Stage 1: empty case -> cap.  These long driver corridors must be used
    # before PCB/tray installation, which is why they are shown separately.
    for index, (x, y) in enumerate(BRAIN_CAP_MOUNT):
        make_check_cyl(comp, 'driver stage 1 case-to-cap screw {}'.format(index + 1),
                       x, y, case_z, 5.0, gadget.BODY_Z, 0.14)
    # Stage 2: PCB screws are reachable from the open component-side bottom
    # before the tray.  They travel upward into the short roof posts.
    for index, (x, y) in enumerate(PCB_HOLE_PATTERN):
        make_check_cyl(comp, 'driver stage 2 PCB screw {}'.format(index + 1),
                       brain['case_x'] + x, case_y + y, case_z, 4.0,
                       getattr(gadget, 'PCB_COMPONENT_FACE_Z',
                               gadget.PCB_TOP_Z - PCB_TH), 0.14)
    # Stage 3: tray screws enter from the open bottom and only retain the tray.
    for index, (x, y) in enumerate(TRAY_MOUNT):
        make_check_cyl(comp, 'driver stage 3 tray screw {}'.format(index + 1),
                       brain['case_x'] + x, case_y + y, case_z, 4.0,
                       gadget.PLATE_SEAT_Z + gadget.PLATE_BOSS_H, 0.14)


def build_screw_markers(comp):
    """Solid marker pins through every cap/lid screw axis.

    The real 3.4mm holes are invisible in a transparent view, which reads as
    'there are no bolts'.  These pins make each fastener's position and
    direction unmissable; they are inspection bodies, not printed geometry.
    """
    for sxs in (-1.0, 1.0):                     # 8 cap side screws (4 per wall)
        for sy in INTERFACE.CAP_SIDE_SCREW_Y:
            body = cyl_x(comp, sy, INTERFACE.CAP_SCREW_Z + CAP_LIFT,
                         sxs * 138.0, 3.0, 22.0, NEW).bodies.item(0)
            body.name = CHECK_PREFIX + ' cap SIDE screw M3 (Y{:.0f}, {}X wall)'.format(
                sy, '+' if sxs > 0 else '-')
            set_opacity(body, 0.85)
    for lx in INTERFACE.WALL_LOCK_X:            # 2 wall-mount floor locks
        body = cyl(comp, lx, INTERFACE.WALL_LOCK_Y, -10.0, 3.0, 24.0,
                   NEW).bodies.item(0)
        body.name = (CHECK_PREFIX + ' wall-mount floor lock M4 (X{:.0f}, driven '
                     'DOWN from inside)'.format(lx))
        set_opacity(body, 0.85)
    for (bx, bz) in ((-120, 72), (120, 72), (-40, 72), (40, 72),
                     (-132, 44), (132, 44)):    # 6 BottomLid screws
        body = cyl_y(comp, bx, bz, FRONT_Y + 2.0, 3.0, 22.0, NEW).bodies.item(0)
        body.name = CHECK_PREFIX + ' BottomLid screw M3 (X{}, Z{})'.format(bx, bz)
        set_opacity(body, 0.85)
    for sx in (-125.0, 125.0):                  # 2 CurvedLid lock screws
        body = cyl_y(comp, sx, 12.0, 206.0, 3.0, 22.0, NEW).bodies.item(0)
        body.name = CHECK_PREFIX + ' CurvedLid lock screw M3 (X{:.0f})'.format(sx)
        set_opacity(body, 0.85)
    # snap detents: mark each click point so the self-lock is visible too
    for sy in INTERFACE.CAP_SNAP_SIDE_Y:
        for sxs in (-1.0, 1.0):
            body = box(comp, sxs * 141.0, sy, INTERFACE.CAP_SNAP_Z0 + CAP_LIFT,
                       4.0, INTERFACE.CAP_SNAP_W, INTERFACE.CAP_SNAP_Z1
                       - INTERFACE.CAP_SNAP_Z0, NEW).bodies.item(0)
            body.name = CHECK_PREFIX + ' self-click detent ({}X wall, Y{:.0f})'.format(
                '+' if sxs > 0 else '-', sy)
            set_opacity(body, 0.85)
    for bx in INTERFACE.CAP_SNAP_BACK_X:
        body = box(comp, bx, -141.0, INTERFACE.CAP_SNAP_Z0 + CAP_LIFT,
                   INTERFACE.CAP_SNAP_W, 4.0, INTERFACE.CAP_SNAP_Z1
                   - INTERFACE.CAP_SNAP_Z0, NEW).bodies.item(0)
        body.name = CHECK_PREFIX + ' self-click detent (back wall, X{:.0f})'.format(bx)
        set_opacity(body, 0.85)
    SKIPPED.append(
        'cap closure: push straight down - at the last 1mm the six wall detents click '
        'into their skirt windows (the cap holds itself), then 8 M3 screws lock it.')


def build_actual_wall_plate(comp):
    """Build the real FIR_WallPlate and hang it where the wall actually is.

    The plate is authored lying wall-face down (local X = shell X, local
    Y = -shell Z, local Z = shell Y - WALL_FACE_Y).  A -90 degree rotation
    about X plus a WALL_FACE_Y shift inverts that mapping exactly.
    """
    plate_source = _load_active_builder('FIR_WallPlate')
    plate = plate_source.build(comp)
    plate.name = CHECK_PREFIX + ' wall plate (actual FIR_WallPlate)'
    coll = adsk.core.ObjectCollection.create()
    coll.add(plate)
    matrix = adsk.core.Matrix3D.create()
    matrix.setToRotation(-math.pi / 2.0, adsk.core.Vector3D.create(1, 0, 0),
                         adsk.core.Point3D.create(0, 0, 0))
    matrix.translation = adsk.core.Vector3D.create(
        0, mm(INTERFACE.WALL_FACE_Y), 0)
    comp.features.moveFeatures.add(comp.features.moveFeatures.createInput(coll, matrix))
    set_opacity(plate, 0.35)

    # The numbers that make this mount work, restated every run.
    SKIPPED.append(
        'wall mount: tub cleat bar drops onto the plate 45deg face and wedges the '
        'box back flat against it; the crest wall means the box must LIFT {:.1f}mm '
        'before it can be pulled off, and the two in-box M4 x 10 floor locks at '
        '(+-{:.0f}, {:.0f}) stop that lift. Cap skirt bottom Z65 clears the plate '
        'top Z{:.0f} by {:.0f}mm; the skirt outer face at Y-143 clears the building '
        'wall at Y{:.0f} by {:.0f}mm. Install: plate -> hang tub -> floor locks '
        'from inside -> cap. With the cap screwed on, the box cannot leave the wall.'
        .format(INTERFACE.cleat_interlock(), abs(INTERFACE.WALL_LOCK_X[0]),
                INTERFACE.WALL_LOCK_Y, INTERFACE.WALL_PLATE_TOP_Z,
                65.0 - INTERFACE.WALL_PLATE_TOP_Z, INTERFACE.WALL_FACE_Y,
                abs(INTERFACE.WALL_FACE_Y) - 143.0))
    return plate


def build_actual_shell_and_cap(comp):
    """Use FIR_Shell's print builders, transforming its cap into assembly."""
    shell_source = _load_active_builder('FIR_Shell')
    del shell_source.SKIPPED[:]
    shell = shell_source.build(comp)
    shell.name = CHECK_PREFIX + ' shell / actual FIR_Shell tub (see-through)'
    set_opacity(shell, 0.22)

    # FIR_Shell builds the cap plate-down for printing: its external roof is
    # local Z=0 and its inner roof face is Z=3.  Rotate 180 degrees around Y
    # and lift to Z=120, preserving +Y as the front.  The cap is symmetric in
    # X, so the X mirror does not change any placement datum.
    cap = shell_source.build_top_lid(comp, 0.0)
    cap.name = CHECK_PREFIX + ' top cap / actual FIR_Shell (see-through)'
    coll = adsk.core.ObjectCollection.create()
    coll.add(cap)
    matrix = adsk.core.Matrix3D.create()
    matrix.setToRotation(math.pi, adsk.core.Vector3D.create(0, 1, 0),
                         adsk.core.Point3D.create(0, 0, 0))
    matrix.translation = adsk.core.Vector3D.create(0, 0, mm(120.0 + CAP_LIFT))
    comp.features.moveFeatures.add(comp.features.moveFeatures.createInput(coll, matrix))
    set_opacity(cap, 0.22)
    # Carry the tub's own build notes into this report.  They are where the
    # cradle says what it had to trim, and they would otherwise never be seen
    # by anyone running the all-up view instead of FIR_Shell directly.
    for note in shell_source.SKIPPED:
        SKIPPED.append('FIR_Shell: ' + note)
    return shell, cap


def clear_old(comp):
    """Delete only bodies made by ShellCheck, never arbitrary user geometry."""
    legacy_names = (
        '1 SHELL (see-through)', '2 BOTTOM LID (see-through)',
        '3 MikroTik 951', '4 TOP CAP (see-through)',
    )
    removed = 0
    for index in range(comp.bRepBodies.count - 1, -1, -1):
        body = comp.bRepBodies.item(index)
        if body.name.startswith(CHECK_PREFIX) or body.name in legacy_names:
            try:
                body.deleteMe()
                removed += 1
            except Exception as e:
                SKIPPED.append('clear {}: {}'.format(body.name, e))
    return removed


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
            design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        except Exception:
            pass
        del SKIPPED[:]
        comp = design.rootComponent
        # Rebuild the current shared contract/builders on every inspection
        # run so a source sync cannot be hidden by Fusion's module cache.
        sys.modules.pop('_freeisp_shared_interface', None)
        removed = clear_old(comp)
        sh, cap = build_actual_shell_and_cap(comp)
        lid, cover = build_actual_front_closure(comp)
        build_actual_wall_plate(comp)
        horn_points = ()
        if SHELLS_ONLY:
            SKIPPED.append(
                'SHELLS-ONLY view: no devices, horn, brain stack or cables drawn. '
                'Set SHELLS_ONLY = False for the full all-up model.')
        else:
            build_mikrotik(comp)
            build_poe_and_front_connectors(comp)
            build_extension_and_adapters(comp)
            brain = build_brain_all_up(comp)
            horn_points = build_horn_preview(comp, brain)
            build_cable_paths(comp, brain)
            if SHOW_DRIVER_ACCESS:
                build_driver_access(comp, brain)
        if SHOW_SCREW_MARKERS:
            build_screw_markers(comp)
        app.activeViewport.fit()
        built = ('the five printed shells ONLY (tub, deep cap, BottomLid, CurvedLid, '
                 'wall plate)'
                 if SHELLS_ONLY else
                 'the assembled tub, BottomLid, CurvedLid, cap, wall plate, actual '
                 'brain case, actual tray, PCB/module envelopes, router, PoE switch, '
                 'three adapters, connectors and cable paths')
        message = (CHECK_VERSION + '\n\n'
                   'Built {}.\n'
                   'Cleared {} prior ShellCheck body(ies).\n'
                   'Interface {}: tray {}x{}, PCB {}x{}, case offset +X{} +Y{}.'
                   .format(built, removed, INTERFACE.INTERFACE_VERSION,
                           TRAY_W, TRAY_H, PCB_W, PCB_H, CASE_TO_CAP_X, CASE_TO_CAP_Y))
        if horn_points:
            hb = INTERFACE.horn_body()
            message += ('\nHorn: INSIDE on the floor behind the switch, '
                        'X{:.1f}..{:.1f} Y{:.1f}..{:.1f} Z{:.1f}..{:.1f}, mouth facing the front. '
                        'Foot bolts at {}.'
                        .format(hb[0], hb[1], hb[2], hb[3], hb[4], hb[5],
                                ', '.join('({:.1f}, {:.1f})'.format(x, y)
                                          for x, y in horn_points)))
        if SKIPPED:
            message += '\n\nInspection notes:\n - ' + '\n - '.join(SKIPPED)
        ui.messageBox(message)
    except:  # noqa
        if ui:
            ui.messageBox('FIR_ShellCheck failed:\n{}'.format(traceback.format_exc()))
