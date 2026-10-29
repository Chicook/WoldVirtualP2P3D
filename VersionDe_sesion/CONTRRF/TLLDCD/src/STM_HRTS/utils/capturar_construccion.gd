extends SceneTree
## Prueba visual del modo construcción: esculpe el terreno de la isla con las
## cuatro herramientas y reza/edita prims, capturando antes y después.
##
## Uso: godot --path . --script res://tools/capturar_construccion.gd
## Salida: CONSTRUCCION_DIR o user://capturas_construccion (PNG + log).
## Necesita ventana (save_png). No escribe en user://construccion: termina las
## pinceladas sin llamar a _terminar_pincel y limpia _sucio antes de cerrar.

const MUNDO := "res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn"
const CIELO := "res://gdshader/cielo_isla_env.tres"
const Prims := preload("res://gdscrip/Prims.gd")
const Terreno := preload("res://gdscrip/TerrenoEditable.gd")
const VoxelSuave := preload("res://gdscrip/VoxelSuave.gd")

var _ok := 0
var _fallos := 0
var _salida := ""
var _mundo: Node = null
var _c: Node = null
var _t = null
var _cam: Camera3D = null
var _objetivo := Vector3.ZERO


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	_salida = OS.get_environment("CONSTRUCCION_DIR")
	if _salida.is_empty():
		_salida = OS.get_user_data_dir().path_join("capturas_construccion")
	DirAccess.make_dir_recursive_absolute(_salida)

	_mundo = (load(MUNDO) as PackedScene).instantiate()
	get_root().add_child(_mundo)
	get_root().size = Vector2i(1280, 720)

	# El mundo jugable recibe luz y cielo desde Boot; aquí se replican para la
	# captura y se oculta el avatar para no tapar el terreno.
	var avatar := _mundo.get_node_or_null("USERBASE")
	if avatar != null:
		avatar.visible = false
	# El explorador de islas no interviene en la prueba y taparía los prims.
	var explorador := _mundo.get_node_or_null("TeleportPanel")
	if explorador != null:
		explorador.visible = false
	var cielo := WorldEnvironment.new()
	cielo.environment = load(CIELO)
	_mundo.add_child(cielo)
	var sol := DirectionalLight3D.new()
	sol.rotation_degrees = Vector3(-58.0, -38.0, 0.0)
	sol.light_energy = 1.15
	sol.shadow_enabled = true
	_mundo.add_child(sol)

	_c = _mundo.get_node_or_null("Constructor")
	for i in 240:
		if _c != null and _c._terrenos.has(0):
			break
		await process_frame
		await physics_frame
	if _c == null or not _c._terrenos.has(0):
		print("FALLO no se registró el terreno de la isla 0")
		quit(1)
		return
	_t = _c._terrenos[0]
	print("ISLA vértices=", _t.vertices.size(), " escala=", _t.escala)

	# La isla se genera a ~200 m; la meseta central queda a y local ~0.5.
	_objetivo = _t.malla.to_global(Vector3(0.0, _altura_local(0.0, 0.0), 0.0))
	_cam = Camera3D.new()
	_cam.fov = 55.0
	_cam.far = 3000.0
	_mundo.add_child(_cam)
	_cam.global_position = _objetivo + Vector3(78.0, 62.0, 108.0)
	_cam.look_at(_objetivo, Vector3.UP)
	_cam.current = true

	# El bucle propio guarda cada 2 s y reconstruye colisión; la prueba la
	# controla a mano y evita escribir en user://construccion.
	_c.set_process(false)
	_c._activar_modo(true)
	_c._refrescar_estado_ui()
	await _apuntar(_objetivo)
	_c._actualizar_mira()
	await _capturar("00_isla_antes.png")

	var h0: float = _altura_local(0.0, 0.0) * _t.escala
	print("ALTURA base=%.2f m (local %.4f)" % [h0, _altura_local(0.0, 0.0)])
	_estadisticas("base")

	# ---------------------------------------------------------------- subir
	await _fijar_radio_fuerza(24.0, 4.0)
	await _pincel(1, 40, _objetivo)
	var h_subir: float = _altura_local(0.0, 0.0) * _t.escala
	_check(h_subir - h0 > 3.0, "subir eleva el terreno: %+.2f m" % (h_subir - h0))
	_estadisticas("subir")
	await _capturar("01_subir.png")

	# ---------------------------------------------------------------- bajar
	await _restaurar_base()
	await _pincel(2, 40, _objetivo)
	var h_bajar: float = _altura_local(0.0, 0.0) * _t.escala
	_check(h0 - h_bajar > 3.0, "bajar hunde el terreno: %+.2f m" % (h_bajar - h0))
	_estadisticas("bajar")
	await _capturar("02_bajar.png")

	# ------------------------------------------------------------- suavizar
	await _restaurar_base()
	await _fijar_radio_fuerza(8.0, 4.0)
	await _pincel(1, 30, _objetivo)
	var pico_antes: float = _altura_local(0.0, 0.0) * _t.escala
	_estadisticas("pico antes de suavizar")
	await _capturar("03a_antes_suavizar.png")
	await _fijar_radio_fuerza(24.0, 4.0)
	await _pincel(3, 40, _objetivo)
	var pico_despues: float = _altura_local(0.0, 0.0) * _t.escala
	_check(pico_despues < pico_antes - 0.5,
			"suavizar rebaja el pico: %.2f -> %.2f m" % [pico_antes, pico_despues])
	_estadisticas("suavizar")
	await _capturar("03_suavizar.png")

	# -------------------------------------------------------------- aplanar
	await _restaurar_base()
	await _fijar_radio_fuerza(10.0, 4.0)
	await _pincel(1, 30, _objetivo)
	var pico_local := _altura_local(0.0, 0.0)
	var cima: Vector3 = _t.malla.to_global(Vector3(0.0, pico_local, 0.0))
	var dispersion_antes := _dispersion(0.12)
	_estadisticas("antes de aplanar")
	await _capturar("04a_antes_aplanar.png")
	await _fijar_radio_fuerza(24.0, 4.0)
	await _pincel(4, 50, cima)
	var dispersion_despues := _dispersion(0.12)
	_check(dispersion_despues < dispersion_antes * 0.6,
			"aplanar reduce el desnivel del disco: %.2f -> %.2f m"
			% [dispersion_antes * _t.escala, dispersion_despues * _t.escala])
	_estadisticas("aplanar")
	await _capturar("04_aplanar.png")

	# ---------------------------------------------------------------- mover
	await _restaurar_base()
	var origen_base := _media_caja(-0.05, 0.0, -0.05, 0.05)
	await _fijar_radio_fuerza(8.0, 4.0)
	await _pincel(1, 40, _objetivo)
	var plataforma := _media_anillo(0.30, 0.45)
	var umbral := plataforma + 0.01
	var centro_antes := _centroide_exceso(umbral)
	var origen_antes := _media_caja(-0.05, 0.0, -0.05, 0.05)
	print("MATERIAL isla: %s (shader de terreno: %s)" % [
		_t.material.get_class(), _t.material.shader != null])
	print("MOVER montículo: plataforma=%.4f, centro x=%.2f m"
			% [plataforma, centro_antes * _t.escala])
	_cam.global_position = _objetivo + Vector3(-14.0, 26.0, 38.0)
	_cam.look_at(_objetivo + Vector3(10.0, 0.0, 0.0), Vector3.UP)
	await _capturar("08a_antes_mover.png")
	await _fijar_radio_fuerza(20.0, 4.0)
	await _pincel_mover(12, _objetivo, 0.6)
	var centro_despues := _centroide_exceso(umbral)
	var origen_despues := _media_caja(-0.05, 0.0, -0.05, 0.05)
	var levantado := origen_antes - origen_base
	var retirado := origen_antes - origen_despues
	_check((centro_despues - centro_antes) * _t.escala > 1.5,
			"mover desplaza el montículo %.2f m hacia +X"
			% ((centro_despues - centro_antes) * _t.escala))
	_check(levantado > 0.004,
			"mover parte de un montículo levantado (%.1f cm)"
			% (levantado * _t.escala * 100.0))
	_check(retirado >= maxf(0.002, levantado * 0.6),
			"mover vacía la posición original (%.3f -> %.3f, base %.3f)"
			% [origen_antes, origen_despues, origen_base])
	print("MOVER resultado: centro x=%.2f m, origen=%.3f"
			% [centro_despues * _t.escala, origen_despues])
	await _capturar("08_mover.png")

	# ---------------------------------------------------------------- playa
	await _restaurar_base()
	await _fijar_radio_fuerza(14.0, 4.0)
	var costa := _indice_cerca(0.50, 0.0)
	var costa_mundo: Vector3 = _t.malla.to_global(_t.vertices[costa])
	_cam.global_position = costa_mundo + Vector3(-32.0, 22.0, 26.0)
	_cam.look_at(costa_mundo + Vector3(10.0, 0.0, 0.0), Vector3.UP)
	await _capturar("09a_antes_playa.png")
	for i in 60:
		_t.aplicar_pincel(costa_mundo, _c._radio, _c._fuerza, 0.05, Terreno.PLAYA)
	_t.actualizar_colision()
	_c._sucio.clear()
	_c._colision_pendiente.clear()
	var esperado: float = _t.nivel_agua + Terreno.MARGEN_PLAYA_M / _t.escala
	var y_costa: float = _t.vertices[costa].y
	var color_costa: Color = _t.colores[costa]
	_check(absf(y_costa - esperado) < 0.01,
			"playa aplana a agua+1 m (%.3f vs %.3f)" % [y_costa, esperado])
	_check(_color_cerca(color_costa, Terreno.COLOR_PLAYA),
			"playa tiñe de arena (%s)" % color_costa.to_html(true))
	print("PLAYA costa: nivel agua=%.3f, altura=%.3f, esperado=%.3f, color=%s"
			% [_t.nivel_agua, y_costa, esperado, color_costa.to_html(true)])
	await process_frame
	await physics_frame
	await _capturar("09_playa.png")
	_cam.global_position = costa_mundo + Vector3(-10.0, 42.0, 28.0)
	_cam.look_at(costa_mundo + Vector3(8.0, 0.0, 0.0), Vector3.UP)
	await _capturar("09b_playa_aerea.png")

	# -------------------------------------------- mover conserva el color
	await _restaurar_base()
	await _fijar_radio_fuerza(14.0, 4.0)
	# Playa en la costa y un montículo encima: la arena queda en la tierra que
	# se va a desplazar. Si Mover no arrastrara el color, se quedaría atrás.
	var arena_costa := _indice_cerca(0.50, 0.0)
	var arena_mundo: Vector3 = _t.malla.to_global(_t.vertices[arena_costa])
	for i in 60:
		_t.aplicar_pincel(arena_mundo, 14.0, 4.0, 0.05, Terreno.PLAYA)
	for i in 20:
		_t.aplicar_pincel(arena_mundo, 8.0, 4.0, 0.05, Terreno.SUBIR)
	_t.actualizar_colision()
	_c._sucio.clear()
	_c._colision_pendiente.clear()
	var arena_x0 := _centroide_arena()
	var masa0 := _masa_arena()
	_cam.global_position = arena_mundo + Vector3(-34.0, 24.0, 30.0)
	_cam.look_at(arena_mundo + Vector3(6.0, 0.0, 0.0), Vector3.UP)
	await _capturar("11a_antes_mover_color.png")
	await _fijar_radio_fuerza(20.0, 4.0)
	for i in 40:
		_t.aplicar_pincel(arena_mundo, 20.0, 4.0, 0.05, Terreno.MOVER, Vector3(0.5, 0.0, 0.0))
	_t.actualizar_colision()
	_c._sucio.clear()
	_c._colision_pendiente.clear()
	var arena_x1 := _centroide_arena()
	var masa1 := _masa_arena()
	_check((arena_x1 - arena_x0) * _t.escala > 2.0,
			"mover arrastra la arena %.2f m" % ((arena_x1 - arena_x0) * _t.escala))
	_check(absf(masa1 - masa0) < masa0 * 0.25,
			"mover conserva la máscara de arena (%.0f -> %.0f)" % [masa0, masa1])
	var alfa_movida := _max_alfa_cerca(arena_x1)
	_check(alfa_movida > 0.5, "la tierra movida sigue siendo arena (alfa %.2f)" % alfa_movida)
	print("MOVER COLOR arena x=%.2f -> %.2f m, masa %.0f -> %.0f"
			% [arena_x0 * _t.escala, arena_x1 * _t.escala, masa0, masa1])
	var foco: Vector3 = _t.malla.to_global(Vector3(arena_x1, _t.vertices[arena_costa].y, 0.0))
	_cam.global_position = foco + Vector3(-9.0, 11.0, 17.0)
	_cam.look_at(foco, Vector3.UP)
	await _capturar("11_mover_color.png")

	# ---------------------------------------------------------------- prims
	await _restaurar_base()
	await _fijar_radio_fuerza(24.0, 4.0)
	var tipos := ["cubo", "esfera", "cilindro", "cono", "toro"]
	for i in tipos.size():
		var tipo: String = tipos[i]
		var esc := Prims.tamano_por_defecto(tipo)
		var x_m := -8.0 + 4.0 * i
		var h_m: float = _altura_local(x_m / _t.escala, 0.0) * _t.escala
		_c._rez_con_datos(0, tipo, Vector3(x_m, h_m + esc.y * 0.5, 0.0),
				Vector3(0.0, 15.0, 0.0), esc, Prims.COLORES[i + 1])
	await process_frame
	_check(int(_c._prims[0].size()) == 5, "se rezan los 5 tipos de prim")
	var nodos_ok := true
	for id in [1, 2, 3, 4, 5]:
		if not _c._nodos[0].has(id):
			nodos_ok = false
	_check(nodos_ok, "cada prim tiene su nodo en la isla")
	_c._sucio.clear()
	_c._colision_pendiente.clear()

	_cam.global_position = _objetivo + Vector3(78.0, 62.0, 108.0)
	_cam.look_at(_objetivo, Vector3.UP)
	await _capturar("05_prims_amplia.png")

	var centro_prims: Vector3 = _t.malla.to_global(Vector3(0.0, _altura_local(0.0, 0.0), 0.0))
	_cam.global_position = centro_prims + Vector3(0.0, 10.0, 27.0)
	_cam.look_at(centro_prims + Vector3(0.0, 1.0, 0.0), Vector3.UP)
	await _capturar("06_prims_detalle.png")

	# ------------------------------------------------------- editar un prim
	_c._seleccionar(_c._nodos[0][1])
	_check(_c._sel_id == 1, "el cubo queda seleccionado para editar")
	_c._aplicar_escala(4.0)
	_c._aplicar_color(Prims.COLORES[1])
	var esc_cubo: Vector3 = _c._prims[0][1]["escala"]
	_check(esc_cubo.is_equal_approx(Vector3(4.0, 4.0, 4.0)),
			"escalar deja el cubo a 4 m por eje")
	_check((_c._prims[0][1]["color"] as Color).to_html(true)
			== Prims.COLORES[1].to_html(true), "el color se aplica al cubo")
	await process_frame
	await _capturar("07_prim_editado.png")
	_c._seleccionar(null)

	await _probar_voxel_visual()

	# --------------------------------------------------- aislamiento por isla
	# Una segunda isla como las que crea ChunkManager: duplicado de la plantilla
	# oculta, con otra isla y otro dueño.
	var plantilla := _mundo.get_node_or_null("ISLA3DCHUNK") as Node3D
	var isla_ajena := plantilla.duplicate() as Node3D
	isla_ajena.name = "IslaAjena"
	var centro_ajeno: Vector2 = _mundo._centro_isla(1)
	isla_ajena.position.x += centro_ajeno.x
	isla_ajena.position.z += centro_ajeno.y
	_mundo.add_child(isla_ajena)
	isla_ajena.show()
	var oceano_original := _mundo.get_node_or_null("Oceano3D") as Node3D
	if oceano_original != null:
		var oceano_ajeno := oceano_original.duplicate() as Node3D
		oceano_ajeno.position.x += centro_ajeno.x
		oceano_ajeno.position.z += centro_ajeno.y
		_mundo.add_child(oceano_ajeno)
		oceano_ajeno.show()
	_mundo.island_owners[1] = [2, "Otro jugador", "UUID-OTRO"]
	_c.registrar_isla(1, isla_ajena)
	_check(_c._terrenos.has(1), "la isla ajena se registra con su propio terreno")
	_check(_c._puedo_editar(0), "mi isla se puede editar")
	_check(not _c._puedo_editar(1), "la isla ajena no se puede editar")
	var t_ajena = _c._terrenos[1]
	var base_ajena: PackedVector3Array = t_ajena.vertices.duplicate()
	var colores_ajenos: PackedColorArray = t_ajena.colores.duplicate()

	# Esculpimos la nuestra: la ajena debe quedar intacta.
	await _fijar_radio_fuerza(24.0, 4.0)
	await _pincel(1, 25, _objetivo)
	_check(t_ajena.vertices == base_ajena, "esculpir mi isla no mueve la ajena")
	_check(t_ajena.colores == colores_ajenos, "esculpir mi isla no tiñe la ajena")
	_check(t_ajena.malla.mesh != _t.malla.mesh, "cada isla conserva su malla")
	_check(t_ajena.material != _t.material, "cada isla conserva su material")

	# Con una herramienta activa, la mira sobre la isla ajena se vuelve roja.
	var punto_ajeno: Vector3 = t_ajena.malla.to_global(Vector3(0.0, 0.5, 0.0))
	_cam.global_position = punto_ajeno + Vector3(-6.0, 30.0, 44.0)
	_cam.look_at(punto_ajeno, Vector3.UP)
	_c._on_herramienta(1)
	_c._panel._botones_herr[1].button_pressed = true
	_c._actualizar_mira({"position": punto_ajeno, "collider": t_ajena.cuerpo})
	_check(_c._mira.visible, "la mira aparece sobre la isla ajena")
	var color_mira: Color = (_c._mira.material_override as StandardMaterial3D).albedo_color
	_check(color_mira == Color(1.0, 0.32, 0.32, 0.9),
			"la mira se vuelve roja en isla ajena (%s)" % color_mira.to_html(true))
	await process_frame
	await physics_frame
	await _capturar("10_isla_ajena.png")
	_c._on_herramienta(0)

	# --------------------------------------------------------------- cierre	_c._activar_modo(false)
	_c._sucio.clear()
	_c._colision_pendiente.clear()
	_c.set_process(false)
	_mundo.queue_free()
	await process_frame
	print("RESULTADO CONSTRUCCION VISUAL: %d OK, %d FALLOS" % [_ok, _fallos])
	quit(1 if _fallos > 0 else 0)


