class_name HarborUI
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

const WHARF_DOCK_POS_XZ: Vector2 = Vector2(0.0, 2.0)
const DOCK_INTERACT_RADIUS: float = 45.0

@export var boat: Node3D

var _fishing_controller: FishingController = null
var _sonar: SonarSystem = null
var _is_open: bool = false
var _active_tab: int = 0 # 0 = Cannery & Shipwright, 1 = Dredged Species Encyclopedia
var _near_wharf_dock: bool = false
var _boiler_level: int = 1

var _backdrop_vignette: Control = null
var _dock_prompt_panel: PanelContainer = null
var _dock_prompt_label: Label = null
var _dock_prompt_drawer: Control = null

var _main_modal: PanelContainer = null
var _modal_frame_drawer: Control = null
var _header_balance_label: Label = null
var _header_hold_label: Label = null
var _tab_market_btn: Button = null
var _tab_log_btn: Button = null
var _close_btn: Button = null

var _market_view: VBoxContainer = null
var _hold_list_vbox: VBoxContainer = null
var _upgrades_hbox: HBoxContainer = null
var _sell_all_btn: Button = null
var _market_status_label: Label = null

var _log_view: VBoxContainer = null
var _log_progress_label: Label = null
var _log_list_vbox: VBoxContainer = null

var _ui_audio_player: AudioStreamPlayer = null
var _dread_audio_player: AudioStreamPlayer = null
var _stream_latch: AudioStreamWAV = null
var _stream_coin: AudioStreamWAV = null
var _stream_dread: AudioStreamWAV = null


func _ready() -> void:
	layer = 12
	_setup_harbor_audio()
	_build_ui_hierarchy()
	_refresh_all_views()


func _setup_harbor_audio() -> void:
	_stream_latch = _dsp_iron_latch()
	_stream_coin = _dsp_coin_clink()
	_stream_dread = _dsp_abyssal_dread()

	_ui_audio_player = AudioStreamPlayer.new()
	_ui_audio_player.name = "HarborUISfxPlayer"
	_ui_audio_player.volume_db = -4.0
	add_child(_ui_audio_player)

	_dread_audio_player = AudioStreamPlayer.new()
	_dread_audio_player.name = "HarborDreadDronePlayer"
	_dread_audio_player.volume_db = -10.5
	add_child(_dread_audio_player)


func _play_ui_sfx(stream: AudioStreamWAV, pitch: float = 1.0) -> void:
	if _ui_audio_player == null or stream == null or DisplayServer.get_name() == "headless":
		return
	_ui_audio_player.stream = stream
	_ui_audio_player.pitch_scale = pitch
	_ui_audio_player.play()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey:
		var key_event: InputEventKey = event as InputEventKey
		if key_event.pressed and not key_event.echo:
			var code: Key = key_event.physical_keycode if key_event.physical_keycode != KEY_NONE else key_event.keycode
			if code == KEY_E:
				if _is_open:
					_set_modal_open(false)
				elif _near_wharf_dock:
					_active_tab = 0
					_set_modal_open(true)
			elif code == KEY_TAB:
				if _is_open and _active_tab == 1:
					_set_modal_open(false)
				else:
					_active_tab = 1
					_set_modal_open(true)
			elif code == KEY_ESCAPE and _is_open:
				_set_modal_open(false)


func _process(_delta: float) -> void:
	_resolve_references()

	var was_near: bool = _near_wharf_dock
	_near_wharf_dock = false
	if boat != null:
		var boat_xz: Vector2 = Vector2(boat.global_position.x, boat.global_position.z)
		var dist: float = boat_xz.distance_to(WHARF_DOCK_POS_XZ)
		var speed_val: float = 0.0
		if "current_speed" in boat:
			speed_val = absf(boat.get("current_speed") as float)
		var fishing_active: bool = false
		if "fishing_mode_active" in boat:
			fishing_active = boat.get("fishing_mode_active") as bool
		_near_wharf_dock = (dist <= DOCK_INTERACT_RADIUS) and (speed_val < 2.8) and (not fishing_active)

	if _dock_prompt_panel != null:
		_dock_prompt_panel.visible = _near_wharf_dock and (not _is_open)
		if _near_wharf_dock and _dock_prompt_label != null and _fishing_controller != null:
			var hold_count: int = _fishing_controller.fish_hold.size()
			var hold_kg: float = _fishing_controller.total_hold_kg
			_dock_prompt_label.text = "⚓  [E] BLACKWATER WHARF & CANNERY (%d Specimens | %.1f kg)    [TAB] DREDGE LEDGER" % [hold_count, hold_kg]

	if was_near != _near_wharf_dock and _is_open:
		_refresh_all_views()


func _resolve_references() -> void:
	if boat == null and get_parent() != null:
		boat = get_parent().get_node_or_null("Boat") as Node3D

	if _fishing_controller == null:
		var fc_nodes: Array[Node] = get_tree().get_nodes_in_group("fishing_controller")
		if not fc_nodes.is_empty():
			_fishing_controller = fc_nodes[0] as FishingController
			if _fishing_controller != null:
				if not _fishing_controller.hold_updated.is_connected(_on_hold_updated):
					_fishing_controller.hold_updated.connect(_on_hold_updated)
				_refresh_all_views()

	if _sonar == null:
		var sonar_nodes: Array[Node] = get_tree().get_nodes_in_group("sonar_system")
		if not sonar_nodes.is_empty():
			_sonar = sonar_nodes[0] as SonarSystem


