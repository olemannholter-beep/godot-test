#!/usr/bin/env python3
"""
Headless Blender 5.4.0 4-Angle Contact-Sheet Preview Renderer (tools/blender_render_preview.py)

Renders a 1920x1080 4-quadrant contact sheet (Front, Side Profile, 3/4 Perspective, Silhouette)
of any .glb model into `res://.mcp_captures/<model_name>_sheet.png`.

Usage:
  blender --background --python tools/blender_render_preview.py -- assets/models/fish/fish_angler.glb
"""

import math
import os
import sys
import tempfile
from typing import List, Tuple
import bpy
from mathutils import Matrix, Vector


QUAD_W: int = 960
QUAD_H: int = 540
SHEET_W: int = QUAD_W * 2
SHEET_H: int = QUAD_H * 2


def clear_scene() -> None:
	bpy.ops.wm.read_factory_settings(use_empty=True)


def get_mesh_world_bbox_corners() -> Tuple[Vector, Vector, List[Vector]]:
	min_v = Vector((1e9, 1e9, 1e9))
	max_v = Vector((-1e9, -1e9, -1e9))
	found = False

	for obj in bpy.context.scene.objects:
		if obj.type != "MESH" or obj.data is None:
			continue
		mw: Matrix = obj.matrix_world
		for v in obj.data.vertices:
			wv: Vector = mw @ v.co
			min_v.x = min(min_v.x, wv.x)
			min_v.y = min(min_v.y, wv.y)
			min_v.z = min(min_v.z, wv.z)
			max_v.x = max(max_v.x, wv.x)
			max_v.y = max(max_v.y, wv.y)
			max_v.z = max(max_v.z, wv.z)
			found = True

	if not found:
		min_v = Vector((-0.5, -0.5, -0.5))
		max_v = Vector((0.5, 0.5, 0.5))

	corners = [
		Vector((x, y, z))
		for x in (min_v.x, max_v.x)
		for y in (min_v.y, max_v.y)
		for z in (min_v.z, max_v.z)
	]
	return min_v, max_v, corners


def ensure_vertex_color_wired() -> None:
	"""Ensure imported glTF materials multiply their Base Color with vertex color attributes if not already linked."""
	for obj in bpy.context.scene.objects:
		if obj.type != "MESH" or obj.data is None:
			continue
		mesh = obj.data
		if len(mesh.color_attributes) == 0:
			continue
		col_name = mesh.color_attributes[0].name
		for mat in mesh.materials:
			if mat is None or not mat.use_nodes or mat.node_tree is None:
				continue
			nt = mat.node_tree
			bsdf = None
			has_vcol = False
			for node in nt.nodes:
				if node.type == "BSDF_PRINCIPLED":
					bsdf = node
				elif node.type in ("VERTEX_COLOR", "ATTRIBUTE"):
					has_vcol = True
			if bsdf is not None and not has_vcol:
				base_in = bsdf.inputs.get("Base Color")
				if base_in is not None:
					vcol_node = nt.nodes.new(type="ShaderNodeVertexColor")
					vcol_node.layer_name = col_name
					if not base_in.is_linked:
						orig_col = tuple(base_in.default_value)
						# If material base color is near-white, wire directly; otherwise multiply
						if orig_col[0] > 0.92 and orig_col[1] > 0.92 and orig_col[2] > 0.92:
							nt.links.new(vcol_node.outputs["Color"], base_in)
						else:
							mix_node = nt.nodes.new(type="ShaderNodeMix")
							mix_node.data_type = "RGBA"
							mix_node.blend_type = "MULTIPLY"
							mix_node.inputs[0].default_value = 1.0
							mix_node.inputs[6].default_value = orig_col
							nt.links.new(vcol_node.outputs["Color"], mix_node.inputs[7])
							nt.links.new(mix_node.outputs[2], base_in)
					else:
						from_socket = base_in.links[0].from_socket
						mix_node = nt.nodes.new(type="ShaderNodeMix")
						mix_node.data_type = "RGBA"
						mix_node.blend_type = "MULTIPLY"
						mix_node.inputs[0].default_value = 1.0
						nt.links.new(from_socket, mix_node.inputs[6])
						nt.links.new(vcol_node.outputs["Color"], mix_node.inputs[7])
						nt.links.new(mix_node.outputs[2], base_in)


