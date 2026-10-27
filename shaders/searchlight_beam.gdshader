shader_type spatial;
render_mode blend_add, depth_draw_never, cull_back, unshaded;

uniform vec4 beam_color : source_color = vec4(1.0, 0.88, 0.68, 0.055);
uniform sampler2D mist_noise : repeat_enable;
uniform sampler2D depth_texture : hint_depth_texture, repeat_disable, filter_nearest;
uniform float edge_softness = 5.5;
uniform float intensity_multiplier = 1.0;

void fragment() {
	// Smooth Exponential Cylindrical Edge Feathering (zero hard cone edges)
	float ndotv = clamp(abs(dot(NORMAL, VIEW)), 0.0, 1.0);
	float radial_profile = pow(max(ndotv, 0.0001), max(edge_softness, 3.5));

	// Smooth Longitudinal Distance Attenuation (0.0 at lamp lens, soft fade toward far end)
	float dist_atten = pow(max(clamp(1.0 - UV.y, 0.0, 1.0), 0.0001), 2.1) * smoothstep(0.0, 0.08, UV.y);

	// Scrolling Storm Mist Inside the Beam (two cross-scrolling UV layers)
	float mist_a = texture(mist_noise, UV * vec2(2.0, 3.0) + vec2(TIME * 0.12, -TIME * 0.28)).r;
	float mist_b = texture(mist_noise, UV * vec2(3.4, 1.8) + vec2(-TIME * 0.07, -TIME * 0.15)).r;
	float mist_wisp = mix(0.75, 1.25, mix(mist_a, mist_b, 0.48));

	// Wide Depth Intersection Feathering so water contact has zero hard oval edge
	float raw_scene_depth = texture(depth_texture, SCREEN_UV).r;
	vec4 scene_view = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, raw_scene_depth, 1.0);
	scene_view.xyz /= scene_view.w;
	float scene_depth = -scene_view.z;

	vec4 frag_view = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, FRAGCOORD.z, 1.0);
	frag_view.xyz /= frag_view.w;
	float frag_depth = -frag_view.z;

	float depth_diff = scene_depth - frag_depth;
	float depth_intersection = smoothstep(0.0, 6.5, depth_diff);

	ALBEDO = beam_color.rgb;
	float base_alpha = beam_color.a * radial_profile * dist_atten * mist_wisp * depth_intersection;
	ALPHA = clamp(base_alpha * intensity_multiplier, 0.0, 1.0);
}
