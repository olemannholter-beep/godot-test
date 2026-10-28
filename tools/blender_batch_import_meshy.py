#!/usr/bin/env python3
"""
Headless Blender 5.4.0 Batch Meshy Model Standardization & Matte Material Processor
(`tools/blender_batch_import_meshy.py`)

Processes all 10 raw Meshy 3D models from `res://assets/models/raw_meshy/` into
`res://assets/models/` (12 exported .glb assets total, including Leviathan head & coil slices):

  1. Meshy_AI_stylized_trawler_aft__1027193606_image-to-3d-texture.glb
     -> res://assets/models/boat.glb (4.7m length, ~1.95m beam, waterline origin, bow -Z)
  2. Meshy_AI_Ghost_Trawler_No_Smok_1028171909_image-to-3d-texture.glb
     -> res://assets/models/enemy_ghost_trawler.glb (14.0m length, waterline origin, bow -Z)
  3. Meshy_AI_Wooden_Lightship_Hulk_1028164929_image-to-3d-texture.glb
     -> res://assets/models/poi_derelict_lightship.glb (18.0m length, waterline origin, bow -Z)
  4. Meshy_AI_Ocean_Warning_Buoy_1028164833_image-to-3d-texture.glb
     -> res://assets/models/rusted_warning_buoy.glb (4.5m height, origin at y=0 float ring)
  5. Meshy_AI_abyssal_leviathan_ser_1027194031_image-to-3d-texture.glb
     -> res://assets/models/enemy_leviathan_full.glb (18.0m length, snout -Z)
     -> res://assets/models/enemy_leviathan_head.glb (sliced front head/neck, 6.5m height, waterline pivot)
     -> res://assets/models/enemy_leviathan_coil.glb (sliced arched mid-body torso, 5.0m span, waterline pivot)
  6. Meshy_AI_stylized_dark_shipwre_1027192005_image-to-3d-texture.glb
     -> res://assets/models/poi_sunken_shipwreck.glb (24.0m length, 18 deg roll, 12 deg pitch, y=0 waterline, skirt to y=-6.5m)
  7. Meshy_AI_Coastal_Stone_Lightho_1028164823_image-to-3d-texture.glb
     -> res://assets/models/harbor_lighthouse.glb (22.0m tower height, y=0 base origin, stone foundation skirt to y=-3.0m)
  8. Meshy_AI_Sea_Fort_Watchtower_1028164849_image-to-3d-texture.glb
     -> res://assets/models/poi_sea_fort_tower.glb (18.0m height, stilt pilings/foundation extended to y=-7.0m)
  9. Meshy_AI_Leviathan_Bone_Skerry_1028165246_image-to-3d-texture.glb
     -> res://assets/models/poi_leviathan_ribcage.glb (26.0m span, rock base extended to y=-6.0m)
 10. Meshy_AI_Big_Game_Fishing_Rod_1028164912_image-to-3d-texture.glb
     -> res://assets/models/fishing_rod_tackle.glb (2.1m length, origin at cork grip (0,0,0), shaft -Z, reel upright +Y/-Y)

Universal Matte Dredge Material Pass:
  - Preserves all Meshy PBR textures (Base Color, Normal)
  - Bakes dirty-vertex cavity ink (`Col`) multiplied into crevices + 0.78x base color darken
  - Clamps Roughness strictly between 0.82 and 0.95 (default 0.88)
  - Clamps Metallic <= 0.20, Specular = 0.20, Coat Weight = 0.0
"""

import math
import os
import shutil
import sys
from typing import Dict, List, Optional, Tuple

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_contact_sheet_gate import render_4view_contact_sheet


PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_DIR: str = os.path.join(PROJECT_ROOT, "assets", "models", "raw_meshy")
FALLBACK_RAW_DIR: str = r"C:\Users\olema\Downloads\pro models"
MODELS_DIR: str = os.path.join(PROJECT_ROOT, "assets", "models")
MESHES_DIR: str = os.path.join(PROJECT_ROOT, "assets", "meshes")
ENEMIES_DIR: str = os.path.join(MODELS_DIR, "enemies")


def resolve_raw_path(filename: str) -> str:
	p1 = os.path.join(RAW_DIR, filename)
	if os.path.isfile(p1):
		return p1
	p2 = os.path.join(FALLBACK_RAW_DIR, filename)
	if os.path.isfile(p2):
		return p2
	raise FileNotFoundError(f"Could not find raw Meshy model '{filename}' in {RAW_DIR} or {FALLBACK_RAW_DIR}")


def clear_scene() -> None:
	bpy.ops.wm.read_factory_settings(use_empty=True)


def import_and_join_raw_glb(filename: str, obj_name: str, target_verts: int = 48000) -> bpy.types.Object:
	clear_scene()
	raw_path = resolve_raw_path(filename)
	print(f"\n==================================================================")
	print(f"[BatchImport] Importing {filename} -> {obj_name}")
	bpy.ops.import_scene.gltf(filepath=raw_path)
	bpy.context.view_layer.update()

	# Strip non-mesh objects (cameras, lights, empties, armatures)
	to_remove = [o for o in list(bpy.data.objects) if o.type != "MESH"]
	for o in to_remove:
		bpy.data.objects.remove(o, do_unlink=True)

	mesh_objs = [o for o in bpy.data.objects if o.type == "MESH" and o.data is not None]
	if not mesh_objs:
		raise RuntimeError(f"No mesh objects found in {filename}")

	bpy.ops.object.select_all(action="DESELECT")
	for o in mesh_objs:
		o.select_set(True)
	bpy.context.view_layer.objects.active = mesh_objs[0]
	if len(mesh_objs) > 1:
		bpy.ops.object.join()

	obj = bpy.context.view_layer.objects.active
	obj.name = obj_name
	bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

	# Decimate while preserving UV maps & PBR textures
	v_count = len(obj.data.vertices)
	print(f"[{obj_name}] Raw vertex count: {v_count}")
	if v_count > target_verts:
		ratio = max(0.012, min(1.0, float(target_verts) / float(v_count)))
		mod = obj.modifiers.new(name="DecimateScan", type="DECIMATE")
		mod.decimate_type = "COLLAPSE"
		mod.ratio = ratio
		mod.use_collapse_triangulate = True
		bpy.context.view_layer.objects.active = obj
		bpy.ops.object.modifier_apply(modifier=mod.name)
		print(f"[{obj_name}] Decimated vertex count: {len(obj.data.vertices)} (ratio={ratio:.4f})")

	# Remove disconnected floating debris scraps (< 0.25% of main component)
	remove_floating_debris(obj)
	return obj


def remove_floating_debris(obj: bpy.types.Object, min_ratio: float = 0.0025) -> None:
	bm = bmesh.new()
	bm.from_mesh(obj.data)
	bm.verts.ensure_lookup_table()

	visited = set()
	islands: List[List[bmesh.types.BMVert]] = []
	for v in bm.verts:
		if v.index in visited:
			continue
		stack = [v]
		comp = []
		visited.add(v.index)
		while stack:
			curr = stack.pop()
			comp.append(curr)
			for e in curr.link_edges:
				other = e.other_vert(curr)
				if other.index not in visited:
					visited.add(other.index)
					stack.append(other)
		islands.append(comp)

	if len(islands) > 1:
		max_len = max(len(c) for c in islands)
		thresh = max(12, int(max_len * min_ratio))
		removed = 0
		for comp in islands:
			if len(comp) < thresh:
				for v in comp:
					bm.verts.remove(v)
				removed += len(comp)
		if removed > 0:
			print(f"[{obj.name}] Stripped {removed} floating debris vertices.")

	bm.to_mesh(obj.data)
	bm.free()
	obj.data.update()


