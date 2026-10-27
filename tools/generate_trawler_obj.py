#!/usr/bin/env python3
"""
Procedural 3D Fishing Trawler Wavefront .obj and .mtl generator for Godot 4.

Coordinate System (Godot 4):
  -Z : Forward (Bow)
  +Z : Aft (Stern)
  +Y : Up
  -X : Port (Left)
  +X : Starboard (Right)

Hull Length: ~4.8m (Hull z = -2.40 to +2.20, Stern A-frame overhang to z = +2.50)
Beam Width : 2.0m (x = -1.00 to +1.00)
"""

import math
import os
from typing import Dict, List, Optional, Tuple

Vec3 = Tuple[float, float, float]


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


MATERIAL_ORDER: List[str] = [
    "HullIron",
    "RustKeel",
    "DeckWood",
    "CabinPaint",
    "DarkMetal",
    "WindowGlow",
]


class MeshBuilder:
    """Collects indexed vertices, normals, and per-material CCW triangles."""

    def __init__(self) -> None:
        self.vertices: List[Vec3] = []
        self.vertex_map: Dict[Tuple[int, int, int], int] = {}
        self.normals: List[Vec3] = []
        self.normal_map: Dict[Tuple[int, int, int], int] = {}
        self.faces_by_mat: Dict[str, List[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]]] = {
            mat: [] for mat in MATERIAL_ORDER
        }

    def _get_vertex_index(self, v: Vec3) -> int:
        key = (round(v[0] * 10000), round(v[1] * 10000), round(v[2] * 10000))
        idx = self.vertex_map.get(key)
        if idx is None:
            self.vertices.append(v)
            idx = len(self.vertices)
            self.vertex_map[key] = idx
        return idx

    def _get_normal_index(self, n: Vec3) -> int:
        unit_n = v_norm(n)
        key = (round(unit_n[0] * 10000), round(unit_n[1] * 10000), round(unit_n[2] * 10000))
        idx = self.normal_map.get(key)
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
        e1 = v_sub(p1, p0)
        e2 = v_sub(p2, p0)
        raw_cross = v_cross(e1, e2)
        if v_len(raw_cross) < 1e-8:
            return  # Skip degenerate triangle

        if outward_hint is not None and v_dot(raw_cross, outward_hint) < 0.0:
            p1, p2 = p2, p1
            raw_cross = v_scale(raw_cross, -1.0)

        n_idx = self._get_normal_index(raw_cross)
        i0 = self._get_vertex_index(p0)
        i1 = self._get_vertex_index(p1)
        i2 = self._get_vertex_index(p2)
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

        # 8 corners
        x0, x1 = cx - hx, cx + hx
        y0, y1 = cy - hy, cy + hy
        z0, z1 = cz - hz, cz + hz

        # Front (-Z)
        self.add_quad(
            material,
            (x0, y0, z0),
            (x0, y1, z0),
            (x1, y1, z0),
            (x1, y0, z0),
            (0.0, 0.0, -1.0),
        )
        # Back (+Z)
        self.add_quad(
            material,
            (x0, y0, z1),
            (x1, y0, z1),
            (x1, y1, z1),
            (x0, y1, z1),
            (0.0, 0.0, 1.0),
        )
        # Port (-X)
        self.add_quad(
            material,
            (x0, y0, z1),
            (x0, y1, z1),
            (x0, y1, z0),
            (x0, y0, z0),
            (-1.0, 0.0, 0.0),
        )
        # Starboard (+X)
        self.add_quad(
            material,
            (x1, y0, z0),
            (x1, y1, z0),
            (x1, y1, z1),
            (x1, y0, z1),
            (1.0, 0.0, 0.0),
        )
        # Top (+Y)
        if not skip_top:
            self.add_quad(
                material,
                (x0, y1, z0),
                (x0, y1, z1),
                (x1, y1, z1),
                (x1, y1, z0),
                (0.0, 1.0, 0.0),
            )
        # Bottom (-Y)
        if not skip_bottom:
            self.add_quad(
                material,
                (x0, y0, z1),
                (x0, y0, z0),
                (x1, y0, z0),
                (x1, y0, z1),
                (0.0, -1.0, 0.0),
            )

    def add_cylinder_between(
        self,
        material: str,
        p_start: Vec3,
        p_end: Vec3,
        r_start: float,
        r_end: float,
        segments: int = 12,
        cap_start: bool = True,
        cap_end: bool = True,
    ) -> None:
        axis = v_sub(p_end, p_start)
        axis_u = v_norm(axis)

        # Pick an arbitrary vector not parallel to axis_u
        ref = (0.0, 0.0, 1.0) if abs(axis_u[1]) > 0.9 else (0.0, 1.0, 0.0)
        tangent = v_norm(v_cross(axis_u, ref))
        bitangent = v_norm(v_cross(axis_u, tangent))

        ring_start: List[Vec3] = []
        ring_end: List[Vec3] = []
        radial_dirs: List[Vec3] = []

        for i in range(segments):
            angle = (2.0 * math.pi * i) / segments
            ca = math.cos(angle)
            sa = math.sin(angle)
            rad_dir = v_norm(v_add(v_scale(tangent, ca), v_scale(bitangent, sa)))
            radial_dirs.append(rad_dir)
            ring_start.append(v_add(p_start, v_scale(rad_dir, r_start)))
            ring_end.append(v_add(p_end, v_scale(rad_dir, r_end)))

        for i in range(segments):
            ni = (i + 1) % segments
            mid_rad = v_add(radial_dirs[i], radial_dirs[ni])
            self.add_quad(
                material,
                ring_start[i],
                ring_end[i],
                ring_end[ni],
                ring_start[ni],
                mid_rad,
            )
            if cap_start and r_start > 1e-5:
                self.add_tri(
                    material,
                    p_start,
                    ring_start[ni],
                    ring_start[i],
                    v_scale(axis_u, -1.0),
                )
            if cap_end and r_end > 1e-5:
                self.add_tri(
                    material,
                    p_end,
                    ring_end[i],
                    ring_end[ni],
                    axis_u,
                )


