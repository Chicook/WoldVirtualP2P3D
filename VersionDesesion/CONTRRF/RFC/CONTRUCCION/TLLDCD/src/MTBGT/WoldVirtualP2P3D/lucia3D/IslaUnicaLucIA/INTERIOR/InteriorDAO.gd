extends Node3D
## Interior de la Isla Única LucIA: atrio de la DAO bajo la cúpula.
##
## Sustituye el interior crudo del GLB (sin suelo ni luz) por un salón
## diseñado: plataforma sobre la meseta, terraza perimetral con rampas,
## despacho de LucIA bajo el óculo, carrusel de avatares y portal.
##
## Todo se construye con primitivas y materiales estándar de Godot, igual que
## `LuciaOficina`, para no depender de assets externos: el GLB sólo aporta la
## isla y la cubierta metálica de la cúpula.

const SUELO_Y := 41.7
const RADIO_ATRIO := 31.0
const RADIO_OFICINA := 7.2
const ALTURA_DAIS := 0.5
const RUTA_LUCIA := "res://lucia3D/GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIAbsIA.tscn"

const COLOR_ACERO := Color(0.045, 0.055, 0.075)
const COLOR_ACERO_CLARO := Color(0.09, 0.11, 0.145)
const COLOR_ORO := Color(0.72, 0.54, 0.18)
const COLOR_CIAN := Color(0.12, 0.72, 1.0)
const COLOR_MADERA := Color(0.36, 0.26, 0.16)

var _lucia: Node3D = null
var _aro_holo: Node3D = null
var _artefactos: Array[Node3D] = []
var _t := 0.0


func _ready() -> void:
	_construir_suelo()
	_construir_terrazas()
	_construir_pilares()
	_construir_vitrinas()
	_construir_boveda()
	_construir_oficina()
	_construir_iluminacion()
	_cargar_lucia()
	var perfil := ConfigFile.new()
	if perfil.load("user://registro.cfg") == OK and FileAccess.file_exists("user://cuenta.json"):
		var cuenta = JSON.parse_string(FileAccess.get_file_as_string("user://cuenta.json"))
		if cuenta is Dictionary and not str(cuenta.get("cuenta_hash", "")).is_empty() \
				and not str(perfil.get_value("jugador", "avatar_scene", "")).is_empty():
			configurar_asamblea()


func _process(delta: float) -> void:
	_t += delta
	if _aro_holo != null:
		_aro_holo.rotation.y += delta * 0.35
	for artefacto in _artefactos:
		if is_instance_valid(artefacto):
			artefacto.rotation.y += delta * 0.8


# ---------------------------------------------------------------------------
# Materiales y primitivas
# ---------------------------------------------------------------------------