## Terreno voxel: varias elevaciones suaves en tierra firme y una playa que
## avanza hasta el contorno sumergido de la isla, nunca más allá de MARGEN_MAR
## sobre la orilla. El borde de cada una se comprueba con rayos contra la isla
## real, no contra el radio declarado.
func _probar_voxel_visual() -> void:
	var isla := _c._islas[0] as Node3D
	_check(_c._panel._btn_terreno != null and _c._panel._btn_terreno.text == "Crear terreno",
			"el panel ofrece el botón Crear terreno")
	_check(_c._panel.forma_voxel() == "isla", "el selector de forma arranca en Isla")

	var agua_y: float = _c._nivel_agua_mundo(_t)
	var costa_idx := _indice_cerca(0.50, 0.0)
	var costa_mundo: Vector3 = _t.malla.to_global(_t.vertices[costa_idx])
	print("VOXEL agua y=%.2f, costa de referencia en (%.1f, %.1f) m"
			% [agua_y, costa_mundo.x, costa_mundo.z])
	var disp_centro: float = _c._radio_tierra(0, Vector3.ZERO, 60.0)
	print("VOXEL tierra disponible desde el centro: %.1f m" % disp_centro)
	_check(disp_centro > 8.0,
			"el contorno deja sitio para elevar terreno (%.1f m)" % disp_centro)
	if disp_centro <= 8.0:
		return

	# La rejilla de prims de la prueba anterior estorba en la vista y en los
	# rayos del contorno.
	for id in [1, 2, 3, 4, 5]:
		_c._host_borrar_prim(0, id)
	await process_frame
	await physics_frame

	var xmax: float = minf(26.0, disp_centro * 0.7)
	var xs := [-xmax, -xmax / 3.0, xmax / 3.0, xmax]
	var formas := ["isla", "meseta", "arco", "cordillera"]
	var colores := [
		Color(0.43, 0.57, 0.32),
		Color(0.50, 0.58, 0.35),
		Color(0.46, 0.50, 0.38),
		Color(0.38, 0.47, 0.30),
	]
	var nodos: Array[Node3D] = []

	# Vista amplia para que el ratón alcance el primer hueco.
	_cam.global_position = _objetivo + Vector3(0.0, 55.0, 95.0)
	_cam.look_at(_objetivo + Vector3(0.0, 4.0, 0.0), Vector3.UP)
	await process_frame
	await physics_frame

	# El primer montículo nace pulsando el botón del panel: cubre la ruta
	# completa (señal -> raycast -> medición de contorno -> rez).
	var h0: float = _altura_local(float(xs[0]) / _t.escala, 0.0) * _t.escala
	await _apuntar(isla.to_global(Vector3(float(xs[0]), h0, 0.0)))
	var ids_antes: Array = _c._prims[0].keys()
	_c._color_actual = colores[0]
	_c._panel._forma_voxel.selected = 0
	_c._panel._btn_terreno.pressed.emit()
	await process_frame
	await physics_frame
	var nodo_boton: Node3D = null
	var id_boton := 0
	for id in _c._prims[0].keys():
		if not ids_antes.has(id):
			id_boton = int(id)
			nodo_boton = _c._nodos[0].get(id) as Node3D
			break
	_check(nodo_boton != null, "el botón Crear terreno reza una elevación")
	if nodo_boton != null:
		var prm_boton: Dictionary = _c._prims[0][id_boton]["params"]
		_check(str(_c._prims[0][id_boton]["tipo"]) == "voxel", "el botón crea un prim voxel")
		_check(str(prm_boton.get("forma", "")) == "isla", "el botón respeta la forma Isla")
		nodos.append(nodo_boton)
		_comprobar_voxel(nodo_boton, prm_boton, false)

	# Las otras tres formas, una por hueco y con semilla fija.
	for i in range(1, 4):
		var creado: Dictionary = await _crear_voxel_en(formas[i], float(xs[i]), 0.0,
				colores[i], 700 + i)
		_check(not creado.is_empty(),
				"%s creado en x=%.1f m" % [VoxelSuave.NOMBRES[formas[i]], float(xs[i])])
		if creado.is_empty():
			continue
		nodos.append(creado["nodo"] as Node3D)
		_comprobar_voxel(creado["nodo"], creado["params"], false)

	_cam.global_position = _objetivo + Vector3(0.0, 55.0, 95.0)
	_cam.look_at(_objetivo + Vector3(0.0, 4.0, 0.0), Vector3.UP)
	await _capturar("12_voxel_formas.png")

	if nodos.size() >= 3:
		var arco: Node3D = nodos[2]
		_cam.global_position = arco.global_position + Vector3(-14.0, 12.0, 22.0)
		_cam.look_at(arco.global_position + Vector3(0.0, 4.5, 0.0), Vector3.UP)
		await _capturar("13_voxel_arco.png")

	# ---------------------------------------------------------------- playa
	var dir_costa := Vector2.RIGHT
	var costa_x: float = _tierra_en_direccion(Vector3.ZERO, dir_costa, 70.0)
	if costa_x < 8.0:
		dir_costa = Vector2.LEFT
		costa_x = _tierra_en_direccion(Vector3.ZERO, dir_costa, 70.0)
	_check(costa_x > 8.0, "se localiza la orilla para la playa (%.1f m)" % costa_x)
	if costa_x > 8.0:
		var centro_playa := dir_costa * maxf(5.0, costa_x - 5.0)
		var playa: Dictionary = await _crear_voxel_en("isla", centro_playa.x,
				centro_playa.y, Color(0.80, 0.72, 0.50), 4242, true)
		_check(not playa.is_empty(), "la playa se crea junto a la orilla")
		if not playa.is_empty():
			var prm_playa: Dictionary = playa["params"]
			var nodo_playa: Node3D = playa["nodo"]
			var disp_playa: float = float(playa["disponible"])
			_check(float(prm_playa["borde"]) <= disp_playa + 0.001,
					"la playa no sale del contorno medido (borde %.2f, tierra %.2f)"
					% [float(prm_playa["borde"]), disp_playa])
			_check(float(prm_playa["playa"]) >= 0.4,
					"la playa lleva faldón de arena (%.2f m)"
					% float(prm_playa["playa"]))
			_check(absf(nodo_playa.global_position.y - (agua_y - 0.15)) < 0.05,
					"la base de la playa nace a 15 cm bajo el agua")
			_comprobar_voxel(nodo_playa, prm_playa, true)
			_cam.global_position = nodo_playa.global_position + Vector3(22.0, 12.0, 20.0)
			_cam.look_at(nodo_playa.global_position + Vector3(-4.0, 0.8, 0.0), Vector3.UP)
			await _capturar("14_voxel_playa.png")

	# ---------------------------------------------------------- panel voxel
	_c._panel._scroll.scroll_vertical = 250
	await process_frame
	await _capturar("15_panel_voxel.png")
	_c._panel._scroll.scroll_vertical = 0
	_c._color_actual = Prims.COLORES[0]
	await process_frame


