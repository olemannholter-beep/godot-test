#!/usr/bin/env python3
"""
Headless Blender 5.4.0 Ultra-Detailed Roaming Maritime Threats Generator.

Run via:
  blender --background --python tools/blender_build_roaming_threats.py

Exports:
  1. assets/models/enemies/enemy_ghost_trawler.glb  (25,000-35,000 tris, 18+ nautical sub-assemblies)
  2. assets/models/enemies/enemy_leviathan_head.glb (25,000-35,000 tris, high-res anatomical sculpt)
  3. assets/models/enemies/enemy_leviathan_coil.glb (20,000-28,000 tris, scaled muscular coil segment)

Features:
  - Multi-component architectural & organic sub-meshes with BEVEL, SUBSURF, and procedural displacement
  - 40+ individually modeled curved ivory fangs, 10 flared gill arches with crimson gill filaments,
    6 multi-part glassy eyes (inner glowing iris + outer glossy clearcoat cornea dome), 4 curling sensory barbels,
    pleated dorsal fin membranes, and barnacle/coral encrustations
  - Topological concavity/ridge vertex-color painting (`Col` attribute) wired to Principled BSDF with wet clearcoat
"""

import math
import os
from typing import Dict, List, Sequence, Tuple

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

Vec3 = Tuple[float, float, float]
Color4 = Tuple[float, float, float, float]


# ---------------------------------------------------------------------------
# Math & Noise Helpers
# ---------------------------------------------------------------------------

def clear_scene() -> None:
	bpy.ops.wm.read_factory_settings(use_empty=True)


def clamp01(v: float) -> float:
	return max(0.0, min(1.0, v))


def lerp(a: float, b: float, t: float) -> float:
	return a + (b - a) * t


def lerp_color(c0: Color4, c1: Color4, t: float) -> Color4:
	ct = clamp01(t)
	return (
		lerp(c0[0], c1[0], ct),
		lerp(c0[1], c1[1], ct),
		lerp(c0[2], c1[2], ct),
		lerp(c0[3], c1[3], ct),
	)


def smoothstep(edge0: float, edge1: float, x: float) -> float:
	if abs(edge1 - edge0) < 1e-6:
		return 1.0 if x >= edge1 else 0.0
	t = clamp01((x - edge0) / (edge1 - edge0))
	return t * t * (3.0 - 2.0 * t)


def hash3(x: float, y: float, z: float) -> float:
	n = math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453123
	return n - math.floor(n)


def noise3d(x: float, y: float, z: float) -> float:
	ix = math.floor(x)
	iy = math.floor(y)
	iz = math.floor(z)
	fx = x - ix
	fy = y - iy
	fz = z - iz
	ux = fx * fx * (3.0 - 2.0 * fx)
	uy = fy * fy * (3.0 - 2.0 * fy)
	uz = fz * fz * (3.0 - 2.0 * fz)

	n000 = hash3(ix, iy, iz)
	n100 = hash3(ix + 1.0, iy, iz)
	n010 = hash3(ix, iy + 1.0, iz)
	n110 = hash3(ix + 1.0, iy + 1.0, iz)
	n001 = hash3(ix, iy, iz + 1.0)
	n101 = hash3(ix + 1.0, iy, iz + 1.0)
	n011 = hash3(ix, iy + 1.0, iz + 1.0)
	n111 = hash3(ix + 1.0, iy + 1.0, iz + 1.0)

	nx00 = lerp(n000, n100, ux)
	nx10 = lerp(n010, n110, ux)
	nx01 = lerp(n001, n101, ux)
	nx11 = lerp(n011, n111, ux)

	nxy0 = lerp(nx00, nx10, uy)
	nxy1 = lerp(nx01, nx11, uy)
	return lerp(nxy0, nxy1, uz)


def fbm3d(x: float, y: float, z: float, octaves: int = 3) -> float:
	val = 0.0
	amp = 0.5
	freq = 1.0
	for _ in range(octaves):
		val += amp * noise3d(x * freq, y * freq, z * freq)
		freq *= 2.05
		amp *= 0.5
	return val


# ---------------------------------------------------------------------------
# PBR Material Factory (Principled BSDF + Wet Clearcoat + Vertex Color `Col`)
# ---------------------------------------------------------------------------

def create_pbr_material(
	name: str,
	base_color: Color4,
	metallic: float = 0.25,
	roughness: float = 0.55,
	coat_weight: float = 1.0,
	coat_roughness: float = 0.06,
	emission_color: Color4 = (0.0, 0.0, 0.0, 1.0),
	emission_strength: float = 0.0,
	use_vertex_color: bool = True,
) -> bpy.types.Material:
	mat = bpy.data.materials.new(name=name)
	mat.use_nodes = True
	nt = mat.node_tree
	nodes = nt.nodes
	links = nt.links

	bsdf = nodes.get("Principled BSDF")
	if bsdf is None:
		bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")

	# When using vertex colors (`Col`) that already encode the base palette + cavity ink,
	# set Base Color to (1,1,1,1) so Godot's vertex_color_use_as_albedo doesn't double-darken.
	bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0) if use_vertex_color else base_color
	bsdf.inputs["Metallic"].default_value = metallic
	bsdf.inputs["Roughness"].default_value = roughness

	if "Coat Weight" in bsdf.inputs:
		bsdf.inputs["Coat Weight"].default_value = coat_weight
	elif "Clearcoat" in bsdf.inputs:
		bsdf.inputs["Clearcoat"].default_value = coat_weight

	if "Coat Roughness" in bsdf.inputs:
		bsdf.inputs["Coat Roughness"].default_value = coat_roughness
	elif "Clearcoat Roughness" in bsdf.inputs:
		bsdf.inputs["Clearcoat Roughness"].default_value = coat_roughness

	if "Emission Color" in bsdf.inputs:
		bsdf.inputs["Emission Color"].default_value = emission_color
	elif "Emission" in bsdf.inputs:
		bsdf.inputs["Emission"].default_value = emission_color

	if "Emission Strength" in bsdf.inputs:
		bsdf.inputs["Emission Strength"].default_value = emission_strength

	if use_vertex_color:
		attr_node = nodes.new(type="ShaderNodeAttribute")
		attr_node.attribute_name = "Col"
		links.new(attr_node.outputs["Color"], bsdf.inputs["Base Color"])
	else:
		attr_node = nodes.new(type="ShaderNodeAttribute")
		attr_node.attribute_name = "Col"
		mix_node = nodes.new(type="ShaderNodeMix")
		mix_node.data_type = "RGBA"
		mix_node.blend_type = "MIX"
		mix_node.inputs[0].default_value = 0.0
		mix_node.inputs[6].default_value = base_color
		links.new(attr_node.outputs["Color"], mix_node.inputs[7])
		links.new(mix_node.outputs[2], bsdf.inputs["Base Color"])

	return mat


def assign_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
	if obj.data is None:
		return
	obj.data.materials.clear()
	obj.data.materials.append(mat)


def add_bevel_modifier(obj: bpy.types.Object, width: float = 0.010, segments: int = 2, angle_limit: float = 32.0) -> None:
	bev = obj.modifiers.new(name="Bevel", type="BEVEL")
	bev.width = width
	bev.segments = segments
	bev.limit_method = "ANGLE"
	bev.angle_limit = math.radians(angle_limit)


def add_subsurf_modifier(obj: bpy.types.Object, levels: int = 1) -> None:
	sub = obj.modifiers.new(name="Subsurf", type="SUBSURF")
	sub.levels = levels
	sub.render_levels = levels


def apply_all_modifiers(obj: bpy.types.Object) -> None:
	bpy.context.view_layer.objects.active = obj
	for mod in list(obj.modifiers):
		try:
			bpy.ops.object.modifier_apply(modifier=mod.name)
		except RuntimeError:
			pass


# ---------------------------------------------------------------------------
# Geometry Primitives & Builders (Blender Space: X=Starboard, -Y=Bow/Snout, +Z=Up)
# ---------------------------------------------------------------------------

def create_box(
	name: str,
	center: Vec3,
	size: Vec3,
	mat: bpy.types.Material,
	rotation_euler: Vec3 = (0.0, 0.0, 0.0),
	bevel_width: float = 0.008,
	bevel_segments: int = 1,
	subdiv_cuts: int = 0,
) -> bpy.types.Object:
	mesh = bpy.data.meshes.new(name + "_mesh")
	obj = bpy.data.objects.new(name, mesh)
	bpy.context.collection.objects.link(obj)

	bm = bmesh.new()
	bmesh.ops.create_cube(bm, size=1.0)
	bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
	if subdiv_cuts > 0:
		bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=subdiv_cuts, use_grid_fill=True)
	bm.to_mesh(mesh)
	bm.free()

	obj.location = Vector(center)
	obj.rotation_euler = rotation_euler
	assign_material(obj, mat)
	if bevel_width > 0.0:
		add_bevel_modifier(obj, width=bevel_width, segments=bevel_segments)
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
	rings: int = 1,
) -> bpy.types.Object:
	v0 = Vector(p_start)
	v1 = Vector(p_end)
	diff = v1 - v0
	length = max(diff.length, 1e-4)
	mid = (v0 + v1) * 0.5

	mesh = bpy.data.meshes.new(name + "_mesh")
	obj = bpy.data.objects.new(name, mesh)
	bpy.context.collection.objects.link(obj)

	bm = bmesh.new()
	ring_verts: List[List[bmesh.types.BMVert]] = []
	steps = max(1, rings)
	for r_i in range(steps + 1):
		t = float(r_i) / float(steps)
		z_local = (t - 0.5) * length
		rad = lerp(r_start, r_end, t)
		ring: List[bmesh.types.BMVert] = []
		for s_i in range(segments):
			ang = (2.0 * math.pi * float(s_i)) / float(segments)
			ring.append(bm.verts.new((math.cos(ang) * rad, math.sin(ang) * rad, z_local)))
		ring_verts.append(ring)

	for r_i in range(steps):
		r0 = ring_verts[r_i]
		r1 = ring_verts[r_i + 1]
		for s_i in range(segments):
			ns = (s_i + 1) % segments
			bm.faces.new((r0[s_i], r0[ns], r1[ns], r1[s_i]))

	if cap_ends:
		if r_start > 1e-5:
			c_bot = bm.verts.new((0.0, 0.0, -0.5 * length))
			for s_i in range(segments):
				ns = (s_i + 1) % segments
				bm.faces.new((ring_verts[0][ns], ring_verts[0][s_i], c_bot))
		if r_end > 1e-5:
			c_top = bm.verts.new((0.0, 0.0, 0.5 * length))
			for s_i in range(segments):
				ns = (s_i + 1) % segments
				bm.faces.new((ring_verts[-1][s_i], ring_verts[-1][ns], c_top))

	bm.to_mesh(mesh)
	bm.free()

	obj.location = mid
	if diff.length > 1e-5:
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
	major_segments: int = 24,
	minor_segments: int = 12,
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
	resolution_u: int = 10,
	bevel_resolution: int = 2,
	cyclic: bool = False,
	taper_end: float = 1.0,
) -> bpy.types.Object:
	curve_data = bpy.data.curves.new(name=name + "_curve", type="CURVE")
	curve_data.dimensions = "3D"
	curve_data.resolution_u = resolution_u
	curve_data.bevel_depth = bevel_depth
	curve_data.bevel_resolution = bevel_resolution
	curve_data.use_fill_caps = True

	spline = curve_data.splines.new(type="POLY")
	spline.points.add(len(points) - 1)
	n_pts = max(1, len(points) - 1)
	for idx, pt in enumerate(points):
		t = float(idx) / float(n_pts)
		spline.points[idx].co = (pt[0], pt[1], pt[2], 1.0)
		spline.points[idx].radius = lerp(1.0, taper_end, t)
	spline.use_cyclic_u = cyclic

	obj = bpy.data.objects.new(name, curve_data)
	bpy.context.collection.objects.link(obj)
	assign_material(obj, mat)
	return obj


def catenary_points(p0: Vec3, p1: Vec3, sag: float, steps: int = 14, sway_x: float = 0.0) -> List[Vec3]:
	v0 = Vector(p0)
	v1 = Vector(p1)
	pts: List[Vec3] = []
	for i in range(steps + 1):
		t = i / float(steps)
		pos = v0.lerp(v1, t)
		arc = 4.0 * t * (1.0 - t)
		pos.z -= arc * sag
		pos.x += arc * sway_x
		pts.append((pos.x, pos.y, pos.z))
	return pts


