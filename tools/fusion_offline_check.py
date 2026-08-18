"""Offline verification harness for the FIR_* Fusion 360 scripts.

Registers a fake ``adsk`` API in ``sys.modules`` BEFORE importing each script,
records every extrude/loft as an exact prism (rect / circle / polygon cross-
section swept along one axis), then runs each script's REAL ``run()`` - never
the bare ``build_*`` helpers, so the final message-box code path is exercised
too.  Rigid moves (the all-up placements are all axis-permuting rotations) are
applied as body transforms, so point-membership queries work in assembled
coordinates.

Usage:
    python tools/fusion_offline_check.py                 # workspace tree
    python tools/fusion_offline_check.py <deployed_dir>  # a second tree, e.g.
        "%APPDATA%/Autodesk/Autodesk Fusion 360/API/Scripts"

Exit code 0 = every check passed.  All lengths reported in millimetres.
Known limits: fillets/chamfers/text are no-ops (the scripts guard them), so
material ADDED by a fillet is invisible here - the shared contract's
validate() covers the one case that matters (the R7 corner-pocket driver
corridors).
"""

import importlib.util
import math
import os
import sys
import types

CM_TO_MM = 10.0

# --------------------------------------------------------------------------
# minimal geometry
# --------------------------------------------------------------------------


class Mat(object):
    """Rotation + translation, in mm."""

    def __init__(self):
        self.r = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        self.t = [0.0, 0.0, 0.0]

    def set_rotation(self, angle, axis):
        ax, ay, az = axis
        n = math.sqrt(ax * ax + ay * ay + az * az)
        ax, ay, az = ax / n, ay / n, az / n
        c, s = math.cos(angle), math.sin(angle)
        ic = 1.0 - c
        self.r = [
            [c + ax * ax * ic, ax * ay * ic - az * s, ax * az * ic + ay * s],
            [ay * ax * ic + az * s, c + ay * ay * ic, ay * az * ic - ax * s],
            [az * ax * ic - ay * s, az * ay * ic + ax * s, c + az * az * ic],
        ]

    def apply(self, p):
        x, y, z = p
        r, t = self.r, self.t
        return (r[0][0] * x + r[0][1] * y + r[0][2] * z + t[0],
                r[1][0] * x + r[1][1] * y + r[1][2] * z + t[1],
                r[2][0] * x + r[2][1] * y + r[2][2] * z + t[2])

    def apply_inverse(self, p):
        x, y, z = (p[0] - self.t[0], p[1] - self.t[1], p[2] - self.t[2])
        r = self.r
        return (r[0][0] * x + r[1][0] * y + r[2][0] * z,
                r[0][1] * x + r[1][1] * y + r[2][1] * z,
                r[0][2] * x + r[1][2] * y + r[2][2] * z)


