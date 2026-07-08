# FIR_Shell.py - Autodesk Fusion 360 script
# The REAL 280x280 FreeISP TUB, fully detailed so you can SEE how the final holds together:
#  - RB951 + PoE bays: sectioned snap-tab cradles on airflow standoffs (devices drop in + click)
#  - integrated BOTTOM LID closes the front opening + bolts on with 6 self-tap screws
#  - EXTENSION strip: a tall guide wall it rests against + wedge tabs that clamp it down
#  - cable run: front-left cord exit + grommet collar + zip-tie slots cut through the floor
#  - back-wall keyholes (hang on 2 screws); side-bolt bosses for the deep-cap top lid.
# Coordinate frame: origin at footprint centre, +Y = front (ports/UI), +Z = up. HALF = 140.
# This is the main tub only (print BOTTOM-DOWN, no support). Bottom lid + top lid are separate.

import adsk.core, adsk.fusion, adsk.cam, traceback

BOX_W, BOX_D, BOX_H = 280.0, 280.0, 80.0       # tub 80mm; deep-cap lid adds the rest
WALL, FLOOR, CORNER_R = 3.0, 3.0, 10.0
HALF = BOX_W / 2.0
FRONT_Y = HALF - WALL

MIK_W, MIK_D, MIK_H, MIK_CX = 114.0, 139.0, 29.0, 78.0   # MikroTik now +X = LEFT in front view (matches lid)
ST_H = 3.5                                       # 951 standoff -> port face z6..35
POE_W, POE_D, POE_H, POE_CX = 100.0, 100.0, 28.0, -85.0  # PoE switch matches the bottom-lid switch frame
EXT_CY = -110.0                                  # extension/adapter zone (back)
EXT_W, EXT_D, EXT_H = 240.0, 47.0, 29.0
EXT_FRONT_RETAINER_H = EXT_H                     # internal front retainer; wedges attach to back casing wall
ADAP_TOP = 70.0                                  # adapter TOP height above floor (CONFIRM w/ real adapters)
DIV_Y = -82.0                                    # AC/DC divider line (front=DC, back=AC)
SHELF_Z, MOD_CX = 45.0, -5.0
PLATE_TH = 3.0
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
    # boss regardless of the plane-normal direction - used for the front lid-bolt pilots
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cx), mm(cz), 0), mm(d / 2.0))
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
    # rectangle on the xZ plane, extruded through Y - used for cuts through front/back walls
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.sketchCurves.sketchLines.addCenterPointRectangle(
        adsk.core.Point3D.create(mm(cx), mm(cz), 0),
        adsk.core.Point3D.create(mm(cx + sx / 2.0), mm(cz + sz / 2.0), 0))
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
    # cylinder running along X (circle on yZ plane), SYMMETRIC about xcenter - for SIDE-wall bolt pilots
    sk = comp.sketches.add(comp.yZConstructionPlane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cy), mm(cz), 0), mm(d / 2.0))
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
        cyl_y(comp, bx, bz, FRONT_Y - 4.5, 2.6, 16, CUT, [sh])         # self-tap pilot (cuts through)
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


