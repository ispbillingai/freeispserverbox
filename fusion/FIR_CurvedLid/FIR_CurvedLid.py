# FIR_CurvedLid.py - Autodesk Fusion 360 script
# Slide-and-lock front cover: flat port face (280 x 80), 65mm top hood and
# two end walls.  The open back seats over the BottomLid shelf.

import importlib.util
import math
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

# The cover's local Y is the shell Z minus this: its lower edge sits at shell
# Z=3 and its local Y=-40.  Keep it written down - the handedness fault came
# from exactly this kind of undocumented frame mapping.
COVER_Y_TO_SHELL_Z = 43.0
# No alarm-horn vents here either: see HORN_VENTS in the shared contract.
LEN, HEIGHT, DEPTH = 280.0, 80.0, 65.0
WALL = 2.5
# KNOCKOUT notches (owner, 20 Aug: "foil style... not a real layer, for easy
# removing to add a cable").  Like the punch-outs on an electrical box: the
# outline of each notch is slotted RIGHT THROUGH the wall, and the blank in
# the middle stays full thickness, held only by two hair-thin hinge tabs.
# Push with a fingertip: the hinges snap, the blank pops out clean.  Unused
# notches stay closed and solid.
KNOCK_SLOT = 0.7                  # the through perforation around the blank
KNOCK_H = 10.0                    # blank height from the face's lower edge
KNOCK_TAB_H = 1.6                 # hinge tab length, one per side, at the top
KNOCK_TAB_SKIN = 0.35             # hinge thickness - snaps at a push
HOLE_D = 7.0
PWR_D = 7.0
NOTCH_H = 7.0
# HANDEDNESS - read before touching these numbers.
# The BottomLid is a flat plate that is turned OVER onto the tub front, so its
# source +X ends up at shell -X. This cover is not turned over: it prints face
# down and only tips up through 90 degrees about X to slide onto the shelf, so
# its source +X stays shell +X. The two parts therefore do NOT share a source
# frame, and these openings used to be written in the BottomLid's mirrored one
# - every notch landed on the wrong device. They are now written in true shell
# X. No notch size and no physical position changed; only the sign is fixed.
#   MikroTik (shell +X): five LAN notches under its measured RJ45 columns.
#   Tenda switch (shell -X): five cable notches under its 68.8mm service slot.
MIKROTIK_LAN_X = [90.5, 76.5, 62.5, 48.5, 34.5]
RJ45_X = MIKROTIK_LAN_X + list(INTERFACE.poe_cable_notch_x())
# Dedicated cable-route centreline. It matches BottomLid's 10mm pass-through,
# which sits at shell X=-10 once that plate is turned over.
POWER_CABLE_X = -10.0

# ---------------------------------------------------------------------------
# THE CURVE (owner, 19 Aug): "make it curved actually, from the top - cover
# the roof - down to the bottom; it will reduce the confusion at the middle,
# there is a lot going on there."
# ---------------------------------------------------------------------------
# He is right about the middle: the cover top, the BottomLid groove and
# tongue, and the cap's front wall all stack up around shell Z83, and it
# reads as clutter.  So the cover grows a curved SHOULDER that starts at its
# top front edge and sweeps up and back - and, per the SEAMLESS decision
# (19 Aug, "like Ubiquiti M2"), it finishes FLUSH with the cap roof's OUTER
# surface at Z120, its tip butting the roof edge with a single 0.3mm shadow
# line.  From the front and from above the box reads as one shell.
#
# The profile is a quarter ellipse, vertical where it leaves the front panel
# and horizontal where it lands, so both joins are tangent:
#     shell (Y205, Z83)  ->  (Y143.3, Z120 = the roof plane)
# The numbers live in the shared contract, because the cap's roof edge and
# skirt are what they must agree with - validate() enforces the flush plane
# and the hairline gap.
SHOULDER_RISE = INTERFACE.COVER_SHOULDER_RISE
SHOULDER_REACH = INTERFACE.COVER_SHOULDER_REACH
SHOULDER_STEPS = INTERFACE.COVER_SHOULDER_STEPS

