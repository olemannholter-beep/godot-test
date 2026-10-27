#!/usr/bin/env python3
"""
Headless Blender 5.4.0 Grounded Maritime POI & Landmark Builder (tools/blender_build_lovecraft_landmarks.py)

Generates 5 high-detail, stylized chiseled & ink-washed 3D maritime landmarks:
  1. res://assets/models/poi_sunken_shipwreck.glb
     - Half-submerged, listing rusted iron steamer/freighter bow, torn hull plating (Boolean breach),
       battered deckhouse with sputtering bulkhead lamp, tilted smokestack, and crooked mast rigging.
  2. res://assets/models/poi_sea_fort_tower.glb
     - Crooked timber-and-rusted-iron Maunsell-style stilt watchtower on cross-braced pilings,
       weathered plank shack with Boolean window cavities, boarding ladder, and hanging iron lantern.
  3. res://assets/models/poi_leviathan_ribcage.glb
     - Jagged displaced dark coastal rock skerry crowned with colossal, weathered ivory-grey curving
       ribcage bones, dorsal spine vertebrae, and cavernous jaw/skull of a beached deep-sea leviathan.
  4. res://assets/models/poi_derelict_lightship.glb
     - Unmanned, battered wooden lightship hull with warped timber strakes, torn sail/rigging,
       and a skeletal iron lattice beacon tower amidships.
  5. res://assets/models/rusted_warning_buoy.glb
     - Crooked, corroded iron lattice cage buoy for Blackwater Wharf harbor channel markers.

Usage:
  blender --background --python tools/blender_build_lovecraft_landmarks.py
"""

from __future__ import annotations

import math
import os
import random
from typing import Dict, List, Tuple

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector


def clear_scene() -> None:
	bpy.ops.object.select_all(action="SELECT")
	bpy.ops.object.delete(use_global=False)
	for mesh in list(bpy.data.meshes):
		bpy.data.meshes.remove(mesh)
	for curve in list(bpy.data.curves):
		bpy.data.curves.remove(curve)
	for mat in list(bpy.data.materials):
		bpy.data.materials.remove(mat)


def clamp01(v: float) -> float:
	return max(0.0, min(1.0, v))


def smoothstep(edge0: float, edge1: float, x: float) -> float:
	if abs(edge1 - edge0) < 1e-6:
		return 1.0 if x >= edge1 else 0.0
	t = clamp01((x - edge0) / (edge1 - edge0))
	return t * t * (3.0 - 2.0 * t)


def lerp_color(
	c0: Tuple[float, float, float, float],
	c1: Tuple[float, float, float, float],
	t: float,
) -> Tuple[float, float, float, float]:
	w = clamp01(t)
	return (
		c0[0] + (c1[0] - c0[0]) * w,
		c0[1] + (c1[1] - c0[1]) * w,
		c0[2] + (c1[2] - c0[2]) * w,
		c0[3] + (c1[3] - c0[3]) * w,
	)


def create_pbr_material(
	name: str,
	base_color: Tuple[float, float, float, float],
	metallic: float = 0.0,
	roughness: float = 0.8,
	emission_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
	emission_strength: float = 0.0,
) -> bpy.types.Material:
	mat = bpy.data.materials.new(name=name)
	mat.use_nodes = True
	nt = mat.node_tree
	nodes = nt.nodes
	links = nt.links

	bsdf = None
	for n in nodes:
		if n.type == "BSDF_PRINCIPLED":
			bsdf = n
			break
	if bsdf is None:
		bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")

	vcol_node = nodes.new(type="ShaderNodeVertexColor")
	vcol_node.layer_name = "Col"
	vcol_node.location = (-320, 220)
	links.new(vcol_node.outputs["Color"], bsdf.inputs["Base Color"])

	bsdf.inputs["Base Color"].default_value = base_color
	bsdf.inputs["Metallic"].default_value = metallic
	bsdf.inputs["Roughness"].default_value = roughness

	if emission_strength > 0.0:
		if "Emission Color" in bsdf.inputs:
			bsdf.inputs["Emission Color"].default_value = emission_color
		elif "Emission" in bsdf.inputs:
			bsdf.inputs["Emission"].default_value = emission_color
		if "Emission Strength" in bsdf.inputs:
			bsdf.inputs["Emission Strength"].default_value = emission_strength

	return mat


def add_bevel_modifier(obj: bpy.types.Object, width: float = 0.04, segments: int = 1) -> None:
	mod = obj.modifiers.new(name="ChiselBevel", type="BEVEL")
	mod.width = width
	mod.segments = segments
	mod.limit_method = "ANGLE"
	mod.angle_limit = math.radians(24.0)


def apply_all_modifiers(obj: bpy.types.Object) -> None:
	bpy.context.view_layer.objects.active = obj
	for mod in list(obj.modifiers):
		try:
			bpy.ops.object.modifier_apply(modifier=mod.name)
		except RuntimeError:
			pass


def assign_single_slot(obj: bpy.types.Object, mats: List[bpy.types.Material], slot_idx: int) -> None:
	obj.data.materials.clear()
	for m in mats:
		obj.data.materials.append(m)
	for poly in obj.data.polygons:
		poly.material_index = slot_idx


def create_strut_between(
	name: str,
	p0: Vector,
	p1: Vector,
	radius: float,
	vertices: int,
	mats: List[bpy.types.Material],
	slot_idx: int,
) -> bpy.types.Object:
	vec = p1 - p0
	mid = 0.5 * (p0 + p1)
	length = max(0.05, vec.length)
	rot_q = vec.normalized().to_track_quat("Z", "X")
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=vertices,
		radius=radius,
		depth=length,
		location=mid,
		rotation=rot_q.to_euler(),
	)
	obj = bpy.context.active_object
	obj.name = name
	add_bevel_modifier(obj, width=min(0.015, radius * 0.25), segments=1)
	apply_all_modifiers(obj)
	assign_single_slot(obj, mats, slot_idx)
	return obj


def create_catenary_cable_mesh(
	name: str,
	p0: Vector,
	p1: Vector,
	sag: float,
	bevel_radius: float,
	mats: List[bpy.types.Material],
	slot_idx: int,
) -> bpy.types.Object:
	curve_data = bpy.data.curves.new(name=name + "_Curve", type="CURVE")
	curve_data.dimensions = "3D"
	curve_data.bevel_depth = bevel_radius
	curve_data.bevel_resolution = 2
	curve_data.resolution_u = 8

	spline = curve_data.splines.new("POLY")
	steps = 9
	spline.points.add(steps - 1)
	for i in range(steps):
		t = float(i) / float(steps - 1)
		pt = p0.lerp(p1, t)
		pt.z -= math.sin(t * math.pi) * sag
		spline.points[i].co = (pt.x, pt.y, pt.z, 1.0)

	curve_obj = bpy.data.objects.new(name, curve_data)
	bpy.context.collection.objects.link(curve_obj)
	bpy.ops.object.select_all(action="DESELECT")
	curve_obj.select_set(True)
	bpy.context.view_layer.objects.active = curve_obj
	bpy.ops.object.convert(target="MESH")
	mesh_obj = bpy.context.active_object
	assign_single_slot(mesh_obj, mats, slot_idx)
	return mesh_obj


