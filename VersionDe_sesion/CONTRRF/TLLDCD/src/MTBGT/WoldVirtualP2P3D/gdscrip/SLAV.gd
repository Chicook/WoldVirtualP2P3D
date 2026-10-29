extends Node3D
## SLAV - Selector de Avatares (carrusel 3D giratorio)
##
## Los avatares se agrupan en turnos de `per_turn` (8). El orden de los arrays
## es el orden real del carrusel y debe alternar chico/chica de forma estricta:
## AVH1, AVMJ1, AVH2, AVMJ2... Al pasar del ultimo avatar de un turno se monta
## el siguiente turno; al confirmar se emite la escena jugable elegida.

signal avatar_confirmed(scene_path: String)

@export var avatar_paths: Array[String] = []
@export var playable_scenes: Array[String] = []
@export var avatar_names: Array[String] = []
## Escala visual base por avatar (1.0 salvo modelos que vienen mas altos).
@export var avatar_scales: Array[float] = []
@export var per_turn := 8
@export var idle_animation := "paradoMJ1_1"
@export var radius := 1.95
@export var y_offset := 0.0
@export var face_offset_deg := 0.0
@export var rotate_speed := 6.0
@export var selected_scale := 1.14
@export var idle_scale := 0.86

var _pivot: Node3D
var _avatars: Array[Node3D] = []
var _index := 0
var _turn := -1
var _target_rot := 0.0
## Indices de avatar ya reservados por otros jugadores. Si los 24 estan
## ocupados se permite elegir igualmente (turno 4: avatar reutilizado).
var ocupados := {}
var _reciclando := false
var _indice_inicial := -1

@onready var _name_label: Label = %NameLabel
@onready var _counter: Label = %Counter


func _ready() -> void:
	_pivot = Node3D.new()
	_pivot.name = "Pivot"
	add_child(_pivot)
	_ir_a(maxi(_indice_inicial, 0), true)


## Marca las plazas ya reservadas por otros jugadores. Llamar antes o despues
## de anadir el nodo al arbol; si aún no se ha montado el carrusel se aplica al
## arrancar.
func set_ocupados(plazas: Array) -> void:
	ocupados.clear()
	for p in plazas:
		var idx := int(p)
		if idx >= 0 and idx < avatar_paths.size():
			ocupados[idx] = true
	_reciclando = not _hay_libres()
	if _pivot != null:
		_ir_a(_index, true)
		_refrescar_ocupados()
	else:
		_indice_inicial = _primer_hueco()
		_index = _indice_inicial


## Coloca el foco en el primer avatar libre (turno 1 con huecos). Si los 24
## estan ocupados se queda en el primero en modo reciclaje.
func abrir_en_primer_hueco() -> void:
	var idx := _primer_hueco()
	if _pivot != null:
		_ir_a(idx, true)
	else:
		_indice_inicial = idx
		_index = idx


func _hay_libres() -> bool:
	return not avatar_paths.is_empty() and ocupados.size() < avatar_paths.size()


func _primer_hueco() -> int:
	for i in avatar_paths.size():
		if not ocupados.has(i):
			return i
	return 0


func _process(delta: float) -> void:
	_pivot.rotation.y = lerp_angle(_pivot.rotation.y, _target_rot, clampf(delta * rotate_speed, 0.0, 1.0))


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_right"):
		_move(1)
	elif event.is_action_pressed("ui_left"):
		_move(-1)
	elif event.is_action_pressed("ui_accept"):
		_confirm()


func _move(dir: int) -> void:
	if avatar_paths.is_empty():
		return
	var total := avatar_paths.size()
	if _hay_libres():
		# Salta las plazas reservadas; da una vuelta completa como maximo.
		var i := _index
		for _paso in total:
			i = wrapi(i + dir, 0, total)
			if not ocupados.has(i):
				_ir_a(i, false)
				return
	_ir_a(_index + dir, false)


func _ir_a(indice: int, instant: bool) -> void:
	_index = wrapi(indice, 0, avatar_paths.size())
	var turno := _index / per_turn
	if turno != _turn:
		_montar_turno(turno)
	_apply_selection(instant)


func _montar_turno(turno: int) -> void:
	_turn = turno
	for avatar in _avatars:
		_pivot.remove_child(avatar)
		avatar.queue_free()
	_avatars.clear()

	# Solo se cargan los 8 avatares del turno visible: los modelos son pesados.
	var inicio := turno * per_turn
	var n := mini(per_turn, avatar_paths.size() - inicio)
	for i in n:
		var escena := load(avatar_paths[inicio + i]) as PackedScene
		if escena == null:
			continue
		var inst := escena.instantiate() as Node3D
		if inst == null:
			continue
		_pivot.add_child(inst)
		var angulo := TAU * float(i) / float(n)
		inst.position = Vector3(sin(angulo) * radius, y_offset, cos(angulo) * radius)
		inst.rotation.y = angulo + deg_to_rad(face_offset_deg)
		_arrancar_idle(inst)
		_avatars.append(inst)

	_target_rot = 0.0
	_pivot.rotation.y = 0.0
	_refrescar_ocupados()


