extends Control

@onready var input_name = $Panel/VBox/LineEdit
@onready var btn_male = $Panel/VBox/HBox/Male
@onready var btn_female = $Panel/VBox/HBox/Female
@onready var btn_login = $Panel/VBox/Login
@onready var status_label = $Panel/VBox/Status

var selected_gender = ""
var save_path = "res://woldvirtual/scene/MTC/users3D/current_user.json"
var wallet_full = ""

func _ready():
	var args = OS.get_cmdline_args() + OS.get_cmdline_user_args()
	for i in range(args.size()):
		if args[i] == "--wallet" and i + 1 < args.size():
			wallet_full = args[i+1]
			break

	setup_glassmorphism()
	
	# Establecer pivotes para escalado correcto al centrarse
	btn_male.pivot_offset = btn_male.custom_minimum_size / 2
	btn_female.pivot_offset = btn_female.custom_minimum_size / 2
	btn_login.pivot_offset = btn_login.custom_minimum_size / 2
	
	setup_button_animations(btn_male)
	setup_button_animations(btn_female)
	setup_button_animations(btn_login)

func setup_glassmorphism():
	var sb = StyleBoxFlat.new()
	sb.bg_color = Color(0.05, 0.05, 0.1, 0.85)
	sb.set_corner_radius_all(20)
	sb.shadow_color = Color(0, 0.8, 1.0, 0.15)
	sb.shadow_size = 20
	sb.border_width_bottom = 2
	sb.border_width_right = 2
	sb.border_color = Color(1, 1, 1, 0.1)
	$Panel.add_theme_stylebox_override("panel", sb)

func setup_button_animations(btn: Button):
	btn.mouse_entered.connect(func(): animate_button(btn, 1.05))
	btn.mouse_exited.connect(func(): animate_button(btn, 1.0))

func animate_button(btn: Button, scale_val: float):
	var tween = create_tween()
	tween.tween_property(btn, "scale", Vector2(scale_val, scale_val), 0.15).set_trans(Tween.TRANS_SINE)

func animate_click(btn: Button):
	var tween = create_tween()
	tween.tween_property(btn, "scale", Vector2(0.95, 0.95), 0.1)
	tween.tween_property(btn, "scale", Vector2(1.05, 1.05), 0.1)

func _on_male_pressed():
	selected_gender = "male"
	status_label.text = "Seleccionado: Hombre"
	btn_male.modulate = Color(0.2, 1.0, 1.0)
	btn_female.modulate = Color(0.5, 0.5, 0.5)
	animate_click(btn_male)

func _on_female_pressed():
	selected_gender = "female"
	status_label.text = "Seleccionado: Mujer"
	btn_female.modulate = Color(1.0, 0.2, 0.6)
	btn_male.modulate = Color(0.5, 0.5, 0.5)
	animate_click(btn_female)

func _on_login_pressed():
	animate_click(btn_login)
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
		print("AVATAR_LOGIN_CLICKED")
		print("Usuario guardado en: ", save_path)
		
		# Cambiar Escena
		get_tree().change_scene_to_file("res://woldvirtual/scene/MTC/N3DWoldVirtualMT.tscn")
	else:
		status_label.text = "Error al guardar perfil"