def bake_stylized_cavity_ink_vertex_colors(
	obj: bpy.types.Object,
	slot_palettes: Dict[int, Tuple[float, float, float, float]],
	emissive_slots: set[int],
	wet_height_z: float = 1.8,
	rust_streak_strength: float = 0.0,
) -> None:
	mesh: bpy.types.Mesh = obj.data
	for poly in mesh.polygons:
		poly.use_smooth = False

	bm = bmesh.new()
	bm.from_mesh(mesh)
	bm.verts.ensure_lookup_table()
	bm.edges.ensure_lookup_table()
	bm.faces.ensure_lookup_table()
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

	vert_concavity: List[float] = [0.0] * len(bm.verts)
	for v in bm.verts:
		adj_edges = v.link_edges
		if not adj_edges:
			continue
		center_sum = Vector((0.0, 0.0, 0.0))
		max_signed = 0.0
		for e in adj_edges:
			other = e.other_vert(v)
			center_sum += other.co
			if len(e.link_faces) == 2:
				f0, f1 = e.link_faces[0], e.link_faces[1]
				edge_vec = f1.calc_center_median() - f0.calc_center_median()
				if edge_vec.length > 1e-6:
					c_val = (f0.normal - f1.normal).dot(edge_vec.normalized())
					if abs(c_val) > abs(max_signed):
						max_signed = c_val
		avg_nb = center_sum / float(len(adj_edges))
		lap = avg_nb - v.co
		lap_proj = lap.dot(v.normal)
		vert_concavity[v.index] = (
			clamp01(max(0.0, lap_proj * 6.5) + max(0.0, max_signed * 0.45))
			- clamp01(max(0.0, -lap_proj * 5.5) + max(0.0, -max_signed * 0.38))
		)

	bm.free()

	if "Col" not in mesh.color_attributes:
		col_attr = mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
	else:
		col_attr = mesh.color_attributes["Col"]
	mesh.color_attributes.active_color = col_attr
	mesh.color_attributes.render_color_index = mesh.color_attributes.find("Col")

	ink_black: Tuple[float, float, float, float] = (0.012, 0.016, 0.022, 1.0)
	rust_orange: Tuple[float, float, float, float] = (0.34, 0.11, 0.05, 1.0)
	tidal_slime: Tuple[float, float, float, float] = (0.025, 0.048, 0.042, 1.0)

	loops = mesh.loops
	verts = mesh.vertices
	flat_colors: List[float] = [0.0] * (len(loops) * 4)

	for poly in mesh.polygons:
		m_idx = poly.material_index
		base_col = slot_palettes.get(m_idx, (0.2, 0.22, 0.25, 1.0))
		is_emissive = m_idx in emissive_slots

		for loop_idx in poly.loop_indices:
			v_idx = loops[loop_idx].vertex_index
			v = verts[v_idx]
			co = v.co
			concav = vert_concavity[v_idx]

			if is_emissive:
				rgba = base_col
			else:
				tidal_w = smoothstep(wet_height_z, -0.45, co.z) * 0.68
				rgba = lerp_color(base_col, tidal_slime, tidal_w)

				if rust_streak_strength > 0.0:
					streak_noise = 0.5 + 0.5 * math.sin(co.x * 1.9 + co.y * 2.3) * math.cos(co.z * 2.8)
					rust_w = clamp01(streak_noise * rust_streak_strength * smoothstep(-0.3, 4.5, co.z))
					rgba = lerp_color(rgba, rust_orange, rust_w * 0.55)

				cav_w = clamp01(smoothstep(0.01, 0.22, concav) * 0.90 + tidal_w * 0.35)
				rgba = lerp_color(rgba, ink_black, cav_w * 0.86)

				ridge_w = clamp01(smoothstep(-0.02, -0.22, concav))
				if ridge_w > 0.0:
					highlight = (
						min(1.0, base_col[0] * 1.42 + 0.09),
						min(1.0, base_col[1] * 1.45 + 0.10),
						min(1.0, base_col[2] * 1.48 + 0.12),
						1.0,
					)
					rgba = lerp_color(rgba, highlight, ridge_w * 0.58)

			off = loop_idx * 4
			flat_colors[off] = rgba[0]
			flat_colors[off + 1] = rgba[1]
			flat_colors[off + 2] = rgba[2]
			flat_colors[off + 3] = rgba[3]

	col_attr.data.foreach_set("color", flat_colors)


def finalize_and_export(
	obj_name: str,
	parts: List[bpy.types.Object],
	slot_palettes: Dict[int, Tuple[float, float, float, float]],
	emissive_slots: set[int],
	wet_height_z: float,
	rust_streak_strength: float,
	out_glb_path: str,
) -> None:
	bpy.ops.object.select_all(action="DESELECT")
	for p in parts:
		p.select_set(True)
	bpy.context.view_layer.objects.active = parts[0]
	bpy.ops.object.join()

	merged = bpy.context.active_object
	merged.name = obj_name
	bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

	bake_stylized_cavity_ink_vertex_colors(
		merged,
		slot_palettes=slot_palettes,
		emissive_slots=emissive_slots,
		wet_height_z=wet_height_z,
		rust_streak_strength=rust_streak_strength,
	)

	os.makedirs(os.path.dirname(os.path.abspath(out_glb_path)), exist_ok=True)
	bpy.ops.export_scene.gltf(
		filepath=os.path.abspath(out_glb_path),
		export_format="GLB",
		export_apply=True,
		export_yup=True,
		export_normals=True,
		export_materials="EXPORT",
	)
	print(f"Exported {out_glb_path}")


