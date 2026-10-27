#!/usr/bin/env python3
"""
Headless Blender 5.4.0 procedural archipelago & rock formation generator.
Generates 6 sculpted .glb models in res://assets/models/ with shared native
Principled BSDF PBR materials assigned by elevation (Z in Blender -> Y in Godot)
and surface slope.
"""

import math
import os
import random
import bpy
import bmesh
from mathutils import Vector, noise


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        if block.users == 0:
            bpy.data.meshes.remove(block)


def create_pbr_materials() -> dict:
    """Create the 4 shared native PBR Principled BSDF materials."""
    specs = {
        "TidalWetRock": {
            "base_color": (0.04, 0.05, 0.06, 1.0),
            "metallic": 0.05,
            "roughness": 0.12,
            "specular_ior": 0.9,
        },
        "BasaltCliff": {
            "base_color": (0.12, 0.14, 0.16, 1.0),
            "metallic": 0.04,
            "roughness": 0.86,
            "specular_ior": 0.45,
        },
        "SharpObsidian": {
            "base_color": (0.06, 0.07, 0.09, 1.0),
            "metallic": 0.25,
            "roughness": 0.38,
            "specular_ior": 0.75,
        },
        "CoastalMoss": {
            "base_color": (0.10, 0.17, 0.12, 1.0),
            "metallic": 0.0,
            "roughness": 0.94,
            "specular_ior": 0.25,
        },
    }

    materials = {}
    for name, cfg in specs.items():
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = bpy.data.materials.new(name=name)
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is None:
            bsdf = mat.node_tree.nodes.new(type="ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = cfg["base_color"]
        bsdf.inputs["Metallic"].default_value = cfg["metallic"]
        bsdf.inputs["Roughness"].default_value = cfg["roughness"]
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = cfg["specular_ior"]
        materials[name] = mat

    return materials


def attach_materials_and_assign_by_height_slope(
    obj: bpy.types.Object,
    mats: dict,
    prefer_obsidian: bool = False,
) -> None:
    """
    Assign materials to faces based on height (z in Blender = y in Godot) and slope:
      - TidalWetRock (slot 0): face center height < 1.8m
      - CoastalMoss  (slot 3): face center height > 2.2m and relatively flat upper ledge (normal.z > 0.66)
      - BasaltCliff  (slot 1) or SharpObsidian (slot 2): steep faces and crags
    """
    mesh = obj.data
    mesh.materials.clear()
    slot_names = ["TidalWetRock", "BasaltCliff", "SharpObsidian", "CoastalMoss"]
    for s_name in slot_names:
        mesh.materials.append(mats[s_name])

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.normal_update()

    for face in bm.faces:
        center = face.calc_center_median()
        normal = face.normal
        z_h = center.z
        up_dot = normal.z

        if z_h < 1.8:
            face.material_index = 0  # TidalWetRock
        elif z_h > 2.2 and up_dot > 0.65 and not prefer_obsidian:
            face.material_index = 3  # CoastalMoss
        elif prefer_obsidian:
            if z_h > 3.5 and up_dot > 0.78:
                face.material_index = 3  # Small mossy cap on flat ledges
            elif up_dot < 0.35 or z_h > 4.0:
                face.material_index = 2  # SharpObsidian
            else:
                face.material_index = 1  # BasaltCliff
        else:
            # Mix BasaltCliff and SharpObsidian on very sheer/overhanging faces
            if up_dot < 0.12 and z_h > 5.0:
                face.material_index = 2  # SharpObsidian
            else:
                face.material_index = 1  # BasaltCliff

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def ridged_voronoi_fbm(p: Vector, octaves: int = 4) -> float:
    """Combines Voronoi cellular ridges and multi-octave Perlin/Simplex fBM."""
    val = 0.0
    amp = 0.55
    freq = 1.0
    for _ in range(octaves):
        sp = p * freq
        n = noise.noise(sp)
        ridge = 1.0 - abs(n)
        vor_dists, _ = noise.voronoi(sp * 0.85)
        v_edge = max(0.0, min(1.0, vor_dists[1] - vor_dists[0]))
        val += (ridge * 0.65 + v_edge * 0.35) * amp
        freq *= 2.05
        amp *= 0.48
    return val


def export_single_object_glb(obj: bpy.types.Object, filepath: str) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        use_selection=True,
        export_format="GLB",
        export_apply=True,
        export_yup=True,
    )


