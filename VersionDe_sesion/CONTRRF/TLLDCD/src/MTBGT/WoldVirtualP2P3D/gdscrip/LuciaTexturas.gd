extends Node
## Pone la textura de LucIA sobre su malla cuando el GLB llega sin material.
##
## El modelo riggeado (`LucIA_rig.glb`) ya trae sus tres texturas embebidas; en
## ese caso no hay que pisarlas. `solo_sin_material = true` limita el arreglo a
## las superficies que realmente vienen sin textura.

const TEXTURA := "res://lucia3D/textures/Image_0.png"

@export var solo_sin_material := false


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
	var respetadas := 0
	for nodo in get_parent().find_children("*", "MeshInstance3D", true, false):
		var malla := nodo as MeshInstance3D
		if malla == null or malla.mesh == null:
			continue
		for superficie in malla.mesh.get_surface_count():
			var original := malla.get_surface_override_material(superficie)
			if original == null:
				original = malla.mesh.surface_get_material(superficie)
			if solo_sin_material and original is BaseMaterial3D \
					and (original as BaseMaterial3D).albedo_texture != null:
				respetadas += 1
				continue
			malla.set_surface_override_material(superficie, material)
			puestas += 1
	print("[LuciaTexturas] superficies con textura: ", puestas, " · respetadas: ", respetadas)
