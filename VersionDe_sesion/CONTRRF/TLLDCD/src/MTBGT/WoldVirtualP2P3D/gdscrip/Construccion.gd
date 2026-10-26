extends Node3D
## Sistema de construcción del metaverso: esculpido del terreno de la isla y
## rezado/edición de prims (cubo, esfera, cilindro, cono, toro).
##
## Todo el estado viaja por el mismo WebSocketMultiplayerPeer (8911) que el
## Visor C# publica a través de su túnel HTTP; no se abre ningún canal nuevo.
## El anfitrión valida la propiedad de la isla y difunde los cambios.

const Terreno := preload("res://gdscrip/TerrenoEditable.gd")
const Prims := preload("res://gdscrip/Prims.gd")
const PanelConstruccion := preload("res://gdscrip/ConstructorPanel.gd")

const CARPETA := "user://construccion"
const TIPO_TERRENO := 0
const TIPO_PRIMS := 1
const BLOQUE_BYTES := 6000
const RADIO_ISLA := 95.0
const PASO_PINCEL := 0.05

enum Herramienta { SELECCION, SUBIR, BAJAR, SUAVIZAR, APLANAR, MOVER, PLAYA }

var _panel = null
var _islas := {}          # indice -> Node3D de la isla
var _terrenos := {}       # indice -> TerrenoEditable
var _contenedores := {}   # indice -> Node3D "Construccion"
var _prims := {}          # indice -> {id: datos}
var _nodos := {}          # indice -> {id: StaticBody3D}
var _siguiente := {}      # indice -> siguiente id
var _seleccionado: Node3D = null
var _sel_isla := -1
var _sel_id := -1
var _modo := false
var _herramienta := Herramienta.SELECCION
var _radio := 8.0
var _fuerza := 1.2
var _snap := true
var _color_actual: Color = Prims.COLORES[0]
var _pincelando := false
var _pincel_isla := -1
var _ultimo_impacto := Vector3.ZERO
var _impacto_previo := Vector3.ZERO
var _mira: MeshInstance3D = null
var _resalte: MeshInstance3D = null
var _recibiendo := {}
var _sucio := {}
var _colision_pendiente := {}
var _guardar_t := 0.0
var _col_t := 0.0
var _ui_t := 0.0
var _mira_t := 0.0
var _pincel_t := 0.0
var _ultimo_envio_ms := 0
var _ultimo_aviso := ""


func _ready() -> void:
	_panel = PanelConstruccion.new()
	_panel.name = "PanelConstruccion"
	add_child(_panel)
	_panel.alternar_solicitado.connect(_alternar_modo)
	_panel.salir_solicitado.connect(func(): _activar_modo(false))
	_panel.herramienta_cambiada.connect(_on_herramienta)
	_panel.radio_cambiada.connect(func(v): _radio = v)
	_panel.fuerza_cambiada.connect(func(v): _fuerza = v)
	_panel.snap_cambiada.connect(func(v): _snap = v)
	_panel.rez_solicitado.connect(_rez)
	_panel.duplicar_solicitado.connect(_duplicar)
	_panel.borrar_solicitado.connect(_borrar)
	_panel.color_solicitado.connect(_aplicar_color)
	_panel.escala_solicitada.connect(_aplicar_escala)
	_crear_mira()
	set_process(true)


func _exit_tree() -> void:
	_guardar_sucios()


# ---------------------------------------------------------------- registro

## Lo llama ChunkManager al crear cada isla (en todos los peers).
func registrar_isla(idx: int, nodo_isla: Node3D) -> void:
	if nodo_isla == null or _islas.has(idx):
		return
	# Un mismo nodo no puede representar dos islas: compartiría terreno y
	# colisión, y esculpir una modificaría la otra.
	for otro in _islas:
		if _islas[otro] == nodo_isla:
			push_warning("[Construccion] La isla %d ya estaba registrada como %s" % [idx, str(otro)])
			return
	_islas[idx] = nodo_isla
	var terreno := Terreno.new()
	if terreno.configurar(nodo_isla, idx):
		_terrenos[idx] = terreno
		if terreno.cuerpo != null:
			terreno.cuerpo.set_meta("isla", idx)
			terreno.cuerpo.set_meta("terreno_editable", true)
		print("[Construccion] Isla ", idx, " preparada: ", terreno.vertices.size(), " vértices")
	var contenedor := Node3D.new()
	contenedor.name = "Construccion"
	nodo_isla.add_child(contenedor)
	_contenedores[idx] = contenedor
	_prims[idx] = {}
	_nodos[idx] = {}
	_siguiente[idx] = 1

	var cargado := false
	if multiplayer.is_server() or _es_mi_isla(idx):
		cargado = _cargar_disco(idx)
	if not multiplayer.is_server():
		if cargado and _es_mi_isla(idx):
			_aportar_estado(idx)
		rpc_id(1, "_pedir_estado", idx)


func _cargar_disco(idx: int) -> bool:
	var cargado := false
	var terreno = _terrenos.get(idx)
	var ruta_t := _ruta_terreno(idx)
	if terreno != null and FileAccess.file_exists(ruta_t):
		var f := FileAccess.open(ruta_t, FileAccess.READ)
		if f != null:
			var datos := f.get_buffer(f.get_length())
			f.close()
			cargado = terreno.cargar(datos) or cargado
	var ruta_p := _ruta_prims(idx)
	if FileAccess.file_exists(ruta_p):
		var f2 := FileAccess.open(ruta_p, FileAccess.READ)
		if f2 != null:
			var texto := f2.get_as_text()
			f2.close()
			var leido := Prims.deserializar_isla(texto)
			if not leido.is_empty():
				_prims[idx] = leido["prims"]
				_siguiente[idx] = int(leido["siguiente"])
				for id in _prims[idx]:
					_instanciar_prim(idx, _prims[idx][id])
				cargado = true
	return cargado