def setup_world_background(color: Tuple[float, float, float, float], strength: float = 1.0) -> None:
	scene = bpy.context.scene
	if scene.world is None:
		scene.world = bpy.data.worlds.new("PreviewWorld")
	world = scene.world
	world.use_nodes = True
	nt = world.node_tree
	bg = nt.nodes.get("Background")
	if bg is None:
		bg = nt.nodes.new(type="ShaderNodeBackground")
	bg.inputs["Color"].default_value = color
	bg.inputs["Strength"].default_value = strength


def setup_studio_lights(center: Vector, radius: float) -> Tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object]:
	# 1. Warm Lantern Key Light (upper front-left)
	key_data = bpy.data.lights.new(name="KeyLight", type="SUN")
	key_data.energy = 4.2
	key_data.color = (1.0, 0.90, 0.74)
	key_data.angle = math.radians(8.0)
	key_obj = bpy.data.objects.new(name="KeyLight", object_data=key_data)
	bpy.context.collection.objects.link(key_obj)
	key_dir = Vector((-0.55, 0.65, -0.52)).normalized()
	key_obj.location = center - key_dir * (radius * 3.0)
	key_obj.rotation_euler = key_dir.to_track_quat("-Z", "Y").to_euler()

	# 2. Eldritch Teal/Moonlight Rim Light (strong back-top edge highlight)
	rim_data = bpy.data.lights.new(name="RimLight", type="SUN")
	rim_data.energy = 5.5
	rim_data.color = (0.48, 0.88, 0.96)
	rim_data.angle = math.radians(6.0)
	rim_obj = bpy.data.objects.new(name="RimLight", object_data=rim_data)
	bpy.context.collection.objects.link(rim_obj)
	rim_dir = Vector((0.45, -0.75, -0.48)).normalized()
	rim_obj.location = center - rim_dir * (radius * 3.0)
	rim_obj.rotation_euler = rim_dir.to_track_quat("-Z", "Y").to_euler()

	# 3. Cool Deep Sea Fill Light (soft under/side fill so ink cavities remain readable)
	fill_data = bpy.data.lights.new(name="FillLight", type="SUN")
	fill_data.energy = 1.65
	fill_data.color = (0.42, 0.56, 0.72)
	fill_data.angle = math.radians(25.0)
	fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_data)
	bpy.context.collection.objects.link(fill_obj)
	fill_dir = Vector((0.65, 0.35, 0.65)).normalized()
	fill_obj.location = center - fill_dir * (radius * 3.0)
	fill_obj.rotation_euler = fill_dir.to_track_quat("-Z", "Y").to_euler()

	return key_obj, rim_obj, fill_obj


