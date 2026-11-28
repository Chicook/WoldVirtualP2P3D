extends Node3D
## Isla Única LucIA: futura DAO del metaverso y sede de LucIA.
##
## Reglas de la isla:
## - Vive siempre en el origen (0,0,0) del mundo, en planta; la altura la marca
##   el terreno del GLB igual que en las islas de ChunkManager.
## - No participa del reparto de islas de ChunkManager (no tiene índice, no se
##   reclama y no se retira al desconectarse nadie), así que nunca se duplica.
## - Es el único nodo del grupo `isla_unica_lucia`; una copia accidental se
##   descarta al arrancar.
## - Su malla es IslaUnicaLucIA.glb. Si Godot aún no ha importado el GLB, se
##   levanta una plataforma de respaldo para no dejar el mundo sin suelo.

const Catalogo = preload("res://avatares/CatalogoAvatares.gd")
const GRUPO := "isla_unica_lucia"
const RUTA_GLB := "res://lucia3D/IslaUnicaLucIA/IslaUnicaLucIA.glb"
const RUTA_DATOS := "res://lucia3D/IslaUnicaLucIA/DAO/dao_metaverso.json"
## Mismo desplazamiento vertical que `ISLA3DCHUNK` en ISLA3Dblock.tscn: el GLB
## comparte el terreno de las islas de ChunkManager, y sin él la meseta quedaría
## 10 m por encima del resto del archipiélago.
const OFFSET_ISLA := -9.75
## Altura de la meseta del GLB ya desplazada; coincide con la superficie de las
## islas de jugador (~40, con el mar en ~39).
const ALTURA_MESETA := 40.2

@export var id_dao: String = "woldvirtual.dao.metaverso"
@export var es_sede_lucia: bool = true
@export var activa: bool = true

var datos_dao: Dictionary = {}
var malla_cargada := false
var _contenedor_miembros_dao: Node3D = null
var _avatares_miembros_dao: Dictionary = {}
var _conectando_dao := false
var _dao_conectada := false


func _ready() -> void:
	if not _es_la_unica():
		return
	add_to_group(GRUPO)
	global_position = Vector3.ZERO
	rotation = Vector3.ZERO
	if not activa:
		return
	_cargar_datos()
	_cargar_malla()
	# Añadir el servicio a /root desde _ready puede coincidir con el montaje
	# recursivo de hijos de la escena y fallar con "Parent node is busy".
	call_deferred("_conectar_servicio_modular")
	_montar_terminal_dao()
	var perfil := ConfigFile.new()
	if perfil.load("user://registro.cfg") == OK and FileAccess.file_exists("user://cuenta.json"):
		call_deferred("conectar_dao_al_metaverso")


## Conecta la DAO al metaverso: asegura el túnel efímero, conecta la sesión modular,
## registra al ciudadano y su avatar, activa la presencia periódica y sincroniza vecinos.
func conectar_dao_al_metaverso() -> Dictionary:
	if _conectando_dao:
		return {"ok": true, "mensaje": "Conexión en curso"}
	_conectando_dao = true
	var res := await _realizar_conexion_dao()
	_conectando_dao = false
	_dao_conectada = bool(res.get("ok", false))
	return res


