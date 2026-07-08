# FIR_Mini.py - Autodesk Fusion 360 script
# A SCALED snap-together miniature of the whole 280x280 box WITH A DEDICATED SEAT for every
# component, so you can see each thing has a tight home it just drops into. 1mm walls = fast.
# Bodies named 'fit ...' are the scaled components shown nested in their seats (hide them to
# see the empty seats). All printed parts laid flat for one print.

import adsk.core, adsk.fusion, adsk.cam, traceback

SCALE = 0.25
def s(v):
    return v * SCALE

WALL = 1.0
SNAP = 1.4
POST = 2.0                                   # seat post size (kept ~real so it prints)

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


def cap4(comp, floor, ox, oy, cx, cy, sx, sy, h):
    # 4 corner-capture posts forming a tight seat around a (scaled) footprint
    for dx in (-1, 1):
        for dy in (-1, 1):
            box(comp, ox + s(cx) + dx * (s(sx) / 2 + POST / 2 + 0.3),
                oy + s(cy) + dy * (s(sy) / 2 + POST / 2 + 0.3), 1.0, POST, POST, h, JOIN, [floor])


def build_shell(comp, ox, oy):
    W, D, H = s(280), s(280), s(95)
    FRONT = s(137)
    floor = box(comp, ox, oy, 0, W, D, 1.0, NEW).bodies.item(0)
    floor.name = 'MINI 1 shell + SEATS'
    fillet_vertical(comp, floor, 3.0)
    # outer walls (1mm) - front kept low so you can see/insert
    box(comp, ox - W / 2 + WALL / 2, oy, 1.0, WALL, D, H, JOIN, [floor])
    box(comp, ox + W / 2 - WALL / 2, oy, 1.0, WALL, D, H, JOIN, [floor])
    box(comp, ox, oy - D / 2 + WALL / 2, 1.0, W, WALL, H, JOIN, [floor])
    box(comp, ox, oy + D / 2 - WALL / 2, 1.0, W, WALL, s(20), JOIN, [floor])   # low front lip
    # AC/DC divider (front DC | back AC)
    box(comp, ox, oy + s(-82), 1.0, W - 2 * WALL, WALL, H * 0.65, JOIN, [floor])

    # === SEATS (a tight home for each component) ===
    cap4(comp, floor, ox, oy, -78, 65.5, 114, 139, s(20))     # RB951 seat
    cap4(comp, floor, ox, oy, 60, 85.5, 100, 100, s(20))      # PoE seat
    for ex in (-123, 123):                                    # extension end-clamp seat
        box(comp, ox + s(ex), oy + s(-110), 1.0, POST, s(47), s(20), JOIN, [floor])
    cyl(comp, ox + s(95), oy + s(-60), 1.0, s(78), s(14), JOIN, [floor])       # siren ring seat
    cyl(comp, ox + s(95), oy + s(-60), 0.5, s(70), s(16), CUT, [floor])
    for bx in (-58.5, 58.5):                                  # brain shelf pillars
        for byo in (-50, 50):
            cyl(comp, ox + s(-5 + bx), oy + s(75.5 + byo), 1.0, 2.6, s(45), JOIN, [floor])
    # 951 + PoE PORT-PLATE seats (side rails at the front -> plate clicks in)
    for sx in (-78 - 63, -78 + 63):
        box(comp, ox + s(sx), oy + FRONT - 1, 1.0, POST, 2.0, s(42), JOIN, [floor])
    for sx in (60 - 52, 60 + 52):
        box(comp, ox + s(sx), oy + FRONT - 1, 1.0, POST, 2.0, s(38), JOIN, [floor])
    # 4 lid-snap recesses on the rim
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        box(comp, ox + dx * (W / 2 - WALL / 2), oy + dy * (D / 2 - WALL / 2),
            H - 4, SNAP + 3, SNAP + 3, 2.0, CUT, [floor])
    return floor


def build_fit(comp, ox, oy):
    # scaled components nested in their seats (hide these to see empty seats)
    def f(name, cx, cy, z, sx, sy, sz):
        box(comp, ox + s(cx), oy + s(cy), z, s(sx), s(sy), s(sz), NEW).bodies.item(0).name = name
    f('fit RB951', -78, 65.5, 1.0 + s(3.5), 114, 139, 29)
    f('fit PoE', 60, 85.5, 1.0 + s(3.5), 100, 100, 28)
    f('fit extension', 0, -110, 1.0, 240, 47, 28)
    for ax in (-80, 0, 80):
        f('fit adapter', ax, -110, 1.0 + s(28), 46, 46, 52)
    cyl(comp, ox + s(95), oy + s(-60), 1.0, s(70), s(50), NEW).bodies.item(0).name = 'fit siren'


def build_lid(comp, ox, oy):
    W, D = s(280), s(280)
    inner = W - 2 * WALL - 0.8
    lid = box(comp, ox, oy, 0, W, D, 1.4, NEW).bodies.item(0)
    lid.name = 'MINI 2 lid'
    fillet_vertical(comp, lid, 3.0)
    box(comp, ox, oy, 1.4, inner, inner, 4.0, JOIN, [lid])
    box(comp, ox, oy, 1.0, inner - 2 * WALL, inner - 2 * WALL, 5.0, CUT, [lid])
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        box(comp, ox + dx * (inner / 2 - 0.4), oy + dy * (inner / 2 - 0.4), 1.4 + 1.6,
            SNAP if dx else SNAP + 3, SNAP + 3 if dx else SNAP, 1.6, JOIN, [lid])
    return lid


def build_plate(comp, ox, oy, name, pw_mm, openings):
    pw, ph = s(pw_mm), s(41)
    plate = box(comp, ox, oy, 0, pw, ph, 1.4, NEW).bodies.item(0)
    plate.name = name
    fillet_vertical(comp, plate, 1.2)
    for rx in openings:
        box(comp, ox + s(rx), oy, -1, s(13), s(12), 4, CUT, [plate])
    return plate


def build_shelf(comp, ox, oy):
    plate = box(comp, ox, oy, 0, s(150), s(130), 1.4, NEW).bodies.item(0)
    plate.name = 'MINI 5 module shelf'
    fillet_vertical(comp, plate, 2.0)
    for bx in (-58.5, 58.5):
        for byo in (-50, 50):
            cyl(comp, ox + s(bx), oy + s(byo), -1, 2.4, 4, CUT, [plate])
    box(comp, ox, oy, -1, s(90), s(80), 4, CUT, [plate])
    return plate


def build_brain(comp, ox, oy):
    b = box(comp, ox, oy, 0, s(135), s(120), s(40), NEW).bodies.item(0)
    b.name = 'MINI 6 brain housing'
    fillet_vertical(comp, b, 3.0)
    return b


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
        comp = design.rootComponent
        build_shell(comp, -55, 50)
        build_fit(comp,   -55, 50)                                   # components nested in their seats
        build_lid(comp,    55, 50)
        build_plate(comp, -95, -50, 'MINI 3 951 plate', 126, (-12.5, 1.5, 15.5, 29.5, 43.5))
        build_plate(comp, -55, -50, 'MINI 4 PoE plate', 96, (-32, -16, 0, 16, 32))
        build_shelf(comp,  -5, -50)
        build_brain(comp,  65, -50)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Mini built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_Mini failed:\n{}'.format(traceback.format_exc()))
