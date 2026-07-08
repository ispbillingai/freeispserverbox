# FIR_OverhangTest.py - Autodesk Fusion 360 script
# QUICK overhang test: 20mm base, 20mm wall, 20mm cantilever tab. Print with NO support; if the tab
# comes out flat (not drooping), your Creality handles a 20mm hook. Small + fast (~10min).

import adsk.core, adsk.fusion, adsk.cam, traceback

REACH, WALL_H = 20.0, 20.0                 # cantilever 20mm + wall height 20mm
TAB_W, TAB_T, WALL_T = 14.0, 3.0, 4.0      # tab width + thickness, wall thickness
BASE_W, BASE_D, BASE_T = 20.0, 20.0, 4.0   # 20mm base (base = height = cantilever = 20mm)

CM = 0.1
def mm(v):
    return v * CM

NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation


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
        comp = design.rootComponent
        back = -BASE_D / 2.0                              # base back edge (-14)
        wall_front = back + WALL_T                        # wall front face (-10)
        # big base, centred (reaches forward past the tab so the piece stays planted)
        body = box(comp, 0, 0, 0, BASE_W, BASE_D, BASE_T, NEW).bodies.item(0)
        body.name = 'OVERHANG TEST 20mm (print NO support)'
        # 15mm wall at the back (overlaps the base 1mm so it merges)
        box(comp, 0, back + WALL_T / 2.0, BASE_T - 1, BASE_W, WALL_T, WALL_H - (BASE_T - 1), JOIN, [body])
        # one 20mm tab at the wall top: overlaps the wall 2mm, then juts REACH forward in mid-air
        tab_y0 = wall_front - 2.0
        tab_y1 = wall_front + REACH
        box(comp, 0, (tab_y0 + tab_y1) / 2.0, WALL_H - TAB_T, TAB_W, tab_y1 - tab_y0, TAB_T, JOIN, [body])
        app.activeViewport.fit()
        ui.messageBox('20mm overhang test built (big base). Print with NO support - '
                      'if the tab is flat, a 20mm hook prints fine.')
    except:  # noqa
        if ui:
            ui.messageBox('FIR_OverhangTest failed:\n{}'.format(traceback.format_exc()))
