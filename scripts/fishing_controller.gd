class_name FishingController
extends Node3D

# Grim Eldritch Nautical Palette Constants
const UI_VOID_BLACK: Color = Color(0.027, 0.035, 0.047, 0.97)
const UI_CORRODED_IRON: Color = Color(0.078, 0.094, 0.114, 0.95)
const UI_TARNISHED_BRASS: Color = Color(0.549, 0.427, 0.231, 1.0)
const UI_BRASS_HIGHLIGHT: Color = Color(0.769, 0.604, 0.322, 1.0)
const UI_BLOOD_CRIMSON: Color = Color(0.478, 0.110, 0.110, 1.0)
const UI_CRIMSON_BRIGHT: Color = Color(0.722, 0.157, 0.157, 1.0)
const UI_ELDRITCH_TEAL: Color = Color(0.220, 0.557, 0.478, 1.0)
const UI_BONE_PARCHMENT: Color = Color(0.847, 0.808, 0.722, 1.0)
const UI_MUTED_PARCHMENT: Color = Color(0.580, 0.545, 0.478, 1.0)

signal catch_landed(catch_data: Dictionary)
signal hold_updated

enum FishingState {
	IDLE,
	STATE_FP_READY,
	STATE_CASTING,
	STATE_WAITING_BITE,
	STATE_HOOKED,
	STATE_LANDING,
}

const SEA_ROD_GLB_PATH: String = "res://assets/models/sea_fishing_rod.glb"
const SEA_BOBBER_GLB_PATH: String = "res://assets/models/sea_bobber_lure.glb"
const CATCH_COD_GLB_PATH: String = "res://assets/models/fish/fish_cod.glb"

var state: FishingState = FishingState.IDLE
var hook_depth_m: float = 0.0
var line_tension: float = 0.0
var reel_drag_pct: float = 65.0
var cast_power: float = 0.0
var fish_distance_m: float = 0.0
var fish_angle: float = 0.0

var total_hold_kg: float = 0.0
var bank_balance: float = 0.0
var money: float = 0.0
var cable_level: int = 1
var winch_level: int = 1
var fish_hold: Array[Dictionary] = []
var species_records: Dictionary[String, Dictionary] = {}

var _boat: BoatController = null
var _visuals: Node3D = null
var _camera: OverheadCamera = null
var _sonar: SonarSystem = null

# First-Person 4-Segment Articulated Rod & Reel Viewmodel Nodes
var _rod_root: Node3D = null
var _rod_base_grip: Node3D = null
var _reel_crank_handle: Node3D = null
var _rod_mid_lower: Node3D = null
var _rod_mid_upper: Node3D = null
var _rod_tip: Node3D = null
var _rod_tip_eyelet: Node3D = null
var _rod_work_light: OmniLight3D = null

# World-Space Bobber, Line, Thrash Wake & Landed Fish Nodes
var _bobber_node: Node3D = null
var _bobber_light: OmniLight3D = null
var _line_mesh_inst: MeshInstance3D = null
var _line_imm_mesh: ImmediateMesh = null
var _line_material: StandardMaterial3D = null
var _splash_particles: GPUParticles3D = null
var _thrash_wake_particles: GPUParticles3D = null
var _abyssal_fish_light: OmniLight3D = null
var _catch_fish_holder: Node3D = null
var _catch_fish_node: Node3D = null
var _catch_inspection_light: OmniLight3D = null
var _loaded_fish_scenes: Dictionary[String, PackedScene] = {}

# Procedural Audio Players & Streams
var _sfx_player: AudioStreamPlayer3D = null
var _drag_click_player: AudioStreamPlayer3D = null
var _stream_whoosh: AudioStreamWAV = null
var _stream_splash: AudioStreamWAV = null
var _stream_nibble: AudioStreamWAV = null
var _stream_strike_alarm: AudioStreamWAV = null
var _stream_reel_click: AudioStreamWAV = null
var _stream_snap: AudioStreamWAV = null
var _stream_catch: AudioStreamWAV = null

# Casting, Waiting, Strike & Fight State Variables
var _is_charging_cast: bool = false
var _cast_in_flight: bool = false
var _cast_flight_time: float = 0.0
var _cast_flight_duration: float = 0.85
var _cast_start_world: Vector3 = Vector3.ZERO
var _cast_target_world: Vector3 = Vector3.ZERO
var _bobber_world_pos: Vector3 = Vector3.ZERO

var _jig_boost_timer: float = 0.0
var _rod_twitch_anim: float = 0.0
var _rod_pump_anim: float = 0.0
var _pump_cooldown_timer: float = 0.0

var _bite_eval_timer: float = 0.0
var _nibbles_remaining: int = 0
var _in_strike_window: bool = false
var _strike_window_timer: float = 0.0
var _nibble_dip_offset: float = 0.0

var _current_catch: Dictionary = {}
var _fish_is_surging: bool = false
var _fish_state_timer: float = 0.0
var _fish_target_angle: float = 0.0
var _fish_stamina: float = 1.0
var _current_fish_weight_kg: float = 10.0
var _current_pull_strength: float = 1.0
var _current_surge_range: Vector2 = Vector2(1.8, 3.0)
var _current_rest_range: Vector2 = Vector2(2.1, 3.4)
var _current_lateral_speed: float = 2.8
var _reel_click_cooldown: float = 0.0
var _redline_timer: float = 0.0
var _landing_timer: float = 0.0
var _landing_start_world: Vector3 = Vector3.ZERO

# First-Person HUD Overlay Nodes
var _fp_hud_layer: CanvasLayer = null
var _hud_panel: PanelContainer = null
var _hud_frame_drawer: Control = null
var _astrolabe_gauge: Control = null
var _reticle_label: Label = null
var _status_banner_label: Label = null
var _tension_bar: ProgressBar = null
var _tension_fill_style: StyleBoxFlat = null
var _tension_value_label: Label = null
var _drag_value_label: Label = null
var _telemetry_label: Label = null
var _controls_hint_label: Label = null
var _stream_dread_drone: AudioStreamWAV = null

var _rng: RandomNumberGenerator = RandomNumberGenerator.new()


func _ready() -> void:
	add_to_group("fishing_controller")
	_rng.randomize()
	_boat = get_parent() as BoatController
	if _boat != null:
		_visuals = _boat.get_node_or_null("Visuals") as Node3D

	_build_procedural_sfx()
	_setup_world_fishing_nodes()
	_setup_audio_players()
	_build_fp_hud_overlay()


func _exit_tree() -> void:
	if _bobber_node != null and is_instance_valid(_bobber_node):
		_bobber_node.queue_free()
	if _line_mesh_inst != null and is_instance_valid(_line_mesh_inst):
		_line_mesh_inst.queue_free()
	if _thrash_wake_particles != null and is_instance_valid(_thrash_wake_particles):
		_thrash_wake_particles.queue_free()
	if _catch_inspection_light != null and is_instance_valid(_catch_inspection_light):
		_catch_inspection_light.queue_free()
	if _rod_root != null and is_instance_valid(_rod_root):
		_rod_root.queue_free()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey:
		var key_event: InputEventKey = event as InputEventKey
		if key_event.pressed and not key_event.echo:
			var code: Key = key_event.physical_keycode if key_event.physical_keycode != KEY_NONE else key_event.keycode
			if code == KEY_F:
				_handle_f_key_pressed()
				return
			elif code == KEY_SPACE and state == FishingState.STATE_LANDING:
				_reset_to_fp_ready()
				return

	if state == FishingState.IDLE:
		return

	if event is InputEventMouseButton:
		var mb: InputEventMouseButton = event as InputEventMouseButton
		if mb.pressed:
			if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
				_handle_scroll_wheel(1.0)
			elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				_handle_scroll_wheel(-1.0)
			elif mb.button_index == MOUSE_BUTTON_RIGHT:
				_handle_right_click_action()
			elif mb.button_index == MOUSE_BUTTON_LEFT:
				if state == FishingState.STATE_WAITING_BITE and _in_strike_window:
					_set_hook_on_strike()


func _physics_process(delta: float) -> void:
	_resolve_scene_references()

	_rod_twitch_anim = move_toward(_rod_twitch_anim, 0.0, delta * 3.2)
	_rod_pump_anim = move_toward(_rod_pump_anim, 0.0, delta * 2.0)
	_nibble_dip_offset = move_toward(_nibble_dip_offset, 0.0, delta * 1.6)
	if _pump_cooldown_timer > 0.0:
		_pump_cooldown_timer = maxf(0.0, _pump_cooldown_timer - delta)
	if _jig_boost_timer > 0.0:
		_jig_boost_timer = maxf(0.0, _jig_boost_timer - delta)
	if _reel_click_cooldown > 0.0:
		_reel_click_cooldown = maxf(0.0, _reel_click_cooldown - delta)

	match state:
		FishingState.IDLE:
			_process_idle_state(delta)
		FishingState.STATE_FP_READY:
			_process_fp_ready_state(delta)
		FishingState.STATE_CASTING:
			_process_casting_state(delta)
		FishingState.STATE_WAITING_BITE:
			_process_waiting_bite_state(delta)
		FishingState.STATE_HOOKED:
			_process_hooked_state(delta)
		FishingState.STATE_LANDING:
			_process_landing_state(delta)

	_update_rod_viewmodel_articulation(delta)
	_update_3d_fishing_line()
	_sync_sonar_hud()
	_update_fp_hud_overlay()


func _resolve_scene_references() -> void:
	if _boat == null:
		_boat = get_parent() as BoatController
	if _visuals == null and _boat != null:
		_visuals = _boat.get_node_or_null("Visuals") as Node3D
	if _camera == null and _boat != null and _boat.get_parent() != null:
		_camera = _boat.get_parent().get_node_or_null("Camera3D") as OverheadCamera
	if _sonar == null:
		var sonar_nodes: Array[Node] = get_tree().get_nodes_in_group("sonar_system")
		if not sonar_nodes.is_empty():
			_sonar = sonar_nodes[0] as SonarSystem

	# Attach 3D rod viewmodel to Camera3D's FPViewmodelAnchor once camera is available
	if _rod_root == null and _camera != null and _camera.fp_viewmodel_anchor != null:
		_setup_fp_rod_viewmodel(_camera.fp_viewmodel_anchor)


func _handle_f_key_pressed() -> void:
	_resolve_scene_references()
	if state == FishingState.IDLE:
		if _boat != null and absf(_boat.current_speed) < 2.5:
			_enter_first_person_deck_mode()
	else:
		_exit_to_navigation_helm()


func _enter_first_person_deck_mode() -> void:
	if _boat != null:
		_boat.fishing_mode_active = true
		_boat.fishing_roll_offset = 0.0
	if _camera != null:
		_camera.fishing_camera_active = true
		_camera.reset_fp_angles()
	_reset_to_fp_ready()


func _reset_to_fp_ready() -> void:
	state = FishingState.STATE_FP_READY
	hook_depth_m = 12.0
	line_tension = 0.0
	cast_power = 0.0
	fish_distance_m = 0.0
	fish_angle = 0.0
	_is_charging_cast = false
	_cast_in_flight = false
	_in_strike_window = false
	_redline_timer = 0.0

	if _sfx_player != null:
		_sfx_player.stop()
	if _drag_click_player != null:
		_drag_click_player.stop()

	if _rod_root != null:
		_rod_root.visible = true
	if _bobber_node != null:
		_bobber_node.visible = false
	if _catch_fish_holder != null:
		_catch_fish_holder.visible = false
	if _catch_inspection_light != null:
		_catch_inspection_light.visible = false
	if _splash_particles != null:
		_splash_particles.emitting = false
	if _thrash_wake_particles != null:
		_thrash_wake_particles.emitting = false
	if _abyssal_fish_light != null:
		_abyssal_fish_light.visible = false
	if _line_imm_mesh != null:
		_line_imm_mesh.clear_surfaces()


