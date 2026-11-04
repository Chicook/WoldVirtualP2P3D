shader_type sky;

// === COLORES DEL CIELO Y HORIZONTE ===
uniform vec4 sky_top_color : source_color = vec4(0.16, 0.45, 0.88, 1.0);
uniform vec4 sky_horizon_color : source_color = vec4(0.66, 0.83, 0.98, 1.0);
uniform vec4 ground_bottom_color : source_color = vec4(0.04, 0.14, 0.24, 1.0);
uniform vec4 ground_horizon_color : source_color = vec4(0.48, 0.68, 0.82, 1.0);

// === SOL Y ATMFÓSFERA ===
uniform vec4 sun_color : source_color = vec4(1.0, 0.96, 0.84, 1.0);
uniform float sun_disk_size : hint_range(0.01, 0.2) = 0.045;
uniform float sun_glow_intensity : hint_range(0.0, 3.0) = 1.0;

// === CÚMULOS (NUBES PRINCIPALES) ===
uniform vec4 cloud_color_sun : source_color = vec4(1.0, 0.99, 0.96, 1.0);
uniform vec4 cloud_color_shadow : source_color = vec4(0.62, 0.70, 0.82, 1.0);
uniform float cloud_coverage : hint_range(0.0, 1.0) = 0.52;
uniform float cloud_softness : hint_range(0.01, 0.6) = 0.20;
uniform float cloud_scale : hint_range(0.1, 5.0) = 1.2;
uniform float cloud_speed : hint_range(0.0, 0.2) = 0.018;
uniform vec2 cloud_direction = vec2(1.0, 0.35);

// === CIRROS (NUBES ALTAS FILAMENTOSAS) ===
uniform vec4 cirrus_color : source_color = vec4(0.96, 0.98, 1.0, 0.55);
uniform float cirrus_coverage : hint_range(0.0, 1.0) = 0.40;
uniform float cirrus_scale : hint_range(0.5, 10.0) = 3.5;
uniform float cirrus_speed : hint_range(0.0, 0.2) = 0.028;

// --- FUNCIONES MATEMÁTICAS Y DE RUIDO ---
vec2 hash2(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(443.897, 441.423, 437.195));
	p3 += dot(p3, p3.yzx + 19.19);
	return fract((p3.xx + p3.yz) * p3.zy);
}

float hash1(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = hash1(i);
	float b = hash1(i + vec2(1.0, 0.0));
	float c = hash1(i + vec2(0.0, 1.0));
	float d = hash1(i + vec2(1.0, 1.0));
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// Ruido celular (Worley) para la redondez y masa de los cúmulos
float worley_noise(vec2 p) {
	vec2 n = floor(p);
	vec2 f = fract(p);
	float min_d = 1.0;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 g = vec2(float(x), float(y));
			vec2 o = hash2(n + g);
			vec2 r = g + o - f;
			min_d = min(min_d, length(r));
		}
	}
	return min_d;
}

// FBM para detalle y erosión natural de bordes
float fbm(vec2 p) {
	float v = 0.0;
	float a = 0.5;
	mat2 rot = mat2(vec2(1.6, 1.2), vec2(-1.2, 1.6));
	for (int i = 0; i < 4; i++) {
		v += a * value_noise(p);
		p = rot * p * 1.18;
		a *= 0.5;
	}
	return v;
}

// Muestra la densidad de la nube en una posición UV dada
float sample_cloud_density(vec2 uv) {
	// Masa básica redondeada con Worley
	float w1 = 1.0 - worley_noise(uv);
	float w2 = 1.0 - worley_noise(uv * 2.2 + 1.7);
	float worley = clamp(w1 * 0.7 + w2 * 0.3, 0.0, 1.0);

	// Detalle orgánico con FBM
	float f = fbm(uv * 2.5);

	// Combinar estructura y fractal
	float density = worley * 0.65 + f * 0.45;
	return density;
}

