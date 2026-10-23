extends SceneTree
## Prueba la pantalla de registro: layout con pestanas, personalizacion en vivo,
## ida y vuelta del aspecto y que aplicar dos veces no acumule escala.
## No confirma el registro: no escribe user://registro.cfg.

const Pers = preload("res://gdscrip/Personalizacion.gd")
const REGISTRO := "res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/registro.tscn"
const AVATAR := "res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH5Ch3D.tscn"

const CONTROLES := [
	"Panel/Personalizacion/Tabs/Colores/PersGrid/Piel/Color",
	"Panel/Personalizacion/Tabs/Colores/PersGrid/Pelo/Color",
	"Panel/Personalizacion/Tabs/Colores/PersGrid/Camiseta/Color",
	"Panel/Personalizacion/Tabs/Colores/PersGrid/Pantalon/Color",
	"Panel/Personalizacion/Tabs/Colores/PersGrid/Zapatillas/Color",
	"Panel/Personalizacion/Tabs/Cuerpo/AlturaFila/Slider",
	"Panel/Personalizacion/Tabs/Cuerpo/AnchoFila/Slider",
	"Panel/Personalizacion/Tabs/Cuerpo/CabezaFila/Slider",
	"Panel/Personalizacion/Tabs/Cuerpo/HombrosFila/Slider",
	"Panel/Personalizacion/Tabs/Cuerpo/TorsoFila/Slider",
	"Panel/Personalizacion/Tabs/Cuerpo/BrazosFila/Slider",
	"Panel/Personalizacion/Tabs/Cuerpo/PiernasFila/Slider",
	"Panel/Personalizacion/Tabs/Cara/NarizFila/Slider",
	"Panel/Personalizacion/Tabs/Cara/LabiosFila/Slider",
	"Panel/Personalizacion/Tabs/Cara/OrejasFila/Slider",
	"Panel/Personalizacion/Tabs/Cara/OjosFila/Slider",
]

