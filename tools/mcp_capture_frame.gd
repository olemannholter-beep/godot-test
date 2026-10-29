class_name MCPCaptureFrame
extends SceneTree

const DEFAULT_SCENE_PATH: String = "res://scenes/overworld.tscn"
const DEFAULT_VIEW_MODE: String = "helm"
const DEFAULT_SETTLE_FRAMES: int = 45
const CAPTURE_DIR: String = "res://.mcp_captures"
const SCREENSHOT_PATH: String = "res://.mcp_captures/latest_frame.png"
const SCENE_STATE_PATH: String = "res://.mcp_captures/scene_state.json"
const SCENE_TREE_PATH: String = "res://.mcp_captures/scene_tree.json"

var _scene_path: String = DEFAULT_SCENE_PATH
var _view_mode: String = DEFAULT_VIEW_MODE
var _target_frames: int = DEFAULT_SETTLE_FRAMES
var _inspect_only: bool = false
var _output_json_path: String = SCENE_STATE_PATH
var _output_png_path: String = SCREENSHOT_PATH
var _frame_count: int = 0
var _scene_root: Node = null
var _preset_applied: bool = false
var _capture_completed: bool = false
var _diagnostics: Array[String] = []


func _initialize() -> void:
	_parse_cli_args()
	_ensure_capture_dir()

	if not _inspect_only and DisplayServer.get_name() != "headless":
		DisplayServer.window_set_size(Vector2i(3840, 2160))
		root.size = Vector2i(3840, 2160)

	var packed: PackedScene = load(_scene_path) as PackedScene
	if packed == null:
		var err_msg: String = "Failed to load PackedScene at path: %s" % _scene_path
		_diagnostics.append(err_msg)
		push_error(err_msg)
		_write_error_report(err_msg)
		quit(1)
		return

	_scene_root = packed.instantiate()
	if _scene_root == null:
		var inst_err: String = "Failed to instantiate PackedScene: %s" % _scene_path
		_diagnostics.append(inst_err)
		push_error(inst_err)
		_write_error_report(inst_err)
		quit(1)
		return

	root.add_child(_scene_root)
	current_scene = _scene_root


func _process(delta: float) -> bool:
	if _capture_completed:
		return true

	_frame_count += 1

	if _scene_root == null:
		return true

	if _inspect_only:
		if _frame_count >= 2:
			_capture_completed = true
			_dump_inspect_scene_tree()
			quit(0)
			return true
		return false

	if _frame_count >= 2:
		_apply_view_preset(_view_mode, delta)

	if _frame_count >= _target_frames:
		_capture_completed = true
		_perform_capture_and_dump()
		quit(0)
		return true

	return false


func _parse_cli_args() -> void:
	var all_args: PackedStringArray = OS.get_cmdline_args()
	var user_args: PackedStringArray = OS.get_cmdline_user_args()
	var combined: Array[String] = []
	for arg: String in all_args:
		combined.append(arg)
	for uarg: String in user_args:
		if not combined.has(uarg):
			combined.append(uarg)

	for arg: String in combined:
		if arg.begins_with("--view="):
			_view_mode = arg.trim_prefix("--view=").strip_edges().to_lower()
		elif arg.begins_with("--preset="):
			_view_mode = arg.trim_prefix("--preset=").strip_edges().to_lower()
		elif arg.begins_with("--frames="):
			var parsed_frames: int = arg.trim_prefix("--frames=").strip_edges().to_int()
			if parsed_frames > 0:
				_target_frames = parsed_frames
		elif arg.begins_with("--scene="):
			var sp: String = arg.trim_prefix("--scene=").strip_edges()
			if not sp.is_empty():
				_scene_path = sp
		elif arg == "--inspect-only":
			_inspect_only = true
		elif arg.begins_with("--inspect-scene="):
			var isp: String = arg.trim_prefix("--inspect-scene=").strip_edges()
			if not isp.is_empty():
				_scene_path = isp
			_inspect_only = true
			_output_json_path = SCENE_TREE_PATH
		elif arg.begins_with("--output-json="):
			var ojp: String = arg.trim_prefix("--output-json=").strip_edges()
			if not ojp.is_empty():
				_output_json_path = ojp
		elif arg.begins_with("--output-png="):
			var opp: String = arg.trim_prefix("--output-png=").strip_edges()
			if not opp.is_empty():
				_output_png_path = opp
		elif arg.begins_with("--out="):
			var out_p: String = arg.trim_prefix("--out=").strip_edges()
			if not out_p.is_empty():
				_output_png_path = out_p