## Crea un prim voxel encajado al contorno medido, con semilla fija y la base
## enterrada bajo la superficie. Devuelve {nodo, params, disponible}.
func _crear_voxel_en(forma: String, x: float, z: float, color: Color, semilla: int,
		tocar_mar := false) -> Dictionary:
	var isla := _c._islas[0] as Node3D
	var prm := VoxelSuave.params_por_defecto(forma)
	prm["semilla"] = semilla
	var disponible: float = _c._disponible_voxel(0, Vector3(x, 0.0, z),
			float(prm["borde"]), tocar_mar)
	if disponible <= 0.0:
		return {}
	var ajustado := VoxelSuave.ajustar_a_borde(prm, disponible, tocar_mar)
	if ajustado.is_empty():
		return {}
	var agua_y: float = _c._nivel_agua_mundo(_t)
	var h_m: float = _altura_local(x / _t.escala, z / _t.escala) * _t.escala
	var y_local := h_m - 0.25
	if tocar_mar:
		y_local = agua_y - isla.global_position.y - 0.15
		var altura_sobre_agua: float = isla.global_position.y + h_m - agua_y
		ajustado["playa"] = clampf(altura_sobre_agua + 0.15, 0.45, 1.2)
	var ids_antes: Array = _c._prims[0].keys()
	_c._rez_con_datos(0, Prims.TIPO_VOXEL, Vector3(x, y_local, z), Vector3.ZERO,
			Vector3.ONE, color, ajustado)
	await process_frame
	await physics_frame
	for id in _c._prims[0].keys():
		if ids_antes.has(id):
			continue
		var nodo := _c._nodos[0].get(id) as Node3D
		if nodo != null:
			return {"nodo": nodo, "params": _c._prims[0][id]["params"],
					"disponible": disponible}
	return {}


