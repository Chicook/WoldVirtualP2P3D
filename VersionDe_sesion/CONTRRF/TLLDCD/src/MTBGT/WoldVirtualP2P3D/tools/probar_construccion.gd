extends SceneTree
## Prueba headless del sistema de construccion: terreno editable, prims y
## registro en Construccion. No abre red: los RPC se validan solo por tipos.

const Terreno := preload("res://gdscrip/TerrenoEditable.gd")
const Prims := preload("res://gdscrip/Prims.gd")
const Construccion := preload("res://gdscrip/Construccion.gd")
const ESCENA_ISLA := "res://gltfimport/terrenoblok/ISLA3DCHUNK.gltf"

var _ok := 0
var _fallos := 0
var _contexto := ""


class StubChunk:
	extends Node3D
	var island_owners := {}
	var my_own_index := -1
	var _mi_uuid := ""


class AvatarFalso:
	extends CharacterBody3D
	var control_avatar := true


func _initialize() -> void:
	_correr()


func _correr() -> void:
	# El árbol debe estar activo para que los nodos tengan transform global.
	await process_frame
	_probar_terreno()
	_probar_prims()
	_probar_construccion()
	print("RESULTADO CONSTRUCCION: %d OK, %d FALLOS" % [_ok, _fallos])
	quit(0 if _fallos == 0 else 1)


func _check(condicion: bool, mensaje: String) -> void:
	if condicion:
		_ok += 1
	else:
		_fallos += 1
		push_error("[FALLO] %s -> %s" % [_contexto, mensaje])
		print("[FALLO] %s -> %s" % [_contexto, mensaje])


func _instancia_isla() -> Node3D:
	var packed := load(ESCENA_ISLA) as PackedScene
	var raiz := packed.instantiate() as Node3D
	root.add_child(raiz)
	return raiz


func _probar_terreno() -> void:
	_contexto = "terreno"
	var isla := _instancia_isla()
	var malla_original := isla.get_node("isla3D") as MeshInstance3D
	var cuerpo_original := malla_original.get_node("StaticBody3D") as StaticBody3D
	var col_original := cuerpo_original.get_node("CollisionShape3D") as CollisionShape3D
	var forma_original := col_original.shape
	var t := Terreno.new()
	_check(t.configurar(isla, 0), "configurar() acepta la malla de la isla")
	_check(t.vertices.size() > 1000, "la malla tiene vertices (%d)" % t.vertices.size())
	_check(t.indices.size() % 3 == 0, "los indices forman triangulos")
	_check(t.forma != null, "la colision trimesh quedo disponible")
	_check(t.forma != forma_original, "la colision se duplico por isla")
	_check(t.normales.size() == t.vertices.size(), "hay una normal por vertice")
	_check(t.material != null, "la malla conserva su material (%s)" % t.material)
	var ymax := -1e20
	for v in t.vertices:
		ymax = maxf(ymax, v.y)
	_check(ymax <= Terreno.ALTURA_MAX + 0.0001, "la malla base cabe en ALTURA_MAX")

	# Un vertice concreto se mueve al aplicar el pincel en su posicion mundial.
	var objetivo := t.vertices.size() / 2
	var antes := t.vertices[objetivo].y
	var mundo := t.malla.to_global(t.vertices[objetivo])
	var t0 := Time.get_ticks_usec()
	var afectados := t.aplicar_pincel(mundo, 6.0, 2.0, 0.05, 0)
	var ms := (Time.get_ticks_usec() - t0) / 1000.0
	print("[terreno] pincel: %d vertices afectados en %.2f ms" % [afectados, ms])
	_check(afectados > 0, "subir afecta a vertices cercanos")
	_check(t.vertices[objetivo].y > antes, "subir aumenta la altura del vertice")

	var tope := 0.0
	for i in 80:
		t.aplicar_pincel(mundo, 6.0, 4.0, 0.05, 0)
	for v in t.vertices:
		tope = maxf(tope, v.y)
	_check(tope <= Terreno.ALTURA_MAX + 0.0001, "subir no supera ALTURA_MAX (%.4f)" % tope)

	for i in 60:
		t.aplicar_pincel(mundo, 6.0, 4.0, 0.05, 1)
	var suelo := 1e20
	for v in t.vertices:
		suelo = minf(suelo, v.y)
	_check(suelo >= Terreno.ALTURA_MIN - 0.0001, "bajar no baja de ALTURA_MIN (%.4f)" % suelo)

	_check(t.aplicar_pincel(mundo, 6.0, 2.0, 0.05, 2) > 0, "suavizar modifica vertices")
	_check(t.aplicar_pincel(mundo, 6.0, 2.0, 0.05, 3) > 0, "aplanar modifica vertices")

	var t1 := Time.get_ticks_usec()
	t.actualizar_colision()
	var ms_col := (Time.get_ticks_usec() - t1) / 1000.0
	print("[terreno] colision: %d caras en %.2f ms" % [t.indices.size(), ms_col])
	_check(t.forma.get_faces().size() == t.indices.size(), "la colision copia todas las caras")
	var caras := t.forma.get_faces()
	_check(caras.size() > 0 and caras[0].is_equal_approx(t.vertices[t.indices[0]]),
			"la primera cara coincide con el vertice")

	var datos := t.serializar()
	print("[terreno] blob: %d bytes, zstd %d bytes" % [
		datos.size(), datos.compress(FileAccess.COMPRESSION_ZSTD).size()])
	_check(datos.size() == 18 + t.vertices.size() * 4, "el blob tiene cabecera y alturas")
	_check(datos.slice(0, 4).get_string_from_utf8() == "WVPT", "magia WVPT correcta")
	_check(datos.decode_u16(4) == Terreno.VERSION, "version del blob correcta")

	# Restaurar en otra malla independiente reproduce las mismas alturas.
	var isla2 := _instancia_isla()
	var t2 := Terreno.new()
	_check(t2.configurar(isla2, 1), "segunda isla configurada")
	_check(t2.cargar(datos), "cargar() acepta el blob guardado")
	var iguales := true
	for i in t.vertices.size():
		if absf(t2.vertices[i].y - t.vertices[i].y) > 0.0001:
			iguales = false
			break
	_check(iguales, "las alturas restauradas coinciden")
	_check(t2.forma.get_faces().size() == t2.indices.size(), "la colision restaurada esta completa")

	var malo := datos.duplicate()
	malo[0] = 65
	_check(not t2.cargar(malo), "rechaza magia desconocida")
	malo = datos.duplicate()
	malo.encode_u16(4, 99)
	_check(not t2.cargar(malo), "rechaza version desconocida")
	malo = datos.duplicate()
	malo.encode_u32(6, 5)
	_check(not t2.cargar(malo), "rechaza recuento distinto")
	malo = datos.duplicate()
	malo.encode_s64(10, datos.decode_s64(10) + 1)
	_check(not t2.cargar(malo), "rechaza geometria base distinta")
	_check(not t2.cargar(PackedByteArray()), "rechaza blob vacio")

	isla.queue_free()
	isla2.queue_free()


