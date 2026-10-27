class_name SonarSystem
extends CanvasLayer

const UI_VOID_BLACK: Color = Color(0.027, 0.035, 0.047, 0.97)
const UI_CORRODED_IRON: Color = Color(0.078, 0.094, 0.114, 0.95)
const UI_TARNISHED_BRASS: Color = Color(0.549, 0.427, 0.231, 1.0)
const UI_BRASS_HIGHLIGHT: Color = Color(0.769, 0.604, 0.322, 1.0)
const UI_BLOOD_CRIMSON: Color = Color(0.478, 0.110, 0.110, 1.0)
const UI_CRIMSON_BRIGHT: Color = Color(0.722, 0.157, 0.157, 1.0)
const UI_ELDRITCH_TEAL: Color = Color(0.220, 0.557, 0.478, 1.0)
const UI_BONE_PARCHMENT: Color = Color(0.847, 0.808, 0.722, 1.0)
const UI_MUTED_PARCHMENT: Color = Color(0.580, 0.545, 0.478, 1.0)

const GRAPH_WIDTH: int = 220
const GRAPH_HEIGHT: int = 135
const MAX_DISPLAY_DEPTH: float = 140.0
const SCROLL_INTERVAL: float = 0.08

@export var boat: Node3D
@export var world_builder: Node3D

@onready var sonar_panel: PanelContainer = $SonarPanel as PanelContainer
@onready var depth_label: Label = $SonarPanel/MarginContainer/VBoxContainer/HeaderRow/DepthLabel as Label
@onready var activity_label: Label = $SonarPanel/MarginContainer/VBoxContainer/HeaderRow/ActivityLabel as Label
@onready var zone_label: Label = $SonarPanel/MarginContainer/VBoxContainer/ZoneLabel as Label
@onready var waterfall_frame: PanelContainer = $SonarPanel/MarginContainer/VBoxContainer/WaterfallFrame as PanelContainer
@onready var waterfall_rect: TextureRect = $SonarPanel/MarginContainer/VBoxContainer/WaterfallFrame/WaterfallTexture as TextureRect
@onready var prompt_label: Label = $SonarPanel/MarginContainer/VBoxContainer/PromptLabel as Label
@onready var catch_banner_panel: PanelContainer = $CatchBannerPanel as PanelContainer
@onready var catch_banner_label: Label = $CatchBannerPanel/MarginContainer/CatchBannerLabel as Label

var hook_active: bool = false
var hook_depth_m: float = 0.0
var is_fish_hooked: bool = false
var line_tension_pct: float = 0.0

var _sonar_frame_overlay: Control = null
var _porthole_glass_overlay: Control = null
var _plaque_frame_overlay: Control = null

var _seabed_noise: FastNoiseLite = FastNoiseLite.new()
var _biomass_noise: FastNoiseLite = FastNoiseLite.new()
var _school_band_noise: FastNoiseLite = FastNoiseLite.new()

var _waterfall_image: Image
var _waterfall_texture: ImageTexture
var _scroll_timer: float = 0.0
var _banner_timer: float = 0.0
var _hotspot_positions: Array[Vector2] = []
var _arch_monolith_positions: Array[Vector2] = []
var _poi_hotspots: Array[Dictionary] = []
var _active_poi_banner_title: String = ""
var _hotspots_cached: bool = false
var _last_reading: Dictionary = {
	"seabed_depth": 42.0,
	"biomass_density": 0.12,
	"school_depth_min": 18.0,
	"school_depth_max": 26.0,
	"activity_tier": "DEAD WATER",
	"near_rock_hazard": false,
	"near_arch_monolith": false,
	"near_poi_hotspot": false,
	"near_poi_discovery": false,
	"nearby_poi_title": "",
}


func _ready() -> void:
	add_to_group("sonar_system")

	_seabed_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_seabed_noise.seed = 4410
	_seabed_noise.frequency = 0.0022
	_seabed_noise.fractal_type = FastNoiseLite.FRACTAL_FBM
	_seabed_noise.fractal_octaves = 4

	_biomass_noise.noise_type = FastNoiseLite.TYPE_CELLULAR
	_biomass_noise.seed = 8821
	_biomass_noise.frequency = 0.0045
	_biomass_noise.fractal_type = FastNoiseLite.FRACTAL_FBM
	_biomass_noise.fractal_octaves = 3

	_school_band_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_school_band_noise.seed = 6109
	_school_band_noise.frequency = 0.008

	_waterfall_image = Image.create(GRAPH_WIDTH, GRAPH_HEIGHT, false, Image.FORMAT_RGBA8)
	_waterfall_image.fill(Color(0.02, 0.05, 0.05, 1.0))
	_draw_initial_grid()
	_waterfall_texture = ImageTexture.create_from_image(_waterfall_image)
	if waterfall_rect != null:
		waterfall_rect.texture = _waterfall_texture

	if catch_banner_panel != null:
		catch_banner_panel.visible = false

	_setup_lovecraft_sonar_overlays()


