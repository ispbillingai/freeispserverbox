# FIR_WallPlate.py - Autodesk Fusion 360 script
# The printed WALL PLATE the whole box hangs on (replaces the two keyholes,
# which could barely hold a 2-3kg loaded box and pushed their screw heads into
# the adapter bank).  One part, printed lying WALL-FACE DOWN:
#  - a slab screwed to the wall with up to six 4.5mm screws whose heads sit in
#    pockets INSIDE the plate, so nothing protrudes toward (or into) the box;
#  - a full-width 45-degree French-cleat face: the tub's matching back-wall
#    bar drops onto it and gravity wedges the box back against the plate;
#  - a crest wall behind the bar tip, so the box must LIFT ~4.4mm before it
#    can be pulled off the wall;
#  - two under-floor ARMS: two M4 x 10 screws driven DOWN from inside the box
#    clamp the tub floor to them.  With the cap screwed on those screws are
#    unreachable - the box cannot leave the wall without opening it.
#
# LOCAL PRINT FRAME (the deliberate mapping - do not eyeball it):
#   local X = assembled shell X
#   local Y = MINUS assembled shell Z   (plate lies on its back)
#   local Z = assembled shell Y + 149   (0 = the building wall face)
# FIR_ShellCheck places this part with a -90 degree rotation about X plus a
# -149mm Y shift, exactly inverting that mapping.

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
    for candidate in candidates:
        path = os.path.realpath(os.path.abspath(candidate))
        if not os.path.isfile(path):
            continue
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

PLATE_TH = INTERFACE.WALL_PLATE_TH
X_HALF = INTERFACE.WALL_PLATE_X_HALF
TOP_Z = INTERFACE.WALL_PLATE_TOP_Z            # assembled Z of the crest top
BOT_Z = INTERFACE.WALL_PLATE_BOT_Z

CM = 0.1


def mm(v):
    return v * CM


def to_local_y(assembled_z):
    return -assembled_z


def to_local_z(assembled_y):
    return assembled_y - INTERFACE.WALL_FACE_Y


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


