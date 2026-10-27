class_name OverheadCamera
extends Camera3D

@export var target: Node3D
@export var target_height_offset: float = 1.2
@export var forward_look_ahead: float = 11.0

@export_group("Orbit Settings")
@export var mouse_sensitivity: float = 0.004
@export var min_pitch_deg: float = -78.0
@export var max_pitch_deg: float = -12.0
@export var orbit_smoothness: float = 10.0

@export_group("Zoom Settings")
@export var default_distance: float = 25.0
@export var min_distance: float = 7.0
@export var max_distance: float = 55.0
@export var zoom_step: float = 3.0
@export var zoom_smoothness: float = 8.0

@export_group("Follow Settings")
@export var follow_smoothness: float = 6.0
@export var fishing_camera_smoothness: float = 10.0
@export var fp_deck_local_offset: Vector3 = Vector3(0.0, 1.95, 1.35)

@export_group("First-Person Look Settings")
@export var fp_mouse_sensitivity: float = 0.0026
@export var fp_max_yaw_deg: float = 115.0
@export var fp_min_pitch_deg: float = -40.0
@export var fp_max_pitch_deg: float = 35.0

@export_group("Camera FOV Settings")
@export var helm_fov: float = 65.0
@export var fp_fishing_fov: float = 85.0

var fishing_camera_active: bool = false
var ui_modal_open: bool = false
var camera_shake_intensity: float = 0.0

var fp_yaw_offset: float = 0.0
var fp_pitch: float = deg_to_rad(-8.0)
var _target_fp_yaw_offset: float = 0.0
var _target_fp_pitch: float = deg_to_rad(-8.0)
var fp_mouse_delta: Vector2 = Vector2.ZERO
var fp_viewmodel_anchor: Node3D = null

var target_yaw: float = 0.0
var current_yaw: float = 0.0
var target_pitch: float = deg_to_rad(-34.0)
var current_pitch: float = deg_to_rad(-34.0)
var target_distance: float = 25.0
var current_distance: float = 25.0
var focus_point: Vector3 = Vector3.ZERO
var _is_orbiting: bool = false
var _was_fishing_active: bool = false
var _shake_time: float = 0.0
var _sway_offset_rot: Vector3 = Vector3.ZERO
var _base_anchor_pos: Vector3 = Vector3(0.32, -0.28, -0.42)


func _ready() -> void:
	far = 3500.0
	near = 0.05
	fov = fp_fishing_fov if fishing_camera_active else helm_fov
	target_pitch = clampf(deg_to_rad(-34.0), deg_to_rad(min_pitch_deg), deg_to_rad(max_pitch_deg))
	current_pitch = target_pitch
	target_distance = clampf(default_distance, min_distance, max_distance)
	current_distance = target_distance

	fp_viewmodel_anchor = Node3D.new()
	fp_viewmodel_anchor.name = "FPViewmodelAnchor"
	fp_viewmodel_anchor.position = _base_anchor_pos
	add_child(fp_viewmodel_anchor)

	if target != null:
		var fwd_dir: Vector3 = -target.global_transform.basis.z
		fwd_dir.y = 0.0
		if fwd_dir.length_squared() > 0.001:
			fwd_dir = fwd_dir.normalized()
		focus_point = target.global_position + fwd_dir * forward_look_ahead + Vector3(0.0, target_height_offset, 0.0)
	var initial_offset: Vector3 = Basis.from_euler(Vector3(current_pitch, current_yaw, 0.0)) * Vector3(0.0, 0.0, current_distance)
	global_position = focus_point + initial_offset
	look_at(focus_point, Vector3.UP)


func reset_fp_angles() -> void:
	_target_fp_yaw_offset = 0.0
	_target_fp_pitch = deg_to_rad(-8.0)
	fp_yaw_offset = 0.0
	fp_pitch = deg_to_rad(-8.0)
	fp_mouse_delta = Vector2.ZERO


