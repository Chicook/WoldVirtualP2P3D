extends Control

@onready var input_name   = $Panel/VBox/LineEdit
@onready var btn_male     = $Panel/VBox/HBox/Male
@onready var btn_female   = $Panel/VBox/HBox/Female
@onready var btn_login    = $Panel/VBox/Login
@onready var status_label = $Panel/VBox/Status

var selected_gender = ""
var save_path       = "res://woldvirtual/scene/MTC/users3D/current_user.json"
var wallet_full     = ""
var detected_lang   = "es"   # Idioma ISO 639-1 detectado por el visor C#
var detected_country = "??"  # País ISO 3166-1 alpha-2 detectado por el visor C#

# ── Traducciones de la UI de registro ──────────────────────────────────────────
const TRANSLATIONS = {
	"es": {
		"title":        "Registro de Avatar",
		"name_hint":    "Nombre de usuario...",
		"gender_label": "Selecciona Género:",
		"male":         "HOMBRE",
		"female":       "MUJER",
		"login_btn":    "INICIAR SESIÓN",
		"err_name":     "Error: Ingresa un nombre",
		"err_gender":   "Error: Selecciona género",
		"sel_male":     "Seleccionado: Hombre",
		"sel_female":   "Seleccionado: Mujer",
		"err_save":     "Error al guardar perfil",
	},
	"en": {
		"title":        "Avatar Registration",
		"name_hint":    "Username...",
		"gender_label": "Select Gender:",
		"male":         "MALE",
		"female":       "FEMALE",
		"login_btn":    "START SESSION",
		"err_name":     "Error: Enter a name",
		"err_gender":   "Error: Select gender",
		"sel_male":     "Selected: Male",
		"sel_female":   "Selected: Female",
		"err_save":     "Error saving profile",
	},
	"fr": {
		"title":        "Inscription Avatar",
		"name_hint":    "Nom d'utilisateur...",
		"gender_label": "Choisir le genre :",
		"male":         "HOMME",
		"female":       "FEMME",
		"login_btn":    "DÉMARRER",
		"err_name":     "Erreur : Entrez un nom",
		"err_gender":   "Erreur : Choisissez le genre",
		"sel_male":     "Sélectionné : Homme",
		"sel_female":   "Sélectionné : Femme",
		"err_save":     "Erreur de sauvegarde",
	},
	"de": {
		"title":        "Avatar-Registrierung",
		"name_hint":    "Benutzername...",
		"gender_label": "Geschlecht wählen:",
		"male":         "MÄNNLICH",
		"female":       "WEIBLICH",
		"login_btn":    "SITZUNG STARTEN",
		"err_name":     "Fehler: Namen eingeben",
		"err_gender":   "Fehler: Geschlecht wählen",
		"sel_male":     "Ausgewählt: Männlich",
		"sel_female":   "Ausgewählt: Weiblich",
		"err_save":     "Fehler beim Speichern",
	},
	"pt": {
		"title":        "Registro de Avatar",
		"name_hint":    "Nome de utilizador...",
		"gender_label": "Selecionar Género:",
		"male":         "MASCULINO",
		"female":       "FEMININO",
		"login_btn":    "INICIAR SESSÃO",
		"err_name":     "Erro: Insira um nome",
		"err_gender":   "Erro: Selecione o género",
		"sel_male":     "Selecionado: Masculino",
		"sel_female":   "Selecionado: Feminino",
		"err_save":     "Erro ao salvar perfil",
	},
	"it": {
		"title":        "Registrazione Avatar",
		"name_hint":    "Nome utente...",
		"gender_label": "Seleziona il genere:",
		"male":         "MASCHIO",
		"female":       "FEMMINA",
		"login_btn":    "AVVIA SESSIONE",
		"err_name":     "Errore: inserisci un nome",
		"err_gender":   "Errore: seleziona il genere",
		"sel_male":     "Selezionato: Maschio",
		"sel_female":   "Selezionata: Femmina",
		"err_save":     "Errore nel salvataggio",
	},
	"zh": {
		"title":        "头像注册",
		"name_hint":    "用户名...",
		"gender_label": "选择性别:",
		"male":         "男",
		"female":       "女",
		"login_btn":    "开始",
		"err_name":     "错误：请输入名称",
		"err_gender":   "错误：请选择性别",
		"sel_male":     "已选：男",
		"sel_female":   "已选：女",
		"err_save":     "保存错误",
	},
	"ja": {
		"title":        "アバター登録",
		"name_hint":    "ユーザー名...",
		"gender_label": "性別を選択：",
		"male":         "男性",
		"female":       "女性",
		"login_btn":    "セッション開始",
		"err_name":     "エラー：名前を入力してください",
		"err_gender":   "エラー：性別を選択してください",
		"sel_male":     "選択：男性",
		"sel_female":   "選択：女性",
		"err_save":     "保存エラー",
	},
}

