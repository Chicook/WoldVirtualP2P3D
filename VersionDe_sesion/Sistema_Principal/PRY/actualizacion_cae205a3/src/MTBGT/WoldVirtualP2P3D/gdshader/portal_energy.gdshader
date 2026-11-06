shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never;

uniform vec4 color_a : source_color = vec4(0.05, 0.55, 1.0, 1.0);
uniform vec4 color_b : source_color = vec4(0.60, 0.12, 0.95, 1.0);
uniform float speed = 0.55;
uniform float intensity = 1.3;
uniform float swirl = 2.4;

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = hash21(i);
	float b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0));
	float d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
	float v = 0.0;
	float amp = 0.5;
	for (int i = 0; i < 5; i++) {
		v += amp * vnoise(p);
		p = p * 2.02 + 17.0;
		amp *= 0.5;
	}
	return v;
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float a = atan(p.y, p.x);
	float tw = a + (1.0 - r) * swirl + TIME * speed;
	vec2 q = vec2(cos(tw), sin(tw)) * r;
	float n = fbm(q * 2.6 + vec2(0.0, TIME * 0.15));
	float core = smoothstep(1.02, 0.15, r);
	float rim = smoothstep(0.78, 1.0, r);
	vec3 col = mix(color_a.rgb, color_b.rgb, smoothstep(0.35, 0.75, n));
	col += color_a.rgb * core * 0.55;
	float alpha = core * (0.40 + 0.55 * n) * intensity * (1.0 - rim * 0.85);
	ALBEDO = col * intensity;
	ALPHA = clamp(alpha, 0.0, 1.0);
}