func _guardar_isla(idx: int) -> bool:
	if not _puede_guardar(idx):
		return false
	_asegurar_carpeta()
	var terreno = _terrenos.get(idx)
	if terreno != null:
		var f := FileAccess.open(_ruta_terreno(idx), FileAccess.WRITE)
		if f != null:
			f.store_buffer(terreno.serializar())
			f.close()
	var texto := Prims.serializar_isla(_prims.get(idx, {}), int(_siguiente.get(idx, 1)), _uuid_dueno(idx))
	var f2 := FileAccess.open(_ruta_prims(idx), FileAccess.WRITE)
	if f2 != null:
		f2.store_string(texto)
		f2.close()
	return true


## Guarda solo lo que este peer puede escribir. Un cliente conserva sucio lo
## de otras islas para que, si asume como anfitrión, no se pierda el estado.
func _guardar_sucios() -> void:
	for idx in _sucio.keys():
		if _guardar_isla(int(idx)):
			_sucio.erase(idx)


func _asegurar_carpeta() -> void:
	var dir := DirAccess.open("user://")
	if dir != null:
		dir.make_dir_recursive("construccion")


func _ruta_terreno(idx: int) -> String:
	return CARPETA.path_join("terreno_%d_%s.bin" % [idx, _clave_dueno(idx)])


func _ruta_prims(idx: int) -> String:
	return CARPETA.path_join("prims_%d_%s.json" % [idx, _clave_dueno(idx)])


func _clave_dueno(idx: int) -> String:
	var uuid := _uuid_dueno(idx)
	return uuid if uuid != "" else "local"


func _uuid_dueno(idx: int) -> String:
	var cm := get_parent()
	if cm == null:
		return ""
	var owners = cm.get("island_owners")
	if owners is Dictionary and owners.has(idx):
		var dato = owners[idx]
		if dato is Array and dato.size() > 2:
			return str(dato[2])
	return ""


func _mi_uuid() -> String:
	var cm := get_parent()
	if cm == null:
		return ""
	var valor = cm.get("_mi_uuid")
	return str(valor) if valor != null else ""


func _es_mi_isla(idx: int) -> bool:
	var cm := get_parent()
	if cm == null or idx < 0:
		return false
	var propio = cm.get("my_own_index")
	if propio != null and int(propio) == idx:
		return true
	var dueno := _uuid_dueno(idx)
	return dueno != "" and dueno == _mi_uuid()


func _puede_guardar(idx: int) -> bool:
	return multiplayer.is_server() or _es_mi_isla(idx)


## Edición local permitida: es tu isla por índice/UUID o eres el peer que la
## tiene asignada en este momento (islas aún sin registrar).
func _puedo_editar(idx: int) -> bool:
	if idx < 0 or not _islas.has(idx):
		return false
	if _es_mi_isla(idx):
		return true
	var cm := get_parent()
	if cm == null:
		return false
	var owners = cm.get("island_owners")
	if owners is Dictionary and owners.has(idx):
		var dato = owners[idx]
		if dato is Array and dato.size() > 0:
			return int(dato[0]) == multiplayer.get_unique_id()
	return false


## Un cambio remoto solo vale si lo firma el dueño actual de esa isla. No hay
## excepción para el propio id ni para remitentes sin identificar: así ningún
## peer puede esculpir el terreno de otro aunque manipule el RPC.
func _validar_remitente(idx: int, remitente: int) -> bool:
	if remitente <= 0 or idx < 0:
		return false
	var cm := get_parent()
	if cm == null:
		return false
	var owners = cm.get("island_owners")
	if owners is Dictionary and owners.has(idx):
		var dato = owners[idx]
		if dato is Array and dato.size() > 0:
			return int(dato[0]) == remitente
	return false


# ------------------------------------------------------------------- modo

func _alternar_modo() -> void:
	_activar_modo(not _modo)


func _activar_modo(activo: bool) -> void:
	_modo = activo
	_pincelando = false
	_pincel_isla = -1
	_panel.abrir(activo)
	_bloquear_avatar(activo)
	if not activo:
		_seleccionar(null)
		if _mira != null:
			_mira.visible = false
	else:
		_avisar("Modo construcción activo. El avatar queda suelto hasta cerrar (B).")


func _bloquear_avatar(activo: bool) -> void:
	var ub := get_parent().get_node_or_null("USERBASE") if get_parent() != null else null
	if ub == null:
		return
	ub.set_meta("construccion_activa", activo)
	# Al cerrar el modo se devuelve el control sin exigir otro clic.
	if "control_avatar" in ub:
		ub.set("control_avatar", not activo)
	if ub is CharacterBody3D:
		var cuerpo := ub as CharacterBody3D
		cuerpo.velocity.x = 0.0
		cuerpo.velocity.z = 0.0
	if activo:
		for accion in ["ui_left", "ui_right", "ui_up", "ui_down", "ui_accept"]:
			Input.action_release(accion)


func _on_herramienta(indice: int) -> void:
	_herramienta = indice
	if indice != Herramienta.SELECCION:
		_seleccionar(null)


# ------------------------------------------------------------------ entrada

func _unhandled_input(event: InputEvent) -> void:
	if not _modo:
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			if _herramienta == Herramienta.SELECCION:
				_seleccionar_bajo_raton()
			else:
				_iniciar_pincel()
		elif _pincelando:
			_terminar_pincel()


func _unhandled_key_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed:
		return
	if not event.echo and event.keycode == KEY_B:
		_alternar_modo()
		get_viewport().set_input_as_handled()
		return
	if not _modo:
		return
	# Ctrl se reserva para atajos (Ctrl+D duplica); sin esto, el movimiento
	# también reaccionaría a las teclas con Ctrl pulsado.
	if event.ctrl_pressed:
		if not event.echo and event.keycode == KEY_D:
			_duplicar()
			get_viewport().set_input_as_handled()
		return
	if not event.echo:
		match event.keycode:
			KEY_ESCAPE:
				if _seleccionado != null:
					_seleccionar(null)
				else:
					_activar_modo(false)
				get_viewport().set_input_as_handled()
				return
			KEY_DELETE:
				_borrar()
				get_viewport().set_input_as_handled()
				return
	if _seleccionado == null:
		return
	if _tecla_edicion(event.keycode):
		_mover_seleccion(event.keycode, event.shift_pressed)
		get_viewport().set_input_as_handled()


