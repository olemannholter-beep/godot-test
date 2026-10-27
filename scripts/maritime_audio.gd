extends RefCounted

const MIX_RATE: int = 44100


static func _compute_lpf_coeffs(cutoff_hz: float, q: float, sample_rate: float) -> PackedFloat64Array:
	var clamped_fc: float = clampf(cutoff_hz, 20.0, sample_rate * 0.45)
	var omega: float = TAU * clamped_fc / sample_rate
	var sn: float = sin(omega)
	var cs: float = cos(omega)
	var alpha: float = sn / (2.0 * maxf(q, 0.1))
	var b0: float = (1.0 - cs) * 0.5
	var b1: float = 1.0 - cs
	var b2: float = (1.0 - cs) * 0.5
	var a0: float = 1.0 + alpha
	var a1: float = -2.0 * cs
	var a2: float = 1.0 - alpha
	var coeffs: PackedFloat64Array = PackedFloat64Array()
	coeffs.resize(5)
	coeffs[0] = b0 / a0
	coeffs[1] = b1 / a0
	coeffs[2] = b2 / a0
	coeffs[3] = a1 / a0
	coeffs[4] = a2 / a0
	return coeffs


static func _compute_bpf_coeffs(center_hz: float, q: float, sample_rate: float) -> PackedFloat64Array:
	var clamped_fc: float = clampf(center_hz, 25.0, sample_rate * 0.45)
	var omega: float = TAU * clamped_fc / sample_rate
	var sn: float = sin(omega)
	var cs: float = cos(omega)
	var alpha: float = sn / (2.0 * maxf(q, 0.1))
	var b0: float = alpha
	var b1: float = 0.0
	var b2: float = -alpha
	var a0: float = 1.0 + alpha
	var a1: float = -2.0 * cs
	var a2: float = 1.0 - alpha
	var coeffs: PackedFloat64Array = PackedFloat64Array()
	coeffs.resize(5)
	coeffs[0] = b0 / a0
	coeffs[1] = b1 / a0
	coeffs[2] = b2 / a0
	coeffs[3] = a1 / a0
	coeffs[4] = a2 / a0
	return coeffs


static func _apply_biquad_pass(samples: PackedFloat32Array, coeffs: PackedFloat64Array) -> void:
	var b0: float = float(coeffs[0])
	var b1: float = float(coeffs[1])
	var b2: float = float(coeffs[2])
	var a1: float = float(coeffs[3])
	var a2: float = float(coeffs[4])
	var x1: float = 0.0
	var x2: float = 0.0
	var y1: float = 0.0
	var y2: float = 0.0
	var count: int = samples.size()
	for i: int in range(count):
		var x0: float = samples[i]
		var y0: float = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
		x2 = x1
		x1 = x0
		y2 = y1
		y1 = y0
		samples[i] = y0


static func _apply_cascaded_lpf(samples: PackedFloat32Array, cutoff_hz: float, q: float = 0.707) -> void:
	var coeffs: PackedFloat64Array = _compute_lpf_coeffs(cutoff_hz, q, float(MIX_RATE))
	_apply_biquad_pass(samples, coeffs)
	_apply_biquad_pass(samples, coeffs)


static func _pack_to_wav(samples: PackedFloat32Array, gain: float, loop_enabled: bool = false) -> AudioStreamWAV:
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
			# Cross-fade loop boundary to exact zero crossing over 64 samples
			if i < 64:
				env_edge *= float(i) / 64.0
			elif i >= count - 64:
				env_edge *= float((count - 1) - i) / 64.0

		var v: float = clampf(samples[i] * gain * env_edge, -0.98, 0.98)
		var s16: int = clampi(int(round(v * 32767.0)), -32767, 32767)
		pcm.encode_s16(i * 2, s16)

	var wav: AudioStreamWAV = AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = MIX_RATE
	wav.stereo = false
	wav.data = pcm
	if loop_enabled:
		wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
		wav.loop_begin = 0
		wav.loop_end = count
	else:
		wav.loop_mode = AudioStreamWAV.LOOP_DISABLED
	return wav


