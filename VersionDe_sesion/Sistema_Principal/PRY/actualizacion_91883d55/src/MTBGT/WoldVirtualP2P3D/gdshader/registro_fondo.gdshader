shader_type canvas_item;
// Fondo del registro: degradado oscuro, halo cian detras del avatar y una
// rejilla tenue, a juego con la cupula del carrusel.

uniform vec4 color_arriba : source_color = vec4(0.055, 0.075, 0.12, 1.0);
uniform vec4 color_abajo : source_color = vec4(0.012, 0.018, 0.035, 1.0);
uniform vec4 color_brillo : source_color = vec4(0.10, 0.48, 0.78, 1.0);
uniform float brillo = 0.30;
uniform float rejilla_energia = 0.045;
uniform float rejilla_celdas = 34.0;

void fragment() {
	vec2 uv = UV;
	vec3 col = mix(color_arriba.rgb, color_abajo.rgb, smoothstep(0.0, 1.0, uv.y));

	float d = distance(uv, vec2(0.5, 0.46));
	col += color_brillo.rgb * brillo * smoothstep(0.80, 0.0, d);

	vec2 g = abs(fract(uv * vec2(rejilla_celdas, rejilla_celdas * 0.56)) - 0.5);
	float lineas = smoothstep(0.465, 0.5, max(g.x, g.y));
	float pulso = 0.75 + 0.25 * sin(TIME * 0.9);
	col += color_brillo.rgb * rejilla_energia * lineas * pulso;

	col *= 1.0 - smoothstep(0.35, 0.92, d) * 0.55;
	COLOR = vec4(col, 1.0);
}
