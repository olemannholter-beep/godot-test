class_name LightingDebugTuner
extends CanvasLayer

const SAVE_PATH: String = "user://tuned_lighting.json"

const UI_VOID_BLACK: Color = Color(0.022, 0.030, 0.042, 0.94)
const UI_SECTION_BG: Color = Color(0.055, 0.072, 0.092, 0.92)
const UI_CORRODED_IRON: Color = Color(0.078, 0.094, 0.114, 0.95)
const UI_TARNISHED_BRASS: Color = Color(0.549, 0.427, 0.231, 1.0)
const UI_BRASS_HIGHLIGHT: Color = Color(0.820, 0.655, 0.365, 1.0)
const UI_ELDRITCH_TEAL: Color = Color(0.240, 0.620, 0.530, 1.0)
const UI_BONE_PARCHMENT: Color = Color(0.865, 0.828, 0.745, 1.0)
const UI_MUTED_PARCHMENT: Color = Color(0.580, 0.545, 0.478, 1.0)

# =============================================================================
# SECTION 1 DEFAULTS — GLOBAL BRIGHTNESS, DARKNESS, MOON & FOG
# =============================================================================
const DEFAULT_MASTER_BRIGHTNESS: float = 1.0
const DEFAULT_MASTER_CONTRAST: float = 1.05
const DEFAULT_CAMERA_EXPOSURE: float = 1.05
const DEFAULT_AMBIENT_ENERGY: float = 0.20
const DEFAULT_SKY_BRIGHTNESS: float = 0.35
const DEFAULT_MOONLIGHT_ENERGY: float = 0.14
const DEFAULT_MOON_ELEVATION_DEG: float = -22.0
const DEFAULT_FOG_DENSITY: float = 0.0085
const DEFAULT_FOG_SELF_GLOW: float = 0.03

# =============================================================================
# SECTION 2 DEFAULTS — ALL BOAT LIGHTS
# =============================================================================
const DEFAULT_SEARCHLIGHT_ENERGY: float = 68.0
const DEFAULT_SEARCHLIGHT_RANGE: float = 185.0
const DEFAULT_SEARCHLIGHT_PITCH_DEG: float = -4.5
const DEFAULT_SEARCHLIGHT_ATTENUATION: float = 0.55
const DEFAULT_SEARCHLIGHT_CONE_ANGLE: float = 28.0
const DEFAULT_SEARCHLIGHT_EDGE_SOFTNESS: float = 1.85
const DEFAULT_SEARCHLIGHT_FOG_CONE: float = 0.40
const DEFAULT_WATER_PATH_ENERGY: float = 34.0
const DEFAULT_WATER_PATH_RANGE: float = 150.0
const DEFAULT_WATER_PATH_PITCH_DEG: float = -7.5
const DEFAULT_STERN_LANTERN_ENERGY: float = 3.2
const DEFAULT_STERN_LANTERN_RANGE: float = 9.5
const DEFAULT_WHEELHOUSE_GLOW_ENERGY: float = 1.6
const DEFAULT_BOAT_RIM_FILL_ENERGY: float = 0.55
const DEFAULT_BOAT_WATERLINE_OFFSET: float = 0.24
const DEFAULT_WAVE_ROCKING_INTENSITY: float = 1.0
const DEFAULT_FP_FISHING_FOV: float = 85.0
const DEFAULT_HELM_FOV: float = 65.0

# =============================================================================
# SECTION 3 DEFAULTS — LIGHTHOUSE TOWER & HARBOR LIGHTS
# =============================================================================
const DEFAULT_LIGHTHOUSE_BEAM_ENERGY: float = 110.0
const DEFAULT_LIGHTHOUSE_BEAM_RANGE: float = 350.0
const DEFAULT_LIGHTHOUSE_BEAM_ANGLE: float = 14.0
const DEFAULT_LIGHTHOUSE_BEAM_SOFTNESS: float = 0.80
const DEFAULT_LIGHTHOUSE_FOG_SHAFTS: float = 4.5
const DEFAULT_LIGHTHOUSE_CORE_GLOW: float = 4.0
const DEFAULT_LIGHTHOUSE_SPIN_SPEED: float = 0.45
const DEFAULT_HARBOR_PIER_ENERGY: float = 3.2
const DEFAULT_HARBOR_PIER_RANGE: float = 14.0
const DEFAULT_ENEMY_GLOW_INTENSITY: float = 1.0
const DEFAULT_SHIPWRECK_SCALE_MULTIPLIER: float = 1.0

@export var moonlight: DirectionalLight3D
@export var world_environment: WorldEnvironment
@export var storm_director: StormDirector
@export var boat: Node3D
@export var world_builder: WorldBuilder
@export var threat_director: RoamingThreatDirector

var _camera: OverheadCamera = null
var _bow_searchlight: SpotLight3D = null
var _water_surface_illuminator: SpotLight3D = null
var _cabin_lantern: OmniLight3D = null
var _wheelhouse_interior_light: OmniLight3D = null
var _boat_rim_fill_light: OmniLight3D = null

var _panel: PanelContainer = null
var _status_label: Label = null
var _peaceful_toggle_btn: Button = null
var _suppress_save: bool = false
var _sliders: Dictionary[String, HSlider] = {}
var _value_labels: Dictionary[String, Label] = {}
var _format_strings: Dictionary[String, String] = {}
var _defaults: Dictionary[String, float] = {}


func _ready() -> void:
	layer = 20
	_init_defaults_dictionary()
	_resolve_scene_nodes()
	_build_tuner_ui()
	call_deferred("_deferred_boot_apply")


func _deferred_boot_apply() -> void:
	# Wait one additional frame so WorldBuilder and BoatController finish spawning/configuring lights
	await get_tree().process_frame
	_resolve_scene_nodes()
	if threat_director != null and not threat_director.debug_ignore_player_changed.is_connected(_on_threat_ignore_player_changed):
		threat_director.debug_ignore_player_changed.connect(_on_threat_ignore_player_changed)
	_refresh_peaceful_button_display()
	_load_and_apply_saved_settings()