## Arranca la animación idle en el avatar del carrusel.
## Estrategia robusta:
##   1) Si el avatar tiene AnimationTree, lo activa y deja los parámetros en 0
##      (idle) — NO se llama .play() directo porque el árbol controla el player.
##   2) Si no hay árbol, se busca el AnimationPlayer y se reproduce la animación
##      idle disponible (la primera cuyo nombre contiene "parad" o "idle", o
##      la primera de la lista si ninguna coincide).
## El seek() con un offset aleatorio evita que todos los avatares estén
## sincronizados en la misma fase del ciclo.
func _arrancar_idle(inst: Node3D) -> void:
	# 1) Intentar activar el AnimationTree (presente en todos los AVMJ/AVH).
	var at := inst.find_child("AnimationTree", true, false) as AnimationTree
	if at != null:
		at.active = true
		# Todos los parámetros de blend a 0 → estado idle.
		for param in ["parameters/ANMJ/blend_amount",
					  "parameters/Add2/add_amount",
					  "parameters/Blend2/blend_amount",
					  "parameters/Blend2 2/blend_amount",
					  "parameters/Blend2 3/blend_amount"]:
			if at.get(param) != null:
				at.set(param, 0.0)
		# Fase aleatoria en el AnimationPlayer subyacente (sin pausar el árbol).
		var ap_linked := at.get_node_or_null(at.anim_player) as AnimationPlayer
		if ap_linked and ap_linked.has_animation(idle_animation):
			ap_linked.seek(randf() * ap_linked.get_animation(idle_animation).length, false)
		return

	# 2) Fallback: AnimationPlayer sin árbol.
	for ap_node in inst.find_children("*", "AnimationPlayer", true, false):
		var ap := ap_node as AnimationPlayer
		if ap == null:
			continue
		# Elegir la mejor animación idle disponible.
		var candidato := idle_animation
		if not ap.has_animation(candidato):
			candidato = ""
			for anim_name in ap.get_animation_list():
				var lo := anim_name.to_lower()
				if lo.contains("parad") or lo.contains("idle"):
					candidato = anim_name
					break
			if candidato.is_empty() and ap.get_animation_list().size() > 0:
				candidato = ap.get_animation_list()[0]
		if not candidato.is_empty():
			ap.play(candidato)
			ap.seek(randf() * ap.get_animation(candidato).length, true)
		break



## Etiqueta "OCUPADO" sobre los avatares ya reservados del turno montado.
## Como cuelgan del avatar, se liberan solas al cambiar de turno.
func _refrescar_ocupados() -> void:
	if _pivot == null:
		return
	var inicio := _turn * per_turn
	for i in _avatars.size():
		var marca := _avatars[i].get_node_or_null("Ocupado") as Label3D
		var esta_ocupado := ocupados.has(inicio + i)
		if esta_ocupado and marca == null:
			marca = Label3D.new()
			marca.name = "Ocupado"
			marca.text = "OCUPADO"
			marca.font_size = 40
			marca.pixel_size = 0.0045
			marca.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			marca.modulate = Color(1.0, 0.35, 0.35, 1.0)
			marca.outline_size = 12
			marca.outline_modulate = Color(0.08, 0.02, 0.02, 1.0)
			marca.render_priority = 1
			marca.position = Vector3(0.0, 2.35, 0.0)
			_avatars[i].add_child(marca)
		elif not esta_ocupado and marca != null:
			marca.queue_free()


func _apply_selection(instant: bool) -> void:
	var n := _avatars.size()
	if n == 0:
		return
	var local := _index % per_turn
	var want := -TAU * float(local) / float(n)
	if instant:
		_target_rot = want
		_pivot.rotation.y = want
	else:
		while want - _target_rot > PI:
			want -= TAU
		while want - _target_rot < -PI:
			want += TAU
		_target_rot = want
	for i in n:
		var s := selected_scale if i == local else idle_scale
		if not _reciclando and ocupados.has(_turn * per_turn + i):
			s *= 0.8
		s *= _escala_base(_turn * per_turn + i)
		var tw := create_tween()
		tw.tween_property(_avatars[i], "scale", Vector3.ONE * s, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	if _name_label:
		var nombre := avatar_names[_index] if _index < avatar_names.size() else str(_index + 1)
		if not _reciclando and ocupados.has(_index):
			nombre += "  ·  OCUPADO"
		_name_label.text = nombre
	if _counter:
		var turnos := ceili(float(avatar_paths.size()) / float(per_turn))
		var texto := "Turno %d/%d  ·  %d/%d" % [_turn + 1, turnos, local + 1, n]
		if _reciclando:
			texto += "  ·  reciclando"
		_counter.text = texto


func _escala_base(indice: int) -> float:
	if indice < avatar_scales.size() and avatar_scales[indice] > 0.0:
		return avatar_scales[indice]
	return 1.0


func _confirm() -> void:
	if not _reciclando and ocupados.has(_index):
		return # plaza reservada por otro jugador
	if _index < playable_scenes.size() and not playable_scenes[_index].is_empty():
		var ruta := playable_scenes[_index]
		avatar_confirmed.emit(ruta)
		# Solo cambia de escena si se ejecuta suelto (sin nadie escuchando).
		if get_tree().current_scene == self:
			get_tree().change_scene_to_file(ruta)


func _on_prev_pressed() -> void:
	_move(-1)


func _on_next_pressed() -> void:
	_move(1)


func _on_confirm_pressed() -> void:
	_confirm()
