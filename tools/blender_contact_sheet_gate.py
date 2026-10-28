"""
Mandatory 4-View Contact Sheet Gate for Blender -> Godot glTF 2.0 Pipeline.

Coordinate mapping when exporting from Blender with `export_yup=True`:
  - Blender +Y  ==  Godot -Z (FORWARD / NORTH)
  - Blender -Y  ==  Godot +Z (BACK / SOUTH / AFT)
  - Blender +X  ==  Godot +X (RIGHT / STARBOARD)
  - Blender -X  ==  Godot -X (LEFT / PORT)
  - Blender +Z  ==  Godot +Y (UP)

This module renders a 2x2 studio-lit contact sheet:
  - Top-Left:     FRONT (-Z in Godot / +Y in Blender)
  - Top-Right:    BACK  (+Z in Godot / -Y in Blender)
  - Bottom-Left:  LEFT  (-X in Godot / -X in Blender)
  - Bottom-Right: RIGHT (+X in Godot / +X in Blender)

It also places 3D world-axis arrows and 3D labels (`-Z FWD`, `+Z BACK`, `+X RIGHT`, `-X LEFT`)
plus a semi-transparent waterline plane at Z=0 (Godot Y=0) so every visual inspection is
100% unambiguous.
"""

import json
import math
import os
import bpy
import numpy as np
from mathutils import Vector, Matrix


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONTACT_SHEET_DIR = os.path.join(PROJECT_ROOT, ".mcp_captures", "contact_sheets")
MANIFEST_PATH = os.path.join(CONTACT_SHEET_DIR, "bbox_manifest.json")


def compute_scene_bounds(mesh_objects):
    min_v = Vector((1e9, 1e9, 1e9))
    max_v = Vector((-1e9, -1e9, -1e9))
    total_verts = 0
    total_faces = 0
    for obj in mesh_objects:
        if obj.type != 'MESH' or not obj.data:
            continue
        mw = obj.matrix_world
        total_verts += len(obj.data.vertices)
        total_faces += len(obj.data.polygons)
        for v in obj.data.vertices:
            wv = mw @ v.co
            min_v.x = min(min_v.x, wv.x)
            min_v.y = min(min_v.y, wv.y)
            min_v.z = min(min_v.z, wv.z)
            max_v.x = max(max_v.x, wv.x)
            max_v.y = max(max_v.y, wv.y)
            max_v.z = max(max_v.z, wv.z)
    if total_verts == 0:
        return Vector((0, 0, 0)), Vector((1, 1, 1)), Vector((0, 0, 0)), 0, 0
    span = max_v - min_v
    center = (min_v + max_v) * 0.5
    return min_v, max_v, span, center, total_verts, total_faces