# ==============================================================================
# 1. POI_SUNKEN_SHIPWRECK.GLB — Half-Submerged Listing Rusted Iron Freighter Bow
# ==============================================================================
def build_poi_sunken_shipwreck(out_glb_path: str) -> None:
	clear_scene()

	c_barnacle = (0.04, 0.065, 0.055, 1.0)
	c_rust_hull = (0.23, 0.10, 0.07, 1.0)
	c_dark_iron = (0.09, 0.11, 0.13, 1.0)
	c_rot_deck = (0.17, 0.13, 0.09, 1.0)
	c_lamp = (1.0, 0.56, 0.22, 1.0)

	mat_barnacle = create_pbr_material("TidalBarnacles", c_barnacle, metallic=0.10, roughness=0.15)
	mat_rust_hull = create_pbr_material("CorrodedBuoyIron", c_rust_hull, metallic=0.65, roughness=0.68)
	mat_dark_iron = create_pbr_material("DarkMetal", c_dark_iron, metallic=0.78, roughness=0.46)
	mat_rot_deck = create_pbr_material("RottingWood", c_rot_deck, metallic=0.05, roughness=0.86)
	mat_lamp = create_pbr_material(
		"WarningBeaconLens",
		c_lamp,
		metallic=0.05,
		roughness=0.15,
		emission_color=(1.0, 0.52, 0.18, 1.0),
		emission_strength=4.2,
	)
	mats = [mat_barnacle, mat_rust_hull, mat_dark_iron, mat_rot_deck, mat_lamp]
	parts: List[bpy.types.Object] = []

	# Multi-station lofted freighter bow hull (y = -7.5m broken midships to y = +7.5m raked prow)
	bm = bmesh.new()
	stations = [
		# (y, beam_half, keel_z, deck_z, flare)
		(-7.2, 3.6, -3.2, 1.2, 1.05),
		(-4.5, 3.5, -2.6, 2.2, 1.08),
		(-1.5, 3.2, -1.8, 3.4, 1.12),
		(1.8, 2.5, -0.9, 4.6, 1.18),
		(4.8, 1.4, -0.1, 5.8, 1.24),
		(7.4, 0.22, 0.8, 6.9, 1.05),
	]
	rings: List[List[bmesh.types.BMVert]] = []
	for y, b_half, kz, dz, flare in stations:
		mid_z = 0.5 * (kz + dz)
		profile = [
			(0.0, y, kz),
			(-b_half * 0.68, y, kz + (dz - kz) * 0.26),
			(-b_half * flare, y, mid_z + (dz - kz) * 0.18),
			(-b_half * 0.92, y, dz),
			(0.0, y, dz - 0.18),
			(b_half * 0.92, y, dz),
			(b_half * flare, y, mid_z + (dz - kz) * 0.18),
			(b_half * 0.68, y, kz + (dz - kz) * 0.26),
		]
		rings.append([bm.verts.new(p) for p in profile])

	bm.verts.ensure_lookup_table()
	n_p = len(rings[0])
	for s in range(len(rings) - 1):
		r0, r1 = rings[s], rings[s + 1]
		for i in range(n_p):
			ni = (i + 1) % n_p
			f = bm.faces.new((r0[i], r0[ni], r1[ni], r1[i]))
			if i in (3, 4):
				f.material_index = 3  # Rotting wood deck
			elif 0.25 * (r0[i].co.z + r0[ni].co.z + r1[ni].co.z + r1[i].co.z) < 1.6:
				f.material_index = 0  # Tidal barnacles
			else:
				f.material_index = 1  # Rusted hull iron

	bm.faces.new(list(reversed(rings[0]))).material_index = 2
	bm.faces.new(rings[-1]).material_index = 1
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

	hull_mesh = bpy.data.meshes.new("ShipwreckHull_Mesh")
	for m in mats:
		hull_mesh.materials.append(m)
	bm.to_mesh(hull_mesh)
	bm.free()

	hull_obj = bpy.data.objects.new("ShipwreckHull", hull_mesh)
	bpy.context.collection.objects.link(hull_obj)
	add_bevel_modifier(hull_obj, width=0.05, segments=1)
	apply_all_modifiers(hull_obj)

	# Boolean jagged hull breach on starboard bow
	bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.65, location=(2.45, 0.8, 2.3))
	breach_cutter = bpy.context.active_object
	breach_cutter.scale = (1.1, 1.6, 0.85)
	bpy.ops.object.transform_apply(scale=True)
	assign_single_slot(breach_cutter, mats, 2)

	bool_mod = hull_obj.modifiers.new(name="HullBreach", type="BOOLEAN")
	bool_mod.operation = "DIFFERENCE"
	bool_mod.solver = "EXACT"
	bool_mod.object = breach_cutter
	apply_all_modifiers(hull_obj)
	bpy.data.objects.remove(breach_cutter, do_unlink=True)
	parts.append(hull_obj)

	# Exposed internal iron hull ribs inside the breach and broken midships
	for ry, rz in ((-5.8, 0.6), (-3.8, 1.3), (0.2, 2.1), (1.4, 2.5)):
		rib = create_strut_between(
			f"HullRib_{ry:.1f}",
			Vector((-2.7, ry, rz - 1.4)),
			Vector((2.7, ry, rz + 0.9)),
			0.11,
			6,
			mats,
			2,
		)
		parts.append(rib)

	# Battered forward wheelhouse cabin with Boolean window cavities
	bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, -2.2, 3.8))
	cabin = bpy.context.active_object
	cabin.scale = (3.8, 3.2, 2.4)
	bpy.ops.object.transform_apply(scale=True)
	add_bevel_modifier(cabin, width=0.05, segments=1)
	apply_all_modifiers(cabin)
	assign_single_slot(cabin, mats, 1)

	for wx in (-1.05, 1.05):
		bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wx, -0.6, 4.15))
		w_cut = bpy.context.active_object
		w_cut.scale = (0.95, 1.2, 0.72)
		bpy.ops.object.transform_apply(scale=True)
		assign_single_slot(w_cut, mats, 2)
		bm_mod = cabin.modifiers.new(name=f"WinCut_{wx:.1f}", type="BOOLEAN")
		bm_mod.operation = "DIFFERENCE"
		bm_mod.solver = "EXACT"
		bm_mod.object = w_cut
		apply_all_modifiers(cabin)
		bpy.data.objects.remove(w_cut, do_unlink=True)
	parts.append(cabin)

	# Tilted corroded smokestack behind wheelhouse
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=10,
		radius=0.68,
		depth=4.4,
		location=(-0.25, -4.5, 4.4),
		rotation=(math.radians(-16.0), math.radians(9.0), 0.0),
	)
	stack = bpy.context.active_object
	add_bevel_modifier(stack, width=0.04, segments=1)
	apply_all_modifiers(stack)
	assign_single_slot(stack, mats, 2)
	parts.append(stack)

	# Crooked foremast + crosstree yardarm + sagging rigging cables
	mast_base = Vector((0.0, 2.6, 4.2))
	mast_top = Vector((0.55, 2.2, 10.6))
	mast = create_strut_between("WreckForemast", mast_base, mast_top, 0.18, 8, mats, 2)
	parts.append(mast)

	yard = create_strut_between(
		"WreckYardarm",
		Vector((-2.2, 2.3, 8.6)),
		Vector((2.8, 2.1, 8.2)),
		0.10,
		6,
		mats,
		2,
	)
	parts.append(yard)

	parts.append(create_catenary_cable_mesh("ShroudPort", mast_top, Vector((-2.4, 1.5, 4.1)), 0.35, 0.035, mats, 2))
	parts.append(create_catenary_cable_mesh("ShroudStbd", mast_top, Vector((2.3, 1.5, 4.1)), 0.42, 0.035, mats, 2))
	parts.append(create_catenary_cable_mesh("Forestay", mast_top, Vector((0.0, 6.8, 6.5)), 0.28, 0.035, mats, 2))

	# Sputtering electrical bulkhead light cage on forward wheelhouse bulkhead
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=8,
		radius=0.28,
		depth=0.42,
		location=(0.0, -0.45, 4.85),
	)
	bulkhead_lamp = bpy.context.active_object
	add_bevel_modifier(bulkhead_lamp, width=0.02, segments=1)
	apply_all_modifiers(bulkhead_lamp)
	assign_single_slot(bulkhead_lamp, mats, 4)
	parts.append(bulkhead_lamp)

	# Apply dramatic 16-deg starboard list so the whole wreck looms crookedly out of the swells
	list_rot = Euler((math.radians(5.0), math.radians(16.0), 0.0), "XYZ").to_matrix().to_4x4()
	for p in parts:
		p.matrix_world = list_rot @ p.matrix_world

	finalize_and_export(
		obj_name="POISunkenShipwreck",
		parts=parts,
		slot_palettes={0: c_barnacle, 1: c_rust_hull, 2: c_dark_iron, 3: c_rot_deck, 4: c_lamp},
		emissive_slots={4},
		wet_height_z=1.8,
		rust_streak_strength=0.95,
		out_glb_path=out_glb_path,
	)


