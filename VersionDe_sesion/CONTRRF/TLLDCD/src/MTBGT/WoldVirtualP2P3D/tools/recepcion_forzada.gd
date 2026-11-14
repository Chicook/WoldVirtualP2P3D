extends "res://gdscrip/LuciaRecepcion.gd"
## Subclase de prueba: fuerza el modo de recepción sin leer ni tocar user:// real.
var modo_forzado := "nuevo"
var cuenta_forzada := {}

func _detectar_modo() -> void:
	_modo = modo_forzado
	_cuenta = cuenta_forzada