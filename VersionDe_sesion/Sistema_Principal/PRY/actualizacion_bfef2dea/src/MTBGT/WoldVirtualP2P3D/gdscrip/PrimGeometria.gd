extends RefCounted
## Generador paramétrico de mallas de prim al estilo OpenSim/Second Life.
##
## Modelo: un PERFIL (curva o polígono) se barre por un CAMINO y sobre el
## resultado se aplican los parámetros de construcción de SL:
##   - corte (Path Cut: recorte del barrido)
##   - hueco (Hollow: vaciado interior)
##   - giro (Twist: torsión a lo largo del barrido)
##   - estrechado (Taper: reduce la parte alta)
##   - cizalla (Top Shear: inclina la cara superior)
##
## El barrido es lineal (extrusión) para cubo/cilindro/cono, y de revolución
## para esfera/toro. Todo es determinista y sin estado compartido: los mismos
## parámetros producen la misma malla en todos los peers.
##
## La malla se genera UNITARIA (1x1x1, centrada en el origen) para no romper el
## sistema de escala ni las colisiones existentes.

const LADOS := 32      ## Segmentos alrededor del perfil (cilindro, esfera...).
const ANILLOS := 20    ## Segmentos a lo largo del barrido (altura o ángulo).

const EXTRUSION := ["cubo", "cilindro", "cono"]
const REVOLUCION := ["esfera", "toro"]

## Claves de parámetro y su valor neutro. Neutro = malla idéntica a la primitiva
## original (la que ya generaba Prims.crear_malla).
const CLAVES := [
	"corte_ini", "corte_fin", "hueco", "hueco_forma",
	"giro", "giro_fin", "estrechado_x", "estrechado_y", "cizalla_x", "cizalla_y",
]
const HUELLAS := {
	"corte_ini": 0.0, "corte_fin": 1.0, "hueco": 0.0, "hueco_forma": 0,
	"giro": 0.0, "giro_fin": 0.0, "estrechado_x": 0.0, "estrechado_y": 0.0,
	"cizalla_x": 0.0, "cizalla_y": 0.0,
}
## Formas del agujero interior (solo informativo/a futuro): redondo, cuadrado, triángulo.
const FORMAS_HUECO := ["redondo", "cuadrado", "triangulo"]

## Si una malla sale con las caras al revés, se voltea aquí de golpe. Lo valida
## la galería visual de tests.
const INVERTIR := true


static func es_tipo_soportado(tipo: String) -> bool:
	return EXTRUSION.has(tipo) or REVOLUCION.has(tipo)


## Parámetros normalizados y saneados. Siempre devuelve todas las claves.
static func normalizar(params) -> Dictionary:
	var p: Dictionary = HUELLAS.duplicate()
	if params is Dictionary:
		for k in CLAVES:
			if params.has(k):
				p[k] = params[k]
	p["corte_ini"] = clampf(float(p["corte_ini"]), 0.0, 1.0)
	p["corte_fin"] = clampf(float(p["corte_fin"]), 0.0, 1.0)
	# El corte nunca es más fino que un 2 % del barrido (evita mallas vacías).
	if float(p["corte_fin"]) - float(p["corte_ini"]) < 0.02:
		p["corte_fin"] = minf(1.0, float(p["corte_ini"]) + 0.02)
	p["hueco"] = clampf(float(p["hueco"]), 0.0, 0.95)
	p["hueco_forma"] = clampi(int(p["hueco_forma"]), 0, FORMAS_HUECO.size() - 1)
	p["giro"] = clampf(float(p["giro"]), -360.0, 360.0)
	p["giro_fin"] = clampf(float(p["giro_fin"]), -360.0, 360.0)
	p["estrechado_x"] = clampf(float(p["estrechado_x"]), -1.0, 1.0)
	p["estrechado_y"] = clampf(float(p["estrechado_y"]), -1.0, 1.0)
	p["cizalla_x"] = clampf(float(p["cizalla_x"]), -1.0, 1.0)
	p["cizalla_y"] = clampf(float(p["cizalla_y"]), -1.0, 1.0)
	return p


## True si los parámetros no cambian la forma (se puede usar la primitiva rápida).
static func params_neutros(params) -> bool:
	if not (params is Dictionary) or params.is_empty():
		return true
	var p := normalizar(params)
	for k in CLAVES:
		if k == "hueco_forma":
			continue
		if not is_equal_approx(float(p[k]), float(HUELLAS[k])):
			return false
	return true


