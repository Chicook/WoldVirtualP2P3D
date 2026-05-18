extends Control

@onready var input_name = $Panel/VBox/LineEdit
@onready var btn_male = $Panel/VBox/HBox/Male
@onready var btn_female = $Panel/VBox/HBox/Female
@onready var status_label = $Panel/VBox/Status

var selected_gender = ""
var save_path = "res://woldvirtual/scene/MTC/users3D/current_user.json"
var wallet_full = ""

func _ready():
	# Leer argumentos de línea de comandos pasados por C# (prioridad usuario)
	var user_args = OS.get_cmdline_user_args()
	var username_arg = ""
	
	for i in range(user_args.size()):
		if user_args[i] == "--wallet" and i + 1 < user_args.size():
			wallet_full = user_args[i+1].replace("\"", "").strip_edges()
		elif user_args[i] == "--user-id" and i + 1 < user_args.size():
			username_arg = user_args[i+1].replace("\"", "").strip_edges()

	# Si no vienen ahí, intentar de los argumentos generales (como fallback)
	var args = OS.get_cmdline_args()
	for i in range(args.size()):
		if (wallet_full == "" or wallet_full == "No Wallet Address") and args[i] == "--wallet" and i + 1 < args.size():
			wallet_full = args[i+1].replace("\"", "").strip_edges()
		if username_arg == "" and args[i] == "--user-id" and i + 1 < args.size():
			username_arg = args[i+1].replace("\"", "").strip_edges()

	# Pre-rellenar y bloquear el campo de nombre para que esté 100% vinculado a su nik
	if username_arg != "":
		input_name.text = username_arg
		input_name.editable = false
		status_label.text = "Identidad vinculada: " + username_arg

	# Estilo Glassmorphism
	var sb = StyleBoxFlat.new()
	sb.bg_color = Color(0.1, 0.1, 0.2, 0.7)
	sb.set_corner_radius_all(15)
	$Panel.add_theme_stylebox_override("panel", sb)

func _on_male_pressed():
	selected_gender = "male"
	status_label.text = "Seleccionado: Hombre"
	btn_male.modulate = Color.CYAN
	btn_female.modulate = Color.WHITE

func _on_female_pressed():
	selected_gender = "female"
	status_label.text = "Seleccionado: Mujer"
	btn_female.modulate = Color.PINK
	btn_male.modulate = Color.WHITE

func _on_login_pressed():
	var username = input_name.text.strip_edges()
	
	if username == "":
		status_label.text = "Error: Ingresa un nombre"
		return
	if selected_gender == "":
		status_label.text = "Error: Selecciona género"
		return
		
	# Guardar Datos (incluyendo wallet completa para el metaverso)
	var data = {
		"username": username,
		"gender": selected_gender,
		"wallet": wallet_full,
		"timestamp": Time.get_unix_time_from_system()
	}
	
	var file = FileAccess.open(save_path, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(data, "\t"))
		file.close()
		print("Usuario guardado en: ", save_path)
		
		# Cambiar Escena
		get_tree().change_scene_to_file("res://woldvirtual/scene/MTC/N3DWoldVirtualMT.tscn")
	else:
		status_label.text = "Error al guardar perfil"
