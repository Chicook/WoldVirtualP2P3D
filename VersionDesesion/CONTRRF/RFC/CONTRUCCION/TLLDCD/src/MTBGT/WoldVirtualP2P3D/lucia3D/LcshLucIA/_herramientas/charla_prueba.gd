extends SceneTree

## Charla real contra el servidor: abre la interfaz, espera el saludo del
## cerebro, envía una consulta y captura el turno (pensando / hablando / final).
##
##   godot --path . --script res://_herramientas/charla_prueba.gd

var cliente: Node
var personaje: Node
var fase := 0
var t_inicio := 0
var t_ultimo := 0
var t_fin := 0
var capturado_pensando := false
var mejor_apertura := -1.0
var max_apertura := 0.0
var texto_final := ""

func _initialize() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://_pruebas/charla/"))
	var esc: PackedScene = load("res://GLTF_lucIA/AreaDeTrabajo/Constructor3D_IA/LucIA_Interfaz.tscn")
	cliente = esc.instantiate()
	get_root().add_child(cliente)
	await process_frame
	personaje = cliente.get_node("lucIA_BASE")
	t_inicio = Time.get_ticks_msec()
	print("Interfaz abierta. Esperando conexión con el cerebro…")

func _process(_delta: float) -> bool:
	var ahora := Time.get_ticks_msec()
	var estado: Label = cliente.get_node("UI/Raiz/Estado")
	match fase:
		0:
			if cliente._esta_listo:
				print("Conectada: ", estado.text)
				cliente._al_enviar_texto("Hola LucIA. Preséntate en dos frases y cuéntame cómo te sientes hoy.")
				t_inicio = ahora
				fase = 1
			elif ahora - t_inicio > 40000:
				push_error("No llegó el saludo del servidor en 40 s")
				quit()
		1:
			if not capturado_pensando and ahora - t_inicio > 900:
				_capturar("01_pensando")
				capturado_pensando = true
			if cliente._audio_sonando:
				print("Empieza a hablar: ", estado.text)
				fase = 2
				t_ultimo = ahora
		2:
			if ahora - t_ultimo >= 70:
				t_ultimo = ahora
				if cliente._audio_sonando:
					max_apertura = maxf(max_apertura, float(personaje._apertura))
					if float(personaje._apertura) > mejor_apertura:
						mejor_apertura = float(personaje._apertura)
						_capturar("02_hablando")
				else:
					print("Termina la voz. Apertura máxima de boca: %.3f" % max_apertura)
					fase = 3
					t_fin = ahora
		3:
			if ahora - t_fin > 1200:
				_capturar("03_final")
				texto_final = cliente.get_node("UI/Raiz/Panel/VBox/Salida").get_parsed_text()
				print("--- RESULTADO ---")
				print("estado: ", estado.text)
				print("texto: ", texto_final.replace("\n", " | "))
				print("gesto final: ", personaje._gesto_objetivo, " peso: ", personaje._peso_gesto)
				print("apertura maxima: ", max_apertura)
				quit()
	return false

func _capturar(nombre: String) -> void:
	var img := get_root().get_texture().get_image()
	img.save_png("res://_pruebas/charla/%s.png" % nombre)
	print("captura: ", nombre)
