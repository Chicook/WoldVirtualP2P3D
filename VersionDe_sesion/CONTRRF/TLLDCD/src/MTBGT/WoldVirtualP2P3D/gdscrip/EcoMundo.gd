extends Node
## Escucha muda para la Sonda: mientras el invitado consulta plazas, el mundo
## del anfitrion le envia islas y roster. Este nodo ocupa la misma ruta que
## ISLA3Dblock para que esos RPC no fallen y se descarten sin efectos.

@rpc("authority", "call_local", "reliable")
func _spawn_island_for_player(_id: int, _index: int, _nick: String = "", _uuid: String = "") -> void:
	pass


@rpc("authority", "reliable")
func _sync_roster(_data: Dictionary) -> void:
	pass


@rpc("authority", "reliable")
func _sync_turnos(_datos: Dictionary) -> void:
	pass


@rpc("authority", "reliable")
func _avatar_asignado(_ruta: String, _turno: int, _reciclado: bool) -> void:
	pass


## PlayerSync del anfitrion difunde posiciones cada 100 ms; durante la sonda
## se descartan aqui para no llenar la consola de "Node not found".
class EcoPlayerSync extends Node3D:
	@rpc("any_peer", "unreliable")
	func _net_position(_pos: Vector3, _rot_y: float, _nick: String, _estado: int, _avatar_path: String = "", _pers: String = "") -> void:
		pass
