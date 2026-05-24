shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec4 ocean_color : source_color = vec4(0.1, 0.4, 0.6, 0.85);
uniform sampler2D texture_normal_1 : hint_roughness_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D texture_normal_2 : hint_roughness_normal, filter_linear_mipmap, repeat_enable;

varying vec3 world_pos;

void vertex() {
    world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    vec3 wave_normal = vec3(0.0, 1.0, 0.0);
    VERTEX.y += sin(world_pos.x * 0.05 + TIME * 1.2) * 0.3;
    VERTEX.y += sin(world_pos.z * 0.08 + TIME * 0.9) * 0.2;
}

void fragment() {
    vec2 uv_1 = world_pos.xz * 0.05 + TIME * 0.02;
    vec2 uv_2 = world_pos.xz * 0.03 - TIME * 0.01;
    vec3 n1 = texture(texture_normal_1, uv_1).rgb * 2.0 - 1.0;
    vec3 n2 = texture(texture_normal_2, uv_2).rgb * 2.0 - 1.0;
    vec3 animated_normal = normalize(n1 + n2);

    float fresnel = pow(1.0 - dot(NORMAL, VIEW), 3.0);
    fresnel = clamp(fresnel, 0.0, 1.0);

    ALBEDO = mix(ocean_color.rgb, vec3(0.7, 0.85, 1.0), fresnel * 0.4);
    ALPHA = mix(ocean_color.a, 0.95, fresnel * 0.5);

    NORMAL_MAP = animated_normal;
    NORMAL_MAP_DEPTH = 0.5;
    METALLIC = 0.1;
    ROUGHNESS = 0.08;
    SPECULAR = 0.5;
}