func _process(_delta: float) -> void:
	if _panel != null and _panel.visible and DisplayServer.get_name() != "headless":
		if Input.mouse_mode != Input.MOUSE_MODE_VISIBLE:
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _init_defaults_dictionary() -> void:
	_defaults = {
		# Section 1: Global Brightness, Darkness, Moon & Fog
		"master_brightness": DEFAULT_MASTER_BRIGHTNESS,
		"master_contrast": DEFAULT_MASTER_CONTRAST,
		"camera_exposure": DEFAULT_CAMERA_EXPOSURE,
		"ambient_night_floor": DEFAULT_AMBIENT_ENERGY,
		"sky_energy_multiplier": DEFAULT_SKY_BRIGHTNESS,
		"moonlight_strength": DEFAULT_MOONLIGHT_ENERGY,
		"moon_elevation_deg": DEFAULT_MOON_ELEVATION_DEG,
		"fog_density": DEFAULT_FOG_DENSITY,
		"fog_self_glow": DEFAULT_FOG_SELF_GLOW,
		# Section 2: All Boat Lights
		"searchlight_energy": DEFAULT_SEARCHLIGHT_ENERGY,
		"searchlight_range": DEFAULT_SEARCHLIGHT_RANGE,
		"searchlight_pitch_deg": DEFAULT_SEARCHLIGHT_PITCH_DEG,
		"searchlight_attenuation": DEFAULT_SEARCHLIGHT_ATTENUATION,
		"searchlight_cone_angle": DEFAULT_SEARCHLIGHT_CONE_ANGLE,
		"searchlight_edge_softness": DEFAULT_SEARCHLIGHT_EDGE_SOFTNESS,
		"searchlight_fog_cone": DEFAULT_SEARCHLIGHT_FOG_CONE,
		"water_path_energy": DEFAULT_WATER_PATH_ENERGY,
		"water_path_range": DEFAULT_WATER_PATH_RANGE,
		"water_path_pitch_deg": DEFAULT_WATER_PATH_PITCH_DEG,
		"stern_lantern_energy": DEFAULT_STERN_LANTERN_ENERGY,
		"stern_lantern_range": DEFAULT_STERN_LANTERN_RANGE,
		"wheelhouse_glow_energy": DEFAULT_WHEELHOUSE_GLOW_ENERGY,
		"boat_rim_fill_energy": DEFAULT_BOAT_RIM_FILL_ENERGY,
		"boat_waterline_offset": DEFAULT_BOAT_WATERLINE_OFFSET,
		"wave_rocking_intensity": DEFAULT_WAVE_ROCKING_INTENSITY,
		"fp_fishing_fov": DEFAULT_FP_FISHING_FOV,
		"helm_fov": DEFAULT_HELM_FOV,
		# Section 3: Lighthouse Tower & Harbor Lights
		"lighthouse_beam_energy": DEFAULT_LIGHTHOUSE_BEAM_ENERGY,
		"lighthouse_beam_range": DEFAULT_LIGHTHOUSE_BEAM_RANGE,
		"lighthouse_beam_angle": DEFAULT_LIGHTHOUSE_BEAM_ANGLE,
		"lighthouse_beam_softness": DEFAULT_LIGHTHOUSE_BEAM_SOFTNESS,
		"lighthouse_fog_shafts": DEFAULT_LIGHTHOUSE_FOG_SHAFTS,
		"lighthouse_core_glow": DEFAULT_LIGHTHOUSE_CORE_GLOW,
		"lighthouse_spin_speed": DEFAULT_LIGHTHOUSE_SPIN_SPEED,
		"harbor_pier_energy": DEFAULT_HARBOR_PIER_ENERGY,
		"harbor_pier_range": DEFAULT_HARBOR_PIER_RANGE,
		# Section 4: Roaming Threats & Enemy Glow
		"enemy_glow_intensity": DEFAULT_ENEMY_GLOW_INTENSITY,
		"shipwreck_scale_multiplier": DEFAULT_SHIPWRECK_SCALE_MULTIPLIER,
	}


func _resolve_scene_nodes() -> void:
	var parent_node: Node = get_parent()
	if parent_node != null:
		if moonlight == null:
			moonlight = parent_node.get_node_or_null("DirectionalLight3D") as DirectionalLight3D
		if world_environment == null:
			world_environment = parent_node.get_node_or_null("WorldEnvironment") as WorldEnvironment
		if storm_director == null:
			storm_director = parent_node.get_node_or_null("StormDirector") as StormDirector
		if boat == null:
			boat = parent_node.get_node_or_null("Boat") as Node3D
		if world_builder == null:
			world_builder = parent_node.get_node_or_null("WorldBuilder") as WorldBuilder
		if threat_director == null:
			threat_director = parent_node.get_node_or_null("RoamingThreatDirector") as RoamingThreatDirector
		if _camera == null:
			_camera = parent_node.get_node_or_null("Camera3D") as OverheadCamera

	if world_environment != null and world_environment.environment != null:
		world_environment.environment.adjustment_enabled = true

	if boat != null:
		if _bow_searchlight == null:
			_bow_searchlight = boat.get_node_or_null("Visuals/SearchlightGimbal/BowSearchlight") as SpotLight3D
			if _bow_searchlight == null:
				_bow_searchlight = boat.find_child("BowSearchlight", true, false) as SpotLight3D
		if _water_surface_illuminator == null:
			_water_surface_illuminator = boat.get_node_or_null("Visuals/SearchlightGimbal/WaterSurfaceIlluminator") as SpotLight3D
			if _water_surface_illuminator == null:
				_water_surface_illuminator = boat.find_child("WaterSurfaceIlluminator", true, false) as SpotLight3D
		if _cabin_lantern == null:
			_cabin_lantern = boat.get_node_or_null("Visuals/CabinLantern") as OmniLight3D
			if _cabin_lantern == null:
				_cabin_lantern = boat.find_child("CabinLantern", true, false) as OmniLight3D
		if _wheelhouse_interior_light == null:
			_wheelhouse_interior_light = boat.get_node_or_null("Visuals/WheelhouseInteriorLight") as OmniLight3D
			if _wheelhouse_interior_light == null:
				_wheelhouse_interior_light = boat.find_child("WheelhouseInteriorLight", true, false) as OmniLight3D
		if _boat_rim_fill_light == null:
			_boat_rim_fill_light = boat.get_node_or_null("Visuals/BoatRimFillLight") as OmniLight3D
			if _boat_rim_fill_light == null:
				_boat_rim_fill_light = boat.find_child("BoatRimFillLight", true, false) as OmniLight3D


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey:
		var key_event: InputEventKey = event as InputEventKey
		if key_event.pressed and not key_event.echo:
			var code: Key = key_event.physical_keycode if key_event.physical_keycode != KEY_NONE else key_event.keycode
			if code == KEY_F10 or (code == KEY_F9 and key_event.shift_pressed):
				if _panel != null:
					_panel.visible = not _panel.visible
					if _camera != null:
						_camera.ui_modal_open = _panel.visible
					if _panel.visible:
						if DisplayServer.get_name() != "headless":
							Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
						_sync_sliders_from_scene()


