shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque;

uniform vec4 base_color : source_color = vec4(0.010, 0.016, 0.030, 1.0);
uniform vec4 line_color : source_color = vec4(0.10, 0.60, 1.0, 1.0);
uniform float cell_u = 36.0;
uniform float cell_v = 18.0;
uniform float line_gain = 0.85;
uniform float panel_energy = 0.35;
uniform float sweep_speed = 0.7;
uniform float grid_top = 0.86;

void fragment() {
	// costillas (verticales) y anillos (horizontes) sobre la superficie del domo
	vec2 c = vec2(UV.x * cell_u, UV.y * cell_v);
	vec2 g = abs(fract(c - 0.5) - 0.5) / max(fwidth(c), vec2(1e-5));
	float line = 1.0 - min(min(g.x, g.y), 1.0);

	// barrido de energia que recorre el domo de abajo hacia arriba
	float sweep = pow(0.5 + 0.5 * sin(UV.y * 6.2831853 * 2.0 - TIME * sweep_speed * 6.2831853), 3.0);

	float vmask = smoothstep(grid_top, grid_top - 0.05, UV.y);
	float gline = line * vmask;

	vec3 col = base_color.rgb;
	col += line_color.rgb * gline * line_gain;
	col += line_color.rgb * sweep * panel_energy * 0.22;

	ALBEDO = col;
	EMISSION = line_color.rgb * (gline * line_gain * 0.85 + sweep * panel_energy * 0.5);
}