func _set_modal_open(open_state: bool) -> void:
	var changed: bool = (_is_open != open_state)
	_is_open = open_state
	if get_parent() != null:
		var cam: OverheadCamera = get_parent().get_node_or_null("Camera3D") as OverheadCamera
		if cam != null:
			cam.ui_modal_open = _is_open
	if _backdrop_vignette != null:
		_backdrop_vignette.visible = _is_open
		if _is_open:
			_backdrop_vignette.queue_redraw()
	if _main_modal != null:
		_main_modal.visible = _is_open
	if _modal_frame_drawer != null and _is_open:
		_modal_frame_drawer.queue_redraw()

	if changed:
		_play_ui_sfx(_stream_latch, 0.96 if _is_open else 0.84)
		if _is_open and _dread_audio_player != null and _stream_dread != null and DisplayServer.get_name() != "headless":
			_dread_audio_player.stream = _stream_dread
			_dread_audio_player.pitch_scale = 0.82
			_dread_audio_player.play()

	if _is_open:
		_refresh_all_views()


func _on_hold_updated() -> void:
	if _is_open:
		_refresh_all_views()


func _on_tab_market_pressed() -> void:
	_active_tab = 0
	_play_ui_sfx(_stream_latch, 1.02)
	_refresh_all_views()


func _on_tab_log_pressed() -> void:
	_active_tab = 1
	_play_ui_sfx(_stream_latch, 0.94)
	_refresh_all_views()


func _on_close_pressed() -> void:
	_set_modal_open(false)


func _on_sell_all_pressed() -> void:
	if _fishing_controller == null:
		return
	if not _near_wharf_dock:
		_play_ui_sfx(_stream_latch, 0.78)
		if _market_status_label != null:
			_market_status_label.text = "Moor within 45m of the Blackwater Wharf Pier to consign your catch."
		return
	var earned: float = _fishing_controller.sell_all_hold()
	if earned > 0.0:
		_play_ui_sfx(_stream_coin, 1.0)
		if _sonar != null:
			_sonar.show_catch_banner("CONSIGNED TO BLACKWATER CANNERY: +$%.2f (COFFERS: $%.2f)" % [earned, _fishing_controller.bank_balance], 3.4)
	else:
		_play_ui_sfx(_stream_latch, 0.85)
	_refresh_all_views()


func _on_sell_single_pressed(item_index: int) -> void:
	if _fishing_controller == null or not _near_wharf_dock:
		return
	var earned: float = _fishing_controller.sell_hold_index(item_index)
	if earned > 0.0:
		_play_ui_sfx(_stream_coin, randf_range(0.95, 1.08))
		if _sonar != null:
			_sonar.show_catch_banner("SPECIMEN CONSIGNED: +$%.2f (COFFERS: $%.2f)" % [earned, _fishing_controller.bank_balance], 2.5)
	_refresh_all_views()


func _on_upgrade_cable_pressed() -> void:
	if _fishing_controller == null or not _near_wharf_dock:
		return
	var cost: float = float(_fishing_controller.cable_level) * 85.0
	if _fishing_controller.bank_balance < cost or _fishing_controller.cable_level >= 4:
		_play_ui_sfx(_stream_latch, 0.76)
		return
	_fishing_controller.bank_balance = snappedf(_fishing_controller.bank_balance - cost, 0.5)
	_fishing_controller.money = _fishing_controller.bank_balance
	_fishing_controller.cable_level += 1
	_play_ui_sfx(_stream_coin, 0.92)
	_refresh_all_views()


func _on_upgrade_winch_pressed() -> void:
	if _fishing_controller == null or not _near_wharf_dock:
		return
	var cost: float = float(_fishing_controller.winch_level) * 95.0
	if _fishing_controller.bank_balance < cost or _fishing_controller.winch_level >= 4:
		_play_ui_sfx(_stream_latch, 0.76)
		return
	_fishing_controller.bank_balance = snappedf(_fishing_controller.bank_balance - cost, 0.5)
	_fishing_controller.money = _fishing_controller.bank_balance
	_fishing_controller.winch_level += 1
	_play_ui_sfx(_stream_coin, 0.96)
	_refresh_all_views()


func _on_upgrade_boiler_pressed() -> void:
	if _fishing_controller == null or not _near_wharf_dock:
		return
	var cost: float = float(_boiler_level) * 110.0
	if _fishing_controller.bank_balance < cost or _boiler_level >= 4:
		_play_ui_sfx(_stream_latch, 0.76)
		return
	_fishing_controller.bank_balance = snappedf(_fishing_controller.bank_balance - cost, 0.5)
	_fishing_controller.money = _fishing_controller.bank_balance
	_boiler_level += 1
	if boat != null and "max_speed" in boat:
		boat.set("max_speed", 8.5 + float(_boiler_level - 1) * 1.15)
	_play_ui_sfx(_stream_coin, 0.88)
	_refresh_all_views()