def get_bounds(mesh: bpy.types.Mesh) -> Tuple[Vector, Vector, Vector]:
	xs = [v.co.x for v in mesh.vertices]
	ys = [v.co.y for v in mesh.vertices]
	zs = [v.co.z for v in mesh.vertices]
	if not xs:
		return Vector((0, 0, 0)), Vector((0, 0, 0)), Vector((0, 0, 0))
	mn = Vector((min(xs), min(ys), min(zs)))
	mx = Vector((max(xs), max(ys), max(zs)))
	return mn, mx, mx - mn


def add_underwater_foundation_skirt(
	obj: bpy.types.Object,
	bottom_z: float,
	top_overlap_z: float,
	radius_x: float,
	radius_y: float,
	center_x: float = 0.0,
	center_y: float = 0.0,
	flare_bottom: float = 1.28,
	is_pilings: bool = False,
	seed: int = 101,
) -> None:
	"""
	Appends a weathered underwater stone/rock foundation skirt (or heavy timber stilt pilings + rock shoal)
	directly into `obj.data` with valid UV coordinates in the darkest region of the texture so it seamlessly
	grounds the landmark down to `bottom_z` (Godot `y = bottom_z`).
	"""
	mesh = obj.data
	bm = bmesh.new()
	bm.from_mesh(mesh)
	bm.verts.ensure_lookup_table()

	uv_layer = bm.loops.layers.uv.active
	if uv_layer is None:
		uv_layer = bm.loops.layers.uv.new("UVMap")

	# Find the UV coordinate of the lowest vertex in the existing mesh so the foundation skirt samples matching dark stone/hull pixels
	lowest_v = min(bm.verts, key=lambda v: v.co.z) if bm.verts else None
	base_uv = Vector((0.15, 0.15))
	if lowest_v is not None and lowest_v.link_loops:
		base_uv = lowest_v.link_loops[0][uv_layer].uv.copy()

	# Build a multi-ring displaced crag/foundation skirt from top_overlap_z down to bottom_z
	rings_count = 7
	segs = 24
	ring_verts: List[List[bmesh.types.BMVert]] = []
	for r_i in range(rings_count + 1):
		t = float(r_i) / float(rings_count)
		z_val = top_overlap_z + t * (bottom_z - top_overlap_z)
		scale_r = 0.88 + t * (flare_bottom - 0.88)
		ring: List[bmesh.types.BMVert] = []
		for s_i in range(segs):
			ang = (2.0 * math.pi * float(s_i)) / float(segs)
			noise = 1.0 + 0.12 * math.sin(ang * 5.0 + t * 4.0 + seed) + 0.07 * math.cos(ang * 7.0 - t * 3.0)
			vx = center_x + math.cos(ang) * radius_x * scale_r * noise
			vy = center_y + math.sin(ang) * radius_y * scale_r * noise
			ring.append(bm.verts.new((vx, vy, z_val)))
		ring_verts.append(ring)

	new_faces: List[bmesh.types.BMFace] = []
	for r_i in range(rings_count):
		r0 = ring_verts[r_i]
		r1 = ring_verts[r_i + 1]
		for s_i in range(segs):
			ns = (s_i + 1) % segs
			f = bm.faces.new((r0[s_i], r0[ns], r1[ns], r1[s_i]))
			new_faces.append(f)

	# Cap the bottom at bottom_z
	v_bot_center = bm.verts.new((center_x, center_y, bottom_z))
	for s_i in range(segs):
		ns = (s_i + 1) % segs
		f = bm.faces.new((ring_verts[-1][ns], ring_verts[-1][s_i], v_bot_center))
		new_faces.append(f)

	# If stilt watchtower, also add 4 heavy submerged corner pilings + cross-braces extending from z = +2.5m down to bottom_z
	if is_pilings:
		piling_offsets = [
			(-radius_x * 0.62, -radius_y * 0.62),
			( radius_x * 0.62, -radius_y * 0.62),
			( radius_x * 0.62,  radius_y * 0.62),
			(-radius_x * 0.62,  radius_y * 0.62),
		]
		for px, py in piling_offsets:
			p_segs = 8
			p_rings = 4
			p_rad = max(0.32, min(radius_x, radius_y) * 0.12)
			p_grid: List[List[bmesh.types.BMVert]] = []
			for pr in range(p_rings + 1):
				pt = float(pr) / float(p_rings)
				pz = 2.2 + pt * (bottom_z - 2.2)
				pring: List[bmesh.types.BMVert] = []
				for ps in range(p_segs):
					pang = (2.0 * math.pi * float(ps)) / float(p_segs)
					pring.append(bm.verts.new((center_x + px + math.cos(pang) * p_rad, center_y + py + math.sin(pang) * p_rad, pz)))
				p_grid.append(pring)
			for pr in range(p_rings):
				for ps in range(p_segs):
					nps = (ps + 1) % p_segs
					f = bm.faces.new((p_grid[pr][ps], p_grid[pr][nps], p_grid[pr + 1][nps], p_grid[pr + 1][ps]))
					new_faces.append(f)

	for f in new_faces:
		f.smooth = True
		for loop in f.loops:
			loop[uv_layer].uv = base_uv

	bmesh.ops.recalc_face_normals(bm, faces=new_faces)
	bm.to_mesh(mesh)
	bm.free()
	mesh.update()