def cradle_grip(comp, sh, cx, cy, w, d, h):
    # SECTIONED grip (saves material vs solid walls): short POSTS at the corners + centre instead of
    # continuous walls - still hugs the device on 3 sides. 2 cantilever SNAP-TABS hook the top edges
    # to lock it; front (toward the ports) stays open. Drops in + clicks; flex the tabs to lift out.
    wt, clr, P = 2.5, 0.5, 14.0
    hw, hd = w / 2 + clr, d / 2 + clr
    HK = 4.0                                                                          # how far the hook curls IN
    # back: 3 posts that RISE PAST the device top, each with a hook growing off the post + curling IN
    for px in (cx - hw + P / 2, cx, cx + hw - P / 2):
        box(comp, px, cy - hd - wt / 2, FLOOR, P, wt, h + 4, JOIN, [sh])               # back post (rises to h+4)
        box(comp, px, cy - hd + HK / 2, FLOOR + h, P, wt + HK, 3, JOIN, [sh])          # hook off the post, curls IN over top
    # front arms sit 11mm BACK from the device front: the lid's holding frames own the front 10mm
    # (tub Y127-137) and the arms used to occupy the exact same space - the lid could not seat.
    fyc = cy + hd - 11 - P / 2
    for s in (-1, 1):
        box(comp, cx + s * (hw + wt / 2), cy - hd + P / 2, FLOOR, wt, P, h, JOIN, [sh])        # back side post
        box(comp, cx + s * (hw + wt / 2), fyc, FLOOR, wt, P, h + 5, JOIN, [sh])                # front arm rises past top
        box(comp, cx + s * (hw - 0.75), fyc, FLOOR + h, HK + wt, P, 3, JOIN, [sh])             # hook off the arm, curls IN
        box(comp, cx + s * w / 4, cy - hd + 2, FLOOR, 3, 3, 3, JOIN, [sh])             # alignment lug
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
    fillet_corners(comp, sh, CORNER_R - WALL, 0, HALF - WALL, back_only=True)     # inner cavity corners R7 FIRST (corner-gap bug)
    fillet_corners(comp, sh, CORNER_R)                                            # then the 2 back outer corners R10 full height

    # ---- AC/DC DIVIDER FRAME REMOVED - there is no separate divider; the extension guide wall + the
    #      bottom-lid power section handle the AC zone now. ----

    # ================= RB951 ROUTER BAY (front-left) =================
    m_back = FRONT_Y - 0.5                             # 951 port face right against the lid inside (0.5mm clearance)
    m_cy = m_back - MIK_D / 2
    for sx in (MIK_CX - (MIK_W / 2 - 6), MIK_CX + (MIK_W / 2 - 6)):     # airflow standoffs
        for sy in (m_back - 14, m_back - MIK_D + 8):                    # front row 14 back: clear of the lid's 10mm frames
            cyl(comp, sx, sy, FLOOR, 7, ST_H, JOIN, [sh])
    cradle_grip(comp, sh, MIK_CX, m_cy, MIK_W, MIK_D, ST_H + MIK_H)     # +ST_H: 951 sits on standoffs, so hooks reach its true top

    # (OLD 951 click-in plate seat REMOVED - the integrated bottom lid is the whole front face now)

    # ================= PoE BAY (front-centre) =================
    p_back = FRONT_Y - 0.5                             # PoE switch right against the lid inside too
    p_cy = p_back - POE_D / 2
    for sx in (POE_CX - (POE_W / 2 - 6), POE_CX + (POE_W / 2 - 6)):    # match lid port height
        for sy in (p_back - 14, p_back - POE_D + 8):                   # front row 14 back: clear of the lid's 10mm frames
            cyl(comp, sx, sy, FLOOR, 7, ST_H, JOIN, [sh])
    cradle_grip(comp, sh, POE_CX, p_cy, POE_W, POE_D, ST_H + POE_H)    # snug cradle + snap-tabs
    # (OLD PoE click-in plate rails REMOVED - integrated bottom lid replaces them)

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

    # ================= THEFT: back-wall keyholes (hang on 2 wall screws) =================
    for kx in (-60, 60):
        cyl_y(comp, kx, BOX_H - 24, -HALF + 1, 11, WALL + 2, CUT, [sh])
        box_y(comp, kx, BOX_H - 33, -HALF + 1, 5, 18, WALL + 2, CUT, [sh])

    # ================= SIDE-BOLT bosses at the lid overlap (lid skirt bolts in from the SIDE) =================
    # block on the side-wall INNER face + a HORIZONTAL (X) self-tap pilot - the bolt enters from the
    # side through the lid skirt, not from the top.
    for sx in (-HALF + WALL, HALF - WALL):                  # +-137 (wall inner face)
        s = 1.0 if sx > 0 else -1.0
        for sy in (-75, 0, 75):
            box(comp, sx - s * 6, sy, BOX_H - 14, 12, 12, 12, JOIN, [sh])     # boss block on the wall inner
            cyl_x(comp, sy, BOX_H - 8, sx, 2.6, 30, CUT, [sh])               # HORIZONTAL X self-tap pilot

    # ===== seat + bolt the integrated BOTTOM LID into the front opening =====
    build_lid_seat(comp, sh)
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
    cyl(comp, 95, -60, FLOOR, 48, 35, NEW).bodies.item(0).name = '=buzzer'
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
    w('~DC to PoE', 30, m_back - 50, FLOOR + 2, 4, 90, 4)                # adapter -> PoE (along floor)
    w('~buzzer wire', 50, -55, FLOOR + 2, 90, 4, 4)                      # buzzer -> brain (along floor)
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


