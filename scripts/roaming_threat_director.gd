class_name RoamingThreatDirector
extends Node3D

const MODEL_GHOST_TRAWLER: String = "res://assets/models/enemy_ghost_trawler.glb"
const MODEL_LEVIATHAN_FULL: String = "res://assets/models/enemy_leviathan_full.glb"
const MODEL_LEVIATHAN_HEAD: String = "res://assets/models/enemy_leviathan_head.glb"
const MODEL_LEVIATHAN_COIL: String = "res://assets/models/enemy_leviathan_coil.glb"
const SHADER_VOLUMETRIC_BEAM: String = "res://shaders/volumetric_beam_cone.gdshader"

const STATE_PATROL: int = 0
const STATE_SUSPICIOUS: int = 1
const STATE_AGGRO_PURSUIT: int = 2
const STATE_COOLDOWN_SEARCH: int = 3

const COLOR_MIMIC_AMBER: Color = Color(1.0, 0.72, 0.30, 1.0)
const COLOR_MIMIC_BEAM: Color = Color(1.0, 0.88, 0.66, 1.0)
const COLOR_SUSPICIOUS_ORANGE: Color = Color(1.0, 0.45, 0.12, 1.0)
const COLOR_AGGRO_CRIMSON: Color = Color(0.95, 0.15, 0.12, 1.0)
const COLOR_LEVIATHAN_CYAN: Color = Color(0.14, 0.92, 0.84, 1.0)
const COLOR_LEVIATHAN_EYE_AMBER: Color = Color(0.98, 0.74, 0.18, 1.0)

@export var boat: BoatController
@export var world_builder: WorldBuilder
@export var safe_harbor_radius: float = 92.0
@export var initial_ghost_trawler_count: int = 3
@export var initial_leviathan_count: int = 2
@export var debug_ignore_player: bool = false

signal debug_ignore_player_changed(enabled: bool)

static var shared_ignore_player: bool = false

var enemy_glow_intensity: float = 1.0

var _scene_ghost_trawler: PackedScene = null
var _scene_leviathan_head: PackedScene = null
var _scene_leviathan_coil: PackedScene = null
var _shader_beam_cone: Shader = null

var _ghost_trawlers: Array[Dictionary] = []
var _leviathans: Array[Dictionary] = []
var _shared_micro_normal_tex: NoiseTexture2D = null
var _foghorn_wav: AudioStreamWAV = null
var _leviathan_rumble_wav: AudioStreamWAV = null
var _fishing_struggle_timer: float = 0.0
var _time_sec: float = 0.0


func _ready() -> void:
	add_to_group("roaming_threat_director")
	_resolve_references()
	_init_shared_resources()
	_spawn_initial_roaming_threats()
	if _check_cli_peaceful_flags() or debug_ignore_player:
		set_debug_ignore_player(true)
	else:
		shared_ignore_player = false


func _check_cli_peaceful_flags() -> bool:
	var all_args: PackedStringArray = OS.get_cmdline_args()
	all_args.append_array(OS.get_cmdline_user_args())
	for raw_arg: String in all_args:
		var clean_arg: String = raw_arg.strip_edges().to_lower()
		if clean_arg == "--peaceful" or clean_arg == "--no-aggro" or clean_arg == "--peaceful=true" or clean_arg == "--no-aggro=true":
			return true
	return false


func set_debug_ignore_player(enabled: bool) -> void:
	var changed: bool = (debug_ignore_player != enabled) or (shared_ignore_player != enabled)
	debug_ignore_player = enabled
	shared_ignore_player = enabled
	if debug_ignore_player:
		clear_all_aggro_states()
	if changed:
		debug_ignore_player_changed.emit(debug_ignore_player)


func is_debug_ignore_player() -> bool:
	return debug_ignore_player


func toggle_debug_ignore_player() -> bool:
	set_debug_ignore_player(not debug_ignore_player)
	return debug_ignore_player


func clear_all_aggro_states() -> void:
	_fishing_struggle_timer = 0.0
	for trawler: Dictionary in _ghost_trawlers:
		trawler["state"] = STATE_PATROL
		trawler["state_timer"] = 0.0
		trawler["cone_exposure_time"] = 0.0
		trawler["escape_dark_timer"] = 0.0
		trawler["ram_cooldown"] = 0.0
		var horn_player: AudioStreamPlayer3D = trawler.get("horn_player") as AudioStreamPlayer3D
		if horn_player != null and horn_player.playing:
			horn_player.stop()
		_apply_ghost_trawler_palette(trawler, COLOR_MIMIC_AMBER, COLOR_MIMIC_BEAM, 1.0, false)

	for lev: Dictionary in _leviathans:
		lev["state"] = STATE_PATROL
		lev["state_timer"] = 0.0
		lev["cone_exposure_time"] = 0.0
		lev["escape_dark_timer"] = 0.0
		lev["ram_cooldown"] = 0.0
		lev["is_lunging"] = false
		lev["lunge_timer"] = 4.2
		var rumble_player: AudioStreamPlayer3D = lev.get("rumble_player") as AudioStreamPlayer3D
		if rumble_player != null and rumble_player.playing:
			rumble_player.stop()
		_apply_leviathan_palette(lev, COLOR_LEVIATHAN_EYE_AMBER, COLOR_LEVIATHAN_CYAN, 1.0)


func _exit_tree() -> void:
	_shared_micro_normal_tex = null
	_foghorn_wav = null
	_leviathan_rumble_wav = null
	_scene_ghost_trawler = null
	_scene_leviathan_head = null
	_scene_leviathan_coil = null
	_shader_beam_cone = null
	var mesh_nodes: Array[Node] = find_children("*", "MeshInstance3D", true, false)
	for node: Node in mesh_nodes:
		var mi: MeshInstance3D = node as MeshInstance3D
		if mi != null and mi.mesh != null:
			for s_i: int in range(mi.mesh.get_surface_count()):
				mi.set_surface_override_material(s_i, null)
	_ghost_trawlers.clear()
	_leviathans.clear()


func _resolve_references() -> void:
	var parent_node: Node = get_parent()
	if parent_node != null:
		if boat == null:
			boat = parent_node.get_node_or_null("Boat") as BoatController
		if world_builder == null:
			world_builder = parent_node.get_node_or_null("WorldBuilder") as WorldBuilder


func _init_shared_resources() -> void:
	if ResourceLoader.exists(MODEL_GHOST_TRAWLER):
		_scene_ghost_trawler = load(MODEL_GHOST_TRAWLER) as PackedScene
	if ResourceLoader.exists(MODEL_LEVIATHAN_HEAD):
		_scene_leviathan_head = load(MODEL_LEVIATHAN_HEAD) as PackedScene
	if ResourceLoader.exists(MODEL_LEVIATHAN_COIL):
		_scene_leviathan_coil = load(MODEL_LEVIATHAN_COIL) as PackedScene
	if ResourceLoader.exists(SHADER_VOLUMETRIC_BEAM):
		_shader_beam_cone = load(SHADER_VOLUMETRIC_BEAM) as Shader

	var noise: FastNoiseLite = FastNoiseLite.new()
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	noise.seed = 4091
	noise.frequency = 0.045
	noise.fractal_octaves = 3
	_shared_micro_normal_tex = NoiseTexture2D.new()
	_shared_micro_normal_tex.noise = noise
	_shared_micro_normal_tex.seamless = true
	_shared_micro_normal_tex.as_normal_map = true
	_shared_micro_normal_tex.bump_strength = 4.5

	_foghorn_wav = _build_warning_foghorn_wav()
	_leviathan_rumble_wav = _build_leviathan_rumble_wav()