func _setup_lovecraft_sonar_overlays() -> void:
	if sonar_panel != null:
		_sonar_frame_overlay = Control.new()
		_sonar_frame_overlay.name = "BathysphereCasingOverlay"
		_sonar_frame_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_sonar_frame_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
		_sonar_frame_overlay.draw.connect(_on_draw_sonar_casing)
		sonar_panel.add_child(_sonar_frame_overlay)
		sonar_panel.move_child(_sonar_frame_overlay, 0)

	if waterfall_frame != null:
		_porthole_glass_overlay = Control.new()
		_porthole_glass_overlay.name = "PortholeGlassOverlay"
		_porthole_glass_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_porthole_glass_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
		_porthole_glass_overlay.draw.connect(_on_draw_porthole_glass)
		waterfall_frame.add_child(_porthole_glass_overlay)

	if catch_banner_panel != null:
		_plaque_frame_overlay = Control.new()
		_plaque_frame_overlay.name = "SpecimenPlaqueOverlay"
		_plaque_frame_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_plaque_frame_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
		_plaque_frame_overlay.draw.connect(_on_draw_specimen_plaque)
		catch_banner_panel.add_child(_plaque_frame_overlay)
		catch_banner_panel.move_child(_plaque_frame_overlay, 0)


func _on_draw_sonar_casing() -> void:
	if _sonar_frame_overlay == null:
		return
	var rect: Rect2 = Rect2(Vector2.ZERO, _sonar_frame_overlay.size)
	_draw_sonar_lovecraft_frame(
		_sonar_frame_overlay,
		rect,
		UI_TARNISHED_BRASS,
		UI_BRASS_HIGHLIGHT,
		clampf((line_tension_pct - 75.0) / 25.0, 0.0, 1.0)
	)


func _on_draw_porthole_glass() -> void:
	if _porthole_glass_overlay == null:
		return
	var sz: Vector2 = _porthole_glass_overlay.size
	if sz.x < 16.0 or sz.y < 16.0:
		return

	# 1. Dark phosphor horizontal scanlines
	var scan_col: Color = Color(0.02, 0.03, 0.04, 0.32)
	var y_step: int = 3
	var max_y: int = int(sz.y)
	for sy: int in range(0, max_y, y_step):
		_porthole_glass_overlay.draw_line(Vector2(0.0, float(sy)), Vector2(sz.x, float(sy)), scan_col, 1.0)

	# 2. Cracked Bathysphere Porthole Glass Vignette & Fracture Lines
	var vig_col: Color = Color(0.02, 0.03, 0.04, 0.55)
	_porthole_glass_overlay.draw_rect(Rect2(Vector2.ZERO, sz), vig_col, false, 6.0)
	_porthole_glass_overlay.draw_rect(Rect2(Vector2.ZERO, sz).grow(-1.0), UI_TARNISHED_BRASS, false, 2.0)

	var crack_col: Color = Color(0.68, 0.82, 0.78, 0.22)
	_porthole_glass_overlay.draw_line(Vector2(6.0, 18.0), Vector2(24.0, 29.0), crack_col, 1.1)
	_porthole_glass_overlay.draw_line(Vector2(24.0, 29.0), Vector2(38.0, 25.0), crack_col, 1.0)
	_porthole_glass_overlay.draw_line(Vector2(24.0, 29.0), Vector2(31.0, 42.0), crack_col, 0.9)

	# 3. Bolted Brass Corner Flanges
	var corners: Array[Vector2] = [
		Vector2(8.0, 8.0),
		Vector2(sz.x - 8.0, 8.0),
		Vector2(sz.x - 8.0, sz.y - 8.0),
		Vector2(8.0, sz.y - 8.0),
	]
	for cp: Vector2 in corners:
		_porthole_glass_overlay.draw_circle(cp, 4.2, UI_CORRODED_IRON)
		_porthole_glass_overlay.draw_circle(cp, 2.5, UI_BRASS_HIGHLIGHT)

	# 4. Eerie Abyssal Depth Ruler along Right Edge (Roman Numerals I, II, III)
	var ruler_x: float = sz.x - 28.0
	var y_35: float = (35.0 / MAX_DISPLAY_DEPTH) * sz.y
	var y_75: float = (75.0 / MAX_DISPLAY_DEPTH) * sz.y
	_porthole_glass_overlay.draw_rect(Rect2(ruler_x, 2.0, 26.0, sz.y - 4.0), Color(0.03, 0.04, 0.05, 0.76), true)
	_porthole_glass_overlay.draw_line(Vector2(ruler_x, 2.0), Vector2(ruler_x, sz.y - 2.0), UI_TARNISHED_BRASS, 1.2)
	_porthole_glass_overlay.draw_line(Vector2(ruler_x, y_35), Vector2(sz.x - 2.0, y_35), UI_BRASS_HIGHLIGHT, 1.5)
	_porthole_glass_overlay.draw_line(Vector2(ruler_x, y_75), Vector2(sz.x - 2.0, y_75), UI_CRIMSON_BRIGHT, 1.5)

	var font: Font = ThemeDB.fallback_font
	if font != null:
		_porthole_glass_overlay.draw_string(
			font,
			Vector2(ruler_x + 8.0, y_35 * 0.5 + 5.0),
			"I",
			HORIZONTAL_ALIGNMENT_LEFT,
			-1.0,
			12,
			UI_ELDRITCH_TEAL
		)
		_porthole_glass_overlay.draw_string(
			font,
			Vector2(ruler_x + 6.0, (y_35 + y_75) * 0.5 + 5.0),
			"II",
			HORIZONTAL_ALIGNMENT_LEFT,
			-1.0,
			12,
			UI_BRASS_HIGHLIGHT
		)
		_porthole_glass_overlay.draw_string(
			font,
			Vector2(ruler_x + 4.0, (y_75 + sz.y) * 0.5 + 5.0),
			"III",
			HORIZONTAL_ALIGNMENT_LEFT,
			-1.0,
			12,
			UI_CRIMSON_BRIGHT
		)