## Comprueba malla y contorno de un voxel. `permitir_agua` deja tocar la orilla
## (playa); sin él, todo el borde debe seguir en tierra firme.
func _comprobar_voxel(nodo: Node3D, params: Dictionary, permitir_agua: bool) -> void:
	var forma := str(params.get("forma", "isla"))
	var malla := nodo.get_node_or_null("Malla") as MeshInstance3D
	_check(malla != null and malla.mesh != null, "el voxel %s tiene malla" % forma)
	if malla == null or malla.mesh == null:
		return
	var verts := malla.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX] as PackedVector3Array
	_check(verts.size() > 100, "la malla de %s tiene %d vértices" % [forma, verts.size()])
	var radio_malla := 0.0
	for v in verts:
		radio_malla = maxf(radio_malla, Vector2(v.x, v.z).length())
	_check(radio_malla <= float(params["borde"]) + 0.01,
			"la malla de %s cabe en su borde (%.2f <= %.2f m)"
			% [forma, radio_malla, float(params["borde"])])
	var frente := _frontera_en_tierra(nodo, radio_malla, permitir_agua)
	_check(bool(frente["ok"]),
			"%s no sale del contorno (%d fallos, cota mínima %.2f m)"
			% [VoxelSuave.NOMBRES.get(forma, forma), int(frente["fallos"]),
			float(frente["peor"])])