func _build_tuner_ui() -> void:
	_panel = PanelContainer.new()
	_panel.name = "LightingTunerPanel"
	_panel.visible = false
	_panel.anchors_preset = Control.PRESET_TOP_LEFT
	_panel.offset_left = 20.0
	_panel.offset_top = 20.0
	_panel.offset_right = 480.0
	_panel.offset_bottom = 700.0
	_panel.custom_minimum_size = Vector2(460.0, 680.0)

	var panel_sb: StyleBoxFlat = StyleBoxFlat.new()
	panel_sb.bg_color = UI_VOID_BLACK
	panel_sb.border_width_left = 2
	panel_sb.border_width_top = 2
	panel_sb.border_width_right = 2
	panel_sb.border_width_bottom = 2
	panel_sb.border_color = UI_TARNISHED_BRASS
	panel_sb.corner_radius_top_left = 4
	panel_sb.corner_radius_top_right = 4
	panel_sb.corner_radius_bottom_left = 4
	panel_sb.corner_radius_bottom_right = 4
	panel_sb.content_margin_left = 14.0
	panel_sb.content_margin_right = 14.0
	panel_sb.content_margin_top = 12.0
	panel_sb.content_margin_bottom = 12.0
	_panel.add_theme_stylebox_override("panel", panel_sb)
	add_child(_panel)

	var outer_vbox: VBoxContainer = VBoxContainer.new()
	outer_vbox.add_theme_constant_override("separation", 8)
	_panel.add_child(outer_vbox)

	# Title Header
	var header_lbl: Label = Label.new()
	header_lbl.text = "⚙ [F9] LIVE LIGHTING & ATMOSPHERE EDITOR"
	header_lbl.add_theme_color_override("font_color", UI_BRASS_HIGHLIGHT)
	header_lbl.add_theme_font_size_override("font_size", 15)
	outer_vbox.add_child(header_lbl)

	# Top Action Bar: Save All to Disk & Reset to Defaults
	var btn_hbox: HBoxContainer = HBoxContainer.new()
	btn_hbox.add_theme_constant_override("separation", 8)
	outer_vbox.add_child(btn_hbox)

	var save_btn: Button = Button.new()
	save_btn.text = "Save All to Disk"
	save_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	save_btn.pressed.connect(_on_save_all_button_pressed)
	btn_hbox.add_child(save_btn)

	var reset_btn: Button = Button.new()
	reset_btn.text = "Reset to Defaults"
	reset_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	reset_btn.pressed.connect(_on_reset_defaults_pressed)
	btn_hbox.add_child(reset_btn)

	_status_label = Label.new()
	_status_label.text = "Auto-saves to user://tuned_lighting.json (F9 to toggle)"
	_status_label.add_theme_color_override("font_color", UI_MUTED_PARCHMENT)
	_status_label.add_theme_font_size_override("font_size", 11)
	outer_vbox.add_child(_status_label)

	# Scrollable Slider Container
	var scroll: ScrollContainer = ScrollContainer.new()
	scroll.name = "LightingScrollContainer"
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.custom_minimum_size = Vector2(430.0, 560.0)
	outer_vbox.add_child(scroll)

	var list_vbox: VBoxContainer = VBoxContainer.new()
	list_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list_vbox.add_theme_constant_override("separation", 7)
	scroll.add_child(list_vbox)

	# =========================================================================
	# SECTION 1 — GLOBAL BRIGHTNESS, DARKNESS, MOON & FOG
	# =========================================================================
	_add_section_header(list_vbox, "1. GLOBAL BRIGHTNESS, DARKNESS, MOON & FOG")
	_register_slider(list_vbox, "master_brightness", "Master Brightness", 0.2, 2.2, 0.01, "%.2f")
	_register_slider(list_vbox, "master_contrast", "Master Contrast / Darkness Crush", 0.5, 2.0, 0.01, "%.2f")
	_register_slider(list_vbox, "camera_exposure", "Camera Exposure", 0.2, 2.5, 0.01, "%.2f")
	_register_slider(list_vbox, "ambient_night_floor", "Shadow Floor / Ambient Darkness", 0.0, 2.0, 0.01, "%.2f")
	_register_slider(list_vbox, "sky_energy_multiplier", "Skybox Brightness (sky_energy_multiplier)", 0.0, 1.5, 0.01, "%.2f")
	_register_slider(list_vbox, "moonlight_strength", "Moonlight Strength", 0.0, 2.5, 0.01, "%.2f")
	_register_slider(list_vbox, "moon_elevation_deg", "Moon Elevation Pitch", -65.0, -5.0, 0.5, "%.1f°")
	_register_slider(list_vbox, "fog_density", "Fog Density", 0.0, 0.05, 0.0005, "%.4f")
	_register_slider(list_vbox, "fog_self_glow", "Fog Self-Glow", 0.0, 1.0, 0.01, "%.2f")

	# =========================================================================
	# SECTION 2 — CAMERA FOV & ALL BOAT LIGHTS
	# =========================================================================
	_add_section_header(list_vbox, "2. CAMERA FOV & BOAT LIGHTS (TRAWLER)")
	_register_slider(list_vbox, "fp_fishing_fov", "First-Person Fishing FOV", 50.0, 115.0, 0.5, "%.1f°")
	_register_slider(list_vbox, "helm_fov", "Third-Person Helm FOV", 40.0, 100.0, 0.5, "%.1f°")
	_register_slider(list_vbox, "boat_waterline_offset", "Boat Waterline Height Offset", -1.5, 1.5, 0.02, "%+.2fm")
	_register_slider(list_vbox, "wave_rocking_intensity", "Wave Roll / Pitch Intensity", 0.2, 2.5, 0.05, "%.2fx")
	_register_slider(list_vbox, "searchlight_energy", "Searchlight Energy", 0.0, 160.0, 0.5, "%.1f")
	_register_slider(list_vbox, "searchlight_range", "Searchlight Range (m)", 20.0, 300.0, 1.0, "%.0fm")
	_register_slider(list_vbox, "searchlight_pitch_deg", "Searchlight Pitch", -25.0, 5.0, 0.5, "%.1f°")
	_register_slider(list_vbox, "searchlight_attenuation", "Searchlight Distance Falloff", 0.15, 2.5, 0.01, "%.2f")
	_register_slider(list_vbox, "searchlight_cone_angle", "Searchlight Cone Width", 10.0, 65.0, 0.5, "%.1f°")
	_register_slider(list_vbox, "searchlight_edge_softness", "Searchlight Edge Softness", 0.3, 4.5, 0.05, "%.2f")
	_register_slider(list_vbox, "searchlight_fog_cone", "Searchlight Fog Cone", 0.0, 4.0, 0.05, "%.2f")
	_register_slider(list_vbox, "water_path_energy", "Water Path Light Energy", 0.0, 100.0, 0.5, "%.1f")
	_register_slider(list_vbox, "water_path_range", "Water Path Range (m)", 20.0, 250.0, 1.0, "%.0fm")
	_register_slider(list_vbox, "water_path_pitch_deg", "Water Path Pitch", -30.0, 0.0, 0.5, "%.1f°")
	_register_slider(list_vbox, "stern_lantern_energy", "Stern Deck Lantern Energy", 0.0, 15.0, 0.1, "%.2f")
	_register_slider(list_vbox, "stern_lantern_range", "Stern Deck Lantern Range (m)", 2.0, 30.0, 0.5, "%.1fm")
	_register_slider(list_vbox, "wheelhouse_glow_energy", "Wheelhouse Window Glow Energy", 0.0, 10.0, 0.1, "%.2f")
	_register_slider(list_vbox, "boat_rim_fill_energy", "Boat Silhouette Fill Light Energy", 0.0, 4.0, 0.05, "%.2f")

	# =========================================================================
	# SECTION 3 — LIGHTHOUSE TOWER & HARBOR LIGHTS
	# =========================================================================
	_add_section_header(list_vbox, "3. LIGHTHOUSE TOWER & HARBOR LIGHTS")
	_register_slider(list_vbox, "lighthouse_beam_energy", "Lighthouse Beam Energy", 0.0, 120.0, 0.5, "%.1f")
	_register_slider(list_vbox, "lighthouse_beam_range", "Lighthouse Beam Range (m)", 30.0, 400.0, 1.0, "%.0fm")
	_register_slider(list_vbox, "lighthouse_beam_angle", "Lighthouse Beam Cone Angle", 5.0, 45.0, 0.5, "%.1f°")
	_register_slider(list_vbox, "lighthouse_beam_softness", "Lighthouse Beam Edge Softness", 0.3, 4.0, 0.05, "%.2f")
	_register_slider(list_vbox, "lighthouse_fog_shafts", "Lighthouse Volumetric Fog Shafts", 0.0, 10.0, 0.1, "%.2f")
	_register_slider(list_vbox, "lighthouse_core_glow", "Lighthouse Lantern Room Core Glow", 0.0, 25.0, 0.25, "%.2f")
	_register_slider(list_vbox, "lighthouse_spin_speed", "Lighthouse Spin Speed (rad/s)", 0.0, 3.0, 0.05, "%.2f rad/s")
	_register_slider(list_vbox, "harbor_pier_energy", "Harbor Pier Lanterns Energy", 0.0, 15.0, 0.1, "%.2f")
	_register_slider(list_vbox, "harbor_pier_range", "Harbor Pier Lanterns Range (m)", 3.0, 35.0, 0.5, "%.1fm")

	# =========================================================================
	# SECTION 4 — ROAMING MARITIME THREATS & LIVE SPAWN CONTROLS
	# =========================================================================
	_add_section_header(list_vbox, "4. ROAMING THREATS & ENEMY AI TUNING")
	_peaceful_toggle_btn = Button.new()
	_peaceful_toggle_btn.name = "PeacefulModeToggleBtn"
	_peaceful_toggle_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_peaceful_toggle_btn.pressed.connect(_on_toggle_peaceful_mode_pressed)
	list_vbox.add_child(_peaceful_toggle_btn)
	_refresh_peaceful_button_display()

	_register_slider(list_vbox, "enemy_glow_intensity", "Enemy Glow Intensity", 0.1, 4.0, 0.05, "%.2fx")
	_register_slider(list_vbox, "shipwreck_scale_multiplier", "Shipwreck Scale Multiplier", 0.5, 2.5, 0.05, "%.2fx")

	var spawn_shipwreck_btn: Button = Button.new()
	spawn_shipwreck_btn.name = "SpawnCustomShipwreckBtn"
	spawn_shipwreck_btn.text = "Spawn / Preview Custom Shipwreck Ahead (40m)"
	spawn_shipwreck_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spawn_shipwreck_btn.pressed.connect(_on_spawn_custom_shipwreck_pressed)
	list_vbox.add_child(spawn_shipwreck_btn)

	var spawn_trawler_btn: Button = Button.new()
	spawn_trawler_btn.name = "SpawnGhostTrawlerBtn"
	spawn_trawler_btn.text = "Spawn Ghost Trawler Ahead (40m)"
	spawn_trawler_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spawn_trawler_btn.pressed.connect(_on_spawn_ghost_trawler_pressed)
	list_vbox.add_child(spawn_trawler_btn)

	var spawn_leviathan_btn: Button = Button.new()
	spawn_leviathan_btn.name = "SpawnLeviathanBtn"
	spawn_leviathan_btn.text = "Spawn Leviathan Ahead (35m)"
	spawn_leviathan_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spawn_leviathan_btn.pressed.connect(_on_spawn_leviathan_pressed)
	list_vbox.add_child(spawn_leviathan_btn)