func _on_draw_specimen_plaque() -> void:
	if _plaque_frame_overlay == null:
		return
	var rect: Rect2 = Rect2(Vector2.ZERO, _plaque_frame_overlay.size)
	_draw_sonar_lovecraft_frame(
		_plaque_frame_overlay,
		rect,
		UI_BRASS_HIGHLIGHT,
		UI_TARNISHED_BRASS,
		0.25
	)
	_draw_sonar_gothic_divider(_plaque_frame_overlay, Vector2(rect.size.x * 0.5, 9.0), rect.size.x * 0.34, UI_BRASS_HIGHLIGHT)
	_draw_sonar_gothic_divider(_plaque_frame_overlay, Vector2(rect.size.x * 0.5, rect.size.y - 9.0), rect.size.x * 0.34, UI_TARNISHED_BRASS)
	_draw_sonar_wax_seal(_plaque_frame_overlay, Vector2(22.0, rect.size.y * 0.5), 9.5)
	_draw_sonar_wax_seal(_plaque_frame_overlay, Vector2(rect.size.x - 22.0, rect.size.y * 0.5), 9.5)


func _draw_sonar_lovecraft_frame(
	canvas: CanvasItem,
	rect: Rect2,
	outer_brass: Color,
	inner_accent: Color,
	stress_pulse: float
) -> void:
	if canvas == null or rect.size.x < 16.0 or rect.size.y < 16.0:
		return
	var x0: float = rect.position.x
	var y0: float = rect.position.y
	var w: float = rect.size.x
	var h: float = rect.size.y
	var x1: float = x0 + w
	var y1: float = y0 + h

	canvas.draw_rect(rect, UI_VOID_BLACK, true)
	canvas.draw_rect(rect.grow(-4.0), UI_CORRODED_IRON.darkened(0.28), true)
	var deep_core: Rect2 = rect.grow(-11.0)
	if deep_core.size.x > 4.0 and deep_core.size.y > 4.0:
		canvas.draw_rect(deep_core, UI_VOID_BLACK, true)

	if stress_pulse > 0.01:
		var glow_a: float = clampf(stress_pulse * 0.45, 0.0, 0.65)
		canvas.draw_rect(rect.grow(-2.0), Color(UI_CRIMSON_BRIGHT.r, UI_CRIMSON_BRIGHT.g, UI_CRIMSON_BRIGHT.b, glow_a), false, 4.0)
		canvas.draw_rect(rect.grow(-6.0), Color(UI_BLOOD_CRIMSON.r, UI_BLOOD_CRIMSON.g, UI_BLOOD_CRIMSON.b, glow_a * 0.6), false, 3.0)

	canvas.draw_rect(rect.grow(-1.0), outer_brass, false, 2.0)
	canvas.draw_rect(rect.grow(-5.0), inner_accent.darkened(0.18), false, 1.2)

	var corner_len: float = minf(22.0, minf(w, h) * 0.22)
	var spike_inset: float = 9.0
	var corners: Array[Vector2] = [Vector2(x0, y0), Vector2(x1, y0), Vector2(x1, y1), Vector2(x0, y1)]
	var signs: Array[Vector2] = [Vector2(1.0, 1.0), Vector2(-1.0, 1.0), Vector2(-1.0, -1.0), Vector2(1.0, -1.0)]
	for idx: int in range(4):
		var c: Vector2 = corners[idx]
		var s: Vector2 = signs[idx]
		canvas.draw_line(c + Vector2(s.x * 2.0, s.y * 2.0), c + Vector2(s.x * corner_len, s.y * 2.0), inner_accent, 2.5)
		canvas.draw_line(c + Vector2(s.x * 2.0, s.y * 2.0), c + Vector2(s.x * 2.0, s.y * corner_len), inner_accent, 2.5)
		var diag_a: Vector2 = c + Vector2(s.x * corner_len * 0.72, s.y * 5.0)
		var diag_b: Vector2 = c + Vector2(s.x * 5.0, s.y * corner_len * 0.72)
		var spike_tip: Vector2 = c + Vector2(s.x * spike_inset, s.y * spike_inset)
		canvas.draw_line(diag_a, diag_b, outer_brass, 1.4)
		var poly: PackedVector2Array = PackedVector2Array([
			c + Vector2(s.x * 2.5, s.y * 2.5),
			c + Vector2(s.x * (spike_inset + 5.0), s.y * 3.5),
			spike_tip,
			c + Vector2(s.x * 3.5, s.y * (spike_inset + 5.0)),
		])
		canvas.draw_colored_polygon(poly, outer_brass.darkened(0.15))
		var rivet_pos: Vector2 = c + Vector2(s.x * 7.5, s.y * 7.5)
		canvas.draw_circle(rivet_pos, 2.4, UI_CORRODED_IRON)
		canvas.draw_circle(rivet_pos, 1.5, inner_accent)