def create_barnacle_cluster(
	name: str,
	base_pos: Vec3,
	normal_dir: Vec3,
	count: int,
	spread: float,
	scale_base: float,
	mat: bpy.types.Material,
	seed: int,
) -> bpy.types.Object:
	mesh = bpy.data.meshes.new(name + "_mesh")
	obj = bpy.data.objects.new(name, mesh)
	bpy.context.collection.objects.link(obj)
	assign_material(obj, mat)

	bm = bmesh.new()
	n_vec = Vector(normal_dir).normalized()
	up_ref = Vector((0.0, 0.0, 1.0)) if abs(n_vec.z) < 0.9 else Vector((1.0, 0.0, 0.0))
	t1 = n_vec.cross(up_ref).normalized()
	t2 = n_vec.cross(t1).normalized()
	center_v = Vector(base_pos)

	segs = 10
	for b_i in range(count):
		h1 = hash3(seed + b_i * 3.1, b_i * 7.3, 1.9)
		h2 = hash3(seed + b_i * 5.7, b_i * 2.1, 4.3)
		h3 = hash3(seed + b_i * 9.3, b_i * 4.9, 8.1)
		ang = h1 * 2.0 * math.pi
		dist = (0.15 + 0.85 * math.sqrt(h2)) * spread if b_i > 0 else 0.0
		offset = t1 * (math.cos(ang) * dist) + t2 * (math.sin(ang) * dist)
		b_origin = center_v + offset - n_vec * (0.015 * scale_base)

		r_bot = scale_base * (0.55 + 0.65 * h3)
		r_top = r_bot * 0.44
		r_in = r_top * 0.58
		height = r_bot * (0.85 + 0.45 * h1)

		ring_bot: List[bmesh.types.BMVert] = []
		ring_mid: List[bmesh.types.BMVert] = []
		ring_top: List[bmesh.types.BMVert] = []
		ring_in: List[bmesh.types.BMVert] = []
		for s in range(segs):
			sa = (2.0 * math.pi * float(s)) / float(segs)
			rib = 1.0 + 0.14 * math.sin(sa * 5.0 + h2 * 6.0)
			radial = (t1 * math.cos(sa) + t2 * math.sin(sa)) * rib
			ring_bot.append(bm.verts.new(b_origin + radial * r_bot))
			ring_mid.append(bm.verts.new(b_origin + radial * (r_bot * 0.76) + n_vec * (height * 0.52)))
			ring_top.append(bm.verts.new(b_origin + radial * r_top + n_vec * height))
			ring_in.append(bm.verts.new(b_origin + radial * r_in + n_vec * (height * 0.35)))

		c_pit = bm.verts.new(b_origin + n_vec * (height * 0.18))
		for s in range(segs):
			ns = (s + 1) % segs
			bm.faces.new((ring_bot[s], ring_bot[ns], ring_mid[ns], ring_mid[s]))
			bm.faces.new((ring_mid[s], ring_mid[ns], ring_top[ns], ring_top[s]))
			bm.faces.new((ring_top[s], ring_top[ns], ring_in[ns], ring_in[s]))
			bm.faces.new((ring_in[s], ring_in[ns], c_pit))

	bm.to_mesh(mesh)
	bm.free()
	return obj


# ---------------------------------------------------------------------------
# MODEL 1: GHOST TRAWLER (`enemy_ghost_trawler.glb` — 25,000+ Tris, 18+ Sub-Assemblies)
# ---------------------------------------------------------------------------

