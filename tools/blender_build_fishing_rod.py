#!/usr/bin/env python3
"""
Headless Blender 5.4.0 generator for Stylized Dark Lovecraftian First-Person Rod & Reel Fishing assets:
  1. res://assets/models/sea_fishing_rod.glb
     - Hierarchical 4-segment articulated offshore sea rod & reel for first-person viewmodel:
       * RodBaseGrip (root at origin, octagonal chiseled cork grips, iron reel seat, riveted brass reel housing)
         ├── ReelCrankHandle (pivoted at reel axle so rotating around X spins the crank)
         └── RodMidLower (pivoted at z = -0.32m in Godot / y = +0.32m in Blender)
               └── RodMidUpper (pivoted at local -0.45m in Godot / y = +0.77m in Blender)
                     └── RodTip (pivoted at local -0.42m in Godot / y = +1.19m in Blender, with RodTipGlow)
                           └── RodTipEyelet (marker at the terminal eyelet y = +1.57m in Blender)
  2. res://assets/models/sea_bobber_lure.glb
     - Chiseled nautical sea-float & brass jig lure with warm AmberGlass night-stick top (Emission Strength = 6.0)
"""

import math
import os
from typing import Dict, List, Tuple
import bpy
import bmesh
from mathutils import Vector


def clear_scene() -> None:
	bpy.ops.wm.read_factory_settings(use_empty=True)


def clamp01(v: float) -> float:
	return max(0.0, min(1.0, v))


def lerp(a: float, b: float, t: float) -> float:
	return a + (b - a) * t


def lerp_color(
	c0: Tuple[float, float, float, float],
	c1: Tuple[float, float, float, float],
	t: float,
) -> Tuple[float, float, float, float]:
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


def create_pbr_material(
	name: str,
	base_color: Tuple[float, float, float, float],
	metallic: float = 0.0,
	roughness: float = 0.5,
	emission_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
	emission_strength: float = 0.0,
	use_vertex_color: bool = True,
) -> bpy.types.Material:
	mat: bpy.types.Material = bpy.data.materials.new(name=name)
	mat.use_nodes = True
	nt = mat.node_tree
	nodes = nt.nodes
	links = nt.links
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

	if use_vertex_color:
		vcol_node = nodes.new(type="ShaderNodeVertexColor")
		vcol_node.layer_name = "Col"
		links.new(vcol_node.outputs["Color"], bsdf.inputs["Base Color"])

	return mat


def add_bevel_modifier(obj: bpy.types.Object, width: float = 0.0025, segments: int = 1) -> None:
	bevel = obj.modifiers.new(name="Bevel", type="BEVEL")
	bevel.width = width
	bevel.segments = segments
	bevel.limit_method = "ANGLE"
	bevel.angle_limit = math.radians(26.0)


def apply_all_modifiers(obj: bpy.types.Object) -> None:
	bpy.context.view_layer.objects.active = obj
	for mod in list(obj.modifiers):
		bpy.ops.object.modifier_apply(modifier=mod.name)