func _draw_sonar_gothic_divider(canvas: CanvasItem, center: Vector2, half_width: float, col: Color) -> void:
	var left_pt: Vector2 = center - Vector2(half_width, 0.0)
	var right_pt: Vector2 = center + Vector2(half_width, 0.0)
	canvas.draw_line(left_pt, right_pt, col, 1.4)
	var diamond: PackedVector2Array = PackedVector2Array([
		center + Vector2(0.0, -4.5),
		center + Vector2(7.0, 0.0),
		center + Vector2(0.0, 4.5),
		center + Vector2(-7.0, 0.0),
	])
	canvas.draw_colored_polygon(diamond, col)
	canvas.draw_circle(left_pt, 2.0, col)
	canvas.draw_circle(right_pt, 2.0, col)


func _draw_sonar_wax_seal(canvas: CanvasItem, center: Vector2, radius: float) -> void:
	canvas.draw_circle(center + Vector2(1.0, 1.5), radius + 1.0, Color(0.0, 0.0, 0.0, 0.65))
	canvas.draw_circle(center, radius, UI_BLOOD_CRIMSON)
	canvas.draw_circle(center, radius * 0.78, UI_CRIMSON_BRIGHT.darkened(0.15))
	canvas.draw_arc(center, radius * 0.78, 0.0, TAU, 20, UI_BONE_PARCHMENT.darkened(0.25), 1.2)
	canvas.draw_line(center + Vector2(-radius * 0.42, 0.0), center + Vector2(radius * 0.42, 0.0), UI_BONE_PARCHMENT, 1.3)
	canvas.draw_line(center + Vector2(0.0, -radius * 0.42), center + Vector2(0.0, radius * 0.42), UI_BONE_PARCHMENT, 1.3)