# ==============================================================================
# 2. POI_SEA_FORT_TOWER.GLB — Crooked Timber & Rusted-Iron Stilt Watchtower
# ==============================================================================
def build_poi_sea_fort_tower(out_glb_path: str) -> None:
	clear_scene()

	c_barnacle = (0.04, 0.065, 0.055, 1.0)
	c_timber = (0.22, 0.17, 0.12, 1.0)
	c_shack = (0.26, 0.23, 0.19, 1.0)
	c_rust_roof = (0.24, 0.12, 0.08, 1.0)
	c_lantern = (1.0, 0.68, 0.28, 1.0)

	mat_barnacle = create_pbr_material("TidalBarnacles", c_barnacle, metallic=0.08, roughness=0.15)
	mat_timber = create_pbr_material("WeatheredTimber", c_timber, metallic=0.04, roughness=0.84)
	mat_shack = create_pbr_material("ShackWall", c_shack, metallic=0.04, roughness=0.82)
	mat_rust_roof = create_pbr_material("CorrugatedRoof", c_rust_roof, metallic=0.65, roughness=0.58)
	mat_lantern = create_pbr_material(
		"AmberGlass",
		c_lantern,
		metallic=0.05,
		roughness=0.16,
		emission_color=(1.0, 0.64, 0.24, 1.0),
		emission_strength=4.5,
	)
	mats = [mat_barnacle, mat_timber, mat_shack, mat_rust_roof, mat_lantern]
	parts: List[bpy.types.Object] = []

	# 4 battered inward-leaning stilt pilings (-2.4m to +6.4m) with cross-bracing
	foot_xy = [(-2.8, -2.8), (2.8, -2.8), (2.8, 2.8), (-2.8, 2.8)]
	top_xy = [(-2.0, -2.0), (2.0, -2.0), (2.0, 2.0), (-2.0, 2.0)]
	slump = Vector((0.28, -0.18, 0.0))

	for i in range(4):
		p_bot = Vector((foot_xy[i][0], foot_xy[i][1], -2.4))
		p_mid = Vector((
			foot_xy[i][0] * 0.72 + top_xy[i][0] * 0.28,
			foot_xy[i][1] * 0.72 + top_xy[i][1] * 0.28,
			1.6,
		))
		p_top = Vector((top_xy[i][0], top_xy[i][1], 6.4)) + slump
		parts.append(create_strut_between(f"PilingBase_{i}", p_bot, p_mid, 0.28, 8, mats, 0))
		parts.append(create_strut_between(f"PilingUpper_{i}", p_mid, p_top, 0.24, 8, mats, 1))

		ni = (i + 1) % 4
		b0 = Vector((foot_xy[i][0] * 0.85, foot_xy[i][1] * 0.85, 0.8))
		b1 = Vector((top_xy[ni][0], top_xy[ni][1], 5.6)) + slump * 0.85
		parts.append(create_strut_between(f"XBraceA_{i}", b0, b1, 0.09, 6, mats, 3))

		b2 = Vector((foot_xy[ni][0] * 0.85, foot_xy[ni][1] * 0.85, 0.8))
		b3 = Vector((top_xy[i][0], top_xy[i][1], 5.6)) + slump * 0.85
		parts.append(create_strut_between(f"XBraceB_{i}", b2, b3, 0.09, 6, mats, 3))

		# Horizontal timber girt beam at z = 3.2m
		g0 = Vector((foot_xy[i][0] * 0.6, foot_xy[i][1] * 0.6, 3.2)) + slump * 0.45
		g1 = Vector((foot_xy[ni][0] * 0.6, foot_xy[ni][1] * 0.6, 3.2)) + slump * 0.45
		parts.append(create_strut_between(f"Girt_{i}", g0, g1, 0.12, 6, mats, 1))

	# Cantilevered plank platform at z = 6.4m (individual weathered timber beams with gaps)
	for px_idx in range(-5, 6):
		px = float(px_idx) * 0.54 + slump.x
		bpy.ops.mesh.primitive_cube_add(
			size=1.0,
			location=(px, slump.y, 6.42 + (px_idx % 2) * 0.02),
			rotation=(0.0, math.radians(1.5), math.radians((px_idx % 3 - 1) * 0.8)),
		)
		plank = bpy.context.active_object
		plank.scale = (0.48, 5.8, 0.18)
		bpy.ops.object.transform_apply(scale=True)
		add_bevel_modifier(plank, width=0.02, segments=1)
		apply_all_modifiers(plank)
		assign_single_slot(plank, mats, 1)
		parts.append(plank)

	# Crooked watch-shack cabin on the platform (z = 6.5m to 10.2m) with Boolean windows
	shack_center = Vector((0.0, 0.25, 8.25)) + slump
	bpy.ops.mesh.primitive_cube_add(
		size=1.0,
		location=shack_center,
		rotation=(math.radians(2.2), math.radians(-2.8), 0.0),
	)
	shack = bpy.context.active_object
	shack.scale = (3.6, 3.6, 3.5)
	bpy.ops.object.transform_apply(scale=True)
	add_bevel_modifier(shack, width=0.05, segments=1)
	apply_all_modifiers(shack)
	assign_single_slot(shack, mats, 2)

	# Carve front and side lookout window cavities via Boolean Difference
	for w_loc, w_scl in (
		(shack_center + Vector((0.0, -1.75, 0.35)), (1.45, 0.9, 0.95)),
		(shack_center + Vector((1.75, 0.0, 0.35)), (0.9, 1.35, 0.95)),
	):
		bpy.ops.mesh.primitive_cube_add(size=1.0, location=w_loc)
		wc = bpy.context.active_object
		wc.scale = w_scl
		bpy.ops.object.transform_apply(scale=True)
		assign_single_slot(wc, mats, 1)
		bmod = shack.modifiers.new(name="WindowCav", type="BOOLEAN")
		bmod.operation = "DIFFERENCE"
		bmod.solver = "EXACT"
		bmod.object = wc
		apply_all_modifiers(shack)
		bpy.data.objects.remove(wc, do_unlink=True)
	parts.append(shack)

	# Glowing interior amber window pane recessed inside the shack
	bpy.ops.mesh.primitive_cube_add(size=1.0, location=shack_center + Vector((0.0, 0.0, 0.32)))
	win_core = bpy.context.active_object
	win_core.scale = (3.1, 3.1, 0.82)
	bpy.ops.object.transform_apply(scale=True)
	assign_single_slot(win_core, mats, 4)
	parts.append(win_core)

	# Pitched corrugated iron pyramid roof + crooked stove pipe chimney
	bpy.ops.mesh.primitive_cone_add(
		vertices=4,
		radius1=3.25,
		radius2=0.18,
		depth=1.85,
		location=shack_center + Vector((0.0, 0.0, 2.55)),
		rotation=(math.radians(2.2), math.radians(-2.8), math.radians(45.0)),
	)
	roof = bpy.context.active_object
	add_bevel_modifier(roof, width=0.04, segments=1)
	apply_all_modifiers(roof)
	assign_single_slot(roof, mats, 3)
	parts.append(roof)

	# Steep wooden boarding ladder descending from platform (-Y side) into the sea
	lad_left_b = Vector((-0.55, -4.2, -0.8))
	lad_left_t = Vector((-0.55, -2.7, 6.5)) + slump
	lad_right_b = Vector((0.55, -4.2, -0.8))
	lad_right_t = Vector((0.55, -2.7, 6.5)) + slump
	parts.append(create_strut_between("LadderRailL", lad_left_b, lad_left_t, 0.07, 6, mats, 1))
	parts.append(create_strut_between("LadderRailR", lad_right_b, lad_right_t, 0.07, 6, mats, 1))
	for r_idx in range(10):
		rt = (float(r_idx) + 0.5) / 10.0
		parts.append(create_strut_between(
			f"LadderRung_{r_idx}",
			lad_left_b.lerp(lad_left_t, rt),
			lad_right_b.lerp(lad_right_t, rt),
			0.045,
			6,
			mats,
			1,
		))

	# Cantilevered iron lantern crane arm & hanging glowing oil lantern at z = 7.4m
	davit_base = shack_center + Vector((1.6, -1.6, 0.8))
	davit_tip = shack_center + Vector((2.9, -2.8, 1.35))
	parts.append(create_strut_between("LanternDavit", davit_base, davit_tip, 0.065, 6, mats, 3))
	parts.append(create_strut_between("LanternChain", davit_tip, davit_tip + Vector((0.0, 0.0, -0.75)), 0.03, 6, mats, 3))

	bpy.ops.mesh.primitive_cylinder_add(
		vertices=8,
		radius=0.28,
		depth=0.52,
		location=davit_tip + Vector((0.0, 0.0, -0.95)),
	)
	lantern = bpy.context.active_object
	add_bevel_modifier(lantern, width=0.02, segments=1)
	apply_all_modifiers(lantern)
	assign_single_slot(lantern, mats, 4)
	parts.append(lantern)

	finalize_and_export(
		obj_name="POISeaFortTower",
		parts=parts,
		slot_palettes={0: c_barnacle, 1: c_timber, 2: c_shack, 3: c_rust_roof, 4: c_lantern},
		emissive_slots={4},
		wet_height_z=1.8,
		rust_streak_strength=0.65,
		out_glb_path=out_glb_path,
	)