# The rails guide the cover. The two front M3 screws are the positive lock;
# there is no pretend snap/detent feature in this part.
# The slide interface (rail position, the ONE clearance value, the key and
# the anti-rattle nubs) is shared contract data: a reviewer caught this file
# declaring CLR=0.4 while hard-coding 0.3 in the rail maths - two competing
# values for one physical gap.  Now there is exactly one, in FIR_Interface.
CLR = INTERFACE.COVER_RAIL_CLR
RAIL_X = INTERFACE.COVER_RAIL_X
SHELF_TOP_Y = -HEIGHT / 2.0
RAIL_TOP_Y = SHELF_TOP_Y + INTERFACE.COVER_RAIL_H
TZ0, TZ1 = WALL, DEPTH - 2.0

# BottomLid groove: 250.0mm long x 1.6mm wide x 1.0mm deep. The locator used
# to be one continuous 249mm tongue; over that length FDM shrink/bow can jam
# a 0.3mm slide, so it is now three short tabs on the same line (reviewer
# agreed).  Same width, depth and clearances.
TONGUE_W, TONGUE_D = 1.0, 0.7

CM = 0.1


def mm(v):
    return v * CM


NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
SKIPPED = []

VERSION = ('v9: KNOCKOUT cable notches - outline perforated right through, blank held by two 0.35mm hinges, push to pop out clean (no cutting); SEAMLESS - the shoulder lands FLUSH with the roof outer '
           'surface (Z120), tip butting the roof edge with one 0.3mm shadow '
           'line, so you cannot tell cover from cap. ASSEMBLY ORDER CHANGED: '
           'slide the cover on LAST, after the cap is closed - its hard end '
           'stop sets the hairline. PRINT STANDING ON AN END WALL '
           '/ interface {}'.format(INTERFACE.INTERFACE_VERSION))


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