func _process(delta: float) -> void:
	if not _hotspots_cached:
		_cache_world_hotspots()

	if _banner_timer > 0.0:
		_banner_timer -= delta
		if _banner_timer <= 0.0 and catch_banner_panel != null:
			catch_banner_panel.visible = false

	if boat == null:
		boat = get_parent().get_node_or_null("Boat") as Node3D
	if world_builder == null:
		world_builder = get_parent().get_node_or_null("WorldBuilder") as Node3D

	var sample_pos: Vector3 = boat.global_position if boat != null else Vector3.ZERO
	var now_sec: float = float(Time.get_ticks_msec()) * 0.001
	_last_reading = get_sonar_reading_at(sample_pos, now_sec)

	_scroll_timer += delta
	if _scroll_timer >= SCROLL_INTERVAL:
		_scroll_timer = fmod(_scroll_timer, SCROLL_INTERVAL)
		_advance_waterfall_column(_last_reading, now_sec)

	_update_hud_labels(_last_reading)


func show_catch_banner(message: String, duration: float = 3.2) -> void:
	if catch_banner_label != null:
		catch_banner_label.text = message
	if catch_banner_panel != null:
		catch_banner_panel.visible = true
	if _plaque_frame_overlay != null:
		_plaque_frame_overlay.queue_redraw()
	_banner_timer = duration


func get_last_reading() -> Dictionary:
	return _last_reading


func get_sonar_reading_at(world_pos: Vector3, time: float) -> Dictionary:
	var pos_xz: Vector2 = Vector2(world_pos.x, world_pos.z)

	# Proximity to nearest island shelf, reef, or sea arch in WorldBuilder
	var min_dist: float = _get_nearest_feature_distance(pos_xz)
	var arch_dist: float = _get_nearest_arch_distance(pos_xz)
	var poi_info: Dictionary = _get_nearest_poi_info(pos_xz)
	var poi_dist: float = poi_info.get("distance", 9999.0) as float
	var near_poi_hotspot: bool = poi_dist <= 35.0
	var near_poi_discovery: bool = poi_dist <= 45.0
	var nearby_poi_title: String = (poi_info.get("discovery_title", "") as String) if near_poi_discovery else ""
	var near_rock_hazard: bool = min_dist <= 115.0 or near_poi_hotspot
	var near_arch_monolith: bool = arch_dist <= 125.0 or near_poi_hotspot

	# 1. Seabed depth (12m near coastal shelves/harbor -> up to 135m in deep abyssal trenches)
	var shelf_factor: float = clampf((min_dist - 18.0) / 145.0, 0.0, 1.0)
	var macro_bathy: float = (_seabed_noise.get_noise_2d(pos_xz.x, pos_xz.y) + 1.0) * 0.5
	var ridge_detail: float = _seabed_noise.get_noise_2d(pos_xz.x * 3.1, pos_xz.y * 3.1) * 9.5
	var raw_depth: float = lerpf(13.5, 48.0 + macro_bathy * 84.0, shelf_factor) + ridge_detail
	var seabed_depth: float = clampf(raw_depth, 12.0, 135.0)

	# 2. Biomass density: congregates near drop-offs (min_dist 22m..110m) + migrating 3D cellular schools
	var dropoff_ring: float = exp(-pow((min_dist - 52.0) / 38.0, 2.0))
	var harbor_shoal: float = exp(-pow((pos_xz.distance_to(Vector2(0.0, -18.0))) / 42.0, 2.0)) * 0.68
	var migrating_cell: float = (_biomass_noise.get_noise_3d(pos_xz.x, pos_xz.y, time * 4.5) + 1.0) * 0.5
	var school_pulse: float = pow(clampf(migrating_cell, 0.0, 1.0), 1.8)

	var biomass: float = 0.07 + dropoff_ring * 0.56 + harbor_shoal + school_pulse * 0.42
	if min_dist > 165.0 and school_pulse < 0.58 and not near_poi_hotspot:
		# Open dead water between reefs has low background biomass (0.05..0.15)
		biomass = clampf(0.05 + school_pulse * 0.16, 0.05, 0.15)
	else:
		biomass = clampf(biomass, 0.05, 1.0)

	if near_poi_hotspot:
		var poi_biomass_boost: float = lerpf(1.0, 0.80, clampf(poi_dist / 35.0, 0.0, 1.0))
		biomass = clampf(maxf(biomass, poi_biomass_boost), 0.80, 1.0)

	# 3. Fish school vertical depth band (suspended above seabed drop-offs)
	var band_wave: float = (_school_band_noise.get_noise_3d(pos_xz.x, pos_xz.y, time * 2.2) + 1.0) * 0.5
	var center_frac: float = lerpf(0.42, 0.76, band_wave)
	var school_center: float = clampf(seabed_depth * center_frac, 6.5, seabed_depth - 3.5)
	var half_span: float = lerpf(2.8, 7.5, biomass)
	var school_depth_min: float = maxf(4.0, school_center - half_span)
	var school_depth_max: float = minf(seabed_depth - 1.5, school_center + half_span)

	var activity_tier: String = "DEAD WATER"
	if biomass >= 0.70:
		activity_tier = "DENSE SHOAL"
	elif biomass >= 0.42:
		activity_tier = "ACTIVE SCHOOL"
	elif biomass >= 0.18:
		activity_tier = "SCATTERED"

	return {
		"seabed_depth": seabed_depth,
		"biomass_density": biomass,
		"school_depth_min": school_depth_min,
		"school_depth_max": school_depth_max,
		"activity_tier": activity_tier,
		"near_rock_hazard": near_rock_hazard,
		"near_arch_monolith": near_arch_monolith,
		"near_poi_hotspot": near_poi_hotspot,
		"near_poi_discovery": near_poi_discovery,
		"nearby_poi_title": nearby_poi_title,
	}