def build_top_lid(comp, ox):
    # TALL-CAP lid: the tub is 80mm but the CLOSED BOX IS 120mm (12cm, Francis) - this cap adds
    # the 37mm of headroom the adapters + hanging brain need. It overlaps the tub walls by just
    # 15mm (Z65-80 assembled; anything deeper is wasted material and buries the keyholes), then
    # its walls RISE to the plate: skirt Z65-117, plate Z117-120. Side bolts sit mid-overlap:
    # tub bosses Z66-78 / pilots Z72 <-> cap holes at print z LH-4 (assembled Z72). The FRONT
    # wall stops at assembled Z83.5 - below that the bottom lid (to Z83) + the cover top (Z83)
    # close the front, and the cover slides in UNDER the cap wall with 0.5mm clearance. Brain
    # bolts to the inner top. Shown beside the tub in print orientation (plate down, skirt up).
    LW = BOX_W + 6.0          # outer - bulges out over the tub
    inner = BOX_W + 1.0       # slides over the 280 tub with clearance
    LH = 52.0                 # skirt: 15mm tub overlap + 37mm headroom -> closed box 120mm
    lid = box(comp, ox, 0, 0, LW, LW, 3.0, NEW).bodies.item(0)
    lid.name = 'FIR TOP LID (deep cap)'
    box(comp, ox, 0, 3.0, LW, LW, LH, JOIN, [lid])                   # skirt block up
    box(comp, ox, 0, 2.0, inner, inner, LH + 2, CUT, [lid])          # hollow -> skirt walls
    fillet_corners(comp, lid, CORNER_R, ox, LW / 2.0)               # round the 4 outer corners FULL HEIGHT (after the skirt)
    for bx in (-58.5, 58.5):                                         # brain bolt bosses (inner top)
        for byo in (-50, 50):
            cyl(comp, ox + bx, byo, 3.0, 7, 12, JOIN, [lid])
            cyl(comp, ox + bx, byo, 3.0, 2.6, 13, CUT, [lid])
    # click ribs: TRUE crush ribs - 0.8mm proud of the skirt inner face, 0.3mm bite into the
    # tub wall (the old ones bulged 4mm inboard = 3.5mm bite, the cap could never slide on).
    # 2 sides + back only; they land at assembled Z73-75, where the FRONT wall doesn't exist.
    for dx, dy in ((1, 0), (-1, 0), (0, -1)):
        box(comp, ox + dx * (inner / 2 + 0.2), dy * (inner / 2 + 0.2), 3 + LH - 10,
            2 if dx else 20, 20 if dx else 2, 2.0, JOIN, [lid])
    # SHORTEN THE FRONT WALL: cut its lower part (inner 281 width only - the rounded corners +
    # side walls stay full) from print z LH-15.5 down past the rim. Assembled, the front wall
    # then spans Z83.5-117: below it the bottom lid's build-out (to Z83) + the cover top (Z83)
    # close the front, and the sliding cover passes UNDER the wall with 0.5mm clearance.
    # ASSEMBLY NOTE: flip the printed cap over about the FRONT-BACK axis (left<->right swap) so
    # the short-wall edge stays at the FRONT; the bolt-hole pattern is symmetric either way.
    box(comp, ox, 141.75, LH - 15.5, inner, 5.5, 20, CUT, [lid])
    # 6 clearance holes for the tub's side bolts (3 per side wall @ Y=-75/0/75; tub pilot Z72 ->
    # print z LH-4). Without these the cap could not be bolted down at all.
    for sxs in (-1, 1):
        for byy in (-75, 0, 75):
            cyl_x(comp, byy, LH - 4, ox + sxs * (inner / 2 + 1.5), 3.4, 6, CUT, [lid])
    if SHOW_PARTS:
        box(comp, ox, 0, 16, 135, 120, 40, NEW).bodies.item(0).name = '=brain (bolts to lid)'
    return lid


VERSION = 'v19 top cap TALL again: closed box 120mm, 15mm overlap, front wall stops @Z83.5, bolts @Z72'


def clear_old(root):
    # delete THIS script's bodies from earlier runs so you never look at stale/floating geometry
    old = [b for b in root.bRepBodies
           if b.name.startswith(('FIR SHELL', 'FIR TOP LID', '=', '~'))]
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
        build(design.rootComponent)                                # 1 TUB (now with front lid seat + bolts)
        build_top_lid(design.rootComponent, BOX_W + 50)            # 2 DEEP TOP LID
        # (3 old front cover, 4 951 plate, 5 PoE plate REMOVED - replaced by the integrated bottom lid)
        if SHOW_PARTS:
            build_components(design.rootComponent)
            build_cables(design.rootComponent)
        app.activeViewport.fit()
        # ALWAYS report the version + cleanup count so you KNOW Fusion ran the newest code
        ui.messageBox('FIR_Shell {} built.\nCleared {} old body(ies).{}'.format(
            VERSION, removed, ('\nSkipped:\n - ' + '\n - '.join(SKIPPED)) if SKIPPED else ''))
    except:  # noqa
        if ui:
            ui.messageBox('FIR_Shell failed:\n{}'.format(traceback.format_exc()))