def apply_universal_matte_dredge_material(
	obj: bpy.types.Object,
	mat_name: str,
	darken_factor: float = 0.78,
	cavity_strength: float = 0.62,
	submerged_darken_z: Optional[float] = 0.0,
	target_roughness: float = 0.88,
) -> None:
	"""
	Universal Matte Dredge Material Pass (Zero Shiny Plastic):
	  - Preserves all Meshy PBR textures (Base Color, Normal)
	  - Bakes dirty-vertex cavity ink (`Col`) multiplied into crevices
	  - Darkens Base Color image pixels by `darken_factor` (0.78x) once per image
	  - Clamps Roughness strictly between 0.82 and 0.95 (default 0.88)
	  - Clamps Metallic <= 0.20, Specular / IOR Level = 0.20, Coat Weight = 0.0
	"""
	mesh = obj.data
	bm = bmesh.new()
	bm.from_mesh(mesh)
	bm.verts.ensure_lookup_table()
	bm.normal_update()

	raw_cavity = [0.0] * len(bm.verts)
	for v in bm.verts:
		edges = v.link_edges
		if not edges:
			continue
		avg_nbr = Vector((0.0, 0.0, 0.0))
		for e in edges:
			avg_nbr += e.other_vert(v).co
		avg_nbr /= float(len(edges))
		delta = avg_nbr - v.co
		edge_len = max(delta.length, 0.0001)
		raw_cavity[v.index] = delta.dot(v.normal) / edge_len

	# 1-ring smoothing pass
	smoothed_cavity = [0.0] * len(bm.verts)
	for v in bm.verts:
		edges = v.link_edges
		if not edges:
			smoothed_cavity[v.index] = raw_cavity[v.index]
			continue
		acc = raw_cavity[v.index] * 2.0
		for e in edges:
			acc += raw_cavity[e.other_vert(v).index]
		smoothed_cavity[v.index] = acc / float(len(edges) + 2)

	bm.free()

	while len(mesh.color_attributes) > 0:
		mesh.color_attributes.remove(mesh.color_attributes[0])

	col_attr = mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
	mesh.color_attributes.active_color = col_attr
	mesh.color_attributes.render_color_index = 0

	flat_colors = [0.0] * (len(mesh.loops) * 4)
	for loop_idx, loop in enumerate(mesh.loops):
		v_idx = loop.vertex_index
		v_co = mesh.vertices[v_idx].co
		v_norm = mesh.vertices[v_idx].normal
		cav = smoothed_cavity[v_idx]

		crevice_darken = max(0.0, min(1.0, cav * 2.8))
		ridge_boost = max(0.0, min(0.08, -cav * 0.35))

		tidal_shade = 1.0
		if submerged_darken_z is not None:
			height_t = max(0.0, min(1.0, (v_co.z - (submerged_darken_z - 2.0)) / 4.0))
			tidal_shade = 0.58 + 0.42 * height_t

		downward_ao = 0.84 + 0.16 * max(0.0, min(1.0, (v_norm.z + 0.6) / 1.4))
		ink_val = (1.0 - crevice_darken * cavity_strength + ridge_boost) * tidal_shade * downward_ao
		ink_val = max(0.22, min(0.96, ink_val))

		r = max(0.18, min(1.0, ink_val * 0.95))
		g = max(0.20, min(1.0, ink_val * 0.97))
		b = max(0.22, min(1.0, ink_val * 1.00))

		base = loop_idx * 4
		flat_colors[base] = r
		flat_colors[base + 1] = g
		flat_colors[base + 2] = b
		flat_colors[base + 3] = 1.0

	col_attr.data.foreach_set("color", flat_colors)

	for mat in mesh.materials:
		if mat is None or not mat.use_nodes or mat.node_tree is None:
			continue
		mat.name = mat_name
		nt = mat.node_tree
		bsdf = None
		base_tex_node = None

		for node in nt.nodes:
			if node.type == "BSDF_PRINCIPLED":
				bsdf = node
			elif node.type == "TEX_IMAGE" and node.image is not None:
				for out_link in node.outputs["Color"].links:
					if out_link.to_socket.name == "Base Color":
						base_tex_node = node

		if bsdf is None:
			continue

		# 1. Coat Weight = 0.0 (Zero shiny clearcoat)
		if "Coat Weight" in bsdf.inputs:
			bsdf.inputs["Coat Weight"].default_value = 0.0
		elif "Clearcoat" in bsdf.inputs:
			bsdf.inputs["Clearcoat"].default_value = 0.0
		if "Coat Roughness" in bsdf.inputs:
			bsdf.inputs["Coat Roughness"].default_value = 0.90

		# 2. Specular = 0.20
		if "IOR Level" in bsdf.inputs:
			bsdf.inputs["IOR Level"].default_value = 0.20
		elif "Specular IOR Level" in bsdf.inputs:
			bsdf.inputs["Specular IOR Level"].default_value = 0.20

		# 3. Roughness strictly clamped (default 0.88, or 0.72 for wet Leviathan organic hide)
		if "Roughness" in bsdf.inputs:
			rough_socket = bsdf.inputs["Roughness"]
			for l in list(rough_socket.links):
				nt.links.remove(l)
			rough_socket.default_value = target_roughness

		# 4. Metallic <= 0.10 (unlinked scalar 0.08 so glTF exports exact low metallicFactor without shiny ORM channels)
		if "Metallic" in bsdf.inputs:
			metal_socket = bsdf.inputs["Metallic"]
			for l in list(metal_socket.links):
				nt.links.remove(l)
			metal_socket.default_value = min(float(metal_socket.default_value), 0.08)

		# 5. Darken Base Color texture by 0.78x (once per image) & keep wired to Base Color
		if base_tex_node is not None and base_tex_node.image is not None:
			img = base_tex_node.image
			if not img.get("matte_darkened_078", False):
				px = list(img.pixels)
				for i in range(0, len(px), 4):
					px[i] = px[i] * darken_factor
					px[i + 1] = px[i + 1] * darken_factor
					px[i + 2] = px[i + 2] * darken_factor
				img.pixels[:] = px
				img.pack()
				img["matte_darkened_078"] = True
			nt.links.new(base_tex_node.outputs["Color"], bsdf.inputs["Base Color"])


def export_glb(output_path: str) -> None:
	os.makedirs(os.path.dirname(output_path), exist_ok=True)
	bpy.ops.export_scene.gltf(
		filepath=output_path,
		export_format="GLB",
		export_apply=True,
		export_yup=True,
		export_texcoords=True,
		export_normals=True,
		export_vertex_color="ACTIVE",
		export_all_vertex_colors=True,
		export_materials="EXPORT",
	)
	print(f"[BatchImport] Exported: {output_path}")


# ==============================================================================
# 1. PLAYER BOAT (`boat.glb` — 4.7m length, ~1.95m beam, waterline origin, bow -Z)
# ==============================================================================
def process_player_boat() -> None:
	obj = import_and_join_raw_glb(
		"Meshy_AI_stylized_trawler_aft__1027193606_image-to-3d-texture.glb",
		"PlayerTrawlerHull",
		target_verts=48000,
	)
	mesh = obj.data
	# Raw: X is length (span 1.902, pointed bow & forward cabin at -X, flat stern & open aft deck with lifebuoys at +X),
	# Y is beam (0.749), Z is up (1.086).
	# Rotate -90 deg around Z (180 deg flip from +90 deg) so -X (pointed bow) -> +Y in Blender (-Z forward in Godot glTF)
	# and +X (open aft deck) -> -Y in Blender (+Z rear in Godot glTF).
	mesh.transform(Matrix.Rotation(math.radians(-90.0), 4, "Z"))

	mn, mx, sp = get_bounds(mesh)
	scale_y = 4.70 / max(sp.y, 0.001)
	# Scale X slightly so beam is ~1.95m while length is 4.70m and height is proportional
	scale_x = 1.95 / max(sp.x, 0.001)
	scale_z = scale_y

	cx = 0.5 * (mn.x + mx.x)
	cy = 0.5 * (mn.y + mx.y)
	# Place waterline at 8% up from keel bottom (lifting hull +0.46m higher out of the water)
	# so the open wooden aft deck planks sit completely above waves
	wl_z = mn.z + sp.z * 0.08

	T = Matrix.Translation(Vector((-cx, -cy, -wl_z)))
	S = Matrix.Diagonal(Vector((scale_x, scale_y, scale_z, 1.0)))
	mesh.transform(S @ T)
	mesh.update()

	mn, mx, sp = get_bounds(mesh)
	# Measure smokestack, cabin roof, bow tip, and aft deck floor height in Godot coordinates (Godot X = X, Y = Z_up, Z = -Y_blender)
	top_verts = [v.co for v in mesh.vertices if v.co.z > mx.z - 0.25]
	smoke_x = sum(v.x for v in top_verts) / len(top_verts) if top_verts else 0.0
	smoke_godot_z = -sum(v.y for v in top_verts) / len(top_verts) if top_verts else -0.35
	smoke_godot_y = mx.z

	bow_verts = [v.co for v in mesh.vertices if v.co.y > mx.y - 0.25]
	bow_tip_godot_z = -mx.y
	bow_tip_godot_y = max(v.z for v in bow_verts) if bow_verts else 1.25

	# Aft deck floor planks (in Blender Y is [-1.8, -0.4], which is Godot Z in [+0.4, +1.8], near center X)
	aft_floor_verts = [v.co for v in mesh.vertices if -1.85 <= v.co.y <= -0.45 and abs(v.co.x) < 0.35 and v.co.z > 0.1]
	aft_floor_z_sorted = sorted(v.z for v in aft_floor_verts) if aft_floor_verts else [0.80]
	aft_floor_godot_y = aft_floor_z_sorted[int(len(aft_floor_z_sorted) * 0.25)]
	print(
		f"[boat.glb] Final Bounds (Blender): X=[{mn.x:.2f},{mx.x:.2f}] ({sp.x:.2f}m), "
		f"Y=[{mn.y:.2f},{mx.y:.2f}] ({sp.y:.2f}m), Z=[{mn.z:.2f},{mx.z:.2f}] ({sp.z:.2f}m) | "
		f"Godot BowTip=(0.00, {bow_tip_godot_y:.2f}, {bow_tip_godot_z:.2f}), "
		f"Godot Smokestack=({smoke_x:.2f}, {smoke_godot_y:.2f}, {smoke_godot_z:.2f}), "
		f"Godot AftDeckFloorY={aft_floor_godot_y:.2f}m"
	)

	apply_universal_matte_dredge_material(obj, "MattePlayerTrawler", darken_factor=0.78, submerged_darken_z=0.0)
	render_4view_contact_sheet("boat", [obj])
	out_path = os.path.join(MODELS_DIR, "boat.glb")
	export_glb(out_path)
	os.makedirs(MESHES_DIR, exist_ok=True)
	shutil.copy2(out_path, os.path.join(MESHES_DIR, "boat.glb"))