static func _hash_noise(index: int, seed_offset: float = 0.0) -> float:
	var s: float = sin(float(index) * 12.9898 + seed_offset * 78.233) * 43758.5453
	return (s - floor(s)) * 2.0 - 1.0


# 1. Heavy Marine Diesel Engine Loop:
# Deep low-passed (140 Hz cutoff) rhythmic 4-stroke cylinder chug with warm sub-bass thrum (45-85 Hz)
# and subtle water-exhaust burble. Zero harsh high-frequency buzz.
static func build_diesel_engine_loop() -> AudioStreamWAV:
	var duration_sec: float = 2.0
	var count: int = int(duration_sec * float(MIX_RATE))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	# Choose integer cycles over 2.0s for a seamless zero-click loop
	var chug_freq: float = 14.0 # 28 chugs in 2.0s
	var sub_freq_a: float = 49.0 # 98 cycles in 2.0s
	var sub_freq_b: float = 70.0 # 140 cycles in 2.0s
	var burble_freq: float = 84.0 # 168 cycles in 2.0s
	var pink_state: float = 0.0

	for i: int in range(count):
		var t: float = float(i) / float(MIX_RATE)
		var chug_phase: float = fmod(t * chug_freq, 1.0)
		var four_stroke_accent: float = 1.0 if (int(floor(t * chug_freq)) % 2 == 0) else 0.76
		var cylinder_pulse: float = exp(-chug_phase * 5.8) * four_stroke_accent

		# Warm sub-bass crankshaft and hull resonance (45-85 Hz)
		var sub_thrum: float = (
			sin(t * TAU * sub_freq_a) * 0.52
			+ sin(t * TAU * sub_freq_b + cylinder_pulse * 0.8) * 0.34
			+ sin(t * TAU * (sub_freq_a * 0.5)) * 0.28
		)

		# Wet exhaust water-muffler burble
		var raw_n: float = _hash_noise(i, 1.7)
		pink_state = pink_state * 0.94 + raw_n * 0.06
		var burble: float = sin(t * TAU * burble_freq + pink_state * 3.5) * 0.22 * (0.4 + 0.6 * cylinder_pulse)

		buf[i] = sub_thrum * (0.55 + 0.45 * cylinder_pulse) + burble + pink_state * cylinder_pulse * 0.30

	# Strict cascaded 24dB/oct Biquad Low-Pass Filter at 140 Hz cutoff
	_apply_cascaded_lpf(buf, 140.0, 0.78)
	return _pack_to_wav(buf, 0.82, true)


# 2. Rod Cast Whoosh:
# Smooth band-passed air whip (300 Hz -> 120 Hz pitch sweep)
static func build_rod_cast_whoosh_wav() -> AudioStreamWAV:
	var duration_sec: float = 0.44
	var count: int = int(duration_sec * float(MIX_RATE))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	var bp_x1: float = 0.0
	var bp_x2: float = 0.0
	var bp_y1: float = 0.0
	var bp_y2: float = 0.0
	var cord_phase: float = 0.0

	for i: int in range(count):
		var frac: float = float(i) / float(max(1, count - 1))
		# Smooth bell envelope peaking at 28% of the whip
		var attack: float = clampf(frac / 0.22, 0.0, 1.0)
		var decay: float = exp(-pow(maxf(0.0, frac - 0.18) * 2.8, 1.6))
		var env: float = attack * attack * decay

		var sweep_hz: float = lerpf(300.0, 120.0, pow(frac, 0.75))
		var coeffs: PackedFloat64Array = _compute_bpf_coeffs(sweep_hz, 2.2, float(MIX_RATE))
		var x0: float = _hash_noise(i, 3.1)
		var y0: float = (
			float(coeffs[0]) * x0
			+ float(coeffs[1]) * bp_x1
			+ float(coeffs[2]) * bp_x2
			- float(coeffs[3]) * bp_y1
			- float(coeffs[4]) * bp_y2
		)
		bp_x2 = bp_x1
		bp_x1 = x0
		bp_y2 = bp_y1
		bp_y1 = y0

		cord_phase += TAU * sweep_hz / float(MIX_RATE)
		var bamboo_flex: float = sin(cord_phase) * 0.24
		buf[i] = (y0 * 1.45 + bamboo_flex) * env

	_apply_cascaded_lpf(buf, 520.0, 0.707)
	return _pack_to_wav(buf, 0.85, false)


