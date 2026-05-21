extends Node

# 🚀 PERFORMANCE MANAGER (Optimizador de FPS para el Metaverso)
# Este script monitorea los FPS y ajusta la calidad en tiempo real

var environment: WorldEnvironment
var check_timer: float = 0.0
var low_fps_threshold: float = 45.0
var high_fps_threshold: float = 55.0
var quality_level: int = 1 # 0: Low, 1: High
var vram_usage: int = 0

func _ready() -> void:
	# Buscar el entorno global
	environment = get_tree().root.find_child("WorldEnvironment", true, false)
	print("[PerfManager] Iniciado. Optimizando para 60 FPS.")

func _process(delta: float) -> void:
	check_timer += delta
	if check_timer >= 2.0: # Revisar cada 2 segundos
		check_timer = 0.0
		_calibrate_performance()
		_report_quota_usage()

func _report_quota_usage():
	# En Godot 4.x, el uso de VRAM se consulta a través de RenderingServer.get_rendering_device()
	# si se usa el backend Forward+ o Mobile. Para compatibilidad general y evitar errores de base,
	# usamos RenderingServer.get_video_adapter_api_version() o similar si fuera necesario,
	# pero para obtener la memoria exacta de forma segura:
	
	var rd = RenderingServer.get_rendering_device()
	var vram_used_mb = 0
	
	if rd:
		# get_memory_usage es para buffers internos, no hay una forma directa y estática 
		# de obtener la VRAM total usada por el proceso de forma sencilla sin RD.
		# Como medida de seguridad para evitar el crash del Parser:
		vram_used_mb = Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / (1024 * 1024)
	else:
		# Fallback para backends de compatibilidad
		vram_used_mb = Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / (1024 * 1024)

	vram_usage = vram_used_mb
	print("[Quota] VRAM Usage: ", vram_usage, " MB / Limit: 128 MB")
	
	# Si superamos los 128MB, forzamos calidad baja preventivamente
	if vram_usage > 120 and quality_level == 1:
		print("[PerfManager] ALERTA: VRAM excedida. Forzando reducción de texturas.")
		_set_quality_low()

func _calibrate_performance():
	var fps = Engine.get_frames_per_second()
	
	if fps < low_fps_threshold and quality_level == 1:
		_set_quality_low()
	elif fps > high_fps_threshold and quality_level == 0:
		_set_quality_high()

func _set_quality_low():
	quality_level = 0
	print("[PerfManager] FPS BAJOS (", Engine.get_frames_per_second(), "). Aplicando Perfil de ALTO RENDIMIENTO.")
	if environment and environment.environment:
		var env = environment.environment
		env.ssao_enabled = false
		env.ssil_enabled = false
		env.sdfgi_enabled = false
		env.glow_enabled = false
		# El océano lógicamente sigue igual pero el renderizado será mucho más liviano.

func _set_quality_high():
	quality_level = 1
	print("[PerfManager] FPS ESTABLES. Restaurando Calidad Visual.")
	if environment and environment.environment:
		var env = environment.environment
		env.ssao_enabled = true
		env.ssil_enabled = true
		env.glow_enabled = true
		# Opcional: env.sdfgi_enabled = true (Si el hardware lo permite)