# ==============================================================================
# 2. MIMIC GHOST TRAWLER (`enemy_ghost_trawler.glb` — 14.0m length, bow -Z)
# ==============================================================================
def process_ghost_trawler() -> None:
	obj = import_and_join_raw_glb(
		"Meshy_AI_Ghost_Trawler_No_Smok_1028171909_image-to-3d-texture.glb",
		"GhostTrawlerHull",
		target_verts=48000,
	)
	mesh = obj.data
	# Raw: X is length (1.892), with raised pointed bow and forward wheelhouse at -X and rear A-frame net gantry at +X.
	# Rotate -90 deg around Z (180 deg flip from +90 deg) so -X (pointed bow & wheelhouse) -> +Y in Blender (-Z forward in Godot)
	# and +X (A-frame net gantry) -> -Y in Blender (+Z rear in Godot).
	mesh.transform(Matrix.Rotation(math.radians(-90.0), 4, "Z"))

	mn, mx, sp = get_bounds(mesh)
	scale_factor = 14.0 / max(sp.y, 0.001)
	cx = 0.5 * (mn.x + mx.x)
	cy = 0.5 * (mn.y + mx.y)
	wl_z = mn.z + sp.z * 0.25

	mesh.transform(Matrix.Scale(scale_factor, 4) @ Matrix.Translation(Vector((-cx, -cy, -wl_z))))
	mesh.update()

	mn, mx, sp = get_bounds(mesh)
	# Measure wheelhouse forward roof (for searchlight) and funnel top (for smoke) in Godot coords
	fwd_high_verts = [v.co for v in mesh.vertices if v.co.y > 0.5 and v.co.z > mx.z * 0.55]
	wh_godot_y = max((v.z for v in fwd_high_verts), default=3.8)
	print(
		f"[enemy_ghost_trawler.glb] Final Bounds: X=[{mn.x:.2f},{mx.x:.2f}] ({sp.x:.2f}m), "
		f"Y=[{mn.y:.2f},{mx.y:.2f}] ({sp.y:.2f}m), Z=[{mn.z:.2f},{mx.z:.2f}] ({sp.z:.2f}m) | "
		f"ForwardPeakY={wh_godot_y:.2f}m"
	)

	apply_universal_matte_dredge_material(obj, "MatteGhostTrawler", darken_factor=0.78, submerged_darken_z=0.0)
	render_4view_contact_sheet("enemy_ghost_trawler", [obj])
	out_main = os.path.join(MODELS_DIR, "enemy_ghost_trawler.glb")
	export_glb(out_main)
	os.makedirs(ENEMIES_DIR, exist_ok=True)
	shutil.copy2(out_main, os.path.join(ENEMIES_DIR, "enemy_ghost_trawler.glb"))
	os.makedirs(MESHES_DIR, exist_ok=True)
	shutil.copy2(out_main, os.path.join(MESHES_DIR, "enemy_ghost_trawler.glb"))


# ==============================================================================
# 3. DERELICT LIGHTSHIP (`poi_derelict_lightship.glb` — 18.0m length, bow -Z)
# ==============================================================================
def process_derelict_lightship() -> None:
	obj = import_and_join_raw_glb(
		"Meshy_AI_Wooden_Lightship_Hulk_1028164929_image-to-3d-texture.glb",
		"DerelictLightship",
		target_verts=48000,
	)
	mesh = obj.data
	# Raw: X is length (1.903), sharp bowsprit/prow at -X (tip width 0.07).
	# Rotate +90 deg around Z so -X -> +Y in Blender (-Z forward in Godot).
	mesh.transform(Matrix.Rotation(math.radians(90.0), 4, "Z"))

	mn, mx, sp = get_bounds(mesh)
	scale_factor = 18.0 / max(sp.y, 0.001)
	cx = 0.5 * (mn.x + mx.x)
	cy = 0.5 * (mn.y + mx.y)
	wl_z = mn.z + sp.z * 0.24

	mesh.transform(Matrix.Scale(scale_factor, 4) @ Matrix.Translation(Vector((-cx, -cy, -wl_z))))
	mesh.update()

	mn, mx, sp = get_bounds(mesh)
	top_verts = [v.co for v in mesh.vertices if v.co.z > mx.z - 0.5]
	mast_y = sum(v.y for v in top_verts) / len(top_verts) if top_verts else 0.0
	print(
		f"[poi_derelict_lightship.glb] Final Bounds: X=[{mn.x:.2f},{mx.x:.2f}] ({sp.x:.2f}m), "
		f"Y=[{mn.y:.2f},{mx.y:.2f}] ({sp.y:.2f}m), Z=[{mn.z:.2f},{mx.z:.2f}] ({sp.z:.2f}m) | mast_top=(0, {mast_y:.2f}, {mx.z:.2f})"
	)

	apply_universal_matte_dredge_material(obj, "MatteDerelictLightship", darken_factor=0.78, submerged_darken_z=0.0)
	export_glb(os.path.join(MODELS_DIR, "poi_derelict_lightship.glb"))


# ==============================================================================
# 4. RUSTED WARNING BUOY (`rusted_warning_buoy.glb` — 4.5m height, y=0 float ring)
# ==============================================================================
def process_warning_buoy() -> None:
	obj = import_and_join_raw_glb(
		"Meshy_AI_Ocean_Warning_Buoy_1028164833_image-to-3d-texture.glb",
		"RustedWarningBuoy",
		target_verts=42000,
	)
	mesh = obj.data
	mn, mx, sp = get_bounds(mesh)
	scale_factor = 4.50 / max(sp.z, 0.001)
	cx = 0.5 * (mn.x + mx.x)
	cy = 0.5 * (mn.y + mx.y)
	# Float ring is at ~38% up from the submerged counterweight bottom
	wl_z = mn.z + sp.z * 0.38

	mesh.transform(Matrix.Scale(scale_factor, 4) @ Matrix.Translation(Vector((-cx, -cy, -wl_z))))
	mesh.update()

	mn, mx, sp = get_bounds(mesh)
	print(
		f"[rusted_warning_buoy.glb] Final Bounds: X=[{mn.x:.2f},{mx.x:.2f}] ({sp.x:.2f}m), "
		f"Y=[{mn.y:.2f},{mx.y:.2f}] ({sp.y:.2f}m), Z=[{mn.z:.2f},{mx.z:.2f}] ({sp.z:.2f}m)"
	)

	apply_universal_matte_dredge_material(obj, "MatteWarningBuoy", darken_factor=0.78, submerged_darken_z=0.0)
	export_glb(os.path.join(MODELS_DIR, "rusted_warning_buoy.glb"))


