extends SceneTree
## Valida la personalizacion sobre los 24 avatares: deformacion real de la
## malla, altura total, idempotencia y vuelta al original. No escribe
## configuracion.

const Pers = preload("res://gdscrip/Personalizacion.gd")

const DIRS := [
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC",
	"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ",
]

const MAXIMO := {
	"altura_cm": 30.0, "ancho": 1.15, "cabeza": 1.15,
	"hombros": 1.25, "torso": 1.25, "brazos": 1.25, "piernas": 1.25,
	"nariz": 1.0, "labios": 1.0, "orejas": 1.0, "ojos": 1.0,
}


func _initialize() -> void:
	_correr()


func _correr() -> void:
	await process_frame
	var fallos := 0
	for dir in DIRS:
		var da := DirAccess.open(dir)
		if da == null:
			print("FALLO no existe ", dir)
			fallos += 1
			continue
		var nombres: Array = []
		for f in da.get_files():
			if f.ends_with("Ch3D.tscn"):
				nombres.append(f)
		nombres.sort()
		for f in nombres:
			fallos += await _probar(dir.path_join(f))
	print("== fin, fallos=%d ==" % fallos)
	quit(1 if fallos > 0 else 0)


func _probar(ruta: String) -> int:
	var fallos := 0
	var avatar := (load(ruta) as PackedScene).instantiate() as Node3D
	get_root().add_child(avatar)
	await process_frame
	avatar.set_physics_process(false)
	Pers.aplicar(avatar, Pers.POR_DEFECTO)
	var sk := Pers._esqueleto(avatar)
	var idx := Pers._indices_huesos(sk)
	var cuerpo := Pers._buscar_cuerpo(avatar, idx)
	if cuerpo == null:
		print("FALLO sin malla de cuerpo: ", ruta)
		avatar.queue_free()
		return 1
	var malla_base: Mesh = cuerpo.mesh
	var base_altura := Pers.altura_total(avatar)

	var datos := Pers.POR_DEFECTO.duplicate()
	for clave in MAXIMO:
		datos[clave] = MAXIMO[clave]
	Pers.aplicar(avatar, datos)
	var malla_max: Mesh = cuerpo.mesh
	var alto := Pers.altura_total(avatar)
	var esperado := base_altura + 0.30
	var movidos := _vertices_movidos(malla_base, malla_max)
	print("%s base=%.3f m max=%.3f m movidos=%d" % [ruta.get_file(), base_altura, alto, movidos])
	if malla_max == malla_base:
		print("FALLO la malla no se reconstruyo: ", ruta)
		fallos += 1
	if movidos < 500:
		print("FALLO demasiado pocos vertices deformados: ", movidos)
		fallos += 1
	if absf(alto - esperado) > 0.01:
		print("FALLO altura %.3f, esperada %.3f" % [alto, esperado])
		fallos += 1

	var modelo := Pers._modelo(avatar)
	var escala1: Vector3 = modelo.scale
	Pers.aplicar(avatar, datos)
	if not modelo.scale.is_equal_approx(escala1):
		print("FALLO escala acumulada: ", escala1, " -> ", modelo.scale)
		fallos += 1
	var i_cabeza := Pers._hueso(sk, "Head")
	if i_cabeza < 0 or not sk.get_bone_pose_scale(i_cabeza).is_equal_approx(Vector3.ONE * 1.15):
		print("FALLO escala de cabeza: ", sk.get_bone_pose_scale(i_cabeza) if i_cabeza >= 0 else "sin hueso")
		fallos += 1

	Pers.aplicar(avatar, Pers.POR_DEFECTO)
	if cuerpo.mesh != malla_base:
		print("FALLO no se restauro la malla original")
		fallos += 1
	if absf(Pers.altura_total(avatar) - base_altura) > 0.005:
		print("FALLO altura no restaurada: ", Pers.altura_total(avatar))
		fallos += 1

	avatar.queue_free()
	await process_frame
	return fallos


func _vertices_movidos(a: Mesh, b: Mesh) -> int:
	var movidos := 0
	for s in mini(a.get_surface_count(), b.get_surface_count()):
		var va: PackedVector3Array = (a.surface_get_arrays(s) as Array)[Mesh.ARRAY_VERTEX]
		var vb: PackedVector3Array = (b.surface_get_arrays(s) as Array)[Mesh.ARRAY_VERTEX]
		for i in mini(va.size(), vb.size()):
			if not va[i].is_equal_approx(vb[i]):
				movidos += 1
	return movidos
