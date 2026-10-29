shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec4 albedo_color : source_color = vec4(0.12, 0.14, 0.16, 1.0);
uniform sampler2D albedo_texture : source_color, filter_linear_mipmap, repeat_enable;
uniform bool use_albedo_texture = false;

uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap, repeat_enable;
uniform bool use_normal_texture = false;
uniform float normal_scale : hint_range(0.0, 4.0) = 1.2;

uniform float roughness : hint_range(0.0, 1.0) = 0.88;
uniform float metallic : hint_range(0.0, 1.0) = 0.08;

uniform float tidal_waterline : hint_range(-5.0, 10.0) = 1.8;
uniform float surge_amplitude : hint_range(0.0, 3.0) = 0.75;
uniform float surge_frequency : hint_range(0.1, 5.0) = 1.25;

varying vec3 v_world_pos;

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	// Base texture / color sampling
	vec4 base = albedo_color;
	if (use_albedo_texture) {
		base *= texture(albedo_texture, UV);
	}

	// Normal mapping
	if (use_normal_texture) {
		vec3 n = texture(normal_texture, UV).rgb * 2.0 - 1.0;
		NORMAL_MAP = n * 0.5 + 0.5;
		NORMAL_MAP_DEPTH = normal_scale;
	}

	// World-space tidal surge lapping
	float surge = sin(TIME * surge_frequency + v_world_pos.x * 0.06 + v_world_pos.z * 0.06) * surge_amplitude;
	float active_waterline = tidal_waterline + surge;

	// Wetness gradient: 1.0 below waterline, fading smoothly up to +4.2m
	float wetness = 1.0 - smoothstep(active_waterline - 0.4, active_waterline + 2.4, v_world_pos.y);
	wetness = clamp(wetness, 0.0, 1.0);

	// Wet rock: darken albedo by 45%, lower roughness to 0.12 (glossy wet sheen)
	vec3 final_albedo = base.rgb * (1.0 - wetness * 0.45);
	float final_roughness = mix(roughness, 0.12, wetness);
	float final_specular = mix(0.5, 0.95, wetness);

	// Boost normal bump in wet zone
	if (use_normal_texture) {
		NORMAL_MAP_DEPTH = normal_scale * (1.0 + wetness * 0.6);
	}

	ALBEDO = final_albedo;
	ROUGHNESS = final_roughness;
	SPECULAR = final_specular;
	METALLIC = metallic;
}
