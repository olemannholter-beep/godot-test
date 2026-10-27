class_name StormDirector
extends Node3D

const STORM_BUS_NAME: String = "StormAmbience"
const RAIN_OGG_PATH: String = "res://assets/audio/rain_ocean_loop.ogg"
const RAIN_WAV_FALLBACK_PATH: String = "res://assets/audio/rain_ocean_loop.wav"
const THUNDER_OGG_PATH: String = "res://assets/audio/thunder_strike.ogg"
const THUNDER_WAV_FALLBACK_PATH: String = "res://assets/audio/thunder_strike.wav"
const ROLLING_SEA_FOG_SHADER_PATH: String = "res://shaders/rolling_sea_fog.gdshader"

@export var boat: Node3D
@export var ocean: Node3D
@export var sea_fog_banks: FogVolume
@export var rain_system: GPUParticles3D
@export var moonlight: DirectionalLight3D
@export var world_environment: WorldEnvironment
@export var rain_audio: AudioStreamPlayer
@export var thunder_audio: AudioStreamPlayer

@export_group("Tracking")
@export var ocean_snap_step: float = 1.20
@export var rain_height_offset: float = 22.0
@export var fog_height_offset: float = 6.0

@export_group("Volumetric Fog & Sea Mist")
@export var min_volumetric_fog_density: float = 0.006
@export var max_volumetric_fog_density: float = 0.010
@export var fog_weather_cycle_seconds: float = 45.0

@export_group("Lightning")
@export var min_lightning_interval: float = 28.0
@export var max_lightning_interval: float = 65.0
@export var flash_duration: float = 0.35
@export var peak_lightning_energy: float = 2.8
@export var lightning_light_color: Color = Color(0.75, 0.88, 1.0, 1.0)
@export var lightning_fog_emission: Color = Color(0.18, 0.25, 0.32, 1.0)
@export var min_thunder_delay: float = 1.2
@export var max_thunder_delay: float = 3.5

@export_group("Lantern Flicker")
@export var flicker_amplitude: float = 0.04
@export var flicker_speed: float = 3.2

var _base_moon_energy: float = 0.42
var _base_moon_color: Color = Color(0.55, 0.72, 0.88, 1.0)
var _base_fog_emission: Color = Color(0.002, 0.004, 0.006, 1.0)
var _base_fog_emission_energy: float = 0.04
var _fog_density_override: float = -1.0
var _rolling_sea_mist_volume: FogVolume = null
var _sea_mist_shader_mat: ShaderMaterial = null

var _masthead_light: OmniLight3D = null
var _base_masthead_energy: float = 3.2
var _ocean_shader_material: ShaderMaterial = null

var _flicker_noise: FastNoiseLite = FastNoiseLite.new()
var _time_elapsed: float = 0.0

var _lightning_timer: float = 35.0
var _flash_elapsed: float = -1.0
var _thunder_timer: float = -1.0


func _ready() -> void:
	_setup_storm_audio_bus()

	_flicker_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_flicker_noise.seed = 909
	_flicker_noise.frequency = 0.8

	if moonlight != null:
		moonlight.rotation_degrees = Vector3(-12.0, 130.0, 0.0)
		moonlight.light_color = Color(0.55, 0.72, 0.88, 1.0)
		moonlight.light_energy = 0.42
		moonlight.light_specular = 1.35
		moonlight.shadow_enabled = true
		moonlight.shadow_blur = 1.5
		moonlight.light_volumetric_fog_energy = 0.35
		_base_moon_energy = moonlight.light_energy
		_base_moon_color = moonlight.light_color

	_configure_volumetric_environment()
	_configure_rolling_sea_mist_volume()
	_configure_rain_particles()

	if ocean is MeshInstance3D:
		var ocean_mesh_inst: MeshInstance3D = ocean as MeshInstance3D
		if ocean_mesh_inst.mesh != null:
			_ocean_shader_material = ocean_mesh_inst.mesh.surface_get_material(0) as ShaderMaterial

	if boat != null:
		_masthead_light = boat.get_node_or_null("Visuals/MastheadLight") as OmniLight3D
		if _masthead_light != null:
			_base_masthead_energy = _masthead_light.light_energy

	_configure_audio_players()
	_lightning_timer = randf_range(min_lightning_interval, max_lightning_interval)


