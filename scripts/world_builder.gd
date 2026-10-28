class_name WorldBuilder
extends Node3D

const MODEL_WHARF_ISLAND: String = "res://assets/models/wharf_island.glb"
const MODEL_ISLAND_LARGE: String = "res://assets/models/island_large_archipelago.glb"
const MODEL_ISLAND_MEDIUM: String = "res://assets/models/island_medium_crag.glb"
const MODEL_ISLAND_STACK: String = "res://assets/models/island_sea_stack.glb"

const MODEL_ROCK_RAZOR: String = "res://assets/models/rock_razor_cluster.glb"
const MODEL_ROCK_ARCH: String = "res://assets/models/rock_jagged_arch.glb"
const MODEL_ROCK_MONOLITH: String = "res://assets/models/rock_basalt_monolith.glb"
const MODEL_POI_SHIPWRECK: String = "res://assets/models/poi_sunken_shipwreck.glb"
const MODEL_POI_SEA_FORT: String = "res://assets/models/poi_sea_fort_tower.glb"
const MODEL_POI_LEVIATHAN: String = "res://assets/models/poi_leviathan_ribcage.glb"
const MODEL_POI_LIGHTSHIP: String = "res://assets/models/poi_derelict_lightship.glb"
const MODEL_RUSTED_BUOY: String = "res://assets/models/rusted_warning_buoy.glb"
const MODEL_HARBOR_LIGHTHOUSE: String = "res://assets/models/harbor_lighthouse.glb"
const SHADER_SEARCHLIGHT_BEAM: String = "res://shaders/searchlight_beam.gdshader"
const SHADER_VOLUMETRIC_BEAM_CONE: String = "res://shaders/volumetric_beam_cone.gdshader"
const PIER_AMBIENT_OGG_PATH: String = "res://assets/audio/rain_ocean_loop.ogg"
const PIER_AMBIENT_WAV_FALLBACK_PATH: String = "res://assets/audio/rain_ocean_loop.wav"

@export var world_half_extent: float = 6000.0
@export var safe_zone_radius: float = 95.0
@export var major_island_count: int = 72
@export var deep_water_rock_count: int = 90
@export var random_seed: int = 1928
@export var lighthouse_rotation_speed: float = 0.45

var _mat_tidal_wet: StandardMaterial3D
var _mat_basalt_cliff: StandardMaterial3D
var _mat_sharp_obsidian: StandardMaterial3D
var _mat_mossy_crag: StandardMaterial3D
var _mat_weathered_timber: StandardMaterial3D
var _mat_rotting_wood: StandardMaterial3D
var _mat_shack_wall: StandardMaterial3D
var _mat_corrugated_roof: StandardMaterial3D
var _mat_rust_iron: StandardMaterial3D
var _mat_dark_metal: StandardMaterial3D
var _mat_amber_glass: StandardMaterial3D
var _mat_lighthouse_stone: StandardMaterial3D
var _mat_lighthouse_band: StandardMaterial3D
var _mat_beacon_lens: StandardMaterial3D

var _materials_by_name: Dictionary[String, StandardMaterial3D] = {}
var _rock_surface_materials: Array[StandardMaterial3D] = []
var _wharf_surface_materials: Array[StandardMaterial3D] = []
var _mat_surge_foam: ShaderMaterial
var _mat_lighthouse_beam: ShaderMaterial

var _scene_wharf_island: PackedScene
var _scene_island_large: PackedScene
var _scene_island_medium: PackedScene
var _scene_island_stack: PackedScene
var _scene_rock_razor: PackedScene
var _scene_rock_arch: PackedScene
var _scene_rock_monolith: PackedScene
var _scene_poi_shipwreck: PackedScene
var _scene_poi_sea_fort: PackedScene
var _scene_poi_leviathan: PackedScene
var _scene_poi_lightship: PackedScene
var _scene_rusted_buoy: PackedScene
var _scene_harbor_lighthouse: PackedScene
var _mesh_foam_ring: TorusMesh

var poi_hotspots: Array[Dictionary] = []

var _lighthouse_rotor: Node3D = null
var _dock_lanterns: Array[OmniLight3D] = []
var _warning_buoys: Array[Node3D] = []
var _warning_buoy_lights: Array[OmniLight3D] = []
var _warning_buoy_base_positions: Array[Vector3] = []
var _shipwreck_bulkhead_lights: Array[OmniLight3D] = []
var _shipwreck_nodes: Array[Node3D] = []
var _shipwreck_base_scales: Array[float] = []
var _shipwreck_scale_multiplier: float = 1.0
var _preview_shipwreck_node: Node3D = null
var _sea_fort_lantern_lights: Array[OmniLight3D] = []
var _sea_fort_lantern_base_pos: Array[Vector3] = []
var _leviathan_bio_lights: Array[OmniLight3D] = []
var _derelict_lightships: Array[Node3D] = []
var _derelict_lightship_base_positions: Array[Vector3] = []
var _derelict_lightship_base_yaws: Array[float] = []
var _derelict_lightship_beacons: Array[OmniLight3D] = []
var _pier_audio_player: AudioStreamPlayer3D = null
var _ocean_horizon: MeshInstance3D = null
var _boat_ref: Node3D = null
var _flicker_time: float = 0.0


func _ready() -> void:
	_init_shared_materials()
	_load_models()
	_setup_ocean_horizon()
	_configure_horizon_fog_darkness()
	_build_wharf_port()
	_populate_ocean_world()
	call_deferred("_configure_horizon_fog_darkness")


func _exit_tree() -> void:
	if _pier_audio_player != null:
		_pier_audio_player.stop()
		_pier_audio_player.stream = null


func _setup_ocean_horizon() -> void:
	var parent_node: Node = get_parent()
	if parent_node == null:
		return
	_boat_ref = parent_node.get_node_or_null("Boat") as Node3D
	_ocean_horizon = parent_node.get_node_or_null("OceanHorizon") as MeshInstance3D

	var ocean_node: MeshInstance3D = parent_node.get_node_or_null("Ocean") as MeshInstance3D
	var ocean_mat: Material = null
	if ocean_node != null and ocean_node.mesh != null:
		ocean_mat = ocean_node.mesh.surface_get_material(0)
		if ocean_mat == null:
			ocean_mat = ocean_node.get_active_material(0)

	if _ocean_horizon == null:
		_ocean_horizon = MeshInstance3D.new()
		_ocean_horizon.name = "OceanHorizon"
		var horizon_plane: PlaneMesh = PlaneMesh.new()
		horizon_plane.size = Vector2(6000.0, 6000.0)
		horizon_plane.subdivide_width = 128
		horizon_plane.subdivide_depth = 128
		if ocean_mat != null:
			horizon_plane.material = ocean_mat
		_ocean_horizon.mesh = horizon_plane
		_ocean_horizon.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_ocean_horizon.position = Vector3(0.0, -0.25, 0.0)
		parent_node.add_child.call_deferred(_ocean_horizon)
	else:
		_ocean_horizon.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if _ocean_horizon.mesh is PlaneMesh:
			var pm: PlaneMesh = _ocean_horizon.mesh as PlaneMesh
			pm.size = Vector2(6000.0, 6000.0)
			pm.subdivide_width = 128
			pm.subdivide_depth = 128
			if pm.material == null and ocean_mat != null:
				pm.material = ocean_mat
		_ocean_horizon.position.y = -0.25


func _configure_horizon_fog_darkness() -> void:
	var parent_node: Node = get_parent()
	if parent_node == null:
		return
	var world_env: WorldEnvironment = parent_node.get_node_or_null("WorldEnvironment") as WorldEnvironment
	if world_env != null and world_env.environment != null:
		var env: Environment = world_env.environment
		env.ambient_light_energy = 0.20
		env.fog_enabled = true
		env.fog_light_color = Color(0.005, 0.009, 0.014, 1.0)
		env.fog_density = 0.0065
		env.fog_aerial_perspective = 0.92
		env.volumetric_fog_albedo = Color(0.06, 0.09, 0.12, 1.0)
		env.volumetric_fog_emission = Color(0.001, 0.002, 0.003, 1.0)
		env.volumetric_fog_emission_energy = 0.03
	var moon: DirectionalLight3D = parent_node.get_node_or_null("DirectionalLight3D") as DirectionalLight3D
	if moon != null:
		moon.light_energy = 0.14