func _tecla_edicion(codigo: int) -> bool:
	return codigo in [
		KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN,
		KEY_W, KEY_A, KEY_S, KEY_D, KEY_Q, KEY_E,
		KEY_PAGEUP, KEY_PAGEDOWN,
		KEY_PLUS, KEY_EQUAL, KEY_MINUS, KEY_KP_ADD, KEY_KP_SUBTRACT,
	]


func _mover_seleccion(codigo: int, rapido: bool) -> void:
	if _seleccionado == null or not is_instance_valid(_seleccionado):
		return
	var datos: Dictionary = _prims[_sel_isla].get(_sel_id, {})
	if datos.is_empty():
		return
	var nodo := _seleccionado
	var pos: Vector3 = datos["pos"]
	var rot: Vector3 = datos["rot"]
	var esc: Vector3 = datos["escala"]
	var paso := 1.0 if rapido else (0.5 if _snap else 0.25)
	match codigo:
		KEY_LEFT, KEY_A:
			pos.x -= paso
		KEY_RIGHT, KEY_D:
			pos.x += paso
		KEY_UP, KEY_W:
			pos.z -= paso
		KEY_DOWN, KEY_S:
			pos.z += paso
		KEY_PAGEUP:
			pos.y += paso
		KEY_PAGEDOWN:
			pos.y = maxf(0.0, pos.y - paso)
		KEY_Q:
			rot.y = snappedf(rot.y - 15.0, 15.0)
		KEY_E:
			rot.y = snappedf(rot.y + 15.0, 15.0)
		KEY_PLUS, KEY_EQUAL, KEY_KP_ADD:
			esc = (esc * 1.08).clamp(Vector3(0.15, 0.15, 0.15), Vector3(40.0, 40.0, 40.0))
			_panel.set_escala_ui(_mayor_escala(esc))
		KEY_MINUS, KEY_KP_SUBTRACT:
			esc = (esc / 1.08).clamp(Vector3(0.15, 0.15, 0.15), Vector3(40.0, 40.0, 40.0))
			_panel.set_escala_ui(_mayor_escala(esc))
		_:
			return
	pos.x = clampf(pos.x, -RADIO_ISLA, RADIO_ISLA)
	pos.z = clampf(pos.z, -RADIO_ISLA, RADIO_ISLA)
	pos.y = clampf(pos.y, 0.0, 140.0)
	datos["pos"] = pos
	datos["rot"] = rot
	datos["escala"] = esc
	_aplicar_datos_prim(_sel_isla, _sel_id, datos)
	_envio_prim_throttled()


# ------------------------------------------------------------------ terreno

func _iniciar_pincel() -> void:
	var hit := _rayo_raton()
	if hit.is_empty():
		_avisar("Apunta a una superficie de la isla para esculpir.")
		return
	var idx := _isla_del_impacto(hit)
	if idx < 0 or not _puedo_editar(idx):
		_avisar("Solo puedes editar el terreno de tu propia isla.")
		return
	_pincelando = true
	_pincel_isla = idx
	_ultimo_impacto = hit["position"]
	_impacto_previo = _ultimo_impacto
	_pincel_t = 0.0
	_tick_pincel()


func _tick_pincel() -> void:
	if not _pincelando or _pincel_isla < 0:
		return
	var terreno = _terrenos.get(_pincel_isla)
	if terreno == null:
		_pincelando = false
		return
	var hit := _rayo_raton()
	if not hit.is_empty():
		_ultimo_impacto = hit["position"]
	var herramienta_terreno := _herramienta - 1
	var delta := Vector3.ZERO
	if herramienta_terreno == Terreno.MOVER:
		delta = _ultimo_impacto - _impacto_previo
		delta.y = 0.0
		var largo := delta.length()
		var tope := maxf(2.0, _radio * 0.5)
		if largo > tope:
			delta = delta / largo * tope
	_impacto_previo = _ultimo_impacto
	var afectados: int = terreno.aplicar_pincel(_ultimo_impacto, _radio, _fuerza, PASO_PINCEL,
			herramienta_terreno, delta)
	if afectados <= 0:
		return
	_colision_pendiente[_pincel_isla] = true
	_sucio[_pincel_isla] = true
	_col_t = 0.0
	if multiplayer.is_server():
		_difundir_pincel(_pincel_isla, _ultimo_impacto, _radio, _fuerza, PASO_PINCEL,
				herramienta_terreno, delta)
	else:
		rpc_id(1, "_solicitar_pincel", _pincel_isla, _ultimo_impacto, _radio, _fuerza,
				PASO_PINCEL, herramienta_terreno, delta)


func _terminar_pincel() -> void:
	_pincelando = false
	if _pincel_isla >= 0:
		var terreno = _terrenos.get(_pincel_isla)
		if terreno != null:
			terreno.actualizar_colision()
		_colision_pendiente.erase(_pincel_isla)
		if _guardar_isla(_pincel_isla):
			_sucio.erase(_pincel_isla)
	_pincel_isla = -1


func _difundir_pincel(idx: int, centro: Vector3, radio: float, fuerza: float, dt: float,
		herramienta: int, delta: Vector3) -> void:
	if multiplayer.get_peers().is_empty():
		return
	rpc("_pincel_remoto", idx, centro, radio, fuerza, dt, herramienta, delta)


@rpc("any_peer", "call_remote", "reliable")
func _solicitar_pincel(idx: int, centro: Vector3, radio: float, fuerza: float, dt: float,
		herramienta: int, delta: Vector3) -> void:
	if not multiplayer.is_server():
		return
	var remitente := multiplayer.get_remote_sender_id()
	if not _validar_remitente(idx, remitente):
		_avisar_remoto(remitente, "No puedes esculpir el terreno de otra isla.")
		return
	var terreno = _terrenos.get(idx)
	if terreno == null:
		return
	terreno.aplicar_pincel(centro, radio, fuerza, dt, herramienta, delta)
	_colision_pendiente[idx] = true
	_sucio[idx] = true
	_col_t = 0.0
	for peer in multiplayer.get_peers():
		if peer != remitente:
			rpc_id(peer, "_pincel_remoto", idx, centro, radio, fuerza, dt, herramienta, delta)


