# FIR_TailSlices.py - Autodesk Fusion 360 script
# TAIL-END TEST SLICES (owner, 31 Aug): "the ROOF LID and the BOTTOM LID -
# cut them at the tail end, like the last eighth of both."  (Replaces the
# 21 Aug tub+cap corner pair: the tub is already printed in full, and the
# BottomLid print carries the OLD weak-joint geometry, so the two parts
# worth slicing now are the two lids.)
#
# This script builds the ACTUAL FIR_BottomLid and the ACTUAL FIR_TopLid with
# their own real builders - nothing redrawn, nothing approximated - then cuts
# each down to its KEY-END strip, roughly the last eighth of the width.  Both
# strips are the SAME assembled corner of the box (shell +X), so they test
# the same neighbourhood the owner photographed.
#
#   TAIL 1  BottomLid end strip (lid-local x <= -105, 35mm): the rail WITH
#           its new detent bumps, the 8mm shelf spine edge, the +-111 gusset,
#           the orientation KEY block, the lock boss / hard end stop, and two
#           of the six face screws.  Slide COUPON 3b (or the real cover) on:
#           it must run free, CLICK at full seat, hold, and unclick with a
#           firm pull - and the rail must feel SOLID, not wobbly.
#   TAIL 2  TopLid end strip (cap-local x <= -109, ~36mm): that side wall
#           with ALL its screw seat pads, the snap-detent windows, the
#           lead-in chamfer and the roof edge.  Drop it over the printed
#           tub's +X wall (the assembly flip lands this strip on that side):
#           slide fit, click, screws line up at Z72, and the cover shoulder
#           lands on its roof edge with the 0.3mm hairline.

import importlib.util
import os
import sys

import adsk.core, adsk.fusion, adsk.cam, traceback

LID_TAIL_XMAX = -105.0            # BottomLid: keep lid-local x <= this
                                  # (280/8 = 35mm; the key/rail end)
CAP_TAIL_XMAX = -109.0            # TopLid: keep cap-local x <= this
                                  # (~291/8; the assembly flip lands this
                                  # strip on the SAME shell +X corner)

CM = 0.1


def mm(v):
    return v * CM


CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
SKIPPED = []


def _load_active_builder(script_name):
    """Load a sibling part script exactly as FIR_ShellCheck does."""
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
        cache_name = '_freeisp_tail_' + script_name.lower()
        sys.modules.pop(cache_name, None)
        spec = importlib.util.spec_from_file_location(cache_name, path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[cache_name] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError('{} builder not found beside FIR_TailSlices'.format(script_name))


def _cut_rect(comp, body, x0, x1, y0, y1):
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchLines.addCenterPointRectangle(
        adsk.core.Point3D.create(mm((x0 + x1) / 2.0), mm((y0 + y1) / 2.0), 0),
        adsk.core.Point3D.create(mm(x1), mm(y1), 0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), CUT)
    ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(mm(-20.0)))
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(200.0)))
    ei.participantBodies = [body]
    f.add(ei)


def tail_cut(comp, body, keep_xmax):
    """Keep only the end strip x <= keep_xmax, in the part's own frame."""
    _cut_rect(comp, body, keep_xmax, 400.0, -400.0, 400.0)


def translate_body(comp, body, dx, dy, dz):
    coll = adsk.core.ObjectCollection.create()
    coll.add(body)
    matrix = adsk.core.Matrix3D.create()
    matrix.translation = adsk.core.Vector3D.create(mm(dx), mm(dy), mm(dz))
    comp.features.moveFeatures.add(comp.features.moveFeatures.createInput(coll, matrix))


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('Open a FRESH Fusion Design and run again.')
            return
        try:
            design.fusionUnitsManager.distanceDisplayUnits = \
                adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        except Exception:
            pass
        del SKIPPED[:]
        comp = design.rootComponent

        # remove earlier tail-slice runs
        for index in range(comp.bRepBodies.count - 1, -1, -1):
            b = comp.bRepBodies.item(index)
            if b.name.startswith('TAIL'):
                try:
                    b.deleteMe()
                except Exception:
                    pass

        # 1. the REAL BottomLid, cut to its key-end strip
        lid_source = _load_active_builder('FIR_BottomLid')
        del lid_source.SKIPPED[:]
        lid = lid_source.build(comp)
        tail_cut(comp, lid, LID_TAIL_XMAX)
        lid.name = ('TAIL 1: BOTTOM LID end strip (real FIR_BottomLid, '
                    'x<={:.0f}) - rail + DETENT + spine + KEY + boss + 2 screws'
                    .format(LID_TAIL_XMAX))

        # 2. the REAL top lid, cut to the matching end strip (the assembly
        #    flip lands this local -X strip on the SAME shell +X corner)
        toplid_source = _load_active_builder('FIR_TopLid')
        del toplid_source.SKIPPED[:]
        cap = toplid_source.build_top_lid(comp, 0.0)
        tail_cut(comp, cap, CAP_TAIL_XMAX)
        cap.name = ('TAIL 2: TOP LID end strip (real FIR_TopLid, local '
                    'x<={:.0f}) - side wall, screw pads, detent windows, '
                    'chamfer, roof edge'.format(CAP_TAIL_XMAX))
        translate_body(comp, cap, 330.0, 0.0, 0.0)

        app.activeViewport.fit()
        ui.messageBox(
            'FIR_TailSlices built the LAST-EIGHTH end strips of the TWO LIDS '
            '(owner, 31 Aug). Export and print them SEPARATELY: right-click '
            'a body > Save As Mesh.\n\n'
            'The tail test:\n'
            ' 1. TAIL 1 in hand: the rail must feel SOLID (8mm spine), not '
            'wobbly like the old print;\n'
            ' 2. slide COUPON 3b (or the real cover end) onto TAIL 1: free '
            'run, CLICK at full seat, holds, firm pull unclicks;\n'
            ' 3. drop TAIL 2 over the printed tub +X wall: slide fit, '
            'detents click into its windows, screws line up at Z72 through '
            'the visible pads;\n'
            ' 4. the cover shoulder must land on TAIL 2 roof edge with the '
            '0.3mm hairline.\n\n'
            'Anything that fights = one contract number + a strip reprint.')
    except:  # noqa
        if ui:
            ui.messageBox('FIR_TailSlices failed:\n{}'.format(traceback.format_exc()))