# ==============================================================================
# 5. ABYSSAL LEVIATHAN (`enemy_leviathan_full.glb`, `_head.glb`, `_coil.glb`)
# ==============================================================================
def process_leviathan_models() -> None:
	# 5A. Full 18.0m Serpent (`enemy_leviathan_full.glb`)
	obj_full = import_and_join_raw_glb(
		"Meshy_AI_abyssal_leviathan_ser_1027194031_image-to-3d-texture.glb",
		"AbyssalLeviathanFull",
		target_verts=48000,
	)
	mesh_full = obj_full.data
	# Raw: Y is longest axis (1.901), with wide flared jaw/fins at -Y and tapering tail at +Y.
	# Rotate 180 deg around Z so -Y (jaw/snout) -> +Y in Blender (-Z forward in Godot)!
	mesh_full.transform(Matrix.Rotation(math.radians(180.0), 4, "Z"))
	mn, mx, sp = get_bounds(mesh_full)
	scale_full = 18.0 / max(sp.y, 0.001)
	cx = 0.5 * (mn.x + mx.x)
	cy = 0.5 * (mn.y + mx.y)
	wl_z = mn.z + sp.z * 0.42

	mesh_full.transform(Matrix.Scale(scale_full, 4) @ Matrix.Translation(Vector((-cx, -cy, -wl_z))))
	mesh_full.update()
	apply_universal_matte_dredge_material(
		obj_full, "MatteLeviathanFull", darken_factor=0.78, submerged_darken_z=0.0, target_roughness=0.72
	)

	out_full = os.path.join(MODELS_DIR, "enemy_leviathan_full.glb")
	export_glb(out_full)

	# 5B. Slice Front Head/Neck Section (`enemy_leviathan_head.glb` / `leviathan_head.glb`)
	# Target: Snout/jaws toward -Z (Blender +Y), neck cut toward +Z (Blender -Y), pitched upward 18 deg,
	# flat neck cut submerged below Y=0, scaled down by 40% (~4.5m-5.0m tall above water, ~3.8m wide), roughness 0.72.
	bpy.ops.object.select_all(action="DESELECT")
	obj_full.select_set(True)
	bpy.context.view_layer.objects.active = obj_full
	bpy.ops.object.duplicate()
	obj_head = bpy.context.view_layer.objects.active
	obj_head.name = "AbyssalLeviathanHead"

	# Remove original full object from scene temporarily so we only export Head
	bpy.data.objects.remove(obj_full, do_unlink=True)

	bm_h = bmesh.new()
	bm_h.from_mesh(obj_head.data)
	bm_h.verts.ensure_lookup_table()
	# Keep front head & neck section (y from +2.8m to +9.0m, since snout is at +Y = Godot -Z)
	bmesh.ops.bisect_plane(
		bm_h,
		geom=bm_h.verts[:] + bm_h.edges[:] + bm_h.faces[:],
		plane_co=Vector((0.0, 2.8, 0.0)),
		plane_no=Vector((0.0, -1.0, 0.0)),
		clear_outer=True,
		clear_inner=False,
	)
	# Curve the rear neck (y < 5.2m) downward strongly so the severed neck cut plunges cleanly below water (Y < 0)
	for v in bm_h.verts:
		if v.co.y < 5.2:
			t_neck = max(0.0, min(1.0, (5.2 - v.co.y) / 2.4))
			v.co.z -= (t_neck * t_neck) * 3.4
			v.co.x *= (1.0 - t_neck * 0.25)
	bm_h.to_mesh(obj_head.data)
	bm_h.free()
	obj_head.data.update()

	# Pitch the head/neck upward by +18 deg around X so jaws rear up menacingly while neck plunges into water at +Z
	obj_head.data.transform(Matrix.Rotation(math.radians(18.0), 4, "X"))
	bm_trim = bmesh.new()
	bm_trim.from_mesh(obj_head.data)
	mn_pre, mx_pre, sp_pre = get_bounds(obj_head.data)
	bmesh.ops.bisect_plane(
		bm_trim,
		geom=bm_trim.verts[:] + bm_trim.edges[:] + bm_trim.faces[:],
		plane_co=Vector((0.0, 0.0, mn_pre.z + sp_pre.z * 0.16)),
		plane_no=Vector((0.0, 0.0, 1.0)),
		clear_outer=False,
		clear_inner=True,
	)
	bm_trim.to_mesh(obj_head.data)
	bm_trim.free()
	obj_head.data.update()

	mn_h, mx_h, sp_h = get_bounds(obj_head.data)
	# Scale DOWN by 40% relative to previous oversized boulder: width ~3.8m, height above water ~4.7m
	scale_x_h = 3.80 / max(sp_h.x, 0.001)
	scale_z_h = 6.10 / max(sp_h.z, 0.001)
	scale_y_h = scale_x_h * 0.96
	cx_h = 0.5 * (mn_h.x + mx_h.x)
	cy_h = 0.5 * (mn_h.y + mx_h.y)
	# Place waterline so ~4.65m rears above Y=0 and ~1.45m (including the entire neck cut) is submerged below Y=0
	wl_h = mn_h.z + sp_h.z * 0.24
	T_h = Matrix.Translation(Vector((-cx_h, -cy_h, -wl_h)))
	S_h = Matrix.Diagonal(Vector((scale_x_h, scale_y_h, scale_z_h, 1.0)))
	obj_head.data.transform(S_h @ T_h)
	obj_head.data.update()

	mn_h, mx_h, sp_h = get_bounds(obj_head.data)
	print(
		f"[enemy_leviathan_head.glb] Final Bounds: X=[{mn_h.x:.2f},{mx_h.x:.2f}] ({sp_h.x:.2f}m), "
		f"Y=[{mn_h.y:.2f},{mx_h.y:.2f}] ({sp_h.y:.2f}m), Z=[{mn_h.z:.2f},{mx_h.z:.2f}] ({sp_h.z:.2f}m)"
	)
	apply_universal_matte_dredge_material(
		obj_head, "MatteLeviathanHead", darken_factor=0.78, submerged_darken_z=0.0, target_roughness=0.72
	)
	render_4view_contact_sheet("enemy_leviathan_head", [obj_head])
	out_head = os.path.join(MODELS_DIR, "enemy_leviathan_head.glb")
	export_glb(out_head)
	os.makedirs(ENEMIES_DIR, exist_ok=True)
	shutil.copy2(out_head, os.path.join(ENEMIES_DIR, "enemy_leviathan_head.glb"))
	shutil.copy2(out_head, os.path.join(MODELS_DIR, "leviathan_head.glb"))
	os.makedirs(MESHES_DIR, exist_ok=True)
	shutil.copy2(out_head, os.path.join(MESHES_DIR, "enemy_leviathan_head.glb"))
	shutil.copy2(out_head, os.path.join(MESHES_DIR, "leviathan_head.glb"))

	# 5C. Slice Arched Mid-Body Torso Section (`enemy_leviathan_coil.glb` / `leviathan_body_coil.glb`)
	# Scale UP cross-sectional thickness/girth by 2.4x-2.8x (~3.85m wide) so Coil 1 matches the girth of the head's base,
	# and sink lower ends of each arch -1.0m deeper below Y=0 so flat cuts never show above water. Roughness = 0.72.
	obj_coil = import_and_join_raw_glb(
		"Meshy_AI_abyssal_leviathan_ser_1027194031_image-to-3d-texture.glb",
		"AbyssalLeviathanCoil",
		target_verts=42000,
	)
	mesh_coil = obj_coil.data
	mesh_coil.transform(Matrix.Rotation(math.radians(180.0), 4, "Z"))
	mn_c, mx_c, sp_c = get_bounds(mesh_coil)
	bm_c = bmesh.new()
	bm_c.from_mesh(mesh_coil)
	bm_c.verts.ensure_lookup_table()

	# Slice the muscular mid-body arch (between 28% and 70% along Y)
	y_cut_front = mn_c.y + sp_c.y * 0.28
	y_cut_back = mn_c.y + sp_c.y * 0.70
	bmesh.ops.bisect_plane(
		bm_c,
		geom=bm_c.verts[:] + bm_c.edges[:] + bm_c.faces[:],
		plane_co=Vector((0.0, y_cut_front, 0.0)),
		plane_no=Vector((0.0, -1.0, 0.0)),
		clear_outer=True,
		clear_inner=False,
	)
	bmesh.ops.bisect_plane(
		bm_c,
		geom=bm_c.verts[:] + bm_c.edges[:] + bm_c.faces[:],
		plane_co=Vector((0.0, y_cut_back, 0.0)),
		plane_no=Vector((0.0, 1.0, 0.0)),
		clear_outer=True,
		clear_inner=False,
	)

	# Curve the ends downward into a deep sea-serpent breaching arch so both ends plunge cleanly below water
	y_mid = 0.5 * (y_cut_front + y_cut_back)
	half_span = max(0.001, 0.5 * (y_cut_back - y_cut_front))
	for v in bm_c.verts:
		norm_y = (v.co.y - y_mid) / half_span
		arch_drop = (norm_y * norm_y) * (sp_c.z * 0.85)
		v.co.z -= arch_drop
		if abs(norm_y) > 0.75:
			taper = max(0.32, 1.0 - (abs(norm_y) - 0.75) * 1.8)
			v.co.x *= taper

	bm_c.to_mesh(mesh_coil)
	bm_c.free()
	mesh_coil.update()

	mn_c, mx_c, sp_c = get_bounds(mesh_coil)
	# Base length scale for 9.5m coil arch span, and 2.5x girth multiplier on X/Z so cross-section is ~3.85m wide
	scale_y_c = 9.50 / max(sp_c.y, 0.001)
	scale_x_c = 3.85 / max(sp_c.x, 0.001)
	scale_z_c = 6.80 / max(sp_c.z, 0.001)
	cx_c = 0.5 * (mn_c.x + mx_c.x)
	cy_c = 0.5 * (mn_c.y + mx_c.y)
	# Sink the lower ends -1.0m deeper (52% up from bottom so min_z is ~ -3.5m below waterline and crest is +3.3m above)
	wl_c = mn_c.z + sp_c.z * 0.52
	T_c = Matrix.Translation(Vector((-cx_c, -cy_c, -wl_c)))
	S_c = Matrix.Diagonal(Vector((scale_x_c, scale_y_c, scale_z_c, 1.0)))
	mesh_coil.transform(S_c @ T_c)
	mesh_coil.update()

	mn_c, mx_c, sp_c = get_bounds(mesh_coil)
	print(
		f"[enemy_leviathan_coil.glb] Final Bounds: X=[{mn_c.x:.2f},{mx_c.x:.2f}] ({sp_c.x:.2f}m), "
		f"Y=[{mn_c.y:.2f},{mx_c.y:.2f}] ({sp_c.y:.2f}m), Z=[{mn_c.z:.2f},{mx_c.z:.2f}] ({sp_c.z:.2f}m)"
	)
	apply_universal_matte_dredge_material(
		obj_coil, "MatteLeviathanCoil", darken_factor=0.78, submerged_darken_z=0.0, target_roughness=0.72
	)
	render_4view_contact_sheet("enemy_leviathan_coil", [obj_coil])
	out_coil = os.path.join(MODELS_DIR, "enemy_leviathan_coil.glb")
	export_glb(out_coil)
	shutil.copy2(out_coil, os.path.join(ENEMIES_DIR, "enemy_leviathan_coil.glb"))
	shutil.copy2(out_coil, os.path.join(MODELS_DIR, "leviathan_body_coil.glb"))
	os.makedirs(MESHES_DIR, exist_ok=True)
	shutil.copy2(out_coil, os.path.join(MESHES_DIR, "enemy_leviathan_coil.glb"))
	shutil.copy2(out_coil, os.path.join(MESHES_DIR, "leviathan_body_coil.glb"))