func _refresh_all_views() -> void:
	if _main_modal == null:
		return

	var balance: float = _fishing_controller.bank_balance if _fishing_controller != null else 0.0
	var hold_kg: float = _fishing_controller.total_hold_kg if _fishing_controller != null else 0.0
	var hold_count: int = _fishing_controller.fish_hold.size() if _fishing_controller != null else 0
	var discovered_count: int = _fishing_controller.species_records.size() if _fishing_controller != null else 0

	if _header_balance_label != null:
		_header_balance_label.text = "COFFERS: $%.2f" % balance
	if _header_hold_label != null:
		_header_hold_label.text = "BILGE HOLD: %d SPECIMENS (%.1f kg)" % [hold_count, hold_kg]

	if _tab_market_btn != null:
		_tab_market_btn.text = "I · BLACKWATER CANNERY & SHIPWRIGHT (%d)" % hold_count
		_tab_market_btn.modulate = UI_BRASS_HIGHLIGHT if _active_tab == 0 else UI_MUTED_PARCHMENT
	if _tab_log_btn != null:
		_tab_log_btn.text = "II · ICHTHYOLOGY DREDGE LEDGER (%d / 12 Cataloged)" % discovered_count
		_tab_log_btn.modulate = UI_BRASS_HIGHLIGHT if _active_tab == 1 else UI_MUTED_PARCHMENT

	if _market_view != null:
		_market_view.visible = (_active_tab == 0)
	if _log_view != null:
		_log_view.visible = (_active_tab == 1)

	if _active_tab == 0:
		_rebuild_market_hold_list()
		_rebuild_shipwright_upgrade_cards()
	else:
		_rebuild_species_encyclopedia_list()


func _rebuild_market_hold_list() -> void:
	if _hold_list_vbox == null:
		return

	for child: Node in _hold_list_vbox.get_children():
		child.queue_free()

	var hold: Array[Dictionary] = []
	if _fishing_controller != null and "fish_hold" in _fishing_controller:
		hold.assign(_fishing_controller.fish_hold)
	var total_val: float = 0.0
	for item: Dictionary in hold:
		total_val += item.get("value", 0.0) as float
	total_val = snappedf(total_val, 0.5)

	if _sell_all_btn != null:
		_sell_all_btn.disabled = hold.is_empty() or (not _near_wharf_dock)
		if _near_wharf_dock:
			_sell_all_btn.text = "CONSIGN ALL SPECIMENS TO BLACKWATER CANNERY (+$%.2f)" % total_val
		else:
			_sell_all_btn.text = "MOOR AT BLACKWATER WHARF TO CONSIGN CATCH ($%.2f IN HOLD)" % total_val

	if _market_status_label != null:
		if _near_wharf_dock:
			_market_status_label.text = "Hawsers fast to Blackwater Pier. Lanterns lit; the Cannery Factor awaits your haul."
			_market_status_label.modulate = UI_ELDRITCH_TEAL
		else:
			_market_status_label.text = "Adrift on the night tide — return within 45m of the Wharf Pier to sell catch or refit."
			_market_status_label.modulate = UI_BRASS_HIGHLIGHT

	if hold.is_empty():
		var empty_lbl: Label = Label.new()
		empty_lbl.text = "The ice-bilge stands empty. Unlimber the stern rod [F] above sonar echoes to dredge specimens from the deep."
		empty_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		empty_lbl.add_theme_color_override("font_color", UI_MUTED_PARCHMENT)
		empty_lbl.add_theme_font_size_override("font_size", 14)
		_hold_list_vbox.add_child(empty_lbl)
		return

	for idx: int in range(hold.size()):
		var entry: Dictionary = hold[idx]
		var sp_name: String = entry.get("name", "Atlantic Cod") as String
		var tier_name: String = entry.get("tier_name", FishCatalog.TIER_COASTAL) as String
		var weight_kg: float = entry.get("weight_kg", 5.0) as float
		var depth_m: float = entry.get("depth_m", 18.0) as float
		var val_dollars: float = entry.get("value", 25.0) as float
		var tier_col: Color = FishCatalog.get_tier_color(tier_name)

		var row_panel: PanelContainer = _create_ornate_card_panel(tier_col, false)
		var row_hbox: HBoxContainer = HBoxContainer.new()
		row_hbox.add_theme_constant_override("separation", 12)
		row_panel.add_child(row_hbox)

		var name_lbl: Label = Label.new()
		name_lbl.text = "❖  " + sp_name
		name_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		name_lbl.add_theme_color_override("font_color", UI_BONE_PARCHMENT)
		name_lbl.add_theme_font_size_override("font_size", 15)
		row_hbox.add_child(name_lbl)

		var tier_lbl: Label = Label.new()
		tier_lbl.text = "[%s]" % tier_name.to_upper()
		tier_lbl.custom_minimum_size = Vector2(165.0, 0.0)
		tier_lbl.add_theme_color_override("font_color", tier_col)
		tier_lbl.add_theme_font_size_override("font_size", 13)
		row_hbox.add_child(tier_lbl)

		var weight_lbl: Label = Label.new()
		weight_lbl.text = "%.1f kg" % weight_kg
		weight_lbl.custom_minimum_size = Vector2(82.0, 0.0)
		weight_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		weight_lbl.add_theme_color_override("font_color", UI_BONE_PARCHMENT)
		weight_lbl.add_theme_font_size_override("font_size", 14)
		row_hbox.add_child(weight_lbl)

		var depth_lbl: Label = Label.new()
		depth_lbl.text = "Dredged @ %.1fm" % depth_m
		depth_lbl.custom_minimum_size = Vector2(125.0, 0.0)
		depth_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		depth_lbl.add_theme_color_override("font_color", UI_MUTED_PARCHMENT)
		depth_lbl.add_theme_font_size_override("font_size", 13)
		row_hbox.add_child(depth_lbl)

		var val_lbl: Label = Label.new()
		val_lbl.text = "$%.2f" % val_dollars
		val_lbl.custom_minimum_size = Vector2(80.0, 0.0)
		val_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		val_lbl.add_theme_color_override("font_color", UI_BRASS_HIGHLIGHT)
		val_lbl.add_theme_font_size_override("font_size", 15)
		row_hbox.add_child(val_lbl)

		var sell_btn: Button = Button.new()
		sell_btn.text = "CONSIGN"
		sell_btn.disabled = not _near_wharf_dock
		_style_iron_button(sell_btn, UI_TARNISHED_BRASS)
		sell_btn.pressed.connect(_on_sell_single_pressed.bind(idx))
		row_hbox.add_child(sell_btn)

		_hold_list_vbox.add_child(row_panel)


