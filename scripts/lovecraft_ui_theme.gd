extends RefCounted

# Grim Eldritch Nautical Palette (Darkest Dungeon / Dredge / 19th-Century Occult Brass)
const VOID_BLACK: Color = Color(0.027, 0.035, 0.047, 0.97) # #07090c
const CORRODED_IRON: Color = Color(0.078, 0.094, 0.114, 0.95) # #14181d
const TARNISHED_BRASS: Color = Color(0.549, 0.427, 0.231, 1.0) # #8c6d3b
const BRASS_HIGHLIGHT: Color = Color(0.769, 0.604, 0.322, 1.0) # #c49a52
const BLOOD_CRIMSON: Color = Color(0.478, 0.110, 0.110, 1.0) # #7a1c1c
const CRIMSON_BRIGHT: Color = Color(0.722, 0.157, 0.157, 1.0) # #b82828
const ELDRITCH_TEAL: Color = Color(0.220, 0.557, 0.478, 1.0) # #388e7a
const BONE_PARCHMENT: Color = Color(0.847, 0.808, 0.722, 1.0) # #d8ceb8
const MUTED_PARCHMENT: Color = Color(0.580, 0.545, 0.478, 1.0) # #948b7a


static func create_void_panel_style(
	border_col: Color = TARNISHED_BRASS,
	bg_col: Color = VOID_BLACK,
	margin_h: float = 16.0,
	margin_v: float = 12.0
) -> StyleBoxFlat:
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


static func style_iron_button(btn: Button, accent_col: Color = TARNISHED_BRASS) -> void:
	var normal_sb: StyleBoxFlat = StyleBoxFlat.new()
	normal_sb.bg_color = CORRODED_IRON
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
	hover_sb.border_color = BRASS_HIGHLIGHT

	var pressed_sb: StyleBoxFlat = normal_sb.duplicate() as StyleBoxFlat
	pressed_sb.bg_color = BLOOD_CRIMSON.darkened(0.35)
	pressed_sb.border_color = CRIMSON_BRIGHT

	var disabled_sb: StyleBoxFlat = normal_sb.duplicate() as StyleBoxFlat
	disabled_sb.bg_color = Color(0.04, 0.05, 0.06, 0.75)
	disabled_sb.border_color = Color(0.24, 0.22, 0.18, 0.55)

	btn.add_theme_stylebox_override("normal", normal_sb)
	btn.add_theme_stylebox_override("hover", hover_sb)
	btn.add_theme_stylebox_override("pressed", pressed_sb)
	btn.add_theme_stylebox_override("disabled", disabled_sb)
	btn.add_theme_color_override("font_color", BONE_PARCHMENT)
	btn.add_theme_color_override("font_hover_color", BRASS_HIGHLIGHT)
	btn.add_theme_color_override("font_pressed_color", BONE_PARCHMENT)
	btn.add_theme_color_override("font_disabled_color", MUTED_PARCHMENT.darkened(0.3))