func _realizar_conexion_dao() -> Dictionary:
	var nick := "Vecino"
	var avatar_scene := "res://avatares/AVMJ1.tscn"
	var cfg := ConfigFile.new()
	if cfg.load("user://registro.cfg") == OK:
		nick = str(cfg.get_value("jugador", "nick", nick)).strip_edges()
		avatar_scene = str(cfg.get_value("jugador", "avatar_scene", avatar_scene)).strip_edges()
	if FileAccess.file_exists("user://cuenta.json"):
		var cuenta = JSON.parse_string(FileAccess.get_file_as_string("user://cuenta.json"))
		if cuenta is Dictionary:
			if nick == "Vecino" or nick.is_empty():
				nick = str(cuenta.get("nick", nick)).strip_edges()
	if nick.is_empty():
		nick = "Vecino"

	# 1. Asegurar / solicitar túnel efímero al visor C#
	var tunel_url := ""
	var tunel_enlace := ""
	var ruta_solicitud := ProjectSettings.globalize_path("user://tunel_solicitud.json")
	var ruta_temporal := ruta_solicitud + ".tmp"
	var ruta_resultado := ProjectSettings.globalize_path("user://validacion_resultado.json")
	if FileAccess.file_exists("user://validacion_resultado.json"):
		DirAccess.remove_absolute(ruta_resultado)
	var f := FileAccess.open("user://tunel_solicitud.json.tmp", FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify({"accion": "conectar", "nick": nick, "uso_interno": true}))
		f.close()
		DirAccess.rename_absolute(ruta_temporal, ruta_solicitud)

	var limite := Time.get_ticks_msec() + 8000
	while Time.get_ticks_msec() < limite:
		if FileAccess.file_exists("user://validacion_resultado.json"):
			var res_json = JSON.parse_string(FileAccess.get_file_as_string("user://validacion_resultado.json"))
			if res_json is Dictionary and bool(res_json.get("exito", false)):
				tunel_url = str(res_json.get("url", "")).strip_edges()
				tunel_enlace = str(res_json.get("enlace", tunel_url)).strip_edges()
				break
		elif FileAccess.file_exists("user://tunel_lucia_url.json"):
			var res_lucia = JSON.parse_string(FileAccess.get_file_as_string("user://tunel_lucia_url.json"))
			if res_lucia is Dictionary and bool(res_lucia.get("exito", false)):
				tunel_url = str(res_lucia.get("url", "")).strip_edges()
				tunel_enlace = str(res_lucia.get("enlace", tunel_url)).strip_edges()
				if not tunel_url.is_empty():
					break
		await get_tree().create_timer(0.1).timeout

	if tunel_url.is_empty() and FileAccess.file_exists("user://tunel_lucia_url.json"):
		var res_lucia = JSON.parse_string(FileAccess.get_file_as_string("user://tunel_lucia_url.json"))
		if res_lucia is Dictionary:
			tunel_url = str(res_lucia.get("url", "")).strip_edges()
			tunel_enlace = str(res_lucia.get("enlace", tunel_url)).strip_edges()

	# El mecanismo actual es interno: no copiar ni exponer una invitación antigua.

	# 2. Conectar y registrar en ServicioConexionModular
	var ok_dao := false
	var sm := _servicio_modular()
	if sm != null and sm.has_method("habilitado") and sm.call("habilitado"):
		if not sm.miembros_actualizados.is_connected(_actualizar_miembros_dao):
			sm.miembros_actualizados.connect(_actualizar_miembros_dao)
		var conn: Dictionary = await sm.conectar(nick)
		if bool(conn.get("ok", false)):
			var token: String = str(conn.get("body", {}).get("token", ""))
			if not token.is_empty():
				var registro: Dictionary = await sm.registrar(token, nick, avatar_scene)
				if bool(registro.get("ok", false)):
					var cuerpo: Dictionary = registro.get("body", {})
					var miembro: Dictionary = cuerpo.get("miembro", {})
					var id_miembro := str(miembro.get("id", "")).strip_edges()
					if not id_miembro.is_empty():
						# El heartbeat identifica al miembro creado; el token solo autoriza
						# el registro y no existe en la tabla de presencia del servidor.
						sm.activar_presencia(id_miembro)
						ok_dao = true
					else:
						push_warning("[DAO modular] El alta respondió correctamente, pero no devolvió el id del miembro.")
				else:
					push_warning("[DAO modular] No se pudo registrar el miembro: %s" % str(registro.get("body", {})))
		await sm.refrescar_miembros()

	print("[IslaUnicaLucIA] DAO conectada al metaverso. Túnel: %s, DAO modular: %s" % [tunel_url, ok_dao])

	# ── Escribir tunel_dao_url.json para que LuciaRecepcion._poll_dao() lo detecte ──
	# Espejo exacto del esquema que escribe el C# para tunel_lucia_url.json.
	var exito_tunel := not tunel_url.is_empty()
	var datos_dao_json := {
		"exito": exito_tunel,
		"url": tunel_url,
		"enlace": tunel_enlace,
		"mensaje": ("DAO activa: " + tunel_url) if exito_tunel else "Túnel DAO no disponible",
		"dao_modular": ok_dao,
		"timestamp": Time.get_datetime_string_from_system()
	}
	var ruta_dao_json := "user://tunel_dao_url.json"
	var tmp_dao := ruta_dao_json + ".tmp"
	var fw := FileAccess.open(tmp_dao, FileAccess.WRITE)
	if fw != null:
		fw.store_string(JSON.stringify(datos_dao_json, "\t"))
		fw.close()
		DirAccess.rename_absolute(
			ProjectSettings.globalize_path(tmp_dao),
			ProjectSettings.globalize_path(ruta_dao_json)
		)
		print("[IslaUnicaLucIA] tunel_dao_url.json escrito (exito=%s, url=%s)" % [exito_tunel, tunel_url])
	else:
		push_warning("[IslaUnicaLucIA] No se pudo escribir tunel_dao_url.json")

	return {
		"ok": true,
		"url": tunel_url,
		"enlace": tunel_enlace,
		"dao": ok_dao
	}


