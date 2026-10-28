class_name BoatController
extends CharacterBody3D

@export var max_speed: float = 8.5
@export var max_reverse_speed: float = 3.0
@export var acceleration: float = 2.2
@export var deceleration: float = 1.4
@export var braking_deceleration: float = 3.2
@export var turn_speed: float = 0.68
@export var rudder_response: float = 1.8

@export_group("Wave & Buoyancy Visuals")
@export var base_waterline_offset: float = 0.24
@export var wave_rocking_intensity: float = 1.0
@export var bow_planing_lift: float = 0.06
@export var wave_tracking_speed: float = 18.0
@export var heave_spring_stiffness: float = 34.0
@export var heave_spring_damping: float = 9.2
@export var pitch_spring_stiffness: float = 26.0
@export var pitch_spring_damping: float = 7.8
@export var roll_spring_stiffness: float = 22.0
@export var roll_spring_damping: float = 6.4
@export var ocean_wave_speed: float = 1.25
@export var ocean_wave_height: float = 0.75
@export var bob_amplitude: float = 0.12
@export var bob_frequency: float = 2.2
@export var pitch_wave_amplitude: float = 0.04
@export var roll_wave_amplitude: float = 0.05
@export var throttle_pitch_factor: float = 0.008
@export var turn_roll_factor: float = 0.22
@export var visual_smoothing: float = 8.0
@export var boat_hull_half_size: Vector3 = Vector3(1.82, 2.2, 5.15)
@export var debug_show_wave_probes: bool = false

static var shared_wave_speed: float = 1.25
static var shared_wave_height: float = 0.75

@onready var visuals: Node3D = $Visuals as Node3D
@onready var searchlight_gimbal: Node3D = $Visuals/SearchlightGimbal as Node3D
@onready var bow_searchlight: SpotLight3D = $Visuals/SearchlightGimbal/BowSearchlight as SpotLight3D
@onready var bow_flood_spill: SpotLight3D = $Visuals/SearchlightGimbal/BowFloodSpill as SpotLight3D
@onready var water_surface_illuminator: SpotLight3D = $Visuals/SearchlightGimbal/WaterSurfaceIlluminator as SpotLight3D
@onready var cabin_lantern: OmniLight3D = $Visuals/CabinLantern as OmniLight3D
@onready var wheelhouse_interior_light: OmniLight3D = $Visuals/WheelhouseInteriorLight as OmniLight3D
@onready var boat_rim_fill_light: OmniLight3D = $Visuals/BoatRimFillLight as OmniLight3D
@onready var volumetric_beam_cone: MeshInstance3D = $Visuals/SearchlightGimbal/VolumetricBeamCone as MeshInstance3D
@onready var propeller_trail: GPUParticles3D = $WakeParticles/PropellerTrail as GPUParticles3D
@onready var port_wave: GPUParticles3D = $WakeParticles/PortWave as GPUParticles3D
@onready var starboard_wave: GPUParticles3D = $WakeParticles/StarboardWave as GPUParticles3D
@onready var bow_spray: GPUParticles3D = $WakeParticles/BowSpray as GPUParticles3D

var current_speed: float = 0.0
var current_turn_rate: float = 0.0
var fishing_mode_active: bool = false
var fishing_roll_offset: float = 0.0
var fishing_pitch_impulse: float = 0.0
var heave_vel: float = 0.0
var _heave_y: float = 0.0
var _pitch_vel: float = 0.0
var _roll_vel: float = 0.0
var _hull_pitch: float = 0.0
var _hull_roll: float = 0.0
var _buoyancy_initialized: bool = false
var _base_visuals_y: float = 0.0
var _ocean_shader_material: ShaderMaterial = null
var _debug_probe_spheres: Array[MeshInstance3D] = []
var _beam_shader_material: ShaderMaterial = null
var _diesel_player: AudioStreamPlayer3D = null
var _creak_player: AudioStreamPlayer3D = null
var _creak_stream: AudioStreamWAV = null
var _creak_timer: float = 6.5
var _stern_lantern_noise: FastNoiseLite = FastNoiseLite.new()
var _base_cabin_lantern_energy: float = 3.5
var base_searchlight_energy: float = 26.0
var base_water_path_energy: float = 34.0
var base_cabin_lantern_energy: float = 3.5
var fp_fishing_fov: float = 85.0
var helm_fov: float = 65.0

# Searchlight Stealth (L Key) & 3-Pip Hull Integrity State
const MAX_HULL_PIPS: int = 3
const SEARCHLIGHT_DIMMER_DURATION: float = 0.18

var _searchlight_active: bool = true
var _searchlight_dimmer_blend: float = 1.0
var hull_integrity_pips: int = MAX_HULL_PIPS
var _ram_invulnerability_timer: float = 0.0
var _ram_roll_impulse: float = 0.0
var _crimson_vignette_alpha: float = 0.0
var _stealth_hud_layer: CanvasLayer = null
var _stealth_badge_panel: PanelContainer = null
var _stealth_badge_label: Label = null
var _peaceful_badge_label: Label = null
var _nav_compass_panel: PanelContainer = null
var _nav_compass_label: Label = null
var _nav_hotkeys_label: Label = null
var _hull_pips_boxes: Array[ColorRect] = []
var _hull_status_label: Label = null
var _crimson_vignette_rect: ColorRect = null
var _ram_impact_player: AudioStreamPlayer3D = null
var _searchlight_toggle_player: AudioStreamPlayer3D = null
var _lamp_lens_override_mat: StandardMaterial3D = null
var _threat_director: RoamingThreatDirector = null


func _ready() -> void:
	_stern_lantern_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_stern_lantern_noise.seed = 1928
	_stern_lantern_noise.frequency = 0.95

	if visuals != null:
		_base_visuals_y = visuals.position.y
		_configure_trawler_materials(visuals)

	if searchlight_gimbal != null:
		searchlight_gimbal.rotation = Vector3.ZERO

	_configure_boat_volumetric_lights()

	if volumetric_beam_cone != null and volumetric_beam_cone.mesh != null:
		_beam_shader_material = volumetric_beam_cone.mesh.surface_get_material(0) as ShaderMaterial

	if searchlight_gimbal != null:
		var lens_mesh: MeshInstance3D = searchlight_gimbal.get_node_or_null("LensGlass") as MeshInstance3D
		if lens_mesh != null and lens_mesh.mesh != null and lens_mesh.mesh.get_surface_count() > 0:
			var orig_lens: StandardMaterial3D = lens_mesh.get_active_material(0) as StandardMaterial3D
			if orig_lens != null:
				_lamp_lens_override_mat = orig_lens.duplicate() as StandardMaterial3D
				lens_mesh.set_surface_override_material(0, _lamp_lens_override_mat)

	var emitters: Array[GPUParticles3D] = [propeller_trail, port_wave, starboard_wave, bow_spray]
	if visuals != null:
		var exhaust_emitter: GPUParticles3D = visuals.get_node_or_null("ExhaustSmoke") as GPUParticles3D
		if exhaust_emitter != null:
			emitters.append(exhaust_emitter)
	for emitter: GPUParticles3D in emitters:
		if emitter != null:
			emitter.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			emitter.local_coords = false
			if emitter != visuals.get_node_or_null("ExhaustSmoke"):
				emitter.emitting = false
			if emitter.draw_pass_1 != null:
				var p_mat: Material = emitter.draw_pass_1.surface_get_material(0)
				if p_mat is StandardMaterial3D:
					var std_p: StandardMaterial3D = p_mat as StandardMaterial3D
					std_p.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
					std_p.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
					std_p.cull_mode = BaseMaterial3D.CULL_DISABLED

	_setup_maritime_boat_audio()
	_build_stealth_and_hull_hud()
	_resolve_ocean_material()
	_sync_hull_exclusion_mask_to_ocean()
	call_deferred("_resolve_threat_director")


func _resolve_threat_director() -> void:
	if _threat_director == null:
		var parent_node: Node = get_parent()
		if parent_node != null:
			_threat_director = parent_node.get_node_or_null("RoamingThreatDirector") as RoamingThreatDirector
		if _threat_director == null and is_inside_tree():
			var nodes: Array[Node] = get_tree().get_nodes_in_group("roaming_threat_director")
			if not nodes.is_empty():
				_threat_director = nodes[0] as RoamingThreatDirector
	if _threat_director != null:
		if not _threat_director.debug_ignore_player_changed.is_connected(_on_debug_ignore_player_changed):
			_threat_director.debug_ignore_player_changed.connect(_on_debug_ignore_player_changed)
	_refresh_stealth_and_hull_hud()


