"""Minimal stand-ins for Blender's modules so the add-on's pure-Python
logic (measuring and report building) can be unit-tested without Blender.

Drawing code (gpu / blf) is NOT exercised here; it needs a real Blender.
"""
import sys
import types


class Vector:
    def __init__(self, values):
        self.v = list(values)

    def __getitem__(self, i):
        return self.v[i]

    def __setitem__(self, i, value):
        self.v[i] = value

    def __sub__(self, other):
        return Vector([a - b for a, b in zip(self.v, other.v)])

    x = property(lambda self: self.v[0])
    y = property(lambda self: self.v[1])
    z = property(lambda self: self.v[2])


class FakeMatrix:
    """Translation-only matrix, enough for bounding-box tests."""

    def __init__(self, offset=(0, 0, 0)):
        self.offset = offset

    def __matmul__(self, vector):
        return Vector([a + b for a, b in zip(vector.v, self.offset)])


class FakeMesh:
    def __init__(self, verts, edges, faces):
        self.vertices = range(verts)
        self.edges = range(edges)
        self.polygons = range(faces)
        # Edit Mode selection counters (only meaningful in Edit Mode)
        self.total_vert_sel, self.total_edge_sel, self.total_face_sel = 3, 2, 1


class FakeObject:
    def __init__(self, name, type="MESH", mode="OBJECT", counts=(8, 12, 6),
                 dims=(2, 2, 2), offset=(0, 0, 0), modifiers=False):
        self.name, self.type, self.mode = name, type, mode
        self.data = FakeMesh(*counts)
        self.dimensions = Vector(dims)
        self.matrix_world = FakeMatrix(offset)
        self.modifiers = [object()] if modifiers else []
        self.bound_box = [
            (x, y, z) for x in (0, dims[0]) for y in (0, dims[1]) for z in (0, dims[2])
        ]

    def evaluated_get(self, depsgraph):
        return self


class FakeSettings:
    def __init__(self, **overrides):
        self.show_overlay = True
        self.include_modifiers = True
        self.show_dimensions = True
        self.show_geometry = True
        self.use_budget = False
        self.budget = 10000
        self.__dict__.update(overrides)


class FakeContext:
    def __init__(self, active, selected=None, settings=None, in_mode=None,
                 unit_system="METRIC", scale_length=1.0):
        self.active_object = active
        self.selected_objects = selected if selected is not None else ([active] if active else [])
        self.scene = types.SimpleNamespace(
            measure_overlay=settings or FakeSettings(),
            unit_settings=types.SimpleNamespace(system=unit_system, scale_length=scale_length),
        )
        if in_mode is not None:
            self.objects_in_mode_unique_data = in_mode

    def evaluated_depsgraph_get(self):
        return object()


def install():
    """Register fake bpy, bmesh, blf, gpu and mathutils modules."""

    def stub(name, **attrs):
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        sys.modules[name] = module
        return module

    prop = lambda *args, **kwargs: None  # noqa: E731
    props = types.SimpleNamespace(
        BoolProperty=prop, EnumProperty=prop, FloatProperty=prop,
        IntProperty=prop, PointerProperty=prop,
    )
    bpy_types = types.SimpleNamespace(
        PropertyGroup=object, Operator=object, Panel=object,
        Scene=type("Scene", (), {}),
    )
    units = types.SimpleNamespace(to_string=lambda system, category, value, precision=3: f"{value:.{precision}f} m")

    stub("bpy", props=props, types=bpy_types, utils=types.SimpleNamespace(units=units),
         app=types.SimpleNamespace(version=(4, 2, 0)), context=None)
    stub("bmesh", from_edit_mesh=lambda mesh: types.SimpleNamespace(
        verts=range(100), edges=range(200), faces=range(101)))
    stub("blf")
    stub("gpu", shader=None, state=None)
    stub("gpu_extras")
    stub("gpu_extras.batch", batch_for_shader=None)
    stub("mathutils", Vector=Vector)