def apply_chiseled_facet_normals_and_cavity_ink(
	obj: bpy.types.Object,
	slot_palettes: Dict[int, Tuple[float, float, float, float]],
	crevice_y_bands: List[float] = None,
) -> None:
	"""
	Marks edges with dihedral angle > 22 deg as sharp for chiseled planar facets, and bakes
	the `Col` vertex color attribute with deep charcoal cavity ink in concave crevices/joints
	and crisp stylized edge highlights on bevel ridges.
	"""
	mesh: bpy.types.Mesh = obj.data
	bm = bmesh.new()
	bm.from_mesh(mesh)
	for f in bm.faces:
		f.smooth = True
	for e in bm.edges:
		if len(e.link_faces) == 2:
			if e.calc_face_angle(0.0) > math.radians(22.0):
				e.smooth = False
	bm.to_mesh(mesh)
	bm.free()

	while len(mesh.color_attributes) > 0:
		mesh.color_attributes.remove(mesh.color_attributes[0])
	col_attr = mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")

	verts = mesh.vertices
	loops = mesh.loops
	num_verts = len(verts)
	num_loops = len(loops)

	vert_neighbors: List[List[int]] = [[] for _ in range(num_verts)]
	for edge in mesh.edges:
		v0, v1 = edge.vertices[0], edge.vertices[1]
		vert_neighbors[v0].append(v1)
		vert_neighbors[v1].append(v0)

	vert_concavity: List[float] = [0.0] * num_verts
	for v_idx in range(num_verts):
		nbrs = vert_neighbors[v_idx]
		if not nbrs:
			continue
		v = verts[v_idx]
		avg_co = Vector((0.0, 0.0, 0.0))
		avg_len = 0.0
		for n_i in nbrs:
			nco = verts[n_i].co
			avg_co += nco
			avg_len += (nco - v.co).length
		inv_n = 1.0 / float(len(nbrs))
		avg_co *= inv_n
		avg_len = max(0.0008, avg_len * inv_n)
		vert_concavity[v_idx] = (avg_co - v.co).dot(v.normal) / avg_len

	ink_black: Tuple[float, float, float, float] = (0.015, 0.018, 0.025, 1.0)
	flat_colors: List[float] = [0.0] * (num_loops * 4)

	for poly in mesh.polygons:
		m_idx = poly.material_index
		base_col = slot_palettes.get(m_idx, (0.5, 0.5, 0.5, 1.0))
		for loop_idx in poly.loop_indices:
			v_idx = loops[loop_idx].vertex_index
			v = verts[v_idx]
			concav = vert_concavity[v_idx]

			# Seam/ferrule ink darkening near joint rings
			joint_ink = 0.0
			if crevice_y_bands:
				for cy in crevice_y_bands:
					dist_y = abs(v.co.y - cy)
					if dist_y < 0.016:
						joint_ink = max(joint_ink, 0.68 * (1.0 - dist_y / 0.016))

			# Soot/oil gradient toward underside (-Z) and deep reel crevices
			underside_shade = clamp01(smoothstep(0.02, -0.04, v.co.z)) * 0.32
			cavity_weight = clamp01(smoothstep(0.01, 0.16, concav) * 0.85 + joint_ink + underside_shade)

			rgba = lerp_color(base_col, ink_black, cavity_weight * 0.88)

			# Crisp stylized bevel highlight on sharp convex ridges
			ridge_w = clamp01(smoothstep(-0.015, -0.18, concav))
			if ridge_w > 0.0:
				highlight = (
					min(1.0, base_col[0] * 1.48 + 0.14),
					min(1.0, base_col[1] * 1.48 + 0.12),
					min(1.0, base_col[2] * 1.45 + 0.10),
					1.0,
				)
				rgba = lerp_color(rgba, highlight, ridge_w * 0.62)

			off = loop_idx * 4
			flat_colors[off] = rgba[0]
			flat_colors[off + 1] = rgba[1]
			flat_colors[off + 2] = rgba[2]
			flat_colors[off + 3] = rgba[3]

	col_attr.data.foreach_set("color", flat_colors)