func set_base_moon_energy(val: float) -> void:
	_base_moon_energy = val
	if moonlight != null and _flash_elapsed < 0.0:
		moonlight.light_energy = val


func set_base_fog_density(val: float) -> void:
	_fog_density_override = clampf(val, 0.0, 0.05)
	min_volumetric_fog_density = _fog_density_override
	max_volumetric_fog_density = _fog_density_override
	if world_environment != null and world_environment.environment != null:
		world_environment.environment.volumetric_fog_density = _fog_density_override


func set_base_fog_emission_energy(val: float) -> void:
	_base_fog_emission_energy = clampf(val, 0.0, 1.0)
	if world_environment != null and world_environment.environment != null and _flash_elapsed < 0.0:
		world_environment.environment.volumetric_fog_emission_energy = _base_fog_emission_energy


func _configure_volumetric_environment() -> void:
	if world_environment == null or world_environment.environment == null:
		return

	var env: Environment = world_environment.environment
	if env.sky != null and env.sky.sky_material is ProceduralSkyMaterial:
		var sky_mat: ProceduralSkyMaterial = env.sky.sky_material as ProceduralSkyMaterial
		sky_mat.sky_top_color = Color(0.004, 0.008, 0.014, 1.0)
		sky_mat.sky_horizon_color = Color(0.015, 0.028, 0.040, 1.0)
		sky_mat.ground_bottom_color = Color(0.002, 0.005, 0.008, 1.0)
		sky_mat.ground_horizon_color = Color(0.010, 0.020, 0.030, 1.0)
		sky_mat.sky_curve = 0.06
		sky_mat.sky_energy_multiplier = 0.35
		sky_mat.sun_angle_max = 3.5
		sky_mat.sun_curve = 0.04
		sky_mat.energy_multiplier = 3.8

	# Ambient Moonlight Floor
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.08, 0.14, 0.20, 1.0)
	env.ambient_light_sky_contribution = 0.0
	env.ambient_light_energy = 0.55

	# ACES Filmic Tonemapping, Atmospheric Softlight Glow, SSAO & SSIL
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.tonemap_exposure = 1.05
	env.tonemap_white = 6.0
	env.glow_enabled = true
	env.glow_intensity = 0.65
	env.glow_strength = 0.95
	env.glow_bloom = 0.08
	env.glow_hdr_threshold = 1.15
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	env.ssao_enabled = true
	env.ssao_radius = 1.2
	env.ssao_intensity = 2.8
	env.ssao_power = 1.8
	env.ssil_enabled = true
	env.ssil_radius = 3.5
	env.ssil_intensity = 1.2

	# Distant aerial depth fog blending smoothly behind the 220m volumetric frustum
	env.fog_enabled = true
	env.fog_light_color = Color(0.008, 0.015, 0.024, 1.0)
	env.fog_density = 0.0045
	env.fog_aerial_perspective = 0.85
	env.fog_sky_affect = 0.0
	env.fog_height = 2.0
	env.fog_height_density = 0.08

	# Brooding dark slate-grey volumetric fog with crisp forward spotlight scattering
	env.volumetric_fog_enabled = true
	env.volumetric_fog_density = 0.0085
	env.volumetric_fog_albedo = Color(0.08, 0.11, 0.14, 1.0)
	env.volumetric_fog_emission = Color(0.002, 0.004, 0.006, 1.0)
	env.volumetric_fog_emission_energy = 0.04
	env.volumetric_fog_anisotropy = 0.42
	env.volumetric_fog_length = 220.0
	env.volumetric_fog_detail_spread = 1.4
	env.volumetric_fog_gi_inject = 0.4
	env.volumetric_fog_ambient_inject = 0.15
	env.volumetric_fog_sky_affect = 0.15
	env.volumetric_fog_temporal_reprojection_enabled = true
	env.volumetric_fog_temporal_reprojection_amount = 0.88

	env.adjustment_enabled = true
	env.adjustment_brightness = 1.0
	env.adjustment_contrast = 1.05

	_base_fog_emission = env.volumetric_fog_emission
	_base_fog_emission_energy = env.volumetric_fog_emission_energy


