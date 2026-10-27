shader_type spatial;
render_mode blend_add, depth_draw_never, cull_back, unshaded;

uniform vec4 beam_color : source_color = vec4(1.0, 0.85, 0.55, 0.16);
uniform float fresnel_power = 2.2;
uniform float axial_fade_power = 1.4;
uniform float proximity_fade_distance = 1.5;
uniform float edge_softness = 5.5;
uniform float intensity_multiplier = 1.0;
uniform sampler2D depth_texture : hint_depth_texture, repeat_disable, filter_nearest;

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = hash21(i);
	float b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0));
	float d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void fragment() {
	// Fresnel edge-softening so cone edges never look like hard polygon edges
	float ndotv = clamp(abs(dot(NORMAL, VIEW)), 0.0, 1.0);
	float fresnel_profile = pow(max(ndotv, 0.0001), max(fresnel_power, 1.5));

	// Axial distance fade along cone length (UV.y = 0 at apex, 1 at base)
	float axial_fade = pow(max(clamp(1.0 - UV.y, 0.0, 1.0), 0.0001), max(axial_fade_power, 0.5)) * smoothstep(0.0, 0.08, UV.y);

	// Subtle procedural sea-mist wisp inside the light cone
	float wisp_a = value_noise(UV * vec2(6.0, 10.0) + vec2(TIME * 0.25, -TIME * 0.65));
	float wisp_b = value_noise(UV * vec2(11.0, 5.0) + vec2(-TIME * 0.18, -TIME * 0.42));
	float mist_wisp = mix(0.78, 1.22, mix(wisp_a, wisp_b, 0.5));

	// Depth proximity fade at water/terrain intersection
	float raw_scene_depth = texture(depth_texture, SCREEN_UV).r;
	vec4 scene_view = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, raw_scene_depth, 1.0);
	scene_view.xyz /= scene_view.w;
	float scene_depth = -scene_view.z;

	vec4 frag_view = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, FRAGCOORD.z, 1.0);
	frag_view.xyz /= frag_view.w;
	float frag_depth = -frag_view.z;

	float depth_diff = scene_depth - frag_depth;
	float proximity_fade = smoothstep(0.0, max(proximity_fade_distance, 0.2), depth_diff);

	ALBEDO = beam_color.rgb;
	ALPHA = clamp(beam_color.a * fresnel_profile * axial_fade * mist_wisp * proximity_fade * intensity_multiplier, 0.0, 1.0);
}
