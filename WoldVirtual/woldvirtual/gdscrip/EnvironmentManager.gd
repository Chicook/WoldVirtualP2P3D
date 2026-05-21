extends Node
class_name EnvironmentManager

@export var day_speed: float = 0.01 # Ciclo mucho más lento y natural
@export var sun_path: NodePath
@export var env_path: NodePath

var sun: DirectionalLight3D
var env: WorldEnvironment
var time: float = 0.0

func _ready():
	if sun_path: sun = get_node(sun_path)
	if env_path: env = get_node(env_path)
	
	_setup_premium_render()

func _setup_premium_render():
	if !is_instance_valid(env): return
	var e = env.environment
	
	# 1. Tonemapping ACES (Look Cinematográfico)
	e.tonemap_mode = Environment.TONE_MAPPER_ACES
	e.tonemap_exposure = 1.0
	e.tonemap_white = 1.0
	
	# 2. Iluminación Global Dinámica (SDFGI)
	e.sdfgi_enabled = true
	e.sdfgi_use_occlusion = true
	e.sdfgi_read_sky_light = true
	
	# 3. Oclusión Ambiental (SSAO) y Luz Indirecta (SSIL)
	e.ssao_enabled = true
	e.ssao_intensity = 2.0
	e.ssil_enabled = true
	
	# 4. Niebla Volumétrica (Atmósfera)
	e.volumetric_fog_enabled = true
	e.volumetric_fog_density = 0.01
	e.volumetric_fog_albedo = Color(0.8, 0.9, 1.0)
	
	# 5. Sombras Suaves del Sol
	if is_instance_valid(sun):
		sun.shadow_enabled = true
		sun.light_angular_distance = 1.0 # Sombras suaves
		sun.shadow_blur = 2.0

func _process(delta):
	time += delta * day_speed
	
	# Rotación natural del sol
	if is_instance_valid(sun):
		var sun_angle = wrapf(time, 0.0, TAU)
		sun.rotation.x = sin(sun_angle) * PI * 0.4
		sun.rotation.y = deg_to_rad(45.0)
		
		# Intensidad Gradual
		var sun_height = sin(sun_angle)
		sun.light_energy = clamp(sun_height + 0.3, 0.0, 1.0)
		
		# Colores Naturales (Blanco a Crema)
		var sunset = clamp(1.0 - sun_height, 0.0, 1.0)
		sun.light_color = Color(1.0, 1.0, 0.9).lerp(Color(1.0, 0.8, 0.5), sunset)
		sun.visible = (sun_height > -0.15)

	# Sincronización del cielo y niebla
	if is_instance_valid(env):
		var e = env.environment
		var sky_h = clamp(sin(time), -1.0, 1.0)
		
		# Color de la niebla sigue al sol de forma suave
		var fog_day = Color(0.6, 0.8, 0.9)
		var fog_night = Color(0.05, 0.1, 0.15)
		e.fog_light_color = fog_day.lerp(fog_night, 1.0 - clamp(sky_h + 0.2, 0.0, 1.0))