@rpc("authority", "call_remote", "reliable")
func _pincel_remoto(idx: int, centro: Vector3, radio: float, fuerza: float, dt: float,
		herramienta: int, delta: Vector3) -> void:
	var terreno = _terrenos.get(idx)
	if terreno == null:
		return
	terreno.aplicar_pincel(centro, radio, fuerza, dt, herramienta, delta)
	_colision_pendiente[idx] = true
	_sucio[idx] = true
	_col_t = 0.0


# -------------------------------------------------------------------- prims

func _rez(tipo: String) -> void:
	var hit := _rayo_raton()
	if hit.is_empty():
		_avisar("Apunta a una superficie para colocar el objeto.")
		return
	var idx := _isla_del_impacto(hit)
	if idx < 0 or not _puedo_editar(idx):
		_avisar("Solo puedes construir en tu propia isla.")
		return
	var isla_nodo: Node3D = _islas[idx]
	var pos := isla_nodo.to_local(hit["position"] as Vector3)
	var tam := Prims.tamano_por_defecto(tipo)
	pos.y += tam.y * 0.5
	if _snap:
		pos = Vector3(snappedf(pos.x, 0.5), pos.y, snappedf(pos.z, 0.5))
	pos.x = clampf(pos.x, -RADIO_ISLA, RADIO_ISLA)
	pos.z = clampf(pos.z, -RADIO_ISLA, RADIO_ISLA)
	var rot := Vector3(0.0, _giro_camara(), 0.0)
	_rez_con_datos(idx, tipo, pos, rot, tam, _color_actual)


func _rez_con_datos(idx: int, tipo: String, pos: Vector3, rot: Vector3, esc: Vector3, color: Color) -> void:
	if multiplayer.is_server():
		var id := _host_crear_prim(idx, tipo, pos, rot, esc, color)
		_difundir_prim_creado(idx, id)
	else:
		rpc_id(1, "_solicitar_rez", idx, tipo, pos, rot, esc, color)


func _host_crear_prim(idx: int, tipo: String, pos: Vector3, rot: Vector3, esc: Vector3, color: Color) -> int:
	if not _prims.has(idx):
		return 0
	var id := int(_siguiente.get(idx, 1))
	_siguiente[idx] = id + 1
	var datos := {
		"id": id,
		"tipo": tipo if Prims.TIPOS.has(tipo) else "cubo",
		"pos": pos,
		"rot": rot,
		"escala": esc.clamp(Vector3(0.15, 0.15, 0.15), Vector3(40.0, 40.0, 40.0)),
		"color": color,
	}
	_prims[idx][id] = datos
	_instanciar_prim(idx, datos)
	_sucio[idx] = true
	return id


func _difundir_prim_creado(idx: int, id: int) -> void:
	if id <= 0 or multiplayer.get_peers().is_empty():
		return
	var d: Dictionary = _prims[idx][id]
	rpc("_prim_creado", idx, id, d["tipo"], d["pos"], d["rot"], d["escala"], d["color"])


@rpc("any_peer", "call_remote", "reliable")
func _solicitar_rez(idx: int, tipo: String, pos: Vector3, rot: Vector3, esc: Vector3, color: Color) -> void:
	if not multiplayer.is_server():
		return
	var remitente := multiplayer.get_remote_sender_id()
	if not _validar_remitente(idx, remitente):
		_avisar_remoto(remitente, "No puedes construir en otra isla.")
		return
	var id := _host_crear_prim(idx, tipo, pos, rot, esc, color)
	if id > 0 and not multiplayer.get_peers().is_empty():
		rpc("_prim_creado", idx, id, tipo, pos, rot, esc, color)


@rpc("authority", "call_remote", "reliable")
func _prim_creado(idx: int, id: int, tipo: String, pos: Vector3, rot: Vector3, esc: Vector3, color: Color) -> void:
	if not _prims.has(idx) or _prims[idx].has(id):
		return
	var datos := {"id": id, "tipo": tipo, "pos": pos, "rot": rot, "escala": esc, "color": color}
	_prims[idx][id] = datos
	# El contador del cliente también avanza para no reutilizar ids al guardar.
	_siguiente[idx] = maxi(int(_siguiente.get(idx, 1)), id + 1)
	_instanciar_prim(idx, datos)
	_sucio[idx] = true


func _instanciar_prim(idx: int, datos: Dictionary) -> void:
	var contenedor: Node3D = _contenedores.get(idx)
	if contenedor == null or datos.is_empty():
		return
	var id := int(datos["id"])
	var cuerpo := StaticBody3D.new()
	cuerpo.name = "Prim_%d" % id
	cuerpo.set_meta("isla", idx)
	cuerpo.set_meta("prim_id", id)
	var malla := MeshInstance3D.new()
	malla.name = "Malla"
	malla.mesh = Prims.crear_malla(str(datos["tipo"]))
	malla.material_override = Prims.crear_material(datos["color"])
	cuerpo.add_child(malla)
	var colision := CollisionShape3D.new()
	colision.name = "Colision"
	colision.shape = Prims.crear_forma(str(datos["tipo"]))
	cuerpo.add_child(colision)
	_posicionar_prim(cuerpo, datos)
	contenedor.add_child(cuerpo)
	_nodos[idx][id] = cuerpo


func _posicionar_prim(nodo: Node3D, datos: Dictionary) -> void:
	nodo.position = datos["pos"]
	nodo.rotation_degrees = datos["rot"]
	nodo.scale = datos["escala"]


