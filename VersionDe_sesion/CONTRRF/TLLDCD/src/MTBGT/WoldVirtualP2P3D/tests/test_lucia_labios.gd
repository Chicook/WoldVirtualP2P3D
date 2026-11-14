extends Node
## Comprueba que la boca de LucIA cambia de valor mientras habla.

func _ready() -> void:
	var packed := load("res://WoldVirtual3DP2P.tscn") as PackedScene
	add_child(packed.instantiate())
	await get_tree().create_timer(1.8).timeout
	var malla := _malla_boca()
	if malla == null:
		print("[labios] no se encontró malla con blend shape")
		get_tree().quit(1)
		return
	print("[labios] blend shapes=", malla.mesh.get_blend_shape_count())
	var valores: Array[float] = []
	for i in 8:
		valores.append(malla.get_blend_shape_value(0))
		await get_tree().create_timer(0.12).timeout
	print("[labios] valores=", valores)
	var minimo: float = valores.min()
	var maximo: float = valores.max()
	print("[labios] rango=", maximo - minimo)
	get_tree().quit(0 if maximo - minimo > 0.05 else 1)


func _malla_boca() -> MeshInstance3D:
	for nodo in get_tree().root.find_children("*", "MeshInstance3D", true, false):
		var malla := nodo as MeshInstance3D
		if malla.mesh != null and malla.mesh.has_method("get_blend_shape_count") \
				and malla.mesh.get_blend_shape_count() > 0:
			return malla
	return null
