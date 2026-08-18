# FIR_PlaneProbe.py - Autodesk Fusion 360 script
# MEASURING CALIBRATION PROBE (v2).  Not a box part.
#
# v1 asked a human to judge positions from a render - and the judgement was
# wrong, which moved the cap screw seats to the floor.  v2 does not ask
# anyone to look at anything: it builds test bodies with KNOWN sketch inputs,
# then reads each body's real bounding box back out of Fusion and prints the
# numbers.  Whatever the popup says IS the convention; no interpretation.
#
# Run in a fresh design, then send the popup text (or a screenshot of it).

import adsk.core, adsk.fusion, adsk.cam, traceback

CM = 0.1


def mm(v):
    return v * CM


NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation


def build_probe(comp, plane, u, v, dia, offset, span):
    """Circle at sketch (u, v), symmetric extrude `span` about `offset`."""
    sk = comp.sketches.add(plane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(u), mm(v), 0), mm(dia / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), NEW)
    if abs(offset) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(offset)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    return f.add(ei).bodies.item(0)


def measure(body):
    """Return (x0, x1, y0, y1, z0, z1) in mm from Fusion's own bounding box."""
    bb = body.boundingBox
    return (bb.minPoint.x / CM, bb.maxPoint.x / CM,
            bb.minPoint.y / CM, bb.maxPoint.y / CM,
            bb.minPoint.z / CM, bb.maxPoint.z / CM)


def describe(name, body, u, v, offset):
    x0, x1, y0, y1, z0, z1 = measure(body)
    cx, cy, cz = (x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0
    # Which world axis did the sketch's first coordinate (u) become?
    got = []
    for axis, centre in (('X', cx), ('Y', cy), ('Z', cz)):
        if abs(centre - u) < 0.6:
            got.append('sketch-U({:.0f}) -> world {}'.format(u, axis))
        if abs(centre - v) < 0.6:
            got.append('sketch-V({:.0f}) -> world {}'.format(v, axis))
        if abs(centre - offset) < 0.6:
            got.append('offset({:.0f}) -> world {} = extrude axis'
                       .format(offset, axis))
    return ('{}\n'
            '    sketched at U={:.0f} V={:.0f}, offset {:.0f}\n'
            '    ACTUAL centre  X{:.1f}  Y{:.1f}  Z{:.1f}\n'
            '    ACTUAL span    X[{:.1f}..{:.1f}] Y[{:.1f}..{:.1f}] Z[{:.1f}..{:.1f}]\n'
            '    => {}'
            .format(name, u, v, offset, cx, cy, cz,
                    x0, x1, y0, y1, z0, z1,
                    '; '.join(got) if got else 'NO AXIS MATCHED - report this'))


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
        comp = design.rootComponent

        lines = ['FIR_PlaneProbe v2 - MEASURED sketch-plane conventions.',
                 'Send this whole text back.', '']

        # Distinct U, V and offset values so no two can be confused.
        yz = build_probe(comp, comp.yZConstructionPlane, 60.0, 30.0, 10.0,
                         85.0, 20.0)
        yz.name = 'PROBE yZ (U60 V30 offset85)'
        lines.append(describe('yZ PLANE (used by the cap side screws, their '
                              'seat pads and the wall cleat bar)',
                              yz, 60.0, 30.0, 85.0))
        lines.append('')

        xz = build_probe(comp, comp.xZConstructionPlane, 60.0, 30.0, 10.0,
                         85.0, 20.0)
        xz.name = 'PROBE xZ (U60 V30 offset85)'
        lines.append(describe('xZ PLANE (used by the BottomLid screw pilots)',
                              xz, 60.0, 30.0, 85.0))
        lines.append('')

        xy = build_probe(comp, comp.xYConstructionPlane, 60.0, 30.0, 10.0,
                         85.0, 20.0)
        xy.name = 'PROBE xY (U60 V30 offset85)'
        lines.append(describe('xY PLANE (reference - known good)',
                              xy, 60.0, 30.0, 85.0))

        app.activeViewport.fit()
        ui.messageBox('\n'.join(lines), 'FIR_PlaneProbe v2 - measured')
    except:  # noqa
        if ui:
            ui.messageBox('FIR_PlaneProbe failed:\n{}'.format(traceback.format_exc()))