func _add_section_header(parent_vbox: VBoxContainer, section_title: String) -> void:
	var header_panel: PanelContainer = PanelContainer.new()
	var sb: StyleBoxFlat = StyleBoxFlat.new()
	sb.bg_color = UI_SECTION_BG
	sb.border_width_left = 3
	sb.border_color = UI_TARNISHED_BRASS
	sb.content_margin_left = 8.0
	sb.content_margin_right = 8.0
	sb.content_margin_top = 4.0
	sb.content_margin_bottom = 4.0
	header_panel.add_theme_stylebox_override("panel", sb)
	parent_vbox.add_child(header_panel)

	var lbl: Label = Label.new()
	lbl.text = section_title
	lbl.add_theme_color_override("font_color", UI_BRASS_HIGHLIGHT)
	lbl.add_theme_font_size_override("font_size", 13)
	header_panel.add_child(lbl)


func _register_slider(
	parent_vbox: VBoxContainer,
	key: String,
	title: String,
	min_val: float,
	max_val: float,
	step_val: float,
	fmt: String
) -> void:
	var default_val: float = float(_defaults.get(key, min_val))
	_format_strings[key] = fmt

	var row_vbox: VBoxContainer = VBoxContainer.new()
	row_vbox.add_theme_constant_override("separation", 2)
	parent_vbox.add_child(row_vbox)

	var top_hbox: HBoxContainer = HBoxContainer.new()
	row_vbox.add_child(top_hbox)

	var title_lbl: Label = Label.new()
	title_lbl.text = title
	title_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_lbl.add_theme_color_override("font_color", UI_BONE_PARCHMENT)
	title_lbl.add_theme_font_size_override("font_size", 12)
	top_hbox.add_child(title_lbl)

	var val_lbl: Label = Label.new()
	val_lbl.text = fmt % default_val
	val_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	val_lbl.add_theme_color_override("font_color", UI_ELDRITCH_TEAL)
	val_lbl.add_theme_font_size_override("font_size", 12)
	top_hbox.add_child(val_lbl)

	var slider: HSlider = HSlider.new()
	slider.min_value = min_val
	slider.max_value = max_val
	slider.step = step_val
	slider.value = default_val
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.value_changed.connect(func(v: float) -> void: _on_slider_value_changed(key, v))
	row_vbox.add_child(slider)

	_sliders[key] = slider
	_value_labels[key] = val_lbl


