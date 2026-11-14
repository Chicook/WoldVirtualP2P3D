extends Node
## Prueba del editor de aspecto: cambia un tinte, aplica y guarda.

func _ready() -> void:
	var packed := load("res://avatares/EditorAspecto.tscn") as PackedScene
	var editor := packed.instantiate()
	editor.call("set_avatar", "AVMJ1")
	add_child(editor)
	await get_tree().create_timer(1.0).timeout
	var pers: Dictionary = editor.get("_pers")
	pers["camiseta"] = Color(0.9, 0.1, 0.1)
	editor.call("_aplicar")
	await get_tree().create_timer(0.4).timeout
	var rojas := 0
	for m in editor.find_children("*", "MeshInstance3D", true, false):
		var mi := m as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			var mat := mi.get_surface_override_material(s)
			if mat is BaseMaterial3D:
				var c := (mat as BaseMaterial3D).albedo_color
				if c.r > 0.35 and c.g < 0.2:
					rojas += 1
	print("[editor] superficies rojas=", rojas)
	editor.call("_guardar")
	await get_tree().create_timer(0.2).timeout
	var cfg := ConfigFile.new()
	var ok := cfg.load("user://registro.cfg") == OK
	var guardado := str(cfg.get_value("personalizacion", "camiseta", "")) if ok else ""
	print("[editor] cfg=", ok, " camiseta=", guardado)
	get_tree().quit(0 if rojas > 0 and guardado.begins_with("e6") else 1)
