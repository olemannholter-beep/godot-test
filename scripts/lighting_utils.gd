class_name LightingUtils
extends RefCounted

static var _version_checked: bool = false
static var _area_light_supported: bool = false


static func is_area_light_supported() -> bool:
	if not _version_checked:
		_version_checked = true
		_area_light_supported = ClassDB.class_exists("AreaLight3D")
		if _area_light_supported:
			print("[LightingPipeline] AreaLight3D supported on Godot %s. Rectangular emitters enabled." % Engine.get_version_info()["string"])
		else:
			print("[LightingPipeline] AreaLight3D not supported on Godot %s; falling back to OmniLight3D/SpotLight3D rigs." % Engine.get_version_info()["string"])
	return _area_light_supported


static func create_area_or_omni_light(
	parent: Node3D,
	light_name: String,
	local_pos: Vector3,
	rot_degrees: Vector3,
	rect_size: Vector2,
	color: Color,
	energy: float,
	light_range: float = 40.0,
	shadows: bool = false,
	shadow_blur: float = 1.5,
	fog_energy: float = 1.0,
	distance_fade_begin: float = 350.0
) -> Light3D:
	if parent == null:
		return null

	var light_node: Light3D = null

	if is_area_light_supported():
		var area_inst: Variant = ClassDB.instantiate("AreaLight3D")
		if area_inst is Light3D:
			light_node = area_inst as Light3D
			light_node.name = light_name
			light_node.position = local_pos
			light_node.rotation_degrees = rot_degrees
			light_node.set("area_size", rect_size)
			light_node.set("area_range", light_range)
			light_node.set("area_attenuation", 1.0)
			light_node.light_color = color
			light_node.light_energy = energy
			light_node.shadow_enabled = shadows
			light_node.shadow_blur = shadow_blur
			light_node.light_volumetric_fog_energy = fog_energy
			light_node.distance_fade_enabled = true
			light_node.distance_fade_begin = distance_fade_begin
			light_node.distance_fade_length = 60.0
			light_node.distance_fade_shadow = distance_fade_begin
			parent.add_child(light_node)
			return light_node

	# Fallback for < Godot 4.7
	if rot_degrees != Vector3.ZERO:
		var spot: SpotLight3D = SpotLight3D.new()
		spot.name = light_name
		spot.position = local_pos
		spot.rotation_degrees = rot_degrees
		spot.light_color = color
		spot.light_energy = energy
		spot.spot_range = light_range
		spot.spot_angle = 55.0
		spot.spot_attenuation = 1.15
		spot.shadow_enabled = shadows
		spot.shadow_blur = shadow_blur
		spot.light_volumetric_fog_energy = fog_energy
		spot.distance_fade_enabled = true
		spot.distance_fade_begin = distance_fade_begin
		spot.distance_fade_length = 60.0
		spot.distance_fade_shadow = distance_fade_begin
		parent.add_child(spot)
		light_node = spot
	else:
		var omni: OmniLight3D = OmniLight3D.new()
		omni.name = light_name
		omni.position = local_pos
		omni.light_color = color
		omni.light_energy = energy
		omni.omni_range = light_range
		omni.omni_attenuation = 1.0
		omni.shadow_enabled = shadows
		omni.shadow_blur = shadow_blur
		omni.light_volumetric_fog_energy = fog_energy
		omni.distance_fade_enabled = true
		omni.distance_fade_begin = distance_fade_begin
		omni.distance_fade_length = 60.0
		omni.distance_fade_shadow = distance_fade_begin
		parent.add_child(omni)
		light_node = omni

	return light_node