func _configure_rain_particles() -> void:
	if rain_system == null:
		return
	rain_system.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var pass_mesh: Mesh = rain_system.draw_pass_1
	if pass_mesh != null:
		var mat: Material = pass_mesh.surface_get_material(0)
		if mat is StandardMaterial3D:
			var std_mat: StandardMaterial3D = mat as StandardMaterial3D
			std_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			std_mat.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
			std_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
			std_mat.albedo_color = Color(0.45, 0.52, 0.58, 0.22)
			std_mat.distance_fade_mode = BaseMaterial3D.DISTANCE_FADE_PIXEL_ALPHA
			std_mat.distance_fade_min_distance = 4.0
			std_mat.distance_fade_max_distance = 8.5


func _configure_rolling_sea_mist_volume() -> void:
	if sea_fog_banks != null:
		_rolling_sea_mist_volume = sea_fog_banks
		_rolling_sea_mist_volume.name = "RollingSeaMistVolume"
	else:
		var parent_node: Node = get_parent()
		if parent_node != null:
			var existing: FogVolume = parent_node.get_node_or_null("RollingSeaMistVolume") as FogVolume
			if existing == null:
				existing = parent_node.get_node_or_null("SeaFogBanks") as FogVolume
			_rolling_sea_mist_volume = existing

	if _rolling_sea_mist_volume == null:
		_rolling_sea_mist_volume = FogVolume.new()
		_rolling_sea_mist_volume.name = "RollingSeaMistVolume"
		add_child(_rolling_sea_mist_volume)
		sea_fog_banks = _rolling_sea_mist_volume

	_rolling_sea_mist_volume.shape = RenderingServer.FOG_VOLUME_SHAPE_BOX
	_rolling_sea_mist_volume.size = Vector3(600.0, 18.0, 600.0)
	var target_x: float = boat.global_position.x if boat != null else _rolling_sea_mist_volume.global_position.x
	var target_z: float = boat.global_position.z if boat != null else _rolling_sea_mist_volume.global_position.z
	_rolling_sea_mist_volume.global_position = Vector3(target_x, fog_height_offset, target_z)

	var fog_shader: Shader = null
	if ResourceLoader.exists(ROLLING_SEA_FOG_SHADER_PATH):
		fog_shader = load(ROLLING_SEA_FOG_SHADER_PATH) as Shader
	if fog_shader == null:
		fog_shader = Shader.new()
		fog_shader.code = """
shader_type fog;

float hash3d(vec3 p) {
	p = fract(p * vec3(0.1031, 0.1030, 0.0973));
	p += dot(p, p.yxz + 33.33);
	return fract((p.x + p.y) * p.z);
}

float value_noise_3d(vec3 x) {
	vec3 i = floor(x);
	vec3 f = fract(x);
	vec3 u = f * f * (3.0 - 2.0 * f);

	float n000 = hash3d(i + vec3(0.0, 0.0, 0.0));
	float n100 = hash3d(i + vec3(1.0, 0.0, 0.0));
	float n010 = hash3d(i + vec3(0.0, 1.0, 0.0));
	float n110 = hash3d(i + vec3(1.0, 1.0, 0.0));
	float n001 = hash3d(i + vec3(0.0, 0.0, 1.0));
	float n101 = hash3d(i + vec3(1.0, 0.0, 1.0));
	float n011 = hash3d(i + vec3(0.0, 1.0, 1.0));
	float n111 = hash3d(i + vec3(1.0, 1.0, 1.0));

	float nx00 = mix(n000, n100, u.x);
	float nx10 = mix(n010, n110, u.x);
	float nx01 = mix(n001, n101, u.x);
	float nx11 = mix(n011, n111, u.x);

	float nxy0 = mix(nx00, nx10, u.y);
	float nxy1 = mix(nx01, nx11, u.y);

	return mix(nxy0, nxy1, u.z);
}

void fog() {
	vec3 wind_offset = vec3(TIME * 2.2, 0.0, TIME * 1.4);
	vec3 sample_pos = (WORLD_POSITION.xyz + wind_offset) * vec3(0.032, 0.065, 0.032);

	float octave_1 = value_noise_3d(sample_pos);
	float octave_2 = value_noise_3d(sample_pos * 2.15 + vec3(17.3, -9.1, 31.7));
	float noise_val = octave_1 * 0.65 + octave_2 * 0.35;

	float height_mask = smoothstep(10.0, 0.5, WORLD_POSITION.y) * smoothstep(-4.0, -1.5, WORLD_POSITION.y);
	float billow_mask = smoothstep(0.35, 0.75, noise_val);

	DENSITY = 0.028 * billow_mask * height_mask;
	ALBEDO = vec3(0.32, 0.38, 0.42);
	EMISSION = vec3(0.006, 0.011, 0.014) * billow_mask;
}
"""

	_sea_mist_shader_mat = ShaderMaterial.new()
	_sea_mist_shader_mat.shader = fog_shader
	_rolling_sea_mist_volume.material = _sea_mist_shader_mat


