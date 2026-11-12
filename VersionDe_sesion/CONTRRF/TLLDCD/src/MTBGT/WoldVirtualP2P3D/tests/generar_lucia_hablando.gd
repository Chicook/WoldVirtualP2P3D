extends SceneTree
## Crea `lucia_hablando`: cuerpo en idle + pista BOCA de `lucIA_ablando`.
## Así LucIA mueve los labios sin ponerse en T.

const BIBLIOTECA := "res://lucia3D/GLTF_lucIA/AreaDeTrabajo/LucIA3D/animaciones_avatar.tres"
const RIG := "res://lucia3D/GLTF_lucIA/AreaDeTrabajo/LucIA3D/LucIA_rig.glb"
const DESTINO := "user://animaciones_avatar.tres"
const DURACION := 2.0


func _init() -> void:
	var libreria := (load(BIBLIOTECA) as AnimationLibrary).duplicate(true) as AnimationLibrary
	var base := libreria.get_animation("lucia_parado")
	if base == null:
		print("[hablando] falta lucia_parado")
		quit(1)
		return
	var rig := _cargar(RIG)
	var jugador := _jugador(rig)
	if jugador == null or not jugador.has_animation("lucIA_ablando"):
		print("[hablando] falta lucIA_ablando")
		quit(1)
		return
	var fuente_boca := jugador.get_animation("lucIA_ablando")
	var nueva := Animation.new()
	nueva.length = DURACION
	nueva.loop_mode = Animation.LOOP_LINEAR
	# Cuerpo: claves del idle hasta 2 s.
	for i in base.get_track_count():
		var tipo := base.track_get_type(i)
		var destino := nueva.add_track(tipo)
		nueva.track_set_path(destino, base.track_get_path(i))
		var interp := base.track_get_interpolation_type(i)
		nueva.track_set_interpolation_type(destino, interp)
		for k in base.track_get_key_count(i):
			var t := base.track_get_key_time(i, k)
			if t > DURACION:
				continue
			nueva.track_insert_key(destino, t, base.track_get_key_value(i, k))
	# Boca: pista de blend shape de lucIA_ablando, repetida hasta 2 s.
	var indice_boca := -1
	for i in fuente_boca.get_track_count():
		if str(fuente_boca.track_get_path(i)).contains("BOCA"):
			indice_boca = i
			break
	if indice_boca < 0:
		print("[hablando] no hay pista BOCA")
		quit(1)
		return
	var destino_boca := nueva.add_track(Animation.TYPE_BLEND_SHAPE)
	nueva.track_set_path(destino_boca, fuente_boca.track_get_path(indice_boca))
	for k in fuente_boca.track_get_key_count(indice_boca):
		var t := fuente_boca.track_get_key_time(indice_boca, k)
		var v = fuente_boca.track_get_key_value(indice_boca, k)
		nueva.track_insert_key(destino_boca, t, v)
		nueva.track_insert_key(destino_boca, t + 1.0, v)
	libreria.add_animation("lucia_hablando", nueva)
	var error := ResourceSaver.save(libreria, DESTINO)
	print("[hablando] guardado error=", error, " pistas=", nueva.get_track_count(), " clips=", libreria.get_animation_list())
	quit(0 if error == OK else 1)


func _cargar(ruta: String) -> Node:
	var p := load(ruta) as PackedScene
	var n := p.instantiate()
	get_root().add_child(n)
	return n


func _jugador(n: Node) -> AnimationPlayer:
	for s in n.find_children("*", "AnimationPlayer", true, false):
		return s as AnimationPlayer
	return null
