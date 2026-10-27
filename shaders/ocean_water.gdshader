shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec4 deep_color : source_color = vec4(0.04, 0.11, 0.15, 1.0);
uniform vec4 shallow_color : source_color = vec4(0.11, 0.26, 0.24, 1.0);
uniform vec4 foam_color : source_color = vec4(0.78, 0.84, 0.86, 1.0);
uniform vec4 fog_tint_color : source_color = vec4(0.10, 0.14, 0.16, 1.0);

uniform vec3 deep_abyss_color : source_color = vec3(0.008, 0.022, 0.035);
uniform vec3 coastal_slate_color : source_color = vec3(0.024, 0.068, 0.088);
uniform vec3 kelp_patch_color : source_color = vec3(0.018, 0.062, 0.052);
uniform vec3 sss_scatter_color : source_color = vec3(0.05, 0.24, 0.26);

uniform float wave_speed : hint_range(0.1, 5.0) = 1.25;
uniform float wave_height : hint_range(0.0, 3.0) = 0.75;
global uniform float ocean_time;
uniform float wave_time = 0.0;
uniform float normal_scale : hint_range(0.005, 0.5) = 0.045;
uniform float normal_strength : hint_range(0.0, 2.0) = 0.95;
uniform float foam_scale : hint_range(0.01, 0.5) = 0.08;
uniform float roughness : hint_range(0.0, 1.0) = 0.22;
uniform float metallic : hint_range(0.0, 1.0) = 0.18;
uniform float specular : hint_range(0.0, 1.0) = 0.92;

uniform sampler2D normal_map_a : hint_normal, repeat_enable;
uniform sampler2D normal_map_b : hint_normal, repeat_enable;
uniform sampler2D foam_noise : repeat_enable;

uniform mat4 boat_inv_xform = mat4(1.0);
uniform vec3 boat_hull_half_size = vec3(1.85, 2.2, 5.2);

varying float v_wave_height;
varying vec3 v_world_pos;

vec3 gerstner_wave(vec2 dir, float steepness, float wavelength, vec2 pos, float time, inout vec3 tangent, inout vec3 binormal) {
	float k = 6.28318530718 / max(wavelength, 0.001);
	float c = sqrt(9.8 / k) * wave_speed;
	vec2 d = normalize(dir);
	float f = k * (dot(d, pos) - c * time);
	float s = steepness * wave_height;
	float a = s / k;

	float sin_f = sin(f);
	float cos_f = cos(f);

	tangent += vec3(
		-d.x * d.x * (s * sin_f),
		d.x * (s * cos_f),
		-d.x * d.y * (s * sin_f)
	);
	binormal += vec3(
		-d.x * d.y * (s * sin_f),
		d.y * (s * cos_f),
		-d.y * d.y * (s * sin_f)
	);

	return vec3(
		d.x * (a * cos_f),
		a * sin_f,
		d.y * (a * cos_f)
	);
}

// --- Procedural Hash, Value Noise, FBM & Cellular / Worley Functions ---

vec2 hash22(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.xx + p3.yz) * p3.zy);
}

float hash21(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = hash21(i);
	float b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0));
	float d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// Analytical value noise with XY gradient for crisp procedural normal perturbation
vec3 value_noise_deriv(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	vec2 du = 6.0 * f * (1.0 - f);

	float a = hash21(i);
	float b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0));
	float d = hash21(i + vec2(1.0, 1.0));

	float k0 = a;
	float k1 = b - a;
	float k2 = c - a;
	float k3 = a - b - c + d;

	float val = k0 + k1 * u.x + k2 * u.y + k3 * u.x * u.y;
	vec2 grad = du * vec2(k1 + k3 * u.y, k2 + k3 * u.x);
	return vec3(val, grad);
}

float fbm_4(vec2 p) {
	float sum = 0.0;
	float amp = 0.5;
	mat2 rot = mat2(vec2(0.80, 0.60), vec2(-0.60, 0.80));
	for (int i = 0; i < 4; i++) {
		sum += amp * value_noise(p);
		p = rot * p * 2.03 + vec2(13.7, 29.1);
		amp *= 0.5;
	}
	return sum;
}