func _setup_storm_audio_bus() -> void:
	var bus_idx: int = AudioServer.get_bus_index(STORM_BUS_NAME)
	if bus_idx == -1:
		AudioServer.add_bus()
		bus_idx = AudioServer.bus_count - 1
		AudioServer.set_bus_name(bus_idx, STORM_BUS_NAME)
		AudioServer.set_bus_send(bus_idx, "Master")

		var lpf: AudioEffectLowPassFilter = AudioEffectLowPassFilter.new()
		lpf.cutoff_hz = 1100.0
		AudioServer.add_bus_effect(bus_idx, lpf)

		var reverb: AudioEffectReverb = AudioEffectReverb.new()
		reverb.room_size = 0.7
		reverb.wet = 0.2
		AudioServer.add_bus_effect(bus_idx, reverb)


func _configure_audio_players() -> void:
	if rain_audio != null:
		var rain_stream: AudioStream = _load_audio_stream(RAIN_OGG_PATH, RAIN_WAV_FALLBACK_PATH)
		if rain_stream is AudioStreamOggVorbis:
			var ogg_rain: AudioStreamOggVorbis = rain_stream as AudioStreamOggVorbis
			ogg_rain.loop = true
		elif rain_stream is AudioStreamWAV:
			var wav_rain: AudioStreamWAV = rain_stream as AudioStreamWAV
			wav_rain.loop_mode = AudioStreamWAV.LOOP_FORWARD
			wav_rain.loop_begin = 0
			wav_rain.loop_end = int(wav_rain.get_length() * float(wav_rain.mix_rate))
		rain_audio.stream = rain_stream
		rain_audio.bus = STORM_BUS_NAME
		rain_audio.volume_db = -12.0
		if not rain_audio.finished.is_connected(_on_rain_audio_finished):
			rain_audio.finished.connect(_on_rain_audio_finished)
		if rain_stream != null and DisplayServer.get_name() != "headless":
			rain_audio.play()

	if thunder_audio != null:
		var thunder_stream: AudioStream = _load_audio_stream(THUNDER_OGG_PATH, THUNDER_WAV_FALLBACK_PATH)
		thunder_audio.stream = thunder_stream
		thunder_audio.bus = STORM_BUS_NAME


func _load_audio_stream(primary_path: String, fallback_path: String) -> AudioStream:
	if ResourceLoader.exists(primary_path):
		return load(primary_path) as AudioStream
	if ResourceLoader.exists(fallback_path):
		return load(fallback_path) as AudioStream
	return null


func _physics_process(delta: float) -> void:
	_time_elapsed += delta
	var synced_time: float = BoatController.get_synced_ocean_time()
	RenderingServer.global_shader_parameter_set("ocean_time", synced_time)
	if _ocean_shader_material != null:
		_ocean_shader_material.set_shader_parameter("wave_time", synced_time)
	_update_infinite_tracking()
	_update_volumetric_fog_cycle()
	_update_lantern_flicker()
	_update_lightning_and_thunder(delta)


func _process(_delta: float) -> void:
	var synced_time: float = BoatController.get_synced_ocean_time()
	RenderingServer.global_shader_parameter_set("ocean_time", synced_time)
	if _ocean_shader_material != null:
		_ocean_shader_material.set_shader_parameter("wave_time", synced_time)


func _update_volumetric_fog_cycle() -> void:
	if world_environment == null or world_environment.environment == null:
		return
	if _fog_density_override >= 0.0:
		world_environment.environment.volumetric_fog_density = _fog_density_override
		return
	var cycle_dur: float = maxf(fog_weather_cycle_seconds, 1.0)
	var cycle_phase: float = (_time_elapsed * TAU) / cycle_dur
	var cycle_t: float = 0.5 + 0.5 * sin(cycle_phase)
	world_environment.environment.volumetric_fog_density = lerpf(
		min_volumetric_fog_density,
		max_volumetric_fog_density,
		cycle_t
	)