# 3. Layered Bubble-Plunge Water Splash:
# Filtered pink noise burst with low-frequency cavity thump and resonant droplet filters
static func build_water_splash_wav() -> AudioStreamWAV:
	var duration_sec: float = 0.58
	var count: int = int(duration_sec * float(MIX_RATE))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	var pink: float = 0.0
	var plunge_phase: float = 0.0
	var drop1_phase: float = 0.0
	var drop2_phase: float = 0.0
	var drop3_phase: float = 0.0

	for i: int in range(count):
		var t: float = float(i) / float(MIX_RATE)
		var frac: float = float(i) / float(max(1, count - 1))
		var raw_n: float = _hash_noise(i, 9.4)
		pink = pink * 0.91 + raw_n * 0.09

		# Cavity plunge thump (115 Hz -> 48 Hz)
		var plunge_hz: float = lerpf(115.0, 48.0, minf(1.0, t * 6.5))
		plunge_phase += TAU * plunge_hz / float(MIX_RATE)
		var cavity_thump: float = sin(plunge_phase) * exp(-t * 14.0) * 0.65

		# Foam wash envelope
		var wash_env: float = clampf(t / 0.015, 0.0, 1.0) * exp(-t * 5.8)

		# 3 resonant bubble droplets (upward pitch chirps as air bubbles rise and pop)
		var d1: float = 0.0
		if t >= 0.04 and t < 0.22:
			var dt1: float = t - 0.04
			drop1_phase += TAU * lerpf(280.0, 540.0, dt1 / 0.18) / float(MIX_RATE)
			d1 = sin(drop1_phase) * exp(-dt1 * 24.0) * 0.32

		var d2: float = 0.0
		if t >= 0.12 and t < 0.34:
			var dt2: float = t - 0.12
			drop2_phase += TAU * lerpf(340.0, 660.0, dt2 / 0.22) / float(MIX_RATE)
			d2 = sin(drop2_phase) * exp(-dt2 * 22.0) * 0.26

		var d3: float = 0.0
		if t >= 0.23 and t < 0.48:
			var dt3: float = t - 0.23
			drop3_phase += TAU * lerpf(240.0, 490.0, dt3 / 0.25) / float(MIX_RATE)
			d3 = sin(drop3_phase) * exp(-dt3 * 20.0) * 0.22

		var tail_fade: float = 1.0 - pow(frac, 3.0)
		buf[i] = (cavity_thump + pink * wash_env * 0.95 + d1 + d2 + d3) * tail_fade

	_apply_cascaded_lpf(buf, 880.0, 0.75)
	return _pack_to_wav(buf, 0.88, false)


# 4. Subtle Bobber Nibble Dip:
# Soft muted underwater bubble-tug
static func build_nibble_dip_wav() -> AudioStreamWAV:
	var duration_sec: float = 0.18
	var count: int = int(duration_sec * float(MIX_RATE))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	var phase: float = 0.0
	var pink: float = 0.0
	for i: int in range(count):
		var t: float = float(i) / float(MIX_RATE)
		var frac: float = float(i) / float(max(1, count - 1))
		var freq: float = lerpf(145.0, 265.0, pow(frac, 0.65))
		phase += TAU * freq / float(MIX_RATE)
		pink = pink * 0.92 + _hash_noise(i, 5.2) * 0.08
		var env: float = clampf(t / 0.008, 0.0, 1.0) * exp(-t * 19.0)
		buf[i] = (sin(phase) * 0.65 + pink * 0.35) * env

	_apply_cascaded_lpf(buf, 520.0, 0.72)
	return _pack_to_wav(buf, 0.82, false)


