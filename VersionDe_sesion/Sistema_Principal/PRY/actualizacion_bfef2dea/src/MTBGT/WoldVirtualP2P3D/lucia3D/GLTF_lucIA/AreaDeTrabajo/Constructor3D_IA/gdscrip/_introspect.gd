extends SceneTree
func _initialize() -> void:
	var m := ArrayMesh.new()
	for x in m.get_method_list():
		var n := str(x.name)
		if "blend" in n or "surface" in n:
			print(n, " -> ", x.args)
	quit()
