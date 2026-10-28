#!/usr/bin/env python3
"""
Fast Top-Down Nautical Chart Generator (`tools/generate_world_map_png.py`)
Parses `scripts/world_builder.gd` and generates a 2048x2048 PNG (`world_map_overview.png`)
showing the exact coordinates, scaled meter footprints, extended 12-segment Black Sound Fjord,
scattered POIs, and the 4 navigable barrier island chains across [-1100m .. +700m].
"""

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORLD_BUILDER_PATH = PROJECT_ROOT / "scripts" / "world_builder.gd"
OUTPUT_PNG_PATH = PROJECT_ROOT / "world_map_overview.png"

# Real-world unscaled mesh footprints (width X, depth Z in meters) from Blender export pipeline
MESH_BASE_FOOTPRINTS: Dict[str, Tuple[float, float]] = {
    "_scene_wharf_island": (58.0, 54.0),
    "_scene_harbor_lighthouse": (9.5, 9.5),
    "_scene_landmark_fjord_gate_arch": (88.0, 46.0),
    "_scene_fjord_cliff_corner_spire": (45.0, 45.0),
    "_scene_fjord_cliff_wall_shack": (46.0, 65.0),
    "_scene_fjord_cliff_wall_basalt": (44.0, 65.0),
    "_scene_fjord_cliff_wall_overhang": (45.0, 65.0),
    "_scene_landmark_terraced_hamlet": (84.0, 92.0),
    "_scene_landmark_stilt_sanctuary": (76.0, 72.0),
    "shipwreck": (12.0, 28.0),
    "sea_fort": (16.0, 16.0),
    "leviathan_ribcage": (24.0, 20.0),
    "derelict_lightship": (11.0, 26.0),
}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        ["consolab.ttf", "arialbd.ttf", "segoeuib.ttf", "calibrib.ttf"]
        if bold
        else ["consola.ttf", "arial.ttf", "segoeui.ttf", "calibri.ttf"]
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def parse_world_builder(gd_path: Path) -> Dict[str, Any]:
    text = gd_path.read_text(encoding="utf-8")

    # 1. Extract Vector3 constants
    constants: Dict[str, Tuple[float, float, float]] = {}
    for m in re.finditer(
        r"const\s+([A-Z0-9_]+)\s*:\s*Vector3\s*=\s*Vector3\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)",
        text,
    ):
        constants[m.group(1)] = (float(m.group(2)), float(m.group(3)), float(m.group(4)))

    # 2. Extract @export scalar parameters
    exports: Dict[str, float] = {}
    for m in re.finditer(r"@export\s+var\s+([a-z0-9_]+)\s*:\s*(?:float|int)\s*=\s*([-\d.]+)", text):
        exports[m.group(1)] = float(m.group(2))

    # 3. Extract all `_spawn_fjord_landmark_piece` calls (Fjord + Landmarks + 4 Barrier Island Chains)
    fjord_pieces: List[Dict[str, Any]] = []
    piece_pattern = re.compile(
        r"_spawn_fjord_landmark_piece\(\s*"
        r"[^,]+,\s*"
        r"(_scene_[a-z0-9_]+)\s*,\s*"
        r"\"([^\"]+)\"\s*,\s*"
        r"(Vector3\([^)]+\)|[A-Z0-9_]+)\s*,\s*"
        r"([-\d.]+)\s*,\s*"
        r"Vector3\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)",
        re.MULTILINE,
    )
    for m in piece_pattern.finditer(text):
        scene_var = m.group(1)
        node_name = m.group(2)
        pos_expr = m.group(3).strip()
        yaw_deg = float(m.group(4))
        sx, sy, sz = float(m.group(5)), float(m.group(6)), float(m.group(7))

        if pos_expr in constants:
            px, py, pz = constants[pos_expr]
        else:
            vm = re.match(r"Vector3\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)", pos_expr)
            px, py, pz = (float(vm.group(1)), float(vm.group(2)), float(vm.group(3))) if vm else (0.0, 0.0, 0.0)

        base_w, base_d = MESH_BASE_FOOTPRINTS.get(scene_var, (40.0, 40.0))
        fjord_pieces.append(
            {
                "scene_var": scene_var,
                "name": node_name,
                "pos": (px, py, pz),
                "yaw_deg": yaw_deg,
                "scale": (sx, sy, sz),
                "footprint_xz": (base_w * sx, base_d * sz),
            }
        )

    # 4. Extract channel_buoy_coords
    buoys: List[Tuple[float, float]] = []
    buoy_block = re.search(r"var\s+channel_buoy_coords\s*:\s*Array\[Vector2\]\s*=\s*\[([^\]]+)\]", text, re.DOTALL)
    if buoy_block:
        for vm in re.finditer(r"Vector2\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)", buoy_block.group(1)):
            buoys.append((float(vm.group(1)), float(vm.group(2))))

    # 5. Extract poi_spawn_coords and poi_types_cycle
    poi_coords: List[Tuple[float, float]] = []
    poi_block = re.search(r"var\s+poi_spawn_coords\s*:\s*Array\[Vector2\]\s*=\s*\[([^\]]+)\]", text, re.DOTALL)
    if poi_block:
        for vm in re.finditer(r"Vector2\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)", poi_block.group(1)):
            poi_coords.append((float(vm.group(1)), float(vm.group(2))))

    poi_types: List[str] = []
    type_block = re.search(r"var\s+poi_types_cycle\s*:\s*Array\[String\]\s*=\s*\[([^\]]+)\]", text, re.DOTALL)
    if type_block:
        for tm in re.finditer(r"\"([^\"]+)\"", type_block.group(1)):
            poi_types.append(tm.group(1))

    pois: List[Dict[str, Any]] = []
    for idx, (px, pz) in enumerate(poi_coords):
        ptype = poi_types[idx % len(poi_types)] if poi_types else "shipwreck"
        pois.append(
            {
                "index": idx,
                "type": ptype,
                "pos_xz": (px, pz),
                "footprint_xz": MESH_BASE_FOOTPRINTS.get(ptype, (14.0, 14.0)),
            }
        )

    return {
        "constants": constants,
        "exports": exports,
        "fjord_pieces": fjord_pieces,
        "buoys": buoys,
        "pois": pois,
    }