func _exit_to_navigation_helm() -> void:
	_reset_to_fp_ready()
	state = FishingState.IDLE
	hook_depth_m = 0.0

	if _boat != null:
		_boat.fishing_mode_active = false
		_boat.fishing_roll_offset = 0.0
	if _camera != null:
		_camera.fishing_camera_active = false
	if _rod_root != null:
		_rod_root.visible = false
	if _hud_panel != null:
		_hud_panel.visible = false
	if _reticle_label != null:
		_reticle_label.visible = false


func _handle_scroll_wheel(dir: float) -> void:
	if state == FishingState.STATE_WAITING_BITE:
		var reading: Dictionary = _get_bobber_sonar_reading()
		var max_d: float = maxf(6.0, (reading.get("seabed_depth", 45.0) as float) - 0.8)
		hook_depth_m = clampf(hook_depth_m - dir * 2.5, 2.0, max_d)
	elif state == FishingState.STATE_HOOKED or state == FishingState.STATE_FP_READY:
		reel_drag_pct = clampf(reel_drag_pct + dir * 5.0, 20.0, 100.0)
		_play_one_shot_sfx(_stream_reel_click, lerpf(0.85, 1.35, reel_drag_pct / 100.0))


func _handle_right_click_action() -> void:
	if state == FishingState.STATE_WAITING_BITE:
		if _in_strike_window:
			_set_hook_on_strike()
		else:
			# Twitch / Jig Rod to attract fish (+35% bite attraction boost)
			_jig_boost_timer = 2.6
			_rod_twitch_anim = 1.0
			_nibble_dip_offset = -0.18
			_play_one_shot_sfx(_stream_nibble, 1.15)
			if _splash_particles != null and _bobber_node != null:
				_splash_particles.global_position = _bobber_node.global_position + Vector3(0.0, 0.08, 0.0)
				_splash_particles.amount_ratio = 0.45
				_splash_particles.emitting = true
	elif state == FishingState.STATE_HOOKED:
		# Pump Rod Back: pulls rod into a high power-arc (2.0s cooldown) to surge fish 2.5m closer
		if _pump_cooldown_timer <= 0.0:
			_pump_cooldown_timer = 2.0
			_rod_pump_anim = 1.0
			fish_distance_m = maxf(2.2, fish_distance_m - 2.5)
			line_tension = clampf(line_tension + 9.5, 0.0, 100.0)
			_fish_stamina = maxf(0.0, _fish_stamina - 0.08)
			if _fish_is_surging:
				# Momentarily interrupt lateral surge run
				_fish_state_timer = minf(_fish_state_timer, 0.45)
			_play_one_shot_sfx(_stream_whoosh, 0.88)


func _process_idle_state(delta: float) -> void:
	line_tension = move_toward(line_tension, 0.0, 40.0 * delta)
	if _boat != null:
		_boat.fishing_roll_offset = move_toward(_boat.fishing_roll_offset, 0.0, 2.0 * delta)


# =============================================================================
# STAGE 1: AIM & POWER CAST (STATE_FP_READY -> STATE_CASTING)
# =============================================================================
func _process_fp_ready_state(delta: float) -> void:
	var lmb_held: bool = Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)
	if lmb_held and (_camera == null or not _camera.ui_modal_open):
		state = FishingState.STATE_CASTING
		_is_charging_cast = true
		_cast_in_flight = false
		cast_power = 0.05
	else:
		cast_power = move_toward(cast_power, 0.0, delta * 2.0)


func _process_casting_state(delta: float) -> void:
	if _is_charging_cast:
		var lmb_held: bool = Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)
		if lmb_held:
			# Charge cast_power from 0.0 to 1.0 over 1.2s
			cast_power = clampf(cast_power + (delta / 1.2), 0.0, 1.0)
		else:
			# Release Left Click: whip rod forward & launch bobber along parabolic arc (10m to 42m)
			_is_charging_cast = false
			_launch_bobber_cast()
		return

	if _cast_in_flight:
		_cast_flight_time += delta
		var t: float = clampf(_cast_flight_time / maxf(0.1, _cast_flight_duration), 0.0, 1.0)
		var horiz_pos: Vector3 = _cast_start_world.lerp(_cast_target_world, t)
		var arc_height: float = sin(t * PI) * lerpf(3.2, 8.5, cast_power)
		_bobber_world_pos = Vector3(horiz_pos.x, lerpf(_cast_start_world.y, _cast_target_world.y, t) + arc_height, horiz_pos.z)

		if _bobber_node != null:
			_bobber_node.visible = true
			_bobber_node.global_position = _bobber_world_pos

		if t >= 1.0:
			_cast_in_flight = false
			_on_bobber_landed_on_water()


func _launch_bobber_cast() -> void:
	_play_one_shot_sfx(_stream_whoosh, lerpf(1.15, 0.85, cast_power))
	_rod_twitch_anim = -0.85

	var start_pos: Vector3 = _get_rod_tip_world_pos()
	var aim_dir: Vector3 = Vector3(0.0, 0.0, 1.0)
	if _camera != null:
		var cam_fwd: Vector3 = -_camera.global_transform.basis.z
		var planar: Vector3 = Vector3(cam_fwd.x, 0.0, cam_fwd.z)
		if planar.length_squared() > 0.001:
			aim_dir = planar.normalized()

	var cast_dist: float = lerpf(10.0, 42.0, cast_power)
	var time_sec: float = float(Time.get_ticks_msec()) * 0.001
	var target_xz: Vector2 = Vector2(start_pos.x + aim_dir.x * cast_dist, start_pos.z + aim_dir.z * cast_dist)
	var wave_y: float = _sample_ocean_wave_y(target_xz, time_sec)

	_cast_start_world = start_pos
	_cast_target_world = Vector3(target_xz.x, wave_y, target_xz.y)
	_cast_flight_time = 0.0
	_cast_flight_duration = lerpf(0.55, 1.05, cast_power)
	_cast_in_flight = true
	fish_distance_m = cast_dist
	fish_angle = _camera.fp_yaw_offset if _camera != null else 0.0


func _on_bobber_landed_on_water() -> void:
	state = FishingState.STATE_WAITING_BITE
	line_tension = 10.0
	_in_strike_window = false
	_strike_window_timer = 0.0
	_bite_eval_timer = 1.1
	_nibbles_remaining = _rng.randi_range(1, 2)

	var reading: Dictionary = _get_bobber_sonar_reading()
	var school_min: float = reading.get("school_depth_min", 14.0) as float
	var school_max: float = reading.get("school_depth_max", 24.0) as float
	var seabed_d: float = reading.get("seabed_depth", 42.0) as float
	hook_depth_m = clampf(0.5 * (school_min + school_max), 4.0, maxf(6.0, seabed_d - 1.5))

	_play_one_shot_sfx(_stream_splash, 1.0)
	if _splash_particles != null:
		_splash_particles.global_position = _bobber_world_pos + Vector3(0.0, 0.08, 0.0)
		_splash_particles.amount_ratio = 0.85
		_splash_particles.emitting = true


# =============================================================================
# STAGE 2: LURE FLOATING, DEPTH ADJUSTMENT & BITE WAITING (STATE_WAITING_BITE)
# =============================================================================
func _process_waiting_bite_state(delta: float) -> void:
	var time_sec: float = float(Time.get_ticks_msec()) * 0.001
	var bobber_xz: Vector2 = Vector2(_bobber_world_pos.x, _bobber_world_pos.z)
	var wave_y: float = _sample_ocean_wave_y(bobber_xz, time_sec)

	var strike_submerge: float = -0.58 if _in_strike_window else _nibble_dip_offset
	_bobber_world_pos.y = wave_y + strike_submerge
	if _bobber_node != null:
		_bobber_node.visible = true
		_bobber_node.global_position = _bobber_world_pos
		_bobber_node.rotation = Vector3(
			sin(time_sec * 3.1) * 0.14,
			0.0,
			cos(time_sec * 2.7) * 0.14
		)

	if _boat != null:
		fish_distance_m = Vector2(_boat.global_position.x, _boat.global_position.z).distance_to(bobber_xz)

	# Adjust hook sink depth beneath the bobber with W / S
	var reading: Dictionary = _get_bobber_sonar_reading()
	var max_seabed: float = maxf(6.0, (reading.get("seabed_depth", 45.0) as float) - 0.8)
	if Input.is_key_pressed(KEY_S) or Input.is_action_pressed("move_backward"):
		hook_depth_m = clampf(hook_depth_m + 12.0 * delta, 2.0, max_seabed)
	elif Input.is_key_pressed(KEY_W) or Input.is_action_pressed("move_forward"):
		hook_depth_m = clampf(hook_depth_m - 12.0 * delta, 2.0, max_seabed)

	# Allow Left Click reeling while waiting (when not in strike window) to retrieve the bobber
	if not _in_strike_window and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) and (_camera == null or not _camera.ui_modal_open):
		if _boat != null:
			var to_boat: Vector2 = (Vector2(_boat.global_position.x, _boat.global_position.z) - bobber_xz)
			if to_boat.length() > 3.0:
				var pull_step: Vector2 = to_boat.normalized() * 8.5 * delta
				_bobber_world_pos.x += pull_step.x
				_bobber_world_pos.z += pull_step.y
				if _reel_crank_handle != null:
					_reel_crank_handle.rotation.x += 12.0 * delta
			else:
				_reset_to_fp_ready()
				return

	# Handle active 1.5s STRIKE Window countdown
	if _in_strike_window:
		_strike_window_timer -= delta
		line_tension = lerpf(line_tension, 34.0, 8.0 * delta)
		if _splash_particles != null:
			_splash_particles.global_position = _bobber_world_pos + Vector3(0.0, 0.1, 0.0)
			_splash_particles.amount_ratio = 0.9
			_splash_particles.emitting = true
		if Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) or Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
			_set_hook_on_strike()
			return
		if _strike_window_timer <= 0.0:
			# Missed strike window — reset for next nibble cycle
			_in_strike_window = false
			_nibbles_remaining = _rng.randi_range(1, 2)
			_bite_eval_timer = 1.4
			line_tension = 10.0
			if _splash_particles != null:
				_splash_particles.emitting = false
		return

	# Evaluate Sonar-driven Nibbles -> Strike Window
	_bite_eval_timer -= delta
	if _bite_eval_timer <= 0.0:
		_bite_eval_timer = 1.15
		_evaluate_nibble_or_strike(reading)


func _evaluate_nibble_or_strike(reading: Dictionary) -> void:
	var biomass: float = reading.get("biomass_density", 0.12) as float
	var school_min: float = reading.get("school_depth_min", 15.0) as float
	var school_max: float = reading.get("school_depth_max", 25.0) as float
	var in_school_band: bool = (hook_depth_m >= school_min - 3.5) and (hook_depth_m <= school_max + 3.5)

	var base_chance: float = 0.14
	if in_school_band:
		base_chance = lerpf(0.42, 0.78, clampf(biomass, 0.0, 1.0))
	else:
		base_chance = lerpf(0.15, 0.35, clampf(biomass, 0.0, 1.0))

	if _jig_boost_timer > 0.0:
		base_chance = clampf(base_chance + 0.35, 0.0, 0.96)

	if _rng.randf() <= base_chance:
		if _nibbles_remaining > 0:
			# Trigger a subtle Nibble: bobber dips 0.2m, small water ripple, slight rod-tip twitch
			_nibbles_remaining -= 1
			_nibble_dip_offset = -0.22
			_rod_twitch_anim = 0.45
			_play_one_shot_sfx(_stream_nibble, _rng.randf_range(0.92, 1.12))
			if _splash_particles != null:
				_splash_particles.global_position = _bobber_world_pos + Vector3(0.0, 0.06, 0.0)
				_splash_particles.amount_ratio = 0.35
				_splash_particles.emitting = true
		else:
			# Trigger the 1.5s STRIKE Window!
			_in_strike_window = true
			_strike_window_timer = 1.5
			_rod_twitch_anim = 0.95
			_play_one_shot_sfx(_stream_strike_alarm, 1.0)


