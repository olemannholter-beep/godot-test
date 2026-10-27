#!/usr/bin/env python3
"""
Headless Blender 5.4.0 generator for the 3D Stern Winch Fishing Minigame assets:
  1. res://assets/models/winch_tension_rig.glb
     - WinchHousing (beveled cast-iron pedestal + boolean-carved recessed dial cavity + backlit AmberGlass dial + redline arc)
     - GaugeNeedle  (pivoted at the dial center for -120..+120 deg rotation in Godot)
     - WinchSpool   (pivoted at the horizontal drum axis, wound with beveled 3D CURVE steel cable coils)
     - TrawlWeight  (beveled steel trawl-door / hook sinker weight)
  2. res://assets/models/catch_fish_cod.glb
     - ~1.1m sculpted wet-skinned Atlantic Cod (multi-station bmesh loft + SUBSURF + Voronoi/Clouds DISPLACE + fins)
"""

import math
import os
from typing import Dict, List, Tuple
import bpy
import bmesh
from mathutils import Vector


def clear_scene() -> None:
	bpy.ops.wm.read_factory_settings(use_empty=True)


def create_pbr_material(
	name: str,
	base_color: Tuple[float, float, float, float],
	metallic: float = 0.0,
	roughness: float = 0.5,
	emission_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
	emission_strength: float = 0.0,
) -> bpy.types.Material:
	mat: bpy.types.Material = bpy.data.materials.new(name=name)
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
	return mat


def add_bevel_modifier(obj: bpy.types.Object, width: float = 0.008, segments: int = 2) -> None:
	bevel = obj.modifiers.new(name="Bevel", type="BEVEL")
	bevel.width = width
	bevel.segments = segments
	bevel.limit_method = "ANGLE"
	bevel.angle_limit = math.radians(32.0)


def apply_all_modifiers(obj: bpy.types.Object) -> None:
	bpy.context.view_layer.objects.active = obj
	for mod in list(obj.modifiers):
		bpy.ops.object.modifier_apply(modifier=mod.name)