def build_trawler_hull(mb: MeshBuilder) -> None:
    """
    Generates a 12-station lofted fishing trawler hull:
      - Sharp pointed stem at z = -2.40
      - Wide flared midship around z = -0.35 .. +0.65 (max beam = 2.0m, half-beam = 1.0m)
      - Flat transom stern at z = +2.20
      - Deep V-bottom keel & lower chine below waterline (RustKeel)
      - Upper flared hull sides, gunwale cap, & inner bulwark walls (HullIron)
      - Recessed flat timber deck at y = 0.35 (DeckWood)
    """
    deck_y: float = 0.35
    waterline_y: float = 0.08
    bulwark_thickness: float = 0.11

    # 12 longitudinal stations:
    # (z, keel_y, keel_half_w, chine_y, chine_w, wl_w, mid_y, mid_w, sheer_y, sheer_w)
    stations: List[Tuple[float, float, float, float, float, float, float, float, float, float]] = [
        # 0: Pointed bow stem (z = -2.40)
        (-2.40, 0.02, 0.00, 0.05, 0.00, 0.01, 0.48, 0.02, 0.94, 0.03),
        # 1: Forefoot entry (z = -2.12)
        (-2.12, -0.26, 0.03, -0.10, 0.16, 0.24, 0.45, 0.35, 0.90, 0.46),
        # 2: Forward bow flare (z = -1.78)
        (-1.78, -0.38, 0.05, -0.15, 0.34, 0.46, 0.43, 0.62, 0.86, 0.75),
        # 3: Forward shoulder (z = -1.35)
        (-1.35, -0.43, 0.06, -0.18, 0.54, 0.68, 0.41, 0.82, 0.81, 0.92),
        # 4: Wheelhouse front (z = -0.85)
        (-0.85, -0.45, 0.07, -0.20, 0.68, 0.82, 0.39, 0.93, 0.76, 0.98),
        # 5: Midship forward (z = -0.35)
        (-0.35, -0.45, 0.07, -0.20, 0.74, 0.88, 0.38, 0.97, 0.72, 1.00),
        # 6: Midship aft (z = +0.15)
        (0.15, -0.45, 0.07, -0.20, 0.75, 0.89, 0.37, 0.97, 0.69, 1.00),
        # 7: Working deck forward (z = +0.65)
        (0.65, -0.44, 0.07, -0.19, 0.73, 0.87, 0.37, 0.95, 0.67, 0.98),
        # 8: Working deck mid (z = +1.10)
        (1.10, -0.42, 0.06, -0.17, 0.69, 0.83, 0.37, 0.91, 0.66, 0.94),
        # 9: Aft quarter (z = +1.50)
        (1.50, -0.39, 0.06, -0.14, 0.64, 0.78, 0.38, 0.86, 0.67, 0.89),
        # 10: Near stern (z = +1.88)
        (1.88, -0.35, 0.05, -0.11, 0.58, 0.72, 0.39, 0.81, 0.69, 0.84),
        # 11: Transom stern (z = +2.20)
        (2.20, -0.30, 0.05, -0.08, 0.52, 0.66, 0.40, 0.75, 0.71, 0.78),
    ]

    # Precompute cross-section profile points for each station
    # Profile indices on each side (0..6):
    #   0: Keel center (x = 0, y = keel_y)
    #   1: Keel skeg edge (x = keel_half_w, y = keel_y)
    #   2: Lower bilge chine (x = chine_w, y = chine_y)
    #   3: Waterline chine (x = wl_w, y = waterline_y)  <-- boundary between RustKeel and HullIron
    #   4: Mid flare chine (x = mid_w, y = mid_y)
    #   5: Outer gunwale sheer (x = sheer_w, y = sheer_y)
    #   6: Inner gunwale top (x = inner_w, y = sheer_y)
    #   7: Inner deck edge (x = inner_deck_w, y = deck_y)
    st_port: List[List[Vec3]] = []
    st_stbd: List[List[Vec3]] = []

    for st in stations:
        z, keel_y, keel_w, chine_y, chine_w, wl_w, mid_y, mid_w, sheer_y, sheer_w = st
        inner_w = max(0.0, sheer_w - bulwark_thickness)
        inner_deck_w = max(0.0, mid_w - bulwark_thickness * 0.85)

        pts_stbd: List[Vec3] = [
            (0.0, keel_y, z),
            (keel_w, keel_y, z),
            (chine_w, chine_y, z),
            (wl_w, waterline_y, z),
            (mid_w, mid_y, z),
            (sheer_w, sheer_y, z),
            (inner_w, sheer_y, z),
            (inner_deck_w, deck_y, z),
        ]
        pts_port: List[Vec3] = [(-p[0], p[1], p[2]) for p in pts_stbd]
        st_stbd.append(pts_stbd)
        st_port.append(pts_port)

    # Loft between consecutive stations i and i+1
    num_stations = len(stations)
    for i in range(num_stations - 1):
        s0_r = st_stbd[i]
        s1_r = st_stbd[i + 1]
        s0_l = st_port[i]
        s1_l = st_port[i + 1]

        # Lower hull bands (0->1, 1->2, 2->3) use RustKeel
        for band in (0, 1, 2):
            out_r = (0.3, -1.0, 0.0) if band == 0 else (1.0, -0.45, 0.0)
            out_l = (-0.3, -1.0, 0.0) if band == 0 else (-1.0, -0.45, 0.0)
            mb.add_quad("RustKeel", s0_r[band], s0_r[band + 1], s1_r[band + 1], s1_r[band], out_r)
            mb.add_quad("RustKeel", s0_l[band + 1], s0_l[band], s1_l[band], s1_l[band + 1], out_l)

        # Upper hull outer bands (3->4, 4->5) use HullIron
        for band in (3, 4):
            out_r = (1.0, -0.15, 0.0)
            out_l = (-1.0, -0.15, 0.0)
            mb.add_quad("HullIron", s0_r[band], s0_r[band + 1], s1_r[band + 1], s1_r[band], out_r)
            mb.add_quad("HullIron", s0_l[band + 1], s0_l[band], s1_l[band], s1_l[band + 1], out_l)

        # Gunwale top cap (5->6) uses HullIron (outward +Y)
        mb.add_quad("HullIron", s0_r[5], s0_r[6], s1_r[6], s1_r[5], (0.0, 1.0, 0.0))
        mb.add_quad("HullIron", s0_l[6], s0_l[5], s1_l[5], s1_l[6], (0.0, 1.0, 0.0))

        # Inner bulwark wall (6->7) uses HullIron (facing inward toward centerline)
        if i >= 1:
            mb.add_quad("HullIron", s0_r[6], s0_r[7], s1_r[7], s1_r[6], (-1.0, 0.1, 0.0))
            mb.add_quad("HullIron", s0_l[7], s0_l[6], s1_l[6], s1_l[7], (1.0, 0.1, 0.0))
        else:
            # Bow peak foredeck cover between station 0 and station 1
            mb.add_quad("HullIron", s0_l[5], s0_r[5], s1_r[6], s1_l[6], (0.0, 1.0, 0.0))
            # Forward breast-hook bulkhead at station 1 dropping from inner sheer to deck_y
            mb.add_quad("HullIron", s1_l[6], s1_r[6], s1_r[7], s1_l[7], (0.0, 0.2, 1.0))

        # Recessed flat DeckWood floor at y = 0.35 (from station 1 to 11)
        if i >= 1:
            c0 = (0.0, deck_y, stations[i][0])
            c1 = (0.0, deck_y, stations[i + 1][0])
            mb.add_quad("DeckWood", c0, s0_r[7], s1_r[7], c1, (0.0, 1.0, 0.0))
            mb.add_quad("DeckWood", s0_l[7], c0, c1, s1_l[7], (0.0, 1.0, 0.0))

    # Close the flat transom at station 11 (z = +2.20)
    tr_r = st_stbd[-1]
    tr_l = st_port[-1]
    z_transom = stations[-1][0]
    aft_n = (0.0, 0.0, 1.0)

    # Lower transom (RustKeel, below waterline_y)
    c_keel = tr_r[0]
    c_chine = (0.0, tr_r[2][1], z_transom)
    c_wl = (0.0, waterline_y, z_transom)

    mb.add_quad("RustKeel", c_keel, tr_r[1], tr_r[2], c_chine, aft_n)
    mb.add_quad("RustKeel", tr_l[1], c_keel, c_chine, tr_l[2], aft_n)
    mb.add_quad("RustKeel", c_chine, tr_r[2], tr_r[3], c_wl, aft_n)
    mb.add_quad("RustKeel", tr_l[2], c_chine, c_wl, tr_l[3], aft_n)

    # Upper outer transom (HullIron, above waterline_y)
    c_mid = (0.0, tr_r[4][1], z_transom)
    c_sheer = (0.0, tr_r[5][1], z_transom)
    mb.add_quad("HullIron", c_wl, tr_r[3], tr_r[4], c_mid, aft_n)
    mb.add_quad("HullIron", tr_l[3], c_wl, c_mid, tr_l[4], aft_n)
    mb.add_quad("HullIron", c_mid, tr_r[4], tr_r[5], c_sheer, aft_n)
    mb.add_quad("HullIron", tr_l[4], c_mid, c_sheer, tr_l[5], aft_n)

    # Stern transom bulwark (inner wall facing forward -Z & top rail cap)
    z_stern_in = z_transom - bulwark_thickness
    st_in_l_top = (tr_l[6][0], tr_l[6][1], z_stern_in)
    st_in_r_top = (tr_r[6][0], tr_r[6][1], z_stern_in)
    st_in_l_bot = (tr_l[7][0], deck_y, z_stern_in)
    st_in_r_bot = (tr_r[7][0], deck_y, z_stern_in)

    # Stern rail cap (+Y)
    mb.add_quad("HullIron", tr_l[6], tr_r[6], st_in_r_top, st_in_l_top, (0.0, 1.0, 0.0))
    # Stern inner bulwark wall (-Z)
    mb.add_quad("HullIron", st_in_l_bot, st_in_l_top, st_in_r_top, st_in_r_bot, (0.0, 0.0, -1.0))

    # Deep skeg keel fin & rudder under the stern (RustKeel)
    mb.add_box("RustKeel", (0.0, -0.48, 0.25), (0.10, 0.14, 2.90))
    mb.add_box("RustKeel", (0.0, -0.34, 2.08), (0.06, 0.34, 0.28))

    # Heavy external rub-rail / fender strake along upper hull side (HullIron)
    for i in range(1, num_stations - 1):
        s0_r = st_stbd[i]
        s1_r = st_stbd[i + 1]
        s0_l = st_port[i]
        s1_l = st_port[i + 1]
        p0_r = v_lerp(s0_r[4], s0_r[5], 0.72)
        p1_r = v_lerp(s1_r[4], s1_r[5], 0.72)
        p0_l = v_lerp(s0_l[4], s0_l[5], 0.72)
        p1_l = v_lerp(s1_l[4], s1_l[5], 0.72)
        out_r = (0.035, 0.0, 0.0)
        out_l = (-0.035, 0.0, 0.0)
        dy = (0.0, 0.045, 0.0)
        mb.add_quad(
            "HullIron",
            v_add(p0_r, out_r),
            v_add(v_add(p0_r, out_r), dy),
            v_add(v_add(p1_r, out_r), dy),
            v_add(p1_r, out_r),
            (1.0, 0.0, 0.0),
        )
        mb.add_quad(
            "HullIron",
            v_add(v_add(p0_l, out_l), dy),
            v_add(p0_l, out_l),
            v_add(p1_l, out_l),
            v_add(v_add(p1_l, out_l), dy),
            (-1.0, 0.0, 0.0),
        )


