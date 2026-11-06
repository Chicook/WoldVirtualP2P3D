extends SceneTree
## Reproduce el flujo registro -> portal: cambia el aspecto en la pantalla de
## registro, guarda como lo hace _on_confirmar_pressed y comprueba que el
## avatar del portal sale personalizado. Hace copia de seguridad de
## user://registro.cfg y la restaura al terminar.

const Pers = preload("res://gdscrip/Personalizacion.gd")
const REGISTRO := "res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/registro.tscn"
const PORTAL := "res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/entornodeprueba.tscn"
const AVATAR := "res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH5Ch3D.tscn"

const DATOS := {
	"piel": Color("8d5524"),
	"pelo": Color("c9a227"),
	"camiseta": Color("c62828"),
	"pantalon": Color("1e3a8a"),
	"zapatillas": Color("eeeeee"),
	"altura_cm": 10.0,
	"ancho": 1.04,
	"cabeza": 1.05,
	"hombros": 1.08,
	"torso": 1.04,
	"brazos": 1.06,
	"piernas": 1.05,
	"nariz": 0.4,
	"labios": 0.6,
	"orejas": 0.3,
	"ojos": 0.5,
}

const CONTROLES := {
	"Panel/Personalizacion/Tabs/Colores/PersGrid/Piel/Color": "piel",
	"Panel/Personalizacion/Tabs/Colores/PersGrid/Pelo/Color": "pelo",
	"Panel/Personalizacion/Tabs/Colores/PersGrid/Camiseta/Color": "camiseta",
	"Panel/Personalizacion/Tabs/Colores/PersGrid/Pantalon/Color": "pantalon",
	"Panel/Personalizacion/Tabs/Colores/PersGrid/Zapatillas/Color": "zapatillas",
	"Panel/Personalizacion/Tabs/Cuerpo/AlturaFila/Slider": "altura_cm",
	"Panel/Personalizacion/Tabs/Cuerpo/AnchoFila/Slider": "ancho",
	"Panel/Personalizacion/Tabs/Cuerpo/CabezaFila/Slider": "cabeza",
	"Panel/Personalizacion/Tabs/Cuerpo/HombrosFila/Slider": "hombros",
	"Panel/Personalizacion/Tabs/Cuerpo/TorsoFila/Slider": "torso",
	"Panel/Personalizacion/Tabs/Cuerpo/BrazosFila/Slider": "brazos",
	"Panel/Personalizacion/Tabs/Cuerpo/PiernasFila/Slider": "piernas",
	"Panel/Personalizacion/Tabs/Cara/NarizFila/Slider": "nariz",
	"Panel/Personalizacion/Tabs/Cara/LabiosFila/Slider": "labios",
	"Panel/Personalizacion/Tabs/Cara/OrejasFila/Slider": "orejas",
	"Panel/Personalizacion/Tabs/Cara/OjosFila/Slider": "ojos",
}

var _fallos := 0
var _cfg := ""
var _respaldo := ""


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	_cfg = ProjectSettings.globalize_path("user://registro.cfg")
	_respaldo = _cfg + ".prueba_portal.bak"
	if FileAccess.file_exists(_cfg):
		DirAccess.copy_absolute(_cfg, _respaldo)
	else:
		_respaldo = ""

	var reg := (load(REGISTRO) as PackedScene).instantiate()
	get_root().add_child(reg)
	await process_frame
	reg.set_avatar_scene(AVATAR)
	await process_frame

	for ruta in CONTROLES:
		var nodo := reg.get_node(ruta)
		var clave: String = CONTROLES[ruta]
		if nodo is ColorPickerButton:
			nodo.color = DATOS[clave]
		else:
			nodo.value = float(DATOS[clave])
	reg._on_pers_cambiada()
	await process_frame

	# Mismo guardado que _on_confirmar_pressed (sin escribir el hash de usuario).
	var cfg := ConfigFile.new()
	cfg.set_value("jugador", "nick", "prueba")
	cfg.set_value("jugador", "avatar_scene", AVATAR)
	cfg.save("user://registro.cfg")
	Pers.guardar(reg._pers)

	var leido := Pers.leer()
	_check(absf(float(leido["altura_cm"]) - 10.0) < 0.01, "altura guardada en disco")
	_check((leido["camiseta"] as Color).is_equal_approx(DATOS["camiseta"]), "color guardado en disco")

	reg.queue_free()
	await process_frame

	var portal := (load(PORTAL) as PackedScene).instantiate()
	get_root().add_child(portal)
	await process_frame
	portal.set_player_avatar(AVATAR)
	await process_frame
	await process_frame

	var avatar := portal.get_node_or_null("PlayerAvatar")
	_check(avatar != null, "el portal instancia PlayerAvatar")
	if avatar != null:
		var modelo := Pers._modelo(avatar)
		_check(modelo != null, "el portal encuentra el modelo")
		var alto := Pers.altura_total(avatar)
		var base := 0.0
		if modelo != null:
			base = float(avatar.get_meta("pers_altura_base", -1.0))
		print("altura base=%.3f total=%.3f" % [base, alto])
		_check(base > 0.0 and absf(alto - (base + 0.10)) < 0.02, "altura aplicada en el portal")
		if modelo != null:
			var piezas := _tintes(avatar)
			_check(piezas.has("camiseta") and (piezas["camiseta"] as Color).is_equal_approx(DATOS["camiseta"]),
					"camiseta personalizada en el portal")
			_check(piezas.has("piel") and (piezas["piel"] as Color).is_equal_approx(DATOS["piel"]),
					"piel personalizada en el portal")

	_restaurar()
	print("== fin, fallos=%d ==" % _fallos)
	quit(1 if _fallos > 0 else 0)


func _tintes(avatar: Node) -> Dictionary:
	var vistos := {}
	for nodo in avatar.find_children("*", "MeshInstance3D", true, false):
		var mi := nodo as MeshInstance3D
		var parte := Pers._parte(mi.name)
		if parte == "":
			continue
		var mat := mi.get_surface_override_material(0) as BaseMaterial3D
		if mat != null:
			vistos[parte] = mat.albedo_color
	return vistos


func _restaurar() -> void:
	if FileAccess.file_exists(_cfg):
		DirAccess.remove_absolute(_cfg)
	if _respaldo != "" and FileAccess.file_exists(_respaldo):
		DirAccess.copy_absolute(_respaldo, _cfg)
		DirAccess.remove_absolute(_respaldo)


func _check(ok: bool, texto: String) -> void:
	if ok:
		print("OK   ", texto)
	else:
		_fallos += 1
		print("FALLO ", texto)