def build_island_large_archipelago(mats: dict, out_dir: str) -> None:
    """
    1. island_large_archipelago.glb (~68m wide, 24m tall, dual-peak Voronoi/Clouds
       displaced island with a crescent cove).
    """
    clear_scene()
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=96, y_segments=96, size=36.0)

    seed_offset = Vector((13.4, -27.8, 5.1))
    for v in bm.verts:
        x, y, _ = v.co
        r = math.sqrt(x * x + y * y)
        angle = math.atan2(y, x)

        # Irregular coastline radius (~34m radius -> ~68m total width)
        coast_noise = noise.noise(Vector((math.cos(angle) * 1.6, math.sin(angle) * 1.6, 2.3))) * 4.5
        # Carve a sheltered crescent cove on the -Y (forward/south) side
        cove_angle_diff = math.atan2(math.sin(angle + math.pi * 0.5), math.cos(angle + math.pi * 0.5))
        cove_indent = math.exp(-(cove_angle_diff * cove_angle_diff) / 0.28) * 12.5

        max_r = 34.0 + coast_noise - cove_indent
        norm_r = r / max(max_r, 8.0)

        if norm_r >= 1.08:
            z = -3.2 - (norm_r - 1.08) * 4.0
        else:
            # Dual-peak profile: Main western peak (~24m) and secondary eastern peak (~18.5m)
            d_peak1 = math.sqrt((x + 11.5) ** 2 + (y - 5.5) ** 2)
            d_peak2 = math.sqrt((x - 13.0) ** 2 + (y - 3.5) ** 2)
            peak1 = math.exp(-(d_peak1 * d_peak1) / 195.0) * 21.0
            peak2 = math.exp(-(d_peak2 * d_peak2) / 160.0) * 16.0

            base_dome = max(0.0, 1.0 - norm_r * norm_r) * 7.5
            # Carve the cove basin down near/below water level
            cove_dist = math.sqrt(x * x + (y + 12.0) ** 2)
            cove_basin = math.exp(-(cove_dist * cove_dist) / 110.0) * 8.5

            # Voronoi + Clouds craggy displacement
            sample_p = Vector((x * 0.075, y * 0.075, 0.0)) + seed_offset
            crag = ridged_voronoi_fbm(sample_p, octaves=4) * 7.2 * max(0.15, 1.0 - norm_r * 0.85)

            # Stepped coastal terrace ledges
            raw_z = base_dome + peak1 + peak2 + crag - cove_basin
            terrace = math.sin(raw_z * 0.85) * 0.45
            z = raw_z + terrace

            # Smooth shoreline skirt dipping below waterline (-2.5m)
            if norm_r > 0.88:
                t = (norm_r - 0.88) / 0.20
                z = z * (1.0 - t) + (-2.8) * t

        # Slight horizontal crag warp on cliffs
        disp_xy = noise.turbulence_vector(Vector((x * 0.09, y * 0.09, z * 0.09)), 3, False)
        v.co = Vector((
            x + disp_xy.x * 1.15 * max(0.0, 1.0 - norm_r),
            y + disp_xy.y * 1.15 * max(0.0, 1.0 - norm_r),
            z,
        ))

    bmesh.ops.triangulate(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("IslandLargeArchipelago")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("IslandLargeArchipelago", mesh)
    bpy.context.collection.objects.link(obj)
    attach_materials_and_assign_by_height_slope(obj, mats, prefer_obsidian=False)

    out_path = os.path.join(out_dir, "island_large_archipelago.glb")
    export_single_object_glb(obj, out_path)
    print(f"Exported {out_path}")


def build_island_medium_crag(mats: dict, out_dir: str) -> None:
    """
    2. island_medium_crag.glb (~32m wide, 16m tall, stepped craggy outcrop).
    """
    clear_scene()
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=64, y_segments=64, size=17.0)

    seed_offset = Vector((-41.2, 19.8, 8.4))
    for v in bm.verts:
        x, y, _ = v.co
        r = math.sqrt((x * 0.95) ** 2 + (y * 1.08) ** 2)
        angle = math.atan2(y, x)

        coast_mod = noise.noise(Vector((math.cos(angle) * 2.0, math.sin(angle) * 2.0, 6.1))) * 2.6
        max_r = 16.0 + coast_mod
        norm_r = r / max(max_r, 4.0)

        if norm_r >= 1.06:
            z = -2.4 - (norm_r - 1.06) * 3.0
        else:
            # Asymmetric stepped crag peak (~16m tall)
            d_peak = math.sqrt((x - 2.2) ** 2 + (y + 1.8) ** 2)
            core = math.exp(-(d_peak * d_peak) / 68.0) * 13.5
            shoulder = math.exp(-((x + 4.5) ** 2 + (y - 3.0) ** 2) / 55.0) * 8.5

            crag = ridged_voronoi_fbm(Vector((x * 0.13, y * 0.13, 1.0)) + seed_offset, octaves=4)
            raw_z = core + shoulder + crag * 4.8 * max(0.2, 1.0 - norm_r * 0.8)

            # Pronounced stepped basalt ledges
            step_h = 3.2
            stepped_z = math.floor(raw_z / step_h) * step_h + (raw_z % step_h) * 0.55
            z = raw_z * 0.45 + stepped_z * 0.55

            if norm_r > 0.84:
                t = (norm_r - 0.84) / 0.22
                z = z * (1.0 - t) + (-2.4) * t

        v.co = Vector((x, y, z))

    bmesh.ops.triangulate(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("IslandMediumCrag")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("IslandMediumCrag", mesh)
    bpy.context.collection.objects.link(obj)
    attach_materials_and_assign_by_height_slope(obj, mats, prefer_obsidian=False)

    out_path = os.path.join(out_dir, "island_medium_crag.glb")
    export_single_object_glb(obj, out_path)
    print(f"Exported {out_path}")


def build_island_sea_stack(mats: dict, out_dir: str) -> None:
    """
    3. island_sea_stack.glb (~14m wide, 28m tall, wave-undercut vertical needle pillar).
    """
    clear_scene()
    bm = bmesh.new()

    radial_segs = 40
    height_segs = 56
    total_h = 30.0  # from z = -2.0m to +28.0m

    rings = []
    for iy in range(height_segs + 1):
        t = iy / height_segs
        z = -2.0 + t * total_h

        # Base flares out underwater (~7.2m radius -> ~14.4m width),
        # wave-undercut notch around z = 0.8m .. 2.8m,
        # widens slightly at mid-body, then tapers to a jagged 28m needle summit
        if z < 0.0:
            base_r = 7.0 - (z / -2.0) * 0.4
        else:
            undercut = math.exp(-((z - 1.5) ** 2) / 2.2) * 1.85
            taper = (1.0 - (z / 28.5) ** 1.35) * 5.8 + 1.15
            bulge = math.exp(-((z - 9.5) ** 2) / 28.0) * 1.1
            base_r = max(1.1, taper + bulge - undercut)

        ring_verts = []
        for ix in range(radial_segs):
            ang = (2.0 * math.pi * ix) / radial_segs
            ca = math.cos(ang)
            sa = math.sin(ang)

            # Vertical fluted basalt ribs + Voronoi fracture
            rib = math.cos(ang * 7.0 + z * 0.12) * 0.45 + math.sin(ang * 13.0 - z * 0.08) * 0.25
            n_val = ridged_voronoi_fbm(Vector((ca * 1.4, sa * 1.4, z * 0.16)), octaves=3)
            r = max(0.65, base_r + rib + (n_val - 0.4) * 1.35)

            # Slight lean/twist along height
            lean_x = math.sin(z * 0.11) * 0.65
            lean_y = math.cos(z * 0.09) * 0.55

            vx = ca * r + lean_x
            vy = sa * r + lean_y
            ring_verts.append(bm.verts.new((vx, vy, z)))
        rings.append(ring_verts)

    for iy in range(height_segs):
        r0 = rings[iy]
        r1 = rings[iy + 1]
        for ix in range(radial_segs):
            nx = (ix + 1) % radial_segs
            bm.faces.new((r0[ix], r0[nx], r1[nx], r1[ix]))

    # Cap top summit with jagged peak vertex
    top_center = bm.verts.new((0.3, -0.2, 28.2))
    top_ring = rings[-1]
    for ix in range(radial_segs):
        nx = (ix + 1) % radial_segs
        bm.faces.new((top_ring[ix], top_ring[nx], top_center))

    # Cap bottom base
    bot_center = bm.verts.new((0.0, 0.0, -2.0))
    bot_ring = rings[0]
    for ix in range(radial_segs):
        nx = (ix + 1) % radial_segs
        bm.faces.new((bot_ring[nx], bot_ring[ix], bot_center))

    bmesh.ops.triangulate(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("IslandSeaStack")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("IslandSeaStack", mesh)
    bpy.context.collection.objects.link(obj)
    attach_materials_and_assign_by_height_slope(obj, mats, prefer_obsidian=False)

    out_path = os.path.join(out_dir, "island_sea_stack.glb")
    export_single_object_glb(obj, out_path)
    print(f"Exported {out_path}")


def build_rock_razor_cluster(mats: dict, out_dir: str) -> None:
    """
    4. rock_razor_cluster.glb (~18m footprint, 6m-15m tall, 6-8 sharp faceted
       angled stone blades).
    """
    clear_scene()
    bm = bmesh.new()

    # 7 angled razor blades arranged across an ~18m footprint
    blade_specs = [
        # (base_x, base_y, height, rx, ry, tilt_x, tilt_y, yaw, sides)
        (0.0, 0.0, 15.0, 2.8, 1.2, 1.4, -0.8, 0.35, 6),
        (-4.8, -2.2, 11.8, 2.4, 1.0, -1.8, -1.1, 0.95, 5),
        (4.6, -1.8, 12.6, 2.5, 1.1, 1.9, -0.9, -0.60, 6),
        (-3.6, 3.8, 9.5, 2.2, 0.95, -1.5, 1.6, 1.40, 5),
        (3.9, 3.4, 10.4, 2.1, 0.95, 1.6, 1.4, -1.15, 6),
        (-6.8, 0.8, 6.8, 1.9, 0.85, -2.1, 0.4, 0.55, 5),
        (6.5, 0.9, 7.4, 2.0, 0.90, 2.2, 0.5, -0.45, 5),
    ]

    for idx, (bx, by, h, rx, ry, tx, ty, yaw, sides) in enumerate(blade_specs):
        segs_z = 12
        cy = math.cos(yaw)
        sy = math.sin(yaw)
        blade_rings = []

        for iz in range(segs_z + 1):
            t = iz / segs_z
            z = -1.8 + t * (h + 1.8)
            # Sharp blade taper with faceted step ridges
            scale = max(0.06, (1.0 - t ** 1.15) * (1.0 + 0.08 * math.sin(t * 14.0)))
            ring = []
            for iside in range(sides):
                ang = (2.0 * math.pi * iside) / sides
                # Flatten into a sharp knife-edge cross-section
                lx = math.cos(ang) * rx * scale
                ly = math.sin(ang) * ry * scale
                # Facet noise
                fn = noise.noise(Vector((lx * 0.4 + idx * 3.1, ly * 0.4, z * 0.25)))
                lx *= 1.0 + fn * 0.22
                ly *= 1.0 + fn * 0.22

                # Rotate by yaw and apply tilt
                wx = bx + (lx * cy - ly * sy) + tx * (t ** 1.1)
                wy = by + (lx * sy + ly * cy) + ty * (t ** 1.1)
                ring.append(bm.verts.new((wx, wy, z)))
            blade_rings.append(ring)

        for iz in range(segs_z):
            r0 = blade_rings[iz]
            r1 = blade_rings[iz + 1]
            for iside in range(sides):
                ns = (iside + 1) % sides
                bm.faces.new((r0[iside], r0[ns], r1[ns], r1[iside]))

        # Sharp apex tip
        tip_v = bm.verts.new((bx + tx * 1.08, by + ty * 1.08, h + 0.35))
        top_r = blade_rings[-1]
        for iside in range(sides):
            ns = (iside + 1) % sides
            bm.faces.new((top_r[iside], top_r[ns], tip_v))

        # Base cap
        bot_v = bm.verts.new((bx, by, -1.8))
        bot_r = blade_rings[0]
        for iside in range(sides):
            ns = (iside + 1) % sides
            bm.faces.new((bot_r[ns], bot_r[iside], bot_v))

    bmesh.ops.triangulate(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("RockRazorCluster")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("RockRazorCluster", mesh)
    bpy.context.collection.objects.link(obj)
    attach_materials_and_assign_by_height_slope(obj, mats, prefer_obsidian=True)

    out_path = os.path.join(out_dir, "rock_razor_cluster.glb")
    export_single_object_glb(obj, out_path)
    print(f"Exported {out_path}")


def build_rock_jagged_arch(mats: dict, out_dir: str) -> None:
    """
    5. rock_jagged_arch.glb (~36m wide, 28m tall, twisted sea arch with a
       Boolean-carved 15m navigable hollow tunnel through the center).
    """
    clear_scene()

    # Step 1: Create the main outer jagged rock mass (~36m wide along X, ~22m deep along Y, ~28m tall along Z)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)

    seed_offset = Vector((73.2, -18.4, 31.0))
    for v in bm.verts:
        nx, ny, nz = v.co.x, v.co.y, v.co.z
        # Stretch into a 36m wide, 22m deep, 28m tall sea-arch massif
        x = nx * 18.0
        y = ny * 11.0
        # Shift vertical range so base sits at z = -3.0m and crown reaches z = 28.0m
        z = (nz * 0.5 + 0.5) * 31.0 - 3.0

        # Add dramatic twist and craggy Voronoi displacement
        twist = (z / 28.0) * 0.38
        tx = x * math.cos(twist) - y * math.sin(twist)
        ty = x * math.sin(twist) + y * math.cos(twist)

        crag = ridged_voronoi_fbm(Vector((tx * 0.08, ty * 0.08, z * 0.08)) + seed_offset, octaves=4)
        radial_len = math.sqrt(nx * nx + ny * ny)
        if radial_len > 1e-4:
            tx += (nx / radial_len) * (crag - 0.35) * 3.8
            ty += (ny / radial_len) * (crag - 0.35) * 3.2
        if z > 2.0:
            z += (crag - 0.35) * 3.5

        v.co = Vector((tx, ty, z))

    arch_mesh = bpy.data.meshes.new("RockJaggedArch")
    bm.to_mesh(arch_mesh)
    bm.free()

    arch_obj = bpy.data.objects.new("RockJaggedArch", arch_mesh)
    bpy.context.collection.objects.link(arch_obj)

    # Step 2: Create the 15m wide navigable hollow tunnel Boolean cutter cylinder
    # Oriented along the Y axis (so in Godot it runs front-to-back along Z, 15m wide x 16m high above water)
    bm_cut = bmesh.new()
    tunnel_segs = 36
    tunnel_len_segs = 24
    tunnel_half_len = 20.0  # extends completely through the 22m depth
    tunnel_rings = []

    for iy in range(tunnel_len_segs + 1):
        ty = -tunnel_half_len + (2.0 * tunnel_half_len * iy) / tunnel_len_segs
        ring = []
        for iseg in range(tunnel_segs):
            ang = (2.0 * math.pi * iseg) / tunnel_segs
            ca = math.cos(ang)
            sa = math.sin(ang)
            # 15m wide tunnel (half-width = 7.8m), arched vault reaching z = 16.5m above water
            rx = 7.8
            rz = 10.5
            # Craggy rock-carved tunnel wall perturbation
            wall_n = noise.noise(Vector((ca * 2.2, ty * 0.15, sa * 2.2))) * 0.85
            cx = ca * (rx + wall_n)
            cz = 5.5 + sa * (rz + wall_n)
            ring.append(bm_cut.verts.new((cx, ty, cz)))
        tunnel_rings.append(ring)

    for iy in range(tunnel_len_segs):
        r0 = tunnel_rings[iy]
        r1 = tunnel_rings[iy + 1]
        for iseg in range(tunnel_segs):
            ns = (iseg + 1) % tunnel_segs
            bm_cut.faces.new((r0[iseg], r0[ns], r1[ns], r1[iseg]))

    # Cap ends of cutter so it is a closed manifold volume
    front_c = bm_cut.verts.new((0.0, -tunnel_half_len, 5.5))
    back_c = bm_cut.verts.new((0.0, tunnel_half_len, 5.5))
    for iseg in range(tunnel_segs):
        ns = (iseg + 1) % tunnel_segs
        bm_cut.faces.new((tunnel_rings[0][ns], tunnel_rings[0][iseg], front_c))
        bm_cut.faces.new((tunnel_rings[-1][iseg], tunnel_rings[-1][ns], back_c))

    bmesh.ops.recalc_face_normals(bm_cut, faces=bm_cut.faces)
    cutter_mesh = bpy.data.meshes.new("TunnelCutter")
    bm_cut.to_mesh(cutter_mesh)
    bm_cut.free()

    cutter_obj = bpy.data.objects.new("TunnelCutter", cutter_mesh)
    bpy.context.collection.objects.link(cutter_obj)

    # Apply Boolean DIFFERENCE modifier on arch_obj
    bpy.context.view_layer.objects.active = arch_obj
    bool_mod = arch_obj.modifiers.new(name="CarveNavigableTunnel", type="BOOLEAN")
    bool_mod.operation = "DIFFERENCE"
    bool_mod.object = cutter_obj
    bpy.ops.object.modifier_apply(modifier=bool_mod.name)

    # Remove cutter object
    bpy.data.objects.remove(cutter_obj, do_unlink=True)
    bpy.data.meshes.remove(cutter_mesh)

    # Triangulate and assign PBR materials by height & slope
    bm_final = bmesh.new()
    bm_final.from_mesh(arch_obj.data)
    bmesh.ops.triangulate(bm_final, faces=bm_final.faces)
    bm_final.to_mesh(arch_obj.data)
    bm_final.free()

    attach_materials_and_assign_by_height_slope(arch_obj, mats, prefer_obsidian=False)

    out_path = os.path.join(out_dir, "rock_jagged_arch.glb")
    export_single_object_glb(arch_obj, out_path)
    print(f"Exported {out_path}")


def build_rock_basalt_monolith(mats: dict, out_dir: str) -> None:
    """
    6. rock_basalt_monolith.glb (~24m wide, 38m tall, cluster of 35+ extruded
       hexagonal basalt columns).
    """
    clear_scene()
    bm = bmesh.new()

    rng = random.Random(40404)
    # Generate a hexagonal grid of 37+ columns within a ~12m radius (~24m diameter)
    hex_spacing = 1.88
    columns = []

    for q in range(-6, 7):
        for r in range(-6, 7):
            cx = hex_spacing * (math.sqrt(3.0) * q + math.sqrt(3.0) * 0.5 * r)
            cy = hex_spacing * (1.5 * r)
            dist = math.sqrt(cx * cx + cy * cy)
            if dist > 11.6:
                continue

            # Central columns soar up to 38m; outer columns step down like Giant's Causeway tiers
            norm_d = dist / 11.4
            if dist < 2.2:
                col_h = 38.0 - rng.uniform(0.0, 2.2)
            else:
                base_profile = (1.0 - norm_d ** 1.25) * 35.0 + 3.2
                col_h = max(2.0, base_profile + rng.uniform(-3.2, 3.2))

            col_radius = hex_spacing * 0.56 * rng.uniform(0.92, 1.04)
            columns.append((cx, cy, col_h, col_radius, dist))

    print(f"Building basalt monolith with {len(columns)} hexagonal columns...")

    for idx, (cx, cy, col_h, col_r, dist) in enumerate(columns):
        segs_z = 8
        z_bot = -2.2
        rings = []

        # Slight outward splay near top of tall columns
        radial_dir = Vector((cx, cy, 0.0))
        if radial_dir.length > 1e-4:
            radial_dir.normalize()

        for iz in range(segs_z + 1):
            t = iz / segs_z
            z = z_bot + t * (col_h - z_bot)
            splay = (t ** 2) * 0.45 * (dist / 11.5)
            ring = []
            for iside in range(6):
                ang = (2.0 * math.pi * iside) / 6.0 + (math.pi / 6.0)
                vx = cx + math.cos(ang) * col_r + radial_dir.x * splay
                vy = cy + math.sin(ang) * col_r + radial_dir.y * splay
                # Subtle basalt fracture jitter along column edges
                jn = noise.noise(Vector((vx * 0.35, vy * 0.35, z * 0.18 + idx))) * 0.12
                ring.append(bm.verts.new((vx + jn, vy + jn, z)))
            rings.append(ring)

        for iz in range(segs_z):
            r0 = rings[iz]
            r1 = rings[iz + 1]
            for iside in range(6):
                ns = (iside + 1) % 6
                bm.faces.new((r0[iside], r0[ns], r1[ns], r1[iside]))

        # Slightly tilted fractured top cap on each hexagonal column
        tilt_x = rng.uniform(-0.18, 0.18)
        tilt_y = rng.uniform(-0.18, 0.18)
        top_r = rings[-1]
        for iside in range(6):
            v = top_r[iside]
            v.co.z += (v.co.x - cx) * tilt_x + (v.co.y - cy) * tilt_y

        top_c = bm.verts.new((cx, cy, col_h + rng.uniform(-0.15, 0.25)))
        for iside in range(6):
            ns = (iside + 1) % 6
            bm.faces.new((top_r[iside], top_r[ns], top_c))

        bot_c = bm.verts.new((cx, cy, z_bot))
        bot_r = rings[0]
        for iside in range(6):
            ns = (iside + 1) % 6
            bm.faces.new((bot_r[ns], bot_r[iside], bot_c))

    bmesh.ops.triangulate(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("RockBasaltMonolith")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("RockBasaltMonolith", mesh)
    bpy.context.collection.objects.link(obj)
    attach_materials_and_assign_by_height_slope(obj, mats, prefer_obsidian=True)

    out_path = os.path.join(out_dir, "rock_basalt_monolith.glb")
    export_single_object_glb(obj, out_path)
    print(f"Exported {out_path}")


def main() -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(project_root, "assets", "models")
    os.makedirs(out_dir, exist_ok=True)

    mats = create_pbr_materials()

    build_island_large_archipelago(mats, out_dir)
    build_island_medium_crag(mats, out_dir)
    build_island_sea_stack(mats, out_dir)
    build_rock_razor_cluster(mats, out_dir)
    build_rock_jagged_arch(mats, out_dir)
    build_rock_basalt_monolith(mats, out_dir)

    print("All 6 archipelago & rock formation .glb models generated successfully.")


if __name__ == "__main__":
    main()