func _spawn_initial_roaming_threats() -> void:
	var trawler_patrol_centers: Array[Vector3] = [
		Vector3(185.0, 0.0, -210.0),
		Vector3(-240.0, 0.0, -165.0),
		Vector3(160.0, 0.0, 230.0),
	]
	for i: int in range(min(initial_ghost_trawler_count, trawler_patrol_centers.size())):
		_create_ghost_trawler_instance(trawler_patrol_centers[i], float(i) * 2.1)

	var leviathan_patrol_centers: Array[Vector3] = [
		Vector3(-210.0, 0.0, 240.0),
		Vector3(260.0, 0.0, 45.0),
	]
	for j: int in range(min(initial_leviathan_count, leviathan_patrol_centers.size())):
		_create_leviathan_instance(leviathan_patrol_centers[j], float(j) * 3.1)


func _create_ghost_trawler_instance(spawn_pos: Vector3, phase_seed: float) -> Dictionary:
	var root_node: Node3D = Node3D.new()
	root_node.name = "GhostTrawler_%d" % _ghost_trawlers.size()
	add_child(root_node)
	root_node.global_position = Vector3(spawn_pos.x, 0.0, spawn_pos.z)

	var visuals: Node3D = Node3D.new()
	visuals.name = "Visuals"
	root_node.add_child(visuals)

	var window_mats: Array[StandardMaterial3D] = []
	var lens_mats: Array[StandardMaterial3D] = []

	if _scene_ghost_trawler != null:
		var model_inst: Node3D = _scene_ghost_trawler.instantiate() as Node3D
		if model_inst != null:
			model_inst.name = "GhostTrawlerModel"
			visuals.add_child(model_inst)
			_configure_enemy_glb_meshes(model_inst, window_mats, lens_mats, true)

	# Roof Searchlight Gimbal (Sweeping 45 deg left-right in Patrol, locking in Suspicious/Aggro)
	var searchlight_pivot: Node3D = Node3D.new()
	searchlight_pivot.name = "RoofSearchlightPivot"
	searchlight_pivot.position = Vector3(0.0, 4.10, -2.15)
	visuals.add_child(searchlight_pivot)

	var spotlight: SpotLight3D = SpotLight3D.new()
	spotlight.name = "GhostRoofSearchlight"
	spotlight.rotation_degrees = Vector3(-6.5, 0.0, 0.0)
	spotlight.light_color = COLOR_MIMIC_BEAM
	spotlight.light_energy = 24.0 * enemy_glow_intensity
	spotlight.spot_range = 88.0
	spotlight.spot_attenuation = 0.75
	spotlight.spot_angle = 28.0
	spotlight.spot_angle_attenuation = 1.4
	spotlight.light_volumetric_fog_energy = 2.8 * enemy_glow_intensity
	spotlight.shadow_enabled = false
	searchlight_pivot.add_child(spotlight)

	var beam_cone_mesh: MeshInstance3D = MeshInstance3D.new()
	beam_cone_mesh.name = "GhostSearchlightCone"
	var cyl_mesh: CylinderMesh = CylinderMesh.new()
	cyl_mesh.top_radius = 0.16
	cyl_mesh.bottom_radius = 10.5
	cyl_mesh.height = 48.0
	cyl_mesh.radial_segments = 20
	cyl_mesh.rings = 3
	cyl_mesh.cap_top = false
	cyl_mesh.cap_bottom = false

	var beam_mat: ShaderMaterial = null
	if _shader_beam_cone != null:
		beam_mat = ShaderMaterial.new()
		beam_mat.shader = _shader_beam_cone
		beam_mat.set_shader_parameter("beam_color", Color(1.0, 0.85, 0.55, 0.036))
		beam_mat.set_shader_parameter("fresnel_power", 2.1)
		beam_mat.set_shader_parameter("axial_fade_power", 1.35)
		beam_mat.set_shader_parameter("proximity_fade_distance", 1.2)
		beam_mat.set_shader_parameter("edge_softness", 5.0)
		beam_mat.set_shader_parameter("intensity_multiplier", 1.2 * enemy_glow_intensity)
		cyl_mesh.material = beam_mat

	beam_cone_mesh.mesh = cyl_mesh
	beam_cone_mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	beam_cone_mesh.position = Vector3(0.0, -2.6, -24.0)
	beam_cone_mesh.rotation_degrees = Vector3(83.5, 0.0, 0.0)
	searchlight_pivot.add_child(beam_cone_mesh)

	# Warm Cabin Interior & Stern Work Lantern OmniLight3D
	var cabin_light: OmniLight3D = OmniLight3D.new()
	cabin_light.name = "GhostCabinGlowLight"
	cabin_light.position = Vector3(0.0, 2.85, -1.60)
	cabin_light.light_color = COLOR_MIMIC_AMBER
	cabin_light.light_energy = 2.8 * enemy_glow_intensity
	cabin_light.omni_range = 12.0
	cabin_light.light_volumetric_fog_energy = 0.85 * enemy_glow_intensity
	visuals.add_child(cabin_light)

	var stern_lantern: OmniLight3D = OmniLight3D.new()
	stern_lantern.name = "GhostSternWorkLantern"
	stern_lantern.position = Vector3(0.0, 3.80, 5.20)
	stern_lantern.light_color = COLOR_MIMIC_AMBER
	stern_lantern.light_energy = 3.2 * enemy_glow_intensity
	stern_lantern.omni_range = 14.0
	stern_lantern.light_volumetric_fog_energy = 0.95 * enemy_glow_intensity
	visuals.add_child(stern_lantern)

	# Smokestack Exhaust Particles (belches heavy dark smoke at stack top on No_Smok Ghost Trawler)
	var smoke_particles: GPUParticles3D = _create_smokestack_particles()
	smoke_particles.position = Vector3(0.0, 4.45, -0.45)
	visuals.add_child(smoke_particles)

	var horn_player: AudioStreamPlayer3D = AudioStreamPlayer3D.new()
	horn_player.name = "GhostWarningHornPlayer"
	horn_player.stream = _foghorn_wav
	horn_player.unit_size = 18.0
	horn_player.max_distance = 220.0
	horn_player.max_db = 0.0
	horn_player.volume_db = -3.0
	horn_player.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
	root_node.add_child(horn_player)

	var data: Dictionary = {
		"root": root_node,
		"visuals": visuals,
		"searchlight_pivot": searchlight_pivot,
		"spotlight": spotlight,
		"beam_mat": beam_mat,
		"cabin_light": cabin_light,
		"stern_lantern": stern_lantern,
		"smoke_particles": smoke_particles,
		"horn_player": horn_player,
		"window_mats": window_mats,
		"lens_mats": lens_mats,
		"state": STATE_PATROL,
		"state_timer": 0.0,
		"cone_exposure_time": 0.0,
		"escape_dark_timer": 0.0,
		"ram_cooldown": 0.0,
		"patrol_origin": spawn_pos,
		"patrol_angle": phase_seed,
		"current_speed": 4.2,
		"beam_yaw": 0.0,
		"phase_seed": phase_seed,
	}
	_ghost_trawlers.append(data)
	return data