# ==============================================================================
# 3. POI_LEVIATHAN_RIBCAGE.GLB — Coastal Skerry Crowned with Colossal Whale Bones
# ==============================================================================
def build_poi_leviathan_ribcage(out_glb_path: str) -> None:
	clear_scene()

	c_tidal = (0.035, 0.05, 0.055, 1.0)
	c_crag = (0.11, 0.13, 0.15, 1.0)
	c_bone = (0.72, 0.69, 0.61, 1.0)
	c_bio = (0.14, 0.86, 0.72, 1.0)

	mat_tidal = create_pbr_material("TidalWetRock", c_tidal, metallic=0.15, roughness=0.14)
	mat_crag = create_pbr_material("BasaltCliff", c_crag, metallic=0.10, roughness=0.86)
	mat_bone = create_pbr_material("LeviathanBone", c_bone, metallic=0.04, roughness=0.78)
	mat_bio = create_pbr_material(
		"EldritchRuneGlow",
		c_bio,
		metallic=0.05,
		roughness=0.20,
		emission_color=(0.12, 0.84, 0.68, 1.0),
		emission_strength=2.8,
	)
	mats = [mat_tidal, mat_crag, mat_bone, mat_bio]
	parts: List[bpy.types.Object] = []

	# 1. Jagged Displaced Coastal Rock Skerry Base (-2.2m to +2.8m)
	bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=5.6, location=(0.0, 0.0, -0.2))
	skerry = bpy.context.active_object
	skerry.name = "SkerryRockBase"
	skerry.scale = (1.15, 1.75, 0.52)
	bpy.ops.object.transform_apply(scale=True)

	for v in skerry.data.vertices:
		co = v.co
		n_val = (
			math.sin(co.x * 0.85 + 1.2) * math.cos(co.y * 0.65 - 0.7) * 0.85
			+ math.sin(co.x * 1.9 - co.y * 1.4) * 0.35
		)
		v.co.x += n_val * 0.55
		v.co.y += n_val * 0.65
		v.co.z += abs(n_val) * 1.25 if co.z > 0.0 else -0.35

	skerry.data.materials.clear()
	for m in mats:
		skerry.data.materials.append(m)
	for poly in skerry.data.polygons:
		poly.material_index = 0 if poly.center.z < 1.35 else 1
	parts.append(skerry)

	# 2. Colossal Curving Leviathan Ribs (7 pairs of thick chiseled bone arches)
	for r_idx in range(7):
		t_rib = float(r_idx) / 6.0
		y_pos = -4.2 + t_rib * 8.8
		arch_scale = 1.0 - 0.38 * abs(t_rib - 0.42)
		rib_span = 4.2 * arch_scale
		rib_height = 6.8 * arch_scale

		for side in (-1.0, 1.0):
			bm = bmesh.new()
			arc_steps = 12
			rings: List[List[bmesh.types.BMVert]] = []
			for s in range(arc_steps + 1):
				st = float(s) / float(arc_steps)
				ang = st * math.pi * 0.86
				rx = side * (0.65 + math.sin(ang) * rib_span)
				rz = 1.2 + (1.0 - math.cos(ang * 1.05)) * (rib_height * 0.55)
				ry = y_pos + side * math.sin(st * math.pi) * 0.32 + (r_idx % 2) * 0.12
				rad = (0.38 - 0.22 * (st ** 1.3)) * arch_scale

				ring = []
				for k in range(6):
					ka = (2.0 * math.pi * float(k)) / 6.0
					vx = rx + math.cos(ka) * rad
					vy = ry + math.sin(ka) * rad * 0.72
					vz = rz + math.sin(ka) * rad * 0.68
					ring.append(bm.verts.new((vx, vy, vz)))
				rings.append(ring)

			bm.verts.ensure_lookup_table()
			for s in range(arc_steps):
				r0, r1 = rings[s], rings[s + 1]
				for k in range(6):
					nk = (k + 1) % 6
					f = bm.faces.new((r0[k], r0[nk], r1[nk], r1[k]))
					f.material_index = 2
			bm.faces.new(list(reversed(rings[0]))).material_index = 2
			bm.faces.new(rings[-1]).material_index = 2
			bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

			rib_mesh = bpy.data.meshes.new(f"LeviathanRib_{r_idx}_{int(side)}_Mesh")
			for m in mats:
				rib_mesh.materials.append(m)
			bm.to_mesh(rib_mesh)
			bm.free()

			rib_obj = bpy.data.objects.new(f"LeviathanRib_{r_idx}_{int(side)}", rib_mesh)
			bpy.context.collection.objects.link(rib_obj)
			parts.append(rib_obj)

		# Dorsal spine vertebra block along the central skerry ridge
		bpy.ops.mesh.primitive_cylinder_add(
			vertices=6,
			radius=0.58 * arch_scale,
			depth=0.95,
			location=(0.0, y_pos, 1.85 + (1.0 - abs(t_rib - 0.45)) * 0.65),
			rotation=(math.radians(82.0), 0.0, math.radians((r_idx % 3 - 1) * 6.0)),
		)
		vert_obj = bpy.context.active_object
		add_bevel_modifier(vert_obj, width=0.04, segments=1)
		apply_all_modifiers(vert_obj)
		assign_single_slot(vert_obj, mats, 2)
		parts.append(vert_obj)

	# 3. Colossal Bleached Leviathan Skull & Gaping Lower Jawbone at the North End (-Y)
	bpy.ops.mesh.primitive_cone_add(
		vertices=6,
		radius1=2.45,
		radius2=0.65,
		depth=4.8,
		location=(0.0, -6.8, 3.2),
		rotation=(math.radians(68.0), math.radians(6.0), 0.0),
	)
	skull = bpy.context.active_object
	skull.scale = (1.15, 0.78, 1.0)
	bpy.ops.object.transform_apply(scale=True)
	add_bevel_modifier(skull, width=0.06, segments=1)
	apply_all_modifiers(skull)
	assign_single_slot(skull, mats, 2)

	# Boolean eye sockets in the skull
	for ex in (-1.35, 1.35):
		bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.78, location=(ex, -5.8, 3.35))
		eye_cut = bpy.context.active_object
		assign_single_slot(eye_cut, mats, 2)
		bmod = skull.modifiers.new(name=f"EyeSocket_{ex:.1f}", type="BOOLEAN")
		bmod.operation = "DIFFERENCE"
		bmod.solver = "EXACT"
		bmod.object = eye_cut
		apply_all_modifiers(skull)
		bpy.data.objects.remove(eye_cut, do_unlink=True)
	parts.append(skull)

	# Bioluminescent barnacle/kelp clusters glowing faintly along the waterline rock crevices
	for b_ang in (0.4, 1.3, 2.5, 3.8, 4.9, 5.7):
		bx = math.cos(b_ang) * 4.4
		by = math.sin(b_ang) * 6.8
		bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.42, location=(bx, by, 0.35))
		bio_node = bpy.context.active_object
		bio_node.scale = (1.3, 1.3, 0.55)
		bpy.ops.object.transform_apply(scale=True)
		assign_single_slot(bio_node, mats, 3)
		parts.append(bio_node)

	finalize_and_export(
		obj_name="POILeviathanRibcage",
		parts=parts,
		slot_palettes={0: c_tidal, 1: c_crag, 2: c_bone, 3: c_bio},
		emissive_slots={3},
		wet_height_z=1.6,
		rust_streak_strength=0.0,
		out_glb_path=out_glb_path,
	)


