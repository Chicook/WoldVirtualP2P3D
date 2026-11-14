extends Node3D
class_name LuciaPersonaje
## Personaje LucIA montado sobre el .glb con rig Mixamo (65 huesos + skin)
## y morph "BOCA" para el lipsync.
##
## Arquitectura (reescrita):
##  - No construye esqueletos ni pesos por código: el .glb ya trae skin real.
##  - Una sola capa de animación (este script) escribe las rotaciones de hueso
##    cada frame. Se elimina el conflicto de tres AnimationPlayer peleando por
##    las mismas pistas y los saltos al detener gestos.
##  - Las rotaciones se piden en ejes del MUNDO y se convierten a la pose local
##    del hueso con `rest_local * (R_global^-1 * Q * R_global)`. Godot guarda la
##    rotación local completa (no un delta), y cada hueso Mixamo tiene su propia
##    orientación: esta fórmula evita depender de esos ejes internos.
##  - IDLE, gestos y parpadeo se componen por suma de cuaterniones con
##    envolventes suaves: no hay saltos al empezar/terminar de hablar.
##  - El lipsync mueve el morph BOCA. Las UVs de los labios se remapean al
##    arte de labios que ya trae el atlas (antes apuntaban a zonas blancas).
##
## API pública usada por lucia_cliente.gd:
##   obtener_aabb_mundo(), fijar_apertura_boca(v),
##   iniciar_gesticulacion(), detener_gesticulacion()

const ALTURA_OBJETIVO := 1.75

# --- Zona de la boca en espacio de malla (medida sobre el .glb riggeado)
const BOCA_CENTRO := Vector3(0.0, 1.506, 0.096)
const BOCA_ANCHO := 0.036            # ancho del interior oscuro de boca abierta
const BOCA_ALTO := 0.017

# --- Postura / movimiento
const BRAZO_REPOSO := 1.05         # rad: bajar los brazos desde la T-pose
const CODO_REPOSO := 0.22
const AMP_RESPIRACION := 0.020
const AMP_BALANCEO := 0.018
const AMP_CABEZA := 0.030
const AMP_PARPADEO := 0.055
const DURACION_PARPADEO := 0.16
const GESTO_ATAQUE := 0.30         # s para entrar en gesto
const GESTO_RELEASE := 0.65        # s para salir de gesto
const DURACION_SENTARSE := 0.85    # s para el cruce de pie -> sentada
const ALTURA_SENTADO := 0.420      # descenso de la cadera al sentarse (asiento a 0.45)
const ANGULO_MUSLO_SENTADO := -1.55   # muslo horizontal (si no, los pies se hunden)
const ANGULO_RODILLA_SENTADO := 1.55  # espinilla vertical
const ANGULO_PIE_SENTADO := 0.0       # planta plana
const PASO_CADERA := 0.36           # cuánto retrocede para sentarse en la silla
const AMPLITUD_PASO := 0.42         # rad de balanceo del muslo al andar
const VELOCIDAD_ANDAR := 0.75       # m/s

# Nombres cortos de hueso (se buscan por sufijo para tolerar prefijos Mixamo).
const HUESOS := {
	"cadera": "Hips",
	"columna1": "Spine",
	"columna2": "Spine1",
	"columna3": "Spine2",
	"cuello": "Neck",
	"cabeza": "Head",
	"hombro_i": "LeftShoulder", "brazo_i": "LeftArm",
	"antebrazo_i": "LeftForeArm", "mano_i": "LeftHand",
	"hombro_d": "RightShoulder", "brazo_d": "RightArm",
	"antebrazo_d": "RightForeArm", "mano_d": "RightHand",
	"muslo_i": "LeftUpLeg", "rodilla_i": "LeftLeg",
	"pie_i": "LeftFoot", "dedo_i": "LeftToeBase",
	"muslo_d": "RightUpLeg", "rodilla_d": "RightLeg",
	"pie_d": "RightFoot", "dedo_d": "RightToeBase",
}

@onready var malla: MeshInstance3D = _buscar_malla(self)
@onready var esqueleto: Skeleton3D = _buscar_esqueleto(self)

