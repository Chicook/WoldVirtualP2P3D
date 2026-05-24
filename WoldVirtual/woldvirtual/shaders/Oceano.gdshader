shader_type spatial;

render_mode blend_mix, depth_draw_always, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec3 color_shallow : source_color = vec3(0.3, 0.7, 0.85); // Azul sutil cristalino
uniform vec3 color_deep : source_color = vec3(0.01, 0.08, 0.22);    // Profundo
uniform float absorption_coeff : hint_range(0.0, 5.0) = 0.8;

uniform float roughness : hint_range(0.0, 1.0) = 0.08;
uniform float specular : hint_range(0.0, 1.0) = 0.5;
uniform float metallic : hint_range(0.0, 1.0) = 0.1; 

uniform sampler2D texture_normal_1 : hint_roughness_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D texture_normal_2 : hint_roughness_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D screen_texture : hint_screen_texture, repeat_disable, filter_linear_mipmap;
uniform sampler2D depth_texture : hint_depth_texture;

varying vec3 world_pos;

// 🌊 GERSTNER WAVE MEJORADA (Mas pequeña y natural)
vec3 gerstner_wave(vec3 pos, float steepness, float wavelength, vec2 direction, float speed, inout vec3 normal) {
    float k = 2.0 * PI / wavelength;
    float c = sqrt(9.8 / k);
    vec2 d = normalize(direction);
    float f = k * (dot(d, pos.xz) - speed * TIME);
    float a = steepness / k;

    normal.x -= d.x * a * k * cos(f);
    normal.y -= steepness * sin(f);
    normal.z -= d.y * a * k * cos(f);

    return vec3(d.x * a * cos(f), a * sin(f), d.y * a * cos(f));
}

void vertex() {
    world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    vec3 wave_normal = vec3(0.0, 1.0, 0.0);
    vec3 total_displacement = vec3(0.0);

    // 🌊 Ondas mas frecuentes y sutiles (Menos "lumpy")
    total_displacement += gerstner_wave(world_pos, 0.12, 18.0, vec2(1.0, 0.3), 1.2, wave_normal);
    total_displacement += gerstner_wave(world_pos, 0.08, 12.0, vec2(-0.4, 0.8), 1.0, wave_normal);
    total_displacement += gerstner_wave(world_pos, 0.05, 6.0, vec2(0.2, -0.6), 0.7, wave_normal);

    VERTEX += total_displacement;
    NORMAL = normalize(wave_normal);
}

void fragment() {
    // --- Capas de Ondas de Viento (Ripples) ---
    vec2 uv_1 = world_pos.xz * 0.05 + TIME * 0.02; // Escala reducida para detalle fino
    vec2 uv_2 = world_pos.xz * 0.03 - TIME * 0.01;
    vec3 n1 = texture(texture_normal_1, uv_1).rgb * 2.0 - 1.0;
    vec3 n2 = texture(texture_normal_2, uv_2).rgb * 2.0 - 1.0;
    vec3 animated_normal = normalize(n1 + n2);

    // --- Profundidad Optimizada (Beer-Lambert) ---
    float depth_raw = texture(depth_texture, SCREEN_UV).r;
    vec4 upp = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, depth_raw, 1.0);
    vec3 vpp = upp.xyz / upp.w;
    float water_depth = -(vpp.z + VERTEX.z);
    
    float depth_factor = exp(-water_depth * absorption_coeff);
    depth_factor = clamp(1.0 - depth_factor, 0.0, 1.0);
    
    // Color de Profundidad (Cian a Azul Marino)
    vec3 ocean_color = mix(color_shallow, color_deep, depth_factor);

    // --- Espuma de Orilla Adaptativa ---
    float foam_line = clamp(1.0 - (water_depth * 4.0), 0.0, 1.0);
    vec3 final_color = mix(ocean_color, vec3(0.9, 0.95, 1.0), foam_line * 0.5);

    // --- Fresnel Avanzado (Reflejos Cristalinos) ---
    float fresnel = pow(1.0 - dot(NORMAL, VIEW), 3.0);
    fresnel = clamp(fresnel, 0.0, 1.0);
    
    // Refracción y Mezcla de Pantalla
    vec2 ref_uv = SCREEN_UV + (animated_normal.xy * 0.015);
    vec3 screen_color = texture(screen_texture, ref_uv).rgb;
    
    ALBEDO = mix(final_color, screen_color, fresnel * 0.5);
    ALPHA = mix(0.05, 0.98, depth_factor);
    
    NORMAL_MAP = animated_normal;
    NORMAL_MAP_DEPTH = 0.5;
    
    // PBR Properties
    METALLIC = metallic;
    ROUGHNESS = roughness;
    SPECULAR = specular;
}