static func draw_lovecraft_frame(
	canvas: CanvasItem,
	rect: Rect2,
	outer_brass: Color = TARNISHED_BRASS,
	inner_accent: Color = BRASS_HIGHLIGHT,
	stress_pulse: float = 0.0
) -> void:
	if canvas == null or rect.size.x < 16.0 or rect.size.y < 16.0:
		return

	var x0: float = rect.position.x
	var y0: float = rect.position.y
	var w: float = rect.size.x
	var h: float = rect.size.y
	var x1: float = x0 + w
	var y1: float = y0 + h

	# 1. Layered dark iron & void backdrop with subtle inner vignette shadow bands
	canvas.draw_rect(rect, VOID_BLACK, true)
	var inner_plate: Rect2 = rect.grow(-4.0)
	canvas.draw_rect(inner_plate, CORRODED_IRON.darkened(0.28), true)
	var deep_core: Rect2 = rect.grow(-11.0)
	if deep_core.size.x > 4.0 and deep_core.size.y > 4.0:
		canvas.draw_rect(deep_core, VOID_BLACK, true)

	# 2. Optional Blood-Crimson stress aura along interior edges
	if stress_pulse > 0.01:
		var glow_a: float = clampf(stress_pulse * 0.45, 0.0, 0.65)
		var blood_col: Color = Color(CRIMSON_BRIGHT.r, CRIMSON_BRIGHT.g, CRIMSON_BRIGHT.b, glow_a)
		canvas.draw_rect(rect.grow(-2.0), blood_col, false, 4.0)
		canvas.draw_rect(rect.grow(-6.0), Color(BLOOD_CRIMSON.r, BLOOD_CRIMSON.g, BLOOD_CRIMSON.b, glow_a * 0.6), false, 3.0)

	# 3. Double-beveled tarnished brass borders
	canvas.draw_rect(rect.grow(-1.0), outer_brass, false, 2.0)
	canvas.draw_rect(rect.grow(-5.0), inner_accent.darkened(0.18), false, 1.2)

	# 4. Angular Gothic Corner Brackets & Spikes
	var corner_len: float = minf(22.0, minf(w, h) * 0.22)
	var spike_inset: float = 9.0
	var corners: Array[Vector2] = [
		Vector2(x0, y0),
		Vector2(x1, y0),
		Vector2(x1, y1),
		Vector2(x0, y1),
	]
	var signs: Array[Vector2] = [
		Vector2(1.0, 1.0),
		Vector2(-1.0, 1.0),
		Vector2(-1.0, -1.0),
		Vector2(1.0, -1.0),
	]

	for idx: int in range(4):
		var c: Vector2 = corners[idx]
		var s: Vector2 = signs[idx]
		# Heavy corner iron bracket L-bars
		canvas.draw_line(
			c + Vector2(s.x * 2.0, s.y * 2.0),
			c + Vector2(s.x * corner_len, s.y * 2.0),
			inner_accent,
			2.5
		)
		canvas.draw_line(
			c + Vector2(s.x * 2.0, s.y * 2.0),
			c + Vector2(s.x * 2.0, s.y * corner_len),
			inner_accent,
			2.5
		)
		# Diagonal gothic filigree miter & inward spear spike
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

		# Corner flange rivet
		var rivet_pos: Vector2 = c + Vector2(s.x * 7.5, s.y * 7.5)
		canvas.draw_circle(rivet_pos, 2.4, CORRODED_IRON)
		canvas.draw_circle(rivet_pos, 1.5, inner_accent)

	# 5. Perimeter Iron Rivets along horizontal & vertical edges
	var top_rivet_count: int = clampi(int(w / 95.0), 2, 10)
	for r_i: int in range(1, top_rivet_count):
		var rx: float = lerpf(x0 + corner_len, x1 - corner_len, float(r_i) / float(top_rivet_count))
		canvas.draw_circle(Vector2(rx, y0 + 3.0), 1.4, inner_accent.darkened(0.1))
		canvas.draw_circle(Vector2(rx, y1 - 3.0), 1.4, inner_accent.darkened(0.1))

	# 6. Subtle Weathered Distress Scratches across frame edges
	var scratch_col: Color = Color(inner_accent.r, inner_accent.g, inner_accent.b, 0.16)
	canvas.draw_line(Vector2(x0 + w * 0.18, y0 + 2.0), Vector2(x0 + w * 0.21, y0 + 8.0), scratch_col, 1.0)
	canvas.draw_line(Vector2(x0 + w * 0.74, y1 - 8.0), Vector2(x0 + w * 0.77, y1 - 2.0), scratch_col, 1.0)
	canvas.draw_line(Vector2(x0 + 2.0, y0 + h * 0.62), Vector2(x0 + 7.0, y0 + h * 0.66), scratch_col, 1.0)