## Último radio (metros de isla) que sigue siendo tierra firme en una
## dirección. La costa se mide con el terreno real, no con la caja de la malla.
func _tierra_en_direccion(centro: Vector3, dir: Vector2, maximo: float) -> float:
	var agua_y: float = _c._nivel_agua_mundo(_t)
	var isla := _c._islas[0] as Node3D
	var excluir := _exclusiones_rayos()
	var ultimo := 0.0
	var r := 0.5
	while r <= maximo:
		var mundo: Vector3 = isla.to_global(Vector3(centro.x + dir.x * r, 0.0,
				centro.z + dir.y * r))
		var consulta := PhysicsRayQueryParameters3D.create(
				Vector3(mundo.x, agua_y + 240.0, mundo.z),
				Vector3(mundo.x, agua_y - 90.0, mundo.z))
		consulta.collide_with_areas = false
		consulta.exclude = excluir
		var golpe: Dictionary = (_mundo as Node3D).get_world_3d().direct_space_state.intersect_ray(consulta)
		if golpe.is_empty():
			break
		var col = golpe["collider"]
		if not (col is Node):
			break
		var nodo := col as Node
		if not nodo.has_meta("terreno_editable") or int(nodo.get_meta("isla", -1)) != 0:
			break
		if (golpe["position"] as Vector3).y <= agua_y:
			break
		ultimo = r
		r += 0.5
	return ultimo


