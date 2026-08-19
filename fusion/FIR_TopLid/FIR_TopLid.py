# FIR_TopLid.py - Autodesk Fusion 360 script
# THE DEEP TOP CAP, and nothing else (owner, 19 Aug: one script per part -
# "give me FIR bottom lid, FIR top lid, FIR curved lid" - so the cap moved
# out of FIR_Shell, which now builds only the tub).
#
# The tub is 80mm but the closed box is 120mm: this cap adds the 37mm of
# headroom the adapters and the hanging brain case need.  It prints ROOF-DOWN
# and is physically FLIPPED left/right at assembly, so every asymmetric
# feature mirrors X exactly once - the codebase's oldest trap.
#
# Tamper sensing note (owner, 19 Aug): the reed/magnet pair senses the
# CURVED LID only.  The top-cap pair that used to hang from this roof was
# removed - opening the box means removing the cover first anyway, and that
# is the event the alarm needs.

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

BOX_W = 280.0
HALF = BOX_W / 2.0
CORNER_R = 10.0
CAP_SKIRT_H = 52.0                # 15mm tub overlap + 37mm headroom
CAP_ROOF_TH = 3.0
# Brain-case attachment (shared contract): four reinforced bosses whose
# pattern derives from the case's own roof holes.
BRAIN_CAP_MOUNT = INTERFACE.CAP_BOSS_PATTERN
BRAIN_CAP_BOSS_D, BRAIN_CAP_BOSS_H = 9.0, 10.8
BRAIN_CAP_FLANGE_D, BRAIN_CAP_FLANGE_H = 13.0, 3.0
BRAIN_CAP_PILOT = 2.6
CAP_SIDE_SCREW_Y = INTERFACE.CAP_SIDE_SCREW_Y
SHOW_PARTS = False

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