func _on_debug_ignore_player_changed(_enabled: bool) -> void:
	_refresh_stealth_and_hull_hud()


func toggle_peaceful_mode() -> void:
	_resolve_threat_director()
	if _threat_director != null:
		_threat_director.toggle_debug_ignore_player()
	else:
		RoamingThreatDirector.shared_ignore_player = not RoamingThreatDirector.shared_ignore_player
	if _searchlight_toggle_player != null and DisplayServer.get_name() != "headless":
		_searchlight_toggle_player.pitch_scale = 1.18 if RoamingThreatDirector.shared_ignore_player else 0.78
		_searchlight_toggle_player.play()
	_refresh_stealth_and_hull_hud()


func _process(_delta: float) -> void:
	_sync_hull_exclusion_mask_to_ocean()
	_update_nav_compass_hud()


func _resolve_ocean_material() -> void:
	var parent_node: Node = get_parent()
	if parent_node != null:
		var ocean_mesh: MeshInstance3D = parent_node.get_node_or_null("Ocean") as MeshInstance3D
		if ocean_mesh != null:
			var water_mat: ShaderMaterial = ocean_mesh.get_active_material(0) as ShaderMaterial
			if water_mat == null and ocean_mesh.mesh != null:
				water_mat = ocean_mesh.mesh.surface_get_material(0) as ShaderMaterial
			_ocean_shader_material = water_mat


func _sync_hull_exclusion_mask_to_ocean() -> void:
	var synced_time: float = get_synced_ocean_time()
	RenderingServer.global_shader_parameter_set("ocean_time", synced_time)
	if _ocean_shader_material == null:
		_resolve_ocean_material()
	if _ocean_shader_material != null:
		_ocean_shader_material.set_shader_parameter("wave_time", synced_time)
		_ocean_shader_material.set_shader_parameter("boat_inv_xform", global_transform.affine_inverse())
		_ocean_shader_material.set_shader_parameter("boat_hull_half_size", boat_hull_half_size)


func set_debug_wave_probes_visible(enabled: bool) -> void:
	debug_show_wave_probes = enabled
	if enabled and _debug_probe_spheres.is_empty():
		var parent_root: Node = get_parent()
		if parent_root == null:
			parent_root = self
		var colors: Array[Color] = [
			Color(0.0, 1.0, 0.25, 1.0), # Bow: Neon Green
			Color(1.0, 0.0, 0.85, 1.0), # Stern: Neon Magenta
			Color(0.0, 0.95, 1.0, 1.0), # Port: Neon Cyan
			Color(1.0, 0.92, 0.0, 1.0), # Starboard: Neon Yellow
			Color(1.0, 0.25, 0.0, 1.0), # Center: Neon Orange
		]
		var names: Array[String] = ["ProbeBow", "ProbeStern", "ProbePort", "ProbeStarboard", "ProbeCenter"]
		for i: int in range(5):
			var mi: MeshInstance3D = MeshInstance3D.new()
			mi.name = names[i]
			mi.top_level = true
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			var sph: SphereMesh = SphereMesh.new()
			sph.radius = 0.25
			sph.height = 0.50
			sph.radial_segments = 16
			sph.rings = 8
			var mat: StandardMaterial3D = StandardMaterial3D.new()
			mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			mat.albedo_color = colors[i]
			sph.material = mat
			mi.mesh = sph
			parent_root.add_child(mi)
			_debug_probe_spheres.append(mi)
	for probe: MeshInstance3D in _debug_probe_spheres:
		if probe != null and is_instance_valid(probe):
			probe.visible = enabled


func _configure_boat_volumetric_lights() -> void:
	if bow_searchlight != null:
		bow_searchlight.position = Vector3(0.0, 0.08, -0.18)
		bow_searchlight.rotation_degrees = Vector3(-4.5, 0.0, 0.0)
		bow_searchlight.light_color = Color(1.0, 0.86, 0.62, 1.0)
		bow_searchlight.light_energy = 26.0
		bow_searchlight.spot_range = 95.0
		bow_searchlight.spot_attenuation = 0.72
		bow_searchlight.spot_angle = 32.0
		bow_searchlight.spot_angle_attenuation = 1.35
		bow_searchlight.light_specular = 2.8
		bow_searchlight.shadow_enabled = true
		bow_searchlight.shadow_blur = 1.5
		bow_searchlight.light_volumetric_fog_energy = 2.4
	if bow_flood_spill != null:
		bow_flood_spill.rotation_degrees = Vector3(-6.0, 0.0, 0.0)
		bow_flood_spill.light_color = Color(0.98, 0.88, 0.68, 1.0)
		bow_flood_spill.light_energy = 4.5
		bow_flood_spill.spot_range = 85.0
		bow_flood_spill.spot_attenuation = 1.2
		bow_flood_spill.spot_angle = 48.0
		bow_flood_spill.spot_angle_attenuation = 2.8
		bow_flood_spill.light_volumetric_fog_energy = 0.05
	if water_surface_illuminator != null:
		water_surface_illuminator.position = Vector3(0.0, 2.2, -12.5)
		water_surface_illuminator.rotation_degrees = Vector3(-7.5, 0.0, 0.0)
		water_surface_illuminator.light_color = Color(0.98, 0.88, 0.68, 1.0)
		water_surface_illuminator.light_volumetric_fog_energy = 0.0
		water_surface_illuminator.light_energy = 34.0
		water_surface_illuminator.spot_range = 150.0
		water_surface_illuminator.spot_attenuation = 0.65
		water_surface_illuminator.spot_angle = 36.0
		water_surface_illuminator.spot_angle_attenuation = 2.4
	if cabin_lantern != null:
		cabin_lantern.light_color = Color(1.0, 0.68, 0.32, 1.0)
		cabin_lantern.light_energy = 3.5
		cabin_lantern.omni_range = 15.0
		cabin_lantern.omni_attenuation = 0.85
		cabin_lantern.shadow_enabled = true
		cabin_lantern.light_volumetric_fog_energy = 0.9
		_base_cabin_lantern_energy = cabin_lantern.light_energy
	if wheelhouse_interior_light != null:
		wheelhouse_interior_light.light_color = Color(0.95, 0.62, 0.28, 1.0)
		wheelhouse_interior_light.light_energy = 1.6
		wheelhouse_interior_light.omni_range = 4.0
		wheelhouse_interior_light.light_volumetric_fog_energy = 0.15
	if boat_rim_fill_light != null:
		boat_rim_fill_light.light_color = Color(0.28, 0.42, 0.52, 1.0)
		boat_rim_fill_light.light_energy = 0.55
		boat_rim_fill_light.omni_range = 14.0
		boat_rim_fill_light.light_volumetric_fog_energy = 0.0
	if visuals != null:
		var cabin_spill: OmniLight3D = visuals.get_node_or_null("CabinWarmSpillLight") as OmniLight3D
		if cabin_spill != null:
			cabin_spill.light_color = Color(1.0, 0.62, 0.25, 1.0)
			cabin_spill.light_energy = 2.8
			cabin_spill.omni_range = 6.5
			cabin_spill.light_volumetric_fog_energy = 0.8
			cabin_spill.shadow_enabled = true
		var mast_light: OmniLight3D = visuals.get_node_or_null("MastheadLight") as OmniLight3D
		if mast_light != null:
			mast_light.light_color = Color(1.0, 0.72, 0.35, 1.0)
			mast_light.light_energy = 3.2
			mast_light.omni_range = 14.0
			mast_light.omni_attenuation = 0.85
			mast_light.light_volumetric_fog_energy = 1.4
		var winch_light: Light3D = visuals.get_node_or_null("WinchWorkLight") as Light3D
		if winch_light != null:
			winch_light.light_volumetric_fog_energy = 0.35

		var aft_area_light: Light3D = visuals.get_node_or_null("AftDeckAreaWorkLight") as Light3D
		if aft_area_light == null:
			LightingUtils.create_area_or_omni_light(
				visuals,
				"AftDeckAreaWorkLight",
				Vector3(0.0, 1.85, 1.35),
				Vector3(-22.0, 0.0, 0.0),
				Vector2(1.6, 0.8),
				Color(1.0, 0.72, 0.38, 1.0),
				1.4,
				7.5,
				false,
				1.0,
				0.25,
				80.0
			)


