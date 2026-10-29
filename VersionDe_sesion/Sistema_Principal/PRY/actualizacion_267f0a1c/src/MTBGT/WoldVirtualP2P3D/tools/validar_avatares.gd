extends SceneTree
## Valida los 24 avatares del carrusel con el cargador real de Godot:
## escena instanciable, Skeleton3D con huesos suficientes, AnimationPlayer con
## los 5 clips que usa el AnimationTree y reproduccion del idle sin errores.
## Uso: godot --headless --path <proyecto> --script res://tools/validar_avatares.gd

const Turnos = preload("res://gdscrip/Turnos.gd")
const CLIPS := ["paradoMJ1_1", "caminarMJ1_2", "correrMJ1_3",
		"left_StrafeMJ1_4", "rightstrafeMJ1_5"]


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	var fallos := 0
	for i in Turnos.AVATARES.size():
		var ruta: String = Turnos.AVATARES[i]
		if not ResourceLoader.exists(ruta):
			print("FALLO %-6s escena inexistente %s" % [Turnos.NOMBRES[i], ruta])
			fallos += 1
			continue
		var ps := load(ruta) as PackedScene
		if ps == null:
			print("FALLO %-6s no carga la escena" % Turnos.NOMBRES[i])
			fallos += 1
			continue
		var inst := ps.instantiate()
		if inst == null:
			print("FALLO %-6s no instancia" % Turnos.NOMBRES[i])
			fallos += 1
			continue
		get_root().add_child(inst)
		await process_frame
		fallos += await _probar(Turnos.NOMBRES[i], inst)
		inst.queue_free()
		await process_frame
	print("== %d avatares, %d con fallo ==" % [Turnos.AVATARES.size(), fallos])
	quit(1 if fallos > 0 else 0)


func _probar(nombre: String, inst: Node) -> int:
	var problemas: Array[String] = []

	var esqueletos := inst.find_children("*", "Skeleton3D", true, false)
	var huesos := 0
	for sk in esqueletos:
		huesos = maxi(huesos, (sk as Skeleton3D).get_bone_count())
	if huesos < 60:
		problemas.append("huesos=%d" % huesos)

	var aps := inst.find_children("*", "AnimationPlayer", true, false)
	if aps.is_empty():
		problemas.append("sin AnimationPlayer")
		return _reportar(nombre, huesos, [], problemas)
	var ap := aps[0] as AnimationPlayer
	var clips := ap.get_animation_list()
	for esperado in CLIPS:
		if not clips.has(esperado):
			problemas.append("falta " + esperado)
	var vacios: Array[String] = []
	for clip in clips:
		var anim := ap.get_animation(clip)
		if anim == null or anim.get_track_count() == 0 or anim.length <= 0.0:
			vacios.append(str(clip))
	if not vacios.is_empty():
		problemas.append("clips vacios: " + ", ".join(vacios))

	# Los clips prestados se reescriben a los huesos de este esqueleto; una pista
	# que siga apuntando al avatar donante aqui no existe.
	var raiz := ap.get_node_or_null(ap.root_node)
	var huerfanas := 0
	if raiz:
		for clip in CLIPS:
			var anim := ap.get_animation(clip)
			if anim == null:
				continue
			for t in anim.get_track_count():
				var nodo := NodePath(anim.track_get_path(t).get_concatenated_names())
				if raiz.get_node_or_null(nodo) == null:
					huerfanas += 1
	if huerfanas > 0:
		problemas.append("pistas sin nodo: %d" % huerfanas)

	var trees := inst.find_children("*", "AnimationTree", true, false)
	if trees.is_empty():
		problemas.append("sin AnimationTree")
	elif not (trees[0] as AnimationTree).active:
		problemas.append("AnimationTree inactivo")

	# El AnimationTree tiene que mover el esqueleto por si solo: es la prueba de
	# que los clips llegan de verdad a la malla, no solo a la lista del reproductor.
	if not esqueletos.is_empty():
		var esqueleto := esqueletos[0] as Skeleton3D
		var antes: Array[Transform3D] = []
		for i in esqueleto.get_bone_count():
			antes.append(esqueleto.get_bone_pose(i))
		await create_timer(0.35).timeout
		var movidos := 0
		for i in esqueleto.get_bone_count():
			if not antes[i].is_equal_approx(esqueleto.get_bone_pose(i)):
				movidos += 1
		print("    huesos en movimiento: %d/%d" % [movidos, esqueleto.get_bone_count()])
		if movidos < 10:
			problemas.append("el esqueleto no se mueve (%d huesos)" % movidos)

	return _reportar(nombre, huesos, clips, problemas)


func _reportar(nombre: String, huesos: int, clips: Array, problemas: Array[String]) -> int:
	var estado := "OK" if problemas.is_empty() else "FALLO"
	print("%s %-6s huesos=%d clips=%d %s" % [
		estado, nombre, huesos, clips.size(),
		"" if problemas.is_empty() else "→ " + "; ".join(problemas),
	])
	return 0 if problemas.is_empty() else 1
