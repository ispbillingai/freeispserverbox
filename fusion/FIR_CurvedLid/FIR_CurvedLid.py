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
# Z=3 and its local Y=-40.  Keep it written down - the handedness fault came
# from exactly this kind of undocumented frame mapping.
COVER_Y_TO_SHELL_Z = 43.0
# No alarm-horn vents here either: see HORN_VENTS in the shared contract.
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
MIKROTIK_LAN_X = [90.5, 76.5, 62.5, 48.5, 34.5]
RJ45_X = MIKROTIK_LAN_X + list(INTERFACE.poe_cable_notch_x())
# Dedicated cable-route centreline. It matches BottomLid's 10mm pass-through,
# which sits at shell X=-10 once that plate is turned over.
POWER_CABLE_X = -10.0

# The rails guide the cover. The two front M3 screws are the positive lock;
# there is no pretend snap/detent feature in this part.
# The slide interface (rail position, the ONE clearance value, the key and
# the anti-rattle nubs) is shared contract data: a reviewer caught this file
# declaring CLR=0.4 while hard-coding 0.3 in the rail maths - two competing
# values for one physical gap.  Now there is exactly one, in FIR_Interface.
CLR = INTERFACE.COVER_RAIL_CLR
RAIL_X = INTERFACE.COVER_RAIL_X
SHELF_TOP_Y = -HEIGHT / 2.0
RAIL_TOP_Y = SHELF_TOP_Y + INTERFACE.COVER_RAIL_H
TZ0, TZ1 = WALL, DEPTH - 2.0

# BottomLid groove: 250.0mm long x 1.6mm wide x 1.0mm deep. The locator used
# to be one continuous 249mm tongue; over that length FDM shrink/bow can jam
# a 0.3mm slide, so it is now three short tabs on the same line (reviewer
# agreed).  Same width, depth and clearances.
TONGUE_W, TONGUE_D = 1.0, 0.7

CM = 0.1


def mm(v):
    return v * CM


NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
SKIPPED = []