func _on_slider_value_changed(key: String, raw_val: float) -> void:
	_resolve_scene_nodes()
	var slider: HSlider = _sliders.get(key, null) as HSlider
	var val: float = raw_val
	if slider != null:
		val = clampf(raw_val, slider.min_value, slider.max_value)

	var val_lbl: Label = _value_labels.get(key, null) as Label
	var fmt: String = String(_format_strings.get(key, "%.2f"))
	if val_lbl != null:
		val_lbl.text = fmt % val

	_apply_parameter(key, val)

	if not _suppress_save:
		_save_settings_to_disk(false)


func _apply_parameter(key: String, val: float) -> void:
	var env: Environment = world_environment.environment if world_environment != null else null
	var boat_ctrl: BoatController = boat as BoatController

	match key:
		# =====================================================================
		# SECTION 1 — GLOBAL BRIGHTNESS, DARKNESS, MOON & FOG
		# =====================================================================
		"master_brightness":
			if env != null:
				env.adjustment_enabled = true
				env.adjustment_brightness = clampf(val, 0.2, 2.2)
		"master_contrast":
			if env != null:
				env.adjustment_enabled = true
				env.adjustment_contrast = clampf(val, 0.5, 2.0)
		"camera_exposure":
			if env != null:
				env.tonemap_exposure = clampf(val, 0.2, 2.5)
		"ambient_night_floor":
			if env != null:
				env.ambient_light_energy = clampf(val, 0.0, 2.0)
		"sky_energy_multiplier":
			if env != null and env.sky != null and env.sky.sky_material is ProceduralSkyMaterial:
				var sky_mat: ProceduralSkyMaterial = env.sky.sky_material as ProceduralSkyMaterial
				sky_mat.sky_energy_multiplier = clampf(val, 0.0, 1.5)
		"moonlight_strength":
			var clamped_moon: float = clampf(val, 0.0, 2.5)
			if moonlight != null:
				moonlight.light_energy = clamped_moon
			if storm_director != null:
				storm_director.set_base_moon_energy(clamped_moon)
		"moon_elevation_deg":
			var clamped_elev: float = clampf(val, -65.0, -5.0)
			if moonlight != null:
				var rot_deg: Vector3 = moonlight.rotation_degrees
				rot_deg.x = clamped_elev
				moonlight.rotation_degrees = rot_deg
		"fog_density":
			var clamped_fog: float = clampf(val, 0.0, 0.05)
			if env != null:
				env.volumetric_fog_density = clamped_fog
			if storm_director != null:
				storm_director.set_base_fog_density(clamped_fog)
		"fog_self_glow":
			var clamped_glow: float = clampf(val, 0.0, 1.0)
			if env != null:
				env.volumetric_fog_emission_energy = clamped_glow
			if storm_director != null:
				storm_director.set_base_fog_emission_energy(clamped_glow)

		# =====================================================================
		# SECTION 2 — ALL BOAT LIGHTS
		# =====================================================================
		"searchlight_energy":
			var clamped_se: float = clampf(val, 0.0, 160.0)
			if boat_ctrl != null:
				boat_ctrl.base_searchlight_energy = clamped_se
			if _bow_searchlight != null:
				_bow_searchlight.light_energy = clamped_se
		"searchlight_range":
			if _bow_searchlight != null:
				_bow_searchlight.spot_range = clampf(val, 20.0, 300.0)
		"searchlight_pitch_deg":
			if _bow_searchlight != null:
				var s_rot: Vector3 = _bow_searchlight.rotation_degrees
				s_rot.x = clampf(val, -25.0, 5.0)
				_bow_searchlight.rotation_degrees = s_rot
		"searchlight_attenuation":
			if _bow_searchlight != null:
				_bow_searchlight.spot_attenuation = clampf(val, 0.15, 2.5)
		"searchlight_cone_angle":
			if _bow_searchlight != null:
				_bow_searchlight.spot_angle = clampf(val, 10.0, 65.0)
		"searchlight_edge_softness":
			if _bow_searchlight != null:
				_bow_searchlight.spot_angle_attenuation = clampf(val, 0.3, 4.5)
		"searchlight_fog_cone":
			if _bow_searchlight != null:
				_bow_searchlight.light_volumetric_fog_energy = clampf(val, 0.0, 4.0)
		"water_path_energy":
			var clamped_wpe: float = clampf(val, 0.0, 100.0)
			if boat_ctrl != null:
				boat_ctrl.base_water_path_energy = clamped_wpe
			if _water_surface_illuminator != null:
				_water_surface_illuminator.light_energy = clamped_wpe
		"water_path_range":
			if _water_surface_illuminator != null:
				_water_surface_illuminator.spot_range = clampf(val, 20.0, 250.0)
		"water_path_pitch_deg":
			if _water_surface_illuminator != null:
				var w_rot: Vector3 = _water_surface_illuminator.rotation_degrees
				w_rot.x = clampf(val, -30.0, 0.0)
				_water_surface_illuminator.rotation_degrees = w_rot
		"stern_lantern_energy":
			var clamped_sle: float = clampf(val, 0.0, 15.0)
			if boat_ctrl != null:
				boat_ctrl.base_cabin_lantern_energy = clamped_sle
				boat_ctrl._base_cabin_lantern_energy = clamped_sle
			if _cabin_lantern != null:
				_cabin_lantern.light_energy = clamped_sle
		"stern_lantern_range":
			if _cabin_lantern != null:
				_cabin_lantern.omni_range = clampf(val, 2.0, 30.0)
		"wheelhouse_glow_energy":
			if _wheelhouse_interior_light != null:
				_wheelhouse_interior_light.light_energy = clampf(val, 0.0, 10.0)
		"boat_rim_fill_energy":
			if _boat_rim_fill_light != null:
				_boat_rim_fill_light.light_energy = clampf(val, 0.0, 4.0)
		"boat_waterline_offset":
			if boat_ctrl != null:
				boat_ctrl.base_waterline_offset = clampf(val, -1.5, 1.5)
		"wave_rocking_intensity":
			if boat_ctrl != null:
				boat_ctrl.wave_rocking_intensity = clampf(val, 0.2, 2.5)
		"fp_fishing_fov":
			var clamped_fp_fov: float = clampf(val, 50.0, 115.0)
			if boat_ctrl != null:
				boat_ctrl.fp_fishing_fov = clamped_fp_fov
			if _camera != null:
				_camera.set_fp_fishing_fov(clamped_fp_fov)
		"helm_fov":
			var clamped_helm_fov: float = clampf(val, 40.0, 100.0)
			if boat_ctrl != null:
				boat_ctrl.helm_fov = clamped_helm_fov
			if _camera != null:
				_camera.set_helm_fov(clamped_helm_fov)

		# =====================================================================
		# SECTION 3 — LIGHTHOUSE TOWER & HARBOR LIGHTS
		# =====================================================================
		"lighthouse_beam_energy":
			var clamped_lbe: float = clampf(val, 0.0, 120.0)
			for node: Node in get_tree().get_nodes_in_group("lighthouse_beams"):
				if node is SpotLight3D:
					(node as SpotLight3D).light_energy = clamped_lbe
		"lighthouse_beam_range":
			var clamped_lbr: float = clampf(val, 30.0, 400.0)
			for node: Node in get_tree().get_nodes_in_group("lighthouse_beams"):
				if node is SpotLight3D:
					(node as SpotLight3D).spot_range = clamped_lbr
		"lighthouse_beam_angle":
			var clamped_lba: float = clampf(val, 5.0, 45.0)
			for node: Node in get_tree().get_nodes_in_group("lighthouse_beams"):
				if node is SpotLight3D:
					(node as SpotLight3D).spot_angle = clamped_lba
		"lighthouse_beam_softness":
			var clamped_lbs: float = clampf(val, 0.3, 4.0)
			for node: Node in get_tree().get_nodes_in_group("lighthouse_beams"):
				if node is SpotLight3D:
					(node as SpotLight3D).spot_angle_attenuation = clamped_lbs
		"lighthouse_fog_shafts":
			var clamped_lfs: float = clampf(val, 0.0, 10.0)
			for node: Node in get_tree().get_nodes_in_group("lighthouse_beams"):
				if node is SpotLight3D:
					(node as SpotLight3D).light_volumetric_fog_energy = clamped_lfs
		"lighthouse_core_glow":
			var clamped_lcg: float = clampf(val, 0.0, 25.0)
			for node: Node in get_tree().get_nodes_in_group("lighthouse_beacon_lamp"):
				if node is OmniLight3D:
					(node as OmniLight3D).light_energy = clamped_lcg
		"lighthouse_spin_speed":
			var clamped_lss: float = clampf(val, 0.0, 3.0)
			if world_builder != null:
				world_builder.lighthouse_rotation_speed = clamped_lss
		"harbor_pier_energy":
			var clamped_hpe: float = clampf(val, 0.0, 15.0)
			for node: Node in get_tree().get_nodes_in_group("harbor_pier_lanterns"):
				if node is OmniLight3D:
					(node as OmniLight3D).light_energy = clamped_hpe
		"harbor_pier_range":
			var clamped_hpr: float = clampf(val, 3.0, 35.0)
			for node: Node in get_tree().get_nodes_in_group("harbor_pier_lanterns"):
				if node is OmniLight3D:
					(node as OmniLight3D).omni_range = clamped_hpr
		"enemy_glow_intensity":
			var clamped_egi: float = clampf(val, 0.1, 4.0)
			if threat_director != null:
				threat_director.set_enemy_glow_intensity(clamped_egi)
		"shipwreck_scale_multiplier":
			var clamped_ssm: float = clampf(val, 0.5, 2.5)
			if world_builder != null:
				world_builder.set_shipwreck_scale_multiplier(clamped_ssm)