def build_wheelhouse(mb: MeshBuilder) -> None:
    """
    Builds the forward wheelhouse (z = -1.10 to -0.10):
      - Lower cabin coaming / trunk (y = 0.35 to 1.05)
      - Upper wheelhouse with raked front windshield wall (y = 1.05 to 1.72)
      - Recessed WindowGlow panes across front (3 panes) and sides
      - Side doors in DarkMetal
      - Overhanging HullIron roof visor
    """
    y_deck: float = 0.35
    y_mid: float = 1.05
    y_top: float = 1.72

    hx_low: float = 0.60
    hx_top: float = 0.56
    z_front_bot: float = -1.10
    z_front_mid: float = -1.08
    z_front_top: float = -0.95  # Raked backward at top of windshield
    z_back: float = -0.10

    # 1. Lower cabin trunk (y = 0.35 to 1.05, z = -1.10 to -0.10)
    p_fl_b: Vec3 = (-hx_low, y_deck, z_front_bot)
    p_fr_b: Vec3 = (hx_low, y_deck, z_front_bot)
    p_bl_b: Vec3 = (-hx_low, y_deck, z_back)
    p_br_b: Vec3 = (hx_low, y_deck, z_back)

    p_fl_m: Vec3 = (-hx_low, y_mid, z_front_mid)
    p_fr_m: Vec3 = (hx_low, y_mid, z_front_mid)
    p_bl_m: Vec3 = (-hx_low, y_mid, z_back)
    p_br_m: Vec3 = (hx_low, y_mid, z_back)

    mb.add_quad("CabinPaint", p_fl_b, p_fl_m, p_fr_m, p_fr_b, (0.0, 0.0, -1.0))
    mb.add_quad("CabinPaint", p_bl_b, p_br_b, p_br_m, p_bl_m, (0.0, 0.0, 1.0))
    mb.add_quad("CabinPaint", p_bl_b, p_bl_m, p_fl_m, p_fl_b, (-1.0, 0.0, 0.0))
    mb.add_quad("CabinPaint", p_fr_b, p_fr_m, p_br_m, p_br_b, (1.0, 0.0, 0.0))
    mb.add_quad("CabinPaint", p_fl_m, p_bl_m, p_br_m, p_fr_m, (0.0, 1.0, 0.0))

    # 2. Upper pilothouse (y = 1.05 to 1.72, raked front z = -1.08 -> -0.95)
    u_fl_b: Vec3 = (-hx_top, y_mid, z_front_mid)
    u_fr_b: Vec3 = (hx_top, y_mid, z_front_mid)
    u_bl_b: Vec3 = (-hx_top, y_mid, z_back)
    u_br_b: Vec3 = (hx_top, y_mid, z_back)

    u_fl_t: Vec3 = (-hx_top, y_top, z_front_top)
    u_fr_t: Vec3 = (hx_top, y_top, z_front_top)
    u_bl_t: Vec3 = (-hx_top, y_top, z_back)
    u_br_t: Vec3 = (hx_top, y_top, z_back)

    mb.add_quad("CabinPaint", u_fl_b, u_fl_t, u_fr_t, u_fr_b, (0.0, 0.25, -1.0))
    mb.add_quad("CabinPaint", u_bl_b, u_br_b, u_br_t, u_bl_t, (0.0, 0.0, 1.0))
    mb.add_quad("CabinPaint", u_bl_b, u_bl_t, u_fl_t, u_fl_b, (-1.0, 0.0, 0.0))
    mb.add_quad("CabinPaint", u_fr_b, u_fr_t, u_br_t, u_br_b, (1.0, 0.0, 0.0))
    mb.add_quad("CabinPaint", u_fl_t, u_bl_t, u_br_t, u_fr_t, (0.0, 1.0, 0.0))

    # 3. Raked front windshield WindowGlow panes (3 panes across front with mullion frames)
    win_t0: float = 0.22
    win_t1: float = 0.82
    wy0 = y_mid + (y_top - y_mid) * win_t0
    wy1 = y_mid + (y_top - y_mid) * win_t1
    wz0 = z_front_mid + (z_front_top - z_front_mid) * win_t0 - 0.012
    wz1 = z_front_mid + (z_front_top - z_front_mid) * win_t1 - 0.012

    pane_x_spans = [(-0.48, -0.18), (-0.13, 0.13), (0.18, 0.48)]
    for x_left, x_right in pane_x_spans:
        mb.add_quad(
            "WindowGlow",
            (x_left, wy0, wz0),
            (x_left, wy1, wz1),
            (x_right, wy1, wz1),
            (x_right, wy0, wz0),
            (0.0, 0.25, -1.0),
        )

    # 4. Port & Starboard side windows (forward half of pilothouse)
    side_z0: float = -0.92
    side_z1: float = -0.52
    side_x_out: float = hx_top + 0.012
    # Port window (-X)
    mb.add_quad(
        "WindowGlow",
        (-side_x_out, wy0, side_z1),
        (-side_x_out, wy1, side_z1),
        (-side_x_out, wy1, side_z0),
        (-side_x_out, wy0, side_z0),
        (-1.0, 0.0, 0.0),
    )
    # Starboard window (+X)
    mb.add_quad(
        "WindowGlow",
        (side_x_out, wy0, side_z0),
        (side_x_out, wy1, side_z0),
        (side_x_out, wy1, side_z1),
        (side_x_out, wy0, side_z1),
        (1.0, 0.0, 0.0),
    )

    # Aft rear lookout window on back of wheelhouse (+Z)
    mb.add_quad(
        "WindowGlow",
        (-0.24, wy0, z_back + 0.012),
        (0.24, wy0, z_back + 0.012),
        (0.24, wy1, z_back + 0.012),
        (-0.24, wy1, z_back + 0.012),
        (0.0, 0.0, 1.0),
    )

    # 5. Port & Starboard Wheelhouse Side Doors (DarkMetal with small porthole WindowGlow)
    door_z_center: float = -0.29
    door_y_center: float = 0.96
    mb.add_box("DarkMetal", (-hx_low - 0.01, door_y_center, door_z_center), (0.04, 1.12, 0.34))
    mb.add_box("DarkMetal", (hx_low + 0.01, door_y_center, door_z_center), (0.04, 1.12, 0.34))

    # 6. Overhanging Wheelhouse Roof Visor (HullIron)
    # Extends forward to z = -1.16 to form a brow visor over the raked windshield
    visor_y0: float = y_top
    visor_y1: float = y_top + 0.09
    visor_hx: float = 0.64
    visor_zf: float = -1.15
    visor_zb: float = -0.04
    mb.add_box(
        "HullIron",
        (0.0, (visor_y0 + visor_y1) * 0.5, (visor_zf + visor_zb) * 0.5),
        (visor_hx * 2.0, visor_y1 - visor_y0, visor_zb - visor_zf),
    )


