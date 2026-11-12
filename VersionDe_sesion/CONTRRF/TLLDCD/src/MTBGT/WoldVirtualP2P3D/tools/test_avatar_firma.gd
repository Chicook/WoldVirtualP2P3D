extends SceneTree
## Prueba unitaria de `AvatarFirma.gd` (firma, diferencia y variantes).
## Uso: godot --headless --path <proyecto> --script res://tools/test_avatar_firma.gd

const Firma = preload("res://gdscrip/AvatarFirma.gd")
const Pers = preload("res://gdscrip/Personalizacion.gd")

var _fallos := 0


func _init() -> void:
	var base: Dictionary = Pers.POR_DEFECTO

	_check(Firma.vector(base).size() == 33, "el vector tiene 33 dimensiones")
	_check(Firma.delta(base, base) == 0.0, "el avatar base se diferencia 0")
	_check(Firma.delta_base(base) == 0.0, "delta_base(base) = 0")
	_check(Firma.porcentaje(Firma.delta_base(base)) == 0, "porcentaje base = 0")
	_check(not Firma.es_original(0.0), "el avatar base no es original")

	var custom: Dictionary = base.duplicate()
	custom["ancho"] = 1.15
	custom["cabeza"] = 1.15
	custom["piel"] = Color(1.0, 0.0, 0.0)
	var delta: float = Firma.delta_base(custom)
	_check(delta > 0.0, "personalizar sube la diferencia")
	_check(Firma.firma(base) == Firma.firma(base.duplicate()), "la firma es estable")
	_check(Firma.firma(base) != Firma.firma(custom), "dos aspectos distintos dan firmas distintas")
	_check(Firma.firma(custom).length() == 64, "la firma es un SHA-256 hexadecimal")

	# La variante debe moverse del original y quedarse dentro de los rangos.
	var variante: Dictionary = Firma.variante(custom, "f".repeat(64), 0)
	_check(Firma.delta(variante, custom) > 0.0, "la variante difiere del avatar original")
	_check(Firma.firma(variante) != Firma.firma(custom), "la variante tiene firma propia")
	var fuera := 0
	for clave in Pers.CAMPOS:
		var rango: Vector2 = Pers.RANGOS[clave]
		var valor := float(variante[clave])
		if valor < rango.x - 0.0001 or valor > rango.y + 0.0001:
			fuera += 1
	_check(fuera == 0, "todos los campos de la variante caen en su rango")

	# Dos semillas distintas no deben producir la misma variante.
	var otra: Dictionary = Firma.variante(custom, "e".repeat(64), 0)
	_check(Firma.firma(variante) != Firma.firma(otra), "semillas distintas dan variantes distintas")

	print("[test_avatar_firma] ", "OK" if _fallos == 0 else ("FALLOS: %d" % _fallos))
	quit(0 if _fallos == 0 else 1)


func _check(condicion: bool, texto: String) -> void:
	if condicion:
		print("[ok]     ", texto)
	else:
		print("[FALLO]  ", texto)
		_fallos += 1