func _cache_world_hotspots() -> void:
	if world_builder == null:
		world_builder = get_parent().get_node_or_null("WorldBuilder") as Node3D
	if world_builder == null:
		return

	_hotspot_positions.clear()
	_arch_monolith_positions.clear()
	_poi_hotspots.clear()
	# Starting Wharf Port shelf hotspot
	_hotspot_positions.append(Vector2(0.0, 12.0))

	var groups_to_scan: Array[String] = ["ArchipelagoIslands", "JaggedRockFormations"]
	for group_name: String in groups_to_scan:
		var container: Node3D = world_builder.get_node_or_null(group_name) as Node3D
		if container == null:
			continue
		for child: Node in container.get_children():
			var node3d: Node3D = child as Node3D
			if node3d != null and not node3d.name.ends_with("_Foam"):
				var pos2: Vector2 = Vector2(node3d.position.x, node3d.position.z)
				_hotspot_positions.append(pos2)
				if group_name == "JaggedRockFormations":
					_arch_monolith_positions.append(pos2)

	if world_builder.has_method("get_poi_hotspots"):
		var raw_pois: Array = world_builder.call("get_poi_hotspots") as Array
		for entry_var: Variant in raw_pois:
			if entry_var is Dictionary:
				var entry_dict: Dictionary = entry_var as Dictionary
				_poi_hotspots.append(entry_dict)
				var p_xz: Vector2 = entry_dict.get("position_xz", Vector2.ZERO) as Vector2
				_hotspot_positions.append(p_xz)
				_arch_monolith_positions.append(p_xz)

	if not _hotspot_positions.is_empty():
		_hotspots_cached = true


func _get_nearest_poi_info(pos_xz: Vector2) -> Dictionary:
	var best_dist: float = 99999.0
	var best_type: String = ""
	var best_title: String = ""
	var best_habitat: String = ""
	for entry: Dictionary in _poi_hotspots:
		var p_xz: Vector2 = entry.get("position_xz", Vector2.ZERO) as Vector2
		var d: float = pos_xz.distance_to(p_xz)
		if d < best_dist:
			best_dist = d
			best_type = entry.get("poi_type", "") as String
			best_title = entry.get("discovery_title", "") as String
			best_habitat = entry.get("habitat_tag", "") as String
	return {
		"distance": best_dist,
		"poi_type": best_type,
		"discovery_title": best_title,
		"habitat_tag": best_habitat,
	}


func _get_nearest_feature_distance(pos_xz: Vector2) -> float:
	if _hotspot_positions.is_empty():
		return pos_xz.distance_to(Vector2(0.0, 20.0))

	var best_dist_sq: float = 1.0e12
	for hp: Vector2 in _hotspot_positions:
		var d_sq: float = pos_xz.distance_squared_to(hp)
		if d_sq < best_dist_sq:
			best_dist_sq = d_sq
	return sqrt(best_dist_sq)


func _get_nearest_arch_distance(pos_xz: Vector2) -> float:
	if _arch_monolith_positions.is_empty():
		return 999.0

	var best_dist_sq: float = 1.0e12
	for ap: Vector2 in _arch_monolith_positions:
		var d_sq: float = pos_xz.distance_squared_to(ap)
		if d_sq < best_dist_sq:
			best_dist_sq = d_sq
	return sqrt(best_dist_sq)