def build_superstructure_details(mb: MeshBuilder) -> None:
    """
    Builds:
      - Diesel Smokestack behind cabin (DarkMetal)
      - Tall Mast with cross-yardarm & masthead light (DarkMetal & WindowGlow)
      - Stern Dredge A-Frame crane (z = 1.90 to 2.50) & hanging lantern (DarkMetal & WindowGlow)
      - Back deck Winch drum (z = 0.80) & bow bollards (DarkMetal)
      - Wheelhouse roof Searchlight housing & glowing lens (DarkMetal & WindowGlow)
    """
    # 1. Raked Cylindrical Diesel Smokestack behind cabin (Port of centerline)
    stack_base: Vec3 = (-0.32, 0.35, 0.08)
    stack_top: Vec3 = (-0.32, 2.05, 0.28)
    mb.add_cylinder_between("DarkMetal", stack_base, stack_top, 0.13, 0.105, segments=14)
    # Exhaust collar rim near top
    collar_bot: Vec3 = v_lerp(stack_base, stack_top, 0.90)
    collar_top: Vec3 = v_lerp(stack_base, stack_top, 0.98)
    mb.add_cylinder_between("DarkMetal", collar_bot, collar_top, 0.12, 0.12, segments=14)

    # 2. Tall Mast & Cross-Yardarm on Wheelhouse Roof
    mast_base: Vec3 = (0.0, 1.80, -0.35)
    mast_top: Vec3 = (0.0, 3.25, -0.32)
    mb.add_cylinder_between("DarkMetal", mast_base, mast_top, 0.055, 0.032, segments=10)

    # Cross-yardarm at y = 2.75
    yard_port: Vec3 = (-0.56, 2.75, -0.33)
    yard_stbd: Vec3 = (0.56, 2.75, -0.33)
    mb.add_cylinder_between("DarkMetal", yard_port, yard_stbd, 0.024, 0.024, segments=8)

    # Masthead Navigation Light (WindowGlow) at top of mast
    mb.add_cylinder_between(
        "WindowGlow",
        (0.0, 3.25, -0.32),
        (0.0, 3.38, -0.32),
        0.055,
        0.045,
        segments=10,
    )

    # 3. Wheelhouse Roof Searchlight Pedestal Base (at z = -0.75 where SearchlightGimbal mounts)
    mb.add_cylinder_between("DarkMetal", (0.0, 1.80, -0.75), (0.0, 1.86, -0.75), 0.08, 0.06, segments=10)

    # 4. Trawl Winch Drum on Back Deck (z = 0.80)
    winch_z: float = 0.80
    winch_y: float = 0.62
    # Port and starboard winch support pedestals
    mb.add_box("DarkMetal", (-0.42, 0.52, winch_z), (0.10, 0.36, 0.34))
    mb.add_box("DarkMetal", (0.42, 0.52, winch_z), (0.10, 0.36, 0.34))
    # Central winch drum & outer flanges
    mb.add_cylinder_between("DarkMetal", (-0.38, winch_y, winch_z), (0.38, winch_y, winch_z), 0.16, 0.16, segments=14)
    mb.add_cylinder_between("DarkMetal", (-0.39, winch_y, winch_z), (-0.34, winch_y, winch_z), 0.24, 0.24, segments=14)
    mb.add_cylinder_between("DarkMetal", (0.34, winch_y, winch_z), (0.39, winch_y, winch_z), 0.24, 0.24, segments=14)
    # Center divider flange
    mb.add_cylinder_between("DarkMetal", (-0.02, winch_y, winch_z), (0.02, winch_y, winch_z), 0.22, 0.22, segments=14)

    # Aft deck cargo hatch coaming behind cabin (z = 0.32)
    mb.add_box("CabinPaint", (0.16, 0.41, 0.32), (0.52, 0.12, 0.48))

    # 5. Stern Dredge A-Frame Crane (mounted at z = 1.90, leaning over stern to z = 2.50)
    a_base_z: float = 1.90
    a_top_z: float = 2.50
    a_top_y: float = 2.02

    port_leg_base: Vec3 = (-0.68, 0.35, a_base_z)
    stbd_leg_base: Vec3 = (0.68, 0.35, a_base_z)
    port_leg_top: Vec3 = (-0.42, a_top_y, a_top_z)
    stbd_leg_top: Vec3 = (0.42, a_top_y, a_top_z)

    mb.add_cylinder_between("DarkMetal", port_leg_base, port_leg_top, 0.06, 0.05, segments=10)
    mb.add_cylinder_between("DarkMetal", stbd_leg_base, stbd_leg_top, 0.06, 0.05, segments=10)

    # Forward support stay struts from z = 1.45 up to mid-A-frame legs
    port_leg_mid: Vec3 = v_lerp(port_leg_base, port_leg_top, 0.62)
    stbd_leg_mid: Vec3 = v_lerp(stbd_leg_base, stbd_leg_top, 0.62)
    mb.add_cylinder_between("DarkMetal", (-0.66, 0.35, 1.42), port_leg_mid, 0.038, 0.035, segments=8)
    mb.add_cylinder_between("DarkMetal", (0.66, 0.35, 1.42), stbd_leg_mid, 0.038, 0.035, segments=8)

    # Top horizontal crossbar at z = 2.50, y = 2.02
    cross_port: Vec3 = (-0.50, a_top_y, a_top_z)
    cross_stbd: Vec3 = (0.50, a_top_y, a_top_z)
    mb.add_cylinder_between("DarkMetal", cross_port, cross_stbd, 0.055, 0.055, segments=10)

    # Central dredge block & hanging Stern Lantern at (0.0, 1.80, 2.48)
    mb.add_cylinder_between("DarkMetal", (0.0, a_top_y, a_top_z), (0.0, 1.88, a_top_z), 0.03, 0.05, segments=8)
    mb.add_cylinder_between("WindowGlow", (0.0, 1.88, a_top_z), (0.0, 1.74, a_top_z), 0.065, 0.05, segments=10)

    # 6. Twin Bow Mooring Bollards on foredeck
    mb.add_cylinder_between("DarkMetal", (-0.28, 0.35, -1.62), (-0.28, 0.56, -1.62), 0.045, 0.055, segments=8)
    mb.add_cylinder_between("DarkMetal", (0.28, 0.35, -1.62), (0.28, 0.56, -1.62), 0.045, 0.055, segments=8)


