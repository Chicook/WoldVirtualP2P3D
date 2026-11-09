extends SceneTree
## Test visual de LucIARecepcion: muestra el formulario de recepción sin necesidad
## de iniciar el visor C# completo. Uso: godot --path . --script res://gdscrip/test_lucia_recepcion.gd

const Recepcion = preload("res://../WoldVirtualP2P3D/gdscrip/LuciaRecepcion.gd")

func _initialize() -> void:
	print("================================================================")
	print("[Test LucIA] Iniciando test visual de recepción")
	print("================================================================")

	# Crear la recepción en modo forzado "nuevo"
	var recepcion = Recepcion.new()
	recepcion.name = "RecepcionLuciaTest"
	root.add_child(recepcion)

	# Conectar señal para saber cuando termine
	recepcion.recepcion_completada.connect(_on_recepcion_completada)
	recepcion.validacion_conexion_solicitada.connect(_on_validacion_solicitada)

	print("[Test LucIA] Recepción creada. Esperando interacción del usuario...")
	print("[Test LucIA] Presiona ESC para salir")


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_ESCAPE:
			print("[Test LucIA] ESC presionado, saliendo...")
			quit()


func _on_recepcion_completada(modo: String) -> void:
	print("[Test LucIA] Recepción completada, modo: ", modo)
	print("[Test LucIA] El usuario ha pasado al carrusel")


func _on_validacion_solicitada() -> void:
	print("[Test LucIA] Validación de conexión solicitada")
	print("[Test LucIA] (En el visor C# real, esto iniciaría el túnel SSH)")