func _draw_initial_grid() -> void:
	var y_35m: int = clampi(int((35.0 / MAX_DISPLAY_DEPTH) * float(GRAPH_HEIGHT)), 1, GRAPH_HEIGHT - 2)
	var y_75m: int = clampi(int((75.0 / MAX_DISPLAY_DEPTH) * float(GRAPH_HEIGHT)), 1, GRAPH_HEIGHT - 2)
	for x: int in range(GRAPH_WIDTH):
		for y: int in range(GRAPH_HEIGHT):
			var bg: Color = Color(0.02, 0.05, 0.05, 1.0)
			if y == y_35m or y == y_75m:
				bg = Color(0.09, 0.20, 0.18, 1.0)
			elif y % 28 == 0:
				bg = Color(0.05, 0.12, 0.10, 1.0)
			_waterfall_image.set_pixel(x, y, bg)


func _advance_waterfall_column(reading: Dictionary, time_sec: float) -> void:
	# Shift existing waterfall image 1 pixel left
	var sub_rect: Rect2i = Rect2i(1, 0, GRAPH_WIDTH - 1, GRAPH_HEIGHT)
	_waterfall_image.blit_rect(_waterfall_image, sub_rect, Vector2i(0, 0))

	var seabed_depth: float = reading.get("seabed_depth", 45.0) as float
	var biomass: float = reading.get("biomass_density", 0.1) as float
	var school_min: float = reading.get("school_depth_min", 15.0) as float
	var school_max: float = reading.get("school_depth_max", 25.0) as float

	var seabed_y: int = clampi(int((seabed_depth / MAX_DISPLAY_DEPTH) * float(GRAPH_HEIGHT)), 6, GRAPH_HEIGHT - 2)
	var school_y0: int = clampi(int((school_min / MAX_DISPLAY_DEPTH) * float(GRAPH_HEIGHT)), 2, seabed_y - 2)
	var school_y1: int = clampi(int((school_max / MAX_DISPLAY_DEPTH) * float(GRAPH_HEIGHT)), school_y0 + 1, seabed_y - 1)
	var hook_y: int = clampi(int((hook_depth_m / MAX_DISPLAY_DEPTH) * float(GRAPH_HEIGHT)), 1, GRAPH_HEIGHT - 2)
	var y_35m: int = clampi(int((35.0 / MAX_DISPLAY_DEPTH) * float(GRAPH_HEIGHT)), 1, GRAPH_HEIGHT - 2)
	var y_75m: int = clampi(int((75.0 / MAX_DISPLAY_DEPTH) * float(GRAPH_HEIGHT)), 1, GRAPH_HEIGHT - 2)

	var right_x: int = GRAPH_WIDTH - 1
	var arch_wave: float = sin(time_sec * 6.5) * 0.5 + 0.5

	for y: int in range(GRAPH_HEIGHT):
		var col: Color = Color(0.02, 0.05, 0.05, 1.0)
		# Depth zone boundary markers at 35m and 75m + gridlines
		if y == y_35m or y == y_75m:
			col = Color(0.09, 0.21, 0.19, 1.0)
		elif y % 28 == 0:
			col = Color(0.05, 0.13, 0.11, 1.0)

		if y == seabed_y or y == seabed_y + 1:
			# Bright amber-gold seabed contour line
			col = Color(0.92, 0.64, 0.22, 1.0)
		elif y > seabed_y + 1:
			# Sub-bottom sediment return shading
			var sed_fade: float = clampf(1.0 - float(y - seabed_y) / 26.0, 0.12, 1.0)
			col = Color(0.34 * sed_fade, 0.21 * sed_fade, 0.09 * sed_fade, 1.0)
		elif y >= school_y0 and y <= school_y1 and biomass > 0.16:
			# Fish arch / baitball return echo
			var band_mid: float = float(school_y0 + school_y1) * 0.5
			var band_half: float = maxf(1.0, float(school_y1 - school_y0) * 0.5)
			var radial: float = 1.0 - absf(float(y) - band_mid) / band_half
			var echo_mask: float = radial * (0.55 + 0.45 * arch_wave) * biomass
			if echo_mask > 0.22:
				if biomass >= 0.70:
					col = Color(1.0, 0.34, 0.12, 1.0)
				elif biomass >= 0.42:
					col = Color(0.98, 0.74, 0.20, 1.0)
				else:
					col = Color(0.24, 0.78, 0.44, 1.0)

		# Crisp horizontal cyan/white trace line for lowered winch cable & hook depth
		if hook_active and abs(y - hook_y) <= 1:
			col = Color(0.88, 0.98, 1.0, 1.0) if not is_fish_hooked else Color(1.0, 0.42, 0.25, 1.0)

		_waterfall_image.set_pixel(right_x, y, col)

	_waterfall_texture.update(_waterfall_image)


