shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back;

void fragment() {
	ALBEDO = vec3(0.1, 0.4, 0.6);
	ALPHA = 0.85;
	ROUGHNESS = 0.08;
	METALLIC = 0.1;
}
