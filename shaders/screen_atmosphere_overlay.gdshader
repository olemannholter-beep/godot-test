shader_type canvas_item;
render_mode blend_mix;

uniform sampler2D screen_texture : hint_screen_texture, filter_linear_mipmap;

uniform float camera_yaw = 0.0;
uniform float camera_pitch = 0.0;
uniform float boat_speed = 0.0;
uniform float rain_intensity : hint_range(0.0, 1.0) = 0.85;
uniform float fog_density_factor : hint_range(0.0, 2.0) = 1.0;
uniform vec4 mist_color : source_color = vec4(0.06, 0.10, 0.14, 0.38);

// Hash and noise functions
float hash21(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

vec2 hash22(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.xx + p3.yz) * p3.zy);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = hash21(i);
	float b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0));
	float d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm_mist(vec2 p) {
	float total = 0.0;
	float amp = 0.55;
	mat2 rot = mat2(vec2(0.8, -0.6), vec2(0.6, 0.8));
	for (int i = 0; i < 4; i++) {
		total += amp * noise(p);
		p = rot * p * 2.02;
		amp *= 0.48;
	}
	return total;
}

// Procedural lens droplet layer returning refractive normal and mask
vec3 lens_droplets(vec2 uv, float speed_factor, float t) {
	vec2 aspect = vec2(16.0 / 9.0, 1.0);
	vec2 p = uv * aspect;

	vec2 total_normal = vec2(0.0);
	float total_mask = 0.0;

	// Layer 1: Static and slow-sliding beads
	vec2 grid_uv1 = p * 18.0;
	vec2 id1 = floor(grid_uv1);
	vec2 gv1 = fract(grid_uv1) - 0.5;

	float h1 = hash21(id1);
	if (h1 > 0.65) {
		float slide_speed = (h1 - 0.65) * (0.15 + speed_factor * 0.45);
		float slide_y = fract(t * slide_speed + h1 * 9.0) * 1.5 - 0.75;
		vec2 drop_center = vec2((h1 * 2.0 - 1.0) * 0.25, slide_y);
		vec2 d = gv1 - drop_center;
		float dist = length(d * vec2(1.0, 0.75 + speed_factor * 0.35));
		float radius = mix(0.08, 0.22, hash21(id1 + 17.3));

		if (dist < radius) {
			float strength = smoothstep(radius, 0.0, dist);
			vec2 n = normalize(d) * strength;
			total_normal += n * 0.035;
			total_mask = max(total_mask, strength);
		}
	}

	// Layer 2: Fast wind-blown streaks driven by boat speed
	if (speed_factor > 0.1) {
		vec2 grid_uv2 = p * vec2(28.0, 7.0);
		grid_uv2.y += t * (1.2 + speed_factor * 2.8);
		vec2 id2 = floor(grid_uv2);
		vec2 gv2 = fract(grid_uv2) - 0.5;
		float h2 = hash21(id2);
		if (h2 > 0.82) {
			vec2 d2 = gv2;
			d2.y *= 0.3; // Elongate along streak direction
			float dist2 = length(d2);
			if (dist2 < 0.18) {
				float s2 = smoothstep(0.18, 0.0, dist2) * speed_factor;
				total_normal += normalize(d2) * s2 * 0.02;
				total_mask = max(total_mask, s2 * 0.7);
			}
		}
	}

	return vec3(total_normal, total_mask);
}

void fragment() {
	// =========================================================================
	// 1. CAMERA-YAW-AWARE LOW HORIZON MIST
	// =========================================================================
	// Offset UV horizontally based on camera yaw so the fog drifts through world space
	float world_yaw_norm = camera_yaw / 6.2831853;
	vec2 mist_coords = vec2(SCREEN_UV.x + world_yaw_norm * 1.8, SCREEN_UV.y * 1.2);
	mist_coords += vec2(TIME * 0.015, -TIME * 0.004);

	float mist_fbm = fbm_mist(mist_coords * vec2(3.5, 2.2));
	float bottom_bias = smoothstep(0.95, 0.35, SCREEN_UV.y);
	float horizon_band = smoothstep(0.20, 0.58, SCREEN_UV.y) * smoothstep(0.88, 0.52, SCREEN_UV.y);
	float mist_density = clamp((bottom_bias * 0.55 + horizon_band * 0.45) * mist_fbm * fog_density_factor * 1.35, 0.0, 1.0);

	// =========================================================================
	// 2. SPEED-DRIVEN WATER DROPLET REFRACTION ON LENS
	// =========================================================================
	float norm_speed = clamp(boat_speed / 8.5, 0.0, 1.0);
	vec3 drop_data = lens_droplets(SCREEN_UV, norm_speed, TIME);
	vec2 refr_offset = drop_data.xy * rain_intensity;

	// Sample distorted scene through droplets
	vec2 refracted_uv = clamp(SCREEN_UV + refr_offset, vec2(0.001), vec2(0.999));
	vec3 scene_col = texture(screen_texture, refracted_uv).rgb;

	// Droplet edge glint / specular reflection
	float glint = smoothstep(0.35, 0.85, drop_data.z) * 0.35;
	vec3 drop_tint = scene_col + vec3(glint * 0.6, glint * 0.7, glint * 0.8);
	vec3 post_water = mix(scene_col, drop_tint, drop_data.z * rain_intensity * 0.85);

	// =========================================================================
	// 3. BLEND MIST OVER WATER-COATED SCENE
	// =========================================================================
	vec3 final_color = mix(post_water, mist_color.rgb, mist_density * mist_color.a);

	// Subtle cinematic vignette
	vec2 vig_uv = (SCREEN_UV - 0.5) * 2.0;
	float vignette = 1.0 - dot(vig_uv * vec2(0.8, 0.9), vig_uv) * 0.28;
	final_color *= clamp(vignette, 0.0, 1.0);

	COLOR = vec4(final_color, 1.0);
}
