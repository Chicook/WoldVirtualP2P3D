extends Node3D

func _ready() -> void:
	print("[VistaPrevia] Iniciando vista previa de la Recepción de LucIA...")
	var rec_script = load("res://gdscrip/LuciaRecepcion.gd")
	if rec_script:
		var rec = rec_script.new()
		rec.name = "LuciaRecepcion"
		add_child(rec)
		print("[VistaPrevia] LuciaRecepcion cargada con éxito.")
	else:
		push_error("[VistaPrevia] No se pudo cargar res://gdscrip/LuciaRecepcion.gd")
