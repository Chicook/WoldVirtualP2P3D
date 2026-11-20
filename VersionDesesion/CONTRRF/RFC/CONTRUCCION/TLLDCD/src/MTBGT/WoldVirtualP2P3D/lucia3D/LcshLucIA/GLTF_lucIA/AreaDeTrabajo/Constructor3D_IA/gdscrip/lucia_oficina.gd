extends Node3D
class_name LuciaOficina
## Oficina 3D construida por código (sin assets externos): suelo, paredes,
## ventana, escritorio con monitor, estantería, planta y luz de techo.
## Todo con primitivas y materiales estándar de Godot.
##
## CORRECCIONES (nov-2026):
##   - Suelo con roughness reducido para ligera reflexión (menos plástico).
##   - Pared fondo: color levemente más cálido para aspecto más acogedor.
##   - Ventana: emisión reducida (evita quemado excesivo en la escena).
##   - SpotLight de techo: spot_angle más amplio + sombra suavizada.
##   - Nueva LuzRelleno lateral (OmniLight fría desde la izquierda del avatar)
##     para evitar el contraste duro de luz cenital sin relleno.
##   - Nueva LuzContrapeso (OmniLight muy tenue desde atrás) para rim light sutil.

const COLOR_PARED := Color(0.60, 0.63, 0.68)   # ligeramente más cálido
const COLOR_SUELO := Color(0.30, 0.28, 0.32)
const COLOR_TECHO := Color(0.90, 0.92, 0.94)
const COLOR_MADERA := Color(0.40, 0.28, 0.16)
const COLOR_CIELO := Color(0.60, 0.78, 1.0)

func _ready() -> void:
	_construir_sala()
	_construir_ventana()
	_construir_escritorio()
	_construir_silla()
	_construir_estanteria()
	_construir_planta()
	_construir_luz_techo()
	_construir_luces_relleno()

func _mat(color: Color, roughness := 0.85, metal := 0.0, emission := Color.BLACK) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = roughness
	m.metallic = metal
	m.metallic_specular = 0.5
	if emission != Color.BLACK:
		m.emission_enabled = true
		m.emission = emission
		m.emission_energy_multiplier = 1.0
	return m