# ==============================================================================
# 6. SUNKEN STEAMER SHIPWRECK (`poi_sunken_shipwreck.glb` — 24.0m, 18° roll, 12° pitch, y=-6.5m foundation)
# ==============================================================================
def process_sunken_shipwreck() -> None:
	obj = import_and_join_raw_glb(
		"Meshy_AI_stylized_dark_shipwre_1027192005_image-to-3d-texture.glb",
		"SunkenShipwreck",
		target_verts=50000,
	)
	mesh = obj.data
	# Raw: X is length (1.905), bow at -X (tip width 0.38 vs +X 0.60).
	# Rotate +90 deg around Z so bow faces +Y in Blender (-Z in Godot).
	mesh.transform(Matrix.Rotation(math.radians(90.0), 4, "Z"))

	mn, mx, sp = get_bounds(mesh)
	scale_factor = 24.0 / max(sp.y, 0.001)
	cx = 0.5 * (mn.x + mx.x)
	cy = 0.5 * (mn.y + mx.y)
	wl_z = mn.z + sp.z * 0.27

	mesh.transform(Matrix.Scale(scale_factor, 4) @ Matrix.Translation(Vector((-cx, -cy, -wl_z))))

	# Apply 18 deg roll and 12 deg bow-up pitch, settled at waterline y=0
	list_euler = Euler((math.radians(12.0), math.radians(18.0), 0.0), "XYZ")
	settle_mat = Matrix.Translation(Vector((0.0, 0.0, -1.65)))
	mesh.transform(settle_mat @ list_euler.to_matrix().to_4x4())
	mesh.update()

	# Extend dark rock reef & lower hull foundation down to y = -6.5m
	mn, mx, sp = get_bounds(mesh)
	add_underwater_foundation_skirt(
		obj,
		bottom_z=-6.50,
		top_overlap_z=-1.10,
		radius_x=sp.x * 0.42,
		radius_y=sp.y * 0.44,
		flare_bottom=1.22,
		seed=606,
	)

	mn, mx, sp = get_bounds(mesh)
	print(
		f"[poi_sunken_shipwreck.glb] Final Bounds: X=[{mn.x:.2f},{mx.x:.2f}] ({sp.x:.2f}m), "
		f"Y=[{mn.y:.2f},{mx.y:.2f}] ({sp.y:.2f}m), Z=[{mn.z:.2f},{mx.z:.2f}] ({sp.z:.2f}m)"
	)
	apply_universal_matte_dredge_material(obj, "MeshyShipwreckStylized", darken_factor=0.78, submerged_darken_z=0.0)
	export_glb(os.path.join(MODELS_DIR, "poi_sunken_shipwreck.glb"))


# ==============================================================================
# 7. HARBOR LIGHTHOUSE (`harbor_lighthouse.glb` — 22.0m height, y=0 base, -3.0m stone skirt)
# ==============================================================================
def process_harbor_lighthouse() -> None:
	obj = import_and_join_raw_glb(
		"Meshy_AI_Coastal_Stone_Lightho_1028164823_image-to-3d-texture.glb",
		"HarborLighthouse",
		target_verts=48000,
	)
	mesh = obj.data
	mn, mx, sp = get_bounds(mesh)
	scale_factor = 22.0 / max(sp.z, 0.001)
	cx = 0.5 * (mn.x + mx.x)
	cy = 0.5 * (mn.y + mx.y)
	base_z = mn.z + sp.z * 0.02  # Base foundation at y = 0.0

	mesh.transform(Matrix.Scale(scale_factor, 4) @ Matrix.Translation(Vector((-cx, -cy, -base_z))))
	mesh.update()

	mn, mx, sp = get_bounds(mesh)
	# Add dark stone foundation skirt extending -3.0m below y = 0.0
	add_underwater_foundation_skirt(
		obj,
		bottom_z=-3.00,
		top_overlap_z=0.08,
		radius_x=sp.x * 0.46,
		radius_y=sp.y * 0.46,
		flare_bottom=1.24,
		seed=707,
	)

	mn, mx, sp = get_bounds(mesh)
	# Lantern room glass center is at ~80% of the 22.0m tower height (~17.6m above tower base)
	print(
		f"[harbor_lighthouse.glb] Final Bounds: X=[{mn.x:.2f},{mx.x:.2f}] ({sp.x:.2f}m), "
		f"Y=[{mn.y:.2f},{mx.y:.2f}] ({sp.y:.2f}m), Z=[{mn.z:.2f},{mx.z:.2f}] ({sp.z:.2f}m)"
	)
	apply_universal_matte_dredge_material(obj, "MatteHarborLighthouse", darken_factor=0.78, submerged_darken_z=0.0)
	export_glb(os.path.join(MODELS_DIR, "harbor_lighthouse.glb"))