func _set_hook_on_strike() -> void:
	_in_strike_window = false
	var reading: Dictionary = _get_bobber_sonar_reading()
	var seabed_depth: float = reading.get("seabed_depth", 45.0) as float
	var biomass: float = reading.get("biomass_density", 0.35) as float
	var near_rock: bool = reading.get("near_rock_hazard", false) as bool
	var near_arch: bool = reading.get("near_arch_monolith", false) as bool
	var near_poi: bool = reading.get("near_poi_hotspot", false) as bool
	if not near_poi and _sonar != null:
		var boat_reading: Dictionary = _sonar.get_last_reading()
		near_poi = (boat_reading.get("near_poi_hotspot", false) as bool) or (boat_reading.get("near_poi_discovery", false) as bool)

	_current_catch = FishCatalog.roll_species_for_hook(
		hook_depth_m,
		seabed_depth,
		near_rock,
		biomass,
		near_arch,
		near_poi
	)

	_current_fish_weight_kg = _current_catch.get("weight_kg", 10.0) as float
	_current_pull_strength = _current_catch.get("pull_strength", 1.0) as float
	_current_surge_range = _current_catch.get("surge_duration_range", Vector2(1.8, 3.0)) as Vector2
	_current_rest_range = _current_catch.get("rest_duration_range", Vector2(2.1, 3.4)) as Vector2
	_current_lateral_speed = _current_catch.get("lateral_thrash_speed", 2.8) as float

	state = FishingState.STATE_HOOKED
	_fish_is_surging = true
	_fish_stamina = 1.0
	_fish_state_timer = _rng.randf_range(_current_surge_range.x, _current_surge_range.y)

	# Compute initial fish distance & angle from the boat's stern
	if _boat != null:
		var rel_world: Vector3 = _bobber_world_pos - _boat.global_position
		var local_rel: Vector3 = _boat.global_transform.basis.inverse() * rel_world
		fish_distance_m = clampf(Vector2(local_rel.x, local_rel.z).length(), 10.0, 44.0)
		fish_angle = clampf(atan2(local_rel.x, maxf(1.0, local_rel.z)), deg_to_rad(-85.0), deg_to_rad(85.0))
	else:
		fish_distance_m = maxf(14.0, fish_distance_m)
		fish_angle = 0.0

	var dir_sign: float = 1.0 if _rng.randf() > 0.5 else -1.0
	_fish_target_angle = clampf(fish_angle + dir_sign * deg_to_rad(38.0), deg_to_rad(-80.0), deg_to_rad(80.0))

	line_tension = clampf(38.0 + _current_pull_strength * 8.0, 35.0, 58.0)
	_redline_timer = 0.0
	_rod_pump_anim = 0.75

	if _boat != null:
		_boat.fishing_pitch_impulse = -0.055 * _current_pull_strength
	if _camera != null:
		_camera.camera_shake_intensity = clampf(0.36 * _current_pull_strength, 0.25, 0.75)

	# Activate bioluminescent water glow if an Abyssal Trench species is hooked
	var tier_name: String = _current_catch.get("tier_name", FishCatalog.TIER_COASTAL) as String
	if _abyssal_fish_light != null:
		_abyssal_fish_light.visible = (tier_name == FishCatalog.TIER_ABYSSAL)

	_play_one_shot_sfx(_stream_splash, 0.85)


# =============================================================================
# STAGE 3: CLASSIC ROD-BENDING & REEL-IN FIGHT (STATE_HOOKED)
# =============================================================================
func _process_hooked_state(delta: float) -> void:
	# 1. Update Fish AI State: SURGING / RUN vs TIRED / GLIDING
	_fish_state_timer -= delta
	if _fish_state_timer <= 0.0:
		_fish_is_surging = not _fish_is_surging
		if _fish_is_surging:
			var stamina_scale: float = lerpf(0.65, 1.0, _fish_stamina)
			_fish_state_timer = _rng.randf_range(_current_surge_range.x, _current_surge_range.y) * stamina_scale
			var side_sign: float = -1.0 if fish_angle >= 0.0 else 1.0
			_fish_target_angle = clampf(side_sign * _rng.randf_range(deg_to_rad(28.0), deg_to_rad(75.0)), deg_to_rad(-82.0), deg_to_rad(82.0))
			if _camera != null and _current_pull_strength >= 1.2:
				_camera.camera_shake_intensity = maxf(_camera.camera_shake_intensity, 0.22 * _current_pull_strength)
		else:
			_fish_state_timer = _rng.randf_range(_current_rest_range.x, _current_rest_range.y)
			_fish_target_angle = fish_angle + _rng.randf_range(deg_to_rad(-18.0), deg_to_rad(18.0))

	# 2. Lateral Fish Swimming & Player Rod Counter-Angling (Mouse Look Left/Right)
	var angular_rate: float = (_current_lateral_speed * 0.14) if _fish_is_surging else (_current_lateral_speed * 0.05)
	var prev_angle: float = fish_angle
	fish_angle = move_toward(fish_angle, _fish_target_angle, angular_rate * delta)
	var swim_dir_sign: float = signf(_fish_target_angle - prev_angle)

	# Rod Angling: pointing camera/rod tip opposite the fish's lateral swim direction
	# applies counter-pressure that drains stamina faster and cuts tension buildup by 35%
	var cam_yaw: float = _camera.fp_yaw_offset if _camera != null else 0.0
	var is_counter_angling: bool = false
	if absf(swim_dir_sign) > 0.01:
		is_counter_angling = (signf(cam_yaw) == -swim_dir_sign and absf(cam_yaw) > deg_to_rad(8.0))
	else:
		is_counter_angling = absf(cam_yaw - fish_angle) < deg_to_rad(22.0)

	var tension_angle_mult: float = 0.65 if is_counter_angling else 1.0
	var stamina_drain_rate: float = 0.055 if is_counter_angling else 0.025
	_fish_stamina = maxf(0.10, _fish_stamina - stamina_drain_rate * delta)

	# 3. Reel In (Hold Left Click) vs Reel Drag Setting (Scroll Wheel 20%..100%)
	var lmb_reeling: bool = Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) and (_camera == null or not _camera.ui_modal_open)
	var drag_norm: float = clampf(reel_drag_pct / 100.0, 0.20, 1.0)
	var winch_bonus: float = 1.0 + float(winch_level - 1) * 0.15
	var cable_resist: float = 1.0 / (1.0 + float(cable_level - 1) * 0.15)

	if lmb_reeling:
		# Spin ReelCrankHandle & play mechanical reel clicks
		if _reel_crank_handle != null:
			var crank_speed: float = 15.0 if not _fish_is_surging else 7.5
			_reel_crank_handle.rotation.x += crank_speed * delta
		if _reel_click_cooldown <= 0.0:
			_reel_click_cooldown = 0.09 if not _fish_is_surging else 0.14
			if _drag_click_player != null and _stream_reel_click != null:
				_drag_click_player.stream = _stream_reel_click
				_drag_click_player.pitch_scale = lerpf(0.92, 1.28, line_tension / 100.0)
				_drag_click_player.play()

		if _fish_is_surging:
			# Reeling while surging spikes tension rapidly and pulls slowly
			var surge_pull_in: float = (1.6 * drag_norm * winch_bonus) / clampf(_current_pull_strength, 0.75, 1.65)
			fish_distance_m = maxf(2.0, fish_distance_m - surge_pull_in * delta)
			var surge_tension_rate: float = 34.0 * _current_pull_strength * (0.55 + 0.55 * drag_norm) * tension_angle_mult * cable_resist
			line_tension = clampf(line_tension + surge_tension_rate * delta, 0.0, 100.0)
		else:
			# Reeling while tired/gliding hauls the fish in smoothly
			var glide_pull_in: float = (6.8 * (0.45 + 0.55 * drag_norm) * winch_bonus) / clampf(_current_pull_strength, 0.75, 1.45)
			fish_distance_m = maxf(2.0, fish_distance_m - glide_pull_in * delta)
			var glide_tension_rate: float = 9.5 * _current_pull_strength * drag_norm * tension_angle_mult * cable_resist
			line_tension = clampf(line_tension + glide_tension_rate * delta, 0.0, 100.0)
	else:
		# Not reeling: fish pulls against the reel drag setting
		if _fish_is_surging:
			# Lower drag lets the surging fish strip a little line out safely without snapping
			var strip_factor: float = maxf(0.0, (1.12 - drag_norm) * _current_pull_strength)
			fish_distance_m = minf(48.0, fish_distance_m + strip_factor * 3.2 * delta)
			var drag_tension_delta: float = (14.5 * drag_norm * _current_pull_strength * tension_angle_mult * cable_resist) - (16.0 * (1.0 - drag_norm))
			line_tension = clampf(line_tension + drag_tension_delta * delta, 12.0, 100.0)
			if strip_factor > 0.25 and _reel_click_cooldown <= 0.0:
				_reel_click_cooldown = 0.08
				if _drag_click_player != null and _stream_reel_click != null:
					_drag_click_player.stream = _stream_reel_click
					_drag_click_player.pitch_scale = 1.24
					_drag_click_player.play()
		else:
			line_tension = clampf(line_tension - 22.0 * delta, 14.0, 100.0)

	# 4. Update 3D Fish World Position, Bobber & Water Thrash Wake
	var time_sec: float = float(Time.get_ticks_msec()) * 0.001
	if _boat != null:
		var local_fish_dir: Vector3 = Vector3(sin(fish_angle), 0.0, cos(fish_angle)).normalized()
		var world_fish_dir: Vector3 = (_boat.global_transform.basis * local_fish_dir).normalized()
		var stern_origin: Vector3 = _boat.global_position + (_boat.global_transform.basis * Vector3(0.0, 0.0, 2.2))
		var fish_xz: Vector2 = Vector2(
			stern_origin.x + world_fish_dir.x * fish_distance_m,
			stern_origin.z + world_fish_dir.z * fish_distance_m
		)
		var wave_y: float = _sample_ocean_wave_y(fish_xz, time_sec)
		_bobber_world_pos = Vector3(fish_xz.x, wave_y - (0.35 if _fish_is_surging else 0.12), fish_xz.y)

		var target_heel: float = clampf(-sin(fish_angle) * 0.045 * _current_pull_strength, -0.14, 0.14)
		_boat.fishing_roll_offset = lerpf(_boat.fishing_roll_offset, target_heel, clampf(4.0 * delta, 0.0, 1.0))

	if _bobber_node != null:
		_bobber_node.visible = true
		_bobber_node.global_position = _bobber_world_pos
	if _thrash_wake_particles != null:
		_thrash_wake_particles.global_position = _bobber_world_pos + Vector3(0.0, 0.10, 0.0)
		_thrash_wake_particles.amount_ratio = 1.0 if _fish_is_surging else 0.45
		_thrash_wake_particles.emitting = true
	if _abyssal_fish_light != null and _abyssal_fish_light.visible:
		_abyssal_fish_light.global_position = _bobber_world_pos + Vector3(0.0, 0.35, 0.0)

	# 5. High-Tension Warning & Redline Snap Check
	if line_tension > 78.0:
		var danger: float = (line_tension - 78.0) / 22.0
		if _camera != null:
			_camera.camera_shake_intensity = maxf(_camera.camera_shake_intensity, 0.12 + danger * 0.28)

	if line_tension >= 99.5:
		_redline_timer += delta
		if _redline_timer > 0.85:
			_trigger_line_snap()
			return
	else:
		_redline_timer = maxf(0.0, _redline_timer - delta * 1.5)

	# 6. Check for Landing the Fish Beside the Boat (fish_distance_m <= 2.5m)
	if fish_distance_m <= 2.5:
		_trigger_land_catch()


func _trigger_line_snap() -> void:
	_play_one_shot_sfx(_stream_snap, 1.0)
	if _camera != null:
		_camera.camera_shake_intensity = 0.80
	if _sonar != null:
		var lost_name: String = (_current_catch.get("display_name", "SPECIMEN") as String).to_upper()
		_sonar.show_catch_banner("FISHING LINE SNAPPED! %s BROKE FREE!" % lost_name, 3.2)
	_reset_to_fp_ready()


