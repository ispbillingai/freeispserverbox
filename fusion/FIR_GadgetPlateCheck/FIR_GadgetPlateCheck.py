# FIR_GadgetPlateCheck.py - Autodesk Fusion 360 script
#
# SMALL ASSEMBLY INSPECTION ONLY -- never export this model for printing.
# It uses the active printable FIR_ModuleGadget and FIR_ModulePlate builders,
# puts the real snug-fit ModulePlate directly below the gadget's real Z=3 ledge, and
# makes the case transparent so the tray-boss / plate-hole fit is easy to inspect.
#
# BOARD ORIENTATION CONTRACT (confirmed by the owner): the brain PCB is
# COMPONENT-SIDE DOWN.  Its silkscreen/ESP32/socket face hangs toward the
# ModulePlate; only the bare solder side faces the case roof.  This checker
# draws that direction explicitly and refuses the assembly if the *face to
# face* ModulePlate-top -> PCB-component-face distance leaves 50..55mm.

import importlib.util
import os
import sys
import traceback

import adsk.core, adsk.fusion, adsk.cam


CHECK_PREFIX = 'CHECK: GADGET+PLATE'
CHECK_VERSION = ('v5: live-reloaded actual Gadget + snug-fit Plate; component-side-down '
                 'PCB stack, J4/J5 service-drop route, 0.25..0.50mm tray-side '
                 'fit and 50..55mm face-to-face hard checks')
TRAY_EXPLODE_Z = 0.0        # 0 = seated. Set e.g. 12 only to lift the tray for inspection.
CASE_OPACITY = 0.28
TRAY_OPACITY = 0.90
MODULE_OPACITY = 0.42
PCB_OPACITY = 0.58
COMPONENT_OPACITY = 0.36
ROUTE_OPACITY = 0.24

REQUIRED_GAP_MIN = 50.0
REQUIRED_GAP_MAX = 55.0

# Inspection-envelope dimensions only.  They deliberately do not modify the
# PCB or the printable case: they make the route from the populated, downward
# facing J4/J5 headers to the real side exit easy to see in a transparent view.
HEADER_STACK_H = 4.0
HEADER_EDGE_OUTSET = 2.0
HEADER_ROUTE_W = 4.0

CM = 0.1


def mm(value):
    return value * CM