# 5. Precision Brass Reel Clicker (2-4ms damped metallic impulse):
static func build_reel_click_wav() -> AudioStreamWAV:
	var duration_sec: float = 0.032
	var count: int = int(duration_sec * float(MIX_RATE))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	for i: int in range(count):
		var t: float = float(i) / float(MIX_RATE)
		# Crisp 2.8ms exponential mechanical pawl impulse
		var impulse_env: float = exp(-t / 0.0028)
		var body_env: float = exp(-t / 0.0065)
		var pawl_mode_a: float = sin(t * TAU * 780.0) * 0.55
		var pawl_mode_b: float = sin(t * TAU * 1240.0) * 0.35
		var brass_ping: float = sin(t * TAU * 1820.0) * 0.18
		var click_trans: float = _hash_noise(i, 11.3) * 0.35 * impulse_env
		buf[i] = (pawl_mode_a + pawl_mode_b) * body_env + (brass_ping + click_trans) * impulse_env

	_apply_cascaded_lpf(buf, 1750.0, 0.707)
	return _pack_to_wav(buf, 0.80, false)


# 6. Heavy Drag Ratchet Burst (when fish surges or strikes):
# Rapid multi-tooth brass drag pawl burst with warm wooden rod groan
static func build_drag_scream_wav() -> AudioStreamWAV:
	var duration_sec: float = 0.34
	var count: int = int(duration_sec * float(MIX_RATE))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	var tooth_interval: float = 0.036
	for i: int in range(count):
		var t: float = float(i) / float(MIX_RATE)
		var frac: float = float(i) / float(max(1, count - 1))
		var local_t: float = fmod(t, tooth_interval)
		var tooth_env: float = exp(-local_t / 0.0032)
		var overall_env: float = sin(frac * PI)

		var pawl_sig: float = (
			sin(local_t * TAU * 860.0) * 0.52
			+ sin(local_t * TAU * 1380.0) * 0.32
			+ _hash_noise(i, 6.4) * 0.25
		) * tooth_env

		var rod_groan: float = sin(t * TAU * 92.0 + sin(t * TAU * 14.0) * 1.4) * 0.28
		buf[i] = (pawl_sig + rod_groan) * overall_env

	_apply_cascaded_lpf(buf, 1450.0, 0.72)
	return _pack_to_wav(buf, 0.82, false)


# 7. Hull & Rigging Timber Creak:
# Deep wooden timber groan (65-110 Hz FM-modulated resonant creak)
static func build_hull_creak_wav() -> AudioStreamWAV:
	var duration_sec: float = 0.85
	var count: int = int(duration_sec * float(MIX_RATE))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	var phase: float = 0.0
	for i: int in range(count):
		var t: float = float(i) / float(MIX_RATE)
		var frac: float = float(i) / float(max(1, count - 1))
		var env: float = sin(frac * PI) * (0.75 + 0.25 * sin(t * TAU * 5.5))
		var base_hz: float = lerpf(72.0, 96.0, sin(frac * PI)) + sin(t * TAU * 11.0) * 12.0
		phase += TAU * base_hz / float(MIX_RATE)
		# Stick-slip timber grain harmonics
		var sig: float = (
			sin(phase) * 0.58
			+ sin(phase * 2.0 + 0.4) * 0.26
			+ sin(phase * 3.0 + 1.1) * 0.12
		)
		buf[i] = sig * env

	_apply_cascaded_lpf(buf, 240.0, 0.85)
	return _pack_to_wav(buf, 0.76, false)


