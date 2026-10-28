#!/usr/bin/env python3
"""
Headless Blender 5.4.0 Wharf Island, Harbor Settlement & Coastal Lighthouse Generator.

Run via:
  blender --background --python tools/blender_build_wharf.py

Exports:
  assets/models/wharf_island.glb

Coordinate Convention:
  - In helper construction space (Godot target coordinates):
      gx : -X Port/West, +X Starboard/East
      gy : +Y Elevation (Up)
      gz : -Z North/Forward, +Z South/Aft (pier starts at gz = +4.0m, island extends to +68.0m)
  - Converted to Blender Z-up space with longitudinal Y negated prior to glTF (+Y Up) export
    so that Blender's glTF 2.0 exporter maps every vertex to exact Godot (gx, gy, gz) coordinates.
  - Spawn Clearance Rule: Clean 8.0m deep-water radius around (0, 0, 0) in front of the pier edge (z = +4.0m).
"""

import math
import os
import random
from typing import Dict, List, Sequence, Tuple

import bmesh
import bpy
from mathutils import Matrix, Vector

Vec3 = Tuple[float, float, float]


# ---------------------------------------------------------------------------
# PBR Material Definitions (Principled BSDF)
# ---------------------------------------------------------------------------

MATERIAL_SPECS: List[Tuple[str, Tuple[float, float, float, float], float, float, Tuple[float, float, float, float], float]] = [
    # (Name, BaseColor, Metallic, Roughness, EmissionColor, EmissionStrength)
    ("TidalWetRock",    (0.10, 0.13, 0.15, 1.0), 0.20, 0.12, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("BasaltCliff",     (0.20, 0.23, 0.26, 1.0), 0.10, 0.88, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("CoastalMoss",     (0.15, 0.23, 0.17, 1.0), 0.05, 0.92, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("WeatheredTimber", (0.23, 0.18, 0.13, 1.0), 0.00, 0.84, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("RottingWood",     (0.15, 0.13, 0.11, 1.0), 0.00, 0.86, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("ShackWall",       (0.27, 0.25, 0.22, 1.0), 0.02, 0.82, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("CorrugatedRoof",  (0.22, 0.15, 0.13, 1.0), 0.65, 0.58, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("RustIron",        (0.14, 0.10, 0.09, 1.0), 0.70, 0.55, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("DarkMetal",       (0.07, 0.08, 0.09, 1.0), 0.80, 0.48, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("LighthouseStone", (0.38, 0.40, 0.42, 1.0), 0.05, 0.85, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("LighthouseBand",  (0.46, 0.12, 0.10, 1.0), 0.08, 0.78, (0.0, 0.0, 0.0, 1.0), 0.0),
    ("AmberGlass",      (1.00, 0.72, 0.30, 1.0), 0.00, 0.18, (1.00, 0.65, 0.24, 1.0), 5.0),
    ("BeaconLens",      (1.00, 0.92, 0.68, 1.0), 0.00, 0.10, (1.00, 0.88, 0.60, 1.0), 14.0),
]


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def create_pbr_materials() -> Dict[str, bpy.types.Material]:
    mats: Dict[str, bpy.types.Material] = {}
    for name, base_color, metallic, roughness, emission_color, emission_strength in MATERIAL_SPECS:
        mat = bpy.data.materials.new(name=name)
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
# Coordinate & Primitive Helpers
# ---------------------------------------------------------------------------
# All input coordinates to helpers are in Godot space: (gx, gy_up, gz_south).
# Internally we store them in Blender modeling space: (x = gx, y = gz_south, z = gy_up).
# At export time, Y is negated on the final mesh so glTF (+Y Up) exports (gx, gy_up, gz_south).

def g2b(pt: Vec3) -> Vector:
    """Convert Godot (x, y_up, z_south) to Blender Z-up modeling coordinates (x, z_south, y_up)."""
    return Vector((pt[0], pt[2], pt[1]))


def assign_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    if obj.data is None:
        return
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def add_bevel_modifier(obj: bpy.types.Object, width: float = 0.015, segments: int = 1, angle_limit: float = 35.0) -> None:
    bev = obj.modifiers.new(name="Bevel", type="BEVEL")
    bev.width = width
    bev.segments = segments
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(angle_limit)


def apply_all_modifiers(obj: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = obj
    for mod in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def create_box_g(
    name: str,
    center_g: Vec3,
    size_g: Vec3,
    mat: bpy.types.Material,
    yaw_deg: float = 0.0,
    pitch_deg: float = 0.0,
    roll_deg: float = 0.0,
    bevel_width: float = 0.0,
) -> bpy.types.Object:
    """Creates a box in Godot coordinates (x, y_up, z) with optional rotations and bevel."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    # In Blender space: size.x = size_g.x, size.y = size_g.z, size.z = size_g.y
    bmesh.ops.scale(bm, vec=Vector((size_g[0], size_g[2], size_g[1])), verts=bm.verts)
    bm.to_mesh(mesh)
    bm.free()

    obj.location = g2b(center_g)
    # Map Godot (pitch around X, yaw around Y_up, roll around Z) to Blender (X, Y_depth, Z_up)
    obj.rotation_euler = (
        math.radians(pitch_deg),
        math.radians(roll_deg),
        math.radians(-yaw_deg),
    )
    assign_material(obj, mat)
    if bevel_width > 0.0:
        add_bevel_modifier(obj, width=bevel_width, segments=1)
    return obj


def create_cylinder_g(
    name: str,
    p_start_g: Vec3,
    p_end_g: Vec3,
    r_start: float,
    r_end: float,
    mat: bpy.types.Material,
    segments: int = 12,
    cap_ends: bool = True,
) -> bpy.types.Object:
    """Creates a tapered cylinder between two Godot (x, y_up, z) points."""
    v0 = g2b(p_start_g)
    v1 = g2b(p_end_g)
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


def create_torus_g(
    name: str,
    center_g: Vec3,
    major_radius: float,
    minor_radius: float,
    mat: bpy.types.Material,
    rot_blender: Vec3 = (0.0, 0.0, 0.0),
    major_segments: int = 20,
    minor_segments: int = 10,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(
        align="WORLD",
        location=g2b(center_g),
        rotation=rot_blender,
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=major_segments,
        minor_segments=minor_segments,
    )
    obj = bpy.context.active_object
    obj.name = name
    assign_material(obj, mat)
    return obj


def create_curve_g(
    name: str,
    points_g: Sequence[Vec3],
    bevel_depth: float,
    mat: bpy.types.Material,
    resolution_u: int = 10,
    cyclic: bool = False,
) -> bpy.types.Object:
    curve_data = bpy.data.curves.new(name=name + "_curve", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = resolution_u
    curve_data.bevel_depth = bevel_depth
    curve_data.bevel_resolution = 3
    curve_data.use_fill_caps = True

    spline = curve_data.splines.new(type="POLY")
    spline.points.add(len(points_g) - 1)
    for idx, pt_g in enumerate(points_g):
        vb = g2b(pt_g)
        spline.points[idx].co = (vb.x, vb.y, vb.z, 1.0)
    spline.use_cyclic_u = cyclic

    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    assign_material(obj, mat)
    return obj


def catenary_points_g(p0_g: Vec3, p1_g: Vec3, sag: float, steps: int = 14, sway_x: float = 0.0) -> List[Vec3]:
    pts: List[Vec3] = []
    for i in range(steps + 1):
        t = i / float(steps)
        gx = p0_g[0] + (p1_g[0] - p0_g[0]) * t + math.sin(t * math.pi) * sway_x
        gy = p0_g[1] + (p1_g[1] - p0_g[1]) * t - 4.0 * t * (1.0 - t) * sag
        gz = p0_g[2] + (p1_g[2] - p0_g[2]) * t
        pts.append((gx, gy, gz))
    return pts


def ridge_noise(x: float, y: float, z: float, seed: int = 0) -> float:
    p1 = math.sin(x * 0.43 + z * 0.37 + float(seed) * 1.7) * math.cos(y * 0.31 - x * 0.29)
    p2 = math.sin(x * 0.91 - z * 0.83 + y * 0.53 + float(seed) * 3.1)
    p3 = math.cos(z * 1.47 + x * 1.13 - y * 0.79 + float(seed) * 5.3)
    r1 = 1.0 - abs(p1)
    r2 = 1.0 - abs(p2)
    r3 = 1.0 - abs(p3)
    return (r1 * 0.55 + r2 * 0.30 + r3 * 0.15) * 2.0 - 1.0


# ---------------------------------------------------------------------------
# 1. Sculpted Coastal Crag, Breakwater Jetty & 42-Step Stone Staircase
# ---------------------------------------------------------------------------

def build_coastal_crag_and_staircase(mats: Dict[str, bpy.types.Material]) -> List[bpy.types.Object]:
    """
    Builds:
      - High-resolution coastal crag island (z = +10m to +68m, x = -30m to +30m, peak y = 10.8m)
        with a sheltered crescent harbor cove on the -Z side and curved breakwater jetty.
      - Uses Blender SUBSURF + DISPLACE (Voronoi procedural texture) modifiers and multi-material
        zonation (TidalWetRock y = -3.0..1.8m, BasaltCliff steep faces, CoastalMoss flat upper shelves).
      - Winding 42-step stone staircase with crooked RustIron stanchions & sagging CURVE rope handrail.
    """
    objects: List[bpy.types.Object] = []

    crag_mesh = bpy.data.meshes.new("CoastalCrag_mesh")
    crag_obj = bpy.data.objects.new("CoastalCrag", crag_mesh)
    bpy.context.collection.objects.link(crag_obj)

    # Append the 3 cliff materials in slots 0, 1, 2
    crag_mesh.materials.append(mats["TidalWetRock"])
    crag_mesh.materials.append(mats["BasaltCliff"])
    crag_mesh.materials.append(mats["CoastalMoss"])

    num_rings = 72
    num_segments = 96
    bm = bmesh.new()
    grid_verts: List[List[bmesh.types.BMVert]] = []

    for r_idx in range(num_rings):
        u = float(r_idx) / float(num_rings - 1)
        ring_cx = 0.0
        ring_cz = 44.0 * (1.0 - u * 0.42) + 34.0 * (u * 0.42)

        ring: List[bmesh.types.BMVert] = []
        for s_idx in range(num_segments):
            theta = (2.0 * math.pi * float(s_idx)) / float(num_segments)
            dir_x = math.cos(theta)
            dir_z = math.sin(theta)

            # Sheltered crescent harbor cove on the -Z side
            cove_facing = max(0.0, -dir_z) * max(0.0, 1.0 - abs(dir_x) * 1.15)
            # Curved stone breakwater jetty on the port (-X, -Z) side
            jetty_align = max(0.0, math.cos((theta - 4.08) * 3.8))
            jetty_boost = (jetty_align ** 2.2) * 10.5 * math.sin(min(1.0, u * 1.25) * math.pi * 0.85)

            base_rad_x = 3.8 + u * (25.5 - cove_facing * 7.8 + jetty_boost * 0.75)
            base_rad_z = 3.8 + u * (23.2 - cove_facing * 10.8 + jetty_boost * 0.95)

            # Elevation profile from y = 10.8m at Lighthouse plateau down to y = -3.8m seafloor
            if u < 0.16:
                base_y = 10.80 - (u / 0.16) * 0.30
            else:
                u_slope = (u - 0.16) / 0.84
                if cove_facing > 0.22 and 0.30 <= u <= 0.70:
                    shelf_blend = math.sin(((u - 0.30) / 0.40) * math.pi) * min(1.0, cove_facing * 1.45)
                    cliff_h = 10.5 * ((1.0 - u_slope) ** 1.32) - 3.8 * (u_slope ** 1.48)
                    base_y = cliff_h * (1.0 - shelf_blend) + 1.92 * shelf_blend
                else:
                    base_y = 10.5 * ((1.0 - u_slope) ** 1.28) - 3.8 * (u_slope ** 1.45)

            if jetty_align > 0.35 and 0.45 < u < 0.90:
                jetty_y = 2.6 * (1.0 - (u - 0.45) / 0.48) * (jetty_align ** 1.6)
                base_y = max(base_y, jetty_y)

            sample_x = ring_cx + dir_x * base_rad_x
            sample_z = ring_cz + dir_z * base_rad_z
            n_val = ridge_noise(sample_x * 0.30, base_y * 0.42, sample_z * 0.30, 710)
            n_fine = ridge_noise(sample_x * 0.82, base_y * 1.05, sample_z * 0.82, 723)

            strata_step = math.sin(base_y * 2.75 + n_val * 0.85) * 0.22
            y_final = base_y + (strata_step + n_val * 0.38 + n_fine * 0.14) * math.sin(u * math.pi)

            # Wave-undercut tidal notch (y = -0.2m to 1.8m)
            undercut_inward = 0.0
            if -0.20 <= y_final <= 1.85 and u > 0.35:
                undercut_phase = (y_final + 0.20) / 2.05
                undercut_inward = 0.85 * math.sin(undercut_phase * math.pi) * (0.7 + 0.3 * abs(n_fine))
            elif 1.85 < y_final <= 2.65 and u > 0.35:
                undercut_inward = -0.28 * math.sin(((y_final - 1.85) / 0.80) * math.pi)

            rad_mod = 1.0 + (n_val * 0.075 + n_fine * 0.03) * min(1.0, u * 1.8)
            rx = max(0.3, base_rad_x * rad_mod - undercut_inward)
            rz = max(0.3, base_rad_z * rad_mod - undercut_inward)

            gx = ring_cx + dir_x * rx
            gz = ring_cz + dir_z * rz

            # Enforce strict 8.0m spawn clearance around origin (0, 0, 0) and pier front
            dist_origin = math.hypot(gx, gz)
            if dist_origin < 10.5:
                scale_push = 10.5 / max(dist_origin, 0.001)
                gx *= scale_push
                gz = max(gz * scale_push, 10.0)

            v = bm.verts.new(g2b((gx, y_final, gz)))
            ring.append(v)
        grid_verts.append(ring)

    # Cap summit center at (0.0, 10.8, 44.0)
    v_summit = bm.verts.new(g2b((0.0, 10.82, 44.0)))
    for s_idx in range(num_segments):
        ns = (s_idx + 1) % num_segments
        bm.faces.new((v_summit, grid_verts[0][ns], grid_verts[0][s_idx]))

    for r_idx in range(num_rings - 1):
        r0 = grid_verts[r_idx]
        r1 = grid_verts[r_idx + 1]
        for s_idx in range(num_segments):
            ns = (s_idx + 1) % num_segments
            bm.faces.new((r0[s_idx], r0[ns], r1[ns], r1[s_idx]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(crag_mesh)
    bm.free()

    # Create vertex group for DISPLACE modifier (protect flat Lighthouse summit & building shelves)
    vg = crag_obj.vertex_groups.new(name="RockDisplace")
    for idx, v in enumerate(crag_mesh.vertices):
        # v.co.z is Godot Y elevation; v.co.y is Godot Z
        elev = v.co.z
        dist_lh = math.hypot(v.co.x, v.co.y - 44.0)
        if dist_lh < 6.8 and elev > 9.6:
            weight = 0.05
        elif 1.4 <= elev <= 2.6 and 14.0 <= v.co.y <= 28.0 and abs(v.co.x) < 16.0:
            weight = 0.12
        else:
            weight = 0.65
        vg.add([idx], weight, "REPLACE")

    # Apply Blender SUBSURF + DISPLACE (Voronoi procedural texture) modifiers
    sub_mod = crag_obj.modifiers.new(name="SubsurfCrag", type="SUBSURF")
    sub_mod.levels = 1
    sub_mod.render_levels = 1

    voronoi_tex = bpy.data.textures.new(name="CoastalVoronoiTex", type="VORONOI")
    voronoi_tex.noise_scale = 3.5

    disp_mod = crag_obj.modifiers.new(name="DisplaceCrag", type="DISPLACE")
    disp_mod.texture = voronoi_tex
    disp_mod.texture_coords = "GLOBAL"
    disp_mod.strength = 0.42
    disp_mod.mid_level = 0.5
    disp_mod.vertex_group = "RockDisplace"

    apply_all_modifiers(crag_obj)

    # Assign TidalWetRock (0), BasaltCliff (1), and CoastalMoss (2) based on displaced elevation & slope
    for poly in crag_mesh.polygons:
        avg_y = poly.center.z  # Blender Z = Godot Y
        slope_up = poly.normal.z
        if avg_y <= 1.85:
            poly.material_index = 0  # TidalWetRock
        elif avg_y >= 5.2 and slope_up > 0.68:
            poly.material_index = 2  # CoastalMoss
        else:
            poly.material_index = 1  # BasaltCliff

    objects.append(crag_obj)

    # --- Curved Stone Breakwater Jetty Boulders on the Port (-X) side (outside 8m spawn circle) ---
    jetty_spires = [
        # (gx, gy, gz, rx, rz, height, seed)
        (-18.5, -3.0, 14.5, 4.0, 3.6, 6.2, 731),
        (-17.0, -3.0, 11.2, 3.6, 3.2, 5.8, 732),
        (-15.2, -3.0,  8.2, 3.3, 3.0, 5.3, 733),
        (-13.4, -3.0,  5.6, 3.0, 2.7, 4.8, 734),
        (-11.8, -3.0,  3.5, 2.6, 2.4, 4.3, 735),
    ]
    for jx, jy, jz, rx, rz, jh, jseed in jetty_spires:
        spire_mesh = bpy.data.meshes.new(f"JettySpire_{jseed}_mesh")
        spire_obj = bpy.data.objects.new(f"JettySpire_{jseed}", spire_mesh)
        bpy.context.collection.objects.link(spire_obj)
        spire_mesh.materials.append(mats["TidalWetRock"])
        spire_mesh.materials.append(mats["BasaltCliff"])

        bm_j = bmesh.new()
        bmesh.ops.create_cone(bm_j, cap_ends=True, cap_tris=True, segments=9, radius1=rx, radius2=rx * 0.28, depth=jh)
        for v in bm_j.verts:
            v.co.y *= (rz / max(rx, 0.01))
            n = ridge_noise(v.co.x + jx, v.co.z + jy, v.co.y + jz, jseed)
            v.co.x += n * 0.45
            v.co.y += n * 0.40
        bm_j.to_mesh(spire_mesh)
        bm_j.free()

        spire_obj.location = g2b((jx, jy + jh * 0.5, jz))
        for poly in spire_mesh.polygons:
            world_y = (jy + jh * 0.5) + poly.center.z
            poly.material_index = 0 if world_y <= 1.8 else 1
        objects.append(spire_obj)

    # --- Winding 42-Step Cliffside Stone Staircase with RustIron Stanchions & Rope Handrail ---
    num_steps = 42
    rng = random.Random(842)
    stanchion_tops: List[Vec3] = []

    def stair_curve(t: float) -> Vec3:
        sx = -3.2 * math.sin(t * math.pi * 1.15) - 4.8 * (t ** 1.3) * math.cos(t * math.pi * 0.45)
        sz = 21.6 + t * 18.4
        sy = 1.38 + t * (10.52 - 1.38) + 0.18 * math.sin(t * math.pi * 2.0)
        return (sx, sy, sz)

    for i in range(num_steps):
        t0 = float(i) / float(num_steps - 1)
        t1 = min(1.0, float(i + 1) / float(num_steps - 1))
        p_curr = stair_curve(t0)
        p_next = stair_curve(t1)
        dx = p_next[0] - p_curr[0]
        dz = p_next[2] - p_curr[2]
        yaw_deg = math.degrees(math.atan2(dx, dz))
        tilt_jitter = rng.uniform(-2.0, 2.0)

        objects.append(
            create_box_g(
                f"StairStep_{i}",
                (p_curr[0], p_curr[1] - 0.08, p_curr[2]),
                (1.65, 0.20, 0.54),
                mats["LighthouseStone"],
                yaw_deg=yaw_deg,
                roll_deg=tilt_jitter,
                bevel_width=0.015,
            )
        )
        objects.append(
            create_box_g(
                f"StairBase_{i}",
                (p_curr[0], p_curr[1] - 0.34, p_curr[2]),
                (1.75, 0.36, 0.60),
                mats["BasaltCliff"],
                yaw_deg=yaw_deg,
            )
        )

        if i % 3 == 0 or i == num_steps - 1:
            rad_yaw = math.radians(yaw_deg)
            out_x = -math.cos(rad_yaw) * 0.78
            out_z = math.sin(rad_yaw) * 0.78
            post_base: Vec3 = (p_curr[0] + out_x, p_curr[1] - 0.05, p_curr[2] + out_z)
            post_top: Vec3 = (
                post_base[0] + rng.uniform(-0.12, 0.06),
                post_base[1] + 0.92,
                post_base[2] + rng.uniform(-0.08, 0.08),
            )
            objects.append(create_cylinder_g(f"StairStanchion_{i}", post_base, post_top, 0.038, 0.032, mats["RustIron"], segments=8))
            objects.append(create_box_g(f"StairStanchionEye_{i}", post_top, (0.09, 0.09, 0.09), mats["RustIron"]))
            stanchion_tops.append(post_top)

    # Sagging rope handrail (CURVE spline) connecting stanchions
    handrail_pts: List[Vec3] = []
    for s_idx in range(len(stanchion_tops) - 1):
        seg_pts = catenary_points_g(stanchion_tops[s_idx], stanchion_tops[s_idx + 1], sag=0.14, steps=6)
        if s_idx > 0:
            seg_pts = seg_pts[1:]
        handrail_pts.extend(seg_pts)
    objects.append(create_curve_g("StairRopeHandrail", handrail_pts, bevel_depth=0.028, mat=mats["WeatheredTimber"], resolution_u=6))

    return objects


# ---------------------------------------------------------------------------
# 2. Multi-Level Timber Wharf, Slipway, Wrecked Rowboat & Dockside Clutter
# ---------------------------------------------------------------------------

def build_wharf_pier_and_clutter(mats: Dict[str, bpy.types.Material]) -> Tuple[List[bpy.types.Object], List[Vec3]]:
    """
    Builds:
      - 98 individual beveled wooden deck planks (WeatheredTimber) with 2cm gaps & subtle tilt/warp
      - Heavy stringer beams, cap-beams, diagonal cross-bracing, barnacle-collared pilings (-4.0m to 2.1m)
      - Lower boat-landing stage (y = 0.65m) with 5-step wooden stair flight
      - Rotting timber boat slipway at (x = -14.5m, z = 12.0m) with a half-sunken broken-ribbed rowboat
      - Cast-iron bollards with 3D spiral rope coils, slatted lobster traps, banded barrels, dented oil drums,
        pier-edge timber jib-crane with hanging chain, and 4 crooked timber lamp posts at
        (-7.5, 1.35, 5.0), (7.5, 1.35, 5.0), (-7.5, 1.35, 14.0), and (7.5, 1.35, 18.0).
    """
    objects: List[bpy.types.Object] = []
    rng = random.Random(777)

    # Longitudinal stringer beams (z = +4.0m to +22.0m)
    for sx in (-7.4, -3.7, 0.0, 3.7, 7.4):
        objects.append(create_box_g(f"PierStringer_{sx:.1f}", (sx, 1.16, 13.0), (0.30, 0.28, 18.2), mats["WeatheredTimber"], bevel_width=0.01))

    # Transverse cap-beams atop piling rows
    piling_z_rows = [4.5, 8.8, 13.2, 17.6, 21.5]
    for pz in piling_z_rows:
        objects.append(create_box_g(f"PierCapBeam_{pz:.1f}", (0.0, 0.96, pz), (16.4, 0.26, 0.32), mats["RottingWood"], bevel_width=0.01))

    # 80 Individual Beveled Wooden Deck Planks on Main Pier (40 rows x 2 staggered bays) with 2cm gaps
    num_main_rows = 40
    plank_z_start = 4.08
    plank_z_end = 21.92
    plank_pitch = (plank_z_end - plank_z_start) / float(num_main_rows)
    plank_depth = plank_pitch - 0.02  # Exact 2cm gap

    for r_i in range(num_main_rows):
        pz = plank_z_start + (float(r_i) + 0.5) * plank_pitch
        split_x = 0.65 if (r_i % 2 == 0) else -0.65
        left_w = (8.0 + split_x) - 0.01
        right_w = (8.0 - split_x) - 0.01
        left_cx = -8.0 + left_w * 0.5
        right_cx = 8.0 - right_w * 0.5

        objects.append(
            create_box_g(
                f"PierPlankL_{r_i}",
                (left_cx, 1.35 + rng.uniform(-0.016, 0.016), pz),
                (left_w, 0.11, plank_depth),
                mats["WeatheredTimber"],
                pitch_deg=rng.uniform(-1.1, 1.1),
                roll_deg=rng.uniform(-0.7, 0.7),
                bevel_width=0.008,
            )
        )
        objects.append(
            create_box_g(
                f"PierPlankR_{r_i}",
                (right_cx, 1.35 + rng.uniform(-0.016, 0.016), pz),
                (right_w, 0.11, plank_depth),
                mats["WeatheredTimber"],
                pitch_deg=rng.uniform(-1.1, 1.1),
                roll_deg=rng.uniform(-0.7, 0.7),
                bevel_width=0.008,
            )
        )

    # Lower Boat-Landing Stage at y = 0.65m (18 more individual beveled planks -> 98 planks total)
    objects.append(create_box_g("StageBeam_In", (8.3, 0.50, 9.6), (0.24, 0.22, 8.0), mats["WeatheredTimber"]))
    objects.append(create_box_g("StageBeam_Out", (11.1, 0.50, 9.6), (0.24, 0.22, 8.0), mats["WeatheredTimber"]))
    num_stage_planks = 18
    stage_z0, stage_z1 = 5.65, 11.85
    stage_pitch = (stage_z1 - stage_z0) / float(num_stage_planks)
    for s_i in range(num_stage_planks):
        spz = stage_z0 + (float(s_i) + 0.5) * stage_pitch
        objects.append(
            create_box_g(
                f"StagePlank_{s_i}",
                (9.7, 0.65 + rng.uniform(-0.012, 0.012), spz),
                (3.3, 0.09, stage_pitch - 0.02),
                mats["WeatheredTimber"],
                roll_deg=rng.uniform(-1.0, 1.0),
                bevel_width=0.006,
            )
        )

    # 5-step stair flight from main pier (y = 1.35m) to landing stage (y = 0.65m)
    objects.append(create_cylinder_g("StageStairStrL", (8.2, 1.35, 13.6), (8.2, 0.65, 11.85), 0.08, 0.08, mats["WeatheredTimber"], segments=6))
    objects.append(create_cylinder_g("StageStairStrR", (10.8, 1.35, 13.6), (10.8, 0.65, 11.85), 0.08, 0.08, mats["WeatheredTimber"], segments=6))
    for st_i in range(5):
        st_frac = (float(st_i) + 0.5) / 5.0
        objects.append(
            create_box_g(
                f"StageStairStep_{st_i}",
                (9.5, 1.35 - st_frac * 0.70, 13.55 - st_frac * 1.65),
                (2.5, 0.07, 0.30),
                mats["WeatheredTimber"],
                bevel_width=0.005,
            )
        )

    # Helper for Barnacle-Collared Pilings
    def add_piling(name: str, px: float, pz: float, bot_y: float, top_y: float, radius: float = 0.24) -> None:
        lx = rng.uniform(-0.07, 0.07)
        lz = rng.uniform(-0.07, 0.07)
        objects.append(create_cylinder_g(name, (px, bot_y, pz), (px + lx, top_y, pz + lz), radius, radius * 0.88, mats["WeatheredTimber"], segments=10))
        frac_mid = (0.2 - bot_y) / max(0.1, top_y - bot_y)
        cx_m = px + lx * frac_mid
        cz_m = pz + lz * frac_mid
        objects.append(create_cylinder_g(name + "_BarnacleBot", (cx_m, -0.50, cz_m), (cx_m, 0.22, cz_m), radius * 1.10, radius * 1.40, mats["TidalWetRock"], segments=9))
        objects.append(create_cylinder_g(name + "_BarnacleTop", (cx_m, 0.22, cz_m), (cx_m, 0.90, cz_m), radius * 1.40, radius * 1.05, mats["TidalWetRock"], segments=9))

    piling_x_cols = [-7.8, -2.6, 2.6, 7.8]
    for pz in piling_z_rows:
        for px in piling_x_cols:
            top_y = 2.15 if abs(px) > 7.0 else 1.30
            add_piling(f"Piling_{px:.1f}_{pz:.1f}", px, pz, -4.0, top_y, radius=0.24)
        # Diagonal X-bracing
        objects.append(create_cylinder_g(f"XBrace1_{pz}", (-7.8, -0.35, pz), (-2.6, 1.12, pz), 0.09, 0.09, mats["RottingWood"], segments=6))
        objects.append(create_cylinder_g(f"XBrace2_{pz}", (-7.8, 1.12, pz), (-2.6, -0.35, pz), 0.09, 0.09, mats["RottingWood"], segments=6))
        objects.append(create_cylinder_g(f"XBrace3_{pz}", (-2.6, -0.35, pz), (2.6, 1.12, pz), 0.09, 0.09, mats["RottingWood"], segments=6))
        objects.append(create_cylinder_g(f"XBrace4_{pz}", (2.6, -0.35, pz), (7.8, 1.12, pz), 0.09, 0.09, mats["RottingWood"], segments=6))
        objects.append(create_cylinder_g(f"XBrace5_{pz}", (2.6, 1.12, pz), (7.8, -0.35, pz), 0.09, 0.09, mats["RottingWood"], segments=6))

    for lpz in (5.8, 9.6, 13.4):
        add_piling(f"StagePiling_{lpz}", 11.2, lpz, -3.8, 1.45, radius=0.20)
        objects.append(create_cylinder_g(f"StageBrace_{lpz}", (7.8, -0.2, lpz), (11.2, 0.55, lpz), 0.08, 0.08, mats["RottingWood"], segments=6))

    # --- Rotting Timber Boat Slipway & Half-Sunken Broken-Ribbed Rowboat at (x = -14.5m, z = 12.0m) ---
    for rail_x in (-15.6, -13.4):
        objects.append(create_cylinder_g(f"SlipwayRail_{rail_x}", (rail_x, 1.52, 16.8), (rail_x, -0.75, 7.2), 0.14, 0.13, mats["WeatheredTimber"], segments=8))
        add_piling(f"SlipwayPilingA_{rail_x}", rail_x, 11.8, -3.6, 0.45, radius=0.17)
        add_piling(f"SlipwayPilingB_{rail_x}", rail_x, 8.4, -3.6, -0.25, radius=0.17)
    for sl_i in range(18):
        sl_t = float(sl_i) / 17.0
        sl_y = 1.55 - sl_t * (1.55 - (-0.70))
        sl_z = 16.6 - sl_t * (16.6 - 7.4)
        objects.append(create_box_g(f"SlipwayTie_{sl_i}", (-14.5, sl_y, sl_z), (2.65, 0.10, 0.24), mats["RottingWood"], pitch_deg=-13.2, bevel_width=0.005))

    # Half-sunken broken-ribbed wooden rowboat resting in the shallows at (-14.5, 0.08, 10.6)
    skiff_cx, skiff_cy, skiff_cz = -14.5, 0.08, 10.6
    yr = math.radians(14.0)
    rr = math.radians(19.5)
    cyaw, syaw = math.cos(yr), math.sin(yr)
    crol, srol = math.cos(rr), math.sin(rr)

    def skiff_pt(lx: float, ly: float, lz: float) -> Vec3:
        rx = lx * crol - ly * srol
        ry = lx * srol + ly * crol
        wx = rx * cyaw + lz * syaw
        wz = -rx * syaw + lz * cyaw
        return (skiff_cx + wx, skiff_cy + ry, skiff_cz + wz)

    objects.append(create_cylinder_g("SkiffKeel", skiff_pt(0.0, -0.25, -2.3), skiff_pt(0.0, -0.32, 2.1), 0.09, 0.09, mats["RottingWood"], segments=8))
    objects.append(create_cylinder_g("SkiffStem", skiff_pt(0.0, -0.25, -2.3), skiff_pt(0.0, 0.58, -2.75), 0.09, 0.07, mats["RottingWood"], segments=8))
    for idx, rz in enumerate((-1.85, -1.30, -0.75, -0.20, 0.35, 0.90, 1.45, 1.95)):
        beam_f = math.cos((rz / 2.45) * (math.pi * 0.46))
        half_w = max(0.32, 1.08 * beam_f)
        p_top = 0.48 if (idx % 3 != 1) else 0.18
        s_top = 0.46 if (idx % 2 == 0) else 0.24
        pk = skiff_pt(0.0, -0.26, rz)
        ppb = skiff_pt(-half_w * 0.72, -0.08, rz)
        ppg = skiff_pt(-half_w, p_top, rz)
        psb = skiff_pt(half_w * 0.72, -0.08, rz)
        psg = skiff_pt(half_w, s_top, rz)
        objects.append(create_cylinder_g(f"SkiffRibPL_{idx}", pk, ppb, 0.045, 0.045, mats["RottingWood"], segments=6))
        objects.append(create_cylinder_g(f"SkiffRibPU_{idx}", ppb, ppg, 0.045, 0.038, mats["RottingWood"], segments=6))
        objects.append(create_cylinder_g(f"SkiffRibSL_{idx}", pk, psb, 0.045, 0.045, mats["RottingWood"], segments=6))
        objects.append(create_cylinder_g(f"SkiffRibSU_{idx}", psb, psg, 0.045, 0.038, mats["RottingWood"], segments=6))

    for side_s in (-1.0, 1.0):
        for sh_idx, strake_h in enumerate((-0.02, 0.18, 0.36)):
            for seg in range(5):
                if seg == 2 and strake_h > 0.1 and side_s < 0.0:
                    continue
                z0 = -2.1 + float(seg) * 0.82
                z1 = z0 + 0.76
                w0 = max(0.22, 1.05 * math.cos((z0 / 2.5) * (math.pi * 0.46))) * side_s
                w1 = max(0.22, 1.05 * math.cos((z1 / 2.5) * (math.pi * 0.46))) * side_s
                objects.append(
                    create_cylinder_g(
                        f"SkiffPlank_{side_s:.0f}_{sh_idx}_{seg}",
                        skiff_pt(w0, strake_h, z0),
                        skiff_pt(w1, strake_h, z1),
                        0.042,
                        0.042,
                        mats["WeatheredTimber"],
                        segments=6,
                    )
                )

    # --- Cast-Iron Mooring Bollards + 3D Spiral Rope Coils (CURVE bevel objects) ---
    bollard_coords = [
        (-6.2, 4.4), (-2.0, 4.4), (2.0, 4.4), (6.2, 4.4),
        (-7.4, 10.5), (7.4, 10.5), (-7.4, 16.0), (7.4, 16.0),
    ]
    for b_idx, (bx, bz) in enumerate(bollard_coords):
        objects.append(create_cylinder_g(f"BollardPost_{b_idx}", (bx, 1.38, bz), (bx, 1.86, bz), 0.16, 0.19, mats["RustIron"], segments=12))
        objects.append(create_box_g(f"BollardCross_{b_idx}", (bx, 1.72, bz), (0.52, 0.08, 0.10), mats["RustIron"], bevel_width=0.008))

        # 3D Spiral Rope Coil resting on deck beside bollard
        spiral_pts: List[Vec3] = []
        turns = 3.5
        steps = 48
        cx_coil, cz_coil = bx + (0.38 if bx < 0.0 else -0.38), bz + 0.25
        for s in range(steps + 1):
            t = s / float(steps)
            ang = t * turns * 2.0 * math.pi
            rad = 0.06 + t * 0.24
            gy = 1.42 + (1.0 - t) * 0.05
            spiral_pts.append((cx_coil + math.cos(ang) * rad, gy, cz_coil + math.sin(ang) * rad))
        objects.append(create_curve_g(f"BollardRopeCoil_{b_idx}", spiral_pts, bevel_depth=0.022, mat=mats["WeatheredTimber"], resolution_u=6))

    # --- Timber Jib-Crane with Hanging Iron Chain at Pier Edge (-5.8, 1.38, 5.2) ---
    cbx, cby, cbz = -5.8, 1.38, 5.2
    mast_top: Vec3 = (cbx, cby + 3.85, cbz)
    boom_tip: Vec3 = (cbx - 1.65, cby + 3.35, cbz - 1.45)
    objects.append(create_cylinder_g("CraneCollar", (cbx, cby, cbz), (cbx, cby + 0.45, cbz), 0.24, 0.22, mats["RustIron"], segments=10))
    objects.append(create_cylinder_g("CraneKingPost", (cbx, cby + 0.40, cbz), mast_top, 0.18, 0.15, mats["WeatheredTimber"], segments=10))
    objects.append(create_cylinder_g("CraneJibBoom", (cbx, cby + 1.15, cbz), boom_tip, 0.13, 0.10, mats["WeatheredTimber"], segments=8))
    objects.append(create_cylinder_g("CraneTieRod", (cbx, cby + 3.70, cbz), boom_tip, 0.032, 0.032, mats["DarkMetal"], segments=8))
    objects.append(create_cylinder_g("CraneWinchDrum", (cbx - 0.28, cby + 0.95, cbz), (cbx + 0.28, cby + 0.95, cbz), 0.16, 0.16, mats["RustIron"], segments=10))
    # Hanging chain links & hook
    for lk in range(12):
        ly = boom_tip[1] - 0.12 - lk * 0.18
        rot_z = math.radians(90.0) if (lk % 2 == 0) else 0.0
        objects.append(
            create_torus_g(
                f"CraneChainLink_{lk}",
                (boom_tip[0], ly, boom_tip[2]),
                major_radius=0.065,
                minor_radius=0.018,
                mat=mats["DarkMetal"],
                rot_blender=(math.radians(90.0), 0.0, rot_z),
                major_segments=12,
                minor_segments=6,
            )
        )
    hook_y = boom_tip[1] - 0.12 - 12 * 0.18
    objects.append(create_box_g("CranePulleyBlock", (boom_tip[0], hook_y, boom_tip[2]), (0.20, 0.24, 0.14), mats["RustIron"], bevel_width=0.01))

    # --- Slatted Wooden Lobster Traps, Banded Barrels & Dented Oil Drums ---
    lobster_placements = [
        ((-5.4, 1.40, 11.4), 12.0),
        ((-5.3, 1.82, 11.4), -8.0),
        ((-4.2, 1.40, 11.6), 28.0),
        ((5.8, 1.40, 14.8), -18.0),
        ((5.8, 1.82, 14.8), 6.0),
        ((-8.8, 1.62, 15.8), 35.0),
        ((9.6, 0.70, 7.4), -14.0),
    ]
    for l_idx, (l_pos, l_yaw) in enumerate(lobster_placements):
        lx, ly, lz = l_pos
        objects.append(create_box_g(f"LobsterTrapFrame_{l_idx}", (lx, ly + 0.20, lz), (0.88, 0.38, 0.56), mats["WeatheredTimber"], yaw_deg=l_yaw, bevel_width=0.01))
        objects.append(create_box_g(f"LobsterTrapSkid_{l_idx}", (lx, ly + 0.03, lz), (0.96, 0.05, 0.62), mats["RottingWood"], yaw_deg=l_yaw))

    barrel_placements = [
        ((-0.2, 1.38, 20.2), 2.0),
        ((0.55, 1.38, 20.4), -3.5),
        ((3.8, 1.38, 20.3), 1.5),
        ((6.2, 1.38, 16.2), 4.0),
        ((-6.4, 1.38, 15.0), -2.5),
        ((10.2, 0.68, 9.2), 3.0),
    ]
    for b_idx, (b_pos, b_tilt) in enumerate(barrel_placements):
        bx, by, bz = b_pos
        dx = math.sin(math.radians(b_tilt)) * 0.82
        p0: Vec3 = (bx, by, bz)
        p_mid: Vec3 = (bx + dx * 0.5, by + 0.41, bz)
        p1: Vec3 = (bx + dx, by + 0.82, bz)
        objects.append(create_cylinder_g(f"BarrelBot_{b_idx}", p0, p_mid, 0.27, 0.32, mats["WeatheredTimber"], segments=12))
        objects.append(create_cylinder_g(f"BarrelTop_{b_idx}", p_mid, p1, 0.32, 0.27, mats["WeatheredTimber"], segments=12))
        objects.append(create_cylinder_g(f"BarrelHoop1_{b_idx}", (bx + dx * 0.22, by + 0.18, bz), (bx + dx * 0.25, by + 0.24, bz), 0.31, 0.31, mats["RustIron"], segments=12))
        objects.append(create_cylinder_g(f"BarrelHoop2_{b_idx}", (bx + dx * 0.75, by + 0.62, bz), (bx + dx * 0.78, by + 0.68, bz), 0.31, 0.31, mats["RustIron"], segments=12))

    drum_placements = [
        ((-6.5, 1.38, 18.8), False, 0.0),
        ((-5.7, 1.38, 19.1), False, 0.0),
        ((-5.0, 1.38, 18.6), True, 24.0),
        ((6.4, 1.38, 8.2), False, 0.0),
        ((6.1, 1.38, 9.1), True, -32.0),
    ]
    for d_idx, (d_pos, on_side, d_yaw) in enumerate(drum_placements):
        dx, dy, dz = d_pos
        if not on_side:
            objects.append(create_cylinder_g(f"OilDrum_{d_idx}", (dx, dy, dz), (dx + 0.03, dy + 0.88, dz - 0.02), 0.29, 0.28, mats["RustIron"], segments=12))
            objects.append(create_cylinder_g(f"OilDrumRib1_{d_idx}", (dx + 0.01, dy + 0.28, dz), (dx + 0.01, dy + 0.33, dz), 0.305, 0.305, mats["DarkMetal"], segments=12))
            objects.append(create_cylinder_g(f"OilDrumRib2_{d_idx}", (dx + 0.02, dy + 0.58, dz), (dx + 0.02, dy + 0.63, dz), 0.305, 0.305, mats["DarkMetal"], segments=12))
        else:
            yr_d = math.radians(d_yaw)
            ox, oz = math.cos(yr_d) * 0.44, math.sin(yr_d) * 0.44
            objects.append(create_cylinder_g(f"OilDrumSide_{d_idx}", (dx - ox, dy + 0.29, dz - oz), (dx + ox, dy + 0.29, dz + oz), 0.29, 0.28, mats["RustIron"], segments=12))

    # --- 4 Crooked Timber Lamp Posts at (-7.5, 1.35, 5.0), (7.5, 1.35, 5.0), (-7.5, 1.35, 14.0), (7.5, 1.35, 18.0) ---
    lamp_specs = [
        (-7.5, 5.0,  0.22, -0.15),
        ( 7.5, 5.0, -0.22, -0.15),
        (-7.5, 14.0, 0.25,  0.12),
        ( 7.5, 18.0, -0.24, 0.14),
    ]
    lamp_post_tops: List[Vec3] = []
    for l_idx, (lx, lz, tx, tz) in enumerate(lamp_specs):
        post_base: Vec3 = (lx, 1.35, lz)
        post_top: Vec3 = (lx + tx, 4.55, lz + tz)
        lamp_post_tops.append(post_top)
        arm_tip: Vec3 = (lx + tx + (0.65 if lx < 0.0 else -0.65), 4.50, lz + tz)
        lantern_top: Vec3 = (arm_tip[0], 4.38, arm_tip[2])
        lantern_bot: Vec3 = (arm_tip[0], 4.00, arm_tip[2])  # Centered at y = 4.2m!

        objects.append(create_cylinder_g(f"LampPost_{l_idx}", post_base, post_top, 0.13, 0.09, mats["WeatheredTimber"], segments=10))
        objects.append(create_cylinder_g(f"LampArm_{l_idx}", post_top, arm_tip, 0.07, 0.06, mats["WeatheredTimber"], segments=8))
        objects.append(create_cylinder_g(f"LampBrace_{l_idx}", (lx + tx * 0.7, 3.85, lz + tz * 0.7), (arm_tip[0] * 0.5 + (lx + tx) * 0.5, 4.50, arm_tip[2]), 0.045, 0.045, mats["WeatheredTimber"], segments=6))
        objects.append(create_cylinder_g(f"LanternHood_{l_idx}", arm_tip, lantern_top, 0.04, 0.16, mats["RustIron"], segments=10))
        objects.append(create_cylinder_g(f"LanternGlass_{l_idx}", lantern_top, lantern_bot, 0.13, 0.10, mats["AmberGlass"], segments=10))
        objects.append(create_cylinder_g(f"LanternBase_{l_idx}", lantern_bot, (arm_tip[0], 3.93, arm_tip[2]), 0.11, 0.05, mats["RustIron"], segments=10))

    return objects, lamp_post_tops


# ---------------------------------------------------------------------------
# 3. Three Slumped, Run-Down Harbor Buildings (Boolean Windows, Clapboard & Sagging Roofs)
# ---------------------------------------------------------------------------

def build_slumped_building(
    name: str,
    center_g: Vec3,
    width: float,
    height: float,
    depth: float,
    wall_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    roof_mat: bpy.types.Material,
    mats: Dict[str, bpy.types.Material],
    lean_x_deg: float,
    lean_z_deg: float,
    roof_sag: float,
    window_front_count: int = 2,
    add_rear_window: bool = True,
    seed: int = 100,
) -> List[bpy.types.Object]:
    """
    Constructs a slumped, weathered harbor building with:
      - Overlapping horizontal clapboard siding
      - Blender BOOLEAN (DIFFERENCE) carved recessed window openings
      - Internal AmberGlass emissive panes & 3D wooden mullions + crooked storm shutters
      - Vertex-warped sagging CorrugatedRoof panels, exposed rafter tails, and sagging rain gutters
    """
    objs: List[bpy.types.Object] = []
    rng = random.Random(seed)
    cx, by, cz = center_g
    hx = width * 0.5
    hz = depth * 0.5
    tan_lx = math.tan(math.radians(lean_x_deg))
    tan_lz = math.tan(math.radians(lean_z_deg))
    lean_dx_top = height * tan_lx
    lean_dz_top = height * tan_lz
    ty = by + height
    gable_h = height * 0.42

    # 1. Solid Structural Wall Core carved with BOOLEAN DIFFERENCE window cutouts
    core_mesh = bpy.data.meshes.new(f"{name}_WallCore_mesh")
    core_obj = bpy.data.objects.new(f"{name}_WallCore", core_mesh)
    bpy.context.collection.objects.link(core_obj)
    assign_material(core_obj, wall_mat)

    bm = bmesh.new()
    # 8 corners + 2 gable peaks
    v_b_fl = bm.verts.new(g2b((cx - hx, by, cz - hz)))
    v_b_fr = bm.verts.new(g2b((cx + hx, by, cz - hz)))
    v_b_br = bm.verts.new(g2b((cx + hx, by, cz + hz)))
    v_b_bl = bm.verts.new(g2b((cx - hx, by, cz + hz)))

    v_t_fl = bm.verts.new(g2b((cx - hx + lean_dx_top, ty, cz - hz + lean_dz_top)))
    v_t_fr = bm.verts.new(g2b((cx + hx + lean_dx_top, ty, cz - hz + lean_dz_top)))
    v_t_br = bm.verts.new(g2b((cx + hx + lean_dx_top, ty, cz + hz + lean_dz_top)))
    v_t_bl = bm.verts.new(g2b((cx - hx + lean_dx_top, ty, cz + hz + lean_dz_top)))

    v_g_l = bm.verts.new(g2b((cx - hx + lean_dx_top, ty + gable_h, cz + lean_dz_top)))
    v_g_r = bm.verts.new(g2b((cx + hx + lean_dx_top, ty + gable_h, cz + lean_dz_top)))

    bm.faces.new((v_b_fl, v_b_fr, v_t_fr, v_t_fl))
    bm.faces.new((v_b_fr, v_b_br, v_t_br, v_t_fr))
    bm.faces.new((v_b_br, v_b_bl, v_t_bl, v_t_br))
    bm.faces.new((v_b_bl, v_b_fl, v_t_fl, v_t_bl))
    bm.faces.new((v_b_bl, v_b_br, v_b_fr, v_b_fl))
    # Gable walls & roof slopes
    bm.faces.new((v_t_bl, v_t_fl, v_g_l))
    bm.faces.new((v_t_fr, v_t_br, v_g_r))
    bm.faces.new((v_t_fl, v_t_fr, v_g_r, v_g_l))
    bm.faces.new((v_t_br, v_t_bl, v_g_l, v_g_r))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(core_mesh)
    bm.free()

    # Overlapping Horizontal Clapboard Siding Strips (10 courses)
    courses = 10
    course_h = height / float(courses)
    for c_idx in range(courses):
        y_c = by + (float(c_idx) + 0.5) * course_h
        frac_c = (y_c - by) / height
        dx_c = frac_c * lean_dx_top
        dz_c = frac_c * lean_dz_top
        objs.append(
            create_box_g(
                f"{name}_Clapboard_{c_idx}",
                (cx + dx_c, y_c, cz + dz_c),
                (width + 0.06, course_h * 0.92, depth + 0.06),
                wall_mat,
                pitch_deg=3.0,
            )
        )

    # Boolean Window Cutters + Internal Emissive AmberGlass Panes + 3D Mullions
    win_w = min(1.10, (width * 0.54) / float(max(1, window_front_count)))
    win_h = min(1.15, height * 0.36)
    win_y = by + height * 0.54
    frac_wy = (win_y - by) / height
    win_z_front = cz - hz + lean_dz_top * frac_wy

    cutters: List[bpy.types.Object] = []

    def add_boolean_window(w_tag: str, wx: float, wy: float, wz: float, normal_z: float) -> None:
        # Boolean cutter box carving 18cm into the wall
        cutter = create_box_g(
            f"{name}_Cutter_{w_tag}",
            (wx, wy, wz - normal_z * 0.05),
            (win_w, win_h, 0.28),
            mats["DarkMetal"],
        )
        cutters.append(cutter)

        # Recessed glowing AmberGlass pane inside the boolean cutout
        glass_z = wz - normal_z * 0.09
        objs.append(
            create_box_g(
                f"{name}_Glass_{w_tag}",
                (wx, wy, glass_z),
                (win_w * 0.94, win_h * 0.94, 0.04),
                mats["AmberGlass"],
            )
        )
        # Window casing jambs, lintel & sill
        objs.append(create_box_g(f"{name}_Lintel_{w_tag}", (wx, wy + win_h * 0.5 + 0.04, wz + normal_z * 0.04), (win_w + 0.22, 0.09, 0.16), trim_mat, bevel_width=0.008))
        objs.append(create_box_g(f"{name}_Sill_{w_tag}", (wx, wy - win_h * 0.5 - 0.04, wz + normal_z * 0.05), (win_w + 0.26, 0.08, 0.18), trim_mat, bevel_width=0.008))
        # 3D Wooden Mullion Crossbars
        mullion_z = glass_z + normal_z * 0.03
        for vx_off in (-win_w * 0.17, win_w * 0.17):
            objs.append(create_box_g(f"{name}_VMullion_{w_tag}_{vx_off:.2f}", (wx + vx_off, wy, mullion_z), (0.035, win_h, 0.045), mats["RottingWood"]))
        for vy_off in (-win_h * 0.17, win_h * 0.17):
            objs.append(create_box_g(f"{name}_HMullion_{w_tag}_{vy_off:.2f}", (wx, wy + vy_off, mullion_z), (win_w, 0.035, 0.045), mats["RottingWood"]))

        # Crooked exterior storm shutters
        shutter_w = win_w * 0.44
        shutter_z = wz + normal_z * 0.05
        objs.append(
            create_box_g(
                f"{name}_ShutterL_{w_tag}",
                (wx - win_w * 0.5 - shutter_w * 0.55, wy, shutter_z),
                (shutter_w, win_h * 0.95, 0.045),
                mats["RottingWood"],
                yaw_deg=10.0 * normal_z,
                roll_deg=rng.uniform(6.0, 14.0),
            )
        )
        objs.append(
            create_box_g(
                f"{name}_ShutterR_{w_tag}",
                (wx + win_w * 0.5 + shutter_w * 0.55, wy - 0.02, shutter_z),
                (shutter_w, win_h * 0.95, 0.045),
                mats["RottingWood"],
                yaw_deg=-12.0 * normal_z,
                roll_deg=rng.uniform(-15.0, -6.0),
            )
        )

    for w_idx in range(window_front_count):
        span_frac = (float(w_idx) + 0.5) / float(window_front_count) - 0.5
        wx_c = cx + span_frac * (width * 0.62) + lean_dx_top * frac_wy
        add_boolean_window(f"Front_{w_idx}", wx_c, win_y, win_z_front, -1.0)

    if add_rear_window:
        win_z_back = cz + hz + lean_dz_top * frac_wy
        add_boolean_window("Rear_0", cx + lean_dx_top * frac_wy, win_y, win_z_back, 1.0)

    if cutters:
        bpy.ops.object.select_all(action="DESELECT")
        for c_obj in cutters:
            c_obj.select_set(True)
        bpy.context.view_layer.objects.active = cutters[0]
        bpy.ops.object.join()
        joined_cutter = bpy.context.active_object

        bool_mod = core_obj.modifiers.new(name="WinBool", type="BOOLEAN")
        bool_mod.operation = "DIFFERENCE"
        bool_mod.object = joined_cutter
        bool_mod.solver = "EXACT"
        apply_all_modifiers(core_obj)
        bpy.data.objects.remove(joined_cutter, do_unlink=True)

    objs.append(core_obj)

    # Corner Trim Posts & Exposed Roof Rafters
    for sx_s in (-1.0, 1.0):
        for sz_s in (-1.0, 1.0):
            p_bot: Vec3 = (cx + sx_s * hx, by - 0.15, cz + sz_s * hz)
            p_top: Vec3 = (cx + sx_s * hx + lean_dx_top, ty + 0.05, cz + sz_s * hz + lean_dz_top)
            objs.append(create_cylinder_g(f"{name}_CornerPost_{sx_s}_{sz_s}", p_bot, p_top, 0.12, 0.11, trim_mat, segments=6))

    eave_ox, eave_oz = 0.38, 0.48
    for r_i in range(8):
        ru = float(r_i) / 7.0
        rx_p = (cx - hx) + ru * width + lean_dx_top
        sag_r = math.sin(ru * math.pi) * roof_sag
        ry_r = ty + gable_h - sag_r
        ey_e = ty - 0.12 - sag_r * 0.42
        zf_e = cz - hz - eave_oz + lean_dz_top
        zb_e = cz + hz + eave_oz + lean_dz_top
        zr = cz + lean_dz_top
        objs.append(create_cylinder_g(f"{name}_RafterF_{r_i}", (rx_p, ry_r - 0.04, zr), (rx_p, ey_e - 0.04, zf_e), 0.05, 0.045, trim_mat, segments=6))
        objs.append(create_cylinder_g(f"{name}_RafterB_{r_i}", (rx_p, ry_r - 0.04, zr), (rx_p, ey_e - 0.04, zb_e), 0.05, 0.045, trim_mat, segments=6))

    # Vertex-warped Sagging CorrugatedRoof Mesh
    roof_mesh = bpy.data.meshes.new(f"{name}_SaggingRoof_mesh")
    roof_obj = bpy.data.objects.new(f"{name}_SaggingRoof", roof_mesh)
    bpy.context.collection.objects.link(roof_obj)
    assign_material(roof_obj, roof_mat)

    bm_r = bmesh.new()
    cols = 10
    total_rw = width + 2.0 * eave_ox
    zf_e = cz - hz - eave_oz + lean_dz_top
    zb_e = cz + hz + eave_oz + lean_dz_top
    zr = cz + lean_dz_top

    r_strips: List[Tuple[bmesh.types.BMVert, bmesh.types.BMVert, bmesh.types.BMVert]] = []
    for c_i in range(cols + 1):
        u = float(c_i) / float(cols)
        x_p = (cx - hx - eave_ox) + u * total_rw + lean_dx_top
        sag_u = math.sin(u * math.pi) * roof_sag
        corrugation = 0.035 * math.sin(u * math.pi * 16.0)
        ry_u = ty + gable_h - sag_u + corrugation
        ey_u = ty - 0.08 - sag_u * 0.42 + corrugation
        v_f = bm_r.verts.new(g2b((x_p, ey_u, zf_e)))
        v_m = bm_r.verts.new(g2b((x_p, ry_u, zr)))
        v_b = bm_r.verts.new(g2b((x_p, ey_u, zb_e)))
        r_strips.append((v_f, v_m, v_b))

    for c_i in range(cols):
        s0 = r_strips[c_i]
        s1 = r_strips[c_i + 1]
        bm_r.faces.new((s0[0], s1[0], s1[1], s0[1]))
        bm_r.faces.new((s0[1], s1[1], s1[2], s0[2]))

    bmesh.ops.recalc_face_normals(bm_r, faces=bm_r.faces)
    bm_r.to_mesh(roof_mesh)
    bm_r.free()

    sol_r = roof_obj.modifiers.new(name="SolidifyRoof", type="SOLIDIFY")
    sol_r.thickness = 0.06
    apply_all_modifiers(roof_obj)
    objs.append(roof_obj)

    # Sagging Rain Gutters (CURVE splines)
    zf_g = zf_e - 0.05
    gutter_pts = catenary_points_g(
        (cx - hx - eave_ox + lean_dx_top, ty - 0.16, zf_g),
        (cx + hx + eave_ox + lean_dx_top, ty - 0.22, zf_g),
        sag=roof_sag * 0.55 + 0.08,
        steps=8,
    )
    objs.append(create_curve_g(f"{name}_FrontGutter", gutter_pts, bevel_depth=0.05, mat=mats["RustIron"], resolution_u=6))

    return objs


def build_harbor_buildings(mats: Dict[str, bpy.types.Material]) -> List[bpy.types.Object]:
    """
    Constructs the 3 slumped, run-down harbor buildings:
      1. Building 1: Slumped Bait & Tackle Shack (-11.0, 1.6, 19.0)
      2. Building 2: Two-Story Cannery & Harbor Master Warehouse (2.0, 2.2, 25.0)
      3. Building 3: Crooked Net-Drying Shanty (13.0, 2.0, 18.0)
    """
    objects: List[bpy.types.Object] = []

    # --- Building 1: Slumped Bait & Tackle Shack (-11.0, 1.6, 19.0) ---
    objects.extend(
        build_slumped_building(
            name="BaitShack",
            center_g=(-11.0, 1.6, 19.0),
            width=6.2,
            height=3.4,
            depth=5.4,
            wall_mat=mats["RottingWood"],
            trim_mat=mats["WeatheredTimber"],
            roof_mat=mats["CorrugatedRoof"],
            mats=mats,
            lean_x_deg=3.5,
            lean_z_deg=-2.5,
            roof_sag=0.28,
            window_front_count=2,
            seed=801,
        )
    )
    # Wooden stilts under water-side half of Bait Shack
    for sx in (-13.7, -8.3):
        for sz in (16.5, 21.5):
            objects.append(create_cylinder_g(f"BaitShackStilt_{sx}_{sz}", (sx, -3.6, sz), (sx, 1.68, sz), 0.19, 0.17, mats["WeatheredTimber"], segments=8))
    # Crooked stovepipe chimney at (-13.0, 6.95, 18.0)
    objects.append(create_cylinder_g("BaitShackChimney", (-12.75, 4.5, 18.2), (-13.0, 6.68, 18.0), 0.15, 0.13, mats["RustIron"], segments=10))
    objects.append(create_cylinder_g("BaitShackChimneyCap", (-13.0, 6.72, 18.0), (-13.0, 6.96, 18.0), 0.28, 0.03, mats["RustIron"], segments=10))

    # --- Building 2: Two-Story Cannery & Harbor Master Warehouse (2.0, 2.2, 25.0) ---
    objects.extend(
        build_slumped_building(
            name="CanneryLower",
            center_g=(2.0, 2.0, 25.0),
            width=10.5,
            height=3.8,
            depth=7.8,
            wall_mat=mats["ShackWall"],
            trim_mat=mats["WeatheredTimber"],
            roof_mat=mats["CorrugatedRoof"],
            mats=mats,
            lean_x_deg=-2.2,
            lean_z_deg=-1.8,
            roof_sag=0.32,
            window_front_count=2,
            seed=802,
        )
    )
    objects.extend(
        build_slumped_building(
            name="CanneryUpper",
            center_g=(2.0, 5.4, 25.2),
            width=7.6,
            height=3.1,
            depth=6.2,
            wall_mat=mats["RottingWood"],
            trim_mat=mats["WeatheredTimber"],
            roof_mat=mats["CorrugatedRoof"],
            mats=mats,
            lean_x_deg=-2.8,
            lean_z_deg=-2.2,
            roof_sag=0.35,
            window_front_count=2,
            seed=803,
        )
    )
    # Double cargo doors facing pier & wall-mounted hoist beam + pulley chain
    objects.append(create_box_g("CanneryCargoDoors", (2.0, 3.15, 20.98), (2.45, 2.35, 0.16), mats["WeatheredTimber"], bevel_width=0.01))
    objects.append(create_box_g("CanneryDoorSeam", (2.0, 3.15, 20.88), (0.06, 2.35, 0.06), mats["DarkMetal"]))
    objects.append(create_cylinder_g("CanneryHoistBeam", (2.0, 8.15, 22.4), (2.0, 8.15, 20.1), 0.11, 0.09, mats["WeatheredTimber"], segments=8))
    objects.append(create_cylinder_g("CanneryHoistChain", (2.0, 8.10, 20.25), (2.0, 5.80, 20.25), 0.025, 0.025, mats["DarkMetal"], segments=6))
    # Brick & iron chimney at (5.2, 10.90, 26.2)
    objects.append(create_box_g("CanneryBrickChimney", (5.2, 8.6, 26.2), (0.78, 1.9, 0.78), mats["LighthouseBand"], bevel_width=0.015))
    objects.append(create_cylinder_g("CanneryFluePipe", (5.2, 9.45, 26.2), (5.2, 10.60, 26.2), 0.19, 0.16, mats["RustIron"], segments=10))
    objects.append(create_cylinder_g("CanneryFlueCap", (5.2, 10.65, 26.2), (5.2, 10.92, 26.2), 0.34, 0.04, mats["RustIron"], segments=10))

    # --- Building 3: Crooked Net-Drying Shanty (13.0, 2.0, 18.0) ---
    objects.extend(
        build_slumped_building(
            name="NetShanty",
            center_g=(13.0, 2.0, 18.0),
            width=5.8,
            height=3.2,
            depth=5.0,
            wall_mat=mats["RottingWood"],
            trim_mat=mats["WeatheredTimber"],
            roof_mat=mats["CorrugatedRoof"],
            mats=mats,
            lean_x_deg=-3.8,
            lean_z_deg=2.4,
            roof_sag=0.26,
            window_front_count=1,
            seed=804,
        )
    )
    # Overhanging porch roof, crooked timber posts, hanging fishing net drapes, and glowing porch lantern
    objects.append(create_box_g("ShantyPorchRoof", (13.0, 4.65, 14.6), (5.6, 0.14, 2.2), mats["CorrugatedRoof"], pitch_deg=6.0, roll_deg=-2.5, bevel_width=0.01))
    objects.append(create_cylinder_g("ShantyPorchPostL", (10.5, 1.35, 13.8), (10.4, 4.65, 13.8), 0.12, 0.10, mats["WeatheredTimber"], segments=8))
    objects.append(create_cylinder_g("ShantyPorchPostR", (15.5, 1.35, 13.8), (15.4, 4.65, 13.8), 0.12, 0.10, mats["WeatheredTimber"], segments=8))
    objects.append(create_cylinder_g("ShantyPorchLantern", (13.0, 4.55, 13.9), (13.0, 4.18, 13.9), 0.12, 0.10, mats["AmberGlass"], segments=10))

    # Hanging fishing net drapes under porch & beside shanty
    for net_i in range(5):
        nx0 = 10.6 + net_i * 1.1
        nx1 = nx0 + 0.95
        net_pts = catenary_points_g((nx0, 4.35, 13.85), (nx1, 4.30, 13.85), sag=1.45, steps=10)
        objects.append(create_curve_g(f"FishingNetDrape_{net_i}", net_pts, bevel_depth=0.035, mat=mats["WeatheredTimber"], resolution_u=6))

    return objects


# ---------------------------------------------------------------------------
# 4. Grand Coastal Lighthouse, Keeper's Cottage & Catenary Power Lines
# ---------------------------------------------------------------------------

def build_lighthouse_and_cables(
    mats: Dict[str, bpy.types.Material],
    lamp_post_tops: List[Vec3],
) -> List[bpy.types.Object]:
    """
    Constructs at (x = 0.0, y = 10.5, z = 44.0, top at y = 36.5m):
      - Stone Keeper's Cottage attached to base of tower
      - 26m tapered masonry tower (LighthouseStone with middle crimson LighthouseBand stripe)
      - Boolean-carved slit windows with stone lintels & AmberGlass panes
      - Flared corbelled gallery balcony (y = 32.0m) with iron railings
      - Cylindrical glass lattice lantern room (BeaconLens centered at y = 33.6m)
      - Copper-patina (CoastalMoss) domed cupola roof with lightning rod (y = 36.5m)
      - Drooping 3D catenary power/lantern cables (CURVE splines with bevel_depth = 0.02, DarkMetal)
    """
    objects: List[bpy.types.Object] = []
    lh_x, lh_z = 0.0, 44.0

    # Keeper's Cottage attached beside base of HarborLighthouse tower (-6.2, 10.4, 41.6)
    objects.extend(
        build_slumped_building(
            name="KeepersCottage",
            center_g=(-6.2, 10.4, 41.6),
            width=5.2,
            height=3.4,
            depth=4.6,
            wall_mat=mats["LighthouseStone"],
            trim_mat=mats["WeatheredTimber"],
            roof_mat=mats["CorrugatedRoof"],
            mats=mats,
            lean_x_deg=-1.2,
            lean_z_deg=-1.0,
            roof_sag=0.16,
            window_front_count=1,
            add_rear_window=False,
            seed=809,
        )
    )
    objects.append(create_box_g("CottageDoor", (-7.5, 11.55, 39.26), (1.15, 2.10, 0.14), mats["WeatheredTimber"], bevel_width=0.01))
    objects.append(create_box_g("CottageDoorLintel", (-7.5, 12.68, 39.22), (1.38, 0.22, 0.24), mats["LighthouseStone"], bevel_width=0.01))

    # Note: The lighthouse tower itself is spawned from `res://assets/models/harbor_lighthouse.glb`
    # at (0.0, 10.5, 44.0) by WorldBuilder (`_build_wharf_port()`).

    # --- Drooping 3D Catenary Power / Lantern Cables (bevel_depth = 0.02, DarkMetal) ---
    cable_spans = [
        ("Cable_Post0_Post2", lamp_post_tops[0], lamp_post_tops[2], 0.68),
        ("Cable_Post1_Post3", lamp_post_tops[1], lamp_post_tops[3], 0.82),
        ("Cable_Post0_Post1", lamp_post_tops[0], lamp_post_tops[1], 0.95),
        ("Cable_Post2_BaitShack", lamp_post_tops[2], (-10.2, 4.85, 16.5), 0.45),
        ("Cable_Post2_Cannery", lamp_post_tops[2], (-1.2, 8.2, 22.1), 0.72),
        ("Cable_Post3_Cannery", lamp_post_tops[3], (5.2, 8.2, 22.1), 0.65),
        ("Cable_Post3_NetShanty", lamp_post_tops[3], (11.5, 4.9, 15.6), 0.48),
        ("Cable_Cannery_Lighthouse", (2.0, 9.8, 27.6), (0.0, 22.0, 41.5), 1.65),
    ]
    objects.append(create_cylinder_g("CanneryRoofPole", (2.0, 8.2, 27.6), (2.0, 9.9, 27.6), 0.08, 0.06, mats["WeatheredTimber"], segments=8))
    for cname, p_a, p_b, sag in cable_spans:
        pts = catenary_points_g(p_a, p_b, sag=sag, steps=14, sway_x=0.12)
        objects.append(create_curve_g(cname, pts, bevel_depth=0.02, mat=mats["DarkMetal"], resolution_u=8))

    return objects


# ---------------------------------------------------------------------------
# Join, Coordinate Alignment & GLB Export
# ---------------------------------------------------------------------------

def finalize_and_export_glb(objects: List[bpy.types.Object], output_glb_path: str) -> None:
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

    bpy.ops.object.select_all(action="DESELECT")
    for obj in mesh_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objects[0]
    bpy.ops.object.join()

    wharf_obj = bpy.context.active_object
    wharf_obj.name = "WharfIslandMesh"
    wharf_obj.data.name = "WharfIslandMesh"

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Negate Blender Y axis (and reverse face winding) so Blender's glTF (+Y Up) exporter
    # maps (x, -gz, gy) -> (x, gy, gz) in Godot 4!
    bm = bmesh.new()
    bm.from_mesh(wharf_obj.data)
    bmesh.ops.scale(bm, vec=Vector((1.0, -1.0, 1.0)), verts=bm.verts)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(wharf_obj.data)
    bm.free()

    for poly in wharf_obj.data.polygons:
        poly.use_smooth = False

    os.makedirs(os.path.dirname(output_glb_path), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=output_glb_path,
        export_format="GLB",
        export_apply=True,
        export_yup=True,
    )

    num_verts = len(wharf_obj.data.vertices)
    num_polys = len(wharf_obj.data.polygons)
    print(f"[Blender 5.4.0] Exported WharfIslandMesh to {output_glb_path}")
    print(f"[Blender 5.4.0] Vertices: {num_verts}, Polygons: {num_polys}, Materials: {len(wharf_obj.data.materials)}")


def main() -> None:
    clear_scene()
    mats = create_pbr_materials()

    all_objects: List[bpy.types.Object] = []
    all_objects.extend(build_coastal_crag_and_staircase(mats))
    pier_objs, lamp_post_tops = build_wharf_pier_and_clutter(mats)
    all_objects.extend(pier_objs)
    all_objects.extend(build_harbor_buildings(mats))
    all_objects.extend(build_lighthouse_and_cables(mats, lamp_post_tops))

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_glb = os.path.join(project_root, "assets", "models", "wharf_island.glb")
    finalize_and_export_glb(all_objects, output_glb)


if __name__ == "__main__":
    main()