func _rebuild_shipwright_upgrade_cards() -> void:
	if _upgrades_hbox == null:
		return

	for child: Node in _upgrades_hbox.get_children():
		child.queue_free()

	var cable_lvl: int = _fishing_controller.cable_level if _fishing_controller != null else 1
	var winch_lvl: int = _fishing_controller.winch_level if _fishing_controller != null else 1
	var balance: float = _fishing_controller.bank_balance if _fishing_controller != null else 0.0

	var upgrades: Array[Dictionary] = [
		{
			"title": "ABYSSAL WIRE LEADER",
			"level": cable_lvl,
			"cost": float(cable_lvl) * 85.0,
			"lore": "Braided phosphor-bronze trace wire tempered in whale oil. Dampens line strain from trench horrors.",
			"callback": Callable(self, "_on_upgrade_cable_pressed"),
		},
		{
			"title": "OCCULT BRASS RATCHET WINCH",
			"level": winch_lvl,
			"cost": float(winch_lvl) * 95.0,
			"lore": "Double-geared Innsmouth capstan drum that hauls thrashing specimens from the dark with relentless torque.",
			"callback": Callable(self, "_on_upgrade_winch_pressed"),
		},
		{
			"title": "BOILER OVERCLOCK & IRON KEEL",
			"level": _boiler_level,
			"cost": float(_boiler_level) * 110.0,
			"lore": "Heavy-oil injector valves that drive the trawler harder across black swells when fleeing rising squalls.",
			"callback": Callable(self, "_on_upgrade_boiler_pressed"),
		},
	]

	for upg: Dictionary in upgrades:
		var lvl: int = upg.get("level", 1) as int
		var cost: float = upg.get("cost", 85.0) as float
		var has_seal: bool = (lvl > 1)
		var card: PanelContainer = _create_ornate_card_panel(UI_TARNISHED_BRASS, has_seal)
		card.size_flags_horizontal = Control.SIZE_EXPAND_FILL

		var card_vbox: VBoxContainer = VBoxContainer.new()
		card_vbox.add_theme_constant_override("separation", 5)
		card.add_child(card_vbox)

		var title_lbl: Label = Label.new()
		title_lbl.text = "%s [TIER %d/4]" % [upg.get("title", "") as String, lvl]
		title_lbl.add_theme_color_override("font_color", UI_BRASS_HIGHLIGHT)
		title_lbl.add_theme_font_size_override("font_size", 13)
		card_vbox.add_child(title_lbl)

		var lore_lbl: Label = Label.new()
		lore_lbl.text = upg.get("lore", "") as String
		lore_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		lore_lbl.custom_minimum_size = Vector2(0.0, 38.0)
		lore_lbl.add_theme_color_override("font_color", UI_MUTED_PARCHMENT)
		lore_lbl.add_theme_font_size_override("font_size", 11)
		card_vbox.add_child(lore_lbl)

		var buy_btn: Button = Button.new()
		if lvl >= 4:
			buy_btn.text = "SEALED IN BLOOD [MAX]"
			buy_btn.disabled = true
		else:
			buy_btn.text = "FORGE UPGRADE ($%.0f)" % cost
			buy_btn.disabled = (not _near_wharf_dock) or (balance < cost)
		_style_iron_button(buy_btn, UI_TARNISHED_BRASS)
		var cb: Callable = upg.get("callback") as Callable
		if cb.is_valid():
			buy_btn.pressed.connect(cb)
		card_vbox.add_child(buy_btn)

		_upgrades_hbox.add_child(card)