func _on_spawn_custom_shipwreck_pressed() -> void:
	_resolve_scene_nodes()
	if world_builder != null and boat != null:
		world_builder.spawn_custom_shipwreck_ahead(boat, 40.0)
		if _status_label != null:
			_status_label.text = "Spawned / Previewed Custom Shipwreck 40m ahead of bow!"


func _on_toggle_peaceful_mode_pressed() -> void:
	_resolve_scene_nodes()
	var boat_ctrl: BoatController = boat as BoatController
	if boat_ctrl != null:
		boat_ctrl.toggle_peaceful_mode()
	elif threat_director != null:
		threat_director.toggle_debug_ignore_player()
	_refresh_peaceful_button_display()
	if _status_label != null:
		var is_peaceful: bool = threat_director.is_debug_ignore_player() if threat_director != null else RoamingThreatDirector.shared_ignore_player
		_status_label.text = "Peaceful Mode ENABLED (Enemies ignore player)" if is_peaceful else "Enemy Aggro ENABLED (Normal pursuit & detection)"


func _on_threat_ignore_player_changed(_enabled: bool) -> void:
	_refresh_peaceful_button_display()


func _refresh_peaceful_button_display() -> void:
	if _peaceful_toggle_btn == null:
		return
	var is_peaceful: bool = RoamingThreatDirector.shared_ignore_player
	if threat_director != null:
		is_peaceful = threat_director.is_debug_ignore_player()
	if is_peaceful:
		_peaceful_toggle_btn.text = "🕊 [P] Enemy Aggro: OFF (Peaceful Explore)"
		_peaceful_toggle_btn.add_theme_color_override("font_color", Color(0.28, 0.92, 0.56, 1.0))
	else:
		_peaceful_toggle_btn.text = "⚔ [P] Enemy Aggro: ON (Click to Toggle Peaceful)"
		_peaceful_toggle_btn.add_theme_color_override("font_color", Color(0.92, 0.44, 0.40, 1.0))


