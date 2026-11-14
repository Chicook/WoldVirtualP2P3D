extends Node
## ══════════════════════════════════════════════════════════════════════════════
## OptimizadorAvatares.gd
## Singleton de optimización de peso en disco + VRAM + CPU para avatares y
## texturas del mundo en tiempo de ejecución (Godot 4.x).
##
## Técnicas aplicadas:
##   1. Redimensionado de texturas  (Image.resize)          → menos VRAM
##   2. Generación de mipmaps       (Image.generate_mipmaps) → menos GPU bandwidth
##   3. Compresión VRAM portátil    (PortableCompressedTexture2D) → menos VRAM
##   4. LOD bias de malla           (GeometryInstance3D.lod_bias) → menos GPU
##   5. Visibility ranges (HLOD)    (GeometryInstance3D)     → cull completo
##   6. Throttle de animaciones     (AnimationPlayer/Tree)   → menos CPU
##
## Uso:
##   • Añadir a Project → Project Settings → Autoload con nombre "OptimizadorAvatares".
##   • O llamar manualmente:
##       OptimizadorAvatares.optimizar_nodo(avatar_node)
##       OptimizadorAvatares.aplicar_configuracion_global()
## ══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# Configuración ajustable por proyecto
# ─────────────────────────────────────────────────────────────────────────────

## Factor de escala de texturas (1.0 = sin cambio, 0.5 = mitad resolución).
## 0.5 reduce 4K->2K, 2K->1K. Ahorra hasta un 75 % de VRAM por textura.
@export var escala_textura: float = 0.5

## Si true, usa PortableCompressedTexture2D para compresión VRAM adicional.
@export var comprimir_vram: bool = true

## Si true, genera mipmaps en todas las texturas procesadas.
@export var generar_mipmaps: bool = true

## Distancia (metros) a partir de la cual se pausa la animación del avatar.
@export var distancia_pausa_anim: float = 30.0

## Distancia a partir de la cual el avatar desaparece completamente (HLOD).
@export var distancia_culling: float = 80.0

## LOD bias aplicado a todos los MeshInstance3D de avatares remotos.
## < 1.0 = cambia antes al LOD bajo (más rápido). 1.0 = comportamiento neutro.
@export var lod_bias_remoto: float = 0.6

## Resolución máxima permitida en píxeles (lado más largo).
## Las texturas ya pequeñas no se tocan.
@export var resolucion_maxima: int = 1024

# ─────────────────────────────────────────────────────────────────────────────
# Estado interno
# ─────────────────────────────────────────────────────────────────────────────

## Caché de texturas ya procesadas (evita reprocesar texturas compartidas).
var _cache_texturas: Dictionary = {}

## Nodos de avatar remotos gestionados para throttle de animaciones.
var _avatares_remotos: Dictionary = {}

## Referencia a la cámara activa (se busca en _process).
var _camara: Camera3D = null

# ─────────────────────────────────────────────────────────────────────────────
# Señales
# ─────────────────────────────────────────────────────────────────────────────

signal avatar_optimizado(nodo: Node3D)

# ─────────────────────────────────────────────────────────────────────────────
# Inicialización
# ─────────────────────────────────────────────────────────────────────────────

func _ready() -> void:
	print("[OptimizadorAvatares] Sistema de optimización iniciado.")
	print("[OptimizadorAvatares] Escala texturas: %.1f | VRAM compress: %s | Max px: %d" \
		% [escala_textura, str(comprimir_vram), resolucion_maxima])
	aplicar_configuracion_global()

func _process(_delta: float) -> void:
	if not is_instance_valid(_camara):
		_camara = get_viewport().get_camera_3d()
	if is_instance_valid(_camara):
		_actualizar_throttle_animaciones()

# ─────────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────────

## Optimiza texturas, LOD y animaciones de un nodo avatar completo.
## Llamar después de instanciar el avatar en la escena.
## es_remoto=true: aplica LOD agresivo (avatares de otros jugadores).
## es_remoto=false: solo texturas (avatar propio, más calidad de LOD).
func optimizar_nodo(nodo: Node3D, es_remoto: bool = true) -> void:
	if not is_instance_valid(nodo):
		return
	print("[OptimizadorAvatares] Optimizando nodo: ", nodo.name)
	_recorrer_y_optimizar_texturas(nodo)
	_aplicar_lod_y_culling(nodo, es_remoto)
	if es_remoto:
		_registrar_para_throttle(nodo)
	emit_signal("avatar_optimizado", nodo)
	print("[OptimizadorAvatares] OK Nodo optimizado: ", nodo.name)