func _rebuild_species_encyclopedia_list() -> void:
	if _log_list_vbox == null:
		return

	for child: Node in _log_list_vbox.get_children():
		child.queue_free()

	var all_species: Array[Dictionary] = FishCatalog.get_all_species()
	var records: Dictionary[String, Dictionary] = {}
	if _fishing_controller != null:
		records = _fishing_controller.species_records
	var discovered_total: int = records.size()

	if _log_progress_label != null:
		_log_progress_label.text = "BLACKWATER ICHTHYOLOGY FOLIO — %d / %d ABYSSAL & COASTAL SPECIMENS CATALOGED" % [
			discovered_total,
			all_species.size(),
		]

	for idx: int in range(all_species.size()):
		var spec: Dictionary = all_species[idx]
		var sp_id: String = spec.get("id", "") as String
		var display_name: String = spec.get("display_name", "Unknown") as String
		var tier_name: String = spec.get("tier_name", FishCatalog.TIER_COASTAL) as String
		var min_d: float = spec.get("min_depth_m", 0.0) as float
		var max_d: float = spec.get("max_depth_m", 100.0) as float
		var price_kg: float = spec.get("price_per_kg", 5.0) as float
		var hint_str: String = spec.get("hint", "") as String
		var lore_str: String = spec.get("lore", "") as String
		var tier_col: Color = FishCatalog.get_tier_color(tier_name)

		var is_discovered: bool = records.has(sp_id)
		var row_border_col: Color = tier_col if is_discovered else UI_CORRODED_IRON.lightened(0.15)
		var row_panel: PanelContainer = _create_ornate_card_panel(row_border_col, is_discovered)

		var outer_vbox: VBoxContainer = VBoxContainer.new()
		outer_vbox.add_theme_constant_override("separation", 3)
		row_panel.add_child(outer_vbox)

		var row_hbox: HBoxContainer = HBoxContainer.new()
		row_hbox.add_theme_constant_override("separation", 12)
		outer_vbox.add_child(row_hbox)

		var num_lbl: Label = Label.new()
		num_lbl.text = "№ %02d" % (idx + 1)
		num_lbl.custom_minimum_size = Vector2(46.0, 0.0)
		num_lbl.add_theme_color_override("font_color", UI_TARNISHED_BRASS)
		row_hbox.add_child(num_lbl)

		var title_lbl: Label = Label.new()
		title_lbl.custom_minimum_size = Vector2(195.0, 0.0)
		if is_discovered:
			title_lbl.text = display_name
			title_lbl.add_theme_color_override("font_color", UI_BONE_PARCHMENT)
		else:
			title_lbl.text = "??? [UNCATALOGED HORROR]"
			title_lbl.add_theme_color_override("font_color", UI_MUTED_PARCHMENT.darkened(0.2))
		title_lbl.add_theme_font_size_override("font_size", 15)
		row_hbox.add_child(title_lbl)

		var tier_lbl: Label = Label.new()
		tier_lbl.text = "[%s]" % tier_name.to_upper()
		tier_lbl.custom_minimum_size = Vector2(165.0, 0.0)
		tier_lbl.add_theme_color_override("font_color", tier_col)
		tier_lbl.add_theme_font_size_override("font_size", 13)
		row_hbox.add_child(tier_lbl)

		var info_lbl: Label = Label.new()
		info_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if is_discovered:
			var rec: Dictionary = records[sp_id]
			var count_caught: int = rec.get("count", 1) as int
			var record_w: float = rec.get("max_weight_kg", 0.0) as float
			info_lbl.text = "Heaviest: %.1f kg  |  Dredged: %d  |  Fathoms: %dm–%dm  |  $%.1f/kg" % [
				record_w,
				count_caught,
				int(round(min_d)),
				int(round(max_d)),
				price_kg,
			]
			info_lbl.add_theme_color_override("font_color", UI_ELDRITCH_TEAL)
		else:
			info_lbl.text = hint_str
			info_lbl.add_theme_color_override("font_color", UI_MUTED_PARCHMENT)
		info_lbl.add_theme_font_size_override("font_size", 13)
		row_hbox.add_child(info_lbl)

		if is_discovered and not lore_str.is_empty():
			var lore_lbl: Label = Label.new()
			lore_lbl.text = "    \"%s\"" % lore_str
			lore_lbl.add_theme_color_override("font_color", UI_MUTED_PARCHMENT)
			lore_lbl.add_theme_font_size_override("font_size", 12)
			outer_vbox.add_child(lore_lbl)

		_log_list_vbox.add_child(row_panel)


func _create_void_panel_style(border_col: Color, bg_col: Color, margin_h: float, margin_v: float) -> StyleBoxFlat:
	var sb: StyleBoxFlat = StyleBoxFlat.new()
	sb.bg_color = bg_col
	sb.border_width_left = 2
	sb.border_width_top = 2
	sb.border_width_right = 2
	sb.border_width_bottom = 2
	sb.border_color = border_col
	sb.corner_radius_top_left = 2
	sb.corner_radius_top_right = 2
	sb.corner_radius_bottom_left = 2
	sb.corner_radius_bottom_right = 2
	sb.shadow_color = Color(0.0, 0.0, 0.0, 0.82)
	sb.shadow_size = 14
	sb.content_margin_left = margin_h
	sb.content_margin_right = margin_h
	sb.content_margin_top = margin_v
	sb.content_margin_bottom = margin_v
	return sb


func _style_iron_button(btn: Button, accent_col: Color) -> void:
	var normal_sb: StyleBoxFlat = StyleBoxFlat.new()
	normal_sb.bg_color = UI_CORRODED_IRON
	normal_sb.border_width_left = 2
	normal_sb.border_width_top = 2
	normal_sb.border_width_right = 2
	normal_sb.border_width_bottom = 2
	normal_sb.border_color = accent_col
	normal_sb.corner_radius_top_left = 2
	normal_sb.corner_radius_top_right = 2
	normal_sb.corner_radius_bottom_left = 2
	normal_sb.corner_radius_bottom_right = 2
	normal_sb.content_margin_left = 14.0
	normal_sb.content_margin_right = 14.0
	normal_sb.content_margin_top = 7.0
	normal_sb.content_margin_bottom = 7.0

	var hover_sb: StyleBoxFlat = normal_sb.duplicate() as StyleBoxFlat
	hover_sb.bg_color = Color(0.11, 0.14, 0.16, 0.98)
	hover_sb.border_color = UI_BRASS_HIGHLIGHT

	var pressed_sb: StyleBoxFlat = normal_sb.duplicate() as StyleBoxFlat
	pressed_sb.bg_color = UI_BLOOD_CRIMSON.darkened(0.35)
	pressed_sb.border_color = UI_CRIMSON_BRIGHT

	var disabled_sb: StyleBoxFlat = normal_sb.duplicate() as StyleBoxFlat
	disabled_sb.bg_color = Color(0.04, 0.05, 0.06, 0.75)
	disabled_sb.border_color = Color(0.24, 0.22, 0.18, 0.55)

	btn.add_theme_stylebox_override("normal", normal_sb)
	btn.add_theme_stylebox_override("hover", hover_sb)
	btn.add_theme_stylebox_override("pressed", pressed_sb)
	btn.add_theme_stylebox_override("disabled", disabled_sb)
	btn.add_theme_color_override("font_color", UI_BONE_PARCHMENT)
	btn.add_theme_color_override("font_hover_color", UI_BRASS_HIGHLIGHT)
	btn.add_theme_color_override("font_pressed_color", UI_BONE_PARCHMENT)
	btn.add_theme_color_override("font_disabled_color", UI_MUTED_PARCHMENT.darkened(0.3))