func _aplicar_datos_prim(idx: int, id: int, datos: Dictionary) -> void:
	var nodo: Node3D = _nodos.get(idx, {}).get(id)
	if nodo == null or not is_instance_valid(nodo):
		return
	_posicionar_prim(nodo, datos)
	var malla := nodo.get_node_or_null("Malla") as MeshInstance3D
	if malla != null:
		var mat := malla.material_override as StandardMaterial3D
		if mat == null:
			malla.material_override = Prims.crear_material(datos["color"])
		else:
			mat.albedo_color = datos["color"]
	if _seleccionado == nodo:
		_actualizar_texto_seleccion()


func _envio_prim_throttled() -> void:
	var ahora := Time.get_ticks_msec()
	if ahora - _ultimo_envio_ms < 90:
		return
	_ultimo_envio_ms = ahora
	_enviar_prim_actual(_sel_isla, _sel_id)


func _enviar_prim_actual(idx: int, id: int) -> void:
	var datos: Dictionary = _prims.get(idx, {}).get(id, {})
	if datos.is_empty():
		return
	if multiplayer.is_server():
		_difundir_prim_actual(idx, id)
	else:
		rpc_id(1, "_solicitar_prim", idx, id, datos["pos"], datos["rot"], datos["escala"], datos["color"])


func _difundir_prim_actual(idx: int, id: int) -> void:
	if multiplayer.get_peers().is_empty():
		return
	var d: Dictionary = _prims[idx][id]
	rpc("_prim_actualizado", idx, id, d["pos"], d["rot"], d["escala"], d["color"])


@rpc("any_peer", "call_remote", "reliable")
func _solicitar_prim(idx: int, id: int, pos: Vector3, rot: Vector3, esc: Vector3, color: Color) -> void:
	if not multiplayer.is_server():
		return
	var remitente := multiplayer.get_remote_sender_id()
	if not _validar_remitente(idx, remitente):
		_avisar_remoto(remitente, "No puedes editar objetos de otra isla.")
		return
	if not _aplicar_cambio_red(idx, id, pos, rot, esc, color):
		return
	for peer in multiplayer.get_peers():
		if peer != remitente:
			rpc_id(peer, "_prim_actualizado", idx, id, pos, rot, esc, color)


@rpc("authority", "call_remote", "reliable")
func _prim_actualizado(idx: int, id: int, pos: Vector3, rot: Vector3, esc: Vector3, color: Color) -> void:
	_aplicar_cambio_red(idx, id, pos, rot, esc, color)


func _aplicar_cambio_red(idx: int, id: int, pos: Vector3, rot: Vector3, esc: Vector3, color: Color) -> bool:
	var datos: Dictionary = _prims.get(idx, {}).get(id, {})
	if datos.is_empty():
		return false
	datos["pos"] = pos
	datos["rot"] = rot
	datos["escala"] = esc
	datos["color"] = color
	_prims[idx][id] = datos
	_aplicar_datos_prim(idx, id, datos)
	_sucio[idx] = true
	return true


func _borrar() -> void:
	if _seleccionado == null or _sel_isla < 0 or _sel_id <= 0:
		return
	_solicitar_borrado(_sel_isla, _sel_id)


func _solicitar_borrado(idx: int, id: int) -> void:
	if multiplayer.is_server():
		if _host_borrar_prim(idx, id):
			_difundir_prim_borrado(idx, id)
	else:
		rpc_id(1, "_solicitar_borrar", idx, id)


@rpc("any_peer", "call_remote", "reliable")
func _solicitar_borrar(idx: int, id: int) -> void:
	if not multiplayer.is_server():
		return
	var remitente := multiplayer.get_remote_sender_id()
	if not _validar_remitente(idx, remitente):
		_avisar_remoto(remitente, "No puedes borrar objetos de otra isla.")
		return
	if _host_borrar_prim(idx, id) and not multiplayer.get_peers().is_empty():
		rpc("_prim_borrado", idx, id)


func _host_borrar_prim(idx: int, id: int) -> bool:
	var datos = _prims.get(idx, {}).get(id)
	if datos == null:
		return false
	if _seleccionado != null and _sel_isla == idx and _sel_id == id:
		_seleccionar(null)
	var nodo = _nodos.get(idx, {}).get(id)
	if nodo != null and is_instance_valid(nodo):
		nodo.queue_free()
	_nodos.get(idx, {}).erase(id)
	_prims.get(idx, {}).erase(id)
	_sucio[idx] = true
	return true


@rpc("authority", "call_remote", "reliable")
func _prim_borrado(idx: int, id: int) -> void:
	if _seleccionado != null and _sel_isla == idx and _sel_id == id:
		_seleccionar(null)
	var nodo = _nodos.get(idx, {}).get(id)
	if nodo != null and is_instance_valid(nodo):
		nodo.queue_free()
	_nodos.get(idx, {}).erase(id)
	_prims.get(idx, {}).erase(id)
	_sucio[idx] = true


func _difundir_prim_borrado(idx: int, id: int) -> void:
	if multiplayer.get_peers().is_empty():
		return
	rpc("_prim_borrado", idx, id)


func _duplicar() -> void:
	if _seleccionado == null or _sel_id <= 0:
		_avisar("Selecciona un objeto para duplicarlo.")
		return
	var datos: Dictionary = _prims[_sel_isla].get(_sel_id, {})
	if datos.is_empty():
		return
	var pos: Vector3 = datos["pos"] + Vector3(1.0, 0.0, 1.0)
	pos.x = clampf(pos.x, -RADIO_ISLA, RADIO_ISLA)
	pos.z = clampf(pos.z, -RADIO_ISLA, RADIO_ISLA)
	_rez_con_datos(_sel_isla, str(datos["tipo"]), pos, datos["rot"], datos["escala"], datos["color"])


func _aplicar_color(color: Color) -> void:
	_color_actual = color
	if _seleccionado == null:
		return
	var datos: Dictionary = _prims[_sel_isla].get(_sel_id, {})
	if datos.is_empty():
		return
	datos["color"] = color
	_aplicar_datos_prim(_sel_isla, _sel_id, datos)
	_enviar_prim_actual(_sel_isla, _sel_id)


