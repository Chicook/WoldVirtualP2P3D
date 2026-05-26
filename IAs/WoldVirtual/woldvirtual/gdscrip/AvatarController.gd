extends Node

const HEIGHT = 28.0
const OCEAN_LEVEL = 3.5

var my_avatar: CharacterBody3D

func setup_avatar(avatar: CharacterBody3D):
	my_avatar = avatar
	# El control de cámara ahora es gestionado externamente por CameraController (RF-05)

func _process(_delta: float):
	# Detección de eventos sociales remotos (RF-12)
	var network = get_parent().get_node_or_null("NetworkLayer")
	if network and network._last_good_state.has("e"):
		var events = network._last_good_state.e
		for pid in events:
			if pid == network.local_id: continue
			for e in events[pid]:
				_handle_remote_event(pid, e)

func _handle_remote_event(pid: String, event: Dictionary):
	# Evitar procesar el mismo evento varias veces (usando timestamp)
	var etime = event.get("ts", 0)
	if etime < Time.get_unix_time_from_system() - 2.0: return 
	
	print("Social Event from ", pid, ": ", event.type)
	# Aquí se activarían las animaciones o burbujas de texto en el futuro
	if !is_instance_valid(my_avatar): return
	
	if my_avatar.global_position.y < -150.0:
		my_avatar.global_position.y = HEIGHT
		
	_lock_ocean()

func _lock_ocean():
	var ocean = get_tree().get_root().find_child("Oceano", true, false)
	if is_instance_valid(ocean):
		ocean.global_position.y = OCEAN_LEVEL
