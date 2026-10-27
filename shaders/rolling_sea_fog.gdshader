shader_type fog;

float hash3d(vec3 p) {
	p = fract(p * vec3(0.1031, 0.1030, 0.0973));
	p += dot(p, p.yxz + 33.33);
	return fract((p.x + p.y) * p.z);
}

float value_noise_3d(vec3 x) {
	vec3 i = floor(x);
	vec3 f = fract(x);
	vec3 u = f * f * (3.0 - 2.0 * f);

	float n000 = hash3d(i + vec3(0.0, 0.0, 0.0));
	float n100 = hash3d(i + vec3(1.0, 0.0, 0.0));
	float n010 = hash3d(i + vec3(0.0, 1.0, 0.0));
	float n110 = hash3d(i + vec3(1.0, 1.0, 0.0));
	float n001 = hash3d(i + vec3(0.0, 0.0, 1.0));
	float n101 = hash3d(i + vec3(1.0, 0.0, 1.0));
	float n011 = hash3d(i + vec3(0.0, 1.0, 1.0));
	float n111 = hash3d(i + vec3(1.0, 1.0, 1.0));

	float nx00 = mix(n000, n100, u.x);
	float nx10 = mix(n010, n110, u.x);
	float nx01 = mix(n001, n101, u.x);
	float nx11 = mix(n011, n111, u.x);

	float nxy0 = mix(nx00, nx10, u.y);
	float nxy1 = mix(nx01, nx11, u.y);

	return mix(nxy0, nxy1, u.z);
}

void fog() {
	vec3 wind_offset = vec3(TIME * 2.2, 0.0, TIME * 1.4);
	vec3 sample_pos = (WORLD_POSITION.xyz + wind_offset) * vec3(0.032, 0.065, 0.032);

	// 2-octave 3D procedural value noise
	float octave_1 = value_noise_3d(sample_pos);
	float octave_2 = value_noise_3d(sample_pos * 2.15 + vec3(17.3, -9.1, 31.7));
	float noise_val = octave_1 * 0.65 + octave_2 * 0.35;

	// Vertical height profile hugging low to the water surface so sky above 10m stays crisp and dark
	float height_mask = smoothstep(10.0, 0.5, WORLD_POSITION.y) * smoothstep(-4.0, -1.5, WORLD_POSITION.y);

	// Distinct, contrasty fog billows
	float billow_mask = smoothstep(0.35, 0.75, noise_val);

	DENSITY = 0.028 * billow_mask * height_mask;
	ALBEDO = vec3(0.32, 0.38, 0.42);
	EMISSION = vec3(0.006, 0.011, 0.014) * billow_mask;
}