def fit_camera_to_corners(
	cam_obj: bpy.types.Object,
	center: Vector,
	corners: List[Vector],
	camera_offset_dir: Vector,
	ortho: bool = True,
	margin: float = 1.24,
	up_vec: Vector = Vector((0.0, 0.0, 1.0)),
) -> None:
	"""
	Positions `cam_obj` along `center + camera_offset_dir * dist` looking at `center`,
	constructing an explicit orthonormal camera basis where `cam_up` aligns with `up_vec`
	and `cam_right` spans the horizontal 16:9 axis.
	"""
	cam_back: Vector = camera_offset_dir.normalized()
	up_hint: Vector = up_vec.normalized()
	if abs(cam_back.dot(up_hint)) > 0.96:
		up_hint = Vector((0.0, 1.0, 0.0)) if abs(up_hint.z) > 0.5 else Vector((0.0, 0.0, 1.0))

	cam_right: Vector = up_hint.cross(cam_back).normalized()
	cam_up: Vector = cam_back.cross(cam_right).normalized()

	cam_basis: Matrix = Matrix((
		(cam_right.x, cam_up.x, cam_back.x),
		(cam_right.y, cam_up.y, cam_back.y),
		(cam_right.z, cam_up.z, cam_back.z),
	))
	rot_quat = cam_basis.to_quaternion()

	max_x = 0.01
	max_y = 0.01
	max_z = 0.01
	for c in corners:
		rel = c - center
		px = abs(rel.dot(cam_right))
		py = abs(rel.dot(cam_up))
		pz = abs(rel.dot(cam_back))
		max_x = max(max_x, px)
		max_y = max(max_y, py)
		max_z = max(max_z, pz)

	aspect = float(QUAD_W) / float(QUAD_H)
	cam_data: bpy.types.Camera = cam_obj.data
	cam_data.clip_start = 0.005
	cam_data.clip_end = 250.0

	if ortho:
		cam_data.type = "ORTHO"
		req_width = max(max_x * 2.0, (max_y * 2.0) * aspect) * margin
		cam_data.ortho_scale = max(0.05, req_width)
		dist = max(1.5, max_z * 3.5 + 1.0)
	else:
		cam_data.type = "PERSP"
		cam_data.lens = 55.0
		cam_data.sensor_fit = "HORIZONTAL"
		hfov = cam_data.angle
		vfov = 2.0 * math.atan(math.tan(hfov * 0.5) / aspect)
		dist_x = (max_x * margin) / max(0.05, math.tan(hfov * 0.5))
		dist_y = (max_y * margin) / max(0.05, math.tan(vfov * 0.5))
		dist = max(dist_x, dist_y) + max_z * 1.15

	cam_obj.location = center + cam_back * dist
	cam_obj.rotation_euler = rot_quat.to_euler()


def composite_four_quadrants(
	tl_path: str,
	tr_path: str,
	bl_path: str,
	br_path: str,
	out_sheet_path: str,
) -> None:
	img_tl = bpy.data.images.load(tl_path)
	img_tr = bpy.data.images.load(tr_path)
	img_bl = bpy.data.images.load(bl_path)
	img_br = bpy.data.images.load(br_path)

	px_tl = list(img_tl.pixels)
	px_tr = list(img_tr.pixels)
	px_bl = list(img_bl.pixels)
	px_br = list(img_br.pixels)

	sheet = bpy.data.images.new("ContactSheet", width=SHEET_W, height=SHEET_H, alpha=True)
	sheet_px = [0.0] * (SHEET_W * SHEET_H * 4)

	row_stride_quad = QUAD_W * 4
	row_stride_sheet = SHEET_W * 4

	# Note: Blender image pixel rows start at bottom-left (y = 0 is bottom)
	for y in range(QUAD_H):
		q_offset = y * row_stride_quad

		# Bottom row (y in [0, QUAD_H)): Bottom-Left & Bottom-Right
		s_bot_offset = y * row_stride_sheet
		sheet_px[s_bot_offset : s_bot_offset + row_stride_quad] = px_bl[q_offset : q_offset + row_stride_quad]
		sheet_px[s_bot_offset + row_stride_quad : s_bot_offset + row_stride_sheet] = px_br[q_offset : q_offset + row_stride_quad]

		# Top row (y + QUAD_H): Top-Left & Top-Right
		s_top_offset = (y + QUAD_H) * row_stride_sheet
		sheet_px[s_top_offset : s_top_offset + row_stride_quad] = px_tl[q_offset : q_offset + row_stride_quad]
		sheet_px[s_top_offset + row_stride_quad : s_top_offset + row_stride_sheet] = px_tr[q_offset : q_offset + row_stride_quad]

	# Draw a crisp 2px tarnished-brass divider crosshair between quadrants
	div_col = (0.55, 0.43, 0.23, 1.0)
	for y in range(QUAD_H - 1, QUAD_H + 1):
		row_start = y * row_stride_sheet
		for x in range(SHEET_W):
			idx = row_start + x * 4
			sheet_px[idx : idx + 4] = div_col

	for y in range(SHEET_H):
		row_start = y * row_stride_sheet
		for x in range(QUAD_W - 1, QUAD_W + 1):
			idx = row_start + x * 4
			sheet_px[idx : idx + 4] = div_col

	sheet.pixels.foreach_set(sheet_px)
	sheet.filepath_raw = out_sheet_path
	sheet.file_format = "PNG"
	sheet.save()

	for tmp_img in (img_tl, img_tr, img_bl, img_br, sheet):
		bpy.data.images.remove(tmp_img)