# =============================================================================
# STAGE 4: LANDING THE FISH BESIDE THE BOAT (fish_distance_m <= 2.5m)
# =============================================================================
func _trigger_land_catch() -> void:
	state = FishingState.STATE_LANDING
	hook_depth_m = 0.0
	line_tension = 15.0
	_landing_timer = 3.8
	_landing_start_world = _bobber_world_pos

	var species_id: String = _current_catch.get("id", "cod") as String
	var species_name: String = _current_catch.get("display_name", "Atlantic Cod") as String
	var tier_name: String = _current_catch.get("tier_name", FishCatalog.TIER_COASTAL) as String
	var glb_path: String = _current_catch.get("glb_path", CATCH_COD_GLB_PATH) as String
	var min_w: float = _current_catch.get("min_weight_kg", 2.0) as float
	var max_w: float = _current_catch.get("max_weight_kg", 20.0) as float
	var caught_depth: float = _current_catch.get("depth_m", 18.0) as float
	var catch_val: float = _current_catch.get("value", 25.0) as float

	total_hold_kg = snappedf(total_hold_kg + _current_fish_weight_kg, 0.1)

	var hold_entry: Dictionary = {
		"id": species_id,
		"name": species_name,
		"tier_name": tier_name,
		"weight_kg": _current_fish_weight_kg,
		"depth_m": caught_depth,
		"value": catch_val,
	}
	fish_hold.append(hold_entry)
	_record_species_discovery(species_id, _current_fish_weight_kg, caught_depth)

	_play_one_shot_sfx(_stream_splash, 1.1)
	_play_one_shot_sfx(_stream_catch, 1.0)

	if _thrash_wake_particles != null:
		_thrash_wake_particles.emitting = false
	if _abyssal_fish_light != null:
		_abyssal_fish_light.visible = false
	if _bobber_node != null:
		_bobber_node.visible = false

	_hoist_species_glb_model(glb_path, _current_fish_weight_kg, min_w, max_w)

	if _sonar != null:
		var lore_text: String = _current_catch.get("lore", "Dredged from the cold black swells.") as String
		var banner_text: String = "SPECIMEN DREDGED: %.1f kg %s [%s] ($%.2f)\n\"%s\"" % [
			_current_fish_weight_kg,
			species_name.to_upper(),
			tier_name.to_upper(),
			catch_val,
			lore_text,
		]
		_sonar.show_catch_banner(banner_text, 4.4)

	catch_landed.emit(hold_entry)
	hold_updated.emit()


func _process_landing_state(delta: float) -> void:
	_landing_timer -= delta
	line_tension = move_toward(line_tension, 8.0, 25.0 * delta)
	if _boat != null:
		_boat.fishing_roll_offset = move_toward(_boat.fishing_roll_offset, 0.0, 2.5 * delta)

	# Hoist the caught 3D fish model ~1.6m directly in front of the player's first-person view,
	# illuminated by a dedicated warm catch-inspection rim/key light while slowly rotating & swaying
	if _catch_fish_holder != null and _catch_fish_holder.visible and _camera != null:
		var progress: float = clampf(1.0 - (_landing_timer / 3.8), 0.0, 1.0)
		var lift_t: float = clampf(progress / 0.28, 0.0, 1.0)
		var smooth_lift: float = 1.0 - pow(1.0 - lift_t, 3.0)
		var cam_forward: Vector3 = -_camera.global_transform.basis.z
		var cam_right: Vector3 = _camera.global_transform.basis.x
		var t_sec: float = float(Time.get_ticks_msec()) * 0.001
		var sway_offset: Vector3 = Vector3(sin(t_sec * 1.9) * 0.04, 0.26 + sin(t_sec * 2.7) * 0.03, 0.0)
		var display_world: Vector3 = _camera.global_position + (cam_forward * 1.60) + sway_offset
		_catch_fish_holder.global_position = _landing_start_world.lerp(display_world, smooth_lift)

		_catch_fish_holder.rotation = Vector3(
			sin(t_sec * 2.2) * 0.07,
			t_sec * 1.15,
			sin(t_sec * 2.9) * 0.09
		)
		_bobber_world_pos = _catch_fish_holder.global_position

		if _catch_inspection_light != null:
			_catch_inspection_light.visible = true
			_catch_inspection_light.global_position = (
				_catch_fish_holder.global_position
				- (cam_forward * 0.58)
				+ (cam_right * 0.34)
				+ Vector3(0.0, -0.18, 0.0)
			)

	if _landing_timer <= 0.0:
		_reset_to_fp_ready()


# =============================================================================
# 4-SEGMENT ARTICULATED 3D ROD BENDING & LINE RENDERING
# =============================================================================
func _update_rod_viewmodel_articulation(delta: float) -> void:
	if _rod_root == null or not _rod_root.visible:
		return

	var base_pitch: float = deg_to_rad(14.0)
	var base_yaw: float = deg_to_rad(-8.0)
	var bend_down: float = 0.0
	var bend_side: float = 0.0

	if state == FishingState.STATE_CASTING and _is_charging_cast:
		# Draw rod backward while holding Left Click to charge cast_power
		base_pitch += deg_to_rad(38.0) * cast_power
		bend_down = -deg_to_rad(8.0) * cast_power
	elif state == FishingState.STATE_WAITING_BITE:
		var t_norm: float = clampf(line_tension / 100.0, 0.0, 1.0)
		bend_down = -deg_to_rad(7.0) * t_norm - deg_to_rad(14.0) * _rod_twitch_anim
		if _in_strike_window:
			var t_sec: float = float(Time.get_ticks_msec()) * 0.001
			bend_down -= deg_to_rad(16.0 + sin(t_sec * 34.0) * 6.0)
	elif state == FishingState.STATE_HOOKED:
		var tension_norm: float = clampf(line_tension / 100.0, 0.0, 1.0)
		var jitter: float = 0.0
		if _fish_is_surging or line_tension > 72.0:
			var t_sec: float = float(Time.get_ticks_msec()) * 0.001
			jitter = sin(t_sec * 42.0) * deg_to_rad(2.8) * tension_norm

		# Bend rod progressively downward & sideways toward the fish's world position
		bend_down = -deg_to_rad(26.0) * tension_norm + jitter
		if _camera != null:
			var rel_fish: Vector3 = _camera.global_transform.basis.inverse() * (_bobber_world_pos - _camera.global_position)
			var horiz_off: float = clampf(atan2(rel_fish.x, maxf(0.5, -rel_fish.z)), -0.85, 0.85)
			bend_side = -horiz_off * deg_to_rad(22.0) * (0.35 + 0.65 * tension_norm)

		# Pumping the rod pulls the base grip high into a power arc
		base_pitch += deg_to_rad(26.0) * _rod_pump_anim
	else:
		base_pitch += deg_to_rad(18.0) * _rod_twitch_anim

	var smooth_w: float = clampf(14.0 * delta, 0.0, 1.0)
	if _rod_base_grip != null:
		_rod_base_grip.rotation.x = lerpf(_rod_base_grip.rotation.x, base_pitch, smooth_w)
		_rod_base_grip.rotation.y = lerpf(_rod_base_grip.rotation.y, base_yaw + bend_side * 0.25, smooth_w)

	if _rod_mid_lower != null:
		_rod_mid_lower.rotation.x = lerpf(_rod_mid_lower.rotation.x, bend_down * 0.45, smooth_w)
		_rod_mid_lower.rotation.y = lerpf(_rod_mid_lower.rotation.y, bend_side * 0.45, smooth_w)

	if _rod_mid_upper != null:
		_rod_mid_upper.rotation.x = lerpf(_rod_mid_upper.rotation.x, bend_down * 0.85, smooth_w)
		_rod_mid_upper.rotation.y = lerpf(_rod_mid_upper.rotation.y, bend_side * 0.75, smooth_w)

	if _rod_tip != null:
		_rod_tip.rotation.x = lerpf(_rod_tip.rotation.x, bend_down * 1.25, smooth_w)
		_rod_tip.rotation.y = lerpf(_rod_tip.rotation.y, bend_side * 1.05, smooth_w)


func _get_rod_tip_world_pos() -> Vector3:
	if _rod_tip_eyelet != null and is_instance_valid(_rod_tip_eyelet):
		return _rod_tip_eyelet.global_position
	if _rod_tip != null and is_instance_valid(_rod_tip):
		return _rod_tip.global_position
	if _camera != null:
		return _camera.global_position + (_camera.global_transform.basis * Vector3(0.35, -0.10, -1.35))
	return global_position


func _update_3d_fishing_line() -> void:
	if _line_imm_mesh == null:
		return

	_line_imm_mesh.clear_surfaces()
	if state == FishingState.IDLE or state == FishingState.STATE_FP_READY or (state == FishingState.STATE_CASTING and _is_charging_cast):
		return

	var tip_world: Vector3 = _get_rod_tip_world_pos()
	var end_world: Vector3 = _bobber_world_pos

	_line_imm_mesh.surface_begin(Mesh.PRIMITIVE_TRIANGLES, _line_material)
	var segments: int = 12
	var sag_max: float = 0.45
	if state == FishingState.STATE_HOOKED:
		sag_max = lerpf(0.32, 0.01, clampf(line_tension / 85.0, 0.0, 1.0))
	elif state == FishingState.STATE_CASTING:
		sag_max = 0.18

	var prev_pt: Vector3 = tip_world
	for i: int in range(1, segments + 1):
		var frac: float = float(i) / float(segments)
		var pt: Vector3 = tip_world.lerp(end_world, frac)
		pt.y -= sin(frac * PI) * sag_max
		_append_line_ribbon_segment(prev_pt, pt, 0.0045)
		prev_pt = pt

	# In WAITING_BITE, also draw the underwater leader descending from the bobber toward hook_depth_m
	if state == FishingState.STATE_WAITING_BITE:
		var sub_end: Vector3 = end_world - Vector3(0.0, minf(hook_depth_m, 14.0), 0.0)
		_append_line_ribbon_segment(end_world, sub_end, 0.0038)

	_line_imm_mesh.surface_end()


func _append_line_ribbon_segment(p0: Vector3, p1: Vector3, radius: float) -> void:
	var dir: Vector3 = p1 - p0
	if dir.length_squared() < 0.00001:
		return
	var r_x: Vector3 = Vector3(radius, 0.0, 0.0)
	var r_y: Vector3 = Vector3(0.0, radius, 0.0)

	_line_imm_mesh.surface_set_normal(Vector3(0.0, 1.0, 0.0))
	_line_imm_mesh.surface_add_vertex(p0 - r_x)
	_line_imm_mesh.surface_add_vertex(p0 + r_x)
	_line_imm_mesh.surface_add_vertex(p1 + r_x)
	_line_imm_mesh.surface_add_vertex(p0 - r_x)
	_line_imm_mesh.surface_add_vertex(p1 + r_x)
	_line_imm_mesh.surface_add_vertex(p1 - r_x)

	_line_imm_mesh.surface_set_normal(Vector3(1.0, 0.0, 0.0))
	_line_imm_mesh.surface_add_vertex(p0 - r_y)
	_line_imm_mesh.surface_add_vertex(p0 + r_y)
	_line_imm_mesh.surface_add_vertex(p1 + r_y)
	_line_imm_mesh.surface_add_vertex(p0 - r_y)
	_line_imm_mesh.surface_add_vertex(p1 + r_y)
	_line_imm_mesh.surface_add_vertex(p1 - r_y)


# =============================================================================
# SONAR & ECONOMY HELPERS
# =============================================================================
func _sample_ocean_wave_y(pos_xz: Vector2, time_sec: float) -> float:
	if _boat != null:
		return _boat.get_wave_height_at(pos_xz, time_sec)
	return 0.0


