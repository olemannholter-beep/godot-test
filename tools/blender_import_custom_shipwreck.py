#!/usr/bin/env python3
"""
Headless Blender 5.4.0 Custom Meshy Shipwreck Processor (tools/blender_import_custom_shipwreck.py)

Imports the raw Meshy shipwreck model from `res://assets/models/raw_meshy/`, cleans and decimates
the dense scan while preserving all UV maps and PBR textures (Base Color, Metallic/Roughness, Normal),
aligns the hull along -Z (forward) with +Y up, scales to ~26.0m coastal steamer length, applies
a half-submerged list (18 deg roll, 12 deg bow-up/stern-down pitch) with pivot at the waterline,
injects mesh curvature / cavity ink into vertex color attribute `Col` alongside wet seawater
clearcoat (`Roughness = 0.35`, `Coat Weight = 0.8`), and exports `res://assets/models/poi_sunken_shipwreck.glb`.
"""

import glob
import math
import os
import sys
import bpy
import bmesh
from mathutils import Euler, Matrix, Vector


PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_DIR: str = os.path.join(PROJECT_ROOT, "assets", "models", "raw_meshy")
FALLBACK_DOWNLOADS_DIR: str = r"C:\Users\olema\Downloads\pro models"
OUTPUT_GLB_PATH: str = os.path.join(PROJECT_ROOT, "assets", "models", "poi_sunken_shipwreck.glb")

TARGET_HULL_LENGTH: float = 26.0
TARGET_DECIMATE_VERTS: int = 55000
LIST_ROLL_DEG: float = 18.0
LIST_PITCH_BOW_UP_DEG: float = 12.0


def find_raw_shipwreck_file() -> str:
	for search_dir in (RAW_DIR, FALLBACK_DOWNLOADS_DIR):
		if not os.path.isdir(search_dir):
			continue
		for ext in ("*.glb", "*.gltf", "*.fbx", "*.obj"):
			matches = sorted(glob.glob(os.path.join(search_dir, ext)))
			if matches:
				return matches[0]
	raise FileNotFoundError(f"No shipwreck model found in {RAW_DIR} or {FALLBACK_DOWNLOADS_DIR}")


def clear_scene() -> None:
	bpy.ops.wm.read_factory_settings(use_empty=True)


def import_raw_model(filepath: str) -> None:
	ext = os.path.splitext(filepath)[1].lower()
	if ext in (".glb", ".gltf"):
		bpy.ops.import_scene.gltf(filepath=filepath)
	elif ext == ".fbx":
		bpy.ops.import_scene.fbx(filepath=filepath)
	elif ext == ".obj":
		bpy.ops.wm.obj_import(filepath=filepath)
	else:
		raise ValueError(f"Unsupported model extension: {ext}")


def clean_and_join_meshes() -> bpy.types.Object:
	# Remove non-mesh objects (cameras, lights, empties, armatures)
	to_remove = [obj for obj in bpy.data.objects if obj.type != "MESH"]
	for obj in to_remove:
		bpy.data.objects.remove(obj, do_unlink=True)

	mesh_objs = [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.data is not None]
	if not mesh_objs:
		raise RuntimeError("No mesh objects found in imported shipwreck file.")

	bpy.ops.object.select_all(action="DESELECT")
	for obj in mesh_objs:
		obj.select_set(True)
	bpy.context.view_layer.objects.active = mesh_objs[0]

	if len(mesh_objs) > 1:
		bpy.ops.object.join()

	hull_obj = bpy.context.view_layer.objects.active
	hull_obj.name = "SunkenShipwreck"
	bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
	return hull_obj


def decimate_preserving_uvs(hull_obj: bpy.types.Object) -> None:
	vert_count = len(hull_obj.data.vertices)
	print(f"[Shipwreck] Initial vertex count: {vert_count}")
	if vert_count > TARGET_DECIMATE_VERTS:
		ratio = max(0.015, min(1.0, float(TARGET_DECIMATE_VERTS) / float(vert_count)))
		print(f"[Shipwreck] Applying UV-preserving Collapse Decimate (ratio={ratio:.4f})...")
		mod = hull_obj.modifiers.new(name="OptimizeScan", type="DECIMATE")
		mod.decimate_type = "COLLAPSE"
		mod.ratio = ratio
		mod.use_collapse_triangulate = True
		bpy.context.view_layer.objects.active = hull_obj
		bpy.ops.object.modifier_apply(modifier=mod.name)
		print(f"[Shipwreck] Post-decimate vertex count: {len(hull_obj.data.vertices)}")