func _create_leviathan_instance(spawn_pos: Vector3, phase_seed: float) -> Dictionary:
	var root_node: Node3D = Node3D.new()
	root_node.name = "AbyssalLeviathan_%d" % _leviathans.size()
	add_child(root_node)
	root_node.global_position = Vector3(spawn_pos.x, 0.0, spawn_pos.z)

	var head_pivot: Node3D = Node3D.new()
	head_pivot.name = "LeviathanHeadPivot"
	root_node.add_child(head_pivot)

	var eye_mats: Array[StandardMaterial3D] = []
	var bio_mats: Array[StandardMaterial3D] = []

	if _scene_leviathan_head != null:
		var head_inst: Node3D = _scene_leviathan_head.instantiate() as Node3D
		if head_inst != null:
			head_inst.name = "LeviathanHeadModel"
			head_pivot.add_child(head_inst)
			_configure_enemy_glb_meshes(head_inst, eye_mats, bio_mats, false)

	var coil_pivots: Array[Node3D] = []
	var history_points: Array[Vector3] = []
	var coil_scales: Array[float] = [1.00, 0.82, 0.65, 0.50]
	for c_i: int in range(4):
		var coil_node: Node3D = Node3D.new()
		coil_node.name = "LeviathanCoil_%d" % c_i
		coil_node.position = Vector3(0.0, -0.55, float(c_i + 1) * 14.5)
		coil_node.scale = Vector3.ONE * coil_scales[c_i]
		root_node.add_child(coil_node)
		if _scene_leviathan_coil != null:
			var coil_inst: Node3D = _scene_leviathan_coil.instantiate() as Node3D
			if coil_inst != null:
				coil_inst.name = "LeviathanCoilModel_%d" % c_i
				coil_node.add_child(coil_inst)
				_configure_enemy_glb_meshes(coil_inst, eye_mats, bio_mats, false)
		coil_pivots.append(coil_node)

	for h_i: int in range(32):
		history_points.append(spawn_pos + Vector3(0.0, 0.0, float(h_i) * 1.8))

	# Eerie moving underwater cyan AreaLight3D spine ribbon & breach splash particles
	var bio_light: OmniLight3D = OmniLight3D.new()
	bio_light.name = "LeviathanCyanBioLight"
	bio_light.position = Vector3(0.0, 2.2, -1.5)
	bio_light.light_color = COLOR_LEVIATHAN_CYAN
	bio_light.light_energy = 2.2 * enemy_glow_intensity
	bio_light.omni_range = 16.0
	bio_light.omni_attenuation = 0.85
	bio_light.light_volumetric_fog_energy = 1.2 * enemy_glow_intensity
	head_pivot.add_child(bio_light)

	var spine_light: Light3D = LightingUtils.create_area_or_omni_light(
		head_pivot,
		"LeviathanSpineAreaLight",
		Vector3(0.0, 1.8, 4.5),
		Vector3(-90.0, 0.0, 0.0),
		Vector2(3.5, 14.0),
		Color(0.15, 0.92, 0.85, 1.0),
		4.8 * enemy_glow_intensity,
		28.0,
		false,
		1.0,
		1.8 * enemy_glow_intensity,
		350.0
	)

	var head_splash: GPUParticles3D = _create_leviathan_splash_particles()
	head_splash.position = Vector3(0.0, 0.15, -0.5)
	head_pivot.add_child(head_splash)

	var coil_light: OmniLight3D = OmniLight3D.new()
	coil_light.name = "LeviathanTrailBioLight"
	coil_light.position = Vector3(0.0, 1.15, 0.0)
	coil_light.light_color = COLOR_LEVIATHAN_CYAN
	coil_light.light_energy = 3.4 * enemy_glow_intensity
	coil_light.omni_range = 16.0
	coil_light.light_volumetric_fog_energy = 1.1 * enemy_glow_intensity
	if coil_pivots.size() >= 2:
		coil_pivots[1].add_child(coil_light)
		var coil_splash: GPUParticles3D = _create_leviathan_splash_particles()
		coil_splash.position = Vector3(0.0, 0.10, 0.0)
		coil_pivots[0].add_child(coil_splash)
	else:
		root_node.add_child(coil_light)

	var rumble_player: AudioStreamPlayer3D = AudioStreamPlayer3D.new()
	rumble_player.name = "LeviathanRumblePlayer"
	rumble_player.stream = _leviathan_rumble_wav
	rumble_player.unit_size = 20.0
	rumble_player.max_distance = 220.0
	rumble_player.max_db = 0.0
	rumble_player.volume_db = -3.5
	rumble_player.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
	root_node.add_child(rumble_player)

	var data: Dictionary = {
		"root": root_node,
		"head_pivot": head_pivot,
		"coil_pivots": coil_pivots,
		"history_points": history_points,
		"bio_light": bio_light,
		"spine_light": spine_light,
		"coil_light": coil_light,
		"rumble_player": rumble_player,
		"eye_mats": eye_mats,
		"bio_mats": bio_mats,
		"state": STATE_PATROL,
		"state_timer": 0.0,
		"cone_exposure_time": 0.0,
		"escape_dark_timer": 0.0,
		"ram_cooldown": 0.0,
		"orbit_angle": phase_seed,
		"lunge_timer": 4.2,
		"is_lunging": false,
		"patrol_origin": spawn_pos,
		"patrol_angle": phase_seed,
		"current_speed": 5.5,
		"phase_seed": phase_seed,
	}
	_leviathans.append(data)
	return data


func _configure_enemy_glb_meshes(
	model_root: Node3D,
	primary_glow_mats: Array[StandardMaterial3D],
	secondary_glow_mats: Array[StandardMaterial3D],
	attach_collision: bool
) -> void:
	var mesh_nodes: Array[Node] = model_root.find_children("*", "MeshInstance3D", true, false)
	for node: Node in mesh_nodes:
		var mesh_inst: MeshInstance3D = node as MeshInstance3D
		if mesh_inst == null or mesh_inst.mesh == null:
			continue
		mesh_inst.visibility_range_end = 450.0
		mesh_inst.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		if attach_collision:
			mesh_inst.create_trimesh_collision()

		var surf_count: int = mesh_inst.mesh.get_surface_count()
		for s_idx: int in range(surf_count):
			var orig_mat: StandardMaterial3D = mesh_inst.get_active_material(s_idx) as StandardMaterial3D
			if orig_mat == null:
				continue
			var dup_mat: StandardMaterial3D = orig_mat.duplicate() as StandardMaterial3D
			var mat_name: String = orig_mat.resource_name
			if mat_name == "WindowGlow" or mat_name == "EyeGlow":
				dup_mat.emission_enabled = true
				dup_mat.emission = COLOR_MIMIC_AMBER if mat_name == "WindowGlow" else COLOR_LEVIATHAN_EYE_AMBER
				dup_mat.emission_energy_multiplier = 4.5 * enemy_glow_intensity
				primary_glow_mats.append(dup_mat)
			elif mat_name == "SearchlightLens" or mat_name == "BioVeinGlow":
				dup_mat.emission_enabled = true
				dup_mat.emission = COLOR_MIMIC_BEAM if mat_name == "SearchlightLens" else COLOR_LEVIATHAN_CYAN
				dup_mat.emission_energy_multiplier = 6.5 * enemy_glow_intensity
				secondary_glow_mats.append(dup_mat)
			elif mat_name != "EyeCornea":
				if mat_name.begins_with("MatteLeviathan"):
					dup_mat.roughness = 0.72
				else:
					dup_mat.roughness = clampf(maxf(dup_mat.roughness, 0.88), 0.82, 0.95)
				dup_mat.metallic = minf(dup_mat.metallic, 0.10)
				dup_mat.metallic_specular = 0.20
				dup_mat.clearcoat_enabled = false
				dup_mat.vertex_color_use_as_albedo = true
				if _shared_micro_normal_tex != null and dup_mat.normal_texture == null:
					dup_mat.normal_enabled = true
					dup_mat.normal_texture = _shared_micro_normal_tex
					dup_mat.normal_scale = 0.42
			mesh_inst.set_surface_override_material(s_idx, dup_mat)


func _create_leviathan_splash_particles() -> GPUParticles3D:
	var particles: GPUParticles3D = GPUParticles3D.new()
	particles.name = "LeviathanBreachSplash"
	particles.amount = 28
	particles.lifetime = 0.85
	particles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	particles.local_coords = false

	var proc_mat: ParticleProcessMaterial = ParticleProcessMaterial.new()
	proc_mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	proc_mat.emission_sphere_radius = 1.15
	proc_mat.direction = Vector3(0.0, 1.0, 0.2)
	proc_mat.spread = 38.0
	proc_mat.initial_velocity_min = 1.6
	proc_mat.initial_velocity_max = 3.8
	proc_mat.gravity = Vector3(0.0, -7.5, 0.0)
	proc_mat.scale_min = 0.18
	proc_mat.scale_max = 0.48
	particles.process_material = proc_mat

	var sphere: SphereMesh = SphereMesh.new()
	sphere.radius = 0.18
	sphere.height = 0.28
	sphere.radial_segments = 6
	sphere.rings = 3
	var foam_mat: StandardMaterial3D = StandardMaterial3D.new()
	foam_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	foam_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	foam_mat.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	foam_mat.albedo_color = Color(0.62, 0.78, 0.80, 0.52)
	foam_mat.roughness = 0.88
	sphere.material = foam_mat
	particles.draw_pass_1 = sphere
	return particles


