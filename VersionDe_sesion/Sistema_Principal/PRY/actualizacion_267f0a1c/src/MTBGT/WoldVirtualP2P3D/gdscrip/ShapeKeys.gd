class_name ShapeKeys
extends RefCounted
## Adaptador de los blend shapes de VRM que usa el addon V-Sekai/vrm-importer
## (Asset Library 2031, MIT) para los avatares de WoldVirtual.
##
## Los 24 GLB no traen morph targets (`"targets": 0` en todos los primitivos),
## asi que `MeshInstance3D.get_blend_shape_count()` devuelve 0 y
## `set_blend_shape_value()` no mueve nada. Este modulo adapta los presets del
## addon (BlendShapePreset de VRM 0.x) a las expresiones analiticas de
## Personalizacion.gd, que deforman vertices en espacio de reposo conservando
## UV, huesos y pesos.

const Pers = preload("res://gdscrip/Personalizacion.gd")

## Presets del estandar VRM, en el orden que documenta el addon.
const PRESETS := ["neutral", "joy", "angry", "sorrow", "fun", "blink",
	"a", "i", "u", "e", "o"]

## Preset VRM -> claves de Personalizacion.EXPRESIONES que lo resuelven.
## Las cinco vocales comparten las dos formas de boca disponibles.
const MAPA := {
	"joy": ["sonrisa"],
	"angry": ["enfado"],
	"sorrow": ["tristeza"],
	"fun": ["sorpresa"],
	"blink": ["parpadeo"],
	"a": ["boca_abierta"],
	"o": ["boca_abierta"],
	"i": ["boca_ancha"],
	"e": ["boca_ancha"],
	"u": ["boca_ancha"],
}


## Pesos neutros de todos los presets.
static func valores_por_defecto() -> Dictionary:
	var d := {}
	for preset in PRESETS:
		d[preset] = 0.0
	return d


static func normalizar(valores: Dictionary) -> Dictionary:
	var d := valores_por_defecto()
	for preset in PRESETS:
		if valores.has(preset):
			d[preset] = clampf(float(valores[preset]), 0.0, 1.0)
	return d


## Convierte pesos VRM en el diccionario de expresiones del sistema. Si dos
## presets comparten clave (a/o, i/e/u) se queda el mayor: no se suman para no
## deformar la boca el doble.
static func a_expresiones(valores: Dictionary) -> Dictionary:
	var v := normalizar(valores)
	var d := {}
	for clave in Pers.EXPRESIONES:
		d[clave] = 0.0
	for preset in MAPA:
		for clave in MAPA[preset]:
			d[clave] = maxf(float(d[clave]), v[preset])
	return d


## Copia de `datos` (aspecto completo) con las expresiones sustituidas por los
## pesos VRM. El resto de claves (tintes, cuerpo, rasgos) no se toca.
static func fusionar(datos: Dictionary, valores: Dictionary) -> Dictionary:
	var d: Dictionary = Pers.normalizar(datos)
	var exp := a_expresiones(valores)
	for clave in exp:
		d[clave] = exp[clave]
	return d


## Aplica el aspecto completo, incluidos los shape keys.
static func aplicar(avatar: Node, datos: Dictionary) -> void:
	Pers.aplicar(avatar, datos)


## Etiqueta legible de cada preset, para paneles y pruebas.
static func nombre(preset: String) -> String:
	match preset:
		"neutral": return "Neutro"
		"joy": return "Alegria"
		"angry": return "Enfado"
		"sorrow": return "Tristeza"
		"fun": return "Sorpresa"
		"blink": return "Parpadeo"
		"a": return "Boca A"
		"i": return "Boca I"
		"u": return "Boca U"
		"e": return "Boca E"
		"o": return "Boca O"
	return preset