def remove_floating_debris_scraps(hull_obj: bpy.types.Object) -> None:
	bm = bmesh.new()
	bm.from_mesh(hull_obj.data)
	bm.verts.ensure_lookup_table()

	visited = set()
	islands = []
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
		max_size = max(len(c) for c in islands)
		# Remove tiny disconnected floating scraps (< 0.25% of main hull vertex count)
		threshold = max(12, int(max_size * 0.0025))
		removed_verts = 0
		for comp in islands:
			if len(comp) < threshold:
				for v in comp:
					bm.verts.remove(v)
				removed_verts += len(comp)
		if removed_verts > 0:
			print(f"[Shipwreck] Removed {removed_verts} disconnected debris scrap vertices.")

	bm.to_mesh(hull_obj.data)
	bm.free()
	hull_obj.data.update()


def orient_scale_and_tilt_hull(hull_obj: bpy.types.Object, flip_bow: bool = False) -> None:
	"""
	Align longest axis along Blender -Y (which exports to -Z forward in Godot glTF)
	with +Z up in Blender (+Y up in Godot), scale to 26.0m length, set pivot at waterline,
	and apply 18 deg roll + 12 deg bow-up/stern-down pitch.
	"""
	mesh = hull_obj.data
	xs = [v.co.x for v in mesh.vertices]
	ys = [v.co.y for v in mesh.vertices]
	zs = [v.co.z for v in mesh.vertices]

	span_x = max(xs) - min(xs)
	span_y = max(ys) - min(ys)
	span_z = max(zs) - min(zs)
	print(f"[Shipwreck] Raw spans: X={span_x:.3f}, Y={span_y:.3f}, Z={span_z:.3f}")

	# If X is the longest horizontal axis (as in Meshy export where X=1.905, Y=0.784, Z=1.391),
	# rotate 90 deg around Z so the longest axis lies along Y.
	if span_x > span_y:
		rot_z_90 = Matrix.Rotation(math.radians(90.0), 4, "Z")
		mesh.transform(rot_z_90)

	# Determine which end along Y (-Y vs +Y) is the bow vs stern.
	# In Blender, -Y exports to -Z (forward/bow in Godot), +Y exports to +Z (aft/stern in Godot).
	# Let's inspect the forward/aft ends to orient the bow toward -Y.
	ys = [v.co.y for v in mesh.vertices]
	min_y, max_y = min(ys), max(ys)
	len_y = max(max_y - min_y, 0.001)

	neg_end = [v.co for v in mesh.vertices if v.co.y < min_y + len_y * 0.22]
	pos_end = [v.co for v in mesh.vertices if v.co.y > max_y - len_y * 0.22]

	# Typically the bow prow reaches higher or narrows more sharply at the tip
	neg_tip = [v.co for v in mesh.vertices if v.co.y < min_y + len_y * 0.08]
	pos_tip = [v.co for v in mesh.vertices if v.co.y > max_y - len_y * 0.08]
	neg_tip_width = (max(v.x for v in neg_tip) - min(v.x for v in neg_tip)) if neg_tip else 1.0
	pos_tip_width = (max(v.x for v in pos_tip) - min(v.x for v in pos_tip)) if pos_tip else 1.0
	neg_max_z = max(v.z for v in neg_end) if neg_end else 0.0
	pos_max_z = max(v.z for v in pos_end) if pos_end else 0.0
	print(
		f"[Shipwreck] End analysis: -Y tip_width={neg_tip_width:.3f}, max_z={neg_max_z:.3f} | "
		f"+Y tip_width={pos_tip_width:.3f}, max_z={pos_max_z:.3f}"
	)

	# If +Y has a narrower prow tip than -Y, rotate 180 deg around Z so bow faces -Y
	should_flip = pos_tip_width < neg_tip_width
	if flip_bow:
		should_flip = not should_flip
	if should_flip:
		print("[Shipwreck] Rotating 180 deg around Z so bow faces -Y (-Z in Godot)")
		mesh.transform(Matrix.Rotation(math.radians(180.0), 4, "Z"))

	# Center X and Y around origin, and scale so total hull length along Y is TARGET_HULL_LENGTH (26.0m)
	xs = [v.co.x for v in mesh.vertices]
	ys = [v.co.y for v in mesh.vertices]
	zs = [v.co.z for v in mesh.vertices]
	center_x = 0.5 * (min(xs) + max(xs))
	center_y = 0.5 * (min(ys) + max(ys))
	min_z, max_z = min(zs), max(zs)
	cur_length = max(max(ys) - min(ys), 0.001)
	scale_factor = TARGET_HULL_LENGTH / cur_length

	# Place the natural waterline at Z = 0.0 before tilting (approx 27% up from keel bottom so lower hull is submerged)
	waterline_raw_z = min_z + (max_z - min_z) * 0.27
	translate_mat = Matrix.Translation(Vector((-center_x, -center_y, -waterline_raw_z)))
	scale_mat = Matrix.Scale(scale_factor, 4)
	mesh.transform(scale_mat @ translate_mat)

	# Apply dramatic half-submerged list:
	# - 18 deg roll around longitudinal Y axis
	# - 12 deg bow-up / stern-down pitch around lateral X axis
	#   (In Blender where bow is at -Y and up is +Z, rotating by -12 deg around +X raises -Y up and drops +Y down)
	pitch_rad = math.radians(-LIST_PITCH_BOW_UP_DEG)
	roll_rad = math.radians(LIST_ROLL_DEG)
	list_euler = Euler((pitch_rad, roll_rad, 0.0), "XYZ")
	list_mat = list_euler.to_matrix().to_4x4()
	# Settle vertically (-1.85m) so the waterline origin (Z=0 in Blender / Y=0 in Godot) cuts right across
	# the listed mid-hull: the stern propeller/rudder and lower keel sit submerged below Y=0 while the
	# raised bow, bulwarks, wheelhouse, smokestack, and masts jut menacingly out of the waves
	settle_mat = Matrix.Translation(Vector((0.0, 0.0, -1.85)))
	mesh.transform(settle_mat @ list_mat)
	mesh.update()

	xs = [v.co.x for v in mesh.vertices]
	ys = [v.co.y for v in mesh.vertices]
	zs = [v.co.z for v in mesh.vertices]
	print(
		f"[Shipwreck] Final Bounds (Blender space): "
		f"X=[{min(xs):.2f}, {max(xs):.2f}]m ({max(xs)-min(xs):.2f}m), "
		f"Y=[{min(ys):.2f}, {max(ys):.2f}]m ({max(ys)-min(ys):.2f}m), "
		f"Z=[{min(zs):.2f}, {max(zs):.2f}]m ({max(zs)-min(zs):.2f}m)"
	)