## Malla paramétrica para el tipo y sus parámetros. Devuelve ArrayMesh (posible-
## mente vacío si el tipo no está soportado).
static func generar(tipo: String, params := {}) -> ArrayMesh:
	if not es_tipo_soportado(tipo):
		return ArrayMesh.new()
	var p := normalizar(params)
	var tris := PackedVector3Array()
	if EXTRUSION.has(tipo):
		tris = _extruir(tipo, p)
	else:
		tris = _revolucionar(tipo, p)
	var suave := tipo != "cubo"
	return _malla(tris, suave)


# ------------------------------------------------------------------ extrusión

## Barrido lineal: el perfil (en el plano XZ) se extruye a lo alto de Y.
static func _extruir(tipo: String, p: Dictionary) -> PackedVector3Array:
	var perfil := _perfil_extrusion(tipo)
	perfil = _a_ccw(perfil)
	var n := perfil.size()
	var m := ANILLOS
	var y0 := -0.5 + float(p["corte_ini"])
	var y1 := -0.5 + float(p["corte_fin"])
	# El cono arranca ancho abajo y afilado arriba; taper y demás se aplican
	# encima multiplicando esta base.
	var es_cono := tipo == "cono"
	var hueco := float(p["hueco"])
	var tris := PackedVector3Array()

	var anillos: Array = []
	for j in m:
		var u := float(j) / float(m - 1)
		var y := lerpf(y0, y1, u)
		var base := lerpf(1.0, 0.04, u) if es_cono else 1.0
		var s := base * (1.0 - float(p["estrechado_x"]) * u)
		var sz := base * (1.0 - float(p["estrechado_y"]) * u)
		var ang := deg_to_rad(lerpf(float(p["giro"]), float(p["giro_fin"]), u))
		var ox := float(p["cizalla_x"]) * u
		var oz := float(p["cizalla_y"]) * u
		var fila := PackedVector3Array()
		for i in n:
			var q: Vector2 = perfil[i]
			var rx := q.x * s
			var rz := q.y * sz
			# Giro alrededor del eje vertical (Y).
			var gx := rx * cos(ang) - rz * sin(ang)
			var gz := rx * sin(ang) + rz * cos(ang)
			fila.append(Vector3(gx + ox, y, gz + oz))
		anillos.append(fila)

	# Pared exterior.
	for j in m - 1:
		for i in n:
			var i2 := (i + 1) % n
			_cuad(tris, anillos[j][i], anillos[j][i2], anillos[j + 1][i2], anillos[j + 1][i])

	if hueco <= 0.001:
		_casquete(tris, anillos[0], false)
		_casquete(tris, anillos[m - 1], true)
		return tris

	# Pared interior + anillos de cierre arriba y abajo (marco/tubo).
	var interior := _encoger(perfil, hueco)
	var anillos_in: Array = []
	for j in m:
		var u2 := float(j) / float(m - 1)
		var y2 := lerpf(y0, y1, u2)
		var base2 := lerpf(1.0, 0.04, u2) if es_cono else 1.0
		var s2 := base2 * (1.0 - float(p["estrechado_x"]) * u2)
		var sz2 := base2 * (1.0 - float(p["estrechado_y"]) * u2)
		var ang2 := deg_to_rad(lerpf(float(p["giro"]), float(p["giro_fin"]), u2))
		var ox2 := float(p["cizalla_x"]) * u2
		var oz2 := float(p["cizalla_y"]) * u2
		var fila2 := PackedVector3Array()
		for i in n:
			var q2: Vector2 = interior[i]
			var rx2 := q2.x * s2
			var rz2 := q2.y * sz2
			var gx2 := rx2 * cos(ang2) - rz2 * sin(ang2)
			var gz2 := rx2 * sin(ang2) + rz2 * cos(ang2)
			fila2.append(Vector3(gx2 + ox2, y2, gz2 + oz2))
		anillos_in.append(fila2)
	for j in m - 1:
		for i in n:
			var i2 := (i + 1) % n
			# Envuelta invertida: la cara interior mira hacia el eje.
			_cuad(tris, anillos_in[j][i2], anillos_in[j][i], anillos_in[j + 1][i], anillos_in[j + 1][i2])
	# Anillo inferior y superior entre pared exterior e interior.
	for i in n:
		var i2 := (i + 1) % n
		_cuad(tris, anillos[0][i2], anillos[0][i], anillos_in[0][i], anillos_in[0][i2])
		_cuad(tris, anillos[m - 1][i], anillos[m - 1][i2], anillos_in[m - 1][i2], anillos_in[m - 1][i])
	return tris


