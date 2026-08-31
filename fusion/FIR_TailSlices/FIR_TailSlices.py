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
#   TAIL UP    TopLid front strip (cap-local y >= 105, ~38mm deep): the roof
#              edge the shoulder butts against, the short front wall and the
#              lead-in chamfer.  Prints roof-down, flat, no supports.
#   TAIL DOWN  CurvedLid top strip (cover-local y >= 20): the upper face
#              band, the top wall, the locator tabs and the ENTIRE curved
#              shoulder.  Print STANDING ON AN END WALL exactly like the
#              full cover - same walls, same curve, quarter of the plastic.
#
# The test: stand TAIL DOWN against TAIL UP the way the closed box holds
# them.  The shoulder tip must land FLUSH with the roof's outer surface and
# butt its edge with the 0.3mm hairline - along the WHOLE width, both ends
# and the middle.  A wedge-shaped gap = bow; a step = the flush plane is
# off; either way it is one contract number and a strip reprint, not a
# 280mm cover reprint.
#
# (The rail / detent / click tests live in FIR_FitCoupons pair 3.)

import importlib.util
import os
import sys

import adsk.core, adsk.fusion, adsk.cam, traceback

CAP_TAIL_YMIN = 105.0             # TopLid: keep cap-local y >= this
                                  # (roof edge at 143; ~38mm strip - misses
                                  # the +-85 screws and the screen window)
COVER_TAIL_YMIN = 20.0            # CurvedLid: keep cover-local y >= this
                                  # (face band + top wall + tabs + the whole
                                  # shoulder; channels/knockouts/magnet stay
                                  # out - they are not this joint)

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
        cap.name = ('TAIL UP: TOP LID front strip (real FIR_TopLid, local '
                    'y>={:.0f}) - the roof edge + front wall the shoulder '
                    'lands on'.format(CAP_TAIL_YMIN))

        # 2. TAIL DOWN: the REAL curved cover, cut to its top strip - the
        #    entire shoulder, full 280 width
        cover_source = _load_active_builder('FIR_CurvedLid')
        del cover_source.SKIPPED[:]
        cover = cover_source.build(comp)
        tail_cut(comp, cover, COVER_TAIL_YMIN)
        cover.name = ('TAIL DOWN: CURVED LID top strip (real FIR_CurvedLid, '
                      'local y>={:.0f}) - face band + top wall + the whole '
                      'curved shoulder'.format(COVER_TAIL_YMIN))
        translate_body(comp, cover, 0.0, -160.0, 0.0)

        app.activeViewport.fit()
        ui.messageBox(
            'FIR_TailSlices built the SEAM PAIR - the up and down of the one '
            'joint the curved lid makes with the roof, both FULL 280mm wide '
            '(owner, 31 Aug). Export and print them SEPARATELY: right-click '
            'a body > Save As Mesh.\n\n'
            'Print: TAIL UP roof-down flat; TAIL DOWN standing on an end '
            'wall, exactly like the full cover.\n\n'
            'The seam test:\n'
            ' 1. hold TAIL DOWN against TAIL UP as the closed box would;\n'
            ' 2. the shoulder tip must finish FLUSH with the roof outer '
            'surface (no step you can feel with a nail);\n'
            ' 3. one even 0.3mm hairline along the WHOLE width - a wedge '
            'gap means FDM bow, a step means the flush plane is off;\n'
            ' 4. rail/click testing is COUPON PAIR 3, not this pair.\n\n'
            'Anything that fights = one contract number + a strip reprint, '
            'never a full 280mm cover reprint.')
    except:  # noqa
        if ui:
            ui.messageBox('FIR_TailSlices failed:\n{}'.format(traceback.format_exc()))