func _mat(color: Color, roughness := 0.7, metal := 0.0,
		emision := Color.BLACK, energia := 1.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = roughness
	m.metallic = metal
	if emision != Color.BLACK:
		m.emission_enabled = true
		m.emission = emision
		m.emission_energy_multiplier = energia
	return m


func _caja(nombre: String, tam: Vector3, pos: Vector3, mat: Material,
		rot := Vector3.ZERO, padre: Node3D = null) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = nombre
	var caja := BoxMesh.new()
	caja.size = tam
	mi.mesh = caja
	mi.material_override = mat
	mi.position = pos
	mi.rotation = rot
	(padre if padre != null else self).add_child(mi)
	return mi


func _cilindro(nombre: String, radio_sup: float, radio_inf: float, alto: float,
		pos: Vector3, mat: Material, padre: Node3D = null) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = nombre
	var cil := CylinderMesh.new()
	cil.top_radius = radio_sup
	cil.bottom_radius = radio_inf
	cil.height = alto
	cil.radial_segments = 96
	mi.mesh = cil
	mi.material_override = mat
	mi.position = pos
	(padre if padre != null else self).add_child(mi)
	return mi


func _aro(nombre: String, radio_int: float, radio_ext: float, pos: Vector3,
		mat: Material, padre: Node3D = null) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = nombre
	var toro := TorusMesh.new()
	toro.inner_radius = radio_int
	toro.outer_radius = radio_ext
	toro.rings = 128
	toro.ring_segments = 8
	mi.mesh = toro
	mi.material_override = mat
	mi.position = pos
	(padre if padre != null else self).add_child(mi)
	return mi


func _colision(nombre: String, forma: Shape3D, pos: Vector3, rot := Vector3.ZERO,
		padre: Node3D = null) -> StaticBody3D:
	var cuerpo := StaticBody3D.new()
	cuerpo.name = nombre
	var nodo := CollisionShape3D.new()
	nodo.shape = forma
	cuerpo.add_child(nodo)
	cuerpo.position = pos
	cuerpo.rotation = rot
	(padre if padre != null else self).add_child(cuerpo)
	return cuerpo


func _texto(nombre: String, contenido: String, pos: Vector3, tam: int, color: Color,
		billboard := true, ancho := 0.006) -> Label3D:
	var etiqueta := Label3D.new()
	etiqueta.name = nombre
	etiqueta.text = contenido
	etiqueta.font_size = tam
	etiqueta.pixel_size = ancho
	etiqueta.modulate = color
	etiqueta.outline_modulate = Color(0.01, 0.03, 0.06, 1.0)
	etiqueta.outline_size = 10
	etiqueta.billboard = BaseMaterial3D.BILLBOARD_ENABLED if billboard else BaseMaterial3D.BILLBOARD_DISABLED
	etiqueta.position = pos
	add_child(etiqueta)
	return etiqueta


# ---------------------------------------------------------------------------
# Suelo y terraza
# ---------------------------------------------------------------------------

func _construir_suelo() -> void:
	# Plataforma maciza sobre la meseta: cubre el anillo de terreno que asoma
	# dentro de la cúpula y deja el salón a 1,5 m sobre la isla.
	var piso := _cilindro("PisoAtrio", RADIO_ATRIO, RADIO_ATRIO + 0.5, 1.5,
			Vector3(0.0, SUELO_Y - 0.75, 0.0), _mat(COLOR_ACERO, 0.38, 0.55))
	piso.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	var forma := CylinderShape3D.new()
	forma.radius = RADIO_ATRIO
	forma.height = 1.5
	_colision("ColisionPisoAtrio", forma, Vector3(0.0, SUELO_Y - 0.75, 0.0))

	var oro := _mat(COLOR_ORO, 0.28, 0.85, COLOR_ORO, 0.55)
	var cian := _mat(Color(0.02, 0.08, 0.1), 0.3, 0.2, COLOR_CIAN, 2.6)
	_aro("AroOficina", RADIO_OFICINA + 0.15, RADIO_OFICINA + 0.5, Vector3(0.0, SUELO_Y + 0.03, 0.0), oro)
	_aro("AroSalon", 14.05, 14.35, Vector3(0.0, SUELO_Y + 0.03, 0.0), cian)
	_aro("AroTerraza", 21.45, 21.8, Vector3(0.0, SUELO_Y + 0.03, 0.0), oro)
	_aro("AroBorde", 30.35, 30.7, Vector3(0.0, SUELO_Y + 0.03, 0.0), oro)

	# Radial de energía entre el despacho y el carrusel.
	for i in 8:
		var ang := deg_to_rad(22.5 + 45.0 * i)
		var centro := Vector3(sin(ang), 0.0, cos(ang)) * 10.85
		_caja("Radial_%d" % i, Vector3(0.16, 0.03, 6.8),
				Vector3(centro.x, SUELO_Y + 0.04, centro.z), cian, Vector3(0.0, ang, 0.0))


func _construir_terrazas() -> void:
	# Cuatro rampas anchas en los puntos cardinales: suben de la isla a la
	# terraza de la DAO (40,2 -> 41,7) atravesando los accesos de la cúpula.
	var metal := _mat(COLOR_ACERO_CLARO, 0.42, 0.45)
	var oro := _mat(COLOR_ORO, 0.3, 0.85, COLOR_ORO, 0.5)
	# El terreno sube distinto en cada punto cardinal: la rampa de Este arranca
	# en 40,33 y la de Oeste en 41,18. Cada perfil ajusta su pendiente para que
	# el borde alto siga a ras de la terraza y la boca no quede enterrada.
	var perfiles := [
		{"inclinacion": atan2(1.5, 5.0), "y": 40.75, "baranda": 41.05},
		{"inclinacion": asin(1.37 / 5.6), "y": 40.869558, "baranda": 41.169558},
		{"inclinacion": atan2(1.5, 5.0), "y": 40.75, "baranda": 41.05},
		{"inclinacion": asin(0.52 / 5.6), "y": 41.290648, "baranda": 41.590648},
	]
	for i in 4:
		# Las colisiones viven en la escena; el constructor sólo añade lo visual.
		var nombre_rampa: String = ["RampaSur", "RampaEste", "RampaNorte", "RampaOeste"][i]
		var nodo := get_node_or_null(nombre_rampa) as Node3D
		if nodo == null:
			nodo = Node3D.new()
			nodo.name = nombre_rampa
			nodo.rotation.y = [0.0, -PI * 0.5, PI, PI * 0.5][i]
			add_child(nodo)
		var inclinacion: float = perfiles[i]["inclinacion"]
		var y_rampa: float = perfiles[i]["y"]
		var y_baranda: float = perfiles[i]["baranda"]
		# El borde alto queda a ras del suelo del atrio: sin escalón, se sale
		# caminando de la terraza por las cuatro rampas.
		_caja("Superficie", Vector3(7.2, 0.3, 5.6), Vector3(0.0, y_rampa, 33.45), metal,
				Vector3(inclinacion, 0.0, 0.0), nodo)
		if nodo.get_node_or_null("ColisionRampa") == null:
			var forma := BoxShape3D.new()
			forma.size = Vector3(7.2, 0.3, 5.6)
			_colision("ColisionRampa", forma, Vector3(0.0, y_rampa, 33.45),
					Vector3(inclinacion, 0.0, 0.0), nodo)
		for lado in [-3.45, 3.45]:
			_caja("Baranda", Vector3(0.18, 0.26, 5.6), Vector3(lado, y_baranda, 33.45), oro,
					Vector3(inclinacion, 0.0, 0.0), nodo)
		if nodo.get_node_or_null("ColisionBarandas") == null:
			# La baranda visual también frena: ningún borde de rampa queda abierto.
			var barandas := StaticBody3D.new()
			barandas.name = "ColisionBarandas"
			nodo.add_child(barandas)
			for lado in [-3.45, 3.45]:
				var forma_baranda := BoxShape3D.new()
				forma_baranda.size = Vector3(0.18, 0.26, 5.6)
				var baranda := CollisionShape3D.new()
				baranda.name = "BarandaIzq" if lado < 0.0 else "BarandaDer"
				baranda.shape = forma_baranda
				baranda.position = Vector3(lado, y_baranda, 33.45)
				baranda.rotation.x = inclinacion
				barandas.add_child(baranda)

	# Petril de la terraza, con huecos en las cuatro rampas.
	var petril := _mat(COLOR_ACERO_CLARO, 0.4, 0.5, Color(0.02, 0.1, 0.14), 0.6)
	var remate := _mat(COLOR_ORO, 0.3, 0.85, COLOR_ORO, 0.5)
	for i in 32:
		var ang := TAU * float(i) / 32.0
		if i % 8 == 0:
			continue
		var centro := Vector3(sin(ang), 0.0, cos(ang)) * 30.4
		# Los dos tramos que flanquean cada boca se corren hacia fuera: la rampa
		# mide 7,2 m y el hueco de un solo tramo sólo deja 5,97 m.
		var resto := i % 8
		if resto == 1 or resto == 7:
			var tangente := Vector3(cos(ang), 0.0, -sin(ang))
			centro += tangente * (0.55 if resto == 1 else -0.55)
		_caja("Petril_%d" % i, Vector3(5.4, 0.9, 0.45),
				Vector3(centro.x, SUELO_Y + 0.45, centro.z), petril, Vector3(0.0, ang, 0.0))
		_caja("RematePetril_%d" % i, Vector3(5.4, 0.1, 0.55),
				Vector3(centro.x, SUELO_Y + 0.95, centro.z), remate, Vector3(0.0, ang, 0.0))


func _construir_pilares() -> void:
	var metal := _mat(COLOR_ACERO_CLARO, 0.35, 0.7)
	var oro := _mat(COLOR_ORO, 0.3, 0.85, COLOR_ORO, 0.6)
	var cian := _mat(Color(0.02, 0.1, 0.14), 0.3, 0.2, COLOR_CIAN, 2.8)
	for i in 8:
		var ang := deg_to_rad(22.5 + 45.0 * i)
		var centro := Vector3(sin(ang), 0.0, cos(ang)) * 19.8
		_caja("Pilar_%d" % i, Vector3(0.9, 5.2, 0.9),
				Vector3(centro.x, SUELO_Y + 2.6, centro.z), metal)
		_caja("Capitel_%d" % i, Vector3(1.4, 0.18, 1.4),
				Vector3(centro.x, SUELO_Y + 5.29, centro.z), oro)
		var interior := Vector3(-centro.x, 0.0, -centro.z).normalized()
		_caja("Filamento_%d" % i, Vector3(0.14, 4.0, 0.14),
				Vector3(centro.x + interior.x * 0.5, SUELO_Y + 2.5, centro.z + interior.z * 0.5), cian)
		var orbe := _cilindro("Farol_%d" % i, 0.26, 0.34, 0.5,
				Vector3(centro.x, SUELO_Y + 5.85, centro.z),
				_mat(Color(0.4, 0.75, 0.9), 0.2, 0.3, COLOR_CIAN, 2.2))
		orbe.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_caja("Varilla_%d" % i, Vector3(0.05, 1.4, 0.05),
				Vector3(centro.x, SUELO_Y + 6.75, centro.z), metal)


func _construir_vitrinas() -> void:
	# Cuatro vitrinas de la DAO entre los pilares: votación, tesoro,
	# propuestas y registro. Cristal con marco dorado y pieza flotante.
	var cristal := _mat(Color(0.1, 0.35, 0.5, 0.16), 0.08, 0.1, Color(0.1, 0.45, 0.6), 0.6)
	cristal.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	var oro := _mat(COLOR_ORO, 0.3, 0.85, COLOR_ORO, 0.7)
	var titulos := ["VOTACIÓN", "TESORO", "PROPUESTAS", "REGISTRO"]
	for i in 4:
		var ang := deg_to_rad(45.0 + 90.0 * i)
		var centro := Vector3(sin(ang), 0.0, cos(ang)) * 18.6
		var base := _caja("VitrinaBase_%d" % i, Vector3(2.6, 0.5, 2.6),
				Vector3(centro.x, SUELO_Y + 0.25, centro.z), _mat(COLOR_ACERO_CLARO, 0.35, 0.6),
				Vector3(0.0, ang, 0.0))
		base.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		_caja("VitrinaCristal_%d" % i, Vector3(2.2, 2.4, 2.2),
				Vector3(centro.x, SUELO_Y + 1.7, centro.z), cristal, Vector3(0.0, ang, 0.0))
		for esquina in [Vector2(-1.12, -1.12), Vector2(1.12, -1.12), Vector2(-1.12, 1.12), Vector2(1.12, 1.12)]:
			var desfase := Vector3(esquina.x, 0.0, esquina.y).rotated(Vector3.UP, ang)
			_caja("VitrinaEsquina_%d" % i, Vector3(0.07, 2.4, 0.07),
					Vector3(centro.x + desfase.x, SUELO_Y + 1.7, centro.z + desfase.z), oro)
		_caja("VitrinaTapa_%d" % i, Vector3(2.4, 0.12, 2.4),
				Vector3(centro.x, SUELO_Y + 2.95, centro.z), oro, Vector3(0.0, ang, 0.0))
		var pieza := MeshInstance3D.new()
		pieza.name = "Pieza_%d" % i
		var esfera := SphereMesh.new()
		esfera.radius = 0.34
		esfera.height = 0.68
		esfera.radial_segments = 4
		esfera.rings = 2
		pieza.mesh = esfera
		pieza.material_override = _mat(COLOR_ORO, 0.2, 0.7, COLOR_ORO, 2.0)
		pieza.position = Vector3(centro.x, SUELO_Y + 1.85, centro.z)
		add_child(pieza)
		_artefactos.append(pieza)
		var texto := _texto("RotuloVitrina_%d" % i, titulos[i],
				Vector3(centro.x, SUELO_Y + 3.5, centro.z), 68, Color(0.95, 0.82, 0.45), true, 0.009)
		texto.name = "RotuloVitrina_%d" % i


# ---------------------------------------------------------------------------
# Bóveda: aros suspendidos y haz de luz del óculo
# ---------------------------------------------------------------------------

func _construir_boveda() -> void:
	# Aros holográficos colgados bajo la cúpula: dan escala al salón y enmarcan
	# el rótulo DAO del despacho sin tocar la cubierta del GLB.
	var oro := _mat(COLOR_ORO, 0.25, 0.8, COLOR_ORO, 1.4)
	var cian := _mat(Color(0.02, 0.1, 0.14), 0.3, 0.2, COLOR_CIAN, 2.4)
	_aro("BovedaAroAlto", 17.4, 17.56, Vector3(0.0, 46.4, 0.0), oro)
	_aro("BovedaAroMedio", 11.6, 11.74, Vector3(0.0, 47.9, 0.0), oro)
	_aro("BovedaAroLuz", 6.4, 6.5, Vector3(0.0, 48.9, 0.0), cian)

	_construir_tambor()

	# Haz volumétrico del óculo sobre el estrado de LucIA.
	var haz := MeshInstance3D.new()
	haz.name = "HazOculo"
	var cono := CylinderMesh.new()
	cono.top_radius = 2.4
	cono.bottom_radius = 7.0
	cono.height = 8.2
	cono.radial_segments = 64
	haz.mesh = cono
	var velo := StandardMaterial3D.new()
	velo.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	velo.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	velo.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	velo.cull_mode = BaseMaterial3D.CULL_DISABLED
	velo.albedo_color = Color(0.5, 0.78, 1.0, 0.02)
	haz.material_override = velo
	haz.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	haz.position = Vector3(0.0, 46.2, 0.0)
	add_child(haz)


func _construir_tambor() -> void:
	# Muro calado del atrio en dos cuerpos, con montantes dorados y huecos en
	# los cuatro accesos. El cristal de la cúpula deslumbra a la altura de los
	# ojos; este tambor lo tapa y da la escala de un salón real.
	const RADIO_TAMBOR := 21.2
	const ALTO_TAMBOR := 5.4
	var metal := _mat(COLOR_ACERO, 0.42, 0.55)
	var metal_claro := _mat(COLOR_ACERO_CLARO, 0.35, 0.65)
	var oro := _mat(COLOR_ORO, 0.3, 0.85, COLOR_ORO, 0.5)
	var cian := _mat(Color(0.02, 0.1, 0.14), 0.3, 0.2, COLOR_CIAN, 2.2)
	var ancho := TAU * RADIO_TAMBOR / 24.0 - 0.35
	for i in 24:
		var ang := TAU * float(i) / 24.0
		if i % 6 != 0:
			var centro := Vector3(sin(ang) * RADIO_TAMBOR, 0.0, cos(ang) * RADIO_TAMBOR)
			_caja("TamborBajo_%d" % i, Vector3(ancho, 3.1, 0.24),
					Vector3(centro.x, SUELO_Y + 1.55, centro.z), metal, Vector3(0.0, ang, 0.0))
			_caja("TamborLuz_%d" % i, Vector3(ancho, 0.08, 0.26),
					Vector3(centro.x, SUELO_Y + 3.16, centro.z), cian, Vector3(0.0, ang, 0.0))
			_caja("TamborAlto_%d" % i, Vector3(ancho, 2.1, 0.24),
					Vector3(centro.x, SUELO_Y + 4.3, centro.z), metal_claro, Vector3(0.0, ang, 0.0))
			_caja("TamborRemate_%d" % i, Vector3(ancho + 0.1, 0.12, 0.34),
					Vector3(centro.x, SUELO_Y + ALTO_TAMBOR, centro.z), oro, Vector3(0.0, ang, 0.0))
			var forma := BoxShape3D.new()
			forma.size = Vector3(ancho, ALTO_TAMBOR, 0.24)
			_colision("ColisionTambor_%d" % i, forma,
					Vector3(centro.x, SUELO_Y + ALTO_TAMBOR * 0.5, centro.z), Vector3(0.0, ang, 0.0))
		# Montante en cada junta; en los huecos hace de jamba del acceso.
		var junta := TAU * (float(i) - 0.5) / 24.0
		var borde := Vector3(sin(junta) * RADIO_TAMBOR, 0.0, cos(junta) * RADIO_TAMBOR)
		_caja("Montante_%d" % i, Vector3(0.16, ALTO_TAMBOR + 0.16, 0.34),
				Vector3(borde.x, SUELO_Y + (ALTO_TAMBOR + 0.16) * 0.5, borde.z), oro,
				Vector3(0.0, junta, 0.0))
	_aro("CornisaTambor", RADIO_TAMBOR - 0.08, RADIO_TAMBOR + 0.12,
			Vector3(0.0, SUELO_Y + ALTO_TAMBOR, 0.0), oro)
	_aro("ZocaloTambor", RADIO_TAMBOR - 0.06, RADIO_TAMBOR + 0.1,
			Vector3(0.0, SUELO_Y + 0.08, 0.0), cian)


# ---------------------------------------------------------------------------
# Despacho de LucIA
# ---------------------------------------------------------------------------

func _construir_oficina() -> void:
	var metal := _mat(COLOR_ACERO_CLARO, 0.35, 0.55)
	var oro := _mat(COLOR_ORO, 0.28, 0.85, COLOR_ORO, 0.7)
	var cian := _mat(Color(0.02, 0.1, 0.14), 0.3, 0.2, COLOR_CIAN, 2.6)
	var madera := _mat(COLOR_MADERA, 0.55)

	var dais := _cilindro("DaisOficina", RADIO_OFICINA, RADIO_OFICINA + 0.25, ALTURA_DAIS,
			Vector3(0.0, SUELO_Y + ALTURA_DAIS * 0.5, 0.0), metal)
	dais.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	var forma_dais := CylinderShape3D.new()
	forma_dais.radius = RADIO_OFICINA
	forma_dais.height = ALTURA_DAIS
	_colision("ColisionDais", forma_dais, Vector3(0.0, SUELO_Y + ALTURA_DAIS * 0.5, 0.0))
	_aro("AroDais", RADIO_OFICINA - 0.05, RADIO_OFICINA + 0.12,
			Vector3(0.0, SUELO_Y + ALTURA_DAIS + 0.01, 0.0), oro)

	# Rampa de acceso al estrado por el sur (única entrada al despacho).
	var rampa := _caja("RampaDais", Vector3(3.6, 0.16, 1.9), Vector3(0.0, SUELO_Y + 0.27, 7.8), oro,
			Vector3(atan2(ALTURA_DAIS, 1.9), 0.0, 0.0))
	rampa.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	if get_node_or_null("ColisionRampaDais") == null:
		var forma_rampa := BoxShape3D.new()
		forma_rampa.size = Vector3(3.6, 0.16, 1.9)
		_colision("ColisionRampaDais", forma_rampa, Vector3(0.0, SUELO_Y + 0.27, 7.8),
				Vector3(atan2(ALTURA_DAIS, 1.9), 0.0, 0.0))

	var alto := SUELO_Y + ALTURA_DAIS
	# Escritorio curvo: mesa de recepción frente a LucIA.
	for i in 3:
		var x := (i - 1) * 1.62
		var z := 3.4 + absf(i - 1) * 0.55
		_caja("Mesa_%d" % i, Vector3(1.75, 0.12, 1.1), Vector3(x, alto + 0.95, z), madera)
		_caja("MesaFrente_%d" % i, Vector3(1.75, 0.78, 0.1), Vector3(x, alto + 0.48, z + 0.5),
				_mat(Color(0.06, 0.07, 0.1), 0.35, 0.4))
		_caja("MesaFilo_%d" % i, Vector3(1.8, 0.05, 1.2), Vector3(x, alto + 1.02, z), oro)
	var forma_mesa := BoxShape3D.new()
	forma_mesa.size = Vector3(5.3, 0.95, 1.1)
	_colision("ColisionMesa", forma_mesa, Vector3(0.0, alto + 0.48, 3.45))

	# Holo sobre la mesa, orientado al visitante.
	_caja("HoloMesa", Vector3(2.1, 0.9, 0.06), Vector3(0.0, alto + 1.55, 3.45),
			_mat(Color(0.02, 0.09, 0.13), 0.2, 0.2, COLOR_CIAN, 1.6))
	var holo_texto := _texto("HoloMesaTexto", "DAO · SESIÓN ABIERTA",
			Vector3(0.0, alto + 2.25, 3.45), 44, Color(0.55, 0.9, 1.0), true, 0.006)
	holo_texto.name = "HoloMesaTexto"

	# Pantallas de datos a la espalda de LucIA, visibles desde el sur.
	var titulos := ["TESORO DE LA DAO", "VOTACIONES ABIERTAS"]
	for i in 2:
		var x := -2.6 + 5.2 * i
		_caja("PanelDatos_%d" % i, Vector3(2.2, 1.5, 0.07), Vector3(x, alto + 2.15, -3.6),
				_mat(Color(0.02, 0.08, 0.12), 0.25, 0.25, Color(0.08, 0.4, 0.6), 1.2))
		_caja("PanelMarco_%d" % i, Vector3(2.3, 0.08, 0.1), Vector3(x, alto + 2.93, -3.6), oro)
		var texto := _texto("PanelTexto_%d" % i, titulos[i], Vector3(x, alto + 2.15, -3.55),
				30, Color(0.6, 0.92, 1.0), true, 0.004)
		texto.name = "PanelTexto_%d" % i

	# Aro holográfico giratorio sobre LucIA y rótulos del despacho.
	_aro_holo = MeshInstance3D.new()
	_aro_holo.name = "AroHoloLucIA"
	var toro := TorusMesh.new()
	toro.inner_radius = 2.1
	toro.outer_radius = 2.28
	toro.rings = 96
	toro.ring_segments = 10
	(_aro_holo as MeshInstance3D).mesh = toro
	(_aro_holo as MeshInstance3D).material_override = _mat(COLOR_ORO, 0.22, 0.7, COLOR_ORO, 2.2)
	_aro_holo.position = Vector3(0.0, alto + 3.9, 0.0)
	add_child(_aro_holo)
	_texto("RotuloDespacho", "DESPACHO DE LUCÍA", Vector3(0.0, alto + 5.6, 0.0),
			96, Color(0.95, 0.84, 0.5), true, 0.006)
	_texto("RotuloSede", "SEDE DE LA DAO · ISLA ÚNICA", Vector3(0.0, alto + 4.8, 0.0),
			44, Color(0.6, 0.9, 1.0), true, 0.005)
	_texto("HoloDAO", "DAO", Vector3(0.0, 50.1, 0.0), 220, Color(0.45, 0.9, 1.0), true, 0.012)

	# Taburetes de visitante y racimos de cristal en el borde del estrado.
	for lado in [-2.4, 2.4]:
		_cilindro("Taburete_%s" % lado, 0.46, 0.5, 0.55,
				Vector3(lado, alto + 0.275, 5.6), _mat(Color(0.1, 0.13, 0.18), 0.7, 0.2))
	for i in 4:
		var ang := deg_to_rad(45.0 + 90.0 * i)
		var centro := Vector3(sin(ang), 0.0, cos(ang)) * 6.2
		for j in 3:
			var desfase := Vector3(sin(float(j) * 2.1), 0.0, cos(float(j) * 2.1)) * 0.45
			var alto_cristal := 0.7 + 0.3 * float(j % 2)
			var cristal := MeshInstance3D.new()
			cristal.name = "Cristal_%d_%d" % [i, j]
			var cono := CylinderMesh.new()
			cono.top_radius = 0.0
			cono.bottom_radius = 0.16
			cono.height = alto_cristal
			cono.radial_segments = 6
			cristal.mesh = cono
			cristal.material_override = _mat(COLOR_ORO if j % 2 == 0 else COLOR_CIAN, 0.2, 0.4,
					COLOR_ORO if j % 2 == 0 else COLOR_CIAN, 1.6)
			cristal.position = Vector3(centro.x + desfase.x, alto + alto_cristal * 0.5, centro.z + desfase.z)
			add_child(cristal)


func _cargar_lucia() -> void:
	var recurso := load(RUTA_LUCIA)
	if not (recurso is PackedScene):
		push_warning("[InteriorDAO] no carga " + RUTA_LUCIA)
		return
	# `lucia_personaje.gd` escribe su posición local cada frame (caminar/sentarse),
	# así que vive dentro de un anclaje que fija el sitio del despacho.
	var anclaje := Node3D.new()
	anclaje.name = "AnclajeLucIA"
	anclaje.position = Vector3(0.0, SUELO_Y + ALTURA_DAIS, -0.6)
	add_child(anclaje)
	_lucia = (recurso as PackedScene).instantiate() as Node3D
	if _lucia == null:
		return
	_lucia.name = "LucIA"
	anclaje.add_child(_lucia)
	var forma := CapsuleShape3D.new()
	forma.radius = 0.35
	forma.height = 1.5
	_colision("ColisionLucIA", forma, Vector3(0.0, SUELO_Y + ALTURA_DAIS + 0.85, -0.6))


func _construir_iluminacion() -> void:
	# El foco cenital se queda suave: a más energía, la cubierta metálica del
	# GLB devuelve un reflejo que quema media bóveda en pantalla.
	var foco := SpotLight3D.new()
	foco.name = "FocoCenital"
	foco.position = Vector3(0.0, 51.0, 0.0)
	foco.rotation = Vector3(-PI * 0.5, 0.0, 0.0)
	foco.light_color = Color(1.0, 0.93, 0.82)
	foco.light_energy = 3.6
	foco.spot_range = 42.0
	foco.spot_angle = 42.0
	foco.shadow_enabled = true
	add_child(foco)

	var relleno := OmniLight3D.new()
	relleno.name = "LuzDespacho"
	relleno.position = Vector3(0.0, SUELO_Y + 3.4, 1.2)
	relleno.light_color = Color(1.0, 0.86, 0.7)
	relleno.light_energy = 2.6
	relleno.omni_range = 13.0
	add_child(relleno)

	for i in 4:
		var ang := deg_to_rad(45.0 + 90.0 * i)
		var centro := Vector3(sin(ang), 0.0, cos(ang)) * 16.5
		var luz := OmniLight3D.new()
		luz.name = "LuzSalon_%d" % i
		luz.position = Vector3(centro.x, SUELO_Y + 4.2, centro.z)
		luz.light_color = Color(0.35, 0.72, 1.0)
		luz.light_energy = 2.2
		luz.omni_range = 16.0
		add_child(luz)


# ---------------------------------------------------------------------------
# API para pruebas y para el resto del mundo
# ---------------------------------------------------------------------------

func configurar_asamblea() -> void:
	# Reaplicar la desactivación incluso cuando el mobiliario ya existe.
	var nodo_carrusel := carrusel()
	if nodo_carrusel != null:
		if nodo_carrusel.has_method("set_auto_abrir"):
			nodo_carrusel.call("set_auto_abrir", false)
		_desactivar_zona_asamblea(nodo_carrusel)
	var zona := zona_personalizacion()
	if zona != null:
		_desactivar_zona_asamblea(zona)
	var rotulo := get_node_or_null("RotuloVitrina_3") as Label3D
	if rotulo != null:
		rotulo.text = "ASAMBLEAS"
	if get_node_or_null("AsambleaDAO") != null:
		return

	var asamblea := Node3D.new()
	asamblea.name = "AsambleaDAO"
	asamblea.position.y = SUELO_Y
	add_child(asamblea)
	var madera := _mat(COLOR_MADERA, 0.55)
	var metal := _mat(COLOR_ACERO_CLARO, 0.35, 0.55)
	var oro := _mat(COLOR_ORO, 0.28, 0.85)
	var tapizado := _mat(Color(0.035, 0.16, 0.22), 0.9)

	# Mesas sobre el aro de radio 14. El sector sur queda abierto: incluso
	# los extremos de los asientos permanecen por debajo de z=10.
	# Los sillones interiores quedan fuera del despacho y de su rampa.
	for i in 9:
		var ang := deg_to_rad(60.0 + 30.0 * i)
		var radial := Vector3(sin(ang), 0.0, cos(ang))
		var mesa := Node3D.new()
		mesa.name = "MesaAsamblea_%02d" % i
		mesa.position = radial * 14.0
		mesa.rotation.y = ang
		asamblea.add_child(mesa)
		_pieza_asamblea("Tablero", Vector3(2.8, 0.14, 1.2), Vector3(0.0, 0.97, 0.0), madera, mesa)
		_pieza_asamblea("Filo", Vector3(2.86, 0.04, 1.26), Vector3(0.0, 1.06, 0.0), oro, mesa)
		for lado in [-0.95, 0.95]:
			_cilindro("Pata_%s" % lado, 0.09, 0.09, 0.9, Vector3(lado, 0.45, 0.0), metal, mesa)
			var forma_pata := CylinderShape3D.new()
			forma_pata.radius = 0.09
			forma_pata.height = 0.9
			_colision("ColisionPata_%s" % lado, forma_pata, Vector3(lado, 0.45, 0.0), Vector3.ZERO, mesa)
			_pieza_asamblea("Pie_%s" % lado, Vector3(0.45, 0.1, 0.9), Vector3(lado, 0.05, 0.0), metal, mesa)

		for j in 2:
			var silla := Node3D.new()
			silla.name = "Silla_%02d_%d" % [i, j]
			silla.position = radial * 16.0 + Vector3((j * 2 - 1) * 0.8, 0.0, 0.0).rotated(Vector3.UP, ang)
			silla.rotation.y = ang
			asamblea.add_child(silla)
			_construir_asiento_asamblea(silla, false, metal, tapizado, oro)

		var sillon := Node3D.new()
		sillon.name = "Sillon_%02d" % i
		sillon.position = radial * 11.5
		sillon.rotation.y = ang + PI
		asamblea.add_child(sillon)
		_construir_asiento_asamblea(sillon, true, metal, tapizado, oro)


func _desactivar_zona_asamblea(nodo: Node) -> void:
	if nodo is Node3D:
		(nodo as Node3D).hide()
	elif nodo is CanvasItem:
		(nodo as CanvasItem).hide()
	if nodo is Area3D:
		(nodo as Area3D).set_deferred("monitoring", false)
	if nodo is CollisionShape3D:
		(nodo as CollisionShape3D).set_deferred("disabled", true)
	nodo.process_mode = Node.PROCESS_MODE_DISABLED
	nodo.set_process(false)
	nodo.set_physics_process(false)
	nodo.set_process_input(false)
	nodo.set_process_unhandled_input(false)
	nodo.set_process_unhandled_key_input(false)
	# También desactivar descendientes con PROCESS_MODE_ALWAYS propio.
	for hijo in nodo.get_children():
		_desactivar_zona_asamblea(hijo)


func _pieza_asamblea(nombre: String, tam: Vector3, pos: Vector3,
		mat: Material, padre: Node3D) -> void:
	_caja(nombre, tam, pos, mat, Vector3.ZERO, padre)
	var forma := BoxShape3D.new()
	forma.size = tam
	_colision("Colision" + nombre, forma, pos, Vector3.ZERO, padre)


func _construir_asiento_asamblea(padre: Node3D, es_sillon: bool,
		metal: Material, tapizado: Material, oro: Material) -> void:
	var ancho := 1.3 if es_sillon else 0.7
	var fondo := 1.05 if es_sillon else 0.75
	_pieza_asamblea("Asiento", Vector3(ancho, 0.22, fondo), Vector3(0.0, 0.55, 0.0), tapizado, padre)
	# Frente local -Z: las sillas miran al centro y los sillones a la mesa.
	_pieza_asamblea("Respaldo", Vector3(ancho, 0.85, 0.18), Vector3(0.0, 1.02, fondo * 0.5 - 0.09), tapizado, padre)
	_pieza_asamblea("RemateRespaldo", Vector3(ancho, 0.05, 0.2), Vector3(0.0, 1.47, fondo * 0.5 - 0.09), oro, padre)
	for x in [-1.0, 1.0]:
		for z in [-1.0, 1.0]:
			_pieza_asamblea("Pata_%s_%s" % [x, z], Vector3(0.09, 0.44, 0.09),
					Vector3(x * (ancho * 0.5 - 0.1), 0.22, z * (fondo * 0.5 - 0.1)), metal, padre)
		if es_sillon:
			_pieza_asamblea("Brazo_%s" % x, Vector3(0.18, 0.35, fondo),
					Vector3(x * (ancho * 0.5 - 0.09), 0.82, 0.0), tapizado, padre)


func lucia() -> Node3D:
	return _lucia


func carrusel() -> Node:
	return get_node_or_null("CarruselDAO")


func portal() -> Node:
	return get_node_or_null("PortalDAO")


func zona_personalizacion() -> Node3D:
	return get_node_or_null("ZonaPersonalizacion") as Node3D


func aro_holo() -> Node3D:
	return _aro_holo