def inject_cavity_ink_and_stylize_material(hull_obj: bpy.types.Object) -> None:
	"""
	Compute mesh curvature / dirty-vertex cavity weights into vertex color attribute `Col`,
	preserve all Meshy PBR textures (Base Color, Metallic/Roughness, Normal), grade the base color
	texture so crevices and submerged timbers look richly inked rather than bright/plastic,
	and configure wet seawater clearcoat (`Roughness = 0.35`, `Coat Weight = 0.8`).
	"""
	mesh = hull_obj.data
	bm = bmesh.new()
	bm.from_mesh(mesh)
	bm.verts.ensure_lookup_table()
	bm.normal_update()

	# Compute per-vertex cavity / curvature + waterline darkening factor
	zs = [v.co.z for v in bm.verts]
	min_z, max_z = min(zs), max(zs)
	span_z = max(max_z - min_z, 0.001)

	raw_cavity = [0.0] * len(bm.verts)
	for v in bm.verts:
		edges = v.link_edges
		if not edges:
			raw_cavity[v.index] = 0.0
			continue
		avg_nbr = Vector((0.0, 0.0, 0.0))
		for e in edges:
			avg_nbr += e.other_vert(v).co
		avg_nbr /= float(len(edges))
		# Positive when neighbors are above v along v.normal (concave crevice/cavity)
		delta = avg_nbr - v.co
		edge_len = max(delta.length, 0.0001)
		concavity = delta.dot(v.normal) / edge_len
		raw_cavity[v.index] = concavity

	# 1-ring smoothing pass on cavity values for smooth artistic Dredge-style crevice ink
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

	# Remove any old color attributes and create `Col`
	while len(mesh.color_attributes) > 0:
		mesh.color_attributes.remove(mesh.color_attributes[0])

	col_attr = mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
	mesh.color_attributes.active_color = col_attr
	mesh.color_attributes.render_color_index = 0

	# Populate corner colors: deep crevices & submerged lower hull get dark maritime ink,
	# while upper hull planks and wheelhouse keep strong readable texture detail under the searchlight.
	flat_colors = [0.0] * (len(mesh.loops) * 4)
	for loop_idx, loop in enumerate(mesh.loops):
		v_idx = loop.vertex_index
		v_co = mesh.vertices[v_idx].co
		v_norm = mesh.vertices[v_idx].normal
		cav = smoothed_cavity[v_idx]

		# Concave crevices (cav > 0) darken strongly; convex ridges (cav < 0) stay crisp
		crevice_darken = max(0.0, min(1.0, cav * 2.8))
		ridge_boost = max(0.0, min(0.12, -cav * 0.45))

		# Subtle tidal darkening near/below waterline (z < 1.2m) and downward-facing overhangs
		height_t = max(0.0, min(1.0, (v_co.z - (-1.5)) / 4.5))
		tidal_shade = 0.72 + 0.28 * height_t
		downward_ao = 0.82 + 0.18 * max(0.0, min(1.0, (v_norm.z + 0.6) / 1.4))

		ink_val = (1.0 - crevice_darken * 0.62 + ridge_boost) * tidal_shade * downward_ao
		ink_val = max(0.24, min(0.96, ink_val))

		# Slight cool eldritch maritime tint in shadows, warm bone-neutral in highlights
		r = max(0.20, min(1.0, ink_val * 0.94))
		g = max(0.22, min(1.0, ink_val * 0.96))
		b = max(0.25, min(1.0, ink_val * 1.00))

		base = loop_idx * 4
		flat_colors[base] = r
		flat_colors[base + 1] = g
		flat_colors[base + 2] = b
		flat_colors[base + 3] = 1.0

	col_attr.data.foreach_set("color", flat_colors)
	print("[Shipwreck] Computed and assigned `Col` cavity ink vertex color attribute.")

	# Configure Principled BSDF materials: preserve Meshy textures, wire `Col` Multiply in shader tree,
	# and enforce weathered matte iron/timber finish (no glossy clearcoat, high roughness, low specular/metallic)
	for mat in mesh.materials:
		if mat is None or not mat.use_nodes or mat.node_tree is None:
			continue
		mat.name = "MeshyShipwreckStylized"
		nt = mat.node_tree
		bsdf = None
		base_tex_node = None
		orm_or_rough_links = []
		metal_links = []
		for node in nt.nodes:
			if node.type == "BSDF_PRINCIPLED":
				bsdf = node
			elif node.type == "TEX_IMAGE" and node.image is not None:
				# Identify Base Color texture node (connected to Base Color)
				for out_link in node.outputs["Color"].links:
					if out_link.to_socket.name == "Base Color":
						base_tex_node = node

		if bsdf is None:
			continue

		# 1. Disable glossy Clearcoat completely
		if "Coat Weight" in bsdf.inputs:
			bsdf.inputs["Coat Weight"].default_value = 0.0
		if "Coat Roughness" in bsdf.inputs:
			bsdf.inputs["Coat Roughness"].default_value = 0.85

		# 2. Lower Specular / IOR Level to 0.22 so corroded iron and barnacles do not shine like plastic
		if "IOR Level" in bsdf.inputs:
			bsdf.inputs["IOR Level"].default_value = 0.22
		elif "Specular IOR Level" in bsdf.inputs:
			bsdf.inputs["Specular IOR Level"].default_value = 0.22

		# 3. Clamp high Roughness (0.78 to 0.96) and low Metallic (<= 0.25)
		if "Roughness" in bsdf.inputs:
			rough_socket = bsdf.inputs["Roughness"]
			if rough_socket.is_linked:
				orig_from = rough_socket.links[0].from_socket
				nt.links.remove(rough_socket.links[0])
				map_rough = nt.nodes.new(type="ShaderNodeMapRange")
				map_rough.name = "ClampMatteRoughness"
				map_rough.clamp = True
				map_rough.inputs["From Min"].default_value = 0.0
				map_rough.inputs["From Max"].default_value = 1.0
				map_rough.inputs["To Min"].default_value = 0.78
				map_rough.inputs["To Max"].default_value = 0.96
				nt.links.new(orig_from, map_rough.inputs["Value"])
				nt.links.new(map_rough.outputs["Result"], rough_socket)
			else:
				rough_socket.default_value = 0.88

		if "Metallic" in bsdf.inputs:
			metal_socket = bsdf.inputs["Metallic"]
			if metal_socket.is_linked:
				orig_m_from = metal_socket.links[0].from_socket
				nt.links.remove(metal_socket.links[0])
				math_metal = nt.nodes.new(type="ShaderNodeMath")
				math_metal.name = "ScaleDownMetallic"
				math_metal.operation = "MULTIPLY"
				math_metal.use_clamp = True
				math_metal.inputs[1].default_value = 0.22
				nt.links.new(orig_m_from, math_metal.inputs[0])
				nt.links.new(math_metal.outputs["Value"], metal_socket)
			else:
				metal_socket.default_value = min(float(metal_socket.default_value), 0.20)

		# 4. Slightly darken Base Color multiplier (0.75x) so diffuse texture doesn't blow out under BowSearchlight
		if base_tex_node is not None and base_tex_node.image is not None:
			img = base_tex_node.image
			if not img.get("matte_darkened", False):
				px = list(img.pixels)
				for i in range(0, len(px), 4):
					px[i] = px[i] * 0.75
					px[i + 1] = px[i + 1] * 0.75
					px[i + 2] = px[i + 2] * 0.75
				img.pixels[:] = px
				img.pack()
				img["matte_darkened"] = True
			vcol_node = nt.nodes.new(type="ShaderNodeVertexColor")
			vcol_node.layer_name = "Col"
			mix_node = nt.nodes.new(type="ShaderNodeMix")
			mix_node.name = "CavityInkMultiply"
			mix_node.data_type = "RGBA"
			mix_node.blend_type = "MULTIPLY"
			mix_node.inputs[0].default_value = 1.0
			nt.links.new(base_tex_node.outputs["Color"], mix_node.inputs[6])
			nt.links.new(vcol_node.outputs["Color"], mix_node.inputs[7])
			nt.links.new(mix_node.outputs[2], bsdf.inputs["Base Color"])
			# Connect base_tex_node directly to Base Color for glTF baseColorTexture export,
			# while export_vertex_color='ACTIVE' exports the `Col` COLOR_0 attribute alongside it
			nt.links.new(base_tex_node.outputs["Color"], bsdf.inputs["Base Color"])


def main() -> None:
	flip_bow = "--flip-bow" in sys.argv
	raw_path = find_raw_shipwreck_file()
	print(f"[Shipwreck] Importing raw model: {raw_path}")

	clear_scene()
	import_raw_model(raw_path)
	hull_obj = clean_and_join_meshes()
	decimate_preserving_uvs(hull_obj)
	remove_floating_debris_scraps(hull_obj)
	orient_scale_and_tilt_hull(hull_obj, flip_bow=flip_bow)
	inject_cavity_ink_and_stylize_material(hull_obj)

	os.makedirs(os.path.dirname(OUTPUT_GLB_PATH), exist_ok=True)
	bpy.ops.export_scene.gltf(
		filepath=OUTPUT_GLB_PATH,
		export_format="GLB",
		export_apply=True,
		export_texcoords=True,
		export_normals=True,
		export_vertex_color="ACTIVE",
		export_all_vertex_colors=True,
		export_materials="EXPORT",
	)
	print(f"[Shipwreck] Successfully exported stylized shipwreck to: {OUTPUT_GLB_PATH}")


if __name__ == "__main__":
	main()
