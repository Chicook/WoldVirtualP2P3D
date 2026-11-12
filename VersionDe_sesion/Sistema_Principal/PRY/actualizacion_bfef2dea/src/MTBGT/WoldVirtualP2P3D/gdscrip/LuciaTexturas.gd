extends Node
## Pone la textura de LucIA sobre su malla del GLB (que llega sin material).

const TEXTURA := "res://lucia3D/textures/Image_0.png"


func _ready() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	var imagen := load(TEXTURA) as Texture2D
	if imagen == null:
		print("[LuciaTexturas] no se pudo cargar la textura")
		return
	var material := StandardMaterial3D.new()
	material.albedo_texture = imagen
	material.roughness = 0.85
	material.metallic = 0.0
	var puestas := 0
	for nodo in get_parent().find_children("*", "MeshInstance3D", true, false):
		var malla := nodo as MeshInstance3D
		if malla == null or malla.mesh == null:
			continue
		for superficie in malla.mesh.get_surface_count():
			malla.set_surface_override_material(superficie, material)
			puestas += 1
	print("[LuciaTexturas] superficies con textura: ", puestas)