def build_tapered_rod_section(
	name: str,
	y_start: float,
	y_end: float,
	r_start: float,
	r_end: float,
	mat_blank: bpy.types.Material,
	mat_brass: bpy.types.Material,
	guide_positions: List[Tuple[float, float]],
	slot_palettes: Dict[int, Tuple[float, float, float, float]],
	mat_tip_glow: bpy.types.Material = None,
) -> bpy.types.Object:
	"""
	Builds an octagonal chiseled tapered rod section along +Y in Blender (-Z forward in Godot glTF)
	with heavy beveled brass line guides and ferrule collars.
	"""
	parts: List[bpy.types.Object] = []

	bm = bmesh.new()
	rings_count = 10
	seg_verts = 8  # Octagonal chiseled planar rod cross-section
	rings = []
	for i in range(rings_count + 1):
		t = float(i) / float(rings_count)
		y = y_start + (y_end - y_start) * t
		r = r_start + (r_end - r_start) * t
		ring = []
		for v in range(seg_verts):
			ang = (2.0 * math.pi * float(v)) / float(seg_verts) + (math.pi / 8.0)
			ring.append(bm.verts.new((math.cos(ang) * r, y, math.sin(ang) * r)))
		rings.append(ring)

	bm.verts.ensure_lookup_table()
	for i in range(rings_count):
		r0 = rings[i]
		r1 = rings[i + 1]
		for v in range(seg_verts):
			nv = (v + 1) % seg_verts
			f = bm.faces.new((r0[v], r0[nv], r1[nv], r1[v]))
			if mat_tip_glow is not None and i >= rings_count - 2:
				f.material_index = 2
			else:
				f.material_index = 0

	bm.faces.new(rings[0]).material_index = 0
	bm.faces.new(list(reversed(rings[-1]))).material_index = 2 if mat_tip_glow is not None else 0
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

	mesh = bpy.data.meshes.new(name + "_BlankMesh")
	bm.to_mesh(mesh)
	bm.free()

	blank_obj = bpy.data.objects.new(name, mesh)
	bpy.context.collection.objects.link(blank_obj)
	blank_obj.data.materials.append(mat_blank)  # 0
	blank_obj.data.materials.append(mat_brass)  # 1
	if mat_tip_glow is not None:
		blank_obj.data.materials.append(mat_tip_glow)  # 2
	parts.append(blank_obj)

	crevice_ys: List[float] = [y_start, y_end]
	# Add heavy chiseled brass line guides & ferrule bands along the section
	for gy, gr in guide_positions:
		crevice_ys.append(gy)
		t_pos = (gy - y_start) / max(0.001, (y_end - y_start))
		blank_r = r_start + (r_end - r_start) * t_pos

		# Ferrule wrap collar around rod blank at guide base
		bpy.ops.mesh.primitive_cylinder_add(
			vertices=8,
			radius=blank_r * 1.26,
			depth=0.022,
			location=(0.0, gy, 0.0),
			rotation=(math.radians(90.0), 0.0, 0.0),
		)
		wrap_collar = bpy.context.active_object
		add_bevel_modifier(wrap_collar, width=0.0015, segments=1)
		apply_all_modifiers(wrap_collar)
		wrap_collar.data.materials.append(mat_brass)
		parts.append(wrap_collar)

		# Heavy angular stanchion strut
		bpy.ops.mesh.primitive_cube_add(
			size=1.0,
			location=(0.0, gy, blank_r + gr * 0.62),
		)
		strut = bpy.context.active_object
		strut.scale = (0.0055, 0.016, gr * 1.05)
		bpy.ops.object.transform_apply(scale=True)
		add_bevel_modifier(strut, width=0.0012, segments=1)
		apply_all_modifiers(strut)
		strut.data.materials.append(mat_brass)
		parts.append(strut)

		# Octagonal chiseled eyelet ring
		bpy.ops.mesh.primitive_torus_add(
			major_segments=10,
			minor_segments=6,
			major_radius=gr * 1.15,
			minor_radius=max(0.0028, gr * 0.30),
			location=(0.0, gy, blank_r + gr * 1.48),
			rotation=(math.radians(90.0), 0.0, 0.0),
		)
		ring_obj = bpy.context.active_object
		ring_obj.data.materials.append(mat_tip_glow if (mat_tip_glow is not None and gy >= y_end - 0.02) else mat_brass)
		parts.append(ring_obj)

	bpy.ops.object.select_all(action="DESELECT")
	for p in parts:
		p.select_set(True)
	bpy.context.view_layer.objects.active = blank_obj
	bpy.ops.object.join()

	apply_chiseled_facet_normals_and_cavity_ink(blank_obj, slot_palettes, crevice_ys)

	# Set origin at the proximal hinge point (0, y_start, 0)
	bpy.context.scene.cursor.location = (0.0, y_start, 0.0)
	bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
	bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
	return blank_obj