void sky() {
	vec3 dir = normalize(EYEDIR);
	float y = dir.y;

	// 1. Gradiente del cielo
	vec3 sky_base;
	if (y >= 0.0) {
		float h = pow(clamp(y, 0.0, 1.0), 0.62);
		sky_base = mix(sky_horizon_color.rgb, sky_top_color.rgb, h);
	} else {
		float g = pow(clamp(-y, 0.0, 1.0), 0.48);
		sky_base = mix(ground_horizon_color.rgb, ground_bottom_color.rgb, g);
	}

	// 2. Sol y resplandor
	vec3 sun_dir = LIGHT0_ENABLED ? normalize(LIGHT0_DIRECTION) : normalize(vec3(-0.35, 0.65, 0.45));
	vec3 sun_col = LIGHT0_ENABLED ? (LIGHT0_COLOR * LIGHT0_ENERGY) : sun_color.rgb;
	float sun_dot = max(dot(dir, sun_dir), 0.0);

	// Disco solar y corona atmosférica
	float sun_disk = smoothstep(1.0 - sun_disk_size * 0.012, 1.0, sun_dot);
	float sun_halo = pow(sun_dot, 6.0) * 0.35 * sun_glow_intensity;
	float sun_flare = pow(sun_dot, 48.0) * 0.65;
	vec3 final_color = sky_base + sun_col * (sun_disk * 2.5 + sun_halo + sun_flare);

	// 3. Nubes (solo visibles en el cielo sobre el horizonte)
	if (y > 0.005) {
		// Proyección esférica sobre cúpula virtual para evitar compresión excesiva en horizonte
		float dome_factor = 1.0 / (y + 0.22);
		vec2 dome_uv = dir.xz * dome_factor;
		vec2 wind = normalize(cloud_direction);

		// Desvanecimiento natural en el horizonte marítimo
		float horizon_fade = smoothstep(0.015, 0.26, y);

		// === CAPA CIRROS (nubes de gran altitud) ===
		vec2 cirrus_uv = dome_uv * cirrus_scale * 0.22 + wind * (TIME * cirrus_speed);
		float cirrus_f = fbm(cirrus_uv * 1.5 + vec2(cirrus_uv.y * 0.5, 0.0));
		float cirrus_thresh = 1.0 - cirrus_coverage;
		float cirrus_alpha = smoothstep(cirrus_thresh, cirrus_thresh + 0.25, cirrus_f);
		cirrus_alpha *= horizon_fade * cirrus_color.a;
		final_color = mix(final_color, cirrus_color.rgb, cirrus_alpha * 0.65);

		// === CAPA CÚMULOS (nubes principales esponjosas con volumen 3D) ===
		vec2 cumulus_uv = dome_uv * cloud_scale * 0.45 + wind * (TIME * cloud_speed);

		float density = sample_cloud_density(cumulus_uv);

		// Umbral de cobertura
		float threshold = 1.0 - cloud_coverage;
		float cloud_alpha = smoothstep(threshold, threshold + cloud_softness, density);
		cloud_alpha *= horizon_fade;

		if (cloud_alpha > 0.002) {
			// Sombreado 3D / oclusión hacia el sol
			vec2 sun_sample_offset = normalize(sun_dir.xz) * 0.07;
			float density_towards_sun = sample_cloud_density(cumulus_uv + sun_sample_offset);
			float self_shadow = clamp(1.0 - (density_towards_sun - density) * 3.0, 0.35, 1.0);

			// Resplandor plateado en los bordes hacia el sol (silver lining)
			float silver_edge = pow(sun_dot, 4.0) * (1.0 - cloud_alpha * 0.6) * 0.9;

			// Color de la nube: sombra ambiental hacia luz solar directa
			vec3 cloud_rgb = mix(cloud_color_shadow.rgb, cloud_color_sun.rgb, self_shadow);
			cloud_rgb += sun_col * silver_edge;

			// Mezcla suave con el cielo
			final_color = mix(final_color, cloud_rgb, cloud_alpha);
		}
	}

	COLOR = final_color;
}