func _process(delta: float) -> void:
	_flicker_time += delta
	if _boat_ref == null and get_parent() != null:
		_boat_ref = get_parent().get_node_or_null("Boat") as Node3D
	if _ocean_horizon == null and get_parent() != null:
		_ocean_horizon = get_parent().get_node_or_null("OceanHorizon") as MeshInstance3D
	if _ocean_horizon != null and _boat_ref != null:
		var boat_pos: Vector3 = _boat_ref.global_position
		_ocean_horizon.global_position = Vector3(
			snappedf(boat_pos.x, 50.0),
			-0.25,
			snappedf(boat_pos.z, 50.0)
		)

	var synced_wave_time: float = BoatController.get_synced_ocean_time()
	if _lighthouse_rotor != null:
		_lighthouse_rotor.rotation.y += delta * lighthouse_rotation_speed

	for b_idx: int in range(_warning_buoys.size()):
		var buoy: Node3D = _warning_buoys[b_idx]
		if buoy != null and b_idx < _warning_buoy_base_positions.size():
			var base_pos: Vector3 = _warning_buoy_base_positions[b_idx]
			var buoy_plane: Dictionary = BoatController.get_exact_wave_plane(
				Vector2(base_pos.x, base_pos.z),
				buoy.rotation.y,
				1.1,
				1.1,
				synced_wave_time
			)
			var heave: float = float(buoy_plane.get("weighted_height", 0.0))
			var target_buoy_pitch: float = clampf(float(buoy_plane.get("local_pitch", 0.0)) * 1.15, -0.32, 0.32)
			var target_buoy_roll: float = clampf(float(buoy_plane.get("local_roll", 0.0)) * 1.15, -0.32, 0.32)
			buoy.position = Vector3(base_pos.x, lerpf(buoy.position.y, base_pos.y + heave, clampf(delta * 12.0, 0.0, 1.0)), base_pos.z)
			buoy.rotation.x = lerpf(buoy.rotation.x, target_buoy_pitch, clampf(delta * 8.0, 0.0, 1.0))
			buoy.rotation.z = lerpf(buoy.rotation.z, target_buoy_roll, clampf(delta * 8.0, 0.0, 1.0))
		if b_idx < _warning_buoy_lights.size():
			var b_light: OmniLight3D = _warning_buoy_lights[b_idx]
			if b_light != null:
				var l_phase: float = _flicker_time * 2.4 + float(b_idx) * 1.7
				var pulse: float = 0.5 + 0.5 * sin(l_phase) + 0.18 * sin(l_phase * 3.7)
				b_light.light_energy = 0.88 + clampf(pulse, 0.0, 1.2) * 0.74

	# Sputtering electrical bulkhead lights on Sunken Shipwrecks
	for sw_idx: int in range(_shipwreck_bulkhead_lights.size()):
		var sw_light: OmniLight3D = _shipwreck_bulkhead_lights[sw_idx]
		if sw_light != null:
			var t_val: float = _flicker_time * 6.2 + float(sw_idx) * 2.7
			var sputter: float = sin(t_val) * cos(t_val * 2.9) + 0.45 * sin(t_val * 5.3)
			if sputter < -0.35:
				sw_light.light_energy = 0.25
			else:
				sw_light.light_energy = 1.65 + clampf(sputter, 0.0, 1.2) * 0.95

	# Swaying warm oil lanterns on Sea-Fort Watchtowers
	for sf_idx: int in range(_sea_fort_lantern_lights.size()):
		var sf_light: OmniLight3D = _sea_fort_lantern_lights[sf_idx]
		if sf_light != null and sf_idx < _sea_fort_lantern_base_pos.size():
			var base_lpos: Vector3 = _sea_fort_lantern_base_pos[sf_idx]
			var sway_phase: float = _flicker_time * 2.1 + float(sf_idx) * 1.5
			sf_light.position = base_lpos + Vector3(sin(sway_phase) * 0.14, 0.0, cos(sway_phase * 0.85) * 0.12)
			sf_light.light_energy = 2.4 + 0.35 * sin(sway_phase * 1.7)

	# Swirling bioluminescent water/mist glow at Leviathan Ribcage Skerries
	for lv_idx: int in range(_leviathan_bio_lights.size()):
		var lv_light: OmniLight3D = _leviathan_bio_lights[lv_idx]
		if lv_light != null:
			var bio_phase: float = _flicker_time * 1.35 + float(lv_idx) * 1.9
			lv_light.position = Vector3(cos(bio_phase) * 1.2, 2.05, sin(bio_phase * 0.9) * 1.2)
			lv_light.light_energy = 1.05 + 0.30 * sin(bio_phase * 1.4)

	# Pitch/roll wave motion and slow-pulsing mast beacon on Derelict Lightships
	for ls_idx: int in range(_derelict_lightships.size()):
		var ls_node: Node3D = _derelict_lightships[ls_idx]
		if ls_node != null and ls_idx < _derelict_lightship_base_positions.size():
			var ls_base: Vector3 = _derelict_lightship_base_positions[ls_idx]
			var ls_yaw: float = _derelict_lightship_base_yaws[ls_idx]
			var ls_plane: Dictionary = BoatController.get_exact_wave_plane(
				Vector2(ls_base.x, ls_base.z),
				ls_yaw,
				5.5,
				2.2,
				synced_wave_time
			)
			var heave_y: float = float(ls_plane.get("weighted_height", 0.0))
			var pitch_x: float = clampf(float(ls_plane.get("local_pitch", 0.0)), -0.24, 0.24)
			var roll_z: float = clampf(float(ls_plane.get("local_roll", 0.0)) * 1.25, -0.28, 0.28)
			ls_node.position = Vector3(ls_base.x, lerpf(ls_node.position.y, ls_base.y + heave_y, clampf(delta * 8.5, 0.0, 1.0)), ls_base.z)
			ls_node.rotation = Vector3(
				lerpf(ls_node.rotation.x, pitch_x, clampf(delta * 6.5, 0.0, 1.0)),
				ls_yaw,
				lerpf(ls_node.rotation.z, roll_z, clampf(delta * 6.5, 0.0, 1.0))
			)
		if ls_idx < _derelict_lightship_beacons.size():
			var ls_beacon: OmniLight3D = _derelict_lightship_beacons[ls_idx]
			if ls_beacon != null:
				var b_pulse: float = 0.5 + 0.5 * sin(_flicker_time * 1.45 + float(ls_idx) * 2.1)
				ls_beacon.light_energy = 0.55 + pow(b_pulse, 2.2) * 2.65


func get_poi_hotspots() -> Array[Dictionary]:
	return poi_hotspots


func _create_noise_texture(
	noise_type: FastNoiseLite.NoiseType,
	seed_val: int,
	freq: float,
	octaves: int,
	as_normal: bool,
	bump_str: float
) -> NoiseTexture2D:
	var noise: FastNoiseLite = FastNoiseLite.new()
	noise.noise_type = noise_type
	noise.seed = seed_val
	noise.frequency = freq
	noise.fractal_type = FastNoiseLite.FRACTAL_FBM
	noise.fractal_octaves = octaves

	var tex: NoiseTexture2D = NoiseTexture2D.new()
	tex.width = 256
	tex.height = 256
	tex.seamless = true
	tex.as_normal_map = as_normal
	tex.bump_strength = bump_str
	tex.noise = noise
	return tex