func _update_infinite_tracking() -> void:
	if boat == null:
		return

	var boat_pos: Vector3 = boat.global_position

	if ocean != null:
		ocean.global_position = Vector3(
			snappedf(boat_pos.x, ocean_snap_step),
			0.0,
			snappedf(boat_pos.z, ocean_snap_step)
		)

	var active_fog_vol: FogVolume = _rolling_sea_mist_volume if _rolling_sea_mist_volume != null else sea_fog_banks
	if active_fog_vol != null:
		active_fog_vol.global_position = Vector3(
			boat_pos.x,
			fog_height_offset,
			boat_pos.z
		)

	if rain_system != null:
		rain_system.global_position = Vector3(
			boat_pos.x,
			boat_pos.y + rain_height_offset,
			boat_pos.z
		)


func _update_lantern_flicker() -> void:
	var t: float = _time_elapsed * flicker_speed
	if _masthead_light != null:
		var mast_mod: float = 1.0 + _flicker_noise.get_noise_1d(t) * flicker_amplitude
		_masthead_light.light_energy = _base_masthead_energy * mast_mod


func _update_lightning_and_thunder(delta: float) -> void:
	if _flash_elapsed < 0.0:
		_lightning_timer -= delta
		if _lightning_timer <= 0.0:
			_trigger_sheet_lightning()
	else:
		_flash_elapsed += delta
		var total_window: float = flash_duration + 0.45
		if _flash_elapsed >= total_window:
			_flash_elapsed = -1.0
			_apply_lightning_intensity(0.0)
		else:
			var intensity: float = _sample_lightning_envelope(_flash_elapsed)
			_apply_lightning_intensity(intensity)

	if _thunder_timer > 0.0:
		_thunder_timer -= delta
		if _thunder_timer <= 0.0:
			_thunder_timer = -1.0
			if thunder_audio != null and thunder_audio.stream != null:
				thunder_audio.pitch_scale = randf_range(0.8, 1.15)
				thunder_audio.play()


func _trigger_sheet_lightning() -> void:
	_flash_elapsed = 0.0
	_lightning_timer = randf_range(min_lightning_interval, max_lightning_interval)
	_thunder_timer = randf_range(min_thunder_delay, max_thunder_delay)


func _sample_lightning_envelope(t: float) -> float:
	if t < 0.07:
		return sin((t / 0.07) * PI) * 0.85
	elif t < 0.12:
		return 0.12
	elif t < 0.23:
		var p: float = (t - 0.12) / 0.11
		return sin(p * PI) * 1.0
	elif t < 0.27:
		return 0.18
	elif t < flash_duration:
		var p2: float = (t - 0.27) / maxf(flash_duration - 0.27, 0.01)
		return sin(p2 * PI) * 0.65
	else:
		var tail: float = clampf(1.0 - ((t - flash_duration) / 0.45), 0.0, 1.0)
		return tail * tail * 0.22


func _apply_lightning_intensity(intensity: float) -> void:
	var clamped: float = clampf(intensity, 0.0, 1.0)
	if moonlight != null:
		moonlight.light_energy = lerpf(_base_moon_energy, peak_lightning_energy, clamped)
		moonlight.light_color = _base_moon_color.lerp(lightning_light_color, clamped)

	if world_environment != null and world_environment.environment != null:
		world_environment.environment.volumetric_fog_emission = _base_fog_emission.lerp(lightning_fog_emission, clamped)
		world_environment.environment.volumetric_fog_emission_energy = lerpf(_base_fog_emission_energy, 1.35, clamped)


func _exit_tree() -> void:
	_ocean_shader_material = null
	_masthead_light = null
	if rain_audio != null:
		if rain_audio.finished.is_connected(_on_rain_audio_finished):
			rain_audio.finished.disconnect(_on_rain_audio_finished)
		rain_audio.stop()
		rain_audio.stream = null
	if thunder_audio != null:
		thunder_audio.stop()
		thunder_audio.stream = null
	var bus_idx: int = AudioServer.get_bus_index(STORM_BUS_NAME)
	if bus_idx != -1:
		for i: int in range(AudioServer.get_bus_effect_count(bus_idx) - 1, -1, -1):
			AudioServer.remove_bus_effect(bus_idx, i)
		AudioServer.remove_bus(bus_idx)


func _on_rain_audio_finished() -> void:
	if rain_audio != null and rain_audio.stream != null:
		rain_audio.play()