func _caja(nombre: String, tam: Vector3, pos: Vector3, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = nombre
	var box := BoxMesh.new()
	box.size = tam
	mi.mesh = box
	mi.position = pos
	mi.material_override = mat
	add_child(mi)
	return mi

func _construir_sala() -> void:
	# Habitación abierta por el frente (cámara en +Z mirando hacia -Z).
	# Suelo con roughness reducido (0.72) para dar ligera reflexión especular.
	_caja("Suelo", Vector3(8.0, 0.1, 8.0), Vector3(0.0, -0.05, 0.0), _mat(COLOR_SUELO, 0.72))
	_caja("ParedFondo", Vector3(8.0, 3.4, 0.12), Vector3(0.0, 1.7, -4.0), _mat(COLOR_PARED, 0.88))
	_caja("ParedIzq", Vector3(0.12, 3.4, 8.0), Vector3(-4.0, 1.7, 0.0), _mat(COLOR_PARED, 0.88))
	_caja("ParedDer", Vector3(0.12, 3.4, 8.0), Vector3(4.0, 1.7, 0.0), _mat(COLOR_PARED, 0.88))
	_caja("Techo", Vector3(8.0, 0.1, 8.0), Vector3(0.0, 3.4, 0.0), _mat(COLOR_TECHO, 0.90))

func _construir_ventana() -> void:
	# Marco y cristal luminoso en la pared del fondo.
	# Emisión reducida (0.9→0.55) para evitar quemado excesivo del fondo.
	var marco := _mat(Color(0.93, 0.93, 0.94), 0.55)
	var cristal := _mat(COLOR_CIELO, 0.25, 0.0, COLOR_CIELO * 0.55)
	var z := -4.07
	_caja("VentanaCristal", Vector3(2.2, 1.5, 0.06), Vector3(-1.0, 1.85, z), cristal)
	_caja("VentanaBordeSup", Vector3(2.4, 0.1, 0.08), Vector3(-1.0, 2.65, z), marco)
	_caja("VentanaBordeInf", Vector3(2.4, 0.1, 0.08), Vector3(-1.0, 1.05, z), marco)
	_caja("VentanaBordeIzq", Vector3(0.1, 1.5, 0.08), Vector3(-2.15, 1.85, z), marco)
	_caja("VentanaBordeDer", Vector3(0.1, 1.5, 0.08), Vector3(0.15, 1.85, z), marco)
	_caja("VentanaTravesano", Vector3(0.06, 1.5, 0.08), Vector3(-1.0, 1.85, z), marco)

func _construir_escritorio() -> void:
	# Escritorio DELANTE de LucIA, con el monitor mirándola: ella mira su PC
	# y a la cámara por encima de la pantalla. El monitor va al extremo
	# izquierdo para no taparle la cara.
	var z := 0.60
	var mx := -0.80
	var madera := _mat(COLOR_MADERA, 0.65)
	var oscuro := _mat(Color(0.07, 0.08, 0.10), 0.35, 0.25)
	_caja("Tablero", Vector3(1.7, 0.07, 0.8), Vector3(0.0, 0.76, z), madera)
	for sx in [-0.75, 0.75]:
		for sz in [-0.32, 0.32]:
			_caja("Pata_%d_%d" % [int(sx * 100), int(sz * 100)],
				Vector3(0.06, 0.76, 0.06), Vector3(sx, 0.38, z + sz), oscuro)

	# Monitor: pantalla hacia -Z (hacia LucIA); desde la cámara se ve la trasera.
	var pantalla := _mat(Color(0.04, 0.10, 0.22), 0.18, 0.12, Color(0.12, 0.35, 0.95))
	_caja("MonitorMarco", Vector3(0.76, 0.48, 0.05), Vector3(mx, 1.20, z - 0.13), oscuro)
	_caja("MonitorPantalla", Vector3(0.70, 0.42, 0.04), Vector3(mx, 1.20, z - 0.17), pantalla)
	_caja("MonitorMastil", Vector3(0.06, 0.22, 0.06), Vector3(mx, 0.94, z - 0.20), oscuro)
	_caja("MonitorBase", Vector3(0.32, 0.03, 0.22), Vector3(mx, 0.81, z - 0.20), oscuro)

func _construir_silla() -> void:
	# Silla de oficina delante del escritorio; el asiento queda a 0,45 m para
	# que coincida con la pose sentada de lucia_personaje.gd.
	var z := -0.34
	var tela := _mat(Color(0.20, 0.23, 0.30), 0.9)
	var metal := _mat(Color(0.10, 0.11, 0.13), 0.4, 0.4)
	_caja("SillaAsiento", Vector3(0.54, 0.07, 0.50), Vector3(0.0, 0.415, z), tela)
	_caja("SillaRespaldo", Vector3(0.50, 0.55, 0.06), Vector3(0.0, 0.72, z - 0.24), tela)
	# Patas
	_caja("SillaPataID", Vector3(0.05, 0.38, 0.05), Vector3(-0.22, 0.19, z + 0.19), metal)
	_caja("SillaPataII", Vector3(0.05, 0.38, 0.05), Vector3(-0.22, 0.19, z - 0.19), metal)
	_caja("SillaPataDD", Vector3(0.05, 0.38, 0.05), Vector3(0.22, 0.19, z + 0.19), metal)
	_caja("SillaPataDI", Vector3(0.05, 0.38, 0.05), Vector3(0.22, 0.19, z - 0.19), metal)
	# Travesaños
	_caja("SillaTravesanoI", Vector3(0.44, 0.04, 0.04), Vector3(0.0, 0.12, z + 0.19), metal)
	_caja("SillaTravesanoD", Vector3(0.44, 0.04, 0.04), Vector3(0.0, 0.12, z - 0.19), metal)

func _construir_estanteria() -> void:
	var madera := _mat(COLOR_MADERA, 0.7)
	var x := -3.3
	var z := -1.4
	_caja("EstanteriaIzq", Vector3(0.08, 2.2, 0.5), Vector3(x - 0.45, 1.1, z), madera)
	_caja("EstanteriaDer", Vector3(0.08, 2.2, 0.5), Vector3(x + 0.45, 1.1, z), madera)
	_caja("EstanteriaSup", Vector3(0.98, 0.06, 0.5), Vector3(x, 2.2, z), madera)
	_caja("EstanteriaInf", Vector3(0.98, 0.06, 0.5), Vector3(x, 0.05, z), madera)
	# Balda central y algunos libros de colores.
	_caja("EstanteriaBalda", Vector3(0.98, 0.05, 0.5), Vector3(x, 1.1, z), madera)
	var colores := [
		Color(0.75, 0.2, 0.2), Color(0.2, 0.55, 0.75), Color(0.85, 0.65, 0.2),
		Color(0.3, 0.65, 0.35), Color(0.6, 0.35, 0.7),
	]
	for i in colores.size():
		_caja("Libro%d" % i, Vector3(0.12, 0.55, 0.38), Vector3(x - 0.34 + float(i) * 0.16, 1.38, z), _mat(colores[i], 0.7))

func _construir_planta() -> void:
	var maceta := _mat(Color(0.55, 0.3, 0.2), 0.9)
	var hoja := _mat(Color(0.2, 0.55, 0.25), 0.9)
	var pos := Vector3(2.9, 0.0, 1.0)
	var pot := CylinderMesh.new()
	pot.top_radius = 0.2
	pot.bottom_radius = 0.14
	pot.height = 0.32
	var mi_pot := MeshInstance3D.new()
	mi_pot.mesh = pot
	mi_pot.position = pos + Vector3(0.0, 0.16, 0.0)
	mi_pot.material_override = maceta
	add_child(mi_pot)
	# Follaje: esferas achatadas apiladas.
	var follaje := SphereMesh.new()
	follaje.radius = 0.34
	follaje.height = 0.62
	for i in 3:
		var mi := MeshInstance3D.new()
		mi.mesh = follaje
		mi.position = pos + Vector3(0.0, 0.42 + float(i) * 0.22, 0.0)
		mi.scale = Vector3(1.0, 1.0, 1.0) * (1.0 - float(i) * 0.18)
		mi.material_override = hoja
		add_child(mi)

func _construir_luz_techo() -> void:
	var panel := _mat(Color.WHITE, 0.3, 0.0, Color(1.0, 0.98, 0.9))
	_caja("LuzPanel", Vector3(1.6, 0.06, 0.5), Vector3(0.0, 3.36, 0.6), panel)
	var luz := SpotLight3D.new()
	luz.name = "LuzTecho"
	luz.position = Vector3(0.0, 3.2, 0.6)
	luz.rotation_degrees = Vector3(-90.0, 0.0, 0.0)
	luz.light_color = Color(1.0, 0.97, 0.92)
	luz.light_energy = 1.8    # reducido: 2.4→1.8 para evitar sobre-exposición
	luz.spot_range = 7.0
	luz.spot_angle = 65.0     # ampliado: 55→65° → cono más difuso, menos duro
	luz.shadow_enabled = true
	add_child(luz)

func _construir_luces_relleno() -> void:
	## Relleno lateral izquierdo (desde el lado derecho del avatar = +X de la cámara).
	## Luz fría-azulada suave que contrarresta el calor de la luz de techo.
	var relleno_lat := OmniLight3D.new()
	relleno_lat.name = "LuzRellenoLateral"
	relleno_lat.position = Vector3(-2.2, 1.6, 1.4)
	relleno_lat.light_color = Color(0.72, 0.82, 1.0)   # azulado frío
	relleno_lat.light_energy = 0.9
	relleno_lat.omni_range = 5.5
	relleno_lat.shadow_enabled = false   # relleno suave, sin sombra
	add_child(relleno_lat)

	## Rim light trasero (contorno) desde detrás-arriba.
	## Da separación visual entre el avatar y la pared del fondo.
	var rim := OmniLight3D.new()
	rim.name = "LuzRim"
	rim.position = Vector3(0.6, 2.4, -1.8)
	rim.light_color = Color(0.95, 0.95, 1.0)   # casi blanco, muy sutil
	rim.light_energy = 0.55
	rim.omni_range = 4.0
	rim.shadow_enabled = false
	add_child(rim)
