extends Node3D
## Prueba visual de la Isla Única LucIA (DAO): única, en el origen, con su
## malla GLB, su carta DAO y las cuatro estaciones de registro.
##
## Usa el mismo entorno que el metaverso: el WorldEnvironment y el sol de
## WoldVirtual3DP2P.tscn y el bloque `ISLA3Dblock` real (1 isla + 1 mar por
## bloque), con la DAO al centro y cuatro islas de jugador en cruz.
##
## Uso:
##   godot --path <proyecto> res://lucia3D/IslaUnicaLucIA/PRUEBAS_VISUALES/PreviewDAO.tscn
## Guarda capturas en res://lucia3D/IslaUnicaLucIA/PRUEBAS_VISUALES/capturas/
## y termina con código 1 si alguna comprobación falla.

const ESCENA_DAO := "res://lucia3D/IslaUnicaLucIA/ESCENAS/IslaUnicaLucIA.tscn"
const RUTA_MUNDO := "res://WoldVirtual3DP2P.tscn"
const RUTA_BLOQUE := "res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn"
const SALIDA := "res://lucia3D/IslaUnicaLucIA/PRUEBAS_VISUALES/capturas"
const CHUNK := 199.5
const SUPERFICIE_MAR := 39.06
const GRUPO := "isla_unica_lucia"

var _dao: Node3D = null
var _fallos: Array[String] = []


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(SALIDA))
	_entorno()
	_bloques_entorno()
	_cargar_dao()
	await _validar()
	await _capturar_todo()
	print("[PRUEBA] fallos: %d" % _fallos.size())
	get_tree().quit(0 if _fallos.is_empty() else 1)


## Cielo, niebla, glow y sol tal como los define la escena del mundo.
func _entorno() -> void:
	var recurso := load(RUTA_MUNDO)
	if not (recurso is PackedScene):
		_fallos.append("No carga la escena del mundo " + RUTA_MUNDO)
		return
	var mundo := (recurso as PackedScene).instantiate()
	var ambiente := mundo.get_node_or_null("WorldEnvironment")
	var sol := mundo.get_node_or_null("DirectionalLight3D")
	if ambiente != null:
		ambiente.owner = null
		mundo.remove_child(ambiente)
		add_child(ambiente)
	if sol != null:
		sol.owner = null
		mundo.remove_child(sol)
		add_child(sol)
	mundo.free()
	_check(ambiente != null and sol != null, "entorno del metaverso (cielo y sol)")


## Cada bloque del mundo es 1 isla + 1 mar. La DAO recibe su bloque de mar en
## el origen, como hace ChunkManager, y las islas de jugador se colocan en cruz.
func _bloques_entorno() -> void:
	var plantilla := load(RUTA_BLOQUE)
	if not (plantilla is PackedScene):
		_fallos.append("No carga el bloque de isla " + RUTA_BLOQUE)
		return
	_montar_bloque(plantilla, Vector3.ZERO, "BloqueDAO", true)
	var celdas := [Vector3(0, 0, -CHUNK), Vector3(CHUNK, 0, 0),
			Vector3(-CHUNK, 0, 0), Vector3(0, 0, CHUNK)]
	for i in celdas.size():
		_montar_bloque(plantilla, celdas[i], "Isla_%d" % i, false)


func _montar_bloque(plantilla: PackedScene, posicion: Vector3, nombre: String,
		solo_mar: bool) -> void:
	var bloque := plantilla.instantiate()
	var oceano := bloque.get_node_or_null("Oceano3D")
	var isla := bloque.get_node_or_null("ISLA3DCHUNK")
	if oceano == null:
		_fallos.append("El bloque de isla no trae Oceano3D")
		bloque.free()
		return
	bloque.remove_child(oceano)
	oceano.owner = null
	if not solo_mar and isla != null:
		bloque.remove_child(isla)
		isla.owner = null
	var contenedor := Node3D.new()
	contenedor.name = nombre
	contenedor.position = posicion
	add_child(contenedor)
	contenedor.add_child(oceano)
	if not solo_mar and isla != null:
		contenedor.add_child(isla)
	bloque.free()


func _cargar_dao() -> void:
	if not ResourceLoader.exists(ESCENA_DAO):
		_fallos.append("No existe la escena " + ESCENA_DAO)
		return
	var recurso := load(ESCENA_DAO)
	if not (recurso is PackedScene):
		_fallos.append("La escena DAO no carga como PackedScene")
		return
	_dao = (recurso as PackedScene).instantiate() as Node3D
	if _dao == null:
		_fallos.append("No se pudo instanciar la escena DAO")
		return
	add_child(_dao)