def build_sea_fishing_rod(out_glb_path: str) -> None:
	clear_scene()

	c_cork = (0.42, 0.27, 0.16, 1.0)
	c_carbon = (0.12, 0.15, 0.18, 1.0)
	c_brass = (0.74, 0.55, 0.23, 1.0)
	c_iron = (0.16, 0.19, 0.22, 1.0)
	c_glow = (0.38, 0.98, 0.62, 1.0)

	mat_cork = create_pbr_material("WeatheredCork", c_cork, metallic=0.04, roughness=0.82)
	mat_carbon = create_pbr_material("DarkCarbonRod", c_carbon, metallic=0.45, roughness=0.28)
	mat_brass = create_pbr_material("TarnishedBrass", c_brass, metallic=0.82, roughness=0.32)
	mat_iron = create_pbr_material("DarkReelIron", c_iron, metallic=0.72, roughness=0.38)
	mat_tip_glow = create_pbr_material(
		"RodTipGlow",
		c_glow,
		metallic=0.10,
		roughness=0.15,
		emission_color=(0.32, 0.98, 0.56, 1.0),
		emission_strength=4.2,
	)

	# -------------------------------------------------------------------------
	# 1. RodBaseGrip (y = -0.22m rear butt to y = +0.32m foregrip ferrule)
	# -------------------------------------------------------------------------
	base_parts: List[bpy.types.Object] = []

	# Chiseled 10-faceted cork rear butt & foregrip (heavier graphic silhouette)
	for cy, clen, crad in ((-0.12, 0.21, 0.023), (0.20, 0.22, 0.021)):
		bpy.ops.mesh.primitive_cylinder_add(
			vertices=10,
			radius=crad,
			depth=clen,
			location=(0.0, cy, 0.0),
			rotation=(math.radians(90.0), 0.0, 0.0),
		)
		cork_cyl = bpy.context.active_object
		add_bevel_modifier(cork_cyl, width=0.0035, segments=1)
		apply_all_modifiers(cork_cyl)
		cork_cyl.data.materials.append(mat_cork)
		base_parts.append(cork_cyl)

	# Heavy octagonal reel seat & knurled brass locking collars (y = -0.02 to +0.09)
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=8,
		radius=0.024,
		depth=0.14,
		location=(0.0, 0.035, 0.0),
		rotation=(math.radians(90.0), 0.0, 0.0),
	)
	seat_cyl = bpy.context.active_object
	add_bevel_modifier(seat_cyl, width=0.0028, segments=1)
	apply_all_modifiers(seat_cyl)
	seat_cyl.data.materials.append(mat_carbon)
	base_parts.append(seat_cyl)

	for ring_y in (-0.22, -0.02, 0.09, 0.31):
		bpy.ops.mesh.primitive_cylinder_add(
			vertices=10,
			radius=0.027,
			depth=0.018,
			location=(0.0, ring_y, 0.0),
			rotation=(math.radians(90.0), 0.0, 0.0),
		)
		collar = bpy.context.active_object
		add_bevel_modifier(collar, width=0.0022, segments=1)
		apply_all_modifiers(collar)
		collar.data.materials.append(mat_brass)
		base_parts.append(collar)

	# Heavy Offshore Winch-Reel Foot & Chiseled 12-Sided Drum Housing (mounted at y = 0.04, z = -0.062)
	reel_center = Vector((0.0, 0.04, -0.064))
	bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.04, -0.030))
	reel_foot = bpy.context.active_object
	reel_foot.scale = (0.022, 0.075, 0.052)
	bpy.ops.object.transform_apply(scale=True)
	add_bevel_modifier(reel_foot, width=0.003, segments=1)
	apply_all_modifiers(reel_foot)
	reel_foot.data.materials.append(mat_brass)
	base_parts.append(reel_foot)

	# Faceted iron reel spool drum (horizontal X axis)
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=12,
		radius=0.044,
		depth=0.076,
		location=reel_center,
		rotation=(0.0, math.radians(90.0), 0.0),
	)
	reel_drum = bpy.context.active_object
	add_bevel_modifier(reel_drum, width=0.0035, segments=1)
	apply_all_modifiers(reel_drum)
	reel_drum.data.materials.append(mat_iron)
	base_parts.append(reel_drum)

	# Chunky 10-sided brass side plates + 6 protruding bolts/rivets per side
	for sx in (-0.040, 0.040):
		bpy.ops.mesh.primitive_cylinder_add(
			vertices=10,
			radius=0.050,
			depth=0.012,
			location=(sx, reel_center.y, reel_center.z),
			rotation=(0.0, math.radians(90.0), 0.0),
		)
		plate = bpy.context.active_object
		add_bevel_modifier(plate, width=0.0024, segments=1)
		apply_all_modifiers(plate)
		plate.data.materials.append(mat_brass)
		base_parts.append(plate)

		# Structural crossbar pillar struts bridging the two brass side plates
		for bar_ang in (0.4, 2.2, 4.8):
			by = reel_center.y + math.cos(bar_ang) * 0.046
			bz = reel_center.z + math.sin(bar_ang) * 0.046
			if sx > 0.0:
				bpy.ops.mesh.primitive_cylinder_add(
					vertices=6,
					radius=0.0038,
					depth=0.082,
					location=(0.0, by, bz),
					rotation=(0.0, math.radians(90.0), 0.0),
				)
				pillar = bpy.context.active_object
				pillar.data.materials.append(mat_iron)
				base_parts.append(pillar)

	bpy.ops.object.select_all(action="DESELECT")
	for bp in base_parts:
		bp.select_set(True)
	bpy.context.view_layer.objects.active = base_parts[0]
	bpy.ops.object.join()
	rod_base_grip = bpy.context.active_object
	rod_base_grip.name = "RodBaseGrip"
	bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

	base_palettes: Dict[int, Tuple[float, float, float, float]] = {}
	for idx, m in enumerate(rod_base_grip.data.materials):
		if m == mat_cork:
			base_palettes[idx] = c_cork
		elif m == mat_carbon:
			base_palettes[idx] = c_carbon
		elif m == mat_brass:
			base_palettes[idx] = c_brass
		else:
			base_palettes[idx] = c_iron

	apply_chiseled_facet_normals_and_cavity_ink(
		rod_base_grip,
		base_palettes,
		crevice_y_bands=[-0.22, -0.02, 0.04, 0.09, 0.31],
	)

	bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
	bpy.ops.object.origin_set(type="ORIGIN_CURSOR")

	# -------------------------------------------------------------------------
	# 2. ReelCrankHandle (child of RodBaseGrip, pivoted at right side of reel)
	# -------------------------------------------------------------------------
	crank_pivot = Vector((0.050, reel_center.y, reel_center.z))
	crank_parts: List[bpy.types.Object] = []

	# Heavy beveled crank arm
	bpy.ops.mesh.primitive_cube_add(
		size=1.0,
		location=(crank_pivot.x + 0.006, crank_pivot.y + 0.026, crank_pivot.z),
	)
	arm = bpy.context.active_object
	arm.scale = (0.009, 0.068, 0.016)
	bpy.ops.object.transform_apply(scale=True)
	add_bevel_modifier(arm, width=0.002, segments=1)
	apply_all_modifiers(arm)
	arm.data.materials.append(mat_brass)
	crank_parts.append(arm)

	# Octagonal chiseled power knob at the end of the crank arm
	bpy.ops.mesh.primitive_cylinder_add(
		vertices=8,
		radius=0.015,
		depth=0.038,
		location=(crank_pivot.x + 0.026, crank_pivot.y + 0.052, crank_pivot.z),
		rotation=(0.0, math.radians(90.0), 0.0),
	)
	knob = bpy.context.active_object
	add_bevel_modifier(knob, width=0.0025, segments=1)
	apply_all_modifiers(knob)
	knob.data.materials.append(mat_cork)
	crank_parts.append(knob)

	bpy.ops.object.select_all(action="DESELECT")
	for cp in crank_parts:
		cp.select_set(True)
	bpy.context.view_layer.objects.active = crank_parts[0]
	bpy.ops.object.join()
	reel_crank = bpy.context.active_object
	reel_crank.name = "ReelCrankHandle"
	apply_chiseled_facet_normals_and_cavity_ink(
		reel_crank,
		{0: c_brass, 1: c_cork},
	)
	bpy.context.scene.cursor.location = crank_pivot
	bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
	bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
	reel_crank.parent = rod_base_grip
	reel_crank.matrix_parent_inverse = rod_base_grip.matrix_world.inverted()

	# -------------------------------------------------------------------------
	# 3. Articulated Rod Blank Segments: RodMidLower -> RodMidUpper -> RodTip
	# -------------------------------------------------------------------------
	sec_palettes = {0: c_carbon, 1: c_brass, 2: c_glow}
	rod_mid_lower = build_tapered_rod_section(
		"RodMidLower",
		0.32,
		0.77,
		0.0155,
		0.0110,
		mat_carbon,
		mat_brass,
		[(0.48, 0.018), (0.72, 0.015)],
		sec_palettes,
	)
	rod_mid_lower.parent = rod_base_grip
	rod_mid_lower.matrix_parent_inverse = rod_base_grip.matrix_world.inverted()

	rod_mid_upper = build_tapered_rod_section(
		"RodMidUpper",
		0.77,
		1.19,
		0.0110,
		0.0072,
		mat_carbon,
		mat_brass,
		[(0.96, 0.0125), (1.15, 0.0105)],
		sec_palettes,
	)
	rod_mid_upper.parent = rod_mid_lower
	rod_mid_upper.matrix_parent_inverse = rod_mid_lower.matrix_world.inverted()

	rod_tip = build_tapered_rod_section(
		"RodTip",
		1.19,
		1.57,
		0.0072,
		0.0040,
		mat_carbon,
		mat_brass,
		[(1.36, 0.0085), (1.56, 0.0080)],
		sec_palettes,
		mat_tip_glow=mat_tip_glow,
	)
	rod_tip.parent = rod_mid_upper
	rod_tip.matrix_parent_inverse = rod_mid_upper.matrix_world.inverted()

	# Add a child Node3D marker right at the tip eyelet (0.0, 1.565, 0.012)
	eyelet_empty = bpy.data.objects.new("RodTipEyelet", None)
	eyelet_empty.empty_display_size = 0.02
	eyelet_empty.location = (0.0, 1.565, 0.012)
	bpy.context.collection.objects.link(eyelet_empty)
	eyelet_empty.parent = rod_tip
	eyelet_empty.matrix_parent_inverse = rod_tip.matrix_world.inverted()

	os.makedirs(os.path.dirname(out_glb_path), exist_ok=True)
	bpy.ops.export_scene.gltf(
		filepath=out_glb_path,
		export_format="GLB",
		export_apply=True,
		export_yup=True,
		export_attributes=True,
		export_all_vertex_colors=True,
	)
	print(f"Exported {out_glb_path}")