func _get_bobber_sonar_reading() -> Dictionary:
	if _sonar != null:
		var now_sec: float = float(Time.get_ticks_msec()) * 0.001
		var query_pos: Vector3 = _bobber_world_pos
		if state == FishingState.STATE_FP_READY and _boat != null:
			query_pos = _boat.global_position
		return _sonar.get_sonar_reading_at(query_pos, now_sec)
	return {
		"seabed_depth": 45.0,
		"biomass_density": 0.35,
		"school_depth_min": 16.0,
		"school_depth_max": 26.0,
		"activity_tier": "SCATTERED",
		"near_rock_hazard": false,
		"near_arch_monolith": false,
	}


func _sync_sonar_hud() -> void:
	if _sonar == null:
		return
	_sonar.hook_active = (state == FishingState.STATE_WAITING_BITE or state == FishingState.STATE_HOOKED)
	_sonar.hook_depth_m = hook_depth_m
	_sonar.is_fish_hooked = (state == FishingState.STATE_HOOKED)
	_sonar.line_tension_pct = line_tension


func _record_species_discovery(species_id: String, weight_kg: float, depth_m: float) -> void:
	if not species_records.has(species_id):
		species_records[species_id] = {
			"discovered": true,
			"count": 1,
			"max_weight_kg": weight_kg,
			"best_depth_m": depth_m,
		}
	else:
		var rec: Dictionary = species_records[species_id]
		var prev_count: int = rec.get("count", 0) as int
		var prev_max_w: float = rec.get("max_weight_kg", 0.0) as float
		rec["discovered"] = true
		rec["count"] = prev_count + 1
		if weight_kg > prev_max_w:
			rec["max_weight_kg"] = weight_kg
			rec["best_depth_m"] = depth_m
		species_records[species_id] = rec


func _hoist_species_glb_model(glb_path: String, weight_kg: float, min_w: float, max_w: float) -> void:
	if _catch_fish_holder == null:
		return

	for child: Node in _catch_fish_holder.get_children():
		child.queue_free()
	_catch_fish_node = null

	var scene_to_spawn: PackedScene = _loaded_fish_scenes.get(glb_path, null) as PackedScene
	if scene_to_spawn == null and ResourceLoader.exists(glb_path):
		scene_to_spawn = load(glb_path) as PackedScene
		if scene_to_spawn != null:
			_loaded_fish_scenes[glb_path] = scene_to_spawn
	if scene_to_spawn == null and ResourceLoader.exists(CATCH_COD_GLB_PATH):
		scene_to_spawn = load(CATCH_COD_GLB_PATH) as PackedScene

	if scene_to_spawn != null:
		_catch_fish_node = scene_to_spawn.instantiate() as Node3D
		if _catch_fish_node != null:
			_configure_wet_clearcoat_fish_materials(_catch_fish_node)
			_catch_fish_holder.add_child(_catch_fish_node)

	var weight_span: float = maxf(0.1, max_w - min_w)
	var weight_norm: float = clampf((weight_kg - min_w) / weight_span, 0.0, 1.0)
	var fish_scale: float = lerpf(0.75, 1.35, weight_norm)
	_catch_fish_holder.scale = Vector3(fish_scale, fish_scale, fish_scale)
	_catch_fish_holder.global_position = _landing_start_world
	_catch_fish_holder.visible = true
	if _catch_inspection_light != null:
		_catch_inspection_light.visible = true


func _configure_wet_clearcoat_fish_materials(root_node: Node) -> void:
	if root_node is MeshInstance3D:
		var m_inst: MeshInstance3D = root_node as MeshInstance3D
		if m_inst.mesh != null:
			var surf_count: int = m_inst.mesh.get_surface_count()
			for s_idx: int in range(surf_count):
				var base_mat: Material = m_inst.get_active_material(s_idx)
				if base_mat is StandardMaterial3D:
					var std_mat: StandardMaterial3D = (base_mat as StandardMaterial3D).duplicate() as StandardMaterial3D
					if not std_mat.resource_name.ends_with("EyeCorneaLens"):
						std_mat.vertex_color_use_as_albedo = true
					std_mat.roughness = minf(std_mat.roughness, 0.14)
					std_mat.metallic_specular = 0.88
					std_mat.clearcoat_enabled = true
					std_mat.clearcoat = 1.0
					std_mat.clearcoat_roughness = 0.03
					std_mat.rim_enabled = true
					std_mat.rim = 0.65
					std_mat.rim_tint = 0.35
					m_inst.set_surface_override_material(s_idx, std_mat)
	for child: Node in root_node.get_children():
		_configure_wet_clearcoat_fish_materials(child)


func _configure_stylized_viewmodel_materials(root_node: Node) -> void:
	if root_node is MeshInstance3D:
		var m_inst: MeshInstance3D = root_node as MeshInstance3D
		if m_inst.mesh != null:
			var surf_count: int = m_inst.mesh.get_surface_count()
			for s_idx: int in range(surf_count):
				var base_mat: Material = m_inst.get_active_material(s_idx)
				if base_mat is StandardMaterial3D:
					var std_mat: StandardMaterial3D = (base_mat as StandardMaterial3D).duplicate() as StandardMaterial3D
					std_mat.vertex_color_use_as_albedo = true
					std_mat.rim_enabled = true
					std_mat.rim = 0.65
					std_mat.rim_tint = 0.35
					m_inst.set_surface_override_material(s_idx, std_mat)
	for child: Node in root_node.get_children():
		_configure_stylized_viewmodel_materials(child)


func sell_all_hold() -> float:
	var total_earned: float = 0.0
	for item: Dictionary in fish_hold:
		total_earned += item.get("value", 0.0) as float
	total_earned = snappedf(total_earned, 0.5)
	bank_balance = snappedf(bank_balance + total_earned, 0.5)
	money = bank_balance
	fish_hold.clear()
	total_hold_kg = 0.0
	hold_updated.emit()
	return total_earned


func sell_hold_index(idx: int) -> float:
	if idx < 0 or idx >= fish_hold.size():
		return 0.0
	var item: Dictionary = fish_hold[idx]
	var earned: float = snappedf(item.get("value", 0.0) as float, 0.5)
	var w_kg: float = item.get("weight_kg", 0.0) as float
	bank_balance = snappedf(bank_balance + earned, 0.5)
	money = bank_balance
	fish_hold.remove_at(idx)
	total_hold_kg = maxf(0.0, snappedf(total_hold_kg - w_kg, 0.1))
	hold_updated.emit()
	return earned


# =============================================================================
# 3D NODE & HUD OVERLAY SETUP
# =============================================================================
func _setup_fp_rod_viewmodel(anchor: Node3D) -> void:
	if not ResourceLoader.exists(SEA_ROD_GLB_PATH):
		return
	var rod_scene: PackedScene = load(SEA_ROD_GLB_PATH) as PackedScene
	if rod_scene == null:
		return

	_rod_root = rod_scene.instantiate() as Node3D
	_rod_root.name = "SeaFishingRodViewmodel"
	_rod_root.visible = (state != FishingState.IDLE)
	_configure_stylized_viewmodel_materials(_rod_root)
	anchor.add_child(_rod_root)

	_rod_base_grip = _rod_root.find_child("RodBaseGrip", true, false) as Node3D
	_reel_crank_handle = _rod_root.find_child("ReelCrankHandle", true, false) as Node3D
	_rod_mid_lower = _rod_root.find_child("RodMidLower", true, false) as Node3D
	_rod_mid_upper = _rod_root.find_child("RodMidUpper", true, false) as Node3D
	_rod_tip = _rod_root.find_child("RodTip", true, false) as Node3D
	_rod_tip_eyelet = _rod_root.find_child("RodTipEyelet", true, false) as Node3D

	# Subtle warm fill light on the first-person rod & brass reel
	_rod_work_light = OmniLight3D.new()
	_rod_work_light.name = "FPRodFillLight"
	_rod_work_light.position = Vector3(-0.24, 0.28, 0.12)
	_rod_work_light.light_color = Color(1.0, 0.82, 0.52, 1.0)
	_rod_work_light.light_energy = 0.42
	_rod_work_light.light_volumetric_fog_energy = 0.0
	_rod_work_light.omni_range = 2.4
	_rod_work_light.shadow_enabled = false
	_rod_root.add_child(_rod_work_light)


func _setup_world_fishing_nodes() -> void:
	# 1. Glowing Nautical Bobber & Lure (top-level in world space)
	if ResourceLoader.exists(SEA_BOBBER_GLB_PATH):
		var bobber_scene: PackedScene = load(SEA_BOBBER_GLB_PATH) as PackedScene
		if bobber_scene != null:
			_bobber_node = bobber_scene.instantiate() as Node3D
			_bobber_node.name = "SeaBobberLure"
			_bobber_node.top_level = true
			_bobber_node.visible = false
			_configure_stylized_viewmodel_materials(_bobber_node)
			add_child(_bobber_node)

			_bobber_light = OmniLight3D.new()
			_bobber_light.name = "BobberNightBeacon"
			_bobber_light.position = Vector3(0.0, 0.32, 0.0)
			_bobber_light.light_color = Color(1.0, 0.78, 0.28, 1.0)
			_bobber_light.light_energy = 3.2
			_bobber_light.light_volumetric_fog_energy = 0.4
			_bobber_light.omni_range = 4.5
			_bobber_light.shadow_enabled = false
			_bobber_node.add_child(_bobber_light)

	# 2. 3D Fishing Line ImmediateMesh (top-level in world coordinates)
	_line_material = StandardMaterial3D.new()
	_line_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	_line_material.albedo_color = Color(0.82, 0.92, 0.96, 1.0)
	_line_material.roughness = 0.25
	_line_material.emission_enabled = true
	_line_material.emission = Color(0.32, 0.46, 0.52, 1.0)
	_line_material.emission_energy_multiplier = 0.65

	_line_imm_mesh = ImmediateMesh.new()
	_line_mesh_inst = MeshInstance3D.new()
	_line_mesh_inst.name = "FishingLine3D"
	_line_mesh_inst.top_level = true
	_line_mesh_inst.mesh = _line_imm_mesh
	_line_mesh_inst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_line_mesh_inst)

	# 3. Bobber Splash & 3D Water Thrash Wake Particles
	var drop_mat: StandardMaterial3D = StandardMaterial3D.new()
	drop_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	drop_mat.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	drop_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	drop_mat.albedo_color = Color(0.82, 0.90, 0.92, 0.78)
	drop_mat.roughness = 0.18
	drop_mat.emission_enabled = true
	drop_mat.emission = Color(0.20, 0.30, 0.34, 1.0)
	drop_mat.emission_energy_multiplier = 0.45

	var drop_mesh: SphereMesh = SphereMesh.new()
	drop_mesh.radius = 0.09
	drop_mesh.height = 0.18
	drop_mesh.radial_segments = 6
	drop_mesh.rings = 3
	drop_mesh.material = drop_mat

	_splash_particles = GPUParticles3D.new()
	_splash_particles.name = "BobberSplashParticles"
	_splash_particles.top_level = true
	_splash_particles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_splash_particles.emitting = false
	_splash_particles.amount = 32
	_splash_particles.lifetime = 0.5
	_splash_particles.local_coords = false

	var splash_proc: ParticleProcessMaterial = ParticleProcessMaterial.new()
	splash_proc.direction = Vector3(0.0, 1.0, 0.0)
	splash_proc.spread = 42.0
	splash_proc.initial_velocity_min = 2.4
	splash_proc.initial_velocity_max = 5.2
	splash_proc.gravity = Vector3(0.0, -9.8, 0.0)
	splash_proc.scale_min = 0.10
	splash_proc.scale_max = 0.25
	_splash_particles.process_material = splash_proc
	_splash_particles.draw_pass_1 = drop_mesh
	add_child(_splash_particles)

	_thrash_wake_particles = GPUParticles3D.new()
	_thrash_wake_particles.name = "FishThrashWakeParticles"
	_thrash_wake_particles.top_level = true
	_thrash_wake_particles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_thrash_wake_particles.emitting = false
	_thrash_wake_particles.amount = 64
	_thrash_wake_particles.lifetime = 0.65
	_thrash_wake_particles.local_coords = false

	var thrash_proc: ParticleProcessMaterial = ParticleProcessMaterial.new()
	thrash_proc.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	thrash_proc.emission_sphere_radius = 0.45
	thrash_proc.direction = Vector3(0.0, 1.0, 0.0)
	thrash_proc.spread = 58.0
	thrash_proc.initial_velocity_min = 3.2
	thrash_proc.initial_velocity_max = 6.8
	thrash_proc.gravity = Vector3(0.0, -9.8, 0.0)
	thrash_proc.scale_min = 0.14
	thrash_proc.scale_max = 0.34
	_thrash_wake_particles.process_material = thrash_proc
	_thrash_wake_particles.draw_pass_1 = drop_mesh
	add_child(_thrash_wake_particles)

	_abyssal_fish_light = OmniLight3D.new()
	_abyssal_fish_light.name = "AbyssalThrashGlow"
	_abyssal_fish_light.top_level = true
	_abyssal_fish_light.visible = false
	_abyssal_fish_light.light_color = Color(0.22, 0.96, 0.84, 1.0)
	_abyssal_fish_light.light_energy = 4.2
	_abyssal_fish_light.omni_range = 6.5
	_abyssal_fish_light.shadow_enabled = false
	add_child(_abyssal_fish_light)

	# 4. Caught Fish Display Holder & Dedicated Warm Rim/Key Inspection Light
	_catch_fish_holder = Node3D.new()
	_catch_fish_holder.name = "CaughtFishHolder"
	_catch_fish_holder.top_level = true
	_catch_fish_holder.visible = false
	add_child(_catch_fish_holder)

	_catch_inspection_light = OmniLight3D.new()
	_catch_inspection_light.name = "CatchInspectionRimLight"
	_catch_inspection_light.top_level = true
	_catch_inspection_light.visible = false
	_catch_inspection_light.light_color = Color(1.0, 0.88, 0.68, 1.0)
	_catch_inspection_light.light_energy = 3.8
	_catch_inspection_light.light_specular = 2.4
	_catch_inspection_light.light_volumetric_fog_energy = 0.0
	_catch_inspection_light.omni_range = 4.2
	_catch_inspection_light.omni_attenuation = 1.1
	_catch_inspection_light.shadow_enabled = false
	add_child(_catch_inspection_light)


