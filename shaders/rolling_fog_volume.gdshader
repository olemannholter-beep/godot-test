shader_type fog;

uniform vec4 fog_color : source_color = vec4(0.08, 0.12, 0.16, 1.0);
uniform float base_density : hint_range(0.0, 1.0) = 0.08;
uniform float vertical_softness : hint_range(0.1, 5.0) = 1.8;
uniform vec3 wind_velocity = vec3(-0.85, 0.0, 0.45);
uniform float noise_scale : hint_range(0.005, 0.1) = 0.025;

float hash31(vec3 p) {
	vec3 p3 = fract(p * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

float noise3d(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	vec3 u = f * f * (3.0 - 2.0 * f);

	float n000 = hash31(i + vec3(0.0, 0.0, 0.0));
	float n100 = hash31(i + vec3(1.0, 0.0, 0.0));
	float n010 = hash31(i + vec3(0.0, 1.0, 0.0));
	float n110 = hash31(i + vec3(1.0, 1.0, 0.0));
	float n001 = hash31(i + vec3(0.0, 0.0, 1.0));
	float n101 = hash31(i + vec3(1.0, 0.0, 1.0));
	float n011 = hash31(i + vec3(0.0, 1.0, 1.0));
	float n111 = hash31(i + vec3(1.0, 1.0, 1.0));

	float lx0 = mix(n000, n100, u.x);
	float lx1 = mix(n010, n110, u.x);
	float lx2 = mix(n001, n101, u.x);
	float lx3 = mix(n011, n111, u.x);

	float ly0 = mix(lx0, lx1, u.y);
	float ly1 = mix(lx2, lx3, u.y);

	return mix(ly0, ly1, u.z);
}

float fbm3d(vec3 p) {
	float val = 0.0;
	float amp = 0.6;
	for (int i = 0; i < 3; i++) {
		val += amp * noise3d(p);
		p = p * 2.15 + vec3(4.31, 1.72, 8.43);
		amp *= 0.45;
	}
	return val;
}

void fog() {
	vec3 world_coords = WORLD_POSITION;
	vec3 wind_drift = wind_velocity * TIME;
	vec3 sample_pos = (world_coords + wind_drift) * noise_scale;

	// Procedural 3D density
	float n = fbm3d(sample_pos);
	float density_variation = smoothstep(0.32, 0.85, n);

	// Vertical ground-hugging gradient (thickest near sea level, fading upwards)
	float height_fade = clamp(1.0 - (world_coords.y / 24.0) * vertical_softness, 0.0, 1.0);
	float final_density = base_density * density_variation * height_fade * clamp(SDF * 0.15, 0.0, 1.0);

	DENSITY = final_density;
	ALBEDO = fog_color.rgb;
	EMISSION = vec3(0.001, 0.002, 0.003);
}