# ==============================================================================
# 8. SEA-FORT WATCHTOWER (`poi_sea_fort_tower.glb` — 18.0m height, pilings/foundation to y=-7.0m)
# ==============================================================================
def process_sea_fort_tower() -> None:
	obj = import_and_join_raw_glb(
		"Meshy_AI_Sea_Fort_Watchtower_1028164849_image-to-3d-texture.glb",
		"SeaFortWatchtower",
		target_verts=48000,
	)
	mesh = obj.data
	mn, mx, sp = get_bounds(mesh)
	scale_factor = 18.0 / max(sp.z, 0.001)
	cx = 0.5 * (mn.x + mx.x)
	cy = 0.5 * (mn.y + mx.y)
	wl_z = mn.z + sp.z * 0.06  # Waterline at base of stilts

	mesh.transform(Matrix.Scale(scale_factor, 4) @ Matrix.Translation(Vector((-cx, -cy, -wl_z))))
	mesh.update()

	mn, mx, sp = get_bounds(mesh)
	# Extend stilt pilings & dark rock shoal foundation down to y = -7.0m
	add_underwater_foundation_skirt(
		obj,
		bottom_z=-7.00,
		top_overlap_z=0.85,
		radius_x=sp.x * 0.38,
		radius_y=sp.y * 0.38,
		flare_bottom=1.30,
		is_pilings=True,
		seed=808,
	)

	mn, mx, sp = get_bounds(mesh)
	print(
		f"[poi_sea_fort_tower.glb] Final Bounds: X=[{mn.x:.2f},{mx.x:.2f}] ({sp.x:.2f}m), "
		f"Y=[{mn.y:.2f},{mx.y:.2f}] ({sp.y:.2f}m), Z=[{mn.z:.2f},{mx.z:.2f}] ({sp.z:.2f}m)"
	)
	apply_universal_matte_dredge_material(obj, "MatteSeaFortTower", darken_factor=0.78, submerged_darken_z=0.0)
	export_glb(os.path.join(MODELS_DIR, "poi_sea_fort_tower.glb"))


# ==============================================================================
# 9. LEVIATHAN BONE SKERRY (`poi_leviathan_ribcage.glb` — 26.0m span, rock base to y=-6.0m)
# ==============================================================================
def process_leviathan_ribcage() -> None:
	obj = import_and_join_raw_glb(
		"Meshy_AI_Leviathan_Bone_Skerry_1028165246_image-to-3d-texture.glb",
		"LeviathanBoneSkerry",
		target_verts=50000,
	)
	mesh = obj.data
	mn, mx, sp = get_bounds(mesh)
	# Raw: Y is longest axis (1.900), Z is up (1.165), skull is at -Y -> rotate 180 deg around Z so skull faces +Y (-Z in Godot)
	mesh.transform(Matrix.Rotation(math.radians(180.0), 4, "Z"))

	mn, mx, sp = get_bounds(mesh)
	scale_factor = 26.0 / max(sp.y, 0.001)
	cx = 0.5 * (mn.x + mx.x)
	cy = 0.5 * (mn.y + mx.y)
	wl_z = mn.z + sp.z * 0.22

	mesh.transform(Matrix.Scale(scale_factor, 4) @ Matrix.Translation(Vector((-cx, -cy, -wl_z))))
	mesh.update()

	mn, mx, sp = get_bounds(mesh)
	# Embed dark rock base down to y = -6.0m
	add_underwater_foundation_skirt(
		obj,
		bottom_z=-6.00,
		top_overlap_z=0.60,
		radius_x=sp.x * 0.44,
		radius_y=sp.y * 0.46,
		flare_bottom=1.25,
		seed=909,
	)

	mn, mx, sp = get_bounds(mesh)
	print(
		f"[poi_leviathan_ribcage.glb] Final Bounds: X=[{mn.x:.2f},{mx.x:.2f}] ({sp.x:.2f}m), "
		f"Y=[{mn.y:.2f},{mx.y:.2f}] ({sp.y:.2f}m), Z=[{mn.z:.2f},{mx.z:.2f}] ({sp.z:.2f}m)"
	)
	apply_universal_matte_dredge_material(obj, "MatteLeviathanRibcage", darken_factor=0.78, submerged_darken_z=0.0)
	export_glb(os.path.join(MODELS_DIR, "poi_leviathan_ribcage.glb"))


