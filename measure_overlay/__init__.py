# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SANJAYA3D

bl_info = {
    "name": "Measure Overlay",
    "author": "SANJAYA3D",
    "version": (2, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Overlays popover | Sidebar (N) > Measure",
    "description": "Live on-screen dimensions and geometry stats for your selection",
    "doc_url": "https://github.com/sanjaya3d/blender-measure-overlay#readme",
    "tracker_url": "https://github.com/sanjaya3d/blender-measure-overlay/issues",
    "category": "3D View",
}

import math
import traceback

import bpy
import bmesh
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FONT_ID = 0
MAX_OBJECTS = 500  # safety cap so huge selections don't slow the viewport
NO_GEOMETRY_TYPES = {'EMPTY', 'CAMERA', 'LIGHT', 'LIGHT_PROBE', 'SPEAKER'}

COLORS = {
    "text": (0.93, 0.93, 0.93, 1.0),
    "dim": (0.62, 0.64, 0.68, 1.0),
    "x": (0.93, 0.42, 0.42, 1.0),
    "y": (0.55, 0.85, 0.40, 1.0),
    "z": (0.40, 0.62, 0.95, 1.0),
    "good": (0.45, 0.85, 0.55, 1.0),
    "warn": (1.00, 0.75, 0.25, 1.0),
    "bad": (1.00, 0.40, 0.35, 1.0),
    "accent": (0.36, 0.60, 1.00, 1.0),
}

# Font size in pixels, and line height as a multiple of that size
SIZES = {"title": 15, "sub": 11.5, "head": 10, "row": 13}
HEIGHTS = {"title": 1.8, "sub": 1.5, "head": 2.3, "row": 1.65}

_draw_handle = None
_shader = None
_error_reported = False


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def tag_redraw(self, context):
    """Redraw every 3D viewport when a setting changes."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


class MeasureSettings(bpy.types.PropertyGroup):
    show_overlay: bpy.props.BoolProperty(
        name="Measure Overlay",
        description="Show measurements in the 3D viewport",
        default=True,
        update=tag_redraw,
    )
    include_modifiers: bpy.props.BoolProperty(
        name="Include Modifiers",
        description="Count geometry after modifiers are applied",
        default=True,
        update=tag_redraw,
    )
    show_dimensions: bpy.props.BoolProperty(
        name="Dimensions", default=True, update=tag_redraw,
    )
    show_geometry: bpy.props.BoolProperty(
        name="Geometry", default=True, update=tag_redraw,
    )
    corner: bpy.props.EnumProperty(
        name="Position",
        items=[
            ('BOTTOM_LEFT', "Bottom Left", ""),
            ('BOTTOM_RIGHT', "Bottom Right", ""),
            ('TOP_LEFT', "Top Left", ""),
            ('TOP_RIGHT', "Top Right", ""),
        ],
        default='BOTTOM_LEFT',
        update=tag_redraw,
    )
    scale: bpy.props.FloatProperty(
        name="Scale", default=1.0, min=0.5, max=3.0, update=tag_redraw,
    )
    opacity: bpy.props.FloatProperty(
        name="Opacity", default=0.65, min=0.0, max=1.0,
        subtype='FACTOR', update=tag_redraw,
    )
    use_budget: bpy.props.BoolProperty(
        name="Face Budget",
        description="Color the face count based on a budget",
        default=False,
        update=tag_redraw,
    )
    budget: bpy.props.IntProperty(
        name="Max Faces", default=10000, min=1, soft_max=1000000,
        update=tag_redraw,
    )


# ---------------------------------------------------------------------------
# Measuring
# ---------------------------------------------------------------------------

def fmt_length(context, value):
    """Format a length using the scene's unit settings."""
    units = context.scene.unit_settings
    value *= units.scale_length
    if units.system == 'NONE':
        return f"{value:.3f}"
    try:
        return bpy.utils.units.to_string(units.system, 'LENGTH', value, precision=3)
    except Exception:
        return f"{value:.3f}"


def combined_dimensions(objs):
    """World-space bounding box size that wraps all given objects."""
    lo = Vector((math.inf, math.inf, math.inf))
    hi = Vector((-math.inf, -math.inf, -math.inf))
    for obj in objs:
        matrix = obj.matrix_world
        for corner in obj.bound_box:
            p = matrix @ Vector(corner)
            for i in range(3):
                lo[i] = min(lo[i], p[i])
                hi[i] = max(hi[i], p[i])
    return hi - lo


def object_mode_counts(context, objs, use_modifiers):
    """Total (vertices, edges, faces) across objects in Object Mode."""
    depsgraph = context.evaluated_depsgraph_get() if use_modifiers else None
    verts = edges = faces = 0
    for obj in objs:
        mesh = obj.evaluated_get(depsgraph).data if depsgraph else obj.data
        verts += len(mesh.vertices)
        edges += len(mesh.edges)
        faces += len(mesh.polygons)
    return verts, edges, faces


def edit_mode_counts(objs):
    """(totals, selected) as (verts, edges, faces) tuples in Edit Mode."""
    total = [0, 0, 0]
    selected = [0, 0, 0]
    for obj in objs:
        bm = bmesh.from_edit_mesh(obj.data)
        total[0] += len(bm.verts)
        total[1] += len(bm.edges)
        total[2] += len(bm.faces)
        selected[0] += obj.data.total_vert_sel
        selected[1] += obj.data.total_edge_sel
        selected[2] += obj.data.total_face_sel
    return tuple(total), tuple(selected)


def budget_state(settings, faces):
    """Return (color_key, ratio) for the face budget, or (None, None)."""
    if not settings.use_budget or settings.budget <= 0:
        return None, None
    ratio = faces / settings.budget
    if ratio > 1.0:
        return "bad", ratio
    if ratio >= 0.75:
        return "warn", ratio
    return "good", ratio


def build_report(context):
    """Collect everything we want to show into a simple dict.

    Both the viewport overlay and the clipboard button use this, so what
    you see on screen is exactly what gets copied.
    """
    settings = context.scene.measure_overlay
    obj = context.active_object

    if obj is None:
        return {"title": "No active object", "subtitle": "", "sections": [], "accent": "dim"}

    in_edit = obj.type == 'MESH' and obj.mode == 'EDIT'
    subtitle = []
    sections = []
    accent = "accent"

    # -- Decide which objects we are measuring ------------------------------
    if in_edit:
        in_mode = getattr(context, "objects_in_mode_unique_data", None) or [obj]
        targets = [o for o in in_mode if o.type == 'MESH']
        subtitle.append("Edit Mode" if len(targets) < 2 else f"Edit Mode, {len(targets)} objects")
    else:
        targets = [o for o in context.selected_objects if o.type == 'MESH']
        if not targets and obj.type == 'MESH':
            targets = [obj]
        if len(targets) > MAX_OBJECTS:
            targets = targets[:MAX_OBJECTS]
            subtitle.append(f"First {MAX_OBJECTS} objects only")

    if len(targets) > 1 and not in_edit:
        title = f"{len(targets)} meshes selected"
        subtitle.append(f"Active: {obj.name}")
    else:
        title = obj.name

    if obj.type != 'MESH' and not targets:
        subtitle.append("Not a mesh (" + obj.type.replace("_", " ").title() + ")")

    if not in_edit and settings.include_modifiers and any(o.modifiers for o in targets):
        subtitle.append("with modifiers")

    # -- Dimensions ----------------------------------------------------------
    if settings.show_dimensions and obj.type not in NO_GEOMETRY_TYPES:
        if len(targets) > 1 and not in_edit:
            dims = combined_dimensions(targets)
            heading = "Selection Size"
        else:
            dims = obj.dimensions
            heading = "Dimensions"
        sections.append((heading, [
            ("X", fmt_length(context, dims.x), "x", "text"),
            ("Y", fmt_length(context, dims.y), "y", "text"),
            ("Z", fmt_length(context, dims.z), "z", "text"),
        ]))

    # -- Geometry ------------------------------------------------------------
    if settings.show_geometry and targets:
        if in_edit:
            total, selected = edit_mode_counts(targets)
            face_total = total[2]
            budget_key, ratio = budget_state(settings, face_total)
            face_color = budget_key or "text"
            rows = [
                ("Vertices", f"{selected[0]:,} / {total[0]:,}", "dim", "text"),
                ("Edges", f"{selected[1]:,} / {total[1]:,}", "dim", "text"),
                ("Faces", f"{selected[2]:,} / {total[2]:,}", "dim", face_color),
            ]
        else:
            verts, edges, faces = object_mode_counts(context, targets, settings.include_modifiers)
            budget_key, ratio = budget_state(settings, faces)
            face_color = budget_key or "text"
            face_text = f"{faces:,}"
            if ratio is not None:
                face_text += f"  ({ratio * 100:.0f}%)"
            rows = [
                ("Vertices", f"{verts:,}", "dim", "text"),
                ("Edges", f"{edges:,}", "dim", "text"),
                ("Faces", face_text, "dim", face_color),
            ]
        if budget_key:
            accent = budget_key
        sections.append(("Geometry", rows))

    return {
        "title": title,
        "subtitle": ", ".join(subtitle),
        "sections": sections,
        "accent": accent,
    }


def report_to_text(report):
    lines = [report["title"]]
    if report["subtitle"]:
        lines.append(report["subtitle"])
    for heading, rows in report["sections"]:
        lines.append(f"{heading}:")
        for row in rows:
            lines.append(f"  {row[0]}: {row[1]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def get_shader():
    global _shader
    if _shader is None:
        # The built-in shader was renamed in newer Blender versions
        for name in ("UNIFORM_COLOR", "2D_UNIFORM_COLOR"):
            try:
                _shader = gpu.shader.from_builtin(name)
                break
            except Exception:
                continue
    return _shader


def set_font_size(size):
    size = int(round(size))
    if bpy.app.version >= (4, 0, 0):
        blf.size(FONT_ID, size)
    else:
        blf.size(FONT_ID, size, 72)


def text_width(text, size):
    set_font_size(size)
    return blf.dimensions(FONT_ID, text)[0]


def draw_text(text, x, y, size, color):
    set_font_size(size)
    blf.color(FONT_ID, *color)
    blf.position(FONT_ID, x, y, 0)
    blf.draw(FONT_ID, text)


def draw_fan(points, color):
    shader = get_shader()
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": points})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def draw_rect(x, y, w, h, color):
    draw_fan([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], color)


def draw_rounded_rect(x, y, w, h, radius, color, segments=6):
    radius = min(radius, w / 2, h / 2)
    corners = (
        (x + w - radius, y + h - radius, 0),
        (x + radius, y + h - radius, 90),
        (x + radius, y + radius, 180),
        (x + w - radius, y + radius, 270),
    )
    points = []
    for cx, cy, start in corners:
        for i in range(segments + 1):
            angle = math.radians(start + 90 * i / segments)
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw_fan([(x + w / 2, y + h / 2)] + points + [points[0]], color)


def region_offsets(context, space, k):
    """Space taken by the toolbar, sidebar and headers (when they overlap the viewport)."""
    area, region = context.area, context.region
    overlap_x = region.width >= area.width - 1
    overlap_y = region.height >= area.height - 1
    left = right = top = bottom = 0

    for r in area.regions:
        if r.width <= 1 or r.height <= 1:  # hidden regions report a size of 1
            continue
        if r.type == 'TOOLS' and overlap_x:
            left += r.width
        elif r.type == 'UI' and overlap_x:
            right += r.width
        elif r.type in {'HEADER', 'TOOL_HEADER'} and overlap_y:
            if r.alignment == 'BOTTOM':
                bottom += r.height
            else:
                top += r.height
    return left, right, top, bottom


def draw_report(context, report, settings):
    region = context.region
    space = context.space_data
    k = settings.scale * context.preferences.system.ui_scale

    # Flat list of lines: (kind, text_a, text_b, color_a, color_b)
    items = [("title", report["title"], "", "dim" if report["accent"] == "dim" else "text", "text")]
    if report["subtitle"]:
        items.append(("sub", report["subtitle"], "", "dim", "dim"))
    for heading, rows in report["sections"]:
        items.append(("head", heading.upper(), "", "dim", "dim"))
        for label, value, label_color, value_color in rows:
            items.append(("row", label, value, label_color, value_color))

    # -- Measure ------------------------------------------------------------
    pad_left, pad_right, pad_y, gap = 17 * k, 12 * k, 10 * k, 18 * k
    label_w = value_w = wide_w = 0
    for kind, a, b, _, _ in items:
        size = SIZES[kind] * k
        if kind == "row":
            label_w = max(label_w, text_width(a, size))
            value_w = max(value_w, text_width(b, size))
        else:
            wide_w = max(wide_w, text_width(a, size))

    content_w = max(wide_w, label_w + gap + value_w, 120 * k)
    total_w = pad_left + content_w + pad_right
    total_h = pad_y * 2 + sum(HEIGHTS[i[0]] * SIZES[i[0]] * k for i in items)

    # -- Position -----------------------------------------------------------
    left, right, top, bottom = region_offsets(context, space, k)
    if (settings.corner == 'TOP_RIGHT'
            and getattr(space, "show_gizmo", True)
            and getattr(space, "show_gizmo_navigate", True)):
        top += 150 * k  # keep clear of the navigation gizmo

    margin = 14 * k
    if total_w + margin * 2 > region.width:
        return  # viewport too small, don't cover it

    if settings.corner in {'BOTTOM_LEFT', 'TOP_LEFT'}:
        x = left + margin
    else:
        x = region.width - right - margin - total_w

    if settings.corner in {'TOP_LEFT', 'TOP_RIGHT'}:
        top_y = region.height - top - margin
    else:
        top_y = bottom + margin + total_h
    y = top_y - total_h

    # -- Background ---------------------------------------------------------
    gpu.state.blend_set('ALPHA')
    draw_rounded_rect(x, y, total_w, total_h, 8 * k, (0.07, 0.08, 0.10, settings.opacity))
    draw_rect(x + 6 * k, y + 8 * k, 3 * k, total_h - 16 * k, COLORS[report["accent"]])

    # -- Text ---------------------------------------------------------------
    text_x = x + pad_left
    cursor = top_y - pad_y
    for kind, a, b, color_a, color_b in items:
        size = SIZES[kind] * k
        height = HEIGHTS[kind] * size
        if kind == "row":
            baseline = cursor - height / 2 - size * 0.3
            draw_text(a, text_x, baseline, size, COLORS[color_a])
            draw_text(b, text_x + content_w - text_width(b, size), baseline, size, COLORS[color_b])
        elif kind == "head":
            draw_rect(text_x, cursor - height * 0.30, content_w, max(1.0, k), (1.0, 1.0, 1.0, 0.10))
            draw_text(a, text_x, cursor - height + size * 0.45, size, COLORS[color_a])
        else:
            draw_text(a, text_x, cursor - height / 2 - size * 0.3, size, COLORS[color_a])
        cursor -= height

    gpu.state.blend_set('NONE')


def draw_overlay():
    """Called by Blender every time a 3D viewport redraws."""
    global _error_reported
    context = bpy.context
    settings = getattr(context.scene, "measure_overlay", None)
    space = context.space_data

    if settings is None or not settings.show_overlay:
        return
    if space is None or space.type != 'VIEW_3D' or not space.overlay.show_overlays:
        return  # respect the viewport's own Overlays on/off switch

    try:
        draw_report(context, build_report(context), settings)
    except Exception:
        gpu.state.blend_set('NONE')
        if not _error_reported:  # print once instead of spamming every redraw
            _error_reported = True
            traceback.print_exc()


# ---------------------------------------------------------------------------
# Operator and UI
# ---------------------------------------------------------------------------

class MEASURE_OT_copy_stats(bpy.types.Operator):
    bl_idname = "measure.copy_stats"
    bl_label = "Copy Stats"
    bl_description = "Copy the current measurements to the clipboard"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        context.window_manager.clipboard = report_to_text(build_report(context))
        self.report({'INFO'}, "Measurements copied to clipboard")
        return {'FINISHED'}


class MEASURE_PT_main(bpy.types.Panel):
    bl_label = "Measure Overlay"
    bl_idname = "MEASURE_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Measure"

    def draw_header(self, context):
        self.layout.prop(context.scene.measure_overlay, "show_overlay", text="")

    def draw(self, context):
        settings = context.scene.measure_overlay
        layout = self.layout
        layout.active = settings.show_overlay
        layout.prop(settings, "include_modifiers")
        layout.operator("measure.copy_stats", icon='COPYDOWN')


class MEASURE_PT_display(bpy.types.Panel):
    bl_label = "Display"
    bl_idname = "MEASURE_PT_display"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Measure"
    bl_parent_id = "MEASURE_PT_main"

    def draw(self, context):
        settings = context.scene.measure_overlay
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.active = settings.show_overlay

        col = layout.column(heading="Show")
        col.prop(settings, "show_dimensions", text="Dimensions")
        col.prop(settings, "show_geometry", text="Geometry")

        col = layout.column()
        col.prop(settings, "corner")
        col.prop(settings, "scale")
        col.prop(settings, "opacity", slider=True)


class MEASURE_PT_budget(bpy.types.Panel):
    bl_label = "Face Budget"
    bl_idname = "MEASURE_PT_budget"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Measure"
    bl_parent_id = "MEASURE_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.scene.measure_overlay, "use_budget", text="")

    def draw(self, context):
        settings = context.scene.measure_overlay
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()
        col.active = settings.use_budget
        col.prop(settings, "budget")
        col.label(text="Orange at 75%, red when over")


def draw_overlay_toggle(self, context):
    """Adds a checkbox to the viewport's Overlays dropdown."""
    settings = getattr(context.scene, "measure_overlay", None)
    if settings is not None:
        self.layout.prop(settings, "show_overlay", text="Measure Overlay")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    MeasureSettings,
    MEASURE_OT_copy_stats,
    MEASURE_PT_main,
    MEASURE_PT_display,
    MEASURE_PT_budget,
)


def register():
    global _draw_handle
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.measure_overlay = bpy.props.PointerProperty(type=MeasureSettings)

    _draw_handle = bpy.types.SpaceView3D.draw_handler_add(
        draw_overlay, (), 'WINDOW', 'POST_PIXEL'
    )
    if hasattr(bpy.types, "VIEW3D_PT_overlay"):
        bpy.types.VIEW3D_PT_overlay.append(draw_overlay_toggle)


def unregister():
    global _draw_handle
    if hasattr(bpy.types, "VIEW3D_PT_overlay"):
        bpy.types.VIEW3D_PT_overlay.remove(draw_overlay_toggle)
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        _draw_handle = None

    del bpy.types.Scene.measure_overlay
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