func _ensure_capture_dir() -> void:
	var abs_dir: String = ProjectSettings.globalize_path(CAPTURE_DIR)
	if not DirAccess.dir_exists_absolute(abs_dir):
		var err: Error = DirAccess.make_dir_recursive_absolute(abs_dir)
		if err != OK:
			_diagnostics.append("Could not create capture directory %s (error %d)" % [abs_dir, int(err)])


func _get_named_view_png_path(mode: String) -> String:
	match mode:
		"fishing":
			return "res://.mcp_captures/godot_fishing.png"
		"first_person", "fp", "deck", "aft":
			return "res://.mcp_captures/godot_first_person.png"
		"overhead":
			return "res://.mcp_captures/godot_overhead.png"
		"harbor_ui", "harbor", "ui":
			return "res://.mcp_captures/godot_harbor_ui.png"
		"bow_light", "bow", "searchlight":
			return "res://.mcp_captures/godot_bow_light.png"
		"shipwreck", "wreck":
			return "res://.mcp_captures/godot_shipwreck.png"
		"wave_probes", "probes":
			return "res://.mcp_captures/godot_wave_probes.png"
		"enemies_aggro", "enemies":
			return "res://.mcp_captures/godot_enemies_aggro.png"
		"harbor_overview", "lighthouse":
			return "res://.mcp_captures/godot_harbor_overview.png"
		"fjord_gate":
			return "res://.mcp_captures/verify_fjord_gate_teleport.png"
		"terraced_hamlet":
			return "res://.mcp_captures/verify_terraced_hamlet_teleport.png"
		"stilt_sanctuary":
			return "res://.mcp_captures/verify_stilt_sanctuary_teleport.png"
		_:
			return "res://.mcp_captures/godot_helm.png"