// Cellular Worley noise + analytical feature-vector gradient for capillary sparkles and bubble froth
vec3 worley_deriv(vec2 p) {
	vec2 n = floor(p);
	vec2 f = fract(p);
	float min_dist = 8.0;
	vec2 min_vec = vec2(0.0);

	for (int j = -1; j <= 1; j++) {
		for (int i = -1; i <= 1; i++) {
			vec2 g = vec2(float(i), float(j));
			vec2 o = hash22(n + g);
			vec2 r = g + o - f;
			float d = dot(r, r);
			if (d < min_dist) {
				min_dist = d;
				min_vec = r;
			}
		}
	}
	float dist = sqrt(max(min_dist, 0.0001));
	return vec3(dist, -min_vec / dist);
}

void vertex() {
	float t = (wave_time > 0.0) ? wave_time : ocean_time;
	vec3 world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 tangent = vec3(1.0, 0.0, 0.0);
	vec3 binormal = vec3(0.0, 0.0, 1.0);
	vec3 displacement = vec3(0.0);

	// 4 layered Gerstner waves with varied directions and frequencies (evaluated in true world-space XZ)
	displacement += gerstner_wave(vec2(1.0, 0.35), 0.30, 18.0, world_pos.xz, t, tangent, binormal);
	displacement += gerstner_wave(vec2(0.65, -0.75), 0.24, 11.5, world_pos.xz, t * 1.08, tangent, binormal);
	displacement += gerstner_wave(vec2(-0.45, 0.88), 0.18, 6.8, world_pos.xz, t * 1.15, tangent, binormal);
	displacement += gerstner_wave(vec2(-0.82, -0.55), 0.14, 4.2, world_pos.xz, t * 1.25, tangent, binormal);

	vec3 displaced_world_pos = world_pos + displacement;
	vec3 local_pos = (boat_inv_xform * vec4(displaced_world_pos, 1.0)).xyz;

	// Normalized ellipsoidal distance strictly inside the inner hull footprint (never depressing water outside the hull walls):
	vec3 hull_scale = boat_hull_half_size / vec3(1.85, 2.2, 5.2);
	vec2 inner_half_xz = vec2(0.78 * hull_scale.x, 2.05 * hull_scale.z);
	vec2 horiz_norm = local_pos.xz / max(inner_half_xz, vec2(0.001));
	float hull_dist_sq = dot(horiz_norm, horiz_norm);

	// If the vertex is horizontally inside the inner hull footprint and below the gunwales:
	if (hull_dist_sq < 1.0 && local_pos.y < boat_hull_half_size.y && local_pos.y > -boat_hull_half_size.y) {
		// Depress the wave displacement smoothly below the floorboards/deck:
		float depress_mask = clamp(1.0 - hull_dist_sq, 0.0, 1.0);
		float depress_y = depress_mask * (local_pos.y + 0.55);
		displacement.y -= depress_y;
		displaced_world_pos.y -= depress_y;
	}

	VERTEX += displacement;
	v_wave_height = displacement.y;
	v_world_pos = displaced_world_pos;

	TANGENT = normalize(tangent);
	BINORMAL = normalize(binormal);
	NORMAL = normalize(cross(binormal, tangent));
}