func _build_fp_hud_overlay() -> void:
	_fp_hud_layer = CanvasLayer.new()
	_fp_hud_layer.name = "FirstPersonFishingHUD"
	_fp_hud_layer.layer = 10
	add_child(_fp_hud_layer)

	# Center Aim Reticle / Strike Prompt
	_reticle_label = Label.new()
	_reticle_label.name = "CastAimReticle"
	_reticle_label.visible = false
	_reticle_label.anchors_preset = Control.PRESET_CENTER
	_reticle_label.anchor_left = 0.5
	_reticle_label.anchor_top = 0.5
	_reticle_label.anchor_right = 0.5
	_reticle_label.anchor_bottom = 0.5
	_reticle_label.offset_left = -260.0
	_reticle_label.offset_top = -34.0
	_reticle_label.offset_right = 260.0
	_reticle_label.offset_bottom = 34.0
	_reticle_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_reticle_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_reticle_label.add_theme_font_size_override("font_size", 18)
	_reticle_label.add_theme_color_override("font_color", UI_BONE_PARCHMENT)
	_reticle_label.add_theme_color_override("font_shadow_color", Color(0.0, 0.0, 0.0, 0.92))
	_reticle_label.add_theme_constant_override("shadow_offset_x", 2)
	_reticle_label.add_theme_constant_override("shadow_offset_y", 2)
	_fp_hud_layer.add_child(_reticle_label)

	# Bottom-Center Ornate Occult-Brass Astrolabe Instrument Panel
	_hud_panel = PanelContainer.new()
	_hud_panel.name = "FPInstrumentPanel"
	_hud_panel.visible = false
	_hud_panel.anchors_preset = Control.PRESET_CENTER_BOTTOM
	_hud_panel.anchor_left = 0.5
	_hud_panel.anchor_top = 1.0
	_hud_panel.anchor_right = 0.5
	_hud_panel.anchor_bottom = 1.0
	_hud_panel.offset_left = -350.0
	_hud_panel.offset_top = -205.0
	_hud_panel.offset_right = 350.0
	_hud_panel.offset_bottom = -18.0

	var panel_sb: StyleBoxFlat = StyleBoxFlat.new()
	panel_sb.bg_color = UI_VOID_BLACK
	panel_sb.border_width_left = 2
	panel_sb.border_width_top = 2
	panel_sb.border_width_right = 2
	panel_sb.border_width_bottom = 2
	panel_sb.border_color = UI_TARNISHED_BRASS
	panel_sb.corner_radius_top_left = 2
	panel_sb.corner_radius_top_right = 2
	panel_sb.corner_radius_bottom_left = 2
	panel_sb.corner_radius_bottom_right = 2
	panel_sb.shadow_color = Color(0.0, 0.0, 0.0, 0.82)
	panel_sb.shadow_size = 14
	panel_sb.content_margin_left = 22.0
	panel_sb.content_margin_right = 22.0
	panel_sb.content_margin_top = 14.0
	panel_sb.content_margin_bottom = 14.0
	_hud_panel.add_theme_stylebox_override("panel", panel_sb)
	_fp_hud_layer.add_child(_hud_panel)

	# Custom Ornate Gothic Frame & Stress Vein Overlay
	_hud_frame_drawer = Control.new()
	_hud_frame_drawer.name = "LovecraftFrameOverlay"
	_hud_frame_drawer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud_frame_drawer.set_anchors_preset(Control.PRESET_FULL_RECT)
	_hud_frame_drawer.draw.connect(_on_draw_fp_hud_frame)
	_hud_panel.add_child(_hud_frame_drawer)

	var vbox: VBoxContainer = VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 4)
	_hud_panel.add_child(vbox)

	# Top Row: Tension Label | Status Banner | Drag Label
	var top_hbox: HBoxContainer = HBoxContainer.new()
	vbox.add_child(top_hbox)

	_tension_value_label = Label.new()
	_tension_value_label.text = "STRAIN: 0%"
	_tension_value_label.custom_minimum_size = Vector2(170.0, 0.0)
	_tension_value_label.add_theme_font_size_override("font_size", 14)
	_tension_value_label.add_theme_color_override("font_color", UI_ELDRITCH_TEAL)
	top_hbox.add_child(_tension_value_label)

	_status_banner_label = Label.new()
	_status_banner_label.text = "STERN DECK — AIM & CAST"
	_status_banner_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_status_banner_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_status_banner_label.add_theme_font_size_override("font_size", 15)
	_status_banner_label.add_theme_color_override("font_color", UI_BRASS_HIGHLIGHT)
	top_hbox.add_child(_status_banner_label)

	_drag_value_label = Label.new()
	_drag_value_label.text = "BRAKE DRAG: 65%"
	_drag_value_label.custom_minimum_size = Vector2(170.0, 0.0)
	_drag_value_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_drag_value_label.add_theme_font_size_override("font_size", 14)
	_drag_value_label.add_theme_color_override("font_color", UI_BONE_PARCHMENT)
	top_hbox.add_child(_drag_value_label)

	# Center Row: Ornate Curved Occult-Brass Tension Astrolabe / Arc Gauge
	_astrolabe_gauge = Control.new()
	_astrolabe_gauge.name = "OccultTensionAstrolabe"
	_astrolabe_gauge.custom_minimum_size = Vector2(0.0, 92.0)
	_astrolabe_gauge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_astrolabe_gauge.draw.connect(_on_draw_tension_astrolabe)
	vbox.add_child(_astrolabe_gauge)

	# Hidden ProgressBar preserved for compatibility
	_tension_bar = ProgressBar.new()
	_tension_bar.min_value = 0.0
	_tension_bar.max_value = 100.0
	_tension_bar.value = 0.0
	_tension_bar.visible = false
	_tension_fill_style = StyleBoxFlat.new()
	vbox.add_child(_tension_bar)

	# Telemetry Row
	_telemetry_label = Label.new()
	_telemetry_label.text = "LURE: READY  |  ABYSSAL SINK DEPTH: 12.0m"
	_telemetry_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_telemetry_label.add_theme_font_size_override("font_size", 13)
	_telemetry_label.add_theme_color_override("font_color", UI_BONE_PARCHMENT)
	vbox.add_child(_telemetry_label)

	# Contextual Controls Hint Row
	_controls_hint_label = Label.new()
	_controls_hint_label.text = "[Hold LMB] Power Cast   [Scroll] Reel Drag   [F] Return to Helm"
	_controls_hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_controls_hint_label.add_theme_font_size_override("font_size", 12)
	_controls_hint_label.add_theme_color_override("font_color", UI_MUTED_PARCHMENT)
	vbox.add_child(_controls_hint_label)


func _on_draw_fp_hud_frame() -> void:
	if _hud_frame_drawer == null:
		return
	var rect: Rect2 = Rect2(Vector2.ZERO, _hud_frame_drawer.size)
	var t_sec: float = float(Time.get_ticks_msec()) * 0.001
	var stress_ratio: float = clampf((line_tension - 75.0) / 25.0, 0.0, 1.0)
	_draw_lovecraft_hud_frame(_hud_frame_drawer, rect, UI_TARNISHED_BRASS, UI_BRASS_HIGHLIGHT, stress_ratio, t_sec)


