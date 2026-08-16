# FIR_BottomLid.py - Autodesk Fusion 360 script
# The BOTTOM LID = one FLAT plate that is the integrated port face: 3 sections in a single
# piece - SWITCH | POWER | MIKROTIK. Cut FLAT (reliable + crisp), prints face-up. It is just
# a lid (no tray/cradles inside); the devices are held by the main box and line up to these
# openings. Slight locating ridges + clip tabs. Same measured port dims.

import adsk.core, adsk.fusion, adsk.cam, traceback

PW, PH, PT = 280.0, 80.0, 3.0                # plate = full front face: width x TUB HEIGHT x thickness
# BottomLid is X-mirrored when mounted on the tub: local +X is physical
# shell -X.  Keep this source datum so the switch remains at shell X=-85.
SW_CX = 85.0
MIK_X0 = -135.0                              # MikroTik port-face left edge in lid coordinates
BASE = 6.5                                   # device base height -> port Y = BASE + measured_z
# Confirmed PoE switch: its port face is 82mm wide x 23mm high; it is 52mm
# deep inside the tub.  Francis measured 6.6mm side lands, so the printed
# slot is the exact 68.8mm (= 82 - 2*6.6) rather than five guessed RJ45 cuts.
SW_W, SW_D, SW_H = 82.0, 52.0, 23.0
SW_PORT_SIDE_LAND = 6.6
SW_PORT_W, SW_PORT_H = SW_W - 2.0 * SW_PORT_SIDE_LAND, 11.5
SW_PORT_FROM_BOTTOM = 3.2
SW_PORT_CY = BASE + SW_PORT_FROM_BOTTOM + SW_PORT_H / 2.0
# Dedicated power-cable route only.  It shares the CurvedLid power-notch
# centreline; the router, switch, RJ45, jack and other measured port openings
# are intentionally not changed here.
POWER_CABLE_X = 10.0

CM = 0.1
def mm(v):
    return v * CM

NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
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


def cyl_x(comp, cy, cz, x0, d, length, op, parts=None):
    # cylinder running along X (circle on the yZ plane) - used for a ROUNDED detent bulge
    sk = comp.sketches.add(comp.yZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cy), mm(cz), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(mm(x0)))
    ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(length)))
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


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


def frame_grip(comp, plate, xl, xr, yb, yt, depth, wt):
    # holding pocket on the INSIDE face: 4 walls (top/bottom/sides) the device front slots into.
    # All walls are CLAMPED to |x| <= 136.7: the tub side-wall inner face sits at 137 when the
    # lid is mounted, and unclamped walls overlapped it by 0.5mm - the lid could not seat.
    clr = 0.5
    lim = PW / 2.0 - 3.3
    fh = (yt - yb) + 2 * clr
    fx0 = max(xl - clr - wt, -lim)
    fx1 = min(xr + clr + wt, lim)
    box(comp, (fx0 + fx1) / 2, yb - clr - wt / 2, -depth, fx1 - fx0, wt, depth, JOIN, [plate])  # bottom
    box(comp, (fx0 + fx1) / 2, yt + clr + wt / 2, -depth, fx1 - fx0, wt, depth, JOIN, [plate])  # top
    box(comp, (fx0 + xl - clr) / 2, (yb + yt) / 2, -depth, (xl - clr) - fx0, fh, depth, JOIN, [plate])  # left
    box(comp, (xr + clr + fx1) / 2, (yb + yt) / 2, -depth, fx1 - (xr + clr), fh, depth, JOIN, [plate])  # right
    return