const DATOS := {
	"piel": Color("b98a6a"),
	"pelo": Color("c9a227"),
	"camiseta": Color("c62828"),
	"pantalon": Color("1e3a8a"),
	"zapatillas": Color("eeeeee"),
	"altura_cm": 8.0,
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


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	get_root().size = Vector2i(1280, 720)
	var reg := (load(REGISTRO) as PackedScene).instantiate()
	get_root().add_child(reg)
	await process_frame

	var fallos := 0
	for ruta in CONTROLES:
		if reg.get_node_or_null(ruta) == null:
			print("FALLO control ausente: ", ruta)
			fallos += 1
	print("controles: ", "OK" if fallos == 0 else "FALLO")

	reg.set_avatar_scene(AVATAR)
	await process_frame
	await process_frame
	# Altura base del avatar sin personalizacion, para comprobar el +8 cm.
	Pers.aplicar(reg._preview, Pers.POR_DEFECTO)
	var alto_base := Pers.altura_total(reg._preview)

	var carpetas := OS.get_environment("TEMP").path_join("pers")
	DirAccess.make_dir_recursive_absolute(carpetas)
	var tabs: TabContainer = reg.get_node("Panel/Personalizacion/Tabs")
	tabs.current_tab = 0
	await create_timer(0.4).timeout
	get_root().get_texture().get_image().save_png(carpetas.path_join("registro_tab_colores.png"))

	for ruta in CONTROLES:
		var nodo := reg.get_node(ruta)
		if nodo is ColorPickerButton:
			nodo.color = DATOS[_clave(ruta)]
		else:
			nodo.value = float(DATOS[_clave(ruta)])
	reg._on_pers_cambiada()
	await create_timer(0.8).timeout

	var preview: Node3D = reg._preview
	fallos += _comprobar_preview(preview, DATOS)

	# Aplicar dos veces no debe acumular la escala del modelo.
	var modelo := Pers._modelo(preview)
	var escala1: Vector3 = modelo.scale
	Pers.aplicar(preview, DATOS)
	await process_frame
	if not modelo.scale.is_equal_approx(escala1):
		print("FALLO escala acumulada: ", escala1, " -> ", modelo.scale)
		fallos += 1
	else:
		print("escala idempotente: OK ", modelo.scale)

	var alto := Pers.altura_total(preview)
	print("altura base: %.3f m | con +8 cm: %.3f m" % [alto_base, alto])
	if absf(alto - (alto_base + 0.08)) > 0.01:
		print("FALLO altura esperada %.3f, obtenida %.3f" % [alto_base + 0.08, alto])
		fallos += 1

	# Ida y vuelta del texto que se replica por red.
	var texto := Pers.codificar(DATOS)
	var vuelta := Pers.decodificar(texto)
	for clave in Pers.ORDEN:
		if not (vuelta[clave] as Color).is_equal_approx(DATOS[clave]):
			print("FALLO ida/vuelta ", clave, ": ", vuelta[clave], " != ", DATOS[clave])
			fallos += 1
	for clave in Pers.PROPORCIONES + Pers.ROSTRO:
		if absf(float(vuelta[clave]) - float(DATOS[clave])) > 0.001:
			print("FALLO ida/vuelta ", clave, ": ", vuelta[clave])
			fallos += 1
	print("serializacion: ", texto)

	tabs.current_tab = 1
	await create_timer(0.4).timeout
	get_root().get_texture().get_image().save_png(carpetas.path_join("registro_tab_cuerpo.png"))
	tabs.current_tab = 2
	await create_timer(0.4).timeout
	get_root().get_texture().get_image().save_png(carpetas.path_join("registro_tab_cara.png"))

	print("== fin, fallos=%d ==" % fallos)
	quit(1 if fallos > 0 else 0)


func _clave(ruta: String) -> String:
	match ruta:
		"Panel/Personalizacion/Tabs/Colores/PersGrid/Piel/Color": return "piel"
		"Panel/Personalizacion/Tabs/Colores/PersGrid/Pelo/Color": return "pelo"
		"Panel/Personalizacion/Tabs/Colores/PersGrid/Camiseta/Color": return "camiseta"
		"Panel/Personalizacion/Tabs/Colores/PersGrid/Pantalon/Color": return "pantalon"
		"Panel/Personalizacion/Tabs/Colores/PersGrid/Zapatillas/Color": return "zapatillas"
		"Panel/Personalizacion/Tabs/Cuerpo/AlturaFila/Slider": return "altura_cm"
		"Panel/Personalizacion/Tabs/Cuerpo/AnchoFila/Slider": return "ancho"
		"Panel/Personalizacion/Tabs/Cuerpo/CabezaFila/Slider": return "cabeza"
		"Panel/Personalizacion/Tabs/Cuerpo/HombrosFila/Slider": return "hombros"
		"Panel/Personalizacion/Tabs/Cuerpo/TorsoFila/Slider": return "torso"
		"Panel/Personalizacion/Tabs/Cuerpo/BrazosFila/Slider": return "brazos"
		"Panel/Personalizacion/Tabs/Cuerpo/PiernasFila/Slider": return "piernas"
		"Panel/Personalizacion/Tabs/Cara/NarizFila/Slider": return "nariz"
		"Panel/Personalizacion/Tabs/Cara/LabiosFila/Slider": return "labios"
		"Panel/Personalizacion/Tabs/Cara/OrejasFila/Slider": return "orejas"
		"Panel/Personalizacion/Tabs/Cara/OjosFila/Slider": return "ojos"
	return ""


func _comprobar_preview(preview: Node3D, datos: Dictionary) -> int:
	var fallos := 0
	if preview == null:
		print("FALLO sin preview")
		return 1
	var vistos := {}
	for nodo in preview.find_children("*", "MeshInstance3D", true, false):
		var mi := nodo as MeshInstance3D
		var parte := Pers._parte(mi.name)
		if parte == "":
			continue
		var mat := mi.get_surface_override_material(0) as BaseMaterial3D
		if mat == null:
			print("FALLO sin override en ", mi.name)
			fallos += 1
			continue
		vistos[parte] = mat.albedo_color
	for parte in vistos:
		if not (vistos[parte] as Color).is_equal_approx(datos[parte]):
			print("FALLO tinte ", parte, ": ", vistos[parte], " != ", datos[parte])
			fallos += 1
	print("tintes aplicados: ", vistos.keys())
	return fallos