var _idx := {}                      # nombre corto -> índice de hueso
var _reposo := {}                   # nombre corto -> Quaternion de reposo GLOBAL
var _reposo_local := {}             # nombre corto -> Quaternion de reposo local
var _idx_boca := -1
var _cavidad: MeshInstance3D
var _pesos_boca := {}               # índice de hueso -> peso en la zona de la boca
var _bind_de_hueso := {}            # índice de hueso -> índice de bind del skin

var _t := 0.0
var _apertura := 0.0
var _peso_gesto := 0.0
var _gesto_objetivo := 0.0
var _blink_restante := 0.0
var _proximo_blink := 3.0
var _listo := false

# --- locomoción / silla
var _posicion_base := Vector3.ZERO
var _destino := Vector3.ZERO
var _caminando := false
var _peso_caminando := 0.0
var _fase_paso := 0.0
var _sentado_objetivo := false
var _peso_sentado := 0.0

func _ready() -> void:
	_normalizar_escala()
	_localizar_piezas()
	if esqueleto == null or malla == null:
		push_warning("LucIA: el modelo no tiene skin/esqueleto; se muestra en reposo.")
		return
	_mapear_huesos()
	_localizar_boca()
	_reparar_uvs_boca()
	_crear_cavidad_boca()
	esqueleto.reset_bone_poses()
	# Aplicar la pose YA: si no, el primer frame (que en D3D12 puede tardar
	# por la compilación de shaders) enseña la T-pose y parece que "sube los brazos".
	_aplicar_pose()
	esqueleto.force_update_all_bone_transforms()
	_actualizar_cavidad()
	_listo = true

# ---------------------------------------------------------------- búsqueda
func _buscar_malla(n: Node) -> MeshInstance3D:
	if n is MeshInstance3D and (n as MeshInstance3D).skin != null:
		return n as MeshInstance3D
	for c in n.get_children():
		var r := _buscar_malla(c)
		if r != null:
			return r
	return null

func _buscar_esqueleto(n: Node) -> Skeleton3D:
	if n is Skeleton3D:
		return n as Skeleton3D
	for c in n.get_children():
		var r := _buscar_esqueleto(c)
		if r != null:
			return r
	return null

func _localizar_piezas() -> void:
	if malla == null:
		malla = _buscar_malla(self)
	if esqueleto == null:
		esqueleto = _buscar_esqueleto(self)

func _mapear_huesos() -> void:
	for alias in HUESOS:
		var sufijo: String = HUESOS[alias]
		var idx := _hueso_por_sufijo(sufijo)
		if idx < 0:
			continue
		_idx[alias] = idx
		var base := esqueleto.get_bone_global_rest(idx).basis.orthonormalized()
		_reposo[alias] = base.get_rotation_quaternion()
		_reposo_local[alias] = esqueleto.get_bone_rest(idx).basis.orthonormalized().get_rotation_quaternion()

func _hueso_por_sufijo(sufijo: String) -> int:
	for i in esqueleto.get_bone_count():
		if str(esqueleto.get_bone_name(i)).ends_with(sufijo):
			return i
	return -1

func _localizar_boca() -> void:
	var m := malla.mesh
	if m == null:
		return
	for i in m.get_blend_shape_count():
		if str(m.get_blend_shape_name(i)) == "BOCA":
			_idx_boca = i
			break