def build_winch_tension_rig(out_glb_path: str) -> None:
	clear_scene()

	mat_dark_metal = create_pbr_material("DarkMetal", (0.08, 0.09, 0.10, 1.0), metallic=0.78, roughness=0.46)
	mat_rust_iron = create_pbr_material("RustIron", (0.17, 0.11, 0.09, 1.0), metallic=0.65, roughness=0.58)
	mat_brass = create_pbr_material("WeatheredBrass", (0.62, 0.46, 0.18, 1.0), metallic=0.86, roughness=0.32)
	mat_amber_dial = create_pbr_material(
		"AmberGlass",
		(0.95, 0.78, 0.42, 1.0),
		metallic=0.05,
		roughness=0.18,
		emission_color=(1.0, 0.72, 0.30, 1.0),
		emission_strength=2.4,
	)
	mat_red_zone = create_pbr_material(
		"GaugeRedZone",
		(0.85, 0.14, 0.10, 1.0),
		metallic=0.1,
		roughness=0.25,
		emission_color=(0.95, 0.16, 0.10, 1.0),
		emission_strength=3.2,
	)
	mat_green_zone = create_pbr_material(
		"GaugeGreenZone",
		(0.18, 0.75, 0.32, 1.0),
		metallic=0.1,
		roughness=0.25,
		emission_color=(0.20, 0.82, 0.35, 1.0),
		emission_strength=1.8,
	)
	mat_steel_cable = create_pbr_material("SteelCable", (0.32, 0.35, 0.38, 1.0), metallic=0.88, roughness=0.30)

	housing_parts: List[bpy.types.Object] = []

	# 1. Cast-iron deck pedestal & side cheek plates supporting the spool
	bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.06))
	base_plinth = bpy.context.active_object
	base_plinth.name = "BasePlinth"
	base_plinth.scale = (0.64, 0.54, 0.12)
	bpy.ops.object.transform_apply(scale=True)
	add_bevel_modifier(base_plinth, width=0.012, segments=2)
	apply_all_modifiers(base_plinth)
	base_plinth.data.materials.append(mat_rust_iron)
	housing_parts.append(base_plinth)

	# Side A-frame cheek stanchions for the winch drum (at x = -0.24 and x = +0.24)
	for sx in (-0.24, 0.24):
		bpy.ops.mesh.primitive_cube_add(size=1.0, location=(sx, 0.02, 0.36))
		cheek = bpy.context.active_object
		cheek.scale = (0.06, 0.42, 0.52)
		bpy.ops.object.transform_apply(scale=True)
		add_bevel_modifier(cheek, width=0.008, segments=2)
		apply_all_modifiers(cheek)
		cheek.data.materials.append(mat_dark_metal)
		housing_parts.append(cheek)

		# Bearing boss collar on outer cheek
		bpy.ops.mesh.primitive_cylinder_add(
			vertices=16,
			radius=0.085,
			depth=0.09,
			location=(sx, 0.02, 0.38),
			rotation=(0.0, math.radians(90.0), 0.0),
		)
		boss = bpy.context.active_object
		add_bevel_modifier(boss, width=0.005, segments=2)
		apply_all_modifiers(boss)
		boss.data.materials.append(mat_rust_iron)
		housing_parts.append(boss)

	# 2. Upper Instrument Column & Boolean-Carved Brass Pressure Dial Housing
	# Dial center in Blender coordinates: (0.0, -0.17, 0.86) -> in Godot: (0.0, 0.86, 0.17) facing -Z (toward camera)
	dial_center_bl = Vector((0.0, -0.16, 0.86))

	bpy.ops.mesh.primitive_cylinder_add(
		vertices=16,
		radius=0.065,
		depth=0.42,
		location=(0.0, -0.08, 0.66),
	)
	neck_col = bpy.context.active_object
	add_bevel_modifier(neck_col, width=0.005, segments=2)
	apply_all_modifiers(neck_col)
	neck_col.data.materials.append(mat_dark_metal)
	housing_parts.append(neck_col)

	# Cast-iron dial drum body
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=28,
		radius=0.22,
		depth=0.14,
		location=(dial_center_bl.x, dial_center_bl.y + 0.05, dial_center_bl.z),
		rotation=(math.radians(90.0), 0.0, 0.0),
	)
	dial_case = bpy.context.active_object
	dial_case.name = "DialCaseBody"
	add_bevel_modifier(dial_case, width=0.008, segments=2)
	apply_all_modifiers(dial_case)
	dial_case.data.materials.append(mat_dark_metal)

	# Real BOOLEAN DIFFERENCE cutter to carve the recessed circular dial cavity facing -Y (Godot -Z)
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=28,
		radius=0.175,
		depth=0.08,
		location=(dial_center_bl.x, dial_center_bl.y - 0.01, dial_center_bl.z),
		rotation=(math.radians(90.0), 0.0, 0.0),
	)
	dial_cutter = bpy.context.active_object
	bool_mod = dial_case.modifiers.new(name="DialCavity", type="BOOLEAN")
	bool_mod.operation = "DIFFERENCE"
	bool_mod.object = dial_cutter
	bpy.context.view_layer.objects.active = dial_case
	bpy.ops.object.modifier_apply(modifier=bool_mod.name)
	bpy.data.objects.remove(dial_cutter, do_unlink=True)
	housing_parts.append(dial_case)

	# WeatheredBrass outer bezel ring & 8 perimeter rivets around the dial face
	bpy.ops.mesh.primitive_torus_add(
		major_segments=28,
		minor_segments=10,
		major_radius=0.195,
		minor_radius=0.024,
		location=(dial_center_bl.x, dial_center_bl.y - 0.015, dial_center_bl.z),
		rotation=(math.radians(90.0), 0.0, 0.0),
	)
	brass_bezel = bpy.context.active_object
	brass_bezel.data.materials.append(mat_brass)
	housing_parts.append(brass_bezel)

	for r_i in range(8):
		ang = (2.0 * math.pi * float(r_i)) / 8.0
		rx = dial_center_bl.x + math.cos(ang) * 0.195
		rz = dial_center_bl.z + math.sin(ang) * 0.195
		bpy.ops.mesh.primitive_uv_sphere_add(
			segments=10,
			ring_count=6,
			radius=0.012,
			location=(rx, dial_center_bl.y - 0.035, rz),
		)
		rivet = bpy.context.active_object
		rivet.data.materials.append(mat_brass)
		housing_parts.append(rivet)

	# Backlit AmberGlass circular dial face inside the boolean cavity
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=28,
		radius=0.172,
		depth=0.012,
		location=(dial_center_bl.x, dial_center_bl.y + 0.012, dial_center_bl.z),
		rotation=(math.radians(90.0), 0.0, 0.0),
	)
	dial_face = bpy.context.active_object
	dial_face.data.materials.append(mat_amber_dial)
	housing_parts.append(dial_face)

	# Raised tick marks on the dial face (-120 deg green safe zone to +120 deg red danger zone)
	for tick_idx in range(9):
		frac = float(tick_idx) / 8.0
		# In dial plane: +Z is 0 deg (12 o'clock), -X is green (-120 deg), +X is red (+120 deg)
		deg = -120.0 + frac * 240.0
		rad = math.radians(deg)
		tx = dial_center_bl.x + math.sin(rad) * 0.135
		tz = dial_center_bl.z + math.cos(rad) * 0.135
		bpy.ops.mesh.primitive_cube_add(
			size=1.0,
			location=(tx, dial_center_bl.y + 0.002, tz),
			rotation=(0.0, rad, 0.0),
		)
		tick = bpy.context.active_object
		tick.scale = (0.014, 0.012, 0.036 if (tick_idx % 2 == 0) else 0.024)
		bpy.ops.object.transform_apply(scale=True)
		if frac >= 0.72:
			tick.data.materials.append(mat_red_zone)
		elif frac <= 0.35:
			tick.data.materials.append(mat_green_zone)
		else:
			tick.data.materials.append(mat_dark_metal)
		housing_parts.append(tick)

	# Join all static housing parts into `WinchHousing`
	bpy.ops.object.select_all(action="DESELECT")
	for part in housing_parts:
		part.select_set(True)
	bpy.context.view_layer.objects.active = housing_parts[0]
	bpy.ops.object.join()
	winch_housing = bpy.context.active_object
	winch_housing.name = "WinchHousing"
	bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")

	# 3. Separate `GaugeNeedle` child MeshInstance3D pivoted at `dial_center_bl`
	needle_parts: List[bpy.types.Object] = []
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=14,
		radius=0.024,
		depth=0.026,
		location=(dial_center_bl.x, dial_center_bl.y - 0.006, dial_center_bl.z),
		rotation=(math.radians(90.0), 0.0, 0.0),
	)
	needle_hub = bpy.context.active_object
	needle_hub.data.materials.append(mat_brass)
	needle_parts.append(needle_hub)

	# Tapered pointer blade pointing straight up (+Z in Blender = +Y in Godot) from dial center
	bpy.ops.mesh.primitive_cone_add(
		vertices=8,
		radius1=0.016,
		radius2=0.003,
		depth=0.145,
		location=(dial_center_bl.x, dial_center_bl.y - 0.008, dial_center_bl.z + 0.062),
	)
	needle_blade = bpy.context.active_object
	needle_blade.scale = (1.0, 0.35, 1.0)
	bpy.ops.object.transform_apply(scale=True)
	needle_blade.data.materials.append(mat_red_zone)
	needle_parts.append(needle_blade)

	bpy.ops.object.select_all(action="DESELECT")
	for np in needle_parts:
		np.select_set(True)
	bpy.context.view_layer.objects.active = needle_parts[0]
	bpy.ops.object.join()
	gauge_needle = bpy.context.active_object
	gauge_needle.name = "GaugeNeedle"
	bpy.context.scene.cursor.location = (dial_center_bl.x, dial_center_bl.y - 0.006, dial_center_bl.z)
	bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
	bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)

	# 4. Separate `WinchSpool` drum wound with grooved 3D CURVE steel cable coils
	spool_center_bl = Vector((0.0, 0.02, 0.38))
	spool_parts: List[bpy.types.Object] = []

	# Core drum barrel along X
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=20,
		radius=0.125,
		depth=0.42,
		location=spool_center_bl,
		rotation=(0.0, math.radians(90.0), 0.0),
	)
	drum_core = bpy.context.active_object
	drum_core.data.materials.append(mat_dark_metal)
	spool_parts.append(drum_core)

	# Left & Right drum flanges with spokehole bolts
	for fx in (-0.20, 0.20):
		bpy.ops.mesh.primitive_cylinder_add(
			vertices=24,
			radius=0.22,
			depth=0.026,
			location=(fx, spool_center_bl.y, spool_center_bl.z),
			rotation=(0.0, math.radians(90.0), 0.0),
		)
		flange = bpy.context.active_object
		add_bevel_modifier(flange, width=0.004, segments=2)
		apply_all_modifiers(flange)
		flange.data.materials.append(mat_rust_iron)
		spool_parts.append(flange)

	# Helical 3D CURVE steel cable coils wound tightly across the drum
	curve_data = bpy.data.curves.new("SpoolCableCurve", type="CURVE")
	curve_data.dimensions = "3D"
	curve_data.bevel_depth = 0.012
	curve_data.bevel_resolution = 3
	spline = curve_data.splines.new("POLY")
	turns: int = 14
	pts_per_turn: int = 16
	total_pts: int = turns * pts_per_turn
	spline.points.add(total_pts - 1)
	for i in range(total_pts):
		u = float(i) / float(total_pts - 1)
		ang = u * float(turns) * 2.0 * math.pi
		cx = -0.175 + u * 0.35
		r_coil = 0.138 + 0.006 * math.sin(u * math.pi * 3.0)
		cy = spool_center_bl.y + math.cos(ang) * r_coil
		cz = spool_center_bl.z + math.sin(ang) * r_coil
		spline.points[i].co = (cx, cy, cz, 1.0)

	cable_obj = bpy.data.objects.new("SpoolCable", curve_data)
	bpy.context.collection.objects.link(cable_obj)
	bpy.ops.object.select_all(action="DESELECT")
	cable_obj.select_set(True)
	bpy.context.view_layer.objects.active = cable_obj
	bpy.ops.object.convert(target="MESH")
	cable_obj.data.materials.append(mat_steel_cable)
	spool_parts.append(cable_obj)

	bpy.ops.object.select_all(action="DESELECT")
	for sp in spool_parts:
		sp.select_set(True)
	bpy.context.view_layer.objects.active = spool_parts[0]
	bpy.ops.object.join()
	winch_spool = bpy.context.active_object
	winch_spool.name = "WinchSpool"
	bpy.context.scene.cursor.location = spool_center_bl
	bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
	bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)

	# 5. Separate `TrawlWeight` heavy steel trawl-door / hook sinker weight
	weight_parts: List[bpy.types.Object] = []
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=12,
		radius=0.075,
		depth=0.22,
		location=(0.0, 0.28, 0.22),
	)
	sinker_body = bpy.context.active_object
	add_bevel_modifier(sinker_body, width=0.015, segments=2)
	apply_all_modifiers(sinker_body)
	sinker_body.data.materials.append(mat_dark_metal)
	weight_parts.append(sinker_body)

	bpy.ops.mesh.primitive_torus_add(
		major_segments=14,
		minor_segments=6,
		major_radius=0.042,
		minor_radius=0.012,
		location=(0.0, 0.28, 0.35),
		rotation=(math.radians(90.0), 0.0, 0.0),
	)
	shackle = bpy.context.active_object
	shackle.data.materials.append(mat_rust_iron)
	weight_parts.append(shackle)

	bpy.ops.object.select_all(action="DESELECT")
	for wp in weight_parts:
		wp.select_set(True)
	bpy.context.view_layer.objects.active = weight_parts[0]
	bpy.ops.object.join()
	trawl_weight = bpy.context.active_object
	trawl_weight.name = "TrawlWeight"
	bpy.context.scene.cursor.location = (0.0, 0.28, 0.35)
	bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
	bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)

	os.makedirs(os.path.dirname(out_glb_path), exist_ok=True)
	bpy.ops.export_scene.gltf(
		filepath=out_glb_path,
		export_format="GLB",
		export_apply=True,
		export_yup=True,
	)
	print(f"Exported {out_glb_path}")


