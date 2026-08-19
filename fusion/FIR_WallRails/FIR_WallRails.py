# FIR_WallRails.py - Autodesk Fusion 360 script
# The two rails the box HANGS on.  Print both at once, flat, no supports.
#
# Why rails and not a plate: a 274 x 274 backing plate is a ~250g print that
# warps on a big bed.  Two 55mm rails carry the same load, print in about an
# hour, and can be levelled independently.
#
# How the mount works:
#   1. screw the TOP rail to the wall (three M5/#10, heads countersunk flush
#      so the box lies flat against it), then the BOTTOM rail 231mm below it;
#   2. offer the box up so the two studs pass through the big round ends of
#      the keyholes in its floor, then let it DROP 20mm - the stud heads are
#      now trapped behind the floor and the box hangs on its own;
#   3. drive two M4 screws through the top rail's upstand into the bosses
#      inside the tub's back wall.  Now it cannot be lifted off.
# Both of those screws are driven from OUTSIDE, with the box closed - which
# is the whole point: the box comes off the wall without being opened.
#
# LOCAL PRINT FRAME: local X = shell X, local Y = shell Y, local Z = out of
# the wall.  The rails are drawn where they actually sit relative to the box,
# so FIR_ShellCheck can show them without moving anything.

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


def cyl_y(comp, cx, cz, ycenter, d, span, op, parts=None):
    # cylinder along Y (circle on the xZ plane).  MEASURED xZ convention
    # (FIR_PlaneProbe v3): sketch-U is world +X, sketch-V is world -Z.
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cx), mm(-cz), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(ycenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(ycenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def wall_screws(comp, rail, cy):
    """Three wall screws in a rail, heads countersunk flush with its face."""
    for sx in INTERFACE.RAIL_SCREW_X:
        cyl(comp, sx, cy, -1.0, INTERFACE.RAIL_SCREW_D,
            INTERFACE.RAIL_TH + 2.0, CUT, [rail])
        # head pocket, opening toward the BOX so nothing stands proud
        cyl(comp, sx, cy, INTERFACE.RAIL_TH - 3.0,
            INTERFACE.RAIL_SCREW_HEAD_D, 3.0 + 1.0, CUT, [rail])
    return


def build_top_rail(comp):
    """The rail that carries the weight: two studs plus the anti-lift upstand."""
    cy = INTERFACE.RAIL_TOP_Y + INTERFACE.RAIL_H / 2.0
    rail = box(comp, 0.0, cy, 0.0, INTERFACE.RAIL_W, INTERFACE.RAIL_H,
               INTERFACE.RAIL_TH, NEW).bodies.item(0)
    rail.name = 'FIR WALL RAIL - TOP (studs + anti-lift; screw this one first)'
    wall_screws(comp, rail, cy)

    # Studs: shaft stands the head off far enough to sit in the floor's
    # counterbore, with 0.4mm of slide clearance behind the floor.
    stand = INTERFACE.stud_standoff()
    for hx, hy in INTERFACE.KEYHOLE_XY:
        cyl(comp, hx, hy, INTERFACE.RAIL_TH, INTERFACE.STUD_SHAFT_D,
            stand, JOIN, [rail])
        cyl(comp, hx, hy, INTERFACE.RAIL_TH + stand, INTERFACE.STUD_HEAD_D,
            INTERFACE.STUD_HEAD_TH, JOIN, [rail])

    # Anti-lift upstand along the rail's top edge, standing out of the wall,
    # with two clearance holes for the M4 screws that go into the tub's back
    # wall bosses.
    up_y = INTERFACE.RAIL_TOP_Y + INTERFACE.PLATE_UPSTAND_TH / 2.0
    box(comp, 0.0, up_y, INTERFACE.RAIL_TH, INTERFACE.RAIL_W,
        INTERFACE.PLATE_UPSTAND_TH, INTERFACE.PLATE_UPSTAND_H, JOIN, [rail])
    for ax in INTERFACE.ANTILIFT_X:
        cyl_y(comp, ax, INTERFACE.RAIL_TH + INTERFACE.ANTILIFT_Z, up_y,
              4.5, INTERFACE.PLATE_UPSTAND_TH + 4.0, CUT, [rail])
    return rail


def build_bottom_rail(comp):
    """A plain spacer of identical thickness: keeps the box square to the wall."""
    cy = INTERFACE.RAIL_BOTTOM_Y + INTERFACE.RAIL_H / 2.0
    rail = box(comp, 0.0, cy, 0.0, INTERFACE.RAIL_W, INTERFACE.RAIL_H,
               INTERFACE.RAIL_TH, NEW).bodies.item(0)
    rail.name = 'FIR WALL RAIL - BOTTOM (plain spacer, no studs)'
    wall_screws(comp, rail, cy)
    return rail


VERSION = ('v1: two wall rails - top carries 2 studs + the anti-lift upstand, '
           'bottom is a plain spacer. Rail pitch {:.0f}mm, stud travel {:.0f}mm '
           '/ interface {}'
           .format(INTERFACE.RAIL_BOTTOM_Y - INTERFACE.RAIL_TOP_Y,
                   INTERFACE.KEY_TRAVEL, INTERFACE.INTERFACE_VERSION))


def clear_old(root):
    old = [b for b in root.bRepBodies if b.name.startswith('FIR WALL RAIL')]
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
        build_top_rail(design.rootComponent)
        build_bottom_rail(design.rootComponent)
        app.activeViewport.fit()
        ui.messageBox(
            'FIR_WallRails {} built.\nCleared {} old body(ies).\n\n'
            'INSTALL: screw the TOP rail to the wall (3 x M5, heads sink flush), '
            'then the BOTTOM rail exactly {:.0f}mm below it. Offer the box up so '
            'the two studs pass through the round ends of the keyholes in its '
            'floor, let it DROP {:.0f}mm - it now hangs by itself - then drive '
            'the two M4 anti-lift screws through the top upstand into the back '
            'wall. To take the box down: undo those two screws, lift {:.0f}mm, '
            'pull off. The box never has to be opened.{}'
            .format(VERSION, removed,
                    INTERFACE.RAIL_BOTTOM_Y - INTERFACE.RAIL_TOP_Y,
                    INTERFACE.KEY_TRAVEL, INTERFACE.KEY_TRAVEL,
                    ('\nSkipped:\n - ' + '\n - '.join(SKIPPED)) if SKIPPED else ''))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_WallRails failed:\n{}'.format(traceback.format_exc()))