## Aplica configuración global de LOD al viewport.
## Llamar una vez en _ready o desde Boot.gd.
func aplicar_configuracion_global() -> void:
	# Umbral global: cuántos píxeles de diferencia en pantalla provocan cambio de LOD.
	# 4.0 es más agresivo que el defecto (1.0): ahorra GPU en mundos densos.
	get_tree().root.mesh_lod_threshold = 4.0
	print("[OptimizadorAvatares] mesh_lod_threshold global -> 4.0")


## Libera la caché de texturas (llamar entre escenas si hay presión de memoria).
func limpiar_cache() -> void:
	_cache_texturas.clear()
	print("[OptimizadorAvatares] Cache de texturas liberada.")


## Elimina un avatar del throttle de animaciones (llamar cuando se destruye).
func desregistrar_avatar(nodo: Node3D) -> void:
	_avatares_remotos.erase(nodo)

# ─────────────────────────────────────────────────────────────────────────────
# Optimización de texturas
# ─────────────────────────────────────────────────────────────────────────────

func _recorrer_y_optimizar_texturas(nodo: Node) -> void:
	if nodo is MeshInstance3D:
		_optimizar_mesh_instance(nodo as MeshInstance3D)
	for hijo in nodo.get_children():
		_recorrer_y_optimizar_texturas(hijo)


func _optimizar_mesh_instance(mi: MeshInstance3D) -> void:
	var mesh: Mesh = mi.mesh
	if not mesh:
		return
	for i in range(mesh.get_surface_count()):
		var mat = mi.get_surface_override_material(i)
		if not mat:
			mat = mesh.surface_get_material(i)
		if mat is BaseMaterial3D:
			_optimizar_material(mat as BaseMaterial3D)
		elif mat is ShaderMaterial:
			_optimizar_shader_material(mat as ShaderMaterial)


func _optimizar_material(mat: BaseMaterial3D) -> void:
	var tipos_textura: Array[int] = [
		BaseMaterial3D.TEXTURE_ALBEDO,
		BaseMaterial3D.TEXTURE_NORMAL,
		BaseMaterial3D.TEXTURE_ROUGHNESS,
		BaseMaterial3D.TEXTURE_METALLIC,
		BaseMaterial3D.TEXTURE_EMISSION,
		BaseMaterial3D.TEXTURE_AMBIENT_OCCLUSION,
	]
	for tipo in tipos_textura:
		var tex: Texture2D = mat.get_texture(tipo)
		if tex and tex is Texture2D:
			var tex_opt = _optimizar_textura(tex, tipo == BaseMaterial3D.TEXTURE_NORMAL)
			if tex_opt:
				mat.set_texture(tipo, tex_opt)


func _optimizar_shader_material(mat: ShaderMaterial) -> void:
	## Parámetros comunes en shaders de avatar. Ampliar con los propios.
	var params_comunes: Array[String] = [
		"texture_albedo", "albedo_texture",
		"texture_normal", "normal_texture",
		"texture_roughness", "roughness_texture",
		"texture_metallic", "metallic_texture",
		"texture_emission", "emission_texture",
	]
	for param in params_comunes:
		var tex = mat.get_shader_parameter(param)
		if tex is Texture2D:
			var es_normal: bool = param.contains("normal")
			var tex_opt = _optimizar_textura(tex as Texture2D, es_normal)
			if tex_opt:
				mat.set_shader_parameter(param, tex_opt)


