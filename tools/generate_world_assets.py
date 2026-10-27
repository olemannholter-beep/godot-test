#!/usr/bin/env python3
"""
Procedural 3D World Asset, Wharf Island Settlement & Jagged Rock Formation Wavefront .obj/.mtl generator.

Generates in res://assets/models/:
  - world_materials.mtl
  - wharf_island.obj           (Starting island with timber pier, 3 slumped buildings, and 26m Lighthouse)
  - rock_razor_cluster.obj     (Shipwrecking Reef Teeth, 18m footprint, 6-15m tall angled shards)
  - rock_jagged_arch.obj       (Twisted Basalt Sea Arch & Overhang, 35m wide, 28m tall, 14m navigable channel)
  - rock_basalt_monolith.obj   (Columnar Basalt Fang Spires, 22m wide, 38m tall stepped hexagonal pillars)
  - island_large_archipelago.obj
  - island_medium_crag.obj
  - island_sea_stack.obj
"""

import math
import os
import random
from typing import Dict, List, Optional, Tuple

Vec3 = Tuple[float, float, float]

MATERIAL_ORDER: List[str] = [
	"TidalWetRock",
	"BasaltCliff",
	"SharpObsidian",
	"MossyCrag",
	"WeatheredTimber",
	"RottingWood",
	"ShackWall",
	"CorrugatedRoof",
	"RustIron",
	"DarkMetal",
	"AmberGlass",
	"LighthouseStone",
	"LighthouseBand",
	"BeaconLens",
]


def v_add(a: Vec3, b: Vec3) -> Vec3:
	return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a: Vec3, b: Vec3) -> Vec3:
	return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_scale(a: Vec3, s: float) -> Vec3:
	return (a[0] * s, a[1] * s, a[2] * s)


def v_dot(a: Vec3, b: Vec3) -> float:
	return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a: Vec3, b: Vec3) -> Vec3:
	return (
		a[1] * b[2] - a[2] * b[1],
		a[2] * b[0] - a[0] * b[2],
		a[0] * b[1] - a[1] * b[0],
	)


def v_len(a: Vec3) -> float:
	return math.sqrt(v_dot(a, a))


def v_norm(a: Vec3) -> Vec3:
	length: float = v_len(a)
	if length < 1e-9:
		return (0.0, 1.0, 0.0)
	return (a[0] / length, a[1] / length, a[2] / length)


def v_lerp(a: Vec3, b: Vec3, t: float) -> Vec3:
	return (
		a[0] + (b[0] - a[0]) * t,
		a[1] + (b[1] - a[1]) * t,
		a[2] + (b[2] - a[2]) * t,
	)


def ridge_noise(x: float, y: float, z: float, seed: int = 0) -> float:
	"""Deterministic sharp ridge/Voronoi-style fractal displacement."""
	p1: float = math.sin(x * 0.43 + z * 0.37 + float(seed) * 1.7) * math.cos(y * 0.31 - x * 0.29)
	p2: float = math.sin(x * 0.91 - z * 0.83 + y * 0.53 + float(seed) * 3.1)
	p3: float = math.cos(z * 1.47 + x * 1.13 - y * 0.79 + float(seed) * 5.3)
	r1: float = 1.0 - abs(p1)
	r2: float = 1.0 - abs(p2)
	r3: float = 1.0 - abs(p3)
	return (r1 * 0.55 + r2 * 0.30 + r3 * 0.15) * 2.0 - 1.0