def draw_dashed_circle(
    draw: ImageDraw.ImageDraw,
    center: Tuple[float, float],
    radius: float,
    color: Tuple[int, int, int, int],
    width: int = 3,
    dash_deg: float = 5.0,
    gap_deg: float = 4.0,
) -> None:
    cx, cy = center
    bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
    angle = 0.0
    while angle < 360.0:
        end_angle = min(360.0, angle + dash_deg)
        draw.arc(bbox, start=angle, end=end_angle, fill=color, width=width)
        angle += dash_deg + gap_deg


def draw_dashed_rect(
    draw: ImageDraw.ImageDraw,
    rect: Tuple[float, float, float, float],
    color: Tuple[int, int, int, int],
    width: int = 2,
    dash_len: float = 12.0,
    gap_len: float = 8.0,
) -> None:
    x0, y0, x1, y1 = rect
    edges = [
        ((x0, y0), (x1, y0)),
        ((x1, y0), (x1, y1)),
        ((x1, y1), (x0, y1)),
        ((x0, y1), (x0, y0)),
    ]
    for (sx, sy), (ex, ey) in edges:
        length = math.hypot(ex - sx, ey - sy)
        if length <= 0.0:
            continue
        ux, uy = (ex - sx) / length, (ey - sy) / length
        dist = 0.0
        while dist < length:
            seg_end = min(length, dist + dash_len)
            p0 = (sx + ux * dist, sy + uy * dist)
            p1 = (sx + ux * seg_end, sy + uy * seg_end)
            draw.line([p0, p1], fill=color, width=width)
            dist += dash_len + gap_len


