shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform sampler2D noise_tex : repeat_enable;
uniform vec4 foam_tint : source_color = vec4(0.55, 0.66, 0.64, 0.7);
uniform float noise_uv_scale : hint_range(0.5, 4.0) = 1.35;

void fragment() {
	float dist = distance(UV, vec2(0.5));
	float radial_mask = 1.0 - smoothstep(0.1, 0.5, dist);

	float n1 = texture(noise_tex, UV * noise_uv_scale + vec2(TIME * 0.03, -TIME * 0.02)).r;
	float n2 = texture(noise_tex, UV * (noise_uv_scale * 1.7) - vec2(TIME * 0.025, TIME * 0.035)).r;
	float noise_val = mix(n1, n2, 0.45);

	float threshold = clamp(1.0 - COLOR.a, 0.0, 0.99);
	float eroded = smoothstep(threshold, 1.0, noise_val * radial_mask);

	ALBEDO = foam_tint.rgb * COLOR.rgb;
	EMISSION = foam_tint.rgb * 0.12 * eroded;
	ROUGHNESS = 0.65;
	SPECULAR = 0.35;
	ALPHA = clamp(eroded * foam_tint.a * radial_mask, 0.0, 1.0);
}
