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

	var trees := inst.find_children("*", "AnimationTree", true, false)
	if trees.is_empty():
		problemas.append("sin AnimationTree")
	elif not (trees[0] as AnimationTree).active:
		problemas.append("AnimationTree inactivo")

	# Reproducir el idle y avanzar medio segundo: detecta clips rotos en runtime.
	if clips.has("paradoMJ1_1"):
		ap.play("paradoMJ1_1")
		await process_frame
		await process_frame
		if ap.current_animation != "paradoMJ1_1":
			problemas.append("el idle no arranca")

	return _reportar(nombre, huesos, clips, problemas)


func _reportar(nombre: String, huesos: int, clips: Array, problemas: Array[String]) -> int:
	var estado := "OK" if problemas.is_empty() else "FALLO"
	print("%s %-6s huesos=%d clips=%d %s" % [
		estado, nombre, huesos, clips.size(),
		"" if problemas.is_empty() else "→ " + "; ".join(problemas),
	])
	return 0 if problemas.is_empty() else 1