def draw_rotated_footprint(
    draw: ImageDraw.ImageDraw,
    center_px: Tuple[float, float],
    size_px: Tuple[float, float],
    yaw_deg: float,
    fill_color: Tuple[int, int, int, int],
    outline_color: Tuple[int, int, int, int],
    outline_width: int = 2,
) -> List[Tuple[float, float]]:
    cx, cy = center_px
    hw, hd = size_px[0] * 0.5, size_px[1] * 0.5
    rad = math.radians(-yaw_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    local_corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    poly: List[Tuple[float, float]] = []
    for lx, lz in local_corners:
        rx = lx * cos_a - lz * sin_a
        rz = lx * sin_a + lz * cos_a
        poly.append((cx + rx, cy + rz))
    draw.polygon(poly, fill=fill_color, outline=outline_color, width=outline_width)
    return poly


def generate_map() -> None:
    data = parse_world_builder(WORLD_BUILDER_PATH)

    W, H = 2048, 2048
    base_img = Image.new("RGBA", (W, H), (7, 16, 24, 255))
    overlay_zones = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    overlay_geom = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    overlay_ui = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    draw_base = ImageDraw.Draw(base_img)
    draw_zones = ImageDraw.Draw(overlay_zones)
    draw_geom = ImageDraw.Draw(overlay_geom)
    draw_ui = ImageDraw.Draw(overlay_ui)

    # Fonts
    font_title = load_font(29, bold=True)
    font_subtitle = load_font(17, bold=False)
    font_sec_hdr = load_font(18, bold=True)
    font_label_md = load_font(14, bold=True)
    font_label_sm = load_font(12, bold=False)
    font_grid = load_font(13, bold=True)
    font_compass = load_font(19, bold=True)

    MARGIN_LEFT = 92
    MARGIN_TOP = 110
    MARGIN_RIGHT = 92
    MARGIN_BOTTOM = 90
    PLOT_W = W - MARGIN_LEFT - MARGIN_RIGHT  # 1864 px
    PLOT_H = H - MARGIN_TOP - MARGIN_BOTTOM  # 1848 px

    # Viewport covering -1100m to +700m on Z (and -900m to +900m on X for 1:1 true meter aspect ratio)
    WORLD_X_MIN, WORLD_X_MAX = -900.0, 900.0
    WORLD_Z_MIN, WORLD_Z_MAX = -1100.0, 700.0
    PX_PER_M_X = PLOT_W / (WORLD_X_MAX - WORLD_X_MIN)
    PX_PER_M_Z = PLOT_H / (WORLD_Z_MAX - WORLD_Z_MIN)
    PX_PER_M = min(PX_PER_M_X, PX_PER_M_Z)

    def world_to_px(x_m: float, z_m: float) -> Tuple[float, float]:
        px = MARGIN_LEFT + (x_m - WORLD_X_MIN) * PX_PER_M_X
        py = MARGIN_TOP + (z_m - WORLD_Z_MIN) * PX_PER_M_Z
        return (px, py)

    # 1. Deep Nautical Chart Background Fill
    draw_base.rectangle(
        [MARGIN_LEFT, MARGIN_TOP, W - MARGIN_RIGHT, H - MARGIN_BOTTOM],
        fill=(10, 22, 34, 255),
        outline=(78, 130, 165, 255),
        width=3,
    )

    origin_px = world_to_px(0.0, 0.0)

    # 2. Coordinate Grid Lines (100m minor, 200m major, 0m primary axis)
    for x_m in range(-900, 901, 100):
        px, _ = world_to_px(float(x_m), 0.0)
        if x_m == 0:
            col = (65, 115, 145, 255)
            w_line = 2
        elif x_m % 200 == 0:
            col = (34, 65, 90, 255)
            w_line = 2
        else:
            col = (20, 42, 60, 255)
            w_line = 1
        draw_base.line([(px, MARGIN_TOP), (px, H - MARGIN_BOTTOM)], fill=col, width=w_line)
        if x_m % 200 == 0 or x_m == 0:
            lbl = f"X={x_m:+d}m" if x_m != 0 else "X=0m (W/E)"
            draw_ui.text((px - 34, MARGIN_TOP - 24), lbl, fill=(165, 210, 235, 255), font=font_grid)
            draw_ui.text((px - 34, H - MARGIN_BOTTOM + 8), lbl, fill=(165, 210, 235, 255), font=font_grid)

    for z_m in range(-1100, 701, 100):
        _, py = world_to_px(0.0, float(z_m))
        if z_m == 0:
            col = (65, 115, 145, 255)
            w_line = 2
        elif z_m % 200 == 0:
            col = (34, 65, 90, 255)
            w_line = 2
        else:
            col = (20, 42, 60, 255)
            w_line = 1
        draw_base.line([(MARGIN_LEFT, py), (W - MARGIN_RIGHT, py)], fill=col, width=w_line)
        if z_m % 100 == 0:
            lbl = f"Z={z_m:+d}m" if z_m != 0 else "Z=0m"
            draw_ui.text((8, py - 8), lbl, fill=(165, 210, 235, 255), font=font_grid)
            draw_ui.text((W - MARGIN_RIGHT + 6, py - 8), lbl, fill=(165, 210, 235, 255), font=font_grid)

    # 3. Harbor Open Departure Zone (R = 220m) & Major Archipelago Ring (R = 380m)
    draw_zones.ellipse(
        [
            origin_px[0] - 220.0 * PX_PER_M,
            origin_px[1] - 220.0 * PX_PER_M,
            origin_px[0] + 220.0 * PX_PER_M,
            origin_px[1] + 220.0 * PX_PER_M,
        ],
        fill=(32, 95, 75, 26),
    )
    draw_dashed_circle(
        draw_zones,
        origin_px,
        220.0 * PX_PER_M,
        color=(85, 220, 155, 195),
        width=2,
        dash_deg=4.0,
        gap_deg=3.0,
    )
    draw_ui.text(
        (origin_px[0] - 142, origin_px[1] + int(220.0 * PX_PER_M) - 20),
        "UNCLUTTERED HARBOR DEPARTURE ZONE (R = 220m)",
        fill=(115, 235, 175, 235),
        font=font_label_sm,
    )

    draw_dashed_circle(
        draw_zones,
        origin_px,
        380.0 * PX_PER_M,
        color=(85, 155, 190, 165),
        width=2,
        dash_deg=4.0,
        gap_deg=3.0,
    )

    # 4. Highlight the 4 Navigable Barrier Island Zones (Dashed Amber Circles)
    barrier_zones = [
        {
            "center_xz": (-410.0, -90.0),
            "radius_m": 135.0,
            "title": "ZONE #1: WESTERN BARRIER PENINSULA",
            "subtitle": "3-Segment Basalt Headland (NNW-SSE) | (-410m, -90m)",
            "lbl_offset": (-385, -188),
        },
        {
            "center_xz": (0.0, 360.0),
            "radius_m": 175.0,
            "title": "ZONE #2: SOUTHERN BREAKWATER RIDGE",
            "subtitle": "4-Segment Chain + 75m Navigable Center Pass | (0m, +360m)",
            "lbl_offset": (-195, 192),
        },
        {
            "center_xz": (460.0, 20.0),
            "radius_m": 135.0,
            "title": "ZONE #3: EASTERN SEA-STACK RIDGE",
            "subtitle": "3-Segment Cliff Ridge South of Sanctuary | (+460m, +20m)",
            "lbl_offset": (-165, 152),
        },
        {
            "center_xz": (-390.0, 290.0),
            "radius_m": 125.0,
            "title": "ZONE #4: SOUTHWEST CALDERA REEF",
            "subtitle": "3-Segment Crescent Sheltered Cove | (-390m, +290m)",
            "lbl_offset": (-385, -158),
        },
    ]

    for bz in barrier_zones:
        bcx, bcz = bz["center_xz"]
        br_m = bz["radius_m"]
        c_px = world_to_px(bcx, bcz)
        r_px = br_m * PX_PER_M
        draw_zones.ellipse(
            [c_px[0] - r_px, c_px[1] - r_px, c_px[0] + r_px, c_px[1] + r_px],
            fill=(255, 168, 38, 34),
        )
        draw_dashed_circle(
            draw_zones,
            c_px,
            r_px,
            color=(255, 188, 58, 235),
            width=3,
            dash_deg=5.0,
            gap_deg=3.5,
        )
        ox, oy = bz["lbl_offset"]
        bx0, by0 = c_px[0] + ox, c_px[1] + oy
        box_w, box_h = 386, 46
        draw_ui.rounded_rectangle(
            [bx0, by0, bx0 + box_w, by0 + box_h],
            radius=5,
            fill=(24, 18, 10, 240),
            outline=(255, 188, 58, 255),
            width=2,
        )
        draw_ui.text((bx0 + 8, by0 + 5), bz["title"], fill=(255, 208, 95, 255), font=font_label_md)
        draw_ui.text((bx0 + 8, by0 + 24), bz["subtitle"], fill=(245, 228, 185, 255), font=font_label_sm)

    # 5. Extended Fjord Clearance Corridor (`|X| <= 135m, Z: -140m to -1080m`)
    fc_tl = world_to_px(-135.0, -1080.0)
    fc_br = world_to_px(135.0, -140.0)
    draw_zones.rectangle(
        [fc_tl[0], fc_tl[1], fc_br[0], fc_br[1]],
        fill=(35, 105, 140, 38),
    )
    draw_dashed_rect(
        draw_zones,
        (fc_tl[0], fc_tl[1], fc_br[0], fc_br[1]),
        color=(95, 205, 245, 210),
        width=2,
        dash_len=10.0,
        gap_len=6.0,
    )
    draw_ui.text(
        (fc_tl[0] - 28, fc_tl[1] - 20),
        "FJORD CLEARANCE CORRIDOR (|X| <= 135m, Z: -140m to -1080m)",
        fill=(125, 220, 250, 245),
        font=font_label_sm,
    )

    # Stilt-Sanctuary Clearance Circle at (380, -180), R = 115m
    ss_pos = data["constants"].get("STILT_SANCTUARY_POS", (380.0, -1.45, -180.0))
    ss_px = world_to_px(ss_pos[0], ss_pos[2])
    ss_rad_px = 115.0 * PX_PER_M
    draw_zones.ellipse(
        [ss_px[0] - ss_rad_px, ss_px[1] - ss_rad_px, ss_px[0] + ss_rad_px, ss_px[1] + ss_rad_px],
        fill=(40, 135, 115, 38),
    )
    draw_dashed_circle(
        draw_zones,
        ss_px,
        ss_rad_px,
        color=(95, 230, 195, 210),
        width=2,
        dash_deg=5.0,
        gap_deg=4.0,
    )

    # 6. Plot [1] Starting Harbor, Wharf Island, Lighthouse & 6 Channel Warning Buoys
    wharf_center_px = world_to_px(0.0, 34.0)
    wharf_w_px = 58.0 * PX_PER_M
    wharf_d_px = 54.0 * PX_PER_M
    draw_rotated_footprint(
        draw_geom,
        wharf_center_px,
        (wharf_w_px, wharf_d_px),
        0.0,
        fill_color=(62, 130, 88, 235),
        outline_color=(140, 245, 175, 255),
        outline_width=3,
    )
    pier_tl = world_to_px(-7.5, 0.0)
    pier_br = world_to_px(7.5, 20.0)
    draw_geom.rectangle(
        [pier_tl[0], pier_tl[1], pier_br[0], pier_br[1]],
        fill=(155, 112, 68, 255),
        outline=(235, 185, 120, 255),
        width=2,
    )

    lh_px = world_to_px(0.0, 44.0)
    lh_r = max(5.5, 7.5 * PX_PER_M)
    draw_zones.polygon(
        [
            lh_px,
            (lh_px[0] - 28.0 * PX_PER_M, lh_px[1] - 150.0 * PX_PER_M),
            (lh_px[0] + 28.0 * PX_PER_M, lh_px[1] - 150.0 * PX_PER_M),
        ],
        fill=(255, 230, 140, 35),
    )
    draw_geom.ellipse(
        [lh_px[0] - lh_r, lh_px[1] - lh_r, lh_px[0] + lh_r, lh_px[1] + lh_r],
        fill=(235, 65, 55, 255),
        outline=(255, 240, 175, 255),
        width=2,
    )

    draw_ui.regular_polygon(
        (origin_px[0], origin_px[1], 9),
        n_sides=3,
        rotation=0,
        fill=(80, 255, 155, 255),
        outline=(10, 30, 20, 255),
    )
    harbor_lbl_pos = (origin_px[0] + 45, origin_px[1] + 10)
    draw_ui.line([origin_px, (harbor_lbl_pos[0] - 4, harbor_lbl_pos[1] + 12)], fill=(110, 245, 165, 240), width=2)
    draw_ui.rounded_rectangle(
        [harbor_lbl_pos[0] - 6, harbor_lbl_pos[1] - 4, harbor_lbl_pos[0] + 332, harbor_lbl_pos[1] + 40],
        radius=5,
        fill=(12, 28, 22, 242),
        outline=(110, 245, 165, 255),
        width=2,
    )
    draw_ui.text(harbor_lbl_pos, "[1] STARTING HARBOR & WHARF (0m, 0m)", fill=(130, 255, 180, 255), font=font_label_md)
    draw_ui.text(
        (harbor_lbl_pos[0], harbor_lbl_pos[1] + 18),
        "Harbor Lighthouse (0m, +44m) | Wharf 58x54m",
        fill=(200, 240, 215, 255),
        font=font_label_sm,
    )

    # Plot 6 Rusted Warning Buoys (Z = -32m to -140m)
    for b_idx, (bx, bz) in enumerate(data["buoys"]):
        b_px = world_to_px(bx, bz)
        draw_geom.ellipse(
            [b_px[0] - 4, b_px[1] - 4, b_px[0] + 4, b_px[1] + 4],
            fill=(255, 70, 50, 255),
            outline=(255, 210, 190, 255),
            width=2,
        )
        if b_idx == 3:
            draw_ui.text(
                (b_px[0] + 12, b_px[1] - 6),
                "6x Rusted Channel Buoys (Z=-32m..-140m)",
                fill=(255, 155, 140, 245),
                font=font_label_sm,
            )

    # 7. Plot All Fjord Pieces, Landmarks & 4 Barrier Island Chains
    for piece in data["fjord_pieces"]:
        pname = piece["name"]
        px, py, pz = piece["pos"]
        yaw_deg = piece["yaw_deg"]
        fw_m, fd_m = piece["footprint_xz"]
        c_px = world_to_px(px, pz)
        size_px = (fw_m * PX_PER_M, fd_m * PX_PER_M)

        if "GateArch" in pname:
            fill_c = (195, 125, 55, 235)
            out_c = (255, 210, 115, 255)
        elif "TerracedHamlet" in pname:
            fill_c = (185, 95, 65, 235)
            out_c = (255, 195, 130, 255)
        elif "StiltSanctuary" in pname:
            fill_c = (55, 155, 138, 235)
            out_c = (145, 250, 225, 255)
        elif "Shack" in pname:
            fill_c = (145, 108, 68, 240)
            out_c = (245, 195, 120, 255)
        elif any(k in pname for k in ("WestBarrier", "SouthBreakwater", "EastRidge", "SWCaldera")):
            fill_c = (118, 92, 66, 235)
            out_c = (255, 192, 85, 255)
        else:
            fill_c = (78, 94, 112, 230)
            out_c = (165, 195, 220, 255)

        draw_rotated_footprint(draw_geom, c_px, size_px, yaw_deg, fill_color=fill_c, outline_color=out_c, outline_width=2)

        if "GateArch" in pname:
            lbl_box = (c_px[0] + 108, c_px[1] - 18)
            draw_ui.line([(c_px[0] + 54, c_px[1]), (lbl_box[0] - 6, lbl_box[1] + 18)], fill=out_c, width=2)
            draw_ui.rounded_rectangle(
                [lbl_box[0] - 6, lbl_box[1] - 4, lbl_box[0] + 356, lbl_box[1] + 40],
                radius=5,
                fill=(28, 20, 12, 244),
                outline=out_c,
                width=2,
            )
            draw_ui.text(lbl_box, f"[2] FJORD ENTRANCE GATE ARCH ({px:.0f}m, {pz:.0f}m)", fill=(255, 215, 125, 255), font=font_label_md)
            draw_ui.text(
                (lbl_box[0], lbl_box[1] + 18),
                f"Footprint: {fw_m:.0f}x{fd_m:.0f}m | Teleport [2]: (0m, -455m)",
                fill=(235, 205, 165, 255),
                font=font_label_sm,
            )
        elif "TerracedHamlet" in pname:
            lbl_box = (c_px[0] - 185, c_px[1] - 96)
            draw_ui.rounded_rectangle(
                [lbl_box[0] - 6, lbl_box[1] - 4, lbl_box[0] + 382, lbl_box[1] + 40],
                radius=5,
                fill=(32, 16, 14, 244),
                outline=out_c,
                width=2,
            )
            draw_ui.text(lbl_box, f"[3] TERRACED FISHING HAMLET ISLAND ({px:.0f}m, {pz:.0f}m)", fill=(255, 195, 135, 255), font=font_label_md)
            draw_ui.text(
                (lbl_box[0], lbl_box[1] + 18),
                f"Footprint: {fw_m:.0f}x{fd_m:.0f}m (Yaw -90°) | Teleport [3]: (0m, -885m)",
                fill=(240, 205, 180, 255),
                font=font_label_sm,
            )
        elif "StiltSanctuary" in pname:
            lbl_box = (c_px[0] + 62, c_px[1] - 42)
            draw_ui.line([(c_px[0] + 36, c_px[1] - 12), (lbl_box[0] - 6, lbl_box[1] + 18)], fill=out_c, width=2)
            draw_ui.rounded_rectangle(
                [lbl_box[0] - 6, lbl_box[1] - 4, lbl_box[0] + 356, lbl_box[1] + 40],
                radius=5,
                fill=(12, 28, 28, 244),
                outline=out_c,
                width=2,
            )
            draw_ui.text(lbl_box, f"[4] STILT-SANCTUARY SPIRES ({px:.0f}m, {pz:.0f}m)", fill=(135, 255, 230, 255), font=font_label_md)
            draw_ui.text(
                (lbl_box[0], lbl_box[1] + 18),
                f"Footprint: {fw_m:.0f}x{fd_m:.0f}m | Teleport [4]: (315m, -145m)",
                fill=(195, 245, 235, 255),
                font=font_label_sm,
            )
        elif pname.startswith("FjordCliff"):
            short_lbl = (
                pname.replace("FjordCliff", "")
                .replace("Wall", "")
                .replace("_Port", " (W)")
                .replace("_Starboard", " (E)")
            )
            is_shack = "Shack" in pname
            lbl_col = (255, 210, 125, 255) if is_shack else (185, 215, 235, 235)
            offset_x = -182 if px < 0 else 36
            draw_ui.text(
                (c_px[0] + offset_x, c_px[1] - 7),
                f"{short_lbl} ({px:.0f},{pz:.0f})",
                fill=lbl_col,
                font=font_label_sm,
            )

    # Label the 75m Navigable Pass in Zone #2 Southern Breakwater Ridge
    pass_px = world_to_px(0.0, 360.0)
    draw_ui.text(
        (pass_px[0] - 62, pass_px[1] - 8),
        "<-- 75m PASS -->",
        fill=(255, 235, 145, 255),
        font=font_label_sm,
    )

    # Banner for "The Black Sound Fjord Walls (12 Segments)"
    fjord_wall_hdr_px = world_to_px(-545.0, -745.0)
    draw_ui.rounded_rectangle(
        [fjord_wall_hdr_px[0], fjord_wall_hdr_px[1], fjord_wall_hdr_px[0] + 292, fjord_wall_hdr_px[1] + 62],
        radius=5,
        fill=(16, 28, 40, 242),
        outline=(155, 195, 225, 240),
        width=2,
    )
    draw_ui.text(
        (fjord_wall_hdr_px[0] + 8, fjord_wall_hdr_px[1] + 5),
        "THE BLACK SOUND FJORD WALLS",
        fill=(185, 225, 250, 255),
        font=font_label_md,
    )
    draw_ui.text(
        (fjord_wall_hdr_px[0] + 8, fjord_wall_hdr_px[1] + 24),
        "12x Overlapping Segments (Z=-555m..-885m)",
        fill=(160, 200, 225, 255),
        font=font_label_sm,
    )
    draw_ui.text(
        (fjord_wall_hdr_px[0] + 8, fjord_wall_hdr_px[1] + 41),
        "Staggered Shacks: W(-626m) & E(-812m)",
        fill=(255, 208, 120, 255),
        font=font_label_sm,
    )

    # Plot Updated Teleport Target Markers [2], [3], [4]
    teleport_pts = [
        ("[2] TP (0,-455)", (0.0, -455.0), (255, 215, 110, 255)),
        ("[3] TP (0,-885)", (0.0, -885.0), (255, 185, 120, 255)),
        ("[4] TP (315,-145)", (315.0, -145.0), (120, 255, 225, 255)),
    ]
    for tp_lbl, (tx, tz), tp_col in teleport_pts:
        tpx = world_to_px(tx, tz)
        draw_ui.regular_polygon((tpx[0], tpx[1], 8), n_sides=3, rotation=0, fill=tp_col, outline=(15, 20, 25, 255))
        draw_ui.text((tpx[0] + 11, tpx[1] - 7), tp_lbl, fill=tp_col, font=font_label_sm)

    # 8. Plot All Grounded Maritime POIs inside the [-900..+900m, -1100..+700m] main chart
    poi_colors: Dict[str, Tuple[Tuple[int, int, int, int], str]] = {
        "shipwreck": ((245, 130, 65, 255), "Sunken Shipwreck"),
        "sea_fort": ((235, 195, 75, 255), "Sea-Fort Tower"),
        "leviathan_ribcage": ((65, 235, 195, 255), "Bone Skerry"),
        "derelict_lightship": ((225, 105, 245, 255), "Derelict Lightship"),
    }

    for poi in data["pois"]:
        px, pz = poi["pos_xz"]
        ptype = poi["type"]
        pidx = poi["index"]
        col, short_type = poi_colors.get(ptype, ((255, 255, 255, 255), ptype))
        if WORLD_X_MIN <= px <= WORLD_X_MAX and WORLD_Z_MIN <= pz <= WORLD_Z_MAX:
            p_px = world_to_px(px, pz)
            fw_m, fd_m = poi["footprint_xz"]
            draw_rotated_footprint(
                draw_geom,
                p_px,
                (max(11.0, fw_m * PX_PER_M), max(11.0, fd_m * PX_PER_M)),
                25.0,
                fill_color=(col[0], col[1], col[2], 220),
                outline_color=col,
                outline_width=2,
            )
            draw_geom.ellipse([p_px[0] - 10, p_px[1] - 10, p_px[0] + 10, p_px[1] + 10], outline=col, width=2)
            lbl_text = f"POI #{pidx:02d}: {short_type} ({px:.0f}, {pz:.0f})"
            if pidx in (0, 2, 6):
                lx, ly = p_px[0] + 14, p_px[1] - 8
            elif px < 0:
                lx, ly = p_px[0] - 235, p_px[1] - 8
            else:
                lx, ly = p_px[0] + 14, p_px[1] - 8
            draw_ui.text((lx, ly), lbl_text, fill=col, font=font_label_sm)

    # 9. Compass Rose (Top-Right inside chart)
    comp_cx, comp_cy = W - MARGIN_RIGHT - 130, MARGIN_TOP + 130
    comp_r = 68
    draw_ui.ellipse(
        [comp_cx - comp_r - 12, comp_cy - comp_r - 12, comp_cx + comp_r + 12, comp_cy + comp_r + 12],
        fill=(12, 24, 36, 240),
        outline=(110, 175, 210, 255),
        width=2,
    )
    draw_ui.ellipse(
        [comp_cx - comp_r, comp_cy - comp_r, comp_cx + comp_r, comp_cy + comp_r],
        outline=(80, 140, 175, 220),
        width=2,
    )
    draw_ui.polygon(
        [(comp_cx, comp_cy - comp_r + 4), (comp_cx - 12, comp_cy), (comp_cx + 12, comp_cy)],
        fill=(255, 195, 85, 255),
    )
    draw_ui.polygon(
        [(comp_cx, comp_cy + comp_r - 4), (comp_cx - 10, comp_cy), (comp_cx + 10, comp_cy)],
        fill=(110, 165, 195, 240),
    )
    draw_ui.line([(comp_cx - comp_r + 6, comp_cy), (comp_cx + comp_r - 6, comp_cy)], fill=(140, 195, 225, 240), width=3)
    draw_ui.text((comp_cx - 32, comp_cy - comp_r - 32), "N (-Z)", fill=(255, 210, 105, 255), font=font_compass)
    draw_ui.text((comp_cx - 30, comp_cy + comp_r + 14), "S (+Z)", fill=(165, 210, 235, 255), font=font_compass)
    draw_ui.text((comp_cx + comp_r + 16, comp_cy - 11), "E (+X)", fill=(165, 210, 235, 255), font=font_compass)
    draw_ui.text((comp_cx - comp_r - 72, comp_cy - 11), "W (-X)", fill=(165, 210, 235, 255), font=font_compass)

    # 10. Full-Ocean Inset Map (Bottom-Right Corner) showing all 20 POIs & [-2200m .. +2200m] Archipelago
    inset_w, inset_h = 430, 430
    inset_x0 = W - MARGIN_RIGHT - inset_w - 16
    inset_y0 = H - MARGIN_BOTTOM - inset_h - 16
    draw_ui.rounded_rectangle(
        [inset_x0, inset_y0, inset_x0 + inset_w, inset_y0 + inset_h],
        radius=8,
        fill=(8, 17, 26, 248),
        outline=(110, 175, 210, 255),
        width=3,
    )
    draw_ui.text(
        (inset_x0 + 14, inset_y0 + 10),
        "FULL-OCEAN ARCHIPELAGO INSET (-2200m..+2200m)",
        fill=(200, 235, 255, 255),
        font=font_label_md,
    )
    inset_pad = 34
    ix_min, ix_max = inset_x0 + inset_pad, inset_x0 + inset_w - inset_pad
    iy_min, iy_max = inset_y0 + 36, inset_y0 + inset_h - 22
    in_span_m = 4400.0

    def inset_to_px(wx: float, wz: float) -> Tuple[float, float]:
        ux = (wx + 2200.0) / in_span_m
        uz = (wz + 2200.0) / in_span_m
        return (ix_min + ux * (ix_max - ix_min), iy_min + uz * (iy_max - iy_min))

    draw_ui.rectangle([ix_min, iy_min, ix_max, iy_max], fill=(11, 24, 36, 255), outline=(65, 110, 140, 240), width=1)
    in_orig = inset_to_px(0.0, 0.0)
    draw_ui.line([(in_orig[0], iy_min), (in_orig[0], iy_max)], fill=(45, 80, 105, 220), width=1)
    draw_ui.line([(ix_min, in_orig[1]), (ix_max, in_orig[1])], fill=(45, 80, 105, 220), width=1)

    vp_tl = inset_to_px(WORLD_X_MIN, WORLD_Z_MIN)
    vp_br = inset_to_px(WORLD_X_MAX, WORLD_Z_MAX)
    draw_ui.rectangle([vp_tl[0], vp_tl[1], vp_br[0], vp_br[1]], outline=(255, 210, 95, 240), width=2)
    draw_ui.text((vp_tl[0] + 4, vp_tl[1] + 2), "Main Chart Area", fill=(255, 210, 95, 240), font=font_label_sm)

    for poi in data["pois"]:
        px, pz = poi["pos_xz"]
        ptype = poi["type"]
        pidx = poi["index"]
        col, _ = poi_colors.get(ptype, ((255, 255, 255, 255), ptype))
        ipx, ipy = inset_to_px(px, pz)
        draw_ui.ellipse([ipx - 4, ipy - 4, ipx + 4, ipy + 4], fill=col)
        if abs(px) > 850 or pz > 650 or pz < -1050:
            draw_ui.text((ipx + 5, ipy - 6), f"#{pidx:02d}({int(px)},{int(pz)})", fill=col, font=font_label_sm)

    # 11. Legend & Coordinate Summary Box (Bottom-Left Corner)
    leg_w, leg_h = 540, 336
    leg_x0 = MARGIN_LEFT + 16
    leg_y0 = H - MARGIN_BOTTOM - leg_h - 16
    draw_ui.rounded_rectangle(
        [leg_x0, leg_y0, leg_x0 + leg_w, leg_y0 + leg_h],
        radius=8,
        fill=(8, 17, 26, 248),
        outline=(110, 175, 210, 255),
        width=3,
    )
    draw_ui.text((leg_x0 + 16, leg_y0 + 10), "NAUTICAL CHART LEGEND & PARSED COORDINATES", fill=(205, 240, 255, 255), font=font_sec_hdr)

    legend_rows = [
        ((130, 255, 180, 255), "[1] Starting Harbor & Wharf (0m, 0m) | Open 220m Departure Bay"),
        ((255, 215, 125, 255), "[2] Fjord Entrance Gate Arch (0m, -520m) | TP [2]: (0m, -455m)"),
        ((165, 195, 220, 255), "Black Sound Fjord: 12 Cliff Segments (Z=-555..-885m, Staggered Shacks)"),
        ((255, 195, 135, 255), "[3] Terraced Fishing Hamlet Island (0m, -960m) | TP [3]: (0m, -885m)"),
        ((135, 255, 230, 255), "[4] Stilt-Sanctuary Spires (+380m, -180m) | TP [4]: (+315m, -145m)"),
        ((255, 188, 58, 255), "Zones #1-#4: 4 Navigable Barrier Island Chains (13 Cliff Segments)"),
        ((255, 70, 50, 255), "6x Rusted Channel Warning Buoys (X=±14..15m, Z=-32m to -140m)"),
        ((245, 130, 65, 255), "POI Sunken Shipwrecks (#00,#04,#08,#12,#16)"),
        ((235, 195, 75, 255), "POI Sea-Fort Watchtowers (#01,#05,#09,#13,#17)"),
        ((65, 235, 195, 255), "POI Leviathan Bone Skerries (#02,#06,#10,#14,#18)"),
        ((225, 105, 245, 255), "POI Derelict Lightships (#03,#07,#11,#15,#19)"),
    ]
    ry = leg_y0 + 40
    for swatch_col, row_txt in legend_rows:
        draw_ui.rectangle([leg_x0 + 16, ry + 3, leg_x0 + 32, ry + 17], fill=swatch_col, outline=(255, 255, 255, 220), width=1)
        draw_ui.text((leg_x0 + 42, ry), row_txt, fill=(220, 235, 245, 255), font=font_label_sm)
        ry += 26

    # 12. Top Header Banner
    draw_ui.text(
        (MARGIN_LEFT, 22),
        "NORTHERN DREDGE — TOP-DOWN NAUTICAL CHART (Z: -1100m to +700m | 2048x2048)",
        fill=(225, 245, 255, 255),
        font=font_title,
    )
    draw_ui.text(
        (MARGIN_LEFT, 58),
        "Parsed from res://scripts/world_builder.gd | 12-Segment Extended Fjord, Uncluttered Harbor (220m), Scattered POIs & 4 Barrier Chains",
        fill=(155, 200, 225, 255),
        font=font_subtitle,
    )

    comp = Image.alpha_composite(base_img, overlay_zones)
    comp = Image.alpha_composite(comp, overlay_geom)
    comp = Image.alpha_composite(comp, overlay_ui)
    rgb_img = comp.convert("RGB")
    try:
        if OUTPUT_PNG_PATH.exists():
            OUTPUT_PNG_PATH.unlink()
        rgb_img.save(OUTPUT_PNG_PATH, format="PNG")
        print(f"[generate_world_map_png] Saved 2048x2048 chart to: {OUTPUT_PNG_PATH}")
    except OSError:
        alt_path = PROJECT_ROOT / "world_map_overview_v2.png"
        rgb_img.save(alt_path, format="PNG")
        print(f"[generate_world_map_png] Primary file locked by viewer; saved to: {alt_path}")


if __name__ == "__main__":
    generate_map()