def _make_emissive_mat(name, color_rgba, strength=3.5, alpha=1.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if alpha < 0.999:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = color_rgba
        bsdf.inputs["Roughness"].default_value = 0.25
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = color_rgba
            bsdf.inputs["Emission Strength"].default_value = 0.6
        mat.blend_method = 'BLEND' if hasattr(mat, "blend_method") else 'OPAQUE'
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    else:
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = color_rgba
        em.inputs["Strength"].default_value = strength
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def _create_3d_text(name, text_str, location, rotation_euler, size, mat, collection):
    curve_data = bpy.data.curves.new(name=name, type='FONT')
    curve_data.body = text_str
    curve_data.align_x = 'CENTER'
    curve_data.align_y = 'CENTER'
    curve_data.size = size
    curve_data.extrude = size * 0.06
    obj = bpy.data.objects.new(name, curve_data)
    collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = rotation_euler
    obj.data.materials.append(mat)
    return obj


def _create_axis_indicator(collection, min_v, max_v, span, center):
    max_dim = max(span.x, span.y, span.z, 0.5)
    arrow_radius = max(max_dim * 0.012, 0.008)
    label_size = max(max_dim * 0.085, 0.05)

    # Waterline reference plane at Z = 0 (Godot Y = 0)
    water_mat = _make_emissive_mat(
        "CS_WaterMat", (0.08, 0.48, 0.65, 1.0), strength=0.6, alpha=0.35
    )
    plane_x = max(span.x * 1.45, max_dim * 0.9)
    plane_y = max(span.y * 1.45, max_dim * 0.9)

    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=10,
        y_subdivisions=10,
        size=1.0,
        location=(center.x, center.y, 0.0),
    )
    grid_obj = bpy.context.active_object
    grid_obj.name = "CS_WaterlinePlane"
    grid_obj.scale = (plane_x, plane_y, 1.0)
    grid_obj.data.materials.append(water_mat)
    for col in list(grid_obj.users_collection):
        col.objects.unlink(grid_obj)
    collection.objects.link(grid_obj)

    # Wireframe border around Z=0 waterline
    mat_cyan = _make_emissive_mat("CS_MatMinusZ", (0.0, 0.95, 1.0, 1.0), strength=4.0)
    mat_orange = _make_emissive_mat("CS_MatPlusZ", (1.0, 0.32, 0.05, 1.0), strength=4.0)
    mat_green = _make_emissive_mat("CS_MatPlusX", (0.15, 1.0, 0.25, 1.0), strength=4.0)
    mat_magenta = _make_emissive_mat("CS_MatMinusX", (0.95, 0.25, 0.95, 1.0), strength=4.0)
    mat_yellow = _make_emissive_mat("CS_MatPlusY", (1.0, 0.92, 0.15, 1.0), strength=4.0)

    z_label_h = max(0.0, min_v.z + span.z * 0.12)
    margin = max_dim * 0.16

    # 1. -Z (FWD in Godot == +Y in Blender) marker at +Y edge
    fwd_pos = Vector((center.x, max_v.y + margin, z_label_h))
    bpy.ops.mesh.primitive_cone_add(
        vertices=16,
        radius1=arrow_radius * 3.2,
        radius2=0.0,
        depth=arrow_radius * 9.0,
        location=fwd_pos,
        rotation=(math.radians(-90.0), 0.0, 0.0),
    )
    cone_fwd = bpy.context.active_object
    cone_fwd.data.materials.append(mat_cyan)
    for col in list(cone_fwd.users_collection):
        col.objects.unlink(cone_fwd)
    collection.objects.link(cone_fwd)

    _create_3d_text(
        "CS_Lbl_MinusZ_Top",
        "-Z (FWD)",
        Vector((center.x, max_v.y + margin * 1.45, z_label_h + label_size * 0.9)),
        (math.radians(90.0), 0.0, math.radians(180.0)),
        label_size,
        mat_cyan,
        collection,
    )
    _create_3d_text(
        "CS_Lbl_MinusZ_Side",
        "-Z (FWD)",
        Vector((center.x, max_v.y + margin * 1.45, z_label_h - label_size * 0.3)),
        (math.radians(90.0), 0.0, math.radians(90.0)),
        label_size * 0.85,
        mat_cyan,
        collection,
    )

    # 2. +Z (BACK in Godot == -Y in Blender) marker at -Y edge
    back_pos = Vector((center.x, min_v.y - margin, z_label_h))
    bpy.ops.mesh.primitive_cone_add(
        vertices=16,
        radius1=arrow_radius * 3.2,
        radius2=0.0,
        depth=arrow_radius * 9.0,
        location=back_pos,
        rotation=(math.radians(90.0), 0.0, 0.0),
    )
    cone_back = bpy.context.active_object
    cone_back.data.materials.append(mat_orange)
    for col in list(cone_back.users_collection):
        col.objects.unlink(cone_back)
    collection.objects.link(cone_back)

    _create_3d_text(
        "CS_Lbl_PlusZ_Front",
        "+Z (BACK)",
        Vector((center.x, min_v.y - margin * 1.45, z_label_h + label_size * 0.9)),
        (math.radians(90.0), 0.0, 0.0),
        label_size,
        mat_orange,
        collection,
    )
    _create_3d_text(
        "CS_Lbl_PlusZ_Side",
        "+Z (BACK)",
        Vector((center.x, min_v.y - margin * 1.45, z_label_h - label_size * 0.3)),
        (math.radians(90.0), 0.0, math.radians(90.0)),
        label_size * 0.85,
        mat_orange,
        collection,
    )

    # 3. +X (RIGHT in Godot == +X in Blender) marker at +X edge
    right_pos = Vector((max_v.x + margin, center.y, z_label_h))
    bpy.ops.mesh.primitive_cone_add(
        vertices=16,
        radius1=arrow_radius * 3.2,
        radius2=0.0,
        depth=arrow_radius * 9.0,
        location=right_pos,
        rotation=(0.0, math.radians(90.0), 0.0),
    )
    cone_right = bpy.context.active_object
    cone_right.data.materials.append(mat_green)
    for col in list(cone_right.users_collection):
        col.objects.unlink(cone_right)
    collection.objects.link(cone_right)

    _create_3d_text(
        "CS_Lbl_PlusX",
        "+X (RIGHT)",
        Vector((max_v.x + margin * 1.45, center.y, z_label_h + label_size * 0.8)),
        (math.radians(90.0), 0.0, math.radians(90.0)),
        label_size,
        mat_green,
        collection,
    )

    # 4. -X (LEFT in Godot == -X in Blender) marker at -X edge
    left_pos = Vector((min_v.x - margin, center.y, z_label_h))
    bpy.ops.mesh.primitive_cone_add(
        vertices=16,
        radius1=arrow_radius * 3.2,
        radius2=0.0,
        depth=arrow_radius * 9.0,
        location=left_pos,
        rotation=(0.0, math.radians(-90.0), 0.0),
    )
    cone_left = bpy.context.active_object
    cone_left.data.materials.append(mat_magenta)
    for col in list(cone_left.users_collection):
        col.objects.unlink(cone_left)
    collection.objects.link(cone_left)

    _create_3d_text(
        "CS_Lbl_MinusX",
        "-X (LEFT)",
        Vector((min_v.x - margin * 1.45, center.y, z_label_h + label_size * 0.8)),
        (math.radians(90.0), 0.0, math.radians(-90.0)),
        label_size,
        mat_magenta,
        collection,
    )

    # 5. +Y (UP in Godot == +Z in Blender) marker at top
    _create_3d_text(
        "CS_Lbl_PlusY",
        "+Y (UP)",
        Vector((center.x, center.y, max_v.z + margin * 0.85)),
        (math.radians(90.0), 0.0, math.radians(180.0)),
        label_size * 0.85,
        mat_yellow,
        collection,
    )


