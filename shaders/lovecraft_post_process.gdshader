shader_type spatial;
render_mode unshaded, fog_disabled, depth_draw_never, depth_test_disabled, cull_disabled;

// Stylized Dark Lovecraftian 3D Post-Processing Shader (res://shaders/lovecraft_post_process.gdshader)
// Runs on a full-screen 3D QuadMesh parented to Camera3D at render_priority = -10 (immediately after opaque pass,
// BEFORE transparent rain particles, splash particles, and volumetric beam cones) using hint_screen_texture
// and hint_depth_texture with world-space water masking (world_position.y < 1.85), distance/sky fade (35m..75m),
// and shadow luma masking (smoothstep(0.03, 0.15, screen_luminance)).

uniform sampler2D screen_tex : hint_screen_texture, repeat_disable, filter_linear;
uniform sampler2D depth_tex : hint_depth_texture, repeat_disable, filter_nearest;

uniform vec3 ink_edge_color : source_color = vec3(0.0196, 0.0275, 0.0353); // #050709
uniform float ink_edge_strength : hint_range(0.0, 1.0) = 0.50;

uniform vec3 shadow_split_color : source_color = vec3(0.0235, 0.0431, 0.0627); // #060b10
uniform vec3 highlight_amber_color : source_color = vec3(0.8314, 0.6078, 0.2941); // #d49b4b
uniform vec3 highlight_crimson_color : source_color = vec3(0.6196, 0.1412, 0.1412); // #9e2424

uniform float vignette_inner_radius : hint_range(0.2, 1.0) = 0.62;
uniform float vignette_outer_radius : hint_range(0.5, 1.5) = 1.05;
uniform float vignette_opacity : hint_range(0.0, 1.0) = 0.72;
uniform float film_grain_intensity : hint_range(0.0, 0.08) = 0.016;

void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