func _create_smokestack_particles() -> GPUParticles3D:
	var particles: GPUParticles3D = GPUParticles3D.new()
	particles.name = "SmokestackParticles"
	particles.amount = 48
	particles.lifetime = 2.2
	particles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	particles.local_coords = false

	var proc_mat: ParticleProcessMaterial = ParticleProcessMaterial.new()
	proc_mat.direction = Vector3(0.0, 1.0, 0.35)
	proc_mat.spread = 18.0
	proc_mat.initial_velocity_min = 0.8
	proc_mat.initial_velocity_max = 1.8
	proc_mat.gravity = Vector3(0.0, 0.45, 0.2)
	proc_mat.scale_min = 0.35
	proc_mat.scale_max = 1.65
	particles.process_material = proc_mat

	var sphere: SphereMesh = SphereMesh.new()
	sphere.radius = 0.24
	sphere.height = 0.42
	sphere.radial_segments = 8
	sphere.rings = 4
	var puff_mat: StandardMaterial3D = StandardMaterial3D.new()
	puff_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	puff_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	puff_mat.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	puff_mat.albedo_color = Color(0.10, 0.11, 0.12, 0.58)
	puff_mat.roughness = 0.95
	sphere.material = puff_mat
	particles.draw_pass_1 = sphere
	return particles


func _physics_process(delta: float) -> void:
	_time_sec = BoatController.get_synced_ocean_time()
	if debug_ignore_player != shared_ignore_player:
		set_debug_ignore_player(debug_ignore_player)

	if boat == null:
		_resolve_references()
		if boat == null:
			return

	# Track whether player is fighting a hooked struggling fish
	if debug_ignore_player:
		_fishing_struggle_timer = 0.0
	else:
		var fishing_ctrl: FishingController = boat.get_node_or_null("FishingController") as FishingController
		if fishing_ctrl != null and int(fishing_ctrl.state) == int(FishingController.FishingState.STATE_HOOKED):
			_fishing_struggle_timer += delta
		else:
			_fishing_struggle_timer = move_toward(_fishing_struggle_timer, 0.0, delta * 0.5)

	for t_idx: int in range(_ghost_trawlers.size()):
		_update_ghost_trawler(_ghost_trawlers[t_idx], delta)

	for l_idx: int in range(_leviathans.size()):
		_update_leviathan(_leviathans[l_idx], delta)


# =============================================================================
# STEALTH & DETECTION RADIUS / CONE MATH
# =============================================================================

func _compute_player_detection_radius() -> float:
	if boat == null:
		return 22.0
	# When Player Searchlight is ON: Enemy detection radius is 90m
	if boat.is_searchlight_active():
		return 90.0
	# When Player is Running Dark (L Key OFF):
	# 14m if drifting silently with engine idle, 22m normal dark cruise, up to 35m at 100% engine throttle
	var throttle_ratio: float = boat.get_throttle_noise_ratio()
	if throttle_ratio < 0.08:
		return 14.0
	elif throttle_ratio > 0.85:
		return lerpf(22.0, 35.0, (throttle_ratio - 0.85) / 0.15)
	return lerpf(14.0, 22.0, throttle_ratio / 0.85)


func _is_enemy_in_player_searchlight_cone(enemy_pos: Vector3) -> bool:
	if boat == null or not boat.is_searchlight_active():
		return false
	var to_enemy: Vector3 = enemy_pos - boat.global_position
	to_enemy.y = 0.0
	var dist: float = to_enemy.length()
	if dist > 150.0 or dist < 0.5:
		return false
	var dir_to_enemy: Vector3 = to_enemy / dist
	var boat_fwd: Vector3 = boat.get_searchlight_forward_dir()
	return boat_fwd.dot(dir_to_enemy) > 0.86


# =============================================================================
# GHOST TRAWLER 4-STATE AI & MIMICRY / AGGRO VISUALS
# =============================================================================