func _init_shared_materials() -> void:
	# Procedural runtime NoiseTexture2D normal & roughness maps for micro-PBR surfaces
	var wet_rock_normal: NoiseTexture2D = _create_noise_texture(FastNoiseLite.TYPE_PERLIN, 101, 0.055, 4, true, 10.0)
	var wet_rock_rough: NoiseTexture2D = _create_noise_texture(FastNoiseLite.TYPE_PERLIN, 102, 0.055, 3, false, 1.0)

	var stone_normal: NoiseTexture2D = _create_noise_texture(FastNoiseLite.TYPE_CELLULAR, 201, 0.065, 5, true, 14.0)
	var stone_rough: NoiseTexture2D = _create_noise_texture(FastNoiseLite.TYPE_PERLIN, 202, 0.050, 5, false, 1.0)

	var wood_normal: NoiseTexture2D = _create_noise_texture(FastNoiseLite.TYPE_SIMPLEX_SMOOTH, 301, 0.050, 4, true, 9.0)
	var wood_rough: NoiseTexture2D = _create_noise_texture(FastNoiseLite.TYPE_SIMPLEX_SMOOTH, 302, 0.045, 3, false, 1.0)

	var metal_normal: NoiseTexture2D = _create_noise_texture(FastNoiseLite.TYPE_SIMPLEX, 401, 0.080, 4, true, 8.0)
	var metal_rough: NoiseTexture2D = _create_noise_texture(FastNoiseLite.TYPE_SIMPLEX, 402, 0.070, 4, false, 1.0)

	# 0: TidalWetRock — Glossy wet surface (roughness = 0.12, specular = 0.9, bump_strength = 10.0)
	_mat_tidal_wet = StandardMaterial3D.new()
	_mat_tidal_wet.resource_name = "TidalWetRock"
	_mat_tidal_wet.albedo_color = Color(0.04, 0.05, 0.06, 1.0)
	_mat_tidal_wet.roughness = 0.12
	_mat_tidal_wet.roughness_texture = wet_rock_rough
	_mat_tidal_wet.metallic = 0.15
	_mat_tidal_wet.metallic_specular = 0.9
	_mat_tidal_wet.normal_enabled = true
	_mat_tidal_wet.normal_texture = wet_rock_normal
	_mat_tidal_wet.uv1_triplanar = true
	_mat_tidal_wet.uv1_scale = Vector3(0.45, 0.45, 0.45)

	# 1: BasaltCliff — High-frequency 5-octave Cellular/Perlin stone bump map (bump_strength = 14.0, roughness = 0.86)
	_mat_basalt_cliff = StandardMaterial3D.new()
	_mat_basalt_cliff.resource_name = "BasaltCliff"
	_mat_basalt_cliff.albedo_color = Color(0.038, 0.045, 0.054, 1.0)
	_mat_basalt_cliff.roughness = 0.88
	_mat_basalt_cliff.roughness_texture = stone_rough
	_mat_basalt_cliff.metallic = 0.08
	_mat_basalt_cliff.normal_enabled = true
	_mat_basalt_cliff.normal_texture = stone_normal
	_mat_basalt_cliff.uv1_triplanar = true
	_mat_basalt_cliff.uv1_scale = Vector3(0.35, 0.35, 0.35)

	# 2: SharpObsidian — Sheer fractured rock faces
	_mat_sharp_obsidian = StandardMaterial3D.new()
	_mat_sharp_obsidian.resource_name = "SharpObsidian"
	_mat_sharp_obsidian.albedo_color = Color(0.024, 0.028, 0.036, 1.0)
	_mat_sharp_obsidian.roughness = 0.42
	_mat_sharp_obsidian.roughness_texture = stone_rough
	_mat_sharp_obsidian.metallic = 0.20
	_mat_sharp_obsidian.metallic_specular = 0.65
	_mat_sharp_obsidian.normal_enabled = true
	_mat_sharp_obsidian.normal_texture = stone_normal
	_mat_sharp_obsidian.uv1_triplanar = true
	_mat_sharp_obsidian.uv1_scale = Vector3(0.40, 0.40, 0.40)

	# 3: CoastalMoss — Storm-swept dark lichen/peat
	_mat_mossy_crag = StandardMaterial3D.new()
	_mat_mossy_crag.resource_name = "CoastalMoss"
	_mat_mossy_crag.albedo_color = Color(0.032, 0.052, 0.038, 1.0)
	_mat_mossy_crag.roughness = 0.94
	_mat_mossy_crag.roughness_texture = stone_rough
	_mat_mossy_crag.metallic = 0.04
	_mat_mossy_crag.normal_enabled = true
	_mat_mossy_crag.normal_texture = stone_normal
	_mat_mossy_crag.uv1_triplanar = true
	_mat_mossy_crag.uv1_scale = Vector3(0.45, 0.45, 0.45)

	# 4: WeatheredTimber — Stretched wood-grain Simplex noise normal map (bump_strength = 9.0, uv1_scale = Vector3(12, 2, 12)), roughness = 0.82
	_mat_weathered_timber = StandardMaterial3D.new()
	_mat_weathered_timber.resource_name = "WeatheredTimber"
	_mat_weathered_timber.albedo_color = Color(0.24, 0.19, 0.14, 1.0)
	_mat_weathered_timber.roughness = 0.82
	_mat_weathered_timber.roughness_texture = wood_rough
	_mat_weathered_timber.normal_enabled = true
	_mat_weathered_timber.normal_texture = wood_normal
	_mat_weathered_timber.uv1_triplanar = true
	_mat_weathered_timber.uv1_scale = Vector3(12.0, 2.0, 12.0)

	# 5: RottingWood — Stretched wood-grain Simplex noise normal map (bump_strength = 9.0, uv1_scale = Vector3(12, 2, 12)), roughness = 0.82
	_mat_rotting_wood = StandardMaterial3D.new()
	_mat_rotting_wood.resource_name = "RottingWood"
	_mat_rotting_wood.albedo_color = Color(0.16, 0.14, 0.12, 1.0)
	_mat_rotting_wood.roughness = 0.82
	_mat_rotting_wood.roughness_texture = wood_rough
	_mat_rotting_wood.normal_enabled = true
	_mat_rotting_wood.normal_texture = wood_normal
	_mat_rotting_wood.uv1_triplanar = true
	_mat_rotting_wood.uv1_scale = Vector3(12.0, 2.0, 12.0)

	# 6: ShackWall — Weathered clapboard siding
	_mat_shack_wall = StandardMaterial3D.new()
	_mat_shack_wall.resource_name = "ShackWall"
	_mat_shack_wall.albedo_color = Color(0.28, 0.26, 0.23, 1.0)
	_mat_shack_wall.roughness = 0.82
	_mat_shack_wall.roughness_texture = wood_rough
	_mat_shack_wall.normal_enabled = true
	_mat_shack_wall.normal_texture = wood_normal
	_mat_shack_wall.uv1_triplanar = true
	_mat_shack_wall.uv1_scale = Vector3(12.0, 2.0, 12.0)

	# 7: CorrugatedRoof — Metallic pitted surface (metallic = 0.65, roughness = 0.55, bump_strength = 8.0)
	_mat_corrugated_roof = StandardMaterial3D.new()
	_mat_corrugated_roof.resource_name = "CorrugatedRoof"
	_mat_corrugated_roof.albedo_color = Color(0.22, 0.16, 0.14, 1.0)
	_mat_corrugated_roof.metallic = 0.65
	_mat_corrugated_roof.roughness = 0.55
	_mat_corrugated_roof.roughness_texture = metal_rough
	_mat_corrugated_roof.normal_enabled = true
	_mat_corrugated_roof.normal_texture = metal_normal
	_mat_corrugated_roof.uv1_triplanar = true
	_mat_corrugated_roof.uv1_scale = Vector3(0.75, 0.75, 0.75)

	# 8: RustIron — Metallic pitted surface (metallic = 0.65, roughness = 0.55, bump_strength = 8.0)
	_mat_rust_iron = StandardMaterial3D.new()
	_mat_rust_iron.resource_name = "RustIron"
	_mat_rust_iron.albedo_color = Color(0.14, 0.11, 0.10, 1.0)
	_mat_rust_iron.metallic = 0.65
	_mat_rust_iron.roughness = 0.55
	_mat_rust_iron.roughness_texture = metal_rough
	_mat_rust_iron.normal_enabled = true
	_mat_rust_iron.normal_texture = metal_normal
	_mat_rust_iron.uv1_triplanar = true
	_mat_rust_iron.uv1_scale = Vector3(0.85, 0.85, 0.85)

	# 9: DarkMetal — Heavy iron cables, chains, and lantern room lattice ribs
	_mat_dark_metal = StandardMaterial3D.new()
	_mat_dark_metal.resource_name = "DarkMetal"
	_mat_dark_metal.albedo_color = Color(0.08, 0.09, 0.10, 1.0)
	_mat_dark_metal.metallic = 0.75
	_mat_dark_metal.roughness = 0.48
	_mat_dark_metal.roughness_texture = metal_rough
	_mat_dark_metal.normal_enabled = true
	_mat_dark_metal.normal_texture = metal_normal
	_mat_dark_metal.uv1_triplanar = true
	_mat_dark_metal.uv1_scale = Vector3(0.85, 0.85, 0.85)

	# 10: AmberGlass — Warm glowing harbor windows & lantern cages
	_mat_amber_glass = StandardMaterial3D.new()
	_mat_amber_glass.resource_name = "AmberGlass"
	_mat_amber_glass.albedo_color = Color(1.0, 0.72, 0.32, 1.0)
	_mat_amber_glass.roughness = 0.20
	_mat_amber_glass.emission_enabled = true
	_mat_amber_glass.emission = Color(1.0, 0.65, 0.25, 1.0)
	_mat_amber_glass.emission_energy_multiplier = 4.5

	# 11: LighthouseStone — High-frequency 5-octave Cellular/Perlin stone bump map (bump_strength = 14.0, roughness = 0.88)
	_mat_lighthouse_stone = StandardMaterial3D.new()
	_mat_lighthouse_stone.resource_name = "LighthouseStone"
	_mat_lighthouse_stone.albedo_color = Color(0.38, 0.40, 0.42, 1.0)
	_mat_lighthouse_stone.roughness = 0.88
	_mat_lighthouse_stone.roughness_texture = stone_rough
	_mat_lighthouse_stone.normal_enabled = true
	_mat_lighthouse_stone.normal_texture = stone_normal
	_mat_lighthouse_stone.uv1_triplanar = true
	_mat_lighthouse_stone.uv1_scale = Vector3(0.42, 0.42, 0.42)

	# 12: LighthouseBand — Crimson-red masonry warning stripe
	_mat_lighthouse_band = StandardMaterial3D.new()
	_mat_lighthouse_band.resource_name = "LighthouseBand"
	_mat_lighthouse_band.albedo_color = Color(0.45, 0.12, 0.10, 1.0)
	_mat_lighthouse_band.roughness = 0.86
	_mat_lighthouse_band.roughness_texture = stone_rough
	_mat_lighthouse_band.normal_enabled = true
	_mat_lighthouse_band.normal_texture = stone_normal
	_mat_lighthouse_band.uv1_triplanar = true
	_mat_lighthouse_band.uv1_scale = Vector3(0.42, 0.42, 0.42)

	# 13: BeaconLens — Blazing lighthouse lantern glass
	_mat_beacon_lens = StandardMaterial3D.new()
	_mat_beacon_lens.resource_name = "BeaconLens"
	_mat_beacon_lens.albedo_color = Color(1.0, 0.92, 0.68, 1.0)
	_mat_beacon_lens.roughness = 0.12
	_mat_beacon_lens.emission_enabled = true
	_mat_beacon_lens.emission = Color(1.0, 0.88, 0.60, 1.0)
	_mat_beacon_lens.emission_energy_multiplier = 14.0

	_rock_surface_materials = [
		_mat_tidal_wet,
		_mat_basalt_cliff,
		_mat_sharp_obsidian,
		_mat_mossy_crag,
	]

	_wharf_surface_materials = [
		_mat_tidal_wet,
		_mat_basalt_cliff,
		_mat_sharp_obsidian,
		_mat_mossy_crag,
		_mat_weathered_timber,
		_mat_rotting_wood,
		_mat_shack_wall,
		_mat_corrugated_roof,
		_mat_rust_iron,
		_mat_dark_metal,
		_mat_amber_glass,
		_mat_lighthouse_stone,
		_mat_lighthouse_band,
		_mat_beacon_lens,
	]

	_materials_by_name = {
		"TidalWetRock": _mat_tidal_wet,
		"BasaltCliff": _mat_basalt_cliff,
		"SharpObsidian": _mat_sharp_obsidian,
		"CoastalMoss": _mat_mossy_crag,
		"MossyCrag": _mat_mossy_crag,
		"WeatheredTimber": _mat_weathered_timber,
		"RottingWood": _mat_rotting_wood,
		"ShackWall": _mat_shack_wall,
		"CorrugatedRoof": _mat_corrugated_roof,
		"RustIron": _mat_rust_iron,
		"DarkMetal": _mat_dark_metal,
		"AmberGlass": _mat_amber_glass,
		"LighthouseStone": _mat_lighthouse_stone,
		"LighthouseBand": _mat_lighthouse_band,
		"BeaconLens": _mat_beacon_lens,
	}

	var foam_shader: Shader = Shader.new()
	foam_shader.code = """
shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform vec4 foam_color : source_color = vec4(0.42, 0.50, 0.52, 0.36);

void fragment() {
	float ring_band = sin(UV.y * 3.14159265);
	float wave_pulse = 0.65 + 0.35 * sin(UV.x * 37.69911 + TIME * 2.1) * cos(UV.x * 18.84955 - TIME * 1.4);
	float alpha_mask = clamp(pow(max(ring_band, 0.0001), 1.6) * wave_pulse, 0.0, 1.0);
	ALBEDO = foam_color.rgb;
	EMISSION = vec3(0.0);
	ROUGHNESS = 0.65;
	ALPHA = alpha_mask * foam_color.a;
}

void light() {
	if (!LIGHT_IS_DIRECTIONAL) {
		DIFFUSE_LIGHT += ALBEDO * LIGHT_COLOR * ATTENUATION * 0.55;
	}
}
"""
	_mat_surge_foam = ShaderMaterial.new()
	_mat_surge_foam.shader = foam_shader

	_mesh_foam_ring = TorusMesh.new()
	_mesh_foam_ring.inner_radius = 6.5
	_mesh_foam_ring.outer_radius = 10.5
	_mesh_foam_ring.rings = 20
	_mesh_foam_ring.ring_segments = 6
	_mesh_foam_ring.material = _mat_surge_foam

	var beam_shader: Shader = load(SHADER_VOLUMETRIC_BEAM_CONE) as Shader
	if beam_shader != null:
		_mat_lighthouse_beam = ShaderMaterial.new()
		_mat_lighthouse_beam.shader = beam_shader
		_mat_lighthouse_beam.set_shader_parameter("beam_color", Color(1.0, 0.88, 0.62, 0.14))
		_mat_lighthouse_beam.set_shader_parameter("fresnel_power", 2.2)
		_mat_lighthouse_beam.set_shader_parameter("axial_fade_power", 1.4)
		_mat_lighthouse_beam.set_shader_parameter("proximity_fade_distance", 1.5)