# ----------------------------------------------------------------- revolución

## Barrido circular: el perfil (en el plano (radio, Y)) gira alrededor del eje Y.
static func _revolucionar(tipo: String, p: Dictionary) -> PackedVector3Array:
	var perfil := _perfil_revolucion(tipo)
	var n := perfil.size()
	var k := ANILLOS
	var a0 := float(p["corte_ini"]) * TAU
	var a1 := float(p["corte_fin"]) * TAU
	var cerrado := absf(float(p["corte_fin"]) - float(p["corte_ini"]) - 1.0) < 0.001
	var hueco := float(p["hueco"])
	var tris := PackedVector3Array()

	var pasos := k if cerrado else k + 1
	var anillos: Array = []
	for s in pasos:
		var a := lerpf(a0, a1, float(s) / float(k))
		anillos.append(_anillo_revolucion(perfil, n, a, p, 1.0))

	for s in pasos - (0 if cerrado else 1):
		var s2 := (s + 1) % pasos
		for i in n:
			var i2 := (i + 1) % n
			_cuad(tris, anillos[s][i], anillos[s][i2], anillos[s2][i2], anillos[s2][i])

	if not cerrado:
		_casquete(tris, anillos[0], false)
		_casquete(tris, anillos[pasos - 1], true)

	if hueco <= 0.001:
		return _voltear(tris)
	# Hueco: perfil interior más pequeño, vuelto con la vuelta invertida.
	var interior := _encoger(perfil, hueco)
	var anillos_in: Array = []
	for s in pasos:
		var a := lerpf(a0, a1, float(s) / float(k))
		anillos_in.append(_anillo_revolucion(interior, n, a, p, 1.0))
	for s in pasos - (0 if cerrado else 1):
		var s2 := (s + 1) % pasos
		for i in n:
			var i2 := (i + 1) % n
			_cuad(tris, anillos_in[s][i2], anillos_in[s][i], anillos_in[s2][i], anillos_in[s2][i2])
	return _voltear(tris)


## Un anillo de revolución: cada punto del perfil girado a un ángulo `a`.
static func _anillo_revolucion(perfil: PackedVector2Array, n: int, a: float,
		p: Dictionary, escala: float) -> PackedVector3Array:
	var fila := PackedVector3Array()
	for i in n:
		var q := perfil[i]
		var v := clampf((q.y + 0.5) / 1.0, 0.0, 1.0)
		# Estrechado: reduce el radio según la altura del punto.
		var r := q.x * escala * (1.0 - float(p["estrechado_x"]) * v)
		# Giro: desplaza el ángulo según la posición a lo largo del perfil.
		var u := float(i) / float(maxi(1, n - 1))
		var ang := a + deg_to_rad(lerpf(float(p["giro"]), float(p["giro_fin"]), u))
		# Cizalla: desplazamiento lateral según la altura.
		var ox := float(p["cizalla_x"]) * v
		var oz := float(p["cizalla_y"]) * v
		fila.append(Vector3(cos(ang) * r + ox, q.y, sin(ang) * r + oz))
	return fila


# --------------------------------------------------------------------- perfiles

## Perfil de extrusión en el plano XZ (unidades dentro de 0.5).
static func _perfil_extrusion(tipo: String) -> PackedVector2Array:
	var pts := PackedVector2Array()
	if tipo == "cubo":
		pts.append(Vector2(-0.5, -0.5))
		pts.append(Vector2(0.5, -0.5))
		pts.append(Vector2(0.5, 0.5))
		pts.append(Vector2(-0.5, 0.5))
		return pts
	for i in LADOS:
		var ang := TAU * float(i) / float(LADOS)
		pts.append(Vector2(cos(ang) * 0.5, sin(ang) * 0.5))
	return pts


## Perfil de revolución en el plano (radio, Y).
static func _perfil_revolucion(tipo: String) -> PackedVector2Array:
	var pts := PackedVector2Array()
	if tipo == "toro":
		var n := 16
		for i in n:
			var ang := TAU * float(i) / float(n)
			pts.append(Vector2(0.35 + 0.15 * cos(ang), 0.15 * sin(ang)))
		return pts
	# esfera: semicírculo del polo sur al norte (radio 0 en los extremos).
	var n2 := ANILLOS
	for i in n2 + 1:
		var t := float(i) / float(n2)
		var theta := lerpf(-PI * 0.5, PI * 0.5, t)
		pts.append(Vector2(0.5 * cos(theta), 0.5 * sin(theta)))
	return pts