func _apply_view_preset(mode: String, delta: float) -> void:
	if _scene_root == null:
		return

	var boat: Node3D = _scene_root.get_node_or_null("Boat") as Node3D
	var cam: OverheadCamera = _scene_root.get_node_or_null("Camera3D") as OverheadCamera
	var harbor_ui: HarborUI = _scene_root.get_node_or_null("HarborUI") as HarborUI
	var fishing_ctrl: FishingController = null
	if boat != null:
		fishing_ctrl = boat.get_node_or_null("FishingController") as FishingController

	match mode:
		"first_person", "fp", "deck", "fishing", "aft":
			if not _preset_applied:
				_preset_applied = true
				if harbor_ui != null:
					harbor_ui._set_modal_open(false)
				if boat != null:
					boat.global_position = Vector3(0.0, boat.global_position.y, 4.0)
					boat.rotation.y = deg_to_rad(131.0)
				if fishing_ctrl != null:
					fishing_ctrl._enter_first_person_deck_mode()
					fishing_ctrl.state = FishingController.FishingState.STATE_WAITING_BITE
					fishing_ctrl._in_strike_window = false
					fishing_ctrl._nibbles_remaining = 99
					fishing_ctrl._bite_eval_timer = 99.0
					var aft_dir: Vector3 = boat.global_transform.basis.z if boat != null else Vector3.BACK
					aft_dir.y = 0.0
					if aft_dir.length_squared() > 0.001:
						aft_dir = aft_dir.normalized()
					var bob_pos: Vector3 = (boat.global_position if boat != null else Vector3.ZERO) + aft_dir * 11.5 + Vector3(0.0, 0.12, 0.0)
					fishing_ctrl._bobber_world_pos = bob_pos
					if fishing_ctrl._bobber_node != null:
						fishing_ctrl._bobber_node.global_position = bob_pos
						fishing_ctrl._bobber_node.visible = true
				elif cam != null:
					cam.fishing_camera_active = true
					cam.reset_fp_angles()
			if cam != null and boat != null:
				cam.fp_pitch = deg_to_rad(-6.0)
				cam._target_fp_pitch = deg_to_rad(-6.0)
				var deck_parent: Node3D = boat.get_node_or_null("Visuals") as Node3D
				if deck_parent == null:
					deck_parent = boat
				cam.global_position = deck_parent.global_transform * cam.fp_deck_local_offset
				var local_look_basis: Basis = Basis.from_euler(Vector3(cam.fp_pitch, PI + cam.fp_yaw_offset, 0.0))
				var boat_yaw_basis: Basis = Basis.from_euler(Vector3(0.0, boat.global_rotation.y, 0.0))
				var full_deck_basis: Basis = deck_parent.global_transform.basis.orthonormalized()
				var stabilized_deck_basis: Basis = boat_yaw_basis.slerp(full_deck_basis, 0.35)
				cam.global_transform.basis = (stabilized_deck_basis * local_look_basis).orthonormalized()
				if fishing_ctrl != null:
					fishing_ctrl._in_strike_window = false
					fishing_ctrl._nibbles_remaining = 99
					fishing_ctrl._update_rod_viewmodel_articulation(delta)
					fishing_ctrl._update_3d_fishing_line()

		"harbor_ui", "harbor", "ui":
			if not _preset_applied:
				_preset_applied = true
				if fishing_ctrl != null:
					fishing_ctrl._exit_to_navigation_helm()
				if harbor_ui != null:
					harbor_ui._active_tab = 0
					harbor_ui._set_modal_open(true)

		"bow_light", "bow", "searchlight":
			if not _preset_applied:
				_preset_applied = true
				if harbor_ui != null:
					harbor_ui._set_modal_open(false)
				if fishing_ctrl != null:
					fishing_ctrl._exit_to_navigation_helm()
			if cam != null and boat != null:
				cam.fishing_camera_active = false
				cam.target_yaw = deg_to_rad(142.0)
				cam.current_yaw = cam.target_yaw
				cam.target_pitch = deg_to_rad(-20.0)
				cam.current_pitch = cam.target_pitch
				cam.target_distance = 16.0
				cam.current_distance = cam.target_distance
				cam.focus_point = boat.global_position + Vector3(0.0, 1.4, -3.5)
				var offset: Vector3 = Basis.from_euler(Vector3(cam.current_pitch, cam.current_yaw, 0.0)) * Vector3(0.0, 0.0, cam.current_distance)
				cam.global_position = cam.focus_point + offset
				cam.look_at(cam.focus_point, Vector3.UP)

		"overhead":
			if not _preset_applied:
				_preset_applied = true
				if harbor_ui != null:
					harbor_ui._set_modal_open(false)
				if fishing_ctrl != null:
					fishing_ctrl._exit_to_navigation_helm()
			if cam != null and boat != null:
				cam.fishing_camera_active = false
				cam.target_yaw = deg_to_rad(28.0)
				cam.current_yaw = cam.target_yaw
				cam.target_pitch = deg_to_rad(-42.0)
				cam.current_pitch = cam.target_pitch
				cam.target_distance = 9.5
				cam.current_distance = cam.target_distance
				cam.focus_point = boat.global_position + Vector3(0.0, 1.1, 0.0)
				var oh_offset: Vector3 = Basis.from_euler(Vector3(cam.current_pitch, cam.current_yaw, 0.0)) * Vector3(0.0, 0.0, cam.current_distance)
				cam.global_position = cam.focus_point + oh_offset
				cam.look_at(cam.focus_point, Vector3.UP)

		"shipwreck", "wreck", "harbor_and_wreck":
			if not _preset_applied:
				_preset_applied = true
				if harbor_ui != null:
					harbor_ui._set_modal_open(false)
				if fishing_ctrl != null:
					fishing_ctrl._exit_to_navigation_helm()
				if mode == "harbor_and_wreck" and boat != null:
					boat.global_position = Vector3(0.0, boat.global_position.y, -18.0)
					boat.rotation = Vector3(0.0, deg_to_rad(22.0), 0.0)
				var wb: WorldBuilder = _scene_root.get_node_or_null("WorldBuilder") as WorldBuilder
				if wb != null and boat != null:
					wb.spawn_custom_shipwreck_ahead(boat, 34.0)
			if cam != null and boat != null:
				cam.fishing_camera_active = false
				cam.target_yaw = deg_to_rad(-12.0) if mode == "harbor_and_wreck" else 0.0
				cam.current_yaw = cam.target_yaw
				cam.target_pitch = deg_to_rad(-22.0)
				cam.current_pitch = cam.target_pitch
				cam.target_distance = 26.0
				cam.current_distance = cam.target_distance
				var fwd_vec_w: Vector3 = -boat.global_transform.basis.z
				fwd_vec_w.y = 0.0
				if fwd_vec_w.length_squared() > 0.001:
					fwd_vec_w = fwd_vec_w.normalized()
				cam.focus_point = boat.global_position + fwd_vec_w * 18.0 + Vector3(2.0, 1.4, 0.0)
				var wreck_offset: Vector3 = Basis.from_euler(Vector3(cam.current_pitch, cam.current_yaw, 0.0)) * Vector3(0.0, 0.0, cam.current_distance)
				cam.global_position = cam.focus_point + wreck_offset
				cam.look_at(cam.focus_point, Vector3.UP)

		"wave_probes", "probes":
			if not _preset_applied:
				_preset_applied = true
				if harbor_ui != null:
					harbor_ui._set_modal_open(false)
				if fishing_ctrl != null:
					fishing_ctrl._exit_to_navigation_helm()
				if boat is BoatController:
					var bc_probes: BoatController = boat as BoatController
					bc_probes.set_debug_wave_probes_visible(true)
			if cam != null and boat != null:
				cam.fishing_camera_active = false
				cam.target_yaw = deg_to_rad(52.0)
				cam.current_yaw = cam.target_yaw
				cam.target_pitch = deg_to_rad(-22.0)
				cam.current_pitch = cam.target_pitch
				cam.target_distance = 8.5
				cam.current_distance = cam.target_distance
				cam.focus_point = boat.global_position + Vector3(0.0, 0.35, 0.0)
				var probe_offset: Vector3 = Basis.from_euler(Vector3(cam.current_pitch, cam.current_yaw, 0.0)) * Vector3(0.0, 0.0, cam.current_distance)
				cam.global_position = cam.focus_point + probe_offset
				cam.look_at(cam.focus_point, Vector3.UP)

		"enemies_aggro", "enemies":
			if not _preset_applied:
				_preset_applied = true
				if harbor_ui != null:
					harbor_ui._set_modal_open(false)
				if fishing_ctrl != null:
					fishing_ctrl._exit_to_navigation_helm()
				if boat != null:
					boat.global_position = Vector3(0.0, boat.global_position.y, -260.0)
					boat.rotation = Vector3.ZERO
				var threat_dir: RoamingThreatDirector = _scene_root.get_node_or_null("RoamingThreatDirector") as RoamingThreatDirector
				if threat_dir != null:
					threat_dir.set_threats_enabled(true)
					var tr_node: Node3D = threat_dir.spawn_ghost_trawler_ahead(25.0)
					var lv_node: Node3D = threat_dir.spawn_leviathan_ahead(24.0)
					if tr_node != null:
						tr_node.global_position = Vector3(-6.5, 0.0, -284.0)
						tr_node.rotation.y = deg_to_rad(-142.0)
					if lv_node != null:
						lv_node.global_position = Vector3(5.5, 0.0, -282.0)
						lv_node.rotation.y = deg_to_rad(138.0)
			if cam != null and boat != null:
				cam.fishing_camera_active = false
				cam.target_yaw = deg_to_rad(18.0)
				cam.current_yaw = cam.target_yaw
				cam.target_pitch = deg_to_rad(-25.0)
				cam.current_pitch = cam.target_pitch
				cam.target_distance = 28.0
				cam.current_distance = cam.target_distance
				cam.focus_point = boat.global_position + Vector3(1.5, 1.8, -22.0)
				var enemy_offset: Vector3 = Basis.from_euler(Vector3(cam.current_pitch, cam.current_yaw, 0.0)) * Vector3(0.0, 0.0, cam.current_distance)
				cam.global_position = cam.focus_point + enemy_offset
				cam.look_at(cam.focus_point, Vector3.UP)

		"harbor_overview", "lighthouse":
			if not _preset_applied:
				_preset_applied = true
				if harbor_ui != null:
					harbor_ui._set_modal_open(false)
				if fishing_ctrl != null:
					fishing_ctrl._exit_to_navigation_helm()
			if cam != null:
				cam.fishing_camera_active = false
				cam.focus_point = Vector3(0.0, 15.0, 42.0)
				cam.global_position = Vector3(24.0, 26.0, 2.0)
				cam.look_at(cam.focus_point, Vector3.UP)

		"fjord_gate", "terraced_hamlet", "stilt_sanctuary":
			if not _preset_applied:
				_preset_applied = true
				if harbor_ui != null:
					harbor_ui._set_modal_open(false)
				if fishing_ctrl != null:
					fishing_ctrl._exit_to_navigation_helm()
				if boat is BoatController:
					var bc_tp: BoatController = boat as BoatController
					if mode == "fjord_gate":
						bc_tp.teleport_to_landmark(2)
					elif mode == "terraced_hamlet":
						bc_tp.teleport_to_landmark(3)
					else:
						bc_tp.teleport_to_landmark(4)
			if cam != null and boat != null:
				cam.fishing_camera_active = false
				cam.target_yaw = boat.rotation.y
				cam.current_yaw = boat.rotation.y
				cam.target_pitch = deg_to_rad(-16.0)
				cam.current_pitch = cam.target_pitch
				cam.target_distance = 22.0
				cam.current_distance = cam.target_distance
				var fwd_tp: Vector3 = -boat.global_transform.basis.z
				fwd_tp.y = 0.0
				if fwd_tp.length_squared() > 0.001:
					fwd_tp = fwd_tp.normalized()
				cam.focus_point = boat.global_position + fwd_tp * 14.0 + Vector3(0.0, 3.8, 0.0)
				var tp_offset: Vector3 = Basis.from_euler(Vector3(cam.current_pitch, cam.current_yaw, 0.0)) * Vector3(0.0, 0.0, cam.current_distance)
				cam.global_position = cam.focus_point + tp_offset
				cam.look_at(cam.focus_point, Vector3.UP)

		_:
			# Default "helm" navigation view
			if not _preset_applied:
				_preset_applied = true
				if harbor_ui != null:
					harbor_ui._set_modal_open(false)
				if fishing_ctrl != null:
					fishing_ctrl._exit_to_navigation_helm()
			if cam != null and boat != null:
				cam.fishing_camera_active = false
				cam.target_yaw = 0.0
				cam.current_yaw = 0.0
				cam.target_pitch = deg_to_rad(-34.0)
				cam.current_pitch = cam.target_pitch
				cam.target_distance = 25.0
				cam.current_distance = cam.target_distance
				var fwd_vec: Vector3 = -boat.global_transform.basis.z
				fwd_vec.y = 0.0
				if fwd_vec.length_squared() > 0.001:
					fwd_vec = fwd_vec.normalized()
				cam.focus_point = boat.global_position + fwd_vec * cam.forward_look_ahead + Vector3(0.0, cam.target_height_offset, 0.0)
				var helm_offset: Vector3 = Basis.from_euler(Vector3(cam.current_pitch, cam.current_yaw, 0.0)) * Vector3(0.0, 0.0, cam.current_distance)
				cam.global_position = cam.focus_point + helm_offset
				cam.look_at(cam.focus_point, Vector3.UP)
				var _unused_delta: float = delta