VERSION = ('v4: TAMPER MAGNET pocket (D12.05 press fit, hidden 1.2mm behind the '
           'face at shell X+15) + ONE shared rail clearance ({}mm), 4 locator '
           'tabs, anti-rattle nubs, and the +X channel key relief so a reversed '
           'cover refuses to seat / interface {}'
           .format(INTERFACE.COVER_RAIL_CLR, INTERFACE.INTERFACE_VERSION))


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

    # Top wall and its tolerant locating tabs (three short, not one long).
    box(comp, 0, HEIGHT / 2.0 - WALL / 2.0, 0, LEN, WALL, DEPTH, JOIN, [front])
    for tx in INTERFACE.COVER_TAB_X:
        box(comp, tx, 38.5, DEPTH, INTERFACE.COVER_TAB_LEN, TONGUE_W,
            TONGUE_D, JOIN, [front])

    # Two end walls run back from the front face.
    for sx in (-LEN / 2.0 + WALL / 2.0, LEN / 2.0 - WALL / 2.0):
        box(comp, sx, 0, 0, WALL, HEIGHT, DEPTH, JOIN, [front])

    # Sliding inverted-U rail guides: CLR side/top clearance on each rail.
    half = INTERFACE.COVER_RAIL_W / 2.0 + CLR
    rib_w = INTERFACE.COVER_CHANNEL_RIB_W
    rib_cy = (SHELF_TOP_Y + RAIL_TOP_Y + CLR) / 2.0
    rib_h = (RAIL_TOP_Y + CLR) - SHELF_TOP_Y
    web_cy = RAIL_TOP_Y + CLR + 1.5
    for side in (-1, 1):
        sx = side * RAIL_X
        box(comp, sx, web_cy, TZ0, 2.0 * (half + rib_w),
            3.0, TZ1 - TZ0, JOIN, [front])
        for off in (-(half + rib_w / 2.0), half + rib_w / 2.0):
            box(comp, sx + off, rib_cy, TZ0, rib_w, rib_h, TZ1 - TZ0,
                JOIN, [front])
        # Anti-rattle nub under the web: 0.15mm bite into the rail top over
        # 5mm, engaging only near full seat so the slide stays free.  The +X
        # nub sits below the key relief so the relief cannot delete it.
        nub_z0 = 46.0 if side > 0 else 57.0
        nub_h = CLR + INTERFACE.COVER_NUB_PROUD
        box(comp, sx, RAIL_TOP_Y + (CLR - INTERFACE.COVER_NUB_PROUD) / 2.0,
            nub_z0, 6.0, nub_h, INTERFACE.COVER_NUB_LEN, JOIN, [front])
    # ORIENTATION KEY relief: shorten the +shell-X channel web at its tub end
    # so it clears the BottomLid's key block.  A reversed cover presents its
    # UNrelieved web to the block and stops ~7mm proud with the lock seats
    # visibly open - the part refuses to assemble backwards.
    box(comp, RAIL_X, web_cy + 0.1, TZ1 - INTERFACE.COVER_KEY_RELIEF_LEN,
        2.0 * (half + rib_w) + 0.4, 3.4,
        INTERFACE.COVER_KEY_RELIEF_LEN + 1.0, CUT, [front])

    # Slide fully home, then drive two M3 screws through the front face into
    # the BottomLid shelf bosses.  These are the outermost screws on the whole
    # box and were invisible flush holes; each now sits in a 10mm dished seat
    # 1.0mm into the face (this part prints FACE-DOWN, so a proud pad would
    # lift it off the bed - a recess is the printable version of the same
    # visual cue).  1.5mm of face is left under the head.
    for sx in (-INTERFACE.COVER_LOCK_X, INTERFACE.COVER_LOCK_X):
        cyl(comp, sx, -31.0, -1.0, INTERFACE.COVER_SEAT_D,
            INTERFACE.COVER_SEAT_DEPTH + 1.0, CUT, [front])
        cyl(comp, sx, -31.0, -1.0, 3.4, WALL + 2.0, CUT, [front])

    # TAMPER MAGNET (owner, 18 Aug): a 16x16 pad on the inner face carries a
    # press-fit pocket for the measured D12.1 disc magnet, pressed in from
    # the inside - the pocket floor keeps 1.2mm of face, so nothing shows
    # outside.  At shell X+15 the closed cover holds the magnet head-on at
    # ~10.6mm from the reed recessed in the BottomLid shelf; the pad bottom
    # sweeps 0.5mm above the reed on its way in.  BENCH-TEST the actual
    # reed+magnet pair at that distance before printing.
    box(comp, INTERFACE.REED_X, INTERFACE.MAGNET_CY, WALL,
        INTERFACE.MAGNET_PAD_SQ, INTERFACE.MAGNET_PAD_SQ,
        INTERFACE.MAGNET_PAD_H, JOIN, [front])
    cyl(comp, INTERFACE.REED_X, INTERFACE.MAGNET_CY,
        INTERFACE.MAGNET_POCKET_FLOOR, INTERFACE.MAGNET_POCKET_D,
        WALL + INTERFACE.MAGNET_PAD_H, CUT, [front])
    if not INTERFACE.MAGNET_TH_MEASURED:
        SKIPPED.append(
            'magnet THICKNESS is ASSUMED {:.1f}mm (diameter 12.1 is measured). '
            'Measure it: the pocket floor moves with it.'
            .format(INTERFACE.MAGNET_TH))
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
        # ALWAYS report the version so a stale %APPDATA% deploy shows itself.
        ui.messageBox('FIR_CurvedLid {} built.{}'.format(
            VERSION, ('\nSkipped:\n - ' + '\n - '.join(SKIPPED)) if SKIPPED else ''))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_CurvedLid failed:\n{}'.format(traceback.format_exc()))