def cyl_x(comp, cy, cz, xcenter, d, span, op, parts=None):
    # cylinder along X (circle on the yZ plane), symmetric about xcenter.
    # MEASURED yZ convention (FIR_PlaneProbe v3): sketch-U is world -Z,
    # sketch-V is world +Y, offset/extrude is world +X.
    sk = comp.sketches.add(comp.yZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(-cz), mm(cy), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(xcenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(xcenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def poly_x(comp, pts_yz, xcenter, span, op, parts=None):
    # closed polygon on the yZ plane, swept along X - the back lead-in wedge.
    # MEASURED yZ convention: sketch-U = world -Z, sketch-V = world +Y.
    sk = comp.sketches.add(comp.yZConstructionPlane)
    lines = sk.sketchCurves.sketchLines
    n = len(pts_yz)
    for i in range(n):
        y0, z0 = pts_yz[i]
        y1, z1 = pts_yz[(i + 1) % n]
        lines.addByTwoPoints(adsk.core.Point3D.create(mm(-z0), mm(y0), 0),
                             adsk.core.Point3D.create(mm(-z1), mm(y1), 0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(xcenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(xcenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def poly_y(comp, pts_xz, ycenter, span, op, parts=None):
    # closed polygon on the xZ plane, swept along Y - the side lead-in wedges.
    # MEASURED xZ convention: sketch-U = world +X, sketch-V = world -Z.
    sk = comp.sketches.add(comp.xZConstructionPlane)
    lines = sk.sketchCurves.sketchLines
    n = len(pts_xz)
    for i in range(n):
        x0, z0 = pts_xz[i]
        x1, z1 = pts_xz[(i + 1) % n]
        lines.addByTwoPoints(adsk.core.Point3D.create(mm(x0), mm(-z0), 0),
                             adsk.core.Point3D.create(mm(x1), mm(-z1), 0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(ycenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(ycenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def poly_z(comp, pts_xy, z0, sz, op, parts=None):
    # closed polygon on the xY plane, extruded along Z - the engraved front
    # arrow (a triangle survives the assembly mirror; text would not).
    sk = comp.sketches.add(comp.xYConstructionPlane)
    lines = sk.sketchCurves.sketchLines
    n = len(pts_xy)
    for i in range(n):
        x0, y0 = pts_xy[i]
        x1, y1 = pts_xy[(i + 1) % n]
        lines.addByTwoPoints(adsk.core.Point3D.create(mm(x0), mm(y0), 0),
                             adsk.core.Point3D.create(mm(x1), mm(y1), 0))
    return _ext(comp, sk.profiles.item(0), z0, sz, op, parts)


def fillet_corners(comp, body, r, cx=0.0, half=None, back_only=False):
    if half is None:
        half = HALF
    try:
        coll = adsk.core.ObjectCollection.create()
        for e in body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                v = g.startPoint.vectorTo(g.endPoint)
                v.normalize()
                if abs(v.z) > 0.99:
                    mx = (g.startPoint.x + g.endPoint.x) / 2.0
                    my = (g.startPoint.y + g.endPoint.y) / 2.0
                    if back_only and my > 0:
                        continue
                    if abs(abs(mx - mm(cx)) - mm(half)) < mm(2) and \
                            abs(abs(my) - mm(half)) < mm(2):
                        coll.add(e)
        if coll.count:
            fi = comp.features.filletFeatures.createInput()
            fi.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
            comp.features.filletFeatures.add(fi)
    except Exception as e:
        SKIPPED.append('corner fillet: {}'.format(e))


def build_top_lid(comp, ox=0.0):
    # Deep cap: roof plate down, skirt up; overlaps the tub 15mm (assembled
    # Z65-80), skirt rises to the roof at Z117-120.  Side bolts mid-overlap:
    # tub pilots Z72 <-> cap holes at print z LH-4.  The FRONT wall stops at
    # assembled Z83.5; below it the BottomLid + the curved cover close the
    # front, and the cover's shoulder lands FLUSH on this roof at Z120 with a
    # 0.3mm shadow line - the seamless joint.
    LW = BOX_W + 6.0          # outer - bulges out over the tub
    inner = BOX_W + 1.0       # slides over the 280 tub with clearance
    LH = CAP_SKIRT_H
    lid = box(comp, ox, 0, 0, LW, LW, CAP_ROOF_TH, NEW).bodies.item(0)
    lid.name = 'FIR TOP LID (deep cap)'
    box(comp, ox, 0, 3.0, LW, LW, LH, JOIN, [lid])                   # skirt block up
    box(comp, ox, 0, 3.0, inner, inner, LH + 2, CUT, [lid])          # hollow -> skirt walls
    fillet_corners(comp, lid, CORNER_R, ox, LW / 2.0)
    # Brain-case bosses.  PRINT-ORIENTATION WARNING: the cap is built
    # roof-DOWN and physically FLIPPED left/right on assembly - a feature at
    # cap-local +X lands at assembled -X, so the X is mirrored exactly once.
    for bx, byo in BRAIN_CAP_MOUNT:
        lx = ox - bx
        cyl(comp, lx, byo, 3.0, BRAIN_CAP_FLANGE_D, BRAIN_CAP_FLANGE_H, JOIN, [lid])
        cyl(comp, lx, byo, 3.0, BRAIN_CAP_BOSS_D, BRAIN_CAP_BOSS_H, JOIN, [lid])
        cyl(comp, lx, byo, 3.0, BRAIN_CAP_PILOT, BRAIN_CAP_BOSS_H + 1.0, CUT, [lid])
    # crush ribs: 2 sides + back, land at assembled Z73-75
    for dx, dy in ((1, 0), (-1, 0), (0, -1)):
        box(comp, ox + dx * (inner / 2 + 0.2), dy * (inner / 2 + 0.2), 3 + LH - 10,
            2 if dx else 20, 20 if dx else 2, 2.0, JOIN, [lid])
    # shorten the FRONT wall (assembled Z83.5-117); flip about the front-back
    # axis on assembly so the short wall stays at the front
    box(comp, ox, 141.75, LH - 15.5, inner, 5.5, 20, CUT, [lid])
    # 4 side screws (2 per wall at the shared rows), each in a VISIBLE 12mm
    # counterbored pad - the head seats on the original skirt face, so no
    # engagement number moved.  Rows identical on both walls = flip-safe.
    pad_h = INTERFACE.CAP_SEAT_PAD_H
    for sxs in (-1, 1):
        for byy in CAP_SIDE_SCREW_Y:
            cyl_x(comp, byy, LH - 4, ox + sxs * (LW / 2 + (pad_h - 1) / 2),
                  INTERFACE.M3_SEAT_PAD_D, pad_h + 1, JOIN, [lid])
            cyl_x(comp, byy, LH - 4, ox + sxs * (inner / 2 + 1.5), 3.4, 6, CUT, [lid])
            cyl_x(comp, byy, LH - 4, ox + sxs * (LW / 2 + pad_h),
                  INTERFACE.M3_SEAT_CBORE_D, 2 * pad_h, CUT, [lid])
    # lead-in chamfer on the skirt's lower inner edge (print top)
    ch = INTERFACE.CAP_LEADIN_CH
    top = 3.0 + LH
    for sxs in (-1, 1):
        poly_y(comp, ((ox + sxs * inner / 2, top),
                      (ox + sxs * (inner / 2 + ch), top),
                      (ox + sxs * inner / 2, top - ch)),
               0.0, inner + 4, CUT, [lid])
    poly_x(comp, ((-(inner / 2), top),
                  (-(inner / 2 + ch), top),
                  (-(inner / 2), top - ch)),
           ox, inner + 4, CUT, [lid])
    # engraved front arrow on the roof's inner face (mirror-safe)
    poly_z(comp, ((ox + 90.0, 126.0), (ox + 83.0, 112.0), (ox + 97.0, 112.0)),
           2.4, 1.0, CUT, [lid])
    # INDOOR VARIANT: 3.5" TFT window + registration seat + 2 LED holes.
    # INDOOR_SCREEN=False restores the sealed weatherproof roof untouched.
    if INTERFACE.INDOOR_SCREEN:
        scx = ox - INTERFACE.SCREEN_CX
        box(comp, scx, INTERFACE.SCREEN_CY, 3.0 - INTERFACE.SCREEN_SEAT_DEPTH,
            INTERFACE.SCREEN_PCB_W, INTERFACE.SCREEN_PCB_H,
            INTERFACE.SCREEN_SEAT_DEPTH + 1.0, CUT, [lid])     # module seat
        box(comp, scx, INTERFACE.SCREEN_CY, -1.0,
            INTERFACE.SCREEN_VIS_W, INTERFACE.SCREEN_VIS_H,
            CAP_ROOF_TH + 2.0, CUT, [lid])                     # view window
        for ledx, ledy in INTERFACE.LED_HOLES:
            cyl(comp, ox - ledx, ledy, -1.0, INTERFACE.LED_HOLE_D,
                CAP_ROOF_TH + 2.0, CUT, [lid])
        SKIPPED.append(
            'INDOOR VARIANT: roof carries the 3.5" TFT window + 2 LED holes - '
            'this cap is NOT top-rain-tight, by owner decision. '
            'INDOOR_SCREEN=False in FIR_Interface.py restores the sealed roof.')
        if not INTERFACE.SCREEN_MEASURED:
            SKIPPED.append(
                'SCREEN DIMENSIONS ARE ASSUMED (typical UNO-shield 3.5" TFT: PCB '
                '{:.1f}x{:.1f}, window {:.0f}x{:.0f}). MEASURE the real Landzo '
                'board before printing this cap - the seat and window move with it.'
                .format(INTERFACE.SCREEN_PCB_W, INTERFACE.SCREEN_PCB_H,
                        INTERFACE.SCREEN_VIS_W, INTERFACE.SCREEN_VIS_H))
    # self-click windows in the skirt (symmetric = flip-safe)
    wz0 = 120.0 - INTERFACE.CAP_SNAP_WIN_Z1
    wh = INTERFACE.CAP_SNAP_WIN_Z1 - INTERFACE.CAP_SNAP_WIN_Z0
    for sy in INTERFACE.CAP_SNAP_SIDE_Y:
        for sxs in (-1, 1):
            box(comp, ox + sxs * (LW / 2.0 - 1.5), sy, wz0,
                5.0, INTERFACE.CAP_SNAP_WIN_W, wh, CUT, [lid])
    for bx in INTERFACE.CAP_SNAP_BACK_X:
        box(comp, ox + bx, -(LW / 2.0 - 1.5), wz0,
            INTERFACE.CAP_SNAP_WIN_W, 5.0, wh, CUT, [lid])
    return lid


VERSION = ('v1 (split from FIR_Shell v42): the deep cap alone - 4 seated side '
           'screws, detent windows, lead-in chamfer, brain bosses, indoor '
           'screen window + LEDs. No top-cap tamper pair: the reed/magnet '
           'senses the CURVED LID only (owner, 19 Aug) / interface {}'
           .format(INTERFACE.INTERFACE_VERSION))


def clear_old(root):
    old = [b for b in root.bRepBodies
           if b.name.startswith(('FIR TOP LID', '=', '~'))]
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
        build_top_lid(design.rootComponent, 0.0)
        app.activeViewport.fit()
        cap_w = BOX_W + 6.0 + 2.0 * INTERFACE.CAP_SEAT_PAD_H
        SKIPPED.append(
            'PRINT ENVELOPE (Ender 3 Plus {:.0f}x{:.0f}): this cap is {:.1f}mm '
            'wide - only {:.1f}mm spare. Centre it on the bed, skip the brim.'
            .format(INTERFACE.BED_X, INTERFACE.BED_Y, cap_w,
                    INTERFACE.BED_X - cap_w))
        ui.messageBox('FIR_TopLid {} built.\nCleared {} old body(ies).{}'.format(
            VERSION, removed,
            ('\nNotes:\n - ' + '\n - '.join(SKIPPED)) if SKIPPED else ''))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_TopLid failed:\n{}'.format(traceback.format_exc()))
