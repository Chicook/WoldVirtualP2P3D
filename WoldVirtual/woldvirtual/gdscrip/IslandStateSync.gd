# Sincronización del Metaverso - DevTraeIA
extends Node

# Rutas dinámicas para portabilidad (RF-01)
var BASE_DIR: String
var PATH: String
var LOCK: String
var PEER_DIR: String

signal network_updated(state: Dictionary)

var data: Dictionary = {}
var _peer_cache: Dictionary = {}
var _known_pids: Array = []
var _missing_counts: Dictionary = {}
var _peer_scan_timer: float = 0.0

func _ready() -> void:
	# Calculamos las rutas absolutas basadas en la ubicación del proyecto
	var project_path = ProjectSettings.globalize_path("res://")
	var base_folder = project_path.get_base_dir() # Sube un nivel desde WoldVirtual/
	
	BASE_DIR = base_folder + "/Estado_Global"
	PATH = BASE_DIR + "/estado.json"
	LOCK = BASE_DIR + "/estado.lock"
	PEER_DIR = BASE_DIR + "/peers/"
	
	# Asegurar que el directorio existe
	if not DirAccess.dir_exists_absolute(BASE_DIR):
		DirAccess.make_dir_recursive_absolute(BASE_DIR)
	if not DirAccess.dir_exists_absolute(PEER_DIR):
		DirAccess.make_dir_recursive_absolute(PEER_DIR)
	
	_load()

## Carga el estado unificado con C#
func _load() -> void:
	var locked = _acquire_lock()
	if FileAccess.file_exists(PATH):
		var f = FileAccess.open(PATH, FileAccess.READ)
		if f:
			var txt = f.get_as_text()
			if txt.strip_edges() != "":
				var parse_res = JSON.parse_string(txt)
				if parse_res is Dictionary: 
					data = parse_res
					if locked: _release_lock()
					return
				else:
					printerr("IslandStateSync: Error parseando estado.json. Se ignora la carga inicial.")
					if locked: _release_lock()
					return

	data = {
		"v": "1.0",
		"ts": Time.get_datetime_string_from_system(),
		"i": {
			"island_0": { "i": "island_0", "n": "Isla Inicial", "o": true }
		},
		"u": {},
		"a": { "i": "id_avatar", "n": "Avatar_1", "o": true }
	}
	_save_no_lock()
	if locked: _release_lock()

func _acquire_lock() -> bool:
	if !FileAccess.file_exists(LOCK):
		var fl = FileAccess.open(LOCK, FileAccess.WRITE)
		if fl:
			fl.store_string(str(OS.get_process_id()))
			return true
	return false

func _release_lock() -> void:
	DirAccess.remove_absolute(LOCK)

func publish_island(id: String, nm: String, file: String, oid: String) -> void:
	var new_is = {
		"i": id,
		"n": nm,
		"f": file,
		"ts": Time.get_datetime_string_from_system(),
		"o": true,
		"w": oid
	}
    
	if not data.has("i") or typeof(data["i"]) != TYPE_DICTIONARY:
		data["i"] = {}
		
	data["i"][id] = new_is
	data["ts"] = Time.get_datetime_string_from_system()
	_save()

func _save() -> void:
	var locked = _acquire_lock()
	_save_no_lock()
	if locked: _release_lock()

func _save_no_lock() -> void:
	if not DirAccess.dir_exists_absolute(BASE_DIR):
		DirAccess.make_dir_recursive_absolute(BASE_DIR)
		
	var f = FileAccess.open(PATH, FileAccess.WRITE)
	if f: 
		f.store_string(JSON.stringify(data, "\t"))
		f.close()

func get_all() -> Array:
	if data.has("i") and typeof(data["i"]) == TYPE_DICTIONARY:
		return data["i"].values()
	return []

func get_stats() -> Dictionary:
	var total = 0
	var active = 0
	if data.has("i") and typeof(data["i"]) == TYPE_DICTIONARY:
		total = data["i"].size()
		for key in data["i"]:
			if data["i"][key].get("o", true): active += 1
	return { "total": total, "active": active, "off": total - active }

# --- Lógica de Red P2P ---
func sync_all_peers(local_id: String, local_data: Dictionary = {}) -> Dictionary:
	if local_id != "" and !local_data.is_empty():
		_save_peer(local_id, local_data)

	var found_now = []
	var dir = DirAccess.open(PEER_DIR)
	if dir:
		dir.list_dir_begin()
		var fn = dir.get_next()
		while fn != "":
			if fn.ends_with(".json") and fn.contains("peer_"):
				found_now.append(fn.replace("peer_", "").replace(".json", ""))
			fn = dir.get_next()
	
	var to_remove = []
	for pid in _known_pids:
		if !found_now.has(pid):
			_missing_counts[pid] = _missing_counts.get(pid, 0) + 1
			if _missing_counts[pid] >= 3: to_remove.append(pid)
		else: _missing_counts[pid] = 0
	for pid in to_remove: _known_pids.erase(pid)
	for pid in found_now:
		if !_known_pids.has(pid):
			_known_pids.append(pid)
			_missing_counts[pid] = 0
	
	var res = {"u": {}, "i": {}, "_pids": _known_pids.duplicate()}
	for pid in _known_pids:
		var path = PEER_DIR + "peer_" + pid + ".json"
		var f = FileAccess.open(path, FileAccess.READ)
		if f:
			var txt = f.get_as_text()
			f.close()
			if txt.strip_edges() != "":
				var p = JSON.parse_string(txt)
				if p is Dictionary:
					if _validate_peer_data(p): _peer_cache[pid] = p
		if _peer_cache.has(pid): _merge_peer(res, _peer_cache[pid])

	for pcid in _peer_cache.keys():
		if !_known_pids.has(pcid): _peer_cache.erase(pcid)

	network_updated.emit(res)
	return res

func _save_peer(id: String, peer_data: Dictionary) -> void:
	var path = PEER_DIR + "peer_" + id + ".json"
	var tmp = path + ".tmp"
	peer_data["ts"] = Time.get_datetime_string_from_system()
	peer_data["v"] = "1.0"
	var f = FileAccess.open(tmp, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(peer_data))
		f.close()
		if FileAccess.file_exists(path): DirAccess.remove_absolute(path)
		DirAccess.rename_absolute(tmp, path)

func _merge_peer(target: Dictionary, peer_data: Dictionary) -> void:
	for uid in peer_data.get("u", {}): target.u[uid] = peer_data.u[uid]
	for iid in peer_data.get("i", {}): target.i[iid] = peer_data.i[iid]

func _validate_peer_data(p: Dictionary) -> bool:
	if not p.has("u") or typeof(p["u"]) != TYPE_DICTIONARY: return false
	return true