func _aplicar_escala(valor: float) -> void:
	if _seleccionado == null:
		return
	var datos: Dictionary = _prims[_sel_isla].get(_sel_id, {})
	if datos.is_empty():
		return
	# Se conserva la proporción original: un cilindro deja de serlo si se
	# fuerza la misma escala en los tres ejes.
	var actual: Vector3 = datos["escala"]
	var mayor := _mayor_escala(actual)
	datos["escala"] = (actual * (valor / mayor) if mayor > 0.001
			else Vector3(valor, valor, valor)).clamp(
			Vector3(0.15, 0.15, 0.15), Vector3(40.0, 40.0, 40.0))
	_aplicar_datos_prim(_sel_isla, _sel_id, datos)
	_enviar_prim_actual(_sel_isla, _sel_id)


func _mayor_escala(esc: Vector3) -> float:
	return maxf(esc.x, maxf(esc.y, esc.z))


# ---------------------------------------------------------------- seleccion

func _seleccionar_bajo_raton() -> void:
	var hit := _rayo_raton()
	if hit.is_empty():
		_seleccionar(null)
		return
	var collider = hit.get("collider")
	if collider is Node and (collider as Node).has_meta("prim_id"):
		var idx := int((collider as Node).get_meta("isla"))
		if not _puedo_editar(idx):
			_avisar("Solo puedes editar objetos de tu propia isla.")
			_seleccionar(null)
			return
		_seleccionar(collider)
	else:
		_seleccionar(null)


func _seleccionar(nodo) -> void:
	if _resalte != null and is_instance_valid(_resalte):
		_resalte.queue_free()
	_resalte = null
	if nodo == null or not is_instance_valid(nodo) or not nodo.has_meta("prim_id"):
		_seleccionado = null
		_sel_isla = -1
		_sel_id = -1
		_panel.set_seleccion("Selección: —")
		return
	_seleccionado = nodo
	_sel_isla = int(nodo.get_meta("isla"))
	_sel_id = int(nodo.get_meta("prim_id"))
	var datos: Dictionary = _prims.get(_sel_isla, {}).get(_sel_id, {})
	_actualizar_texto_seleccion()
	if not datos.is_empty():
		_panel.set_escala_ui(_mayor_escala(datos["escala"]))
	_crear_resalte(nodo)


func _actualizar_texto_seleccion() -> void:
	var datos: Dictionary = _prims.get(_sel_isla, {}).get(_sel_id, {})
	if datos.is_empty():
		_panel.set_seleccion("Selección: —")
		return
	_panel.set_seleccion("Selección: %s #%d · %.1f × %.1f × %.1f m" % [
		Prims.NOMBRES.get(datos["tipo"], datos["tipo"]), _sel_id,
		datos["escala"].x, datos["escala"].y, datos["escala"].z])


func _crear_resalte(nodo: Node3D) -> void:
	var malla := nodo.get_node_or_null("Malla") as MeshInstance3D
	if malla == null or malla.mesh == null:
		return
	var caja: AABB = malla.mesh.get_aabb()
	var esquinas := _esquinas(caja)
	var im := ImmediateMesh.new()
	im.surface_begin(Mesh.PRIMITIVE_LINES)
	for par in [[0, 1], [1, 3], [3, 2], [2, 0], [4, 5], [5, 7], [7, 6], [6, 4],
			[0, 4], [1, 5], [2, 6], [3, 7]]:
		im.surface_add_vertex(esquinas[par[0]])
		im.surface_add_vertex(esquinas[par[1]])
	im.surface_end()
	var resalte := MeshInstance3D.new()
	resalte.name = "Resalte"
	resalte.mesh = im
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color(0.2, 1.0, 0.95)
	mat.no_depth_test = true
	resalte.material_override = mat
	nodo.add_child(resalte)
	_resalte = resalte


func _esquinas(caja: AABB) -> Array:
	var p := caja.position
	var s := caja.size
	return [
		Vector3(p.x, p.y, p.z), Vector3(p.x + s.x, p.y, p.z),
		Vector3(p.x, p.y + s.y, p.z), Vector3(p.x + s.x, p.y + s.y, p.z),
		Vector3(p.x, p.y, p.z + s.z), Vector3(p.x + s.x, p.y, p.z + s.z),
		Vector3(p.x, p.y + s.y, p.z + s.z), Vector3(p.x + s.x, p.y + s.y, p.z + s.z),
	]


# ------------------------------------------------------------------- estado

func _refrescar_estado_ui() -> void:
	if _panel == null:
		return
	var idx := _isla_actual()
	var editable: bool = _puedo_editar(idx)
	var nombre := "—"
	if idx >= 0:
		nombre = _nombre_dueno(idx)
	_panel.set_isla("Isla %s · %s" % [str(idx) if idx >= 0 else "—", nombre], editable)
	var prims: int = int(_prims.get(idx, {}).size()) if idx >= 0 else 0
	var canal := "Anfitrión · WS 8911 (túnel)" if multiplayer.is_server() else "Invitado · cambios por el túnel del anfitrión"
	# Un aviso reciente manda: el refresco periódico no debe taparlo.
	if _ultimo_aviso == "":
		_panel.set_estado("%s\nObjetos: %d" % [canal, prims])


func _isla_actual() -> int:
	var cm := get_parent()
	if cm == null:
		return -1
	var propio = cm.get("my_own_index")
	if propio != null and int(propio) >= 0:
		return int(propio)
	var tm := get_parent().get_node_or_null("TeleportManager")
	var ub := get_parent().get_node_or_null("USERBASE") as Node3D
	if tm != null and ub != null and tm.has_method("current_island_index"):
		return int(tm.call("current_island_index", ub.position))
	return -1


func _nombre_dueno(idx: int) -> String:
	var cm := get_parent()
	if cm == null:
		return "—"
	var owners = cm.get("island_owners")
	if owners is Dictionary and owners.has(idx):
		var dato = owners[idx]
		if dato is Array and dato.size() > 1:
			var nick := str(dato[1])
			return nick if nick != "" else "Jugador %d" % int(dato[0])
	return "sin registrar"