func _probar_prims() -> void:
	_contexto = "prims"
	for tipo in Prims.TIPOS:
		_check(Prims.crear_malla(tipo) != null, "malla de %s" % tipo)
		_check(Prims.crear_forma(tipo) != null, "colision de %s" % tipo)
		var tam := Prims.tamano_por_defecto(tipo)
		_check(tam.x > 0.0 and tam.y > 0.0 and tam.z > 0.0, "tamano por defecto de %s" % tipo)
	_check(Prims.crear_forma("toro") is ConcavePolygonShape3D, "el toro usa colision trimesh")

	var datos := {
		7: {
			"id": 7,
			"tipo": "cilindro",
			"pos": Vector3(1.5, 2.0, -3.0),
			"rot": Vector3(0.0, 45.0, 0.0),
			"escala": Vector3(1.4, 2.2, 1.4),
			"color": Color(0.28, 0.68, 0.95),
		},
	}
	var texto := Prims.serializar_isla(datos, 8, "UUID-PRUEBA")
	var leido := Prims.deserializar_isla(texto)
	_check(not leido.is_empty(), "JSON de prims legible")
	_check(int(leido["siguiente"]) == 8, "conserva el siguiente id")
	var p: Dictionary = leido["prims"][7]
	_check(p["tipo"] == "cilindro", "conserva el tipo")
	_check((p["pos"] as Vector3).is_equal_approx(Vector3(1.5, 2.0, -3.0)), "conserva la posicion")
	_check((p["escala"] as Vector3).is_equal_approx(Vector3(1.4, 2.2, 1.4)), "conserva la escala")
	_check((p["color"] as Color).to_html(true) == Color(0.28, 0.68, 0.95).to_html(true),
			"conserva el color")
	_check(Prims.deserializar_isla("[1, 2, 3]").is_empty(), "rechaza JSON que no es objeto")
	_check(Prims.deserializar_isla('{"version": 2, "prims": []}').is_empty(),
			"rechaza version desconocida")
	var con_id_malo := Prims.deserializar_isla(
			'{"version": 1, "siguiente": 1, "prims": [{"id": 0, "tipo": "cubo"}]}')
	_check(con_id_malo["prims"].is_empty(), "descarta ids no positivos")


