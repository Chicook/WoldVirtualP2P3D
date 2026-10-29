extends SceneTree
## Retirada de islas de jugadores que ya no están conectados (sin red).
##
## El anfitrión retira la isla de un peer al recibir su desconexión y conserva el
## registro del dueño, de modo que si el mismo UUID vuelve recupera su índice.
## Sin ese registro no se instancia ninguna isla: al arrancar sin usuarios
## conectados el mundo no debe tener islas ajenas.

const CM = preload("res://gdscrip/ChunkManager.gd")

var _fallos := 0


func _initialize() -> void:
	_correr()


func _check(cond: bool, texto: String) -> void:
	if cond:
		print("OK    ", texto)
	else:
		print("FALLO ", texto)
		_fallos += 1


func _correr() -> void:
	await process_frame

	# Un ChunkManager recién creado (fuera del árbol, sin abrir el 8911) no tiene islas.
	var cm = CM.new()
	_check(cm.spawned_indices.is_empty() and cm.island_nodes.is_empty(),
			"sin usuarios conectados no hay islas instanciadas")

	# Dos jugadores con isla: índice 0 (jugador 5) e índice 1 (jugador 6).
	var isla_a := Node3D.new()
	var oceano_a := Node3D.new()
	var isla_b := Node3D.new()
	var oceano_b := Node3D.new()
	cm.add_child(isla_a)
	cm.add_child(oceano_a)
	cm.add_child(isla_b)
	cm.add_child(oceano_b)
	cm.spawned_indices[0] = true
	cm.spawned_indices[1] = true
	cm.island_nodes[0] = [isla_a, oceano_a]
	cm.island_nodes[1] = [isla_b, oceano_b]
	cm.island_owners[0] = [5, "B", "11111111-1111-1111-1111-111111111111"]
	cm.island_owners[1] = [6, "C", "22222222-2222-2222-2222-222222222222"]
	cm._uuid_por_isla[0] = "11111111-1111-1111-1111-111111111111"
	cm._uuid_por_isla[1] = "22222222-2222-2222-2222-222222222222"
	cm._islas_por_uuid["11111111-1111-1111-1111-111111111111"] = 0
	cm._islas_por_uuid["22222222-2222-2222-2222-222222222222"] = 1

	# El jugador 5 se desconecta: su isla sale de la escena.
	cm._despawn_island(0)

	_check(not cm.spawned_indices.has(0), "el índice 0 queda libre")
	_check(not cm.island_nodes.has(0), "island_nodes ya no guarda la isla retirada")
	_check(cm.get_child_count() == 2, "los nodos de la isla salen de la escena")
	_check(cm.spawned_indices.has(1) and cm.island_nodes.has(1),
			"la isla del jugador que sigue conectado permanece")
	_check(cm.island_owners.has(0) and cm._islas_por_uuid.get(
			"11111111-1111-1111-1111-111111111111", -1) == 0,
			"el registro del dueño se conserva para su vuelta")

	# Retirar una isla que ya no existe no debe romper nada.
	cm._despawn_island(99)
	_check(cm.get_child_count() == 2 and cm.spawned_indices.size() == 1,
			"retirar una isla inexistente no altera el mundo")

	# Limpieza: los nodos viven fuera del árbol, donde queue_free() no se procesa.
	for nodo in [isla_a, oceano_a, isla_b, oceano_b]:
		if is_instance_valid(nodo) and nodo.get_parent() == cm:
			cm.remove_child(nodo)
		if is_instance_valid(nodo):
			nodo.free()
	cm.free()

	print("== islas/fantasma, fallos=", _fallos, " ==")
	quit(0 if _fallos == 0 else 1)