func _on_spawn_ghost_trawler_pressed() -> void:
	_resolve_scene_nodes()
	if threat_director != null:
		threat_director.spawn_ghost_trawler_ahead(40.0)
		if _status_label != null:
			_status_label.text = "Spawned Ghost Trawler 40m ahead of bow!"


func _on_spawn_leviathan_pressed() -> void:
	_resolve_scene_nodes()
	if threat_director != null:
		threat_director.spawn_leviathan_ahead(35.0)
		if _status_label != null:
			_status_label.text = "Spawned Abyssal Leviathan 35m ahead of bow!"


func _on_save_all_button_pressed() -> void:
	_save_settings_to_disk(true)


func _on_reset_defaults_pressed() -> void:
	_suppress_save = true
	for key: String in _defaults.keys():
		var def_val: float = _defaults[key]
		var slider: HSlider = _sliders.get(key, null) as HSlider
		if slider != null:
			slider.value = def_val
		var val_lbl: Label = _value_labels.get(key, null) as Label
		var fmt: String = String(_format_strings.get(key, "%.2f"))
		if val_lbl != null:
			val_lbl.text = fmt % def_val
		_apply_parameter(key, def_val)
	_suppress_save = false
	_save_settings_to_disk(true)
	if _status_label != null:
		_status_label.text = "Reset all sliders to defaults & saved to user://tuned_lighting.json"


func _set_slider_display_quiet(key: String, val: float) -> void:
	var slider: HSlider = _sliders.get(key, null) as HSlider
	if slider != null:
		slider.value = val
	var val_lbl: Label = _value_labels.get(key, null) as Label
	var fmt: String = String(_format_strings.get(key, "%.2f"))
	if val_lbl != null:
		val_lbl.text = fmt % val