func _load_models() -> void:
	_scene_wharf_island = load(MODEL_WHARF_ISLAND) as PackedScene
	_scene_island_large = load(MODEL_ISLAND_LARGE) as PackedScene
	_scene_island_medium = load(MODEL_ISLAND_MEDIUM) as PackedScene
	_scene_island_stack = load(MODEL_ISLAND_STACK) as PackedScene
	_scene_rock_razor = load(MODEL_ROCK_RAZOR) as PackedScene
	_scene_rock_arch = load(MODEL_ROCK_ARCH) as PackedScene
	_scene_rock_monolith = load(MODEL_ROCK_MONOLITH) as PackedScene
	_scene_poi_shipwreck = load(MODEL_POI_SHIPWRECK) as PackedScene
	_scene_poi_sea_fort = load(MODEL_POI_SEA_FORT) as PackedScene
	_scene_poi_leviathan = load(MODEL_POI_LEVIATHAN) as PackedScene
	_scene_poi_lightship = load(MODEL_POI_LIGHTSHIP) as PackedScene
	_scene_rusted_buoy = load(MODEL_RUSTED_BUOY) as PackedScene
	_scene_harbor_lighthouse = load(MODEL_HARBOR_LIGHTHOUSE) as PackedScene


func _configure_stylized_landmark_hierarchy(
	node: Node,
	vis_range_end: float,
	vis_margin: float
) -> void:
	if node is MeshInstance3D:
		var mesh_inst: MeshInstance3D = node as MeshInstance3D
		mesh_inst.visibility_range_end = vis_range_end
		mesh_inst.visibility_range_end_margin = vis_margin
		mesh_inst.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF

		if mesh_inst.mesh != null:
			var surf_count: int = mesh_inst.mesh.get_surface_count()
			for s_idx: int in range(surf_count):
				var imported_mat: Material = mesh_inst.mesh.surface_get_material(s_idx)
				if imported_mat is StandardMaterial3D:
					var std_mat: StandardMaterial3D = (imported_mat as StandardMaterial3D).duplicate() as StandardMaterial3D
					var mat_name: String = imported_mat.resource_name
					if mat_name == "WarmLanternGlass":
						std_mat.vertex_color_use_as_albedo = false
						std_mat.albedo_color = Color(1.0, 0.72, 0.34, 1.0)
						std_mat.emission_enabled = true
						std_mat.emission = Color(1.0, 0.68, 0.28, 1.0)
						std_mat.emission_energy_multiplier = 3.2
						std_mat.roughness = 0.16
					elif mat_name == "WarningBeaconLens":
						std_mat.vertex_color_use_as_albedo = false
						std_mat.albedo_color = Color(0.55, 0.16, 0.05, 1.0)
						std_mat.emission_enabled = true
						std_mat.emission = Color(1.0, 0.34, 0.10, 1.0)
						std_mat.emission_energy_multiplier = 3.4
						std_mat.roughness = 0.15
					elif std_mat.albedo_texture != null:
						# Preserve custom Meshy PBR base color & normal textures + multiply `Col` cavity ink
						# Enforce matte corroded iron / waterlogged timber finish (no glossy clearcoat, high roughness, low specular/metallic)
						std_mat.vertex_color_use_as_albedo = true
						std_mat.albedo_color = Color(0.88, 0.86, 0.84, 1.0)
						std_mat.metallic = minf(std_mat.metallic, 0.10)
						std_mat.metallic_specular = 0.20
						std_mat.metallic_texture = null
						std_mat.roughness = clampf(maxf(std_mat.roughness, 0.88), 0.82, 0.95)
						std_mat.roughness_texture = null
						std_mat.clearcoat_enabled = false
						std_mat.rim_enabled = true
						std_mat.rim = 0.25
						std_mat.rim_tint = 0.45
					else:
						std_mat.vertex_color_use_as_albedo = true
						std_mat.metallic = minf(std_mat.metallic, 0.10)
						std_mat.metallic_specular = 0.20
						std_mat.roughness = clampf(maxf(std_mat.roughness, 0.88), 0.82, 0.95)
						std_mat.clearcoat_enabled = false
						std_mat.rim_enabled = true
						std_mat.rim = 0.35
						std_mat.rim_tint = 0.35
					mesh_inst.set_surface_override_material(s_idx, std_mat)

			mesh_inst.create_trimesh_collision()

	for child: Node in node.get_children():
		_configure_stylized_landmark_hierarchy(child, vis_range_end, vis_margin)


func _configure_glb_hierarchy(
	node: Node,
	vis_range_end: float,
	vis_margin: float,
	fallback_materials: Array[StandardMaterial3D]
) -> void:
	if node is MeshInstance3D:
		var mesh_inst: MeshInstance3D = node as MeshInstance3D
		mesh_inst.visibility_range_end = vis_range_end
		mesh_inst.visibility_range_end_margin = vis_margin
		mesh_inst.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF

		if mesh_inst.mesh != null:
			var surf_count: int = mesh_inst.mesh.get_surface_count()
			for s_idx: int in range(surf_count):
				var assigned_mat: StandardMaterial3D = null
				var imported_mat: Material = mesh_inst.mesh.surface_get_material(s_idx)
				if imported_mat != null and _materials_by_name.has(imported_mat.resource_name):
					assigned_mat = _materials_by_name[imported_mat.resource_name]
				elif s_idx < fallback_materials.size():
					assigned_mat = fallback_materials[s_idx]

				if assigned_mat != null:
					mesh_inst.set_surface_override_material(s_idx, assigned_mat)

			mesh_inst.create_trimesh_collision()

	for child: Node in node.get_children():
		_configure_glb_hierarchy(child, vis_range_end, vis_margin, fallback_materials)