static func draw_gothic_divider(canvas: CanvasItem, center: Vector2, half_width: float, col: Color = TARNISHED_BRASS) -> void:
	if canvas == null:
		return
	var left_pt: Vector2 = center - Vector2(half_width, 0.0)
	var right_pt: Vector2 = center + Vector2(half_width, 0.0)
	canvas.draw_line(left_pt, right_pt, col, 1.4)
	# Center occult diamond sigil
	var diamond: PackedVector2Array = PackedVector2Array([
		center + Vector2(0.0, -4.5),
		center + Vector2(7.0, 0.0),
		center + Vector2(0.0, 4.5),
		center + Vector2(-7.0, 0.0),
	])
	canvas.draw_colored_polygon(diamond, col)
	canvas.draw_circle(left_pt, 2.0, col)
	canvas.draw_circle(right_pt, 2.0, col)


static func draw_wax_seal(canvas: CanvasItem, center: Vector2, radius: float = 11.0) -> void:
	if canvas == null:
		return
	canvas.draw_circle(center + Vector2(1.0, 1.5), radius + 1.0, Color(0.0, 0.0, 0.0, 0.65))
	canvas.draw_circle(center, radius, BLOOD_CRIMSON)
	canvas.draw_circle(center, radius * 0.78, CRIMSON_BRIGHT.darkened(0.15))
	canvas.draw_arc(center, radius * 0.78, 0.0, TAU, 20, BONE_PARCHMENT.darkened(0.25), 1.2)
	# Inner anchor/star rune cross
	canvas.draw_line(center + Vector2(-radius * 0.42, 0.0), center + Vector2(radius * 0.42, 0.0), BONE_PARCHMENT, 1.3)
	canvas.draw_line(center + Vector2(0.0, -radius * 0.42), center + Vector2(0.0, radius * 0.42), BONE_PARCHMENT, 1.3)


static func draw_eldritch_veins(canvas: CanvasItem, rect: Rect2, intensity: float, time_sec: float) -> void:
	if canvas == null or intensity <= 0.01:
		return
	var pulse: float = 0.65 + 0.35 * sin(time_sec * 16.0)
	var alpha: float = clampf(intensity * pulse, 0.0, 0.92)
	var vein_col: Color = Color(CRIMSON_BRIGHT.r, CRIMSON_BRIGHT.g, CRIMSON_BRIGHT.b, alpha)
	var dark_vein: Color = Color(BLOOD_CRIMSON.r, BLOOD_CRIMSON.g, BLOOD_CRIMSON.b, alpha * 0.75)

	var x0: float = rect.position.x + 6.0
	var y0: float = rect.position.y + 6.0
	var x1: float = rect.position.x + rect.size.x - 6.0
	var y1: float = rect.position.y + rect.size.y - 6.0
	var reach: float = 18.0 + 28.0 * intensity

	# Creeping arterial tendrils from the 4 corners
	var corner_origins: Array[Vector2] = [
		Vector2(x0, y0),
		Vector2(x1, y0),
		Vector2(x1, y1),
		Vector2(x0, y1),
	]
	var dirs: Array[Vector2] = [
		Vector2(1.0, 0.55).normalized(),
		Vector2(-1.0, 0.55).normalized(),
		Vector2(-1.0, -0.55).normalized(),
		Vector2(1.0, -0.55).normalized(),
	]

	for i: int in range(4):
		var p0: Vector2 = corner_origins[i]
		var d: Vector2 = dirs[i]
		var p1: Vector2 = p0 + d * (reach * 0.45) + Vector2(sin(time_sec * 9.0 + float(i)) * 3.0, cos(time_sec * 7.0) * 2.5)
		var p2: Vector2 = p1 + d * (reach * 0.55) + Vector2(-d.y * 5.0, d.x * 4.0)
		var branch: Vector2 = p1 + Vector2(d.x * reach * 0.35, -d.y * reach * 0.25)
		canvas.draw_line(p0, p1, dark_vein, 2.6)
		canvas.draw_line(p1, p2, vein_col, 1.6)
		canvas.draw_line(p1, branch, vein_col, 1.2)