def render_glb_contact_sheet(glb_path: str, out_dir: str) -> str:
	clear_scene()

	abs_glb = os.path.abspath(glb_path)
	if not os.path.isfile(abs_glb):
		raise FileNotFoundError(f"GLB file not found: {abs_glb}")

	bpy.ops.import_scene.gltf(filepath=abs_glb)
	bpy.context.view_layer.update()
	ensure_vertex_color_wired()

	min_v, max_v, corners = get_mesh_world_bbox_corners()
	center = 0.5 * (min_v + max_v)
	size = max_v - min_v
	radius = max(0.1, size.length * 0.5)

	# Fish catalog models are authored with +Y dorsal and +Z longitudinal axis;
	# all other Blender Z-up assets have +Z as vertical up after view_layer.update().
	is_fish_asset = os.path.basename(abs_glb).startswith("fish_")
	if not is_fish_asset:
		front_dir = Vector((0.08, -1.0, 0.08))
		side_dir = Vector((1.0, 0.0, 0.04))
		persp_dir = Vector((0.72, -0.68, 0.34))
		up_vec = Vector((0.0, 0.0, 1.0))
	else:
		front_dir = Vector((0.0, 0.08, 1.0))
		side_dir = Vector((1.0, 0.04, 0.0))
		persp_dir = Vector((0.72, 0.34, 0.68))
		up_vec = Vector((0.0, 1.0, 0.0))

	scene = bpy.context.scene
	available_engines = {
		item.identifier
		for item in scene.render.bl_rna.properties["engine"].enum_items
	}
	if "BLENDER_EEVEE" in available_engines:
		scene.render.engine = "BLENDER_EEVEE"
	elif "BLENDER_EEVEE_NEXT" in available_engines:
		scene.render.engine = "BLENDER_EEVEE_NEXT"
	else:
		scene.render.engine = "BLENDER_WORKBENCH"

	scene.render.resolution_x = QUAD_W
	scene.render.resolution_y = QUAD_H
	scene.render.resolution_percentage = 100
	scene.render.image_settings.file_format = "PNG"
	scene.render.image_settings.color_mode = "RGBA"
	scene.render.film_transparent = False

	if hasattr(scene, "eevee"):
		if hasattr(scene.eevee, "taa_render_samples"):
			scene.eevee.taa_render_samples = 16

	cam_data = bpy.data.cameras.new("PreviewCamera")
	cam_obj = bpy.data.objects.new("PreviewCamera", cam_data)
	bpy.context.collection.objects.link(cam_obj)
	scene.camera = cam_obj

	key_obj, rim_obj, fill_obj = setup_studio_lights(center, radius)

	# Dark eldritch slate background for shaded views
	setup_world_background((0.032, 0.045, 0.058, 1.0), strength=0.85)

	tmp_dir = tempfile.mkdtemp(prefix="blender_sheet_")
	tl_path = os.path.join(tmp_dir, "quad_tl_front.png")
	tr_path = os.path.join(tmp_dir, "quad_tr_side.png")
	bl_path = os.path.join(tmp_dir, "quad_bl_persp.png")
	br_path = os.path.join(tmp_dir, "quad_br_silhouette.png")

	# 1. Top-Left: Front View
	fit_camera_to_corners(cam_obj, center, corners, front_dir, ortho=True, margin=1.28, up_vec=up_vec)
	scene.render.filepath = tl_path
	bpy.ops.render.render(write_still=True)

	# 2. Top-Right: Side Profile View
	fit_camera_to_corners(cam_obj, center, corners, side_dir, ortho=True, margin=1.16, up_vec=up_vec)
	scene.render.filepath = tr_path
	bpy.ops.render.render(write_still=True)

	# 3. Bottom-Left: 3/4 Perspective View
	fit_camera_to_corners(cam_obj, center, corners, persp_dir, ortho=False, margin=1.16, up_vec=up_vec)
	scene.render.filepath = bl_path
	bpy.ops.render.render(write_still=True)

	# 4. Bottom-Right: High-Contrast Graphic Silhouette View
	# Convert non-emissive materials to pure charcoal-black flat silhouette against a bright misty backdrop
	setup_world_background((0.56, 0.64, 0.66, 1.0), strength=1.15)
	key_obj.data.energy = 0.0
	fill_obj.data.energy = 0.0
	rim_obj.data.energy = 0.0
	for obj in bpy.context.scene.objects:
		if obj.type != "MESH" or obj.data is None:
			continue
		for mat in obj.data.materials:
			if mat is None or not mat.use_nodes or mat.node_tree is None:
				continue
			nt = mat.node_tree
			for node in nt.nodes:
				if node.type == "BSDF_PRINCIPLED":
					em_str = node.inputs.get("Emission Strength")
					if em_str is not None and em_str.default_value > 0.5:
						continue
					base_in = node.inputs.get("Base Color")
					if base_in is not None:
						for link in list(base_in.links):
							nt.links.remove(link)
						base_in.default_value = (0.012, 0.016, 0.022, 1.0)
					if "Metallic" in node.inputs:
						node.inputs["Metallic"].default_value = 0.0
					if "Roughness" in node.inputs:
						node.inputs["Roughness"].default_value = 1.0
					if "Coat Weight" in node.inputs:
						node.inputs["Coat Weight"].default_value = 0.0
					if "IOR" in node.inputs:
						node.inputs["IOR"].default_value = 1.0
	silhouette_dir = front_dir if (not is_fish_asset and size.x > size.y * 1.4) else side_dir
	fit_camera_to_corners(cam_obj, center, corners, silhouette_dir, ortho=True, margin=1.16, up_vec=up_vec)
	scene.render.filepath = br_path
	bpy.ops.render.render(write_still=True)

	model_stem = os.path.splitext(os.path.basename(abs_glb))[0]
	os.makedirs(out_dir, exist_ok=True)
	out_sheet_path = os.path.join(out_dir, f"{model_stem}_sheet.png")
	composite_four_quadrants(tl_path, tr_path, bl_path, br_path, out_sheet_path)

	for p in (tl_path, tr_path, bl_path, br_path):
		if os.path.exists(p):
			os.remove(p)
	try:
		os.rmdir(tmp_dir)
	except OSError:
		pass

	print(f"Saved 4-angle contact sheet: {out_sheet_path}")
	return out_sheet_path


def main() -> None:
	project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	captures_dir = os.path.join(project_root, ".mcp_captures")

	argv = sys.argv
	user_args: List[str] = []
	if "--" in argv:
		user_args = argv[argv.index("--") + 1 :]

	if not user_args:
		user_args = [
			os.path.join(project_root, "assets", "models", "fish", "fish_angler.glb"),
			os.path.join(project_root, "assets", "models", "fish", "fish_cod.glb"),
			os.path.join(project_root, "assets", "models", "sea_fishing_rod.glb"),
		]

	for target in user_args:
		if not os.path.isabs(target):
			target = os.path.join(project_root, target)
		render_glb_contact_sheet(target, captures_dir)


if __name__ == "__main__":
	main()
