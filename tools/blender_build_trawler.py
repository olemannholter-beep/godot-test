#!/usr/bin/env python3
"""
Headless Blender 5.4.0 Procedural & Sculpted Fishing Trawler Generator.

Run via:
  blender --background --python tools/blender_build_trawler.py

Exports:
  assets/models/trawler.glb

Dimensions & Coordinate Alignment:
  - Total Hull Length: ~4.8m (-2.40m bow stem to +2.25m transom, +2.50m stern A-frame overhang)
  - Beam Width: ~2.0m (-1.00m Port to +1.00m Starboard)
  - In Blender modeling space:
      -Y : Bow (Forward)
      +Y : Stern (Aft)
      +Z : Up
      -X : Port (Left)
      +X : Starboard (Right)
  - Prior to glTF (+Y Up) export, longitudinal Y is oriented so that Blender's glTF exporter
    places the Bow along -Z (Forward), Stern along +Z (Aft), Port along -X, Starboard along +X,
    and Up along +Y in Godot 4.
"""

import math
import os
from typing import Dict, List, Sequence, Tuple

import bmesh
import bpy
from mathutils import Matrix, Vector

Vec3 = Tuple[float, float, float]


# ---------------------------------------------------------------------------
# Scene & Material Setup
# ---------------------------------------------------------------------------