func _perform_capture_and_dump() -> void:
	var screenshot_saved: bool = false
	var img_width: int = 0
	var img_height: int = 0

	if DisplayServer.get_name() != "headless":
		RenderingServer.force_draw(false)
		var vp_tex: ViewportTexture = root.get_texture()
		if vp_tex != null:
			var img: Image = vp_tex.get_image()
			if img != null and not img.is_empty():
				img_width = img.get_width()
				img_height = img.get_height()
				var save_err: Error = img.save_png(_output_png_path)
				if save_err == OK:
					screenshot_saved = true
					var named_view_path: String = _get_named_view_png_path(_view_mode)
					if not named_view_path.is_empty() and named_view_path != _output_png_path:
						img.save_png(named_view_path)
				else:
					_diagnostics.append("Failed to save PNG to %s (Error %d)" % [_output_png_path, int(save_err)])
			else:
				_diagnostics.append("Viewport texture image was null or empty.")
		else:
			_diagnostics.append("Viewport texture was null.")
	else:
		_diagnostics.append("Running with headless DisplayServer; viewport image capture requires non-headless GPU rendering.")

	var state_dict: Dictionary = _build_scene_state_summary(screenshot_saved, img_width, img_height)
	_save_json_file(_output_json_path, state_dict)


func _build_scene_state_summary(screenshot_saved: bool, img_w: int, img_h: int) -> Dictionary:
	var lights_list: Array[Dictionary] = []
	var nodes_list: Array[Dictionary] = []
	var ui_controls: Array[Dictionary] = []
	var env_summary: Dictionary = {}
	var camera_summary: Dictionary = {}

	if _scene_root != null:
		_collect_scene_telemetry(_scene_root, lights_list, nodes_list, ui_controls)
		env_summary = _extract_environment_summary(_scene_root)
		camera_summary = _extract_camera_summary(_scene_root)

	return {
		"timestamp": Time.get_datetime_string_from_system(true),
		"scene_path": _scene_path,
		"view_mode": _view_mode,
		"frames_settled": _frame_count,
		"screenshot_saved": screenshot_saved,
		"screenshot_path": _output_png_path,
		"screenshot_global_path": ProjectSettings.globalize_path(_output_png_path),
		"viewport_size": [img_w if img_w > 0 else root.size.x, img_h if img_h > 0 else root.size.y],
		"display_server": DisplayServer.get_name(),
		"rendering_device": RenderingServer.get_video_adapter_name(),
		"active_camera": camera_summary,
		"environment": env_summary,
		"lights_count": lights_list.size(),
		"lights": lights_list,
		"ui_controls": ui_controls,
		"active_nodes_count": nodes_list.size(),
		"nodes": nodes_list,
		"diagnostics": _diagnostics,
	}


