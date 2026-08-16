# FIR_CurvedLid.py - Autodesk Fusion 360 script
# Slide-and-lock front cover: flat port face (280 x 80), 65mm top hood and
# two end walls.  The open back seats over the BottomLid shelf.

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

# The cover's local Y is the shell Z minus this: its lower edge sits at shell
# Z=3 and its local Y=-40.  Used to line the horn window up with the BottomLid.
COVER_Y_TO_SHELL_Z = 43.0
LEN, HEIGHT, DEPTH = 280.0, 80.0, 65.0
WALL = 2.5
SKIN = 0.55
HOLE_D = 7.0
PWR_D = 7.0
NOTCH_H = 7.0
# HANDEDNESS - read before touching these numbers.
# The BottomLid is a flat plate that is turned OVER onto the tub front, so its
# source +X ends up at shell -X. This cover is not turned over: it prints face
# down and only tips up through 90 degrees about X to slide onto the shelf, so
# its source +X stays shell +X. The two parts therefore do NOT share a source
# frame, and these openings used to be written in the BottomLid's mirrored one
# - every notch landed on the wrong device. They are now written in true shell
# X. No notch size and no physical position changed; only the sign is fixed.
#   MikroTik (shell +X): five LAN notches under its measured RJ45 columns.
#   Tenda switch (shell -X): five cable notches under its 68.8mm service slot.
RJ45_X = [90.5, 76.5, 62.5, 48.5, 34.5, -53.0, -69.0, -85.0, -101.0, -117.0]
# Dedicated cable-route centreline. It matches BottomLid's 10mm pass-through,
# which sits at shell X=-10 once that plate is turned over.
POWER_CABLE_X = -10.0

# The rails guide the cover. The two front M3 screws are the positive lock;
# there is no pretend snap/detent feature in this part.
CLR = 0.4
RAIL_X = 133.0
SHELF_TOP_Y = -HEIGHT / 2.0
RAIL_TOP_Y = SHELF_TOP_Y + 5.0
TZ0, TZ1 = WALL, DEPTH - 2.0

# BottomLid groove: 250.0mm long x 1.6mm wide x 1.0mm deep. The tongue is
# only a locator, so it deliberately leaves 0.5mm at each X end and 0.3mm
# at the groove root for a printable slide.
TONGUE_LEN, TONGUE_W, TONGUE_D = 249.0, 1.0, 0.7

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


def build(comp):
    """Build the printable cover and return its body.

    FIR_ShellCheck imports this exact builder for a physical all-up closure
    inspection. Keep printable cover geometry here rather than duplicating it.
    """
    # Front face lies on Z=0 so the port notches cut reliably through it.
    front = box(comp, 0, 0, 0, LEN, HEIGHT, WALL, NEW).bodies.item(0)
    front.name = 'FIR Lid Cover (4 sides)'
    depth = (WALL - SKIN) + 1.0
    bottom = -HEIGHT / 2.0
    top_y = bottom + NOTCH_H

    def notch(cx, width):
        # An arch notch opens at the face's lower edge and retains a pop-out skin.
        box(comp, cx, (bottom - 2.0 + top_y) / 2.0, -1.0, width,
            top_y - (bottom - 2.0), depth, CUT, [front])
        cyl(comp, cx, top_y, -1.0, width, depth, CUT, [front])

    for rx in RJ45_X:
        notch(rx, HOLE_D)
    notch(POWER_CABLE_X, PWR_D)

    # ALARM HORN sound window: the same slots the BottomLid carries, so the
    # two line up once the cover is slid home.  Without this the sound would
    # only reach the 65mm hood cavity and stop there.
    for gz0, gz1 in INTERFACE.horn_grille_slots():
        cy = (gz0 + gz1) / 2.0 - COVER_Y_TO_SHELL_Z
        box(comp, INTERFACE.HORN_GRILLE_CX, cy, -1.0,
            INTERFACE.HORN_GRILLE_W, gz1 - gz0, WALL + 2.0, CUT, [front])

    # Top wall and its tolerant locating tongue.
    box(comp, 0, HEIGHT / 2.0 - WALL / 2.0, 0, LEN, WALL, DEPTH, JOIN, [front])
    box(comp, 0, 38.5, DEPTH, TONGUE_LEN, TONGUE_W, TONGUE_D, JOIN, [front])

    # Two end walls run back from the front face.
    for sx in (-LEN / 2.0 + WALL / 2.0, LEN / 2.0 - WALL / 2.0):
        box(comp, sx, 0, 0, WALL, HEIGHT, DEPTH, JOIN, [front])

    # Sliding inverted-U rail guides: 0.3mm side/top clearance on each rail.
    half = 2.0 + 0.3
    rib_w = 1.6
    rib_cy = (SHELF_TOP_Y + RAIL_TOP_Y + 0.3) / 2.0
    rib_h = (RAIL_TOP_Y + 0.3) - SHELF_TOP_Y
    for side in (-1, 1):
        sx = side * RAIL_X
        box(comp, sx, RAIL_TOP_Y + 1.8, TZ0, 2.0 * (half + rib_w),
            3.0, TZ1 - TZ0, JOIN, [front])
        for off in (-(half + rib_w / 2.0), half + rib_w / 2.0):
            box(comp, sx + off, rib_cy, TZ0, rib_w, rib_h, TZ1 - TZ0,
                JOIN, [front])

    # Slide fully home, then drive two M3 screws through the front face into
    # the BottomLid shelf bosses.
    for sx in (-125, 125):
        cyl(comp, sx, -31.0, -1.0, 3.4, WALL + 2.0, CUT, [front])
    return front


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
        build(design.rootComponent)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Cover built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_CurvedLid failed:\n{}'.format(traceback.format_exc()))