MATERIAL_SPECS: List[Tuple[str, Tuple[float, float, float, float], float, float, Tuple[float, float, float, float], float]] = [
    # (Name, BaseColor, Metallic, Roughness, EmissionColor, EmissionStrength)
    ("HullIron", (0.10, 0.13, 0.15, 1.0), 0.55, 0.68, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("RustKeel", (0.26, 0.09, 0.07, 1.0), 0.25, 0.85, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("DeckWood", (0.15, 0.10, 0.07, 1.0), 0.00, 0.88, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("CabinPaint", (0.38, 0.41, 0.40, 1.0), 0.05, 0.78, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("DarkMetal", (0.06, 0.06, 0.07, 1.0), 0.80, 0.45, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("LifeRing", (0.55, 0.16, 0.08, 1.0), 0.00, 0.70, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("WindowGlow", (1.00, 0.72, 0.30, 1.0), 0.00, 0.15, (1.00, 0.65, 0.22, 1.0), 4.5),
]


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def create_pbr_materials() -> Dict[str, bpy.types.Material]:
    mats: Dict[str, bpy.types.Material] = {}
    for name, base_color, metallic, roughness, emission_color, emission_strength in MATERIAL_SPECS:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf is None:
            bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")

        bsdf.inputs["Base Color"].default_value = base_color
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness

        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = emission_color
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = emission_color

        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength

        mats[name] = mat
    return mats


# ---------------------------------------------------------------------------
# Geometry Helpers (Blender Modeling Space: X=Starboard, -Y=Bow/+Y=Stern, +Z=Up)
# ---------------------------------------------------------------------------

def assign_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    if obj.data is None:
        return
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def add_bevel_modifier(obj: bpy.types.Object, width: float = 0.008, segments: int = 2, angle_limit: float = 35.0) -> None:
    bev = obj.modifiers.new(name="Bevel", type="BEVEL")
    bev.width = width
    bev.segments = segments
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(angle_limit)


def apply_all_modifiers(obj: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = obj
    for mod in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def create_box(
    name: str,
    center: Vec3,
    size: Vec3,
    mat: bpy.types.Material,
    rotation_euler: Vec3 = (0.0, 0.0, 0.0),
    bevel_width: float = 0.006,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bm.to_mesh(mesh)
    bm.free()

    obj.location = Vector(center)
    obj.rotation_euler = rotation_euler
    assign_material(obj, mat)
    if bevel_width > 0.0:
        add_bevel_modifier(obj, width=bevel_width, segments=2)
    return obj


def create_cylinder_between(
    name: str,
    p_start: Vec3,
    p_end: Vec3,
    r_start: float,
    r_end: float,
    mat: bpy.types.Material,
    segments: int = 16,
    cap_ends: bool = True,
) -> bpy.types.Object:
    v0 = Vector(p_start)
    v1 = Vector(p_end)
    diff = v1 - v0
    length = diff.length
    mid = (v0 + v1) * 0.5

    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=cap_ends,
        cap_tris=False,
        segments=segments,
        radius1=r_start,
        radius2=r_end,
        depth=max(length, 1e-4),
    )
    bm.to_mesh(mesh)
    bm.free()

    obj.location = mid
    if length > 1e-5:
        direction = diff.normalized()
        rot_quat = direction.to_track_quat("Z", "Y")
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = rot_quat
        obj.rotation_mode = "XYZ"

    assign_material(obj, mat)
    return obj


def create_torus(
    name: str,
    center: Vec3,
    major_radius: float,
    minor_radius: float,
    mat: bpy.types.Material,
    rotation_euler: Vec3 = (0.0, 0.0, 0.0),
    major_segments: int = 28,
    minor_segments: int = 14,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(
        align="WORLD",
        location=center,
        rotation=rotation_euler,
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=major_segments,
        minor_segments=minor_segments,
    )
    obj = bpy.context.active_object
    obj.name = name
    assign_material(obj, mat)
    return obj


def create_curve_cable(
    name: str,
    points: Sequence[Vec3],
    bevel_depth: float,
    mat: bpy.types.Material,
    resolution_u: int = 12,
    cyclic: bool = False,
) -> bpy.types.Object:
    curve_data = bpy.data.curves.new(name=name + "_curve", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = resolution_u
    curve_data.bevel_depth = bevel_depth
    curve_data.bevel_resolution = 4
    curve_data.use_fill_caps = True

    spline = curve_data.splines.new(type="POLY")
    spline.points.add(len(points) - 1)
    for idx, pt in enumerate(points):
        spline.points[idx].co = (pt[0], pt[1], pt[2], 1.0)
    spline.use_cyclic_u = cyclic

    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    assign_material(obj, mat)
    return obj


def catenary_points(p0: Vec3, p1: Vec3, sag: float, steps: int = 16) -> List[Vec3]:
    v0 = Vector(p0)
    v1 = Vector(p1)
    pts: List[Vec3] = []
    for i in range(steps + 1):
        t = i / float(steps)
        pos = v0.lerp(v1, t)
        # Parabolic/catenary sag peaking at t = 0.5
        drop = 4.0 * t * (1.0 - t) * sag
        pos.z -= drop
        pts.append((pos.x, pos.y, pos.z))
    return pts


# ---------------------------------------------------------------------------
# 1. Curved Naval Hull (bmesh + SUBSURF + SOLIDIFY + BEVEL) + Tire Fenders
# ---------------------------------------------------------------------------

def build_naval_hull(mats: Dict[str, bpy.types.Material]) -> List[bpy.types.Object]:
    """
    Builds a smooth, multi-station naval hull in Blender space:
      - Bow stem at y = -2.40, Stern transom at y = +2.25
      - Lower anti-fouling hull & skeg keel (RustKeel)
      - Upper flared steel hull plates & bulwark gunwales (HullIron) with SUBSURF + SOLIDIFY + BEVEL
      - Welded external rubbing strakes (DarkMetal)
      - 4 heavy rubber tire fenders (Torus) hanging on vertical chains
    """
    objects: List[bpy.types.Object] = []

    waterline_z = 0.08
    deck_z = 0.35

    # 14 longitudinal stations from bow (-2.40) to stern (+2.25):
    # (y, keel_z, keel_w, chine_z, chine_w, wl_w, mid_z, mid_w, sheer_z, sheer_w)
    stations = [
        (-2.40,  0.04, 0.000,  0.06, 0.005, 0.010, 0.52, 0.025, 0.98, 0.035),
        (-2.22, -0.18, 0.020, -0.06, 0.110, 0.175, 0.49, 0.270, 0.94, 0.370),
        (-1.95, -0.34, 0.038, -0.13, 0.255, 0.365, 0.46, 0.510, 0.90, 0.640),
        (-1.60, -0.42, 0.052, -0.17, 0.440, 0.580, 0.43, 0.740, 0.85, 0.850),
        (-1.20, -0.45, 0.062, -0.19, 0.610, 0.750, 0.41, 0.880, 0.80, 0.955),
        (-0.75, -0.46, 0.068, -0.20, 0.710, 0.850, 0.39, 0.955, 0.76, 0.995),
        (-0.30, -0.46, 0.070, -0.20, 0.750, 0.890, 0.38, 0.980, 0.72, 1.000),
        ( 0.15, -0.46, 0.070, -0.20, 0.760, 0.900, 0.37, 0.980, 0.69, 1.000),
        ( 0.60, -0.45, 0.068, -0.19, 0.740, 0.880, 0.37, 0.960, 0.67, 0.985),
        ( 1.05, -0.43, 0.062, -0.17, 0.700, 0.840, 0.37, 0.920, 0.66, 0.950),
        ( 1.45, -0.40, 0.058, -0.14, 0.650, 0.790, 0.38, 0.875, 0.67, 0.905),
        ( 1.80, -0.36, 0.052, -0.11, 0.595, 0.735, 0.39, 0.825, 0.68, 0.855),
        ( 2.05, -0.33, 0.048, -0.09, 0.550, 0.690, 0.40, 0.785, 0.70, 0.815),
        ( 2.25, -0.30, 0.045, -0.07, 0.510, 0.650, 0.41, 0.750, 0.72, 0.780),
    ]

    # --- A. Upper Steel Hull Shell (HullIron) with SUBSURF + SOLIDIFY + BEVEL ---
    upper_mesh = bpy.data.meshes.new("UpperHull_mesh")
    upper_obj = bpy.data.objects.new("UpperHull", upper_mesh)
    bpy.context.collection.objects.link(upper_obj)
    assign_material(upper_obj, mats["HullIron"])

    bm_up = bmesh.new()
    st_rings_up: List[List[bmesh.types.BMVert]] = []

    for st in stations:
        y, _, _, _, _, wl_w, mid_z, mid_w, sheer_z, sheer_w = st
        # 5 profile points from Port sheer -> Port mid -> Port wl ... Starboard sheer
        v_p_sheer = bm_up.verts.new((-sheer_w, y, sheer_z))
        v_p_mid = bm_up.verts.new((-mid_w, y, mid_z))
        v_p_wl = bm_up.verts.new((-wl_w, y, waterline_z))
        v_s_wl = bm_up.verts.new((wl_w, y, waterline_z))
        v_s_mid = bm_up.verts.new((mid_w, y, mid_z))
        v_s_sheer = bm_up.verts.new((sheer_w, y, sheer_z))
        st_rings_up.append([v_p_sheer, v_p_mid, v_p_wl, v_s_wl, v_s_mid, v_s_sheer])

    for i in range(len(stations) - 1):
        r0 = st_rings_up[i]
        r1 = st_rings_up[i + 1]
        # Port side bands (0->1, 1->2)
        bm_up.faces.new((r0[0], r0[1], r1[1], r1[0]))
        bm_up.faces.new((r0[1], r0[2], r1[2], r1[1]))
        # Starboard side bands (3->4, 4->5)
        bm_up.faces.new((r0[3], r0[4], r1[4], r1[3]))
        bm_up.faces.new((r0[4], r0[5], r1[5], r1[4]))

    # Close bow stem seam and flat transom stern above waterline
    tr = st_rings_up[-1]
    y_tr = stations[-1][0]
    v_tr_c_wl = bm_up.verts.new((0.0, y_tr, waterline_z))
    v_tr_c_mid = bm_up.verts.new((0.0, y_tr, stations[-1][6]))
    v_tr_c_sh = bm_up.verts.new((0.0, y_tr, stations[-1][8]))
    bm_up.faces.new((tr[2], v_tr_c_wl, v_tr_c_mid, tr[1]))
    bm_up.faces.new((tr[1], v_tr_c_mid, v_tr_c_sh, tr[0]))
    bm_up.faces.new((v_tr_c_wl, tr[3], tr[4], v_tr_c_mid))
    bm_up.faces.new((v_tr_c_mid, tr[4], tr[5], v_tr_c_sh))

    # Raised forecastle peak deck cover at bow (stations 0..2)
    for i in range(2):
        r0 = st_rings_up[i]
        r1 = st_rings_up[i + 1]
        bm_up.faces.new((r0[0], r1[0], r1[5], r0[5]))

    bmesh.ops.recalc_face_normals(bm_up, faces=bm_up.faces)
    bm_up.to_mesh(upper_mesh)
    bm_up.free()

    sub_up = upper_obj.modifiers.new(name="Subsurf", type="SUBSURF")
    sub_up.levels = 1
    sub_up.render_levels = 1
    sol_up = upper_obj.modifiers.new(name="Solidify", type="SOLIDIFY")
    sol_up.thickness = 0.085
    sol_up.offset = -1.0
    sol_up.use_even_offset = True
    add_bevel_modifier(upper_obj, width=0.012, segments=2, angle_limit=30.0)
    apply_all_modifiers(upper_obj)
    objects.append(upper_obj)

    # --- B. Lower Anti-Fouling Hull & Deep Keel (RustKeel) with SUBSURF + BEVEL ---
    lower_mesh = bpy.data.meshes.new("LowerHull_mesh")
    lower_obj = bpy.data.objects.new("LowerHull", lower_mesh)
    bpy.context.collection.objects.link(lower_obj)
    assign_material(lower_obj, mats["RustKeel"])

    bm_low = bmesh.new()
    st_rings_low: List[List[bmesh.types.BMVert]] = []
    for st in stations:
        y, keel_z, keel_w, chine_z, chine_w, wl_w, _, _, _, _ = st
        top_z = waterline_z + 0.025
        v_p_wl = bm_low.verts.new((-wl_w, y, top_z))
        v_p_ch = bm_low.verts.new((-chine_w, y, chine_z))
        v_p_kl = bm_low.verts.new((-max(keel_w, 0.005), y, keel_z))
        v_c_kl = bm_low.verts.new((0.0, y, keel_z - 0.02))
        v_s_kl = bm_low.verts.new((max(keel_w, 0.005), y, keel_z))
        v_s_ch = bm_low.verts.new((chine_w, y, chine_z))
        v_s_wl = bm_low.verts.new((wl_w, y, top_z))
        st_rings_low.append([v_p_wl, v_p_ch, v_p_kl, v_c_kl, v_s_kl, v_s_ch, v_s_wl])

    for i in range(len(stations) - 1):
        r0 = st_rings_low[i]
        r1 = st_rings_low[i + 1]
        for b in range(6):
            bm_low.faces.new((r0[b], r0[b + 1], r1[b + 1], r1[b]))
        # Cap top of lower hull at waterline
        bm_low.faces.new((r0[0], r1[0], r1[6], r0[6]))

    # Close stern transom of lower hull
    rl = st_rings_low[-1]
    y_tr = stations[-1][0]
    v_top_c = bm_low.verts.new((0.0, y_tr, waterline_z + 0.025))
    v_ch_c = bm_low.verts.new((0.0, y_tr, stations[-1][3]))
    bm_low.faces.new((rl[0], rl[1], v_ch_c, v_top_c))
    bm_low.faces.new((rl[1], rl[2], rl[3], v_ch_c))
    bm_low.faces.new((v_top_c, v_ch_c, rl[5], rl[6]))
    bm_low.faces.new((v_ch_c, rl[3], rl[4], rl[5]))

    bmesh.ops.recalc_face_normals(bm_low, faces=bm_low.faces)
    bm_low.to_mesh(lower_mesh)
    bm_low.free()

    sub_low = lower_obj.modifiers.new(name="Subsurf", type="SUBSURF")
    sub_low.levels = 1
    sub_low.render_levels = 1
    add_bevel_modifier(lower_obj, width=0.01, segments=2, angle_limit=35.0)
    apply_all_modifiers(lower_obj)
    objects.append(lower_obj)

    # Heavy skeg keel bar, rudder blade, and propeller nozzle under stern
    objects.append(create_box("KeelSkeg", (0.0, 0.20, -0.49), (0.11, 3.10, 0.16), mats["RustKeel"], bevel_width=0.012))
    objects.append(create_box("RudderBlade", (0.0, 2.12, -0.34), (0.055, 0.32, 0.38), mats["RustKeel"], bevel_width=0.008))
    objects.append(create_cylinder_between("PropShaft", (0.0, 1.55, -0.36), (0.0, 1.96, -0.36), 0.045, 0.035, mats["DarkMetal"], segments=12))

    # --- C. External Welded Rubbing Strakes & Gunwale Pipe Rail (DarkMetal) ---
    port_upper_strake: List[Vec3] = []
    stbd_upper_strake: List[Vec3] = []
    port_lower_strake: List[Vec3] = []
    stbd_lower_strake: List[Vec3] = []
    port_gunwale_cap: List[Vec3] = []
    stbd_gunwale_cap: List[Vec3] = []

    for st in stations:
        y, _, _, _, _, wl_w, mid_z, mid_w, sheer_z, sheer_w = st
        # Upper rub strake at 75% between mid and sheer
        sx = mid_w + (sheer_w - mid_w) * 0.72 + 0.015
        sz = mid_z + (sheer_z - mid_z) * 0.72
        port_upper_strake.append((-sx, y, sz))
        stbd_upper_strake.append((sx, y, sz))

        # Lower fender strake near mid chine
        lx = mid_w + 0.018
        lz = mid_z
        port_lower_strake.append((-lx, y, lz))
        stbd_lower_strake.append((lx, y, lz))

        # Gunwale top pipe rail
        gx = sheer_w - 0.03
        gz = sheer_z + 0.015
        port_gunwale_cap.append((-gx, y, gz))
        stbd_gunwale_cap.append((gx, y, gz))

    objects.append(create_curve_cable("PortUpperStrake", port_upper_strake, 0.024, mats["DarkMetal"]))
    objects.append(create_curve_cable("StbdUpperStrake", stbd_upper_strake, 0.024, mats["DarkMetal"]))
    objects.append(create_curve_cable("PortLowerStrake", port_lower_strake, 0.020, mats["DarkMetal"]))
    objects.append(create_curve_cable("StbdLowerStrake", stbd_lower_strake, 0.020, mats["DarkMetal"]))
    objects.append(create_curve_cable("PortGunwaleCap", port_gunwale_cap, 0.028, mats["DarkMetal"]))
    objects.append(create_curve_cable("StbdGunwaleCap", stbd_gunwale_cap, 0.028, mats["DarkMetal"]))

    # Stern transom top rail
    objects.append(
        create_cylinder_between(
            "SternGunwaleCap",
            (-0.76, 2.24, 0.73),
            (0.76, 2.24, 0.73),
            0.028,
            0.028,
            mats["DarkMetal"],
            segments=12,
        )
    )

    # Inner bulwark stanchion ribs along working deck
    for y_rib, half_w, top_z in [
        (-1.40, 0.82, 0.80),
        (-0.80, 0.90, 0.74),
        (-0.20, 0.91, 0.70),
        (0.45, 0.89, 0.66),
        (1.10, 0.85, 0.65),
        (1.75, 0.77, 0.67),
    ]:
        for side in (-1.0, 1.0):
            objects.append(
                create_box(
                    f"BulwarkRib_{y_rib:.1f}_{side:.0f}",
                    (side * half_w, y_rib, (deck_z + top_z) * 0.5),
                    (0.05, 0.045, top_z - deck_z),
                    mats["HullIron"],
                    bevel_width=0.004,
                )
            )

    # --- D. 4 Heavy Rubber Tire Fenders (2 Port, 2 Starboard) on Hanging Chains ---
    fender_mounts = [
        # (name, x_hull, y_pos, z_tire, z_gunwale, yaw_deg)
        ("FenderPortFwd", -1.03, -0.55, 0.46, 0.75, 5.0),
        ("FenderPortAft", -1.00,  0.85, 0.43, 0.67, -4.0),
        ("FenderStbdFwd",  1.03, -0.55, 0.46, 0.75, -5.0),
        ("FenderStbdAft",  1.00,  0.85, 0.43, 0.67, 4.0),
    ]
    for fname, fx, fy, fz, gz, yaw_deg in fender_mounts:
        # Torus aligned vertically against the outer hull side (normal along X)
        tire = create_torus(
            fname,
            (fx, fy, fz),
            major_radius=0.16,
            minor_radius=0.065,
            mat=mats["DarkMetal"],
            rotation_euler=(0.0, math.radians(90.0), math.radians(yaw_deg)),
            major_segments=24,
            minor_segments=12,
        )
        objects.append(tire)

        # Hanging vertical chain links from gunwale down to tire top
        chain_x = fx * 0.96
        num_links = 5
        for lk in range(num_links):
            t_link = lk / float(max(num_links - 1, 1))
            lz = (fz + 0.14) + t_link * (gz - (fz + 0.14))
            rot_y = math.radians(90.0) if (lk % 2 == 0) else 0.0
            link_obj = create_torus(
                f"{fname}_Chain_{lk}",
                (chain_x, fy, lz),
                major_radius=0.022,
                minor_radius=0.007,
                mat=mats["DarkMetal"],
                rotation_euler=(math.radians(90.0), rot_y, 0.0),
                major_segments=12,
                minor_segments=6,
            )
            objects.append(link_obj)

    return objects


# ---------------------------------------------------------------------------
# 2. Recessed Timber Working Deck & Deck Clutter
# ---------------------------------------------------------------------------

def build_working_deck_and_clutter(mats: Dict[str, bpy.types.Material]) -> List[bpy.types.Object]:
    """
    Builds:
      - Recessed wooden deck (DeckWood) at z = 0.35m with individual beveled longitudinal planks
      - Raised central fish-hold hatch cover with iron dog-clamps
      - Cast-iron twin mooring bollards at bow and stern
      - Coiled mooring ropes built from beveled spiral CURVE objects on deck
    """
    objects: List[bpy.types.Object] = []
    deck_z = 0.35

    # Base sub-deck floor plate (DarkMetal) so plank seams show dark caulking underneath
    objects.append(
        create_box(
            "SubDeckCaulk",
            (0.0, 0.18, deck_z - 0.03),
            (1.72, 4.08, 0.04),
            mats["DarkMetal"],
            bevel_width=0.0,
        )
    )

    # Individual beveled longitudinal timber planks across the deck width
    plank_width = 0.115
    plank_gap = 0.008
    step_x = plank_width + plank_gap
    for idx in range(-7, 8):
        px = idx * step_x
        abs_x = abs(px)
        # Taper plank forward length to fit inside the flared bow
        y_front = -1.92 + (abs_x * 0.72)
        y_back = 2.18
        if y_front >= y_back - 0.2:
            continue
        plank_len = y_back - y_front
        plank_cy = (y_front + y_back) * 0.5
        plank = create_box(
            f"DeckPlank_{idx}",
            (px, plank_cy, deck_z - 0.004),
            (plank_width, plank_len, 0.028),
            mats["DeckWood"],
            bevel_width=0.004,
        )
        objects.append(plank)

    # Raised central fish-hold hatch coaming & timber hatch cover (at y = 0.32, x = +0.12)
    hatch_cx, hatch_cy = 0.12, 0.34
    hatch_w, hatch_l = 0.62, 0.56
    # Steel coaming base
    objects.append(
        create_box(
            "HatchCoaming",
            (hatch_cx, hatch_cy, deck_z + 0.055),
            (hatch_w, hatch_l, 0.11),
            mats["CabinPaint"],
            bevel_width=0.008,
        )
    )
    # Recessed wooden hatch lid planks + steel binding frame
    objects.append(
        create_box(
            "HatchCoverLid",
            (hatch_cx, hatch_cy, deck_z + 0.12),
            (hatch_w + 0.04, hatch_l + 0.04, 0.035),
            mats["HullIron"],
            bevel_width=0.006,
        )
    )
    for p_i in range(-2, 3):
        objects.append(
            create_box(
                f"HatchTimber_{p_i}",
                (hatch_cx + p_i * 0.11, hatch_cy, deck_z + 0.142),
                (0.095, hatch_l - 0.04, 0.022),
                mats["DeckWood"],
                bevel_width=0.003,
            )
        )
    # Iron dog-clamps & hinges around hatch perimeter
    for dx in (-1.0, 1.0):
        for dy in (-0.18, 0.18):
            objects.append(
                create_box(
                    f"HatchDogClampX_{dx}_{dy}",
                    (hatch_cx + dx * (hatch_w * 0.5 + 0.022), hatch_cy + dy, deck_z + 0.105),
                    (0.035, 0.045, 0.065),
                    mats["DarkMetal"],
                    bevel_width=0.003,
                )
            )
    for dy in (-1.0, 1.0):
        for dx in (-0.18, 0.18):
            objects.append(
                create_box(
                    f"HatchDogClampY_{dy}_{dx}",
                    (hatch_cx + dx, hatch_cy + dy * (hatch_l * 0.5 + 0.022), deck_z + 0.105),
                    (0.045, 0.035, 0.065),
                    mats["DarkMetal"],
                    bevel_width=0.003,
                )
            )

    # Cast-iron Twin Mooring Bollards (Bow Foredeck & Stern Quarters)
    bollard_sites = [
        ("BollardBowPort", -0.32, -1.62),
        ("BollardBowStbd",  0.32, -1.62),
        ("BollardSternPort", -0.58, 1.98),
        ("BollardSternStbd",  0.58, 1.98),
    ]
    for bname, bx, by in bollard_sites:
        # Base plate
        objects.append(
            create_box(
                f"{bname}_Base",
                (bx, by, deck_z + 0.018),
                (0.16, 0.26, 0.036),
                mats["DarkMetal"],
                bevel_width=0.005,
            )
        )
        # Twin vertical cast-iron horns + top mushrooms + cross-pin
        for dy_horn in (-0.065, 0.065):
            hy = by + dy_horn
            objects.append(
                create_cylinder_between(
                    f"{bname}_Post_{dy_horn}",
                    (bx, hy, deck_z + 0.03),
                    (bx, hy, deck_z + 0.21),
                    0.036,
                    0.032,
                    mats["DarkMetal"],
                    segments=12,
                )
            )
            objects.append(
                create_cylinder_between(
                    f"{bname}_Cap_{dy_horn}",
                    (bx, hy, deck_z + 0.21),
                    (bx, hy, deck_z + 0.235),
                    0.046,
                    0.042,
                    mats["DarkMetal"],
                    segments=12,
                )
            )
        objects.append(
            create_cylinder_between(
                f"{bname}_CrossPin",
                (bx - 0.06, by, deck_z + 0.14),
                (bx + 0.06, by, deck_z + 0.14),
                0.014,
                0.014,
                mats["DarkMetal"],
                segments=8,
            )
        )

    # Coiled Mooring Ropes (beveled spiral CURVE objects resting on deck)
    coil_sites = [
        ("RopeCoilForedeck", 0.0, -1.42, 0.04, 0.22, 4.5),
        ("RopeCoilPortAft", -0.50, 1.25, 0.035, 0.20, 4.0),
        ("RopeCoilStbdMid",  0.58, -0.05, 0.03, 0.17, 3.5),
    ]
    for cname, cx, cy, r_min, r_max, turns in coil_sites:
        spiral_pts: List[Vec3] = []
        total_steps = int(turns * 20)
        for s in range(total_steps + 1):
            t = s / float(total_steps)
            ang = t * turns * 2.0 * math.pi
            rad = r_min + (r_max - r_min) * t
            # Slight stacking height near center
            z_off = deck_z + 0.022 + (1.0 - t) * 0.025 + 0.004 * math.sin(ang * 3.0)
            spiral_pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad, z_off))
        objects.append(create_curve_cable(cname, spiral_pts, bevel_depth=0.016, mat=mats["DeckWood"], resolution_u=8))

    return objects


# ---------------------------------------------------------------------------
# 3. Boolean-Carved Forward Wheelhouse (y = -1.10m to -0.10m)
# ---------------------------------------------------------------------------

def build_wheelhouse(mats: Dict[str, bpy.types.Material]) -> List[bpy.types.Object]:
    """
    Constructs the forward pilothouse (y = -1.10m to -0.10m):
      - Angled maritime pilothouse with forward-sloping windshield & overhanging roof brow/visor
      - Blender BOOLEAN (DIFFERENCE) modifiers cutting real recessed window cavities across front,
        sides, and rear door
      - Internal WindowGlow emissive core framed by 3D dark wooden mullions
      - Weathered Lifebuoy Ring (Torus with rope bands) on port cabin wall
      - Exterior handrails & rooftop radar dome / compass binnacle behind searchlight mount
    """
    objects: List[bpy.types.Object] = []

    z_deck = 0.35
    z_waist = 1.06
    z_roof = 1.74

    hx_low = 0.60
    hx_top = 0.56
    y_front_bot = -1.10
    y_front_mid = -1.08
    y_front_top = -0.94  # Raked windshield top
    y_back = -0.10

    # --- A. Outer Wheelhouse Shell (CabinPaint) carved with BOOLEAN DIFFERENCE ---
    wh_mesh = bpy.data.meshes.new("WheelhouseOuter_mesh")
    wh_obj = bpy.data.objects.new("WheelhouseOuter", wh_mesh)
    bpy.context.collection.objects.link(wh_obj)
    assign_material(wh_obj, mats["CabinPaint"])

    bm = bmesh.new()
    # Bottom ring (z = z_deck)
    v_b_fl = bm.verts.new((-hx_low, y_front_bot, z_deck))
    v_b_fr = bm.verts.new(( hx_low, y_front_bot, z_deck))
    v_b_br = bm.verts.new(( hx_low, y_back,      z_deck))
    v_b_bl = bm.verts.new((-hx_low, y_back,      z_deck))

    # Waist ring (z = z_waist)
    v_m_fl = bm.verts.new((-hx_top, y_front_mid, z_waist))
    v_m_fr = bm.verts.new(( hx_top, y_front_mid, z_waist))
    v_m_br = bm.verts.new(( hx_top, y_back,      z_waist))
    v_m_bl = bm.verts.new((-hx_top, y_back,      z_waist))

    # Roof ring (z = z_roof)
    v_t_fl = bm.verts.new((-hx_top, y_front_top, z_roof))
    v_t_fr = bm.verts.new(( hx_top, y_front_top, z_roof))
    v_t_br = bm.verts.new(( hx_top, y_back,      z_roof))
    v_t_bl = bm.verts.new((-hx_top, y_back,      z_roof))

    # Lower trunk faces
    bm.faces.new((v_b_fl, v_b_fr, v_m_fr, v_m_fl))
    bm.faces.new((v_b_fr, v_b_br, v_m_br, v_m_fr))
    bm.faces.new((v_b_br, v_b_bl, v_m_bl, v_m_br))
    bm.faces.new((v_b_bl, v_b_fl, v_m_fl, v_m_bl))
    bm.faces.new((v_b_bl, v_b_br, v_b_fr, v_b_fl))

    # Upper raked pilothouse faces
    bm.faces.new((v_m_fl, v_m_fr, v_t_fr, v_t_fl))
    bm.faces.new((v_m_fr, v_m_br, v_t_br, v_t_fr))
    bm.faces.new((v_m_br, v_m_bl, v_t_bl, v_t_br))
    bm.faces.new((v_m_bl, v_m_fl, v_t_fl, v_t_bl))
    bm.faces.new((v_t_fl, v_t_fr, v_t_br, v_t_bl))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(wh_mesh)
    bm.free()

    # Create BOOLEAN cutter collection object for front, side, and rear windows
    cutter_objs: List[bpy.types.Object] = []

    # 3 Front windshield window cutters (angled to match raked front wall)
    rake_angle = math.atan2(y_front_top - y_front_mid, z_roof - z_waist)
    win_z_center = (z_waist + z_roof) * 0.5 + 0.02
    win_y_center = (y_front_mid + y_front_top) * 0.5
    for idx, x_c in enumerate((-0.34, 0.0, 0.34)):
        w_pane = 0.25 if idx != 1 else 0.27
        c_front = create_box(
            f"Cutter_FrontWin_{idx}",
            (x_c, win_y_center - 0.02, win_z_center),
            (w_pane, 0.24, 0.42),
            mats["DarkMetal"],
            rotation_euler=(-rake_angle, 0.0, 0.0),
            bevel_width=0.0,
        )
        cutter_objs.append(c_front)

    # Port & Starboard side window cutters
    c_side_fwd = create_box(
        "Cutter_SideWinFwd",
        (0.0, -0.74, win_z_center),
        (1.40, 0.38, 0.40),
        mats["DarkMetal"],
        bevel_width=0.0,
    )
    cutter_objs.append(c_side_fwd)

    # Rear window & door cutout on aft wall of cabin
    c_rear_win = create_box(
        "Cutter_RearWin",
        (0.0, y_back + 0.02, win_z_center),
        (0.46, 0.22, 0.38),
        mats["DarkMetal"],
        bevel_width=0.0,
    )
    cutter_objs.append(c_rear_win)

    # Join all window cutters into a single cutter mesh and apply BOOLEAN DIFFERENCE
    bpy.ops.object.select_all(action="DESELECT")
    for c_obj in cutter_objs:
        c_obj.select_set(True)
    bpy.context.view_layer.objects.active = cutter_objs[0]
    bpy.ops.object.join()
    combined_cutter = bpy.context.active_object
    combined_cutter.name = "WheelhouseWindowCutters"

    bool_mod = wh_obj.modifiers.new(name="WindowCutouts", type="BOOLEAN")
    bool_mod.operation = "DIFFERENCE"
    bool_mod.object = combined_cutter
    bool_mod.solver = "EXACT"
    add_bevel_modifier(wh_obj, width=0.006, segments=2, angle_limit=32.0)
    apply_all_modifiers(wh_obj)

    # Remove cutter object after boolean is applied
    bpy.data.objects.remove(combined_cutter, do_unlink=True)
    objects.append(wh_obj)

    # --- B. Internal Emissive WindowGlow Core Inside the Recessed Cutouts ---
    glow_mesh = bpy.data.meshes.new("WheelhouseGlow_mesh")
    glow_obj = bpy.data.objects.new("WheelhouseGlow", glow_mesh)
    bpy.context.collection.objects.link(glow_obj)
    assign_material(glow_obj, mats["WindowGlow"])

    bm_g = bmesh.new()
    gx = hx_top - 0.045
    gy_f_bot = y_front_mid + 0.055
    gy_f_top = y_front_top + 0.055
    gy_b = y_back - 0.045
    gz_0 = z_waist + 0.14
    gz_1 = z_roof - 0.10

    g_b_fl = bm_g.verts.new((-gx, gy_f_bot, gz_0))
    g_b_fr = bm_g.verts.new(( gx, gy_f_bot, gz_0))
    g_b_br = bm_g.verts.new(( gx, gy_b,     gz_0))
    g_b_bl = bm_g.verts.new((-gx, gy_b,     gz_0))

    g_t_fl = bm_g.verts.new((-gx, gy_f_top, gz_1))
    g_t_fr = bm_g.verts.new(( gx, gy_f_top, gz_1))
    g_t_br = bm_g.verts.new(( gx, gy_b,     gz_1))
    g_t_bl = bm_g.verts.new((-gx, gy_b,     gz_1))

    bm_g.faces.new((g_b_fl, g_b_fr, g_t_fr, g_t_fl))
    bm_g.faces.new((g_b_fr, g_b_br, g_t_br, g_t_fr))
    bm_g.faces.new((g_b_br, g_b_bl, g_t_bl, g_t_br))
    bm_g.faces.new((g_b_bl, g_b_fl, g_t_fl, g_t_bl))
    bm_g.faces.new((g_t_fl, g_t_fr, g_t_br, g_t_bl))
    bm_g.faces.new((g_b_bl, g_b_br, g_b_fr, g_b_fl))

    bmesh.ops.recalc_face_normals(bm_g, faces=bm_g.faces)
    bm_g.to_mesh(glow_mesh)
    bm_g.free()
    objects.append(glow_obj)

    # --- C. 3D Dark Wooden Window Mullions & Sills (DeckWood) ---
    # Front windshield vertical mullions and top/bottom sills
    for mx in (-0.48, -0.20, 0.20, 0.48):
        objects.append(
            create_box(
                f"FrontMullion_{mx:.2f}",
                (mx, win_y_center - 0.005, win_z_center),
                (0.032, 0.055, 0.45),
                mats["DeckWood"],
                rotation_euler=(-rake_angle, 0.0, 0.0),
                bevel_width=0.004,
            )
        )
    for sz_off in (-0.21, 0.21):
        sy = win_y_center + (sz_off * math.sin(rake_angle)) - 0.008
        objects.append(
            create_box(
                f"FrontSill_{sz_off:.2f}",
                (0.0, sy, win_z_center + sz_off),
                (1.04, 0.06, 0.034),
                mats["DeckWood"],
                rotation_euler=(-rake_angle, 0.0, 0.0),
                bevel_width=0.004,
            )
        )

    # Side window timber frames (Port & Starboard)
    for side in (-1.0, 1.0):
        sx = side * (hx_top - 0.005)
        for sz_off in (-0.20, 0.20):
            objects.append(
                create_box(
                    f"SideSill_{side}_{sz_off}",
                    (sx, -0.74, win_z_center + sz_off),
                    (0.05, 0.42, 0.032),
                    mats["DeckWood"],
                    bevel_width=0.003,
                )
            )
        for sy_pos in (-0.93, -0.74, -0.55):
            objects.append(
                create_box(
                    f"SideMullion_{side}_{sy_pos}",
                    (sx, sy_pos, win_z_center),
                    (0.05, 0.03, 0.42),
                    mats["DeckWood"],
                    bevel_width=0.003,
                )
            )

    # Port & Starboard aft cabin doors (DarkMetal) + porthole rims
    for side in (-1.0, 1.0):
        dx = side * (hx_low - 0.005)
        objects.append(
            create_box(
                f"CabinDoor_{side}",
                (dx, -0.30, 0.94),
                (0.045, 0.34, 1.12),
                mats["DarkMetal"],
                bevel_width=0.005,
            )
        )
        # Brass/iron door handle
        objects.append(
            create_box(
                f"DoorHandle_{side}",
                (dx + side * 0.025, -0.20, 0.92),
                (0.02, 0.06, 0.02),
                mats["HullIron"],
                bevel_width=0.002,
            )
        )

    # --- D. Overhanging Pilothouse Roof Brow / Sun Visor (HullIron) ---
    objects.append(
        create_box(
            "WheelhouseRoofVisor",
            (0.0, -0.59, z_roof + 0.045),
            (1.26, 1.16, 0.08),
            mats["HullIron"],
            bevel_width=0.012,
        )
    )
    # Angled front brow shield
    objects.append(
        create_box(
            "WheelhouseFrontBrow",
            (0.0, -1.16, z_roof + 0.02),
            (1.24, 0.14, 0.06),
            mats["HullIron"],
            rotation_euler=(math.radians(18.0), 0.0, 0.0),
            bevel_width=0.008,
        )
    )

    # --- E. Weathered Orange/Red Lifebuoy Ring on Port Cabin Wall ---
    buoy_center: Vec3 = (-hx_low - 0.045, -0.72, 0.76)
    lifebuoy = create_torus(
        "LifebuoyRing",
        buoy_center,
        major_radius=0.17,
        minor_radius=0.048,
        mat=mats["LifeRing"],
        rotation_euler=(0.0, math.radians(90.0), 0.0),
        major_segments=28,
        minor_segments=14,
    )
    objects.append(lifebuoy)

    # 4 rope-band collars around the lifebuoy ring + wall mounting bracket
    for angle_deg in (45.0, 135.0, 225.0, 315.0):
        rad = math.radians(angle_deg)
        by = buoy_center[1] + math.cos(rad) * 0.17
        bz = buoy_center[2] + math.sin(rad) * 0.17
        band = create_torus(
            f"LifebuoyBand_{angle_deg:.0f}",
            (buoy_center[0], by, bz),
            major_radius=0.050,
            minor_radius=0.010,
            mat=mats["CabinPaint"],
            rotation_euler=(math.radians(angle_deg), 0.0, 0.0),
            major_segments=14,
            minor_segments=8,
        )
        objects.append(band)

    # --- F. Exterior Handrails & Rooftop Radar Dome / Compass Binnacle ---
    # Side grab rails along lower cabin coaming & roof edges
    for side in (-1.0, 1.0):
        rx_side = side * (hx_low + 0.035)
        objects.append(
            create_cylinder_between(
                f"CabinGrabRail_{side}",
                (rx_side, -1.04, 1.03),
                (rx_side, -0.50, 1.03),
                0.014,
                0.014,
                mats["DarkMetal"],
                segments=10,
            )
        )
        rx_roof = side * 0.56
        objects.append(
            create_cylinder_between(
                f"RoofHandrail_{side}",
                (rx_roof, -1.02, z_roof + 0.12),
                (rx_roof, -0.12, z_roof + 0.12),
                0.015,
                0.015,
                mats["DarkMetal"],
                segments=10,
            )
        )
        for ry_post in (-1.00, -0.56, -0.14):
            objects.append(
                create_cylinder_between(
                    f"RoofRailPost_{side}_{ry_post}",
                    (rx_roof, ry_post, z_roof + 0.07),
                    (rx_roof, ry_post, z_roof + 0.125),
                    0.012,
                    0.012,
                    mats["DarkMetal"],
                    segments=8,
                )
            )

    # Searchlight Mounting Pedestal at (0.0, -0.75, 1.78..1.85) where Godot's SearchlightGimbal sits
    objects.append(
        create_cylinder_between(
            "SearchlightPedestalBase",
            (0.0, -0.75, z_roof + 0.06),
            (0.0, -0.75, 1.85),
            0.095,
            0.065,
            mats["DarkMetal"],
            segments=16,
        )
    )

    # Rooftop Radar Dome & Compass Binnacle behind the searchlight mount (at y = -0.52)
    objects.append(
        create_cylinder_between(
            "RadarPedestal",
            (0.0, -0.52, z_roof + 0.06),
            (0.0, -0.52, z_roof + 0.24),
            0.065,
            0.048,
            mats["DarkMetal"],
            segments=14,
        )
    )
    objects.append(
        create_cylinder_between(
            "RadarRadomeDrum",
            (0.0, -0.52, z_roof + 0.24),
            (0.0, -0.52, z_roof + 0.36),
            0.19,
            0.17,
            mats["CabinPaint"],
            segments=20,
        )
    )
    # Navigation horn mounted on starboard roof
    objects.append(
        create_cylinder_between(
            "FogHorn",
            (0.36, -0.82, z_roof + 0.11),
            (0.36, -1.05, z_roof + 0.13),
            0.020,
            0.055,
            mats["DarkMetal"],
            segments=12,
        )
    )

    return objects


# ---------------------------------------------------------------------------
# 4. Diesel Smokestack, Rigging Mast & Stern A-Frame Dredge Gantry
# ---------------------------------------------------------------------------

def build_rigging_and_stern_gantry(mats: Dict[str, bpy.types.Material]) -> List[bpy.types.Object]:
    """
    Builds:
      - Raked cylindrical diesel exhaust stack (-0.32, 0.28, 2.08 top) with outer heat-shield cage
      - Tapered main mast with cross-yardarms, masthead light, & 3D catenary rigging cables
      - Heavy industrial steel Stern A-Frame dredge gantry with top pulley sheaves, hydraulic
        support struts, dual-drum trawl winch wound with steel cable, and hanging iron chains
    """
    objects: List[bpy.types.Object] = []
    deck_z = 0.35

    # --- A. Raked Diesel Smokestack + Perforated Heat-Shield Cage (Port side behind cabin) ---
    stack_base: Vec3 = (-0.32, 0.08, deck_z)
    stack_top: Vec3 = (-0.32, 0.26, 1.96)
    stack_tip: Vec3 = (-0.32, 0.30, 2.09)  # Matches ExhaustSmoke at (-0.32, 2.08, 0.28) in Godot!

    # Base deck casing box
    objects.append(
        create_box(
            "StackBaseCasing",
            (-0.32, 0.08, deck_z + 0.18),
            (0.34, 0.34, 0.36),
            mats["HullIron"],
            bevel_width=0.008,
        )
    )
    # Inner exhaust pipe
    objects.append(
        create_cylinder_between(
            "DieselExhaustStack",
            stack_base,
            stack_top,
            0.125,
            0.100,
            mats["DarkMetal"],
            segments=18,
        )
    )
    # Angled exhaust tip pipe at top
    objects.append(
        create_cylinder_between(
            "DieselExhaustTip",
            (-0.32, 0.25, 1.90),
            stack_tip,
            0.092,
            0.082,
            mats["DarkMetal"],
            segments=16,
        )
    )

    # Outer perforated / slotted cage heat-shield around the stack (vertical bars + 3 collar rings)
    v_stack_b = Vector(stack_base)
    v_stack_t = Vector(stack_top)
    stack_axis = (v_stack_t - v_stack_b).normalized()
    stack_rot = stack_axis.to_track_quat("Z", "Y").to_euler()

    for t_ring in (0.30, 0.58, 0.86):
        ring_pos = v_stack_b.lerp(v_stack_t, t_ring)
        objects.append(
            create_torus(
                f"StackCageRing_{t_ring:.2f}",
                (ring_pos.x, ring_pos.y, ring_pos.z),
                major_radius=0.148,
                minor_radius=0.012,
                mat=mats["DarkMetal"],
                rotation_euler=(stack_rot.x, stack_rot.y, stack_rot.z),
                major_segments=18,
                minor_segments=8,
            )
        )

    p_cage_0 = v_stack_b.lerp(v_stack_t, 0.28)
    p_cage_1 = v_stack_b.lerp(v_stack_t, 0.88)
    num_cage_bars = 10
    for b_idx in range(num_cage_bars):
        ang = (2.0 * math.pi * b_idx) / num_cage_bars
        ox = math.cos(ang) * 0.148
        oy = math.sin(ang) * 0.148
        objects.append(
            create_cylinder_between(
                f"StackCageBar_{b_idx}",
                (p_cage_0.x + ox, p_cage_0.y + oy, p_cage_0.z),
                (p_cage_1.x + ox, p_cage_1.y + oy, p_cage_1.z),
                0.009,
                0.009,
                mats["DarkMetal"],
                segments=8,
            )
        )

    # --- B. Tapered Main Mast, Yardarms & 3D Catenary Rigging Cables ---
    mast_base: Vec3 = (0.0, -0.35, 1.78)
    mast_top: Vec3 = (0.0, -0.32, 3.26)
    objects.append(
        create_cylinder_between(
            "MainMast",
            mast_base,
            mast_top,
            0.058,
            0.032,
            mats["DarkMetal"],
            segments=14,
        )
    )

    # Upper & lower cross-yardarms (crosstrees)
    yard_z = 2.78
    yard_y = -0.33
    objects.append(
        create_cylinder_between(
            "MainYardarm",
            (-0.62, yard_y, yard_z),
            (0.62, yard_y, yard_z),
            0.024,
            0.024,
            mats["DarkMetal"],
            segments=10,
        )
    )
    objects.append(
        create_cylinder_between(
            "UpperSpreader",
            (-0.36, -0.32, 3.08),
            (0.36, -0.32, 3.08),
            0.018,
            0.018,
            mats["DarkMetal"],
            segments=10,
        )
    )

    # Masthead Navigation Light (WindowGlow) at top of mast
    objects.append(
        create_cylinder_between(
            "MastheadLantern",
            (0.0, -0.32, 3.26),
            (0.0, -0.32, 3.40),
            0.056,
            0.046,
            mats["WindowGlow"],
            segments=14,
        )
    )
    objects.append(
        create_cylinder_between(
            "MastheadCap",
            (0.0, -0.32, 3.40),
            (0.0, -0.32, 3.44),
            0.064,
            0.020,
            mats["DarkMetal"],
            segments=14,
        )
    )

    # 3D Catenary Rigging Cables (CURVE splines with bevel_depth = 0.015)
    # Note: Rear stays and stern A-frame/winch are omitted so the aft fishing deck is 100% unobstructed.
    rigging_runs = [
        # Forestay from masthead down to bow stem
        ("Rig_Forestay", (0.0, -0.32, 3.22), (0.0, -2.32, 0.96), 0.06),
        # Port & Starboard crosstree shrouds to forward bow gunwales
        ("Rig_PortFwdShroud", (-0.58, yard_y, yard_z), (-0.82, -1.55, 0.84), 0.05),
        ("Rig_StbdFwdShroud", ( 0.58, yard_y, yard_z), ( 0.82, -1.55, 0.84), 0.05),
        # Port & Starboard main shrouds from masthead to midship gunwales
        ("Rig_PortMidShroud", (-0.04, -0.32, 3.18), (-0.96, -0.35, 0.72), 0.04),
        ("Rig_StbdMidShroud", ( 0.04, -0.32, 3.18), ( 0.96, -0.35, 0.72), 0.04),
    ]
    for rname, p_a, p_b, sag in rigging_runs:
        pts = catenary_points(p_a, p_b, sag=sag, steps=16)
        objects.append(create_curve_cable(rname, pts, bevel_depth=0.015, mat=mats["DarkMetal"], resolution_u=8))

    # --- C. Wheelhouse Rear Overhang Deck Lantern (y = 0.02m, z = 1.54..1.72m) ---
    # Relocated from the removed stern A-frame to the aft overhang of the wheelhouse cabin
    # so the entire rear working deck is open for first-person fishing while staying warmly lit.
    lantern_y = 0.02
    objects.append(
        create_cylinder_between(
            "SternLanternBracket",
            (0.0, -0.10, 1.72),
            (0.0, lantern_y, 1.72),
            0.022,
            0.022,
            mats["DarkMetal"],
            segments=10,
        )
    )
    objects.append(
        create_cylinder_between(
            "SternLanternMount",
            (0.0, lantern_y, 1.72),
            (0.0, lantern_y, 1.66),
            0.022,
            0.042,
            mats["DarkMetal"],
            segments=10,
        )
    )
    objects.append(
        create_cylinder_between(
            "SternLanternHood",
            (0.0, lantern_y, 1.66),
            (0.0, lantern_y, 1.62),
            0.045,
            0.085,
            mats["DarkMetal"],
            segments=14,
        )
    )
    objects.append(
        create_cylinder_between(
            "SternLanternGlass",
            (0.0, lantern_y, 1.62),
            (0.0, lantern_y, 1.51),
            0.056,
            0.045,
            mats["WindowGlow"],
            segments=14,
        )
    )

    return objects


# ---------------------------------------------------------------------------
# Join, Coordinate Alignment & GLB Export
# ---------------------------------------------------------------------------

def finalize_and_export_glb(
    objects: List[bpy.types.Object],
    mats: Dict[str, bpy.types.Material],
    output_glb_path: str,
) -> None:
    """
    Converts all CURVE objects to MESH, applies all modifiers, joins everything into
    a single clean `TrawlerMesh` object with deterministic material slot ordering,
    aligns longitudinal coordinates for glTF (+Y Up -> Godot -Z Forward), and exports .glb.
    """
    bpy.ops.object.select_all(action="DESELECT")

    mesh_objects: List[bpy.types.Object] = []
    for obj in objects:
        if obj is None or obj.name not in bpy.data.objects:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        if obj.type == "CURVE":
            bpy.ops.object.convert(target="MESH")
        elif obj.type == "MESH":
            apply_all_modifiers(obj)

        mesh_objects.append(bpy.context.active_object)

    # Join all meshes into a single clean TrawlerMesh
    bpy.ops.object.select_all(action="DESELECT")
    for obj in mesh_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objects[0]
    bpy.ops.object.join()

    trawler_obj = bpy.context.active_object
    trawler_obj.name = "TrawlerMesh"
    trawler_obj.data.name = "TrawlerMesh"

    # Bake transforms into mesh vertices
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Blender's glTF 2.0 exporter with export_yup=True maps:
    #   (x_blender, y_blender, z_blender) -> (x_gltf, z_blender, -y_blender)
    # Since we modeled with bow at y = -2.40 and stern at y = +2.50, negating Y on the
    # mesh vertices (and reversing face winding to preserve outward normals) makes glTF
    # export the bow to z_godot = -2.40 (-Z forward) and stern to z_godot = +2.50 (+Z aft),
    # while keeping Port at -X, Starboard at +X, and Up at +Y!
    bm = bmesh.new()
    bm.from_mesh(trawler_obj.data)
    bmesh.ops.scale(bm, vec=Vector((1.0, -1.0, 1.0)), verts=bm.verts)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(trawler_obj.data)
    bm.free()

    # Smooth shade with sharp edge auto-split via normals update
    for poly in trawler_obj.data.polygons:
        poly.use_smooth = False

    os.makedirs(os.path.dirname(output_glb_path), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=output_glb_path,
        export_format="GLB",
        export_apply=True,
        export_yup=True,
    )

    num_verts = len(trawler_obj.data.vertices)
    num_polys = len(trawler_obj.data.polygons)
    print(f"[Blender 5.4.0] Exported TrawlerMesh to {output_glb_path}")
    print(f"[Blender 5.4.0] Vertices: {num_verts}, Polygons: {num_polys}, Materials: {len(trawler_obj.data.materials)}")


def main() -> None:
    clear_scene()
    mats = create_pbr_materials()

    all_objects: List[bpy.types.Object] = []
    all_objects.extend(build_naval_hull(mats))
    all_objects.extend(build_working_deck_and_clutter(mats))
    all_objects.extend(build_wheelhouse(mats))
    all_objects.extend(build_rigging_and_stern_gantry(mats))

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_glb = os.path.join(project_root, "assets", "models", "trawler.glb")
    finalize_and_export_glb(all_objects, mats, output_glb)


if __name__ == "__main__":
    main()