func _draw_lovecraft_hud_frame(
	canvas: CanvasItem,
	rect: Rect2,
	outer_brass: Color,
	inner_accent: Color,
	stress_pulse: float,
	time_sec: float
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

	var top_rivet_count: int = clampi(int(w / 95.0), 2, 10)
	for r_i: int in range(1, top_rivet_count):
		var rx: float = lerpf(x0 + corner_len, x1 - corner_len, float(r_i) / float(top_rivet_count))
		canvas.draw_circle(Vector2(rx, y0 + 3.0), 1.4, inner_accent.darkened(0.1))
		canvas.draw_circle(Vector2(rx, y1 - 3.0), 1.4, inner_accent.darkened(0.1))

	if stress_pulse > 0.01:
		var pulse: float = 0.65 + 0.35 * sin(time_sec * 16.0)
		var alpha: float = clampf(stress_pulse * pulse, 0.0, 0.92)
		var vein_col: Color = Color(UI_CRIMSON_BRIGHT.r, UI_CRIMSON_BRIGHT.g, UI_CRIMSON_BRIGHT.b, alpha)
		var dark_vein: Color = Color(UI_BLOOD_CRIMSON.r, UI_BLOOD_CRIMSON.g, UI_BLOOD_CRIMSON.b, alpha * 0.75)
		var reach: float = 18.0 + 28.0 * stress_pulse
		var dirs: Array[Vector2] = [
			Vector2(1.0, 0.55).normalized(),
			Vector2(-1.0, 0.55).normalized(),
			Vector2(-1.0, -0.55).normalized(),
			Vector2(1.0, -0.55).normalized(),
		]
		for i: int in range(4):
			var p0: Vector2 = corners[i] + signs[i] * 6.0
			var d: Vector2 = dirs[i]
			var p1: Vector2 = p0 + d * (reach * 0.45) + Vector2(sin(time_sec * 9.0 + float(i)) * 3.0, cos(time_sec * 7.0) * 2.5)
			var p2: Vector2 = p1 + d * (reach * 0.55) + Vector2(-d.y * 5.0, d.x * 4.0)
			var branch: Vector2 = p1 + Vector2(d.x * reach * 0.35, -d.y * reach * 0.25)
			canvas.draw_line(p0, p1, dark_vein, 2.6)
			canvas.draw_line(p1, p2, vein_col, 1.6)
			canvas.draw_line(p1, branch, vein_col, 1.2)


func _on_draw_tension_astrolabe() -> void:
	if _astrolabe_gauge == null:
		return
	var sz: Vector2 = _astrolabe_gauge.size
	var center: Vector2 = Vector2(sz.x * 0.5, sz.y - 10.0)
	var radius: float = minf(sz.x * 0.28, sz.y - 16.0)
	if radius < 20.0:
		return

	var t_sec: float = float(Time.get_ticks_msec()) * 0.001
	var gauge_pct: float = (cast_power * 100.0) if state == FishingState.STATE_CASTING else line_tension
	var norm_val: float = clampf(gauge_pct / 100.0, 0.0, 1.0)
	var stress_ratio: float = clampf((line_tension - 75.0) / 25.0, 0.0, 1.0)

	# 1. Pulsing Blood-Crimson & Eldritch-Veined stress aura when tension > 75%
	if stress_ratio > 0.01:
		var pulse: float = 0.60 + 0.40 * sin(t_sec * 22.0)
		var aura_col: Color = Color(
			UI_CRIMSON_BRIGHT.r,
			UI_CRIMSON_BRIGHT.g,
			UI_CRIMSON_BRIGHT.b,
			0.36 * stress_ratio * pulse
		)
		_astrolabe_gauge.draw_arc(center, radius + 9.0, PI, TAU, 36, aura_col, 8.0)
		for v_idx: int in range(7):
			var v_ang: float = lerpf(PI + 0.2, TAU - 0.2, float(v_idx) / 6.0)
			var vp0: Vector2 = center + Vector2(cos(v_ang), sin(v_ang)) * (radius + 6.0)
			var vp1: Vector2 = vp0 + Vector2(cos(v_ang + sin(t_sec * 12.0 + float(v_idx)) * 0.4), sin(v_ang)) * (12.0 * stress_ratio)
			_astrolabe_gauge.draw_line(vp0, vp1, aura_col, 1.8)

	# 2. Dark Engraved Astrolabe Backing & Outer/Inner Brass Rings
	_astrolabe_gauge.draw_arc(center, radius, PI, TAU, 48, UI_CORRODED_IRON.darkened(0.35), 14.0)
	_astrolabe_gauge.draw_arc(center, radius + 7.0, PI, TAU, 48, UI_TARNISHED_BRASS, 2.2)
	_astrolabe_gauge.draw_arc(center, radius - 7.0, PI, TAU, 48, UI_TARNISHED_BRASS.darkened(0.2), 1.6)
	_astrolabe_gauge.draw_line(
		center + Vector2(-radius - 10.0, 0.0),
		center + Vector2(radius + 10.0, 0.0),
		UI_TARNISHED_BRASS,
		1.8
	)

	# 3. Color-coded Zone Arcs (Eldritch Teal 0-50%, Tarnished Brass 50-75%, Blood Crimson 75-100%)
	_astrolabe_gauge.draw_arc(center, radius, PI, PI + PI * 0.50, 24, UI_ELDRITCH_TEAL.darkened(0.35), 7.0)
	_astrolabe_gauge.draw_arc(center, radius, PI + PI * 0.50, PI + PI * 0.75, 16, UI_BRASS_HIGHLIGHT.darkened(0.30), 7.0)
	_astrolabe_gauge.draw_arc(center, radius, PI + PI * 0.75, TAU, 16, UI_BLOOD_CRIMSON, 7.0)

	# Active filled arc up to current needle angle
	if norm_val > 0.01:
		var active_col: Color = UI_ELDRITCH_TEAL
		if state == FishingState.STATE_CASTING:
			active_col = UI_BRASS_HIGHLIGHT
		elif gauge_pct >= 75.0:
			active_col = UI_CRIMSON_BRIGHT
		elif gauge_pct >= 50.0:
			active_col = UI_BRASS_HIGHLIGHT
		_astrolabe_gauge.draw_arc(center, radius, PI, PI + PI * norm_val, 32, active_col, 6.0)

	# 4. Runic Degree Ticks & Astrolabe Spoke Lines
	var tick_count: int = 12
	for i: int in range(tick_count + 1):
		var frac: float = float(i) / float(tick_count)
		var ang: float = PI + frac * PI
		var dir: Vector2 = Vector2(cos(ang), sin(ang))
		var is_major: bool = (i % 3 == 0)
		var inner_r: float = (radius - 13.0) if is_major else (radius - 8.0)
		var outer_r: float = (radius + 11.0) if is_major else (radius + 7.0)
		var tick_col: Color = UI_BRASS_HIGHLIGHT if is_major else UI_TARNISHED_BRASS
		if frac >= 0.75:
			tick_col = UI_CRIMSON_BRIGHT
		_astrolabe_gauge.draw_line(center + dir * inner_r, center + dir * outer_r, tick_col, 2.2 if is_major else 1.2)
		if is_major and i > 0 and i < tick_count:
			_astrolabe_gauge.draw_line(center + dir * 12.0, center + dir * (radius - 14.0), Color(UI_TARNISHED_BRASS, 0.28), 1.0)

	# 5. Reel Drag Threshold Marker on Outer Rim
	var drag_ang: float = PI + clampf(reel_drag_pct / 100.0, 0.0, 1.0) * PI
	var drag_dir: Vector2 = Vector2(cos(drag_ang), sin(drag_ang))
	var drag_perp: Vector2 = Vector2(-drag_dir.y, drag_dir.x)
	var drag_tip: Vector2 = center + drag_dir * (radius + 7.0)
	var drag_tri: PackedVector2Array = PackedVector2Array([
		drag_tip,
		drag_tip + drag_dir * 7.0 + drag_perp * 4.5,
		drag_tip + drag_dir * 7.0 - drag_perp * 4.5,
	])
	_astrolabe_gauge.draw_colored_polygon(drag_tri, UI_BONE_PARCHMENT)

	# 6. Sinister Sharp Forged-Iron Needle
	var jitter: float = 0.0
	if gauge_pct >= 75.0:
		jitter = sin(t_sec * 45.0) * 0.028 * stress_ratio
	var needle_ang: float = PI + clampf(norm_val + jitter, 0.0, 1.0) * PI
	var n_dir: Vector2 = Vector2(cos(needle_ang), sin(needle_ang))
	var n_perp: Vector2 = Vector2(-n_dir.y, n_dir.x)
	var needle_tip: Vector2 = center + n_dir * (radius + 4.0)
	var needle_poly: PackedVector2Array = PackedVector2Array([
		needle_tip,
		center + n_perp * 4.2 - n_dir * 4.0,
		center - n_dir * 10.0,
		center - n_perp * 4.2 - n_dir * 4.0,
	])
	var needle_col: Color = UI_CRIMSON_BRIGHT if gauge_pct >= 75.0 else UI_BONE_PARCHMENT
	_astrolabe_gauge.draw_colored_polygon(needle_poly, needle_col)
	_astrolabe_gauge.draw_polyline(needle_poly, UI_VOID_BLACK, 1.2)

	# Center Brass Astrolabe Hub Cap
	_astrolabe_gauge.draw_circle(center, 9.0, UI_CORRODED_IRON)
	_astrolabe_gauge.draw_circle(center, 6.5, UI_TARNISHED_BRASS)
	_astrolabe_gauge.draw_circle(center, 2.8, UI_BRASS_HIGHLIGHT)


func _update_fp_hud_overlay() -> void:
	if _hud_panel == null or _reticle_label == null:
		return

	var active: bool = (state != FishingState.IDLE)
	_hud_panel.visible = active
	_reticle_label.visible = active
	if not active:
		return

	if _hud_frame_drawer != null:
		_hud_frame_drawer.queue_redraw()
	if _astrolabe_gauge != null:
		_astrolabe_gauge.queue_redraw()

	var t_sec: float = float(Time.get_ticks_msec()) * 0.001
	_drag_value_label.text = "BRAKE DRAG: %d%%" % int(round(reel_drag_pct))

	if state == FishingState.STATE_FP_READY:
		_reticle_label.text = "✦  AIM CAST OVER DARK SWELLS  ✦"
		_reticle_label.modulate = UI_BONE_PARCHMENT
		_tension_bar.value = 0.0
		_tension_value_label.text = "CAST ARC: 0%"
		_tension_value_label.modulate = UI_ELDRITCH_TEAL
		_status_banner_label.text = "STERN DECK — READY TO CAST"
		_status_banner_label.modulate = UI_BRASS_HIGHLIGHT
		_telemetry_label.text = "HOLD: %.1f kg (%d Specimens)  |  PRESET SINK DEPTH: %.1fm" % [total_hold_kg, fish_hold.size(), hook_depth_m]
		_controls_hint_label.text = "[Hold LMB] Draw & Cast Rod   [Scroll] Brake Drag   [TAB] Dredge Ledger   [F] Return to Helm"
	elif state == FishingState.STATE_CASTING:
		var pct: int = int(round(cast_power * 100.0))
		_reticle_label.text = ("❖  CAST IMPULSE: %d%%  ❖" % pct) if _is_charging_cast else "LURE DESCENDING..."
		_reticle_label.modulate = UI_BRASS_HIGHLIGHT
		_tension_bar.value = cast_power * 100.0
		_tension_value_label.text = "CAST ARC: %d%%" % pct
		_tension_value_label.modulate = UI_BRASS_HIGHLIGHT
		_status_banner_label.text = "DRAWING ROD BACKWARD..." if _is_charging_cast else "LURE IN FLIGHT..."
		_telemetry_label.text = "ESTIMATED CAST REACH: %.1fm" % lerpf(10.0, 42.0, cast_power)
		_controls_hint_label.text = "[Release LMB] Whip Rod Forward to Cast"
	elif state == FishingState.STATE_WAITING_BITE:
		_tension_bar.value = line_tension
		_tension_value_label.text = "LINE STRAIN: %d%%" % int(round(line_tension))
		_tension_value_label.modulate = UI_ELDRITCH_TEAL
		if _in_strike_window:
			var pulse: float = 0.65 + 0.35 * sin(t_sec * 24.0)
			_reticle_label.text = "☠  SOMETHING TAKES THE BAIT! [STRIKE!]  ☠"
			_reticle_label.modulate = Color(UI_CRIMSON_BRIGHT.r, UI_CRIMSON_BRIGHT.g, UI_CRIMSON_BRIGHT.b, pulse)
			_status_banner_label.text = "ABYSSAL STRIKE — CLICK TO SET IRON HOOK!"
			_status_banner_label.modulate = UI_CRIMSON_BRIGHT
		else:
			var jig_str: String = " [LURE TWITCHING]" if _jig_boost_timer > 0.0 else ""
			_reticle_label.text = "◈  WATCH THE LANTERN FLOAT" + jig_str + "  ◈"
			_reticle_label.modulate = UI_BONE_PARCHMENT
			_status_banner_label.text = "BAIT SUSPENDED IN THE DARK" + jig_str
			_status_banner_label.modulate = UI_ELDRITCH_TEAL
		_telemetry_label.text = "%.1fm ASTERN  |  HOOK SINK DEPTH: %.1fm" % [fish_distance_m, hook_depth_m]
		_controls_hint_label.text = "[W/S or Scroll] Sink Depth   [RMB] Twitch Lure   [Hold LMB] Retrieve   [F] Return to Helm"
	elif state == FishingState.STATE_HOOKED:
		var t_pct: int = int(round(line_tension))
		_tension_bar.value = line_tension
		_tension_value_label.text = "LINE STRAIN: %d%%" % t_pct
		if line_tension >= 75.0:
			_tension_value_label.modulate = UI_CRIMSON_BRIGHT
		elif line_tension >= 48.0:
			_tension_value_label.modulate = UI_BRASS_HIGHLIGHT
		else:
			_tension_value_label.modulate = UI_ELDRITCH_TEAL

		var pump_ready: String = " [HEAVE READY]" if _pump_cooldown_timer <= 0.0 else (" [HEAVE %.1fs]" % _pump_cooldown_timer)
		if _fish_is_surging:
			_status_banner_label.text = "SPECIMEN THRASHING! EASE REEL OR LOWER DRAG!" + pump_ready
			_status_banner_label.modulate = UI_CRIMSON_BRIGHT
			_reticle_label.text = "⟪  SPECIMEN SURGING — COUNTER-ANGLE ROD  ⟫"
			_reticle_label.modulate = UI_CRIMSON_BRIGHT
		else:
			_status_banner_label.text = "SPECIMEN FATIGUED — HEAVE & CRANK REEL!" + pump_ready
			_status_banner_label.modulate = UI_ELDRITCH_TEAL
			_reticle_label.text = "⟪  HOLD LEFT CLICK TO HAUL ABOARD  ⟫"
			_reticle_label.modulate = UI_ELDRITCH_TEAL

		_telemetry_label.text = "DISTANCE: %.1fm ASTERN  |  DEPTH: %.1fm  |  VIGOR: %d%%" % [
			fish_distance_m,
			hook_depth_m,
			int(round(_fish_stamina * 100.0)),
		]
		_controls_hint_label.text = "[Hold LMB] Crank Reel   [RMB] Heave Rod   [Mouse] Counter-Angle   [Scroll] Drag   [F] Cut Line"
	elif state == FishingState.STATE_LANDING:
		var caught_name: String = (_current_catch.get("display_name", "Catch") as String).to_upper()
		_reticle_label.text = "✦  DREDGED ABOARD: %.1f kg %s ($%.2f)  ✦" % [
			_current_fish_weight_kg,
			caught_name,
			_current_catch.get("value", 0.0) as float,
		]
		_reticle_label.modulate = UI_BRASS_HIGHLIGHT
		_status_banner_label.text = "SPECIMEN HAULED ONTO STERN DECK!"
		_status_banner_label.modulate = UI_BRASS_HIGHLIGHT
		_telemetry_label.text = "TOTAL HOLD: %.1f kg (%d Specimens)" % [total_hold_kg, fish_hold.size()]
		_controls_hint_label.text = "[SPACE] Cast Again Immediately   [F] Return to Ship Helm"


func _setup_audio_players() -> void:
	_sfx_player = AudioStreamPlayer3D.new()
	_sfx_player.name = "RodSfxPlayer"
	_sfx_player.unit_size = 5.0
	_sfx_player.max_distance = 35.0
	_sfx_player.max_db = -3.0
	_sfx_player.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
	add_child(_sfx_player)

	_drag_click_player = AudioStreamPlayer3D.new()
	_drag_click_player.name = "ReelDragClickPlayer"
	_drag_click_player.unit_size = 5.0
	_drag_click_player.max_distance = 35.0
	_drag_click_player.max_db = -4.0
	_drag_click_player.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
	add_child(_drag_click_player)


func _play_one_shot_sfx(stream: AudioStreamWAV, pitch: float = 1.0) -> void:
	if _sfx_player == null or stream == null or DisplayServer.get_name() == "headless":
		return
	_sfx_player.stream = stream
	_sfx_player.pitch_scale = pitch
	_sfx_player.play()


func _build_procedural_sfx() -> void:
	_stream_whoosh = _dsp_rod_cast_whoosh()
	_stream_splash = _dsp_water_splash()
	_stream_nibble = _dsp_nibble_dip()
	_stream_strike_alarm = _dsp_drag_scream()
	_stream_reel_click = _dsp_reel_click()
	_stream_snap = _dsp_line_snap()
	_stream_catch = _dsp_abyssal_dread_drone()
	_stream_dread_drone = _stream_catch


func _dsp_hash_noise(index: int, seed_offset: float) -> float:
	var s: float = sin(float(index) * 12.9898 + seed_offset * 78.233) * 43758.5453
	return (s - floor(s)) * 2.0 - 1.0


func _dsp_cascaded_lpf(samples: PackedFloat32Array, cutoff_hz: float, q: float, sample_rate: float) -> void:
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


func _dsp_pack_wav(samples: PackedFloat32Array, gain: float, mix_rate: int = 44100) -> AudioStreamWAV:
	var count: int = samples.size()
	var pcm: PackedByteArray = PackedByteArray()
	pcm.resize(count * 2)
	var fade_in_len: int = min(64, count)
	var fade_out_len: int = min(256, count)

	for i: int in range(count):
		var env_edge: float = 1.0
		if i < fade_in_len:
			env_edge *= float(i) / float(max(1, fade_in_len))
		if i >= count - fade_out_len:
			var rem: int = (count - 1) - i
			env_edge *= float(rem) / float(max(1, fade_out_len))

		var v: float = clampf(samples[i] * gain * env_edge, -0.98, 0.98)
		var s16: int = clampi(int(round(v * 32767.0)), -32767, 32767)
		pcm.encode_s16(i * 2, s16)

	var wav: AudioStreamWAV = AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = mix_rate
	wav.stereo = false
	wav.data = pcm
	wav.loop_mode = AudioStreamWAV.LOOP_DISABLED
	return wav


func _dsp_rod_cast_whoosh() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var count: int = int(0.44 * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)
	var bp_x1: float = 0.0
	var bp_x2: float = 0.0
	var bp_y1: float = 0.0
	var bp_y2: float = 0.0
	var cord_phase: float = 0.0
	for i: int in range(count):
		var frac: float = float(i) / float(max(1, count - 1))
		var attack: float = clampf(frac / 0.22, 0.0, 1.0)
		var decay: float = exp(-pow(maxf(0.0, frac - 0.18) * 2.8, 1.6))
		var env: float = attack * attack * decay
		var sweep_hz: float = lerpf(300.0, 120.0, pow(frac, 0.75))
		var omega: float = TAU * sweep_hz / float(mix_rate)
		var sn: float = sin(omega)
		var cs: float = cos(omega)
		var alpha: float = sn / 4.4
		var a0: float = 1.0 + alpha
		var x0: float = _dsp_hash_noise(i, 3.1)
		var y0: float = (alpha / a0) * (x0 - bp_x2) - ((-2.0 * cs) / a0) * bp_y1 - ((1.0 - alpha) / a0) * bp_y2
		bp_x2 = bp_x1
		bp_x1 = x0
		bp_y2 = bp_y1
		bp_y1 = y0
		cord_phase += TAU * sweep_hz / float(mix_rate)
		buf[i] = (y0 * 1.45 + sin(cord_phase) * 0.24) * env
	_dsp_cascaded_lpf(buf, 520.0, 0.707, float(mix_rate))
	return _dsp_pack_wav(buf, 0.85, mix_rate)


func _dsp_water_splash() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var count: int = int(0.58 * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)
	var pink: float = 0.0
	var plunge_phase: float = 0.0
	var d1_p: float = 0.0
	var d2_p: float = 0.0
	var d3_p: float = 0.0
	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var frac: float = float(i) / float(max(1, count - 1))
		pink = pink * 0.91 + _dsp_hash_noise(i, 9.4) * 0.09
		var plunge_hz: float = lerpf(115.0, 48.0, minf(1.0, t * 6.5))
		plunge_phase += TAU * plunge_hz / float(mix_rate)
		var cavity_thump: float = sin(plunge_phase) * exp(-t * 14.0) * 0.65
		var wash_env: float = clampf(t / 0.015, 0.0, 1.0) * exp(-t * 5.8)
		var d1: float = 0.0
		if t >= 0.04 and t < 0.22:
			var dt1: float = t - 0.04
			d1_p += TAU * lerpf(280.0, 540.0, dt1 / 0.18) / float(mix_rate)
			d1 = sin(d1_p) * exp(-dt1 * 24.0) * 0.32
		var d2: float = 0.0
		if t >= 0.12 and t < 0.34:
			var dt2: float = t - 0.12
			d2_p += TAU * lerpf(340.0, 660.0, dt2 / 0.22) / float(mix_rate)
			d2 = sin(d2_p) * exp(-dt2 * 22.0) * 0.26
		var d3: float = 0.0
		if t >= 0.23 and t < 0.48:
			var dt3: float = t - 0.23
			d3_p += TAU * lerpf(240.0, 490.0, dt3 / 0.25) / float(mix_rate)
			d3 = sin(d3_p) * exp(-dt3 * 20.0) * 0.22
		buf[i] = (cavity_thump + pink * wash_env * 0.95 + d1 + d2 + d3) * (1.0 - pow(frac, 3.0))
	_dsp_cascaded_lpf(buf, 880.0, 0.75, float(mix_rate))
	return _dsp_pack_wav(buf, 0.88, mix_rate)


func _dsp_nibble_dip() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var count: int = int(0.18 * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)
	var phase: float = 0.0
	var pink: float = 0.0
	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var frac: float = float(i) / float(max(1, count - 1))
		phase += TAU * lerpf(145.0, 265.0, pow(frac, 0.65)) / float(mix_rate)
		pink = pink * 0.92 + _dsp_hash_noise(i, 5.2) * 0.08
		var env: float = clampf(t / 0.008, 0.0, 1.0) * exp(-t * 19.0)
		buf[i] = (sin(phase) * 0.65 + pink * 0.35) * env
	_dsp_cascaded_lpf(buf, 520.0, 0.72, float(mix_rate))
	return _dsp_pack_wav(buf, 0.82, mix_rate)


func _dsp_reel_click() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var count: int = int(0.032 * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)
	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var impulse_env: float = exp(-t / 0.0028)
		var body_env: float = exp(-t / 0.0065)
		var pawl_a: float = sin(t * TAU * 780.0) * 0.55
		var pawl_b: float = sin(t * TAU * 1240.0) * 0.35
		var ping: float = sin(t * TAU * 1820.0) * 0.18
		buf[i] = (pawl_a + pawl_b) * body_env + (ping + _dsp_hash_noise(i, 11.3) * 0.35) * impulse_env
	_dsp_cascaded_lpf(buf, 1750.0, 0.707, float(mix_rate))
	return _dsp_pack_wav(buf, 0.80, mix_rate)


func _dsp_drag_scream() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var count: int = int(0.34 * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)
	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var frac: float = float(i) / float(max(1, count - 1))
		var local_t: float = fmod(t, 0.036)
		var tooth_env: float = exp(-local_t / 0.0032)
		var pawl_sig: float = (sin(local_t * TAU * 860.0) * 0.52 + sin(local_t * TAU * 1380.0) * 0.32 + _dsp_hash_noise(i, 6.4) * 0.25) * tooth_env
		var rod_groan: float = sin(t * TAU * 92.0 + sin(t * TAU * 14.0) * 1.4) * 0.28
		buf[i] = (pawl_sig + rod_groan) * sin(frac * PI)
	_dsp_cascaded_lpf(buf, 1450.0, 0.72, float(mix_rate))
	return _dsp_pack_wav(buf, 0.82, mix_rate)


func _dsp_line_snap() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var count: int = int(0.38 * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)
	var phase: float = 0.0
	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		phase += TAU * lerpf(240.0, 56.0, minf(1.0, t * 5.5)) / float(mix_rate)
		var recoil: float = sin(phase) * exp(-t * 12.0) * 0.68
		var crack: float = _dsp_hash_noise(i, 14.2) * exp(-t * 38.0) * 0.52
		var twang: float = sin(t * TAU * 410.0) * exp(-t * 22.0) * 0.25
		buf[i] = recoil + crack + twang
	_dsp_cascaded_lpf(buf, 760.0, 0.74, float(mix_rate))
	return _dsp_pack_wav(buf, 0.88, mix_rate)


func _dsp_abyssal_dread_drone() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var count: int = int(1.35 * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)
	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var frac: float = float(i) / float(max(1, count - 1))
		var env: float = clampf(t / 0.14, 0.0, 1.0) * exp(-maxf(0.0, t - 0.14) * 2.4) * (1.0 - pow(frac, 4.0))
		var sub_bell: float = sin(t * TAU * 55.0) * 0.48
		var fifth_drone: float = sin(t * TAU * 82.5 + sin(t * TAU * 2.2) * 0.6) * 0.30
		var minor_tierce: float = sin(t * TAU * 118.8) * 0.18 * exp(-t * 1.8)
		var bowed_metal: float = sin(t * TAU * 167.2 + sin(t * TAU * 5.0) * 1.2) * 0.12 * exp(-t * 2.2)
		buf[i] = (sub_bell + fifth_drone + minor_tierce + bowed_metal) * env
	_dsp_cascaded_lpf(buf, 260.0, 0.78, float(mix_rate))
	return _dsp_pack_wav(buf, 0.84, mix_rate)