func _optimizar_textura(tex: Texture2D, es_normal_map: bool = false) -> Texture2D:
	## Devuelve la versión optimizada de la textura.
	## Usa caché por RID para no reprocesar texturas compartidas.
	var clave = tex.get_rid()
	if _cache_texturas.has(clave):
		return _cache_texturas[clave]

	var img: Image = tex.get_image()
	if not img or img.is_empty():
		return tex

	var ancho_orig: int = img.get_width()
	var alto_orig:  int = img.get_height()
	var lado_max:   int = maxi(ancho_orig, alto_orig)

	# Si ya es pequeña y no hay que añadir mipmaps, devolver sin cambios
	if lado_max <= resolucion_maxima and escala_textura >= 1.0:
		if generar_mipmaps and not img.has_mipmaps():
			img.generate_mipmaps(es_normal_map)
			var tex_mip = ImageTexture.create_from_image(img)
			_cache_texturas[clave] = tex_mip
			return tex_mip
		return tex

	# Calcular factor de escala real (escala_textura Y límite de resolucion_maxima)
	var factor: float = escala_textura
	if lado_max > resolucion_maxima:
		var factor_max: float = float(resolucion_maxima) / float(lado_max)
		factor = minf(factor, factor_max)

	var nuevo_ancho: int = maxi(4, int(ancho_orig * factor))
	var nuevo_alto:  int = maxi(4, int(alto_orig  * factor))

	# Múltiplo de 4 (requerido por S3TC/BC y ETC2)
	nuevo_ancho = (nuevo_ancho + 3) & ~3
	nuevo_alto  = (nuevo_alto  + 3) & ~3

	# Redimensionar con Lanczos (mejor calidad para downscale)
	img.resize(nuevo_ancho, nuevo_alto, Image.INTERPOLATE_LANCZOS)

	# Mipmaps
	if generar_mipmaps:
		img.generate_mipmaps(es_normal_map)  # true = renormaliza vectores en normal maps

	var tex_final: Texture2D

	if comprimir_vram:
		## PortableCompressedTexture2D: compresión VRAM portátil en runtime.
		## COMPRESSION_MODE_LOSSLESS: sin pérdida visible, portable.
		## COMPRESSION_MODE_LOSSY:    más pequeño, ligera pérdida (aceptable en mobile).
		var tex_comp := PortableCompressedTexture2D.new()
		tex_comp.create_from_image(img, PortableCompressedTexture2D.COMPRESSION_MODE_LOSSLESS)
		tex_final = tex_comp
	else:
		tex_final = ImageTexture.create_from_image(img)

	_cache_texturas[clave] = tex_final

	print("[OptimizadorAvatares] Textura %dx%d -> %dx%d (normal=%s vram=%s)" \
		% [ancho_orig, alto_orig, nuevo_ancho, nuevo_alto,
		   str(es_normal_map), str(comprimir_vram)])

	return tex_final

# ─────────────────────────────────────────────────────────────────────────────
# LOD bias y Visibility ranges (HLOD)
# ─────────────────────────────────────────────────────────────────────────────

func _aplicar_lod_y_culling(nodo: Node, es_remoto: bool) -> void:
	if nodo is GeometryInstance3D:
		var gi := nodo as GeometryInstance3D
		if es_remoto:
			# Cambiar antes al LOD bajo para avatares remotos
			gi.lod_bias = lod_bias_remoto
		# HLOD: cull total más allá de distancia_culling metros
		gi.visibility_range_end        = distancia_culling
		gi.visibility_range_end_margin = 5.0
		gi.visibility_range_fade_mode  = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	for hijo in nodo.get_children():
		_aplicar_lod_y_culling(hijo, es_remoto)

# ─────────────────────────────────────────────────────────────────────────────
# Throttle de animaciones por distancia
# ─────────────────────────────────────────────────────────────────────────────

func _registrar_para_throttle(nodo: Node3D) -> void:
	var info: Dictionary = {
		"anim_player": _buscar_nodo_tipo(nodo, "AnimationPlayer"),
		"anim_tree":   _buscar_nodo_tipo(nodo, "AnimationTree"),
		"activo":      true,
	}
	_avatares_remotos[nodo] = info


func _actualizar_throttle_animaciones() -> void:
	var a_eliminar: Array = []
	for nodo in _avatares_remotos:
		if not is_instance_valid(nodo):
			a_eliminar.append(nodo)
			continue
		var info: Dictionary = _avatares_remotos[nodo]
		var dist: float = nodo.global_position.distance_to(_camara.global_position)
		var deberia_activo: bool = dist < distancia_pausa_anim
		if deberia_activo != info["activo"]:
			_set_animacion_activa(info, deberia_activo)
			info["activo"] = deberia_activo
			_avatares_remotos[nodo] = info
	for n in a_eliminar:
		_avatares_remotos.erase(n)


func _set_animacion_activa(info: Dictionary, activo: bool) -> void:
	# Prioridad: AnimationTree (lo gestiona todo). Si no hay, usar AnimationPlayer.
	var at: AnimationTree = info.get("anim_tree")
	if is_instance_valid(at):
		at.active = activo
		return
	var ap: AnimationPlayer = info.get("anim_player")
	if is_instance_valid(ap):
		if activo: ap.play()
		else:      ap.pause()

# ─────────────────────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────────────────────

## Busca recursivamente el primer hijo cuya clase coincida con tipo (String).
func _buscar_nodo_tipo(nodo: Node, tipo: String):
	if nodo.get_class() == tipo:
		return nodo
	for hijo in nodo.get_children():
		var resultado = _buscar_nodo_tipo(hijo, tipo)
		if resultado:
			return resultado
	return null