func _ready():
	var args = OS.get_cmdline_args() + OS.get_cmdline_user_args()
	for i in range(args.size()):
		if args[i] == "--wallet" and i + 1 < args.size():
			wallet_full = args[i + 1]
		elif args[i] == "--lang" and i + 1 < args.size():
			detected_lang = args[i + 1].to_lower()
		elif args[i] == "--country" and i + 1 < args.size():
			detected_country = args[i + 1].to_upper()

	# Resolver idioma: si no existe en la tabla, usar "en" como fallback
	if not TRANSLATIONS.has(detected_lang):
		detected_lang = "en"

	apply_locale()
	setup_glassmorphism()

	# Establecer pivotes para escalado correcto al centrarse
	btn_male.pivot_offset   = btn_male.custom_minimum_size / 2
	btn_female.pivot_offset = btn_female.custom_minimum_size / 2
	btn_login.pivot_offset  = btn_login.custom_minimum_size / 2

	setup_button_animations(btn_male)
	setup_button_animations(btn_female)
	setup_button_animations(btn_login)

	print("[RegistroAV] Idioma detectado: '", detected_lang, "' | País: '", detected_country, "'")

# ── Aplica los textos localizados a los nodos de la UI ──────────────────────────
func apply_locale():
	var t = TRANSLATIONS[detected_lang]

	# Título del panel
	if $Panel/VBox/Title:
		$Panel/VBox/Title.text = t["title"]

	# Placeholder del campo de nombre
	input_name.placeholder_text = t["name_hint"]

	# Etiqueta de género
	if $Panel/VBox/GenderLabel:
		$Panel/VBox/GenderLabel.text = t["gender_label"]

	# Botones de género y login
	btn_male.text   = t["male"]
	btn_female.text = t["female"]
	btn_login.text  = t["login_btn"]

	# Mostrar bandera/país detectado en el status label
	status_label.text = "🌍 " + detected_country + " · " + detected_lang.to_upper()

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
	btn.mouse_exited.connect(func():  animate_button(btn, 1.0))

func animate_button(btn: Button, scale_val: float):
	var tween = create_tween()
	tween.tween_property(btn, "scale", Vector2(scale_val, scale_val), 0.15).set_trans(Tween.TRANS_SINE)

func animate_click(btn: Button):
	var tween = create_tween()
	tween.tween_property(btn, "scale", Vector2(0.95, 0.95), 0.1)
	tween.tween_property(btn, "scale", Vector2(1.05, 1.05), 0.1)

func _on_male_pressed():
	selected_gender = "male"
	status_label.text = TRANSLATIONS[detected_lang]["sel_male"]
	btn_male.modulate   = Color(0.2, 1.0, 1.0)
	btn_female.modulate = Color(0.5, 0.5, 0.5)
	animate_click(btn_male)

func _on_female_pressed():
	selected_gender = "female"
	status_label.text = TRANSLATIONS[detected_lang]["sel_female"]
	btn_female.modulate = Color(1.0, 0.2, 0.6)
	btn_male.modulate   = Color(0.5, 0.5, 0.5)
	animate_click(btn_female)

func _on_login_pressed():
	animate_click(btn_login)
	var username = input_name.text.strip_edges()
	var t = TRANSLATIONS[detected_lang]

	if username == "":
		status_label.text = t["err_name"]
		return
	if selected_gender == "":
		status_label.text = t["err_gender"]
		return

	# Guardar datos del usuario (incluyendo wallet, idioma y país)
	var data = {
		"username":  username,
		"gender":    selected_gender,
		"wallet":    wallet_full,
		"lang":      detected_lang,
		"country":   detected_country,
		"timestamp": Time.get_unix_time_from_system()
	}

	# Asegurar que el directorio de destino existe
	var dir_path = save_path.get_base_dir()
	if not DirAccess.dir_exists_absolute(dir_path):
		DirAccess.make_dir_recursive_absolute(dir_path)

	var file = FileAccess.open(save_path, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(data, "\t"))
		file.close()
		print("AVATAR_LOGIN_CLICKED")
		print("Usuario guardado en: ", save_path)
		print("Idioma: ", detected_lang, " | País: ", detected_country)

		# Cambiar Escena
		get_tree().change_scene_to_file("res://woldvirtual/scene/MTC/N3DWoldVirtualMT.tscn")
	else:
		status_label.text = t["err_save"]