func _update_ghost_trawler(trawler: Dictionary, delta: float) -> void:
	var root_node: Node3D = trawler.get("root") as Node3D
	var visuals: Node3D = trawler.get("visuals") as Node3D
	var searchlight_pivot: Node3D = trawler.get("searchlight_pivot") as Node3D
	var spotlight: SpotLight3D = trawler.get("spotlight") as SpotLight3D
	var beam_mat: ShaderMaterial = trawler.get("beam_mat") as ShaderMaterial
	var cabin_light: OmniLight3D = trawler.get("cabin_light") as OmniLight3D
	var stern_lantern: OmniLight3D = trawler.get("stern_lantern") as OmniLight3D
	var smoke_particles: GPUParticles3D = trawler.get("smoke_particles") as GPUParticles3D
	var horn_player: AudioStreamPlayer3D = trawler.get("horn_player") as AudioStreamPlayer3D
	if root_node == null or visuals == null:
		return

	var state: int = int(trawler.get("state", STATE_PATROL))
	var state_timer: float = float(trawler.get("state_timer", 0.0)) + delta
	var cone_exposure: float = float(trawler.get("cone_exposure_time", 0.0))
	var escape_dark_timer: float = float(trawler.get("escape_dark_timer", 0.0))
	var ram_cooldown: float = maxf(0.0, float(trawler.get("ram_cooldown", 0.0)) - delta)
	var phase_seed: float = float(trawler.get("phase_seed", 0.0))

	var pos: Vector3 = root_node.global_position
	var player_pos: Vector3 = boat.global_position
	var to_player: Vector3 = player_pos - pos
	to_player.y = 0.0
	var dist_to_player: float = to_player.length()
	var dir_to_player: Vector3 = (to_player / dist_to_player) if dist_to_player > 0.001 else Vector3.FORWARD

	if debug_ignore_player:
		if state != STATE_PATROL:
			state = STATE_PATROL
			state_timer = 0.0
			escape_dark_timer = 0.0
			ram_cooldown = 0.0
			if horn_player != null and horn_player.playing:
				horn_player.stop()
		cone_exposure = 0.0
	else:
		# 1. Check if player's searchlight cone is shining directly onto this Ghost Trawler (> 1.2s)
		if _is_enemy_in_player_searchlight_cone(pos):
			cone_exposure += delta
			if cone_exposure >= 1.2:
				if state == STATE_PATROL or state == STATE_COOLDOWN_SEARCH:
					state = STATE_SUSPICIOUS
					state_timer = 0.0
					_play_horn_once(horn_player, 0.92)
				elif state == STATE_SUSPICIOUS and state_timer >= 0.8:
					state = STATE_AGGRO_PURSUIT
					state_timer = 0.0
					_play_horn_once(horn_player, 0.72)
		else:
			cone_exposure = move_toward(cone_exposure, 0.0, delta * 0.6)

	# 2. Check if player is inside Ghost Trawler's own front searchlight cone
	var trawler_beam_fwd: Vector3 = -root_node.global_transform.basis.z
	if searchlight_pivot != null:
		trawler_beam_fwd = -searchlight_pivot.global_transform.basis.z
	trawler_beam_fwd.y = 0.0
	if trawler_beam_fwd.length_squared() > 0.0001:
		trawler_beam_fwd = trawler_beam_fwd.normalized()
	var player_in_trawler_beam: bool = (not debug_ignore_player) and (dist_to_player <= 82.0) and (trawler_beam_fwd.dot(dir_to_player) > 0.84)

	var detection_radius: float = _compute_player_detection_radius()
	var manual_grace: float = maxf(0.0, float(trawler.get("manual_spawn_grace_timer", 0.0)) - delta)
	trawler["manual_spawn_grace_timer"] = manual_grace
	var player_in_safe_harbor: bool = (player_pos.length() < safe_harbor_radius) and (manual_grace <= 0.0)

	# 3. 4-State AI Transitions & Movement
	var target_move_dir: Vector3 = -root_node.global_transform.basis.z
	var target_speed: float = 4.2
	var target_turn_rate: float = 0.65

	match state:
		STATE_PATROL:
			# Mimic Mode: Patrol open water loop, sweeping roof searchlight +-45 deg left-right
			var patrol_angle: float = float(trawler.get("patrol_angle", 0.0)) + delta * 0.08
			trawler["patrol_angle"] = patrol_angle
			var patrol_origin: Vector3 = trawler.get("patrol_origin", Vector3(180.0, 0.0, -180.0))
			var waypoint: Vector3 = patrol_origin + Vector3(cos(patrol_angle) * 75.0, 0.0, sin(patrol_angle * 0.8) * 75.0)
			var to_wp: Vector3 = waypoint - pos
			to_wp.y = 0.0
			if to_wp.length_squared() > 1.0:
				target_move_dir = to_wp.normalized()
			target_speed = 4.4

			if searchlight_pivot != null:
				var sweep_rad: float = deg_to_rad(45.0) * sin(_time_sec * 1.15 + phase_seed)
				searchlight_pivot.rotation.y = lerpf(searchlight_pivot.rotation.y, sweep_rad, clampf(delta * 4.0, 0.0, 1.0))

			_apply_ghost_trawler_palette(trawler, COLOR_MIMIC_AMBER, COLOR_MIMIC_BEAM, 1.0, false)

			if not debug_ignore_player and not player_in_safe_harbor and (player_in_trawler_beam or dist_to_player <= detection_radius):
				state = STATE_SUSPICIOUS
				state_timer = 0.0
				escape_dark_timer = 0.0
				_play_horn_once(horn_player, 0.94)

		STATE_SUSPICIOUS:
			# 2.5s Warning: Searchlight snaps onto player's boat & pulses flickering orange while warning horn sounds
			target_move_dir = dir_to_player
			target_speed = 3.2
			target_turn_rate = 1.05

			if searchlight_pivot != null:
				var local_to_p: Vector3 = root_node.to_local(player_pos)
				var desired_beam_yaw: float = clampf(atan2(-local_to_p.x, -local_to_p.z), deg_to_rad(-65.0), deg_to_rad(65.0))
				searchlight_pivot.rotation.y = lerpf(searchlight_pivot.rotation.y, desired_beam_yaw, clampf(delta * 8.0, 0.0, 1.0))

			var flicker: float = 0.72 + 0.55 * absf(sin(_time_sec * 19.0))
			_apply_ghost_trawler_palette(trawler, COLOR_SUSPICIOUS_ORANGE, COLOR_SUSPICIOUS_ORANGE, flicker, false)

			if player_in_safe_harbor:
				state = STATE_COOLDOWN_SEARCH
				state_timer = 0.0
			elif state_timer >= 2.5:
				# Did the player press L (Go Dark) and veer out of the beam?
				if not boat.is_searchlight_active() and not player_in_trawler_beam and dist_to_player > 24.0:
					state = STATE_COOLDOWN_SEARCH
					state_timer = 0.0
				else:
					state = STATE_AGGRO_PURSUIT
					state_timer = 0.0
					escape_dark_timer = 0.0
					_play_horn_once(horn_player, 0.68)

		STATE_AGGRO_PURSUIT:
			# Blood-crimson windows & searchlight, heavy dark smokestack exhaust, 11.5 m/s ramming charge
			target_move_dir = dir_to_player
			target_speed = 11.5
			target_turn_rate = 1.25

			if searchlight_pivot != null:
				var local_to_p: Vector3 = root_node.to_local(player_pos)
				var desired_beam_yaw: float = clampf(atan2(-local_to_p.x, -local_to_p.z), deg_to_rad(-40.0), deg_to_rad(40.0))
				searchlight_pivot.rotation.y = lerpf(searchlight_pivot.rotation.y, desired_beam_yaw, clampf(delta * 7.0, 0.0, 1.0))

			_apply_ghost_trawler_palette(trawler, COLOR_AGGRO_CRIMSON, COLOR_AGGRO_CRIMSON, 1.45, true)

			# Ramming collision check
			if dist_to_player <= 5.4 and ram_cooldown <= 0.0:
				ram_cooldown = 3.2
				boat.apply_enemy_ram_impulse(dir_to_player, 1.35)
				_play_horn_once(horn_player, 0.64)

			# Stealth Escape rule: Player cuts searchlight (L) and stays outside 30m and out of front beam for 10s
			if player_in_safe_harbor:
				state = STATE_COOLDOWN_SEARCH
				state_timer = 0.0
			elif not boat.is_searchlight_active() and dist_to_player > 30.0 and not player_in_trawler_beam:
				escape_dark_timer += delta
				if escape_dark_timer >= 10.0:
					state = STATE_COOLDOWN_SEARCH
					state_timer = 0.0
					escape_dark_timer = 0.0
			else:
				escape_dark_timer = move_toward(escape_dark_timer, 0.0, delta * 0.5)

		STATE_COOLDOWN_SEARCH:
			# Confused wide searchlight sweep in the fog before returning to patrol
			target_speed = 3.0
			if searchlight_pivot != null:
				var confused_sweep: float = deg_to_rad(68.0) * sin(_time_sec * 2.2 + phase_seed)
				searchlight_pivot.rotation.y = lerpf(searchlight_pivot.rotation.y, confused_sweep, clampf(delta * 5.0, 0.0, 1.0))

			_apply_ghost_trawler_palette(trawler, COLOR_SUSPICIOUS_ORANGE.lerp(COLOR_MIMIC_AMBER, clampf(state_timer / 7.0, 0.0, 1.0)), COLOR_MIMIC_BEAM, 0.9, false)

			if not player_in_safe_harbor and (player_in_trawler_beam or (boat.is_searchlight_active() and dist_to_player <= 65.0)):
				state = STATE_SUSPICIOUS
				state_timer = 0.0
				_play_horn_once(horn_player, 0.88)
			elif state_timer >= 7.5:
				state = STATE_PATROL
				state_timer = 0.0

	# Keep outside safe harbor perimeter unless manually spawned for testing
	if manual_grace <= 0.0 and pos.length() < safe_harbor_radius + 8.0:
		target_move_dir = pos.normalized()

	if target_move_dir.length_squared() > 0.001:
		var desired_yaw: float = atan2(-target_move_dir.x, -target_move_dir.z)
		root_node.rotation.y = lerp_angle(root_node.rotation.y, desired_yaw, clampf(target_turn_rate * delta, 0.0, 1.0))

	var cur_speed: float = lerpf(float(trawler.get("current_speed", 4.2)), target_speed, clampf(delta * 2.4, 0.0, 1.0))
	trawler["current_speed"] = cur_speed
	var fwd: Vector3 = -root_node.global_transform.basis.z
	fwd.y = 0.0
	if fwd.length_squared() > 0.001:
		fwd = fwd.normalized()
	root_node.global_position += fwd * (cur_speed * delta)
	root_node.global_position.y = 0.0

	# 4-point Gerstner wave plane fitting + spring-damper buoyancy synchronized with ocean_water.gdshader
	var wave_plane: Dictionary = BoatController.get_exact_wave_plane(
		Vector2(root_node.global_position.x, root_node.global_position.z),
		root_node.rotation.y,
		4.2,
		1.8,
		_time_sec
	)
	var waterline_off: float = boat.base_waterline_offset if boat != null else -0.04
	var rock_scale: float = boat.wave_rocking_intensity if boat != null else 1.0
	var target_heave_y: float = float(wave_plane.get("weighted_height", 0.0)) + waterline_off
	var target_pitch_x: float = clampf(float(wave_plane.get("local_pitch", 0.0)) * rock_scale, -0.28, 0.30)
	var target_roll_z: float = clampf(float(wave_plane.get("local_roll", 0.0)) * 1.25 * rock_scale, -0.34, 0.34)

	var dt_buoy: float = clampf(delta, 0.001, 0.05)
	var cur_heave_y: float = float(trawler.get("heave_y", target_heave_y))
	var cur_heave_vel: float = float(trawler.get("heave_vel", 0.0))
	var cur_pitch_x: float = float(trawler.get("pitch_x", target_pitch_x))
	var cur_pitch_vel: float = float(trawler.get("pitch_vel", 0.0))
	var cur_roll_z: float = float(trawler.get("roll_z", target_roll_z))
	var cur_roll_vel: float = float(trawler.get("roll_vel", 0.0))

	cur_heave_vel += ((target_heave_y - cur_heave_y) * 32.0 - cur_heave_vel * 8.8) * dt_buoy
	cur_heave_y += cur_heave_vel * dt_buoy
	cur_pitch_vel += ((target_pitch_x - cur_pitch_x) * 24.0 - cur_pitch_vel * 7.4) * dt_buoy
	cur_pitch_x = clampf(cur_pitch_x + cur_pitch_vel * dt_buoy, -0.30, 0.32)
	cur_roll_vel += ((target_roll_z - cur_roll_z) * 20.0 - cur_roll_vel * 6.2) * dt_buoy
	cur_roll_z = clampf(cur_roll_z + cur_roll_vel * dt_buoy, -0.36, 0.36)

	trawler["heave_y"] = cur_heave_y
	trawler["heave_vel"] = cur_heave_vel
	trawler["pitch_x"] = cur_pitch_x
	trawler["pitch_vel"] = cur_pitch_vel
	trawler["roll_z"] = cur_roll_z
	trawler["roll_vel"] = cur_roll_vel

	visuals.position.y = cur_heave_y
	visuals.rotation.x = cur_pitch_x
	visuals.rotation.z = cur_roll_z

	if smoke_particles != null:
		smoke_particles.amount_ratio = 1.0 if state == STATE_AGGRO_PURSUIT else 0.35
	if cabin_light != null and stern_lantern != null:
		cabin_light.light_energy = 3.2 * enemy_glow_intensity
		stern_lantern.light_energy = 3.4 * enemy_glow_intensity
	if spotlight != null and beam_mat != null:
		var _unused_spot: SpotLight3D = spotlight

	trawler["state"] = state
	trawler["state_timer"] = state_timer
	trawler["cone_exposure_time"] = cone_exposure
	trawler["escape_dark_timer"] = escape_dark_timer
	trawler["ram_cooldown"] = ram_cooldown