func _collect_scene_telemetry(
	node: Node,
	lights_list: Array[Dictionary],
	nodes_list: Array[Dictionary],
	ui_controls: Array[Dictionary]
) -> void:
	var node_path_str: String = String(_scene_root.get_path_to(node)) if _scene_root != null else node.name
	var script_res: Script = node.get_script() as Script
	var script_path: String = script_res.resource_path if script_res != null else ""

	var node_entry: Dictionary = {
		"name": node.name,
		"path": node_path_str,
		"type": node.get_class(),
	}
	if not script_path.is_empty():
		node_entry["script"] = script_path

	if node is Node3D:
		var n3d: Node3D = node as Node3D
		node_entry["visible"] = n3d.is_visible_in_tree()
		node_entry["global_position"] = _vec3_to_array(n3d.global_position)
		node_entry["global_rotation_deg"] = _vec3_to_array(n3d.global_rotation_degrees)
		node_entry["scale"] = _vec3_to_array(n3d.scale)

	if node is Light3D:
		var light: Light3D = node as Light3D
		var light_info: Dictionary = {
			"name": light.name,
			"path": node_path_str,
			"type": light.get_class(),
			"visible": light.is_visible_in_tree(),
			"light_energy": snappedf(light.light_energy, 0.001),
			"light_volumetric_fog_energy": snappedf(light.light_volumetric_fog_energy, 0.001),
			"light_specular": snappedf(light.light_specular, 0.001),
			"light_color": _color_to_array(light.light_color),
			"shadow_enabled": light.shadow_enabled,
			"global_position": _vec3_to_array(light.global_position),
			"global_rotation_deg": _vec3_to_array(light.global_rotation_degrees),
		}
		if light is SpotLight3D:
			var spot: SpotLight3D = light as SpotLight3D
			light_info["spot_range"] = snappedf(spot.spot_range, 0.01)
			light_info["spot_angle"] = snappedf(spot.spot_angle, 0.01)
		elif light is OmniLight3D:
			var omni: OmniLight3D = light as OmniLight3D
			light_info["omni_range"] = snappedf(omni.omni_range, 0.01)
		lights_list.append(light_info)

	if node is MeshInstance3D:
		var mi: MeshInstance3D = node as MeshInstance3D
		if mi.mesh == null:
			_diagnostics.append("MeshInstance3D '%s' has null mesh." % node_path_str)
		else:
			var mat: Material = mi.get_active_material(0)
			if mat is ShaderMaterial:
				var smat: ShaderMaterial = mat as ShaderMaterial
				if smat.shader == null:
					_diagnostics.append("ShaderMaterial on '%s' has null shader." % node_path_str)
				else:
					node_entry["shader"] = smat.shader.resource_path

	if node is Control:
		var ctrl: Control = node as Control
		if ctrl.is_visible_in_tree() and (ctrl.get_parent() is CanvasLayer or ctrl is PanelContainer):
			ui_controls.append({
				"name": ctrl.name,
				"path": node_path_str,
				"type": ctrl.get_class(),
				"rect_position": [snappedf(ctrl.global_position.x, 0.1), snappedf(ctrl.global_position.y, 0.1)],
				"rect_size": [snappedf(ctrl.size.x, 0.1), snappedf(ctrl.size.y, 0.1)],
			})

	# Keep nodes_list concise by recording top-level/landmark/scripted/light/camera nodes
	var depth: int = node_path_str.count("/")
	if depth <= 2 or not script_path.is_empty() or node is Light3D or node is Camera3D or node is CanvasLayer or node is FogVolume:
		nodes_list.append(node_entry)

	for child: Node in node.get_children():
		_collect_scene_telemetry(child, lights_list, nodes_list, ui_controls)


