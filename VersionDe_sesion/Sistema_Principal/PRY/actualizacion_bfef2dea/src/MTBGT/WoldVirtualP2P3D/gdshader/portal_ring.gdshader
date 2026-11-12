shader_type spatial;
render_mode cull_back;

uniform vec4 base_color : source_color = vec4(0.04, 0.06, 0.09, 1.0);
uniform vec4 glow_color : source_color = vec4(0.15, 0.75, 1.0, 1.0);
uniform float bands = 5.0;
uniform float speed = 0.6;
uniform float glow_energy = 1.6;

void fragment() {
	float pulse = pow(0.5 + 0.5 * sin(UV.x * 6.2831853 * bands - TIME * speed * 6.2831853), 8.0);
	ALBEDO = base_color.rgb;
	METALLIC = 0.85;
	ROUGHNESS = 0.22;
	EMISSION = glow_color.rgb * (0.08 + pulse * glow_energy);
}