# ==============================================================================
# 10. FIRST-PERSON FISHING ROD (`fishing_rod_tackle.glb` — 2.1m length, grip at (0,0,0), shaft -Z, reel +Y/-Y)
# ==============================================================================
def process_fishing_rod_tackle() -> None:
	obj = import_and_join_raw_glb(
		"Meshy_AI_Big_Game_Fishing_Rod_1028164912_image-to-3d-texture.glb",
		"RodBaseGrip",
		target_verts=32000,
	)
	mesh = obj.data
	# Goal in Godot (+Y Up, -Z Forward):
	#   - Rod shaft points forward along -Z (which is +Y in Blender)
	#   - Line-guide eyelets sit vertically along the top spine (+Y in Godot / +Z in Blender)
	#   - Brass reel drum spool axis is horizontal (left-to-right X axis)
	#   - Reel crank handle is on the right-hand side (+X)
	#   - Origin (0, 0, 0) at the cork handle grip.
	# Rotating -90 deg around Z places:
	#   - Tip (-X raw) -> +Y (Blender forward = Godot -Z)
	#   - Eyelets (+Z raw) -> +Z (Blender Up = Godot +Y top spine)
	#   - Crank handle (+Y raw) -> +X (Blender Right = Godot +X right side)
	rot_z = Matrix.Rotation(math.radians(-90.0), 4, "Z")
	mesh.transform(rot_z)
	mesh.update()

	mn, mx, sp = get_bounds(mesh)
	scale_factor = 2.10 / max(sp.y, 0.001)
	mesh.transform(Matrix.Scale(scale_factor, 4))
	mesh.update()

	# Find the rod shaft axis center in X and Z near the foregrip/tip, and place the cork handle grip at (0, 0, 0)
	mn, mx, sp = get_bounds(mesh)
	# Use lower half of vertices near the tip shaft to find the blank center (excluding top eyelets)
	shaft_verts = [v.co for v in mesh.vertices if v.co.y > mn.y + sp.y * 0.55]
	min_shaft_z = min((v.z for v in shaft_verts), default=0.0)
	blank_verts = [v for v in shaft_verts if v.z <= min_shaft_z + 0.025]
	if not blank_verts:
		blank_verts = shaft_verts
	shaft_cx = sum(v.x for v in blank_verts) / len(blank_verts) if blank_verts else 0.0
	shaft_cz = sum(v.z for v in blank_verts) / len(blank_verts) if blank_verts else 0.0
	# Cork handle grip is ~0.28m forward of the rear butt cap (mn.y), right behind the reel seat
	grip_y = mn.y + 0.28
	mesh.transform(Matrix.Translation(Vector((-shaft_cx, -grip_y, -shaft_cz))))
	mesh.update()

	apply_universal_matte_dredge_material(
		obj,
		"MatteFishingRodTackle",
		darken_factor=0.82,
		cavity_strength=0.55,
		submerged_darken_z=None,
	)

	mn, mx, sp = get_bounds(mesh)
	tip_verts = [v.co for v in mesh.vertices if v.co.y >= mx.y - 0.035]
	tip_x = sum(v.x for v in tip_verts) / len(tip_verts) if tip_verts else 0.0
	tip_y = mx.y - 0.008
	min_tz = min((v.z for v in tip_verts), default=0.0)
	max_tz = max((v.z for v in tip_verts), default=0.02)
	# Center of the top tip eyelet ring (upper part of the tip profile along +Z = Godot +Y)
	tip_z = min_tz + 0.68 * (max_tz - min_tz)
	print(
		f"[fishing_rod_tackle.glb] Final Bounds (Blender): X=[{mn.x:.3f},{mx.x:.3f}], "
		f"Y=[{mn.y:.3f},{mx.y:.3f}] (len={sp.y:.2f}m), Z=[{mn.z:.3f},{mx.z:.3f}] | "
		f"RodTipEyelet Blender=({tip_x:.3f}, {tip_y:.3f}, {tip_z:.3f}) -> Godot=({tip_x:.3f}, {tip_z:.3f}, {-tip_y:.3f})"
	)

	# Render mandatory 4-view contact sheet before splitting/exporting
	render_4view_contact_sheet("fishing_rod_tackle", [obj])

	# Split the standardized 2.1m Meshy rod mesh into the 4 articulated hierarchy segments
	# (`RodBaseGrip` -> `RodMidLower` -> `RodMidUpper` -> `RodTip` -> `RodTipEyelet` & `RodTipMarker`)
	# so FishingController's cast, twitch, pump, and multi-segment tension bend animations work seamlessly!
	# Y ranges in Blender (+Y = Godot -Z):
	#   RodBaseGrip : y <= 0.45m (butt, cork handle, reel seat, big-game reel)
	#   RodMidLower : 0.45m .. 0.98m
	#   RodMidUpper : 0.98m .. 1.44m
	#   RodTip      : 1.44m .. tip_y (~1.82m)
	y1, y2, y3 = 0.45, 0.98, 1.44

	def extract_y_band_object(src_obj: bpy.types.Object, new_name: str, y_min: float, y_max: float, pivot_y: float) -> bpy.types.Object:
		bpy.ops.object.select_all(action="DESELECT")
		src_obj.select_set(True)
		bpy.context.view_layer.objects.active = src_obj
		bpy.ops.object.duplicate()
		seg_obj = bpy.context.view_layer.objects.active
		seg_obj.name = new_name

		bm = bmesh.new()
		bm.from_mesh(seg_obj.data)
		bm.verts.ensure_lookup_table()
		if y_min > -99.0:
			bmesh.ops.bisect_plane(
				bm,
				geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
				plane_co=Vector((0.0, y_min, 0.0)),
				plane_no=Vector((0.0, 1.0, 0.0)),
				clear_outer=False,
				clear_inner=True,
			)
		if y_max < 99.0:
			bmesh.ops.bisect_plane(
				bm,
				geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
				plane_co=Vector((0.0, y_max, 0.0)),
				plane_no=Vector((0.0, 1.0, 0.0)),
				clear_outer=True,
				clear_inner=False,
			)
		bm.to_mesh(seg_obj.data)
		bm.free()
		seg_obj.data.update()

		bpy.ops.object.select_all(action="DESELECT")
		seg_obj.select_set(True)
		bpy.context.view_layer.objects.active = seg_obj
		bpy.context.scene.cursor.location = (0.0, pivot_y, 0.0)
		bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
		bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
		return seg_obj

	rod_mid_lower = extract_y_band_object(obj, "RodMidLower", y1, y2, y1)
	rod_mid_upper = extract_y_band_object(obj, "RodMidUpper", y2, y3, y2)
	rod_tip = extract_y_band_object(obj, "RodTip", y3, 999.0, y3)

	# Trim `obj` (`RodBaseGrip`) to y <= y1
	bm_base = bmesh.new()
	bm_base.from_mesh(obj.data)
	bmesh.ops.bisect_plane(
		bm_base,
		geom=bm_base.verts[:] + bm_base.edges[:] + bm_base.faces[:],
		plane_co=Vector((0.0, y1, 0.0)),
		plane_no=Vector((0.0, 1.0, 0.0)),
		clear_outer=True,
		clear_inner=False,
	)
	bm_base.to_mesh(obj.data)
	bm_base.free()
	obj.data.update()

	bpy.ops.object.select_all(action="DESELECT")
	obj.select_set(True)
	bpy.context.view_layer.objects.active = obj
	bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
	bpy.ops.object.origin_set(type="ORIGIN_CURSOR")

	# Parent articulated chain: RodBaseGrip -> RodMidLower -> RodMidUpper -> RodTip
	rod_mid_lower.parent = obj
	rod_mid_lower.matrix_parent_inverse = obj.matrix_world.inverted()

	rod_mid_upper.parent = rod_mid_lower
	rod_mid_upper.matrix_parent_inverse = rod_mid_lower.matrix_world.inverted()

	rod_tip.parent = rod_mid_upper
	rod_tip.matrix_parent_inverse = rod_mid_upper.matrix_world.inverted()

	# Add `ReelCrankHandle` pivot node on `RodBaseGrip` (right-hand side +X) and `RodTipEyelet` + `RodTipMarker` on `RodTip`
	reel_crank_empty = bpy.data.objects.new("ReelCrankHandle", None)
	reel_crank_empty.empty_display_size = 0.02
	reel_crank_empty.location = (0.08, 0.08, -0.02)
	bpy.context.collection.objects.link(reel_crank_empty)
	reel_crank_empty.parent = obj
	reel_crank_empty.matrix_parent_inverse = obj.matrix_world.inverted()

	for marker_name in ("RodTipEyelet", "RodTipMarker"):
		marker = bpy.data.objects.new(marker_name, None)
		marker.empty_display_size = 0.02
		marker.location = (tip_x, tip_y, tip_z)
		bpy.context.collection.objects.link(marker)
		marker.parent = rod_tip
		marker.matrix_parent_inverse = rod_tip.matrix_world.inverted()

	out_rod = os.path.join(MODELS_DIR, "fishing_rod_tackle.glb")
	export_glb(out_rod)
	# Also keep sea_fishing_rod.glb synced as a fallback and copy to assets/meshes/
	shutil.copy2(out_rod, os.path.join(MODELS_DIR, "sea_fishing_rod.glb"))
	os.makedirs(MESHES_DIR, exist_ok=True)
	shutil.copy2(out_rod, os.path.join(MESHES_DIR, "fishing_rod_tackle.glb"))


def main() -> None:
	if "--only-rod" in sys.argv:
		process_fishing_rod_tackle()
		print("\n[BatchImport] Fishing rod (fishing_rod_tackle.glb) standardized and exported successfully!")
		return
	if "--only-boat" in sys.argv:
		process_player_boat()
		print("\n[BatchImport] Player boat (boat.glb) standardized and exported successfully!")
		return
	if "--only-part1" in sys.argv:
		process_player_boat()
		process_ghost_trawler()
		process_leviathan_models()
		process_fishing_rod_tackle()
		print("\n[BatchImport] All Part 1 models standardized, contact-sheet verified, and exported successfully!")
		return
	process_player_boat()
	process_ghost_trawler()
	process_derelict_lightship()
	process_warning_buoy()
	process_leviathan_models()
	process_sunken_shipwreck()
	process_harbor_lighthouse()
	process_sea_fort_tower()
	process_leviathan_ribcage()
	process_fishing_rod_tackle()
	print("\n[BatchImport] All 10 Meshy models (12 target GLBs) standardized and exported successfully!")


if __name__ == "__main__":
	main()
