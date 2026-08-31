# FIR_Shell.py - Autodesk Fusion 360 script
# THE TUB, and nothing else (owner, 19 Aug: one script per part - the deep
# cap moved to FIR_TopLid, the horn sled is gone).  Fully detailed so you can
# SEE how the final holds together:
#  - RB951 + PoE bays: sectioned snap-tab cradles on airflow standoffs (devices drop in + click)
#  - integrated BOTTOM LID closes the front opening + bolts on with 6 self-tap screws
#  - EXTENSION strip: a tall guide wall it rests against + wedge tabs that clamp it down
#  - cable run: front-left cord exit + grommet collar + zip-tie slots cut through the floor
#  - back-wall CLEAT BAR (hangs on the printed FIR WALL PLATE, locked by two in-box
#    floor screws - the old keyholes are gone); side-bolt bosses for the deep-cap top lid.
# Coordinate frame: origin at footprint centre, +Y = front (ports/UI), +Z = up. HALF = 140.
# This is the main tub only (print BOTTOM-DOWN, no support). Bottom lid + top lid are separate.

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

    seen = set()
    for candidate in candidates:
        path = os.path.realpath(os.path.abspath(candidate))
        if path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        # Always reload the shared contract: Fusion otherwise preserves an
        # older tray/cap interface after a source sync.
        sys.modules.pop('_freeisp_shared_interface', None)
        spec = importlib.util.spec_from_file_location(
            '_freeisp_shared_interface', path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules['_freeisp_shared_interface'] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError(
        'FIR_Interface.py not found. Deploy fusion/_shared beside the '
        'Fusion script folders, or set FIR_INTERFACE_PATH.')


INTERFACE = _load_shared_interface()

BOX_W, BOX_D, BOX_H = 280.0, 280.0, 80.0       # tub 80mm; deep-cap lid adds the rest
WALL, FLOOR, CORNER_R = 3.0, 3.0, 10.0
HALF = BOX_W / 2.0
FRONT_Y = HALF - WALL

MIK_W, MIK_D, MIK_H, MIK_CX = 114.0, 139.0, 29.0, 78.0   # MikroTik now +X = LEFT in front view (matches lid)
ST_H = 3.5                                       # 951 standoff -> port face z6..35
# Confirmed physical PoE switch: 82mm port face x 52mm depth x 23mm high.
# Its front face remains against the BottomLid, so only its rear edge moves
# forward; the centre stays aligned with the 68.8mm long BottomLid opening.
# Owner moved the switch inboard so a STRAIGHT barrel plug goes in from the
# side: 25mm off its jack end face instead of 11mm.  Position and envelope come
# from the shared contract now, because the BottomLid slot and the front-cover
# cable notches have to move with it.
POE_W, POE_D, POE_H = INTERFACE.POE_W, INTERFACE.POE_D, INTERFACE.POE_H
POE_CX = INTERFACE.POE_CX
EXT_CY = -110.0                                  # extension/adapter zone (back)
EXT_W, EXT_D, EXT_H = 240.0, 47.0, 29.0
EXT_FRONT_RETAINER_H = EXT_H                     # internal front retainer; wedges attach to back casing wall
ADAP_TOP = 70.0                                  # adapter TOP height above floor (CONFIRM w/ real adapters)
DIV_Y = -82.0                                    # AC/DC divider line (front=DC, back=AC)
SHELF_Z, MOD_CX = 45.0, -5.0
PLATE_TH = 3.0
# Brain-case interface: the small FIR_ModuleGadget hangs from these four
# reinforced bosses using low-profile M3x12 self-tapping screws.  A broad
# flange embeds each boss into the cap roof so tightening cannot snap a thin
# free-standing post.  The shared contract owns the small-case offset and
# derives this cap pattern from its four local roof holes.  The 10.8mm boss
# height keeps the confirmed 69.6mm brain case 1.1mm above the MikroTik in
# the all-up stack, while an M3x12 still gets 9mm engagement after crossing
# the case's 3mm roof.
BRAIN_CASE_TO_CAP_Y = INTERFACE.CASE_TO_CAP_Y
BRAIN_CASE_MOUNT = INTERFACE.CASE_MOUNT
BRAIN_CAP_MOUNT = INTERFACE.CAP_BOSS_PATTERN
BRAIN_CAP_BOSS_D, BRAIN_CAP_BOSS_H = 9.0, 10.8
BRAIN_CAP_FLANGE_D, BRAIN_CAP_FLANGE_H = 13.0, 3.0
BRAIN_CAP_PILOT = 2.6

# ---- deep top cap, expressed once so the tub can reason about it -----------
CAP_SKIRT_H = 52.0                               # 15mm tub overlap + 37mm headroom
CAP_ROOF_TH = 3.0
CAP_TUB_OVERLAP = 15.0
CAP_TOP_Z = BOX_H - CAP_TUB_OVERLAP + CAP_SKIRT_H + CAP_ROOF_TH   # 120 assembled
CAP_ROOF_INNER_Z = CAP_TOP_Z - CAP_ROOF_TH                        # 117 assembled

# ---- the hanging brain case, as a KEEP-OUT for tub features ---------------
# The small case bolts up under the cap bosses, so its underside is fixed by
# the cap, not by the tub.  Anything in the tub that rises into this box is an
# interference the all-up view would otherwise only show as a faint overlap.
BRAIN_CASE_BOTTOM_Z = CAP_ROOF_INNER_Z - BRAIN_CAP_BOSS_H - INTERFACE.CASE_BODY_Z
BRAIN_CASE_TO_CAP_X = INTERFACE.CASE_TO_CAP_X
BRAIN_CASE_KEEPOUT = (
    BRAIN_CASE_TO_CAP_X - INTERFACE.CASE_OUTER_W / 2.0,
    BRAIN_CASE_TO_CAP_X + INTERFACE.CASE_OUTER_W / 2.0,
    BRAIN_CASE_TO_CAP_Y - INTERFACE.CASE_OUTER_H / 2.0,
    BRAIN_CASE_TO_CAP_Y + INTERFACE.CASE_OUTER_H / 2.0,
    BRAIN_CASE_BOTTOM_Z - 1.0,                   # keep a 1mm air gap under it
)

# ---- confirmed Tenda switch DC jack (shared contract) ----------------------
POE_JACK_SIDE = INTERFACE.POE_JACK_SIDE
POE_JACK_FROM_REAR = INTERFACE.POE_JACK_FROM_REAR
POE_JACK_FROM_BASE = INTERFACE.POE_JACK_FROM_BASE
POE_PLUG_D = INTERFACE.POE_PLUG_D
# The jack height is not measured yet, so the cradle post beside it is clipped
# to a height that clears the plug wherever it actually sits on that face.
POE_JACK_POST_MAX_H = 8.0

# ---- alarm horn, INSIDE on the floor behind the switch (shared contract) ---
# It does not touch the cap at all any more.  The only reason a 102mm horn has
# anywhere to stand is that the brain case moved +47mm off centre; if that
# shift is ever dialled back, FIR_Interface.validate() refuses to load.
HORN_PAD_D, HORN_PAD_H = INTERFACE.HORN_PAD_D, INTERFACE.HORN_PAD_H
HORN_PILOT_D, HORN_PILOT_DEPTH = INTERFACE.HORN_PILOT_D, INTERFACE.HORN_PILOT_DEPTH
HORN_FOOT_D = INTERFACE.HORN_FOOT_D
# Cap-to-tub fastening: FOUR screws per SIDE wall, all horizontal, all
# drivable with the box hanging on its wall.  The old back pair at X=+-115
# could not be reached behind a wall-hung box (8mm of air), so it moved to
# the side walls at Y=-118; the back edge keeps its two snap detents.
CAP_SIDE_SCREW_Y = INTERFACE.CAP_SIDE_SCREW_Y
CAP_SCREW_Z = INTERFACE.CAP_SCREW_Z

SHOW_PARTS = False                               # False = print-ready (no display components/cables)

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


def cyl_y(comp, cx, cz, ycenter, d, span, op, parts=None):
    # cylinder running along Y (circle on xZ plane), SYMMETRIC about ycenter so it cuts through the
    # boss regardless of the plane-normal direction - used for the front lid-bolt pilots.
    # MEASURED xZ convention (FIR_PlaneProbe v3, 18 Aug 2026): sketch-U is
    # world +X, sketch-V is world -Z, offset/extrude is world +Y.  The V flip
    # is why these pilots used to land BELOW the floor at -Z.
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cx), mm(-cz), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(ycenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(ycenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def box_y(comp, cx, cz, ycenter, sx, sz, span, op, parts=None):
    # rectangle on the xZ plane, extruded through Y - used for cuts through front/back walls.
    # MEASURED xZ convention: sketch-V is world -Z (see cyl_y).
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.sketchCurves.sketchLines.addCenterPointRectangle(
        adsk.core.Point3D.create(mm(cx), mm(-cz), 0),
        adsk.core.Point3D.create(mm(cx + sx / 2.0), mm(-cz + sz / 2.0), 0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(ycenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(ycenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def cyl_x(comp, cy, cz, xcenter, d, span, op, parts=None):
    # cylinder running along X (circle on yZ plane), SYMMETRIC about xcenter - for SIDE-wall bolt pilots.
    # MEASURED yZ convention (FIR_PlaneProbe v3, 18 Aug 2026): sketch-U is
    # world -Z, sketch-V is world +Y, offset/extrude is world +X.  Getting
    # only half of this right is what put the seat pads under the box.
    sk = comp.sketches.add(comp.yZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(-cz), mm(cy), 0), mm(d / 2.0))
    f = comp.features.extrudeFeatures
    ei = f.createInput(sk.profiles.item(0), op)
    if abs(xcenter) > 1e-9:
        ei.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(mm(xcenter)))
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(span)), True)
    if parts:
        ei.participantBodies = parts
    return f.add(ei)


def poly_x(comp, pts_yz, xcenter, span, op, parts=None):
    # closed polygon on the yZ plane (points are (y, z) mm), extruded along X
    # symmetric about xcenter - used for the cap skirt's lead-in chamfer, which
    # a rectangle cannot make.
    # MEASURED yZ convention: sketch-U = world -Z, sketch-V = world +Y.
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


def fillet_corners(comp, body, r, cx=0.0, half=None, back_only=False):
    # round ONLY the 4 outer vertical corners (at cx+-half in X, +-half in Y). Call AFTER the
    # walls/skirt so the FULL-HEIGHT corner is rounded, not just the base plate. cx/half let it
    # work on the offset top lid too. back_only limits it to the -Y corners (the front of the tub
    # is open now, and the wall end-face edges at Y=+137 must NOT be rounded - they seat the lid).
    if half is None:
        half = HALF
    try:
        coll = adsk.core.ObjectCollection.create()
        for e in body.edges:
            g = e.geometry
            if isinstance(g, adsk.core.Line3D):
                v = g.startPoint.vectorTo(g.endPoint)
                v.normalize()
                if abs(v.z) > 0.99:
                    mx = (g.startPoint.x + g.endPoint.x) / 2.0
                    my = (g.startPoint.y + g.endPoint.y) / 2.0
                    if back_only and my > 0:
                        continue
                    if abs(abs(mx - mm(cx)) - mm(half)) < mm(2) and abs(abs(my) - mm(half)) < mm(2):
                        coll.add(e)
        if coll.count:
            fi = comp.features.filletFeatures.createInput()
            fi.addConstantRadiusEdgeSet(coll, adsk.core.ValueInput.createByReal(mm(r)), False)
            comp.features.filletFeatures.add(fi)
    except Exception as e:
        SKIPPED.append('corner fillet: {}'.format(e))


def build_lid_seat(comp, sh):
    # The integrated BOTTOM LID (front port face, 280x80) fills the front slab Y137-140 and bolts
    # on with its 6 self-tap screws. The SEAT is: floor front edge (bottom) + side-wall end faces
    # at Y137 (sides) + the pulled-back top rail (top) + these 6 bosses. Lid bolt pattern (lidX,
    # lidY) maps to the front face as (-X, Z); pilots run -Y into the tub. Removable: unbolt ->
    # slide the switch/router in. (The old "left/right front rails" sat buried INSIDE the side
    # walls = dead geometry - removed.)
    # 6 self-tap M3 bolt bosses at the lid's perimeter pattern. The side pair (±132) is widened to
    # X127-137 so it MERGES with the side wall (9mm wide it stopped 0.5mm short and floated).
    for (bx, bz) in ((-120, 72), (120, 72), (-40, 72), (40, 72), (-132, 44), (132, 44)):
        bw = 10 if abs(bx) == 132 else 9
        box(comp, bx, FRONT_Y - 4.5, bz - 4, bw, 9, 8, JOIN, [sh])      # boss block behind the lid
        cyl_y(comp, bx, bz, FRONT_Y - 4.5,
              INTERFACE.BOTTOM_LID_BOSS_PILOT_D, 16, CUT, [sh])         # pilot (self-tap or insert bore)
    return


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


def wedge_tab(comp, sh, cx, w):
    # Wall-attached hold-down tab. Built from simple boxes so it cannot drift off
    # the casing wall: root overlaps the wall, lip sits at the extension top.
    wall_inner = -HALF + WALL                         # back casing inner face
    strip_back = EXT_CY - EXT_D / 2.0                 # extension back edge
    z0 = FLOOR + EXT_H                                # extension top height
    wall_overlap = 1.5                                # positive overlap into casing wall
    lip_depth = 8.0                                   # reach over the strip edge
    root_h = 8.0
    lip_h = 4.0

    root_y0 = wall_inner - wall_overlap
    root_y1 = strip_back
    box(comp, cx, (root_y0 + root_y1) / 2.0, z0 - root_h / 2.0,
        w, root_y1 - root_y0, root_h, JOIN, [sh])

    lip_y0 = strip_back - 0.5                         # overlaps root only above strip top
    lip_y1 = strip_back + lip_depth
    return box(comp, cx, (lip_y0 + lip_y1) / 2.0, z0,
               w, lip_y1 - lip_y0, lip_h, JOIN, [sh])


def grip_tab(comp, sh, sx, w=12.0):
    # INTEGRAL overhang grip on the SOLID BACK CASING WALL (the box's own structural wall) - merges into
    # thick material so it's rock-solid, no thin-wall/floating issues. A root buried in the back wall +
    # a FLAT lip that juts 10mm FORWARD over the strip's BACK edge, holding it down. Overhang prints fine.
    top = FLOOR + EXT_H                             # strip top = lip underside (32)
    strip_back = EXT_CY - EXT_D / 2.0              # strip back edge (-133.5; follows the extension if it moves)
    wall_inner = -HALF + WALL                       # back casing wall inner face (-137)
    reach = 10.0                                    # how far the lip juts over the strip
    # root: bridges from INSIDE the back wall to the strip back edge (overlaps the wall -> real merge)
    root_y0 = wall_inner - 1.5                       # 1.5mm into the solid back wall
    root_y1 = strip_back
    box(comp, sx, (root_y0 + root_y1) / 2.0, top - 3, w, root_y1 - root_y0, 6, JOIN, [sh])
    # lip: flat overhang, underside AT the strip top, juts forward over the strip back edge
    lip_y0 = strip_back - 2.0                        # 2mm into the root (real merge)
    lip_y1 = strip_back + reach                      # 10mm forward over the strip
    box(comp, sx, (lip_y0 + lip_y1) / 2.0, top, w, lip_y1 - lip_y0, 3, JOIN, [sh])  # flat overhang lip
    return


def side_grip(comp, sh, cy, gw=15.0):
    # overhang lip on the +X (MikroTik / left) SIDE WALL, reaching 4mm IN over the strip's +X END top
    # corner to hold the strip sideways. Merges straight into the solid full-height side wall.
    top = FLOOR + EXT_H                             # strip top = lip underside (32)
    wall_inner = HALF - WALL                        # +X side wall inner face (137) = strip +X end
    x_in = wall_inner + 2.0                          # 2mm into the side wall (real merge)
    x_over = wall_inner - 4.0                        # 4mm in over the strip end corner
    box(comp, (x_in + x_over) / 2.0, cy, top, x_in - x_over, gw, 3, JOIN, [sh])
    return


def front_grip(comp, sh, sx, w=12.0):
    # 3mm overhang lip on the FRONT retainer wall, reaching back over the strip's FRONT edge - holds
    # the strip's front corner down (companion to the back lips).
    top = FLOOR + EXT_H                             # strip top = lip underside (32)
    strip_front = EXT_CY + EXT_D / 2.0             # strip front edge (-86.5)
    wall_cy = strip_front + 1.5                     # front retainer wall centre (-85)
    reach = 10.0
    box(comp, sx, wall_cy, top - 3, w, WALL, 6, JOIN, [sh])    # root in the front wall (merges)
    lip_y0 = strip_front + 2.0
    lip_y1 = strip_front - reach
    box(comp, sx, (lip_y0 + lip_y1) / 2.0, top, w, lip_y0 - lip_y1, 3, JOIN, [sh])  # flat lip over strip front
    return


def strap_anchor(comp, sh, sx_wall):
    # ADAPTER STRAP anchor: a SHORT lug on a side wall with a THROUGH-HOLE (front<->back) the strap /
    # zip-tie passes through. Thread one through each anchor, over the 4 adapter tops, and cinch -> it
    # squashes the row down.
    s = 1.0 if sx_wall > 0 else -1.0
    tab_x = sx_wall - s * 4.0                        # tab centre, in from the wall inner
    z0 = FLOOR + 41.0                                # raised + shorter (sits above the strip)
    box(comp, tab_x, EXT_CY, z0, 12, 16, 22, JOIN, [sh])             # short lug (Z 44-66), merges the wall
    box(comp, tab_x, EXT_CY, z0 + 5, 7, 22, 12, CUT, [sh])           # THROUGH-HOLE (front<->back) - strap passes through
    return


def cradle_grip(comp, sh, cx, cy, w, d, h, ceiling=None, side_post_clip=None, label='cradle'):
    # SECTIONED grip (saves material vs solid walls): short POSTS at the corners + centre instead of
    # continuous walls - still hugs the device on 3 sides. 2 cantilever SNAP-TABS hook the top edges
    # to lock it; front (toward the ports) stays open. Drops in + clicks; flex the tabs to lift out.
    #
    # ceiling = (x0, x1, y0, y1, z_max): anything of this cradle whose footprint falls inside that
    #   rectangle is TRIMMED to z_max instead of rising into whatever hangs there. A feature that
    #   would be trimmed to nothing is dropped entirely - never leave a floating stub.
    # side_post_clip = (side_sign, z_max): shorten one back SIDE post so a connector on that end
    #   face of the device stays reachable. It is clipped, not windowed: a window through a 2.5mm
    #   post leaves the material above it hanging on nothing.
    wt, clr, P = 2.5, 0.5, 14.0
    hw, hd = w / 2 + clr, d / 2 + clr
    # 31 Aug rework after printed fingers kept snapping: 1.8mm curl with a
    # half-curl ramp band (wedges open gradually), an outer strap tying each
    # hook down its post, and root feet under the device.  See the contract.
    HK = INTERFACE.CRADLE_HOOK_CURL
    RAMP = INTERFACE.CRADLE_HOOK_RAMP

    def part(fx, fy, z0, sx, sy, sz, what):
        # Build one cradle feature, trimmed to whatever hangs above it, and return the
        # top Z it actually reached (None if there was no room for it at all).
        if ceiling:
            x0, x1, y0, y1, z_max = ceiling
            overlaps = (fx + sx / 2.0 > x0 and fx - sx / 2.0 < x1 and
                        fy + sy / 2.0 > y0 and fy - sy / 2.0 < y1)
            if overlaps:
                sz = min(sz, z_max - z0)
        if sz < 1.0:
            SKIPPED.append('{} {} at X{:.1f} omitted BY DESIGN: only {:.1f}mm under the part '
                           'hanging above it. Nothing is lost - a device with that little air '
                           'over it cannot lift out of the cradle anyway'
                           .format(label, what, fx, max(0.0, sz)))
            return None
        box(comp, fx, fy, z0, sx, sy, sz, JOIN, [sh])
        return z0 + sz

    # back: 3 posts that RISE PAST the device top, each with a hook growing off the post + curling IN
    for px in (cx - hw + P / 2, cx, cx + hw - P / 2):
        top = part(px, cy - hd - wt / 2, FLOOR, P, wt, h + 4, 'back post')             # back post (rises to h+4)
        part(px, cy - hd + INTERFACE.CRADLE_FOOT_REACH / 2.0, FLOOR,
             P, INTERFACE.CRADLE_FOOT_REACH, INTERFACE.CRADLE_FOOT_H,
             'post root foot')                                                         # under the device, widens the floor weld
        # A hook only makes sense on a post that still reaches the device top; growing one
        # off a trimmed post would leave it floating in mid-air.
        if top is not None and top >= FLOOR + h - 1e-6:
            part(px, cy - hd - wt - INTERFACE.CRADLE_STRAP_T / 2.0 + 0.2,
                 FLOOR + h - INTERFACE.CRADLE_STRAP_H + 3.0, P,
                 INTERFACE.CRADLE_STRAP_T + 0.4, INTERFACE.CRADLE_STRAP_H,
                 'hook strap')                                                         # ties the hook down the post's outer face
            part(px, cy - hd + (HK - wt) / 2.0, FLOOR + h,
                 P, wt + HK, 1.5, 'back hook catch')                                   # full 1.8 curl - the retention lip
            part(px, cy - hd + (RAMP - wt) / 2.0, FLOOR + h + 1.5,
                 P, wt + RAMP, 1.5, 'back hook ramp')                                  # half curl on top = lead-in
    # front arms sit 11mm BACK from the device front: the lid's holding frames own the front 10mm
    # (tub Y127-137) and the arms used to occupy the exact same space - the lid could not seat.
    fyc = cy + hd - 11 - P / 2
    for s in (-1, 1):
        side_h = h
        if side_post_clip and side_post_clip[0] == s:
            side_h = max(0.0, side_post_clip[1] - FLOOR)
        part(cx + s * (hw + wt / 2), cy - hd + P / 2, FLOOR, wt, P, side_h, 'back side post')
        part(cx + s * (hw - INTERFACE.CRADLE_FOOT_REACH / 2.0),
             cy - hd + P / 2, FLOOR, INTERFACE.CRADLE_FOOT_REACH, P,
             INTERFACE.CRADLE_FOOT_H, 'side post root foot')
        top = part(cx + s * (hw + wt / 2), fyc, FLOOR, wt, P, h + 5, 'front arm')      # rises past top
        part(cx + s * (hw - INTERFACE.CRADLE_FOOT_REACH / 2.0), fyc, FLOOR,
             INTERFACE.CRADLE_FOOT_REACH, P, INTERFACE.CRADLE_FOOT_H,
             'front arm root foot')
        if top is not None and top >= FLOOR + h - 1e-6:
            part(cx + s * (hw + wt + INTERFACE.CRADLE_STRAP_T / 2.0 - 0.2), fyc,
                 FLOOR + h - INTERFACE.CRADLE_STRAP_H + 3.0,
                 INTERFACE.CRADLE_STRAP_T + 0.4, P, INTERFACE.CRADLE_STRAP_H,
                 'front hook strap')
            part(cx + s * (hw + (wt - HK) / 2.0), fyc, FLOOR + h,
                 HK + wt, P, 1.5, 'front hook catch')                                  # full curl lip
            part(cx + s * (hw + (wt - RAMP) / 2.0), fyc, FLOOR + h + 1.5,
                 RAMP + wt, P, 1.5, 'front hook ramp')                                 # lead-in on top
        part(cx + s * w / 4, cy - hd + 2, FLOOR, 3, 3, 3, 'alignment lug')
    return


def build_mount_keyholes(comp, sh):
    """Two BLIND keyholes in the floor - the whole wall mount.

    Nothing passes through into the box.  The screw head lives buried inside
    the floor's own thickness, between a 2mm outer skin (which is what the
    box actually hangs on) and a 2mm inner skin that is never cut - so the
    mount cannot let water, dust or an insect into the sealed volume, and no
    fastener enters it either.

        wall  |==== outer skin ====|   entry hole + shank slot cut here
              |     head channel   |   the head slides along here
              |==== inner skin ====|   SOLID - the box side stays closed
              |      box inside    |

    Every cut is made from the wall side, so the floor still prints
    face-down flat on the bed.
    """
    z0, z1 = INTERFACE.key_channel_z()
    travel = INTERFACE.KEY_TRAVEL
    pad_h = INTERFACE.KEY_PAD_H
    for hx, hy in INTERFACE.KEYHOLE_XY:
        entry_y = hy + travel
        mid_y = (hy + entry_y) / 2.0
        # local thickening, long enough to back the whole keyhole
        box(comp, hx, mid_y, FLOOR, INTERFACE.KEY_PAD_D,
            travel + INTERFACE.KEY_PAD_D, pad_h, JOIN, [sh])
        # the buried channel the head slides in - blind at BOTH faces
        for py in (hy, entry_y):
            cyl(comp, hx, py, z0, INTERFACE.KEY_CHANNEL_D, z1 - z0, CUT, [sh])
        box(comp, hx, mid_y, z0, INTERFACE.KEY_CHANNEL_D, travel,
            z1 - z0, CUT, [sh])
        # through the OUTER skin only: the round entry the head passes,
        # and the slot the shank slides along
        cyl(comp, hx, entry_y, -1.0, INTERFACE.KEY_ENTRY_D,
            z0 + 1.0, CUT, [sh])
        cyl(comp, hx, hy, -1.0, INTERFACE.KEY_SLOT_W, z0 + 1.0, CUT, [sh])
        box(comp, hx, mid_y, -1.0, INTERFACE.KEY_SLOT_W, travel,
            z0 + 1.0, CUT, [sh])
    SKIPPED.append(
        'WALL MOUNT - as simple as a router, and CLOSED: drive two wall screws '
        '{:.0f}mm apart (4.5mm shank, head under {:.1f}mm) leaving about '
        '{:.0f}mm proud, hang the box on them and let it DROP {:.0f}mm. The '
        'heads end up buried INSIDE the floor: {:.1f}mm of skin carries the '
        'box, and the {:.1f}mm skin behind them is never cut - nothing passes '
        'through, so no water or dust can get in through the mount.'
        .format(abs(INTERFACE.KEYHOLE_XY[0][0] - INTERFACE.KEYHOLE_XY[1][0]),
                INTERFACE.WALL_SCREW_HEAD_D, INTERFACE.WALL_SCREW_PROUD,
                INTERFACE.KEY_TRAVEL, INTERFACE.KEY_OUTER_SKIN,
                INTERFACE.key_inner_skin()))
    SKIPPED.append(
        'ORIENTATION: the floor lies on the wall, so model +Z points OUT of '
        'the wall, not up, and the port face (+Y) runs DOWN the wall so cables '
        'hang and drip clear. Internal retention is SETTLED (owner, 18 Aug): '
        'the cradles, extension lips and adapter strap were designed for this '
        'orientation and hold their parts trapped in shear.')
    return


def build(comp):
    # ---- FLOOR + side/back walls. EVERYTHING STOPS AT Y=137: the bottom lid IS the front face
    #      (it fills the slab Y137-140), so the tub leaves that slab completely open. The old
    #      full-depth floor/walls + front lip/rail all ran to Y140 = hard collision, the lid
    #      could never seat. Lid now seats on: floor front edge + wall end faces + the top rail
    #      pulled back behind the lid plane + the 6 bolt bosses. ----
    sh = box(comp, 0, -WALL / 2, 0, BOX_W, BOX_D - WALL, FLOOR, NEW).bodies.item(0)
    sh.name = 'FIR SHELL (tub)'
    box(comp, -HALF + WALL / 2, -WALL / 2, FLOOR, WALL, BOX_D - WALL, BOX_H - FLOOR, JOIN, [sh]) # left wall (ends Y137)
    box(comp,  HALF - WALL / 2, -WALL / 2, FLOOR, WALL, BOX_D - WALL, BOX_H - FLOOR, JOIN, [sh]) # right wall (ends Y137)
    box(comp, 0, -HALF + WALL / 2, FLOOR, BOX_W, WALL, BOX_H - FLOOR, JOIN, [sh]) # back wall
    box(comp, 0, FRONT_Y - 1.5, BOX_H - 8, BOX_W - 2 * WALL, 3, 8, JOIN, [sh])    # top rail BEHIND the lid (Y134-137)
    # ================= RB951 ROUTER BAY (front-left) =================
    m_back = FRONT_Y - 0.5                             # 951 port face right against the lid inside (0.5mm clearance)
    m_cy = m_back - MIK_D / 2
    for sx in (MIK_CX - (MIK_W / 2 - 6), MIK_CX + (MIK_W / 2 - 6)):     # airflow standoffs
        for sy in (m_back - 14, m_back - MIK_D + 8):                    # front row 14 back: clear of the lid's 10mm frames
            cyl(comp, sx, sy, FLOOR, 7, ST_H, JOIN, [sh])
    # +ST_H: the 951 sits on standoffs, so the hooks reach its true top. The brain case hangs
    # only 1.1mm over that top, so the -X end of this cradle CANNOT carry a snap hook: it is
    # trimmed to a plain support post there. Nothing is lost - a router with 1.1mm of air above
    # it cannot lift out of the cradle in the first place.
    cradle_grip(comp, sh, MIK_CX, m_cy, MIK_W, MIK_D, ST_H + MIK_H,
                ceiling=BRAIN_CASE_KEEPOUT, label='MikroTik cradle')

    # (OLD 951 click-in plate seat REMOVED - the integrated bottom lid is the whole front face now)

    # ================= PoE BAY (front-centre) =================
    p_back = FRONT_Y - 0.5                             # PoE switch right against the lid inside too
    p_cy = p_back - POE_D / 2
    for sx in (POE_CX - (POE_W / 2 - 6), POE_CX + (POE_W / 2 - 6)):    # match lid port height
        for sy in (p_back - 14, p_back - POE_D + 8):                   # front row 14 back: clear of the lid's 10mm frames
            cyl(comp, sx, sy, FLOOR, 7, ST_H, JOIN, [sh])
    # The Tenda's DC barrel jack is on the switch's own RIGHT-hand end face (shell -X), 8.3mm
    # forward of its rear. The cradle's back side post stood right across it, so on that end the
    # post is clipped short and the plug now has a clear run out to the side wall.
    poe_jack_post_top = min(FLOOR + POE_JACK_POST_MAX_H,
                            FLOOR + ST_H + POE_JACK_FROM_BASE - POE_PLUG_D / 2.0 - 1.0)
    cradle_grip(comp, sh, POE_CX, p_cy, POE_W, POE_D, ST_H + POE_H,    # snug cradle + snap-tabs
                ceiling=BRAIN_CASE_KEEPOUT, label='switch cradle',
                side_post_clip=(POE_JACK_SIDE, poe_jack_post_top))
    # (OLD PoE click-in plate rails REMOVED - integrated bottom lid replaces them)
    # How much air the plug actually gets on that end face. On the -X end the side wall is the
    # limit; on the +X end it is the MikroTik. Report it rather than let it be found at wiring.
    jack_face_x = POE_CX + POE_JACK_SIDE * POE_W / 2.0
    if POE_JACK_SIDE < 0:
        poe_jack_air = jack_face_x - (-HALF + WALL)
    else:
        poe_jack_air = (MIK_CX - MIK_W / 2.0) - jack_face_x
    if poe_jack_air < INTERFACE.POE_PLUG_MIN_AIR:
        SKIPPED.append(
            'switch DC jack has only {:.1f}mm of air off its end face: a straight barrel plug '
            'needs ~{:.0f}mm, a right-angle plug ~{:.0f}mm'
            .format(poe_jack_air, INTERFACE.POE_PLUG_STRAIGHT_L,
                    INTERFACE.POE_PLUG_RIGHT_ANGLE_L))

    # ================= ALARM HORN: floor mount behind the switch =================
    horn_floor_mount(comp, sh)
    horn_clearances()

    # ================= BRAIN MODULE: bolts to the LID (zero shelf) =================
    # No shelf, no ledges - the brain hangs from the lid; bolt bosses live on the lid.

    # ================= EXTENSION + ADAPTER ZONE (back, clean + light) =================
    # HOLD THE EXTENSION STRIP BY INTEGRAL 10mm OVERHANG LIPS on the SOLID BACK CASING WALL (no bolts):
    # the grips merge into the box's own thick back wall (rock-solid, no thin-wall issues) and each lip
    # juts 10mm forward over the strip's BACK edge to hold it down. The front retainer wall keeps the
    # strip from sliding forward; slide the strip in and its back tucks under the lips.
    # the front retaining wall fills the MikroTik (+X / left) corner but STOPS SHORT on the switch (-X / right)
    # side, leaving a SPACE for the power cable to pass through. (Assumes strip is left-aligned to +X.)
    box(comp, 17, EXT_CY + EXT_D / 2 + 1.5, FLOOR, EXT_W, WALL, EXT_FRONT_RETAINER_H, JOIN, [sh])
    # X positions are placeholders until the real clear spots along the strip back are measured.
    for sx in (-53, 17, 87):
        grip_tab(comp, sh, sx)
    side_grip(comp, sh, EXT_CY)                        # +X (MikroTik) side lip: holds the strip's end sideways
    front_grip(comp, sh, -95)                          # 3mm front lip at the SWITCH (-X) end of the front retainer wall
    strap_anchor(comp, sh, HALF - WALL)                # +X strap lug \  thread a strap/zip-tie between them,
    strap_anchor(comp, sh, -(HALF - WALL))             # -X strap lug /  over the 4 adapters, to hold them down

    # ================= POWER IN + CABLE RUN =================
    # (cord-exit hole/collar + zip-tie tie-down slots on the SWITCH (-X) side REMOVED - Francis cleared
    #  the switch side; mains cord exit / routing to be re-decided.)

    # (BUZZER/alarm seat REMOVED - Francis will just bolt it; no cradle needed)

    # ================= WALL MOUNT: two keyholes, nothing else ================
    # The simplest mount there is, and the one the owner asked for: the same
    # keyhole a router or an extension strip has.  Everything fancier was
    # tried and dropped - a cleat plate, back-wall ears, projecting tabs
    # (328mm wide, would not fit the 300mm bed), screws through the floor
    # (needed the box gutted) and a two-rail hanger (two more parts to print).
    build_mount_keyholes(comp, sh)

    # ================= SIDE-BOLT bosses at the lid overlap    # ================= SIDE-BOLT bosses at the lid overlap (lid skirt bolts in from the SIDE) =================
    # block on the side-wall INNER face + a HORIZONTAL (X) pilot - the bolt
    # enters from the side through the lid skirt, not from the top.  Four rows
    # per wall now: the rearmost row (Y-118) replaces the old back pair, so
    # every cap screw stays drivable with the box hanging on its wall.
    for sx in (-HALF + WALL, HALF - WALL):                  # +-137 (wall inner face)
        s = 1.0 if sx > 0 else -1.0
        for sy in CAP_SIDE_SCREW_Y:
            box(comp, sx - s * 6, sy, BOX_H - 14, 12, 12, 12, JOIN, [sh])     # boss block on the wall inner
            cyl_x(comp, sy, CAP_SCREW_Z, sx,
                  INTERFACE.CAP_BOSS_PILOT_D, 30, CUT, [sh])                  # HORIZONTAL X pilot

    # ================= SELF-CLICK DETENTS (cap snaps onto the tub) =================
    # Stepped bumps on the OUTER wall faces: the descending cap skirt flexes
    # ~0.7mm over them and pops home into its windows - an audible, positive
    # click that holds the cap even before any screw goes in.  The step
    # (full-proud low band, half-proud upper band) is the printable ramp; the
    # flat underside at Z71 is the catch.
    z0, z1 = INTERFACE.CAP_SNAP_Z0, INTERFACE.CAP_SNAP_Z1
    zm = (z0 + z1) / 2.0
    for sy in INTERFACE.CAP_SNAP_SIDE_Y:                      # side walls
        for sxs in (-1.0, 1.0):
            wall = sxs * HALF
            box(comp, wall + sxs * INTERFACE.CAP_SNAP_PROUD / 2.0, sy, z0,
                INTERFACE.CAP_SNAP_PROUD, INTERFACE.CAP_SNAP_W, zm - z0, JOIN, [sh])
            box(comp, wall + sxs * INTERFACE.CAP_SNAP_PROUD / 4.0, sy, zm,
                INTERFACE.CAP_SNAP_PROUD / 2.0, INTERFACE.CAP_SNAP_W,
                z1 - zm, JOIN, [sh])
    for sx in INTERFACE.CAP_SNAP_BACK_X:                      # back wall
        box(comp, sx, -HALF - INTERFACE.CAP_SNAP_PROUD / 2.0, z0,
            INTERFACE.CAP_SNAP_W, INTERFACE.CAP_SNAP_PROUD, zm - z0, JOIN, [sh])
        box(comp, sx, -HALF - INTERFACE.CAP_SNAP_PROUD / 4.0, zm,
            INTERFACE.CAP_SNAP_W, INTERFACE.CAP_SNAP_PROUD / 2.0,
            z1 - zm, JOIN, [sh])

    # ===== seat + bolt the integrated BOTTOM LID into the front opening =====
    build_lid_seat(comp, sh)
    if not (INTERFACE.CAP_BOSS_INSERTS and INTERFACE.COVER_LOCK_INSERTS):
        SKIPPED.append(
            'DECISION PENDING: the often-opened closures (8 cap screws, 2 cover '
            'locks) are M3 self-tappers into 2.6mm printed pilots; repeated '
            'opening strips PETG. Agreed plan: brass inserts for those two '
            'closures only (flip CAP_BOSS_INSERTS / COVER_LOCK_INSERTS in '
            'FIR_Interface.py AFTER setting M3_INSERT_BORE_D from the bought '
            'insert\'s datasheet). BottomLid stays self-tap.')
    return sh


def build_components(comp):
    # the bought devices dropped into their seats (DISPLAY) - hide before printing the shell
    m_back = FRONT_Y - 0.5                             # match build(): devices sit right against the lid
    def p(name, cx, cy, z, sx, sy, sz):
        box(comp, cx, cy, z, sx, sy, sz, NEW).bodies.item(0).name = name
    p('=951 router', MIK_CX, m_back - MIK_D / 2, FLOOR + ST_H, MIK_W, MIK_D, MIK_H)
    p('=PoE switch', POE_CX, m_back - POE_D / 2, FLOOR + ST_H, POE_W, POE_D, POE_H)
    p('=extension', 0, EXT_CY, FLOOR, EXT_W, EXT_D, EXT_H)
    for ax in (-80, 0, 80):
        p('=adapter', ax, EXT_CY, FLOOR + EXT_H, 46, 46, 52)     # plugged into the extension
    # The old 48mm internal buzzer proxy is retired.  The real 104mm horn is
    # now reviewed as an external top-cap candidate in FIR_ShellCheck before
    # any permanent cap mount holes are added.
    # (brain module is shown on the LID, not here - it bolts to the lid)


def build_cables(comp):
    # simple cable runs showing HOW IT'S WIRED (display) - thin tubes
    def w(name, cx, cy, z, sx, sy, sz):
        box(comp, cx, cy, z, sx, sy, sz, NEW).bodies.item(0).name = name
    m_back = FRONT_Y - 0.5                             # match build(): devices sit right against the lid
    # extension cord: out of the extension -> over the top -> down to the front ports
    w('~mains cord', 20, -75, FLOOR + 2, 5, 5, 52)                       # rises out of the extension
    w('~mains cord', -28, -55, 54, 110, 5, 5)                           # along the top, to the left
    w('~mains cord', -85, -52, FLOOR + 2, 5, 5, 52)                     # drops down at the front-left
    w('~mains cord', -85, 25, FLOOR + 3, 5, 155, 5)                     # forward along the floor to the ports
    w('~DC to 951', -40, m_back - 70, FLOOR + 2, 4, 120, 4)              # adapter -> router (along floor)
    # The switch's jack is on its -X end, so its DC lead runs up the -X wall gap, not up the
    # middle of the box where it was drawn before.
    jack_x = POE_CX + POE_JACK_SIDE * (POE_W / 2.0 + 5.0)
    w('~DC to PoE', jack_x, m_back - 60, FLOOR + 2, 4, 110, 4)           # adapter -> switch jack (along floor)
    hx, hy = INTERFACE.horn_foot_centre()
    w('~horn lead', hx, hy + 45, FLOOR + 2, 4, 90, 4)                    # horn -> brain (along the floor)
    for rx in (-100, -84, -68, -52, -36):                               # LAN leads out the front (951)
        w('~LAN', MIK_CX + (rx + 68), FRONT_Y + 8, FLOOR + 16, 4, 22, 4)
    for rx in (38, 54, 70):                                              # LAN leads out the front (PoE)
        w('~LAN', rx, FRONT_Y + 8, FLOOR + 16, 4, 22, 4)


def build_front_cover(comp, ox):
    # REMOVABLE FRONT COVER for the open port/cable area - clips over the ports, cables
    # squeeze out the bottom edge. Shown beside the tub, FLAT (face-up) for printing.
    W, Hh = BOX_W - 4, 78.0
    cov = box(comp, ox, 0, 0, W, Hh, 3.0, NEW).bodies.item(0)
    cov.name = 'FIR FRONT COVER (removable)'
    fillet_vertical(comp, cov, 6.0)
    for i in range(-4, 5):                                  # squeeze-in cable slots along the bottom
        cx = ox + i * 28.0
        box(comp, cx, -Hh / 2 + 8, -1, 4.5, 16, 5, CUT, [cov])
        cyl(comp, cx, -Hh / 2 + 14, -1, 7, 5, CUT, [cov])
    for ty in (-Hh / 2 + 14, Hh / 2 - 14):                  # 4 clip tabs (sides) - clicks onto the tub
        for sx in (-W / 2 - 2, W / 2 + 2):
            box(comp, ox + sx, ty, 0, 5, 9, 3, JOIN, [cov])
    return cov


def build_951_plate(comp, ox, oy):
    # RB951 port plate (measured openings + 0.5 clearance). Snap-tabs click into the tub seat.
    x0, y0 = ox - 57, oy - 14.5
    plate = box(comp, ox, oy, 0, 126, 41, 3, NEW).bodies.item(0)
    plate.name = 'PART 951 port plate'
    fillet_vertical(comp, plate, 4)
    feats = [('c', 11, 15, 6.5, 0), ('c', 19, 10, 2.5, 0), ('r', 25, 9.5, 4, 3), ('r', 33, 9.5, 4, 3),
             ('r', 44.5, 16, 13.5, 12.5), ('r', 58.5, 16, 13.5, 12.5), ('r', 72.5, 16, 13.5, 12.5),
             ('r', 86.5, 16, 13.5, 12.5), ('r', 100.5, 16, 13.5, 12.5)]
    for (k, fx, fz, a, b) in feats:
        if k == 'c':
            cyl(comp, x0 + fx, y0 + fz, -1, a, 5, CUT, [plate])
        else:
            box(comp, x0 + fx, y0 + fz, -1, a, b, 5, CUT, [plate])
    for tx in (-42, 42):                                              # snap-tabs
        box(comp, ox + tx, oy + 41 / 2 + 1.5, 0, 9, 3, 3, JOIN, [plate])
    return plate


def build_poe_plate(comp, ox, oy):
    plate = box(comp, ox, oy, 0, 96, 32, 3, NEW).bodies.item(0)
    plate.name = 'PART PoE port plate'
    fillet_vertical(comp, plate, 4)
    for k in range(5):                                               # 5 RJ45
        box(comp, ox - 32 + k * 16, oy, -1, 13.5, 12.5, 5, CUT, [plate])
    for tx in (-32, 32):
        box(comp, ox + tx, oy + 32 / 2 + 1.5, 0, 9, 3, 3, JOIN, [plate])
    return plate


def horn_floor_mount(comp, sh):
    """Two pads; the horn's foot bolts STRAIGHT onto them.  No sled, no cage.

    Owner (19 Aug): "why is there a horn sled - it should just be two buttons
    to tighten the horn on."  So: two 14mm pads on the floor under the foot's
    two REAR holes (the pair that stays reachable beside the bracket arm),
    each with an M4 pilot sized so an M4 x 10 bottoms at the pilot floor with
    2mm of tub floor beneath.  The apex hole goes unused, by owner decision.
    NEVER use a screw longer than M4 x 10 here.
    """
    for px, py in INTERFACE.horn_mount_points()[1:]:
        cyl(comp, px, py, FLOOR, HORN_PAD_D, HORN_PAD_H, JOIN, [sh])
        cyl(comp, px, py, FLOOR + HORN_PAD_H - HORN_PILOT_DEPTH,
            HORN_PILOT_D, HORN_PILOT_DEPTH, CUT, [sh])
    SKIPPED.append(
        'horn: bolts DIRECTLY to two floor pads with M4 x 10 (owner, 19 Aug - '
        'no sled, no cage; the foot\'s apex hole is unused).')
    if not INTERFACE.HORN_FOOT_MEASURED:
        SKIPPED.append(
            'horn foot triangle assumes the foot centre {:.0f}mm back from the '
            'mouth - the two pads move with that number, so measure it before '
            'printing the tub.'.format(INTERFACE.HORN_FOOT_FROM_MOUTH))
    return


def horn_clearances():
    """Report what the horn is actually touching, in the tub's own build."""
    hx0, hx1, hy0, hy1, hz0, hz1 = INTERFACE.horn_body()
    checks = (
        ('-X side wall', hx0 - (-HALF + WALL)),
        ('cap side-bolt bosses, which stand 12mm off that wall',
         hx0 - (-HALF + WALL + 12.0)),
        ('brain case', (BRAIN_CASE_TO_CAP_X - INTERFACE.CASE_OUTER_W / 2.0) - hx1),
        ('switch cradle', (FRONT_Y - 0.5 - POE_D - 3.0) - hy1),
        ('extension retainer',
         (hy0 - INTERFACE.HORN_BOLT_TAIL) - (EXT_CY + EXT_D / 2.0 + 3.0)),
        ('cap roof underside', CAP_ROOF_INNER_Z - hz1),
    )
    for name, air in checks:
        if air < 1.0:
            SKIPPED.append('HORN INTERFERENCE: {:.1f}mm to the {}'.format(air, name))
    return checks


VERSION = ('v44: GENTLE cradle fingers - 1.8mm ramped hooks, outer straps, root '
           'feet (the old square 4mm hooks snapped printed posts); TUB ONLY '
           '(the cap is FIR_TopLid now); horn bolts DIRECTLY to '
           'two floor pads - no sled, no cage; tamper reed senses the CURVED '
           'LID only, so the top-rail groove is gone; blind watertight '
           'keyholes; floor prints flat / interface {}'
           .format(INTERFACE.INTERFACE_VERSION))


def clear_old(root):
    # delete THIS script's bodies from earlier runs so you never look at
    # stale geometry (TOP LID / HORN prefixes stay listed so bodies from
    # pre-split runs are still cleaned out of old documents)
    old = [b for b in root.bRepBodies
           if b.name.startswith(('FIR SHELL', 'FIR TOP LID', 'FIR HORN', '=', '~'))]
    for b in old:
        try:
            b.deleteMe()
        except Exception as e:
            SKIPPED.append('clear: {}'.format(e))
    return len(old)


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
        removed = clear_old(design.rootComponent)                  # wipe stale bodies from earlier runs FIRST
        # parts laid out. The integrated BOTTOM LID + curved cover are their OWN scripts now
        # (FIR_BottomLid / FIR_CurvedLid) - not rebuilt here; this tub just SEATS + BOLTS them.
        build(design.rootComponent)                                # THE TUB - the only part here now
        # (the deep cap is FIR_TopLid; BottomLid / CurvedLid / brain parts are
        #  their own scripts; the horn sled no longer exists)
        if SHOW_PARTS:
            build_components(design.rootComponent)
            build_cables(design.rootComponent)
        app.activeViewport.fit()
        tub_w = BOX_W + 2.0 * INTERFACE.CAP_SNAP_PROUD
        SKIPPED.append(
            'PRINT ENVELOPE (Ender 3 Plus {:.0f}x{:.0f}): tub {:.1f}mm wide, '
            '{:.1f}mm spare. Print floor-down, flat on the bed.'
            .format(INTERFACE.BED_X, INTERFACE.BED_Y, tub_w,
                    INTERFACE.BED_X - tub_w))
        # ALWAYS report the version + cleanup count so you KNOW Fusion ran the newest code
        ui.messageBox('FIR_Shell {} built.\nCleared {} old body(ies).{}'.format(
            VERSION, removed, ('\nSkipped:\n - ' + '\n - '.join(SKIPPED)) if SKIPPED else ''))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_Shell failed:\n{}'.format(traceback.format_exc()))