float luma(vec3 c) {
	return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

vec3 reconstruct_view_pos(vec2 uv, float raw_depth, mat4 inv_proj) {
	vec3 ndc = vec3(uv * 2.0 - 1.0, raw_depth);
	vec4 view_pos = inv_proj * vec4(ndc, 1.0);
	return view_pos.xyz / view_pos.w;
}

vec3 sample_view_pos(vec2 uv, mat4 inv_proj) {
	float rd = texture(depth_tex, uv).r;
	return reconstruct_view_pos(uv, rd, inv_proj);
}

void fragment() {
	vec2 uv = SCREEN_UV;
	vec2 px = (1.0 / VIEWPORT_SIZE) * 1.25;

	vec3 col = texture(screen_tex, uv).rgb;
	float screen_luminance = luma(col);

	// Reconstruct 3D view-space and world-space position from hardware depth buffer
	float raw_depth = texture(depth_tex, uv).r;
	vec3 view_pos = reconstruct_view_pos(uv, raw_depth, INV_PROJECTION_MATRIX);
	float linear_depth = -view_pos.z;
	vec3 world_position = (INV_VIEW_MATRIX * vec4(view_pos, 1.0)).xyz;

	// =========================================================================
	// 1. 3D DEPTH & NORMAL CREASE EDGE INK-WASH (#050709, strength 0.50)
	//    Masked out on water (world_position.y < 1.85), sky/distant geometry (35m..75m),
	//    and deep shadows (smoothstep(0.03, 0.15, screen_luminance)).
	// =========================================================================
	// Water Plane Mask: if world_position.y < 1.85 (ocean waves/foam), edge_strength = 0.0
	float water_mask = (world_position.y < 1.85) ? 0.0 : smoothstep(1.85, 2.02, world_position.y);

	// Distance & Sky Mask: smoothly fade edge_strength to 0.0 between linear_depth = 35.0 and 75.0
	float sky_mask = step(0.0001, raw_depth);
	float dist_mask = (1.0 - smoothstep(35.0, 75.0, linear_depth)) * sky_mask;

	// Luma / Shadow Mask: never draw harsh black rings inside dark shadow transitions
	float luma_mask = smoothstep(0.03, 0.15, screen_luminance);

	float combined_edge_mask = water_mask * dist_mask * luma_mask;

	float edge_strength = 0.0;
	if (combined_edge_mask > 0.001) {
		vec3 vp_tl = sample_view_pos(uv + vec2(-px.x, -px.y), INV_PROJECTION_MATRIX);
		vec3 vp_tc = sample_view_pos(uv + vec2(0.0,   -px.y), INV_PROJECTION_MATRIX);
		vec3 vp_tr = sample_view_pos(uv + vec2( px.x, -px.y), INV_PROJECTION_MATRIX);
		vec3 vp_ml = sample_view_pos(uv + vec2(-px.x,  0.0),  INV_PROJECTION_MATRIX);
		vec3 vp_mr = sample_view_pos(uv + vec2( px.x,  0.0),  INV_PROJECTION_MATRIX);
		vec3 vp_bl = sample_view_pos(uv + vec2(-px.x,  px.y), INV_PROJECTION_MATRIX);
		vec3 vp_bc = sample_view_pos(uv + vec2(0.0,    px.y), INV_PROJECTION_MATRIX);
		vec3 vp_br = sample_view_pos(uv + vec2( px.x,  px.y), INV_PROJECTION_MATRIX);

		float ref_d = max(linear_depth, 0.35);
		float d_tl = -vp_tl.z;
		float d_tc = -vp_tc.z;
		float d_tr = -vp_tr.z;
		float d_ml = -vp_ml.z;
		float d_mr = -vp_mr.z;
		float d_bl = -vp_bl.z;
		float d_bc = -vp_bc.z;
		float d_br = -vp_br.z;

		// 3D Depth Discontinuity Sobel
		float gx_d = (-d_tl - 2.0 * d_ml - d_bl + d_tr + 2.0 * d_mr + d_br) / ref_d;
		float gy_d = (-d_tl - 2.0 * d_tc - d_tr + d_bl + 2.0 * d_bc + d_br) / ref_d;
		float depth_grad = sqrt(gx_d * gx_d + gy_d * gy_d);

		// Reconstructed View-Space Normal Crease Detection (catches 3D bevels, timber beams, chain links & rod segments)
		vec3 n_center = normalize(cross(vp_mr - vp_ml, vp_tc - vp_bc));
		vec3 n_horiz  = normalize(cross(vp_mr - view_pos, vp_tr - vp_br));
		vec3 n_vert   = normalize(cross(vp_tr - vp_tl, vp_tc - view_pos));
		float normal_crease = max(1.0 - clamp(dot(n_center, n_horiz), 0.0, 1.0), 1.0 - clamp(dot(n_center, n_vert), 0.0, 1.0));

		// Foreground structural crease on above-water geometry (world_position.y >= 1.85)
		float l_tl = luma(texture(screen_tex, uv + vec2(-px.x, -px.y)).rgb);
		float l_tc = luma(texture(screen_tex, uv + vec2(0.0,   -px.y)).rgb);
		float l_tr = luma(texture(screen_tex, uv + vec2( px.x, -px.y)).rgb);
		float l_ml = luma(texture(screen_tex, uv + vec2(-px.x,  0.0)).rgb);
		float l_mr = luma(texture(screen_tex, uv + vec2( px.x,  0.0)).rgb);
		float l_bl = luma(texture(screen_tex, uv + vec2(-px.x,  px.y)).rgb);
		float l_bc = luma(texture(screen_tex, uv + vec2(0.0,    px.y)).rgb);
		float l_br = luma(texture(screen_tex, uv + vec2( px.x,  px.y)).rgb);

		float gx_l = -l_tl - 2.0 * l_ml - l_bl + l_tr + 2.0 * l_mr + l_br;
		float gy_l = -l_tl - 2.0 * l_tc - l_tr + l_bl + 2.0 * l_bc + l_br;
		float luma_grad = sqrt(gx_l * gx_l + gy_l * gy_l);

		float edge_depth = smoothstep(0.06, 0.24, depth_grad);
		float edge_normal = smoothstep(0.18, 0.55, normal_crease) * (1.0 - edge_depth * 0.5);
		float edge_crease = smoothstep(0.20, 0.62, luma_grad) * 0.85;

		float raw_edge = max(max(edge_depth, edge_normal), edge_crease);
		edge_strength = raw_edge * ink_edge_strength * combined_edge_mask;
	}

	col = mix(col, ink_edge_color, clamp(edge_strength, 0.0, 1.0));

	// =========================================================================
	// 2. ELDRITCH SPLIT-TONE COLOR GRADING
	//    Deep shadows -> cold abyssal midnight-teal (#060b10)
	//    Warm highlights -> amber/gold (#d49b4b) & blood-crimson (#9e2424)
	// =========================================================================
	float lum = luma(col);
	float shadow_weight = smoothstep(0.26, 0.01, lum);
	col = mix(col, mix(col, shadow_split_color, 0.42), shadow_weight);

	// Preserve and enrich warm lantern/searchlight amber (#d49b4b) and crimson (#9e2424) accents
	float warmth = clamp((col.r - col.b) * 1.65, 0.0, 1.0);
	float crimson_dominance = clamp((col.r - col.g * 1.35) * 2.1, 0.0, 1.0);
	vec3 warm_target = mix(highlight_amber_color, highlight_crimson_color, crimson_dominance * 0.65);
	float highlight_mask = smoothstep(0.18, 0.78, lum) * warmth;
	col = mix(col, col * mix(vec3(1.0), warm_target * 1.35, 0.26), highlight_mask);

	// =========================================================================
	// 3. OPPRESSIVE ABYSSAL VIGNETTE & ULTRA-FINE ANALOG FILM GRAIN
	// =========================================================================
	vec2 centered = (uv - vec2(0.5)) * vec2(2.0);
	float breath = sin(TIME * 1.15) * 0.018;
	float radial_dist = length(centered * vec2(1.0, 0.92));
	float vig = smoothstep(vignette_inner_radius + breath, vignette_outer_radius + breath, radial_dist);
	col = mix(col, ink_edge_color * 0.65, vig * vignette_opacity);

	// Animated fine film grain (0.016 intensity) to eliminate dark fog banding
	vec2 grain_seed = uv * VIEWPORT_SIZE + vec2(fract(TIME * 17.3) * 413.0, fract(TIME * 29.7) * 619.0);
	float grain = (hash12(grain_seed) - 0.5) * 2.0;
	float fog_band_mask = smoothstep(0.0, 0.04, lum) * smoothstep(0.75, 0.15, lum);
	col += vec3(grain * film_grain_intensity * (0.45 + 0.55 * fog_band_mask));

	ALBEDO = max(col, vec3(0.0));
}
