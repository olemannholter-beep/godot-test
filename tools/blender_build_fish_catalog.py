#!/usr/bin/env python3
"""
Headless Blender 5.4.0 High-Resolution Anatomical Fish Catalog Generator (.glb):
  1.  res://assets/models/fish/fish_mackerel.glb
  2.  res://assets/models/fish/fish_pollock.glb
  3.  res://assets/models/fish/fish_cod.glb
  4.  res://assets/models/fish/fish_rockfish.glb
  5.  res://assets/models/fish/fish_hake.glb
  6.  res://assets/models/fish/fish_wolffish.glb
  7.  res://assets/models/fish/fish_monkfish.glb
  8.  res://assets/models/fish/fish_halibut.glb
  9.  res://assets/models/fish/fish_scabbardfish.glb
  10. res://assets/models/fish/fish_grenadier.glb
  11. res://assets/models/fish/fish_oarfish.glb
  12. res://assets/models/fish/fish_angler.glb

Features:
- 64 longitudinal spine stations x 36 radial cross-section vertices (12,000-25,000 triangles per fish)
- Dorsal muscle ridges, recessed orbital sockets with bony supraorbital brow ridges, pinched caudal peduncle with lateral keels, S-curve swimming/thrashing bend
- Physical Lateral Sensory Line groove and diamond-lattice overlapping scale displacement along vertex normals
- Articulated gaping jaws (upper maxillary lip + lower hinged mandible), recessed dark oral throat cavity, flared left/right Operculum (gill cover plates) with physical gill slits and crimson gill arches underneath
- Species-specific 3D teeth/fangs/canines/molars, dermal jawline flaps (Monkfish), and barbels/lures (Cod, Monkfish, Oarfish, Anglerfish)
- 3D pleated bony fin-ray webs (raised fin-ray spines alternating with thin scalloped webbing membranes) for Dorsal, Pectoral, Pelvic, Anal, and Caudal fins
- Two-layer anatomical eyes (inner recessed dark pupil + metallic iridescent iris ring, outer glossy bulging cornea lens dome)
- High-resolution procedural vertex colors (`Col` attribute) wired to wet mucus clearcoat Principled BSDF materials (`Roughness = 0.14`, `Coat Weight = 1.0`, `Coat Roughness = 0.03`)
"""

import math
import os
from typing import Dict, List, Optional, Tuple
import bpy
import bmesh
from mathutils import Euler, Matrix, Vector


# Part IDs encoded into face material indices for both PBR slot assignment and vertex color rules:
# Slot 0: BodySkin (wet clearcoat + vertex color Col)
# Slot 1: PleatedFins (translucent/ribbed fin clearcoat + vertex color Col)
# Slot 2: OralGillCavity (recessed throat & crimson gill arches + vertex color Col)
# Slot 3: TeethIvory (ivory/translucent fangs & tusks + vertex color Col)
# Slot 4: EyeIrisPupil (metallic iridescent iris & pupil + vertex color Col)
# Slot 5: EyeCorneaLens (ultra-glossy clearcoat cornea dome, Roughness=0.02, Coat=1.0)
# Slot 6: BiolumEscaLure (high-emission bioluminescent lure / crest, Emission Strength=12.0)


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
		freq *= 2.07
		amp *= 0.5
	return val