## Encoge un perfil hacia su centroide (para el hueco). Conserva el nº de puntos.
static func _encoger(perfil: PackedVector2Array, t: float) -> PackedVector2Array:
	var centro := Vector2.ZERO
	for q in perfil:
		centro += q
	centro /= float(perfil.size())
	var salida := PackedVector2Array()
	for q in perfil:
		salida.append(q.lerp(centro, clampf(t * 0.92, 0.0, 0.95)))
	return salida


## Reordena un lazo para que su área con signo sea positiva (CCW en XZ).
static func _a_ccw(perfil: PackedVector2Array) -> PackedVector2Array:
	var area := 0.0
	var n := perfil.size()
	for i in n:
		var a := perfil[i]
		var b := perfil[(i + 1) % n]
		area += a.x * b.y - b.x * a.y
	if area >= 0.0:
		return perfil
	var rev := PackedVector2Array()
	for i in range(n - 1, -1, -1):
		rev.append(perfil[i])
	return rev


# -------------------------------------------------------------------- primitivas

## Cuadrilátero (a,b,c,d) como dos triángulos.
static func _cuad(tris: PackedVector3Array, a: Vector3, b: Vector3, c: Vector3, d: Vector3) -> void:
	_add_tri(tris, a, b, c)
	_add_tri(tris, a, c, d)


## Devuelve la lista de triángulos con cada cara volteada (b<->c). La revolución
## gira en sentido contrario a la extrusión, por eso se compensa aquí.
static func _voltear(tris: PackedVector3Array) -> PackedVector3Array:
	var salida := PackedVector3Array()
	salida.resize(tris.size())
	for t in range(0, tris.size(), 3):
		salida[t] = tris[t]
		salida[t + 1] = tris[t + 2]
		salida[t + 2] = tris[t + 1]
	return salida


## Tapa en abanico desde el centroide. `arriba` orienta la tapa hacia +Y o -Y.
static func _casquete(tris: PackedVector3Array, anillo: PackedVector3Array, arriba: bool) -> void:
	if anillo.is_empty():
		return
	var centro := Vector3.ZERO
	for v in anillo:
		centro += v
	centro /= float(anillo.size())
	var n := anillo.size()
	for i in n:
		var a := anillo[i]
		var b := anillo[(i + 1) % n]
		if arriba:
			_add_tri(tris, centro, a, b)
		else:
			_add_tri(tris, centro, b, a)


static func _add_tri(tris: PackedVector3Array, a: Vector3, b: Vector3, c: Vector3) -> void:
	if INVERTIR:
		tris.append(a)
		tris.append(c)
		tris.append(b)
	else:
		tris.append(a)
		tris.append(b)
		tris.append(c)


## Construye la ArrayMesh con normales. `suave` promedia normales por posición
## (cilindros/esferas redondos); si no, sombreado plano (cubos con aristas).
static func _malla(tris: PackedVector3Array, suave: bool) -> ArrayMesh:
	if tris.is_empty():
		return ArrayMesh.new()
	var normales := PackedVector3Array()
	normales.resize(tris.size())
	if suave:
		var sumas := {}
		for t in range(0, tris.size(), 3):
			var n := _normal_tri(tris[t], tris[t + 1], tris[t + 2])
			for k in 3:
				var clave := _clave(tris[t + k])
				sumas[clave] = (sumas.get(clave, Vector3.ZERO) as Vector3) + n
		for i in tris.size():
			var s: Vector3 = sumas.get(_clave(tris[i]), Vector3.UP)
			normales[i] = s.normalized() if s.length_squared() > 1e-12 else Vector3.UP
	else:
		for t in range(0, tris.size(), 3):
			var n := _normal_tri(tris[t], tris[t + 1], tris[t + 2])
			normales[t] = n
			normales[t + 1] = n
			normales[t + 2] = n
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = tris
	arrays[Mesh.ARRAY_NORMAL] = normales
	var malla := ArrayMesh.new()
	malla.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return malla


static func _normal_tri(a: Vector3, b: Vector3, c: Vector3) -> Vector3:
	var n := (b - a).cross(c - a)
	if n.length_squared() < 1e-16:
		return Vector3.UP
	return n.normalized()


static func _clave(v: Vector3) -> Vector3i:
	return Vector3i(roundi(v.x * 10000.0), roundi(v.y * 10000.0), roundi(v.z * 10000.0))