func _reparar_uvs_boca() -> void:
	## La geometría de los labios apuntaba a zonas blancas del atlas. La cara
	## pintada (con labios) está en UV ~(0.4945, 0.5575); remapeamos SOLO los
	## vértices del morph BOCA a ese dibujo. No se toca la textura ni el resto
	## de la malla, así que el cambio es reversible y no depende de assets.
	if _idx_boca < 0:
		return
	var m := malla.mesh as ArrayMesh
	if m == null or m.get_surface_count() == 0:
		return
	var formas := m.surface_get_blend_shape_arrays(0)
	if formas.is_empty():
		return
	var arr: Array = m.surface_get_arrays(0)
	var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var uvs: PackedVector2Array = arr[Mesh.ARRAY_TEX_UV]
	if uvs.size() != verts.size():
		return
	var morph: PackedVector3Array = (formas[0] as Array)[Mesh.ARRAY_VERTEX]
	var n := 0
	for i in verts.size():
		if verts[i].y < 1.3:
			continue
		if (morph[i] - verts[i]).length() <= 0.0002:
			continue
		uvs[i] = Vector2(
			0.4930 + verts[i].x * 0.60,
			0.5572 - (verts[i].y - 1.506) * 0.50)
		n += 1
	if n == 0:
		return
	arr[Mesh.ARRAY_TEX_UV] = uvs
	# `surface_get_blend_shape_arrays()` devuelve posiciones ABSOLUTAS, pero
	# `add_surface_from_arrays()` las espera como DELTAS: si se pasan tal cual,
	# el morph se suma dos veces y al abrir la boca el personaje se escala y la
	# cara se sale de cámara. Convertimos a delta respetando el formato
	# (vértice, normal y tangente) que exige el ArrayMesh.
	var formas_delta: Array = []
	for forma in formas:
		var f: Array = (forma as Array).duplicate(true)
		var fv: PackedVector3Array = f[Mesh.ARRAY_VERTEX]
		for i in fv.size():
			fv[i] = fv[i] - verts[i]
		f[Mesh.ARRAY_VERTEX] = fv
		if f[Mesh.ARRAY_NORMAL] != null and arr[Mesh.ARRAY_NORMAL] != null:
			var fn: PackedVector3Array = f[Mesh.ARRAY_NORMAL]
			var bn: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
			for i in mini(fn.size(), bn.size()):
				fn[i] = fn[i] - bn[i]
			f[Mesh.ARRAY_NORMAL] = fn
		if f[Mesh.ARRAY_TANGENT] != null and arr[Mesh.ARRAY_TANGENT] != null:
			var ft: PackedFloat32Array = f[Mesh.ARRAY_TANGENT]
			var bt: PackedFloat32Array = arr[Mesh.ARRAY_TANGENT]
			for i in mini(ft.size(), bt.size()):
				ft[i] = ft[i] - bt[i]
			f[Mesh.ARRAY_TANGENT] = ft
		formas_delta.append(f)
	var nuevo := ArrayMesh.new()
	for b in m.get_blend_shape_count():
		nuevo.add_blend_shape(m.get_blend_shape_name(b))
	nuevo.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr, formas_delta)
	nuevo.surface_set_material(0, m.surface_get_material(0))
	malla.mesh = nuevo

# ---------------------------------------------------------------- boca

# ---------------------------------------------------------------- interior de la boca
func _crear_cavidad_boca() -> void:
	## Interior oscuro DETRÁS de los labios pintados: al abrir el morph se ve
	## la boca, no la malla blanca del interior de la cabeza. Se ancla a la
	## transformación de piel de la zona (mezcla Head/Neck), no a un hueso rígido.
	if _idx_boca < 0:
		return
	_calcular_pesos_boca()
	if _pesos_boca.is_empty():
		return
	_cavidad = MeshInstance3D.new()
	_cavidad.name = "CavidadBoca"
	var plano := QuadMesh.new()
	plano.size = Vector2(BOCA_ANCHO, BOCA_ALTO)
	_cavidad.mesh = plano
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = _textura_ovalo_boca()
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	_cavidad.material_override = mat
	_cavidad.visible = false
	esqueleto.add_child(_cavidad)
	_actualizar_cavidad()

func _calcular_pesos_boca() -> void:
	var m := malla.mesh
	if m == null or malla.skin == null:
		return
	var arr: Array = m.surface_get_arrays(0)
	var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var huesos: PackedInt32Array = arr[Mesh.ARRAY_BONES]
	var pesos: PackedFloat32Array = arr[Mesh.ARRAY_WEIGHTS]
	var skin := malla.skin
	for i in range(0, skin.get_bind_count()):
		# Los skins del glTF usan binds por NOMBRE: get_bind_bone() devuelve -1.
		var nombre := str(skin.get_bind_name(i))
		var hueso := esqueleto.find_bone(nombre)
		if hueso < 0:
			hueso = skin.get_bind_bone(i)
		if hueso >= 0:
			_bind_de_hueso[hueso] = i

	var acum := {}
	for i in verts.size():
		if verts[i].distance_to(BOCA_CENTRO) > 0.030:
			continue
		for k in 4:
			var w := pesos[i * 4 + k]
			if w <= 0.01:
				continue
			var bind_idx := huesos[i * 4 + k]
			if bind_idx < 0 or bind_idx >= skin.get_bind_count():
				continue
			var hueso := _hueso_de_bind(bind_idx)
			if hueso >= 0:
				acum[hueso] = acum.get(hueso, 0.0) + w

	var total := 0.0
	for k in acum:
		total += acum[k]
	if total <= 0.0001:
		return
	for k in acum:
		_pesos_boca[k] = acum[k] / total