func _update_hud_labels(reading: Dictionary) -> void:
	var seabed_depth: float = reading.get("seabed_depth", 42.0) as float
	var biomass: float = reading.get("biomass_density", 0.12) as float
	var tier: String = reading.get("activity_tier", "DEAD WATER") as String
	var near_rock: bool = reading.get("near_rock_hazard", false) as bool
	var near_arch: bool = reading.get("near_arch_monolith", false) as bool
	var near_poi_discovery: bool = reading.get("near_poi_discovery", false) as bool
	var nearby_poi_title: String = reading.get("nearby_poi_title", "") as String

	if near_poi_discovery and not nearby_poi_title.is_empty():
		if _active_poi_banner_title != nearby_poi_title:
			_active_poi_banner_title = nearby_poi_title
			show_catch_banner(nearby_poi_title, 3.8)
	else:
		_active_poi_banner_title = ""

	if _sonar_frame_overlay != null:
		_sonar_frame_overlay.queue_redraw()
	if _porthole_glass_overlay != null:
		_porthole_glass_overlay.queue_redraw()

	if depth_label != null:
		if hook_active:
			depth_label.text = "FATHOMS: %.1fm | LURE: %.1fm" % [seabed_depth, hook_depth_m]
		else:
			depth_label.text = "FATHOMS: %.1fm" % seabed_depth

	if activity_label != null:
		var pct: int = clampi(int(round(biomass * 100.0)), 0, 100)
		activity_label.text = "ECHO: %d%% [%s]" % [pct, tier]
		if biomass >= 0.70:
			activity_label.modulate = UI_CRIMSON_BRIGHT
		elif biomass >= 0.42:
			activity_label.modulate = UI_BRASS_HIGHLIGHT
		else:
			activity_label.modulate = UI_ELDRITCH_TEAL

	if zone_label != null:
		if near_poi_discovery and not nearby_poi_title.is_empty():
			zone_label.text = nearby_poi_title
			zone_label.modulate = UI_BRASS_HIGHLIGHT
		else:
			var ref_depth: float = hook_depth_m if hook_active else seabed_depth
			var zone_str: String = "I · SHALLOWS 0-35m"
			var zone_col: Color = UI_ELDRITCH_TEAL
			if ref_depth >= 75.0:
				zone_str = "III · ABYSSAL 75m+"
				zone_col = UI_CRIMSON_BRIGHT
			elif ref_depth >= 35.0:
				zone_str = "II · PELAGIC 35-75m"
				zone_col = UI_BRASS_HIGHLIGHT

			var habitat_str: String = "OPEN SWELLS"
			if seabed_depth >= 75.0:
				habitat_str = "ABYSSAL TRENCH"
			elif near_arch:
				habitat_str = "NAUTICAL WRECK"
			elif near_rock:
				habitat_str = "DROWNED REEF"

			var target_prefix: String = "LURE STRATUM" if hook_active else "SEABED STRATUM"
			zone_label.text = "%s: %s  |  %s" % [target_prefix, zone_str, habitat_str]
			zone_label.modulate = zone_col

	if prompt_label != null:
		var boat_speed: float = 0.0
		if boat != null and "current_speed" in boat:
			boat_speed = absf(boat.get("current_speed") as float)

		if not hook_active:
			if boat_speed < 2.5:
				prompt_label.text = "[F] UNLIMBER SEA ROD (1ST PERSON)   [TAB] DREDGE LEDGER"
				prompt_label.modulate = UI_BRASS_HIGHLIGHT
			else:
				prompt_label.text = "EASE THROTTLE BELOW 2.5 m/s TO CAST [F]"
				prompt_label.modulate = UI_MUTED_PARCHMENT
		elif is_fish_hooked:
			prompt_label.text = "[LMB] CRANK  [RMB] HEAVE  [SCROLL] DRAG  (STRAIN: %d%%)" % int(round(line_tension_pct))
			prompt_label.modulate = UI_CRIMSON_BRIGHT if line_tension_pct > 72.0 else UI_BRASS_HIGHLIGHT
		else:
			prompt_label.text = "[W/S] SINK DEPTH  [RMB] TWITCH  [LMB] RETRIEVE  [F] STOW"
			prompt_label.modulate = UI_BONE_PARCHMENT