func _apply_ghost_trawler_palette(
	trawler: Dictionary,
	win_color: Color,
	beam_color: Color,
	energy_mult: float,
	is_aggro: bool
) -> void:
	var spotlight: SpotLight3D = trawler.get("spotlight") as SpotLight3D
	var beam_mat: ShaderMaterial = trawler.get("beam_mat") as ShaderMaterial
	var cabin_light: OmniLight3D = trawler.get("cabin_light") as OmniLight3D
	var stern_lantern: OmniLight3D = trawler.get("stern_lantern") as OmniLight3D
	var window_mats: Array = trawler.get("window_mats", [])
	var lens_mats: Array = trawler.get("lens_mats", [])

	var glow_scale: float = energy_mult * enemy_glow_intensity
	if spotlight != null:
		spotlight.light_color = beam_color
		spotlight.light_energy = (34.0 if is_aggro else 24.0) * glow_scale
		spotlight.light_volumetric_fog_energy = (3.6 if is_aggro else 2.6) * glow_scale
	if beam_mat != null:
		beam_mat.set_shader_parameter("beam_color", Color(beam_color.r, beam_color.g, beam_color.b, 0.045 if is_aggro else 0.034))
		beam_mat.set_shader_parameter("intensity_multiplier", 1.25 * glow_scale)
	if cabin_light != null:
		cabin_light.light_color = win_color
	if stern_lantern != null:
		stern_lantern.light_color = win_color

	for m_var: Variant in window_mats:
		var m: StandardMaterial3D = m_var as StandardMaterial3D
		if m != null:
			m.albedo_color = win_color
			m.emission = win_color
			m.emission_energy_multiplier = 4.8 * glow_scale
	for l_var: Variant in lens_mats:
		var lm: StandardMaterial3D = l_var as StandardMaterial3D
		if lm != null:
			lm.albedo_color = beam_color
			lm.emission = beam_color
			lm.emission_energy_multiplier = 7.5 * glow_scale


# =============================================================================
# ABYSSAL LEVIATHAN 4-STATE AI & MULTI-SEGMENT SINE UNDULATION
# =============================================================================