def write_mtl_file(mtl_path: str) -> None:
    mtl_lines: List[str] = [
        "# Procedural Fishing Trawler Material Library",
        "",
        "newmtl HullIron",
        "Kd 0.12 0.15 0.17",
        "Ks 0.15 0.15 0.15",
        "Ns 32.0",
        "d 1.0",
        "illum 2",
        "",
        "newmtl RustKeel",
        "Kd 0.28 0.10 0.08",
        "Ks 0.08 0.06 0.05",
        "Ns 16.0",
        "d 1.0",
        "illum 2",
        "",
        "newmtl DeckWood",
        "Kd 0.18 0.13 0.09",
        "Ks 0.05 0.05 0.05",
        "Ns 12.0",
        "d 1.0",
        "illum 2",
        "",
        "newmtl CabinPaint",
        "Kd 0.42 0.45 0.44",
        "Ks 0.12 0.12 0.12",
        "Ns 24.0",
        "d 1.0",
        "illum 2",
        "",
        "newmtl DarkMetal",
        "Kd 0.08 0.08 0.09",
        "Ks 0.25 0.25 0.26",
        "Ns 48.0",
        "d 1.0",
        "illum 2",
        "",
        "newmtl WindowGlow",
        "Kd 1.0 0.70 0.28",
        "Ke 0.9 0.55 0.15",
        "Ks 0.50 0.45 0.35",
        "Ns 64.0",
        "d 1.0",
        "illum 2",
        "",
    ]
    with open(mtl_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(mtl_lines))