def create_vertex_color_wet_material(
	name: str,
	fallback_color: Tuple[float, float, float, float],
	metallic: float = 0.35,
	roughness: float = 0.14,
	coat_weight: float = 1.0,
	coat_roughness: float = 0.03,
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

	bsdf.inputs["Base Color"].default_value = fallback_color
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
		vcol_node = nodes.new(type="ShaderNodeVertexColor")
		vcol_node.layer_name = "Col"
		links.new(vcol_node.outputs["Color"], bsdf.inputs["Base Color"])

	return mat


def interpolate_station_profile(
	control_stations: List[Tuple[float, float, float, float]],
	u: float,
) -> Tuple[float, float, float, float]:
	"""Catmull-Rom / piecewise smooth interpolation of (z_pos, rx, ry_dorsal, ry_ventral) at u in [0, 1]."""
	n = len(control_stations)
	if u <= 0.0:
		return control_stations[0]
	if u >= 1.0:
		return control_stations[-1]

	z_start = control_stations[0][0]
	z_end = control_stations[-1][0]
	target_z = lerp(z_start, z_end, u)

	for idx in range(n - 1):
		z0, rx0, ryd0, ryv0 = control_stations[idx]
		z1, rx1, ryd1, ryv1 = control_stations[idx + 1]
		if z1 <= target_z <= z0 or idx == n - 2:
			span = max(1e-6, abs(z0 - z1))
			local_t = clamp01(abs(z0 - target_z) / span)
			# Smooth hermite blend for organic muscle transitions
			st = local_t * local_t * (3.0 - 2.0 * local_t)
			return (
				target_z,
				lerp(rx0, rx1, st),
				lerp(ryd0, ryd1, st),
				lerp(ryv0, ryv1, st),
			)
	return control_stations[-1]


def build_pleated_fin_bmesh(
	bm: bmesh.types.BMesh,
	origin: Tuple[float, float, float],
	span_vec: Tuple[float, float, float],
	length_vec: Tuple[float, float, float],
	thickness: float,
	num_rays: int,
	span_steps: int,
	mat_idx: int,
	scallop_depth: float = 0.14,
	spiny_leading: bool = False,
	profile_taper: Tuple[float, float] = (1.0, 0.42),
) -> None:
	"""
	Builds a 3D ribbed fin with alternating raised bony fin-ray spines and thin pleated webbing
	membranes with scalloped outer edges.
	"""
	ox, oy, oz = origin
	sx, sy, sz = span_vec
	lx, ly, lz = length_vec

	s_vec = Vector((sx, sy, sz))
	l_vec = Vector((lx, ly, lz))
	n_vec = s_vec.cross(l_vec)
	if n_vec.length < 1e-6:
		n_vec = Vector((1.0, 0.0, 0.0))
	else:
		n_vec.normalize()

	# Each ray has 2 longitudinal sub-columns (ray ridge + membrane valley)
	cols = max(6, num_rays * 2 + 1)
	rows = max(5, span_steps)

	grid_pos: List[List[bmesh.types.BMVert]] = []
	grid_neg: List[List[bmesh.types.BMVert]] = []

	for r in range(rows):
		v_frac = float(r) / float(rows - 1)
		row_pos: List[bmesh.types.BMVert] = []
		row_neg: List[bmesh.types.BMVert] = []
		for c in range(cols):
			u_frac = float(c) / float(cols - 1)
			is_ray_spine = (c % 2 == 0)

			# Arch curve of the fin silhouette along u_frac
			arch = math.sin(math.pi * clamp01(u_frac)) ** 0.55
			if u_frac < 0.15:
				arch = smoothstep(0.0, 0.15, u_frac)
			taper = lerp(profile_taper[0], profile_taper[1], u_frac) * (0.35 + 0.65 * arch)

			# Scalloped membrane notch at outer edge between rays (exaggerated Dredge silhouette)
			scallop = 1.0
			if not is_ray_spine:
				scallop = 1.0 - min(0.48, scallop_depth * 1.45) * (v_frac ** 1.35)
			elif spiny_leading and c < cols // 2:
				scallop = 1.0 + 0.16 * (v_frac ** 1.4)

			eff_v = v_frac * taper * scallop
			# Backward sweep of fin rays toward tip
			sweep_u = u_frac + 0.16 * (v_frac ** 1.45)

			base_pt = Vector((ox, oy, oz)) + s_vec * eff_v + l_vec * (sweep_u - 0.5)

			# Chiseled diamond-section fin rays: bony ray is sharply raised, webbing valley is deeply recessed
			ray_bulge = 1.32 if is_ray_spine else 0.18
			pleat_shift = (0.45 * thickness * math.sin(u_frac * num_rays * math.pi)) * v_frac
			half_t = max(0.0006, 0.55 * thickness * ray_bulge * (1.0 - 0.58 * v_frac))

			if r == rows - 1:
				half_t *= 0.15

			vp = bm.verts.new(base_pt + n_vec * (half_t + pleat_shift))
			vn = bm.verts.new(base_pt + n_vec * (-half_t + pleat_shift))
			row_pos.append(vp)
			row_neg.append(vn)
		grid_pos.append(row_pos)
		grid_neg.append(row_neg)

	# Connect positive & negative faces
	for r in range(rows - 1):
		for c in range(cols - 1):
			try:
				f1 = bm.faces.new((grid_pos[r][c], grid_pos[r][c + 1], grid_pos[r + 1][c + 1], grid_pos[r + 1][c]))
				f1.material_index = mat_idx
			except ValueError:
				pass
			try:
				f2 = bm.faces.new((grid_neg[r][c], grid_neg[r + 1][c], grid_neg[r + 1][c + 1], grid_neg[r][c + 1]))
				f2.material_index = mat_idx
			except ValueError:
				pass

	# Stitch outer perimeter (tip row and leading/trailing edges)
	top_r = rows - 1
	for c in range(cols - 1):
		try:
			ft = bm.faces.new((grid_pos[top_r][c], grid_neg[top_r][c], grid_neg[top_r][c + 1], grid_pos[top_r][c + 1]))
			ft.material_index = mat_idx
		except ValueError:
			pass
	for r in range(rows - 1):
		try:
			fl = bm.faces.new((grid_neg[r][0], grid_pos[r][0], grid_pos[r + 1][0], grid_neg[r + 1][0]))
			fl.material_index = mat_idx
			fr = bm.faces.new((grid_pos[r][-1], grid_neg[r][-1], grid_neg[r + 1][-1], grid_pos[r + 1][-1]))
			fr.material_index = mat_idx
		except ValueError:
			pass


def build_caudal_tail_bmesh(
	bm: bmesh.types.BMesh,
	peduncle_z: float,
	tail_end_z: float,
	peduncle_rx: float,
	peduncle_ry: float,
	tail_span_y: float,
	fork_depth: float,
	serpentine_x: float,
	flatfish_mode: bool,
	mat_idx: int,
) -> None:
	"""
	Builds a 3D ribbed, multi-ray caudal tail fin (forked, lunate, or rounded) with raised bony
	caudal fin rays and scalloped webbing membranes.
	"""
	num_rays = 19  # 19 rays -> 37 vertical stations across the caudal fan
	u_steps = 8    # 8 longitudinal stations from peduncle wrist to trailing edge

	grid_pos: List[List[bmesh.types.BMVert]] = []
	grid_neg: List[List[bmesh.types.BMVert]] = []

	for u_idx in range(u_steps):
		u = float(u_idx) / float(u_steps - 1)
		row_p: List[bmesh.types.BMVert] = []
		row_n: List[bmesh.types.BMVert] = []
		for v_idx in range(num_rays * 2 - 1):
			v = (float(v_idx) / float(num_rays * 2 - 2)) * 2.0 - 1.0  # -1..+1
			is_ray = (v_idx % 2 == 0)

			# Span flares from peduncle_ry to tail_span_y
			flare_y = lerp(peduncle_ry * 0.85, tail_span_y, u ** 0.78) * v

			# Fork indentation at center (v near 0) and lobe rounding near |v| == 1
			center_notch = math.exp(-(v * v) / 0.18) * fork_depth * (u ** 1.35)
			lobe_round = 0.018 * (v ** 4) * u
			scallop_z = 0.0 if is_ray else (0.008 * u)

			z_val = lerp(peduncle_z, tail_end_z, u) + center_notch + lobe_round + scallop_z

			# Ribbed thickness
			ray_factor = 1.0 if is_ray else 0.30
			pleat_x = 0.0018 * math.sin(v * num_rays * math.pi) * u
			half_thick = lerp(peduncle_rx * 0.65, 0.0016, u) * ray_factor
			if u_idx == u_steps - 1:
				half_thick *= 0.22

			if flatfish_mode:
				# Flatfish tail lies along the same vertical YZ plane as standard fish in our coordinate space
				pass

			x_center = serpentine_x + pleat_x
			row_p.append(bm.verts.new((x_center + half_thick, flare_y, z_val)))
			row_n.append(bm.verts.new((x_center - half_thick, flare_y, z_val)))

		grid_pos.append(row_p)
		grid_neg.append(row_n)

	cols = len(grid_pos[0])
	for r in range(u_steps - 1):
		for c in range(cols - 1):
			try:
				f1 = bm.faces.new((grid_pos[r][c], grid_pos[r][c + 1], grid_pos[r + 1][c + 1], grid_pos[r + 1][c]))
				f1.material_index = mat_idx
				f2 = bm.faces.new((grid_neg[r][c], grid_neg[r + 1][c], grid_neg[r + 1][c + 1], grid_neg[r][c + 1]))
				f2.material_index = mat_idx
			except ValueError:
				pass

	# Stitch trailing edge & dorsal/ventral margins
	last_r = u_steps - 1
	for c in range(cols - 1):
		try:
			ft = bm.faces.new((grid_pos[last_r][c], grid_neg[last_r][c], grid_neg[last_r][c + 1], grid_pos[last_r][c + 1]))
			ft.material_index = mat_idx
		except ValueError:
			pass
	for r in range(u_steps - 1):
		try:
			fd = bm.faces.new((grid_neg[r][0], grid_pos[r][0], grid_pos[r + 1][0], grid_neg[r + 1][0]))
			fd.material_index = mat_idx
			fv = bm.faces.new((grid_pos[r][-1], grid_neg[r][-1], grid_neg[r + 1][-1], grid_pos[r + 1][-1]))
			fv.material_index = mat_idx
		except ValueError:
			pass


def add_curved_tooth_bmesh(
	bm: bmesh.types.BMesh,
	base_pos: Tuple[float, float, float],
	direction: Tuple[float, float, float],
	curve_vec: Tuple[float, float, float],
	base_radius: float,
	length: float,
	mat_idx: int,
	segments: int = 8,
	rings: int = 5,
) -> None:
	"""Adds a curved 3D conical tooth/fang/tusk into the BMesh."""
	bx, by, bz = base_pos
	d = Vector(direction).normalized()
	c = Vector(curve_vec)
	up_ref = Vector((0.0, 0.0, 1.0)) if abs(d.z) < 0.9 else Vector((1.0, 0.0, 0.0))
	t1 = d.cross(up_ref).normalized()
	t2 = d.cross(t1).normalized()

	ring_lists: List[List[bmesh.types.BMVert]] = []
	for r in range(rings):
		frac = float(r) / float(rings - 1)
		rad = max(0.0003, base_radius * ((1.0 - frac) ** 0.85))
		center = Vector((bx, by, bz)) + d * (length * frac) + c * (frac * frac)
		ring: List[bmesh.types.BMVert] = []
		for s in range(segments):
			ang = (2.0 * math.pi * float(s)) / float(segments)
			pt = center + (t1 * math.cos(ang) + t2 * math.sin(ang)) * rad
			ring.append(bm.verts.new(pt))
		ring_lists.append(ring)

	for r in range(rings - 1):
		for s in range(segments):
			ns = (s + 1) % segments
			try:
				f = bm.faces.new((ring_lists[r][s], ring_lists[r][ns], ring_lists[r + 1][ns], ring_lists[r + 1][s]))
				f.material_index = mat_idx
			except ValueError:
				pass

	tip_vert = bm.verts.new(Vector((bx, by, bz)) + d * length + c)
	last_ring = ring_lists[-1]
	for s in range(segments):
		ns = (s + 1) % segments
		try:
			f = bm.faces.new((last_ring[s], last_ring[ns], tip_vert))
			f.material_index = mat_idx
		except ValueError:
			pass


def add_two_layer_anatomical_eye_bmesh(
	bm: bmesh.types.BMesh,
	center: Tuple[float, float, float],
	outward_normal: Tuple[float, float, float],
	radius: float,
	iris_mat_idx: int,
	cornea_mat_idx: int,
) -> None:
	"""
	Builds a two-layer anatomical fish eye:
	1. Inner eyeball sphere with a recessed pupil concavity & raised iris ring (iris_mat_idx)
	2. Outer glossy bulging cornea lens dome (cornea_mat_idx, Roughness=0.02, Coat=1.0)
	"""
	cx, cy, cz = center
	n = Vector(outward_normal).normalized()
	ref = Vector((0.0, 0.0, 1.0)) if abs(n.z) < 0.9 else Vector((0.0, 1.0, 0.0))
	u_axis = n.cross(ref).normalized()
	v_axis = n.cross(u_axis).normalized()

	segs = 16
	rings = 8

	# Layer 1: Inner Iris + Recessed Pupil Cup
	inner_rings: List[List[bmesh.types.BMVert]] = []
	for r in range(rings):
		phi = (0.55 * math.pi) * (float(r) / float(rings - 1))  # 0 at pupil center -> >90 deg rim
		sin_p = math.sin(phi)
		cos_p = math.cos(phi)
		# Recessed pupil inside r < 3, raised iris ridge at r == 3..5
		pupil_recess = -0.22 * radius * math.exp(-((float(r) / 2.2) ** 2))
		iris_flare = 0.08 * radius * math.sin(clamp01(float(r) / 5.0) * math.pi)
		axial = radius * (0.72 * cos_p) + pupil_recess + iris_flare
		radial = radius * 0.94 * sin_p
		if r == 0:
			radial = 0.0008 * radius
		ring: List[bmesh.types.BMVert] = []
		for s in range(segs):
			theta = (2.0 * math.pi * float(s)) / float(segs)
			pt = Vector((cx, cy, cz)) + n * axial + (u_axis * math.cos(theta) + v_axis * math.sin(theta)) * radial
			ring.append(bm.verts.new(pt))
		inner_rings.append(ring)

	for r in range(rings - 1):
		for s in range(segs):
			ns = (s + 1) % segs
			try:
				f = bm.faces.new((inner_rings[r][s], inner_rings[r + 1][s], inner_rings[r + 1][ns], inner_rings[r][ns]))
				f.material_index = iris_mat_idx
			except ValueError:
				pass

	# Layer 2: Chiseled Orbital Sclera Bezel Ring (frames the recessed pupil & glowing metallic iris without occluding them)
	cornea_rings: List[List[bmesh.types.BMVert]] = []
	for r in range(rings // 2, rings):
		phi = (0.56 * math.pi) * (float(r) / float(rings - 1))
		sin_p = math.sin(phi)
		cos_p = math.cos(phi)
		axial = radius * (0.76 * cos_p)
		radial = max(0.0008 * radius, radius * 1.04 * sin_p)
		ring = []
		for s in range(segs):
			theta = (2.0 * math.pi * float(s)) / float(segs)
			pt = Vector((cx, cy, cz)) + n * axial + (u_axis * math.cos(theta) + v_axis * math.sin(theta)) * radial
			ring.append(bm.verts.new(pt))
		cornea_rings.append(ring)

	for r in range(len(cornea_rings) - 1):
		for s in range(segs):
			ns = (s + 1) % segs
			try:
				f = bm.faces.new((cornea_rings[r][s], cornea_rings[r + 1][s], cornea_rings[r + 1][ns], cornea_rings[r][ns]))
				f.material_index = cornea_mat_idx
			except ValueError:
				pass


def add_gill_arches_and_operculum_bmesh(
	bm: bmesh.types.BMesh,
	gill_z: float,
	rx_at_gill: float,
	ry_dorsal: float,
	ry_ventral: float,
	wave_x: float,
	operculum_mat_idx: int,
	gill_arch_mat_idx: int,
) -> None:
	"""
	Builds flared left/right Operculum (bony gill cover plates) with a crescent contour
	and 3 crimson branchial gill arches tucked inside each gill cavity.
	"""
	for side_sign in (-1.0, 1.0):
		# 1. Crescent-contoured Bony Operculum Plate (tapers into body at dorsal/ventral ends)
		u_steps = 6
		v_steps = 9
		op_outer: List[List[bmesh.types.BMVert]] = []
		op_inner: List[List[bmesh.types.BMVert]] = []
		span_z = max(0.018, min(0.038, rx_at_gill * 0.42))
		for u_i in range(u_steps):
			u = float(u_i) / float(u_steps - 1)  # 0 = anterior hinge, 1 = flared posterior margin
			row_o: List[bmesh.types.BMVert] = []
			row_i: List[bmesh.types.BMVert] = []
			for v_i in range(v_steps):
				v = (float(v_i) / float(v_steps - 1)) * 2.0 - 1.0  # -1 ventral .. +1 dorsal
				crescent = math.cos(v * 0.46 * math.pi)
				ang = v * 0.68
				ry = ry_dorsal if ang >= 0.0 else ry_ventral
				y_pos = math.sin(ang) * ry * 0.72
				flare_out = side_sign * rx_at_gill * (0.94 + 0.11 * (u ** 1.2) * crescent)
				x_curve = math.cos(ang) * flare_out + wave_x
				z_off = gill_z + lerp(span_z, -span_z, u) * (0.55 + 0.45 * crescent) - 0.012 * math.sin(u * math.pi) * crescent
				thick = side_sign * 0.0035 * (1.0 - 0.55 * u) * crescent

				row_o.append(bm.verts.new((x_curve + thick, y_pos, z_off)))
				row_i.append(bm.verts.new((x_curve - thick * 0.5, y_pos, z_off)))
			op_outer.append(row_o)
			op_inner.append(row_i)

		for r in range(u_steps - 1):
			for c in range(v_steps - 1):
				try:
					if side_sign > 0.0:
						f1 = bm.faces.new((op_outer[r][c], op_outer[r + 1][c], op_outer[r + 1][c + 1], op_outer[r][c + 1]))
						f2 = bm.faces.new((op_inner[r][c], op_inner[r][c + 1], op_inner[r + 1][c + 1], op_inner[r + 1][c]))
					else:
						f1 = bm.faces.new((op_outer[r][c], op_outer[r][c + 1], op_outer[r + 1][c + 1], op_outer[r + 1][c]))
						f2 = bm.faces.new((op_inner[r][c], op_inner[r + 1][c], op_inner[r + 1][c + 1], op_inner[r][c + 1]))
					f1.material_index = operculum_mat_idx
					f2.material_index = gill_arch_mat_idx
				except ValueError:
					pass

		# 2. Three Crimson Branchial Gill Arches visible inside the opercular gap
		for arch_idx in range(3):
			arch_z = gill_z - 0.008 - float(arch_idx) * 0.014
			arch_rx = rx_at_gill * (0.86 - float(arch_idx) * 0.04)
			arch_pts = 8
			arch_segs = 6
			arch_rings: List[List[bmesh.types.BMVert]] = []
			for p_i in range(arch_pts):
				v = (float(p_i) / float(arch_pts - 1)) * 2.0 - 1.0
				ang = v * 0.78
				ry = ry_dorsal if ang >= 0.0 else ry_ventral
				cy = math.sin(ang) * ry * 0.72
				cx = side_sign * math.cos(ang) * arch_rx + wave_x
				cz = arch_z - 0.012 * math.cos(ang)
				tube_r = 0.0042 * (1.0 - 0.35 * v * v)
				ring: List[bmesh.types.BMVert] = []
				for s in range(arch_segs):
					ta = (2.0 * math.pi * float(s)) / float(arch_segs)
					ring.append(bm.verts.new((cx + math.cos(ta) * tube_r, cy, cz + math.sin(ta) * tube_r)))
				arch_rings.append(ring)
			for p_i in range(arch_pts - 1):
				for s in range(arch_segs):
					ns = (s + 1) % arch_segs
					try:
						f = bm.faces.new((arch_rings[p_i][s], arch_rings[p_i][ns], arch_rings[p_i + 1][ns], arch_rings[p_i + 1][s]))
						f.material_index = gill_arch_mat_idx
					except ValueError:
						pass


def paint_fish_vertex_colors(
	mesh: bpy.types.Mesh,
	spec: Dict,
) -> None:
	"""
	Creates the byte vertex color attribute `Col` (BYTE_COLOR on CORNER domain) and procedurally
	paints biological counter-shading, lateral sensory lines, and species-specific markings.
	"""
	while len(mesh.color_attributes) > 0:
		mesh.color_attributes.remove(mesh.color_attributes[0])

	col_attr = mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")

	species_id: str = spec["id"]
	dorsal_col: Tuple[float, float, float, float] = spec["dorsal_color"]
	belly_col: Tuple[float, float, float, float] = spec["belly_color"]
	fin_col: Tuple[float, float, float, float] = spec["fin_color"]
	accent_col: Tuple[float, float, float, float] = spec.get("accent_color", dorsal_col)
	eye_col: Tuple[float, float, float, float] = spec.get("eye_color", (0.85, 0.72, 0.25, 1.0))
	flatfish_mode: bool = spec.get("flatfish_mode", False)

	stations = spec["stations"]
	z_min = min(s[0] for s in stations)
	z_max = max(s[0] for s in stations)
	z_span = max(0.1, z_max - z_min)

	verts = mesh.vertices
	loops = mesh.loops
	num_verts = len(verts)
	num_loops = len(loops)

	# Map each vertex to its primary polygon material_index and compute topological concavity/ridge curvature
	vert_mat_idx = [0] * num_verts
	vert_neighbors: List[List[int]] = [[] for _ in range(num_verts)]
	for edge in mesh.edges:
		v0, v1 = edge.vertices[0], edge.vertices[1]
		vert_neighbors[v0].append(v1)
		vert_neighbors[v1].append(v0)

	for poly in mesh.polygons:
		m_i = poly.material_index
		for v_i in poly.vertices:
			if m_i != 0 or vert_mat_idx[v_i] == 0:
				vert_mat_idx[v_i] = m_i

	# Compute geometric cavity/ridge curvature: positive = concave crevice, negative = sharp convex ridge
	vert_concavity: List[float] = [0.0] * num_verts
	for v_idx in range(num_verts):
		nbrs = vert_neighbors[v_idx]
		if not nbrs:
			continue
		v = verts[v_idx]
		avg_co = Vector((0.0, 0.0, 0.0))
		avg_edge_len = 0.0
		for n_idx in nbrs:
			nco = verts[n_idx].co
			avg_co += nco
			avg_edge_len += (nco - v.co).length
		inv_n = 1.0 / float(len(nbrs))
		avg_co *= inv_n
		avg_edge_len = max(0.001, avg_edge_len * inv_n)
		diff = avg_co - v.co
		# Normalized signed projection onto vertex normal
		vert_concavity[v_idx] = diff.dot(v.normal) / avg_edge_len

	vert_colors: List[Tuple[float, float, float, float]] = [(0.5, 0.5, 0.5, 1.0)] * num_verts
	ink_black: Tuple[float, float, float, float] = (0.012, 0.015, 0.022, 1.0)

	for v_idx in range(num_verts):
		v = verts[v_idx]
		vx, vy, vz = v.co.x, v.co.y, v.co.z
		nx = v.normal.x
		mat_idx = vert_mat_idx[v_idx]

		# Normalized longitudinal coordinate (0 = snout tip, 1 = tail tip)
		u_long = clamp01((z_max - vz) / z_span)

		# Special material slots:
		# 2 = OralGillCavity, 3 = TeethIvory, 4 = EyeIrisPupil, 5 = EyeCorneaLens, 6 = BiolumEscaLure
		if mat_idx == 2:
			if vz < -0.055:
				vert_colors[v_idx] = (0.58, 0.08, 0.10, 1.0)
			else:
				vert_colors[v_idx] = (0.14, 0.05, 0.07, 1.0)
			continue
		elif mat_idx == 3:
			vert_colors[v_idx] = (0.92, 0.89, 0.78, 1.0)
			continue
		elif mat_idx == 4:
			# Recessed dark pupil in center of eye, bright metallic iris ring around it
			eye_y_dist = abs(vy - spec.get("eye_pos", (0.065, 0.035, -0.09))[1])
			eye_z_dist = abs(vz - spec.get("eye_pos", (0.065, 0.035, -0.09))[2])
			r_eye = math.sqrt(eye_y_dist * eye_y_dist + eye_z_dist * eye_z_dist)
			if r_eye < spec.get("eye_radius", 0.018) * 0.48:
				vert_colors[v_idx] = (0.01, 0.01, 0.015, 1.0)
			else:
				vert_colors[v_idx] = eye_col
			continue
		elif mat_idx == 5:
			# Dark charcoal orbital sclera rim framing the glowing iris
			vert_colors[v_idx] = (0.04, 0.05, 0.06, 1.0)
			continue
		elif mat_idx == 6:
			vert_colors[v_idx] = accent_col
			continue

		# Base biological counter-shading (Dorsal -> Iridescent Mid-Flank -> Ventral Belly)
		local_ry = max(0.03, 0.12 * (1.0 - 0.55 * u_long))
		y_norm = max(-1.0, min(1.0, vy / local_ry))

		if flatfish_mode:
			eyed_mask = smoothstep(-0.008, 0.012, vx)
			mottle = fbm3d(vx * 18.0, vy * 18.0, vz * 18.0, 2)
			spot_ring = math.sin(vy * 38.0 + mottle * 6.5) * math.cos(vz * 34.0 - mottle * 5.0)
			eyed_col = lerp_color(
				(0.11, 0.09, 0.07, 1.0),
				(0.24, 0.20, 0.15, 1.0),
				clamp01(mottle * 1.1 + 0.25 * spot_ring),
			)
			blind_col = (0.90, 0.92, 0.89, 1.0)
			base_rgba = lerp_color(blind_col, eyed_col, eyed_mask)
		else:
			belly_t = smoothstep(-0.55, 0.32, y_norm)
			mid_band = math.exp(-((y_norm - 0.05) ** 2) / 0.16)
			mid_col = lerp_color(belly_col, dorsal_col, 0.52)
			base_rgba = lerp_color(belly_col, dorsal_col, belly_t)
			base_rgba = lerp_color(base_rgba, mid_col, mid_band * 0.35)

		if species_id == "mackerel":
			if y_norm > -0.05:
				wiggle = 0.42 * math.sin(vy * 36.0 + vz * 12.0) + 0.25 * noise3d(vx * 20.0, vy * 20.0, vz * 20.0)
				tiger_wave = math.sin(vz * 82.0 + wiggle * 6.2 + abs(vy) * 18.0)
				tiger_mask = smoothstep(0.15, 0.65, tiger_wave) * smoothstep(-0.05, 0.28, y_norm)
				irid_back = lerp_color((0.04, 0.32, 0.38, 1.0), (0.08, 0.46, 0.42, 1.0), 0.5 + 0.5 * math.sin(vz * 18.0))
				base_rgba = lerp_color(base_rgba, irid_back, smoothstep(0.0, 0.45, y_norm) * 0.75)
				base_rgba = lerp_color(base_rgba, (0.015, 0.05, 0.11, 1.0), tiger_mask * 0.88)
			else:
				sheen = 0.5 + 0.5 * math.sin(vz * 15.0 + vy * 25.0)
				base_rgba = lerp_color(base_rgba, (0.84, 0.88, 0.92, 1.0), sheen * 0.35)

		elif species_id in ("cod", "monkfish"):
			m1 = fbm3d(vx * 22.0, vy * 22.0, vz * 22.0, 2)
			m2 = noise3d(vx * 48.0 + 7.1, vy * 48.0 - 3.4, vz * 48.0 + 11.2)
			retic = smoothstep(0.42, 0.68, m1)
			spots = smoothstep(0.58, 0.78, m2)
			ochre = (0.34, 0.29, 0.16, 1.0) if species_id == "cod" else (0.28, 0.20, 0.14, 1.0)
			dark_blotch = (0.08, 0.09, 0.05, 1.0) if species_id == "cod" else (0.06, 0.04, 0.03, 1.0)
			dorsal_weight = smoothstep(-0.35, 0.25, y_norm)
			base_rgba = lerp_color(base_rgba, ochre, retic * dorsal_weight * 0.72)
			base_rgba = lerp_color(base_rgba, dark_blotch, spots * dorsal_weight * 0.78)

			if species_id == "cod":
				lat_y = 0.022 * math.sin(u_long * math.pi)
				lat_dist = abs(vy - lat_y)
				if 0.12 < u_long < 0.92 and abs(vx) > 0.015:
					lat_mask = smoothstep(0.014, 0.003, lat_dist)
					base_rgba = lerp_color(base_rgba, (0.86, 0.84, 0.72, 1.0), lat_mask * 0.92)

		elif species_id == "pollock":
			lat_y = 0.015 * math.sin(u_long * math.pi)
			if 0.12 < u_long < 0.92 and abs(vx) > 0.012:
				lat_mask = smoothstep(0.012, 0.0025, abs(vy - lat_y))
				base_rgba = lerp_color(base_rgba, (0.82, 0.85, 0.76, 1.0), lat_mask * 0.88)

		elif species_id == "rockfish":
			mottle = fbm3d(vx * 24.0, vy * 24.0, vz * 24.0, 2)
			saddle_wave = math.sin(vz * 24.0 + mottle * 2.5)
			saddle_mask = smoothstep(0.20, 0.65, saddle_wave) * smoothstep(0.05, 0.45, y_norm)
			vermilion = (0.76, 0.16, 0.09, 1.0)
			orange_belly = (0.88, 0.46, 0.20, 1.0)
			dusky_saddle = (0.20, 0.05, 0.04, 1.0)
			base_rgba = lerp_color(orange_belly, vermilion, smoothstep(-0.45, 0.25, y_norm))
			base_rgba = lerp_color(base_rgba, dusky_saddle, saddle_mask * 0.82)

		elif species_id == "wolffish":
			bar_warp = 0.025 * noise3d(vx * 18.0, vy * 18.0, vz * 18.0)
			bar_phase = math.sin((vz + bar_warp) * 48.0)
			bar_mask = smoothstep(0.18, 0.68, bar_phase) * smoothstep(-0.35, 0.15, y_norm)
			spots = smoothstep(0.55, 0.75, noise3d(vx * 42.0, vy * 42.0, vz * 42.0))
			dark_bar = (0.07, 0.05, 0.10, 1.0)
			base_rgba = lerp_color(base_rgba, dark_bar, max(bar_mask * 0.85, spots * 0.55))

		elif species_id == "oarfish":
			if mat_idx == 1 or (vy > 0.075 and abs(vx) < 0.018):
				crest_var = 0.5 + 0.5 * math.sin(vz * 30.0)
				base_rgba = lerp_color((0.88, 0.06, 0.10, 1.0), (0.98, 0.16, 0.18, 1.0), crest_var)
			else:
				streak = noise3d(vx * 25.0, vy * 35.0, vz * 14.0)
				streak_mask = smoothstep(0.62, 0.80, streak)
				chrome = (0.82, 0.87, 0.92, 1.0)
				midnight = (0.14, 0.20, 0.34, 1.0)
				base_rgba = lerp_color(chrome, midnight, streak_mask * 0.72)

		elif species_id in ("angler", "scabbardfish"):
			vein_n = abs(math.sin(vx * 55.0 + vy * 42.0 + vz * 38.0 + 3.0 * noise3d(vx * 25.0, vy * 25.0, vz * 25.0)))
			vein_mask = smoothstep(0.08, 0.0, vein_n)
			jaw_or_fin_prox = 1.0 if (u_long < 0.28 or abs(y_norm) > 0.62 or mat_idx == 1) else 0.35
			biolum_vein = (0.18, 0.78, 0.86, 1.0) if species_id == "angler" else (0.36, 0.28, 0.68, 1.0)
			base_rgba = lerp_color(base_rgba, biolum_vein, vein_mask * jaw_or_fin_prox * 0.65)

		elif species_id in ("hake", "grenadier"):
			scale_pocket = 0.5 + 0.5 * math.sin(vz * 95.0 + vy * 95.0) * math.sin(vz * 95.0 - vy * 95.0)
			base_rgba = lerp_color(base_rgba, accent_col, scale_pocket * 0.28)

		if mat_idx == 1 and species_id != "oarfish":
			ray_highlight = clamp01(abs(nx) * 0.65)
			base_rgba = lerp_color(fin_col, base_rgba, 0.25 + 0.45 * ray_highlight)

		# Stylized Dark Lovecraftian Cavity Ink-Wash & Chiseled Ridge Highlights (Dredge / Darkest Dungeon style)
		concav = vert_concavity[v_idx]
		# Anatomical crevice boost: gill slit zone, mouth corners, deep orbital rim, lateral line groove, fin base
		gill_crevice = 0.0
		if 0.135 <= u_long <= 0.215 and abs(vx) > 0.015:
			gill_crevice = 0.65 * math.sin(((u_long - 0.135) / 0.080) * math.pi)
		mouth_corner_crevice = 0.0
		if u_long < 0.115 and abs(y_norm) < 0.30:
			mouth_corner_crevice = 0.72 * (1.0 - u_long / 0.115) * (1.0 - abs(y_norm) / 0.30)

		cavity_ink_weight = clamp01(smoothstep(0.008, 0.14, concav) * 0.88 + gill_crevice + mouth_corner_crevice)
		if mat_idx == 1 and concav > 0.005:
			# Deep ink wash inside pleated fin webbing valleys between bony rays
			cavity_ink_weight = clamp01(cavity_ink_weight + 0.45 * smoothstep(0.005, 0.09, concav))

		if cavity_ink_weight > 0.0:
			base_rgba = lerp_color(base_rgba, ink_black, cavity_ink_weight * 0.90)

		# Crisp hand-painted ridge highlight along sharp chiseled bevel crests & fin-ray spines
		ridge_strength = clamp01(smoothstep(-0.012, -0.15, concav))
		if ridge_strength > 0.0:
			ridge_tint = (
				min(1.0, base_rgba[0] * 1.45 + 0.14),
				min(1.0, base_rgba[1] * 1.45 + 0.15),
				min(1.0, base_rgba[2] * 1.45 + 0.16),
				1.0,
			)
			base_rgba = lerp_color(base_rgba, ridge_tint, ridge_strength * 0.58)

		vert_colors[v_idx] = base_rgba

	flat_loop_colors: List[float] = [0.0] * (num_loops * 4)
	for loop_idx in range(num_loops):
		c = vert_colors[loops[loop_idx].vertex_index]
		base_offset = loop_idx * 4
		flat_loop_colors[base_offset] = c[0]
		flat_loop_colors[base_offset + 1] = c[1]
		flat_loop_colors[base_offset + 2] = c[2]
		flat_loop_colors[base_offset + 3] = c[3]

	col_attr.data.foreach_set("color", flat_loop_colors)


def build_anatomical_fish(
	spec: Dict,
	out_glb_path: str,
) -> None:
	clear_scene()

	species_id: str = spec["id"]
	flatfish_mode: bool = spec.get("flatfish_mode", False)

	# 7 Multi-Slot Wet Mucus Clearcoat Materials
	mat_body = create_vertex_color_wet_material(
		f"{species_id}_BodySkin",
		spec["dorsal_color"],
		metallic=spec.get("metallic", 0.35),
		roughness=0.14,
		coat_weight=1.0,
		coat_roughness=0.03,
	)
	mat_fins = create_vertex_color_wet_material(
		f"{species_id}_PleatedFins",
		spec["fin_color"],
		metallic=max(0.25, spec.get("metallic", 0.35) * 0.8),
		roughness=0.14,
		coat_weight=1.0,
		coat_roughness=0.03,
		emission_color=spec.get("fin_emission", (0.0, 0.0, 0.0, 1.0)),
		emission_strength=spec.get("fin_emission_strength", 0.0),
	)
	mat_oral_gill = create_vertex_color_wet_material(
		f"{species_id}_OralGillCavity",
		(0.38, 0.06, 0.08, 1.0),
		metallic=0.15,
		roughness=0.12,
		coat_weight=1.0,
		coat_roughness=0.02,
	)
	mat_teeth = create_vertex_color_wet_material(
		f"{species_id}_TeethIvory",
		(0.92, 0.89, 0.78, 1.0),
		metallic=0.10,
		roughness=0.08,
		coat_weight=1.0,
		coat_roughness=0.02,
	)
	mat_eye_iris = create_vertex_color_wet_material(
		f"{species_id}_EyeIris",
		spec.get("eye_color", (0.85, 0.72, 0.25, 1.0)),
		metallic=0.55,
		roughness=0.08,
		coat_weight=1.0,
		coat_roughness=0.02,
		emission_color=spec.get("eye_emission", (0.0, 0.0, 0.0, 1.0)),
		emission_strength=spec.get("eye_emission_strength", 0.0),
	)
	mat_eye_cornea = create_vertex_color_wet_material(
		f"{species_id}_EyeCorneaLens",
		(0.96, 0.98, 1.0, 1.0),
		metallic=0.25,
		roughness=0.02,
		coat_weight=1.0,
		coat_roughness=0.01,
		use_vertex_color=True,
	)
	mat_esca = create_vertex_color_wet_material(
		f"{species_id}_BiolumEsca",
		spec.get("accent_color", (0.25, 0.95, 0.88, 1.0)),
		metallic=0.25,
		roughness=0.10,
		coat_weight=1.0,
		coat_roughness=0.02,
		emission_color=spec.get("lure_emission", (0.20, 0.95, 0.85, 1.0)),
		emission_strength=spec.get("lure_emission_strength", 12.0),
	)

	bm = bmesh.new()

	control_stations: List[Tuple[float, float, float, float]] = spec["stations"]
	num_spine_stations: int = 64
	ring_verts: int = 36

	serpentine_amp: float = max(0.018, spec.get("serpentine_amp", 0.022))
	jaw_underbite: float = spec.get("jaw_underbite", 0.018) * 1.45
	mouth_gape: float = spec.get("mouth_gape", 0.028) * 1.35
	tail_fork_depth: float = spec.get("tail_fork_depth", 0.045) * 1.20
	eye_pos: Tuple[float, float, float] = spec.get("eye_pos", (0.065, 0.035, -0.09))
	eye_radius: float = spec.get("eye_radius", 0.018) * 1.12
	scale_amp: float = spec.get("scale_disp_strength", 0.0028)

	z_start = control_stations[0][0]
	z_end = control_stations[-1][0]
	body_length = abs(z_end - z_start)

	# 1. Build 5 Recessed Oral Cavity Throat Rings (inside the gaping mouth) + 64 Anatomical Body Spine Stations
	all_rings: List[List[bmesh.types.BMVert]] = []
	ring_mat_indices: List[int] = []

	# Throat cavity rings (from deep throat z = -0.105 forward to inner lip z = -0.004)
	throat_depths = [
		(-0.105, 0.18),
		(-0.082, 0.42),
		(-0.055, 0.68),
		(-0.026, 0.86),
		(-0.005, 0.96),
	]
	_, rx_mouth, ryd_mouth, ryv_mouth = interpolate_station_profile(control_stations, 0.06)

	for tz, t_scale in throat_depths:
		t_ring: List[bmesh.types.BMVert] = []
		for i in range(ring_verts):
			theta = (2.0 * math.pi * float(i)) / float(ring_verts)
			ca = math.cos(theta)
			sa = math.sin(theta)
			ry_base = ryd_mouth if sa >= 0.0 else (ryv_mouth + mouth_gape * 0.65)
			vx = ca * rx_mouth * t_scale * 0.78
			vy = sa * ry_base * t_scale * 0.78
			vz = tz
			if sa < -0.15 and tz > -0.04:
				vz += jaw_underbite * 0.55 * abs(sa)
			t_ring.append(bm.verts.new((vx, vy, vz)))
		all_rings.append(t_ring)
		ring_mat_indices.append(2)  # Slot 2 = OralGillCavity

	# 64 Longitudinal Spine Stations from open lip rim (u=0) to caudal peduncle (u=1)
	peduncle_station = control_stations[-2]
	tail_tip_station = control_stations[-1]
	peduncle_z = peduncle_station[0]

	for s_idx in range(num_spine_stations):
		u = float(s_idx) / float(num_spine_stations - 1)
		# Map u across the main body from snout (0.0) to caudal peduncle wrist (0.90 of station list)
		u_profile = u * 0.89
		z_pos, rx, ry_dorsal, ry_ventral = interpolate_station_profile(control_stations, u_profile)

		# Dynamic S-curve swimming/thrashing bend
		wave_x = serpentine_amp * math.sin(u * 2.15 * math.pi - 0.35) * (u ** 0.75)
		wave_y = 0.008 * math.cos(u * 1.8 * math.pi) * u

		ring: List[bmesh.types.BMVert] = []
		for i in range(ring_verts):
			theta = (2.0 * math.pi * float(i)) / float(ring_verts)
			ca = math.cos(theta)
			sa = math.sin(theta)
			ry = ry_dorsal if sa >= 0.0 else ry_ventral

			# A. Stylized Chiseled Planar Facets, Dorsal Epaxial Ridges & Pinched Belly Keel
			# Quantize cross-section into 10 bold planar bevel facets so light breaks in stylized bands
			chisel_facet = 1.0 - 0.046 * (1.0 - abs(math.cos(theta * 5.0)))
			muscle_ridge = chisel_facet
			if sa > 0.32 and 0.08 < u < 0.86:
				# Exaggerated dorsal crest & twin epaxial bevel planes
				muscle_ridge += 0.115 * math.sin((abs(ca) ** 0.75) * math.pi * 2.0) * math.sin(u * math.pi)
			elif sa < -0.60 and 0.15 < u < 0.76:
				# Sharp angular ventral keel bevel
				muscle_ridge += 0.065 * (abs(sa) - 0.60)

			# B. Recessed Orbital Eye Sockets & Sharp Angular Supraorbital Brow Ridges
			eye_z_dist = abs(z_pos - eye_pos[2])
			socket_mod = 1.0
			if eye_z_dist < eye_radius * 2.25:
				z_fac = math.cos((eye_z_dist / (eye_radius * 2.25)) * 0.5 * math.pi)
				target_ey_norm = eye_pos[1] / max(0.02, ry_dorsal)
				ang_dist = abs(sa - target_ey_norm)
				if not flatfish_mode or ca > 0.0:
					if ang_dist < 0.30 and abs(ca) > 0.42:
						# Deeply recessed orbital socket for cavity ink shadow
						socket_mod -= 0.22 * z_fac * math.cos((ang_dist / 0.30) * 0.5 * math.pi)
					elif 0.28 <= (sa - target_ey_norm) <= 0.62 and abs(ca) > 0.36:
						# Bold chiseled supraorbital brow ridge overhang
						socket_mod += 0.18 * z_fac

			# C. Chiseled Lateral Sensory Line Bevel Groove (from upper gill cover u=0.14 to tail wrist u=0.96)
			lat_line_y = 0.12 * math.sin((u - 0.14) * math.pi)
			lat_groove = 1.0
			if 0.14 <= u <= 0.96 and abs(ca) > 0.52:
				lat_dist = abs(sa - lat_line_y)
				if lat_dist < 0.095:
					lat_groove -= 0.085 * math.cos((lat_dist / 0.095) * 0.5 * math.pi)

			# D. Deeply Recessed Sub-Opercular Gill Cavity Indentation (u in [0.14, 0.21])
			gill_indent = 1.0
			if 0.140 <= u <= 0.210 and abs(ca) > 0.35 and abs(sa) < 0.82:
				g_phase = (u - 0.140) / 0.070
				gill_indent -= 0.26 * math.sin(g_phase * math.pi)

			# E. Caudal Peduncle Lateral Keels (u > 0.80)
			keel_x = 1.0
			if u > 0.78 and abs(sa) < 0.25:
				keel_x += 0.36 * ((u - 0.78) / 0.22) * (1.0 - abs(sa) / 0.25)

			# F. Stylized Chiseled Myomere Chevrons (clean planar bands instead of noisy micro-bumps)
			myomere_bevel = 0.0
			if 0.16 < u < 0.92 and abs(ca) > 0.45:
				chevron = math.cos(z_pos * 36.0 - abs(sa) * 7.5)
				myomere_bevel = scale_amp * 0.65 * chevron * math.sin(u * math.pi)

			eff_rx = rx * muscle_ridge * socket_mod * lat_groove * gill_indent * keel_x + myomere_bevel
			eff_ry = ry * muscle_ridge * socket_mod * lat_groove * gill_indent + myomere_bevel

			# G. Exaggerated Gaping Jaws & Heavy Jutting Underbite (Dredge-inspired menacing silhouette)
			z_local = z_pos
			if u < 0.125:
				jaw_t = 1.0 - (u / 0.125)
				if sa >= 0.0:
					# Upper maxillary arch flares upward with a chiseled snout ridge
					eff_ry += mouth_gape * 0.48 * jaw_t * (sa ** 0.65)
					z_local += 0.015 * jaw_t * sa
				else:
					# Heavy hinged lower mandible juts forward (+Z) and drops wide open (-Y)
					eff_ry += mouth_gape * 0.96 * jaw_t * (abs(sa) ** 0.68)
					z_local += (jaw_underbite + 0.024) * jaw_t * (abs(sa) ** 0.8)
				# Deeply notched angular mouth corners at sa near 0
				if abs(sa) < 0.26:
					z_local -= 0.032 * jaw_t * (1.0 - abs(sa) / 0.26)

			vx = ca * eff_rx + wave_x
			vy = sa * eff_ry + wave_y
			vz = z_local
			ring.append(bm.verts.new((vx, vy, vz)))

		all_rings.append(ring)
		ring_mat_indices.append(0)  # Slot 0 = BodySkin

	# Cap the deep oral throat cavity
	try:
		f_throat = bm.faces.new(all_rings[0])
		f_throat.material_index = 2
	except ValueError:
		pass

	# Bridge all rings from deep throat -> lip rim -> caudal peduncle
	for r_idx in range(len(all_rings) - 1):
		r0 = all_rings[r_idx]
		r1 = all_rings[r_idx + 1]
		m_idx = ring_mat_indices[r_idx + 1]
		for i in range(ring_verts):
			ni = (i + 1) % ring_verts
			try:
				f = bm.faces.new((r0[i], r0[ni], r1[ni], r1[i]))
				f.material_index = m_idx
			except ValueError:
				pass

	# Cap caudal peduncle wrist
	try:
		f_ped = bm.faces.new(list(reversed(all_rings[-1])))
		f_ped.material_index = 0
	except ValueError:
		pass

	# 2. Add Flared Operculum (Gill Cover Plates) & Crimson Gill Arches
	gill_u = 0.165
	gill_z, gill_rx, gill_ryd, gill_ryv = interpolate_station_profile(control_stations, gill_u * 0.89)
	gill_wave_x = serpentine_amp * math.sin(gill_u * 2.15 * math.pi - 0.35) * (gill_u ** 0.75)
	add_gill_arches_and_operculum_bmesh(
		bm,
		gill_z=gill_z,
		rx_at_gill=gill_rx,
		ry_dorsal=gill_ryd,
		ry_ventral=gill_ryv,
		wave_x=gill_wave_x,
		operculum_mat_idx=0,
		gill_arch_mat_idx=2,
	)

	# 3. Add Species-Specific 3D Dentition (Needle Fangs, Canine Tusks, Molar Rows, Dermal Flaps)
	_, snout_rx, snout_ryd, snout_ryv = interpolate_station_profile(control_stations, 0.02)
	dentition_type: str = spec.get("dentition", "standard")

	if dentition_type in ("fangs", "angler", "scabbard", "hake"):
		num_teeth = 10 if dentition_type == "angler" else 8
		fang_len = spec.get("fang_length", 0.032)
		fang_rad = spec.get("fang_radius", 0.0042)
		for t_i in range(num_teeth):
			frac = (float(t_i) / float(num_teeth - 1)) * 2.0 - 1.0
			if abs(frac) < 0.08:
				continue
			ang = frac * 1.15
			# Lower mandible inward-curving needle fangs
			lx = math.sin(ang) * snout_rx * 0.84
			ly = -math.cos(ang * 0.65) * (snout_ryv + mouth_gape * 0.55)
			lz = 0.006 - 0.022 * (frac * frac) + jaw_underbite * 0.65
			scale_t = 1.0 - 0.45 * abs(frac)
			add_curved_tooth_bmesh(
				bm,
				base_pos=(lx, ly, lz),
				direction=(-lx * 1.2, 0.88, 0.35),
				curve_vec=(0.0, 0.004, -0.008 * scale_t),
				base_radius=fang_rad * scale_t,
				length=fang_len * scale_t,
				mat_idx=3,
			)
			# Upper maxillary needle fangs
			ux = math.sin(ang) * snout_rx * 0.80
			uy = math.cos(ang * 0.65) * (snout_ryd + mouth_gape * 0.25)
			uz = 0.004 - 0.020 * (frac * frac)
			add_curved_tooth_bmesh(
				bm,
				base_pos=(ux, uy, uz),
				direction=(-ux * 1.2, -0.85, 0.25),
				curve_vec=(0.0, -0.003, -0.007 * scale_t),
				base_radius=fang_rad * 0.85 * scale_t,
				length=fang_len * 0.82 * scale_t,
				mat_idx=3,
			)

	elif dentition_type == "wolffish":
		# Heavy anterior canine crushing tusks + inner molariform crushing rows
		for side in (-1.0, 1.0):
			for pair_idx, (x_fac, r_fac, l_fac) in enumerate(((0.35, 1.0, 1.0), (0.68, 0.82, 0.78))):
				add_curved_tooth_bmesh(
					bm,
					base_pos=(side * snout_rx * x_fac, -(snout_ryv + mouth_gape * 0.45), 0.008 - pair_idx * 0.006),
					direction=(-side * 0.15, 0.92, 0.35),
					curve_vec=(0.0, 0.002, -0.005),
					base_radius=0.0075 * r_fac,
					length=0.034 * l_fac,
					mat_idx=3,
				)
				add_curved_tooth_bmesh(
					bm,
					base_pos=(side * snout_rx * x_fac, (snout_ryd + mouth_gape * 0.22), 0.006 - pair_idx * 0.006),
					direction=(-side * 0.15, -0.92, 0.28),
					curve_vec=(0.0, -0.002, -0.005),
					base_radius=0.0070 * r_fac,
					length=0.030 * l_fac,
					mat_idx=3,
				)
			# Inner molar crushing row
			for m_idx in range(3):
				mz = -0.015 - float(m_idx) * 0.014
				add_curved_tooth_bmesh(
					bm,
					base_pos=(side * snout_rx * 0.55, -snout_ryv * 0.72, mz),
					direction=(0.0, 1.0, 0.0),
					curve_vec=(0.0, 0.0, 0.0),
					base_radius=0.0065,
					length=0.012,
					mat_idx=3,
				)

	elif dentition_type == "monkfish":
		# Wide cavernous upturned frog-like maw lined with double rows of ragged recurved teeth + dermal skin flaps
		for row_idx in range(2):
			r_scale = 1.0 if row_idx == 0 else 0.72
			z_shift = -0.008 * float(row_idx)
			for t_i in range(12):
				frac = (float(t_i) / 11.0) * 2.0 - 1.0
				ang = frac * 1.25
				lx = math.sin(ang) * snout_rx * (0.92 - 0.08 * row_idx)
				ly = -math.cos(ang * 0.55) * (snout_ryv + mouth_gape * 0.45)
				lz = 0.012 - 0.028 * (frac * frac) + z_shift
				add_curved_tooth_bmesh(
					bm,
					base_pos=(lx, ly, lz),
					direction=(-lx * 0.8, 0.85, -0.35),
					curve_vec=(0.0, 0.003, -0.009),
					base_radius=0.0048 * r_scale,
					length=0.026 * r_scale,
					mat_idx=3,
				)
		# Fleshy dermal skin fringes around the monkfish jawline
		for flap_i in range(8):
			frac = (float(flap_i) / 7.0) * 2.0 - 1.0
			if abs(frac) < 0.15:
				continue
			fx = frac * snout_rx * 1.05
			fy = -snout_ryv * 0.85
			fz = -0.02 - 0.08 * (frac * frac)
			build_pleated_fin_bmesh(
				bm,
				origin=(fx, fy, fz),
				span_vec=(math.copysign(0.028, frac), -0.022, -0.008),
				length_vec=(0.0, -0.008, -0.032),
				thickness=0.003,
				num_rays=3,
				span_steps=4,
				mat_idx=1,
				scallop_depth=0.35,
			)
	else:
		# Subtle conical jaw teeth on standard predatory fish (Cod, Pollock, Rockfish, Halibut, Grenadier)
		for t_i in range(6):
			frac = (float(t_i) / 5.0) * 2.0 - 1.0
			if abs(frac) < 0.12:
				continue
			lx = frac * snout_rx * 0.68
			ly = -(snout_ryv + mouth_gape * 0.35)
			lz = 0.002 - 0.012 * (frac * frac)
			add_curved_tooth_bmesh(
				bm,
				base_pos=(lx, ly, lz),
				direction=(0.0, 0.92, 0.18),
				curve_vec=(0.0, 0.0, -0.003),
				base_radius=0.0024,
				length=0.011,
				mat_idx=3,
			)

	# 4. Build All Pleated Bony Fin-Ray Structures (Dorsals, Anal, Pectorals, Pelvics, and Caudal Tail)
	spiny_species = species_id in ("rockfish", "pollock", "cod", "monkfish")
	for fin_idx, (fin_loc, fin_scale, fin_rot) in enumerate(spec.get("dorsal_fins", [])):
		fx, fy, fz = fin_loc
		sx, sy, sz = fin_scale
		is_dorsal = (fy >= 0.0)
		u_fin = clamp01(abs(fz - z_start) / body_length)
		fin_wave_x = serpentine_amp * math.sin(u_fin * 2.15 * math.pi - 0.35) * (u_fin ** 0.75)

		span_y = (sy * 1.45) if is_dorsal else (-sy * 1.35)
		length_z = -sz * 1.85
		num_rays = max(7, min(18, int(abs(length_z) * 42.0)))

		build_pleated_fin_bmesh(
			bm,
			origin=(fx + fin_wave_x, fy * 0.86, fz),
			span_vec=(0.0, span_y, -0.035 * abs(span_y)),
			length_vec=(0.0, 0.0, length_z),
			thickness=max(0.004, sx * 0.75),
			num_rays=num_rays,
			span_steps=7,
			mat_idx=1,
			scallop_depth=0.18 if (spiny_species and fin_idx == 0) else 0.12,
			spiny_leading=(spiny_species and is_dorsal and fin_idx == 0),
		)

	# Sharp Protruding Dorsal Spines (Rockfish, Pollock, Cod, Monkfish) — exaggerated angular silhouette
	for sp_loc, sp_rad, sp_depth, sp_rot in spec.get("spines", []):
		u_sp = clamp01(abs(sp_loc[2] - z_start) / body_length)
		sp_wave_x = serpentine_amp * math.sin(u_sp * 2.15 * math.pi - 0.35) * (u_sp ** 0.75)
		add_curved_tooth_bmesh(
			bm,
			base_pos=(sp_loc[0] + sp_wave_x, sp_loc[1] * 0.76, sp_loc[2]),
			direction=(0.0, 0.90, -0.44),
			curve_vec=(0.0, -0.010, -0.022),
			base_radius=sp_rad * 1.15,
			length=sp_depth * 1.38,
			mat_idx=1,
		)

	# Left & Right Ribbed Pectoral Fins + Ventral Pelvic Fins
	pec_cfg = spec.get("pectoral_fin", ((0.11, -0.02, -0.22), (0.08, 0.010, 0.06), (18.0, 36.0)))
	pec_loc, pec_scale, pec_angles = pec_cfg
	u_pec = clamp01(abs(pec_loc[2] - z_start) / body_length)
	pec_wave_x = serpentine_amp * math.sin(u_pec * 2.15 * math.pi - 0.35) * (u_pec ** 0.75)

	for sx_sign in (-1.0, 1.0):
		build_pleated_fin_bmesh(
			bm,
			origin=(sx_sign * pec_loc[0] * 0.88 + pec_wave_x, pec_loc[1], pec_loc[2]),
			span_vec=(sx_sign * pec_scale[0] * 1.35, -pec_scale[0] * 0.42, -pec_scale[2] * 0.85),
			length_vec=(0.0, -pec_scale[2] * 0.35, -pec_scale[2] * 1.45),
			thickness=max(0.0035, pec_scale[1] * 0.65),
			num_rays=9,
			span_steps=6,
			mat_idx=1,
			scallop_depth=0.14,
			profile_taper=(0.95, 0.55),
		)
		# Paired Ventral Pelvic Fins slightly below and behind the pectoral base
		if not flatfish_mode:
			build_pleated_fin_bmesh(
				bm,
				origin=(sx_sign * pec_loc[0] * 0.42 + pec_wave_x, - abs(pec_loc[0]) * 0.82, pec_loc[2] - 0.04),
				span_vec=(sx_sign * pec_scale[0] * 0.55, -pec_scale[0] * 0.68, -pec_scale[2] * 0.55),
				length_vec=(0.0, 0.0, -pec_scale[2] * 0.95),
				thickness=0.003,
				num_rays=6,
				span_steps=5,
				mat_idx=1,
				scallop_depth=0.15,
			)

	# Forked / Lunate / Rounded Ribbed Caudal Tail Fin
	ped_wave_x = serpentine_amp * math.sin(0.95 * 2.15 * math.pi - 0.35)
	build_caudal_tail_bmesh(
		bm,
		peduncle_z=peduncle_z + 0.015,
		tail_end_z=tail_tip_station[0],
		peduncle_rx=peduncle_station[1],
		peduncle_ry=peduncle_station[2],
		tail_span_y=max(0.045, tail_tip_station[2] * 1.08),
		fork_depth=tail_fork_depth,
		serpentine_x=ped_wave_x,
		flatfish_mode=flatfish_mode,
		mat_idx=1,
	)

	# 5. Two-Layer Anatomical Eyes (Recessed Pupil + Metallic Iris Ring + Glossy Cornea Dome)
	u_eye = clamp01(abs(eye_pos[2] - z_start) / body_length)
	eye_wave_x = serpentine_amp * math.sin(u_eye * 2.15 * math.pi - 0.35) * (u_eye ** 0.75)
	if flatfish_mode:
		# Both migrated eyes on the right (+X) dark ocular side of the Halibut
		for ey_off, ez_off in ((0.032, 0.0), (-0.018, -0.022)):
			add_two_layer_anatomical_eye_bmesh(
				bm,
				center=(eye_pos[0] + eye_wave_x, eye_pos[1] + ey_off, eye_pos[2] + ez_off),
				outward_normal=(0.96, 0.18, 0.12),
				radius=eye_radius,
				iris_mat_idx=4,
				cornea_mat_idx=5,
			)
	else:
		for sx_sign in (-1.0, 1.0):
			add_two_layer_anatomical_eye_bmesh(
				bm,
				center=(sx_sign * eye_pos[0] + eye_wave_x, eye_pos[1], eye_pos[2]),
				outward_normal=(sx_sign * 0.90, 0.28, 0.22),
				radius=eye_radius,
				iris_mat_idx=4,
				cornea_mat_idx=5,
			)

	# 6. 3D Barbels, Head Plumes, Illicium Stalk & Multi-Lobed Bioluminescent Esca Bulb
	for fil_pts, fil_rad, use_accent in spec.get("curve_filaments", []):
		f_mat = 6 if use_accent else 1
		# Loft tapered tubular filament along control points
		interp_pts: List[Vector] = []
		for idx in range(len(fil_pts) - 1):
			p0 = Vector(fil_pts[idx])
			p1 = Vector(fil_pts[idx + 1])
			steps = 5
			for s_i in range(steps if idx < len(fil_pts) - 2 else steps + 1):
				t = float(s_i) / float(steps)
				interp_pts.append(p0.lerp(p1, t))

		f_segs = 8
		f_rings: List[List[bmesh.types.BMVert]] = []
		for p_i, pt in enumerate(interp_pts):
			frac = float(p_i) / float(max(1, len(interp_pts) - 1))
			rad = max(0.0008, fil_rad * (1.0 - 0.65 * frac))
			tang = (interp_pts[min(len(interp_pts) - 1, p_i + 1)] - interp_pts[max(0, p_i - 1)]).normalized()
			ref = Vector((1.0, 0.0, 0.0)) if abs(tang.x) < 0.9 else Vector((0.0, 1.0, 0.0))
			b1 = tang.cross(ref).normalized()
			b2 = tang.cross(b1).normalized()
			ring: List[bmesh.types.BMVert] = []
			for s in range(f_segs):
				ang = (2.0 * math.pi * float(s)) / float(f_segs)
				ring.append(bm.verts.new(pt + (b1 * math.cos(ang) + b2 * math.sin(ang)) * rad))
			f_rings.append(ring)

		for p_i in range(len(f_rings) - 1):
			for s in range(f_segs):
				ns = (s + 1) % f_segs
				try:
					f = bm.faces.new((f_rings[p_i][s], f_rings[p_i][ns], f_rings[p_i + 1][ns], f_rings[p_i + 1][s]))
					f.material_index = f_mat
				except ValueError:
					pass

	if "esca_bulb" in spec:
		bulb_loc, bulb_rad = spec["esca_bulb"]
		bx, by, bz = bulb_loc
		# Multi-lobed bioluminescent esca organ with 3 glowing lateral tendrils
		u_segs = 16
		v_rings = 12
		esca_rings: List[List[bmesh.types.BMVert]] = []
		for r in range(v_rings):
			phi = math.pi * (float(r) / float(v_rings - 1))
			sp = math.sin(phi)
			cp = math.cos(phi)
			ring = []
			for s in range(u_segs):
				theta = (2.0 * math.pi * float(s)) / float(u_segs)
				# Multi-lobed organic modulation
				lobe = 1.0 + 0.24 * math.sin(theta * 3.0) * (sp ** 1.5) + 0.14 * math.cos(phi * 4.0)
				rad = max(0.0005, bulb_rad * lobe)
				px = bx + rad * sp * math.cos(theta)
				py = by + rad * sp * math.sin(theta)
				pz = bz + rad * 1.25 * cp
				ring.append(bm.verts.new((px, py, pz)))
			esca_rings.append(ring)

		for r in range(v_rings - 1):
			for s in range(u_segs):
				ns = (s + 1) % u_segs
				try:
					f = bm.faces.new((esca_rings[r][s], esca_rings[r + 1][s], esca_rings[r + 1][ns], esca_rings[r][ns]))
					f.material_index = 6  # Slot 6 = BiolumEscaLure (Emission Strength = 12.0)
				except ValueError:
					pass

	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

	fish_mesh = bpy.data.meshes.new(f"{species_id}_Mesh")
	bm.to_mesh(fish_mesh)
	bm.free()

	fish_obj = bpy.data.objects.new(f"Fish_{species_id}", fish_mesh)
	bpy.context.collection.objects.link(fish_obj)
	bpy.context.view_layer.objects.active = fish_obj
	fish_obj.select_set(True)

	# Assign all 7 PBR material slots
	fish_obj.data.materials.append(mat_body)        # 0
	fish_obj.data.materials.append(mat_fins)        # 1
	fish_obj.data.materials.append(mat_oral_gill)   # 2
	fish_obj.data.materials.append(mat_teeth)       # 3
	fish_obj.data.materials.append(mat_eye_iris)    # 4
	fish_obj.data.materials.append(mat_eye_cornea)  # 5
	fish_obj.data.materials.append(mat_esca)        # 6

	# Stylized Chiseled Planar Bevel Shading: preserve crisp planar facets & bevel creases instead of noisy Voronoi bumps
	bevel_mod = fish_obj.modifiers.new(name="ChiseledBevel", type="BEVEL")
	bevel_mod.width = 0.0022
	bevel_mod.segments = 1
	bevel_mod.limit_method = "ANGLE"
	bevel_mod.angle_limit = math.radians(28.0)

	for mod in list(fish_obj.modifiers):
		bpy.ops.object.modifier_apply(modifier=mod.name)

	# Mark edges with dihedral angle > 22 degrees as sharp so planar facets catch crisp light bands
	bm_sharp = bmesh.new()
	bm_sharp.from_mesh(fish_obj.data)
	for poly in bm_sharp.faces:
		poly.smooth = True
	for edge in bm_sharp.edges:
		if len(edge.link_faces) == 2:
			ang = edge.calc_face_angle(0.0)
			if ang > math.radians(22.0):
				edge.smooth = False
	bm_sharp.to_mesh(fish_obj.data)
	bm_sharp.free()

	# Bake high-resolution biological + cavity ink-wash vertex colors (`Col` attribute)
	paint_fish_vertex_colors(fish_obj.data, spec)

	bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
	bpy.ops.object.origin_set(type="ORIGIN_CURSOR")

	tri_count = sum(max(0, len(p.vertices) - 2) for p in fish_obj.data.polygons)

	os.makedirs(os.path.dirname(out_glb_path), exist_ok=True)
	bpy.ops.export_scene.gltf(
		filepath=out_glb_path,
		export_format="GLB",
		export_apply=True,
		export_yup=True,
		export_attributes=True,
		export_all_vertex_colors=True,
	)
	print(f"Exported {out_glb_path} ({tri_count} triangles, {len(fish_obj.data.vertices)} vertices)")


def get_12_species_specs() -> List[Dict]:
	return [
		# 1. Atlantic Mackerel — Streamlined torpedo body, iridescent blue-green tiger stripes, deeply forked tail
		{
			"id": "mackerel",
			"dorsal_color": (0.04, 0.26, 0.32, 1.0),
			"belly_color": (0.80, 0.85, 0.90, 1.0),
			"fin_color": (0.12, 0.24, 0.28, 1.0),
			"accent_color": (0.015, 0.06, 0.12, 1.0),
			"eye_color": (0.78, 0.82, 0.65, 1.0),
			"metallic": 0.50,
			"mouth_gape": 0.018,
			"jaw_underbite": 0.012,
			"tail_fork_depth": 0.068,
			"serpentine_amp": 0.020,
			"stations": [
				(0.00, 0.018, 0.020, 0.018),
				(-0.07, 0.048, 0.055, 0.050),
				(-0.18, 0.068, 0.082, 0.078),
				(-0.32, 0.074, 0.088, 0.085),
				(-0.48, 0.058, 0.072, 0.068),
				(-0.62, 0.032, 0.042, 0.040),
				(-0.72, 0.014, 0.022, 0.022),
				(-0.84, 0.006, 0.115, 0.115),
			],
			"dorsal_fins": [
				((0.0, 0.092, -0.26), (0.008, 0.058, 0.085), (0.0, 0.0, 0.0)),
				((0.0, 0.072, -0.50), (0.007, 0.042, 0.065), (0.0, 0.0, 0.0)),
				((0.0, -0.070, -0.52), (0.007, 0.040, 0.060), (0.0, 0.0, 0.0)),
			],
			"pectoral_fin": ((0.068, -0.01, -0.17), (0.068, 0.008, 0.045), (16.0, 38.0)),
			"eye_radius": 0.014,
			"eye_pos": (0.042, 0.018, -0.075),
		},
		# 2. Saithe Pollock — Sleek dark-olive dorsal back, pale lateral line, three dorsal fins
		{
			"id": "pollock",
			"dorsal_color": (0.10, 0.18, 0.13, 1.0),
			"belly_color": (0.72, 0.76, 0.74, 1.0),
			"fin_color": (0.14, 0.20, 0.15, 1.0),
			"accent_color": (0.82, 0.85, 0.76, 1.0),
			"eye_color": (0.82, 0.70, 0.32, 1.0),
			"metallic": 0.35,
			"mouth_gape": 0.024,
			"jaw_underbite": 0.022,
			"tail_fork_depth": 0.054,
			"serpentine_amp": 0.022,
			"stations": [
				(0.00, 0.026, 0.028, 0.032),
				(-0.09, 0.068, 0.078, 0.075),
				(-0.22, 0.098, 0.118, 0.112),
				(-0.38, 0.108, 0.135, 0.128),
				(-0.56, 0.088, 0.112, 0.102),
				(-0.74, 0.055, 0.072, 0.068),
				(-0.88, 0.024, 0.038, 0.038),
				(-1.02, 0.008, 0.145, 0.145),
			],
			"dorsal_fins": [
				((0.0, 0.138, -0.28), (0.010, 0.068, 0.085), (0.0, 0.0, 0.0)),
				((0.0, 0.125, -0.50), (0.009, 0.062, 0.095), (0.0, 0.0, 0.0)),
				((0.0, 0.088, -0.72), (0.008, 0.050, 0.072), (0.0, 0.0, 0.0)),
				((0.0, -0.112, -0.52), (0.009, 0.054, 0.085), (0.0, 0.0, 0.0)),
				((0.0, -0.078, -0.73), (0.008, 0.044, 0.068), (0.0, 0.0, 0.0)),
			],
			"pectoral_fin": ((0.098, -0.02, -0.21), (0.082, 0.010, 0.058), (18.0, 35.0)),
			"eye_radius": 0.017,
			"eye_pos": (0.058, 0.028, -0.088),
		},
		# 3. Atlantic Cod — Heavy-bellied mottled olive-brown body, chin barbel, broad pectoral fins
		{
			"id": "cod",
			"dorsal_color": (0.18, 0.20, 0.11, 1.0),
			"belly_color": (0.68, 0.70, 0.62, 1.0),
			"fin_color": (0.20, 0.22, 0.14, 1.0),
			"accent_color": (0.86, 0.84, 0.72, 1.0),
			"eye_color": (0.85, 0.68, 0.25, 1.0),
			"metallic": 0.30,
			"mouth_gape": 0.032,
			"jaw_underbite": 0.014,
			"tail_fork_depth": 0.022,
			"serpentine_amp": 0.024,
			"stations": [
				(0.00, 0.036, 0.040, 0.034),
				(-0.09, 0.086, 0.094, 0.082),
				(-0.22, 0.124, 0.142, 0.138),
				(-0.38, 0.142, 0.172, 0.168),
				(-0.56, 0.118, 0.146, 0.138),
				(-0.74, 0.078, 0.102, 0.092),
				(-0.90, 0.042, 0.058, 0.052),
				(-0.98, 0.022, 0.046, 0.046),
				(-1.14, 0.009, 0.168, 0.168),
			],
			"dorsal_fins": [
				((0.0, 0.168, -0.30), (0.012, 0.075, 0.095), (0.0, 0.0, 0.0)),
				((0.0, 0.152, -0.54), (0.011, 0.070, 0.110), (0.0, 0.0, 0.0)),
				((0.0, 0.106, -0.78), (0.010, 0.058, 0.082), (0.0, 0.0, 0.0)),
				((0.0, -0.142, -0.56), (0.010, 0.060, 0.095), (0.0, 0.0, 0.0)),
				((0.0, -0.095, -0.79), (0.009, 0.050, 0.075), (0.0, 0.0, 0.0)),
			],
			"pectoral_fin": ((0.135, -0.03, -0.24), (0.098, 0.012, 0.075), (20.0, 38.0)),
			"eye_radius": 0.019,
			"eye_pos": (0.074, 0.038, -0.095),
			"curve_filaments": [
				([(0.0, -0.042, 0.005), (0.0, -0.082, -0.018), (0.0, -0.118, -0.055)], 0.0055, False),
			],
		},
		# 4. Redband Rockfish — Deep-bodied spiny crimson-orange reef perch, large eyes, sharp dorsal spines
		{
			"id": "rockfish",
			"dorsal_color": (0.72, 0.15, 0.09, 1.0),
			"belly_color": (0.88, 0.46, 0.22, 1.0),
			"fin_color": (0.58, 0.12, 0.07, 1.0),
			"accent_color": (0.24, 0.05, 0.04, 1.0),
			"eye_color": (0.95, 0.78, 0.22, 1.0),
			"metallic": 0.28,
			"mouth_gape": 0.034,
			"jaw_underbite": 0.020,
			"tail_fork_depth": 0.016,
			"serpentine_amp": 0.020,
			"stations": [
				(0.00, 0.032, 0.038, 0.036),
				(-0.08, 0.078, 0.105, 0.092),
				(-0.20, 0.112, 0.175, 0.148),
				(-0.34, 0.118, 0.192, 0.158),
				(-0.50, 0.088, 0.142, 0.118),
				(-0.64, 0.048, 0.078, 0.068),
				(-0.74, 0.024, 0.048, 0.048),
				(-0.88, 0.008, 0.138, 0.138),
			],
			"dorsal_fins": [
				((0.0, 0.185, -0.32), (0.012, 0.085, 0.165), (0.0, 0.0, 0.0)),
				((0.0, -0.135, -0.52), (0.011, 0.070, 0.090), (0.0, 0.0, 0.0)),
			],
			"spines": [
				((0.0, 0.225, -0.18), 0.009, 0.085, (math.radians(-68.0), 0.0, 0.0)),
				((0.0, 0.242, -0.25), 0.010, 0.095, (math.radians(-72.0), 0.0, 0.0)),
				((0.0, 0.245, -0.33), 0.010, 0.095, (math.radians(-75.0), 0.0, 0.0)),
				((0.0, 0.232, -0.41), 0.009, 0.082, (math.radians(-78.0), 0.0, 0.0)),
				((0.0, 0.205, -0.49), 0.008, 0.070, (math.radians(-80.0), 0.0, 0.0)),
			],
			"pectoral_fin": ((0.112, -0.02, -0.22), (0.108, 0.012, 0.085), (22.0, 42.0)),
			"eye_radius": 0.024,
			"eye_pos": (0.068, 0.045, -0.082),
		},
		# 5. Silver Hake — Elongated metallic slate-silver predator, needle fangs, long continuous second dorsal fin
		{
			"id": "hake",
			"dorsal_color": (0.24, 0.29, 0.34, 1.0),
			"belly_color": (0.76, 0.80, 0.85, 1.0),
			"fin_color": (0.18, 0.22, 0.26, 1.0),
			"accent_color": (0.10, 0.13, 0.17, 1.0),
			"eye_color": (0.85, 0.82, 0.58, 1.0),
			"metallic": 0.48,
			"dentition": "hake",
			"fang_length": 0.022,
			"fang_radius": 0.0032,
			"mouth_gape": 0.030,
			"jaw_underbite": 0.026,
			"tail_fork_depth": 0.035,
			"serpentine_amp": 0.026,
			"stations": [
				(0.00, 0.024, 0.026, 0.030),
				(-0.10, 0.062, 0.068, 0.066),
				(-0.24, 0.085, 0.102, 0.096),
				(-0.44, 0.092, 0.112, 0.104),
				(-0.68, 0.076, 0.094, 0.088),
				(-0.90, 0.048, 0.062, 0.058),
				(-1.04, 0.022, 0.036, 0.036),
				(-1.18, 0.008, 0.132, 0.132),
			],
			"dorsal_fins": [
				((0.0, 0.112, -0.26), (0.009, 0.068, 0.065), (0.0, 0.0, 0.0)),
				((0.0, 0.104, -0.66), (0.009, 0.058, 0.240), (0.0, 0.0, 0.0)),
				((0.0, -0.098, -0.68), (0.009, 0.052, 0.220), (0.0, 0.0, 0.0)),
			],
			"pectoral_fin": ((0.084, -0.02, -0.24), (0.088, 0.009, 0.055), (16.0, 36.0)),
			"eye_radius": 0.018,
			"eye_pos": (0.054, 0.026, -0.095),
		},
		# 6. Spotted Wolffish — Thick muscular mottled slate-violet eel-like body, blunt armored head, canine tusks
		{
			"id": "wolffish",
			"dorsal_color": (0.24, 0.20, 0.30, 1.0),
			"belly_color": (0.48, 0.42, 0.52, 1.0),
			"fin_color": (0.22, 0.18, 0.28, 1.0),
			"accent_color": (0.08, 0.06, 0.11, 1.0),
			"eye_color": (0.88, 0.65, 0.20, 1.0),
			"metallic": 0.26,
			"dentition": "wolffish",
			"mouth_gape": 0.038,
			"jaw_underbite": 0.016,
			"serpentine_amp": 0.034,
			"tail_fork_depth": 0.0,
			"stations": [
				(0.00, 0.055, 0.062, 0.058),
				(-0.08, 0.112, 0.128, 0.118),
				(-0.20, 0.128, 0.148, 0.136),
				(-0.42, 0.118, 0.138, 0.124),
				(-0.68, 0.096, 0.118, 0.105),
				(-0.92, 0.068, 0.088, 0.078),
				(-1.12, 0.036, 0.055, 0.050),
				(-1.24, 0.012, 0.088, 0.088),
			],
			"dorsal_fins": [
				((0.0, 0.135, -0.64), (0.012, 0.070, 0.460), (0.0, 0.0, 0.0)),
				((0.0, -0.112, -0.78), (0.010, 0.054, 0.320), (0.0, 0.0, 0.0)),
			],
			"pectoral_fin": ((0.125, -0.02, -0.22), (0.118, 0.014, 0.098), (24.0, 44.0)),
			"eye_radius": 0.019,
			"eye_pos": (0.088, 0.062, -0.072),
		},
		# 7. Blackbellied Monkfish — Wide flattened frog-like head and cavernous jaw with double rows of teeth & skin flaps
		{
			"id": "monkfish",
			"dorsal_color": (0.18, 0.14, 0.10, 1.0),
			"belly_color": (0.28, 0.22, 0.18, 1.0),
			"fin_color": (0.12, 0.09, 0.07, 1.0),
			"accent_color": (0.38, 0.28, 0.20, 1.0),
			"eye_color": (0.72, 0.85, 0.42, 1.0),
			"metallic": 0.25,
			"dentition": "monkfish",
			"mouth_gape": 0.048,
			"jaw_underbite": 0.042,
			"tail_fork_depth": 0.005,
			"serpentine_amp": 0.024,
			"stations": [
				(0.00, 0.145, 0.052, 0.068),
				(-0.12, 0.245, 0.088, 0.095),
				(-0.28, 0.268, 0.098, 0.102),
				(-0.46, 0.185, 0.082, 0.085),
				(-0.64, 0.105, 0.068, 0.068),
				(-0.82, 0.058, 0.052, 0.052),
				(-0.96, 0.028, 0.038, 0.038),
				(-1.10, 0.010, 0.115, 0.115),
			],
			"dorsal_fins": [
				((0.0, 0.068, -0.74), (0.010, 0.060, 0.140), (0.0, 0.0, 0.0)),
				((0.0, -0.062, -0.76), (0.010, 0.050, 0.120), (0.0, 0.0, 0.0)),
			],
			"spines": [
				((0.0, 0.105, -0.22), 0.006, 0.075, (math.radians(-62.0), 0.0, 0.0)),
				((0.0, 0.102, -0.34), 0.006, 0.068, (math.radians(-68.0), 0.0, 0.0)),
			],
			"curve_filaments": [
				([(0.0, 0.058, -0.06), (0.0, 0.135, 0.02), (0.0, 0.165, 0.09)], 0.0045, True),
			],
			"pectoral_fin": ((0.255, -0.02, -0.34), (0.138, 0.016, 0.108), (12.0, 28.0)),
			"eye_radius": 0.018,
			"eye_pos": (0.095, 0.078, -0.12),
		},
		# 8. Atlantic Halibut — Broad diamond-shaped giant flatfish, mottled chocolate/charcoal top side, pearly white underside
		{
			"id": "halibut",
			"dorsal_color": (0.14, 0.12, 0.09, 1.0),
			"belly_color": (0.90, 0.92, 0.89, 1.0),
			"fin_color": (0.16, 0.15, 0.12, 1.0),
			"accent_color": (0.26, 0.24, 0.18, 1.0),
			"eye_color": (0.82, 0.72, 0.30, 1.0),
			"metallic": 0.28,
			"flatfish_mode": True,
			"mouth_gape": 0.022,
			"jaw_underbite": 0.014,
			"tail_fork_depth": 0.028,
			"serpentine_amp": 0.018,
			"stations": [
				(0.00, 0.022, 0.042, 0.042),
				(-0.12, 0.042, 0.125, 0.125),
				(-0.30, 0.058, 0.265, 0.265),
				(-0.52, 0.064, 0.345, 0.345),
				(-0.76, 0.052, 0.245, 0.245),
				(-0.98, 0.036, 0.125, 0.125),
				(-1.12, 0.020, 0.058, 0.058),
				(-1.28, 0.009, 0.195, 0.195),
			],
			"dorsal_fins": [
				((0.0, 0.325, -0.56), (0.008, 0.078, 0.380), (0.0, 0.0, 0.0)),
				((0.0, -0.325, -0.58), (0.008, 0.078, 0.360), (0.0, 0.0, 0.0)),
			],
			"pectoral_fin": ((0.058, 0.02, -0.26), (0.072, 0.009, 0.060), (15.0, 48.0)),
			"eye_radius": 0.018,
			"eye_pos": (0.044, 0.025, -0.105),
		},
		# 9. Black Scabbardfish — Long ribbon-compressed obsidian-black metallic body, fang-filled jaws
		{
			"id": "scabbardfish",
			"dorsal_color": (0.04, 0.045, 0.06, 1.0),
			"belly_color": (0.10, 0.11, 0.14, 1.0),
			"fin_color": (0.06, 0.06, 0.08, 1.0),
			"accent_color": (0.36, 0.28, 0.68, 1.0),
			"eye_color": (0.92, 0.76, 0.24, 1.0),
			"eye_emission": (0.85, 0.68, 0.22, 1.0),
			"eye_emission_strength": 1.8,
			"metallic": 0.55,
			"dentition": "scabbard",
			"fang_length": 0.030,
			"fang_radius": 0.0038,
			"mouth_gape": 0.032,
			"jaw_underbite": 0.034,
			"serpentine_amp": 0.036,
			"tail_fork_depth": 0.048,
			"stations": [
				(0.00, 0.014, 0.028, 0.032),
				(-0.14, 0.028, 0.068, 0.064),
				(-0.34, 0.034, 0.086, 0.082),
				(-0.62, 0.032, 0.082, 0.078),
				(-0.92, 0.026, 0.068, 0.064),
				(-1.18, 0.016, 0.044, 0.042),
				(-1.34, 0.008, 0.022, 0.022),
				(-1.46, 0.004, 0.092, 0.092),
			],
			"dorsal_fins": [
				((0.0, 0.086, -0.74), (0.006, 0.052, 0.560), (0.0, 0.0, 0.0)),
			],
			"pectoral_fin": ((0.034, -0.02, -0.26), (0.065, 0.007, 0.048), (18.0, 38.0)),
			"eye_radius": 0.022,
			"eye_pos": (0.028, 0.022, -0.115),
		},
		# 10. Abyssal Grenadier — Large armored head with glowing pale-green abyssal eyes, tapering to a long rat-tail
		{
			"id": "grenadier",
			"dorsal_color": (0.16, 0.19, 0.22, 1.0),
			"belly_color": (0.08, 0.10, 0.13, 1.0),
			"fin_color": (0.12, 0.15, 0.18, 1.0),
			"accent_color": (0.28, 0.34, 0.38, 1.0),
			"eye_color": (0.35, 0.96, 0.58, 1.0),
			"eye_emission": (0.28, 0.95, 0.52, 1.0),
			"eye_emission_strength": 3.4,
			"metallic": 0.36,
			"scale_noise_size": 0.036,
			"scale_disp_strength": 0.0042,
			"mouth_gape": 0.026,
			"jaw_underbite": 0.012,
			"serpentine_amp": 0.038,
			"tail_fork_depth": 0.0,
			"stations": [
				(0.00, 0.042, 0.048, 0.032),
				(-0.10, 0.095, 0.115, 0.088),
				(-0.24, 0.112, 0.138, 0.112),
				(-0.42, 0.082, 0.105, 0.084),
				(-0.66, 0.048, 0.065, 0.052),
				(-0.92, 0.024, 0.036, 0.030),
				(-1.18, 0.010, 0.018, 0.016),
				(-1.38, 0.003, 0.008, 0.008),
			],
			"dorsal_fins": [
				((0.0, 0.148, -0.28), (0.010, 0.098, 0.065), (0.0, 0.0, 0.0)),
				((0.0, -0.055, -0.82), (0.007, 0.042, 0.420), (0.0, 0.0, 0.0)),
			],
			"pectoral_fin": ((0.105, -0.02, -0.25), (0.090, 0.010, 0.060), (20.0, 40.0)),
			"eye_radius": 0.030,
			"eye_pos": (0.082, 0.042, -0.105),
		},
		# 11. Regal Oarfish — Long serpentine mirror-chrome ribbon body with vivid crimson dorsal crest & head plumes
		{
			"id": "oarfish",
			"dorsal_color": (0.78, 0.84, 0.90, 1.0),
			"belly_color": (0.88, 0.92, 0.96, 1.0),
			"fin_color": (0.90, 0.08, 0.12, 1.0),
			"fin_emission": (0.75, 0.06, 0.10, 1.0),
			"fin_emission_strength": 1.6,
			"accent_color": (0.95, 0.10, 0.14, 1.0),
			"lure_emission": (0.92, 0.08, 0.12, 1.0),
			"lure_emission_strength": 2.4,
			"eye_color": (0.88, 0.90, 0.95, 1.0),
			"metallic": 0.55,
			"mouth_gape": 0.020,
			"jaw_underbite": 0.010,
			"serpentine_amp": 0.058,
			"tail_fork_depth": 0.0,
			"stations": [
				(0.00, 0.022, 0.058, 0.048),
				(-0.12, 0.036, 0.115, 0.095),
				(-0.36, 0.038, 0.128, 0.105),
				(-0.68, 0.034, 0.118, 0.098),
				(-1.02, 0.028, 0.098, 0.082),
				(-1.34, 0.020, 0.074, 0.062),
				(-1.60, 0.012, 0.045, 0.038),
				(-1.78, 0.005, 0.020, 0.018),
			],
			"dorsal_fins": [
				((0.0, 0.115, -0.88), (0.008, 0.058, 0.780), (0.0, 0.0, 0.0)),
			],
			"curve_filaments": [
				([(0.0, 0.065, -0.04), (0.02, 0.21, 0.05), (0.04, 0.34, -0.02)], 0.0065, True),
				([(0.0, 0.082, -0.08), (-0.02, 0.24, 0.01), (-0.04, 0.38, -0.08)], 0.0060, True),
				([(0.0, 0.095, -0.12), (0.01, 0.22, -0.06), (0.02, 0.32, -0.15)], 0.0055, True),
			],
			"pectoral_fin": ((0.038, -0.03, -0.20), (0.062, 0.008, 0.045), (16.0, 34.0)),
			"eye_radius": 0.021,
			"eye_pos": (0.034, 0.032, -0.085),
		},
		# 12. Void-Lantern Angler — Bulbous obsidian-charcoal body, cavernous maw with long fangs, multi-lobed glowing esca bulb
		{
			"id": "angler",
			"dorsal_color": (0.03, 0.035, 0.05, 1.0),
			"belly_color": (0.05, 0.045, 0.07, 1.0),
			"fin_color": (0.05, 0.05, 0.08, 1.0),
			"accent_color": (0.25, 0.96, 0.88, 1.0),
			"lure_emission": (0.22, 0.96, 0.86, 1.0),
			"lure_emission_strength": 12.0,
			"eye_color": (0.75, 0.95, 1.0, 1.0),
			"eye_emission": (0.45, 0.85, 0.98, 1.0),
			"eye_emission_strength": 2.6,
			"metallic": 0.28,
			"dentition": "angler",
			"fang_length": 0.048,
			"fang_radius": 0.0052,
			"mouth_gape": 0.055,
			"jaw_underbite": 0.056,
			"tail_fork_depth": 0.008,
			"serpentine_amp": 0.022,
			"stations": [
				(0.00, 0.115, 0.095, 0.125),
				(-0.12, 0.195, 0.185, 0.210),
				(-0.28, 0.225, 0.215, 0.235),
				(-0.46, 0.175, 0.175, 0.185),
				(-0.62, 0.095, 0.105, 0.105),
				(-0.76, 0.045, 0.058, 0.058),
				(-0.88, 0.014, 0.135, 0.135),
			],
			"dorsal_fins": [
				((0.0, 0.125, -0.62), (0.010, 0.072, 0.110), (0.0, 0.0, 0.0)),
				((0.0, -0.115, -0.64), (0.010, 0.062, 0.095), (0.0, 0.0, 0.0)),
			],
			"curve_filaments": [
				(
					[
						(0.0, 0.12, -0.08),
						(0.0, 0.24, 0.04),
						(0.0, 0.28, 0.14),
						(0.0, 0.20, 0.20),
					],
					0.0075,
					False,
				),
			],
			"esca_bulb": ((0.0, 0.19, 0.21), 0.034),
			"pectoral_fin": ((0.205, -0.03, -0.32), (0.108, 0.016, 0.088), (22.0, 38.0)),
			"eye_radius": 0.017,
			"eye_pos": (0.105, 0.082, -0.115),
		},
	]


def main() -> None:
	project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
	fish_dir = os.path.join(project_root, "assets", "models", "fish")
	os.makedirs(fish_dir, exist_ok=True)

	specs = get_12_species_specs()
	for spec in specs:
		out_path = os.path.join(fish_dir, f"fish_{spec['id']}.glb")
		build_anatomical_fish(spec, out_path)


if __name__ == "__main__":
	main()