# 8. Abyssal Dread Drone / Bronze Bell Undertone:
# Eerie sub-audible eldritch bronze-bell / bowed-metal undertone
static func build_abyssal_dread_drone_wav() -> AudioStreamWAV:
	var duration_sec: float = 1.35
	var count: int = int(duration_sec * float(MIX_RATE))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	for i: int in range(count):
		var t: float = float(i) / float(MIX_RATE)
		var frac: float = float(i) / float(max(1, count - 1))
		var attack: float = clampf(t / 0.14, 0.0, 1.0)
		var release: float = exp(-maxf(0.0, t - 0.14) * 2.4)
		var env: float = attack * release * (1.0 - pow(frac, 4.0))

		# Deep bronze bell inharmonic partials (55 Hz fundamental + 82.5 Hz + 118.8 Hz + 167.2 Hz)
		var sub_bell: float = sin(t * TAU * 55.0) * 0.48
		var fifth_drone: float = sin(t * TAU * 82.5 + sin(t * TAU * 2.2) * 0.6) * 0.30
		var minor_tierce: float = sin(t * TAU * 118.8) * 0.18 * exp(-t * 1.8)
		var bowed_metal: float = sin(t * TAU * 167.2 + sin(t * TAU * 5.0) * 1.2) * 0.12 * exp(-t * 2.2)
		buf[i] = (sub_bell + fifth_drone + minor_tierce + bowed_metal) * env

	_apply_cascaded_lpf(buf, 260.0, 0.78)
	return _pack_to_wav(buf, 0.84, false)


# 9. Line Snap Recoil Thud:
static func build_line_snap_wav() -> AudioStreamWAV:
	var duration_sec: float = 0.38
	var count: int = int(duration_sec * float(MIX_RATE))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	var phase: float = 0.0
	for i: int in range(count):
		var t: float = float(i) / float(MIX_RATE)
		var freq: float = lerpf(240.0, 56.0, minf(1.0, t * 5.5))
		phase += TAU * freq / float(MIX_RATE)
		var recoil_thud: float = sin(phase) * exp(-t * 12.0) * 0.68
		var whip_crack: float = _hash_noise(i, 14.2) * exp(-t * 38.0) * 0.52
		var wire_twang: float = sin(t * TAU * 410.0) * exp(-t * 22.0) * 0.25
		buf[i] = recoil_thud + whip_crack + wire_twang

	_apply_cascaded_lpf(buf, 760.0, 0.74)
	return _pack_to_wav(buf, 0.88, false)


# 10. Heavy Iron Latch Thud (UI Button / Ledger Tab):
static func build_iron_latch_wav() -> AudioStreamWAV:
	var duration_sec: float = 0.12
	var count: int = int(duration_sec * float(MIX_RATE))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	for i: int in range(count):
		var t: float = float(i) / float(MIX_RATE)
		var iron_thud: float = sin(t * TAU * 92.0) * exp(-t * 34.0) * 0.62
		var latch_clank: float = (
			sin(t * TAU * 340.0) * 0.32
			+ sin(t * TAU * 580.0) * 0.18
			+ _hash_noise(i, 8.8) * 0.22
		) * exp(-t * 68.0)
		buf[i] = iron_thud + latch_clank

	_apply_cascaded_lpf(buf, 820.0, 0.72)
	return _pack_to_wav(buf, 0.80, false)


# 11. Harbor Coin & Brass Sovereign Clink (Selling Catch / Upgrades):
static func build_coin_clink_wav() -> AudioStreamWAV:
	var duration_sec: float = 0.42
	var count: int = int(duration_sec * float(MIX_RATE))
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(count)

	for i: int in range(count):
		var t: float = float(i) / float(MIX_RATE)
		var pouch_thud: float = sin(t * TAU * 110.0) * exp(-t * 26.0) * 0.42

		# Three staggered damped metallic coin strikes
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

	_apply_cascaded_lpf(buf, 2900.0, 0.707)
	return _pack_to_wav(buf, 0.78, false)