func _validar() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	if _dao == null:
		return

	var grupo := get_tree().get_nodes_in_group(GRUPO)
	_check(grupo.size() == 1, "isla única en el grupo", "nodos=%d" % grupo.size())
	_check(_dao.global_position.is_equal_approx(Vector3.ZERO), "anclada en el origen",
			str(_dao.global_position))
	_check(bool(_dao.get("malla_cargada")), "malla GLB cargada",
			"usa plataforma de respaldo" if not bool(_dao.get("malla_cargada")) else "ok")

	var carta: Dictionary = _dao.get("datos_dao")
	_check(not carta.is_empty(), "carta DAO leída", "claves=%d" % carta.size())
	_check(str(carta.get("id", "")) == str(_dao.get("id_dao")), "id de carta coincide",
			"id=%s" % str(carta.get("id", "")))
	print("[PRUEBA] sede de LucIA: ", _dao.call("sede_lucia"))
	_medir_mallas(_dao)
	await _sondear_suelo()
	_validar_entorno()

	var plaza = _dao.call("plaza_registro")
	_check(plaza != null, "plaza de registro presente")
	if plaza == null:
		return

	var claves: Array = plaza.call("estaciones")
	_check(claves.size() == 4, "cuatro estaciones", str(claves))
	await get_tree().physics_frame
	await get_tree().physics_frame
	for clave in claves:
		var marcador: Marker3D = plaza.call("marcador", clave)
		if marcador == null:
			_check(false, "estación %s" % clave, "marcador ausente")
			continue
		print("[PRUEBA] estación %s en %s" % [clave, marcador.global_position])
		_check(marcador.get_child_count() >= 2, "estación %s con piso y etiqueta" % clave,
				"hijos=%d" % marcador.get_child_count())
		var suelo := _altura_suelo(marcador.global_position)
		_check(absf(suelo - marcador.global_position.y) < 1.5,
				"estación %s apoyada en el terreno" % clave,
				"suelo=%.2f marcador=%.2f" % [suelo, marcador.global_position.y])

	# El trámite completo debe cerrar en las cuatro estaciones.
	for clave in claves:
		plaza.call("abrir", clave)
		plaza.call("completar", clave, {"prueba": true})
	_check(bool(plaza.call("registro_completo")), "registro de las 4 estaciones completo",
			"progreso=%d" % int(plaza.call("progreso")))
	plaza.call("reiniciar")

	await _validar_interior()


