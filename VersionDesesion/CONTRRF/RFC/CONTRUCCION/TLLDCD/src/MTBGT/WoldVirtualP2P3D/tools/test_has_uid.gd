extends SceneTree

func _init() -> void:
	var uid_str = "uid://cnclwarjtesb0"
	var id = ResourceUID.text_to_id(uid_str)
	print("has_id for ", uid_str, " (id=", id, "): ", ResourceUID.has_id(id))
	if ResourceUID.has_id(id):
		print("  path: ", ResourceUID.get_id_path(id))
	quit(0)