func _servicio_modular() -> Node:
	if has_node("/root/ServicioConexionModular"):
		return get_node("/root/ServicioConexionModular")
	var sc = load("res://gdscrip/ServicioConexionModular.gd")
	if sc != null:
		var inst = sc.new()
		inst.name = "ServicioConexionModular"
		get_tree().root.add_child(inst)
		return inst
	return null


func _conectar_servicio_modular() -> void:
	var sm := _servicio_modular()
	if sm != null and sm.has_method("habilitado") and sm.call("habilitado"):
		if not sm.miembros_actualizados.is_connected(_actualizar_miembros_dao):
			sm.miembros_actualizados.connect(_actualizar_miembros_dao)
		sm.refrescar_miembros()


## Incorpora a la DAO única a un peer real del mundo compartido. El avatar
## queda alrededor de la sede; su isla personal la administra ChunkManager.
func incorporar_vecino_remoto(peer_id: int, avatar_scene: String) -> void:
	if peer_id <= 0 or avatar_scene.is_empty():
		return
	var lista: Array = []
	if _contenedor_miembros_dao != null and is_instance_valid(_contenedor_miembros_dao):
		for miembro_id in _avatares_miembros_dao.keys():
			var avatar: Node3D = _avatares_miembros_dao[miembro_id]
			var placa := avatar.get_node_or_null("NombreDAO") as Label3D
			lista.append({"id": str(miembro_id), "avatar": avatar.scene_file_path,
				"nick": placa.text if placa != null else "Vecino"})
	var id := "p2p-%d" % peer_id
	var encontrado := false
	for i in lista.size():
		if str(lista[i].get("id", "")) == id:
			lista[i]["avatar"] = avatar_scene
			encontrado = true
			break
	if not encontrado:
		lista.append({"id": id, "avatar": avatar_scene, "nick": "Vecino %d" % peer_id})
	_actualizar_miembros_dao(lista)


## La presencia visual P2P se reconcilia con los peers aún conectados.
func sincronizar_vecinos_p2p(peer_ids: Dictionary) -> void:
	if _contenedor_miembros_dao == null or not is_instance_valid(_contenedor_miembros_dao):
		return
	var lista: Array = []
	for miembro_id in _avatares_miembros_dao.keys():
		var id := str(miembro_id)
		if id.begins_with("p2p-"):
			var peer := int(id.trim_prefix("p2p-"))
			if not peer_ids.has(peer):
				continue
		var avatar: Node3D = _avatares_miembros_dao[miembro_id]
		var placa := avatar.get_node_or_null("NombreDAO") as Label3D
		lista.append({"id": id, "avatar": avatar.scene_file_path,
			"nick": placa.text if placa != null else "Vecino"})
	_actualizar_miembros_dao(lista)