def build_sea_bobber_lure(out_glb_path: str) -> None:
	clear_scene()

	c_crimson = (0.72, 0.12, 0.09, 1.0)
	c_timber = (0.78, 0.72, 0.60, 1.0)
	c_brass = (0.72, 0.54, 0.22, 1.0)
	c_amber = (1.0, 0.84, 0.36, 1.0)

	mat_crimson = create_pbr_material("BobberCrimson", c_crimson, metallic=0.12, roughness=0.22)
	mat_timber = create_pbr_material("BobberCork", c_timber, metallic=0.05, roughness=0.40)
	mat_brass = create_pbr_material("LureBrass", c_brass, metallic=0.85, roughness=0.28)
	mat_amber_glow = create_pbr_material(
		"AmberGlass",
		c_amber,
		metallic=0.05,
		roughness=0.12,
		emission_color=(1.0, 0.78, 0.28, 1.0),
		emission_strength=6.0,
	)

	bm = bmesh.new()
	stations = [
		(-0.24, 0.009, 2),
		(-0.18, 0.032, 2),
		(-0.12, 0.020, 1),
		(-0.05, 0.082, 1),
		(0.02, 0.105, 0),
		(0.09, 0.074, 0),
		(0.14, 0.026, 2),
		(0.15, 0.030, 3),
		(0.34, 0.028, 3),
		(0.37, 0.009, 3),
	]
	ring_verts = 10  # Chiseled 10-sided nautical float
	rings = []
	for z_h, rad, _ in stations:
		ring = []
		for i in range(ring_verts):
			ang = (2.0 * math.pi * float(i)) / float(ring_verts)
			ring.append(bm.verts.new((math.cos(ang) * rad, math.sin(ang) * rad, z_h)))
		rings.append(ring)

	bm.verts.ensure_lookup_table()
	for r_idx in range(len(rings) - 1):
		r0 = rings[r_idx]
		r1 = rings[r_idx + 1]
		mat_slot = stations[r_idx + 1][2]
		for i in range(ring_verts):
			ni = (i + 1) % ring_verts
			f = bm.faces.new((r0[i], r0[ni], r1[ni], r1[i]))
			f.material_index = mat_slot

	bm.faces.new(rings[0]).material_index = 2
	bm.faces.new(list(reversed(rings[-1]))).material_index = 3
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

	mesh = bpy.data.meshes.new("SeaBobberLureMesh")
	bm.to_mesh(mesh)
	bm.free()

	bobber_obj = bpy.data.objects.new("SeaBobberLure", mesh)
	bpy.context.collection.objects.link(bobber_obj)
	bobber_obj.data.materials.append(mat_crimson)     # 0
	bobber_obj.data.materials.append(mat_timber)      # 1
	bobber_obj.data.materials.append(mat_brass)       # 2
	bobber_obj.data.materials.append(mat_amber_glow)  # 3

	add_bevel_modifier(bobber_obj, width=0.0025, segments=1)
	apply_all_modifiers(bobber_obj)
	apply_chiseled_facet_normals_and_cavity_ink(
		bobber_obj,
		{0: c_crimson, 1: c_timber, 2: c_brass, 3: c_amber},
	)

	os.makedirs(os.path.dirname(out_glb_path), exist_ok=True)
	bpy.ops.export_scene.gltf(
		filepath=out_glb_path,
		export_format="GLB",
		export_apply=True,
		export_yup=True,
		export_attributes=True,
		export_all_vertex_colors=True,
	)
	print(f"Exported {out_glb_path}")


def main() -> None:
	project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	models_dir = os.path.join(project_root, "assets", "models")
	os.makedirs(models_dir, exist_ok=True)
	build_sea_fishing_rod(os.path.join(models_dir, "sea_fishing_rod.glb"))
	build_sea_bobber_lure(os.path.join(models_dir, "sea_bobber_lure.glb"))


if __name__ == "__main__":
	main()