func _validar_interior() -> void:
	var interior := _dao.get_node_or_null("InteriorDAO")
	_check(interior != null, "interior de la DAO instanciado")
	if interior == null:
		return
	var lucia = interior.call("lucia")
	_check(lucia != null, "Lucía en su despacho")
	if lucia != null:
		var altura := float(lucia.global_position.y) - 41.7
		_check(absf(altura - 0.5) < 0.2, "Lucía sobre el estrado del despacho",
				"altura=%.2f" % altura)

	var carrusel = interior.call("carrusel")
	_check(carrusel != null, "carrusel de avatares de la DAO")
	if carrusel != null:
		var total := int(carrusel.call("total_estatuas"))
		_check(total == 8, "carrusel con los 8 avatares del catálogo", "total=%d" % total)
		var con_malla := 0
		var en_pedestal := 0
		for estatua in carrusel.call("estatuas"):
			print("[PRUEBA] estatua %s global=%s visible=%s" % [estatua.name,
					estatua.global_position, estatua.is_visible_in_tree()])
			if absf(float(estatua.global_position.y) - 42.2) < 0.4:
				en_pedestal += 1
			if estatua.find_children("*", "MeshInstance3D", true, false).size() > 0:
				con_malla += 1
		_check(en_pedestal == total, "estatuas sobre los pedestales del atrio",
				"en_pedestal=%d" % en_pedestal)
		_check(con_malla == total, "estatuas con malla visible", "con_malla=%d" % con_malla)

	var portal = interior.call("portal")
	_check(portal != null, "portal del archipiélago")
	if portal != null:
		var z := float(portal.global_position.z)
		_check(absf(z - 18.2) < 0.5, "portal en el eje del acceso sur", "z=%.2f" % z)

	await get_tree().physics_frame
	await get_tree().physics_frame
	var suelo_salon := _rayo_suelo(Vector3(10.0, 45.0, 0.0), 30.0)
	_check(absf(suelo_salon - 41.7) < 0.25, "suelo del atrio a la altura del diseño",
			"y=%.2f" % suelo_salon)
	var suelo_dais := _rayo_suelo(Vector3(0.0, 46.0, 0.0), 30.0)
	_check(absf(suelo_dais - 42.2) < 0.25, "estrado del despacho transitable",
			"y=%.2f" % suelo_dais)
	var suelo_terraza := _rayo_suelo(Vector3(0.0, 45.0, 27.0), 30.0)
	_check(absf(suelo_terraza - 41.7) < 0.3, "terraza perimetral de la DAO",
			"y=%.2f" % suelo_terraza)

	# Las cuatro rampas y la del estrado declaran su collision shape en la escena
	# y deben ser transitables con un rayo desde arriba. La boca de Este y Oeste
	# vive a distinta altura porque el terreno sube distinto en cada eje.
	var perfil_y := {
		"RampaSur": [40.75, 41.05],
		"RampaEste": [40.869558, 41.169558],
		"RampaNorte": [40.75, 41.05],
		"RampaOeste": [41.290648, 41.590648],
	}
	for nombre_rampa in ["RampaSur", "RampaEste", "RampaNorte", "RampaOeste"]:
		var rampa := interior.get_node_or_null(nombre_rampa) as Node3D
		if rampa == null:
			_check(false, "rampa %s en la escena" % nombre_rampa)
			continue
		var y_rampa: float = perfil_y[nombre_rampa][0]
		var y_baranda: float = perfil_y[nombre_rampa][1]
		var forma := _forma_de(rampa, "ColisionRampa")
		_check(forma != null and forma.shape is BoxShape3D,
				"colisión de la rampa %s en la escena" % nombre_rampa)
		if forma == null:
			continue
		var centro := rampa.global_transform * Vector3(0.0, y_rampa, 33.45)
		var suelo := _rayo_suelo(centro + Vector3(0.0, 4.0, 0.0), 30.0)
		_check(absf(suelo - (centro.y + 0.15)) < 0.35,
				"rampa %s transitable" % nombre_rampa, "y=%.2f" % suelo)
		var umbral := rampa.global_transform * Vector3(0.0, 41.70, 30.9)
		var alto := _rayo_suelo(umbral + Vector3(0.0, 4.0, 0.0), 30.0)
		_check(absf(alto - 41.70) < 0.12, "umbral de la rampa %s a ras del atrio"
				% nombre_rampa, "y=%.2f" % alto)
		var barandas := rampa.get_node_or_null("ColisionBarandas") as StaticBody3D
		var izq: CollisionShape3D = barandas.get_node_or_null("BarandaIzq") if barandas != null else null
		var der: CollisionShape3D = barandas.get_node_or_null("BarandaDer") if barandas != null else null
		_check(izq != null and izq.shape is BoxShape3D and der != null and der.shape is BoxShape3D,
				"barandas de la rampa %s con colisión" % nombre_rampa)
		var rail := rampa.global_transform * Vector3(3.45, y_baranda, 33.45)
		var rail_y := _rayo_suelo(rail + Vector3(0.0, 4.0, 0.0), 30.0)
		_check(absf(rail_y - (rail.y + 0.13)) < 0.35,
				"baranda %s frena" % nombre_rampa, "y=%.2f" % rail_y)

	var rampa_dais := interior.get_node_or_null("ColisionRampaDais") as StaticBody3D
	var forma_dais: CollisionShape3D = null
	if rampa_dais != null:
		forma_dais = rampa_dais.get_node_or_null("CollisionShape3D") as CollisionShape3D
	_check(forma_dais != null and forma_dais.shape is BoxShape3D,
			"colisión de la rampa del estrado en la escena")
	if forma_dais != null:
		var alto_rampa := _rayo_suelo(Vector3(0.0, 46.0, 7.8), 30.0)
		_check(absf(alto_rampa - 42.05) < 0.3, "rampa del estrado transitable",
				"y=%.2f" % alto_rampa)


func _forma_de(padre: Node, nombre: String) -> CollisionShape3D:
	var cuerpo := padre.get_node_or_null(nombre) as StaticBody3D
	if cuerpo == null:
		return null
	return cuerpo.get_node_or_null("CollisionShape3D") as CollisionShape3D


func _rayo_suelo(punto: Vector3, hasta_y: float) -> float:
	var espacio := get_world_3d().direct_space_state
	var consulta := PhysicsRayQueryParameters3D.create(punto, Vector3(punto.x, hasta_y, punto.z))
	var golpe := espacio.intersect_ray(consulta)
	return float(golpe["position"].y) if not golpe.is_empty() else NAN


