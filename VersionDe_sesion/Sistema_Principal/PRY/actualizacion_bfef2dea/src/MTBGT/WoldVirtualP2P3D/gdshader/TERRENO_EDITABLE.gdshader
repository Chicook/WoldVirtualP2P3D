shader_type spatial;
// Terreno editable: la textura rocosa original se conserva y el color por
// vértice se usa como superposición (la arena de playa). COLOR.a = 0 deja la
// textura intacta; COLOR.a = 1 pinta el color del vértice tal cual.
// Opaco a propósito: la isla es una única superficie cerrada y renderizarla
// como transparente hacía que las caras traseras taparan el relieve.
render_mode cull_disabled, depth_draw_opaque, diffuse_burley, specular_schlick_ggx;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform float roughness_val : hint_range(0.0, 1.0) = 0.5;
uniform float metallic_val : hint_range(0.0, 1.0) = 0.0;

void fragment() {
	vec3 tex = texture(albedo_tex, UV).rgb;
	ALBEDO = mix(tex, COLOR.rgb, clamp(COLOR.a, 0.0, 1.0));
	ROUGHNESS = roughness_val;
	METALLIC = metallic_val;
}