class Solid(object):
    """One recorded extrude: 2D shape swept along an axis, local frame, mm."""

    __slots__ = ('kind', 'plane', 'shape', 'a0', 'a1', 'op')

    def __init__(self, kind, plane, shape, a0, a1, op):
        self.kind = kind          # 'rect' | 'circle' | 'poly'
        self.plane = plane        # 'xY' | 'xZ' | 'yZ'
        self.shape = shape
        self.a0, self.a1 = (a0, a1) if a0 <= a1 else (a1, a0)
        self.op = op              # 'new' | 'join' | 'cut'

    def uvw(self, p):
        x, y, z = p
        if self.plane == 'xY':
            return x, y, z
        if self.plane == 'xZ':
            return x, z, y
        return y, z, x            # yZ

    def contains(self, p, tol=1e-6):
        u, v, w = self.uvw(p)
        if w < self.a0 - tol or w > self.a1 + tol:
            return False
        if self.kind == 'rect':
            cx, cy, hw, hh = self.shape
            return abs(u - cx) <= hw + tol and abs(v - cy) <= hh + tol
        if self.kind == 'circle':
            cx, cy, r = self.shape
            return math.hypot(u - cx, v - cy) <= r + tol
        pts = self.shape
        inside = False
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if ((yi > v) != (yj > v)) and \
                    (u < (xj - xi) * (v - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def aabb(self):
        if self.kind == 'rect':
            cx, cy, hw, hh = self.shape
            u0, u1, v0, v1 = cx - hw, cx + hw, cy - hh, cy + hh
        elif self.kind == 'circle':
            cx, cy, r = self.shape
            u0, u1, v0, v1 = cx - r, cx + r, cy - r, cy + r
        else:
            us = [p[0] for p in self.shape]
            vs = [p[1] for p in self.shape]
            u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
        w0, w1 = self.a0, self.a1
        if self.plane == 'xY':
            return (u0, u1, v0, v1, w0, w1)
        if self.plane == 'xZ':
            return (u0, u1, w0, w1, v0, v1)
        return (w0, w1, u0, u1, v0, v1)


class Body(object):
    def __init__(self, comp, name):
        self.component = comp
        self.name = name
        self.records = []          # ordered (op, Solid)
        self.transforms = []       # applied in order, local -> world
        self.opacity = 1.0
        self.edges = []
        self.faces = []
        self.isLightBulbOn = True

    def deleteMe(self):
        if self in self.component.bodies_list:
            self.component.bodies_list.remove(self)

    def to_local(self, p):
        for m in reversed(self.transforms):
            p = m.apply_inverse(p)
        return p

    def material_at(self, p):
        """Exact prism-CSG membership at a WORLD point."""
        q = self.to_local(p)
        state = False
        for op, solid in self.records:
            if solid.contains(q):
                state = op != 'cut'
        return state

    def world_aabb(self):
        boxes = []
        for op, solid in self.records:
            if op == 'cut':
                continue
            x0, x1, y0, y1, z0, z1 = solid.aabb()
            corners = [(x, y, z) for x in (x0, x1) for y in (y0, y1)
                       for z in (z0, z1)]
            for m in self.transforms:
                corners = [m.apply(c) for c in corners]
            xs = [c[0] for c in corners]
            ys = [c[1] for c in corners]
            zs = [c[2] for c in corners]
            boxes.append((min(xs), max(xs), min(ys), max(ys),
                          min(zs), max(zs)))
        if not boxes:
            return None
        return (min(b[0] for b in boxes), max(b[1] for b in boxes),
                min(b[2] for b in boxes), max(b[3] for b in boxes),
                min(b[4] for b in boxes), max(b[5] for b in boxes))

    def solids(self, op=None, kind=None, plane=None):
        return [s for o, s in self.records
                if (op is None or o == op)
                and (kind is None or s.kind == kind)
                and (plane is None or s.plane == plane)]


# --------------------------------------------------------------------------
# the adsk stub
# --------------------------------------------------------------------------


def install_stub():
    core = types.ModuleType('adsk.core')
    fusion = types.ModuleType('adsk.fusion')
    cam = types.ModuleType('adsk.cam')
    adsk = types.ModuleType('adsk')
    adsk.core, adsk.fusion, adsk.cam = core, fusion, cam

    messages = []

    class Point3D(object):
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

        @staticmethod
        def create(x, y, z):
            return Point3D(x, y, z)

    class Vector3D(object):
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

        @staticmethod
        def create(x, y, z):
            return Vector3D(x, y, z)

        def normalize(self):
            n = math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)
            if n:
                self.x, self.y, self.z = self.x / n, self.y / n, self.z / n

    class Matrix3D(object):
        def __init__(self):
            self.mat = Mat()

        @staticmethod
        def create():
            return Matrix3D()

        def setToRotation(self, angle, axis, origin):
            self.mat.set_rotation(angle, (axis.x, axis.y, axis.z))

        @property
        def translation(self):
            t = self.mat.t
            return Vector3D(t[0] / CM_TO_MM, t[1] / CM_TO_MM, t[2] / CM_TO_MM)

        @translation.setter
        def translation(self, v):
            self.mat.t = [v.x * CM_TO_MM, v.y * CM_TO_MM, v.z * CM_TO_MM]

    class ValueInput(object):
        def __init__(self, v):
            self.value = v

        @staticmethod
        def createByReal(v):
            return ValueInput(v)

    class ObjectCollection(object):
        def __init__(self):
            self.items = []

        @staticmethod
        def create():
            return ObjectCollection()

        def add(self, item):
            self.items.append(item)

        @property
        def count(self):
            return len(self.items)

        def __iter__(self):
            return iter(self.items)

    class Line3D(object):
        pass

    class Plane(object):
        pass

    class ViewOrientations(object):
        TopViewOrientation = 1

    class Camera(object):
        viewOrientation = None

    class Viewport(object):
        def __init__(self):
            self.camera = Camera()

        def fit(self):
            pass

    class ConstructionPlane(object):
        def __init__(self, ptype, offset=0.0):
            self.ptype = ptype
            self.offset = offset      # mm, along the plane normal
            self.isLightBulbOn = True

    class ConstructionPlaneInput(object):
        def __init__(self):
            self.base = None
            self.offset = 0.0

        def setByOffset(self, base_plane, value):
            self.base = base_plane
            self.offset = value.value * CM_TO_MM

    class ConstructionPlanes(object):
        def __init__(self):
            pass

        def createInput(self):
            return ConstructionPlaneInput()

        def add(self, pin):
            return ConstructionPlane(pin.base.ptype,
                                     pin.base.offset + pin.offset)

    class SketchLines(object):
        def __init__(self, sketch):
            self.sketch = sketch

        def addCenterPointRectangle(self, center, corner):
            cx = center.x * CM_TO_MM
            cy = center.y * CM_TO_MM
            hw = abs(corner.x - center.x) * CM_TO_MM
            hh = abs(corner.y - center.y) * CM_TO_MM
            self.sketch.shapes.append(('rect', (cx, cy, hw, hh)))

        def addByTwoPoints(self, p0, p1):
            self.sketch.poly_pts.append((p0.x * CM_TO_MM, p0.y * CM_TO_MM))
            self.sketch.poly_pts.append((p1.x * CM_TO_MM, p1.y * CM_TO_MM))

    class SketchCircles(object):
        def __init__(self, sketch):
            self.sketch = sketch

        def addByCenterRadius(self, center, radius):
            self.sketch.shapes.append(
                ('circle', (center.x * CM_TO_MM, center.y * CM_TO_MM,
                            radius * CM_TO_MM)))

    class SketchTexts(object):
        def createInput2(self, s, h):
            raise RuntimeError('sketch text not supported offline')

    class SketchCurves(object):
        def __init__(self, sketch):
            self.sketchLines = SketchLines(sketch)
            self.sketchCircles = SketchCircles(sketch)

    class Profile(object):
        def __init__(self, sketch):
            self.sketch = sketch

    class Profiles(object):
        def __init__(self, sketch):
            self.sketch = sketch

        def item(self, index):
            return Profile(self.sketch)

    class Sketch(object):
        def __init__(self, plane):
            self.plane = plane
            self.shapes = []
            self.poly_pts = []
            self.sketchCurves = SketchCurves(self)
            self.sketchTexts = SketchTexts()
            self.profiles = Profiles(self)
            self.isLightBulbOn = True

        def main_shape(self):
            if self.shapes:
                return self.shapes[0]
            if self.poly_pts:
                pts, seen = [], set()
                for p in self.poly_pts:
                    key = (round(p[0], 6), round(p[1], 6))
                    if key not in seen:
                        seen.add(key)
                        pts.append(p)
                return ('poly', pts)
            raise RuntimeError('empty sketch used as a profile')

    class Sketches(object):
        def __init__(self, comp):
            self.comp = comp

        def add(self, plane):
            return Sketch(plane)

    class OffsetStartDefinition(object):
        def __init__(self, v):
            self.value = v

        @staticmethod
        def create(value_input):
            return OffsetStartDefinition(value_input.value)

    class ExtrudeInput(object):
        def __init__(self, profile, op):
            self.profile = profile
            self.op = op
            self.startExtent = None
            self.participantBodies = None
            self.distance = None
            self.symmetric = None

        def setDistanceExtent(self, is_symmetric, value):
            self.distance = value.value * CM_TO_MM

        def setSymmetricExtent(self, value, is_full):
            self.symmetric = value.value * CM_TO_MM

    class Feature(object):
        def __init__(self, bodies):
            self._bodies = bodies

        @property
        def bodies(self):
            coll = ObjectCollection()
            for b in self._bodies:
                coll.add(b)
            coll.item = lambda i: coll.items[i]
            return coll

    class ExtrudeFeatures(object):
        def __init__(self, comp):
            self.comp = comp

        def createInput(self, profile, op):
            return ExtrudeInput(profile, op)

        def add(self, ei):
            sketch = ei.profile.sketch
            kind, shape = sketch.main_shape()
            plane = sketch.plane.ptype
            start = sketch.plane.offset
            if ei.startExtent is not None:
                start += ei.startExtent.value * CM_TO_MM
            if ei.symmetric is not None:
                a0 = start - ei.symmetric / 2.0
                a1 = start + ei.symmetric / 2.0
            else:
                a0, a1 = start, start + ei.distance
            solid = Solid(kind, plane, shape, a0, a1,
                          OP_NAMES[ei.op])
            return self.comp.add_solid(solid, ei.op, ei.participantBodies)

    class LoftInput(object):
        def __init__(self, op):
            self.op = op
            self.isSolid = True
            self.participantBodies = None
            self.loftSections = ObjectCollection()

    class LoftFeatures(object):
        def __init__(self, comp):
            self.comp = comp

        def createInput(self, op):
            return LoftInput(op)

        def add(self, li):
            profs = li.loftSections.items
            aabbs = []
            zs = []
            for prof in profs:
                kind, shape = prof.sketch.main_shape()
                s2 = Solid(kind, prof.sketch.plane.ptype, shape, 0.0, 1.0,
                           'join')
                u0, u1, v0, v1, _, _ = s2.aabb()
                aabbs.append((u0, u1, v0, v1))
                zs.append(prof.sketch.plane.offset)
            u0 = min(b[0] for b in aabbs)
            u1 = max(b[1] for b in aabbs)
            v0 = min(b[2] for b in aabbs)
            v1 = max(b[3] for b in aabbs)
            solid = Solid('rect', profs[0].sketch.plane.ptype,
                          ((u0 + u1) / 2.0, (v0 + v1) / 2.0,
                           (u1 - u0) / 2.0, (v1 - v0) / 2.0),
                          min(zs), max(zs), OP_NAMES[li.op])
            return self.comp.add_solid(solid, li.op, li.participantBodies)

    class FilletInput(object):
        def addConstantRadiusEdgeSet(self, coll, radius, tangent):
            pass

    class FilletFeatures(object):
        def createInput(self):
            return FilletInput()

        def add(self, fi):
            return None

    class ChamferFeatures(object):
        def createInput2(self):
            raise RuntimeError('chamfer not supported offline')

        def add(self, ci):
            return None

    class MoveInput(object):
        def __init__(self, coll, matrix):
            self.coll = coll
            self.matrix = matrix

    class MoveFeatures(object):
        def createInput(self, coll, matrix):
            return MoveInput(coll, matrix)

        def add(self, mi):
            for body in mi.coll.items:
                body.transforms.append(mi.matrix.mat)
            return None

    class Features(object):
        def __init__(self, comp):
            self.extrudeFeatures = ExtrudeFeatures(comp)
            self.loftFeatures = LoftFeatures(comp)
            self.filletFeatures = FilletFeatures()
            self.chamferFeatures = ChamferFeatures()
            self.moveFeatures = MoveFeatures()

    class BRepBodies(object):
        def __init__(self, comp):
            self.comp = comp

        @property
        def count(self):
            return len(self.comp.bodies_list)

        def item(self, index):
            return self.comp.bodies_list[index]

        def __iter__(self):
            return iter(list(self.comp.bodies_list))

    class Component(object):
        def __init__(self):
            self.bodies_list = []
            self.body_counter = 0
            self.xYConstructionPlane = ConstructionPlane('xY')
            self.xZConstructionPlane = ConstructionPlane('xZ')
            self.yZConstructionPlane = ConstructionPlane('yZ')
            self.sketches = Sketches(self)
            self.features = Features(self)
            self.constructionPlanes = ConstructionPlanes()
            self.bRepBodies = BRepBodies(self)

        def add_solid(self, solid, op, participants):
            if op == FeatureOperations.NewBodyFeatureOperation:
                self.body_counter += 1
                body = Body(self, 'Body{}'.format(self.body_counter))
                body.records.append(('new', solid))
                self.bodies_list.append(body)
                return Feature([body])
            targets = list(participants) if participants else \
                (self.bodies_list[-1:] if self.bodies_list else [])
            if not targets:
                raise RuntimeError('join/cut with no target body')
            opname = OP_NAMES[op]
            for body in targets:
                # participants are given in WORLD terms; the recorded solid is
                # in build coordinates, which equal world for untransformed
                # bodies (all join/cut in these scripts happens pre-move).
                body.records.append((opname, solid))
            return Feature(targets)

    class FusionUnitsManager(object):
        distanceDisplayUnits = None

    class Design(object):
        def __init__(self):
            self.rootComponent = Component()
            self.fusionUnitsManager = FusionUnitsManager()

        @staticmethod
        def cast(obj):
            return obj

    class UserInterface(object):
        def messageBox(self, text):
            messages.append(text)

    class Application(object):
        _instance = None

        def __init__(self):
            self.userInterface = UserInterface()
            self.activeProduct = Design()
            self.activeViewport = Viewport()

        @staticmethod
        def get():
            return Application._instance

    class FeatureOperations(object):
        NewBodyFeatureOperation = 'op_new'
        JoinFeatureOperation = 'op_join'
        CutFeatureOperation = 'op_cut'

    OP_NAMES = {
        FeatureOperations.NewBodyFeatureOperation: 'new',
        FeatureOperations.JoinFeatureOperation: 'join',
        FeatureOperations.CutFeatureOperation: 'cut',
    }

    class DistanceUnits(object):
        MillimeterDistanceUnits = 1

    core.Point3D = Point3D
    core.Vector3D = Vector3D
    core.Matrix3D = Matrix3D
    core.ValueInput = ValueInput
    core.ObjectCollection = ObjectCollection
    core.Line3D = Line3D
    core.Plane = Plane
    core.Application = Application
    core.ViewOrientations = ViewOrientations
    fusion.Design = Design
    fusion.FeatureOperations = FeatureOperations
    fusion.OffsetStartDefinition = OffsetStartDefinition
    fusion.DistanceUnits = DistanceUnits

    sys.modules['adsk'] = adsk
    sys.modules['adsk.core'] = core
    sys.modules['adsk.fusion'] = fusion
    sys.modules['adsk.cam'] = cam

    class World(object):
        pass

    world = World()
    world.messages = messages
    world.Application = Application
    world.Design = Design
    return world


# --------------------------------------------------------------------------
# running scripts
# --------------------------------------------------------------------------


def load_script(path, name):
    for cached in [k for k in sys.modules
                   if k.startswith(('_freeisp', '_offline_fir'))]:
        sys.modules.pop(cached, None)
    spec = importlib.util.spec_from_file_location('_offline_fir_' + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['_offline_fir_' + name] = module
    spec.loader.exec_module(module)
    return module


def run_script(world, path, name, tweak=None):
    """Import a script and execute its real run(); return (module, design)."""
    world.Application._instance = world.Application()
    del world.messages[:]
    module = load_script(path, name)
    if tweak:
        tweak(module)
    module.run(None)
    design = world.Application._instance.activeProduct
    return module, design, list(world.messages)


class Checker(object):
    def __init__(self):
        self.rows = []

    def check(self, name, ok, detail=''):
        self.rows.append((bool(ok), name, detail))

    def report(self):
        failed = [r for r in self.rows if not r[0]]
        for ok, name, detail in self.rows:
            mark = 'PASS' if ok else 'FAIL'
            line = ' [{}] {}'.format(mark, name)
            if detail:
                line += ' -- {}'.format(detail)
            print(line)
        return len(failed)


def body_named(design, prefix):
    for b in design.rootComponent.bodies_list:
        if b.name.startswith(prefix):
            return b
    raise AssertionError('no body named {}*'.format(prefix))


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol


# --------------------------------------------------------------------------
# the checks
# --------------------------------------------------------------------------


def check_tree(root, label):
    print('\n=== {} tree: {} ==='.format(label, root))
    world = install_stub()
    c = Checker()

    interface = load_script(
        os.path.join(root, '_shared', 'FIR_Interface.py'), 'iface')
    c.check('contract validate()', not interface.validate(),
            'version ' + interface.INTERFACE_VERSION)

    def p(script):
        return os.path.join(root, script, script + '.py')

    # ---------------- FIR_Shell ------------------------------------------
    shell_mod, shell_design, msgs = run_script(world, p('FIR_Shell'), 'shell')
    c.check('FIR_Shell run() completed',
            msgs and 'failed' not in msgs[-1],
            (msgs[-1][:120].replace('\n', ' ') if msgs else 'no message'))
    c.check('FIR_Shell popup states v34', any('v34' in m for m in msgs))
    tub = body_named(shell_design, 'FIR SHELL (tub)')
    cap = body_named(shell_design, 'FIR TOP LID')

    rows = interface.CAP_SIDE_SCREW_Y
    z72 = interface.CAP_SCREW_Z

    # tub: one 12x12 boss and one horizontal pilot per wall per row
    pilots = [s for s in tub.solids('cut', 'circle', 'yZ')
              if near(s.shape[2], interface.CAP_BOSS_PILOT_D / 2.0)]
    ok_rows = []
    for sy in rows:
        for wall in (-137.0, 137.0):
            hit = [s for s in pilots
                   if near(s.shape[0], sy) and near(s.shape[1], z72)
                   and s.a0 <= wall <= s.a1]
            ok_rows.append(len(hit) == 1)
    c.check('tub: 8 cap-screw pilots on the side walls at Z72',
            len(pilots) == 8 and all(ok_rows),
            'rows {}'.format(rows))
    c.check('tub: no back-wall cap screws remain',
            not [s for s in tub.solids('cut', 'circle', 'xZ')
                 if near(s.shape[2], interface.CAP_BOSS_PILOT_D / 2.0)
                 and s.a0 < -130.0 and near(s.shape[1], z72)])
    c.check('tub: keyholes removed',
            not [s for s in tub.solids('cut', 'circle', 'xZ')
                 if near(s.shape[2], 5.5)])

    # cleat bar: polygon on the back wall, correct profile
    bars = tub.solids('join', 'poly', 'yZ')
    c.check('tub: cleat bar exists', len(bars) == 1)
    if bars:
        bar = bars[0]
        x0, x1, y0, y1, z0, z1 = bar.aabb()
        tipz = interface.cleat_bar_tip_z()
        c.check('tub: cleat bar spans X +-{:.0f}, Y {:.1f}..{:.1f}, '
                'Z {:.1f}..{:.1f}'.format(interface.CLEAT_BAR_X_HALF,
                                          y0, y1, z0, z1),
                near(x0, -interface.CLEAT_BAR_X_HALF)
                and near(x1, interface.CLEAT_BAR_X_HALF)
                and near(y0, -140.0 - interface.CLEAT_BAR_RUN)
                and near(z0, interface.CLEAT_FACE_Z0)
                and near(z1, interface.CLEAT_BAR_TOP_Z))
        c.check('tub: bar top clears the cap skirt (Z65) by {:.1f}mm'
                .format(65.0 - z1), z1 <= 64.0)
        # the 45-degree underside: both defining points on z = -y - c
        cft = [pt for pt in bar.shape if near(pt[0], -140.0)]
        tip = [pt for pt in bar.shape
               if near(pt[0], -140.0 - interface.CLEAT_BAR_RUN)
               and near(pt[1], tipz)]
        line_c = -(-140.0) - interface.CLEAT_FACE_Z0
        c.check('tub: bar underside is a true 45deg face (z=-y-{:.1f})'
                .format(line_c),
                any(near(pt[1], interface.CLEAT_FACE_Z0) for pt in cft)
                and len(tip) == 1)

    # floor lock holes
    locks = [s for s in tub.solids('cut', 'circle', 'xY')
             if near(s.shape[2], interface.WALL_LOCK_CLEAR_D / 2.0)]
    c.check('tub: 2 floor lock holes at (+-{:.0f}, {:.0f})'
            .format(abs(interface.WALL_LOCK_X[0]), interface.WALL_LOCK_Y),
            len(locks) == 2 and
            sorted(round(s.shape[0], 3) for s in locks) ==
            sorted(interface.WALL_LOCK_X) and
            all(near(s.shape[1], interface.WALL_LOCK_Y) for s in locks))
    if locks:
        lx = interface.WALL_LOCK_X[1]
        ly = interface.WALL_LOCK_Y
        c.check('tub: floor material around the lock hole, open at its centre',
                tub.material_at((lx + 3.2, ly, 1.5))
                and not tub.material_at((lx, ly, 1.5)))
        # straight-down driver corridor: no tub material from Z5 up to Z80
        clear = True
        for dz in range(5, 80, 3):
            for du, dv in ((0, 0), (3.4, 0), (-3.4, 0), (0, 3.4), (0, -3.4),
                           (2.4, 2.4), (2.4, -2.4), (-2.4, 2.4), (-2.4, -2.4)):
                if tub.material_at((lx + du, ly + dv, float(dz))) or \
                        tub.material_at((-lx + du, ly + dv, float(dz))):
                    clear = False
        c.check('tub: 7mm driver corridors above both lock screws are open '
                '(Z5..80)', clear)

    # cap: 8 seat pads + counterbores + through holes, aligned through the flip
    pads = [s for s in cap.solids('join', 'circle', 'yZ')
            if near(s.shape[2], interface.M3_SEAT_PAD_D / 2.0)]
    cbores = [s for s in cap.solids('cut', 'circle', 'yZ')
              if near(s.shape[2], interface.M3_SEAT_CBORE_D / 2.0)]
    through = [s for s in cap.solids('cut', 'circle', 'yZ')
               if near(s.shape[2], 1.7)]
    c.check('cap: 8 visible seat pads / 8 counterbores / 8 through holes',
            len(pads) == 8 and len(cbores) == 8 and len(through) == 8)
    lh = 52.0
    cap_ox = shell_mod.BOX_W + 50.0        # the cap is laid out beside the tub
    align = []
    for sy in rows:
        for sxs in (-1, 1):
            def rel_mid(s):
                return (s.a0 + s.a1) / 2.0 - cap_ox

            hole = [s for s in through
                    if near(s.shape[0], sy) and near(s.shape[1], lh - 4.0)
                    and rel_mid(s) * sxs > 0]
            if len(hole) != 1:
                align.append('missing hole Y{} {}X'.format(sy, sxs))
                continue
            # print -> assembled: (x, y, z) -> (-x, y, 120 - z)
            az = 120.0 - (lh - 4.0)
            if not near(az, z72):
                align.append('hole Y{} lands at Z{}'.format(sy, az))
            pad = [s for s in pads
                   if near(s.shape[0], sy) and near(s.shape[1], lh - 4.0)
                   and rel_mid(s) * sxs > 0]
            cb = [s for s in cbores
                  if near(s.shape[0], sy) and near(s.shape[1], lh - 4.0)
                  and rel_mid(s) * sxs > 0]
            if len(pad) != 1 or len(cb) != 1:
                align.append('missing seat Y{} {}X'.format(sy, sxs))
                continue
            # head must seat on the ORIGINAL skirt face (|x|=143)
            seat_face = min(abs(cb[0].a0 - cap_ox), abs(cb[0].a1 - cap_ox))
            if not near(seat_face, 143.0):
                align.append('cbore floor at |x|={:.2f}'.format(seat_face))
            pad_outer = max(abs(pad[0].a0 - cap_ox), abs(pad[0].a1 - cap_ox))
            if not near(pad_outer, 143.0 + interface.CAP_SEAT_PAD_H):
                align.append('pad top at |x|={:.2f}'.format(pad_outer))
    c.check('cap: every hole maps onto its tub pilot through the print flip, '
            'head seats on the original skirt face',
            not align, '; '.join(align) if align else
            'assembled Z{:.0f}, seat face |X|143, pad to |X|{:.1f}'
            .format(z72, 143.0 + interface.CAP_SEAT_PAD_H))

    # 18 Aug review additions on the cap: lead-in chamfer (3 wedge cuts) and
    # the engraved, mirror-safe front arrow in the roof's inner face
    chamfers = [s for s in cap.solids('cut', 'poly')
                if s.plane in ('xZ', 'yZ')]
    arrows = [s for s in cap.solids('cut', 'poly', 'xY')]
    c.check('cap: 3 lead-in chamfer wedges + 1 engraved front arrow',
            len(chamfers) == 3 and len(arrows) == 1)
    if arrows:
        c.check('cap: arrow engraves 0.6mm, leaves {:.1f}mm of roof'
                .format(3.0 - (3.0 - arrows[0].a0)),
                near(arrows[0].a0, 2.4) and arrows[0].a1 > 3.0)

    # cap tamper pair: pillar + downward pocket on the cap (mirrored once),
    # reed groove in the tub top rail, and the seated pair distance
    pillars = [s for s in cap.solids('join', 'rect', 'xY')
               if near(2 * s.shape[2], interface.CAP_MAG_PILLAR_SQ)
               and near(s.shape[1], interface.CAP_MAGNET_Y)]
    cpockets = [s for s in cap.solids('cut', 'circle', 'xY')
                if near(s.shape[2], interface.MAGNET_POCKET_D / 2.0)]
    c.check('cap: magnet pillar (mirrored to assembled X{:.0f}) + D{:.2f} '
            'pocket, seated reed..magnet {:.1f}mm'
            .format(interface.CAP_MAGNET_X, interface.MAGNET_POCKET_D,
                    interface.cap_reed_magnet_distance()),
            len(pillars) == 1 and len(cpockets) == 1
            and near(pillars[0].shape[0] - cap_ox, -interface.CAP_MAGNET_X)
            and near(120.0 - pillars[0].a1, interface.CAP_MAG_PILLAR_BOT_Z)
            and near(cpockets[0].a0,
                     pillars[0].a1 - interface.MAGNET_POCKET_DEPTH)
            and interface.cap_reed_magnet_distance() <= 13.0)
    rail_grooves = [s for s in tub.solids('cut', 'rect', 'xY')
                    if near(s.shape[0], interface.CAP_MAGNET_X)
                    and near(s.a0, interface.CAP_REED_GROOVE_Z0)]
    c.check('tub: cap-reed groove in the top rail front face',
            len(rail_grooves) == 1
            and near(rail_grooves[0].shape[1] - rail_grooves[0].shape[3], 134.0))
    # indoor variant: screen seat + window + LED holes, mirrored once so they
    # land at the assembled coordinates; the window must sit inside the seat
    if interface.INDOOR_SCREEN:
        wins = [s for s in cap.solids('cut', 'rect', 'xY')
                if near(2 * s.shape[2], interface.SCREEN_VIS_W)
                and near(s.shape[1], interface.SCREEN_CY)]
        seats = [s for s in cap.solids('cut', 'rect', 'xY')
                 if near(2 * s.shape[2], interface.SCREEN_PCB_W)
                 and near(s.shape[1], interface.SCREEN_CY)]
        leds = [s for s in cap.solids('cut', 'circle', 'xY')
                if near(s.shape[2], interface.LED_HOLE_D / 2.0)]
        c.check('cap INDOOR: screen window in its seat + {} LED holes, all '
                'mirrored to assembled X'.format(len(interface.LED_HOLES)),
                len(wins) == 1 and len(seats) == 1
                and len(leds) == len(interface.LED_HOLES)
                and near(wins[0].shape[0] - cap_ox, -interface.SCREEN_CX)
                and near(seats[0].shape[0] - cap_ox, -interface.SCREEN_CX)
                and near(seats[0].a0, 3.0 - interface.SCREEN_SEAT_DEPTH)
                and wins[0].a0 < 0 < wins[0].a1
                and sorted(round(s.shape[0] - cap_ox, 1) for s in leds) ==
                sorted(round(-lx, 1) for lx, _ in interface.LED_HOLES))

    shell_notes = '\n'.join(msgs)
    c.check('FIR_Shell: no interference notes',
            'INTERFERENCE' not in shell_notes)
    c.check('FIR_Shell: insert decision is raised in the popup',
            'DECISION PENDING' in shell_notes and 'insert' in shell_notes)
    c.check('FIR_Shell: wall-mount install order is stated',
            'THEN fit' in shell_notes.replace('\n', ' '))

    # ---------------- FIR_BottomLid --------------------------------------
    lid_mod, lid_design, msgs = run_script(
        world, p('FIR_BottomLid'), 'bottomlid')
    c.check('FIR_BottomLid run() completed',
            msgs and 'failed' not in msgs[-1])
    c.check('FIR_BottomLid popup states v4', any('v4' in m for m in msgs))
    lid = body_named(lid_design, 'FIR Bottom Lid')
    lpads = [s for s in lid.solids('join', 'circle', 'xY')
             if near(s.shape[2], interface.M3_SEAT_PAD_D / 2.0)
             or near(s.shape[2], 5.0)]
    # NO face feature may reach the CurvedLid end walls (inner face |X|137.5):
    # a D12 pad at +-132 did exactly that, caught 18 Aug.
    c.check('BottomLid: no outer-face feature reaches the cover end walls',
            all(abs(s.shape[0]) + s.shape[2] <= 137.0 for s in lpads))
    # the router's DC-jack port is also 6.5mm: keep only cuts that start at
    # the counterbore floor (above the plate mid), never full-depth port holes
    lcb = [s for s in lid.solids('cut', 'circle', 'xY')
           if near(s.shape[2], interface.M3_SEAT_CBORE_D / 2.0)
           and s.a0 > 0.5]
    lthrough = [s for s in lid.solids('cut', 'circle', 'xY')
                if near(s.shape[2], 1.75)]
    c.check('BottomLid: 6 pads / 6 counterbores / 6 through holes',
            len(lpads) == 6 and len(lcb) == 6 and len(lthrough) == 6)
    if lcb:
        land = min(s.a0 for s in lcb)
        pad_top = max(s.a1 for s in lpads)
        c.check('BottomLid: head land {:.1f}mm (was 0.8), pad top at '
                'Z{:.1f}'.format(land, pad_top),
                near(land, 3.0 + interface.LID_SEAT_PAD_H
                     - interface.LID_SEAT_CBORE_DEPTH)
                and near(pad_top, 3.0 + interface.LID_SEAT_PAD_H))
        head_top = land + interface.M3_HEAD_H
        c.check('BottomLid: M3 pan head finishes {:.2f}mm below the pad top'
                .format(pad_top - head_top), head_top <= pad_top + 0.05)
    # tub boss <-> lid hole mirror agreement (both patterns are the shared
    # perimeter set; the lid is turned over, X negates, the set is symmetric)
    lid_xy = sorted((round(s.shape[0], 1), round(s.shape[1], 1))
                    for s in lthrough)
    c.check('BottomLid: hole pattern matches the tub lid-seat bosses through '
            'the turn-over', lid_xy == sorted(
                ((-120.0, 72.0), (-40.0, 72.0), (40.0, 72.0), (120.0, 72.0),
                 (-132.0, 44.0), (132.0, 44.0))))
    # 18 Aug review: flush end-stop bosses (10 wide at +-COVER_LOCK_X, face
    # exactly on the cover's inner face) and the rail-top orientation key
    # block at lid-local -X (= shell +X, this plate is turned over)
    stops = [s for s in lid.solids('join', 'rect', 'xY')
             if near(s.shape[2], interface.COVER_LOCK_BOSS_W / 2.0)
             and near(abs(s.shape[0]), interface.COVER_LOCK_X)
             and s.a0 > 50.0]
    c.check('BottomLid: 2 widened lock bosses end flush at Z65.5 (hard stop)',
            len(stops) == 2 and all(near(s.a1, 65.5) for s in stops))
    keys = [s for s in lid.solids('join', 'rect', 'xY')
            if near(s.shape[0], -interface.COVER_RAIL_X)
            and near(s.shape[1], 3 + interface.COVER_RAIL_H
                     + interface.COVER_KEY_BLOCK_H / 2.0)]
    c.check('BottomLid: orientation key block on the lid-local -X rail '
            '(shell +X)', len(keys) == 1 and
            near(keys[0].a1, 3.0 + interface.COVER_KEY_BLOCK_LEN))
    # reed: recessed shelf groove at lid-local -REED_X plus the D4 wire hole
    grooves = [s for s in lid.solids('cut', 'rect', 'xY')
               if near(s.shape[0], -interface.REED_X)
               and near(2 * s.shape[3], interface.REED_SLOT_DEPTH)]
    holes4 = [s for s in lid.solids('cut', 'circle', 'xY')
              if near(s.shape[2], interface.REED_WIRE_HOLE_D / 2.0)]
    c.check('BottomLid: reed groove in the shelf (shell X+{:.0f}) + D4 wire '
            'hole'.format(interface.REED_X),
            len(grooves) == 1 and len(holes4) == 1
            and near(grooves[0].a0, interface.REED_SLOT_Z0)
            and near(holes4[0].shape[0], interface.REED_WIRE_HOLE_XY[0])
            and near(holes4[0].shape[1], interface.REED_WIRE_HOLE_XY[1]))

    # ---------------- FIR_CurvedLid --------------------------------------
    cov_mod, cov_design, msgs = run_script(
        world, p('FIR_CurvedLid'), 'curvedlid')
    c.check('FIR_CurvedLid run() completed',
            msgs and 'failed' not in msgs[-1])
    cover = body_named(cov_design, 'FIR Lid Cover')
    seats = [s for s in cover.solids('cut', 'circle', 'xY')
             if near(s.shape[2], interface.COVER_SEAT_D / 2.0)]
    c.check('CurvedLid: 2 dished lock-screw seats at (+-{:.0f}, -31)'
            .format(interface.COVER_LOCK_X),
            len(seats) == 2 and
            all(near(abs(s.shape[0]), interface.COVER_LOCK_X)
                and near(s.shape[1], -31.0) for s in seats))
    if seats:
        depth_left = 2.5 - max(s.a1 for s in seats)
        c.check('CurvedLid: {:.1f}mm of face left under the head'
                .format(depth_left), depth_left >= 1.4)
    # 18 Aug review: four short locator tabs, two anti-rattle nubs, and the
    # +X channel key relief that makes a reversed cover refuse to seat
    tabs = [s for s in cover.solids('join', 'rect', 'xY')
            if near(s.shape[1], 38.5) and near(s.shape[3], 0.5)]
    c.check('CurvedLid: locator tongue is now {} short tabs'
            .format(len(interface.COVER_TAB_X)),
            sorted(round(s.shape[0], 1) for s in tabs) ==
            sorted(interface.COVER_TAB_X)
            and all(near(2 * s.shape[2], interface.COVER_TAB_LEN)
                    for s in tabs))
    nubs = [s for s in cover.solids('join', 'rect', 'xY')
            if near(2 * s.shape[3],
                    interface.COVER_RAIL_CLR + interface.COVER_NUB_PROUD)]
    c.check('CurvedLid: 2 anti-rattle nubs biting {:.2f}mm into the rails'
            .format(interface.COVER_NUB_PROUD),
            len(nubs) == 2 and
            sorted(round(s.shape[0], 1) for s in nubs) ==
            [-interface.COVER_RAIL_X, interface.COVER_RAIL_X])
    # tamper magnet: pad on the inner face + press-fit pocket, floor keeping
    # >=1mm of outer face closed, and the closed-cover distance to the reed
    mpads = [s for s in cover.solids('join', 'rect', 'xY')
             if near(s.shape[0], interface.REED_X)
             and near(2 * s.shape[2], interface.MAGNET_PAD_SQ)]
    mpockets = [s for s in cover.solids('cut', 'circle', 'xY')
                if near(s.shape[2], interface.MAGNET_POCKET_D / 2.0)]
    c.check('CurvedLid: magnet pad + D{:.2f} press pocket, reed..magnet '
            '{:.1f}mm when closed'.format(interface.MAGNET_POCKET_D,
                                          interface.reed_magnet_distance()),
            len(mpads) == 1 and len(mpockets) == 1
            and near(mpockets[0].a0, interface.MAGNET_POCKET_FLOOR)
            and interface.MAGNET_POCKET_FLOOR - 2.5 >= 1.0
            and interface.reed_magnet_distance() <= 13.0)
    relief = [s for s in cover.solids('cut', 'rect', 'xY')
              if near(s.shape[0], interface.COVER_RAIL_X)
              and s.a0 > 40.0]
    web_tip_shell_y = 205.0 - (63.0 - interface.COVER_KEY_RELIEF_LEN)
    block_end_shell_y = 140.0 + interface.COVER_KEY_BLOCK_LEN
    c.check('CurvedLid: key relief on the +X channel only; relieved web '
            'clears the block by {:.1f}mm, a REVERSED cover hits it'
            .format(web_tip_shell_y - block_end_shell_y),
            len(relief) == 1
            and web_tip_shell_y - block_end_shell_y >= 1.5
            and interface.COVER_KEY_BLOCK_H - interface.COVER_RAIL_CLR >= 1.0)

    # ---------------- FIR_WallPlate --------------------------------------
    wp_mod, wp_design, msgs = run_script(
        world, p('FIR_WallPlate'), 'wallplate')
    c.check('FIR_WallPlate run() completed',
            msgs and 'failed' not in msgs[-1])
    c.check('FIR_WallPlate popup states v1', any('v1' in m for m in msgs))
    plate = body_named(wp_design, 'FIR WALL PLATE')
    slabs = plate.solids('new', 'poly', 'yZ')
    c.check('WallPlate: slab+cleat is one polygon profile', len(slabs) == 1)
    if slabs:
        x0, x1, y0, y1, z0, z1 = slabs[0].aabb()
        c.check('WallPlate: {:.0f} wide x {:.1f} tall x {:.0f} thick'
                .format(x1 - x0, y1 - y0, z1 - z0),
                near(x1 - x0, 2 * interface.WALL_PLATE_X_HALF)
                and near(z1 - z0, interface.WALL_PLATE_TH))
        # the cleat face, mapped to ASSEMBLED coords, must be COLLINEAR with
        # the tub bar's 45deg underside: assembled y = lz + WALL_FACE_Y,
        # assembled z = -ly.
        pts = [(lz + interface.WALL_FACE_Y, -ly) for ly, lz in slabs[0].shape]
        on_line = [pt for pt in pts
                   if near(pt[1], -pt[0] - (140.0 - interface.CLEAT_FACE_Z0))]
        c.check('WallPlate: plate 45deg face is collinear with the tub bar '
                'face (wedge mates flush)', len(on_line) >= 2,
                'shared line z = -y - {:.1f}, {} profile points on it'
                .format(140.0 - interface.CLEAT_FACE_Z0, len(on_line)))
        crest = [pt for pt in pts
                 if near(pt[0], interface.cleat_crest_front_y())]
        c.check('WallPlate: crest wall at Y{:.1f}, top Z{:.0f} -> box must '
                'lift {:.1f}mm to unhook'
                .format(interface.cleat_crest_front_y(),
                        interface.CLEAT_CREST_TOP_Z,
                        interface.cleat_interlock()),
                len(crest) >= 1 and interface.cleat_interlock() >= 3.0)
    arms = [s for s in plate.solids('join', 'rect', 'xY')]
    c.check('WallPlate: 2 under-floor arms', len(arms) == 2)
    apilots = [s for s in plate.solids('cut', 'circle', 'xZ')
               if near(s.shape[2], interface.WALL_LOCK_PILOT_D / 2.0)]
    ok_pilots = (len(apilots) == 2 and all(
        near(s.shape[0], lx) and
        near(s.shape[1], interface.WALL_LOCK_Y - interface.WALL_FACE_Y)
        for s, lx in zip(sorted(apilots, key=lambda s: s.shape[0]),
                         sorted(interface.WALL_LOCK_X))))
    c.check('WallPlate: arm pilots line up under the tub floor holes',
            ok_pilots,
            'M4 x 10 = 3 floor + 0.4 lift + {:.1f} bite, 1mm arm left below'
            .format(interface.WALL_LOCK_PILOT_DEPTH - 0.4))
    wscrews = [s for s in plate.solids('cut', 'circle', 'xY')
               if near(s.shape[2], interface.WALL_SCREW_D / 2.0)]
    wpockets = [s for s in plate.solids('cut', 'circle', 'xY')
                if near(s.shape[2], interface.WALL_SCREW_HEAD_D / 2.0)]
    c.check('WallPlate: {} wall screws, every head pocketed below the '
            'contact face'.format(len(interface.WALL_SCREW_POS)),
            len(wscrews) == len(interface.WALL_SCREW_POS)
            and len(wpockets) == len(interface.WALL_SCREW_POS)
            and all(near(s.a0, interface.WALL_PLATE_TH
                         - interface.WALL_SCREW_HEAD_DEPTH)
                    for s in wpockets))

    # ---------------- FIR_FitCoupons -------------------------------------
    fc_mod, fc_design, msgs = run_script(
        world, p('FIR_FitCoupons'), 'fitcoupons')
    c.check('FIR_FitCoupons run() completed',
            msgs and 'failed' not in msgs[-1])
    coupon_names = [b.name for b in fc_design.rootComponent.bodies_list]
    c.check('FitCoupons: all 6 coupon bodies built',
            sum(1 for n in coupon_names if n.startswith('COUPON')) == 6,
            '; '.join(sorted(coupon_names)))

    # ---------------- FIR_ShellCheck, both modes -------------------------
    for shells_only in (True, False):
        def tweak(mod, so=shells_only):
            mod.SHELLS_ONLY = so
            # The default shell-only inspection must remain only the five
            # printable bodies.  Exercise optional marker geometry in the
            # full all-up run, where it cannot be confused with print parts.
            mod.SHOW_SCREW_MARKERS = not so
            # and exercise the opaque owner-review mode on the FULL pass,
            # where marker hardware is expected anyway - the default shells
            # view must stay exactly the five printable bodies
            if not so and hasattr(mod, 'PRESENTATION'):
                mod.PRESENTATION = True
        try:
            chk_mod, chk_design, msgs = run_script(
                world, p('FIR_ShellCheck'), 'shellcheck', tweak)
            text = '\n'.join(msgs)
            mode = 'SHELLS_ONLY' if shells_only else 'FULL all-up'
            c.check('FIR_ShellCheck {} run() completed'.format(mode),
                    msgs and 'failed' not in msgs[-1],
                    (msgs[-1][:110].replace('\n', ' ') if msgs else ''))
            if shells_only:
                printed_shells = [
                    b for b in chk_design.rootComponent.bodies_list
                    if b.name.startswith('CHECK: ALL-UP')]
                c.check('FIR_ShellCheck SHELLS_ONLY: exactly the five printed '
                        'shells, no loose inspection hardware',
                        len(printed_shells) == 5)
            c.check('FIR_ShellCheck {}: no interference / handedness faults'
                    .format(mode),
                    'INTERFERENCE' not in text
                    and 'handedness is wrong' not in text
                    and 'misses the sled' not in text)
            if not shells_only:
                for needle, why in (
                        ('horn clearance', 'horn clearances reported'),
                        ('wall mount', 'wall-mount summary reported')):
                    c.check('FIR_ShellCheck FULL: {}'.format(why),
                            needle in text)
        except Exception as exc:  # noqa
            c.check('FIR_ShellCheck mode run', False, repr(exc))

    return c.report()


def main():
    ws_root = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', 'fusion')
    roots = [(os.path.realpath(ws_root), 'workspace')]
    for extra in sys.argv[1:]:
        roots.append((os.path.realpath(extra), 'deployed'))
    failures = 0
    for root, label in roots:
        failures += check_tree(root, label)
    print('\n{}'.format('ALL CHECKS PASSED' if failures == 0 else
                        '{} CHECK(S) FAILED'.format(failures)))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
