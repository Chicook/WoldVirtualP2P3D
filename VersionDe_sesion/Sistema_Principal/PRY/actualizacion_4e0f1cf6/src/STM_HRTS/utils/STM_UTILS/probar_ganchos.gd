extends SceneTree
## Comprueba que el portal aplica el aspecto al avatar y que los scripts de
## mundo/red siguen cargando. No escribe configuracion.

const Pers = preload("res://gdscrip/Personalizacion.gd")
const PORTAL := "res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/entornodeprueba.tscn"
const AVATAR := "res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH5Ch3D.tscn"


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	var fallos := 0
	for script in ["res://gdscrip/Personalizacion.gd", "res://gdscrip/PlayerSync.gd", "res://gdscrip/ChunkManager.gd"]:
		if load(script) == null:
			print("FALLO no carga ", script)
			fallos += 1
		else:
			print("carga OK ", script)

	var vacio := Pers.decodificar("")
	if not (vacio["camiseta"] as Color).is_equal_approx(Color.WHITE) or float(vacio["altura_cm"]) != 0.0:
		print("FALLO decodificar vacio: ", vacio)
		fallos += 1
	else:
		print("decodificar vacio: OK")

	var portal := (load(PORTAL) as PackedScene).instantiate()
	get_root().add_child(portal)
	await process_frame
	portal.set_player_avatar(AVATAR)
	await process_frame
	var avatar := portal.get_node_or_null("PlayerAvatar")
	if avatar == null:
		print("FALLO portal sin PlayerAvatar")
		fallos += 1
	else:
		var modelo := Pers._modelo(avatar)
		var base: Vector3 = avatar.get_meta("pers_escala_base", Vector3.ONE)
		if modelo == null or not modelo.scale.is_equal_approx(base):
			print("FALLO escala del portal: ", modelo.scale if modelo else null, " base=", base)
			fallos += 1
		else:
			print("portal: avatar y escala OK ", modelo.scale)

	print("== fin, fallos=%d ==" % fallos)
	quit(1 if fallos > 0 else 0)
