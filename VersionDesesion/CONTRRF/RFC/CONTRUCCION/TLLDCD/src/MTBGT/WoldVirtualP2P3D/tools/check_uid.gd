extends SceneTree

func _init() -> void:
	print("ResourceUID methods:")
	for m in ClassDB.class_get_method_list("ResourceUID"):
		print("  ", m.name)
	quit(0)