void fragment() {
	vec3 local_frag_pos = (boat_inv_xform * vec4(v_world_pos, 1.0)).xyz;
	vec3 hull_scale = boat_hull_half_size / vec3(1.85, 2.2, 5.2);
	float bow_taper = clamp((-local_frag_pos.z / max(hull_scale.z, 0.001) - 0.55) / 1.65, 0.0, 1.0);
	float stern_taper = clamp((local_frag_pos.z / max(hull_scale.z, 0.001) - 1.05) / 1.20, 0.0, 1.0);
	float inner_half_w = mix(0.82, 0.08, bow_taper * bow_taper) * mix(1.0, 0.72, stern_taper) * hull_scale.x;
	vec3 inner_hull_bounds = vec3(inner_half_w, boat_hull_half_size.y, 2.18 * hull_scale.z);
	if (all(lessThan(abs(local_frag_pos), inner_hull_bounds * 0.95))) {
		discard;
	}

	float t = (wave_time > 0.0) ? wave_time : ocean_time;
	vec2 world_xz = v_world_pos.xz;

	// Geometric world-space normal before normal-map perturbation (for steep slope detection)
	vec3 geom_world_normal = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
	float geom_slope = clamp(1.0 - geom_world_normal.y, 0.0, 1.0);

	// =========================================================================
	// 1. MACRO OCEAN COLOR VARIATION (World-Space Turbidity & Swirls)
	// =========================================================================
	float macro_swirl = fbm_4(world_xz * 0.004 + vec2(t * 0.003, -t * 0.002));
	float meso_turbidity = fbm_4(world_xz * 0.015 + vec2(-t * 0.008, t * 0.006) + macro_swirl * 1.6);

	float slate_blend = smoothstep(0.28, 0.74, macro_swirl);
	float kelp_blend = smoothstep(0.46, 0.84, meso_turbidity) * smoothstep(0.20, 0.70, 1.0 - macro_swirl * 0.5);

	vec3 macro_water_color = mix(deep_abyss_color, coastal_slate_color, slate_blend);
	macro_water_color = mix(macro_water_color, kelp_patch_color, kelp_blend * 0.80);

	// Wave height contrast: keep unlit water troughs and slopes deep, dark liquid obsidian
	float trough_to_crest = smoothstep(-wave_height * 1.15, wave_height * 1.15, v_wave_height);
	float trough_shadow = mix(0.28, 0.72, trough_to_crest);

	vec3 obsidian_trough = vec3(0.025, 0.048, 0.072);
	vec3 base_water = mix(obsidian_trough, macro_water_color * trough_shadow + vec3(0.02, 0.04, 0.06), smoothstep(0.0, 0.75, trough_to_crest));

	// =========================================================================
	// 2. MULTI-LAYERED MICRO-RIPPLE NORMALS & 4K SPARKLE
	// =========================================================================
	// Base scrolling normal maps
	vec2 uv_a = world_xz * normal_scale + vec2(t * 0.035, t * 0.022);
	vec2 uv_b = world_xz * (normal_scale * 1.37) + vec2(-t * 0.028, t * 0.031);
	vec2 tex_xy_a = texture(normal_map_a, uv_a).rg * 2.0 - 1.0;
	vec2 tex_xy_b = texture(normal_map_b, uv_b).rg * 2.0 - 1.0;
	vec2 base_norm_xy = (tex_xy_a + tex_xy_b) * 0.5;

	// Scale 1: Medium Chop (world_pos.xz * 0.22) - crisp secondary wind-chop facets
	vec2 chop_uv_1 = world_xz * 0.22 + vec2(t * 0.42, t * 0.16);
	vec2 chop_uv_2 = (mat2(vec2(0.92, -0.39), vec2(0.39, 0.92)) * world_xz) * 0.22 + vec2(t * 0.34, -t * 0.24);
	vec2 medium_chop_grad = value_noise_deriv(chop_uv_1).yz * 0.65 + value_noise_deriv(chop_uv_2).yz * 0.55;

	// Scale 2 & 3: Fine Capillary Ripples (world_pos.xz * 1.15 & 2.4) at offset angles around storm wind
	// Use smooth C1 value_noise_deriv instead of conical Worley pits so point lights never create dark pockmark dots
	mat2 wind_rot_a = mat2(vec2(0.96, 0.28), vec2(-0.28, 0.96));
	mat2 wind_rot_b = mat2(vec2(0.91, -0.41), vec2(0.41, 0.91));
	vec2 cap_uv_1 = (wind_rot_a * world_xz) * 1.05 + vec2(t * 0.95, t * 0.34);
	vec2 cap_uv_2 = (wind_rot_b * world_xz) * 1.85 + vec2(t * 1.35, -t * 0.48);

	vec3 cap_deriv_1 = value_noise_deriv(cap_uv_1);
	vec3 cap_deriv_2 = value_noise_deriv(cap_uv_2);
	vec2 capillary_grad = cap_deriv_1.yz * 0.24 + cap_deriv_2.yz * 0.18;

	// Combine all 3 detail scales into tangent-space NORMAL_MAP
	vec2 combined_xy = base_norm_xy * 0.58 + medium_chop_grad * 0.34 + capillary_grad * 0.26;
	float combined_z = sqrt(max(1.0 - dot(combined_xy, combined_xy), 0.12));
	vec3 final_tangent_normal = normalize(vec3(combined_xy, combined_z));
	NORMAL_MAP = final_tangent_normal * 0.5 + 0.5;
	NORMAL_MAP_DEPTH = normal_strength;

	// =========================================================================
	// 3. WIND-STREAKED FOAM VEINS & WAVE-CREST WHITECAPS
	// =========================================================================
	float crest_factor = clamp((v_wave_height / max(wave_height * 1.55, 0.001)) * 0.5 + 0.5, 0.0, 1.0);

	// Smooth multi-scale FBM sea-froth (no cellular black center holes/pockmarks)
	vec2 foam_uv_1 = world_xz * (foam_scale * 1.8) + vec2(t * 0.04, -t * 0.03);
	vec2 foam_uv_2 = world_xz * (foam_scale * 3.2) - vec2(t * 0.025, t * 0.035);
	float froth_fbm_a = fbm_4(foam_uv_1);
	float froth_fbm_b = fbm_4(foam_uv_2);
	float lacy_froth = smoothstep(0.28, 0.76, mix(froth_fbm_a, froth_fbm_b, 0.5));

	// Breaking Crest Foam: high wave height + steep surface slope
	float steep_crest_driver = smoothstep(0.58, 0.92, crest_factor + geom_slope * 1.20);
	float whitecap_mask = smoothstep(0.38, 0.72, steep_crest_driver * (0.45 + 0.85 * lacy_froth));

	// Wind-Driven Foam Streaks (Langmuir Lanes): anisotropic FBM stretched along wind vector
	vec2 langmuir_uv = vec2(v_world_pos.x * 0.08 + t * 0.3, v_world_pos.z * 0.45);
	vec2 warp_offset = vec2(
		value_noise(world_xz * 0.06 + vec2(t * 0.04, 0.0)),
		value_noise(world_xz * 0.06 - vec2(0.0, t * 0.04))
	) * 0.65;
	float langmuir_fbm = fbm_4(langmuir_uv + warp_offset);
	float bubble_veins = smoothstep(0.60, 0.80, langmuir_fbm) * (0.45 + 0.55 * lacy_froth);
	// Modulate streaks across wave slopes and troughs
	float streak_mask = bubble_veins * mix(0.32, 0.78, trough_to_crest);

	float total_foam_mask = clamp(whitecap_mask + streak_mask * 0.50, 0.0, 1.0);
	vec3 whitecap_foam_rgb = vec3(0.78, 0.84, 0.86);

	// =========================================================================
	// 4. VARIABLE WIND-SLICK ROUGHNESS (ZERO SELF-EMISSION IN DARKNESS)
	// =========================================================================
	// Wind-scoured patches vs mirror-like wind slicks in the troughs (0.14 to 0.42)
	float wind_scour = smoothstep(0.30, 0.75, meso_turbidity * 0.65 + cap_deriv_1.x * 0.35);
	float surface_roughness_factor = clamp(trough_to_crest * 0.65 + wind_scour * 0.35 + total_foam_mask * 0.55, 0.0, 1.0);
	float dynamic_roughness = mix(0.14, 0.42, surface_roughness_factor);

	ALBEDO = max(base_water, vec3(0.0));
	EMISSION = vec3(0.0);
	ROUGHNESS = dynamic_roughness;
	METALLIC = mix(metallic, 0.04, total_foam_mask);
	SPECULAR = specular;
}