def cyl_y(comp, cx, cz, ycenter, d, span, op, parts=None):
    # cylinder along local Y (circle on the xZ plane), symmetric about ycenter
    # - the arm pilots run along local Y (assembled straight DOWN).
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cx), mm(cz), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(ycenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(ycenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def poly_x(comp, pts_yz, xcenter, span, op, parts=None):
    # closed polygon on the yZ plane, extruded along X - the slab-plus-cleat
    # cross-section is one profile so the 45-degree face is a true plane.
    sk = comp.sketches.add(comp.yZConstructionPlane)
    lines = sk.sketchCurves.sketchLines
    n = len(pts_yz)
    for i in range(n):
        y0, z0 = pts_yz[i]
        y1, z1 = pts_yz[(i + 1) % n]
        lines.addByTwoPoints(adsk.core.Point3D.create(mm(y0), mm(z0), 0),
                             adsk.core.Point3D.create(mm(y1), mm(z1), 0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(xcenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(xcenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def build(comp):
    """Build the printable wall plate (local print frame) and return its body.

    FIR_ShellCheck imports this exact builder for the all-up inspection.
    """
    crest_front_lz = to_local_z(INTERFACE.cleat_crest_front_y())   # 2.4
    face_top_ly = to_local_y(INTERFACE.CLEAT_FACE_Z0 +
                             INTERFACE.CLEAT_BAR_RUN +
                             INTERFACE.CLEAT_TIP_CLEAR)            # -57.4
    profile = (
        (to_local_y(BOT_Z), PLATE_TH),                # front-bottom
        (to_local_y(INTERFACE.CLEAT_FACE_Z0), PLATE_TH),
        (face_top_ly, crest_front_lz),                # up the 45-degree face
        (to_local_y(TOP_Z), crest_front_lz),          # crest wall front
        (to_local_y(TOP_Z), 0.0),                     # crest top, wall side
        (to_local_y(BOT_Z), 0.0),                     # wall-bottom
    )
    feature = poly_x(comp, profile, 0.0, 2.0 * X_HALF, NEW)
    plate = feature.bodies.item(0)
    plate.name = 'FIR WALL PLATE (screw to the wall; the box hangs on this)'

    # Under-floor arms: the tub floor rests 0.4mm above them (the cleat takes
    # the weight); the two M4 x 10 lock screws pull the floor down onto them.
    # Each arm root is buried 1mm into the slab for a true structural join.
    arm_ly0 = to_local_y(INTERFACE.WALL_ARM_TOP_Z)     # 0.4  (assembled Z-0.4)
    arm_ly1 = to_local_y(BOT_Z)                        # 8.4
    arm_len = INTERFACE.WALL_ARM_Y0 - INTERFACE.WALL_FACE_Y   # wall -> forward end
    for lx in INTERFACE.WALL_LOCK_X:
        box(comp, lx, (arm_ly0 + arm_ly1) / 2.0, PLATE_TH - 1.0,
            INTERFACE.WALL_ARM_W, arm_ly1 - arm_ly0,
            arm_len - PLATE_TH + 1.0, JOIN, [plate])
        # Blind pilot straight down (local -Y), opened clear above the arm's
        # top face: M4 x 10 bottoms exactly at the pilot floor with 1mm of
        # arm left under it.  Never use a longer screw.
        pilot_ly0 = arm_ly0 - 1.0
        pilot_ly1 = arm_ly0 + INTERFACE.WALL_LOCK_PILOT_DEPTH
        cyl_y(comp, lx, to_local_z(INTERFACE.WALL_LOCK_Y),
              (pilot_ly0 + pilot_ly1) / 2.0, INTERFACE.WALL_LOCK_PILOT_D,
              pilot_ly1 - pilot_ly0, CUT, [plate])

    # Wall screws: through-holes plus head pockets sunk from the FRONT face,
    # so the heads finish below the plane the tub's back wall rests on.
    for wx, wz in INTERFACE.WALL_SCREW_POS:
        cyl(comp, wx, to_local_y(wz), -1.0,
            INTERFACE.WALL_SCREW_D, PLATE_TH + 2.0, CUT, [plate])
        cyl(comp, wx, to_local_y(wz), PLATE_TH - INTERFACE.WALL_SCREW_HEAD_DEPTH,
            INTERFACE.WALL_SCREW_HEAD_D, INTERFACE.WALL_SCREW_HEAD_DEPTH + 2.0,
            CUT, [plate])
    return plate


VERSION = ('v1: wall plate + 45deg cleat (bar drops on, wedges tight, must lift '
           '{:.1f}mm to unhook) + two under-floor arms for the in-box M4 x 10 '
           'floor locks / interface {}'
           .format(INTERFACE.cleat_interlock(), INTERFACE.INTERFACE_VERSION))


def clear_old(root):
    old = [b for b in root.bRepBodies if b.name.startswith('FIR WALL PLATE')]
    for b in old:
        try:
            b.deleteMe()
        except Exception as e:
            SKIPPED.append('clear: {}'.format(e))
    return len(old)


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
        removed = clear_old(design.rootComponent)
        build(design.rootComponent)
        app.activeViewport.fit()
        ui.messageBox(
            'FIR_WallPlate {} built.\nCleared {} old body(ies).\n\n'
            'Install: level the plate, drive up to {} wall screws (4.5mm '
            'clearance, heads pocketed), hang the tub on the cleat, push it '
            'down until the back sits flat, then drive the two M4 x 10 floor '
            'locks from INSIDE the box. Cap goes on last.{}'
            .format(VERSION, removed, len(INTERFACE.WALL_SCREW_POS),
                    ('\nSkipped:\n - ' + '\n - '.join(SKIPPED)) if SKIPPED else ''))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_WallPlate failed:\n{}'.format(traceback.format_exc()))