func _setup_maritime_boat_audio() -> void:
	_diesel_player = AudioStreamPlayer3D.new()
	_diesel_player.name = "DieselEngineAudio"
	_diesel_player.stream = _build_diesel_engine_loop_wav()
	_diesel_player.unit_size = 6.0
	_diesel_player.max_distance = 55.0
	_diesel_player.max_db = -6.0
	_diesel_player.volume_db = -10.0
	_diesel_player.pitch_scale = 0.78
	_diesel_player.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
	add_child(_diesel_player)
	if DisplayServer.get_name() != "headless":
		_diesel_player.play()

	_creak_stream = _build_hull_creak_wav()
	_creak_player = AudioStreamPlayer3D.new()
	_creak_player.name = "HullTimberCreakAudio"
	_creak_player.stream = _creak_stream
	_creak_player.unit_size = 6.0
	_creak_player.max_distance = 40.0
	_creak_player.max_db = -6.0
	_creak_player.volume_db = -10.5
	_creak_player.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
	add_child(_creak_player)

	_ram_impact_player = AudioStreamPlayer3D.new()
	_ram_impact_player.name = "HullRamImpactAudio"
	_ram_impact_player.stream = _build_ram_impact_wav()
	_ram_impact_player.unit_size = 10.0
	_ram_impact_player.max_distance = 80.0
	_ram_impact_player.max_db = 0.0
	_ram_impact_player.volume_db = -2.5
	_ram_impact_player.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
	add_child(_ram_impact_player)

	_searchlight_toggle_player = AudioStreamPlayer3D.new()
	_searchlight_toggle_player.name = "SearchlightRelayAudio"
	_searchlight_toggle_player.stream = _build_relay_click_wav()
	_searchlight_toggle_player.unit_size = 6.0
	_searchlight_toggle_player.max_distance = 30.0
	_searchlight_toggle_player.max_db = -4.0
	_searchlight_toggle_player.volume_db = -7.0
	_searchlight_toggle_player.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
	add_child(_searchlight_toggle_player)