void light() {
	if (LIGHT_IS_DIRECTIONAL) {
		// =====================================================================
		// 5A. LUNAR DIFFUSE & RIM-WRAP + SILVER LUNAR GLITTER-PATH (THE MOON)
		// =====================================================================
		float moon_wrap = max(dot(NORMAL, LIGHT), 0.0) * 0.7 + 0.3;
		vec3 lunar_slate_tint = mix(ALBEDO, vec3(0.14, 0.24, 0.34), 0.78);
		DIFFUSE_LIGHT += lunar_slate_tint * moon_wrap * LIGHT_COLOR * ATTENUATION * 2.25;

		vec3 moon_half = normalize(LIGHT + VIEW);
		float moon_ndoth = max(dot(NORMAL, moon_half), 0.0001);
		float silver_glitter = pow(moon_ndoth, 24.0) * 0.35 + pow(moon_ndoth, 96.0) * 0.8;
		SPECULAR_LIGHT += silver_glitter * moon_wrap * LIGHT_COLOR * ATTENUATION;
	} else {
		// =====================================================================
		// 5. GRAZING-ANGLE LONG-RANGE WATER ILLUMINATION & SUBSURFACE SCATTER
		// =====================================================================
		float n_dot_l = max(dot(NORMAL, LIGHT), 0.0);
		// 0.45 base wrap ensures shallow long-range spotlight rays still illuminate distant wave faces toward the overhead camera
		float light_reach = n_dot_l * 0.55 + 0.45;
		vec3 subsurface_tint = mix(ALBEDO, vec3(0.06, 0.22, 0.25), 0.45);
		DIFFUSE_LIGHT += subsurface_tint * LIGHT_COLOR * ATTENUATION * light_reach * 1.15;

		// Wave crest foam brightening and teal subsurface scatter strictly inside light()
		float t_light = (ocean_time > 0.0) ? ocean_time : ((wave_time > 0.0) ? wave_time : TIME);
		float crest_mask = smoothstep(-0.08, wave_height * 0.88, v_wave_height);
		float froth_a = fbm_4(v_world_pos.xz * (foam_scale * 1.8) + vec2(t_light * 0.04, -t_light * 0.03));
		float lit_foam = clamp(crest_mask * smoothstep(0.28, 0.72, froth_a), 0.0, 1.0);
		vec3 lit_crest_contrib = (sss_scatter_color * crest_mask * 0.42 + foam_color.rgb * lit_foam * 0.58);
		DIFFUSE_LIGHT += lit_crest_contrib * LIGHT_COLOR * ATTENUATION * light_reach;

		// =====================================================================
		// 6. WIDE SOFT SPECULAR SHEEN ON WAVE SLOPES FACING THE LIGHT
		// =====================================================================
		vec3 half_vec = normalize(VIEW + LIGHT);
		float ndoth = max(dot(NORMAL, half_vec), 0.0001);
		float ndotv = max(dot(NORMAL, VIEW), 0.0001);

		// For a boat-mounted spotlight viewed from an overhead chase camera, VIEW and LIGHT both point back toward the boat,
		// so half_vec is tilted toward the boat; use a broad exponent (4.2 and 14.0) + wave slope facing the light so distant swells shimmer
		float wave_slope_toward_light = clamp(n_dot_l * 2.2 + 0.20, 0.0, 1.25);
		float wide_sheen = pow(ndoth, 4.2) * 0.16 + pow(ndoth, 14.0) * 0.42 + pow(ndoth, 38.0) * 0.60;
		float grazing_boost = 1.0 + 0.85 * pow(max(1.0 - ndotv, 0.0001), 1.8);
		vec3 spec_contrib = (wide_sheen * grazing_boost * wave_slope_toward_light) * LIGHT_COLOR * ATTENUATION;
		SPECULAR_LIGHT += max(spec_contrib, vec3(0.0));
	}
}