func _extract_environment_summary(scene_node: Node) -> Dictionary:
	var we: WorldEnvironment = scene_node.get_node_or_null("WorldEnvironment") as WorldEnvironment
	if we == null or we.environment == null:
		return {}
	var env: Environment = we.environment
	return {
		"tonemap_mode": env.tonemap_mode,
		"tonemap_exposure": snappedf(env.tonemap_exposure, 0.001),
		"ambient_light_energy": snappedf(env.ambient_light_energy, 0.001),
		"ambient_light_color": _color_to_array(env.ambient_light_color),
		"ssr_enabled": env.ssr_enabled,
		"glow_enabled": env.glow_enabled,
		"glow_intensity": snappedf(env.glow_intensity, 0.001),
		"fog_enabled": env.fog_enabled,
		"fog_density": snappedf(env.fog_density, 0.0001),
		"volumetric_fog_enabled": env.volumetric_fog_enabled,
		"volumetric_fog_density": snappedf(env.volumetric_fog_density, 0.0001),
		"volumetric_fog_albedo": _color_to_array(env.volumetric_fog_albedo),
		"volumetric_fog_anisotropy": snappedf(env.volumetric_fog_anisotropy, 0.001),
		"volumetric_fog_length": snappedf(env.volumetric_fog_length, 0.1),
	}