func _build_wharf_port() -> void:
	var wharf_root: Node3D = Node3D.new()
	wharf_root.name = "WharfPort"
	wharf_root.position = Vector3.ZERO
	add_child(wharf_root)

	if _scene_wharf_island != null:
		var wharf_scene_inst: Node3D = _scene_wharf_island.instantiate() as Node3D
		if wharf_scene_inst != null:
			wharf_scene_inst.name = "WharfIslandModel"
			wharf_root.add_child(wharf_scene_inst)
			_configure_glb_hierarchy(wharf_scene_inst, 3500.0, 150.0, _wharf_surface_materials)

	# Standardized 22.0m Harbor Lighthouse (`harbor_lighthouse.glb`) on the wharf summit at (0.0, 10.5, 44.0)
	if _scene_harbor_lighthouse != null:
		var lh_inst: Node3D = _scene_harbor_lighthouse.instantiate() as Node3D
		if lh_inst != null:
			lh_inst.name = "HarborLighthouseModel"
			lh_inst.position = Vector3(0.0, 10.5, 44.0)
			wharf_root.add_child(lh_inst)
			_configure_stylized_landmark_hierarchy(lh_inst, 3500.0, 150.0)

	# Shoreline surge foam around the wharf island base
	if _mesh_foam_ring != null:
		var island_foam: MeshInstance3D = MeshInstance3D.new()
		island_foam.name = "WharfIslandFoam"
		island_foam.mesh = _mesh_foam_ring
		island_foam.position = Vector3(0.0, 0.15, 34.0)
		island_foam.scale = Vector3(2.9, 0.2, 2.7)
		island_foam.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		island_foam.visibility_range_end = 1800.0
		wharf_root.add_child(island_foam)

	# 4 Warm Sodium-Amber Dock Post Lanterns at the 4 pier lamp post coordinates (y = 4.0m)
	var dock_post_positions: Array[Vector3] = [
		Vector3(-6.8, 4.0, 5.0),
		Vector3(6.8, 4.0, 5.0),
		Vector3(-6.8, 4.0, 14.0),
		Vector3(6.8, 4.0, 18.0),
	]
	_dock_lanterns.clear()
	for i: int in range(dock_post_positions.size()):
		var dock_light: OmniLight3D = OmniLight3D.new()
		dock_light.name = "DockPostLantern_%d" % i
		dock_light.position = dock_post_positions[i]
		dock_light.light_color = Color(1.0, 0.68, 0.28, 1.0)
		dock_light.light_energy = 3.2
		dock_light.omni_range = 14.0
		dock_light.omni_attenuation = 1.05
		dock_light.light_specular = 0.85
		dock_light.light_volumetric_fog_energy = 1.4
		dock_light.shadow_enabled = true
		dock_light.add_to_group("harbor_pier_lanterns")
		wharf_root.add_child(dock_light)
		_dock_lanterns.append(dock_light)

	_spawn_channel_warning_buoys(wharf_root)

	# 3 Building Window / Porch Spill Lights outside the 3 run-down buildings
	var building_spill_positions: Array[Vector3] = [
		Vector3(-11.0, 3.2, 16.0),
		Vector3(2.0, 4.0, 21.0),
		Vector3(13.0, 3.2, 15.0),
	]
	for j: int in range(building_spill_positions.size()):
		var spill_light: OmniLight3D = OmniLight3D.new()
		spill_light.name = "BuildingSpillLight_%d" % j
		spill_light.position = building_spill_positions[j]
		spill_light.light_color = Color(1.0, 0.58, 0.22, 1.0)
		spill_light.light_energy = 4.0
		spill_light.light_volumetric_fog_energy = 1.4
		spill_light.omni_range = 16.0
		wharf_root.add_child(spill_light)

	# Long-Range Rotating Lighthouse Beacon at (0.0, 28.1, 44.0) aligned with the 22.0m HarborLighthouse lantern room
	_lighthouse_rotor = Node3D.new()
	_lighthouse_rotor.name = "LighthouseRotor"
	_lighthouse_rotor.position = Vector3(0.0, 28.1, 44.0)
	wharf_root.add_child(_lighthouse_rotor)

	var core_glow: OmniLight3D = OmniLight3D.new()
	core_glow.name = "LighthouseCoreGlow"
	core_glow.light_color = Color(1.0, 0.88, 0.62, 1.0)
	core_glow.light_energy = 4.0
	core_glow.light_volumetric_fog_energy = 0.6
	core_glow.omni_range = 16.0
	core_glow.omni_attenuation = 1.15
	core_glow.add_to_group("lighthouse_beacon_lamp")
	_lighthouse_rotor.add_child(core_glow)

	var cone_mesh: CylinderMesh = CylinderMesh.new()
	cone_mesh.height = 220.0
	cone_mesh.top_radius = 1.2
	cone_mesh.bottom_radius = 36.0
	cone_mesh.radial_segments = 24
	cone_mesh.rings = 4
	cone_mesh.cap_top = false
	cone_mesh.cap_bottom = false
	if _mat_lighthouse_beam != null:
		cone_mesh.material = _mat_lighthouse_beam

	# Opposing BeamNorth (-Z) and BeamSouth (+Z), tilted -4.0 degrees downward
	var beam_yaws: Array[float] = [0.0, PI]
	var beam_names: Array[String] = ["BeamNorth", "BeamSouth"]

	for b_idx: int in range(2):
		var spot: SpotLight3D = SpotLight3D.new()
		spot.name = beam_names[b_idx]
		spot.rotation = Vector3(deg_to_rad(-4.0), beam_yaws[b_idx], 0.0)
		spot.light_color = Color(1.0, 0.88, 0.62, 1.0)
		spot.light_energy = 110.0
		spot.light_volumetric_fog_energy = 4.5
		spot.spot_range = 350.0
		spot.spot_angle = 14.0
		spot.spot_angle_attenuation = 0.8
		spot.spot_attenuation = 0.8
		spot.add_to_group("lighthouse_beams")
		_lighthouse_rotor.add_child(spot)

		var cone_inst: MeshInstance3D = MeshInstance3D.new()
		cone_inst.name = "LighthouseBeamCone" if b_idx == 0 else (beam_names[b_idx] + "Cone")
		cone_inst.mesh = cone_mesh
		cone_inst.rotation = Vector3(deg_to_rad(90.0), 0.0, 0.0)
		cone_inst.position = Vector3(0.0, 0.0, -110.0)
		cone_inst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		cone_inst.visibility_range_end = 3500.0
		spot.add_child(cone_inst)

	# Chimney Smoke Emitters (GPUParticles3D) at the Bait Shack and Cannery chimney tops
	var bait_shack_smoke: GPUParticles3D = _create_chimney_smoke_emitter(
		"BaitShackChimneySmoke",
		Vector3(-13.0, 6.95, 18.0)
	)
	wharf_root.add_child(bait_shack_smoke)

	var cannery_smoke: GPUParticles3D = _create_chimney_smoke_emitter(
		"CanneryChimneySmoke",
		Vector3(5.2, 10.90, 26.2)
	)
	wharf_root.add_child(cannery_smoke)

	# Pier Ambient Audio (AudioStreamPlayer3D) playing low-pitched wooden creak / harbor water lap
	_setup_pier_ambient_audio(wharf_root)


func _create_chimney_smoke_emitter(emitter_name: String, pos: Vector3) -> GPUParticles3D:
	var particles: GPUParticles3D = GPUParticles3D.new()
	particles.name = emitter_name
	particles.position = pos
	particles.amount = 28
	particles.lifetime = 4.8
	particles.preprocess = 2.0
	particles.randomness = 0.35
	particles.visibility_aabb = AABB(Vector3(-14.0, -2.0, -14.0), Vector3(28.0, 24.0, 28.0))
	particles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	var proc_mat: ParticleProcessMaterial = ParticleProcessMaterial.new()
	proc_mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	proc_mat.emission_sphere_radius = 0.16
	proc_mat.direction = Vector3(0.65, 1.0, 0.35).normalized()
	proc_mat.spread = 18.0
	proc_mat.initial_velocity_min = 0.75
	proc_mat.initial_velocity_max = 1.40
	proc_mat.gravity = Vector3(0.85, 0.32, 0.42)
	proc_mat.damping_min = 0.20
	proc_mat.damping_max = 0.50
	proc_mat.scale_min = 0.55
	proc_mat.scale_max = 1.65
	proc_mat.color = Color(0.62, 0.66, 0.70, 0.24)
	particles.process_material = proc_mat

	var smoke_pass_mat: StandardMaterial3D = StandardMaterial3D.new()
	smoke_pass_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	smoke_pass_mat.vertex_color_use_as_albedo = true
	smoke_pass_mat.albedo_color = Color(0.68, 0.72, 0.75, 0.26)
	smoke_pass_mat.roughness = 0.95
	smoke_pass_mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	smoke_pass_mat.billboard_keep_scale = true

	var puff_mesh: SphereMesh = SphereMesh.new()
	puff_mesh.radius = 0.38
	puff_mesh.height = 0.76
	puff_mesh.radial_segments = 8
	puff_mesh.rings = 4
	puff_mesh.material = smoke_pass_mat
	particles.draw_pass_1 = puff_mesh

	return particles


