shader_type spatial;

uniform vec4 base_color : source_color = vec4(0.045, 0.055, 0.075, 1.0);
uniform vec4 seam_color : source_color = vec4(0.008, 0.012, 0.018, 1.0);
uniform float panel = 2.0;
uniform float variation = 0.3;
uniform float metallic_value = 0.75;
uniform float roughness_value = 0.42;

varying vec3 world_pos;
varying vec3 world_normal;

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec2 uv;
	if (abs(world_normal.y) > 0.5) {
		uv = world_pos.xz;
	} else if (abs(world_normal.z) > abs(world_normal.x)) {
		uv = world_pos.xy;
	} else {
		uv = world_pos.zy;
	}
	vec2 coord = uv / panel;
	vec2 grid = abs(fract(coord - 0.5) - 0.5) / max(fwidth(coord), vec2(1e-5));
	float line = 1.0 - min(min(grid.x, grid.y), 1.0);
	float h = hash21(floor(coord));
	vec3 panel_col = base_color.rgb * (1.0 - variation * 0.5 + variation * h);
	ALBEDO = mix(panel_col, seam_color.rgb, line);
	METALLIC = metallic_value;
	ROUGHNESS = mix(roughness_value, 0.8, line);
}