func _extract_camera_summary(scene_node: Node) -> Dictionary:
	var cam: Camera3D = root.get_camera_3d()
	if cam == null:
		cam = scene_node.get_node_or_null("Camera3D") as Camera3D
	if cam == null:
		return {}
	var info: Dictionary = {
		"name": cam.name,
		"path": String(scene_node.get_path_to(cam)),
		"global_position": _vec3_to_array(cam.global_position),
		"global_rotation_deg": _vec3_to_array(cam.global_rotation_degrees),
		"fov": snappedf(cam.fov, 0.1),
		"near": snappedf(cam.near, 0.001),
		"far": snappedf(cam.far, 0.1),
	}
	if cam is OverheadCamera:
		var ocam: OverheadCamera = cam as OverheadCamera
		info["fishing_camera_active"] = ocam.fishing_camera_active
		info["ui_modal_open"] = ocam.ui_modal_open
		info["current_distance"] = snappedf(ocam.current_distance, 0.01)
	return info


func _dump_inspect_scene_tree() -> void:
	if _scene_root == null:
		return
	var tree_data: Dictionary = {
		"scene_path": _scene_path,
		"timestamp": Time.get_datetime_string_from_system(true),
		"root": _serialize_node_recursive(_scene_root, 0, 6),
	}
	_save_json_file(_output_json_path, tree_data)


