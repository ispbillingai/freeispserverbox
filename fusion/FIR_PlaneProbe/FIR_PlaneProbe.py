# FIR_PlaneProbe.py - Autodesk Fusion 360 script
# ONE-RUN CALIBRATION PROBE.  Not a box part.
#
# Purpose: several FIR features are built by sketching on the yZ and xZ
# construction planes and extruding sideways (the 8 cap side screws, their
# seat pads, the wall-cleat bar).  The renders suggest those land in the
# wrong place in REAL Fusion, while the offline checker - which assumes a
# particular sketch-axis convention - says they are right.  This script
# builds five small, clearly named bodies whose positions reveal Fusion's
# actual conventions.  Run it in a FRESH design, press HOME on the ViewCube,
# and screenshot the whole scene (with the ViewCube visible).
#
# What each body proves:
#   PROBE origin cube      - 20mm cube at +X+Y on the floor: view reference.
#   PROBE +X arm / +Y arm  - thin bars along +X and +Y: axis reference.
#   PROBE yZ cylinder      - drawn at sketch (60, 30), symmetric 20 about an
#                            OFFSET of 40.  Where it lands tells us what the
#                            yZ sketch axes map to and whether the offset
#                            start is honoured for symmetric extents.
#                            IF the code's assumption is right it is a 10mm-
#                            dia cylinder at Y=60, Z=30, spanning X=30..50.
#   PROBE yZ block         - rectangle sketch (80..100, 10..20) extruded +15
#                            with no offset.  Its side of the origin reveals
#                            the plane's normal direction.  Expected if the
#                            assumption is right: X=0..15, Y=80..100, Z=10..20.
#   PROBE xZ cylinder      - same idea on the xZ plane: expected at X=60,
#                            Z=30, spanning Y=30..50.
#   PROBE xZ block         - expected X=80..100, Y=0..15, Z=10..20.

import adsk.core, adsk.fusion, adsk.cam, traceback

CM = 0.1


def mm(v):
    return v * CM


NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation


def probe(comp, plane, kind, u, v, size, offset, span, symmetric, name):
    sk = comp.sketches.add(plane)
    if kind == 'circle':
        sk.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(mm(u), mm(v), 0), mm(size / 2.0))
    else:
        sk.sketchCurves.sketchLines.addCenterPointRectangle(
            adsk.core.Point3D.create(mm(u), mm(v), 0),
            adsk.core.Point3D.create(mm(u + size / 2.0), mm(v + size / 4.0), 0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), NEW)
    if abs(offset) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(offset)))
    if symmetric:
        ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    else:
        ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(span)))
    body = f.add(ei).bodies.item(0)
    body.name = name
    return body


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

        # references (xY plane is known-good)
        probe(comp, comp.xYConstructionPlane, 'rect', 10, 10, 20, 0, 20,
              False, 'PROBE origin cube (+X+Y, on the floor)')
        probe(comp, comp.xYConstructionPlane, 'rect', 45, 0, 40, 0, 6,
              False, 'PROBE +X arm')
        probe(comp, comp.xYConstructionPlane, 'rect', 0, 55, 12, 0, 6,
              False, 'PROBE +Y arm (this bar plus the long axis = +Y)')

        # the suspects
        probe(comp, comp.yZConstructionPlane, 'circle', 60, 30, 10, 40, 20,
              True, 'PROBE yZ cylinder (expected: Y60 Z30, X30..50)')
        probe(comp, comp.yZConstructionPlane, 'rect', 90, 12.5, 20, 0, 15,
              False, 'PROBE yZ block (expected: Y80..100 Z10..15, X0..15)')
        probe(comp, comp.xZConstructionPlane, 'circle', 60, 30, 10, 40, 20,
              True, 'PROBE xZ cylinder (expected: X60 Z30, Y30..50)')
        probe(comp, comp.xZConstructionPlane, 'rect', 90, 12.5, 20, 0, 15,
              False, 'PROBE xZ block (expected: X80..100 Z10..15, Y0..15)')

        app.activeViewport.fit()
        ui.messageBox(
            'FIR_PlaneProbe built 7 bodies.\n\n'
            '1. Press HOME on the ViewCube.\n'
            '2. Screenshot the WHOLE scene with the ViewCube visible.\n'
            '3. Send the screenshot.\n\n'
            'Each body name says where it is EXPECTED if the code\'s plane '
            'assumption is right (open the Bodies folder and click them). '
            'Where they ACTUALLY sit tells us how to fix the side-screw '
            'features once and for all.')
    except:  # noqa
        if ui:
            ui.messageBox('FIR_PlaneProbe failed:\n{}'.format(traceback.format_exc()))