def render_4view_contact_sheet(asset_name, mesh_objects=None, panel_res=800):
    """
    Renders a 2x2 contact sheet of the current Blender scene's mesh objects in true Godot coordinates:
      - Top-Left:     FRONT -Z (Camera at Blender +Y looking toward -Y)
      - Top-Right:    BACK  +Z (Camera at Blender -Y looking toward +Y)
      - Bottom-Left:  LEFT  -X (Camera at Blender -X looking toward +X)
      - Bottom-Right: RIGHT +X (Camera at Blender +X looking toward -X)

    Returns `(sheet_path, bbox_info)` and leaves the scene clean (removes temporary lights/cameras/markers).
    """
    os.makedirs(CONTACT_SHEET_DIR, exist_ok=True)
    if mesh_objects is None:
        mesh_objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']

    min_v, max_v, span, center, total_verts, total_faces = compute_scene_bounds(mesh_objects)
    max_dim = max(span.x, span.y, span.z, 0.5)

    # Create temporary helper collection
    helper_col = bpy.data.collections.new("CS_TempHelpers")
    bpy.context.scene.collection.children.link(helper_col)

    _create_axis_indicator(helper_col, min_v, max_v, span, center)

    # Studio lighting
    scn = bpy.context.scene
    scn.render.engine = 'BLENDER_EEVEE'
    scn.render.resolution_x = panel_res
    scn.render.resolution_y = panel_res
    scn.render.film_transparent = False

    if not scn.world:
        scn.world = bpy.data.worlds.new("CS_World")
    scn.world.use_nodes = True
    bg = scn.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.14, 0.17, 0.22, 1.0)
        bg.inputs[1].default_value = 2.2

    sun_angles = [
        ("CS_Sun1", (math.radians(48.0), 0.0, math.radians(35.0)), 4.2, (1.0, 0.98, 0.95)),
        ("CS_Sun2", (math.radians(52.0), 0.0, math.radians(215.0)), 3.2, (0.85, 0.92, 1.0)),
        ("CS_Sun3", (math.radians(65.0), 0.0, math.radians(125.0)), 2.5, (0.95, 0.95, 1.0)),
        ("CS_Sun4", (math.radians(65.0), 0.0, math.radians(-55.0)), 2.5, (0.95, 0.95, 1.0)),
    ]
    for sname, srot, senergy, scol in sun_angles:
        ldata = bpy.data.lights.new(name=sname, type='SUN')
        ldata.energy = senergy
        ldata.color = scol
        lobj = bpy.data.objects.new(name=sname, object_data=ldata)
        helper_col.objects.link(lobj)
        lobj.rotation_euler = srot

    cam_data = bpy.data.cameras.new("CS_Camera")
    cam_data.type = 'ORTHO'
    cam_data.clip_start = max(0.005, max_dim * 0.001)
    cam_data.clip_end = max(5000.0, max_dim * 20.0)
    cam_obj = bpy.data.objects.new("CS_Camera", cam_data)
    helper_col.objects.link(cam_obj)
    scn.camera = cam_obj

    mat_header = _make_emissive_mat("CS_MatHeader", (1.0, 1.0, 1.0, 1.0), strength=5.0)

    # 4 views in true Godot coordinate mapping:
    # Slightly elevated (12 deg) so horizontal decks/waterline + vertical profile are both clear
    elev = math.sin(math.radians(12.0))
    horiz = math.cos(math.radians(12.0))
    views = [
        (
            "front_minus_z",
            f"{asset_name}\nFRONT -Z (Godot Fwd / Blender +Y)",
            Vector((0.0, horiz, elev)).normalized(),
            max(span.x, span.z, max_dim * 0.65) * 1.48,
        ),
        (
            "back_plus_z",
            f"{asset_name}\nBACK +Z (Godot Rear / Blender -Y)",
            Vector((0.0, -horiz, elev)).normalized(),
            max(span.x, span.z, max_dim * 0.65) * 1.48,
        ),
        (
            "left_minus_x",
            f"{asset_name}\nLEFT -X (Godot Port / Blender -X)",
            Vector((-horiz, 0.0, elev)).normalized(),
            max(span.y, span.z, max_dim * 0.65) * 1.48,
        ),
        (
            "right_plus_x",
            f"{asset_name}\nRIGHT +X (Godot Starboard / Blender +X)",
            Vector((horiz, 0.0, elev)).normalized(),
            max(span.y, span.z, max_dim * 0.65) * 1.48,
        ),
    ]

    panel_paths = []
    dist = max_dim * 3.0

    for v_key, v_title, v_dir, ortho_scale in views:
        cam_data.ortho_scale = ortho_scale
        cam_pos = center + v_dir * dist
        cam_obj.location = cam_pos
        look_vec = (center - cam_pos).normalized()
        rot_quat = look_vec.to_track_quat('-Z', 'Y')
        cam_obj.rotation_euler = rot_quat.to_euler()

        # Place temporary title banner locked to top of camera view
        cam_up = rot_quat @ Vector((0.0, 1.0, 0.0))
        title_pos = center + v_dir * (max_dim * 1.1) + cam_up * (ortho_scale * 0.41)
        title_obj = _create_3d_text(
            f"CS_Title_{v_key}",
            v_title,
            title_pos,
            rot_quat.to_euler(),
            ortho_scale * 0.036,
            mat_header,
            helper_col,
        )

        p_path = os.path.join(CONTACT_SHEET_DIR, f"_tmp_{asset_name}_{v_key}.png")
        scn.render.filepath = p_path
        bpy.ops.render.render(write_still=True)
        panel_paths.append(p_path)

        bpy.data.objects.remove(title_obj, do_unlink=True)

    # Composite 2x2 grid into single PNG using Blender Image API + numpy
    out_sheet_path = os.path.join(CONTACT_SHEET_DIR, f"{asset_name}_4view.png")
    imgs = [bpy.data.images.load(p) for p in panel_paths]
    # Note: Blender image rows start at bottom (row 0 is bottom)
    # Top-Left = imgs[0] (FRONT -Z), Top-Right = imgs[1] (BACK +Z)
    # Bottom-Left = imgs[2] (LEFT -X), Bottom-Right = imgs[3] (RIGHT +X)
    arrs = []
    for im in imgs:
        arr = np.array(im.pixels[:], dtype=np.float32).reshape((panel_res, panel_res, 4))
        arrs.append(arr)
        bpy.data.images.remove(im)

    top_row = np.concatenate([arrs[0], arrs[1]], axis=1)
    bot_row = np.concatenate([arrs[2], arrs[3]], axis=1)
    # Since row 0 is bottom in OpenGL/Blender images, bot_row goes first vertically, then top_row
    full_grid = np.concatenate([bot_row, top_row], axis=0)
    # Add separator lines
    full_grid[panel_res - 2:panel_res + 2, :, :] = [0.9, 0.9, 0.9, 1.0]
    full_grid[:, panel_res - 2:panel_res + 2, :] = [0.9, 0.9, 0.9, 1.0]

    comp_img = bpy.data.images.new(
        f"CS_Comp_{asset_name}", width=panel_res * 2, height=panel_res * 2, alpha=True
    )
    comp_img.pixels.foreach_set(full_grid.ravel())
    comp_img.filepath_raw = out_sheet_path
    comp_img.file_format = 'PNG'
    comp_img.save()
    bpy.data.images.remove(comp_img)

    # Remove temporary panel files
    for p in panel_paths:
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass

    # Clean up helper collection and its objects
    for obj in list(helper_col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(helper_col)

    bbox_info = {
        "asset": asset_name,
        "godot_width_x": round(float(span.x), 3),
        "godot_height_y": round(float(span.z), 3),
        "godot_length_z": round(float(span.y), 3),
        "godot_min_y": round(float(min_v.z), 3),
        "godot_max_y": round(float(max_v.z), 3),
        "godot_min_x": round(float(min_v.x), 3),
        "godot_max_x": round(float(max_v.x), 3),
        "godot_min_z": round(float(-max_v.y), 3),
        "godot_max_z": round(float(-min_v.y), 3),
        "verts": total_verts,
        "faces": total_faces,
        "contact_sheet": out_sheet_path,
    }

    # Update manifest JSON
    manifest = {}
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}
    manifest[asset_name] = bbox_info
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"[ContactSheetGate] Saved 4-view contact sheet: {out_sheet_path}")
    print(f"[ContactSheetGate] Bounds ({asset_name}): {bbox_info}")
    return out_sheet_path, bbox_info


if __name__ == "__main__":
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for glb_arg in argv:
        glb_path = os.path.abspath(glb_arg)
        if not os.path.exists(glb_path):
            print(f"[ContactSheetGate] Missing file: {glb_path}")
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=glb_path)
        name = os.path.splitext(os.path.basename(glb_path))[0]
        render_4view_contact_sheet(name)

