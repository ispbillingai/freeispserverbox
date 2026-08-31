# FIR_BottomLid.py - Autodesk Fusion 360 script
# The BOTTOM LID = one FLAT plate that is the integrated port face: 3 sections in a single
# piece - SWITCH | POWER | MIKROTIK. Cut FLAT (reliable + crisp), prints face-up. It is just
# a lid (no tray/cradles inside); the devices are held by the main box and line up to these
# openings. Slight locating ridges + clip tabs. Same measured port dims.

import importlib.util
import os
import sys

import adsk.core, adsk.fusion, adsk.cam, traceback


def _load_shared_interface():
    """Load the one mechanical-interface contract in workspace or Fusion."""
    script_file = globals().get('__file__', '')
    script_dir = (os.path.dirname(os.path.abspath(script_file))
                  if script_file else os.getcwd())
    candidates = []
    override = os.environ.get('FIR_INTERFACE_PATH')
    if override:
        candidates.append(override if override.lower().endswith('.py')
                          else os.path.join(override, 'FIR_Interface.py'))
    workspace_source = globals().get('_workspace_source')
    if workspace_source:
        candidates.append(os.path.join(
            os.path.dirname(os.path.abspath(workspace_source)), '..',
            '_shared', 'FIR_Interface.py'))
    candidates.extend((
        os.path.join(script_dir, 'FIR_Interface.py'),
        os.path.join(script_dir, '..', '_shared', 'FIR_Interface.py'),
    ))
    for candidate in candidates:
        path = os.path.realpath(os.path.abspath(candidate))
        if not os.path.isfile(path):
            continue
        sys.modules.pop('_freeisp_shared_interface', None)
        spec = importlib.util.spec_from_file_location(
            '_freeisp_shared_interface', path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules['_freeisp_shared_interface'] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError(
        'FIR_Interface.py not found. Deploy fusion/_shared beside the Fusion scripts.')


INTERFACE = _load_shared_interface()

PW, PH, PT = 280.0, 80.0, 3.0                # plate = full front face: width x TUB HEIGHT x thickness
# BottomLid is X-mirrored when mounted on the tub: local +X is physical
# shell -X.  Keep this source datum so the switch remains at shell X=-85.
# Local +X is physical shell -X, so the switch's shell position is negated
# here.  It moved inboard for barrel-plug clearance; taking it from the shared
# contract is what keeps this slot on the real switch.
SW_CX = -INTERFACE.POE_CX
MIK_X0 = -135.0                              # MikroTik port-face left edge in lid coordinates
BASE = 6.5                                   # device base height -> port Y = BASE + measured_z
# Confirmed PoE switch: its port face is 82mm wide x 23mm high; it is 52mm
# deep inside the tub.  Francis measured 6.6mm side lands, so the printed
# slot is the exact 68.8mm (= 82 - 2*6.6) rather than five guessed RJ45 cuts.
SW_W, SW_D, SW_H = INTERFACE.POE_W, INTERFACE.POE_D, INTERFACE.POE_H
SW_PORT_SIDE_LAND = INTERFACE.POE_PORT_SIDE_LAND
SW_PORT_W, SW_PORT_H = INTERFACE.POE_PORT_W, INTERFACE.POE_PORT_H
SW_PORT_FROM_BOTTOM = INTERFACE.POE_PORT_FROM_BOTTOM
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

VERSION = ('v7: 8mm SHELF SPINE (5mm doubler slab, split at the magnet corridor) - the wobbly-rail fix; shelf root gussets at +-111 + SOFTER detents (0.3mm click); SELF-CLICK rail detents - stepped bumps on the rail outboard faces, '
           'the cover clicks home and holds without its screws; '
           'TAMPER REED groove in the shelf (shell X+15, D4 wire hole into '
           'the box) + hard end stop, orientation key block, contract-driven '
           'rails; 6 face screws in visible pads (side pair now D10 - a D12 '
           'pad clipped the cover end wall) / interface {}'
           .format(INTERFACE.INTERFACE_VERSION))


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
    # cylinder running along X (circle on the yZ plane) - currently unused.
    # MEASURED yZ convention (FIR_PlaneProbe v3): sketch-U = world -Z,
    # sketch-V = world +Y, offset/extrude = world +X.
    sk = comp.sketches.add(comp.yZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(-cz), mm(cy), 0), mm(d / 2.0))
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
    # The land above the switch is intentionally BLANK. A slotted alarm-horn
    # window was cut here and then removed at the owner's request: the siren is
    # loud enough that plastic will not muffle it, so the panel stays closed.
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
    # ===== BOLTING: attach the lid to the main box - now in VISIBLE seats =====
    # 4 along the top + 2 mid-height (kept ABOVE the bottom shelf so a screwdriver can reach)
    # all 6 on the OPENING PERIMETER (4 near one long edge + 2 out on the side edges) so the
    # shell can anchor every boss to a wall/flange (was 2 mid-span).
    # The owner could not FIND these screws on the 280mm face - a flush 3.4mm
    # hole is invisible in a shaded render.  Each one now sits in a 12mm pad
    # standing 1.5mm proud of the face, and the counterbore is re-cut from the
    # pad top: the head finishes flush with the pad and the land under it
    # GROWS from 0.8mm to 1.9mm of plate.  (M3 screws now grip the tub bosses
    # ~1.1mm less; with the through-pilot that is still 8mm of thread.)
    pad_h = INTERFACE.LID_SEAT_PAD_H
    cb_floor = PT + pad_h - INTERFACE.LID_SEAT_CBORE_DEPTH
    for (bx, by) in ((-120, 72), (-40, 72), (40, 72), (120, 72), (-132, 44), (132, 44)):
        # The side pair at +-132 is D10, not D12: a D12 pad there overlaps
        # the CurvedLid's end wall (inner face |X|137.5) by 0.5mm - a real
        # collision the 18 Aug reed work uncovered.
        pad_d = 10.0 if abs(bx) == 132 else INTERFACE.M3_SEAT_PAD_D
        cyl(comp, bx, by, PT - 0.5, pad_d,
            pad_h + 0.5, JOIN, [plate])                               # seat pad, root in the plate
        cyl(comp, bx, by, -1, 3.5, PT + pad_h + 2, CUT, [plate])              # M3 through-hole
        cyl(comp, bx, by, cb_floor, INTERFACE.M3_SEAT_CBORE_D,
            INTERFACE.LID_SEAT_CBORE_DEPTH + 1, CUT, [plate])                 # head counterbore

    # ===== STEP 1: 65mm horizontal SHELF sticking OUT from the bottom-OUTSIDE, full length =====
    box(comp, 0, 1.5, PT, PW, 3, 65, JOIN, [plate])           # Y 0-3 (bottom), out 65mm
    # SHELF DOUBLER (owner photo, 31 Aug: the rail is "weak and wobbly" - its
    # 3mm foundation flexes, not the rail).  A 5mm spine on the shelf top,
    # split around the magnet/reed-wire corridor, stopping short of the
    # channel-rib sweep and of the lock bosses/reed slot.  Welded to the
    # shelf AND to the plate face, so it is also one long root gusset.
    dx0, dx1 = INTERFACE.SHELF_DOUBLER_CORRIDOR
    for x0, x1 in ((-INTERFACE.SHELF_DOUBLER_XMAX, dx0),
                   (dx1, INTERFACE.SHELF_DOUBLER_XMAX)):
        box(comp, (x0 + x1) / 2.0, 3.0 + INTERFACE.SHELF_DOUBLER_H / 2.0, PT,
            x1 - x0, INTERFACE.SHELF_DOUBLER_H,
            INTERFACE.SHELF_DOUBLER_ZMAX - PT, JOIN, [plate])
    # ===== RAILS the curved cover slides onto + clips down to (run along Z = the slide dir) =====
    # Rail position/size and the one slide clearance are shared contract data
    # now - the cover's channels and the fit coupons derive from the same
    # numbers, so the two parts can no longer disagree about this interface.
    rail_x = INTERFACE.COVER_RAIL_X
    for rx in (-rail_x, rail_x):
        box(comp, rx, 3 + INTERFACE.COVER_RAIL_H / 2.0, PT,
            INTERFACE.COVER_RAIL_W, INTERFACE.COVER_RAIL_H, 62,
            JOIN, [plate])                                    # rail: Y3-8, Z3-65 (slide guide)
    # SHELF ROOT GUSSETS (owner, 31 Aug: printed joints snapping).  The shelf
    # is a 3mm wall on a 3mm plate; these two stepped webs at lid-local +-111
    # triple the root section right where hands pry.  X chosen clear of the
    # switch slot (ends 105.4), the last RJ45 (starts 117.75), the lock
    # bosses (+-122), the rails (+-133) and the magnet sweep (-15).
    for gx in (-111.0, 111.0):
        box(comp, gx, 9.0, PT, 6.0, 12.0, 5.0, JOIN, [plate])
        box(comp, gx, 6.5, PT + 5.0, 6.0, 7.0, 4.0, JOIN, [plate])
        box(comp, gx, 4.5, PT + 9.0, 6.0, 3.0, 4.0, JOIN, [plate])
    # SELF-CLICK DETENT (owner, 31 Aug: the cover "just falls off - the rails
    # are only a guide").  Stepped bump on each rail's OUTBOARD side face:
    # square catch band toward the plate, half-proud lead-in band toward the
    # shelf front; the cover's outboard rib gap drops over it at full seat and
    # the cover holds itself.  Lock screws stay the security lock.
    dz0, dlen = INTERFACE.COVER_DETENT_LID_Z0, INTERFACE.COVER_DETENT_LEN
    for rx in (-rail_x, rail_x):
        s_ = 1.0 if rx > 0 else -1.0
        f = rx + s_ * (INTERFACE.COVER_RAIL_W / 2.0)
        box(comp, f + s_ * INTERFACE.COVER_DETENT_PROUD / 2.0,
            3 + INTERFACE.COVER_RAIL_H / 2.0, dz0,
            INTERFACE.COVER_DETENT_PROUD, 4.0, dlen / 2.0, JOIN, [plate])
        box(comp, f + s_ * INTERFACE.COVER_DETENT_STEP_PROUD / 2.0,
            3 + INTERFACE.COVER_RAIL_H / 2.0, dz0 + dlen / 2.0,
            INTERFACE.COVER_DETENT_STEP_PROUD, 4.0, dlen / 2.0, JOIN, [plate])
    # ORIENTATION KEY block, on top of the rail at lid-local -X = SHELL +X
    # (this plate is turned over on assembly).  The RIGHT cover's relieved
    # channel web stops 2.5mm short of it; a REVERSED cover's unrelieved web
    # hits it and stands ~7mm proud - backwards assembly refuses itself.
    box(comp, -rail_x, 3 + INTERFACE.COVER_RAIL_H
        + INTERFACE.COVER_KEY_BLOCK_H / 2.0, PT,
        INTERFACE.COVER_RAIL_W, INTERFACE.COVER_KEY_BLOCK_H,
        INTERFACE.COVER_KEY_BLOCK_LEN, JOIN, [plate])
    # LOCK SCREWS: cover slides on, then 2 screws hold it CLOSED -> minimal screw bosses at the shelf front
    for sx in (-INTERFACE.COVER_LOCK_X, INTERFACE.COVER_LOCK_X):
        # Boss face at z65.5 = flush contact with the cover's inner face:
        # this is the cover's HARD END STOP, and the two lock screws clamp
        # the cover against it (18 Aug review - there was no defined stop).
        # 10mm wide and at X+-122 (was 7 wide at +-125): a boss that can one
        # day take a brass insert, clear of the cover channel rib at 129.1.
        box(comp, sx, 9.5, PT + 54, INTERFACE.COVER_LOCK_BOSS_W, 13, 8.5,
            JOIN, [plate])                                    # boss = end stop
        cyl(comp, sx, 12, PT + 54, INTERFACE.COVER_LOCK_BOSS_PILOT_D, 8,
            CUT, [plate])                                     # pilot (self-tap or insert bore)
    # ===== TAMPER REED (owner, 18 Aug): recessed groove in the shelf top =====
    # The reed lies along X in a 3.2-wide, 2.0-deep groove (1mm of shelf left
    # under it) at lid-local X-15 = SHELL +X15 - this plate is turned over.
    # The cover's magnet stops head-on ~10.6mm away; glue the reed in, run
    # its wires back along the shelf and through the D4 hole into the box
    # (the hole lands between the router frame wall and the port row).
    box(comp, -INTERFACE.REED_X, PT - INTERFACE.REED_SLOT_DEPTH / 2.0,
        INTERFACE.REED_SLOT_Z0, INTERFACE.REED_SLOT_LEN,
        INTERFACE.REED_SLOT_DEPTH, INTERFACE.REED_SLOT_W, CUT, [plate])
    wx, wy = INTERFACE.REED_WIRE_HOLE_XY
    cyl(comp, wx, wy, -1, INTERFACE.REED_WIRE_HOLE_D, PT + 2, CUT, [plate])

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
        # ALWAYS report the version so a stale %APPDATA% deploy shows itself.
        ui.messageBox('FIR_BottomLid {} built.{}'.format(
            VERSION, ('\nSkipped:\n - ' + '\n - '.join(SKIPPED)) if SKIPPED else ''))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_BottomLid failed:\n{}'.format(traceback.format_exc()))
