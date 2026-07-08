# FIR_Mikrotik.py - Autodesk Fusion 360 script
# A model of the RB951 MikroTik router: 114(W) x 139(D) x 29(H), with its MEASURED port face
# (DC jack, reset, PWR/ACT LEDs, 5 RJ45) recessed into the +Y face. Own frame: X centred (±57),
# Y centred (±69.5), Z = height (0..29, base at 0). Port face faces +Y. Used to assemble + verify
# the ports line up with the bottom lid + the shell cradle. Run ALONE, or it is rebuilt inside
# FIR_ShellCheck for the alignment view.

import adsk.core, adsk.fusion, adsk.cam, traceback

MW, MD, MH = 114.0, 139.0, 29.0
# measured ports: (kind, x-from-left-edge, z-from-base, a, b)
PORTS = [('c', 11, 15, 6.5, 0), ('c', 19, 10, 2.5, 0), ('r', 25, 9.5, 4, 3), ('r', 33, 9.5, 4, 3),
         ('r', 44.5, 16, 13.5, 12.5), ('r', 58.5, 16, 13.5, 12.5), ('r', 72.5, 16, 13.5, 12.5),
         ('r', 86.5, 16, 13.5, 12.5), ('r', 100.5, 16, 13.5, 12.5)]

CM = 0.1
def mm(v):
    return v * CM

NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
SKIPPED = []


def box(comp, cx, cy, z0, sx, sy, sz, op, parts=None):
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.sketchCurves.sketchLines.addCenterPointRectangle(
        adsk.core.Point3D.create(mm(cx), mm(cy), 0),
        adsk.core.Point3D.create(mm(cx + sx / 2.0), mm(cy + sy / 2.0), 0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(z0) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(z0)))
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(sz)))
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def yport(comp, body, cx, cz, kind, a, b, y_face, depth):
    # recess a port into the +Y face (sketch on xZ plane, cut -Y by depth)
    try:
        sk = comp.sketches.add(comp.xZConstructionPlane)
        if kind == 'c':
            sk.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(mm(cx), mm(cz), 0), mm(a / 2.0))
        else:
            sk.sketchCurves.sketchLines.addCenterPointRectangle(
                adsk.core.Point3D.create(mm(cx), mm(cz), 0),
                adsk.core.Point3D.create(mm(cx + a / 2.0), mm(cz + b / 2.0), 0))
        f = comp.features.extrudeFeatures
        ei = f.createInput(sk.profiles.item(0), CUT)
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(y_face)))
        ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(depth)), True)
        ei.participantBodies = [body]
        f.add(ei)
    except Exception as e:
        SKIPPED.append('port: {}'.format(e))


def build_mikrotik(comp, ox=0.0, oy=0.0, oz=0.0, flipx=False):
    # ox,oy,oz = where to place the device's centre/base; flipx mirrors the port order in X
    s = -1.0 if flipx else 1.0
    body = box(comp, ox, oy, oz, MW, MD, MH, NEW).bodies.item(0)
    body.name = 'RB951 MikroTik'
    y_face = oy + MD / 2.0                                  # the +Y port face
    for (k, x, z, a, b) in PORTS:
        cx = ox + s * (-MW / 2.0 + x)                      # x from the (left) edge of the port face
        yport(comp, body, cx, oz + z, k, a, b, y_face, 5.0)
    return body


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
        build_mikrotik(design.rootComponent)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('MikroTik built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_Mikrotik failed:\n{}'.format(traceback.format_exc()))