func _create_ornate_card_panel(border_color: Color, show_wax_seal: bool = false) -> PanelContainer:
	var panel: PanelContainer = PanelContainer.new()
	var sb: StyleBoxFlat = StyleBoxFlat.new()
	sb.bg_color = UI_CORRODED_IRON.darkened(0.32)
	sb.border_width_left = 3
	sb.border_width_top = 1
	sb.border_width_right = 2
	sb.border_width_bottom = 1
	sb.border_color = border_color
	sb.corner_radius_top_left = 2
	sb.corner_radius_top_right = 2
	sb.corner_radius_bottom_left = 2
	sb.corner_radius_bottom_right = 2
	sb.content_margin_left = 12.0
	sb.content_margin_right = 14.0
	sb.content_margin_top = 8.0
	sb.content_margin_bottom = 8.0
	panel.add_theme_stylebox_override("panel", sb)

	var deco: Control = Control.new()
	deco.mouse_filter = Control.MOUSE_FILTER_IGNORE
	deco.set_anchors_preset(Control.PRESET_FULL_RECT)
	deco.draw.connect(_on_draw_card_ornament.bind(deco, border_color, show_wax_seal))
	panel.add_child(deco)
	return panel


func _on_draw_card_ornament(deco: Control, border_col: Color, show_wax_seal: bool) -> void:
	if deco == null:
		return
	var sz: Vector2 = deco.size
	if sz.x < 12.0 or sz.y < 12.0:
		return
	deco.draw_rect(Rect2(Vector2.ZERO, sz).grow(-3.0), Color(border_col.r, border_col.g, border_col.b, 0.35), false, 1.0)
	deco.draw_circle(Vector2(6.0, 6.0), 1.6, UI_BRASS_HIGHLIGHT)
	deco.draw_circle(Vector2(sz.x - 6.0, 6.0), 1.6, UI_BRASS_HIGHLIGHT)
	deco.draw_circle(Vector2(6.0, sz.y - 6.0), 1.6, UI_BRASS_HIGHLIGHT)
	deco.draw_circle(Vector2(sz.x - 6.0, sz.y - 6.0), 1.6, UI_BRASS_HIGHLIGHT)
	if show_wax_seal:
		_draw_harbor_wax_seal(deco, Vector2(sz.x - 16.0, 14.0), 7.5)


func _on_draw_backdrop_vignette() -> void:
	if _backdrop_vignette == null:
		return
	var sz: Vector2 = _backdrop_vignette.size
	_backdrop_vignette.draw_rect(Rect2(Vector2.ZERO, sz), Color(0.015, 0.02, 0.028, 0.76), true)
	for i: int in range(6):
		var inset: float = float(i) * 28.0
		var r: Rect2 = Rect2(Vector2.ZERO, sz).grow(-inset)
		if r.size.x > 0.0 and r.size.y > 0.0:
			_backdrop_vignette.draw_rect(r, Color(0.01, 0.012, 0.018, 0.22), false, 32.0)


func _on_draw_dock_prompt_frame() -> void:
	if _dock_prompt_drawer == null:
		return
	var rect: Rect2 = Rect2(Vector2.ZERO, _dock_prompt_drawer.size)
	_draw_harbor_lovecraft_frame(_dock_prompt_drawer, rect, UI_TARNISHED_BRASS, UI_BRASS_HIGHLIGHT, 0.0)


func _on_draw_main_modal_frame() -> void:
	if _modal_frame_drawer == null:
		return
	var rect: Rect2 = Rect2(Vector2.ZERO, _modal_frame_drawer.size)
	_draw_harbor_lovecraft_frame(_modal_frame_drawer, rect, UI_TARNISHED_BRASS, UI_BRASS_HIGHLIGHT, 0.12)
	_draw_harbor_gothic_divider(_modal_frame_drawer, Vector2(rect.size.x * 0.5, 52.0), rect.size.x * 0.44, UI_TARNISHED_BRASS)