func _setup_pier_ambient_audio(wharf_root: Node3D) -> void:
	_pier_audio_player = AudioStreamPlayer3D.new()
	_pier_audio_player.name = "PierHarborAmbience"
	_pier_audio_player.position = Vector3(0.0, 1.35, 10.5)
	_pier_audio_player.volume_db = -7.0
	_pier_audio_player.unit_size = 9.0
	_pier_audio_player.max_distance = 45.0
	_pier_audio_player.pitch_scale = 0.52
	_pier_audio_player.attenuation_filter_cutoff_hz = 680.0
	_pier_audio_player.attenuation_filter_db = -18.0

	var base_stream: AudioStream = null
	if ResourceLoader.exists(PIER_AMBIENT_OGG_PATH):
		base_stream = load(PIER_AMBIENT_OGG_PATH) as AudioStream
	elif ResourceLoader.exists(PIER_AMBIENT_WAV_FALLBACK_PATH):
		base_stream = load(PIER_AMBIENT_WAV_FALLBACK_PATH) as AudioStream

	if base_stream != null:
		var pier_stream: AudioStream = base_stream.duplicate() as AudioStream
		if pier_stream is AudioStreamOggVorbis:
			var ogg_stream: AudioStreamOggVorbis = pier_stream as AudioStreamOggVorbis
			ogg_stream.loop = true
		elif pier_stream is AudioStreamWAV:
			var wav_stream: AudioStreamWAV = pier_stream as AudioStreamWAV
			wav_stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
			wav_stream.loop_begin = 0
			wav_stream.loop_end = int(wav_stream.get_length() * float(wav_stream.mix_rate))
		_pier_audio_player.stream = pier_stream

	wharf_root.add_child(_pier_audio_player)
	if not _pier_audio_player.finished.is_connected(_on_pier_audio_finished):
		_pier_audio_player.finished.connect(_on_pier_audio_finished)
	if _pier_audio_player.stream != null and DisplayServer.get_name() != "headless":
		_pier_audio_player.play()


func _on_pier_audio_finished() -> void:
	if _pier_audio_player != null and _pier_audio_player.stream != null:
		_pier_audio_player.play()


func _populate_ocean_world() -> void:
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = random_seed

	var islands_root: Node3D = Node3D.new()
	islands_root.name = "ArchipelagoIslands"
	add_child(islands_root)

	var rocks_root: Node3D = Node3D.new()
	rocks_root.name = "JaggedRockFormations"
	add_child(rocks_root)

	var island_positions: Array[Vector2] = []
	var island_radii: Array[float] = []

	# 1. Spawn 65+ Major Islands in natural archipelago chains across -6000..+6000m
	var num_chains: int = 12
	var islands_per_chain: int = maxi(6, int(ceil(float(major_island_count) / float(num_chains))))
	var spawned_islands: int = 0

	for chain_idx: int in range(num_chains):
		var chain_angle: float = (TAU * float(chain_idx) / float(num_chains)) + rng.randf_range(-0.18, 0.18)
		var chain_dist: float = rng.randf_range(380.0, world_half_extent * 0.86)
		var cursor: Vector2 = Vector2(cos(chain_angle), sin(chain_angle)) * chain_dist
		var step_heading: float = chain_angle + rng.randf_range(0.55, 1.35)

		for _member_idx: int in range(islands_per_chain):
			if spawned_islands >= major_island_count:
				break

			var pos_xz: Vector2 = cursor + Vector2(
				rng.randf_range(-95.0, 95.0),
				rng.randf_range(-95.0, 95.0)
			)
			pos_xz.x = clampf(pos_xz.x, -world_half_extent + 220.0, world_half_extent - 220.0)
			pos_xz.y = clampf(pos_xz.y, -world_half_extent + 220.0, world_half_extent - 220.0)

			if pos_xz.length() < safe_zone_radius + 75.0:
				pos_xz = pos_xz.normalized() * (safe_zone_radius + 135.0)

			var roll_type: float = rng.randf()
			var chosen_scene: PackedScene = _scene_island_medium
			var base_footprint: float = 28.0
			var scale_factor: float = rng.randf_range(0.95, 1.65)

			if roll_type < 0.34:
				chosen_scene = _scene_island_large
				base_footprint = 48.0
				scale_factor = rng.randf_range(0.90, 1.55)
			elif roll_type < 0.72:
				chosen_scene = _scene_island_medium
				base_footprint = 28.0
				scale_factor = rng.randf_range(0.95, 1.65)
			else:
				chosen_scene = _scene_island_stack
				base_footprint = 16.0
				scale_factor = rng.randf_range(1.0, 1.80)

			_spawn_formation_instance(
				islands_root,
				chosen_scene,
				"Island_%03d" % spawned_islands,
				pos_xz,
				rng.randf_range(0.0, TAU),
				deg_to_rad(rng.randf_range(-3.5, 3.5)),
				deg_to_rad(rng.randf_range(-3.5, 3.5)),
				scale_factor,
				400.0,
				false,
				base_footprint * scale_factor
			)

			var effective_radius: float = base_footprint * scale_factor
			island_positions.append(pos_xz)
			island_radii.append(effective_radius)
			spawned_islands += 1

			step_heading += rng.randf_range(-0.42, 0.42)
			cursor += Vector2(cos(step_heading), sin(step_heading)) * rng.randf_range(290.0, 560.0)

	# 2. Spawn Hazardous Coastal Reef Belts around islands (35m-90m offshore)
	var spawned_rocks: int = 0
	for i: int in range(island_positions.size()):
		var center_xz: Vector2 = island_positions[i]
		var island_r: float = island_radii[i]
		var belt_count: int = rng.randi_range(1, 3)

		for _b: int in range(belt_count):
			var reef_angle: float = rng.randf_range(0.0, TAU)
			var offshore_dist: float = island_r + rng.randf_range(35.0, 90.0)
			var rock_xz: Vector2 = center_xz + Vector2(cos(reef_angle), sin(reef_angle)) * offshore_dist

			if rock_xz.length() < safe_zone_radius + 15.0:
				continue
			if absf(rock_xz.x) > world_half_extent or absf(rock_xz.y) > world_half_extent:
				continue

			_spawn_random_jagged_rock(rocks_root, rng, rock_xz, spawned_rocks)
			spawned_rocks += 1

	# 3. Spawn Deep-Water Labyrinth Fields in the open abyss (ensuring 180+ total jagged rocks)
	var target_total_rocks: int = maxi(195, spawned_rocks + deep_water_rock_count)
	var labyrinth_clusters: int = 24
	var cluster_idx: int = 0

	while spawned_rocks < target_total_rocks:
		var cluster_angle: float = (TAU * float(cluster_idx % labyrinth_clusters) / float(labyrinth_clusters)) + rng.randf_range(-0.22, 0.22)
		var cluster_dist: float = rng.randf_range(160.0, world_half_extent * 0.94)
		var cluster_center: Vector2 = Vector2(cos(cluster_angle), sin(cluster_angle)) * cluster_dist
		var members_in_cluster: int = rng.randi_range(3, 6)

		for _m: int in range(members_in_cluster):
			if spawned_rocks >= target_total_rocks:
				break
			var offset: Vector2 = Vector2(
				rng.randf_range(-110.0, 110.0),
				rng.randf_range(-110.0, 110.0)
			)
			var rock_xz: Vector2 = cluster_center + offset
			rock_xz.x = clampf(rock_xz.x, -world_half_extent + 80.0, world_half_extent - 80.0)
			rock_xz.y = clampf(rock_xz.y, -world_half_extent + 80.0, world_half_extent - 80.0)

			if rock_xz.length() < safe_zone_radius + 18.0:
				rock_xz = rock_xz.normalized() * (safe_zone_radius + rng.randf_range(28.0, 85.0))

			_spawn_random_jagged_rock(rocks_root, rng, rock_xz, spawned_rocks)
			spawned_rocks += 1

		cluster_idx += 1

	# 4. Scatter 20 Grounded Maritime Exploration POIs across coastal reefs, channels, and deep trenches
	var poi_root: Node3D = Node3D.new()
	poi_root.name = "MaritimePOIs"
	add_child(poi_root)

	poi_hotspots.clear()
	_shipwreck_bulkhead_lights.clear()
	_shipwreck_nodes.clear()
	_shipwreck_base_scales.clear()
	_sea_fort_lantern_lights.clear()
	_sea_fort_lantern_base_pos.clear()
	_leviathan_bio_lights.clear()
	_derelict_lightships.clear()
	_derelict_lightship_base_positions.clear()
	_derelict_lightship_base_yaws.clear()
	_derelict_lightship_beacons.clear()

	var poi_spawn_coords: Array[Vector2] = [
		Vector2(-38.0, -68.0),
		Vector2(42.0, -78.0),
		Vector2(-68.0, -96.0),
		Vector2(64.0, -108.0),
		Vector2(-185.0, -240.0),
		Vector2(220.0, -290.0),
		Vector2(-340.0, -120.0),
		Vector2(380.0, -140.0),
		Vector2(-420.0, 180.0),
		Vector2(460.0, 240.0),
		Vector2(-680.0, -620.0),
		Vector2(740.0, -580.0),
		Vector2(-890.0, 420.0),
		Vector2(920.0, 510.0),
		Vector2(-1150.0, 820.0),
		Vector2(1240.0, -960.0),
		Vector2(-1480.0, -880.0),
		Vector2(1540.0, 920.0),
		Vector2(-1820.0, -1440.0),
		Vector2(1950.0, 1580.0),
	]
	var poi_types_cycle: Array[String] = [
		"shipwreck",
		"sea_fort",
		"leviathan_ribcage",
		"derelict_lightship",
	]

	for p_idx: int in range(poi_spawn_coords.size()):
		var p_xz: Vector2 = poi_spawn_coords[p_idx]
		var p_type: String = poi_types_cycle[p_idx % poi_types_cycle.size()]
		var p_yaw: float = rng.randf_range(0.0, TAU)
		if p_idx == 0:
			p_yaw = deg_to_rad(28.0)
		elif p_idx == 1:
			p_yaw = deg_to_rad(-24.0)
		elif p_idx == 2:
			p_yaw = deg_to_rad(36.0)
		elif p_idx == 3:
			p_yaw = deg_to_rad(-32.0)
		var p_scale: float = 1.0 if p_idx < 4 else rng.randf_range(0.95, 1.28)
		_spawn_nautical_poi_hotspot(
			poi_root,
			"MaritimePOI_%02d_%s" % [p_idx, p_type],
			p_type,
			p_xz,
			p_yaw,
			p_scale
		)