## Lanza 32 rayos justo en el contorno real de la malla y comprueba que todos
## caen en la isla propia. En tierra firme la cota debe seguir sobre el agua;
## en la playa basta con que haya terreno de la isla: su borde ya se midió
## contra el contorno, y el fondo puede estar sumergido.
func _frontera_en_tierra(nodo: Node3D, borde: float, permitir_agua: bool) -> Dictionary:
	var agua_y: float = _c._nivel_agua_mundo(_t)
	var tolerancia := 1e9 if permitir_agua else 0.05
	var excluir := _exclusiones_rayos()
	var fallos := 0
	var peor := 1e9
	var radio := borde
	for a in 32:
		var angulo := TAU * float(a) / 32.0
		var punto: Vector3 = nodo.global_position \
				+ Vector3(cos(angulo), 0.0, sin(angulo)) * radio
		var consulta := PhysicsRayQueryParameters3D.create(
				Vector3(punto.x, agua_y + 240.0, punto.z),
				Vector3(punto.x, agua_y - 90.0, punto.z))
		consulta.collide_with_areas = false
		consulta.exclude = excluir
		var golpe: Dictionary = (_mundo as Node3D).get_world_3d().direct_space_state.intersect_ray(consulta)
		var cota := -1e9
		if not golpe.is_empty():
			var col = golpe["collider"]
			if col is Node:
				var n := col as Node
				if n.has_meta("terreno_editable") and int(n.get_meta("isla", -1)) == 0:
					cota = (golpe["position"] as Vector3).y - agua_y
		if cota >= -tolerancia:
			peor = minf(peor, cota)
		else:
			fallos += 1
	return {"ok": fallos == 0, "fallos": fallos,
			"peor": peor if peor < 1e8 else -999.0}