func _sync_sliders_from_scene() -> void:
	_resolve_scene_nodes()
	_suppress_save = true

	var env: Environment = world_environment.environment if world_environment != null else null
	var boat_ctrl: BoatController = boat as BoatController

	if env != null:
		_set_slider_display_quiet("master_brightness", env.adjustment_brightness)
		_set_slider_display_quiet("master_contrast", env.adjustment_contrast)
		_set_slider_display_quiet("camera_exposure", env.tonemap_exposure)
		_set_slider_display_quiet("ambient_night_floor", env.ambient_light_energy)
		_set_slider_display_quiet("fog_density", env.volumetric_fog_density)
		_set_slider_display_quiet("fog_self_glow", env.volumetric_fog_emission_energy)
		if env.sky != null and env.sky.sky_material is ProceduralSkyMaterial:
			var sky_mat: ProceduralSkyMaterial = env.sky.sky_material as ProceduralSkyMaterial
			_set_slider_display_quiet("sky_energy_multiplier", sky_mat.sky_energy_multiplier)

	if moonlight != null:
		_set_slider_display_quiet("moonlight_strength", moonlight.light_energy)
		_set_slider_display_quiet("moon_elevation_deg", moonlight.rotation_degrees.x)

	if _bow_searchlight != null:
		var se: float = boat_ctrl.base_searchlight_energy if boat_ctrl != null else _bow_searchlight.light_energy
		_set_slider_display_quiet("searchlight_energy", se)
		_set_slider_display_quiet("searchlight_range", _bow_searchlight.spot_range)
		_set_slider_display_quiet("searchlight_pitch_deg", _bow_searchlight.rotation_degrees.x)
		_set_slider_display_quiet("searchlight_attenuation", _bow_searchlight.spot_attenuation)
		_set_slider_display_quiet("searchlight_cone_angle", _bow_searchlight.spot_angle)
		_set_slider_display_quiet("searchlight_edge_softness", _bow_searchlight.spot_angle_attenuation)
		_set_slider_display_quiet("searchlight_fog_cone", _bow_searchlight.light_volumetric_fog_energy)

	if _water_surface_illuminator != null:
		var wpe: float = boat_ctrl.base_water_path_energy if boat_ctrl != null else _water_surface_illuminator.light_energy
		_set_slider_display_quiet("water_path_energy", wpe)
		_set_slider_display_quiet("water_path_range", _water_surface_illuminator.spot_range)
		_set_slider_display_quiet("water_path_pitch_deg", _water_surface_illuminator.rotation_degrees.x)

	if _cabin_lantern != null:
		var sle: float = boat_ctrl.base_cabin_lantern_energy if boat_ctrl != null else _cabin_lantern.light_energy
		_set_slider_display_quiet("stern_lantern_energy", sle)
		_set_slider_display_quiet("stern_lantern_range", _cabin_lantern.omni_range)

	if _wheelhouse_interior_light != null:
		_set_slider_display_quiet("wheelhouse_glow_energy", _wheelhouse_interior_light.light_energy)

	if _boat_rim_fill_light != null:
		_set_slider_display_quiet("boat_rim_fill_energy", _boat_rim_fill_light.light_energy)

	if boat_ctrl != null:
		_set_slider_display_quiet("boat_waterline_offset", boat_ctrl.base_waterline_offset)
		_set_slider_display_quiet("wave_rocking_intensity", boat_ctrl.wave_rocking_intensity)

	if _camera != null:
		_set_slider_display_quiet("fp_fishing_fov", _camera.fp_fishing_fov)
		_set_slider_display_quiet("helm_fov", _camera.helm_fov)

	var beams: Array[Node] = get_tree().get_nodes_in_group("lighthouse_beams")
	if not beams.is_empty() and beams[0] is SpotLight3D:
		var beam0: SpotLight3D = beams[0] as SpotLight3D
		_set_slider_display_quiet("lighthouse_beam_energy", beam0.light_energy)
		_set_slider_display_quiet("lighthouse_beam_range", beam0.spot_range)
		_set_slider_display_quiet("lighthouse_beam_angle", beam0.spot_angle)
		_set_slider_display_quiet("lighthouse_beam_softness", beam0.spot_angle_attenuation)
		_set_slider_display_quiet("lighthouse_fog_shafts", beam0.light_volumetric_fog_energy)

	var core_lamps: Array[Node] = get_tree().get_nodes_in_group("lighthouse_beacon_lamp")
	if not core_lamps.is_empty() and core_lamps[0] is OmniLight3D:
		var lamp0: OmniLight3D = core_lamps[0] as OmniLight3D
		_set_slider_display_quiet("lighthouse_core_glow", lamp0.light_energy)

	if world_builder != null:
		_set_slider_display_quiet("lighthouse_spin_speed", world_builder.lighthouse_rotation_speed)
		_set_slider_display_quiet("shipwreck_scale_multiplier", world_builder.get_shipwreck_scale_multiplier())

	var pier_lamps: Array[Node] = get_tree().get_nodes_in_group("harbor_pier_lanterns")
	if not pier_lamps.is_empty() and pier_lamps[0] is OmniLight3D:
		var pier0: OmniLight3D = pier_lamps[0] as OmniLight3D
		_set_slider_display_quiet("harbor_pier_energy", pier0.light_energy)
		_set_slider_display_quiet("harbor_pier_range", pier0.omni_range)

	if threat_director != null:
		_set_slider_display_quiet("enemy_glow_intensity", threat_director.get_enemy_glow_intensity())

	_suppress_save = false


func _load_and_apply_saved_settings() -> void:
	_resolve_scene_nodes()
	var loaded_values: Dictionary[String, float] = {}
	for key: String in _defaults.keys():
		loaded_values[key] = _defaults[key]

	if FileAccess.file_exists(SAVE_PATH):
		var file: FileAccess = FileAccess.open(SAVE_PATH, FileAccess.READ)
		if file != null:
			var raw_text: String = file.get_as_text()
			file.close()
			var parsed: Variant = JSON.parse_string(raw_text)
			if parsed is Dictionary:
				var data: Dictionary = parsed as Dictionary
				for key: String in _defaults.keys():
					if data.has(key):
						var slider: HSlider = _sliders.get(key, null) as HSlider
						var v: float = float(data.get(key, _defaults[key]))
						if slider != null:
							v = clampf(v, slider.min_value, slider.max_value)
						loaded_values[key] = v
				if not data.has("sky_energy_multiplier") and data.has("skybox_brightness"):
					loaded_values["sky_energy_multiplier"] = clampf(
						float(data.get("skybox_brightness", DEFAULT_SKY_BRIGHTNESS)),
						0.0,
						1.5
					)
				if float(loaded_values.get("boat_waterline_offset", DEFAULT_BOAT_WATERLINE_OFFSET)) < 0.08:
					loaded_values["boat_waterline_offset"] = DEFAULT_BOAT_WATERLINE_OFFSET

	_suppress_save = true
	for key: String in loaded_values.keys():
		var val: float = loaded_values[key]
		_set_slider_display_quiet(key, val)
		_apply_parameter(key, val)
	_suppress_save = false


func _save_settings_to_disk(copy_to_clipboard: bool = false) -> void:
	var payload: Dictionary = {}
	for key: String in _defaults.keys():
		var slider: HSlider = _sliders.get(key, null) as HSlider
		payload[key] = slider.value if slider != null else _defaults[key]

	var json_str: String = JSON.stringify(payload, "\t")
	var file: FileAccess = FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if file != null:
		file.store_string(json_str)
		file.close()

	if copy_to_clipboard and DisplayServer.get_name() != "headless":
		DisplayServer.clipboard_set(json_str)
		if _status_label != null:
			_status_label.text = "Saved to user://tuned_lighting.json & copied JSON to clipboard!"
	else:
		if _status_label != null:
			_status_label.text = "Saved to user://tuned_lighting.json"