func _serialize_node_recursive(node: Node, depth: int, max_depth: int) -> Dictionary:
	var script_res: Script = node.get_script() as Script
	var script_path: String = script_res.resource_path if script_res != null else ""

	var data: Dictionary = {
		"name": node.name,
		"type": node.get_class(),
		"path": String(_scene_root.get_path_to(node)) if _scene_root != null else node.name,
	}
	if not node.scene_file_path.is_empty():
		data["instance_scene"] = node.scene_file_path
	if not script_path.is_empty():
		data["script"] = script_path
		data["exported_properties"] = _extract_exported_properties(node)

	var groups: Array[String] = []
	for g: StringName in node.get_groups():
		var gs: String = String(g)
		if not gs.begins_with("_"):
			groups.append(gs)
	if not groups.is_empty():
		data["groups"] = groups

	if node is Node3D:
		var n3d: Node3D = node as Node3D
		data["position"] = _vec3_to_array(n3d.position)
		data["rotation_deg"] = _vec3_to_array(n3d.rotation_degrees)
		data["scale"] = _vec3_to_array(n3d.scale)
		data["visible"] = n3d.visible

	if node is Light3D:
		var l3d: Light3D = node as Light3D
		data["light_energy"] = snappedf(l3d.light_energy, 0.001)
		data["light_volumetric_fog_energy"] = snappedf(l3d.light_volumetric_fog_energy, 0.001)
		data["light_color"] = _color_to_array(l3d.light_color)

	if depth < max_depth:
		var children_arr: Array[Dictionary] = []
		for child: Node in node.get_children():
			children_arr.append(_serialize_node_recursive(child, depth + 1, max_depth))
		if not children_arr.is_empty():
			data["children"] = children_arr
	elif node.get_child_count() > 0:
		data["child_count_truncated"] = node.get_child_count()

	return data


func _extract_exported_properties(node: Node) -> Dictionary:
	var result: Dictionary = {}
	var prop_list: Array[Dictionary] = node.get_property_list()
	for prop: Dictionary in prop_list:
		var usage: int = prop.get("usage", 0) as int
		var prop_name: String = prop.get("name", "") as String
		if prop_name.is_empty() or prop_name.begins_with("_"):
			continue
		var is_script_var: bool = (usage & PROPERTY_USAGE_SCRIPT_VARIABLE) != 0
		var is_editor: bool = (usage & PROPERTY_USAGE_EDITOR) != 0
		if is_script_var and is_editor:
			var val: Variant = node.get(prop_name)
			result[prop_name] = _variant_to_json_safe(val)
	return result


func _variant_to_json_safe(val: Variant) -> Variant:
	if val == null:
		return null
	if val is bool or val is int or val is float or val is String:
		return val
	if val is StringName or val is NodePath:
		return String(val)
	if val is Vector2:
		var v2: Vector2 = val as Vector2
		return [snappedf(v2.x, 0.001), snappedf(v2.y, 0.001)]
	if val is Vector3:
		return _vec3_to_array(val as Vector3)
	if val is Color:
		return _color_to_array(val as Color)
	if val is Node:
		var n: Node = val as Node
		return String(_scene_root.get_path_to(n)) if (_scene_root != null and n.is_inside_tree()) else n.name
	if val is Resource:
		var res: Resource = val as Resource
		return res.resource_path if not res.resource_path.is_empty() else res.get_class()
	return str(val)


func _vec3_to_array(v: Vector3) -> Array[float]:
	return [snappedf(v.x, 0.001), snappedf(v.y, 0.001), snappedf(v.z, 0.001)]


func _color_to_array(c: Color) -> Array[float]:
	return [snappedf(c.r, 0.001), snappedf(c.g, 0.001), snappedf(c.b, 0.001), snappedf(c.a, 0.001)]


func _write_error_report(err_msg: String) -> void:
	var report: Dictionary = {
		"timestamp": Time.get_datetime_string_from_system(true),
		"scene_path": _scene_path,
		"error": err_msg,
		"diagnostics": _diagnostics,
	}
	_save_json_file(_output_json_path, report)


func _save_json_file(path: String, payload: Dictionary) -> void:
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(payload, "\t"))
		file.close()