## Cuerpos que no deben tapar la medición del contorno: todo lo que no sea
## terreno editable (océano, avatar, prims, plantilla oculta). Así el rayo
## atraviesa el agua y mide la isla que hay debajo.
func _exclusiones_rayos() -> Array[RID]:
	var excluir: Array[RID] = []
	_excluir_sin_terreno(_mundo, excluir)
	return excluir


func _excluir_sin_terreno(nodo: Node, excluir: Array[RID]) -> void:
	if nodo is CollisionObject3D and not nodo.has_meta("terreno_editable"):
		excluir.append((nodo as CollisionObject3D).get_rid())
	for hijo in nodo.get_children():
		_excluir_sin_terreno(hijo, excluir)


func _pincel(herramienta: int, ticks: int, destino: Vector3) -> void:
	await _apuntar(destino)
	_c._on_herramienta(herramienta)
	_c._panel._botones_herr[herramienta].button_pressed = true
	_c._actualizar_mira()
	await process_frame
	await physics_frame
	_c._iniciar_pincel()
	var real: bool = _c._pincelando
	if real and _c._ultimo_impacto.distance_to(destino) > 3.0:
		print("AVISO el ratón apunta a %.1f m del objetivo; se aplica el pincel directo"
				% _c._ultimo_impacto.distance_to(destino))
		real = false
	if real:
		for _i in ticks:
			_c._tick_pincel()
	else:
		for _i in ticks:
			_t.aplicar_pincel(destino, _c._radio, _c._fuerza, 0.05, herramienta - 1)
	_c._pincelando = false
	_c._pincel_isla = -1
	_t.actualizar_colision()
	_c._sucio.clear()
	_c._colision_pendiente.clear()
	await process_frame
	await physics_frame


## Arrastra el pincel Mover: el ratón avanza `paso_m` metros por tick sobre el
## terreno para que Construccion calcule el delta real del arrastre.
func _pincel_mover(ticks: int, inicio: Vector3, paso_m: float) -> void:
	await _apuntar(inicio)
	_c._on_herramienta(5)
	_c._panel._botones_herr[5].button_pressed = true
	_c._actualizar_mira()
	await process_frame
	await physics_frame
	_c._iniciar_pincel()
	var real: bool = _c._pincelando
	if real and _c._ultimo_impacto.distance_to(inicio) > 3.0:
		print("AVISO el ratón apunta a %.1f m del montículo; se aplica Mover directo"
				% _c._ultimo_impacto.distance_to(inicio))
		real = false
	if real:
		for i in ticks:
			var destino := inicio + Vector3(paso_m * float(i + 1), 0.0, 0.0)
			var pantalla := _cam.unproject_position(destino)
			get_root().warp_mouse(pantalla)
			var ev := InputEventMouseMotion.new()
			ev.position = pantalla
			ev.global_position = pantalla
			get_root().push_input(ev, true)
			await process_frame
			_c._actualizar_mira()
			_c._tick_pincel()
	else:
		print("AVISO el ratón no alcanza el terreno; se aplica Mover directo")
		var centro := inicio
		for _i in ticks:
			centro += Vector3(paso_m, 0.0, 0.0)
			_t.aplicar_pincel(centro, _c._radio, _c._fuerza, 0.05, Terreno.MOVER,
					Vector3(paso_m, 0.0, 0.0))
	_c._pincelando = false
	_c._pincel_isla = -1
	_t.actualizar_colision()
	_c._sucio.clear()
	_c._colision_pendiente.clear()
	await process_frame
	await physics_frame


func _apuntar(punto_mundo: Vector3) -> void:
	var pantalla := _cam.unproject_position(punto_mundo)
	get_root().warp_mouse(pantalla)
	var ev := InputEventMouseMotion.new()
	ev.position = pantalla
	ev.global_position = pantalla
	get_root().push_input(ev, true)
	await process_frame
	await physics_frame