def _load_active_builder(script_name):
    """Load a sibling active Fusion script in workspace or deployed layout."""
    script_file = globals().get('__file__', '')
    script_dir = (os.path.dirname(os.path.abspath(script_file))
                  if script_file else os.getcwd())
    source_file = script_name + '.py'
    candidates = [os.path.join(script_dir, '..', script_name, source_file)]
    source_root = os.environ.get('FIR_SOURCE_ROOT')
    if source_root:
        candidates.append(os.path.join(source_root, script_name, source_file))

    for candidate in candidates:
        path = os.path.realpath(os.path.abspath(candidate))
        if not os.path.isfile(path):
            continue
        # Fusion may keep Python modules alive between script runs.  Always
        # discard this inspection loader's copy so a rerun cannot show an old
        # Gadget/Plate after the printable source has changed.
        cache_name = '_freeisp_gadget_plate_' + script_name.lower()
        sys.modules.pop(cache_name, None)
        spec = importlib.util.spec_from_file_location(cache_name, path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[cache_name] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError('{} builder not found beside FIR_GadgetPlateCheck'.format(script_name))


def translate_body(comp, body, dx, dy, dz):
    coll = adsk.core.ObjectCollection.create()
    coll.add(body)
    matrix = adsk.core.Matrix3D.create()
    matrix.translation = adsk.core.Vector3D.create(mm(dx), mm(dy), mm(dz))
    comp.features.moveFeatures.add(comp.features.moveFeatures.createInput(coll, matrix))


def set_opacity(body, opacity):
    try:
        body.opacity = opacity
    except Exception:
        pass


def _number(value, name):
    """Return a dimension as float, with a useful error for a bad builder."""
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError('{} must be a numeric millimetre value'.format(name))


def component_face_z(gadget):
    """Return the DOWN-facing populated PCB face in the gadget datum.

    Newer Gadget builds publish PCB_COMPONENT_FACE_Z directly.  The fallback
    is intentionally orientation-aware: PCB_TOP_Z is the UP-facing bare solder
    face, so the component face is one PCB thickness below it.
    """
    explicit = getattr(gadget, 'PCB_COMPONENT_FACE_Z', None)
    if explicit is not None:
        return _number(explicit, 'PCB_COMPONENT_FACE_Z')
    pcb_top = _number(getattr(gadget, 'PCB_TOP_Z', None), 'PCB_TOP_Z')
    pcb_th = _number(getattr(gadget, 'PCB_TH', None), 'PCB_TH')
    return pcb_top - pcb_th


def stack_contract(gadget, plate_source):
    """Compute the user-specified face-to-face PCB clearance.

    The plate datum is taken from the real ModulePlate source when available;
    its required physical value is still explicitly checked as Z=3.0mm.  A
    stale or mismatched builder therefore cannot quietly pass this inspection.
    """
    plate_top = _number(
        getattr(plate_source, 'PLATE_TOP', getattr(gadget, 'PLATE_SEAT_Z', 3.0)),
        'ModulePlate PLATE_TOP')
    component_face = component_face_z(gadget)
    clearance = component_face - plate_top
    plate_datum_ok = abs(plate_top - 3.0) < 0.001
    clearance_ok = REQUIRED_GAP_MIN <= clearance <= REQUIRED_GAP_MAX
    pocket_w = _number(getattr(gadget, 'IN_W', None), 'Gadget IN_W')
    pocket_h = _number(getattr(gadget, 'IN_H', None), 'Gadget IN_H')
    tray_w = _number(getattr(plate_source, 'PLATE_W', None), 'ModulePlate PLATE_W')
    tray_h = _number(getattr(plate_source, 'PLATE_H', None), 'ModulePlate PLATE_H')
    tray_fit_x = (pocket_w - tray_w) / 2.0
    tray_fit_y = (pocket_h - tray_h) / 2.0
    tray_fit_ok = 0.25 <= min(tray_fit_x, tray_fit_y) <= 0.50
    return {
        'plate_top': plate_top,
        'component_face': component_face,
        'pcb_solder_face': _number(getattr(gadget, 'PCB_TOP_Z', None),
                                   'PCB_TOP_Z'),
        'pcb_thickness': _number(getattr(gadget, 'PCB_TH', None), 'PCB_TH'),
        'clearance': clearance,
        'plate_datum_ok': plate_datum_ok,
        'clearance_ok': clearance_ok,
        'tray_w': tray_w,
        'tray_h': tray_h,
        'tray_fit_x': tray_fit_x,
        'tray_fit_y': tray_fit_y,
        'tray_fit_ok': tray_fit_ok,
        'ok': plate_datum_ok and clearance_ok and tray_fit_ok,
    }


def _make_box(comp, source, name, cx, cy, z0, sx, sy, sz, opacity):
    """Make a named, transparent inspection-only envelope."""
    body = source.box(comp, cx, cy, z0, sx, sy, sz, source.NEW).bodies.item(0)
    body.name = CHECK_PREFIX + ' ' + name
    set_opacity(body, opacity)
    return body


def _rects_overlap(a, b):
    """Strict 3-D AABB overlap; touching faces are deliberately not a clash."""
    return (a['x0'] < b['x1'] and a['x1'] > b['x0'] and
            a['y0'] < b['y1'] and a['y1'] > b['y0'] and
            a['z0'] < b['z1'] and a['z1'] > b['z0'])


def _rect(name, cx, cy, z0, sx, sy, sz):
    return {
        'name': name,
        'x0': cx - sx / 2.0, 'x1': cx + sx / 2.0,
        'y0': cy - sy / 2.0, 'y1': cy + sy / 2.0,
        'z0': z0, 'z1': z0 + sz,
    }


def build_j4_j5_service_route(comp, gadget, stack, module_rects):
    """Draw the J4/J5 header-to-exit service volume from active Gadget data.

    The PCB's populated face points DOWN.  J4/J5 header plugs therefore hang
    down from that face.  The exit itself belongs to the printable Gadget, so
    every coordinate below is read from the live Gadget source rather than
    copied into this check.  The visual route consists of: header stack,
    vertical service drop, a side-wall throat, and the exact 50 x 5 exit
    volume.  All are inspection-only transparent bodies.
    """
    pcb_w = _number(getattr(gadget, 'PCB_W', None), 'PCB_W')
    body_w = _number(getattr(gadget, 'W', None), 'Gadget W')
    wall = _number(getattr(gadget, 'WALL', None), 'Gadget WALL')
    jumper_y = _number(getattr(gadget, 'JUMPER_Y', None), 'JUMPER_Y')
    jumper_w = _number(getattr(gadget, 'JUMPER_W', None), 'JUMPER_W')
    jumper_h = _number(getattr(gadget, 'JUMPER_H', None), 'JUMPER_H')
    jumper_z0 = _number(getattr(gadget, 'JUMPER_Z0', None), 'JUMPER_Z0')
    header_y0 = _number(getattr(gadget, 'J4_J5_Y_MIN', None),
                        'J4_J5_Y_MIN')
    header_y1 = _number(getattr(gadget, 'J4_J5_Y_MAX', None),
                        'J4_J5_Y_MAX')
    if header_y1 <= header_y0:
        raise ValueError('J4/J5 header span must have positive length')
    if jumper_w <= 0.0 or jumper_h <= 0.0:
        raise ValueError('J4/J5 jumper opening must have positive size')

    component_face = stack['component_face']
    header_z0 = component_face - HEADER_STACK_H
    header_z1 = component_face
    jumper_y0 = jumper_y - jumper_w / 2.0
    jumper_y1 = jumper_y + jumper_w / 2.0
    jumper_z1 = jumper_z0 + jumper_h
    header_cy = (header_y0 + header_y1) / 2.0
    header_span = header_y1 - header_y0

    # J4/J5 sit on the +X edge.  The header envelope starts at the PCB edge
    # and projects only 4mm into the internal side-wall clearance.
    header_cx = pcb_w / 2.0 + HEADER_EDGE_OUTSET
    header = _rect('J4/J5 component-side header envelope', header_cx,
                   header_cy, header_z0, HEADER_ROUTE_W, header_span,
                   HEADER_STACK_H)
    _make_box(comp, gadget, header['name'] + ' (hangs DOWN)', header_cx,
              header_cy, header_z0, HEADER_ROUTE_W, header_span,
              HEADER_STACK_H, COMPONENT_OPACITY)

    # The flexible wires can drop vertically beside the PCB before turning
    # through the exit.  Its Z range intentionally encloses both the header
    # level and the exact active JUMPER_Z0..JUMPER_Z0+JUMPER_H range, so a
    # moved exit visibly changes this inspection geometry on the next rerun.
    drop_z0 = min(header_z0, jumper_z0)
    drop_z1 = max(header_z1, jumper_z1)
    drop = _rect('J4/J5 vertical service-drop envelope', header_cx,
                 header_cy, drop_z0, HEADER_ROUTE_W, header_span,
                 drop_z1 - drop_z0)
    _make_box(comp, gadget, drop['name'], header_cx, header_cy, drop_z0,
              HEADER_ROUTE_W, header_span, drop_z1 - drop_z0,
              ROUTE_OPACITY)

    # A short horizontal throat joins the vertical service area to the actual
    # side-wall cut.  Use the union of the header and exit spans: if a future
    # Gadget shifts the 50x5 exit to the middle of the side, the check shows
    # the required sideways wire travel instead of pretending it is straight.
    throat_x0 = pcb_w / 2.0
    throat_x1 = body_w / 2.0 + wall * 1.5
    throat_y0 = min(header_y0, jumper_y0)
    throat_y1 = max(header_y1, jumper_y1)
    throat = _rect('J4/J5 route-to-exit throat envelope',
                   (throat_x0 + throat_x1) / 2.0,
                   (throat_y0 + throat_y1) / 2.0, jumper_z0,
                   throat_x1 - throat_x0, throat_y1 - throat_y0, jumper_h)
    _make_box(comp, gadget, throat['name'],
              (throat_x0 + throat_x1) / 2.0,
              (throat_y0 + throat_y1) / 2.0, jumper_z0,
              throat_x1 - throat_x0, throat_y1 - throat_y0, jumper_h,
              ROUTE_OPACITY)

    # This is an exact transparent proxy for the printable side opening.  It
    # extends wall*1.5 either side of the wall centre, matching Gadget.build.
    exit_box = _rect('J4/J5 active side-exit envelope (JUMPER)',
                     body_w / 2.0, jumper_y, jumper_z0,
                     wall * 3.0, jumper_w, jumper_h)
    _make_box(comp, gadget, exit_box['name'], body_w / 2.0, jumper_y,
              jumper_z0, wall * 3.0, jumper_w, jumper_h, ROUTE_OPACITY)

    collisions = []
    for route_part in (header, drop, throat):
        for module in module_rects:
            if _rects_overlap(route_part, module):
                collisions.append('{} overlaps {}'.format(route_part['name'],
                                                          module['name']))

    direct_y_coverage = jumper_y0 <= header_y0 and jumper_y1 >= header_y1
    return collisions, {
        'header_y0': header_y0,
        'header_y1': header_y1,
        'header_z0': header_z0,
        'header_z1': header_z1,
        'drop_z0': drop_z0,
        'drop_z1': drop_z1,
        'jumper_y0': jumper_y0,
        'jumper_y1': jumper_y1,
        'jumper_z0': jumper_z0,
        'jumper_z1': jumper_z1,
        'direct_y_coverage': direct_y_coverage,
    }


def build_inspection_envelopes(comp, gadget, plate_source, stack):
    """Draw the real module bounds, populated PCB face, and J4/J5 route.

    The actual printable plate has its clips/bosses, but not the electronics.
    These semitransparent bodies make the occupied volume legible.  They are
    only inspection geometry and are never joined to either printable body.
    """
    plate_top = stack['plate_top']
    module_rects = []
    raise_z = _number(getattr(plate_source, 'RAISE', 0.0), 'ModulePlate RAISE')
    for name, width, length, height, cx, cy, mount in plate_source.MODULES:
        z0 = plate_top if mount == 'flat' else plate_top + raise_z
        _make_box(comp, gadget, 'plate module envelope: ' + name,
                  cx, cy, z0, width, length, height, MODULE_OPACITY)
        module_rects.append(_rect(name, cx, cy, z0, width, length, height))

    pcb_w = _number(getattr(gadget, 'PCB_W', None), 'PCB_W')
    pcb_h = _number(getattr(gadget, 'PCB_H', None), 'PCB_H')
    pcb_th = stack['pcb_thickness']
    component_z = stack['component_face']
    solder_z = stack['pcb_solder_face']
    # Component-side DOWN: board starts at its populated component face and
    # rises only through its 1.6mm laminate to the bare solder face above.
    _make_box(comp, gadget, 'brain PCB 115x115 (component face DOWN)',
              0.0, 0.0, component_z, pcb_w, pcb_h, pcb_th, PCB_OPACITY)

    socket_h = _number(getattr(gadget, 'PCB_SOCKET_H', 8.5), 'PCB_SOCKET_H')
    devkit_h = _number(getattr(gadget, 'PCB_DEVKIT_H', 13.0), 'PCB_DEVKIT_H')
    # Known physical ESP32 clearance model: 28 x 56mm DevKit on 8.5mm sockets.
    # It starts at the component face and descends toward the ModulePlate.
    socket_z = component_z - socket_h
    devkit_z = socket_z - devkit_h
    socket = _rect('ESP32 socket envelope', 0.0, 0.0, socket_z,
                   28.0, 56.0, socket_h)
    devkit = _rect('ESP32 DevKit envelope', 0.0, 0.0, devkit_z,
                   28.0, 56.0, devkit_h)
    _make_box(comp, gadget, socket['name'] + ' (hangs DOWN)',
              0.0, 0.0, socket_z, 28.0, 56.0, socket_h, COMPONENT_OPACITY)
    _make_box(comp, gadget, devkit['name'] + ' (hangs DOWN)',
              0.0, 0.0, devkit_z, 28.0, 56.0, devkit_h, COMPONENT_OPACITY)

    collisions = []
    for pcb_part in (socket, devkit):
        for module in module_rects:
            if _rects_overlap(pcb_part, module):
                collisions.append('{} overlaps {}'.format(pcb_part['name'],
                                                          module['name']))
    # This proves the board body follows the contract exactly rather than a
    # hidden hard-coded height.  It is also useful when reading a screenshot.
    if abs((component_z + pcb_th) - solder_z) > 0.02:
        collisions.append('PCB thickness mismatch: component/solder faces do not span {:.2f}mm'
                          .format(pcb_th))
    route_collisions, route = build_j4_j5_service_route(
        comp, gadget, stack, module_rects)
    collisions.extend(route_collisions)
    return collisions, route


def clear_old(comp):
    removed = 0
    for index in range(comp.bRepBodies.count - 1, -1, -1):
        body = comp.bRepBodies.item(index)
        if body.name.startswith(CHECK_PREFIX):
            body.deleteMe()
            removed += 1
    return removed


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
        removed = clear_old(comp)
        # The builders themselves cache the common interface.  Drop that too
        # so this check is a truthful live view after any deployed sync.
        sys.modules.pop('_freeisp_shared_interface', None)
        gadget = _load_active_builder('FIR_ModuleGadget')
        plate_source = _load_active_builder('FIR_ModulePlate')

        stack = stack_contract(gadget, plate_source)

        case = gadget.build(comp)
        case.name = CHECK_PREFIX + ' brain case (actual FIR_ModuleGadget)'
        set_opacity(case, CASE_OPACITY)

        tray = plate_source.build_plate(comp)
        tray.name = CHECK_PREFIX + ' electronics tray (actual FIR_ModulePlate)'
        # The plate is Z=0..3; the case ledge begins at Z=3.  Its top face
        # contacts the underside of the ledge, while screws enter from below.
        # Keep the seated assembly in the original part datum.  A move is
        # useful only when the reviewer deliberately requests an exploded
        # inspection view.
        if TRAY_EXPLODE_Z:
            translate_body(comp, tray, 0.0, 0.0, TRAY_EXPLODE_Z)
        set_opacity(tray, TRAY_OPACITY)

        collisions, route = build_inspection_envelopes(
            comp, gadget, plate_source, stack)

        gadget_bad, gadget_detail = gadget.validate()
        plate_bad, plate_detail = plate_source.validate()
        app.activeViewport.fit()
        status = 'PASS' if stack['ok'] else 'FAIL'
        plate_datum_status = ('PASS' if stack['plate_datum_ok'] else
                              'FAIL (expected Z=3.0mm)')
        clearance_status = ('PASS' if stack['clearance_ok'] else
                            'FAIL (must be 50.0..55.0mm)')
        tray_fit_status = ('PASS' if stack['tray_fit_ok'] else
                           'FAIL (must be 0.25..0.50mm per side)')
        collision_status = ('none' if not collisions else '; '.join(collisions))
        message = (
            '{}\n\n'
            'STACK CONTRACT: {}\n'
            'ModulePlate flat top: Z={:.1f}mm [{}]\n'
            'PCB component face (DOWN, toward plate): Z={:.1f}mm\n'
            'PCB solder face (UP, toward roof): Z={:.1f}mm\n'
            'FACE-TO-FACE GAP (plate top -> PCB component face): {:.1f}mm [{}]\n'
            'TRAY PUSH-FIT: {:.1f} x {:.1f}mm plate; {:.2f} x {:.2f}mm per-side pocket gap [{}]\n'
            'ESP32/socket envelopes descend from the component face toward the plate.\n'
            'J4/J5 service path: header Z{:.1f}..{:.1f} -> vertical drop '
            'Z{:.1f}..{:.1f} -> active exit Y{:.1f}..{:.1f}, Z{:.1f}..{:.1f} [{}]\n'
            'Envelope collisions: {}\n\n'
            'The real snug-fit ModulePlate is seated directly below the ModuleGadget '
            'ledge. The transparent case shows all four tray-hole / tray-boss locations.\n'
            'Cleared {} prior inspection body(ies).\n\n'
            'Gadget source: {}\n'
            'Gadget self-check: {}\n'
            'Plate self-check: {}'
        ).format(
            CHECK_VERSION, status,
            stack['plate_top'], plate_datum_status,
            stack['component_face'], stack['pcb_solder_face'],
            stack['clearance'], clearance_status,
            stack['tray_w'], stack['tray_h'], stack['tray_fit_x'], stack['tray_fit_y'], tray_fit_status,
            route['header_z0'], route['header_z1'],
            route['drop_z0'], route['drop_z1'],
            route['jumper_y0'], route['jumper_y1'],
            route['jumper_z0'], route['jumper_z1'],
            'direct Y coverage' if route['direct_y_coverage'] else
            'sideways travel shown',
            collision_status,
            removed,
            getattr(gadget, 'VERSION', 'unknown'),
            'PASS' if not gadget_bad else 'PROBLEM: ' + '; '.join(gadget_bad),
            'PASS' if not plate_bad else 'PROBLEM: ' + '; '.join(plate_bad),
        )
        ui.messageBox(message)
    except:  # noqa
        if ui:
            ui.messageBox('FIR_GadgetPlateCheck failed:\n{}'.format(
                traceback.format_exc()))