func _avisar(texto: String) -> void:
	if texto == _ultimo_aviso:
		return
	_ultimo_aviso = texto
	_panel.set_estado(texto)
	print("[Construccion] ", texto)
	get_tree().create_timer(1.0).timeout.connect(func(): _ultimo_aviso = "")


@rpc("authority", "call_remote", "reliable")
func _aviso_red(texto: String) -> void:
	_avisar(texto)


func _avisar_remoto(peer: int, texto: String) -> void:
	if peer > 0:
		rpc_id(peer, "_aviso_red", texto)


# ------------------------------------------------------------ sincronizacion

@rpc("any_peer", "call_remote", "reliable")
func _pedir_estado(idx: int) -> void:
	if not multiplayer.is_server():
		return
	_enviar_estado(idx, multiplayer.get_remote_sender_id())


func _enviar_estado(idx: int, peer: int) -> void:
	if peer <= 0:
		return
	var terreno = _terrenos.get(idx)
	if terreno != null:
		_enviar_blob(peer, idx, TIPO_TERRENO, terreno.serializar())
	if _prims.has(idx):
		var texto := Prims.serializar_isla(_prims[idx], int(_siguiente.get(idx, 1)), _uuid_dueno(idx))
		_enviar_blob(peer, idx, TIPO_PRIMS, texto.to_utf8_buffer())


func _enviar_blob(peer: int, idx: int, tipo: int, datos: PackedByteArray) -> void:
	var comp := datos.compress(FileAccess.COMPRESSION_ZSTD)
	var partes := ceili(float(comp.size()) / float(BLOQUE_BYTES))
	if partes <= 0:
		partes = 1
	rpc_id(peer, "_blob_ini", idx, tipo, datos.size(), partes)
	for p in partes:
		var ini := p * BLOQUE_BYTES
		var fin := mini(comp.size(), ini + BLOQUE_BYTES)
		rpc_id(peer, "_blob_parte", idx, tipo, p, comp.slice(ini, fin))


@rpc("authority", "call_remote", "reliable")
func _blob_ini(idx: int, tipo: int, total: int, partes: int) -> void:
	_recibiendo["%d:%d" % [idx, tipo]] = {
		"total": total,
		"partes": partes,
		"datos": PackedByteArray(),
	}


@rpc("authority", "call_remote", "reliable")
func _blob_parte(idx: int, tipo: int, parte: int, datos: PackedByteArray) -> void:
	var clave := "%d:%d" % [idx, tipo]
	if not _recibiendo.has(clave):
		return
	var reg: Dictionary = _recibiendo[clave]
	var buffer: PackedByteArray = reg["datos"]
	buffer.append_array(datos)
	reg["datos"] = buffer
	if parte >= int(reg["partes"]) - 1:
		_recibiendo.erase(clave)
		var comprimido: PackedByteArray = reg["datos"]
		var crudo := comprimido.decompress(int(reg["total"]), FileAccess.COMPRESSION_ZSTD)
		_aplicar_blob(idx, tipo, crudo)


func _aplicar_blob(idx: int, tipo: int, crudo: PackedByteArray) -> void:
	if tipo == TIPO_TERRENO:
		var terreno = _terrenos.get(idx)
		# cargar() reconstruye malla y colisión.
		if terreno != null and terreno.cargar(crudo):
			_sucio[idx] = true
	elif tipo == TIPO_PRIMS:
		var leido := Prims.deserializar_isla(crudo.get_string_from_utf8())
		if leido.is_empty() or not _prims.has(idx):
			return
		_seleccionar(null)
		for id in _nodos[idx].keys():
			var nodo = _nodos[idx][id]
			if nodo != null and is_instance_valid(nodo):
				nodo.queue_free()
		_nodos[idx].clear()
		_prims[idx] = leido["prims"]
		_siguiente[idx] = int(leido["siguiente"])
		for id in _prims[idx]:
			_instanciar_prim(idx, _prims[idx][id])
		_sucio[idx] = true


func _aportar_estado(idx: int) -> void:
	var terreno = _terrenos.get(idx)
	if terreno != null:
		rpc_id(1, "_aportar_terreno", idx, terreno.serializar())
	var texto := Prims.serializar_isla(_prims.get(idx, {}), int(_siguiente.get(idx, 1)), _uuid_dueno(idx))
	rpc_id(1, "_aportar_prims", idx, texto.to_utf8_buffer())


@rpc("any_peer", "call_remote", "reliable")
func _aportar_terreno(idx: int, datos: PackedByteArray) -> void:
	if not multiplayer.is_server():
		return
	var remitente := multiplayer.get_remote_sender_id()
	if not _validar_remitente(idx, remitente):
		return
	var terreno = _terrenos.get(idx)
	if terreno == null or not terreno.cargar(datos):
		return
	terreno.actualizar_colision()
	_sucio[idx] = true
	for peer in multiplayer.get_peers():
		if peer != remitente:
			_enviar_blob(peer, idx, TIPO_TERRENO, datos)


@rpc("any_peer", "call_remote", "reliable")
func _aportar_prims(idx: int, datos: PackedByteArray) -> void:
	if not multiplayer.is_server():
		return
	var remitente := multiplayer.get_remote_sender_id()
	if not _validar_remitente(idx, remitente):
		return
	if not _prims.has(idx):
		return
	var leido := Prims.deserializar_isla(datos.get_string_from_utf8())
	if leido.is_empty():
		return
	_seleccionar(null)
	for id in _nodos[idx].keys():
		var nodo = _nodos[idx][id]
		if nodo != null and is_instance_valid(nodo):
			nodo.queue_free()
	_nodos[idx].clear()
	_prims[idx] = leido["prims"]
	_siguiente[idx] = int(leido["siguiente"])
	for id in _prims[idx]:
		_instanciar_prim(idx, _prims[idx][id])
	_sucio[idx] = true
	for peer in multiplayer.get_peers():
		if peer != remitente:
			var texto := Prims.serializar_isla(_prims[idx], int(_siguiente.get(idx, 1)), _uuid_dueno(idx))
			_enviar_blob(peer, idx, TIPO_PRIMS, texto.to_utf8_buffer())