func _update_leviathan(lev: Dictionary, delta: float) -> void:
	var root_node: Node3D = lev.get("root") as Node3D
	var head_pivot: Node3D = lev.get("head_pivot") as Node3D
	var coil_pivots: Array = lev.get("coil_pivots", [])
	var history_points: Array = lev.get("history_points", [])
	var bio_light: OmniLight3D = lev.get("bio_light") as OmniLight3D
	var coil_light: OmniLight3D = lev.get("coil_light") as OmniLight3D
	var rumble_player: AudioStreamPlayer3D = lev.get("rumble_player") as AudioStreamPlayer3D
	if root_node == null or head_pivot == null:
		return

	var state: int = int(lev.get("state", STATE_PATROL))
	var state_timer: float = float(lev.get("state_timer", 0.0)) + delta
	var cone_exposure: float = float(lev.get("cone_exposure_time", 0.0))
	var escape_dark_timer: float = float(lev.get("escape_dark_timer", 0.0))
	var ram_cooldown: float = maxf(0.0, float(lev.get("ram_cooldown", 0.0)) - delta)
	var phase_seed: float = float(lev.get("phase_seed", 0.0))

	var pos: Vector3 = root_node.global_position
	var player_pos: Vector3 = boat.global_position
	var to_player: Vector3 = player_pos - pos
	to_player.y = 0.0
	var dist_to_player: float = to_player.length()
	var dir_to_player: Vector3 = (to_player / dist_to_player) if dist_to_player > 0.001 else Vector3.FORWARD

	if debug_ignore_player:
		if state != STATE_PATROL:
			state = STATE_PATROL
			state_timer = 0.0
			escape_dark_timer = 0.0
			ram_cooldown = 0.0
			lev["is_lunging"] = false
			lev["lunge_timer"] = 4.2
			if rumble_player != null and rumble_player.playing:
				rumble_player.stop()
		cone_exposure = 0.0
	else:
		# Check player searchlight cone exposure (> 1.2s)
		if _is_enemy_in_player_searchlight_cone(pos):
			cone_exposure += delta
			if cone_exposure >= 1.2:
				if state == STATE_PATROL or state == STATE_COOLDOWN_SEARCH:
					state = STATE_SUSPICIOUS
					state_timer = 0.0
					_play_horn_once(rumble_player, 0.90)
				elif state == STATE_SUSPICIOUS and state_timer >= 0.7:
					state = STATE_AGGRO_PURSUIT
					state_timer = 0.0
					_play_horn_once(rumble_player, 0.74)
		else:
			cone_exposure = move_toward(cone_exposure, 0.0, delta * 0.6)

	var detection_radius: float = _compute_player_detection_radius()
	# Leviathan also attracts if player fights a struggling fish for too long (> 5.0s)
	if not debug_ignore_player and _fishing_struggle_timer > 5.0:
		detection_radius = maxf(detection_radius, 115.0)

	var manual_grace: float = maxf(0.0, float(lev.get("manual_spawn_grace_timer", 0.0)) - delta)
	lev["manual_spawn_grace_timer"] = manual_grace
	var player_in_shallow_safe_water: bool = (player_pos.length() < (safe_harbor_radius + 14.0)) and (manual_grace <= 0.0)
	var target_move_dir: Vector3 = -root_node.global_transform.basis.z
	var target_speed: float = 5.5
	var target_turn_rate: float = 1.15

	match state:
		STATE_PATROL:
			var patrol_angle: float = float(lev.get("patrol_angle", 0.0)) + delta * 0.11
			lev["patrol_angle"] = patrol_angle
			var patrol_origin: Vector3 = lev.get("patrol_origin", Vector3(-200.0, 0.0, 220.0))
			var wp: Vector3 = patrol_origin + Vector3(cos(patrol_angle) * 65.0, 0.0, sin(patrol_angle * 1.2) * 65.0)
			var to_wp: Vector3 = wp - pos
			to_wp.y = 0.0
			if to_wp.length_squared() > 1.0:
				target_move_dir = to_wp.normalized()
			target_speed = 5.6
			_apply_leviathan_palette(lev, COLOR_LEVIATHAN_EYE_AMBER, COLOR_LEVIATHAN_CYAN, 1.0)

			if not debug_ignore_player and not player_in_shallow_safe_water and dist_to_player <= detection_radius:
				state = STATE_SUSPICIOUS
				state_timer = 0.0
				_play_horn_once(rumble_player, 0.95)

		STATE_SUSPICIOUS:
			# Stalks toward the player's light/struggling fish; if player goes dark & still, breaks off
			target_move_dir = dir_to_player
			target_speed = 6.8
			_apply_leviathan_palette(lev, COLOR_SUSPICIOUS_ORANGE, COLOR_LEVIATHAN_CYAN, 1.35)

			if player_in_shallow_safe_water:
				state = STATE_COOLDOWN_SEARCH
				state_timer = 0.0
			elif state_timer >= 2.5:
				if not boat.is_searchlight_active() and boat.get_throttle_noise_ratio() < 0.08 and _fishing_struggle_timer <= 0.1:
					state = STATE_COOLDOWN_SEARCH
					state_timer = 0.0
				else:
					state = STATE_AGGRO_PURSUIT
					state_timer = 0.0
					lev["lunge_timer"] = 3.2
					lev["is_lunging"] = false
					_play_horn_once(rumble_player, 0.72)

		STATE_AGGRO_PURSUIT:
			# Circles the boat rapidly before lunging inward to strike the hull—unless player cuts searchlight (L) and holds still
			var orbit_angle: float = float(lev.get("orbit_angle", 0.0)) + delta * 0.95
			lev["orbit_angle"] = orbit_angle
			var lunge_timer: float = float(lev.get("lunge_timer", 3.2)) - delta
			var is_lunging: bool = bool(lev.get("is_lunging", false))

			if lunge_timer <= 0.0:
				is_lunging = not is_lunging
				lunge_timer = 2.4 if is_lunging else 3.4
				if is_lunging:
					_play_horn_once(rumble_player, 0.66)
			lev["lunge_timer"] = lunge_timer
			lev["is_lunging"] = is_lunging

			if is_lunging:
				target_move_dir = dir_to_player
				target_speed = 13.2
				target_turn_rate = 2.2
			else:
				var orbit_radius: float = 18.0
				var orbit_pt: Vector3 = player_pos + Vector3(cos(orbit_angle) * orbit_radius, 0.0, sin(orbit_angle) * orbit_radius)
				var to_orbit: Vector3 = orbit_pt - pos
				to_orbit.y = 0.0
				if to_orbit.length_squared() > 0.2:
					target_move_dir = to_orbit.normalized()
				target_speed = 11.8
				target_turn_rate = 1.85

			_apply_leviathan_palette(lev, COLOR_AGGRO_CRIMSON, COLOR_LEVIATHAN_CYAN, 1.65)

			if dist_to_player <= 5.0 and ram_cooldown <= 0.0:
				ram_cooldown = 3.4
				boat.apply_enemy_ram_impulse(dir_to_player, 1.45)
				lev["is_lunging"] = false
				lev["lunge_timer"] = 3.6

			# Escape check: shallow harbor/reef waters OR Running Dark + holding still
			if player_in_shallow_safe_water:
				state = STATE_COOLDOWN_SEARCH
				state_timer = 0.0
			elif not boat.is_searchlight_active() and boat.get_throttle_noise_ratio() < 0.08 and _fishing_struggle_timer <= 0.1:
				escape_dark_timer += delta
				if escape_dark_timer >= 3.5:
					state = STATE_COOLDOWN_SEARCH
					state_timer = 0.0
					escape_dark_timer = 0.0
			elif not boat.is_searchlight_active() and dist_to_player > 32.0:
				escape_dark_timer += delta * 0.5
				if escape_dark_timer >= 5.0:
					state = STATE_COOLDOWN_SEARCH
					state_timer = 0.0
					escape_dark_timer = 0.0
			else:
				escape_dark_timer = move_toward(escape_dark_timer, 0.0, delta * 0.5)

		STATE_COOLDOWN_SEARCH:
			target_move_dir = -dir_to_player
			target_speed = 5.0
			_apply_leviathan_palette(lev, COLOR_LEVIATHAN_EYE_AMBER, COLOR_LEVIATHAN_CYAN, 0.95)
			if state_timer >= 6.5:
				state = STATE_PATROL
				state_timer = 0.0

	if manual_grace <= 0.0 and pos.length() < safe_harbor_radius + 14.0:
		target_move_dir = pos.normalized()

	if target_move_dir.length_squared() > 0.001:
		var desired_yaw: float = atan2(-target_move_dir.x, -target_move_dir.z)
		root_node.rotation.y = lerp_angle(root_node.rotation.y, desired_yaw, clampf(target_turn_rate * delta, 0.0, 1.0))

	var cur_speed: float = lerpf(float(lev.get("current_speed", 5.5)), target_speed, clampf(delta * 3.0, 0.0, 1.0))
	lev["current_speed"] = cur_speed
	var fwd: Vector3 = -root_node.global_transform.basis.z
	fwd.y = 0.0
	if fwd.length_squared() > 0.001:
		fwd = fwd.normalized()
	root_node.global_position += fwd * (cur_speed * delta)
	root_node.global_position.y = 0.0

	# Phase-shifted vertical sine waves synchronized with exact Gerstner water height
	var wave_base_y: float = BoatController.get_exact_water_height(Vector2(root_node.global_position.x, root_node.global_position.z), _time_sec)
	var head_sine: float = sin(_time_sec * 3.2 + phase_seed)
	var head_cos: float = cos(_time_sec * 3.2 + phase_seed)
	head_pivot.position = Vector3(
		sin(_time_sec * 2.1 + phase_seed) * 0.35,
		wave_base_y + 0.32 + head_sine * 0.55,
		0.0
	)
	head_pivot.rotation.x = clampf(head_cos * 0.22, -0.32, 0.32)
	head_pivot.rotation.y = cos(_time_sec * 2.1 + phase_seed) * 0.16

	# Update trailing history breadcrumb trail and position the 4 body coil segments
	if history_points.size() > 0:
		var first_pt: Vector3 = history_points[0] as Vector3
		if root_node.global_position.distance_to(first_pt) >= 0.75:
			history_points.push_front(root_node.global_position)
			if history_points.size() > 36:
				history_points.pop_back()

	for idx: int in range(coil_pivots.size()):
		var coil_node: Node3D = coil_pivots[idx] as Node3D
		if coil_node == null:
			continue
		var seg_idx_f: float = float(idx + 1)
		var coil_sine: float = sin(_time_sec * 3.2 - seg_idx_f * 1.35 + phase_seed)
		var coil_cos: float = cos(_time_sec * 3.2 - seg_idx_f * 1.35 + phase_seed)
		var lateral_sway: float = sin(_time_sec * 2.1 - seg_idx_f * 0.95 + phase_seed) * 0.62
		coil_node.position = Vector3(
			lateral_sway,
			wave_base_y - 0.35 + coil_sine * 0.65,
			seg_idx_f * 14.5
		)
		coil_node.rotation.x = coil_cos * 0.18
		coil_node.rotation.y = cos(_time_sec * 2.1 - seg_idx_f * 0.95 + phase_seed) * 0.16
		coil_node.rotation.z = lateral_sway * 0.18

	if bio_light != null and coil_light != null:
		var pulse: float = 0.85 + 0.25 * sin(_time_sec * 3.2 + phase_seed)
		bio_light.light_energy = 5.4 * pulse * enemy_glow_intensity
		coil_light.light_energy = 3.6 * pulse * enemy_glow_intensity
		var spine_light: Light3D = lev.get("spine_light") as Light3D
		if spine_light != null:
			spine_light.light_energy = 4.8 * pulse * enemy_glow_intensity

	lev["state"] = state
	lev["state_timer"] = state_timer
	lev["cone_exposure_time"] = cone_exposure
	lev["escape_dark_timer"] = escape_dark_timer
	lev["ram_cooldown"] = ram_cooldown