func _actualizar_miembros_dao(miembros: Array) -> void:
	if _contenedor_miembros_dao == null or not is_instance_valid(_contenedor_miembros_dao):
		_contenedor_miembros_dao = get_node_or_null("MiembrosModularesDAO") as Node3D
		if _contenedor_miembros_dao == null:
			_contenedor_miembros_dao = Node3D.new()
			_contenedor_miembros_dao.name = "MiembrosModularesDAO"
			add_child(_contenedor_miembros_dao)
	var presentes: Dictionary = {}
	var visibles: Array[Dictionary] = []
	var sm := _servicio_modular()
	for item in miembros:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var miembro: Dictionary = item
		var id := str(miembro.get("id", miembro.get("Id", "")))
		if id.is_empty():
			continue
		# Si este miembro coincide con el ID del jugador local actual, no duplicar el avatar estático
		var sm_id = sm.get("_miembro_id") if sm != null else ""
		if not str(sm_id).is_empty() and id == str(sm_id):
			continue
		presentes[id] = true
		visibles.append(miembro)
		if not _avatares_miembros_dao.has(id):
			var avatar_id := str(miembro.get("avatar", miembro.get("Avatar", "")))
			var avatar := Catalogo.crear(avatar_id)
			if avatar == null:
				continue
			avatar.name = "Miembro_" + id
			avatar.set("es_selector", true)
			avatar.set_physics_process(false)
			avatar.set_process_input(false)
			avatar.set_process_unhandled_input(false)
			_bloquear_colisiones_avatar(avatar)
			var placa := Label3D.new()
			placa.name = "NombreDAO"
			placa.text = str(miembro.get("nick", miembro.get("Nick", "Vecino")))
			placa.position.y = 2.05
			placa.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			placa.font_size = 32
			placa.outline_size = 8
			avatar.add_child(placa)
			_contenedor_miembros_dao.add_child(avatar)
			_avatares_miembros_dao[id] = avatar
	for i in visibles.size():
		var miembro: Dictionary = visibles[i]
		var id := str(miembro.get("id", miembro.get("Id", "")))
		if not _avatares_miembros_dao.has(id):
			continue
		var avatar: Node3D = _avatares_miembros_dao[id]
		var angulo := TAU * float(i) / maxf(float(visibles.size()), 1.0)
		avatar.position = Vector3(cos(angulo) * 7.0, ALTURA_MESETA, sin(angulo) * 7.0)
		avatar.look_at(Vector3(0.0, ALTURA_MESETA, 0.0), Vector3.UP)
	for id in _avatares_miembros_dao.keys():
		if not presentes.has(str(id)):
			var avatar: Node = _avatares_miembros_dao[id]
			if is_instance_valid(avatar):
				avatar.queue_free()
			_avatares_miembros_dao.erase(id)


func _bloquear_colisiones_avatar(nodo: Node) -> void:
	if nodo is CollisionShape3D:
		(nodo as CollisionShape3D).disabled = true
	elif nodo is CollisionPolygon3D:
		(nodo as CollisionPolygon3D).disabled = true
	elif nodo is CollisionObject3D:
		(nodo as CollisionObject3D).collision_layer = 0
		(nodo as CollisionObject3D).collision_mask = 0
	for hijo in nodo.get_children():
		_bloquear_colisiones_avatar(hijo)


func _es_la_unica() -> bool:
	for nodo in get_tree().get_nodes_in_group(GRUPO):
		if nodo != self and is_instance_valid(nodo):
			push_warning("IslaUnicaLucIA duplicada: se descarta esta instancia.")
			queue_free()
			return false
	return true


func _cargar_datos() -> void:
	if not FileAccess.file_exists(RUTA_DATOS):
		push_warning("Sin carta DAO en " + RUTA_DATOS + "; se usan valores por defecto.")
		return
	var crudo = JSON.parse_string(FileAccess.get_file_as_string(RUTA_DATOS))
	if crudo is Dictionary:
		datos_dao = crudo
		var carta := str(datos_dao.get("id", ""))
		if not carta.is_empty() and carta != id_dao:
			push_warning("Carta DAO '%s' distinta de id_dao '%s'." % [carta, id_dao])
	else:
		push_warning("La carta DAO no es un JSON válido.")


func _cargar_malla() -> void:
	if not ResourceLoader.exists(RUTA_GLB):
		push_warning("IslaUnicaLucIA.glb sin importar todavía; se usa plataforma provisional.")
		_plataforma_respaldo()
		return
	var recurso: Resource = load(RUTA_GLB)
	if not (recurso is PackedScene):
		push_warning("IslaUnicaLucIA.glb no se cargó como escena; se usa plataforma provisional.")
		_plataforma_respaldo()
		return
	var malla := (recurso as PackedScene).instantiate() as Node3D
	malla.name = "MallaIsla"
	malla.position = Vector3(0.0, OFFSET_ISLA, 0.0)
	add_child(malla)
	malla_cargada = true
	# Los nodos `-col` del GLB ya traen colisión al importarse; si el import no
	# la generó, se construye aquí para que la isla nunca quede sin suelo.
	if _cuerpo_colision(malla) == null:
		_colision_trimesh(malla)


func _cuerpo_colision(raiz: Node) -> CollisionObject3D:
	for hijo in raiz.get_children():
		if hijo is CollisionObject3D:
			return hijo as CollisionObject3D
		var encontrado := _cuerpo_colision(hijo)
		if encontrado != null:
			return encontrado
	return null