class FacetedMeshBuilder:
	"""Collects indexed vertices and planar per-face normals (vn) grouped by material."""

	def __init__(self) -> None:
		self.vertices: List[Vec3] = []
		self.vertex_map: Dict[Tuple[int, int, int], int] = {}
		self.normals: List[Vec3] = []
		self.normal_map: Dict[Tuple[int, int, int], int] = {}
		self.faces_by_mat: Dict[str, List[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]]] = {
			mat: [] for mat in MATERIAL_ORDER
		}

	def _get_vertex_index(self, v: Vec3) -> int:
		key: Tuple[int, int, int] = (round(v[0] * 1000), round(v[1] * 1000), round(v[2] * 1000))
		idx: Optional[int] = self.vertex_map.get(key)
		if idx is None:
			self.vertices.append(v)
			idx = len(self.vertices)
			self.vertex_map[key] = idx
		return idx

	def _get_normal_index(self, n: Vec3) -> int:
		unit_n: Vec3 = v_norm(n)
		key: Tuple[int, int, int] = (round(unit_n[0] * 1000), round(unit_n[1] * 1000), round(unit_n[2] * 1000))
		idx: Optional[int] = self.normal_map.get(key)
		if idx is None:
			self.normals.append(unit_n)
			idx = len(self.normals)
			self.normal_map[key] = idx
		return idx

	def add_tri(
		self,
		material: str,
		p0: Vec3,
		p1: Vec3,
		p2: Vec3,
		outward_hint: Optional[Vec3] = None,
	) -> None:
		e1: Vec3 = v_sub(p1, p0)
		e2: Vec3 = v_sub(p2, p0)
		raw_cross: Vec3 = v_cross(e1, e2)
		if v_len(raw_cross) < 1e-7:
			return
		if outward_hint is not None and v_dot(raw_cross, outward_hint) < 0.0:
			p1, p2 = p2, p1
			raw_cross = v_scale(raw_cross, -1.0)

		n_idx: int = self._get_normal_index(raw_cross)
		i0: int = self._get_vertex_index(p0)
		i1: int = self._get_vertex_index(p1)
		i2: int = self._get_vertex_index(p2)
		self.faces_by_mat[material].append(((i0, n_idx), (i1, n_idx), (i2, n_idx)))

	def add_quad(
		self,
		material: str,
		p0: Vec3,
		p1: Vec3,
		p2: Vec3,
		p3: Vec3,
		outward_hint: Optional[Vec3] = None,
	) -> None:
		self.add_tri(material, p0, p1, p2, outward_hint)
		self.add_tri(material, p0, p2, p3, outward_hint)

	def add_box(
		self,
		material: str,
		center: Vec3,
		size: Vec3,
		skip_bottom: bool = False,
		skip_top: bool = False,
	) -> None:
		cx, cy, cz = center
		hx, hy, hz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
		x0, x1 = cx - hx, cx + hx
		y0, y1 = cy - hy, cy + hy
		z0, z1 = cz - hz, cz + hz

		self.add_quad(material, (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (0.0, 0.0, -1.0))
		self.add_quad(material, (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0.0, 0.0, 1.0))
		self.add_quad(material, (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (-1.0, 0.0, 0.0))
		self.add_quad(material, (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (1.0, 0.0, 0.0))
		if not skip_top:
			self.add_quad(material, (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (0.0, 1.0, 0.0))
		if not skip_bottom:
			self.add_quad(material, (x0, y0, z1), (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (0.0, -1.0, 0.0))

	def add_oriented_box(
		self,
		material: str,
		center: Vec3,
		size: Vec3,
		yaw_deg: float = 0.0,
		pitch_deg: float = 0.0,
		roll_deg: float = 0.0,
		skip_bottom: bool = False,
		skip_top: bool = False,
	) -> None:
		cx, cy, cz = center
		hx, hy, hz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
		yr: float = math.radians(yaw_deg)
		pr: float = math.radians(pitch_deg)
		rr: float = math.radians(roll_deg)
		cyaw, syaw = math.cos(yr), math.sin(yr)
		cpit, spit = math.cos(pr), math.sin(pr)
		crol, srol = math.cos(rr), math.sin(rr)

		def transform_local(lx: float, ly: float, lz: float) -> Vec3:
			# Roll around Z
			x1: float = lx * crol - ly * srol
			y1: float = lx * srol + ly * crol
			z1: float = lz
			# Pitch around X
			x2: float = x1
			y2: float = y1 * cpit - z1 * spit
			z2: float = y1 * spit + z1 * cpit
			# Yaw around Y
			x3: float = x2 * cyaw + z2 * syaw
			y3: float = y2
			z3: float = -x2 * syaw + z2 * cyaw
			return (cx + x3, cy + y3, cz + z3)

		p000: Vec3 = transform_local(-hx, -hy, -hz)
		p100: Vec3 = transform_local(hx, -hy, -hz)
		p110: Vec3 = transform_local(hx, hy, -hz)
		p010: Vec3 = transform_local(-hx, hy, -hz)
		p001: Vec3 = transform_local(-hx, -hy, hz)
		p101: Vec3 = transform_local(hx, -hy, hz)
		p111: Vec3 = transform_local(hx, hy, hz)
		p011: Vec3 = transform_local(-hx, hy, hz)

		n_front: Vec3 = v_sub(transform_local(0.0, 0.0, -1.0), center)
		n_back: Vec3 = v_sub(transform_local(0.0, 0.0, 1.0), center)
		n_left: Vec3 = v_sub(transform_local(-1.0, 0.0, 0.0), center)
		n_right: Vec3 = v_sub(transform_local(1.0, 0.0, 0.0), center)
		n_top: Vec3 = v_sub(transform_local(0.0, 1.0, 0.0), center)
		n_bot: Vec3 = v_sub(transform_local(0.0, -1.0, 0.0), center)

		self.add_quad(material, p000, p010, p110, p100, n_front)
		self.add_quad(material, p001, p101, p111, p011, n_back)
		self.add_quad(material, p001, p011, p010, p000, n_left)
		self.add_quad(material, p100, p110, p111, p101, n_right)
		if not skip_top:
			self.add_quad(material, p010, p011, p111, p110, n_top)
		if not skip_bottom:
			self.add_quad(material, p001, p000, p100, p101, n_bot)

	def add_cylinder_between(
		self,
		material: str,
		p_start: Vec3,
		p_end: Vec3,
		r_start: float,
		r_end: float,
		segments: int = 10,
		cap_start: bool = True,
		cap_end: bool = True,
	) -> None:
		axis: Vec3 = v_sub(p_end, p_start)
		if v_len(axis) < 1e-6:
			return
		axis_u: Vec3 = v_norm(axis)
		ref: Vec3 = (0.0, 0.0, 1.0) if abs(axis_u[1]) > 0.9 else (0.0, 1.0, 0.0)
		tangent: Vec3 = v_norm(v_cross(axis_u, ref))
		bitangent: Vec3 = v_norm(v_cross(axis_u, tangent))

		ring_start: List[Vec3] = []
		ring_end: List[Vec3] = []
		radial_dirs: List[Vec3] = []

		for i in range(segments):
			angle: float = (2.0 * math.pi * float(i)) / float(segments)
			ca: float = math.cos(angle)
			sa: float = math.sin(angle)
			rad_dir: Vec3 = v_norm(v_add(v_scale(tangent, ca), v_scale(bitangent, sa)))
			radial_dirs.append(rad_dir)
			ring_start.append(v_add(p_start, v_scale(rad_dir, r_start)))
			ring_end.append(v_add(p_end, v_scale(rad_dir, r_end)))

		for i in range(segments):
			ni: int = (i + 1) % segments
			mid_rad: Vec3 = v_add(radial_dirs[i], radial_dirs[ni])
			self.add_quad(material, ring_start[i], ring_end[i], ring_end[ni], ring_start[ni], mid_rad)
			if cap_start and r_start > 1e-5:
				self.add_tri(material, p_start, ring_start[ni], ring_start[i], v_scale(axis_u, -1.0))
			if cap_end and r_end > 1e-5:
				self.add_tri(material, p_end, ring_end[i], ring_end[ni], axis_u)

	def add_catenary_cable(
		self,
		material: str,
		p_start: Vec3,
		p_end: Vec3,
		sag: float,
		radius: float = 0.024,
		segments: int = 12,
		radial_sides: int = 5,
	) -> None:
		pts: List[Vec3] = []
		for i in range(segments + 1):
			t: float = float(i) / float(segments)
			base_p: Vec3 = v_lerp(p_start, p_end, t)
			# Catenary / parabolic droop with slight wind sway in +X
			droop: float = 4.0 * t * (1.0 - t) * sag
			sway_x: float = math.sin(t * math.pi) * sag * 0.14
			pts.append((base_p[0] + sway_x, base_p[1] - droop, base_p[2]))
		for i in range(segments):
			self.add_cylinder_between(
				material,
				pts[i],
				pts[i + 1],
				radius,
				radius,
				segments=radial_sides,
				cap_start=(i == 0),
				cap_end=(i == segments - 1),
			)


def select_rock_material(avg_y: float, face_seed: int, allow_moss: bool = False) -> str:
	if avg_y <= 2.2:
		return "TidalWetRock"
	if allow_moss and avg_y > 16.0 and (face_seed % 4 == 0):
		return "MossyCrag"
	return "SharpObsidian" if (face_seed % 2 == 0) else "BasaltCliff"


def add_jagged_spire(
	mb: FacetedMeshBuilder,
	base_center: Vec3,
	base_rx: float,
	base_rz: float,
	height: float,
	tilt_x_deg: float,
	tilt_z_deg: float,
	sides: int,
	tiers: int,
	seed: int,
	allow_moss: bool = False,
	stepped_terraces: bool = False,
	flat_top_ratio: float = 0.0,
) -> None:
	"""Builds a faceted, ridge-fractured rock blade, spire, or flat-topped island crag."""
	rng: random.Random = random.Random(seed)
	tilt_dx: float = math.tan(math.radians(tilt_x_deg))
	tilt_dz: float = math.tan(math.radians(tilt_z_deg))

	angle_offsets: List[float] = []
	radius_mults: List[float] = []
	for s in range(sides):
		base_ang: float = (2.0 * math.pi * float(s)) / float(sides)
		jitter_ang: float = rng.uniform(-0.14, 0.14) if not stepped_terraces else rng.uniform(-0.04, 0.04)
		angle_offsets.append(base_ang + jitter_ang)
		if stepped_terraces:
			radius_mults.append(rng.uniform(0.88, 1.12))
		else:
			fin: float = 1.28 if (s % 2 == 0) else 0.68
			radius_mults.append(fin * rng.uniform(0.82, 1.18))

	rings: List[List[Vec3]] = []
	for t in range(tiers):
		frac: float = float(t) / float(tiers - 1)
		y: float = base_center[1] + frac * height
		cx: float = base_center[0] + (y - base_center[1]) * tilt_dx
		cz: float = base_center[2] + (y - base_center[1]) * tilt_dz

		if flat_top_ratio > 0.0:
			taper: float = max(flat_top_ratio, 1.0 - frac * (1.0 - flat_top_ratio))
		elif stepped_terraces:
			step_quant: float = math.floor(frac * 4.0) / 4.0
			taper = max(0.18, 1.0 - step_quant * 0.55 - (frac * 0.25))
		else:
			taper = max(0.06, (1.0 - frac) ** 0.78)

		ring: List[Vec3] = []
		for s in range(sides):
			ang: float = angle_offsets[s]
			rm: float = radius_mults[s]
			disp: float = 1.0 + 0.18 * ridge_noise(cx + math.cos(ang) * 3.0, y, cz + math.sin(ang) * 3.0, seed + s)
			rx: float = base_rx * taper * rm * disp
			rz: float = base_rz * taper * rm * disp
			vx: float = cx + math.cos(ang) * rx
			vz: float = cz + math.sin(ang) * rz
			vy: float = y + (0.28 * ridge_noise(vx, y, vz, seed) if (0 < t < tiers - 1) else 0.0)
			ring.append((vx, vy, vz))
		rings.append(ring)

	for t in range(tiers - 1):
		r0: List[Vec3] = rings[t]
		r1: List[Vec3] = rings[t + 1]
		for s in range(sides):
			ns: int = (s + 1) % sides
			p00: Vec3 = r0[s]
			p10: Vec3 = r0[ns]
			p11: Vec3 = r1[ns]
			p01: Vec3 = r1[s]
			avg_y: float = (p00[1] + p10[1] + p11[1] + p01[1]) * 0.25
			mat: str = select_rock_material(avg_y, seed + t * 7 + s, allow_moss)
			out_dir: Vec3 = (
				(p00[0] + p10[0]) * 0.5 - base_center[0],
				0.15,
				(p00[2] + p10[2]) * 0.5 - base_center[2],
			)
			mb.add_tri(mat, p00, p10, p11, out_dir)
			mb.add_tri(mat, p00, p11, p01, out_dir)

	top_ring: List[Vec3] = rings[-1]
	top_y: float = base_center[1] + height
	if flat_top_ratio > 0.0:
		peak_pt: Vec3 = (
			base_center[0] + height * tilt_dx,
			top_y + 0.25,
			base_center[2] + height * tilt_dz,
		)
	else:
		peak_pt = (
			base_center[0] + height * tilt_dx + rng.uniform(-0.25, 0.25),
			top_y + rng.uniform(0.6, 1.6),
			base_center[2] + height * tilt_dz + rng.uniform(-0.25, 0.25),
		)
	peak_mat: str = "MossyCrag" if (allow_moss and flat_top_ratio > 0.0) else select_rock_material(top_y, seed + 99, allow_moss)
	for s in range(sides):
		ns = (s + 1) % sides
		out_dir = (
			top_ring[s][0] - peak_pt[0],
			0.6,
			top_ring[s][2] - peak_pt[2],
		)
		mb.add_tri(peak_mat, top_ring[s], top_ring[ns], peak_pt, out_dir)


def add_stratified_coastal_cliff(mb: FacetedMeshBuilder) -> None:
	"""
	Builds a High-Resolution Stratified Coastal Cliff (128 radial rings x 160 angular segments):
	  - Realistic crescent harbor cove carved on the -Z side
	  - Flanked by a jagged stony breakwater jetty curving out to protect the dock
	  - Terraced basalt rock ledges and coastal erosion undercuts at y = 0.0m to 1.8m
	"""
	num_rings: int = 128
	num_segments: int = 160
	grid_pts: List[List[Vec3]] = []

	for r_idx in range(num_rings):
		u: float = float(r_idx) / float(num_rings - 1)
		# Shift ring center from the headland peak (0.0, 44.0) out toward the island center (0.0, 35.0)
		ring_cx: float = 0.0
		ring_cz: float = 44.0 * (1.0 - u * 0.45) + 33.0 * (u * 0.45)

		ring: List[Vec3] = []
		for s_idx in range(num_segments):
			theta: float = (2.0 * math.pi * float(s_idx)) / float(num_segments)
			dir_x: float = math.cos(theta)
			dir_z: float = math.sin(theta)

			# Outer radius profile: ~29m wide in X, ~27m in Z, carved inward at the -Z harbor cove
			cove_facing: float = max(0.0, -dir_z) * max(0.0, 1.0 - abs(dir_x) * 1.15)
			# Breakwater arm extension on the -X / -Z port side of the cove (theta ~ 3.85..4.35 rad)
			jetty_align: float = max(0.0, math.cos((theta - 4.08) * 3.8))
			jetty_boost: float = (jetty_align ** 2.2) * 11.5 * math.sin(min(1.0, u * 1.25) * math.pi * 0.85)

			base_rad_x: float = 4.2 + u * (25.5 - cove_facing * 7.5 + jetty_boost * 0.75)
			base_rad_z: float = 4.2 + u * (23.0 - cove_facing * 10.5 + jetty_boost * 1.05)

			# Elevation profile from y = 10.8m at headland plateau down to y = -4.2m seafloor
			if u < 0.16:
				# Flat-ish summit plateau around the Lighthouse (y = 10.5m..10.9m)
				base_y: float = 10.85 - (u / 0.16) * 0.35
			else:
				u_slope: float = (u - 0.16) / 0.84
				# In the -Z harbor cove, create a lower coastal shelf around y = 1.7m..2.3m for the buildings
				if cove_facing > 0.22 and 0.32 <= u <= 0.68:
					shelf_blend: float = math.sin(((u - 0.32) / 0.36) * math.pi) * min(1.0, cove_facing * 1.45)
					cliff_h: float = 10.5 * ((1.0 - u_slope) ** 1.35) - 4.2 * (u_slope ** 1.5)
					base_y = cliff_h * (1.0 - shelf_blend) + 1.95 * shelf_blend
				else:
					base_y = 10.5 * ((1.0 - u_slope) ** 1.28) - 4.2 * (u_slope ** 1.45)

			# Keep breakwater jetty ridge above water out to u ~ 0.85
			if jetty_align > 0.35 and 0.45 < u < 0.90:
				jetty_y: float = 2.8 * (1.0 - (u - 0.45) / 0.48) * (jetty_align ** 1.6)
				base_y = max(base_y, jetty_y)

			# Stratified basalt terrace steps & ridge fracture noise
			sample_x: float = ring_cx + dir_x * base_rad_x
			sample_z: float = ring_cz + dir_z * base_rad_z
			n_val: float = ridge_noise(sample_x * 0.32, base_y * 0.45, sample_z * 0.32, 710)
			n_fine: float = ridge_noise(sample_x * 0.85, base_y * 1.1, sample_z * 0.85, 723)

			# Terraced basalt ledges (stepped horizontal strata)
			strata_step: float = math.sin(base_y * 2.85 + n_val * 0.9) * 0.24
			y_final: float = base_y + (strata_step + n_val * 0.42 + n_fine * 0.16) * math.sin(u * math.pi)

			# Coastal erosion undercuts at the waterline (y = 0.0m to 1.8m)
			undercut_inward: float = 0.0
			if -0.15 <= y_final <= 1.95 and u > 0.35:
				undercut_phase: float = (y_final + 0.15) / 2.10
				undercut_inward = 0.95 * math.sin(undercut_phase * math.pi) * (0.7 + 0.3 * abs(n_fine))
			elif 1.95 < y_final <= 2.75 and u > 0.35:
				# Overhanging tidal lip above the wave-cut notch
				undercut_inward = -0.32 * math.sin(((y_final - 1.95) / 0.80) * math.pi)

			rad_mod: float = 1.0 + (n_val * 0.08 + n_fine * 0.035) * min(1.0, u * 1.8)
			rx: float = max(0.4, base_rad_x * rad_mod - undercut_inward)
			rz: float = max(0.4, base_rad_z * rad_mod - undercut_inward)

			vx: float = ring_cx + dir_x * rx
			vz: float = ring_cz + dir_z * rz
			ring.append((vx, y_final, vz))
		grid_pts.append(ring)

	for r_idx in range(num_rings - 1):
		r0: List[Vec3] = grid_pts[r_idx]
		r1: List[Vec3] = grid_pts[r_idx + 1]
		for s_idx in range(num_segments):
			ns: int = (s_idx + 1) % num_segments
			p00: Vec3 = r0[s_idx]
			p10: Vec3 = r0[ns]
			p11: Vec3 = r1[ns]
			p01: Vec3 = r1[s_idx]

			avg_y: float = (p00[1] + p10[1] + p11[1] + p01[1]) * 0.25
			slope_dy: float = abs(p00[1] - p01[1]) + abs(p10[1] - p11[1])
			face_hash: int = (r_idx * 13 + s_idx * 7) % 16

			if avg_y <= 2.15:
				mat: str = "TidalWetRock"
			elif avg_y > 6.8 and slope_dy < 0.32 and (face_hash % 3 == 0):
				mat = "MossyCrag"
			elif slope_dy > 0.55 and (face_hash % 2 == 0):
				mat = "SharpObsidian"
			else:
				mat = "BasaltCliff"

			out_hint: Vec3 = (
				(p00[0] + p11[0]) * 0.5,
				0.35,
				(p00[2] + p11[2]) * 0.5 - 36.0,
			)
			mb.add_tri(mat, p00, p10, p11, out_hint)
			mb.add_tri(mat, p00, p11, p01, out_hint)

	# Reinforce the curved stony Breakwater Jetty on the port (-X, -Z) side of the harbor cove
	jetty_nodes: List[Tuple[float, float, float, float, float, int]] = [
		(-18.5, -3.2, 14.5, 4.2, 6.2, 731),
		(-17.2, -3.2, 11.2, 3.8, 5.8, 732),
		(-15.5, -3.2, 8.0, 3.5, 5.4, 733),
		(-13.6, -3.2, 5.2, 3.2, 5.0, 734),
		(-11.4, -3.2, 2.8, 2.9, 4.6, 735),
	]
	for jx, jy, jz, j_rad, j_h, j_seed in jetty_nodes:
		add_jagged_spire(
			mb,
			base_center=(jx, jy, jz),
			base_rx=j_rad,
			base_rz=j_rad * 0.88,
			height=j_h,
			tilt_x_deg=-12.0,
			tilt_z_deg=-8.0,
			sides=7,
			tiers=5,
			seed=j_seed,
			allow_moss=False,
			stepped_terraces=True,
		)


def add_cliffside_stone_staircase(mb: FacetedMeshBuilder) -> None:
	"""
	Builds a winding carved stone-step pathway (42 individual stone steps) climbing from the rear
	of the wooden wharf (y = 1.38m, z = 21.6m) up the steep cliffside to the Lighthouse base
	at y = 10.5m (z = 40.0m), lined with crooked RustIron stanchion posts and a sagging handrail rope.
	"""
	num_steps: int = 42
	rng: random.Random = random.Random(842)
	stanchion_tops: List[Vec3] = []

	def stair_curve(t: float) -> Vec3:
		# Winding cliffside S-curve around the west side of the Cannery up to the Lighthouse cottage
		sx: float = -3.2 * math.sin(t * math.pi * 1.15) - 4.8 * (t ** 1.3) * math.cos(t * math.pi * 0.45)
		sz: float = 21.6 + t * 18.4
		sy: float = 1.38 + t * (10.52 - 1.38) + 0.18 * math.sin(t * math.pi * 2.0)
		return (sx, sy, sz)

	for i in range(num_steps):
		t0: float = float(i) / float(num_steps - 1)
		t1: float = min(1.0, float(i + 1) / float(num_steps - 1))
		p_curr: Vec3 = stair_curve(t0)
		p_next: Vec3 = stair_curve(t1)
		dx: float = p_next[0] - p_curr[0]
		dz: float = p_next[2] - p_curr[2]
		yaw_deg: float = math.degrees(math.atan2(dx, dz))
		tilt_jitter: float = rng.uniform(-2.2, 2.2)

		# Individual stone step slab (LighthouseStone tread + BasaltCliff foundation curb)
		mb.add_oriented_box(
			"LighthouseStone",
			(p_curr[0], p_curr[1] - 0.08, p_curr[2]),
			(1.65, 0.18, 0.52),
			yaw_deg=yaw_deg,
			roll_deg=tilt_jitter,
		)
		mb.add_oriented_box(
			"BasaltCliff",
			(p_curr[0], p_curr[1] - 0.32, p_curr[2]),
			(1.75, 0.34, 0.58),
			yaw_deg=yaw_deg,
		)

		# Crooked RustIron stanchion posts along the outer (-X) edge of the staircase
		if i % 3 == 0 or i == num_steps - 1:
			rad_yaw: float = math.radians(yaw_deg)
			out_x: float = -math.cos(rad_yaw) * 0.78
			out_z: float = math.sin(rad_yaw) * 0.78
			post_base: Vec3 = (p_curr[0] + out_x, p_curr[1] - 0.05, p_curr[2] + out_z)
			lean_x: float = rng.uniform(-0.12, 0.06)
			lean_z: float = rng.uniform(-0.08, 0.08)
			post_top: Vec3 = (post_base[0] + lean_x, post_base[1] + 0.92, post_base[2] + lean_z)
			mb.add_cylinder_between("RustIron", post_base, post_top, 0.038, 0.032, segments=6)
			# Small iron eye-ring cap at top of stanchion
			mb.add_box("RustIron", post_top, (0.09, 0.09, 0.09))
			stanchion_tops.append(post_top)

	# Sagging handrail rope connecting all cliffside stanchion posts
	for s_idx in range(len(stanchion_tops) - 1):
		mb.add_catenary_cable(
			"WeatheredTimber",
			stanchion_tops[s_idx],
			stanchion_tops[s_idx + 1],
			sag=0.14,
			radius=0.028,
			segments=6,
			radial_sides=5,
		)


def add_barnacle_piling(
	mb: FacetedMeshBuilder,
	px: float,
	pz: float,
	bottom_y: float,
	top_y: float,
	lean_x: float = 0.0,
	lean_z: float = 0.0,
	radius: float = 0.23,
) -> None:
	"""
	Builds a weathered timber piling with a flared, rough TidalWetRock barnacle & kelp cluster
	collar sleeve between y = -0.5m and y = 0.9m.
	"""
	mb.add_cylinder_between(
		"WeatheredTimber",
		(px, bottom_y, pz),
		(px + lean_x, top_y, pz + lean_z),
		radius,
		radius * 0.88,
		segments=8,
	)
	# Barnacle & kelp encrustation sleeve from y = -0.5m to y = 0.9m
	frac_mid: float = (0.2 - bottom_y) / max(0.1, top_y - bottom_y)
	cx_mid: float = px + lean_x * frac_mid
	cz_mid: float = pz + lean_z * frac_mid
	mb.add_cylinder_between(
		"TidalWetRock",
		(cx_mid, -0.50, cz_mid),
		(cx_mid, 0.22, cz_mid),
		radius * 1.12,
		radius * 1.42,
		segments=7,
	)
	mb.add_cylinder_between(
		"TidalWetRock",
		(cx_mid, 0.22, cz_mid),
		(cx_mid, 0.90, cz_mid),
		radius * 1.42,
		radius * 1.06,
		segments=7,
	)


def add_wrecked_skiff(mb: FacetedMeshBuilder, center: Vec3, yaw_deg: float, roll_deg: float) -> None:
	"""
	Builds a half-sunken, broken-ribbed wooden rowboat / skiff resting in the shallows beside the slipway.
	"""
	cx, cy, cz = center
	yr: float = math.radians(yaw_deg)
	rr: float = math.radians(roll_deg)
	cyaw, syaw = math.cos(yr), math.sin(yr)
	crol, srol = math.cos(rr), math.sin(rr)

	def to_world(lx: float, ly: float, lz: float) -> Vec3:
		rx: float = lx * crol - ly * srol
		ry: float = lx * srol + ly * crol
		wx: float = rx * cyaw + lz * syaw
		wz: float = -rx * syaw + lz * cyaw
		return (cx + wx, cy + ry, cz + wz)

	# Heavy rotting keel beam & angled bow stem post
	mb.add_cylinder_between("RottingWood", to_world(0.0, -0.25, -2.3), to_world(0.0, -0.32, 2.1), 0.09, 0.09, segments=6)
	mb.add_cylinder_between("RottingWood", to_world(0.0, -0.25, -2.3), to_world(0.0, 0.58, -2.75), 0.09, 0.07, segments=6)

	# 8 Curved U-shaped wooden hull ribs (some snapped off unevenly)
	rib_z_list: List[float] = [-1.85, -1.30, -0.75, -0.20, 0.35, 0.90, 1.45, 1.95]
	for idx, rz in enumerate(rib_z_list):
		beam_Factor: float = math.cos((rz / 2.45) * (math.pi * 0.46))
		half_w: float = max(0.32, 1.08 * beam_Factor)
		port_top_y: float = 0.48 if (idx % 3 != 1) else 0.18  # Broken ribs on port side
		stbd_top_y: float = 0.46 if (idx % 2 == 0) else 0.24  # Broken ribs on starboard side

		p_keel: Vec3 = to_world(0.0, -0.26, rz)
		p_port_bilge: Vec3 = to_world(-half_w * 0.72, -0.08, rz)
		p_port_gunwale: Vec3 = to_world(-half_w, port_top_y, rz)
		p_stbd_bilge: Vec3 = to_world(half_w * 0.72, -0.08, rz)
		p_stbd_gunwale: Vec3 = to_world(half_w, stbd_top_y, rz)

		mb.add_cylinder_between("RottingWood", p_keel, p_port_bilge, 0.045, 0.045, segments=5)
		mb.add_cylinder_between("RottingWood", p_port_bilge, p_port_gunwale, 0.045, 0.038, segments=5)
		mb.add_cylinder_between("RottingWood", p_keel, p_stbd_bilge, 0.045, 0.045, segments=5)
		mb.add_cylinder_between("RottingWood", p_stbd_bilge, p_stbd_gunwale, 0.045, 0.038, segments=5)

	# Remaining weathered hull strake planks (with rotting gaps exposing the ribs)
	for side_sign in (-1.0, 1.0):
		for strake_h in (-0.02, 0.18, 0.36):
			for seg in range(5):
				if seg == 2 and strake_h > 0.1 and side_sign < 0.0:
					continue  # Gaping hole in port hull planks
				z0: float = -2.1 + float(seg) * 0.82
				z1: float = z0 + 0.76
				w0: float = max(0.22, 1.05 * math.cos((z0 / 2.5) * (math.pi * 0.46))) * side_sign
				w1: float = max(0.22, 1.05 * math.cos((z1 / 2.5) * (math.pi * 0.46))) * side_sign
				mb.add_cylinder_between(
					"WeatheredTimber",
					to_world(w0, strake_h, z0),
					to_world(w1, strake_h, z1),
					0.04,
					0.04,
					segments=5,
				)

	# Broken thwart bench & stern transom board
	mb.add_cylinder_between("WeatheredTimber", to_world(-0.88, 0.22, -0.20), to_world(0.85, 0.14, -0.20), 0.06, 0.06, segments=6)
	mb.add_oriented_box("RottingWood", to_world(0.0, 0.10, 2.08), (1.15, 0.48, 0.08), yaw_deg=yaw_deg, roll_deg=roll_deg)


def add_recessed_mullion_window(
	mb: FacetedMeshBuilder,
	center: Vec3,
	win_w: float,
	win_h: float,
	wall_normal_z: float,
	lean_x_deg: float,
	shutter_tilt_left: float = 9.0,
	shutter_tilt_right: float = -14.0,
) -> None:
	"""
	Builds an 8cm-deep recessed window cavity containing glowing AmberGlass panes divided by a 3D
	cross-grid of thin dark wooden mullions, a projecting exterior sill, top lintel, and crooked storm shutters.
	"""
	wx, wy, wz = center
	recess_depth: float = 0.085
	glass_z: float = wz - wall_normal_z * recess_depth

	# Recessed wooden window casing frame (8cm deep top, bottom, left, right jambs)
	jamb_thick: float = 0.065
	mb.add_box("RottingWood", (wx - win_w * 0.5, wy, wz - wall_normal_z * 0.04), (jamb_thick, win_h + 0.08, recess_depth + 0.04))
	mb.add_box("RottingWood", (wx + win_w * 0.5, wy, wz - wall_normal_z * 0.04), (jamb_thick, win_h + 0.08, recess_depth + 0.04))
	mb.add_box("WeatheredTimber", (wx, wy + win_h * 0.5 + 0.04, wz + wall_normal_z * 0.03), (win_w + 0.22, 0.09, recess_depth + 0.10))
	# Projecting exterior window sill
	mb.add_box("WeatheredTimber", (wx, wy - win_h * 0.5 - 0.04, wz + wall_normal_z * 0.05), (win_w + 0.26, 0.08, recess_depth + 0.14))

	# Recessed glowing AmberGlass pane
	hw: float = win_w * 0.48
	hh: float = win_h * 0.48
	mb.add_quad(
		"AmberGlass",
		(wx - hw, wy - hh, glass_z),
		(wx - hw, wy + hh, glass_z),
		(wx + hw, wy + hh, glass_z),
		(wx + hw, wy - hh, glass_z),
		(0.0, 0.0, wall_normal_z),
	)

	# 3D Cross-Grid of thin dark wooden mullions (2 vertical + 2 horizontal muntin bars)
	mullion_z: float = glass_z + wall_normal_z * 0.025
	for vx_off in (-win_w * 0.17, win_w * 0.17):
		mb.add_box("RottingWood", (wx + vx_off, wy, mullion_z), (0.032, win_h, 0.038))
	for vy_off in (-win_h * 0.17, win_h * 0.17):
		mb.add_box("RottingWood", (wx, wy + vy_off, mullion_z), (win_w, 0.032, 0.038))

	# Crooked storm shutters hanging at odd angles beside the window
	shutter_w: float = win_w * 0.44
	shutter_z: float = wz + wall_normal_z * 0.04
	mb.add_oriented_box(
		"RottingWood",
		(wx - win_w * 0.5 - shutter_w * 0.56, wy, shutter_z),
		(shutter_w, win_h * 0.96, 0.045),
		yaw_deg=12.0 * wall_normal_z,
		roll_deg=shutter_tilt_left + lean_x_deg,
	)
	mb.add_oriented_box(
		"RottingWood",
		(wx + win_w * 0.5 + shutter_w * 0.56, wy - 0.03, shutter_z),
		(shutter_w, win_h * 0.96, 0.045),
		yaw_deg=-15.0 * wall_normal_z,
		roll_deg=shutter_tilt_right + lean_x_deg,
	)


def add_architectural_harbor_building(
	mb: FacetedMeshBuilder,
	center: Vec3,
	width: float,
	height: float,
	depth: float,
	wall_mat: str,
	trim_mat: str,
	roof_mat: str,
	lean_x_deg: float,
	lean_z_deg: float,
	roof_sag: float,
	window_front_count: int = 2,
	add_side_windows: bool = True,
	seed: int = 100,
) -> None:
	"""
	Builds a hyper-detailed run-down harbor building:
	  - Overlapping horizontal clapboard weatherboard siding (12 courses)
	  - Vertical corner trim posts & diagonal timber knee-braces
	  - Recessed multi-pane AmberGlass mullion windows with sills & crooked storm shutters
	  - Visibly ribbed CorrugatedRoof panels (with lifted/peeling corners), exposed rafter tails,
	    sagging RustIron rain gutters, and vertical corner downspouts.
	"""
	rng: random.Random = random.Random(seed)
	cx, by, cz = center
	hx: float = width * 0.5
	hz: float = depth * 0.5
	tan_lx: float = math.tan(math.radians(lean_x_deg))
	tan_lz: float = math.tan(math.radians(lean_z_deg))

	# 1. Overlapping Horizontal Clapboard Siding (12 weatherboard courses on all 4 walls)
	courses: int = 12
	course_h: float = height / float(courses)
	lap_out: float = 0.028  # Bottom edge of each clapboard overlaps outward by 2.8cm
	for c_idx in range(courses):
		y0: float = by + float(c_idx) * course_h
		y1: float = y0 + course_h * 1.06
		dx0: float = (y0 - by) * tan_lx
		dz0: float = (y0 - by) * tan_lz
		dx1: float = (y1 - by) * tan_lx
		dz1: float = (y1 - by) * tan_lz

		c_mat: str = wall_mat if (c_idx % 4 != 3) else ("RottingWood" if wall_mat == "ShackWall" else "ShackWall")

		# Front wall (-Z) clapboard strip (bottom edge flares to -Z - lap_out)
		mb.add_quad(
			c_mat,
			(cx - hx + dx0, y0, cz - hz + dz0 - lap_out),
			(cx - hx + dx1, y1, cz - hz + dz1),
			(cx + hx + dx1, y1, cz - hz + dz1),
			(cx + hx + dx0, y0, cz - hz + dz0 - lap_out),
			(0.0, -0.15, -1.0),
		)
		# Back wall (+Z) clapboard strip
		mb.add_quad(
			c_mat,
			(cx + hx + dx0, y0, cz + hz + dz0 + lap_out),
			(cx + hx + dx1, y1, cz + hz + dz1),
			(cx - hx + dx1, y1, cz + hz + dz1),
			(cx - hx + dx0, y0, cz + hz + dz0 + lap_out),
			(0.0, -0.15, 1.0),
		)
		# Left wall (-X) clapboard strip
		mb.add_quad(
			c_mat,
			(cx - hx + dx0 - lap_out, y0, cz + hz + dz0),
			(cx - hx + dx1, y1, cz + hz + dz1),
			(cx - hx + dx1, y1, cz - hz + dz1),
			(cx - hx + dx0 - lap_out, y0, cz - hz + dz0),
			(-1.0, -0.15, 0.0),
		)
		# Right wall (+X) clapboard strip
		mb.add_quad(
			c_mat,
			(cx + hx + dx0 + lap_out, y0, cz - hz + dz0),
			(cx + hx + dx1, y1, cz - hz + dz1),
			(cx + hx + dx1, y1, cz + hz + dz1),
			(cx + hx + dx0 + lap_out, y0, cz + hz + dz0),
			(1.0, -0.15, 0.0),
		)

	# 2. Vertical Corner Trim Posts & Timber Knee-Braces
	lean_dx_top: float = height * tan_lx
	lean_dz_top: float = height * tan_lz
	ty: float = by + height
	for sx_sign in (-1.0, 1.0):
		for sz_sign in (-1.0, 1.0):
			p_bot: Vec3 = (cx + sx_sign * hx, by - 0.15, cz + sz_sign * hz)
			p_top: Vec3 = (cx + sx_sign * hx + lean_dx_top, ty + 0.05, cz + sz_sign * hz + lean_dz_top)
			mb.add_cylinder_between(trim_mat, p_bot, p_top, 0.12, 0.11, segments=4)
			# Diagonal knee-brace under eave
			brace_start: Vec3 = v_lerp(p_bot, p_top, 0.68)
			brace_end: Vec3 = (
				p_top[0] - sx_sign * 0.65,
				ty - 0.05,
				p_top[2] + (-sz_sign * 0.35),
			)
			mb.add_cylinder_between(trim_mat, brace_start, brace_end, 0.065, 0.065, segments=4)

	# 3. Gable End Walls with horizontal clapboard courses
	gable_h: float = height * 0.44
	t_fl: Vec3 = (cx - hx + lean_dx_top, ty, cz - hz + lean_dz_top)
	t_fr: Vec3 = (cx + hx + lean_dx_top, ty, cz - hz + lean_dz_top)
	t_bl: Vec3 = (cx - hx + lean_dx_top, ty, cz + hz + lean_dz_top)
	t_br: Vec3 = (cx + hx + lean_dx_top, ty, cz + hz + lean_dz_top)
	r_left: Vec3 = (cx - hx + lean_dx_top, ty + gable_h, cz + lean_dz_top)
	r_right: Vec3 = (cx + hx + lean_dx_top, ty + gable_h, cz + lean_dz_top)
	mb.add_tri(wall_mat, t_bl, r_left, t_fl, (-1.0, 0.0, 0.0))
	mb.add_tri(wall_mat, t_fr, r_right, t_br, (1.0, 0.0, 0.0))

	# 4. Exposed Rafter Tails under the front (-Z) and back (+Z) eaves
	eave_overhang_x: float = 0.38
	eave_overhang_z: float = 0.48
	rafter_count: int = 9
	for r_i in range(rafter_count):
		ru: float = float(r_i) / float(rafter_count - 1)
		rx_pos: float = (cx - hx) + ru * width + lean_dx_top
		sag_r: float = math.sin(ru * math.pi) * roof_sag
		ry_ridge: float = ty + gable_h - sag_r
		ey_eave: float = ty - 0.14 - sag_r * 0.42
		zf_eave: float = cz - hz - eave_overhang_z + lean_dz_top
		zb_eave: float = cz + hz + eave_overhang_z + lean_dz_top
		z_ridge: float = cz + lean_dz_top

		mb.add_cylinder_between(trim_mat, (rx_pos, ry_ridge - 0.05, z_ridge), (rx_pos, ey_eave - 0.04, zf_eave), 0.05, 0.045, segments=4)
		mb.add_cylinder_between(trim_mat, (rx_pos, ry_ridge - 0.05, z_ridge), (rx_pos, ey_eave - 0.04, zb_eave), 0.05, 0.045, segments=4)

	# 5. Visibly Ribbed CorrugatedRoof Panels (some slightly lifted/peeling at the corners)
	panel_cols: int = 8
	total_roof_w: float = width + 2.0 * eave_overhang_x
	for p_i in range(panel_cols):
		u0: float = float(p_i) / float(panel_cols)
		u1: float = float(p_i + 1) / float(panel_cols)
		x0: float = (cx - hx - eave_overhang_x) + u0 * total_roof_w + lean_dx_top
		x1: float = (cx - hx - eave_overhang_x) + u1 * total_roof_w + lean_dx_top
		sag0: float = math.sin(u0 * math.pi) * roof_sag
		sag1: float = math.sin(u1 * math.pi) * roof_sag

		ry0: float = ty + gable_h - sag0
		ry1: float = ty + gable_h - sag1
		ey0: float = ty - 0.10 - sag0 * 0.42
		ey1: float = ty - 0.10 - sag1 * 0.42

		# Slightly lifted / storm-peeled corner sheets on outer or alternate panels
		peel_f0: float = 0.11 if (p_i == 0 or p_i == 5) else 0.0
		peel_f1: float = 0.09 if (p_i == panel_cols - 1 or p_i == 2) else 0.0
		peel_b1: float = 0.10 if (p_i == 1 or p_i == 6) else 0.0

		zf_eave = cz - hz - eave_overhang_z + lean_dz_top
		zb_eave = cz + hz + eave_overhang_z + lean_dz_top
		z_ridge = cz + lean_dz_top

		# Front roof sheet (-Z)
		mb.add_quad(
			roof_mat,
			(x0, ey0 + peel_f0, zf_eave),
			(x0, ry0, z_ridge),
			(x1, ry1, z_ridge),
			(x1, ey1 + peel_f1, zf_eave),
			(0.0, 1.0, -0.5),
		)
		# Back roof sheet (+Z)
		mb.add_quad(
			roof_mat,
			(x0, ry0, z_ridge),
			(x0, ey0, zb_eave),
			(x1, ey1 + peel_b1, zb_eave),
			(x1, ry1, z_ridge),
			(0.0, 1.0, 0.5),
		)

		# Raised 3D corrugation ribs along each sheet panel (3 ribs per panel)
		for rib_sub in range(3):
			ru_rib: float = u0 + (u1 - u0) * ((float(rib_sub) + 0.5) / 3.0)
			rx_rib: float = (cx - hx - eave_overhang_x) + ru_rib * total_roof_w + lean_dx_top
			sag_rib: float = math.sin(ru_rib * math.pi) * roof_sag
			ry_rib: float = ty + gable_h - sag_rib + 0.03
			ey_rib: float = ty - 0.10 - sag_rib * 0.42 + 0.03
			mb.add_cylinder_between(roof_mat, (rx_rib, ry_rib, z_ridge), (rx_rib, ey_rib + peel_f0 * 0.5, zf_eave), 0.028, 0.028, segments=4)
			mb.add_cylinder_between(roof_mat, (rx_rib, ry_rib, z_ridge), (rx_rib, ey_rib + peel_b1 * 0.5, zb_eave), 0.028, 0.028, segments=4)

	# 6. Sagging Rain Gutters & Vertical Downspouts (RustIron)
	zf_gutter: float = cz - hz - eave_overhang_z - 0.05 + lean_dz_top
	zb_gutter: float = cz + hz + eave_overhang_z + 0.05 + lean_dz_top
	gutter_left_f: Vec3 = (cx - hx - eave_overhang_x + lean_dx_top, ty - 0.16, zf_gutter)
	gutter_right_f: Vec3 = (cx + hx + eave_overhang_x + lean_dx_top, ty - 0.22, zf_gutter)
	mb.add_catenary_cable("RustIron", gutter_left_f, gutter_right_f, sag=roof_sag * 0.55 + 0.08, radius=0.055, segments=6, radial_sides=5)

	gutter_left_b: Vec3 = (cx - hx - eave_overhang_x + lean_dx_top, ty - 0.18, zb_gutter)
	gutter_right_b: Vec3 = (cx + hx + eave_overhang_x + lean_dx_top, ty - 0.15, zb_gutter)
	mb.add_catenary_cable("RustIron", gutter_left_b, gutter_right_b, sag=roof_sag * 0.50 + 0.07, radius=0.055, segments=6, radial_sides=5)

	# Vertical downspouts at front-right and back-left corners with elbow bends
	ds_top_f: Vec3 = gutter_right_f
	ds_elbow_f: Vec3 = (cx + hx + 0.08 + lean_dx_top, ty - 0.45, cz - hz - 0.08 + lean_dz_top)
	ds_bot_f: Vec3 = (cx + hx + 0.08, by - 0.10, cz - hz - 0.08)
	mb.add_cylinder_between("RustIron", ds_top_f, ds_elbow_f, 0.045, 0.045, segments=6)
	mb.add_cylinder_between("RustIron", ds_elbow_f, ds_bot_f, 0.045, 0.045, segments=6)

	# 7. Recessed Multi-Pane Mullion Windows on front (-Z) wall
	win_w: float = min(1.08, (width * 0.54) / float(max(1, window_front_count)))
	win_h: float = min(1.12, height * 0.35)
	win_y: float = by + height * 0.54
	frac_wy: float = (win_y - by) / height
	win_z: float = cz - hz + lean_dz_top * frac_wy

	for w_idx in range(window_front_count):
		span_frac: float = (float(w_idx) + 0.5) / float(window_front_count) - 0.5
		wx_c: float = cx + span_frac * (width * 0.62) + lean_dx_top * frac_wy
		add_recessed_mullion_window(
			mb,
			center=(wx_c, win_y, win_z),
			win_w=win_w,
			win_h=win_h,
			wall_normal_z=-1.0,
			lean_x_deg=lean_x_deg,
			shutter_tilt_left=rng.uniform(6.0, 16.0),
			shutter_tilt_right=rng.uniform(-18.0, -7.0),
		)

	if add_side_windows:
		# Rear (+Z) recessed mullion window so building glows from all angles
		add_recessed_mullion_window(
			mb,
			center=(cx + lean_dx_top * frac_wy, win_y, cz + hz + lean_dz_top * frac_wy),
			win_w=win_w * 0.88,
			win_h=win_h * 0.88,
			wall_normal_z=1.0,
			lean_x_deg=lean_x_deg,
			shutter_tilt_left=-11.0,
			shutter_tilt_right=13.0,
		)


def add_lobster_trap(mb: FacetedMeshBuilder, center: Vec3, yaw_deg: float = 0.0) -> None:
	"""Builds a slatted wooden half-cylindrical / rectangular lobster pot trap."""
	cx, cy, cz = center
	yr: float = math.radians(yaw_deg)
	cyaw, syaw = math.cos(yr), math.sin(yr)

	def pt(lx: float, ly: float, lz: float) -> Vec3:
		return (cx + lx * cyaw + lz * syaw, cy + ly, cz - lx * syaw + lz * cyaw)

	# Base wooden skids
	mb.add_oriented_box("WeatheredTimber", pt(0.0, 0.03, -0.26), (0.92, 0.05, 0.08), yaw_deg=yaw_deg)
	mb.add_oriented_box("WeatheredTimber", pt(0.0, 0.03, 0.26), (0.92, 0.05, 0.08), yaw_deg=yaw_deg)
	# 3 End/middle frame bows
	for bx in (-0.42, 0.0, 0.42):
		mb.add_oriented_box("RottingWood", pt(bx, 0.22, 0.0), (0.05, 0.38, 0.56), yaw_deg=yaw_deg, skip_bottom=True)
	# 7 Longitudinal wooden lath slats around the top & sides
	slat_offsets: List[Tuple[float, float]] = [
		(0.12, -0.28), (0.28, -0.26), (0.40, -0.14), (0.42, 0.0),
		(0.40, 0.14), (0.28, 0.26), (0.12, 0.28),
	]
	for sy, sz in slat_offsets:
		mb.add_cylinder_between("WeatheredTimber", pt(-0.45, sy, sz), pt(0.45, sy, sz), 0.022, 0.022, segments=4)


def add_fish_barrel(mb: FacetedMeshBuilder, base_pos: Vec3, tilt_deg: float = 0.0) -> None:
	"""Builds a banded wooden stave fish barrel with twin RustIron hoops."""
	bx, by, bz = base_pos
	dx: float = math.sin(math.radians(tilt_deg)) * 0.82
	p0: Vec3 = (bx, by, bz)
	p_mid: Vec3 = (bx + dx * 0.5, by + 0.41, bz)
	p1: Vec3 = (bx + dx, by + 0.82, bz)
	mb.add_cylinder_between("WeatheredTimber", p0, p_mid, 0.27, 0.32, segments=9, cap_end=False)
	mb.add_cylinder_between("WeatheredTimber", p_mid, p1, 0.32, 0.27, segments=9, cap_start=False)
	# Iron barrel hoops
	p_h1: Vec3 = v_lerp(p0, p1, 0.22)
	p_h2: Vec3 = v_lerp(p0, p1, 0.78)
	mb.add_cylinder_between("RustIron", p_h1, (p_h1[0], p_h1[1] + 0.06, p_h1[2]), 0.305, 0.305, segments=9)
	mb.add_cylinder_between("RustIron", p_h2, (p_h2[0], p_h2[1] + 0.06, p_h2[2]), 0.305, 0.305, segments=9)


def add_fuel_drum(mb: FacetedMeshBuilder, base_pos: Vec3, on_side: bool = False, yaw_deg: float = 0.0) -> None:
	"""Builds a dented RustIron fuel drum with rolling ribs."""
	bx, by, bz = base_pos
	if not on_side:
		mb.add_cylinder_between("RustIron", (bx, by, bz), (bx + 0.03, by + 0.88, bz - 0.02), 0.29, 0.28, segments=10)
		mb.add_cylinder_between("DarkMetal", (bx + 0.01, by + 0.28, bz), (bx + 0.01, by + 0.33, bz), 0.305, 0.305, segments=10)
		mb.add_cylinder_between("DarkMetal", (bx + 0.02, by + 0.58, bz), (bx + 0.02, by + 0.63, bz), 0.305, 0.305, segments=10)
	else:
		yr: float = math.radians(yaw_deg)
		dx: float = math.cos(yr) * 0.44
		dz: float = math.sin(yr) * 0.44
		p0: Vec3 = (bx - dx, by + 0.29, bz - dz)
		p1: Vec3 = (bx + dx, by + 0.29, bz + dz)
		mb.add_cylinder_between("RustIron", p0, p1, 0.29, 0.28, segments=10)
		# Wooden chocks under horizontal drum
		mb.add_oriented_box("WeatheredTimber", (bx, by + 0.06, bz), (0.55, 0.12, 0.68), yaw_deg=yaw_deg)


def add_pier_jib_crane(mb: FacetedMeshBuilder, base_pos: Vec3) -> None:
	"""
	Builds a wooden dockside jib-crane at the pier end with a diagonal timber boom,
	iron tie-rods, a hanging DarkMetal chain, and a RustIron cargo hook.
	"""
	bx, by, bz = base_pos
	mast_top: Vec3 = (bx, by + 3.85, bz)
	boom_base: Vec3 = (bx, by + 1.15, bz)
	boom_tip: Vec3 = (bx - 1.65, by + 3.35, bz - 1.55)

	# Heavy vertical timber king-post & iron base collar
	mb.add_cylinder_between("RustIron", (bx, by, bz), (bx, by + 0.45, bz), 0.24, 0.22, segments=8)
	mb.add_cylinder_between("WeatheredTimber", (bx, by + 0.40, bz), mast_top, 0.18, 0.15, segments=8)
	# Diagonal wooden jib boom
	mb.add_cylinder_between("WeatheredTimber", boom_base, boom_tip, 0.13, 0.10, segments=6)
	# Iron tie-rod from mast top to boom tip
	mb.add_cylinder_between("DarkMetal", (bx, by + 3.70, bz), boom_tip, 0.032, 0.032, segments=6)
	# Hand-winch drum & crank on the king-post
	mb.add_cylinder_between("RustIron", (bx - 0.28, by + 0.95, bz), (bx + 0.28, by + 0.95, bz), 0.16, 0.16, segments=8)

	# Hanging iron chain & cargo hook dangling from the boom tip
	chain_bot: Vec3 = (boom_tip[0], by + 1.05, boom_tip[2])
	mb.add_cylinder_between("DarkMetal", boom_tip, chain_bot, 0.026, 0.026, segments=6)
	# Iron pulley block & curved cargo hook
	mb.add_box("RustIron", chain_bot, (0.18, 0.22, 0.12))
	mb.add_cylinder_between("RustIron", chain_bot, (chain_bot[0] - 0.14, chain_bot[1] - 0.22, chain_bot[2]), 0.035, 0.030, segments=6)
	mb.add_cylinder_between(
		"RustIron",
		(chain_bot[0] - 0.14, chain_bot[1] - 0.22, chain_bot[2]),
		(chain_bot[0] + 0.08, chain_bot[1] - 0.12, chain_bot[2]),
		0.030,
		0.018,
		segments=6,
	)


def build_wharf_island() -> FacetedMeshBuilder:
	"""
	Builds the hyper-detailed wharf_island.obj:
	  1. High-Resolution Stratified Coastal Cliff (128 radial rings x 160 angular segments) with
	     crescent harbor cove, breakwater jetty, terraced basalt ledges, waterline undercuts,
	     and a 42-step cliffside stone staircase with crooked stanchions & handrail rope.
	  2. Multi-level Timber Wharf (main pier at y=1.35m + lower tidal landing stage at y=0.65m),
	     96 individual warped WeatheredTimber planks with 2cm gaps, stringers, rubbing-strake fenders,
	     barnacle-collared pilings, and a rotting wooden slipway with a half-sunken wrecked skiff.
	  3. 3 Hyper-detailed run-down harbor buildings (Bait Shack, Two-Story Cannery, Net-Drying Shanty)
	     with overlapping clapboard siding, 8cm recessed multi-pane mullion windows, crooked shutters,
	     ribbed corrugated roofs, exposed rafter tails, sagging gutters, and stovepipe/brick chimneys.
	  4. Heavy dockside clutter (lobster traps, fish barrels, fuel drums, jib-crane with chain & hook,
	     coiled mooring ropes) and sagging 3D catenary overhead cables (DarkMetal).
	  5. Architectural Lighthouse Complex at (0.0, 10.5, 44.0) with Keeper's Cottage, 26m recessed-course
	     masonry tower, projecting window lintels, flared corbelled gallery stonework, iron lattice
	     lantern room, and copper-patina domed cupola with weathervane and lightning rod.
	"""
	mb: FacetedMeshBuilder = FacetedMeshBuilder()
	rng: random.Random = random.Random(777)

	# --- 1. High-Resolution Stratified Coastal Cliff & 42-Step Stone Staircase ---
	add_stratified_coastal_cliff(mb)
	add_cliffside_stone_staircase(mb)

	# --- 2. Intricate Timber Wharf, Tidal Landing Stage, Slipway & Wrecked Skiff ---
	# Heavy longitudinal under-deck stringer beams (main pier z = +4.0m to +22.0m)
	for sx in (-7.4, -3.7, 0.0, 3.7, 7.4):
		mb.add_box("WeatheredTimber", (sx, 1.16, 13.0), (0.30, 0.28, 18.2))
	# Transverse cap-beams atop piling rows
	piling_z_rows: List[float] = [4.5, 8.8, 13.2, 17.6, 21.5]
	for pz in piling_z_rows:
		mb.add_box("RottingWood", (0.0, 0.96, pz), (16.2, 0.26, 0.32))

	# 80 Individual WeatheredTimber planks on Main Pier (40 rows x 2 staggered lateral bays) with 2cm gaps
	num_main_rows: int = 40
	plank_z_start: float = 4.08
	plank_z_end: float = 21.92
	plank_pitch: float = (plank_z_end - plank_z_start) / float(num_main_rows)
	plank_depth: float = plank_pitch - 0.02  # Exact 2cm gap between planks
	for r_i in range(num_main_rows):
		pz = plank_z_start + (float(r_i) + 0.5) * plank_pitch
		split_x: float = 0.65 if (r_i % 2 == 0) else -0.65
		left_w: float = (8.0 + split_x) - 0.01
		right_w: float = (8.0 - split_x) - 0.01
		left_cx: float = -8.0 + left_w * 0.5
		right_cx: float = 8.0 - right_w * 0.5

		mb.add_oriented_box(
			"WeatheredTimber",
			(left_cx, 1.35 + rng.uniform(-0.018, 0.018), pz),
			(left_w, 0.11, plank_depth),
			pitch_deg=rng.uniform(-1.2, 1.2),
			roll_deg=rng.uniform(-0.8, 0.8),
		)
		mb.add_oriented_box(
			"WeatheredTimber",
			(right_cx, 1.35 + rng.uniform(-0.018, 0.018), pz),
			(right_w, 0.11, plank_depth),
			pitch_deg=rng.uniform(-1.2, 1.2),
			roll_deg=rng.uniform(-0.8, 0.8),
		)

	# Lower Tidal Boat-Landing Stage (y = 0.65m, x = +8.0m to +11.4m, z = +5.6m to +13.6m)
	mb.add_box("WeatheredTimber", (8.3, 0.50, 9.6), (0.24, 0.22, 8.0))
	mb.add_box("WeatheredTimber", (11.1, 0.50, 9.6), (0.24, 0.22, 8.0))
	num_stage_planks: int = 18  # 80 + 18 = 98 individual planks (> 90 planks)
	stage_z0: float = 5.65
	stage_z1: float = 11.85
	stage_pitch: float = (stage_z1 - stage_z0) / float(num_stage_planks)
	for s_i in range(num_stage_planks):
		spz: float = stage_z0 + (float(s_i) + 0.5) * stage_pitch
		mb.add_oriented_box(
			"WeatheredTimber",
			(9.7, 0.65 + rng.uniform(-0.014, 0.014), spz),
			(3.3, 0.09, stage_pitch - 0.02),
			roll_deg=rng.uniform(-1.1, 1.1),
		)

	# Wooden stair flight (5 steps) connecting Main Pier (y = 1.35m) to Lower Landing Stage (y = 0.65m)
	mb.add_cylinder_between("WeatheredTimber", (8.2, 1.35, 13.6), (8.2, 0.65, 11.85), 0.08, 0.08, segments=4)
	mb.add_cylinder_between("WeatheredTimber", (10.8, 1.35, 13.6), (10.8, 0.65, 11.85), 0.08, 0.08, segments=4)
	for st_i in range(5):
		st_frac: float = (float(st_i) + 0.5) / 5.0
		st_y: float = 1.35 - st_frac * (1.35 - 0.65)
		st_z: float = 13.55 - st_frac * (13.55 - 11.90)
		mb.add_box("WeatheredTimber", (9.5, st_y, st_z), (2.5, 0.07, 0.30))

	# Barnacle-collared Pilings & Under-Pier Diagonal X-Bracing
	piling_x_cols: List[float] = [-7.6, -2.6, 2.6, 7.6]
	for pz in piling_z_rows:
		for px in piling_x_cols:
			top_y: float = 2.18 if abs(px) > 7.0 else 1.30
			add_barnacle_piling(
				mb,
				px,
				pz,
				bottom_y=-4.0,
				top_y=top_y,
				lean_x=rng.uniform(-0.08, 0.08),
				lean_z=rng.uniform(-0.08, 0.08),
				radius=0.24,
			)
		# Diagonal timber cross-bracing between pilings
		mb.add_cylinder_between("RottingWood", (-7.6, -0.35, pz), (-2.6, 1.12, pz), 0.09, 0.09, segments=6)
		mb.add_cylinder_between("RottingWood", (-7.6, 1.12, pz), (-2.6, -0.35, pz), 0.09, 0.09, segments=6)
		mb.add_cylinder_between("RottingWood", (-2.6, -0.35, pz), (2.6, 1.12, pz), 0.09, 0.09, segments=6)
		mb.add_cylinder_between("RottingWood", (2.6, -0.35, pz), (7.6, 1.12, pz), 0.09, 0.09, segments=6)
		mb.add_cylinder_between("RottingWood", (2.6, 1.12, pz), (7.6, -0.35, pz), 0.09, 0.09, segments=6)

	# Pilings & cross-bracing under the lower tidal landing stage
	for lpz in (5.8, 9.6, 13.4):
		add_barnacle_piling(mb, 11.2, lpz, bottom_y=-3.8, top_y=1.45, lean_x=0.05, lean_z=-0.04, radius=0.20)
		mb.add_cylinder_between("RottingWood", (7.6, -0.2, lpz), (11.2, 0.55, lpz), 0.08, 0.08, segments=5)

	# Vertical Timber Rubbing-Strake Fenders along outer mooring edges
	for fx in (-6.8, -4.5, -2.2, 0.0, 2.2, 4.5, 6.8):
		mb.add_box("WeatheredTimber", (fx, 0.72, 3.96), (0.18, 1.48, 0.14))
		mb.add_box("RustIron", (fx, 1.22, 3.88), (0.20, 0.08, 0.04))
	for fz in (5.6, 7.6, 9.6, 11.6, 13.6, 15.6, 17.6, 19.6):
		mb.add_box("WeatheredTimber", (-8.04, 0.72, fz), (0.14, 1.48, 0.18))
		if fz > 13.8:
			mb.add_box("WeatheredTimber", (8.04, 0.72, fz), (0.14, 1.48, 0.18))
		else:
			mb.add_box("WeatheredTimber", (11.42, 0.35, fz), (0.14, 1.15, 0.18))

	# Rotting Wooden Slipway & Wrecked Skiff at (x = -14.0, z = 12.0)
	for rail_x in (-15.1, -12.9):
		mb.add_cylinder_between("WeatheredTimber", (rail_x, 1.52, 16.8), (rail_x, -0.75, 7.2), 0.14, 0.13, segments=6)
		add_barnacle_piling(mb, rail_x, 11.5, bottom_y=-3.6, top_y=0.45, radius=0.17)
		add_barnacle_piling(mb, rail_x, 8.2, bottom_y=-3.6, top_y=-0.25, radius=0.17)
	for sl_i in range(18):
		sl_t: float = float(sl_i) / 17.0
		sl_y: float = 1.55 - sl_t * (1.55 - (-0.70))
		sl_z: float = 16.6 - sl_t * (16.6 - 7.4)
		mb.add_oriented_box("RottingWood", (-14.0, sl_y, sl_z), (2.65, 0.10, 0.24), pitch_deg=-13.2)

	# Half-sunken, broken-ribbed wooden rowboat resting in the shallows beside the slipway
	add_wrecked_skiff(mb, center=(-14.15, 0.08, 10.35), yaw_deg=14.0, roll_deg=19.5)

	# --- 3. Three Hyper-Detailed Run-Down Harbor Buildings ---
	# Building 1: Slumped Bait & Tackle Shack (x = -11.0, y = 1.6, z = 19.0)
	add_architectural_harbor_building(
		mb,
		center=(-11.0, 1.6, 19.0),
		width=6.2,
		height=3.4,
		depth=5.4,
		wall_mat="RottingWood",
		trim_mat="WeatheredTimber",
		roof_mat="CorrugatedRoof",
		lean_x_deg=3.5,
		lean_z_deg=-2.5,
		roof_sag=0.28,
		window_front_count=2,
		seed=801,
	)
	for sx in (-13.7, -8.3):
		for sz in (16.5, 21.5):
			add_barnacle_piling(mb, sx, sz, bottom_y=-3.6, top_y=1.68, radius=0.19)
	# Bait Shack rusted stovepipe chimney with conical rain cap at (-13.0, 6.85, 18.0)
	mb.add_cylinder_between("RustIron", (-12.75, 4.5, 18.2), (-13.0, 6.65, 18.0), 0.15, 0.13, segments=8)
	mb.add_cylinder_between("RustIron", (-13.0, 6.72, 18.0), (-13.0, 6.96, 18.0), 0.28, 0.03, segments=8)

	# Building 2: Two-Story Cannery Warehouse (x = 2.0, y = 2.0, z = 25.0)
	add_architectural_harbor_building(
		mb,
		center=(2.0, 2.0, 25.0),
		width=10.5,
		height=3.8,
		depth=7.8,
		wall_mat="ShackWall",
		trim_mat="WeatheredTimber",
		roof_mat="CorrugatedRoof",
		lean_x_deg=-2.2,
		lean_z_deg=-1.8,
		roof_sag=0.32,
		window_front_count=2,
		seed=802,
	)
	add_architectural_harbor_building(
		mb,
		center=(2.0, 5.4, 25.2),
		width=7.6,
		height=3.1,
		depth=6.2,
		wall_mat="RottingWood",
		trim_mat="WeatheredTimber",
		roof_mat="CorrugatedRoof",
		lean_x_deg=-2.8,
		lean_z_deg=-2.2,
		roof_sag=0.35,
		window_front_count=2,
		seed=803,
	)
	# Heavy double loading doors & timber lintel facing the dock on the Cannery
	mb.add_box("WeatheredTimber", (2.0, 3.15, 20.98), (2.45, 2.35, 0.16))
	mb.add_box("DarkMetal", (2.0, 3.15, 20.88), (0.06, 2.35, 0.06))
	# Cannery brick & iron chimney stack on roof with conical rain cap at (5.2, 10.75, 26.2)
	mb.add_box("LighthouseBand", (5.2, 8.6, 26.2), (0.78, 1.9, 0.78))
	mb.add_cylinder_between("RustIron", (5.2, 9.45, 26.2), (5.2, 10.58, 26.2), 0.19, 0.16, segments=8)
	mb.add_cylinder_between("RustIron", (5.2, 10.65, 26.2), (5.2, 10.92, 26.2), 0.34, 0.04, segments=8)

	# Building 3: Crooked Net-Drying Shanty (x = 13.0, y = 2.0, z = 18.0)
	add_architectural_harbor_building(
		mb,
		center=(13.0, 2.0, 18.0),
		width=5.8,
		height=3.2,
		depth=5.0,
		wall_mat="RottingWood",
		trim_mat="WeatheredTimber",
		roof_mat="CorrugatedRoof",
		lean_x_deg=-3.8,
		lean_z_deg=2.4,
		roof_sag=0.26,
		window_front_count=1,
		seed=804,
	)
	# Overhanging porch roof, crooked timber posts, net-drying racks & porch lantern
	mb.add_oriented_box("CorrugatedRoof", (13.0, 4.65, 14.6), (5.6, 0.14, 2.2), pitch_deg=6.0, roll_deg=-2.5)
	mb.add_cylinder_between("WeatheredTimber", (10.5, 1.35, 13.8), (10.4, 4.65, 13.8), 0.12, 0.10, segments=6)
	mb.add_cylinder_between("WeatheredTimber", (15.5, 1.35, 13.8), (15.4, 4.65, 13.8), 0.12, 0.10, segments=6)
	mb.add_cylinder_between("AmberGlass", (13.0, 4.55, 13.9), (13.0, 4.18, 13.9), 0.12, 0.10, segments=8)

	# --- 4. Heavy Maritime Clutter, Bollards, Lamp Posts & Overhead Catenary Cables ---
	# Iron mooring bollards with coiled WeatheredTimber mooring ropes wrapped around them
	bollard_coords: List[Tuple[float, float]] = [
		(-6.2, 4.4), (-2.0, 4.4), (2.0, 4.4), (6.2, 4.4),
		(-7.4, 10.5), (7.4, 10.5), (-7.4, 16.0), (7.4, 16.0),
	]
	for bx, bz in bollard_coords:
		mb.add_cylinder_between("RustIron", (bx, 1.38, bz), (bx, 1.84, bz), 0.16, 0.19, segments=8)
		mb.add_box("RustIron", (bx, 1.72, bz), (0.52, 0.08, 0.10))
		# Coiled mooring rope turns wrapped around bollard base + flat deck coil
		mb.add_cylinder_between("WeatheredTimber", (bx, 1.40, bz), (bx, 1.62, bz), 0.23, 0.21, segments=8)
		mb.add_cylinder_between("WeatheredTimber", (bx + 0.34, 1.38, bz + 0.24), (bx + 0.34, 1.48, bz + 0.24), 0.26, 0.22, segments=8)

	# Wooden Jib-Crane with hanging chain & cargo hook at pier end
	add_pier_jib_crane(mb, (-5.8, 1.38, 5.2))

	# Slatted wooden lobster traps stacked on pier & near Bait Shack
	lobster_placements: List[Tuple[Vec3, float]] = [
		((-5.4, 1.40, 11.4), 12.0),
		((-5.3, 1.82, 11.4), -8.0),
		((-4.2, 1.40, 11.6), 28.0),
		((5.8, 1.40, 14.8), -18.0),
		((5.8, 1.82, 14.8), 6.0),
		((-8.8, 1.62, 15.8), 35.0),
		((9.6, 0.70, 7.4), -14.0),
	]
	for l_pos, l_yaw in lobster_placements:
		add_lobster_trap(mb, l_pos, yaw_deg=l_yaw)

	# Banded wooden fish barrels
	barrel_placements: List[Tuple[Vec3, float]] = [
		((-0.2, 1.38, 20.2), 2.0),
		((0.55, 1.38, 20.4), -3.5),
		((3.8, 1.38, 20.3), 1.5),
		((6.2, 1.38, 16.2), 4.0),
		((-6.4, 1.38, 15.0), -2.5),
		((10.2, 0.68, 9.2), 3.0),
	]
	for b_pos, b_tilt in barrel_placements:
		add_fish_barrel(mb, b_pos, tilt_deg=b_tilt)

	# Dented RustIron fuel drums
	drum_placements: List[Tuple[Vec3, bool, float]] = [
		((-6.5, 1.38, 18.8), False, 0.0),
		((-5.7, 1.38, 19.1), False, 0.0),
		((-5.0, 1.38, 18.6), True, 24.0),
		((6.4, 1.38, 8.2), False, 0.0),
		((6.1, 1.38, 9.1), True, -32.0),
	]
	for d_pos, d_side, d_yaw in drum_placements:
		add_fuel_drum(mb, d_pos, on_side=d_side, yaw_deg=d_yaw)

	# 4 Crooked Wooden Lamp Posts with hanging AmberGlass lantern cages at y = 4.2m
	lamp_posts: List[Tuple[float, float, float, float]] = [
		(-7.5, 5.0, 0.22, -0.15),
		(7.5, 5.0, -0.22, -0.15),
		(-7.5, 14.0, 0.25, 0.12),
		(7.5, 18.0, -0.24, 0.14),
	]
	lamp_post_tops: List[Vec3] = []
	for lx, lz, tilt_x, tilt_z in lamp_posts:
		post_base: Vec3 = (lx, 1.35, lz)
		post_top: Vec3 = (lx + tilt_x, 4.55, lz + tilt_z)
		lamp_post_tops.append(post_top)
		arm_tip: Vec3 = (lx + tilt_x + (0.65 if lx < 0.0 else -0.65), 4.50, lz + tilt_z)
		lantern_top: Vec3 = (arm_tip[0], 4.35, arm_tip[2])
		lantern_bot: Vec3 = (arm_tip[0], 3.98, arm_tip[2])

		mb.add_cylinder_between("WeatheredTimber", post_base, post_top, 0.13, 0.09, segments=8)
		mb.add_cylinder_between("WeatheredTimber", post_top, arm_tip, 0.07, 0.06, segments=6)
		mb.add_cylinder_between("RustIron", arm_tip, lantern_top, 0.03, 0.14, segments=8)
		mb.add_cylinder_between("AmberGlass", lantern_top, lantern_bot, 0.13, 0.10, segments=8)

	# Sagging 3D Catenary Power & Lantern Lines (DarkMetal) between dock posts, Cannery, and Lighthouse
	mb.add_catenary_cable("DarkMetal", lamp_post_tops[0], lamp_post_tops[2], sag=0.68, radius=0.022, segments=12)
	mb.add_catenary_cable("DarkMetal", lamp_post_tops[1], lamp_post_tops[3], sag=0.82, radius=0.022, segments=12)
	mb.add_catenary_cable("DarkMetal", lamp_post_tops[0], lamp_post_tops[1], sag=0.95, radius=0.020, segments=12)
	mb.add_catenary_cable("DarkMetal", lamp_post_tops[2], (-10.2, 4.85, 16.5), sag=0.45, radius=0.022, segments=10)
	mb.add_catenary_cable("DarkMetal", lamp_post_tops[2], (-1.2, 8.2, 22.1), sag=0.72, radius=0.024, segments=12)
	mb.add_catenary_cable("DarkMetal", lamp_post_tops[3], (5.2, 8.2, 22.1), sag=0.65, radius=0.024, segments=12)
	mb.add_catenary_cable("DarkMetal", lamp_post_tops[3], (11.5, 4.9, 15.6), sag=0.48, radius=0.022, segments=10)
	# High-span power cable from Cannery roof pole up to the Lighthouse tower
	mb.add_cylinder_between("WeatheredTimber", (2.0, 8.2, 27.6), (2.0, 10.1, 27.6), 0.09, 0.07, segments=6)
	mb.add_catenary_cable("DarkMetal", (2.0, 10.0, 27.6), (0.0, 23.8, 40.65), sag=1.75, radius=0.026, segments=16)

	# --- 5. Architectural Lighthouse Complex (x = 0.0, y = 10.5, z = 44.0) ---
	lh_x: float = 0.0
	lh_z: float = 44.0

	# Cramped Stone Lighthouse Keeper's Cottage attached to base of tower (-X / -Z flank)
	add_architectural_harbor_building(
		mb,
		center=(-4.8, 10.4, 41.6),
		width=5.2,
		height=3.4,
		depth=4.6,
		wall_mat="LighthouseStone",
		trim_mat="WeatheredTimber",
		roof_mat="CorrugatedRoof",
		lean_x_deg=-1.2,
		lean_z_deg=-1.0,
		roof_sag=0.16,
		window_front_count=1,
		add_side_windows=False,
		seed=809,
	)
	# Heavy timber entrance door with DarkMetal iron strap hinges on Keeper's Cottage
	mb.add_box("WeatheredTimber", (-6.1, 11.55, 39.26), (1.15, 2.10, 0.14))
	mb.add_box("LighthouseStone", (-6.1, 12.68, 39.22), (1.38, 0.22, 0.24))
	mb.add_box("DarkMetal", (-6.42, 11.95, 39.18), (0.45, 0.06, 0.04))
	mb.add_box("DarkMetal", (-6.42, 11.15, 39.18), (0.45, 0.06, 0.04))

	# Octagonal / 16-sided stepped stone plinth seated into headland crag (y = 8.4m to 10.7m)
	mb.add_cylinder_between("LighthouseStone", (lh_x, 8.4, lh_z), (lh_x, 10.7, lh_z), 5.1, 4.55, segments=16)

	# 26m Tapered Masonry Tower with 24 Recessed Masonry Courses (y = 10.5m to 31.1m)
	num_courses: int = 24
	tower_y0: float = 10.5
	tower_y1: float = 31.1
	course_step_h: float = (tower_y1 - tower_y0) / float(num_courses)
	for c_i in range(num_courses):
		cy0: float = tower_y0 + float(c_i) * course_step_h
		cy1: float = cy0 + course_step_h * 0.88
		cy_top: float = cy0 + course_step_h
		u0_c: float = float(c_i) / float(num_courses)
		u1_c: float = float(c_i + 1) / float(num_courses)
		r0_c: float = 4.22 - u0_c * (4.22 - 2.62)
		r1_c: float = 4.22 - u1_c * (4.22 - 2.62)

		band_mat: str = "LighthouseBand" if (17.4 <= cy0 <= 24.8) else "LighthouseStone"
		# Main ashlar masonry course block
		mb.add_cylinder_between(band_mat, (lh_x, cy0, lh_z), (lh_x, cy1, lh_z), r0_c, r1_c, segments=16, cap_start=False, cap_end=False)
		# Recessed mortar shadow-groove course ring (inset by 3.5cm)
		mb.add_cylinder_between(
			band_mat,
			(lh_x, cy1, lh_z),
			(lh_x, cy_top, lh_z),
			r1_c - 0.035,
			r1_c - 0.035,
			segments=16,
			cap_start=True,
			cap_end=True,
		)

	# Vertical Slit Windows with Projecting Stone Lintels, Sills & DarkMetal Muntin Bars
	slit_windows: List[Tuple[float, float, float]] = [
		(13.6, 0.0, 3.96),
		(17.2, -0.48, 3.70),
		(20.8, 0.52, 3.42),
		(25.2, -0.52, 3.08),
		(28.8, 0.0, 2.80),
	]
	for sy, s_ang, s_rad in slit_windows:
		sx_pos: float = lh_x + math.sin(s_ang) * s_rad
		sz_pos: float = lh_z - math.cos(s_ang) * s_rad
		yaw_w: float = -math.degrees(s_ang)
		# Projecting stone lintel header & sill block
		mb.add_oriented_box("LighthouseStone", (sx_pos, sy + 0.78, sz_pos), (0.68, 0.18, 0.48), yaw_deg=yaw_w)
		mb.add_oriented_box("LighthouseStone", (sx_pos, sy - 0.78, sz_pos), (0.68, 0.16, 0.48), yaw_deg=yaw_w)
		# Glowing AmberGlass slit pane & iron cross-bars
		mb.add_oriented_box("AmberGlass", (sx_pos, sy, sz_pos), (0.42, 1.38, 0.32), yaw_deg=yaw_w)
		mb.add_oriented_box("DarkMetal", (sx_pos, sy, sz_pos), (0.46, 0.06, 0.36), yaw_deg=yaw_w)
		mb.add_oriented_box("DarkMetal", (sx_pos, sy + 0.34, sz_pos), (0.46, 0.05, 0.36), yaw_deg=yaw_w)
		mb.add_oriented_box("DarkMetal", (sx_pos, sy - 0.34, sz_pos), (0.46, 0.05, 0.36), yaw_deg=yaw_w)

	# Flared Corbelled Stonework (y = 30.8m to 31.85m) supporting the upper Gallery Platform
	mb.add_cylinder_between("LighthouseStone", (lh_x, 30.85, lh_z), (lh_x, 31.35, lh_z), 2.64, 2.95, segments=16)
	mb.add_cylinder_between("LighthouseStone", (lh_x, 31.35, lh_z), (lh_x, 31.80, lh_z), 2.95, 3.28, segments=16)
	for cb_idx in range(16):
		cb_ang: float = (2.0 * math.pi * float(cb_idx)) / 16.0
		cb_x: float = lh_x + math.cos(cb_ang) * 2.95
		cb_z: float = lh_z + math.sin(cb_ang) * 2.95
		mb.add_cylinder_between(
			"LighthouseStone",
			(lh_x + math.cos(cb_ang) * 2.58, 30.65, lh_z + math.sin(cb_ang) * 2.58),
			(cb_x, 31.80, cb_z),
			0.14,
			0.22,
			segments=4,
		)

	# Upper Iron Gallery Platform & Dual-Rail Balcony at y = 32.0m
	mb.add_cylinder_between("RustIron", (lh_x, 31.80, lh_z), (lh_x, 32.22, lh_z), 3.28, 3.42, segments=16)
	for r_idx in range(16):
		ang: float = (2.0 * math.pi * float(r_idx)) / 16.0
		rx_p: float = lh_x + math.cos(ang) * 3.26
		rz_p: float = lh_z + math.sin(ang) * 3.26
		mb.add_cylinder_between("RustIron", (rx_p, 32.22, rz_p), (rx_p, 33.30, rz_p), 0.05, 0.045, segments=6)

		next_ang: float = (2.0 * math.pi * float((r_idx + 1) % 16)) / 16.0
		nx_p: float = lh_x + math.cos(next_ang) * 3.26
		nz_p: float = lh_z + math.sin(next_ang) * 3.26
		mb.add_cylinder_between("RustIron", (rx_p, 32.75, rz_p), (nx_p, 32.75, nz_p), 0.038, 0.038, segments=5)
		mb.add_cylinder_between("RustIron", (rx_p, 33.26, rz_p), (nx_p, 33.26, nz_p), 0.045, 0.045, segments=6)

	# Cylindrical BeaconLens Lantern Room (y = 32.2m to 35.2m) with Vertical & Horizontal Iron Lattice Ribs
	mb.add_cylinder_between("BeaconLens", (lh_x, 32.2, lh_z), (lh_x, 35.2, lh_z), 2.14, 2.14, segments=16)
	# 3 Horizontal iron glazing rings around the lantern room
	for ring_y in (32.32, 33.70, 35.08):
		mb.add_cylinder_between("DarkMetal", (lh_x, ring_y - 0.05, lh_z), (lh_x, ring_y + 0.05, lh_z), 2.21, 2.21, segments=16)
	# 16 Vertical & diagonal diamond lattice ribs framing the lantern glass
	for lat_idx in range(16):
		ang0: float = (2.0 * math.pi * float(lat_idx)) / 16.0
		ang1: float = (2.0 * math.pi * float((lat_idx + 1) % 16)) / 16.0
		lx0: float = lh_x + math.cos(ang0) * 2.19
		lz0: float = lh_z + math.sin(ang0) * 2.19
		lx1: float = lh_x + math.cos(ang1) * 2.19
		lz1: float = lh_z + math.sin(ang1) * 2.19
		# Vertical astragal rib
		mb.add_cylinder_between("DarkMetal", (lx0, 32.22, lz0), (lx0, 35.18, lz0), 0.04, 0.04, segments=5)
		# Diagonal lattice rib
		if lat_idx % 2 == 0:
			mb.add_cylinder_between("DarkMetal", (lx0, 32.32, lz0), (lx1, 35.08, lz1), 0.028, 0.028, segments=4)

	# Copper-Patina Domed Cupola Roof (MossyCrag patina dome + DarkMetal ribs), Weathervane & Lightning Rod
	mb.add_cylinder_between("RustIron", (lh_x, 35.12, lh_z), (lh_x, 35.35, lh_z), 2.52, 2.40, segments=16)
	mb.add_cylinder_between("MossyCrag", (lh_x, 35.35, lh_z), (lh_x, 35.85, lh_z), 2.36, 1.72, segments=16)
	mb.add_cylinder_between("MossyCrag", (lh_x, 35.85, lh_z), (lh_x, 36.25, lh_z), 1.72, 0.68, segments=16)
	mb.add_cylinder_between("MossyCrag", (lh_x, 36.25, lh_z), (lh_x, 36.45, lh_z), 0.68, 0.18, segments=16)
	# Radial seam ribs on cupola dome
	for d_i in range(8):
		d_ang: float = (2.0 * math.pi * float(d_i)) / 8.0
		dx_c: float = math.cos(d_ang)
		dz_c: float = math.sin(d_ang)
		mb.add_cylinder_between(
			"DarkMetal",
			(lh_x + dx_c * 2.38, 35.35, lh_z + dz_c * 2.38),
			(lh_x + dx_c * 0.68, 36.26, lh_z + dz_c * 0.68),
			0.035,
			0.030,
			segments=4,
		)
	# Ventilator ball finial, Weathervane crossbars + pointer, and Lightning Rod spire (to y = 37.5m)
	mb.add_cylinder_between("DarkMetal", (lh_x, 36.42, lh_z), (lh_x, 36.72, lh_z), 0.24, 0.24, segments=10)
	mb.add_cylinder_between("DarkMetal", (lh_x, 36.72, lh_z), (lh_x, 37.55, lh_z), 0.05, 0.015, segments=6)
	# Weathervane cardinal arms & directional arrow at y = 37.05m
	mb.add_cylinder_between("DarkMetal", (lh_x - 0.85, 37.05, lh_z), (lh_x + 0.85, 37.05, lh_z), 0.025, 0.025, segments=5)
	mb.add_cylinder_between("DarkMetal", (lh_x, 37.05, lh_z - 0.95), (lh_x, 37.05, lh_z + 0.85), 0.025, 0.025, segments=5)
	mb.add_box("RustIron", (lh_x, 37.08, lh_z + 0.72), (0.04, 0.22, 0.36))

	return mb


def build_rock_razor_cluster() -> FacetedMeshBuilder:
	mb: FacetedMeshBuilder = FacetedMeshBuilder()
	blades: List[Tuple[float, float, float, float, float, float, float, float, int, int]] = [
		(0.0, -3.0, 0.0, 2.8, 2.1, 17.8, 19.0, -14.0, 7, 101),
		(-5.2, -3.0, -3.4, 2.4, 1.8, 14.5, -24.0, -16.0, 6, 102),
		(5.4, -3.0, -2.8, 2.5, 1.9, 15.6, 26.0, -12.0, 7, 103),
		(-4.6, -3.0, 4.5, 2.2, 1.7, 12.2, -18.0, 22.0, 6, 104),
		(4.8, -3.0, 4.2, 2.1, 1.6, 11.0, 21.0, 18.0, 6, 105),
		(0.8, -3.0, -6.2, 1.9, 1.5, 9.6, 8.0, -28.0, 6, 106),
	]
	for bx, by, bz, rx, rz, h, tx, tz, sides, seed in blades:
		add_jagged_spire(
			mb,
			base_center=(bx, by, bz),
			base_rx=rx,
			base_rz=rz,
			height=h,
			tilt_x_deg=tx,
			tilt_z_deg=tz,
			sides=sides,
			tiers=7,
			seed=seed,
			allow_moss=False,
			stepped_terraces=False,
		)
	return mb


def build_rock_jagged_arch() -> FacetedMeshBuilder:
	mb: FacetedMeshBuilder = FacetedMeshBuilder()
	add_jagged_spire(
		mb,
		base_center=(-12.5, -3.5, 0.0),
		base_rx=5.2,
		base_rz=6.0,
		height=30.5,
		tilt_x_deg=8.0,
		tilt_z_deg=-4.0,
		sides=8,
		tiers=8,
		seed=201,
		allow_moss=True,
	)
	add_jagged_spire(
		mb,
		base_center=(12.5, -3.5, 0.0),
		base_rx=5.2,
		base_rz=6.0,
		height=28.5,
		tilt_x_deg=-9.0,
		tilt_z_deg=5.0,
		sides=8,
		tiers=8,
		seed=202,
		allow_moss=True,
	)

	arch_segments: int = 12
	ring_sides: int = 7
	arch_rings: List[List[Vec3]] = []
	arch_centers: List[Vec3] = []

	for i in range(arch_segments + 1):
		u: float = float(i) / float(arch_segments)
		ang: float = math.pi * (1.0 - u)
		cx: float = math.cos(ang) * 11.8
		cy: float = 4.5 + math.sin(ang) * 14.5
		cz: float = math.sin(u * math.pi * 2.0) * 1.4
		arch_centers.append((cx, cy, cz))

		rx_tube: float = 3.2 - 0.6 * math.sin(ang)
		rz_tube: float = 4.2 - 0.8 * math.sin(ang)

		ring: List[Vec3] = []
		for s in range(ring_sides):
			theta: float = (2.0 * math.pi * float(s)) / float(ring_sides)
			n_disp: float = 1.0 + 0.18 * ridge_noise(cx, cy + math.sin(theta) * 2.0, cz + math.cos(theta) * 2.0, 210 + s)
			vy_off: float = math.sin(theta) * rx_tube * n_disp
			vz_off: float = math.cos(theta) * rz_tube * n_disp
			vx_off: float = -math.sin(theta) * math.cos(ang) * 1.4
			ring.append((cx + vx_off, cy + vy_off, cz + vz_off))
		arch_rings.append(ring)

	for i in range(arch_segments):
		r0: List[Vec3] = arch_rings[i]
		r1: List[Vec3] = arch_rings[i + 1]
		c_mid: Vec3 = v_scale(v_add(arch_centers[i], arch_centers[i + 1]), 0.5)
		for s in range(ring_sides):
			ns: int = (s + 1) % ring_sides
			p00: Vec3 = r0[s]
			p10: Vec3 = r0[ns]
			p11: Vec3 = r1[ns]
			p01: Vec3 = r1[s]
			face_center: Vec3 = v_scale(v_add(v_add(p00, p10), v_add(p11, p01)), 0.25)
			out_hint: Vec3 = v_sub(face_center, c_mid)
			mat: str = select_rock_material(face_center[1], 220 + i * 5 + s, allow_moss=True)
			mb.add_tri(mat, p00, p10, p11, out_hint)
			mb.add_tri(mat, p00, p11, p01, out_hint)

	stalactites: List[Tuple[float, float, float, float, int]] = [
		(-4.2, 16.2, -0.6, -4.2, 231),
		(-1.4, 17.5, 0.5, -4.8, 232),
		(1.8, 17.3, -0.4, -4.5, 233),
		(4.5, 15.8, 0.7, -3.9, 234),
	]
	for sx, sy, sz, neg_h, s_seed in stalactites:
		add_jagged_spire(
			mb,
			base_center=(sx, sy, sz),
			base_rx=1.15,
			base_rz=1.15,
			height=neg_h,
			tilt_x_deg=4.0,
			tilt_z_deg=-3.0,
			sides=5,
			tiers=4,
			seed=s_seed,
			allow_moss=False,
		)

	flank_spikes: List[Tuple[float, float, float, float, float, int]] = [
		(-16.2, -3.0, -5.5, 2.2, 11.5, 241),
		(-15.5, -3.0, 6.0, 2.0, 9.8, 242),
		(16.0, -3.0, -5.8, 2.3, 12.2, 243),
		(15.4, -3.0, 5.6, 2.1, 10.4, 244),
	]
	for fx, fy, fz, fr, fh, f_seed in flank_spikes:
		add_jagged_spire(
			mb,
			base_center=(fx, fy, fz),
			base_rx=fr,
			base_rz=fr * 0.85,
			height=fh,
			tilt_x_deg=16.0 if fx < 0.0 else -16.0,
			tilt_z_deg=12.0,
			sides=6,
			tiers=5,
			seed=f_seed,
			allow_moss=False,
		)

	return mb


def build_rock_basalt_monolith() -> FacetedMeshBuilder:
	mb: FacetedMeshBuilder = FacetedMeshBuilder()
	columns: List[Tuple[float, float, float, float, float, float, int]] = [
		(0.0, 0.0, 4.2, 41.0, 2.5, -2.0, 301),
		(-4.8, -3.2, 3.4, 33.5, -4.0, -3.5, 302),
		(4.6, -2.8, 3.5, 31.0, 5.0, -3.0, 303),
		(-4.2, 4.4, 3.2, 27.5, -5.0, 4.5, 304),
		(4.5, 4.0, 3.1, 25.0, 4.5, 5.0, 305),
		(-8.2, 0.6, 2.6, 19.5, -9.0, 2.0, 306),
		(8.4, -0.4, 2.7, 21.0, 10.0, -2.0, 307),
		(0.4, -7.6, 2.5, 17.5, 2.0, -11.0, 308),
		(-0.6, 7.8, 2.4, 16.0, -2.0, 10.0, 309),
	]
	for cx, cz, rad, h, tx, tz, seed in columns:
		add_jagged_spire(
			mb,
			base_center=(cx, -3.0, cz),
			base_rx=rad,
			base_rz=rad * 0.92,
			height=h,
			tilt_x_deg=tx,
			tilt_z_deg=tz,
			sides=6,
			tiers=9,
			seed=seed,
			allow_moss=True,
			stepped_terraces=True,
		)
	return mb


def build_island_large_archipelago() -> FacetedMeshBuilder:
	mb: FacetedMeshBuilder = FacetedMeshBuilder()
	peaks: List[Tuple[float, float, float, float, float, float, float, int]] = [
		(0.0, 0.0, 28.0, 24.0, 45.0, 3.0, -2.0, 401),
		(-22.0, -14.0, 18.0, 16.0, 32.0, -6.0, -5.0, 402),
		(24.0, 12.0, 19.0, 15.0, 29.0, 7.0, 4.0, 403),
		(-16.0, 20.0, 14.0, 13.0, 22.0, -5.0, 8.0, 404),
		(18.0, -19.0, 13.0, 11.0, 20.0, 8.0, -7.0, 405),
	]
	for px, pz, rx, rz, h, tx, tz, seed in peaks:
		add_jagged_spire(
			mb,
			base_center=(px, -4.0, pz),
			base_rx=rx,
			base_rz=rz,
			height=h,
			tilt_x_deg=tx,
			tilt_z_deg=tz,
			sides=10,
			tiers=8,
			seed=seed,
			allow_moss=True,
			stepped_terraces=True,
		)
	return mb


def build_island_medium_crag() -> FacetedMeshBuilder:
	mb: FacetedMeshBuilder = FacetedMeshBuilder()
	peaks: List[Tuple[float, float, float, float, float, float, float, int]] = [
		(0.0, 0.0, 16.5, 14.0, 29.5, 5.0, -4.0, 501),
		(-11.5, 6.5, 10.5, 9.5, 21.0, -8.0, 6.0, 502),
		(10.8, -7.2, 9.5, 8.5, 18.5, 9.0, -7.0, 503),
	]
	for px, pz, rx, rz, h, tx, tz, seed in peaks:
		add_jagged_spire(
			mb,
			base_center=(px, -3.5, pz),
			base_rx=rx,
			base_rz=rz,
			height=h,
			tilt_x_deg=tx,
			tilt_z_deg=tz,
			sides=9,
			tiers=7,
			seed=seed,
			allow_moss=True,
			stepped_terraces=False,
		)
	return mb


def build_island_sea_stack() -> FacetedMeshBuilder:
	mb: FacetedMeshBuilder = FacetedMeshBuilder()
	add_jagged_spire(
		mb,
		base_center=(0.0, -3.5, 0.0),
		base_rx=9.5,
		base_rz=8.2,
		height=35.0,
		tilt_x_deg=6.0,
		tilt_z_deg=-5.0,
		sides=8,
		tiers=8,
		seed=601,
		allow_moss=True,
		stepped_terraces=True,
	)
	add_jagged_spire(
		mb,
		base_center=(6.8, -3.5, 4.2),
		base_rx=4.5,
		base_rz=3.8,
		height=19.0,
		tilt_x_deg=14.0,
		tilt_z_deg=9.0,
		sides=6,
		tiers=6,
		seed=602,
		allow_moss=False,
		stepped_terraces=False,
	)
	return mb


def write_world_mtl(mtl_path: str) -> None:
	lines: List[str] = [
		"# Procedural World, Wharf Settlement & Jagged Rock Formation Material Library",
		"",
		"newmtl TidalWetRock",
		"Kd 0.05 0.07 0.08",
		"Ks 0.45 0.48 0.50",
		"Ns 48.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl BasaltCliff",
		"Kd 0.11 0.13 0.15",
		"Ks 0.18 0.20 0.22",
		"Ns 24.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl SharpObsidian",
		"Kd 0.07 0.08 0.10",
		"Ks 0.35 0.38 0.42",
		"Ns 56.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl MossyCrag",
		"Kd 0.09 0.14 0.11",
		"Ks 0.08 0.10 0.08",
		"Ns 12.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl WeatheredTimber",
		"Kd 0.22 0.17 0.13",
		"Ks 0.06 0.05 0.04",
		"Ns 10.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl RottingWood",
		"Kd 0.16 0.14 0.12",
		"Ks 0.05 0.05 0.04",
		"Ns 8.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl ShackWall",
		"Kd 0.28 0.26 0.23",
		"Ks 0.08 0.08 0.07",
		"Ns 12.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl CorrugatedRoof",
		"Kd 0.20 0.15 0.13",
		"Ks 0.22 0.18 0.16",
		"Ns 28.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl RustIron",
		"Kd 0.14 0.11 0.10",
		"Ks 0.25 0.22 0.20",
		"Ns 36.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl DarkMetal",
		"Kd 0.08 0.09 0.10",
		"Ks 0.32 0.34 0.36",
		"Ns 48.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl AmberGlass",
		"Kd 1.00 0.68 0.28",
		"Ke 0.95 0.58 0.20",
		"Ks 0.50 0.45 0.35",
		"Ns 64.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl LighthouseStone",
		"Kd 0.38 0.40 0.42",
		"Ks 0.12 0.12 0.13",
		"Ns 18.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl LighthouseBand",
		"Kd 0.45 0.12 0.10",
		"Ks 0.14 0.10 0.10",
		"Ns 20.0",
		"d 1.0",
		"illum 2",
		"",
		"newmtl BeaconLens",
		"Kd 1.00 0.90 0.65",
		"Ke 1.00 0.85 0.55",
		"Ks 0.70 0.65 0.55",
		"Ns 96.0",
		"d 1.0",
		"illum 2",
		"",
	]
	with open(mtl_path, "w", encoding="utf-8", newline="\n") as f:
		f.write("\n".join(lines))


def write_obj_file(obj_path: str, object_name: str, mtl_filename: str, mb: FacetedMeshBuilder) -> int:
	lines: List[str] = [
		f"# Procedural 3D {object_name} Wavefront OBJ",
		f"mtllib {mtl_filename}",
		f"o {object_name}",
		"",
	]
	for vx, vy, vz in mb.vertices:
		lines.append(f"v {vx:.4f} {vy:.4f} {vz:.4f}")
	lines.append("")

	for vx, vy, vz in mb.vertices:
		u_coord: float = (vx + vz) * 0.25
		v_coord: float = vy * 0.25
		lines.append(f"vt {u_coord:.4f} {v_coord:.4f}")
	lines.append("")

	for nx, ny, nz in mb.normals:
		lines.append(f"vn {nx:.4f} {ny:.4f} {nz:.4f}")
	lines.append("")

	total_tris: int = 0
	for mat in MATERIAL_ORDER:
		faces = mb.faces_by_mat[mat]
		if not faces:
			continue
		total_tris += len(faces)
		lines.append(f"g {mat}")
		lines.append(f"usemtl {mat}")
		lines.append("s off")
		for (v0, n0), (v1, n1), (v2, n2) in faces:
			lines.append(f"f {v0}/{v0}/{n0} {v1}/{v1}/{n1} {v2}/{v2}/{n2}")
		lines.append("")

	with open(obj_path, "w", encoding="utf-8", newline="\n") as f:
		f.write("\n".join(lines))
	return total_tris


def main() -> None:
	project_root: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	output_dir: str = os.path.join(project_root, "assets", "models")
	os.makedirs(output_dir, exist_ok=True)

	mtl_filename: str = "world_materials.mtl"
	mtl_path: str = os.path.join(output_dir, mtl_filename)
	write_world_mtl(mtl_path)
	print(f"Generated {mtl_path}")

	assets: List[Tuple[str, str, FacetedMeshBuilder]] = [
		("wharf_island.obj", "WharfIsland", build_wharf_island()),
		("rock_razor_cluster.obj", "RockRazorCluster", build_rock_razor_cluster()),
		("rock_jagged_arch.obj", "RockJaggedArch", build_rock_jagged_arch()),
		("rock_basalt_monolith.obj", "RockBasaltMonolith", build_rock_basalt_monolith()),
		("island_large_archipelago.obj", "IslandLargeArchipelago", build_island_large_archipelago()),
		("island_medium_crag.obj", "IslandMediumCrag", build_island_medium_crag()),
		("island_sea_stack.obj", "IslandSeaStack", build_island_sea_stack()),
	]

	for filename, obj_name, builder in assets:
		out_path: str = os.path.join(output_dir, filename)
		tris: int = write_obj_file(out_path, obj_name, mtl_filename, builder)
		print(f"Generated {out_path}: {len(builder.vertices)} verts, {len(builder.normals)} normals, {tris} tris")


if __name__ == "__main__":
	main()
