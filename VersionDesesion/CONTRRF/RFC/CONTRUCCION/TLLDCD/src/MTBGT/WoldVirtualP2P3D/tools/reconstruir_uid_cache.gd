extends SceneTree

func _init() -> void:
	print("--- REGENERANDO UID CACHE EXACTO ---")
	var cache_file = "res://.godot/uid_cache.bin"
	
	# Regexes
	var rx_header = RegEx.new()
	rx_header.compile('^\\[(?:gd_scene|gd_resource)[^\\]]*uid="(uid://[a-zA-Z0-9]+)"')
	var rx_import_uid = RegEx.new()
	rx_import_uid.compile('uid="(uid://[a-zA-Z0-9]+)"')
	var rx_import_src = RegEx.new()
	rx_import_src.compile('source_file="(res://[^"]+)"')
	var rx_ext1 = RegEx.new()
	rx_ext1.compile('\\[ext_resource[^\\]]*uid="(uid://[a-zA-Z0-9]+)"[^\\]]*path="(res://[^"]+)"')
	var rx_ext2 = RegEx.new()
	rx_ext2.compile('\\[ext_resource[^\\]]*path="(res://[^"]+)"[^\\]]*uid="(uid://[a-zA-Z0-9]+)"')
	
	var uids = {} # int64 id -> String path
	
	# Escanear res://
	var dirs = ["res://"]
	var all_files = []
	while dirs.size() > 0:
		var d = dirs.pop_back()
		var dir = DirAccess.open(d)
		if dir:
			dir.list_dir_begin()
			var name = dir.get_next()
			while name != "":
				if name != "." and name != "..":
					var full = d + ("/" if not d.ends_with("/") else "") + name
					if dir.current_is_dir():
						if name != ".godot":
							dirs.append(full)
					else:
						all_files.append(full)
				name = dir.get_next()
			dir.list_dir_end()
			
	for f in all_files:
		if f.ends_with(".import"):
			var fa = FileAccess.open(f, FileAccess.READ)
			if fa:
				var txt = fa.get_as_text()
				fa.close()
				var mu = rx_import_uid.search(txt)
				var ms = rx_import_src.search(txt)
				if mu:
					var target = ms.get_string(1) if ms else f.substr(0, f.length() - 7)
					var id = ResourceUID.text_to_id(mu.get_string(1))
					if id != ResourceUID.INVALID_ID:
						uids[id] = target
		elif f.ends_with(".tscn") or f.ends_with(".tres"):
			var fa = FileAccess.open(f, FileAccess.READ)
			if fa:
				var line1 = fa.get_line()
				var mh = rx_header.search(line1)
				if mh:
					var id = ResourceUID.text_to_id(mh.get_string(1))
					if id != ResourceUID.INVALID_ID:
						uids[id] = f
				for i in range(50):
					var line = fa.get_line()
					if line.begins_with("[sub_resource") or line.begins_with("[node"):
						break
					var m1 = rx_ext1.search(line)
					if m1:
						var id = ResourceUID.text_to_id(m1.get_string(1))
						if id != ResourceUID.INVALID_ID:
							uids[id] = m1.get_string(2)
					var m2 = rx_ext2.search(line)
					if m2:
						var id = ResourceUID.text_to_id(m2.get_string(2))
						if id != ResourceUID.INVALID_ID:
							uids[id] = m2.get_string(1)
				fa.close()
				
	print("Total UIDs mapeados: ", uids.size())
	
	# Guardar en cache_file
	var out = FileAccess.open(cache_file, FileAccess.WRITE)
	if out:
		out.store_32(uids.size())
		for id in uids:
			out.store_64(id)
			var pb = uids[id].to_utf8_buffer()
			out.store_32(pb.size())
			out.store_buffer(pb)
		out.close()
		print("âœ” uid_cache.bin guardado correctamente.")
	else:
		printerr("ERROR: no se pudo escribir ", cache_file)
		
	# Verificaciones
	var id_blgl = ResourceUID.text_to_id("uid://blglsbol7iwh4")
	var id_avh1 = ResourceUID.text_to_id("uid://cnclwarjtesb0")
	var id_isla = ResourceUID.text_to_id("uid://nx5703p746xp")
	var id_hm1  = ResourceUID.text_to_id("uid://wtu4b26xpfqi")
	print("blglsbol7iwh4 -> ", uids.get(id_blgl))
	print("cnclwarjtesb0 -> ", uids.get(id_avh1))
	print("nx5703p746xp  -> ", uids.get(id_isla))
	print("wtu4b26xpfqi  -> ", uids.get(id_hm1))
	print("--- FIN REGENERACION ---")
	quit(0)