def write_obj_file(obj_path: str, mtl_filename: str, mb: MeshBuilder) -> None:
    lines: List[str] = [
        "# Procedural 3D Fishing Trawler Wavefront OBJ",
        "# Coordinate System: -Z Forward, +Z Stern, +Y Up, X Port/Starboard",
        f"mtllib {mtl_filename}",
        "o Trawler",
        "",
    ]

    for vx, vy, vz in mb.vertices:
        lines.append(f"v {vx:.5f} {vy:.5f} {vz:.5f}")
    lines.append("")

    for nx, ny, nz in mb.normals:
        lines.append(f"vn {nx:.5f} {ny:.5f} {nz:.5f}")
    lines.append("")

    for mat in MATERIAL_ORDER:
        faces = mb.faces_by_mat[mat]
        if not faces:
            continue
        lines.append(f"g {mat}")
        lines.append(f"usemtl {mat}")
        lines.append("s off")
        for (v0, n0), (v1, n1), (v2, n2) in faces:
            lines.append(f"f {v0}//{n0} {v1}//{n1} {v2}//{n2}")
        lines.append("")

    with open(obj_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main() -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "assets", "models")
    os.makedirs(output_dir, exist_ok=True)

    obj_path = os.path.join(output_dir, "trawler.obj")
    mtl_path = os.path.join(output_dir, "trawler.mtl")

    mb = MeshBuilder()
    build_trawler_hull(mb)
    build_wheelhouse(mb)
    build_superstructure_details(mb)

    write_mtl_file(mtl_path)
    write_obj_file(obj_path, "trawler.mtl", mb)

    total_tris = sum(len(faces) for faces in mb.faces_by_mat.values())
    print(f"Generated {mtl_path}")
    print(f"Generated {obj_path}: {len(mb.vertices)} vertices, {len(mb.normals)} normals, {total_tris} triangles")
    for idx, mat in enumerate(MATERIAL_ORDER):
        print(f"  Surface {idx} ({mat}): {len(mb.faces_by_mat[mat])} triangles")


if __name__ == "__main__":
    main()