# ==============================================================================
# 4. POI_DERELICT_LIGHTSHIP.GLB — Unmanned Battered Wooden Lightship & Beacon Tower
# ==============================================================================
def build_poi_derelict_lightship(out_glb_path: str) -> None:
	clear_scene()

	c_barnacle = (0.04, 0.065, 0.055, 1.0)
	c_hull_red = (0.28, 0.09, 0.07, 1.0)
	c_timber = (0.20, 0.15, 0.11, 1.0)
	c_iron = (0.10, 0.12, 0.14, 1.0)
	c_beacon = (0.96, 0.74, 0.34, 1.0)

	mat_barnacle = create_pbr_material("TidalBarnacles", c_barnacle, metallic=0.08, roughness=0.15)
	mat_hull_red = create_pbr_material("CorrodedBuoyIron", c_hull_red, metallic=0.35, roughness=0.76)
	mat_timber = create_pbr_material("WeatheredTimber", c_timber, metallic=0.04, roughness=0.85)
	mat_iron = create_pbr_material("DarkMetal", c_iron, metallic=0.76, roughness=0.48)
	mat_beacon = create_pbr_material(
		"BeaconLens",
		c_beacon,
		metallic=0.05,
		roughness=0.14,
		emission_color=(0.95, 0.72, 0.32, 1.0),
		emission_strength=4.8,
	)
	mats = [mat_barnacle, mat_hull_red, mat_timber, mat_iron, mat_beacon]
	parts: List[bpy.types.Object] = []

	# 1. Multi-station lofted wooden lightship hull (-7.2m stern to +7.5m bow)
	bm = bmesh.new()
	stations = [
		(-7.2, 1.45, -1.2, 2.35),
		(-4.8, 2.35, -1.5, 2.05),
		(-1.5, 2.65, -1.6, 1.85),
		(2.0, 2.55, -1.5, 1.95),
		(5.0, 1.65, -1.2, 2.35),
		(7.5, 0.20, -0.4, 2.85),
	]
	rings: List[List[bmesh.types.BMVert]] = []
	for y, b_half, kz, dz in stations:
		mid_z = 0.5 * (kz + dz)
		profile = [
			(0.0, y, kz),
			(-b_half * 0.72, y, kz + (dz - kz) * 0.28),
			(-b_half * 1.06, y, mid_z + 0.15),
			(-b_half * 0.96, y, dz),
			(0.0, y, dz - 0.22),
			(b_half * 0.96, y, dz),
			(b_half * 1.06, y, mid_z + 0.15),
			(b_half * 0.72, y, kz + (dz - kz) * 0.28),
		]
		rings.append([bm.verts.new(p) for p in profile])

	bm.verts.ensure_lookup_table()
	n_p = len(rings[0])
	for s in range(len(rings) - 1):
		r0, r1 = rings[s], rings[s + 1]
		for i in range(n_p):
			ni = (i + 1) % n_p
			f = bm.faces.new((r0[i], r0[ni], r1[ni], r1[i]))
			if i in (3, 4):
				f.material_index = 2  # Timber deck
			elif i in (0, 1, 7):
				f.material_index = 0  # Barnacle keel/waterline
			else:
				f.material_index = 1  # Weathered red-lead lightship hull

	bm.faces.new(list(reversed(rings[0]))).material_index = 1
	bm.faces.new(rings[-1]).material_index = 1
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

	hull_mesh = bpy.data.meshes.new("LightshipHull_Mesh")
	for m in mats:
		hull_mesh.materials.append(m)
	bm.to_mesh(hull_mesh)
	bm.free()

	hull_obj = bpy.data.objects.new("LightshipHull", hull_mesh)
	bpy.context.collection.objects.link(hull_obj)
	add_bevel_modifier(hull_obj, width=0.045, segments=1)
	apply_all_modifiers(hull_obj)
	parts.append(hull_obj)

	# 2. Skeletal 4-Legged Iron Lattice Beacon Tower Amidships (z = 1.7m to 8.6m)
	base_pts = [(-1.25, -1.25), (1.25, -1.25), (1.25, 1.25), (-1.25, 1.25)]
	top_pts = [(-0.55, -0.55), (0.55, -0.55), (0.55, 0.55), (-0.55, 0.55)]
	for i in range(4):
		p0 = Vector((base_pts[i][0], base_pts[i][1], 1.65))
		p1 = Vector((top_pts[i][0], top_pts[i][1], 8.6))
		parts.append(create_strut_between(f"TowerLeg_{i}", p0, p1, 0.095, 6, mats, 3))

		ni = (i + 1) % 4
		for hz0, hz1 in ((2.0, 4.2), (4.2, 6.4), (6.4, 8.4)):
			t0 = (hz0 - 1.65) / (8.6 - 1.65)
			t1 = (hz1 - 1.65) / (8.6 - 1.65)
			ba = p0.lerp(p1, t0)
			pn0 = Vector((base_pts[ni][0], base_pts[ni][1], 1.65))
			pn1 = Vector((top_pts[ni][0], top_pts[ni][1], 8.6))
			bb = pn0.lerp(pn1, t1)
			parts.append(create_strut_between(f"TowerDiag_{i}_{hz0:.0f}", ba, bb, 0.05, 6, mats, 3))

	# Lantern gallery platform + Fresnel beacon lens + storm hood at z = 8.6m..10.2m
	bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=1.05, depth=0.22, location=(0.0, 0.0, 8.65))
	gallery = bpy.context.active_object
	add_bevel_modifier(gallery, width=0.02, segments=1)
	apply_all_modifiers(gallery)
	assign_single_slot(gallery, mats, 3)
	parts.append(gallery)

	bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.58, depth=1.05, location=(0.0, 0.0, 9.25))
	fresnel_lens = bpy.context.active_object
	add_bevel_modifier(fresnel_lens, width=0.03, segments=1)
	apply_all_modifiers(fresnel_lens)
	assign_single_slot(fresnel_lens, mats, 4)
	parts.append(fresnel_lens)

	bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.82, radius2=0.10, depth=0.65, location=(0.0, 0.0, 10.05))
	dome = bpy.context.active_object
	add_bevel_modifier(dome, width=0.02, segments=1)
	apply_all_modifiers(dome)
	assign_single_slot(dome, mats, 3)
	parts.append(dome)

	# 3. Aft wooden deckhouse & crooked foremast with torn sail / drooping rigging
	bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, -4.2, 2.55))
	deckhouse = bpy.context.active_object
	deckhouse.scale = (2.4, 2.6, 1.45)
	bpy.ops.object.transform_apply(scale=True)
	add_bevel_modifier(deckhouse, width=0.04, segments=1)
	apply_all_modifiers(deckhouse)
	assign_single_slot(deckhouse, mats, 2)
	parts.append(deckhouse)

	fore_base = Vector((0.0, 4.2, 1.9))
	fore_top = Vector((0.35, 4.4, 7.6))
	parts.append(create_strut_between("ForeMast", fore_base, fore_top, 0.13, 6, mats, 2))
	parts.append(create_strut_between("ForeYard", Vector((-1.7, 4.3, 6.2)), Vector((2.1, 4.4, 5.9)), 0.08, 6, mats, 2))
	parts.append(create_catenary_cable_mesh("LightshipStayA", fore_top, Vector((0.0, 7.3, 2.75)), 0.25, 0.03, mats, 3))
	parts.append(create_catenary_cable_mesh("LightshipStayB", Vector((0.0, 0.0, 8.5)), fore_top, 0.45, 0.03, mats, 3))
	parts.append(create_catenary_cable_mesh("LightshipStayC", Vector((0.0, 0.0, 8.5)), Vector((0.0, -6.8, 2.3)), 0.55, 0.03, mats, 3))

	finalize_and_export(
		obj_name="POIDerelictLightship",
		parts=parts,
		slot_palettes={0: c_barnacle, 1: c_hull_red, 2: c_timber, 3: c_iron, 4: c_beacon},
		emissive_slots={4},
		wet_height_z=1.2,
		rust_streak_strength=0.80,
		out_glb_path=out_glb_path,
	)