func _colision_trimesh(raiz: Node) -> void:
	for hijo in raiz.get_children():
		if hijo is MeshInstance3D and (hijo as MeshInstance3D).mesh != null:
			(hijo as MeshInstance3D).create_trimesh_collision()
		_colision_trimesh(hijo)


func _plataforma_respaldo() -> void:
	var plataforma := MeshInstance3D.new()
	plataforma.name = "PlataformaRespaldo"
	var malla := CylinderMesh.new()
	malla.top_radius = 90.0
	malla.bottom_radius = 90.0
	malla.height = 4.0
	plataforma.mesh = malla
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.16, 0.24, 0.2)
	material.roughness = 0.9
	plataforma.material_override = material
	plataforma.position = Vector3(0.0, ALTURA_MESETA - 2.0, 0.0)
	add_child(plataforma)

	var cuerpo := StaticBody3D.new()
	cuerpo.name = "ColisionRespaldo"
	cuerpo.position = plataforma.position
	var forma := CollisionShape3D.new()
	var cilindro := CylinderShape3D.new()
	cilindro.radius = 90.0
	cilindro.height = 4.0
	forma.shape = cilindro
	cuerpo.add_child(forma)
	add_child(cuerpo)


## Punto donde se sienta el núcleo de LucIA cuando sea su sede.
func sede_lucia() -> Marker3D:
	if not es_sede_lucia:
		return null
	return get_node_or_null("SedeLucIA") as Marker3D


## Plaza con las estaciones del proceso de registro de la DAO.
func plaza_registro():
	return get_node_or_null("PlazaRegistroDAO")


func es_unica() -> bool:
	return is_in_group(GRUPO)


func _montar_terminal_dao() -> void:
	if get_node_or_null("TerminalDAO") != null:
		return
	var terminal := Node3D.new()
	terminal.name = "TerminalDAO"
	terminal.position = Vector3(0.0, ALTURA_MESETA, 16.0)
	add_child(terminal)

	# Pedestal
	var mi := MeshInstance3D.new()
	var cil := CylinderMesh.new()
	cil.top_radius = 1.2
	cil.bottom_radius = 1.4
	cil.height = 0.9
	mi.mesh = cil
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.08, 0.14, 0.22)
	mat.metallic = 0.8
	mat.roughness = 0.3
	mat.emission_enabled = true
	mat.emission = Color(0.12, 0.72, 1.0)
	mat.emission_energy_multiplier = 0.8
	mi.material_override = mat
	mi.position.y = 0.45
	terminal.add_child(mi)

	# Orbe superior
	var orbe := MeshInstance3D.new()
	var esfera := SphereMesh.new()
	esfera.radius = 0.35
	esfera.height = 0.7
	orbe.mesh = esfera
	var mat_orbe := StandardMaterial3D.new()
	mat_orbe.albedo_color = Color(0.2, 0.85, 1.0)
	mat_orbe.emission_enabled = true
	mat_orbe.emission = Color(0.12, 0.85, 1.0)
	mat_orbe.emission_energy_multiplier = 2.0
	orbe.material_override = mat_orbe
	orbe.position.y = 1.3
	terminal.add_child(orbe)

	# Colisión física del pedestal
	var body := StaticBody3D.new()
	var col_shape := CollisionShape3D.new()
	var cyl_shape := CylinderShape3D.new()
	cyl_shape.radius = 1.4
	cyl_shape.height = 0.9
	col_shape.shape = cyl_shape
	col_shape.position.y = 0.45
	body.add_child(col_shape)
	terminal.add_child(body)

	# Rótulo holográfico
	var label := Label3D.new()
	label.name = "RotuloTerminal"
	label.text = "🏛 TERMINAL DAO\nConectar al Metaverso"
	label.position.y = 2.2
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = 32
	label.outline_size = 8
	label.modulate = Color(0.4, 0.9, 1.0)
	terminal.add_child(label)

	# Área de proximidad
	var area := Area3D.new()
	area.name = "AreaConexion"
	var area_shape := CollisionShape3D.new()
	var esfera_shape := SphereShape3D.new()
	esfera_shape.radius = 4.0
	area_shape.shape = esfera_shape
	area.add_child(area_shape)
	area.body_entered.connect(_on_terminal_dao_body_entered)
	terminal.add_child(area)


func _on_terminal_dao_body_entered(body: Node3D) -> void:
	if body != null and (body.name == "USERBASE" or body.is_in_group("jugador_local")):
		conectar_dao_al_metaverso()