func _spawn_channel_warning_buoys(wharf_root: Node3D) -> void:
	if _scene_rusted_buoy == null:
		return

	_warning_buoys.clear()
	_warning_buoy_lights.clear()
	_warning_buoy_base_positions.clear()

	var channel_buoy_coords: Array[Vector2] = [
		Vector2(-14.0, -32.0),
		Vector2(14.0, -34.0),
		Vector2(-14.5, -75.0),
		Vector2(14.5, -77.0),
		Vector2(-15.0, -120.0),
		Vector2(15.0, -122.0),
	]

	for b_idx: int in range(channel_buoy_coords.size()):
		var xz: Vector2 = channel_buoy_coords[b_idx]
		var buoy_inst: Node3D = _scene_rusted_buoy.instantiate() as Node3D
		if buoy_inst == null:
			continue

		buoy_inst.name = "ChannelWarningBuoy_%02d" % b_idx
		var base_pos: Vector3 = Vector3(xz.x, 0.0, xz.y)
		buoy_inst.position = base_pos
		buoy_inst.rotation = Vector3(0.0, float(b_idx) * 1.15, 0.0)
		wharf_root.add_child(buoy_inst)

		_configure_stylized_landmark_hierarchy(buoy_inst, 1600.0, 90.0)

		var beacon_light: OmniLight3D = OmniLight3D.new()
		beacon_light.name = "WarningBuoyLight_%02d" % b_idx
		beacon_light.position = Vector3(0.0, 2.45, 0.0)
		beacon_light.light_color = Color(1.0, 0.22, 0.14, 1.0)
		beacon_light.light_energy = 1.32
		beacon_light.omni_range = 14.0
		beacon_light.omni_attenuation = 1.15
		beacon_light.light_specular = 1.35
		beacon_light.light_volumetric_fog_energy = 0.65
		buoy_inst.add_child(beacon_light)

		var water_pool_spot: SpotLight3D = SpotLight3D.new()
		water_pool_spot.name = "BuoyWaterPoolSpot_%02d" % b_idx
		water_pool_spot.position = Vector3(0.0, 2.30, 0.0)
		water_pool_spot.rotation_degrees = Vector3(-75.0, 0.0, 0.0)
		water_pool_spot.light_color = Color(1.0, 0.22, 0.14, 1.0)
		water_pool_spot.light_energy = 0.88
		water_pool_spot.spot_range = 8.5
		water_pool_spot.spot_angle = 42.0
		water_pool_spot.spot_attenuation = 1.1
		water_pool_spot.light_specular = 1.2
		water_pool_spot.light_volumetric_fog_energy = 0.45
		buoy_inst.add_child(water_pool_spot)

		_warning_buoys.append(buoy_inst)
		_warning_buoy_lights.append(beacon_light)
		_warning_buoy_base_positions.append(base_pos)


func _spawn_nautical_poi_hotspot(
	parent_node: Node3D,
	node_name: String,
	poi_type: String,
	pos_xz: Vector2,
	yaw_rad: float,
	scale_val: float
) -> void:
	var scene_res: PackedScene = null
	var discovery_title: String = ""
	var habitat_tag: String = "COASTAL REEF"

	if poi_type == "shipwreck":
		scene_res = _scene_poi_shipwreck
		discovery_title = "NEARBY: FOUNDERED STEAMER WRECK — High Reef Activity"
		habitat_tag = "COASTAL REEF"
	elif poi_type == "sea_fort":
		scene_res = _scene_poi_sea_fort
		discovery_title = "NEARBY: ABANDONED STILT WATCHTOWER — Deep Piling Shoals"
		habitat_tag = "COASTAL REEF"
	elif poi_type == "leviathan_ribcage":
		scene_res = _scene_poi_leviathan
		discovery_title = "NEARBY: LEVIATHAN BONE SKERRY — Abyssal Scavengers Detected"
		habitat_tag = "ABYSSAL TRENCH"
	else:
		scene_res = _scene_poi_lightship
		discovery_title = "NEARBY: DERELICT BEACON LIGHTSHIP — Pelagic Predators Below"
		habitat_tag = "OPEN PELAGIC"

	if scene_res == null:
		return

	var inst: Node3D = scene_res.instantiate() as Node3D
	if inst == null:
		return

	inst.name = node_name
	var base_y: float = -1.85 if poi_type == "shipwreck" else 0.0
	var list_roll_rad: float = deg_to_rad(14.0) if poi_type == "shipwreck" else 0.0
	var base_pos: Vector3 = Vector3(pos_xz.x, base_y, pos_xz.y)
	inst.position = base_pos
	inst.rotation = Vector3(0.0, yaw_rad, list_roll_rad)
	inst.scale = Vector3(scale_val, scale_val, scale_val)
	parent_node.add_child(inst)

	_configure_stylized_landmark_hierarchy(inst, 400.0, 60.0)

	if poi_type == "shipwreck":
		var eff_scale: float = scale_val * _shipwreck_scale_multiplier
		inst.scale = Vector3(eff_scale, eff_scale, eff_scale)
		_shipwreck_nodes.append(inst)
		_shipwreck_base_scales.append(scale_val)
		_enforce_matte_shipwreck_materials(inst)
		_attach_shipwreck_hull_collision(inst)

		var bulkhead_light: OmniLight3D = OmniLight3D.new()
		bulkhead_light.name = node_name + "_BulkheadLight"
		bulkhead_light.position = Vector3(1.1, 4.35, 2.2)
		bulkhead_light.light_color = Color(1.0, 0.58, 0.24, 1.0)
		bulkhead_light.light_energy = 2.8
		bulkhead_light.omni_range = 18.0
		bulkhead_light.omni_attenuation = 1.25
		bulkhead_light.light_specular = 1.6
		bulkhead_light.light_volumetric_fog_energy = 0.95
		inst.add_child(bulkhead_light)
		_shipwreck_bulkhead_lights.append(bulkhead_light)

		var bow_hold_light: OmniLight3D = OmniLight3D.new()
		bow_hold_light.name = node_name + "_BowHoldLight"
		bow_hold_light.position = Vector3(-0.6, 3.6, -3.8)
		bow_hold_light.light_color = Color(1.0, 0.54, 0.20, 1.0)
		bow_hold_light.light_energy = 2.2
		bow_hold_light.omni_range = 15.0
		bow_hold_light.omni_attenuation = 1.30
		bow_hold_light.light_specular = 1.4
		bow_hold_light.light_volumetric_fog_energy = 0.75
		inst.add_child(bow_hold_light)
		_shipwreck_bulkhead_lights.append(bow_hold_light)
	elif poi_type == "sea_fort":
		var lantern_light: OmniLight3D = OmniLight3D.new()
		lantern_light.name = node_name + "_WatchtowerLantern"
		var l_pos: Vector3 = Vector3(-2.3, 11.2, 0.0)
		lantern_light.position = l_pos
		lantern_light.light_color = Color(1.0, 0.68, 0.30, 1.0)
		lantern_light.light_energy = 2.5
		lantern_light.omni_range = 18.0
		lantern_light.omni_attenuation = 1.2
		lantern_light.light_specular = 1.5
		lantern_light.light_volumetric_fog_energy = 0.75
		inst.add_child(lantern_light)
		_sea_fort_lantern_lights.append(lantern_light)
		_sea_fort_lantern_base_pos.append(l_pos)
	elif poi_type == "leviathan_ribcage":
		var bio_light: OmniLight3D = OmniLight3D.new()
		bio_light.name = node_name + "_BioMistGlow"
		bio_light.position = Vector3(0.0, 2.45, 0.0)
		bio_light.light_color = Color(0.14, 0.86, 0.72, 1.0)
		bio_light.light_energy = 1.2
		bio_light.omni_range = 15.0
		bio_light.omni_attenuation = 1.3
		bio_light.light_specular = 1.2
		bio_light.light_volumetric_fog_energy = 0.5
		inst.add_child(bio_light)
		_leviathan_bio_lights.append(bio_light)
	else:
		var mast_beacon: OmniLight3D = OmniLight3D.new()
		mast_beacon.name = node_name + "_MastBeacon"
		mast_beacon.position = Vector3(0.0, 6.85, 0.40)
		mast_beacon.light_color = Color(0.95, 0.74, 0.34, 1.0)
		mast_beacon.light_energy = 2.4
		mast_beacon.omni_range = 18.0
		mast_beacon.omni_attenuation = 1.25
		mast_beacon.light_specular = 1.5
		mast_beacon.light_volumetric_fog_energy = 0.75
		inst.add_child(mast_beacon)
		_derelict_lightships.append(inst)
		_derelict_lightship_base_positions.append(base_pos)
		_derelict_lightship_base_yaws.append(yaw_rad)
		_derelict_lightship_beacons.append(mast_beacon)

	if _mesh_foam_ring != null and poi_type != "derelict_lightship" and poi_type != "shipwreck":
		var foam_inst: MeshInstance3D = MeshInstance3D.new()
		foam_inst.name = node_name + "_Foam"
		foam_inst.mesh = _mesh_foam_ring
		foam_inst.position = Vector3(pos_xz.x, 0.15, pos_xz.y)
		foam_inst.rotation = Vector3(0.0, yaw_rad, 0.0)
		var foam_mult: float = 1.75 if poi_type == "shipwreck" else 1.35
		foam_inst.scale = Vector3(foam_mult * scale_val, 0.18, foam_mult * scale_val)
		foam_inst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		foam_inst.visibility_range_end = 400.0
		foam_inst.visibility_range_end_margin = 60.0
		foam_inst.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		parent_node.add_child(foam_inst)

	var poi_entry: Dictionary = {
		"position_xz": pos_xz,
		"poi_type": poi_type,
		"discovery_title": discovery_title,
		"habitat_tag": habitat_tag,
	}
	poi_hotspots.append(poi_entry)


