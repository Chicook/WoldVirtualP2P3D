extends Node
## Guarda y recupera el avatar elegido por el jugador.
##
## Se registra como autoload con el nombre `Avatares`. Mantiene dos sitios:
##   - `user://avatar_jugador.cfg`  → selección nueva, independiente del registro.
##   - `user://registro.cfg`        → compatibilidad con ChunkManager/PlayerSync,
##                                    que siguen leyendo `jugador/avatar_scene`.

const RUTA_AVATAR := "user://avatar_jugador.cfg"
const SECCION := "avatar"
const Catalogo = preload("res://avatares/CatalogoAvatares.gd")

var id_actual: String = ""


func _ready() -> void:
	cargar()


func cargar() -> String:
	var cfg := ConfigFile.new()
	if cfg.load(RUTA_AVATAR) != OK:
		id_actual = ""
		return id_actual
	var guardado := str(cfg.get_value(SECCION, "id", "")).strip_edges()
	if Catalogo.id_valido(guardado):
		id_actual = guardado
	else:
		id_actual = ""
	return id_actual


func guardar(id: String) -> bool:
	if not Catalogo.id_valido(id):
		return false
	id_actual = id.to_upper()
	var cfg := ConfigFile.new()
	cfg.load(RUTA_AVATAR)
	cfg.set_value(SECCION, "id", id_actual)
	cfg.set_value(SECCION, "escena", Catalogo.escena_de(id_actual))
	cfg.set_value(SECCION, "guardado", Time.get_datetime_string_from_system())
	cfg.save(RUTA_AVATAR)
	sincronizar_registro(id_actual, "")
	return true


## Escribe también el registro que consume el resto del mundo (ChunkManager,
## PlayerSync, teleport y reserva de plazas).
func sincronizar_registro(id: String, nick: String) -> void:
	if not Catalogo.id_valido(id):
		return
	var cfg := ConfigFile.new()
	cfg.load("user://registro.cfg")
	cfg.set_value("jugador", "avatar_scene", Catalogo.escena_de(id))
	cfg.set_value("jugador", "avatar_id", id.to_upper())
	if not nick.strip_edges().is_empty():
		cfg.set_value("jugador", "nick", nick.strip_edges())
	cfg.set_value("jugador", "avatar_reparado", true)
	cfg.save("user://registro.cfg")


func ruta_actual() -> String:
	if id_actual.is_empty():
		cargar()
	return Catalogo.escena_de(id_actual)


func crear(id: String = "", con_camara: bool = true) -> Node3D:
	var elegido := id if not id.is_empty() else id_actual
	if elegido.is_empty():
		elegido = str(Catalogo.por_indice(0).get("id", ""))
	var nodo: Node3D = Catalogo.crear(elegido)
	if nodo != null:
		nodo.es_selector = not con_camara
	return nodo


## Sustituye el avatar de un mundo ya montado (ISLA3Dblock u otro Node3D que
## tenga un hijo llamado USERBASE).
func aplicar_a_mundo(mundo: Node, id: String = "") -> bool:
	var elegido := id if not id.is_empty() else id_actual
	if elegido.is_empty() or mundo == null or not is_instance_valid(mundo):
		return false
	var nuevo := crear(elegido, true)
	if nuevo == null:
		return false
	var viejo := mundo.get_node_or_null("USERBASE")
	if viejo == null:
		nuevo.name = "USERBASE"
		mundo.add_child(nuevo)
		return true
	nuevo.name = "USERBASE"
	if viejo is Node3D and nuevo is Node3D:
		nuevo.transform = (viejo as Node3D).transform
	var padre := viejo.get_parent()
	var indice := viejo.get_index()
	viejo.queue_free()
	padre.add_child(nuevo)
	padre.move_child(nuevo, indice)
	return true


func hay_seleccion() -> bool:
	return not id_actual.is_empty() and Catalogo.id_valido(id_actual)
