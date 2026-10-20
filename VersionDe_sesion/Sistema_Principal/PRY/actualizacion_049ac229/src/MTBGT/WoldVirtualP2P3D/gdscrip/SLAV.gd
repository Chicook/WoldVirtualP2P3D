extends Node3D
## SLAV - Selector de Avatares (carrusel 3D giratorio)

signal avatar_confirmed(scene_path: String)

@export var avatar_scenes: Array[PackedScene] = []
@export var playable_scenes: Array[String] = []
@export var avatar_names: Array[String] = []
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
var _target_rot := 0.0

@onready var _name_label: Label = %NameLabel
@onready var _counter: Label = %Counter


func _ready() -> void:
	_pivot = Node3D.new()
	_pivot.name = "Pivot"
	add_child(_pivot)

	var n := avatar_scenes.size()
	for i in n:
		var inst := avatar_scenes[i].instantiate() as Node3D
		if inst == null:
			continue
		_pivot.add_child(inst)
		var a := TAU * float(i) / float(n)
		inst.position = Vector3(sin(a) * radius, y_offset, cos(a) * radius)
		inst.rotation.y = a + deg_to_rad(face_offset_deg)
		for ap in inst.find_children("*", "AnimationPlayer", true, false):
			(ap as AnimationPlayer).play(idle_animation)
			(ap as AnimationPlayer).seek(randf() * 3.0, true)
		_avatars.append(inst)

	_apply_selection(true)


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
	var n := _avatars.size()
	if n == 0:
		return
	_index = wrapi(_index + dir, 0, n)
	_apply_selection(false)


func _apply_selection(instant: bool) -> void:
	var n := _avatars.size()
	if n == 0:
		return
	var want := -TAU * float(_index) / float(n)
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
		var s := selected_scale if i == _index else idle_scale
		var tw := create_tween()
		tw.tween_property(_avatars[i], "scale", Vector3.ONE * s, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	if _name_label:
		_name_label.text = avatar_names[_index] if _index < avatar_names.size() else str(_index + 1)
	if _counter:
		_counter.text = "%d / %d" % [_index + 1, n]


func _confirm() -> void:
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
