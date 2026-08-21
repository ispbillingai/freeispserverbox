# FIR_TailSlices.py - Autodesk Fusion 360 script
# TAIL-END TEST SLICES OF THE REAL PARTS (owner, 21 Aug): "print the whole
# box, then slice the last tenth - as easy as that, not just parts."
#
# This script builds the ACTUAL tub (FIR_Shell) and the ACTUAL top lid
# (FIR_TopLid) with their own real builders - nothing redrawn, nothing
# approximated - then cuts away everything except the BOTTOM-END strip
# (shell Y >= 70, the last ~70mm where the whole front closure lives).
# Print the two slices plus the REAL FIR_BottomLid and the REAL FIR_CurvedLid
# and you can assemble and close the entire busy bottom end:
#
#   1. screw the real BottomLid onto the TUB TAIL - all SIX bosses are in
#      the slice, so every screw is tested;
#   2. slide the real CurvedLid home on its rails, click, lock;
#   3. drop the TOP LID TAIL over the tub wall: 0.5mm slide fit, chamfer
#      lead-in, and its two Y+85 screws must line up at Z72 through the
#      visible pads;
#   4. the cover's shoulder must land on the cap tail's roof edge with the
#      0.3mm hairline - the seamless joint, tested for real.
#
# The screen window and LED holes also land inside the cap slice, so the
# Landzo module can be trial-fitted once it is measured.
# Because both slices are cut at the SAME shell line, they correspond to the
# same region of the assembled box and mate exactly like the full parts.

import importlib.util
import os
import sys

import adsk.core, adsk.fusion, adsk.cam, traceback

TAIL_KEEP_Y = 70.0                # keep shell Y >= this; everything else goes

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


def tail_cut(comp, body):
    """Cut away everything below the keep-line, in the part's own frame."""
    sk = comp.sketches.add(comp.xYConstructionPlane)
    # a huge rectangle over everything with y < TAIL_KEEP_Y
    sk.sketchCurves.sketchLines.addCenterPointRectangle(
        adsk.core.Point3D.create(0, mm((TAIL_KEEP_Y - 400.0) / 2.0), 0),
        adsk.core.Point3D.create(mm(250.0), mm(TAIL_KEEP_Y), 0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), CUT)
    ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(mm(-20.0)))
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(200.0)))
    ei.participantBodies = [body]
    f.add(ei)


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

        # 1. the REAL tub, then the tail cut
        shell_source = _load_active_builder('FIR_Shell')
        del shell_source.SKIPPED[:]
        tub = shell_source.build(comp)
        tail_cut(comp, tub)
        tub.name = ('TAIL 1: TUB bottom end (real FIR_Shell, kept Y>={:.0f}) '
                    '- all 6 BottomLid bosses + both Y85 cap bosses'
                    .format(TAIL_KEEP_Y))

        # 2. the REAL top lid, then the same cut (its print frame keeps the
        #    front at +Y, so the same line slices the same assembled region)
        toplid_source = _load_active_builder('FIR_TopLid')
        del toplid_source.SKIPPED[:]
        cap = toplid_source.build_top_lid(comp, 0.0)
        tail_cut(comp, cap)
        cap.name = ('TAIL 2: TOP LID bottom end (real FIR_TopLid, kept '
                    'Y>={:.0f}) - seat pads, screen window, front wall'
                    .format(TAIL_KEEP_Y))
        translate_body(comp, cap, 330.0, 0.0, 0.0)

        app.activeViewport.fit()
        ui.messageBox(
            'FIR_TailSlices built 2 REAL tail slices (cut at shell Y{:.0f}).\n\n'
            'Print these two plus the REAL FIR_BottomLid and REAL FIR_CurvedLid, '
            'then close the whole bottom end:\n'
            ' 1. screw the BottomLid onto TAIL 1 - all six screws;\n'
            ' 2. slide the CurvedLid home - click, flush stop, lock screws;\n'
            ' 3. drop TAIL 2 over the wall - slide fit + two Y85 screws at Z72;\n'
            ' 4. the cover shoulder must land on TAIL 2\'s roof edge with the '
            '0.3mm hairline.\n\n'
            'Anything that fights = one contract number + a reprint of a slice, '
            'never a full 280mm part.')
    except:  # noqa
        if ui:
            ui.messageBox('FIR_TailSlices failed:\n{}'.format(traceback.format_exc()))
