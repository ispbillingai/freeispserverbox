# FIR_BoxBottom.py - Autodesk Fusion 360 script
# The BOX BOTTOM section: the bay where the RB951 lies flat (standoffs + walls), with the
# front OPEN for the port plate (FIR_PortPlate mounts there, vertical). Includes a safety
# DIVIDER WALL separating the 240V mains "dirty" strip from the router "clean" bay, and a
# reference RB951 block so you can see it fits. Mains parts (gland/MCB/terminals/PSU) get
# added once their real sizes are known - they are BOUGHT, not printed (see memory).

import adsk.core, adsk.fusion, adsk.cam, traceback

MIK_W, MIK_D, MIK_H = 114.0, 139.0, 29.0     # RB951 (port-face width x depth x height)
CLR, WALL, FLOOR = 4.0, 2.5, 2.5
ST_H, ST_D = 3.5, 7.0                          # standoff: 951 base at z=6 -> port face z=6..35
BAY_H = 42.0                                   # fits the 41mm-tall port plate (z=0..41) up the front
MAINS_W = 44.0                                 # reserved mains-compartment strip (one side)
PLATE_TH = 3.0                                 # port-plate thickness it seats against

# layout: port-plate plane at Y=0 (ports exit +Y); everything extends into -Y
MIK_FRONT_Y = -2.0
MIK_BACK_Y = MIK_FRONT_Y - MIK_D               # -141
MIK_CY = (MIK_FRONT_Y + MIK_BACK_Y) / 2.0      # -71.5
BAY_X = MIK_W / 2 + CLR                         # 61  router cavity half-width
DIV_X = BAY_X + WALL                            # 63.5  divider outer
MAINS_OUT_X = DIV_X + MAINS_W                   # 107.5 mains inner
RIGHT_X = MAINS_OUT_X + WALL                    # 110   right outer
LEFT_X = -(BAY_X + WALL)                         # -63.5 left outer
FRONT_Y = 1.0
BACK_OUT_Y = MIK_BACK_Y - CLR - WALL           # -147.5
FLOOR_CX = (LEFT_X + RIGHT_X) / 2.0
FLOOR_CY = (FRONT_Y + BACK_OUT_Y) / 2.0
FLOOR_W = RIGHT_X - LEFT_X
FLOOR_LEN = FRONT_Y - BACK_OUT_Y

CM = 0.1
def mm(v):
    return v * CM

NEW  = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation
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


def fillet_vertical(comp, body, r):
    try:
        coll = adsk.core.ObjectCollection.create()
        for e in body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                v = g.startPoint.vectorTo(g.endPoint)
                v.normalize()
                if abs(v.z) > 0.99:
                    coll.add(e)
        if coll.count:
            fi = comp.features.filletFeatures.createInput()
            fi.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
            comp.features.filletFeatures.add(fi)
    except Exception as e:
        SKIPPED.append('fillet: {}'.format(e))


def build_bottom(comp):
    floor = box(comp, FLOOR_CX, FLOOR_CY, 0, FLOOR_W, FLOOR_LEN, FLOOR, NEW).bodies.item(0)
    floor.name = '1 Box Bottom (router bay + mains strip)'
    fillet_vertical(comp, floor, 6.0)

    z = FLOOR
    # outer walls: left, right, back (front of the router bay stays OPEN for the port plate)
    box(comp, LEFT_X + WALL / 2, FLOOR_CY, z, WALL, FLOOR_LEN, BAY_H, JOIN, [floor])         # left
    box(comp, RIGHT_X - WALL / 2, FLOOR_CY, z, WALL, FLOOR_LEN, BAY_H, JOIN, [floor])        # right
    box(comp, FLOOR_CX, BACK_OUT_Y + WALL / 2, z, FLOOR_W, WALL, BAY_H, JOIN, [floor])       # back
    # DIVIDER wall - 240V mains 'dirty' strip | router 'clean' bay (safety separation)
    box(comp, BAY_X + WALL / 2, FLOOR_CY, z, WALL, FLOOR_LEN, BAY_H, JOIN, [floor])
    # mains-strip FRONT wall (only the router bay front is open)
    box(comp, (DIV_X + MAINS_OUT_X) / 2, FRONT_Y - WALL / 2, z, MAINS_W, WALL, BAY_H, JOIN, [floor])

    # router-bay standoffs (951 rests on these, lifted off the floor for airflow)
    for sx in (-(MIK_W / 2 - 6), (MIK_W / 2 - 6)):
        for sy in (MIK_FRONT_Y - 8, MIK_BACK_Y + 8):
            cyl(comp, sx, sy, z, ST_D, ST_H, JOIN, [floor])

    # PORT-PLATE SEAT: a back-stop ledge the plate seats against at the front (plate sits
    # at y = 0..PLATE_TH behind it), so its openings land on the 951 ports. Drop-in.
    box(comp, 0, FRONT_Y - PLATE_TH - 0.75, 0, 2 * BAY_X + 2 * WALL, 1.5, BAY_H, JOIN, [floor])  # bottom is floor; this is the back-stop wall
    for sx in (-(BAY_X - 1), (BAY_X - 1)):                              # side guide ribs (locate plate in X)
        box(comp, sx, FRONT_Y - PLATE_TH / 2, 0, 1.5, PLATE_TH + 1, BAY_H, JOIN, [floor])
    # SNAP CLIPS (no screws): cantilever arms rise from the back-stop and hook forward
    # over the plate's top edge - flex to drop the plate in, they snap over to retain it.
    for cx in (-42.0, 42.0):
        box(comp, cx, FRONT_Y - PLATE_TH - 0.75, 28, 9, 1.8, BAY_H - 28, JOIN, [floor])      # flex arm
        box(comp, cx, FRONT_Y - PLATE_TH / 2, BAY_H - 2.5, 9, PLATE_TH + 1.5, 2.5, JOIN, [floor])  # hook
    # cut the plate-window through that back-stop so the 951 ports reach the plate
    box(comp, 0, FRONT_Y - PLATE_TH - 0.75, 6, MIK_W + 2, 4, 30, CUT, [floor])

    # CABLE ROUTING: zip-tie slot pairs on the floor (tie the LAN/DC leads down)
    for ty in (MIK_FRONT_Y - 20, MIK_CY, MIK_BACK_Y + 20):
        box(comp, -2.5, ty, -1, 2, 9, FLOOR + 2, CUT, [floor])
        box(comp, 2.5, ty, -1, 2, 9, FLOOR + 2, CUT, [floor])
    # DC pass-through notch over the divider (router-side DC lead reaches the mains-side PSU)
    box(comp, BAY_X + WALL / 2, MIK_BACK_Y + 15, BAY_H - 9, WALL + 2, 12, 10, CUT, [floor])
    return floor


def build_reference(comp):
    mik = box(comp, 0, MIK_CY, FLOOR + ST_H, MIK_W, MIK_D, MIK_H, NEW).bodies.item(0)
    mik.name = '2 RB951 (reference - hide before print)'
    return mik


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
        build_bottom(design.rootComponent)
        build_reference(design.rootComponent)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Box bottom built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_BoxBottom failed:\n{}'.format(traceback.format_exc()))
