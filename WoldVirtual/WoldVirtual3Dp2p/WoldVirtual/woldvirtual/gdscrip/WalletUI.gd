extends Control

## HUD superior-derecho: Balance + Wallet truncada
## Estilo: Glassmorphism premium con bordes luminosos

@onready var wallet_label = $BgPanel/HBox/WalletLabel
@onready var balance_label = $BgPanel/HBox/BalanceLabel

var _full_wallet := ""

func _ready():
	# 1. Intentar leer de los argumentos de usuario de Godot 4 (después de '--')
	var user_args = OS.get_cmdline_user_args()
	for i in range(user_args.size()):
		if user_args[i] == "--wallet" and i + 1 < user_args.size():
			_full_wallet = user_args[i+1]
			break

	# 2. Si no viene ahí, intentar de los argumentos generales (como fallback)
	if _full_wallet == "" or _full_wallet == "No Wallet Address":
		var args = OS.get_cmdline_args()
		for i in range(args.size()):
			if args[i] == "--wallet" and i + 1 < args.size():
				_full_wallet = args[i+1]
				break

	# 3. Si no viene en los argumentos, intentar leer del perfil JSON
	if _full_wallet == "" or _full_wallet == "No Wallet Address":
		var user_path = "res://woldvirtual/scene/MTC/users3D/current_user.json"
		var file = FileAccess.open(user_path, FileAccess.READ)
		
		if file:
			var json_text = file.get_as_text()
			file.close()
			var json = JSON.new()
			if json.parse(json_text) == OK:
				var data = json.data
				if data.has("wallet") and data["wallet"] != "":
					_full_wallet = data["wallet"]

	# Mostrar wallet TRUNCADA (profesional)
	if _full_wallet.length() > 10:
		wallet_label.text = _full_wallet.substr(0, 6) + "..." + _full_wallet.substr(_full_wallet.length() - 4)
	elif _full_wallet != "":
		wallet_label.text = _full_wallet
	else:
		wallet_label.text = "No Wallet"

	# Balance con formato
	balance_label.text = "0.000 WCV"

	# ── Estilo Premium del Panel ──
	var sb = StyleBoxFlat.new()
	sb.bg_color = Color(0.04, 0.06, 0.12, 0.92)
	sb.set_corner_radius_all(12)
	sb.border_width_top = 1
	sb.border_width_bottom = 1
	sb.border_width_left = 1
	sb.border_width_right = 1
	sb.border_color = Color(0.0, 0.85, 1.0, 0.35)
	sb.shadow_color = Color(0.0, 0.6, 1.0, 0.15)
	sb.shadow_size = 6
	sb.content_margin_left = 16
	sb.content_margin_right = 16
	sb.content_margin_top = 8
	sb.content_margin_bottom = 8
	$BgPanel.add_theme_stylebox_override("panel", sb)

	# Estilo de los labels
	balance_label.add_theme_color_override("font_color", Color(0.0, 1.0, 0.65, 1.0))
	balance_label.add_theme_font_size_override("font_size", 15)
	wallet_label.add_theme_color_override("font_color", Color(0.55, 0.82, 1.0, 0.9))
	wallet_label.add_theme_font_size_override("font_size", 13)