func _capturar_todo() -> void:
	if _dao == null:
		return
	await _vista("01_aerea", Vector3(150, 165, 150), Vector3(0, 42, 0), 60.0)
	await _vista("02_plaza_cenital", Vector3(0, 320, 40), Vector3(0, 40, 0), 40.0)
	await _vista("03_llegada_norte", Vector3(0, 45, -48), Vector3(0, 44, 0), 65.0)
	await _vista("04_estacion_este", Vector3(50, 49, 8), Vector3(34, 42, 0), 55.0)
	await _vista("05_mar_metaverso", Vector3(0, 50, -96), Vector3(0, 44, -190), 50.0)
	await _vista("06_llegada_sur", Vector3(0, 49, 52), Vector3(0, 42, 0), 60.0)
	await _vista("07_archipielago", Vector3(270, 70, 270), Vector3(0, 34, 0), 55.0)
	await _vista("08_interior_acceso_sur", Vector3(0, 44.8, -19.0), Vector3(0, 43.6, 0), 74.0)
	await _vista("09_despacho_lucia", Vector3(7.8, 44.6, 9.0), Vector3(0, 43.2, 0), 55.0)
	await _vista("10_carrusel_avatares", Vector3(0, 45.0, 16.8), Vector3(0, 43.2, -2), 80.0)
	await _vista("11_portal_archipielago", Vector3(0, 45.0, 8.6), Vector3(0, 45.6, 18.2), 58.0)
	await _vista("12_cupula_oculo", Vector3(0, 42.8, 9.0), Vector3(0, 51.5, -1.5), 90.0)


func _vista(nombre: String, desde: Vector3, hacia: Vector3, fov: float) -> void:
	var cam := Camera3D.new()
	cam.name = "Cam_" + nombre
	cam.fov = fov
	cam.far = 3000.0
	add_child(cam)
	cam.global_position = desde
	cam.look_at(hacia, Vector3.UP)
	cam.current = true
	for i in 4:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var imagen := get_viewport().get_texture().get_image()
	var ruta := SALIDA + "/" + nombre + ".png"
	var error := imagen.save_png(ruta)
	_check(error == OK, "captura " + nombre, "error=%d" % error)
	cam.queue_free()


func _medir_mallas(nodo: Node, sangria: String = "") -> void:
	if nodo is MeshInstance3D and (nodo as MeshInstance3D).mesh != null:
		var caja: AABB = (nodo as MeshInstance3D).global_transform * (nodo as MeshInstance3D).mesh.get_aabb()
		if caja.size.y > 1.0:
			print("[PRUEBA] malla %s%s centro=%s tamanio=%s" % [sangria, nodo.name,
					caja.get_center(), caja.size])
	for hijo in nodo.get_children():
		_medir_mallas(hijo, sangria + "-")


func _validar_entorno() -> void:
	var mares := 0
	var islas := 0
	for hijo in get_children():
		if hijo.get_node_or_null("Oceano3D/Oceano") != null:
			mares += 1
		if hijo.get_node_or_null("ISLA3DCHUNK") != null:
			islas += 1
	_check(mares == 5, "1 mar por bloque (DAO + 4 islas)", "mares=%d" % mares)
	_check(islas == 4, "4 islas de jugador en cruz", "islas=%d" % islas)
	var mar := get_node_or_null("BloqueDAO/Oceano3D/Oceano") as MeshInstance3D
	if mar == null or mar.mesh == null:
		_check(false, "mar del metaverso en el bloque DAO")
		return
	var caja: AABB = mar.global_transform * mar.mesh.get_aabb()
	var superficie := caja.position.y + caja.size.y
	_check(absf(superficie - SUPERFICIE_MAR) < 0.6, "superficie del mar del metaverso",
			"y=%.2f" % superficie)


func _sondear_suelo() -> void:
	await get_tree().physics_frame
	await get_tree().physics_frame
	for radio in [36, 50, 60]:
		var puntos := [Vector2(0, -radio), Vector2(radio, 0), Vector2(0, radio), Vector2(-radio, 0)]
		var nombres := ["N", "E", "S", "O"]
		for i in puntos.size():
			var p: Vector2 = puntos[i]
			var altura := _altura_suelo(Vector3(p.x, 0, p.y))
			print("[PRUEBA] suelo r=%d %s y=%.2f" % [radio, nombres[i], altura])


func _altura_suelo(punto: Vector3) -> float:
	var espacio := get_world_3d().direct_space_state
	var consulta := PhysicsRayQueryParameters3D.create(
			Vector3(punto.x, 200, punto.z), Vector3(punto.x, -40, punto.z))
	var golpe := espacio.intersect_ray(consulta)
	return float(golpe["position"].y) if not golpe.is_empty() else NAN


func _check(ok: bool, titulo: String, detalle: String = "") -> void:
	if ok:
		print("[PRUEBA] OK   %s %s" % [titulo, detalle])
	else:
		_fallos.append(titulo)
		print("[PRUEBA] FALLO %s %s" % [titulo, detalle])