func _enforce_matte_shipwreck_materials(node: Node) -> void:
	if node is MeshInstance3D:
		var mi: MeshInstance3D = node as MeshInstance3D
		if mi.mesh != null:
			var sc: int = mi.mesh.get_surface_count()
			for s_idx: int in range(sc):
				var mat: Material = mi.get_active_material(s_idx)
				if mat is BaseMaterial3D:
					var bmat: BaseMaterial3D = (mat as BaseMaterial3D).duplicate() as BaseMaterial3D
					bmat.roughness = clampf(maxf(bmat.roughness, 0.88), 0.82, 0.96)
					bmat.roughness_texture = null
					bmat.metallic = minf(bmat.metallic, 0.10)
					bmat.metallic_specular = 0.20
					bmat.metallic_texture = null
					bmat.clearcoat_enabled = false
					mi.set_surface_override_material(s_idx, bmat)
	for child: Node in node.get_children():
		_enforce_matte_shipwreck_materials(child)


func _attach_shipwreck_hull_collision(wreck_inst: Node3D) -> void:
	if wreck_inst == null:
		return
	var body: StaticBody3D = StaticBody3D.new()
	body.name = "ShipwreckHullStaticBody"
	wreck_inst.add_child(body)

	# Fitted multi-box hull collider matching the 26m angled wreck footprint (18 deg roll, 12 deg bow-up pitch)
	var main_hull_col: CollisionShape3D = CollisionShape3D.new()
	main_hull_col.name = "MainHullCollider"
	var main_box: BoxShape3D = BoxShape3D.new()
	main_box.size = Vector3(9.4, 8.5, 25.2)
	main_hull_col.shape = main_box
	main_hull_col.position = Vector3(0.5, 1.5, 0.2)
	main_hull_col.rotation_degrees = Vector3(12.0, 0.0, 18.0)
	body.add_child(main_hull_col)

	var bow_prow_col: CollisionShape3D = CollisionShape3D.new()
	bow_prow_col.name = "BowSuperstructureCollider"
	var bow_box: BoxShape3D = BoxShape3D.new()
	bow_box.size = Vector3(7.6, 10.0, 11.5)
	bow_prow_col.shape = bow_box
	bow_prow_col.position = Vector3(0.2, 2.8, -6.2)
	bow_prow_col.rotation_degrees = Vector3(12.0, 0.0, 18.0)
	body.add_child(bow_prow_col)


func set_shipwreck_scale_multiplier(mult: float) -> void:
	_shipwreck_scale_multiplier = clampf(mult, 0.5, 2.5)
	for i: int in range(_shipwreck_nodes.size()):
		var node: Node3D = _shipwreck_nodes[i]
		if node != null and is_instance_valid(node):
			var base_s: float = _shipwreck_base_scales[i] if i < _shipwreck_base_scales.size() else 1.0
			var eff_s: float = base_s * _shipwreck_scale_multiplier
			node.scale = Vector3(eff_s, eff_s, eff_s)


func get_shipwreck_scale_multiplier() -> float:
	return _shipwreck_scale_multiplier


func spawn_custom_shipwreck_ahead(boat_node: Node3D, distance: float = 40.0) -> Node3D:
	if boat_node == null or _scene_poi_shipwreck == null:
		return null

	var fwd_dir: Vector3 = -boat_node.global_transform.basis.z
	fwd_dir.y = 0.0
	if fwd_dir.length_squared() < 0.0001:
		fwd_dir = Vector3.FORWARD
	else:
		fwd_dir = fwd_dir.normalized()

	var spawn_pos: Vector3 = boat_node.global_position + fwd_dir * distance
	spawn_pos.y = -1.85
	# Orient the wreck slightly broadside (38 deg relative to the boat's sightline) so the raised bow,
	# tilted wheelhouse, masts, and Meshy hull textures are dramatically silhouetted in the searchlight
	var boat_yaw: float = boat_node.global_rotation.y
	var wreck_yaw: float = boat_yaw + deg_to_rad(38.0)

	var poi_root: Node3D = get_node_or_null("MaritimePOIs") as Node3D
	if poi_root == null:
		poi_root = self

	if _preview_shipwreck_node != null and is_instance_valid(_preview_shipwreck_node):
		_preview_shipwreck_node.global_position = spawn_pos
		_preview_shipwreck_node.rotation = Vector3(0.0, wreck_yaw, deg_to_rad(14.0))
		var eff_s: float = _shipwreck_scale_multiplier
		_preview_shipwreck_node.scale = Vector3(eff_s, eff_s, eff_s)
		var preview_foam: MeshInstance3D = poi_root.get_node_or_null("PreviewCustomShipwreck_Foam") as MeshInstance3D
		if preview_foam != null:
			preview_foam.global_position = Vector3(spawn_pos.x, 0.15, spawn_pos.z)
			preview_foam.rotation = Vector3(0.0, wreck_yaw, 0.0)
			preview_foam.scale = Vector3(1.75 * eff_s, 0.18, 1.75 * eff_s)
		return _preview_shipwreck_node

	_spawn_nautical_poi_hotspot(
		poi_root,
		"PreviewCustomShipwreck",
		"shipwreck",
		Vector2(spawn_pos.x, spawn_pos.z),
		wreck_yaw,
		1.0
	)
	_preview_shipwreck_node = poi_root.get_node_or_null("PreviewCustomShipwreck") as Node3D
	return _preview_shipwreck_node


func _spawn_random_jagged_rock(
	parent_node: Node3D,
	rng: RandomNumberGenerator,
	pos_xz: Vector2,
	rock_index: int
) -> void:
	var roll: float = rng.randf()
	var rock_scene: PackedScene = _scene_rock_razor
	var vis_range: float = 400.0
	var tilt_max_deg: float = 8.0
	var foam_radius_scale: float = 1.0

	if roll < 0.56:
		rock_scene = _scene_rock_razor
		vis_range = 400.0
		tilt_max_deg = 8.0
		foam_radius_scale = 1.0
	elif roll < 0.78:
		rock_scene = _scene_rock_arch
		vis_range = 400.0
		tilt_max_deg = 3.0
		foam_radius_scale = 1.85
	else:
		rock_scene = _scene_rock_monolith
		vis_range = 400.0
		tilt_max_deg = 6.5
		foam_radius_scale = 1.35

	var scale_val: float = rng.randf_range(0.75, 1.80)
	var yaw_rad: float = rng.randf_range(0.0, TAU)
	var pitch_rad: float = deg_to_rad(rng.randf_range(-tilt_max_deg, tilt_max_deg))
	var roll_rad: float = deg_to_rad(rng.randf_range(-tilt_max_deg, tilt_max_deg))

	_spawn_formation_instance(
		parent_node,
		rock_scene,
		"JaggedRock_%03d" % rock_index,
		pos_xz,
		yaw_rad,
		pitch_rad,
		roll_rad,
		scale_val,
		vis_range,
		true,
		foam_radius_scale * scale_val
	)


func _spawn_formation_instance(
	parent_node: Node3D,
	scene_res: PackedScene,
	node_name: String,
	pos_xz: Vector2,
	yaw_rad: float,
	pitch_rad: float,
	roll_rad: float,
	scale_val: float,
	vis_range_end: float,
	add_foam_ring: bool,
	foam_scale: float
) -> void:
	if scene_res == null:
		return

	var inst: Node3D = scene_res.instantiate() as Node3D
	if inst == null:
		return

	inst.name = node_name
	inst.position = Vector3(pos_xz.x, -1.2, pos_xz.y)
	inst.rotation = Vector3(pitch_rad, yaw_rad, roll_rad)
	inst.scale = Vector3(scale_val, scale_val, scale_val)
	parent_node.add_child(inst)

	_configure_glb_hierarchy(inst, vis_range_end, 60.0, _rock_surface_materials)

	if add_foam_ring and _mesh_foam_ring != null:
		var foam_inst: MeshInstance3D = MeshInstance3D.new()
		foam_inst.name = node_name + "_Foam"
		foam_inst.mesh = _mesh_foam_ring
		foam_inst.position = Vector3(pos_xz.x, 0.15, pos_xz.y)
		foam_inst.rotation = Vector3(0.0, yaw_rad, 0.0)
		foam_inst.scale = Vector3(foam_scale, 0.18, foam_scale)
		foam_inst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		foam_inst.visibility_range_end = 400.0
		foam_inst.visibility_range_end_margin = 60.0
		foam_inst.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		parent_node.add_child(foam_inst)