func _hueso_de_bind(bind_idx: int) -> int:
	var nombre := str(malla.skin.get_bind_name(bind_idx))
	var hueso := esqueleto.find_bone(nombre)
	if hueso < 0:
		hueso = malla.skin.get_bind_bone(bind_idx)
	return hueso

func _actualizar_cavidad() -> void:
	if _cavidad == null or _pesos_boca.is_empty():
		return
	var suma := Transform3D(Basis(Vector3.ZERO, Vector3.ZERO, Vector3.ZERO), Vector3.ZERO)
	for hueso in _pesos_boca:
		var bind_idx: int = _bind_de_hueso.get(hueso, -1)
		if bind_idx < 0:
			continue
		var w: float = _pesos_boca[hueso]
		var m: Transform3D = esqueleto.get_bone_global_pose(hueso) * malla.skin.get_bind_pose(bind_idx)
		suma.basis.x += m.basis.x * w
		suma.basis.y += m.basis.y * w
		suma.basis.z += m.basis.z * w
		suma.origin += m.origin * w
	var b := suma.basis.orthonormalized()
	var pos := suma * BOCA_CENTRO
	# 6 mm por delante del centro del morro: detrás de la superficie de los
	# labios (así los bordes quedan tapados) y delante de la malla blanca.
	_cavidad.transform = Transform3D(b, pos + b.z.normalized() * 0.006)

func _textura_ovalo_boca() -> ImageTexture:
	## Interior de boca: oscuro arriba (paladar), algo más cálido abajo (lengua),
	## con borde suave. Generado por código, sin assets.
	var w := 96
	var h := 48
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	for y in h:
		for x in w:
			var u := (float(x) + 0.5) / float(w) * 2.0 - 1.0
			var v := (float(y) + 0.5) / float(h) * 2.0 - 1.0
			var d := u * u + v * v
			if d < 1.0:
				var a := clampf((1.0 - d) * 6.0, 0.0, 1.0)
				var c := Color(0.11, 0.015, 0.020)
				if v > 0.35:
					c = Color(0.34, 0.09, 0.09)   # lengua
				img.set_pixel(x, y, Color(c.r, c.g, c.b, a))
			else:
				img.set_pixel(x, y, Color(0, 0, 0, 0))
	return ImageTexture.create_from_image(img)

func fijar_apertura_boca(valor: float) -> void:
	_apertura = clampf(valor, 0.0, 1.0)
	if _idx_boca < 0:
		return
	malla.set_blend_shape_value(_idx_boca, _apertura)
	if _cavidad != null:
		_cavidad.visible = _apertura > 0.05
		_cavidad.scale = Vector3(1.0, 0.25 + 0.75 * _apertura, 1.0)

func abrir_boca() -> void:
	fijar_apertura_boca(1.0)

func cerrar_boca() -> void:
	fijar_apertura_boca(0.0)

# ---------------------------------------------------------------- gestos
func iniciar_gesticulacion() -> void:
	_gesto_objetivo = 1.0

func detener_gesticulacion() -> void:
	# No resetea huesos: la envolvente baja suavemente y evita el tirón final.
	_gesto_objetivo = 0.0

# ---------------------------------------------------------------- silla / andar
func sentarse() -> void:
	_caminando = false
	_sentado_objetivo = true

func levantarse() -> void:
	_sentado_objetivo = false

func esta_sentada() -> bool:
	return _sentado_objetivo

func caminar_hasta(punto: Vector3) -> void:
	# Solo en el plano; la altura la decide la pose.
	_sentado_objetivo = false
	_destino = Vector3(punto.x, 0.0, punto.z)
	_caminando = true

func caminar_adelante(metros: float) -> void:
	caminar_hasta(_posicion_base + Vector3(0.0, 0.0, metros))

func volver() -> void:
	caminar_hasta(Vector3.ZERO)