def build_catch_fish_cod(out_glb_path: str) -> None:
	clear_scene()

	mat_cod_back = create_pbr_material("CodBackSlate", (0.11, 0.16, 0.18, 1.0), metallic=0.12, roughness=0.15)
	mat_cod_belly = create_pbr_material("CodBellySilver", (0.52, 0.56, 0.54, 1.0), metallic=0.25, roughness=0.15)
	mat_cod_fins = create_pbr_material("CodFins", (0.16, 0.20, 0.19, 1.0), metallic=0.08, roughness=0.22)
	mat_cod_eye = create_pbr_material("CodEye", (0.02, 0.02, 0.03, 1.0), metallic=0.4, roughness=0.05)

	# Build a ~1.1m Atlantic Cod hanging vertically with mouth at (0, 0, 0) and tail at z = -1.12m
	# (In Godot +Y up, z in Blender maps to +Y in Godot, so hanging along -Z in Blender = hanging along -Y in Godot)
	bm = bmesh.new()
	stations: List[Tuple[float, float, float, float]] = [
		# (z_pos, half_width_x, half_depth_y_dorsal, half_depth_y_ventral)
		(0.00, 0.035, 0.038, 0.032),   # Mouth / snout tip at hook
		(-0.08, 0.082, 0.088, 0.075),  # Head / eye socket
		(-0.20, 0.118, 0.135, 0.125),  # Gill operculum
		(-0.36, 0.135, 0.162, 0.155),  # Thickest mid-body
		(-0.54, 0.115, 0.142, 0.132),  # Mid-posterior torso
		(-0.72, 0.078, 0.102, 0.088),  # Taper toward tail
		(-0.88, 0.042, 0.058, 0.052),  # Caudal peduncle
		(-0.96, 0.022, 0.045, 0.045),  # Tail fin root
		(-1.12, 0.008, 0.165, 0.165),  # Broad forked caudal tail fin
	]

	ring_verts: int = 16
	rings: List[List[bmesh.types.BMVert]] = []
	for z_pos, rx, ry_pos, ry_neg in stations:
		ring: List[bmesh.types.BMVert] = []
		for i in range(ring_verts):
			theta = (2.0 * math.pi * float(i)) / float(ring_verts)
			ca = math.cos(theta)
			sa = math.sin(theta)
			ry = ry_pos if sa >= 0.0 else ry_neg
			# Slight organic scale ripple displacement
			ripple = 1.0 + 0.035 * math.sin(z_pos * 28.0 + theta * 4.0)
			vx = ca * rx * ripple
			vy = sa * ry * ripple
			# Fork indentation in the middle of the tail fluke
			vz = z_pos
			if z_pos <= -1.10 and abs(sa) < 0.35:
				vz += 0.045 * (1.0 - abs(sa) / 0.35)
			ring.append(bm.verts.new((vx, vy, vz)))
		rings.append(ring)

	bm.verts.ensure_lookup_table()

	for r_idx in range(len(rings) - 1):
		r0 = rings[r_idx]
		r1 = rings[r_idx + 1]
		for i in range(ring_verts):
			ni = (i + 1) % ring_verts
			f = bm.faces.new((r0[i], r0[ni], r1[ni], r1[i]))
			# Assign material index: 0 = CodBackSlate (dorsal +Y), 1 = CodBellySilver (ventral -Y), 2 = CodFins (tail)
			theta_mid = (2.0 * math.pi * (float(i) + 0.5)) / float(ring_verts)
			if r_idx >= len(rings) - 2:
				f.material_index = 2
			elif math.sin(theta_mid) < -0.15:
				f.material_index = 1
			else:
				f.material_index = 0

	# Cap snout & tail tip
	bm.faces.new(rings[0]).material_index = 0
	bm.faces.new(list(reversed(rings[-1]))).material_index = 2
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

	fish_mesh = bpy.data.meshes.new("AtlanticCodMesh")
	bm.to_mesh(fish_mesh)
	bm.free()

	fish_obj = bpy.data.objects.new("AtlanticCod", fish_mesh)
	bpy.context.collection.objects.link(fish_obj)
	fish_obj.data.materials.append(mat_cod_back)
	fish_obj.data.materials.append(mat_cod_belly)
	fish_obj.data.materials.append(mat_cod_fins)
	fish_obj.data.materials.append(mat_cod_eye)

	# Subdivision Surface + Procedural Clouds Displacement for organic wet fish skin
	subsurf = fish_obj.modifiers.new(name="Subsurf", type="SUBSURF")
	subsurf.levels = 2
	subsurf.render_levels = 2

	tex = bpy.data.textures.new("CodScaleNoise", type="CLOUDS")
	tex.noise_scale = 0.08
	disp = fish_obj.modifiers.new(name="ScaleDisplace", type="DISPLACE")
	disp.texture = tex
	disp.strength = 0.008
	apply_all_modifiers(fish_obj)

	fish_parts: List[bpy.types.Object] = [fish_obj]

	# Dorsal fins (2 characteristic cod dorsal fins along +Y back) & Pectoral fins
	dorsal_configs = [
		((0.0, 0.165, -0.36), (0.012, 0.075, 0.12)),
		((0.0, 0.135, -0.64), (0.010, 0.065, 0.11)),
		((0.0, -0.125, -0.66), (0.010, 0.055, 0.09)),  # Ventral anal fin
	]
	for loc, scl in dorsal_configs:
		bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
		fin = bpy.context.active_object
		fin.scale = scl
		bpy.ops.object.transform_apply(scale=True)
		add_bevel_modifier(fin, width=0.004, segments=2)
		apply_all_modifiers(fin)
		fin.data.materials.append(mat_cod_fins)
		fish_parts.append(fin)

	# Left & Right Pectoral fins
	for sx in (-1.0, 1.0):
		bpy.ops.mesh.primitive_cube_add(
			size=1.0,
			location=(sx * 0.135, -0.03, -0.24),
			rotation=(math.radians(18.0), sx * math.radians(38.0), 0.0),
		)
		pfin = bpy.context.active_object
		pfin.scale = (0.085, 0.012, 0.065)
		bpy.ops.object.transform_apply(scale=True)
		add_bevel_modifier(pfin, width=0.003, segments=2)
		apply_all_modifiers(pfin)
		pfin.data.materials.append(mat_cod_fins)
		fish_parts.append(pfin)

		# Bulging glassy fish eyes
		bpy.ops.mesh.primitive_uv_sphere_add(
			segments=12,
			ring_count=8,
			radius=0.018,
			location=(sx * 0.072, 0.038, -0.095),
		)
		eye = bpy.context.active_object
		eye.data.materials.append(mat_cod_eye)
		fish_parts.append(eye)

	bpy.ops.object.select_all(action="DESELECT")
	for fp in fish_parts:
		fp.select_set(True)
	bpy.context.view_layer.objects.active = fish_obj
	bpy.ops.object.join()
	bpy.ops.object.shade_smooth()

	os.makedirs(os.path.dirname(out_glb_path), exist_ok=True)
	bpy.ops.export_scene.gltf(
		filepath=out_glb_path,
		export_format="GLB",
		export_apply=True,
		export_yup=True,
	)
	print(f"Exported {out_glb_path}")


def main() -> None:
	project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	models_dir = os.path.join(project_root, "assets", "models")
	build_winch_tension_rig(os.path.join(models_dir, "winch_tension_rig.glb"))
	build_catch_fish_cod(os.path.join(models_dir, "catch_fish_cod.glb"))


if __name__ == "__main__":
	main()