func set_helm_fov(deg: float) -> void:
	helm_fov = clampf(deg, 40.0, 100.0)
	if not fishing_camera_active:
		fov = helm_fov


func set_fp_fishing_fov(deg: float) -> void:
	fp_fishing_fov = clampf(deg, 50.0, 115.0)
	if fishing_camera_active:
		fov = fp_fishing_fov


func _unhandled_input(event: InputEvent) -> void:
	if fishing_camera_active:
		if not ui_modal_open and event is InputEventMouseMotion:
			var motion: InputEventMouseMotion = event as InputEventMouseMotion
			fp_mouse_delta = motion.relative
			var max_yaw_rad: float = deg_to_rad(fp_max_yaw_deg)
			_target_fp_yaw_offset = clampf(
				_target_fp_yaw_offset - motion.relative.x * fp_mouse_sensitivity,
				-max_yaw_rad,
				max_yaw_rad
			)
			_target_fp_pitch = clampf(
				_target_fp_pitch - motion.relative.y * fp_mouse_sensitivity,
				deg_to_rad(fp_min_pitch_deg),
				deg_to_rad(fp_max_pitch_deg)
			)
		return

	if event is InputEventMouseButton:
		var mouse_button: InputEventMouseButton = event as InputEventMouseButton
		if mouse_button.button_index == MOUSE_BUTTON_RIGHT or mouse_button.button_index == MOUSE_BUTTON_MIDDLE:
			var rmb_held: bool = Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT)
			var mmb_held: bool = Input.is_mouse_button_pressed(MOUSE_BUTTON_MIDDLE)
			_is_orbiting = mouse_button.pressed or rmb_held or mmb_held
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if _is_orbiting else Input.MOUSE_MODE_VISIBLE
		elif mouse_button.pressed:
			if mouse_button.button_index == MOUSE_BUTTON_WHEEL_UP:
				target_distance = clampf(target_distance - zoom_step, min_distance, max_distance)
			elif mouse_button.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				target_distance = clampf(target_distance + zoom_step, min_distance, max_distance)

	elif event is InputEventMouseMotion and _is_orbiting:
		var mouse_motion: InputEventMouseMotion = event as InputEventMouseMotion
		target_yaw -= mouse_motion.relative.x * mouse_sensitivity
		target_pitch = clampf(
			target_pitch - mouse_motion.relative.y * mouse_sensitivity,
			deg_to_rad(min_pitch_deg),
			deg_to_rad(max_pitch_deg)
		)