def build_ghost_trawler_model(output_glb_path: str) -> None:
	clear_scene()

	# Material Palette for Ghost Trawler
	mats: Dict[str, bpy.types.Material] = {
		"HullIron": create_pbr_material("HullIron", (0.09, 0.12, 0.14, 1.0), metallic=0.62, roughness=0.58, coat_weight=0.85, coat_roughness=0.08, use_vertex_color=True),
		"RustKeel": create_pbr_material("RustKeel", (0.24, 0.08, 0.06, 1.0), metallic=0.30, roughness=0.78, coat_weight=0.95, coat_roughness=0.05, use_vertex_color=True),
		"DeckWood": create_pbr_material("DeckWood", (0.14, 0.10, 0.07, 1.0), metallic=0.02, roughness=0.84, coat_weight=0.65, coat_roughness=0.12, use_vertex_color=True),
		"CabinPaint": create_pbr_material("CabinPaint", (0.26, 0.30, 0.31, 1.0), metallic=0.08, roughness=0.76, coat_weight=0.55, coat_roughness=0.14, use_vertex_color=True),
		"DarkMetal": create_pbr_material("DarkMetal", (0.06, 0.07, 0.08, 1.0), metallic=0.82, roughness=0.42, coat_weight=0.80, coat_roughness=0.06, use_vertex_color=True),
		"TarnishedBrass": create_pbr_material("TarnishedBrass", (0.48, 0.36, 0.18, 1.0), metallic=0.86, roughness=0.36, coat_weight=0.85, coat_roughness=0.05, use_vertex_color=True),
		"BarnacleShell": create_pbr_material("BarnacleShell", (0.34, 0.36, 0.33, 1.0), metallic=0.05, roughness=0.86, coat_weight=0.90, coat_roughness=0.06, use_vertex_color=True),
		"CoralGrowth": create_pbr_material("CoralGrowth", (0.38, 0.14, 0.16, 1.0), metallic=0.04, roughness=0.65, coat_weight=1.0, coat_roughness=0.04, use_vertex_color=True),
		"KelpNet": create_pbr_material("KelpNet", (0.06, 0.14, 0.10, 1.0), metallic=0.02, roughness=0.52, coat_weight=1.0, coat_roughness=0.04, use_vertex_color=True),
		"LifeRing": create_pbr_material("LifeRing", (0.52, 0.14, 0.08, 1.0), metallic=0.0, roughness=0.72, coat_weight=0.5, coat_roughness=0.15, use_vertex_color=True),
		"WindowGlow": create_pbr_material("WindowGlow", (1.0, 0.68, 0.26, 1.0), metallic=0.0, roughness=0.12, coat_weight=1.0, coat_roughness=0.02, emission_color=(1.0, 0.62, 0.20, 1.0), emission_strength=4.5, use_vertex_color=False),
		"SearchlightLens": create_pbr_material("SearchlightLens", (1.0, 0.88, 0.62, 1.0), metallic=0.0, roughness=0.06, coat_weight=1.0, coat_roughness=0.01, emission_color=(1.0, 0.84, 0.52, 1.0), emission_strength=7.5, use_vertex_color=False),
	}

	objects: List[bpy.types.Object] = []

	# -----------------------------------------------------------------------
	# Sub-Assembly 1 & 2: Multi-Station Ribbed & Plated Hull + Lower Keel
	# -----------------------------------------------------------------------
	stations = [
		(-3.15,  0.06, 0.000,  0.08, 0.008, 0.014, 0.62, 0.032, 1.18, 0.045),
		(-2.90, -0.22, 0.024, -0.08, 0.140, 0.220, 0.58, 0.340, 1.12, 0.460),
		(-2.55, -0.42, 0.046, -0.16, 0.320, 0.450, 0.54, 0.630, 1.05, 0.780),
		(-2.10, -0.52, 0.062, -0.21, 0.540, 0.710, 0.50, 0.900, 0.98, 1.030),
		(-1.55, -0.56, 0.075, -0.24, 0.740, 0.910, 0.47, 1.070, 0.92, 1.160),
		(-0.95, -0.58, 0.082, -0.25, 0.860, 1.030, 0.45, 1.160, 0.87, 1.210),
		(-0.35, -0.58, 0.085, -0.25, 0.910, 1.080, 0.44, 1.190, 0.83, 1.220),
		( 0.25, -0.58, 0.085, -0.25, 0.920, 1.090, 0.43, 1.190, 0.80, 1.210),
		( 0.85, -0.56, 0.082, -0.24, 0.890, 1.060, 0.43, 1.160, 0.78, 1.180),
		( 1.40, -0.53, 0.075, -0.21, 0.840, 1.010, 0.44, 1.110, 0.77, 1.140),
		( 1.90, -0.49, 0.068, -0.17, 0.780, 0.950, 0.45, 1.050, 0.78, 1.080),
		( 2.35, -0.44, 0.062, -0.14, 0.710, 0.880, 0.46, 0.980, 0.80, 1.020),
		( 2.75, -0.39, 0.055, -0.11, 0.650, 0.810, 0.48, 0.920, 0.83, 0.960),
	]
	waterline_z = 0.08
	deck_z = 0.42

	# A. Upper Steel Hull Shell with SUBSURF(2) + SOLIDIFY + BEVEL
	upper_mesh = bpy.data.meshes.new("GhostUpperHull_mesh")
	upper_obj = bpy.data.objects.new("GhostUpperHull", upper_mesh)
	bpy.context.collection.objects.link(upper_obj)
	assign_material(upper_obj, mats["HullIron"])

	bm_up = bmesh.new()
	rings_up: List[List[bmesh.types.BMVert]] = []
	for st in stations:
		y, _, _, _, _, wl_w, mid_z, mid_w, sheer_z, sheer_w = st
		# Subtle eldritch structural slump/warp
		warp_x = 0.025 * math.sin(y * 0.9)
		warp_z = -0.018 * math.cos(y * 0.7)
		rings_up.append([
			bm_up.verts.new((-sheer_w + warp_x, y, sheer_z + warp_z)),
			bm_up.verts.new((-mid_w + warp_x, y, mid_z + warp_z)),
			bm_up.verts.new((-wl_w + warp_x, y, waterline_z)),
			bm_up.verts.new((wl_w + warp_x, y, waterline_z)),
			bm_up.verts.new((mid_w + warp_x, y, mid_z + warp_z)),
			bm_up.verts.new((sheer_w + warp_x, y, sheer_z + warp_z)),
		])

	for i in range(len(stations) - 1):
		r0, r1 = rings_up[i], rings_up[i + 1]
		bm_up.faces.new((r0[0], r0[1], r1[1], r1[0]))
		bm_up.faces.new((r0[1], r0[2], r1[2], r1[1]))
		bm_up.faces.new((r0[3], r0[4], r1[4], r1[3]))
		bm_up.faces.new((r0[4], r0[5], r1[5], r1[4]))

	tr = rings_up[-1]
	y_tr = stations[-1][0]
	v_tr_wl = bm_up.verts.new((0.0, y_tr, waterline_z))
	v_tr_mid = bm_up.verts.new((0.0, y_tr, stations[-1][6]))
	v_tr_sh = bm_up.verts.new((0.0, y_tr, stations[-1][8]))
	bm_up.faces.new((tr[2], v_tr_wl, v_tr_mid, tr[1]))
	bm_up.faces.new((tr[1], v_tr_mid, v_tr_sh, tr[0]))
	bm_up.faces.new((v_tr_wl, tr[3], tr[4], v_tr_mid))
	bm_up.faces.new((v_tr_mid, tr[4], tr[5], v_tr_sh))

	bw = rings_up[0]
	bm_up.faces.new((bw[0], bw[5], bw[4], bw[1]))
	bm_up.faces.new((bw[1], bw[4], bw[3], bw[2]))
	bmesh.ops.recalc_face_normals(bm_up, faces=bm_up.faces)
	bm_up.to_mesh(upper_mesh)
	bm_up.free()

	add_subsurf_modifier(upper_obj, levels=1)
	sol_up = upper_obj.modifiers.new(name="Solidify", type="SOLIDIFY")
	sol_up.thickness = 0.065
	sol_up.offset = -1.0
	add_bevel_modifier(upper_obj, width=0.012, segments=1)
	objects.append(upper_obj)

	# B. Lower Anti-Fouling Keel Hull (RustKeel) with SUBSURF(1)
	lower_mesh = bpy.data.meshes.new("GhostLowerKeel_mesh")
	lower_obj = bpy.data.objects.new("GhostLowerKeel", lower_mesh)
	bpy.context.collection.objects.link(lower_obj)
	assign_material(lower_obj, mats["RustKeel"])

	bm_lo = bmesh.new()
	rings_lo: List[List[bmesh.types.BMVert]] = []
	for st in stations:
		y, keel_z, keel_w, chine_z, chine_w, wl_w, _, _, _, _ = st
		rings_lo.append([
			bm_lo.verts.new((-wl_w, y, waterline_z + 0.02)),
			bm_lo.verts.new((-chine_w, y, chine_z)),
			bm_lo.verts.new((-keel_w, y, keel_z)),
			bm_lo.verts.new((keel_w, y, keel_z)),
			bm_lo.verts.new((chine_w, y, chine_z)),
			bm_lo.verts.new((wl_w, y, waterline_z + 0.02)),
		])
	for i in range(len(stations) - 1):
		r0, r1 = rings_lo[i], rings_lo[i + 1]
		for k in range(5):
			bm_lo.faces.new((r0[k], r0[k + 1], r1[k + 1], r1[k]))
	bmesh.ops.recalc_face_normals(bm_lo, faces=bm_lo.faces)
	bm_lo.to_mesh(lower_mesh)
	bm_lo.free()
	add_subsurf_modifier(lower_obj, levels=1)
	objects.append(lower_obj)

	# -----------------------------------------------------------------------
	# Sub-Assembly 3: Raised Riveted Steel Strake Bands & Internal Hull Ribs
	# -----------------------------------------------------------------------
	for z_band, w_scale in [(0.26, 1.015), (0.52, 1.022), (0.76, 1.018)]:
		for side in (-1.0, 1.0):
			strake_pts: List[Vec3] = []
			for st in stations:
				y, _, _, _, _, wl_w, mid_z, mid_w, sheer_z, sheer_w = st
				t_z = clamp01((z_band - waterline_z) / max(0.1, sheer_z - waterline_z))
				w_interp = lerp(wl_w, sheer_w, t_z) * w_scale
				z_actual = lerp(waterline_z, sheer_z, t_z)
				strake_pts.append((side * w_interp, y, z_actual))
			objects.append(
				create_curve_cable(
					f"RivetedStrake_{side:.0f}_{z_band:.2f}",
					strake_pts,
					bevel_depth=0.024,
					mat=mats["DarkMetal"],
					resolution_u=6,
				)
			)

	# Heavy timber rub-rails along the upper gunwale sheer
	for side in (-1.0, 1.0):
		rub_pts: List[Vec3] = []
		for st in stations:
			y, _, _, _, _, _, _, _, sheer_z, sheer_w = st
			rub_pts.append((side * (sheer_w + 0.035), y, sheer_z - 0.04))
		objects.append(
			create_curve_cable(
				f"TimberRubRail_{side:.0f}",
				rub_pts,
				bevel_depth=0.036,
				mat=mats["DeckWood"],
				resolution_u=6,
			)
		)

	# Exposed internal bulwark ribs along port & starboard deck edges
	for r_idx in range(12):
		ry = -2.40 + r_idx * 0.42
		t_st = clamp01((ry + 3.15) / 5.90)
		rx = lerp(0.45, 1.08, math.sin(t_st * math.pi * 0.82))
		for side in (-1.0, 1.0):
			objects.append(
				create_box(
					f"BulwarkRib_{side:.0f}_{r_idx}",
					(side * (rx - 0.04), ry, 0.65),
					(0.05, 0.05, 0.46),
					mats["HullIron"],
					rotation_euler=(0.0, side * math.radians(6.0), 0.0),
					bevel_width=0.006,
				)
			)

	# -----------------------------------------------------------------------
	# Sub-Assembly 4: Jagged Reinforced Iron Ramming Prow + Barnacles & Coral
	# -----------------------------------------------------------------------
	# Heavy iron prow spine & 5 horizontal jagged ramming blades at the bow (-3.45 .. -2.55)
	objects.append(
		create_cylinder_between(
			"RammingProwSpine",
			(0.0, -3.48, 0.95),
			(0.0, -2.85, -0.38),
			0.075,
			0.115,
			mats["DarkMetal"],
			segments=12,
			rings=6,
		)
	)
	for b_i in range(5):
		bz = -0.12 + b_i * 0.24
		by_tip = -3.44 + b_i * 0.03
		bw_back = 0.24 + b_i * 0.06
		for side in (-1.0, 1.0):
			objects.append(
				create_cylinder_between(
					f"RamBlade_{b_i}_{side:.0f}",
					(0.0, by_tip, bz),
					(side * bw_back, -2.55, bz - 0.03),
					0.025,
					0.055,
					mats["DarkMetal"],
					segments=8,
					rings=3,
				)
			)
		# Forward serrated ramming spike tooth
		objects.append(
			create_cylinder_between(
				f"RamProwSpike_{b_i}",
				(0.0, by_tip + 0.08, bz),
				(0.0, by_tip - 0.28, bz + 0.04),
				0.048,
				0.006,
				mats["DarkMetal"],
				segments=8,
			)
		)

	# Giant clustered barnacles & twisted deep-sea coral tubers encrusting the bow & waterline
	barnacle_sites = [
		((-0.22, -2.82, 0.18), (-0.7, -0.7, 0.1), 16, 0.22, 0.055),
		(( 0.24, -2.78, 0.14), ( 0.7, -0.7, 0.1), 16, 0.22, 0.055),
		((-0.58, -2.15, 0.12), (-0.9, -0.4, 0.1), 14, 0.26, 0.060),
		(( 0.62, -2.05, 0.15), ( 0.9, -0.4, 0.1), 14, 0.26, 0.060),
		((-1.02, -0.85, 0.14), (-1.0,  0.0, 0.1), 14, 0.28, 0.062),
		(( 1.04, -0.65, 0.12), ( 1.0,  0.0, 0.1), 14, 0.28, 0.062),
		((-0.98,  0.95, 0.12), (-1.0,  0.1, 0.1), 12, 0.25, 0.058),
		(( 0.96,  1.15, 0.14), ( 1.0,  0.1, 0.1), 12, 0.25, 0.058),
	]
	for idx, (bpos, bnorm, bcnt, bspr, bsc) in enumerate(barnacle_sites):
		objects.append(
			create_barnacle_cluster(
				f"HullBarnacleCluster_{idx}",
				bpos,
				bnorm,
				count=bcnt,
				spread=bspr,
				scale_base=bsc,
				mat=mats["BarnacleShell"],
				seed=100 + idx * 17,
			)
		)

	# Twisted deep-sea coral tubers on the bow & prow
	for c_i in range(8):
		side = -1.0 if (c_i % 2 == 0) else 1.0
		cy_base = -2.95 + (c_i // 2) * 0.24
		cz_base = 0.08 + (c_i % 3) * 0.18
		cx_base = side * (0.16 + (c_i // 2) * 0.12)
		tuber_pts: List[Vec3] = []
		for step in range(8):
			t = step / 7.0
			tx = cx_base + side * (t * 0.26 + 0.05 * math.sin(t * 9.0 + c_i))
			ty = cy_base - t * 0.18 + 0.04 * math.cos(t * 7.0 + c_i)
			tz = cz_base + t * 0.28 + 0.04 * math.sin(t * 6.0)
			tuber_pts.append((tx, ty, tz))
		objects.append(
			create_curve_cable(
				f"CoralTuber_{c_i}",
				tuber_pts,
				bevel_depth=0.034,
				mat=mats["CoralGrowth"],
				resolution_u=8,
				taper_end=0.22,
			)
		)

	# -----------------------------------------------------------------------
	# Sub-Assembly 5: Bow Hawsepipes & Hanging Rusted Anchor Chains
	# -----------------------------------------------------------------------
	for side in (-1.0, 1.0):
		hx, hy, hz = side * 0.42, -2.52, 0.78
		objects.append(
			create_torus(
				f"HawsepipeLip_{side:.0f}",
				(hx, hy, hz),
				major_radius=0.085,
				minor_radius=0.026,
				mat=mats["DarkMetal"],
				rotation_euler=(math.radians(20.0), side * math.radians(58.0), 0.0),
				major_segments=16,
				minor_segments=8,
			)
		)
		for link_i in range(10):
			lz = hz - 0.06 - link_i * 0.068
			lx = hx + side * (0.04 + 0.015 * math.sin(link_i * 0.7))
			ly = hy + 0.02 * link_i
			rot_y = math.radians(90.0) if (link_i % 2 == 0) else 0.0
			objects.append(
				create_torus(
					f"BowAnchorChain_{side:.0f}_{link_i}",
					(lx, ly, lz),
					major_radius=0.045,
					minor_radius=0.014,
					mat=mats["RustKeel"],
					rotation_euler=(math.radians(85.0), rot_y, 0.0),
					major_segments=12,
					minor_segments=6,
				)
			)

	# -----------------------------------------------------------------------
	# Sub-Assembly 6: Warped Individual Timber Deck Planks & Coaming Hatch
	# -----------------------------------------------------------------------
	num_planks = 14
	for p_i in range(num_planks):
		px = -1.04 + p_i * 0.16
		dist_x = abs(px)
		y_start = -2.65 + (dist_x ** 1.45) * 1.45
		y_end = 2.68
		p_len = max(0.4, y_end - y_start)
		py_mid = 0.5 * (y_start + y_end)
		warp_z = 0.008 * math.sin(p_i * 1.7)
		objects.append(
			create_box(
				f"DeckPlank_{p_i}",
				(px, py_mid, deck_z + warp_z),
				(0.142, p_len, 0.045),
				mats["DeckWood"],
				rotation_euler=(math.radians(0.4 * math.cos(p_i)), math.radians(0.6 * math.sin(p_i)), 0.0),
				bevel_width=0.005,
				subdiv_cuts=0,
			)
		)

	# Aft Fish-Hold Coaming Hatch with iron bars
	objects.append(
		create_box("FishHoldCoaming", (0.0, 0.95, deck_z + 0.11), (1.05, 1.15, 0.18), mats["HullIron"], bevel_width=0.012, subdiv_cuts=1)
	)
	for h_i in range(4):
		hx = -0.36 + h_i * 0.24
		objects.append(
			create_box(f"HatchCoverPlank_{h_i}", (hx, 0.95, deck_z + 0.22), (0.21, 1.08, 0.04), mats["DeckWood"], bevel_width=0.006)
		)

	# -----------------------------------------------------------------------
	# Sub-Assembly 7 & 8: Detailed Wheelhouse Cabin, Mullions, Storm-Planks & Watertight Door
	# -----------------------------------------------------------------------
	cab_y = -0.78
	cab_z = deck_z + 0.72
	# Slumped cabin main structure (2.2 deg list for weathered eldritch feel)
	cab_rot = (math.radians(-1.2), math.radians(2.1), math.radians(0.8))
	objects.append(
		create_box("WheelhouseBody", (0.0, cab_y, cab_z), (1.42, 1.48, 1.38), mats["CabinPaint"], rotation_euler=cab_rot, bevel_width=0.015, subdiv_cuts=2)
	)
	# Overhanging cabin roof brow
	objects.append(
		create_box("WheelhouseRoof", (0.0, cab_y - 0.04, deck_z + 1.44), (1.58, 1.68, 0.09), mats["HullIron"], rotation_euler=cab_rot, bevel_width=0.012, subdiv_cuts=2)
	)

	# Emissive Interior Glowing Window Planes (`WindowGlow` material slot)
	# Front windshield panes (3 panes)
	for w_i in (-1, 0, 1):
		wx = w_i * 0.40
		objects.append(
			create_box(f"FrontWindowGlass_{w_i}", (wx, cab_y - 0.745, deck_z + 1.02), (0.32, 0.02, 0.38), mats["WindowGlow"], rotation_euler=cab_rot, bevel_width=0.002)
		)
		# Framed window surround & vertical mullions
		objects.append(
			create_box(f"FrontWindowFrameTop_{w_i}", (wx, cab_y - 0.76, deck_z + 1.22), (0.36, 0.04, 0.035), mats["DarkMetal"], rotation_euler=cab_rot, bevel_width=0.004)
		)
		objects.append(
			create_box(f"FrontWindowFrameBot_{w_i}", (wx, cab_y - 0.76, deck_z + 0.82), (0.36, 0.04, 0.035), mats["DarkMetal"], rotation_euler=cab_rot, bevel_width=0.004)
		)
		objects.append(
			create_box(f"FrontWindowMullionV_{w_i}", (wx, cab_y - 0.76, deck_z + 1.02), (0.025, 0.035, 0.38), mats["DarkMetal"], rotation_euler=cab_rot, bevel_width=0.003)
		)

	# Side wheelhouse windows (2 per side) + mullions
	for side in (-1.0, 1.0):
		for wy_off in (-0.32, 0.26):
			objects.append(
				create_box(
					f"SideWindowGlass_{side:.0f}_{wy_off:.2f}",
					(side * 0.715, cab_y + wy_off, deck_z + 1.02),
					(0.02, 0.42, 0.36),
					mats["WindowGlow"],
					rotation_euler=cab_rot,
					bevel_width=0.002,
				)
			)
			objects.append(
				create_box(
					f"SideWindowMullionH_{side:.0f}_{wy_off:.2f}",
					(side * 0.73, cab_y + wy_off, deck_z + 1.02),
					(0.035, 0.44, 0.026),
					mats["DarkMetal"],
					rotation_euler=cab_rot,
					bevel_width=0.003,
				)
			)

	# Wooden storm-plank boards nailed diagonally across broken panes
	storm_planks = [
		((-0.38, cab_y - 0.775, deck_z + 1.04), (0.46, 0.03, 0.075), (0.0, math.radians(24.0), 0.0)),
		(( 0.36, cab_y - 0.775, deck_z + 0.98), (0.44, 0.03, 0.070), (0.0, math.radians(-19.0), 0.0)),
		((-0.74, cab_y - 0.30,  deck_z + 1.03), (0.03, 0.50, 0.075), (math.radians(22.0), 0.0, 0.0)),
		(( 0.74, cab_y + 0.25,  deck_z + 1.01), (0.03, 0.48, 0.070), (math.radians(-25.0), 0.0, 0.0)),
	]
	for sp_idx, (sp_pos, sp_sz, sp_rot) in enumerate(storm_planks):
		objects.append(
			create_box(f"StormPlankBoard_{sp_idx}", sp_pos, sp_sz, mats["DeckWood"], rotation_euler=sp_rot, bevel_width=0.004)
		)

	# Heavy Iron Watertight Door on aft cabin wall with wheel-dog latches & hinges
	door_y = cab_y + 0.75
	objects.append(
		create_box("WatertightDoorSlab", (0.0, door_y, deck_z + 0.58), (0.58, 0.05, 1.06), mats["HullIron"], rotation_euler=cab_rot, bevel_width=0.012)
	)
	objects.append(
		create_torus(
			"WatertightDogWheel",
			(0.0, door_y + 0.045, deck_z + 0.60),
			major_radius=0.12,
			minor_radius=0.018,
			mat=mats["TarnishedBrass"],
			rotation_euler=(math.radians(90.0), 0.0, 0.0),
			major_segments=16,
			minor_segments=8,
		)
	)
	for latch_z in (deck_z + 0.28, deck_z + 0.58, deck_z + 0.88):
		objects.append(
			create_box(f"DoorDogLatch_{latch_z:.2f}", (0.28, door_y + 0.035, latch_z), (0.09, 0.03, 0.035), mats["DarkMetal"], bevel_width=0.004)
		)

	# Life-rings mounted on port and starboard cabin walls
	for side in (-1.0, 1.0):
		objects.append(
			create_torus(
				f"CabinLifeRing_{side:.0f}",
				(side * 0.75, cab_y + 0.02, deck_z + 0.54),
				major_radius=0.22,
				minor_radius=0.055,
				mat=mats["LifeRing"],
				rotation_euler=(0.0, math.radians(90.0), 0.0),
				major_segments=20,
				minor_segments=10,
			)
		)

	# -----------------------------------------------------------------------
	# Sub-Assembly 9, 10 & 11: Roof Searchlight with Cooling Fins, Twin Foghorns & Smokestack
	# -----------------------------------------------------------------------
	roof_z = deck_z + 1.49
	sl_y = cab_y - 0.52
	# Gimbaled pedestal & yoke
	objects.append(
		create_cylinder_between("SearchlightPedestal", (0.0, sl_y, roof_z), (0.0, sl_y, roof_z + 0.22), 0.11, 0.07, mats["DarkMetal"], segments=14)
	)
	for side in (-1.0, 1.0):
		objects.append(
			create_box(f"SearchlightYokeArm_{side:.0f}", (side * 0.17, sl_y, roof_z + 0.34), (0.03, 0.06, 0.26), mats["TarnishedBrass"], bevel_width=0.004)
		)
	# Searchlight barrel + 5 radial cooling fins + emissive front lens
	objects.append(
		create_cylinder_between("SearchlightBarrel", (0.0, sl_y + 0.20, roof_z + 0.42), (0.0, sl_y - 0.24, roof_z + 0.40), 0.15, 0.17, mats["TarnishedBrass"], segments=20, rings=3)
	)
	for fin_i in range(5):
		fy = sl_y + 0.15 - fin_i * 0.075
		objects.append(
			create_torus(
				f"SearchlightCoolingFin_{fin_i}",
				(0.0, fy, roof_z + 0.41),
				major_radius=0.175,
				minor_radius=0.012,
				mat=mats["DarkMetal"],
				rotation_euler=(math.radians(90.0), 0.0, 0.0),
				major_segments=18,
				minor_segments=6,
			)
		)
	objects.append(
		create_cylinder_between("SearchlightFrontLens", (0.0, sl_y - 0.23, roof_z + 0.40), (0.0, sl_y - 0.26, roof_z + 0.40), 0.155, 0.155, mats["SearchlightLens"], segments=20)
	)

	# Twin Rusted Brass Foghorn Trumpets on cabin roof
	for side in (-1.0, 1.0):
		hx = side * 0.46
		objects.append(
			create_cylinder_between(
				f"FoghornTrumpet_{side:.0f}",
				(hx, cab_y - 0.15, roof_z + 0.08),
				(hx, cab_y - 0.62, roof_z + 0.11),
				0.028,
				0.095,
				mats["TarnishedBrass"],
				segments=14,
				rings=3,
			)
		)

	# Tilted Ribbed Iron Exhaust Smokestack with Wire Spark-Arrestor Cage & Guy-Wires
	stack_base = (0.44, cab_y + 0.45, roof_z - 0.05)
	stack_top = (0.52, cab_y + 0.72, roof_z + 1.42)
	objects.append(
		create_cylinder_between("ExhaustSmokestack", stack_base, stack_top, 0.16, 0.14, mats["HullIron"], segments=18, rings=6)
	)
	for r_i in range(4):
		t_r = (r_i + 1) / 5.0
		rx = lerp(stack_base[0], stack_top[0], t_r)
		ry = lerp(stack_base[1], stack_top[1], t_r)
		rz = lerp(stack_base[2], stack_top[2], t_r)
		objects.append(
			create_torus(
				f"SmokestackRibCollar_{r_i}",
				(rx, ry, rz),
				major_radius=0.162,
				minor_radius=0.018,
				mat=mats["DarkMetal"],
				rotation_euler=(math.radians(10.0), math.radians(4.0), 0.0),
				major_segments=16,
				minor_segments=8,
			)
		)
	# Wire spark-arrestor cage crown at top of smokestack
	for cage_i in range(6):
		ang = (math.pi * float(cage_i)) / 6.0
		dx = math.cos(ang) * 0.14
		dy = math.sin(ang) * 0.14
		cage_pts = [
			(stack_top[0] - dx, stack_top[1] - dy, stack_top[2] - 0.02),
			(stack_top[0] - dx * 0.7, stack_top[1] - dy * 0.7, stack_top[2] + 0.18),
			(stack_top[0], stack_top[1], stack_top[2] + 0.25),
			(stack_top[0] + dx * 0.7, stack_top[1] + dy * 0.7, stack_top[2] + 0.18),
			(stack_top[0] + dx, stack_top[1] + dy, stack_top[2] - 0.02),
		]
		objects.append(
			create_curve_cable(f"SparkArrestorWire_{cage_i}", cage_pts, bevel_depth=0.009, mat=mats["DarkMetal"], resolution_u=6)
		)
	# Smokestack guy-wires
	for gw_pt in [(-0.25, cab_y + 0.10, roof_z), (0.68, cab_y - 0.25, roof_z), (0.68, cab_y + 0.72, roof_z)]:
		objects.append(
			create_curve_cable(
				f"StackGuyWire_{gw_pt[0]:.2f}_{gw_pt[1]:.2f}",
				catenary_points((stack_top[0], stack_top[1], stack_top[2] - 0.25), gw_pt, sag=0.03, steps=8),
				bevel_depth=0.008,
				mat=mats["DarkMetal"],
				resolution_u=6,
			)
		)

	# -----------------------------------------------------------------------
	# Sub-Assembly 12 & 13: Forward Steel Lattice Mast, Crosstrees, Pulley Blocks & Swinging Lantern
	# -----------------------------------------------------------------------
	mast_y = -1.85
	mast_top_z = deck_z + 3.45
	objects.append(
		create_cylinder_between("ForwardMainMast", (0.0, mast_y, deck_z), (0.0, mast_y + 0.18, mast_top_z), 0.095, 0.055, mats["HullIron"], segments=14, rings=6)
	)
	# Forward lattice tripod struts & horizontal lattice rungs
	for side in (-1.0, 1.0):
		objects.append(
			create_cylinder_between(
				f"MastLatticeLeg_{side:.0f}",
				(side * 0.42, mast_y + 0.28, deck_z),
				(0.0, mast_y + 0.14, mast_top_z - 0.45),
				0.045,
				0.032,
				mats["DarkMetal"],
				segments=10,
			)
		)
	for rung_i in range(6):
		t_m = (rung_i + 1) / 7.0
		rz = lerp(deck_z + 0.35, mast_top_z - 0.55, t_m)
		rw = lerp(0.40, 0.06, t_m)
		ry = lerp(mast_y + 0.26, mast_y + 0.14, t_m)
		objects.append(
			create_cylinder_between(f"MastLatticeRung_{rung_i}", (-rw, ry, rz), (rw, ry, rz), 0.022, 0.022, mats["DarkMetal"], segments=8)
		)

	# Mast Crosstree Yardarm & Pulley Blocks
	yard_z = mast_top_z - 0.35
	objects.append(
		create_cylinder_between("MastCrosstreeYardarm", (-1.15, mast_y + 0.15, yard_z), (1.15, mast_y + 0.15, yard_z), 0.032, 0.032, mats["HullIron"], segments=12)
	)
	for px_off in (-0.95, -0.48, 0.48, 0.95):
		objects.append(
			create_torus(
				f"MastPulleySheave_{px_off:.2f}",
				(px_off, mast_y + 0.15, yard_z - 0.08),
				major_radius=0.055,
				minor_radius=0.018,
				mat=mats["TarnishedBrass"],
				rotation_euler=(0.0, math.radians(90.0), 0.0),
				major_segments=14,
				minor_segments=8,
			)
		)

	# Swinging Iron Lantern Cage hanging from forward mast stay
	lant_pos = (0.0, mast_y - 0.38, yard_z - 0.28)
	objects.append(
		create_cylinder_between("MastLanternArm", (0.0, mast_y + 0.14, yard_z + 0.10), (lant_pos[0], lant_pos[1], lant_pos[2] + 0.18), 0.025, 0.018, mats["DarkMetal"], segments=8)
	)
	objects.append(
		create_cylinder_between("MastLanternGlass", (lant_pos[0], lant_pos[1], lant_pos[2] + 0.12), (lant_pos[0], lant_pos[1], lant_pos[2] - 0.10), 0.075, 0.065, mats["WindowGlow"], segments=14)
	)
	for bar_i in range(4):
		ba = (math.pi * 0.5) * bar_i
		bx = lant_pos[0] + math.cos(ba) * 0.09
		by = lant_pos[1] + math.sin(ba) * 0.09
		objects.append(
			create_cylinder_between(f"MastLanternCageBar_{bar_i}", (bx, by, lant_pos[2] + 0.15), (bx, by, lant_pos[2] - 0.13), 0.010, 0.010, mats["DarkMetal"], segments=6)
		)

	# -----------------------------------------------------------------------
	# Sub-Assembly 14, 15, 16, 17 & 18: Stern A-Frame Gantry, Dual-Drum Winch,
	# Bollards, Outrigger Booms, Tangled Netting & Hanging Kelp Tendrils
	# -----------------------------------------------------------------------
	# Dual-Drum Hydraulic Trawl Winch wound with steel cable
	winch_y = 0.18
	winch_z = deck_z + 0.28
	for side in (-1.0, 1.0):
		objects.append(
			create_box(f"WinchSideHousing_{side:.0f}", (side * 0.56, winch_y, winch_z), (0.09, 0.52, 0.48), mats["HullIron"], bevel_width=0.010)
		)
		# Wound cable drum with helical cable ridges
		drum_x0 = side * 0.10
		drum_x1 = side * 0.50
		objects.append(
			create_cylinder_between(f"WinchCableDrum_{side:.0f}", (drum_x0, winch_y, winch_z), (drum_x1, winch_y, winch_z), 0.19, 0.19, mats["DarkMetal"], segments=20, rings=4)
		)
		for coil_i in range(7):
			cx = lerp(drum_x0, drum_x1, (coil_i + 0.5) / 7.0)
			objects.append(
				create_torus(
					f"WinchWoundCable_{side:.0f}_{coil_i}",
					(cx, winch_y, winch_z),
					major_radius=0.195,
					minor_radius=0.018,
					mat=mats["RustKeel"],
					rotation_euler=(0.0, math.radians(90.0), 0.0),
					major_segments=18,
					minor_segments=8,
				)
			)

	# Heavy Bolted Steel A-Frame Gantry at Stern
	gantry_y_bot = 2.45
	gantry_y_top = 2.88
	gantry_z_top = deck_z + 2.35
	for side in (-1.0, 1.0):
		objects.append(
			create_cylinder_between(
				f"SternAFrameMainLeg_{side:.0f}",
				(side * 0.88, gantry_y_bot, deck_z),
				(side * 0.52, gantry_y_top, gantry_z_top),
				0.075,
				0.062,
				mats["HullIron"],
				segments=12,
				rings=4,
			)
		)
		objects.append(
			create_cylinder_between(
				f"SternAFrameForwardBrace_{side:.0f}",
				(side * 0.92, 1.48, deck_z),
				(side * 0.62, gantry_y_top - 0.14, gantry_z_top - 0.38),
				0.052,
				0.045,
				mats["DarkMetal"],
				segments=10,
			)
		)
	objects.append(
		create_box("SternAFrameCrossbeam", (0.0, gantry_y_top, gantry_z_top), (1.32, 0.14, 0.14), mats["HullIron"], bevel_width=0.012)
	)
	# Stern hanging work lantern on A-frame crossbeam
	objects.append(
		create_cylinder_between("SternWorkLanternGlass", (0.0, gantry_y_top, gantry_z_top - 0.08), (0.0, gantry_y_top, gantry_z_top - 0.28), 0.075, 0.062, mats["WindowGlow"], segments=14)
	)

	# Rusted mooring bollards/cleats along gunwales
	for b_y in (-2.05, 0.45, 2.25):
		for side in (-1.0, 1.0):
			bx = side * 0.86 if b_y > -1.5 else side * 0.58
			objects.append(
				create_box(f"BollardBase_{side:.0f}_{b_y:.2f}", (bx, b_y, deck_z + 0.04), (0.16, 0.28, 0.05), mats["DarkMetal"], bevel_width=0.005)
			)
			for post_off in (-0.07, 0.07):
				objects.append(
					create_cylinder_between(
						f"BollardPost_{side:.0f}_{b_y:.2f}_{post_off:.2f}",
						(bx, b_y + post_off, deck_z + 0.05),
						(bx, b_y + post_off, deck_z + 0.24),
						0.036,
						0.042,
						mats["RustKeel"],
						segments=10,
					)
				)

	# Outrigger Trawl Booms extending port & starboard with Tattered Fishing Nets & Organic Kelp Tendrils
	for side in (-1.0, 1.0):
		boom_base = (side * 0.85, 0.55, deck_z + 0.65)
		boom_tip = (side * 2.35, 0.85, deck_z + 1.65)
		objects.append(
			create_cylinder_between(f"OutriggerBoom_{side:.0f}", boom_base, boom_tip, 0.055, 0.035, mats["HullIron"], segments=12, rings=4)
		)
		# Stay wire from mast top to outrigger tip
		objects.append(
			create_curve_cable(
				f"OutriggerStayWire_{side:.0f}",
				catenary_points((0.0, mast_y + 0.16, mast_top_z - 0.15), boom_tip, sag=0.14, steps=12),
				bevel_depth=0.011,
				mat=mats["DarkMetal"],
				resolution_u=8,
			)
		)
		# Trawl cable from winch drum to stern gantry sheave
		objects.append(
			create_curve_cable(
				f"SternWinchCable_{side:.0f}",
				catenary_points((side * 0.30, winch_y, winch_z + 0.15), (side * 0.48, gantry_y_top, gantry_z_top - 0.12), sag=0.08, steps=12),
				bevel_depth=0.015,
				mat=mats["DarkMetal"],
				resolution_u=8,
			)
		)

		# Tattered dark fishing net mesh curtain + organic kelp tendrils hanging from outrigger boom
		for n_i in range(6):
			t_b = (n_i + 1) / 7.0
			nx = lerp(boom_base[0], boom_tip[0], t_b)
			ny = lerp(boom_base[1], boom_tip[1], t_b)
			nz = lerp(boom_base[2], boom_tip[2], t_b)
			drop_len = 0.65 + 0.55 * math.sin(t_b * math.pi)
			kelp_pts: List[Vec3] = []
			for k_s in range(7):
				kt = k_s / 6.0
				kx = nx + side * 0.08 * math.sin(kt * 5.0 + n_i)
				ky = ny + 0.14 * kt + 0.05 * math.cos(kt * 6.0 + n_i)
				kz = nz - kt * drop_len
				kelp_pts.append((kx, ky, kz))
			objects.append(
				create_curve_cable(
					f"OutriggerKelpTendril_{side:.0f}_{n_i}",
					kelp_pts,
					bevel_depth=0.026,
					mat=mats["KelpNet"],
					resolution_u=8,
					taper_end=0.15,
				)
			)
		# Cross-strands forming tangled fishing net web between hanging strands
		for row_i in range(3):
			rz_drop = 0.18 + row_i * 0.22
			p_net_0 = (
				lerp(boom_base[0], boom_tip[0], 0.18),
				lerp(boom_base[1], boom_tip[1], 0.18) + 0.05 * row_i,
				lerp(boom_base[2], boom_tip[2], 0.18) - rz_drop,
			)
			p_net_1 = (
				lerp(boom_base[0], boom_tip[0], 0.92),
				lerp(boom_base[1], boom_tip[1], 0.92) + 0.05 * row_i,
				lerp(boom_base[2], boom_tip[2], 0.92) - rz_drop,
			)
			objects.append(
				create_curve_cable(
					f"OutriggerTangledNetCord_{side:.0f}_{row_i}",
					catenary_points(p_net_0, p_net_1, sag=0.12, steps=10),
					bevel_depth=0.014,
					mat=mats["KelpNet"],
					resolution_u=8,
				)
			)

	# Drooping catenary rigging wires from forward mast to bow & cabin
	rigging_pairs = [
		((0.0, mast_y + 0.16, mast_top_z - 0.10), (0.0, -3.10, 1.15), 0.08),
		((0.0, mast_y + 0.16, mast_top_z - 0.15), (-0.52, gantry_y_top, gantry_z_top), 0.22),
		((0.0, mast_y + 0.16, mast_top_z - 0.15), ( 0.52, gantry_y_top, gantry_z_top), 0.22),
		((-0.95, mast_y + 0.15, yard_z), (-0.72, cab_y - 0.45, roof_z), 0.10),
		(( 0.95, mast_y + 0.15, yard_z), ( 0.72, cab_y - 0.45, roof_z), 0.10),
	]
	for r_idx, (rp0, rp1, rsag) in enumerate(rigging_pairs):
		objects.append(
			create_curve_cable(
				f"RiggingCatenaryCable_{r_idx}",
				catenary_points(rp0, rp1, sag=rsag, steps=12),
				bevel_depth=0.011,
				mat=mats["DarkMetal"],
				resolution_u=8,
			)
		)

	finalize_paint_and_export_glb(
		objects=objects,
		mesh_name="GhostTrawlerMesh",
		output_glb_path=output_glb_path,
		target_min_tris=25500,
		palette_map={
			"HullIron": (0.11, 0.14, 0.17, 1.0),
			"RustKeel": (0.28, 0.10, 0.07, 1.0),
			"DeckWood": (0.18, 0.13, 0.09, 1.0),
			"CabinPaint": (0.30, 0.34, 0.35, 1.0),
			"DarkMetal": (0.08, 0.09, 0.11, 1.0),
			"TarnishedBrass": (0.54, 0.41, 0.20, 1.0),
			"BarnacleShell": (0.40, 0.42, 0.38, 1.0),
			"CoralGrowth": (0.46, 0.16, 0.18, 1.0),
			"KelpNet": (0.08, 0.18, 0.13, 1.0),
			"LifeRing": (0.58, 0.16, 0.09, 1.0),
			"WindowGlow": (1.0, 0.68, 0.26, 1.0),
			"SearchlightLens": (1.0, 0.88, 0.62, 1.0),
		},
	)


# ---------------------------------------------------------------------------
# MODEL 2: ABYSSAL LEVIATHAN HEAD (`enemy_leviathan_head.glb` — 25,000+ Tris)
# ---------------------------------------------------------------------------

def build_leviathan_head_model(output_glb_path: str) -> None:
	clear_scene()

	mats: Dict[str, bpy.types.Material] = {
		"ChitinCarapace": create_pbr_material("ChitinCarapace", (0.07, 0.13, 0.15, 1.0), metallic=0.32, roughness=0.22, coat_weight=1.0, coat_roughness=0.04, use_vertex_color=True),
		"OralCavity": create_pbr_material("OralCavity", (0.32, 0.05, 0.07, 1.0), metallic=0.08, roughness=0.16, coat_weight=1.0, coat_roughness=0.03, use_vertex_color=True),
		"IvoryFangs": create_pbr_material("IvoryFangs", (0.82, 0.78, 0.66, 1.0), metallic=0.12, roughness=0.18, coat_weight=1.0, coat_roughness=0.03, use_vertex_color=True),
		"PleatedFinWeb": create_pbr_material("PleatedFinWeb", (0.10, 0.22, 0.24, 1.0), metallic=0.18, roughness=0.26, coat_weight=1.0, coat_roughness=0.04, use_vertex_color=True),
		"BarnacleEncrust": create_pbr_material("BarnacleEncrust", (0.36, 0.38, 0.34, 1.0), metallic=0.05, roughness=0.84, coat_weight=0.90, coat_roughness=0.06, use_vertex_color=True),
		"EyeGlow": create_pbr_material("EyeGlow", (0.95, 0.74, 0.18, 1.0), metallic=0.2, roughness=0.10, coat_weight=1.0, coat_roughness=0.02, emission_color=(0.95, 0.72, 0.16, 1.0), emission_strength=6.5, use_vertex_color=False),
		"EyeCornea": create_pbr_material("EyeCornea", (0.14, 0.22, 0.24, 1.0), metallic=0.0, roughness=0.02, coat_weight=1.0, coat_roughness=0.01, use_vertex_color=False),
		"BioVeinGlow": create_pbr_material("BioVeinGlow", (0.14, 0.92, 0.84, 1.0), metallic=0.0, roughness=0.12, coat_weight=1.0, coat_roughness=0.02, emission_color=(0.12, 0.88, 0.78, 1.0), emission_strength=5.8, use_vertex_color=False),
	}

	objects: List[bpy.types.Object] = []

	# -----------------------------------------------------------------------
	# 1. Sculpted Upper Cranium & Recessed Crimson Oral Cavity (High-Res Loft)
	# -----------------------------------------------------------------------
	# Snout tip at y = -2.45, widening across orbital brow (-1.20), neck collar at y = +1.85
	skull_mesh = bpy.data.meshes.new("LeviathanSkull_mesh")
	skull_obj = bpy.data.objects.new("LeviathanSkull", skull_mesh)
	bpy.context.collection.objects.link(skull_obj)
	skull_obj.data.materials.append(mats["ChitinCarapace"])
	skull_obj.data.materials.append(mats["OralCavity"])
	skull_obj.data.materials.append(mats["BioVeinGlow"])

	bm_sk = bmesh.new()
	n_u = 42
	n_v = 36
	skull_rings: List[List[bmesh.types.BMVert]] = []

	for u_i in range(n_u):
		u = float(u_i) / float(n_u - 1)
		y = lerp(-2.45, 1.85, u)
		# Longitudinal profile of armored cranium
		env_w = math.sin(clamp01((u + 0.04) / 1.04) * math.pi * 0.82) ** 0.65
		rx = 1.38 * env_w + 0.14 * math.exp(-((u - 0.34) / 0.14) ** 2)
		rz_top = 1.25 * env_w + 0.22 * math.exp(-((u - 0.38) / 0.18) ** 2)
		# Gaping upper jaw arch for u < 0.56
		jaw_open = smoothstep(0.58, 0.05, u)
		z_arch_floor = 0.12 + 0.48 * jaw_open * math.sin(clamp01(u / 0.56) * math.pi * 0.85)

		ring: List[bmesh.types.BMVert] = []
		for v_i in range(n_v):
			ang = (2.0 * math.pi * float(v_i)) / float(n_v)
			ca = math.cos(ang)
			sa = math.sin(ang)

			# Dorsal carapace ridges & battle scars
			dorsal_ridge = 0.0
			if sa > 0.0:
				dorsal_ridge = 0.09 * (math.sin(ang * 5.0) ** 2) * sa
				# Overlapping transverse carapace plate steps + battle scar gouges
				plate_step = 0.045 * ((u * 9.0) - math.floor(u * 9.0))
				scar = -0.055 * math.exp(-((u - 0.32) * 14.0 + ca * 3.5) ** 2) - 0.045 * math.exp(-((u - 0.52) * 12.0 - ca * 4.0) ** 2)
				dorsal_ridge += plate_step + scar

			px = ca * (rx + dorsal_ridge * 0.6)
			if sa >= -0.15:
				pz = z_arch_floor + (sa + 0.15) / 1.15 * (rz_top + dorsal_ridge)
			else:
				# Recessed crimson oral palate cavity under upper jaw
				if u < 0.55:
					palate_depth = 0.34 * jaw_open * abs(sa + 0.15)
					throat_fold = 0.035 * math.sin(ca * 18.0 + u * 22.0)
					pz = z_arch_floor + palate_depth + throat_fold
				else:
					pz = z_arch_floor + sa * (rz_top * 0.68)

			ring.append(bm_sk.verts.new((px, y, pz)))
		skull_rings.append(ring)

	for u_i in range(n_u - 1):
		u = float(u_i) / float(n_u - 1)
		r0, r1 = skull_rings[u_i], skull_rings[u_i + 1]
		for v_i in range(n_v):
			nv = (v_i + 1) % n_v
			ang = (2.0 * math.pi * float(v_i)) / float(n_v)
			sa = math.sin(ang)
			f = bm_sk.faces.new((r0[v_i], r0[nv], r1[nv], r1[v_i]))
			if u < 0.54 and sa < -0.22:
				f.material_index = 1  # OralCavity
			elif abs(sa - 0.18) < 0.08 and (u_i % 3 == 0):
				f.material_index = 2  # BioVeinGlow lateral sensory groove
			else:
				f.material_index = 0  # ChitinCarapace

	# Close snout tip & posterior neck cap
	c_snout = bm_sk.verts.new((0.0, -2.48, 0.22))
	c_neck = bm_sk.verts.new((0.0, 1.85, 0.25))
	for v_i in range(n_v):
		nv = (v_i + 1) % n_v
		bm_sk.faces.new((skull_rings[0][nv], skull_rings[0][v_i], c_snout))
		f_n = bm_sk.faces.new((skull_rings[-1][v_i], skull_rings[-1][nv], c_neck))
		f_n.material_index = 1
	bmesh.ops.recalc_face_normals(bm_sk, faces=bm_sk.faces)
	bm_sk.to_mesh(skull_mesh)
	bm_sk.free()
	objects.append(skull_obj)

	# -----------------------------------------------------------------------
	# 2. Overlapping Dorsal Chitin Armor Plates (8 Layered Beveled Plates)
	# -----------------------------------------------------------------------
	for p_i in range(8):
		t_p = p_i / 7.0
		py = lerp(-1.85, 1.55, t_p)
		pw = lerp(0.55, 1.32, math.sin(clamp01((t_p + 0.15) * 0.9) * math.pi))
		pz = lerp(0.78, 1.38, math.sin(clamp01((t_p + 0.12) * 0.88) * math.pi))
		objects.append(
			create_box(
				f"DorsalArmorPlate_{p_i}",
				(0.0, py, pz),
				(pw, 0.48, 0.14),
				mats["ChitinCarapace"],
				rotation_euler=(math.radians(-14.0), 0.0, 0.0),
				bevel_width=0.022,
				bevel_segments=2,
				subdiv_cuts=2,
			)
		)

	# -----------------------------------------------------------------------
	# 3. Heavy Articulated Lower Jaw (`Mandible`) with Crimson Throat Folds
	# -----------------------------------------------------------------------
	jaw_mesh = bpy.data.meshes.new("LeviathanMandible_mesh")
	jaw_obj = bpy.data.objects.new("LeviathanMandible", jaw_mesh)
	bpy.context.collection.objects.link(jaw_obj)
	jaw_obj.data.materials.append(mats["ChitinCarapace"])
	jaw_obj.data.materials.append(mats["OralCavity"])

	bm_jw = bmesh.new()
	jw_u = 32
	jw_v = 28
	jw_rings: List[List[bmesh.types.BMVert]] = []
	for u_i in range(jw_u):
		u = float(u_i) / float(jw_u - 1)
		# Hinged from y = -2.25 (chin tip dropped down to z = -0.82) back to jaw hinge at y = +0.20 (z = -0.15)
		y = lerp(-2.25, 0.25, u)
		w_j = lerp(0.22, 1.18, u ** 0.62)
		z_base = lerp(-0.82, -0.16, u) - 0.14 * math.sin(u * math.pi)
		ring_j: List[bmesh.types.BMVert] = []
		for v_i in range(jw_v):
			ang = (2.0 * math.pi * float(v_i)) / float(jw_v)
			ca = math.cos(ang)
			sa = math.sin(ang)
			px = ca * w_j
			if sa > 0.0:
				# Concave crimson oral floor with fleshy throat folds
				fold = 0.03 * math.sin(ca * 14.0 + u * 16.0)
				pz = z_base - sa * 0.12 + fold
			else:
				# Keeled armored chin underside with bony spikes
				chin_keel = 0.08 * (abs(ca) < 0.35) * math.sin(u * 24.0)
				pz = z_base + sa * (0.28 + 0.12 * u) - abs(chin_keel)
			ring_j.append(bm_jw.verts.new((px, y, pz)))
		jw_rings.append(ring_j)

	for u_i in range(jw_u - 1):
		r0, r1 = jw_rings[u_i], jw_rings[u_i + 1]
		for v_i in range(jw_v):
			nv = (v_i + 1) % jw_v
			ang = (2.0 * math.pi * float(v_i)) / float(jw_v)
			f = bm_jw.faces.new((r0[v_i], r0[nv], r1[nv], r1[v_i]))
			f.material_index = 1 if math.sin(ang) > 0.15 else 0

	c_chin = bm_jw.verts.new((0.0, -2.32, -0.80))
	c_hinge = bm_jw.verts.new((0.0, 0.28, -0.18))
	for v_i in range(jw_v):
		nv = (v_i + 1) % jw_v
		bm_jw.faces.new((jw_rings[0][nv], jw_rings[0][v_i], c_chin))
		bm_jw.faces.new((jw_rings[-1][v_i], jw_rings[-1][nv], c_hinge))
	bmesh.ops.recalc_face_normals(bm_jw, faces=bm_jw.faces)
	bm_jw.to_mesh(jaw_mesh)
	bm_jw.free()
	objects.append(jaw_obj)

	# -----------------------------------------------------------------------
	# 4. 48 Individually Modeled Inward-Curving Ivory Needle Fangs
	# -----------------------------------------------------------------------
	# Upper outer maxillary row (18 fangs), upper inner palatal row (12 fangs), lower mandibular row (18 fangs) = 48 fangs
	def build_curved_fang(name: str, base_pt: Vec3, tip_dir: Vec3, curve_back: Vec3, length: float, r_base: float) -> bpy.types.Object:
		v_b = Vector(base_pt)
		v_d = Vector(tip_dir).normalized()
		v_c = Vector(curve_back).normalized()
		pts: List[Vec3] = []
		for s in range(6):
			t = s / 5.0
			p = v_b + v_d * (length * t) + v_c * (length * 0.28 * (t * t))
			pts.append((p.x, p.y, p.z))
		return create_curve_cable(name, pts, bevel_depth=r_base, mat=mats["IvoryFangs"], resolution_u=6, bevel_resolution=3, taper_end=0.04)

	# Upper outer row (9 per side = 18)
	for f_i in range(9):
		t = f_i / 8.0
		fy = lerp(-2.32, -0.55, t)
		fx_abs = lerp(0.18, 0.96, t ** 0.72)
		fz = lerp(0.28, 0.36, math.sin(t * math.pi))
		flen = lerp(0.42, 0.22, t) * (1.15 if f_i in (1, 3) else 0.92)
		f_rad = lerp(0.038, 0.024, t)
		for side in (-1.0, 1.0):
			objects.append(
				build_curved_fang(
					f"UpperMaxillaryFang_{side:.0f}_{f_i}",
					(side * fx_abs, fy, fz),
					(-side * 0.18, -0.10, -1.0),
					(-side * 0.25, 0.85, 0.15),
					flen,
					f_rad,
				)
			)

	# Upper inner palatal row (6 per side = 12)
	for f_i in range(6):
		t = f_i / 5.0
		fy = lerp(-2.05, -0.75, t)
		fx_abs = lerp(0.12, 0.62, t ** 0.75)
		fz = 0.38
		flen = lerp(0.28, 0.18, t)
		for side in (-1.0, 1.0):
			objects.append(
				build_curved_fang(
					f"UpperPalatalFang_{side:.0f}_{f_i}",
					(side * fx_abs, fy, fz),
					(-side * 0.22, 0.15, -1.0),
					(0.0, 0.95, 0.10),
					flen,
					0.024,
				)
			)

	# Lower mandibular row (9 per side = 18)
	for f_i in range(9):
		t = f_i / 8.0
		fy = lerp(-2.18, -0.35, t)
		fx_abs = lerp(0.16, 0.88, t ** 0.68)
		fz = lerp(-0.76, -0.32, t)
		flen = lerp(0.44, 0.20, t) * (1.20 if f_i in (0, 2, 4) else 0.88)
		f_rad = lerp(0.036, 0.022, t)
		for side in (-1.0, 1.0):
			objects.append(
				build_curved_fang(
					f"LowerMandibleFang_{side:.0f}_{f_i}",
					(side * fx_abs, fy, fz),
					(-side * 0.15, -0.12, 1.0),
					(-side * 0.20, 0.90, -0.10),
					flen,
					f_rad,
				)
			)

	# -----------------------------------------------------------------------
	# 5. 5 Flared Gill Arches Per Side (10 Total) with Crimson Gill Filaments
	# -----------------------------------------------------------------------
	for side in (-1.0, 1.0):
		for g_i in range(5):
			gy = 0.35 + g_i * 0.28
			gx_base = side * (1.22 - g_i * 0.04)
			arch_pts: List[Vec3] = []
			for step in range(9):
				st = (step / 8.0) * 2.0 - 1.0
				az = 0.15 + st * 0.56
				ax = gx_base + side * (0.24 * (1.0 - st * st))
				ay = gy + 0.08 * (1.0 - st * st)
				arch_pts.append((ax, ay, az))
			objects.append(
				create_curve_cable(
					f"GillArchBone_{side:.0f}_{g_i}",
					arch_pts,
					bevel_depth=0.038,
					mat=mats["ChitinCarapace"],
					resolution_u=8,
				)
			)
			# Inner crimson gill filament frills along each gill arch
			fil_pts = [(p[0] - side * 0.05, p[1] + 0.04, p[2]) for p in arch_pts]
			objects.append(
				create_curve_cable(
					f"GillFilamentFrill_{side:.0f}_{g_i}",
					fil_pts,
					bevel_depth=0.032,
					mat=mats["OralCavity"],
					resolution_u=8,
				)
			)

	# -----------------------------------------------------------------------
	# 6. 4 Long Curling Sensory Whiskers / Barbels (2 Snout + 2 Chin)
	# -----------------------------------------------------------------------
	for side in (-1.0, 1.0):
		# Snout trailing sensory barbel
		snout_barbel_pts: List[Vec3] = []
		for s in range(16):
			t = s / 15.0
			bx = side * (0.32 + t * 0.95 + 0.18 * math.sin(t * 7.5))
			by = -2.05 + t * 2.65
			bz = 0.32 - t * 0.45 + 0.14 * math.cos(t * 6.5)
			snout_barbel_pts.append((bx, by, bz))
		objects.append(
			create_curve_cable(
				f"SnoutSensoryBarbel_{side:.0f}",
				snout_barbel_pts,
				bevel_depth=0.042,
				mat=mats["ChitinCarapace"],
				resolution_u=10,
				taper_end=0.08,
			)
		)
		# Chin curling sensory barbel
		chin_barbel_pts: List[Vec3] = []
		for s in range(16):
			t = s / 15.0
			bx = side * (0.24 + t * 0.65 + 0.15 * math.cos(t * 8.0))
			by = -1.95 + t * 2.35
			bz = -0.78 - t * 0.55 + 0.18 * math.sin(t * 7.0)
			chin_barbel_pts.append((bx, by, bz))
		objects.append(
			create_curve_cable(
				f"ChinSensoryBarbel_{side:.0f}",
				chin_barbel_pts,
				bevel_depth=0.036,
				mat=mats["ChitinCarapace"],
				resolution_u=10,
				taper_end=0.08,
			)
		)

	# -----------------------------------------------------------------------
	# 7. 6 Multi-Part Glassy Eyes (3 Pairs: Socket + Glowing Iris + Glossy Cornea Dome)
	# -----------------------------------------------------------------------
	eye_pairs = [
		(-1.55, 0.94, 0.86, 0.19),  # Primary forward predator pair protruding on supraorbital brow
		(-1.02, 1.18, 0.98, 0.16),  # Mid-brow lateral pair
		(-0.48, 1.28, 1.06, 0.14),  # Posterior temporal pair
	]
	for pair_idx, (ey, ex_abs, ez, erad) in enumerate(eye_pairs):
		for side in (-1.0, 1.0):
			ex = side * ex_abs
			# Recessed bony orbital socket ring
			objects.append(
				create_torus(
					f"EyeSocketBrow_{pair_idx}_{side:.0f}",
					(ex, ey, ez),
					major_radius=erad * 1.15,
					minor_radius=erad * 0.30,
					mat=mats["ChitinCarapace"],
					rotation_euler=(math.radians(18.0), side * math.radians(64.0), math.radians(-15.0)),
					major_segments=20,
					minor_segments=10,
				)
			)
			# Outer bulging glossy cornea scleral dome (`EyeCornea`, Roughness = 0.02, Coat Weight = 1.0)
			bpy.ops.mesh.primitive_uv_sphere_add(
				segments=18,
				ring_count=12,
				radius=erad * 0.95,
				location=(ex + side * (erad * 0.08), ey - erad * 0.04, ez + erad * 0.04),
			)
			cornea_obj = bpy.context.active_object
			cornea_obj.name = f"EyeCorneaDome_{pair_idx}_{side:.0f}"
			assign_material(cornea_obj, mats["EyeCornea"])
			objects.append(cornea_obj)

			# Prominent glowing amber/sickly-teal iris lens cap (`EyeGlow`, Roughness = 0.02, Coat Weight = 1.0)
			bpy.ops.mesh.primitive_uv_sphere_add(
				segments=20,
				ring_count=14,
				radius=erad * 0.82,
				location=(ex + side * (erad * 0.28), ey - erad * 0.12, ez + erad * 0.10),
			)
			iris_obj = bpy.context.active_object
			iris_obj.name = f"EyeInnerIris_{pair_idx}_{side:.0f}"
			assign_material(iris_obj, mats["EyeGlow"])
			objects.append(iris_obj)

	# -----------------------------------------------------------------------
	# 8. Tall Ribbed Bony Dorsal Fin Spines + Tattered Pleated Webbing + Barnacles
	# -----------------------------------------------------------------------
	spine_tips: List[Vec3] = []
	spine_bases: List[Vec3] = []
	num_spines = 9
	for s_i in range(num_spines):
		t = s_i / float(num_spines - 1)
		sy_base = lerp(-1.15, 1.72, t)
		sz_base = lerp(0.95, 1.18, math.sin(t * math.pi * 0.85))
		s_height = lerp(0.75, 1.45, math.sin((t * 0.85 + 0.1) * math.pi))
		sy_tip = sy_base + s_height * 0.42
		sz_tip = sz_base + s_height
		sx_tip = 0.06 * math.sin(s_i * 1.3)
		spine_bases.append((0.0, sy_base, sz_base))
		spine_tips.append((sx_tip, sy_tip, sz_tip))

		spine_pts: List[Vec3] = []
		for k in range(7):
			kt = k / 6.0
			spine_pts.append((
				sx_tip * (kt * kt),
				lerp(sy_base, sy_tip, kt) - 0.08 * math.sin(kt * math.pi),
				lerp(sz_base, sz_tip, kt),
			))
		objects.append(
			create_curve_cable(
				f"DorsalCrestSpine_{s_i}",
				spine_pts,
				bevel_depth=0.046,
				mat=mats["ChitinCarapace"],
				resolution_u=8,
				taper_end=0.14,
			)
		)

	# Pleated tattered webbing membrane connecting the dorsal spines
	web_mesh = bpy.data.meshes.new("LeviathanCrestWebbing_mesh")
	web_obj = bpy.data.objects.new("LeviathanCrestWebbing", web_mesh)
	bpy.context.collection.objects.link(web_obj)
	assign_material(web_obj, mats["PleatedFinWeb"])
	bm_web = bmesh.new()
	for s_i in range(num_spines - 1):
		b0, t0 = Vector(spine_bases[s_i]), Vector(spine_tips[s_i])
		b1, t1 = Vector(spine_bases[s_i + 1]), Vector(spine_tips[s_i + 1])
		cols = 6
		rows = 8
		grid: List[List[bmesh.types.BMVert]] = []
		for c in range(cols + 1):
			cu = c / float(cols)
			base_p = b0.lerp(b1, cu)
			tip_p = t0.lerp(t1, cu)
			# Scalloped tattered notch between spines
			scallop = 1.0 - 0.24 * math.sin(cu * math.pi)
			pleat_x = 0.035 * math.sin(cu * math.pi * 4.0)
			col_verts: List[bmesh.types.BMVert] = []
			for r in range(rows + 1):
				rv = (r / float(rows)) * scallop
				pos = base_p.lerp(tip_p, rv)
				pos.x += pleat_x * rv
				col_verts.append(bm_web.verts.new(pos))
			grid.append(col_verts)
		for c in range(cols):
			for r in range(rows):
				bm_web.faces.new((grid[c][r], grid[c + 1][r], grid[c + 1][r + 1], grid[c][r + 1]))
	bmesh.ops.recalc_face_normals(bm_web, faces=bm_web.faces)
	bm_web.to_mesh(web_mesh)
	bm_web.free()
	sol_web = web_obj.modifiers.new(name="Solidify", type="SOLIDIFY")
	sol_web.thickness = 0.022
	objects.append(web_obj)

	# Whale-barnacle clusters encrusting brow ridges and dorsal armor
	head_barnacles = [
		((-0.65, -0.75, 1.08), (-0.5, -0.2, 0.8), 14, 0.24, 0.062),
		(( 0.68, -0.68, 1.06), ( 0.5, -0.2, 0.8), 14, 0.24, 0.062),
		((-0.95,  0.42, 0.96), (-0.7,  0.1, 0.7), 16, 0.28, 0.068),
		(( 0.98,  0.48, 0.94), ( 0.7,  0.1, 0.7), 16, 0.28, 0.068),
		(( 0.00,  0.15, 1.34), ( 0.0,  0.0, 1.0), 14, 0.26, 0.064),
	]
	for b_idx, (bpos, bnorm, bcnt, bspr, bsc) in enumerate(head_barnacles):
		objects.append(
			create_barnacle_cluster(
				f"LeviathanHeadBarnacles_{b_idx}",
				bpos,
				bnorm,
				count=bcnt,
				spread=bspr,
				scale_base=bsc,
				mat=mats["BarnacleEncrust"],
				seed=300 + b_idx * 23,
			)
		)

	finalize_paint_and_export_glb(
		objects=objects,
		mesh_name="LeviathanHeadMesh",
		output_glb_path=output_glb_path,
		target_min_tris=25500,
		palette_map={
			"ChitinCarapace": (0.09, 0.16, 0.19, 1.0),
			"OralCavity": (0.38, 0.06, 0.08, 1.0),
			"IvoryFangs": (0.86, 0.82, 0.70, 1.0),
			"PleatedFinWeb": (0.12, 0.26, 0.28, 1.0),
			"BarnacleEncrust": (0.42, 0.44, 0.39, 1.0),
			"EyeGlow": (0.95, 0.74, 0.18, 1.0),
			"EyeCornea": (0.14, 0.22, 0.24, 1.0),
			"BioVeinGlow": (0.14, 0.92, 0.84, 1.0),
		},
	)


# ---------------------------------------------------------------------------
# MODEL 3: ABYSSAL LEVIATHAN COIL (`enemy_leviathan_coil.glb` — 20,000+ Tris)
# ---------------------------------------------------------------------------

def build_leviathan_coil_model(output_glb_path: str) -> None:
	clear_scene()

	mats: Dict[str, bpy.types.Material] = {
		"ChitinCarapace": create_pbr_material("ChitinCarapace", (0.07, 0.13, 0.15, 1.0), metallic=0.32, roughness=0.22, coat_weight=1.0, coat_roughness=0.04, use_vertex_color=True),
		"PleatedFinWeb": create_pbr_material("PleatedFinWeb", (0.10, 0.22, 0.24, 1.0), metallic=0.18, roughness=0.26, coat_weight=1.0, coat_roughness=0.04, use_vertex_color=True),
		"BarnacleEncrust": create_pbr_material("BarnacleEncrust", (0.36, 0.38, 0.34, 1.0), metallic=0.05, roughness=0.84, coat_weight=0.90, coat_roughness=0.06, use_vertex_color=True),
		"BioVeinGlow": create_pbr_material("BioVeinGlow", (0.14, 0.92, 0.84, 1.0), metallic=0.0, roughness=0.12, coat_weight=1.0, coat_roughness=0.02, emission_color=(0.12, 0.88, 0.78, 1.0), emission_strength=5.8, use_vertex_color=False),
	}

	objects: List[bpy.types.Object] = []

	# -----------------------------------------------------------------------
	# 1. Muscular Arched Body Coil Segment with Overlapping Diamond-Scale Relief
	#    and Recessed Bioluminescent Cyan-Teal Vein Grooves
	# -----------------------------------------------------------------------
	coil_mesh = bpy.data.meshes.new("LeviathanCoilBody_mesh")
	coil_obj = bpy.data.objects.new("LeviathanCoilBody", coil_mesh)
	bpy.context.collection.objects.link(coil_obj)
	coil_obj.data.materials.append(mats["ChitinCarapace"])
	coil_obj.data.materials.append(mats["BioVeinGlow"])

	bm_co = bmesh.new()
	n_u = 96
	n_v = 68
	coil_rings: List[List[bmesh.types.BMVert]] = []

	for u_i in range(n_u):
		u = float(u_i) / float(n_u - 1)
		y = lerp(-2.35, 2.35, u)
		# Muscular arch rising out of the water at u = 0.5 and tapering into water at ends
		arch_sin = math.sin(u * math.pi)
		z_spine = -0.65 + 1.65 * (arch_sin ** 0.85)
		x_sway = 0.24 * math.sin(u * math.pi * 2.0)
		rad_x = 0.42 + 0.68 * (arch_sin ** 0.55)
		rad_z = 0.46 + 0.74 * (arch_sin ** 0.55)

		ring: List[bmesh.types.BMVert] = []
		for v_i in range(n_v):
			ang = (2.0 * math.pi * float(v_i)) / float(n_v)
			ca = math.cos(ang)
			sa = math.sin(ang)

			# Overlapping diamond-scale relief along flanks
			d1 = math.sin(u * 48.0 * math.pi + ang * 14.0)
			d2 = math.sin(u * 48.0 * math.pi - ang * 14.0)
			diamond_scale = 0.032 * max(0.0, d1 * d2) * (0.4 + 0.6 * abs(ca))

			# Dorsal chitin ridge plates & recessed bioluminescent lateral vein groove
			dorsal_plate = 0.055 * (sa ** 3) * (0.5 + 0.5 * math.cos(u * 28.0 * math.pi)) if sa > 0.2 else 0.0
			vein_dist = abs(sa - 0.12 * math.sin(u * 4.0 * math.pi))
			vein_groove = -0.042 if vein_dist < 0.095 else 0.0

			disp = diamond_scale + dorsal_plate + vein_groove
			px = x_sway + ca * (rad_x + disp)
			pz = z_spine + sa * (rad_z + disp)
			ring.append(bm_co.verts.new((px, y, pz)))
		coil_rings.append(ring)

	for u_i in range(n_u - 1):
		u = float(u_i) / float(n_u - 1)
		r0, r1 = coil_rings[u_i], coil_rings[u_i + 1]
		for v_i in range(n_v):
			nv = (v_i + 1) % n_v
			ang = (2.0 * math.pi * float(v_i)) / float(n_v)
			sa = math.sin(ang)
			vein_dist = abs(sa - 0.12 * math.sin(u * 4.0 * math.pi))
			f = bm_co.faces.new((r0[v_i], r0[nv], r1[nv], r1[v_i]))
			if vein_dist < 0.085 or (sa > 0.72 and (u_i % 6 == 0)):
				f.material_index = 1  # BioVeinGlow
			else:
				f.material_index = 0  # ChitinCarapace

	c_front = bm_co.verts.new((0.0, -2.38, -0.65))
	c_back = bm_co.verts.new((0.0, 2.38, -0.65))
	for v_i in range(n_v):
		nv = (v_i + 1) % n_v
		bm_co.faces.new((coil_rings[0][nv], coil_rings[0][v_i], c_front))
		bm_co.faces.new((coil_rings[-1][v_i], coil_rings[-1][nv], c_back))
	bmesh.ops.recalc_face_normals(bm_co, faces=bm_co.faces)
	bm_co.to_mesh(coil_mesh)
	bm_co.free()
	objects.append(coil_obj)

	# -----------------------------------------------------------------------
	# 2. Row of Jagged Dorsal Fin Rays with Pleated Membrane Webbing Along Spine
	# -----------------------------------------------------------------------
	num_rays = 11
	ray_bases: List[Vec3] = []
	ray_tips: List[Vec3] = []
	for r_i in range(num_rays):
		u = (r_i + 0.5) / float(num_rays)
		ry = lerp(-1.95, 1.95, u)
		arch_sin = math.sin(u * math.pi)
		rz_spine = -0.65 + 1.65 * (arch_sin ** 0.85) + (0.46 + 0.74 * (arch_sin ** 0.55)) * 0.92
		rx_sway = 0.24 * math.sin(u * math.pi * 2.0)
		r_len = (0.38 + 0.78 * arch_sin)
		b_pt = (rx_sway, ry, rz_spine)
		t_pt = (rx_sway + 0.05 * math.sin(r_i), ry + r_len * 0.36, rz_spine + r_len)
		ray_bases.append(b_pt)
		ray_tips.append(t_pt)

		ray_pts: List[Vec3] = []
		for k in range(7):
			kt = k / 6.0
			ray_pts.append((
				lerp(b_pt[0], t_pt[0], kt),
				lerp(b_pt[1], t_pt[1], kt) - 0.06 * math.sin(kt * math.pi),
				lerp(b_pt[2], t_pt[2], kt),
			))
		objects.append(
			create_curve_cable(
				f"CoilDorsalFinRay_{r_i}",
				ray_pts,
				bevel_depth=0.038,
				mat=mats["ChitinCarapace"],
				resolution_u=8,
				taper_end=0.14,
			)
		)

	coil_web_mesh = bpy.data.meshes.new("CoilFinWebbing_mesh")
	coil_web_obj = bpy.data.objects.new("CoilFinWebbing", coil_web_mesh)
	bpy.context.collection.objects.link(coil_web_obj)
	assign_material(coil_web_obj, mats["PleatedFinWeb"])
	bm_cw = bmesh.new()
	for r_i in range(num_rays - 1):
		b0, t0 = Vector(ray_bases[r_i]), Vector(ray_tips[r_i])
		b1, t1 = Vector(ray_bases[r_i + 1]), Vector(ray_tips[r_i + 1])
		cols, rows = 8, 10
		grid: List[List[bmesh.types.BMVert]] = []
		for c in range(cols + 1):
			cu = c / float(cols)
			base_p = b0.lerp(b1, cu)
			tip_p = t0.lerp(t1, cu)
			scallop = 1.0 - 0.22 * math.sin(cu * math.pi)
			pleat_x = 0.03 * math.sin(cu * math.pi * 4.0)
			col_v: List[bmesh.types.BMVert] = []
			for r in range(rows + 1):
				rv = (r / float(rows)) * scallop
				p = base_p.lerp(tip_p, rv)
				p.x += pleat_x * rv
				col_v.append(bm_cw.verts.new(p))
			grid.append(col_v)
		for c in range(cols):
			for r in range(rows):
				bm_cw.faces.new((grid[c][r], grid[c + 1][r], grid[c + 1][r + 1], grid[c][r + 1]))
	bmesh.ops.recalc_face_normals(bm_cw, faces=bm_cw.faces)
	bm_cw.to_mesh(coil_web_mesh)
	bm_cw.free()
	sol_cw = coil_web_obj.modifiers.new(name="Solidify", type="SOLIDIFY")
	sol_cw.thickness = 0.020
	objects.append(coil_web_obj)

	# -----------------------------------------------------------------------
	# 3. Clusters of Rocky Whale-Barnacles Along Arched Flanks
	# -----------------------------------------------------------------------
	coil_barnacles = [
		((-0.82, -0.75, 0.72), (-0.8, -0.1, 0.5), 16, 0.28, 0.065),
		(( 0.92, -0.45, 0.88), ( 0.8,  0.0, 0.5), 16, 0.28, 0.065),
		((-0.96,  0.15, 0.96), (-0.8,  0.0, 0.6), 18, 0.30, 0.068),
		(( 0.86,  0.65, 0.78), ( 0.8,  0.1, 0.5), 16, 0.28, 0.065),
		((-0.62,  1.15, 0.48), (-0.8,  0.2, 0.4), 14, 0.24, 0.060),
		(( 0.58, -1.15, 0.46), ( 0.8, -0.2, 0.4), 14, 0.24, 0.060),
	]
	for cb_idx, (bpos, bnorm, bcnt, bspr, bsc) in enumerate(coil_barnacles):
		objects.append(
			create_barnacle_cluster(
				f"CoilBarnacles_{cb_idx}",
				bpos,
				bnorm,
				count=bcnt,
				spread=bspr,
				scale_base=bsc,
				mat=mats["BarnacleEncrust"],
				seed=500 + cb_idx * 31,
			)
		)

	finalize_paint_and_export_glb(
		objects=objects,
		mesh_name="LeviathanCoilMesh",
		output_glb_path=output_glb_path,
		target_min_tris=20500,
		palette_map={
			"ChitinCarapace": (0.09, 0.16, 0.19, 1.0),
			"PleatedFinWeb": (0.12, 0.26, 0.28, 1.0),
			"BarnacleEncrust": (0.42, 0.44, 0.39, 1.0),
			"BioVeinGlow": (0.14, 0.92, 0.84, 1.0),
		},
	)


# ---------------------------------------------------------------------------
# Topological Cavity Vertex-Color Painting (`Col`) & GLB Export Pipeline
# ---------------------------------------------------------------------------

def paint_cavity_vertex_colors(
	mesh: bpy.types.Mesh,
	palette_map: Dict[str, Color4],
) -> None:
	"""
	Creates the `Col` byte vertex color attribute on CORNER domain and paints:
	  - Material base color from `palette_map`
	  - Deep topological cavity ink (`vert_concavity > 0`) in crevices, ribs, scales & rivets
	  - Weathered edge highlights on sharp convex ridges (`vert_concavity < 0`)
	  - Wet dark waterline slime/barnacle gradient near z <= 0.20m
	"""
	while len(mesh.color_attributes) > 0:
		mesh.color_attributes.remove(mesh.color_attributes[0])

	col_attr = mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")

	verts = mesh.vertices
	loops = mesh.loops
	num_verts = len(verts)

	vert_mat_idx = [0] * num_verts
	vert_neighbors: List[List[int]] = [[] for _ in range(num_verts)]
	for edge in mesh.edges:
		v0, v1 = edge.vertices[0], edge.vertices[1]
		vert_neighbors[v0].append(v1)
		vert_neighbors[v1].append(v0)

	for poly in mesh.polygons:
		m_i = poly.material_index
		for v_i in poly.vertices:
			vert_mat_idx[v_i] = m_i

	vert_concavity: List[float] = [0.0] * num_verts
	for v_idx in range(num_verts):
		nbrs = vert_neighbors[v_idx]
		if not nbrs:
			continue
		v = verts[v_idx]
		avg_co = Vector((0.0, 0.0, 0.0))
		avg_len = 0.0
		for n_idx in nbrs:
			nco = verts[n_idx].co
			avg_co += nco
			avg_len += (nco - v.co).length
		inv_n = 1.0 / float(len(nbrs))
		avg_co *= inv_n
		avg_len = max(0.001, avg_len * inv_n)
		vert_concavity[v_idx] = (avg_co - v.co).dot(v.normal) / avg_len

	mat_names = [m.name if m is not None else "" for m in mesh.materials]
	ink_col: Color4 = (0.015, 0.020, 0.028, 1.0)
	ridge_col: Color4 = (0.62, 0.72, 0.76, 1.0)
	slime_col: Color4 = (0.04, 0.11, 0.09, 1.0)

	vert_colors: List[Color4] = [(0.5, 0.5, 0.5, 1.0)] * num_verts
	for v_idx in range(num_verts):
		v = verts[v_idx]
		vx, vy, vz = v.co.x, v.co.y, v.co.z
		m_idx = vert_mat_idx[v_idx]
		m_name = mat_names[m_idx] if 0 <= m_idx < len(mat_names) else ""
		base_c = palette_map.get(m_name, (0.25, 0.28, 0.30, 1.0))

		# Noise mottling
		n_val = fbm3d(vx * 2.2, vy * 2.2, vz * 2.2, octaves=3)
		c = lerp_color(base_c, (base_c[0] * 1.28, base_c[1] * 1.28, base_c[2] * 1.28, 1.0), (n_val - 0.35) * 0.65)

		# Waterline wet slime darkening near z in [-0.25, 0.25]
		wl_factor = 1.0 - smoothstep(0.0, 0.38, abs(vz - 0.05))
		c = lerp_color(c, slime_col, wl_factor * 0.38)

		# Topological cavity ink & convex edge highlight
		conc = vert_concavity[v_idx]
		if conc > 0.02:
			ink_t = clamp01((conc - 0.02) * 2.8)
			c = lerp_color(c, ink_col, ink_t * 0.78)
		elif conc < -0.04:
			ridge_t = clamp01((-conc - 0.04) * 2.2)
			c = lerp_color(c, ridge_col, ridge_t * 0.32)

		vert_colors[v_idx] = (clamp01(c[0]), clamp01(c[1]), clamp01(c[2]), 1.0)

	loop_flat: List[float] = [1.0] * (len(loops) * 4)
	for l_idx, loop in enumerate(loops):
		vc = vert_colors[loop.vertex_index]
		base_i = l_idx * 4
		loop_flat[base_i] = vc[0]
		loop_flat[base_i + 1] = vc[1]
		loop_flat[base_i + 2] = vc[2]
		loop_flat[base_i + 3] = 1.0

	col_attr.data.foreach_set("color", loop_flat)


def finalize_paint_and_export_glb(
	objects: List[bpy.types.Object],
	mesh_name: str,
	output_glb_path: str,
	target_min_tris: int,
	palette_map: Dict[str, Color4],
) -> None:
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

	joined_obj = bpy.context.active_object
	joined_obj.name = mesh_name
	joined_obj.data.name = mesh_name
	bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

	# Align longitudinal axis for glTF (+Y Up -> Godot -Z Forward) and triangulate
	bm = bmesh.new()
	bm.from_mesh(joined_obj.data)
	bmesh.ops.scale(bm, vec=Vector((1.0, -1.0, 1.0)), verts=bm.verts)
	bmesh.ops.reverse_faces(bm, faces=bm.faces)
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
	bmesh.ops.triangulate(bm, faces=bm.faces)
	bm.to_mesh(joined_obj.data)
	bm.free()

	for poly in joined_obj.data.polygons:
		poly.use_smooth = True

	paint_cavity_vertex_colors(joined_obj.data, palette_map)

	os.makedirs(os.path.dirname(output_glb_path), exist_ok=True)
	bpy.ops.export_scene.gltf(
		filepath=output_glb_path,
		export_format="GLB",
		export_apply=True,
		export_yup=True,
	)

	num_verts = len(joined_obj.data.vertices)
	num_tris = len(joined_obj.data.polygons)
	print(f"[Blender 5.4.0] Exported {mesh_name} -> {output_glb_path}")
	print(f"[Blender 5.4.0]   Vertices: {num_verts:,} | Triangles: {num_tris:,} (Target >= {target_min_tris:,}) | Materials: {len(joined_obj.data.materials)}")


def main() -> None:
	project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	enemies_dir = os.path.join(project_root, "assets", "models", "enemies")
	os.makedirs(enemies_dir, exist_ok=True)

	build_ghost_trawler_model(os.path.join(enemies_dir, "enemy_ghost_trawler.glb"))
	build_leviathan_head_model(os.path.join(enemies_dir, "enemy_leviathan_head.glb"))
	build_leviathan_coil_model(os.path.join(enemies_dir, "enemy_leviathan_coil.glb"))


if __name__ == "__main__":
	main()