func _probar_construccion() -> void:
	_contexto = "construccion"
	var stub := StubChunk.new()
	stub.name = "StubChunk"
	root.add_child(stub)
	var avatar := AvatarFalso.new()
	avatar.name = "USERBASE"
	stub.add_child(avatar)
	stub.island_owners = {99: [1, "Prueba", "UUID-PRUEBA"]}
	stub.my_own_index = 99
	stub._mi_uuid = "UUID-PRUEBA"

	var c := Construccion.new()
	c.name = "Constructor"
	stub.add_child(c)
	_check(c._panel != null, "_ready construye el panel")

	var isla := _instancia_isla()
	isla.get_parent().remove_child(isla)
	stub.add_child(isla)
	c.registrar_isla(99, isla)
	_check(c._terrenos.has(99), "la isla queda registrada con terreno")
	_check(c._contenedores.has(99), "la isla tiene contenedor de objetos")
	_check(c._prims.has(99) and c._prims[99].is_empty(), "empieza sin objetos")

	var id: int = c._host_crear_prim(99, "cilindro", Vector3(1.0, 2.0, 3.0),
			Vector3(0.0, 45.0, 0.0), Vector3(1.4, 2.2, 1.4), Color(0.28, 0.68, 0.95))
	_check(id == 1, "el primer prim recibe id 1")
	_check(c._prims[99].has(1), "el prim queda en el registro")
	_check(c._nodos[99].has(1), "el prim se instancia en la isla")
	var nodo: Node3D = c._nodos[99][1]
	_check(nodo.position.is_equal_approx(Vector3(1.0, 2.0, 3.0)), "posicion aplicada al nodo")
	_check(nodo.scale.is_equal_approx(Vector3(1.4, 2.2, 1.4)), "escala aplicada al nodo")
	_check(nodo.get_node_or_null("Malla") is MeshInstance3D, "el prim tiene malla")
	_check(nodo.get_node_or_null("Colision") is CollisionShape3D, "el prim tiene colision")

	# Simula el aviso del anfitrion con un id creado por otro peer.
	c._siguiente[99] = 1
	c._prim_creado(99, 5, "cubo", Vector3.ZERO, Vector3.ZERO, Vector3.ONE, Color.WHITE)
	_check(int(c._siguiente[99]) == 6, "el contador avanza con ids remotos")
	_check(c._prims[99].has(5), "un prim remoto se instancia")
	c._prim_borrado(99, 5)

	c._seleccionar(nodo)
	_check(c._sel_id == 1 and c._sel_isla == 99, "seleccionar fija isla e id")
	_check(c._puedo_editar(99), "la isla propia se puede editar")
	_check(not c._puedo_editar(123), "una isla desconocida no se puede editar")
	_check(is_equal_approx(c._panel.escala_objetivo(), 2.2), "el panel muestra el tamano real")

	c._aplicar_escala(4.4)
	var esc: Vector3 = c._prims[99][1]["escala"]
	_check(esc.is_equal_approx(Vector3(2.8, 4.4, 2.8)), "escalar conserva la proporcion")

	var antes_x: float = c._prims[99][1]["pos"].x
	c._mover_seleccion(KEY_RIGHT, false)
	_check(is_equal_approx(c._prims[99][1]["pos"].x, antes_x + 0.5), "mover desplaza con la rejilla")

	c._aplicar_color(Color(0.93, 0.32, 0.31))
	_check((c._prims[99][1]["color"] as Color).to_html(true) == Color(0.93, 0.32, 0.31).to_html(true),
			"el color se aplica al prim")

	var serializado := Prims.serializar_isla(c._prims[99], int(c._siguiente[99]), "UUID-PRUEBA")
	var releido := Prims.deserializar_isla(serializado)
	_check(int(releido["siguiente"]) == int(c._siguiente[99]), "el estado guardado conserva el contador")
	_check(releido["prims"].has(1), "el estado guardado incluye el prim")

	c._borrar()
	_check(not c._prims[99].has(1), "borrar elimina el prim del registro")
	_check(not c._nodos[99].has(1), "borrar elimina el nodo")

	c._bloquear_avatar(true)
	_check(avatar.get_meta("construccion_activa", false), "el modo construccion marca al avatar")
	_check(not avatar.control_avatar, "el avatar suelto no responde a flechas")
	c._bloquear_avatar(false)
	_check(not avatar.get_meta("construccion_activa", true), "al salir se retira la marca")

	_check(c._validar_remitente(99, root.multiplayer.get_unique_id()), "el anfitrion puede editar")
	_check(not c._validar_remitente(99, 777), "un peer ajeno no puede editar")
	_check(not c._validar_remitente(123, 777), "una isla desconocida se rechaza")

	c._refrescar_estado_ui()
	_check(c._isla_actual() == 99, "_isla_actual usa my_own_index")

	c._sucio.clear()
	stub.free()