func _apply_leviathan_palette(lev: Dictionary, eye_color: Color, bio_color: Color, mult: float) -> void:
	var eye_mats: Array = lev.get("eye_mats", [])
	var bio_mats: Array = lev.get("bio_mats", [])
	var scale_val: float = mult * enemy_glow_intensity
	for e_var: Variant in eye_mats:
		var em: StandardMaterial3D = e_var as StandardMaterial3D
		if em != null:
			em.albedo_color = eye_color
			em.emission = eye_color
			em.emission_energy_multiplier = 6.5 * scale_val
	for b_var: Variant in bio_mats:
		var bm: StandardMaterial3D = b_var as StandardMaterial3D
		if bm != null:
			bm.albedo_color = bio_color
			bm.emission = bio_color
			bm.emission_energy_multiplier = 5.8 * scale_val


func _play_horn_once(player: AudioStreamPlayer3D, pitch: float) -> void:
	if player != null and not player.playing and DisplayServer.get_name() != "headless":
		player.pitch_scale = pitch
		player.play()


# =============================================================================
# LIVE F9 DEBUG SPAWN & GLOW TUNING API
# =============================================================================

func spawn_ghost_trawler_ahead(distance_m: float = 40.0) -> Node3D:
	_resolve_references()
	if boat == null:
		return null
	var fwd: Vector3 = boat.get_searchlight_forward_dir()
	var right: Vector3 = Vector3(-fwd.z, 0.0, fwd.x)
	var spawn_pos: Vector3 = boat.global_position + fwd * distance_m - right * 3.5
	spawn_pos.y = 0.0

	var trawler_data: Dictionary
	if _ghost_trawlers.is_empty():
		trawler_data = _create_ghost_trawler_instance(spawn_pos, 0.0)
	else:
		trawler_data = _ghost_trawlers[0]

	var root_node: Node3D = trawler_data.get("root") as Node3D
	if root_node != null:
		root_node.global_position = spawn_pos
		# Angle 35 deg across the bow so both the jagged ramming prow, wheelhouse windows, and stern gantry are visible
		var look_target: Vector3 = boat.global_position + right * 8.0
		var dir: Vector3 = (look_target - spawn_pos).normalized()
		root_node.rotation.y = atan2(-dir.x, -dir.z)
		trawler_data["patrol_origin"] = spawn_pos - right * 75.0
		trawler_data["patrol_angle"] = 0.0
		trawler_data["manual_spawn_grace_timer"] = 30.0
		trawler_data["state"] = STATE_PATROL
		trawler_data["state_timer"] = 0.0
	return root_node


func spawn_leviathan_ahead(distance_m: float = 35.0) -> Node3D:
	_resolve_references()
	if boat == null:
		return null
	var fwd: Vector3 = boat.get_searchlight_forward_dir()
	var right: Vector3 = Vector3(-fwd.z, 0.0, fwd.x)
	var spawn_pos: Vector3 = boat.global_position + fwd * distance_m + right * 5.5
	spawn_pos.y = 0.0

	var lev_data: Dictionary
	if _leviathans.is_empty():
		lev_data = _create_leviathan_instance(spawn_pos, 0.5)
	else:
		lev_data = _leviathans[0]

	var root_node: Node3D = lev_data.get("root") as Node3D
	if root_node != null:
		root_node.global_position = spawn_pos
		var look_target: Vector3 = boat.global_position + fwd * 8.0 - right * 10.0
		var dir: Vector3 = (look_target - spawn_pos).normalized()
		root_node.rotation.y = atan2(-dir.x, -dir.z)
		lev_data["patrol_origin"] = spawn_pos - right * 65.0
		lev_data["patrol_angle"] = 0.0
		lev_data["manual_spawn_grace_timer"] = 30.0
		lev_data["state"] = STATE_PATROL
		lev_data["state_timer"] = 0.0
	return root_node


func set_enemy_glow_intensity(val: float) -> void:
	enemy_glow_intensity = clampf(val, 0.05, 5.0)
	for trawler: Dictionary in _ghost_trawlers:
		var st: int = int(trawler.get("state", STATE_PATROL))
		if st == STATE_AGGRO_PURSUIT:
			_apply_ghost_trawler_palette(trawler, COLOR_AGGRO_CRIMSON, COLOR_AGGRO_CRIMSON, 1.45, true)
		elif st == STATE_SUSPICIOUS:
			_apply_ghost_trawler_palette(trawler, COLOR_SUSPICIOUS_ORANGE, COLOR_SUSPICIOUS_ORANGE, 1.15, false)
		else:
			_apply_ghost_trawler_palette(trawler, COLOR_MIMIC_AMBER, COLOR_MIMIC_BEAM, 1.0, false)
	for lev: Dictionary in _leviathans:
		var st_l: int = int(lev.get("state", STATE_PATROL))
		var eye_c: Color = COLOR_AGGRO_CRIMSON if st_l == STATE_AGGRO_PURSUIT else COLOR_LEVIATHAN_EYE_AMBER
		_apply_leviathan_palette(lev, eye_c, COLOR_LEVIATHAN_CYAN, 1.2)


func get_enemy_glow_intensity() -> float:
	return enemy_glow_intensity


# =============================================================================
# PROCEDURAL WARNING HORN & LEVIATHAN HYDROPHONE AUDIO SYNTHESIS
# =============================================================================

func _build_warning_foghorn_wav() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var duration_sec: float = 1.65
	var count: int = int(duration_sec * float(mix_rate))
	var pcm: PackedByteArray = PackedByteArray()
	pcm.resize(count * 2)

	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var env: float = clampf(t / 0.18, 0.0, 1.0) * clampf((duration_sec - t) / 0.35, 0.0, 1.0)
		var base_f: float = lerpf(82.0, 76.0, t / duration_sec)
		var sig: float = (
			sin(t * TAU * base_f) * 0.55
			+ sin(t * TAU * (base_f * 1.5)) * 0.22
			+ sin(t * TAU * (base_f * 2.0)) * 0.18
			+ sin(t * TAU * (base_f * 3.0)) * 0.08
		)
		var v: float = clampf(sig * env * 0.85, -0.98, 0.98)
		var s16: int = clampi(int(round(v * 32767.0)), -32767, 32767)
		pcm.encode_s16(i * 2, s16)

	var wav: AudioStreamWAV = AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = mix_rate
	wav.stereo = false
	wav.data = pcm
	wav.loop_mode = AudioStreamWAV.LOOP_DISABLED
	return wav


func _build_leviathan_rumble_wav() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var duration_sec: float = 1.85
	var count: int = int(duration_sec * float(mix_rate))
	var pcm: PackedByteArray = PackedByteArray()
	pcm.resize(count * 2)

	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var env: float = sin(clampf(t / duration_sec, 0.0, 1.0) * PI)
		var f_mod: float = 52.0 + 14.0 * sin(t * TAU * 2.2)
		var sig: float = (
			sin(t * TAU * f_mod) * 0.62
			+ sin(t * TAU * (f_mod * 0.5)) * 0.32
			+ sin(t * TAU * 118.0 + sin(t * TAU * 6.5) * 2.4) * 0.16
		)
		var v: float = clampf(sig * env * 0.88, -0.98, 0.98)
		var s16: int = clampi(int(round(v * 32767.0)), -32767, 32767)
		pcm.encode_s16(i * 2, s16)

	var wav: AudioStreamWAV = AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = mix_rate
	wav.stereo = false
	wav.data = pcm
	wav.loop_mode = AudioStreamWAV.LOOP_DISABLED
	return wav