func _physics_process(delta: float) -> void:
	if target == null:
		return

	# Sync mouse capture mode & FOV on state transitions
	if fishing_camera_active != _was_fishing_active:
		_was_fishing_active = fishing_camera_active
		if fishing_camera_active:
			fov = fp_fishing_fov
			_is_orbiting = false
			reset_fp_angles()
			if not ui_modal_open and DisplayServer.get_name() != "headless":
				Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		else:
			fov = helm_fov
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

	var desired_fov: float = fp_fishing_fov if fishing_camera_active else helm_fov
	if not is_equal_approx(fov, desired_fov):
		fov = desired_fov

	if fishing_camera_active and DisplayServer.get_name() != "headless":
		var desired_mode: Input.MouseMode = Input.MOUSE_MODE_VISIBLE if ui_modal_open else Input.MOUSE_MODE_CAPTURED
		if Input.mouse_mode != desired_mode:
			Input.mouse_mode = desired_mode

	_shake_time += delta
	var shake_offset: Vector3 = Vector3.ZERO
	if camera_shake_intensity > 0.001:
		shake_offset = Vector3(
			sin(_shake_time * 43.0) * 0.06 + cos(_shake_time * 67.0) * 0.03,
			cos(_shake_time * 51.0) * 0.05 + sin(_shake_time * 37.0) * 0.03,
			sin(_shake_time * 59.0) * 0.04
		) * camera_shake_intensity
		camera_shake_intensity = move_toward(camera_shake_intensity, 0.0, delta * 2.2)

	if fishing_camera_active:
		var deck_parent: Node3D = target.get_node_or_null("Visuals") as Node3D
		if deck_parent == null:
			deck_parent = target

		var desired_pos: Vector3 = deck_parent.global_transform * fp_deck_local_offset + shake_offset
		var pos_blend: float = clampf(fishing_camera_smoothness * delta, 0.0, 1.0)
		global_position = global_position.lerp(desired_pos, pos_blend)

		var look_smooth: float = clampf(16.0 * delta, 0.0, 1.0)
		fp_yaw_offset = lerpf(fp_yaw_offset, _target_fp_yaw_offset, look_smooth)
		fp_pitch = lerpf(fp_pitch, _target_fp_pitch, look_smooth)

		# Default first-person view faces aft over the stern (+Z in boat local space = yaw PI)
		var local_look_basis: Basis = Basis.from_euler(Vector3(fp_pitch, PI + fp_yaw_offset, 0.0))
		# Inherit 35% of deck wave pitch/roll so the horizon feels alive without causing motion sickness
		var boat_yaw_basis: Basis = Basis.from_euler(Vector3(0.0, target.global_rotation.y, 0.0))
		var full_deck_basis: Basis = deck_parent.global_transform.basis.orthonormalized()
		var stabilized_deck_basis: Basis = boat_yaw_basis.slerp(full_deck_basis, 0.35)
		var desired_cam_basis: Basis = (stabilized_deck_basis * local_look_basis).orthonormalized()

		global_transform.basis = global_transform.basis.orthonormalized().slerp(desired_cam_basis, look_smooth)

		# Update first-person viewmodel sway from mouse movement and wave rock
		if fp_viewmodel_anchor != null:
			var target_sway: Vector3 = Vector3(
				clampf(-fp_mouse_delta.y * 0.0018, -0.08, 0.08),
				clampf(-fp_mouse_delta.x * 0.0018, -0.10, 0.10),
				clampf(fp_mouse_delta.x * 0.0022, -0.09, 0.09)
			)
			_sway_offset_rot = _sway_offset_rot.lerp(target_sway, clampf(10.0 * delta, 0.0, 1.0))
			var wave_bob_y: float = sin(_shake_time * 2.4) * 0.008
			fp_viewmodel_anchor.position = _base_anchor_pos + Vector3(0.0, wave_bob_y, 0.0)
			fp_viewmodel_anchor.rotation = _sway_offset_rot
		fp_mouse_delta = fp_mouse_delta.lerp(Vector2.ZERO, clampf(14.0 * delta, 0.0, 1.0))
		return

	current_yaw = lerp_angle(current_yaw, target_yaw, orbit_smoothness * delta)
	current_pitch = lerpf(current_pitch, target_pitch, orbit_smoothness * delta)
	current_distance = lerpf(current_distance, target_distance, zoom_smoothness * delta)

	var fwd_vec: Vector3 = -target.global_transform.basis.z
	fwd_vec.y = 0.0
	if fwd_vec.length_squared() > 0.001:
		fwd_vec = fwd_vec.normalized()
	focus_point = focus_point.lerp(
		target.global_position + fwd_vec * forward_look_ahead + Vector3(0.0, target_height_offset, 0.0),
		follow_smoothness * delta
	)

	var camera_offset: Vector3 = Basis.from_euler(Vector3(current_pitch, current_yaw, 0.0)) * Vector3(0.0, 0.0, current_distance)
	var nav_pos: Vector3 = focus_point + camera_offset + shake_offset
	var nav_blend: float = clampf(fishing_camera_smoothness * 1.4 * delta, 0.0, 1.0)
	global_position = global_position.lerp(nav_pos, nav_blend)
	var nav_dir: Vector3 = focus_point - global_position
	if nav_dir.length_squared() > 0.001:
		var nav_basis: Basis = Basis.looking_at(nav_dir.normalized(), Vector3.UP)
		global_transform.basis = global_transform.basis.orthonormalized().slerp(nav_basis, nav_blend)