def poly_x(comp, pts_yz, xcenter, span, op, parts=None):
    """Closed polygon on the yZ plane (points are local (y, z)), swept along X.

    MEASURED yZ convention (FIR_PlaneProbe v3): sketch-U is world -Z,
    sketch-V is world +Y, and the offset/extrude runs along world +X.
    """
    sk = comp.sketches.add(comp.yZConstructionPlane)
    lines = sk.sketchCurves.sketchLines
    n = len(pts_yz)
    for i in range(n):
        y0, z0 = pts_yz[i]
        y1, z1 = pts_yz[(i + 1) % n]
        lines.addByTwoPoints(adsk.core.Point3D.create(mm(-z0), mm(y0), 0),
                             adsk.core.Point3D.create(mm(-z1), mm(y1), 0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(xcenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(xcenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def shoulder_profile():
    """Outer and inner curves of the shoulder, in local (y, z) mm.

    A quarter ellipse: tangent-vertical where it leaves the front panel and
    tangent-horizontal where it meets the roof, so neither join shows a
    crease.  The inner curve is a true normal offset, so the wall stays
    WALL thick all the way round instead of pinching at the ends.
    """
    outer, inner = [], []
    for i in range(SHOULDER_STEPS + 1):
        t = (math.pi / 2.0) * i / SHOULDER_STEPS
        y = HEIGHT / 2.0 + SHOULDER_RISE * math.sin(t)
        z = SHOULDER_REACH * (1.0 - math.cos(t))
        dy = SHOULDER_RISE * math.cos(t)
        dz = SHOULDER_REACH * math.sin(t)
        length = math.hypot(dy, dz) or 1.0
        ny, nz = -dz / length, dy / length          # inward normal
        outer.append((y, z))
        inner.append((y + WALL * ny, z + WALL * nz))
    return outer, inner


def build_shoulder(comp, front):
    """The curved shoulder: a shell across the width, closed at both ends."""
    outer, inner = shoulder_profile()
    # the shell itself, stopping short of each end wall
    shell_span = LEN - 2.0 * WALL
    poly_x(comp, outer + list(reversed(inner)), 0.0, shell_span, JOIN, [front])
    # solid end caps, filling between the top wall and the curve
    top_y = HEIGHT / 2.0
    cap_face = [(top_y, 0.0)] + outer + [(top_y, SHOULDER_REACH)]
    for sx in (-(LEN - WALL) / 2.0, (LEN - WALL) / 2.0):
        poly_x(comp, cap_face, sx, WALL, JOIN, [front])
    return


def build(comp):
    """Build the printable cover and return its body.

    FIR_ShellCheck imports this exact builder for a physical all-up closure
    inspection. Keep printable cover geometry here rather than duplicating it.
    """
    # Front face lies on Z=0 so the port notches cut reliably through it.
    front = box(comp, 0, 0, 0, LEN, HEIGHT, WALL, NEW).bodies.item(0)
    front.name = 'FIR Lid Cover (4 sides)'
    bottom = -HEIGHT / 2.0

    def notch(cx, width):
        # KNOCKOUT: perforate the outline right through; the blank stays
        # full-thickness on two thin hinge tabs at its top corners.
        top = bottom + KNOCK_H
        side = width / 2.0 + KNOCK_SLOT / 2.0
        slot_h = KNOCK_H - KNOCK_TAB_H + 2.0          # from below the edge
        for sxn in (-1.0, 1.0):
            # side slots, stopping short of the hinge zone
            box(comp, cx + sxn * side, bottom - 2.0 + slot_h / 2.0, -1.0,
                KNOCK_SLOT, slot_h, WALL + 2.0, CUT, [front])
            # hinge relief: same line, but leaves KNOCK_TAB_SKIN at the
            # inner face - this is the "foil" that snaps
            box(comp, cx + sxn * side, top - KNOCK_TAB_H / 2.0, -1.0,
                KNOCK_SLOT, KNOCK_TAB_H, WALL + 1.0 - KNOCK_TAB_SKIN,
                CUT, [front])
        # top slot, right through, connecting the two side slots' hinge ends
        box(comp, cx, top + KNOCK_SLOT / 2.0, -1.0,
            width + 2.0 * KNOCK_SLOT, KNOCK_SLOT, WALL + 2.0, CUT, [front])

    for rx in RJ45_X:
        notch(rx, HOLE_D)
    notch(POWER_CABLE_X, PWR_D)

    # Top wall and its tolerant locating tabs (three short, not one long).
    box(comp, 0, HEIGHT / 2.0 - WALL / 2.0, 0, LEN, WALL, DEPTH, JOIN, [front])
    for tx in INTERFACE.COVER_TAB_X:
        box(comp, tx, 38.5, DEPTH, INTERFACE.COVER_TAB_LEN, TONGUE_W,
            TONGUE_D, JOIN, [front])

    # Two end walls run back from the front face.
    for sx in (-LEN / 2.0 + WALL / 2.0, LEN / 2.0 - WALL / 2.0):
        box(comp, sx, 0, 0, WALL, HEIGHT, DEPTH, JOIN, [front])

    # Sliding inverted-U rail guides: CLR side/top clearance on each rail.
    half = INTERFACE.COVER_RAIL_W / 2.0 + CLR
    rib_w = INTERFACE.COVER_CHANNEL_RIB_W
    rib_cy = (SHELF_TOP_Y + RAIL_TOP_Y + CLR) / 2.0
    rib_h = (RAIL_TOP_Y + CLR) - SHELF_TOP_Y
    web_cy = RAIL_TOP_Y + CLR + 1.5
    for side in (-1, 1):
        sx = side * RAIL_X
        box(comp, sx, web_cy, TZ0, 2.0 * (half + rib_w),
            3.0, TZ1 - TZ0, JOIN, [front])
        for off in (-(half + rib_w / 2.0), half + rib_w / 2.0):
            box(comp, sx + off, rib_cy, TZ0, rib_w, rib_h, TZ1 - TZ0,
                JOIN, [front])
        # Anti-rattle nub under the web: 0.15mm bite into the rail top over
        # 5mm, engaging only near full seat so the slide stays free.  The +X
        # nub sits below the key relief so the relief cannot delete it.
        nub_z0 = 46.0 if side > 0 else 57.0
        nub_h = CLR + INTERFACE.COVER_NUB_PROUD
        box(comp, sx, RAIL_TOP_Y + (CLR - INTERFACE.COVER_NUB_PROUD) / 2.0,
            nub_z0, 6.0, nub_h, INTERFACE.COVER_NUB_LEN, JOIN, [front])
    # ORIENTATION KEY relief: shorten the +shell-X channel web at its tub end
    # so it clears the BottomLid's key block.  A reversed cover presents its
    # UNrelieved web to the block and stops ~7mm proud with the lock seats
    # visibly open - the part refuses to assemble backwards.
    box(comp, RAIL_X, web_cy + 0.1, TZ1 - INTERFACE.COVER_KEY_RELIEF_LEN,
        2.0 * (half + rib_w) + 0.4, 3.4,
        INTERFACE.COVER_KEY_RELIEF_LEN + 1.0, CUT, [front])

    # The curved shoulder: from the top of this panel, up and back to finish
    # flush under the cap roof, hiding the busy middle seam.
    build_shoulder(comp, front)

    # Slide fully home, then drive two M3 screws through the front face into
    # the BottomLid shelf bosses.  These are the outermost screws on the whole
    # box and were invisible flush holes; each now sits in a 10mm dished seat
    # 1.0mm into the face (this part prints FACE-DOWN, so a proud pad would
    # lift it off the bed - a recess is the printable version of the same
    # visual cue).  1.5mm of face is left under the head.
    for sx in (-INTERFACE.COVER_LOCK_X, INTERFACE.COVER_LOCK_X):
        cyl(comp, sx, -31.0, -1.0, INTERFACE.COVER_SEAT_D,
            INTERFACE.COVER_SEAT_DEPTH + 1.0, CUT, [front])
        cyl(comp, sx, -31.0, -1.0, 3.4, WALL + 2.0, CUT, [front])

    # TAMPER MAGNET (owner, 18 Aug): a 16x16 pad on the inner face carries a
    # press-fit pocket for the measured D12.1 disc magnet, pressed in from
    # the inside - the pocket floor keeps 1.2mm of face, so nothing shows
    # outside.  At shell X+15 the closed cover holds the magnet head-on at
    # ~10.6mm from the reed recessed in the BottomLid shelf; the pad bottom
    # sweeps 0.5mm above the reed on its way in.  BENCH-TEST the actual
    # reed+magnet pair at that distance before printing.
    box(comp, INTERFACE.REED_X, INTERFACE.MAGNET_CY, WALL,
        INTERFACE.MAGNET_PAD_SQ, INTERFACE.MAGNET_PAD_SQ,
        INTERFACE.MAGNET_PAD_H, JOIN, [front])
    cyl(comp, INTERFACE.REED_X, INTERFACE.MAGNET_CY,
        INTERFACE.MAGNET_POCKET_FLOOR, INTERFACE.MAGNET_POCKET_D,
        WALL + INTERFACE.MAGNET_PAD_H, CUT, [front])
    if not INTERFACE.MAGNET_TH_MEASURED:
        SKIPPED.append(
            'magnet THICKNESS is ASSUMED {:.1f}mm (diameter 12.1 is measured). '
            'Measure it: the pocket floor moves with it.'
            .format(INTERFACE.MAGNET_TH))
    return front


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
        ui.messageBox('FIR_CurvedLid {} built.{}'.format(
            VERSION, ('\nSkipped:\n - ' + '\n - '.join(SKIPPED)) if SKIPPED else ''))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_CurvedLid failed:\n{}'.format(traceback.format_exc()))
