# FIR_TailSlices.py - Autodesk Fusion 360 script
# THE SEAM PAIR (owner, 31 Aug, from the top view he circled): "this is the
# only part I want, so I can check it will fit the curved lid - it's the only
# part in connection.  One piece or two pieces, the up and down."
#
# The circled strip is where the CurvedLid's curved shoulder lands on the
# TopLid's roof edge - the seamless Ubiquiti-style joint with its one 0.3mm
# hairline.  This script builds the ACTUAL two parts with their own real
# builders and cuts each down to that connection, FULL 280mm WIDTH, because
# a curve that mates at one end and gapes at the other (FDM bow) is exactly
# what a narrow coupon would hide.
#
# Settled with the owner (31 Aug, after he showed his PRINTED BottomLid and
# PRINTED CurvedLid): "I already have this piece - where the piece will be
# bolting, that is the issue, that is what I want to see if they will fit.
# The parts we are slicing come from the TWO MAIN BIG BOXES - just 20mm of
# them."  The big boxes are the TUB and the ROOF CAP.  His printed lids are
# one side of every front joint; these strips are the OTHER side.
#
#   TAIL TUB   TUB front strip (real FIR_Shell, shell y >= 112, 25mm): the
#              floor edge, both wall stubs, the top rail, and ALL SIX
#              BottomLid seat bosses with their pilots - the piece his
#              printed BottomLid BOLTS TO.  Prints floor-down, flat.
#   TAIL ROOF  TOP LID front strip (cap-local y >= 123, 20mm of roof): the
#              roof edge his printed CurvedLid's shoulder lands on, plus the
#              short front wall that rides 0.5mm above the BottomLid's top.
#              Prints roof-down, flat.
#
# The test, with HIS printed parts:
#   1. bolt the printed BottomLid onto TAIL TUB - all 6 screws, real bosses;
#   2. slide the printed CurvedLid onto the BottomLid as normal;
#   3. offer TAIL ROOF up: its front wall rides 0.5mm above the lid's top
#      build-out, and the cover's shoulder tip lands FLUSH on its roof with
#      one even 0.3mm hairline, along the WHOLE width;
#   4. a wedge gap = FDM bow; a feelable step = flush plane; either is one
#      contract number and a strip reprint, never a big-box reprint.
#
# (Rail/detent/click micro-tests: FIR_FitCoupons pair 3.)

import importlib.util
import os
import sys

import adsk.core, adsk.fusion, adsk.cam, traceback

CAP_TAIL_YMIN = 123.0             # TopLid: keep cap-local y >= this
                                  # (roof edge at 143 -> a 20mm strip; misses
                                  # the +-85 screws and the screen window)
TUB_TAIL_YMIN = 112.0             # Tub: keep shell y >= this (25mm: floor
                                  # edge, wall stubs, top rail, and all SIX
                                  # BottomLid seat bosses + pilots at y132.5)

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


def tail_cut(comp, body, keep_ymin):
    """Keep only the strip y >= keep_ymin, in the part's own frame."""
    _cut_rect(comp, body, -400.0, 400.0, -400.0, keep_ymin)


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

        # 1. TAIL UP: the REAL top lid, cut to its front strip - the roof
        #    edge the cover's shoulder butts against
        toplid_source = _load_active_builder('FIR_TopLid')
        del toplid_source.SKIPPED[:]
        cap = toplid_source.build_top_lid(comp, 0.0)
        tail_cut(comp, cap, CAP_TAIL_YMIN)
        cap.name = ('TAIL ROOF: ROOF LID front strip (real FIR_TopLid, local '
                    'y>={:.0f}) - the roof edge + front wall the shoulder '
                    'lands on'.format(CAP_TAIL_YMIN))
        # park it just behind the tub strip, near the origin, its own body
        translate_body(comp, cap, 0.0, -173.0, 0.0)

        # 2. TAIL TUB: the REAL tub, cut to its front strip - the piece the
        #    printed BottomLid bolts onto (all six seat bosses + pilots)
        shell_source = _load_active_builder('FIR_Shell')
        del shell_source.SKIPPED[:]
        tub = shell_source.build(comp)
        tail_cut(comp, tub, TUB_TAIL_YMIN)
        tub.name = ('TAIL TUB: TUB front strip (real FIR_Shell, shell '
                    'y>={:.0f}) - floor edge + wall stubs + top rail + all '
                    '6 BottomLid bosses/pilots'.format(TUB_TAIL_YMIN))
        # centre the strip near the origin so it lands ON the slicer bed
        translate_body(comp, tub, 0.0, -124.5, 0.0)

        app.activeViewport.fit()
        ui.messageBox(
            'FIR_TailSlices built the 2 strips of the BIG BOXES your '
            'printed lids attach to (owner, 31 Aug) - both full 280mm '
            'wide, laid flat NEAR THE ORIGIN so both land on the slicer bed. '
            'Export ONE BODY AT A TIME (right-click the BODY in the browser '
            '> Save As Mesh): two files = two independent pieces to orient freely.\n\n'
            'Print: TAIL TUB floor-down flat; TAIL ROOF roof-down flat. '
            'No supports.\n\n'
            'The fit test, with YOUR printed parts:\n'
            ' 1. BOLT your printed BottomLid onto TAIL TUB - all 6 screws '
            'into real bosses; the lid frames must clear the wall stubs;\n'
            ' 2. slide your printed CurvedLid onto the BottomLid;\n'
            ' 3. offer TAIL ROOF up: front wall rides 0.5mm above the '
            'lid top, and the shoulder tip lands FLUSH on the roof with '
            'one even 0.3mm hairline, end to end;\n'
            ' 4. a wedge gap = printer bow; a feelable step = flush plane '
            'off - either is one contract number + a strip reprint.\n\n'
            '(Rail/click micro-tests: FIR_FitCoupons pair 3.)')
    except:  # noqa
        if ui:
            ui.messageBox('FIR_TailSlices failed:\n{}'.format(traceback.format_exc()))