def build(comp):
    plate = box(comp, 0, PH / 2, 0, PW, PH, PT, NEW).bodies.item(0)
    plate.name = 'FIR Bottom Lid (flat port face)'
    fillet_vertical(comp, plate, 6.0)

    def hole(cx, cy, shape, a, b):                          # flat Z-cut - always works
        if shape == 'c':
            cyl(comp, cx, cy, -1, a, PT + 2, CUT, [plate])
        else:
            box(comp, cx, cy, -1, a, b, PT + 2, CUT, [plate])

    # ---- MIKROTIK section (right) - exact measured 951 layout ----
    hole(MIK_X0 + 11, BASE + 15, 'c', 6.5, 0)              # DC jack
    hole(MIK_X0 + 19, BASE + 10, 'c', 2.5, 0)             # reset
    hole(MIK_X0 + 25, BASE + 9.5, 'r', 4, 3)             # PWR LED
    hole(MIK_X0 + 33, BASE + 9.5, 'r', 4, 3)             # ACT LED
    for rx in (44.5, 58.5, 72.5, 86.5, 100.5):           # 5 RJ45
        hole(MIK_X0 + rx, BASE + 16, 'r', 13.5, 12.5)
    hole(MIK_X0 + 23, 42, 'c', 9, 0)                      # power-cable pass-through (moved RIGHT, clear of the side bolt)
    # ---- SWITCH section (left) - one confirmed long port opening ----
    # The opening is 68.8 x 11.5mm (approximately the requested 69 x 11.5),
    # centred in the 82mm switch face and 3.2mm above its lower edge.
    hole(SW_CX, SW_PORT_CY, 'r', SW_PORT_W, SW_PORT_H)
    # ---- POWER section (centre) ----
    hole(-8, BASE + 18, 'r', 19, 13)                     # power switch (rocker)
    hole(-3, BASE + 8, 'c', 7.0, 0)                      # power jack  - moved LEFT below the switch, clear of the PoE support
    # 10mm grommet/pass-through.  Centreline matches FIR_CurvedLid's dedicated
    # power notch at X=+10; this is not a router or switch port change.
    hole(POWER_CABLE_X, BASE + 8, 'c', 10.0, 0)

    # HOLDING FRAMES on the INSIDE - 10mm walls (top/bottom/sides) pocket each device's port end
    # so it can't slide up/down/sideways (the box-side retention comes later)
    frame_grip(comp, plate, MIK_X0, MIK_X0 + 114, BASE, BASE + 29, 10, 2.0)        # MIKROTIK (left), 2mm walls
    frame_grip(comp, plate, SW_CX - SW_W / 2.0, SW_CX + SW_W / 2.0,
               BASE, BASE + SW_H, 10, 2.0)                                          # confirmed switch frame
    # clip tabs along the top edge (locate it on the box front before bolting)
    for tx in (-130, -40, 40, 130):
        box(comp, tx, PH - 2, 0, 10, 4, PT, JOIN, [plate])
    # ===== BOLTING: attach the lid to the main box (counterbored - heads flush on the front) =====
    # 4 along the top + 2 mid-height (kept ABOVE the bottom shelf so a screwdriver can reach)
    # all 6 on the OPENING PERIMETER (4 near one long edge + 2 out on the side edges) so the
    # shell can anchor every boss to a wall/flange (was 2 mid-span)
    for (bx, by) in ((-120, 72), (-40, 72), (40, 72), (120, 72), (-132, 44), (132, 44)):
        cyl(comp, bx, by, -1, 3.5, PT + 2, CUT, [plate])      # M3 through-hole
        cyl(comp, bx, by, PT - 2.2, 6.5, 3, CUT, [plate])     # counterbore (head sits flush)

    # ===== STEP 1: 65mm horizontal SHELF sticking OUT from the bottom-OUTSIDE, full length =====
    box(comp, 0, 1.5, PT, PW, 3, 65, JOIN, [plate])           # Y 0-3 (bottom), out 65mm
    # ===== RAILS the curved cover slides onto + clips down to (run along Z = the slide dir) =====
    # 5mm tall on the shelf top (Y 3-8), X=±133, Z 3-65; the cover's cap hooks over these.
    for rx in (-133, 133):
        box(comp, rx, 5.5, PT, 4, 5, 62, JOIN, [plate])       # rail: X±133, Y3-8, Z3-65 (slide guide)
    # LOCK SCREWS: cover slides on, then 2 screws hold it CLOSED -> minimal screw bosses at the shelf front
    for sx in (-125, 125):
        # boss stops at z65 = 0.5 clear of the cover's INNER face (65.5); 11 deep it poked 2.5mm
        # THROUGH the cover front wall and the cover could not close
        box(comp, sx, 9.5, PT + 54, 7, 13, 8, JOIN, [plate])  # SMALL boss, just enough around the screw
        cyl(comp, sx, 12, PT + 54, 2.6, 8, CUT, [plate])      # M3 self-tap pilot, screw enters from the front
    # ===== TOP GROOVE: build OUT 3mm at the top (lid top now meets cover top) + a 1mm channel =====
    box(comp, 0, PH + 1.5, 0, PW, 3, PT, JOIN, [plate])       # extend lid top UP 3mm -> Y 80-83
    box(comp, 0, PH + 1.5, PT - 1, 250, 1.6, 2, CUT, [plate]) # 1mm-deep groove in the outer face, full width
    return plate


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
        build(design.rootComponent)
        app.activeViewport.fit()
        if SKIPPED:
            ui.messageBox('Bottom lid built. Skipped:\n - ' + '\n - '.join(SKIPPED))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_BottomLid failed:\n{}'.format(traceback.format_exc()))