# ==============================================================================
# 5. RUSTED_WARNING_BUOY.GLB — Crooked Iron Lattice Cage Channel Buoy
# ==============================================================================
def build_rusted_warning_buoy(out_glb_path: str) -> None:
	clear_scene()

	c_barnacle = (0.045, 0.065, 0.058, 1.0)
	c_rust_iron = (0.24, 0.11, 0.08, 1.0)
	c_dark_metal = (0.09, 0.11, 0.13, 1.0)
	c_brass = (0.68, 0.49, 0.21, 1.0)
	c_lantern = (1.0, 0.34, 0.12, 1.0)

	mat_barnacle = create_pbr_material("TidalBarnacles", c_barnacle, metallic=0.08, roughness=0.16)
	mat_rust_iron = create_pbr_material("CorrodedBuoyIron", c_rust_iron, metallic=0.62, roughness=0.68)
	mat_dark_metal = create_pbr_material("BuoyCageStruts", c_dark_metal, metallic=0.76, roughness=0.46)
	mat_brass = create_pbr_material("TarnishedBellBrass", c_brass, metallic=0.84, roughness=0.34)
	mat_lantern = create_pbr_material(
		"WarningBeaconLens",
		c_lantern,
		metallic=0.08,
		roughness=0.14,
		emission_color=(1.0, 0.32, 0.10, 1.0),
		emission_strength=5.0,
	)
	mats = [mat_barnacle, mat_rust_iron, mat_dark_metal, mat_brass, mat_lantern]
	parts: List[bpy.types.Object] = []

	bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.52, depth=1.15, location=(0.0, 0.0, -0.58))
	sub_skirt = bpy.context.active_object
	add_bevel_modifier(sub_skirt, width=0.025, segments=1)
	apply_all_modifiers(sub_skirt)
	assign_single_slot(sub_skirt, mats, 0)
	parts.append(sub_skirt)

	bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=1.18, depth=0.95, location=(0.0, 0.0, 0.25))
	float_drum = bpy.context.active_object
	add_bevel_modifier(float_drum, width=0.055, segments=1)
	apply_all_modifiers(float_drum)
	assign_single_slot(float_drum, mats, 1)
	parts.append(float_drum)

	bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=1.28, depth=0.22, location=(0.0, 0.0, 0.12))
	fender_belt = bpy.context.active_object
	add_bevel_modifier(fender_belt, width=0.03, segments=1)
	apply_all_modifiers(fender_belt)
	assign_single_slot(fender_belt, mats, 2)
	parts.append(fender_belt)

	rng = random.Random(1928)
	for b_idx in range(18):
		ang = (2.0 * math.pi * float(b_idx)) / 18.0 + rng.uniform(-0.08, 0.08)
		br = rng.uniform(1.12, 1.24)
		bz = rng.uniform(-0.22, 0.18)
		bpy.ops.mesh.primitive_cone_add(
			vertices=6,
			radius1=rng.uniform(0.11, 0.19),
			radius2=rng.uniform(0.04, 0.07),
			depth=rng.uniform(0.14, 0.24),
			location=(math.cos(ang) * br, math.sin(ang) * br, bz),
			rotation=(rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), ang),
		)
		barn = bpy.context.active_object
		assign_single_slot(barn, mats, 0)
		parts.append(barn)

	tower_base_z = 0.68
	tower_top_z = 3.45
	slump_offset = Vector((0.18, -0.09, 0.0))

	num_struts = 4
	for i in range(num_struts):
		ang = (2.0 * math.pi * float(i)) / float(num_struts) + (math.pi * 0.25)
		p0 = Vector((math.cos(ang) * 0.92, math.sin(ang) * 0.92, tower_base_z))
		p1 = Vector((math.cos(ang) * 0.36, math.sin(ang) * 0.36, tower_top_z)) + slump_offset
		parts.append(create_strut_between(f"BuoyLeg_{i}", p0, p1, 0.055, 6, mats, 2))

		next_ang = (2.0 * math.pi * float((i + 1) % num_struts)) / float(num_struts) + (math.pi * 0.25)
		b0 = Vector((math.cos(ang) * 0.78, math.sin(ang) * 0.78, 1.15)) + slump_offset * 0.2
		b1 = Vector((math.cos(next_ang) * 0.52, math.sin(next_ang) * 0.52, 2.55)) + slump_offset * 0.7
		parts.append(create_strut_between(f"BuoyBrace_{i}", b0, b1, 0.034, 6, mats, 1))

	for hz, hr, h_t in ((1.35, 0.76, 0.25), (2.45, 0.54, 0.65), (3.42, 0.40, 1.0)):
		center_h = Vector((0.0, 0.0, hz)) + slump_offset * h_t
		bpy.ops.mesh.primitive_torus_add(
			major_segments=8,
			minor_segments=6,
			major_radius=hr,
			minor_radius=0.042,
			location=center_h,
			rotation=(math.radians(2.5), math.radians(-1.8), 0.0),
		)
		hoop = bpy.context.active_object
		assign_single_slot(hoop, mats, 2)
		parts.append(hoop)

	bell_center = Vector((0.0, 0.0, 1.85)) + slump_offset * 0.45
	bpy.ops.mesh.primitive_cone_add(
		vertices=10,
		radius1=0.38,
		radius2=0.16,
		depth=0.52,
		location=bell_center,
		rotation=(math.radians(4.0), math.radians(-3.0), 0.0),
	)
	bell_body = bpy.context.active_object
	add_bevel_modifier(bell_body, width=0.02, segments=1)
	apply_all_modifiers(bell_body)
	assign_single_slot(bell_body, mats, 3)
	parts.append(bell_body)

	bpy.ops.mesh.primitive_torus_add(
		major_segments=10,
		minor_segments=6,
		major_radius=0.38,
		minor_radius=0.045,
		location=bell_center + Vector((0.0, 0.0, -0.24)),
		rotation=(math.radians(4.0), math.radians(-3.0), 0.0),
	)
	bell_rim = bpy.context.active_object
	assign_single_slot(bell_rim, mats, 3)
	parts.append(bell_rim)

	bpy.ops.mesh.primitive_uv_sphere_add(
		segments=8,
		ring_count=6,
		radius=0.095,
		location=bell_center + Vector((0.02, -0.01, -0.32)),
	)
	clapper = bpy.context.active_object
	assign_single_slot(clapper, mats, 2)
	parts.append(clapper)

	lantern_base = Vector((0.0, 0.0, tower_top_z)) + slump_offset
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=8,
		radius=0.26,
		depth=0.46,
		location=lantern_base + Vector((0.0, 0.0, 0.26)),
	)
	lens = bpy.context.active_object
	add_bevel_modifier(lens, width=0.018, segments=1)
	apply_all_modifiers(lens)
	assign_single_slot(lens, mats, 4)
	parts.append(lens)

	bpy.ops.mesh.primitive_cone_add(
		vertices=8,
		radius1=0.36,
		radius2=0.06,
		depth=0.26,
		location=lantern_base + Vector((0.0, 0.0, 0.58)),
	)
	hood = bpy.context.active_object
	add_bevel_modifier(hood, width=0.015, segments=1)
	apply_all_modifiers(hood)
	assign_single_slot(hood, mats, 2)
	parts.append(hood)

	finalize_and_export(
		obj_name="RustedWarningBuoy",
		parts=parts,
		slot_palettes={0: c_barnacle, 1: c_rust_iron, 2: c_dark_metal, 3: c_brass, 4: c_lantern},
		emissive_slots={4},
		wet_height_z=0.55,
		rust_streak_strength=0.90,
		out_glb_path=out_glb_path,
	)


def main() -> None:
	project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	models_dir = os.path.join(project_root, "assets", "models")
	os.makedirs(models_dir, exist_ok=True)

	# Remove deprecated eldritch_basalt_monolith.glb if present
	old_monolith = os.path.join(models_dir, "eldritch_basalt_monolith.glb")
	if os.path.exists(old_monolith):
		try:
			os.remove(old_monolith)
		except OSError:
			pass
	if os.path.exists(old_monolith + ".import"):
		try:
			os.remove(old_monolith + ".import")
		except OSError:
			pass

	build_poi_sunken_shipwreck(os.path.join(models_dir, "poi_sunken_shipwreck.glb"))
	build_poi_sea_fort_tower(os.path.join(models_dir, "poi_sea_fort_tower.glb"))
	build_poi_leviathan_ribcage(os.path.join(models_dir, "poi_leviathan_ribcage.glb"))
	build_poi_derelict_lightship(os.path.join(models_dir, "poi_derelict_lightship.glb"))
	build_rusted_warning_buoy(os.path.join(models_dir, "rusted_warning_buoy.glb"))


if __name__ == "__main__":
	main()