# ------------------------------------------------------------------ proceso

func _process(delta: float) -> void:
	_ui_t += delta
	if _ui_t >= 0.5:
		_ui_t = 0.0
		_refrescar_estado_ui()
	if _modo:
		# Soltar el botón sobre la interfaz no llega a _unhandled_input: el
		# trazo se cierra aquí para no quedarse esculpiendo sin clic.
		if _pincelando and not Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
			_terminar_pincel()
		_mira_t += delta
		if _mira_t >= 0.07:
			_mira_t = 0.0
			_actualizar_mira()
		if _pincelando:
			_pincel_t += delta
			if _pincel_t >= PASO_PINCEL:
				_pincel_t = 0.0
				_tick_pincel()
	_col_t += delta
	# Debounce: la colisión trimesh tarda ~20 ms; se reconstruye cuando el
	# pincel lleva 0,5 s sin cambios (o al soltar, en _terminar_pincel).
	if _col_t >= 0.5 and not _colision_pendiente.is_empty():
		_col_t = 0.0
		for idx in _colision_pendiente.keys():
			var t = _terrenos.get(int(idx))
			if t != null:
				t.actualizar_colision()
		_colision_pendiente.clear()
	_guardar_t += delta
	if _guardar_t >= 2.0:
		_guardar_t = 0.0
		_guardar_sucios()


# ------------------------------------------------------------- utilidades

func _rayo_raton() -> Dictionary:
	var cam := get_viewport().get_camera_3d()
	if cam == null:
		return {}
	var pantalla := get_viewport().get_mouse_position()
	var desde := cam.project_ray_origin(pantalla)
	var hasta := desde + cam.project_ray_normal(pantalla) * 600.0
	var consulta := PhysicsRayQueryParameters3D.create(desde, hasta)
	consulta.collide_with_areas = false
	var ub := get_parent().get_node_or_null("USERBASE") if get_parent() != null else null
	if ub is CollisionObject3D:
		consulta.exclude = [(ub as CollisionObject3D).get_rid()]
	return get_world_3d().direct_space_state.intersect_ray(consulta)


func _isla_del_impacto(hit: Dictionary) -> int:
	var collider = hit.get("collider")
	if collider is Node and is_instance_valid(collider):
		var nodo := collider as Node
		if nodo.has_meta("isla"):
			return int(nodo.get_meta("isla"))
		var padre := nodo.get_parent()
		while padre != null:
			if padre.has_meta("isla"):
				return int(padre.get_meta("isla"))
			padre = padre.get_parent()
	if hit.has("position"):
		return _isla_por_posicion(hit["position"])
	return -1


func _isla_por_posicion(pos: Vector3) -> int:
	var mejor := -1
	var mejor_d := 1e20
	for idx in _islas.keys():
		var nodo: Node3D = _islas[idx]
		if nodo == null or not is_instance_valid(nodo):
			continue
		var d := Vector2(nodo.global_position.x - pos.x, nodo.global_position.z - pos.z).length()
		if d < mejor_d:
			mejor_d = d
			mejor = int(idx)
	return mejor if mejor_d <= 110.0 else -1


func _giro_camara() -> float:
	var cam := get_viewport().get_camera_3d()
	if cam == null:
		return 0.0
	return rad_to_deg(cam.global_rotation.y)


func _crear_mira() -> void:
	var im := ImmediateMesh.new()
	im.surface_begin(Mesh.PRIMITIVE_LINE_STRIP)
	for i in 49:
		var angulo := TAU * float(i) / 48.0
		im.surface_add_vertex(Vector3(cos(angulo), 0.0, sin(angulo)))
	im.surface_end()
	_mira = MeshInstance3D.new()
	_mira.name = "MiraConstruccion"
	_mira.mesh = im
	_mira.top_level = true
	_mira.visible = false
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color(0.25, 1.0, 0.85, 0.95)
	mat.no_depth_test = true
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_mira.material_override = mat
	add_child(_mira)


## `impacto` permite fijar el acierto desde una prueba; en juego se calcula
## con el rayo del ratón.
func _actualizar_mira(impacto := {}) -> void:
	if _mira == null:
		return
	if not _modo or _herramienta == Herramienta.SELECCION:
		_mira.visible = false
		return
	var hit: Dictionary = impacto if not impacto.is_empty() else _rayo_raton()
	if hit.is_empty():
		_mira.visible = false
		return
	_mira.visible = true
	_mira.global_position = (hit["position"] as Vector3) + Vector3(0.0, 0.25, 0.0)
	_mira.scale = Vector3(_radio, 1.0, _radio)
	var mat := _mira.material_override as StandardMaterial3D
	if mat == null:
		return
	# Vista previa de permisos: sobre una isla ajena la mira se vuelve roja en
	# lugar de ofrecer un pincel que el anfitrión va a rechazar.
	if not _puedo_editar(_isla_del_impacto(hit)):
		mat.albedo_color = Color(1.0, 0.32, 0.32, 0.9)
		return
	match _herramienta:
		Herramienta.SUBIR:
			mat.albedo_color = Color(0.3, 1.0, 0.55, 0.95)
		Herramienta.BAJAR:
			mat.albedo_color = Color(1.0, 0.42, 0.35, 0.95)
		Herramienta.SUAVIZAR:
			mat.albedo_color = Color(0.35, 0.85, 1.0, 0.95)
		Herramienta.APLANAR:
			mat.albedo_color = Color(1.0, 0.85, 0.3, 0.95)
		Herramienta.MOVER:
			mat.albedo_color = Color(0.85, 0.72, 1.0, 0.95)
		Herramienta.PLAYA:
			mat.albedo_color = Color(0.98, 0.9, 0.62, 0.95)
