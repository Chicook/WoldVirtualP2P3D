extends SceneTree

func _init() -> void:
	print("--- TEST LOAD START ---")
	var paths = [
		"res://gltfimport/terrenoblok/ISLA3DCHUNK.gltf",
		"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH1Ch3D.tscn",
		"res://ESCENAS/sceneOPTM/constructor/UA/UserAnimados/Import_UserAnimados/ctr_tscn_userBS/scenesconstr/userbaseh1.tscn",
		"res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn"
	]
	for p in paths:
		print("Testing: ", p)
		var res = ResourceLoader.load(p)
		print("  Resource: ", res)
		if res is PackedScene:
			var node = res.instantiate()
			print("  Instantiated node: ", node, " name=", node.name if node else "null")
			if node:
				print("  Child count: ", node.get_child_count())
				node.free()
	print("--- TEST LOAD END ---")
	quit(0)
