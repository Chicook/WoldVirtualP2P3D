class_name AvatarFirma
extends RefCounted
## Firma y "originalidad" del avatar (discusión #86 · diseño de LucIA anfitriona).
##
## Los 24 GLB no traen morph targets, así que el aspecto no se mide por blend
## shapes del modelo sino por el aspecto **aplicado**: los 5 tintes y los 18
## campos de `Personalizacion` (cuerpo, rostro y expresiones), cada uno
## normalizado a 0..1 con sus rangos reales.
##
## - `firma()` es el SHA-256 de ese vector cuantizado: identifica un aspecto
##   concreto y sirve para comparar sin guardar la imagen.
## - `delta_base()` mide cuánto se aparta el avatar del aspecto por defecto
##   (0 = tal cual viene el modelo, 1 = todo al extremo opuesto).
## - Un `delta` por encima de `UMBRAL_ORIGINALIDAD` se considera diferencia
##   *considerable*: es lo que permite marcar el nick como validado por avatar
##   propio, y lo que se envía como dato de entrenamiento a las neuronas.

const Pers = preload("res://gdscrip/Personalizacion.gd")

## Media absoluta mínima (sobre 33 dimensiones) para considerar el avatar
## "propio". Con los valores por defecto el avatar da 0.0; tintar tres prendas
## y mover proporciones ronda 0.12–0.20.
const UMBRAL_ORIGINALIDAD := 0.12

## Zonas del vector, para diagnóstico y para el generador de variantes.
const DIMENSIONES := 33  # 5 colores x 3 canales + 18 campos


## Vector normalizado del aspecto (33 valores en 0..1).
static func vector(datos: Dictionary) -> PackedFloat32Array:
	var d: Dictionary = Pers.normalizar(datos)
	var v := PackedFloat32Array()
	for clave in Pers.ORDEN:
		var c: Color = d.get(clave, Color.WHITE)
		v.append(clampf(c.r, 0.0, 1.0))
		v.append(clampf(c.g, 0.0, 1.0))
		v.append(clampf(c.b, 0.0, 1.0))
	for clave in Pers.CAMPOS:
		var rango: Vector2 = Pers.RANGOS.get(clave, Vector2(0.0, 1.0))
		var x := float(d.get(clave, 0.0))
		var t := 0.0
		if rango.y > rango.x:
			t = (x - rango.x) / (rango.y - rango.x)
		v.append(clampf(t, 0.0, 1.0))
	return v


## Diferencia media absoluta entre dos aspectos, en 0..1.
static func delta(a: Dictionary, b: Dictionary) -> float:
	var va := vector(a)
	var vb := vector(b)
	var n: int = mini(va.size(), vb.size())
	if n == 0:
		return 0.0
	var suma := 0.0
	for i in n:
		suma += absf(va[i] - vb[i])
	return clampf(suma / float(n), 0.0, 1.0)


## Diferencia contra el aspecto por defecto (el avatar recién elegido).
static func delta_base(datos: Dictionary) -> float:
	return delta(datos, Pers.POR_DEFECTO)


## SHA-256 del aspecto cuantizado a 3 decimales (estable entre sesiones).
static func firma(datos: Dictionary) -> String:
	var v := vector(datos)
	var partes := PackedStringArray()
	for x in v:
		partes.append("%.3f" % x)
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update("|".join(partes).to_utf8_buffer())
	return ctx.finish().hex_encode()


static func porcentaje(d: float) -> int:
	return int(round(clampf(d, 0.0, 1.0) * 100.0))


static func es_original(d: float) -> bool:
	return d >= UMBRAL_ORIGINALIDAD


## Variante del aspecto con diferencias deterministas, para nutrir el carrusel
## con avatares nuevos a partir de uno original. `semilla` hace que dos cuentas
## con el mismo avatar no generen exactamente las mismas variantes.
static func variante(datos: Dictionary, semilla: String, indice: int) -> Dictionary:
	var d: Dictionary = Pers.normalizar(datos)
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(("%s|%d" % [semilla, indice]).to_utf8_buffer())
	var bytes := ctx.finish()
	var v := vector(d)
	var salida := {}
	var pos := 0
	# Tintes: desplaza el canal según la semilla (sin salirse de 0..1).
	for clave in Pers.ORDEN:
		var c: Color = d.get(clave, Color.WHITE)
		var dr := (float(bytes[pos % 32]) / 255.0 - 0.5) * 0.30
		var dg := (float(bytes[(pos + 1) % 32]) / 255.0 - 0.5) * 0.30
		var db := (float(bytes[(pos + 2) % 32]) / 255.0 - 0.5) * 0.30
		salida[clave] = Color(clampf(c.r + dr, 0.0, 1.0),
			clampf(c.g + dg, 0.0, 1.0), clampf(c.b + db, 0.0, 1.0))
		pos += 3
	# Campos: desplaza dentro de su rango, un poco más suave en el rostro.
	for clave in Pers.CAMPOS:
		var rango: Vector2 = Pers.RANGOS.get(clave, Vector2(0.0, 1.0))
		var amplitud := (rango.y - rango.x) * 0.10
		if clave in Pers.ROSTRO:
			amplitud *= 0.6
		var desvio := (float(bytes[pos % 32]) / 255.0 - 0.5) * 2.0 * amplitud
		salida[clave] = clampf(float(d.get(clave, 0.0)) + desvio, rango.x, rango.y)
		pos += 1
	return salida