func _build_diesel_engine_loop_wav() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var duration_sec: float = 2.0
	var count: int = int(duration_sec * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	var chug_freq: float = 14.0
	var sub_freq_a: float = 49.0
	var sub_freq_b: float = 70.0
	var burble_freq: float = 84.0
	var pink_state: float = 0.0

	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var chug_phase: float = fmod(t * chug_freq, 1.0)
		var four_stroke_accent: float = 1.0 if (int(floor(t * chug_freq)) % 2 == 0) else 0.76
		var cylinder_pulse: float = exp(-chug_phase * 5.8) * four_stroke_accent
		var sub_thrum: float = (
			sin(t * TAU * sub_freq_a) * 0.52
			+ sin(t * TAU * sub_freq_b + cylinder_pulse * 0.8) * 0.34
			+ sin(t * TAU * (sub_freq_a * 0.5)) * 0.28
		)
		var s_hash: float = sin(float(i) * 12.9898 + 132.99) * 43758.5453
		var raw_n: float = (s_hash - floor(s_hash)) * 2.0 - 1.0
		pink_state = pink_state * 0.94 + raw_n * 0.06
		var burble: float = sin(t * TAU * burble_freq + pink_state * 3.5) * 0.22 * (0.4 + 0.6 * cylinder_pulse)
		buf[i] = sub_thrum * (0.55 + 0.45 * cylinder_pulse) + burble + pink_state * cylinder_pulse * 0.30

	_apply_biquad_lpf_cascade(buf, 140.0, 0.78, float(mix_rate))
	return _pack_samples_to_wav(buf, 0.82, mix_rate, true)


func _build_hull_creak_wav() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var duration_sec: float = 0.85
	var count: int = int(duration_sec * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	var phase: float = 0.0
	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var frac: float = float(i) / float(max(1, count - 1))
		var env: float = sin(frac * PI) * (0.75 + 0.25 * sin(t * TAU * 5.5))
		var base_hz: float = lerpf(72.0, 96.0, sin(frac * PI)) + sin(t * TAU * 11.0) * 12.0
		phase += TAU * base_hz / float(mix_rate)
		var sig: float = (
			sin(phase) * 0.58
			+ sin(phase * 2.0 + 0.4) * 0.26
			+ sin(phase * 3.0 + 1.1) * 0.12
		)
		buf[i] = sig * env

	_apply_biquad_lpf_cascade(buf, 240.0, 0.85, float(mix_rate))
	return _pack_samples_to_wav(buf, 0.76, mix_rate, false)


func _build_ram_impact_wav() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var duration_sec: float = 0.72
	var count: int = int(duration_sec * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var env: float = exp(-t * 6.8)
		var sub_boom: float = sin(t * TAU * lerpf(98.0, 34.0, clampf(t * 2.4, 0.0, 1.0))) * 0.65
		var metal_crunch: float = sin(t * TAU * 186.0 + sin(t * TAU * 47.0) * 3.8) * 0.35 * exp(-t * 11.0)
		var n_hash: float = sin(float(i) * 12.9898 + 78.233) * 43758.5453
		var noise_burst: float = ((n_hash - floor(n_hash)) * 2.0 - 1.0) * 0.42 * exp(-t * 16.0)
		buf[i] = (sub_boom + metal_crunch + noise_burst) * env

	_apply_biquad_lpf_cascade(buf, 420.0, 0.90, float(mix_rate))
	return _pack_samples_to_wav(buf, 0.92, mix_rate, false)


func _build_relay_click_wav() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var duration_sec: float = 0.14
	var count: int = int(duration_sec * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var click_a: float = sin(t * TAU * 640.0) * exp(-t * 85.0) * 0.75
		var click_b: float = sin(maxf(0.0, t - 0.032) * TAU * 420.0) * exp(-maxf(0.0, t - 0.032) * 70.0) * (0.65 if t >= 0.032 else 0.0)
		buf[i] = click_a + click_b

	return _pack_samples_to_wav(buf, 0.80, mix_rate, false)


func _apply_biquad_lpf_cascade(samples: PackedFloat32Array, cutoff_hz: float, q: float, sample_rate: float) -> void:
	var clamped_fc: float = clampf(cutoff_hz, 20.0, sample_rate * 0.45)
	var omega: float = TAU * clamped_fc / sample_rate
	var sn: float = sin(omega)
	var cs: float = cos(omega)
	var alpha: float = sn / (2.0 * maxf(q, 0.1))
	var a0: float = 1.0 + alpha
	var b0: float = ((1.0 - cs) * 0.5) / a0
	var b1: float = (1.0 - cs) / a0
	var b2: float = ((1.0 - cs) * 0.5) / a0
	var a1: float = (-2.0 * cs) / a0
	var a2: float = (1.0 - alpha) / a0

	for _pass: int in range(2):
		var x1: float = 0.0
		var x2: float = 0.0
		var y1: float = 0.0
		var y2: float = 0.0
		for i: int in range(samples.size()):
			var x0: float = samples[i]
			var y0: float = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
			x2 = x1
			x1 = x0
			y2 = y1
			y1 = y0
			samples[i] = y0


func _pack_samples_to_wav(samples: PackedFloat32Array, gain: float, mix_rate: int, loop_enabled: bool) -> AudioStreamWAV:
	var count: int = samples.size()
	var pcm: PackedByteArray = PackedByteArray()
	pcm.resize(count * 2)
	var fade_in_len: int = min(64, count)
	var fade_out_len: int = min(256, count)

	for i: int in range(count):
		var env_edge: float = 1.0
		if not loop_enabled:
			if i < fade_in_len:
				env_edge *= float(i) / float(max(1, fade_in_len))
			if i >= count - fade_out_len:
				var rem: int = (count - 1) - i
				env_edge *= float(rem) / float(max(1, fade_out_len))
		else:
			if i < 64:
				env_edge *= float(i) / 64.0
			elif i >= count - 64:
				env_edge *= float((count - 1) - i) / 64.0

		var v: float = clampf(samples[i] * gain * env_edge, -0.98, 0.98)
		var s16: int = clampi(int(round(v * 32767.0)), -32767, 32767)
		pcm.encode_s16(i * 2, s16)

	var wav: AudioStreamWAV = AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = mix_rate
	wav.stereo = false
	wav.data = pcm
	if loop_enabled:
		wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
		wav.loop_begin = 0
		wav.loop_end = count
	else:
		wav.loop_mode = AudioStreamWAV.LOOP_DISABLED
	return wav


func _configure_trawler_materials(root_node: Node) -> void:
	var mesh_nodes: Array[Node] = root_node.find_children("*", "MeshInstance3D", true, false)
	for node: Node in mesh_nodes:
		var mesh_inst: MeshInstance3D = node as MeshInstance3D
		if mesh_inst == null or mesh_inst.mesh == null:
			continue
		if mesh_inst.name == "LampHousing" or mesh_inst.name == "LensGlass" or mesh_inst.name == "VolumetricBeamCone" or mesh_inst.name == "BowSearchlightCone":
			continue
		var surface_count: int = mesh_inst.mesh.get_surface_count()
		for surf_idx: int in range(surface_count):
			var mat: Material = mesh_inst.get_active_material(surf_idx)
			var std_mat: StandardMaterial3D = mat as StandardMaterial3D
			if std_mat == null:
				continue
			if std_mat.resource_name == "WindowGlow" or std_mat.emission_enabled:
				var glow_mat: StandardMaterial3D = std_mat.duplicate() as StandardMaterial3D
				glow_mat.albedo_color = Color(1.0, 0.72, 0.30, 1.0)
				glow_mat.roughness = 0.15
				glow_mat.emission_enabled = true
				glow_mat.emission = Color(1.0, 0.65, 0.22, 1.0)
				glow_mat.emission_energy_multiplier = 3.5
				mesh_inst.set_surface_override_material(surf_idx, glow_mat)
			else:
				var matte_mat: StandardMaterial3D = std_mat.duplicate() as StandardMaterial3D
				matte_mat.roughness = clampf(maxf(std_mat.roughness, 0.88), 0.82, 0.95)
				matte_mat.metallic = minf(std_mat.metallic, 0.20)
				matte_mat.metallic_specular = 0.20
				matte_mat.clearcoat_enabled = false
				matte_mat.vertex_color_use_as_albedo = true
				mesh_inst.set_surface_override_material(surf_idx, matte_mat)


func _exit_tree() -> void:
	_beam_shader_material = null
	_lamp_lens_override_mat = null
	_creak_stream = null
	if _diesel_player != null:
		_diesel_player.stop()
		_diesel_player.stream = null
	if _creak_player != null:
		_creak_player.stop()
		_creak_player.stream = null
	if _ram_impact_player != null:
		_ram_impact_player.stop()
		_ram_impact_player.stream = null
	if _searchlight_toggle_player != null:
		_searchlight_toggle_player.stop()
		_searchlight_toggle_player.stream = null
	if visuals != null:
		var mesh_nodes: Array[Node] = visuals.find_children("*", "MeshInstance3D", true, false)
		for node: Node in mesh_nodes:
			var mesh_inst: MeshInstance3D = node as MeshInstance3D
			if mesh_inst != null and mesh_inst.mesh != null:
				for surf_idx: int in range(mesh_inst.mesh.get_surface_count()):
					mesh_inst.set_surface_override_material(surf_idx, null)


func _physics_process(delta: float) -> void:
	var turn_input: float = Input.get_axis("ui_right", "ui_left")
	if is_zero_approx(turn_input) and InputMap.has_action("turn_left") and InputMap.has_action("turn_right"):
		turn_input = Input.get_axis("turn_right", "turn_left")

	var throttle_input: float = Input.get_axis("ui_down", "ui_up")
	if is_zero_approx(throttle_input) and InputMap.has_action("move_forward") and InputMap.has_action("move_backward"):
		throttle_input = Input.get_axis("move_backward", "move_forward")

	var safe_max_speed: float = maxf(max_speed, 0.001)
	if fishing_mode_active:
		# Lock out normal W/S boat throttle & apply strong sea-anchor braking drag
		throttle_input = 0.0
		current_speed = move_toward(current_speed, 0.0, 4.0 * delta)
		# Dedicated stationary prop-wash rudder authority (0.45 rad/sec) to align stern with fish pull
		var fishing_target_turn: float = turn_input * 0.45
		current_turn_rate = lerpf(current_turn_rate, fishing_target_turn, clampf(rudder_response * 1.4 * delta, 0.0, 1.0))
	else:
		# Determine target speed and heavy displacement hull acceleration / coasting / braking rate
		var target_speed: float = 0.0
		if throttle_input > 0.0:
			target_speed = throttle_input * max_speed
		elif throttle_input < 0.0:
			target_speed = throttle_input * max_reverse_speed

		var rate: float = deceleration
		if not is_zero_approx(throttle_input):
			var is_braking: bool = (throttle_input > 0.0 and current_speed < -0.05) or (throttle_input < 0.0 and current_speed > 0.05)
			rate = braking_deceleration if is_braking else acceleration

		current_speed = move_toward(current_speed, target_speed, rate * delta)

		# Hydrodynamic Steering Effectiveness based on abs(current_speed) / max_speed:
		# 0.22 at dead stop (prop-wash only) -> 1.0 at 50% speed -> 0.85 at 100% speed
		var speed_norm: float = clampf(absf(current_speed) / safe_max_speed, 0.0, 1.0)
		var steering_effectiveness: float = 0.22
		if speed_norm <= 0.5:
			steering_effectiveness = lerpf(0.22, 1.0, speed_norm / 0.5)
		else:
			steering_effectiveness = lerpf(1.0, 0.85, (speed_norm - 0.5) / 0.5)

		var reverse_dir: float = -1.0 if current_speed < -0.15 else 1.0
		var target_turn_rate: float = turn_input * turn_speed * steering_effectiveness * reverse_dir
		current_turn_rate = lerpf(current_turn_rate, target_turn_rate, clampf(rudder_response * delta, 0.0, 1.0))

	rotation.y += current_turn_rate * delta

	# Reset physics transform to flat horizontal plane Y = 0.0 before move_and_slide()
	# so WorldBoundaryShape3D and island colliders resolve cleanly on the horizontal plane
	global_position.y = 0.0
	rotation.x = 0.0
	rotation.z = 0.0

	# Strictly horizontal movement vector (Y = 0.0)
	var planar_forward: Vector3 = Vector3(-global_transform.basis.z.x, 0.0, -global_transform.basis.z.z)
	var forward_dir: Vector3 = Vector3.FORWARD
	if planar_forward.length_squared() > 0.0001:
		forward_dir = planar_forward.normalized()

	# Hull drift / side-slip: blend horizontal velocity toward forward_dir * current_speed
	var horizontal_vel: Vector3 = Vector3(velocity.x, 0.0, velocity.z)
	var drifted_vel: Vector3 = horizontal_vel.lerp(forward_dir * current_speed, clampf(3.5 * delta, 0.0, 1.0))
	velocity.x = drifted_vel.x
	velocity.z = drifted_vel.z
	velocity.y = 0.0

	move_and_slide()
	# Prevent WorldBoundaryShape3D or collision slopes from lifting the CharacterBody3D off Y = 0.0
	velocity.y = 0.0
	global_position.y = 0.0

	# Keep internal speed synchronized if colliding with obstacles
	var planar_velocity: Vector3 = Vector3(velocity.x, 0.0, velocity.z)
	if is_on_wall():
		current_speed = planar_velocity.dot(forward_dir)

	shared_wave_speed = ocean_wave_speed
	shared_wave_height = ocean_wave_height
	RenderingServer.global_shader_parameter_set("ocean_time", get_synced_ocean_time())

	_update_wake_particles(turn_input)
	_update_visual_buoyancy(delta)
	_sync_hull_exclusion_mask_to_ocean()
	_update_searchlight(delta)


func _update_wake_particles(turn_input: float) -> void:
	var safe_max_speed: float = maxf(max_speed, 0.001)
	var speed_ratio: float = clampf(absf(current_speed) / safe_max_speed, 0.0, 1.0)
	var should_emit_wake: bool = absf(current_speed) > 0.4

	if propeller_trail != null:
		propeller_trail.amount_ratio = speed_ratio
		propeller_trail.emitting = should_emit_wake

	if port_wave != null:
		port_wave.amount_ratio = speed_ratio
		port_wave.emitting = should_emit_wake

	if starboard_wave != null:
		starboard_wave.amount_ratio = speed_ratio
		starboard_wave.emitting = should_emit_wake

	if bow_spray != null:
		var forward_ratio: float = clampf(current_speed / safe_max_speed, 0.0, 1.0)
		var should_emit_spray: bool = forward_ratio > 0.35
		var turn_boost: float = absf(turn_input) * 0.3
		var spray_ratio: float = clampf(((forward_ratio - 0.35) / 0.65) + turn_boost, 0.0, 1.0)
		bow_spray.amount_ratio = spray_ratio if should_emit_spray else 0.0
		bow_spray.emitting = should_emit_spray


static func get_synced_ocean_time() -> float:
	return float(Time.get_ticks_msec()) * 0.001


static func _gerstner_layer_displacement(dir: Vector2, steepness: float, wavelength: float, pos_xz: Vector2, layer_time: float) -> Vector3:
	var k: float = 6.28318530718 / maxf(wavelength, 0.001)
	var c: float = sqrt(9.8 / k) * shared_wave_speed
	var d: Vector2 = dir.normalized()
	var f: float = k * (d.dot(pos_xz) - c * layer_time)
	var s: float = steepness * shared_wave_height
	var a: float = s / k
	var cos_f: float = cos(f)
	var sin_f: float = sin(f)
	return Vector3(d.x * a * cos_f, a * sin_f, d.y * a * cos_f)


static func gerstner_horizontal_offset(world_xz: Vector2, t: float) -> Vector2:
	var disp: Vector3 = Vector3.ZERO
	disp += _gerstner_layer_displacement(Vector2(1.0, 0.35), 0.30, 18.0, world_xz, t)
	disp += _gerstner_layer_displacement(Vector2(0.65, -0.75), 0.24, 11.5, world_xz, t * 1.08)
	disp += _gerstner_layer_displacement(Vector2(-0.45, 0.88), 0.18, 6.8, world_xz, t * 1.15)
	disp += _gerstner_layer_displacement(Vector2(-0.82, -0.55), 0.14, 4.2, world_xz, t * 1.25)
	return Vector2(disp.x, disp.z)


static func _gerstner_vertical_height_raw(sample_xz: Vector2, t: float) -> float:
	var y_disp: float = 0.0
	y_disp += _gerstner_layer_displacement(Vector2(1.0, 0.35), 0.30, 18.0, sample_xz, t).y
	y_disp += _gerstner_layer_displacement(Vector2(0.65, -0.75), 0.24, 11.5, sample_xz, t * 1.08).y
	y_disp += _gerstner_layer_displacement(Vector2(-0.45, 0.88), 0.18, 6.8, sample_xz, t * 1.15).y
	y_disp += _gerstner_layer_displacement(Vector2(-0.82, -0.55), 0.14, 4.2, sample_xz, t * 1.25).y
	return y_disp


static func get_exact_water_height(world_xz: Vector2, time_override: float = -1.0) -> float:
	var t: float = time_override if time_override >= 0.0 else get_synced_ocean_time()
	# 2-iteration horizontal Gerstner displacement compensation so the CPU height lookup matches the rendered water mesh pixel-for-pixel
	var sample_pos: Vector2 = world_xz - gerstner_horizontal_offset(world_xz, t)
	sample_pos = world_xz - gerstner_horizontal_offset(sample_pos, t)
	return _gerstner_vertical_height_raw(sample_pos, t)


static func get_exact_wave_plane(center_xz: Vector2, yaw: float, half_length: float = 4.2, half_beam: float = 1.8, time_override: float = -1.0) -> Dictionary:
	var t: float = time_override if time_override >= 0.0 else get_synced_ocean_time()
	var yaw_basis: Basis = Basis(Vector3.UP, yaw)
	var bow_off: Vector3 = yaw_basis * Vector3(0.0, 0.0, -half_length)
	var stern_off: Vector3 = yaw_basis * Vector3(0.0, 0.0, half_length)
	var port_off: Vector3 = yaw_basis * Vector3(-half_beam, 0.0, 0.0)
	var stbd_off: Vector3 = yaw_basis * Vector3(half_beam, 0.0, 0.0)

	var p_bow: Vector2 = Vector2(center_xz.x + bow_off.x, center_xz.y + bow_off.z)
	var p_stern: Vector2 = Vector2(center_xz.x + stern_off.x, center_xz.y + stern_off.z)
	var p_port: Vector2 = Vector2(center_xz.x + port_off.x, center_xz.y + port_off.z)
	var p_starboard: Vector2 = Vector2(center_xz.x + stbd_off.x, center_xz.y + stbd_off.z)

	var h_bow: float = get_exact_water_height(p_bow, t)
	var h_stern: float = get_exact_water_height(p_stern, t)
	var h_port: float = get_exact_water_height(p_port, t)
	var h_starboard: float = get_exact_water_height(p_starboard, t)
	var h_center: float = get_exact_water_height(center_xz, t)

	var weighted_height: float = (
		h_bow * 0.25
		+ h_stern * 0.25
		+ h_port * 0.15
		+ h_starboard * 0.15
		+ h_center * 0.20
	)

	var vec_long: Vector3 = Vector3(p_bow.x, h_bow, p_bow.y) - Vector3(p_stern.x, h_stern, p_stern.y)
	var vec_lat: Vector3 = Vector3(p_starboard.x, h_starboard, p_starboard.y) - Vector3(p_port.x, h_port, p_port.y)
	var wave_normal: Vector3 = vec_lat.cross(vec_long).normalized()
	if wave_normal.y < 0.0:
		wave_normal = -wave_normal
	if wave_normal.length_squared() < 0.0001:
		wave_normal = Vector3.UP

	var local_normal: Vector3 = (yaw_basis.inverse() * wave_normal).normalized()
	var safe_ny: float = maxf(local_normal.y, 0.001)
	var local_pitch: float = atan2(local_normal.z, safe_ny)
	var local_roll: float = atan2(-local_normal.x, safe_ny)

	return {
		"h_bow": h_bow,
		"h_stern": h_stern,
		"h_port": h_port,
		"h_starboard": h_starboard,
		"h_center": h_center,
		"weighted_height": weighted_height,
		"wave_normal": wave_normal,
		"local_pitch": local_pitch,
		"local_roll": local_roll
	}


func get_wave_height_at(world_xz: Vector2, time_sec: float = -1.0) -> float:
	return get_exact_water_height(world_xz, time_sec)


func _update_visual_buoyancy(delta: float) -> void:
	var time_sec: float = get_synced_ocean_time()
	var safe_max_speed: float = maxf(max_speed, 0.001)
	var speed_ratio: float = clampf(absf(current_speed) / safe_max_speed, 0.0, 1.0)
	var forward_ratio: float = clampf(current_speed / safe_max_speed, 0.0, 1.0)

	# 4-Point Hull Footprint Plane Fitting at physical hull corners (+2.15m bow, -2.15m stern, -0.90m port, +0.90m starboard, plus center)
	var yaw: float = rotation.y
	var yaw_basis: Basis = Basis(Vector3.UP, yaw)
	var center_xz: Vector2 = Vector2(global_position.x, global_position.z)

	var bow_off: Vector3 = yaw_basis * Vector3(0.0, 0.0, -2.15)
	var stern_off: Vector3 = yaw_basis * Vector3(0.0, 0.0, 2.15)
	var port_off: Vector3 = yaw_basis * Vector3(-0.90, 0.0, 0.0)
	var stbd_off: Vector3 = yaw_basis * Vector3(0.90, 0.0, 0.0)

	var p_bow: Vector3 = Vector3(center_xz.x + bow_off.x, 0.0, center_xz.y + bow_off.z)
	var p_stern: Vector3 = Vector3(center_xz.x + stern_off.x, 0.0, center_xz.y + stern_off.z)
	var p_port: Vector3 = Vector3(center_xz.x + port_off.x, 0.0, center_xz.y + port_off.z)
	var p_starboard: Vector3 = Vector3(center_xz.x + stbd_off.x, 0.0, center_xz.y + stbd_off.z)

	var h_bow: float = get_exact_water_height(Vector2(p_bow.x, p_bow.z), time_sec)
	var h_stern: float = get_exact_water_height(Vector2(p_stern.x, p_stern.z), time_sec)
	var h_port: float = get_exact_water_height(Vector2(p_port.x, p_port.z), time_sec)
	var h_starboard: float = get_exact_water_height(Vector2(p_starboard.x, p_starboard.z), time_sec)
	var h_center: float = get_exact_water_height(center_xz, time_sec)

	if debug_show_wave_probes:
		if _debug_probe_spheres.is_empty():
			set_debug_wave_probes_visible(true)
		if _debug_probe_spheres.size() >= 5:
			_debug_probe_spheres[0].global_position = Vector3(p_bow.x, h_bow, p_bow.z)
			_debug_probe_spheres[1].global_position = Vector3(p_stern.x, h_stern, p_stern.z)
			_debug_probe_spheres[2].global_position = Vector3(p_port.x, h_port, p_port.z)
			_debug_probe_spheres[3].global_position = Vector3(p_starboard.x, h_starboard, p_starboard.z)
			_debug_probe_spheres[4].global_position = Vector3(center_xz.x, h_center, center_xz.y)

	# Weighted average water height under the keel + waterline offset + planing lift
	var planing_lift: float = bow_planing_lift * speed_ratio
	var target_y: float = (
		h_bow * 0.25
		+ h_stern * 0.25
		+ h_port * 0.15
		+ h_starboard * 0.15
		+ h_center * 0.20
	) + base_waterline_offset + planing_lift

	# True 3D Wave Surface Normal from the 4 hull probes
	var vec_long: Vector3 = Vector3(p_bow.x, h_bow, p_bow.z) - Vector3(p_stern.x, h_stern, p_stern.z)
	var vec_lat: Vector3 = Vector3(p_starboard.x, h_starboard, p_starboard.z) - Vector3(p_port.x, h_port, p_port.z)
	var wave_normal: Vector3 = vec_lat.cross(vec_long).normalized()
	if wave_normal.y < 0.0:
		wave_normal = -wave_normal
	if wave_normal.length_squared() < 0.0001:
		wave_normal = Vector3.UP

	var local_normal: Vector3 = (yaw_basis.inverse() * wave_normal).normalized()
	var safe_ny: float = maxf(local_normal.y, 0.001)
	var wave_pitch: float = atan2(local_normal.z, safe_ny) * wave_rocking_intensity
	var wave_roll: float = atan2(-local_normal.x, safe_ny) * 1.25 * wave_rocking_intensity

	# Pitch: wave slope normal + bow-up throttle planing tilt + fishing strike impulse
	fishing_pitch_impulse = move_toward(fishing_pitch_impulse, 0.0, delta * 0.25)
	_ram_roll_impulse = move_toward(_ram_roll_impulse, 0.0, delta * 0.38)
	var bow_up_planing_pitch: float = deg_to_rad(2.2) * forward_ratio
	var target_pitch: float = clampf(wave_pitch + bow_up_planing_pitch + fishing_pitch_impulse, -0.28, 0.30)

	# Roll: 1.25x amplified beam wave slope + rudder bank when turning + fishing cable pull + ram impulse
	var turn_roll: float = clampf(-current_turn_rate * turn_roll_factor, -0.16, 0.16)
	var target_roll: float = clampf(wave_roll + turn_roll + fishing_roll_offset + _ram_roll_impulse, -0.34, 0.34)

	if not _buoyancy_initialized:
		_buoyancy_initialized = true
		_heave_y = target_y
		heave_vel = 0.0
		_hull_pitch = target_pitch
		_pitch_vel = 0.0
		_hull_roll = target_roll
		_roll_vel = 0.0
	else:
		# Tight real-time wave tracking (lerp weight delta * 18.0 for heave and delta * 14.0 for pitch/roll) with zero phase delay
		var heave_weight: float = clampf(delta * 18.0, 0.0, 1.0)
		var prev_heave: float = _heave_y
		_heave_y = lerpf(_heave_y, target_y, heave_weight)
		heave_vel = (_heave_y - prev_heave) / maxf(delta, 0.001)

		var angle_weight: float = clampf(delta * 14.0, 0.0, 1.0)
		_hull_pitch = clampf(lerpf(_hull_pitch, target_pitch, angle_weight), -0.30, 0.32)
		_hull_roll = clampf(lerpf(_hull_roll, target_roll, angle_weight), -0.36, 0.36)

	global_position.y = _heave_y
	rotation.x = _hull_pitch
	rotation.z = _hull_roll
	if visuals != null:
		visuals.position.y = _base_visuals_y
		visuals.rotation = Vector3.ZERO

	_update_maritime_boat_audio(delta, speed_ratio, absf(_hull_roll) + absf(_hull_pitch))


func _update_maritime_boat_audio(delta: float, speed_ratio: float, hull_stress: float) -> void:
	if _diesel_player != null:
		var base_vol_db: float = lerpf(-10.5, -3.5, speed_ratio)
		var target_vol_db: float = (base_vol_db - 10.0) if fishing_mode_active else base_vol_db
		var target_pitch: float = 0.72 if fishing_mode_active else lerpf(0.76, 1.38, speed_ratio)
		_diesel_player.volume_db = lerpf(_diesel_player.volume_db, target_vol_db, clampf(6.0 * delta, 0.0, 1.0))
		_diesel_player.pitch_scale = lerpf(_diesel_player.pitch_scale, target_pitch, clampf(6.0 * delta, 0.0, 1.0))

	_creak_timer -= delta * (1.0 + hull_stress * 3.5)
	if _creak_timer <= 0.0:
		_creak_timer = randf_range(5.5, 10.5)
		if _creak_player != null and not _creak_player.playing and DisplayServer.get_name() != "headless":
			_creak_player.volume_db = -16.5 if fishing_mode_active else -10.5
			_creak_player.pitch_scale = randf_range(0.84, 1.14)
			_creak_player.play()


func _update_searchlight(delta: float) -> void:
	if _ram_invulnerability_timer > 0.0:
		_ram_invulnerability_timer = maxf(0.0, _ram_invulnerability_timer - delta)

	if _crimson_vignette_alpha > 0.001:
		_crimson_vignette_alpha = move_toward(_crimson_vignette_alpha, 0.0, delta * 0.85)
		if _crimson_vignette_rect != null:
			_crimson_vignette_rect.color = Color(0.68, 0.06, 0.08, _crimson_vignette_alpha)
			_crimson_vignette_rect.visible = _crimson_vignette_alpha > 0.005

	var target_dimmer: float = 1.0 if _searchlight_active else 0.0
	var dimmer_step: float = delta / maxf(SEARCHLIGHT_DIMMER_DURATION, 0.01)
	_searchlight_dimmer_blend = move_toward(_searchlight_dimmer_blend, target_dimmer, dimmer_step)

	if searchlight_gimbal == null or visuals == null:
		return

	# Strictly static yaw locked dead-ahead along the bow (-Z)
	searchlight_gimbal.rotation.y = 0.0

	# Dynamic vertical horizon stabilization at -11.0 deg counteracting 70% of hull wave pitch
	var target_pitch: float = deg_to_rad(-11.0) - (_hull_pitch * 0.70)
	var weight: float = clampf(visual_smoothing * delta, 0.0, 1.0)
	searchlight_gimbal.rotation.x = lerpf(searchlight_gimbal.rotation.x, target_pitch, weight)

	# Dynamic diesel alternator surge based on engine RPM / boat speed + subtle ripple
	var time_sec: float = float(Time.get_ticks_msec()) * 0.001
	var speed_ratio: float = clampf(absf(current_speed) / maxf(max_speed, 0.001), 0.0, 1.0)
	var alternator_ripple: float = sin(time_sec * 18.0) * 0.025 + cos(time_sec * 7.3) * 0.015
	var surge_factor: float = lerpf(0.88, 1.12, speed_ratio) + alternator_ripple

	if bow_searchlight != null:
		var searchlight_ripple: float = (1.0 + alternator_ripple * 0.4) if base_searchlight_energy > 0.001 else 0.0
		bow_searchlight.light_energy = base_searchlight_energy * searchlight_ripple * _searchlight_dimmer_blend
		bow_searchlight.visible = _searchlight_dimmer_blend > 0.005

	if bow_flood_spill != null:
		bow_flood_spill.light_energy = 8.0 * surge_factor * _searchlight_dimmer_blend
		bow_flood_spill.visible = _searchlight_dimmer_blend > 0.005

	if water_surface_illuminator != null:
		var water_ripple: float = (1.0 + alternator_ripple * 0.3) if base_water_path_energy > 0.001 else 0.0
		water_surface_illuminator.light_energy = base_water_path_energy * water_ripple * _searchlight_dimmer_blend
		water_surface_illuminator.visible = _searchlight_dimmer_blend > 0.005

	if cabin_lantern != null:
		# Smooth 1D FastNoiseLite generator flicker (+-7% energy wobble) on the stern oil lantern
		var lantern_wobble: float = _stern_lantern_noise.get_noise_1d(time_sec * 3.4) * 0.07
		var active_cabin_base: float = base_cabin_lantern_energy
		_base_cabin_lantern_energy = active_cabin_base
		var stealth_lantern_scale: float = lerpf(0.35, 1.0, _searchlight_dimmer_blend)
		cabin_lantern.light_energy = active_cabin_base * (1.0 + lantern_wobble) * stealth_lantern_scale if active_cabin_base > 0.001 else 0.0

	if _beam_shader_material != null:
		_beam_shader_material.set_shader_parameter("intensity_multiplier", surge_factor * 1.18 * _searchlight_dimmer_blend)
	if volumetric_beam_cone != null:
		volumetric_beam_cone.visible = _searchlight_dimmer_blend > 0.01

	if _lamp_lens_override_mat != null:
		_lamp_lens_override_mat.emission_energy_multiplier = 8.0 * _searchlight_dimmer_blend


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey:
		var key_event: InputEventKey = event as InputEventKey
		if key_event.pressed and not key_event.echo:
			var code: Key = key_event.physical_keycode if key_event.physical_keycode != KEY_NONE else key_event.keycode
			if code == KEY_L:
				set_searchlight_active(not _searchlight_active)
			elif code == KEY_P or (code == KEY_F9 and not key_event.shift_pressed):
				toggle_peaceful_mode()
			elif code == KEY_1 or code == KEY_KP_1:
				teleport_to_landmark(1)
			elif code == KEY_2 or code == KEY_KP_2:
				teleport_to_landmark(2)
			elif code == KEY_3 or code == KEY_KP_3:
				teleport_to_landmark(3)
			elif code == KEY_4 or code == KEY_KP_4:
				teleport_to_landmark(4)


func teleport_to_landmark(slot: int) -> void:
	var dest_xz: Vector2 = Vector2.ZERO
	var dest_yaw: float = 0.0
	if slot == 1:
		# [1] Starting Harbor Dock
		dest_xz = Vector2(0.0, 0.0)
		dest_yaw = 0.0
	elif slot == 2:
		# [2] 65m South of the Fjord Entrance Gate Arch (at Z = -520.0), facing into Fjord canyon (-Z)
		dest_xz = Vector2(0.0, -455.0)
		dest_yaw = 0.0
	elif slot == 3:
		# [3] Inside the Fjord Basin 75m South of the Terraced Fishing Hamlet Island (at Z = -960.0)
		dest_xz = Vector2(0.0, -885.0)
		dest_yaw = 0.0
	elif slot == 4:
		# [4] 75m in front of the Stilt-Sanctuary Spires Cluster (at (380.0, -1.45, -180.0))
		dest_xz = Vector2(315.0, -145.0)
		dest_yaw = deg_to_rad(-60.0)
	else:
		return

	velocity = Vector3.ZERO
	current_speed = 0.0
	current_turn_rate = 0.0
	heave_vel = 0.0
	_pitch_vel = 0.0
	_roll_vel = 0.0
	_hull_pitch = 0.0
	_hull_roll = 0.0
	_buoyancy_initialized = false

	var wave_h: float = get_exact_water_height(dest_xz)
	var waterline_y: float = wave_h + base_waterline_offset
	_heave_y = waterline_y
	global_position = Vector3(dest_xz.x, waterline_y, dest_xz.y)
	rotation = Vector3(0.0, dest_yaw, 0.0)

	# Snap OverheadCamera immediately behind the boat so there is zero camera sweep lag
	var parent_node: Node = get_parent()
	if parent_node != null:
		var cam: OverheadCamera = parent_node.get_node_or_null("Camera3D") as OverheadCamera
		if cam != null:
			cam.target_yaw = dest_yaw
			cam.current_yaw = dest_yaw
			var fwd_dir: Vector3 = -global_transform.basis.z
			fwd_dir.y = 0.0
			if fwd_dir.length_squared() > 0.001:
				fwd_dir = fwd_dir.normalized()
			cam.focus_point = global_position + fwd_dir * cam.forward_look_ahead + Vector3(0.0, cam.target_height_offset, 0.0)
			var cam_offset: Vector3 = Basis.from_euler(Vector3(cam.current_pitch, cam.current_yaw, 0.0)) * Vector3(0.0, 0.0, cam.current_distance)
			cam.global_position = cam.focus_point + cam_offset
			cam.look_at(cam.focus_point, Vector3.UP)

	_update_visual_buoyancy(0.016)
	_sync_hull_exclusion_mask_to_ocean()
	_update_nav_compass_hud()


func _compass_cardinal_from_vec(dir_xz: Vector2) -> String:
	if dir_xz.length_squared() < 0.0001:
		return "N"
	# In Godot: -Z (dir_xz.y < 0) is North (0 deg), +X (dir_xz.x > 0) is East (90 deg), +Z is South (180 deg), -X is West (270 deg)
	var bearing_deg: float = fposmod(rad_to_deg(atan2(dir_xz.x, -dir_xz.y)), 360.0)
	var cardinals: Array[String] = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
	var idx: int = int(round(bearing_deg / 45.0)) % 8
	return cardinals[idx]


func _update_nav_compass_hud() -> void:
	if _nav_compass_label == null:
		return
	var boat_xz: Vector2 = Vector2(global_position.x, global_position.z)
	var fwd_3d: Vector3 = get_searchlight_forward_dir()
	var fwd_xz: Vector2 = Vector2(fwd_3d.x, fwd_3d.z)
	var hdg_deg: int = int(round(fposmod(rad_to_deg(atan2(fwd_xz.x, -fwd_xz.y)), 360.0))) % 360
	var hdg_card: String = _compass_cardinal_from_vec(fwd_xz)

	var fjord_gate_xz: Vector2 = Vector2(WorldBuilder.FJORD_GATE_ARCH_POS.x, WorldBuilder.FJORD_GATE_ARCH_POS.z)
	var to_gate: Vector2 = fjord_gate_xz - boat_xz
	var gate_dist: int = int(round(to_gate.length()))
	var gate_card: String = _compass_cardinal_from_vec(to_gate)

	_nav_compass_label.text = "POS: (%d, %d)   |   HDG: %03d° %s   |   [2] Fjord Gate: %dm %s" % [
		int(round(boat_xz.x)),
		int(round(boat_xz.y)),
		hdg_deg,
		hdg_card,
		gate_dist,
		gate_card,
	]


func set_searchlight_active(active: bool) -> void:
	if _searchlight_active == active:
		return
	_searchlight_active = active
	if _searchlight_toggle_player != null and DisplayServer.get_name() != "headless":
		_searchlight_toggle_player.pitch_scale = 1.06 if _searchlight_active else 0.86
		_searchlight_toggle_player.play()
	_refresh_stealth_and_hull_hud()


func is_searchlight_active() -> bool:
	return _searchlight_active and _searchlight_dimmer_blend > 0.25


func get_searchlight_forward_dir() -> Vector3:
	var planar_fwd: Vector3 = Vector3(-global_transform.basis.z.x, 0.0, -global_transform.basis.z.z)
	if planar_fwd.length_squared() > 0.0001:
		return planar_fwd.normalized()
	return Vector3.FORWARD


func get_throttle_noise_ratio() -> float:
	if fishing_mode_active:
		return 0.0
	return clampf(absf(current_speed) / maxf(max_speed, 0.001), 0.0, 1.0)


func repair_hull_full() -> void:
	hull_integrity_pips = MAX_HULL_PIPS
	_refresh_stealth_and_hull_hud()


func apply_enemy_ram_impulse(hit_dir: Vector3, severity: float) -> void:
	if RoamingThreatDirector.shared_ignore_player:
		return
	var clamped_sev: float = clampf(severity, 0.35, 2.5)
	var planar_dir: Vector3 = Vector3(hit_dir.x, 0.0, hit_dir.z)
	if planar_dir.length_squared() < 0.0001:
		planar_dir = -get_searchlight_forward_dir()
	else:
		planar_dir = planar_dir.normalized()

	# Physical velocity recoil & bow/stern speed knockback
	velocity.x += planar_dir.x * (9.5 * clamped_sev)
	velocity.z += planar_dir.z * (9.5 * clamped_sev)
	current_speed = clampf(current_speed * 0.25 + planar_dir.dot(get_searchlight_forward_dir()) * (4.2 * clamped_sev), -max_reverse_speed * 1.5, max_speed * 1.2)

	# Visual pitch & roll jolt
	fishing_pitch_impulse = clampf(fishing_pitch_impulse + 0.11 * clamped_sev, -0.18, 0.18)
	var right_vec: Vector3 = Vector3(global_transform.basis.x.x, 0.0, global_transform.basis.x.z).normalized()
	var side_sign: float = signf(planar_dir.dot(right_vec))
	if is_zero_approx(side_sign):
		side_sign = 1.0
	_ram_roll_impulse = clampf(_ram_roll_impulse + side_sign * 0.14 * clamped_sev, -0.22, 0.22)

	# Trigger camera shake on OverheadCamera
	var parent_node: Node = get_parent()
	if parent_node != null:
		var cam: OverheadCamera = parent_node.get_node_or_null("Camera3D") as OverheadCamera
		if cam != null:
			cam.camera_shake_intensity = maxf(cam.camera_shake_intensity, 1.85 * clamped_sev)

	# Flash crimson vignette & play metallic hull crunch audio
	_crimson_vignette_alpha = clampf(0.48 * clamped_sev, 0.28, 0.72)
	if _crimson_vignette_rect != null:
		_crimson_vignette_rect.color = Color(0.68, 0.06, 0.08, _crimson_vignette_alpha)
		_crimson_vignette_rect.visible = true

	if _ram_impact_player != null and DisplayServer.get_name() != "headless":
		_ram_impact_player.pitch_scale = randf_range(0.88, 1.08)
		_ram_impact_player.play()

	# Reduce 3-pip Hull Integrity meter (with 2.2s invulnerability window against multi-hit frame overlap)
	if _ram_invulnerability_timer <= 0.0:
		_ram_invulnerability_timer = 2.2
		hull_integrity_pips = maxi(0, hull_integrity_pips - 1)
		_refresh_stealth_and_hull_hud()


func _build_stealth_and_hull_hud() -> void:
	_stealth_hud_layer = CanvasLayer.new()
	_stealth_hud_layer.name = "StealthAndHullHUD"
	_stealth_hud_layer.layer = 9
	add_child(_stealth_hud_layer)

	# Fullscreen crimson damage vignette overlay
	_crimson_vignette_rect = ColorRect.new()
	_crimson_vignette_rect.name = "CrimsonRamVignette"
	_crimson_vignette_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_crimson_vignette_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_crimson_vignette_rect.color = Color(0.68, 0.06, 0.08, 0.0)
	_crimson_vignette_rect.visible = false
	_stealth_hud_layer.add_child(_crimson_vignette_rect)

	# Bottom-Left Nautical Stealth & Hull Integrity Status Panel
	_stealth_badge_panel = PanelContainer.new()
	_stealth_badge_panel.name = "StealthHullBadgePanel"
	_stealth_badge_panel.anchors_preset = Control.PRESET_BOTTOM_LEFT
	_stealth_badge_panel.anchor_left = 0.0
	_stealth_badge_panel.anchor_top = 1.0
	_stealth_badge_panel.anchor_right = 0.0
	_stealth_badge_panel.anchor_bottom = 1.0
	_stealth_badge_panel.offset_left = 24.0
	_stealth_badge_panel.offset_top = -140.0
	_stealth_badge_panel.offset_right = 456.0
	_stealth_badge_panel.offset_bottom = -24.0

	var sb: StyleBoxFlat = StyleBoxFlat.new()
	sb.bg_color = Color(0.024, 0.032, 0.044, 0.94)
	sb.border_width_left = 2
	sb.border_width_top = 2
	sb.border_width_right = 2
	sb.border_width_bottom = 2
	sb.border_color = Color(0.549, 0.427, 0.231, 0.96)
	sb.corner_radius_top_left = 3
	sb.corner_radius_top_right = 3
	sb.corner_radius_bottom_left = 3
	sb.corner_radius_bottom_right = 3
	sb.content_margin_left = 14.0
	sb.content_margin_right = 14.0
	sb.content_margin_top = 10.0
	sb.content_margin_bottom = 10.0
	_stealth_badge_panel.add_theme_stylebox_override("panel", sb)
	_stealth_hud_layer.add_child(_stealth_badge_panel)

	var vbox: VBoxContainer = VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 6)
	_stealth_badge_panel.add_child(vbox)

	_stealth_badge_label = Label.new()
	_stealth_badge_label.name = "StealthStatusBadgeLabel"
	_stealth_badge_label.add_theme_font_size_override("font_size", 13)
	vbox.add_child(_stealth_badge_label)

	var hull_hbox: HBoxContainer = HBoxContainer.new()
	hull_hbox.add_theme_constant_override("separation", 8)
	vbox.add_child(hull_hbox)

	var hull_title: Label = Label.new()
	hull_title.text = "HULL INTEGRITY:"
	hull_title.add_theme_color_override("font_color", Color(0.847, 0.808, 0.722, 1.0))
	hull_title.add_theme_font_size_override("font_size", 13)
	hull_hbox.add_child(hull_title)

	_hull_pips_boxes.clear()
	for pip_i: int in range(MAX_HULL_PIPS):
		var pip_rect: ColorRect = ColorRect.new()
		pip_rect.name = "HullPip_%d" % pip_i
		pip_rect.custom_minimum_size = Vector2(36.0, 14.0)
		pip_rect.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		hull_hbox.add_child(pip_rect)
		_hull_pips_boxes.append(pip_rect)

	_hull_status_label = Label.new()
	_hull_status_label.name = "HullPipCountLabel"
	_hull_status_label.add_theme_font_size_override("font_size", 12)
	hull_hbox.add_child(_hull_status_label)

	_peaceful_badge_label = Label.new()
	_peaceful_badge_label.name = "PeacefulModeStatusLabel"
	_peaceful_badge_label.add_theme_font_size_override("font_size", 12)
	vbox.add_child(_peaceful_badge_label)

	# Top-Left Navigation Compass, Coordinates & Instant Landmark Teleport Readout
	_nav_compass_panel = PanelContainer.new()
	_nav_compass_panel.name = "NavCompassTeleportPanel"
	_nav_compass_panel.anchors_preset = Control.PRESET_TOP_LEFT
	_nav_compass_panel.anchor_left = 0.0
	_nav_compass_panel.anchor_top = 0.0
	_nav_compass_panel.anchor_right = 0.0
	_nav_compass_panel.anchor_bottom = 0.0
	_nav_compass_panel.offset_left = 24.0
	_nav_compass_panel.offset_top = 20.0
	_nav_compass_panel.offset_right = 636.0
	_nav_compass_panel.offset_bottom = 86.0
	_nav_compass_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_nav_compass_panel.add_theme_stylebox_override("panel", sb.duplicate())
	_stealth_hud_layer.add_child(_nav_compass_panel)

	var nav_vbox: VBoxContainer = VBoxContainer.new()
	nav_vbox.add_theme_constant_override("separation", 4)
	_nav_compass_panel.add_child(nav_vbox)

	_nav_compass_label = Label.new()
	_nav_compass_label.name = "NavCompassTelemetryLabel"
	_nav_compass_label.add_theme_font_size_override("font_size", 13)
	_nav_compass_label.add_theme_color_override("font_color", Color(0.96, 0.80, 0.42, 1.0))
	nav_vbox.add_child(_nav_compass_label)

	_nav_hotkeys_label = Label.new()
	_nav_hotkeys_label.name = "NavTeleportHotkeysLabel"
	_nav_hotkeys_label.text = "TELEPORT:  [1] Harbor Dock   [2] Fjord Gate   [3] Terraced Hamlet   [4] Stilt Sanctuary"
	_nav_hotkeys_label.add_theme_font_size_override("font_size", 12)
	_nav_hotkeys_label.add_theme_color_override("font_color", Color(0.76, 0.84, 0.82, 0.92))
	nav_vbox.add_child(_nav_hotkeys_label)

	_refresh_stealth_and_hull_hud()
	_update_nav_compass_hud()


func _refresh_stealth_and_hull_hud() -> void:
	if _stealth_badge_label != null:
		if _searchlight_active:
			_stealth_badge_label.text = "SEARCHLIGHT: BLAZING [L] — High Visibility"
			_stealth_badge_label.add_theme_color_override("font_color", Color(0.96, 0.76, 0.34, 1.0))
		else:
			_stealth_badge_label.text = "STEALTH: RUNNING DARK [L] — Low Visibility"
			_stealth_badge_label.add_theme_color_override("font_color", Color(0.28, 0.84, 0.72, 1.0))

	if _peaceful_badge_label != null:
		var is_peaceful: bool = RoamingThreatDirector.shared_ignore_player
		if _threat_director != null:
			is_peaceful = _threat_director.is_debug_ignore_player()
		if is_peaceful:
			_peaceful_badge_label.text = "[F9] Peaceful Mode: ON"
			_peaceful_badge_label.add_theme_color_override("font_color", Color(0.28, 0.92, 0.56, 1.0))
		else:
			_peaceful_badge_label.text = "[F9] Peaceful Mode: OFF"
			_peaceful_badge_label.add_theme_color_override("font_color", Color(0.86, 0.36, 0.34, 0.92))

	for i: int in range(_hull_pips_boxes.size()):
		var pip: ColorRect = _hull_pips_boxes[i]
		if pip == null:
			continue
		if i < hull_integrity_pips:
			if hull_integrity_pips == 1:
				pip.color = Color(0.82, 0.18, 0.16, 1.0)
			elif hull_integrity_pips == 2:
				pip.color = Color(0.86, 0.62, 0.24, 1.0)
			else:
				pip.color = Color(0.26, 0.74, 0.62, 1.0)
		else:
			pip.color = Color(0.14, 0.16, 0.19, 0.85)

	if _hull_status_label != null:
		_hull_status_label.text = "[%d/%d]" % [hull_integrity_pips, MAX_HULL_PIPS]
		if hull_integrity_pips <= 1:
			_hull_status_label.add_theme_color_override("font_color", Color(0.92, 0.24, 0.22, 1.0))
		else:
			_hull_status_label.add_theme_color_override("font_color", Color(0.769, 0.604, 0.322, 1.0))