func _draw_harbor_lovecraft_frame(
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

	var top_rivet_count: int = clampi(int(w / 95.0), 2, 10)
	for r_i: int in range(1, top_rivet_count):
		var rx: float = lerpf(x0 + corner_len, x1 - corner_len, float(r_i) / float(top_rivet_count))
		canvas.draw_circle(Vector2(rx, y0 + 3.0), 1.4, inner_accent.darkened(0.1))
		canvas.draw_circle(Vector2(rx, y1 - 3.0), 1.4, inner_accent.darkened(0.1))


func _draw_harbor_gothic_divider(canvas: CanvasItem, center: Vector2, half_width: float, col: Color) -> void:
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


func _draw_harbor_wax_seal(canvas: CanvasItem, center: Vector2, radius: float) -> void:
	canvas.draw_circle(center + Vector2(1.0, 1.5), radius + 1.0, Color(0.0, 0.0, 0.0, 0.65))
	canvas.draw_circle(center, radius, UI_BLOOD_CRIMSON)
	canvas.draw_circle(center, radius * 0.78, UI_CRIMSON_BRIGHT.darkened(0.15))
	canvas.draw_arc(center, radius * 0.78, 0.0, TAU, 20, UI_BONE_PARCHMENT.darkened(0.25), 1.2)
	canvas.draw_line(center + Vector2(-radius * 0.42, 0.0), center + Vector2(radius * 0.42, 0.0), UI_BONE_PARCHMENT, 1.3)
	canvas.draw_line(center + Vector2(0.0, -radius * 0.42), center + Vector2(0.0, radius * 0.42), UI_BONE_PARCHMENT, 1.3)


func _build_ui_hierarchy() -> void:
	_backdrop_vignette = Control.new()
	_backdrop_vignette.name = "SmokyHarborVignette"
	_backdrop_vignette.visible = false
	_backdrop_vignette.set_anchors_preset(Control.PRESET_FULL_RECT)
	_backdrop_vignette.draw.connect(_on_draw_backdrop_vignette)
	add_child(_backdrop_vignette)

	_dock_prompt_panel = PanelContainer.new()
	_dock_prompt_panel.name = "WharfDockPrompt"
	_dock_prompt_panel.visible = false
	_dock_prompt_panel.position = Vector2(28.0, 28.0)

	var prompt_sb: StyleBoxFlat = _create_void_panel_style(UI_TARNISHED_BRASS, UI_VOID_BLACK, 18.0, 10.0)
	_dock_prompt_panel.add_theme_stylebox_override("panel", prompt_sb)

	_dock_prompt_drawer = Control.new()
	_dock_prompt_drawer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dock_prompt_drawer.set_anchors_preset(Control.PRESET_FULL_RECT)
	_dock_prompt_drawer.draw.connect(_on_draw_dock_prompt_frame)
	_dock_prompt_panel.add_child(_dock_prompt_drawer)

	_dock_prompt_label = Label.new()
	_dock_prompt_label.text = "⚓  [E] BLACKWATER WHARF & CANNERY    [TAB] DREDGE LEDGER"
	_dock_prompt_label.add_theme_color_override("font_color", UI_BRASS_HIGHLIGHT)
	_dock_prompt_label.add_theme_font_size_override("font_size", 15)
	_dock_prompt_panel.add_child(_dock_prompt_label)
	add_child(_dock_prompt_panel)

	_main_modal = PanelContainer.new()
	_main_modal.name = "HarborCanneryModal"
	_main_modal.visible = false
	_main_modal.anchors_preset = Control.PRESET_CENTER
	_main_modal.anchor_left = 0.5
	_main_modal.anchor_top = 0.5
	_main_modal.anchor_right = 0.5
	_main_modal.anchor_bottom = 0.5
	_main_modal.offset_left = -490.0
	_main_modal.offset_top = -340.0
	_main_modal.offset_right = 490.0
	_main_modal.offset_bottom = 340.0

	var modal_sb: StyleBoxFlat = _create_void_panel_style(UI_TARNISHED_BRASS, UI_VOID_BLACK, 24.0, 20.0)
	_main_modal.add_theme_stylebox_override("panel", modal_sb)
	add_child(_main_modal)

	_modal_frame_drawer = Control.new()
	_modal_frame_drawer.name = "ModalOrnateFrame"
	_modal_frame_drawer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_modal_frame_drawer.set_anchors_preset(Control.PRESET_FULL_RECT)
	_modal_frame_drawer.draw.connect(_on_draw_main_modal_frame)
	_main_modal.add_child(_modal_frame_drawer)

	var root_vbox: VBoxContainer = VBoxContainer.new()
	root_vbox.add_theme_constant_override("separation", 12)
	_main_modal.add_child(root_vbox)

	var header_hbox: HBoxContainer = HBoxContainer.new()
	header_hbox.add_theme_constant_override("separation", 16)
	root_vbox.add_child(header_hbox)

	var title_lbl: Label = Label.new()
	title_lbl.text = "✦  BLACKWATER WHARF & INNSMOUTH MARITIME LEDGER  ✦"
	title_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_lbl.add_theme_color_override("font_color", UI_BRASS_HIGHLIGHT)
	title_lbl.add_theme_font_size_override("font_size", 18)
	header_hbox.add_child(title_lbl)

	_header_hold_label = Label.new()
	_header_hold_label.text = "BILGE HOLD: 0 SPECIMENS (0.0 kg)"
	_header_hold_label.add_theme_color_override("font_color", UI_ELDRITCH_TEAL)
	_header_hold_label.add_theme_font_size_override("font_size", 14)
	header_hbox.add_child(_header_hold_label)

	_header_balance_label = Label.new()
	_header_balance_label.text = "COFFERS: $0.00"
	_header_balance_label.add_theme_color_override("font_color", UI_BONE_PARCHMENT)
	_header_balance_label.add_theme_font_size_override("font_size", 16)
	header_hbox.add_child(_header_balance_label)

	_close_btn = Button.new()
	_close_btn.text = "SEAL LEDGER [ESC]"
	_style_iron_button(_close_btn, UI_BLOOD_CRIMSON)
	_close_btn.pressed.connect(_on_close_pressed)
	header_hbox.add_child(_close_btn)

	var tab_hbox: HBoxContainer = HBoxContainer.new()
	tab_hbox.add_theme_constant_override("separation", 12)
	root_vbox.add_child(tab_hbox)

	_tab_market_btn = Button.new()
	_tab_market_btn.text = "I · BLACKWATER CANNERY & SHIPWRIGHT"
	_tab_market_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_style_iron_button(_tab_market_btn, UI_TARNISHED_BRASS)
	_tab_market_btn.pressed.connect(_on_tab_market_pressed)
	tab_hbox.add_child(_tab_market_btn)

	_tab_log_btn = Button.new()
	_tab_log_btn.text = "II · ICHTHYOLOGY DREDGE LEDGER (0 / 12 Cataloged)"
	_tab_log_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_style_iron_button(_tab_log_btn, UI_TARNISHED_BRASS)
	_tab_log_btn.pressed.connect(_on_tab_log_pressed)
	tab_hbox.add_child(_tab_log_btn)

	_market_view = VBoxContainer.new()
	_market_view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_market_view.add_theme_constant_override("separation", 8)
	root_vbox.add_child(_market_view)

	_market_status_label = Label.new()
	_market_status_label.text = "Hawsers fast to Blackwater Pier."
	_market_status_label.add_theme_font_size_override("font_size", 13)
	_market_view.add_child(_market_status_label)

	var market_scroll: ScrollContainer = ScrollContainer.new()
	market_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_market_view.add_child(market_scroll)

	_hold_list_vbox = VBoxContainer.new()
	_hold_list_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_hold_list_vbox.add_theme_constant_override("separation", 6)
	market_scroll.add_child(_hold_list_vbox)

	_sell_all_btn = Button.new()
	_sell_all_btn.custom_minimum_size = Vector2(0.0, 38.0)
	_sell_all_btn.text = "CONSIGN ALL SPECIMENS TO BLACKWATER CANNERY (+$0.00)"
	_style_iron_button(_sell_all_btn, UI_BRASS_HIGHLIGHT)
	_sell_all_btn.pressed.connect(_on_sell_all_pressed)
	_market_view.add_child(_sell_all_btn)

	var shipwright_header: Label = Label.new()
	shipwright_header.text = "⚙  BLACKWATER SHIPWRIGHT & OCCULT TRAWLER OUTFITTING  ⚙"
	shipwright_header.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	shipwright_header.add_theme_color_override("font_color", UI_BRASS_HIGHLIGHT)
	shipwright_header.add_theme_font_size_override("font_size", 14)
	_market_view.add_child(shipwright_header)

	_upgrades_hbox = HBoxContainer.new()
	_upgrades_hbox.add_theme_constant_override("separation", 10)
	_market_view.add_child(_upgrades_hbox)

	_log_view = VBoxContainer.new()
	_log_view.visible = false
	_log_view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_log_view.add_theme_constant_override("separation", 8)
	root_vbox.add_child(_log_view)

	_log_progress_label = Label.new()
	_log_progress_label.text = "BLACKWATER ICHTHYOLOGY FOLIO — 0 / 12 SPECIMENS CATALOGED"
	_log_progress_label.add_theme_color_override("font_color", UI_ELDRITCH_TEAL)
	_log_progress_label.add_theme_font_size_override("font_size", 14)
	_log_view.add_child(_log_progress_label)

	var log_scroll: ScrollContainer = ScrollContainer.new()
	log_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_log_view.add_child(log_scroll)

	_log_list_vbox = VBoxContainer.new()
	_log_list_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_log_list_vbox.add_theme_constant_override("separation", 6)
	log_scroll.add_child(_log_list_vbox)


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


func _dsp_iron_latch() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var count: int = int(0.12 * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)
	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var s: float = sin(float(i) * 12.9898 + 688.45) * 43758.5453
		var n: float = (s - floor(s)) * 2.0 - 1.0
		var iron_thud: float = sin(t * TAU * 92.0) * exp(-t * 34.0) * 0.62
		var clank: float = (sin(t * TAU * 340.0) * 0.32 + sin(t * TAU * 580.0) * 0.18 + n * 0.22) * exp(-t * 68.0)
		buf[i] = iron_thud + clank
	_dsp_cascaded_lpf(buf, 820.0, 0.72, float(mix_rate))
	return _dsp_pack_wav(buf, 0.80, mix_rate)


func _dsp_coin_clink() -> AudioStreamWAV:
	var mix_rate: int = 44100
	var count: int = int(0.42 * float(mix_rate))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)
	for i: int in range(count):
		var t: float = float(i) / float(mix_rate)
		var pouch_thud: float = sin(t * TAU * 110.0) * exp(-t * 26.0) * 0.42
		var c1: float = (sin(t * TAU * 1420.0) * 0.36 + sin(t * TAU * 2180.0) * 0.18) * exp(-t * 28.0)
		var c2: float = 0.0
		if t >= 0.065:
			var t2: float = t - 0.065
			c2 = (sin(t2 * TAU * 1680.0) * 0.34 + sin(t2 * TAU * 2540.0) * 0.16) * exp(-t2 * 30.0)
		var c3: float = 0.0
		if t >= 0.135:
			var t3: float = t - 0.135
			c3 = (sin(t3 * TAU * 1890.0) * 0.30 + sin(t3 * TAU * 2820.0) * 0.14) * exp(-t3 * 26.0)
		buf[i] = pouch_thud + c1 + c2 + c3
	_dsp_cascaded_lpf(buf, 2900.0, 0.707, float(mix_rate))
	return _dsp_pack_wav(buf, 0.78, mix_rate)


func _dsp_abyssal_dread() -> AudioStreamWAV:
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
