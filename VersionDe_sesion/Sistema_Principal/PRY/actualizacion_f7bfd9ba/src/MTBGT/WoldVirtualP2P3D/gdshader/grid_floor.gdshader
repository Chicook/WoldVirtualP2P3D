shader_type spatial;
render_mode unshaded, cull_disabled;

uniform vec4 base_color : source_color = vec4(0.015, 0.02, 0.03, 1.0);
uniform vec4 line_color : source_color = vec4(0.06, 0.35, 0.6, 1.0);
uniform float cell = 1.0;
uniform float line_gain = 0.8;
uniform float fade_start = 6.5;
uniform float fade_end = 11.5;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 coord = world_pos.xz / cell;
	vec2 grid = abs(fract(coord - 0.5) - 0.5) / max(fwidth(coord), vec2(1e-5));
	float line = 1.0 - min(min(grid.x, grid.y), 1.0);
	float fade = smoothstep(fade_start, fade_end, length(world_pos.xz));
	ALBEDO = base_color.rgb + line_color.rgb * line * line_gain * (1.0 - fade);
}