func _fijar_radio_fuerza(radio: float, fuerza: float) -> void:
	_c._panel._slider_radio.value = radio
	_c._panel._slider_fuerza.value = fuerza
	await process_frame


func _restaurar_base() -> void:
	_t.vertices = _t.vertices_base.duplicate()
	_t.colores.fill(Terreno.COLOR_SIN_ARENA)
	_t._recalcular_normales()
	_t._reconstruir_malla()
	_t.actualizar_colision()
	_c._sucio.clear()
	_c._colision_pendiente.clear()
	await process_frame
	await physics_frame


func _color_cerca(a: Color, b: Color) -> bool:
	var margen := 1.01 / 255.0
	return (absf(a.r - b.r) <= margen and absf(a.g - b.g) <= margen
			and absf(a.b - b.b) <= margen and absf(a.a - b.a) <= margen)


## Centro X local de la máscara de arena, ponderado por alfa.
func _centroide_arena() -> float:
	var suma := 0.0
	var peso := 0.0
	for i in _t.colores.size():
		var a: float = _t.colores[i].a
		if a <= 0.05:
			continue
		suma += _t.vertices[i].x * a
		peso += a
	return suma / peso if peso > 0.0 else 0.0


func _masa_arena() -> float:
	var total := 0.0
	for c in _t.colores:
		total += c.a
	return total


func _max_alfa_cerca(lx: float) -> float:
	var mejor := 0.0
	for i in _t.vertices.size():
		if absf(_t.vertices[i].x - lx) > 0.05 or absf(_t.vertices[i].z) > 0.10:
			continue
		mejor = maxf(mejor, _t.colores[i].a)
	return mejor


## Vértice más cercano a x/z local.
func _indice_cerca(lx: float, lz: float) -> int:
	var mejor := 0
	var mejor_d := 1e9
	for i in _t.vertices.size():
		var v: Vector3 = _t.vertices[i]
		var d := Vector2(v.x - lx, v.z - lz).length()
		if d < mejor_d:
			mejor_d = d
			mejor = i
	return mejor


## Altura media en un anillo local XZ (la plataforma lejos del montículo).
func _media_anillo(r0: float, r1: float) -> float:
	var suma := 0.0
	var n := 0
	for v in _t.vertices:
		var r := Vector2(v.x, v.z).length()
		if r >= r0 and r <= r1:
			suma += v.y
			n += 1
	return suma / float(n) if n > 0 else 0.0


## Centro X del exceso de altura sobre `umbral` cerca del centro de la isla.
func _centroide_exceso(umbral: float) -> float:
	var suma := 0.0
	var peso := 0.0
	for v in _t.vertices:
		if absf(v.x) > 0.2 or absf(v.z) > 0.2:
			continue
		var exceso: float = float(v.y) - umbral
		if exceso <= 0.0:
			continue
		suma += v.x * exceso
		peso += exceso
	return suma / peso if peso > 0.0 else 0.0


## Altura media dentro de una caja local XZ.
func _media_caja(x0: float, x1: float, z0: float, z1: float) -> float:
	var suma := 0.0
	var n := 0
	for v in _t.vertices:
		if v.x >= x0 and v.x <= x1 and v.z >= z0 and v.z <= z1:
			suma += v.y
			n += 1
	return suma / float(n) if n > 0 else 0.0


## Altura de la malla (local, sin escala) en el vértice más cercano a x/z.
func _altura_local(lx: float, lz: float) -> float:
	var mejor := -1.0
	var mejor_d := 1e9
	for v in _t.vertices:
		var d := Vector2(v.x - lx, v.z - lz).length()
		if d < mejor_d:
			mejor_d = d
			mejor = v.y
	return mejor


func _estadisticas(etiqueta: String) -> void:
	var minimo := 1e9
	var maximo := -1e9
	var suma := 0.0
	var n := 0
	for v in _t.vertices:
		if Vector2(v.x, v.z).length() <= 0.24:
			minimo = minf(minimo, v.y)
			maximo = maxf(maximo, v.y)
			suma += v.y
			n += 1
	var media: float = (suma / float(n)) * _t.escala if n > 0 else 0.0
	print("DATOS %s: centro=%.2f m, disco min=%.2f max=%.2f media=%.2f n=%d"
			% [etiqueta, _altura_local(0.0, 0.0) * _t.escala, minimo * _t.escala,
			maximo * _t.escala, media, n])


## Diferencia entre la altura máxima y mínima dentro de un radio local.
func _dispersion(radio_local: float) -> float:
	var minimo := 1e9
	var maximo := -1e9
	for v in _t.vertices:
		if Vector2(v.x, v.z).length() <= radio_local:
			minimo = minf(minimo, v.y)
			maximo = maxf(maximo, v.y)
	return maximo - minimo


func _capturar(nombre: String) -> void:
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var destino := _salida.path_join(nombre)
	var err := get_root().get_texture().get_image().save_png(destino)
	print("CAPTURA ", destino, " err=", err)


func _check(ok: bool, texto: String) -> void:
	if ok:
		_ok += 1
		print("OK   ", texto)
	else:
		_fallos += 1
		print("FALLO ", texto)
