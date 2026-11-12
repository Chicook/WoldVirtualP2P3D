extends SceneTree

func _init() -> void:
	var uid_str = "uid://cnclwarjtesb0"
	var id = ResourceUID.text_to_id(uid_str)
	var path = "res://gltfimport/avatares/AVH1.gltf"
	print("Adding UID: ", uid_str, " -> ", path)
	ResourceUID.add_id(id, path)
	print("has_id after add: ", ResourceUID.has_id(id))
	quit(0)