# ---------------------------------------------------------------- animación
func _process(delta: float) -> void:
	if not _listo:
		return
	_t += delta
	var vel := 1.0 / GESTO_ATAQUE if _gesto_objetivo > 0.5 else 1.0 / GESTO_RELEASE
	_peso_gesto = move_toward(_peso_gesto, _gesto_objetivo, delta * vel)
	_actualizar_parpadeo(delta)
	_actualizar_desplazamiento(delta)
	_aplicar_pose()
	esqueleto.force_update_all_bone_transforms()
	_actualizar_cavidad()

func _actualizar_desplazamiento(delta: float) -> void:
	var objetivo := 1.0 if _sentado_objetivo else 0.0
	_peso_sentado = move_toward(_peso_sentado, objetivo, delta / DURACION_SENTARSE)

	if _caminando and _peso_sentado < 0.5:
		var plano := Vector3(_destino.x - _posicion_base.x, 0.0, _destino.z - _posicion_base.z)
		var distancia := plano.length()
		if distancia > 0.02:
			var paso := minf(VELOCIDAD_ANDAR * delta, distancia)
			_posicion_base += plano / distancia * paso
			_fase_paso += delta * TAU * 1.7
			_peso_caminando = move_toward(_peso_caminando, 1.0, delta / 0.25)
		else:
			_caminando = false
	else:
		_peso_caminando = move_toward(_peso_caminando, 0.0, delta / 0.35)

	# Al sentarse retrocede PASO_CADERA para quedar sobre el asiento.
	position = _posicion_base + Vector3(0.0, 0.0, -PASO_CADERA * _peso_sentado)

func _actualizar_parpadeo(delta: float) -> void:
	if _blink_restante > 0.0:
		_blink_restante = maxf(_blink_restante - delta, 0.0)
		return
	_proximo_blink -= delta
	if _proximo_blink <= 0.0:
		_blink_restante = DURACION_PARPADEO
		_proximo_blink = randf_range(2.8, 6.0)

func _blink() -> float:
	if _blink_restante <= 0.0:
		return 0.0
	var fase := 1.0 - _blink_restante / DURACION_PARPADEO
	return sin(fase * PI)

func _aplicar_pose() -> void:
	var t := _t
	var resp := sin(TAU * t / 4.2)
	var bal := sin(TAU * t / 9.0)
	var cabeceo := sin(TAU * t / 7.3)
	var giro_cab := sin(TAU * t / 5.9 + 0.8)
	var g := _peso_gesto

	# --- respiración y balanceo (idle)
	_poner("columna3", Quaternion(Vector3.RIGHT, AMP_RESPIRACION * resp))
	_poner("columna2", Quaternion(Vector3.RIGHT, AMP_RESPIRACION * 0.55 * resp))
	_poner("cadera", Quaternion(Vector3.BACK, AMP_BALANCEO * bal))

	# --- cabeza: idle + gesto + parpadeo (suma de cuaterniones)
	var q_cab_idle := Quaternion(Vector3.UP, AMP_CABEZA * giro_cab) * Quaternion(Vector3.RIGHT, AMP_CABEZA * 0.6 * cabeceo)
	var q_cab_gesto := Quaternion(Vector3.UP, 0.10 * sin(TAU * t / 3.1)) * Quaternion(Vector3.RIGHT, 0.08 * sin(TAU * t / 1.9 + 0.4))
	# Sentada mira hacia su monitor (a su derecha, -X), pero al hablar vuelve
	# en buena parte hacia la cámara.
	var q_cab_silla := Quaternion(Vector3.UP, -0.32 * _peso_sentado * (1.0 - 0.75 * g))
	var q_blink := Quaternion(Vector3.RIGHT, AMP_PARPADEO * _blink())
	_poner("cabeza", q_cab_silla * q_cab_idle * q_cab_gesto, q_blink)
	_poner("cuello", Quaternion(Vector3.UP, AMP_CABEZA * 0.35 * giro_cab))

	# --- brazos: reposo + gesto + balanceo al andar + manos en los muslos sentada
	var pulso_d := 0.5 + 0.5 * sin(TAU * t / 2.6)
	var pulso_i := 0.5 + 0.5 * sin(TAU * t / 3.9 + 1.1)
	var andar := _peso_caminando
	var swing_i := 0.22 * sin(_fase_paso + PI) * andar
	var swing_d := 0.22 * sin(_fase_paso) * andar
	var sentada := _peso_sentado

	_poner("brazo_i", Quaternion(Vector3.RIGHT, -0.16 * g * pulso_i + swing_i)
		* Quaternion(Vector3.BACK, -BRAZO_REPOSO + 0.012 * bal))
	_poner("brazo_d", Quaternion(Vector3.RIGHT, -0.16 * g * pulso_d + swing_d)
		* Quaternion(Vector3.BACK, BRAZO_REPOSO - 0.012 * bal))
	_poner("hombro_i", Quaternion(Vector3.RIGHT, -0.05 * g * pulso_i))
	_poner("hombro_d", Quaternion(Vector3.RIGHT, -0.05 * g * pulso_d))
	_poner("antebrazo_i", Quaternion(Vector3.RIGHT, -CODO_REPOSO - 0.70 * g * pulso_i - 0.55 * sentada))
	_poner("antebrazo_d", Quaternion(Vector3.RIGHT, -CODO_REPOSO - 0.55 * g * pulso_d - 0.55 * sentada))

	# --- piernas (andar / sentarse)
	if _idx.has("cadera"):
		var hips_idx: int = _idx["cadera"]
		var rest := esqueleto.get_bone_rest(hips_idx).origin
		var bob := 0.010 * sin(2.0 * _fase_paso) * andar
		esqueleto.set_bone_pose_position(hips_idx, rest + Vector3(0.0, -ALTURA_SENTADO * sentada + bob, 0.0))
	_aplicar_pierna("muslo_i", "rodilla_i", "pie_i", 0.0)
	_aplicar_pierna("muslo_d", "rodilla_d", "pie_d", PI)

func _aplicar_pierna(muslo: String, rodilla: String, pie: String, desfase: float) -> void:
	var s := sin(_fase_paso + desfase)
	var andar := _peso_caminando
	var sentada := _peso_sentado
	# Al andar: muslo adelante/atrás, rodilla que se dobla al recoger el pie.
	var a_muslo := -AMPLITUD_PASO * s * andar
	var a_rodilla := (0.12 + 0.55 * maxf(0.0, -s)) * andar
	var a_pie := -0.20 * s * andar
	_poner(muslo, Quaternion(Vector3.RIGHT, lerpf(a_muslo, ANGULO_MUSLO_SENTADO, sentada)))
	_poner(rodilla, Quaternion(Vector3.RIGHT, lerpf(a_rodilla, ANGULO_RODILLA_SENTADO, sentada)))
	_poner(pie, Quaternion(Vector3.RIGHT, lerpf(a_pie, ANGULO_PIE_SENTADO, sentada)))

# Aplica una rotación pedida en ejes del mundo al hueso.
# En Godot la pose es la rotación LOCAL COMPLETA (incluye el reposo del hueso),
# por eso se compone: pose = rest_local * (R_global^-1 * Q_world * R_global).
func _poner(alias: String, q_mundo: Quaternion, q_extra := Quaternion.IDENTITY) -> void:
	if not _idx.has(alias):
		return
	var idx: int = _idx[alias]
	var r_local: Quaternion = _reposo_local[alias]
	var r_glob: Quaternion = _reposo[alias]
	var delta := r_glob.inverse() * (q_extra * q_mundo) * r_glob
	esqueleto.set_bone_pose_rotation(idx, (r_local * delta).normalized())

# ---------------------------------------------------------------- utilidades
func obtener_aabb_mundo() -> AABB:
	var total := AABB()
	var primera := true
	for n in _mallas():
		var mi := n as MeshInstance3D
		if mi.mesh == null:
			continue
		var caja: AABB = mi.global_transform * mi.mesh.get_aabb()
		if primera:
			total = caja
			primera = false
		else:
			total = total.merge(caja)
	return total

func _mallas() -> Array[MeshInstance3D]:
	var res: Array[MeshInstance3D] = []
	_recoger(self, res)
	return res

func _recoger(n: Node, res: Array[MeshInstance3D]) -> void:
	if n is MeshInstance3D:
		res.append(n as MeshInstance3D)
	for c in n.get_children():
		_recoger(c, res)

func _normalizar_escala() -> void:
	scale = Vector3.ONE
	var aabb := obtener_aabb_mundo()
	var alto := aabb.size.y
	if alto > 0.001:
		var factor := ALTURA_OBJETIVO / alto
		if absf(factor - 1.0) > 0.01:
			scale = Vector3.ONE * factor
