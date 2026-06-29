extends Node

signal network_updated(state: Dictionary)

# Rutas dinámicas para portabilidad
var BASE_DIR: String
var PEER_DIR: String
const INTERVAL = 1.5

var local_id: String = ""
var poll: float = 0.0
var _peer_scan_timer: float = 0.0
var _last_good_state: Dictionary = {"u": {}, "i": {}}
var _first_load_done: bool = false

var _peer_cache: Dictionary = {}
var _peer_last_seen: Dictionary = {}
var _known_pids: Array = []
var _missing_counts: Dictionary = {}

var _ws := WebSocketPeer.new()
var _ws_connected := false

func _ready() -> void:
	# Calculamos las rutas absolutas basadas en la ubicación del proyecto
	var project_path = ProjectSettings.globalize_path("res://")
	var base_folder = project_path.get_base_dir()
	
	BASE_DIR = base_folder + "/Estado_Global"
	PEER_DIR = BASE_DIR + "/peers/"
	
	if !DirAccess.dir_exists_absolute(PEER_DIR):
		DirAccess.make_dir_recursive_absolute(PEER_DIR)
		
	_setup_identity()
	
	var err = _ws.connect_to_url("ws://127.0.0.1:8082/ws")
	if err != OK:
		print("Failed to start WebSocket connection: ", err)
		
	_initial_sync()

func _setup_identity():
	var args = OS.get_cmdline_args() + OS.get_cmdline_user_args()
	for i in args.size():
		if args[i] == "--user-id" and i + 1 < args.size():
			local_id = args[i+1]
			break
	if local_id == "":
		local_id = str(Time.get_ticks_usec() + OS.get_process_id()).md5_text().substr(0, 8)

func _initial_sync():
	for i in 5:
		_io()
		if _first_load_done: break
		OS.delay_msec(100)

func _process(delta: float) -> void:
	_ws.poll()
	var state = _ws.get_ready_state()
	
	if state == WebSocketPeer.STATE_OPEN:
		if not _ws_connected:
			_ws_connected = true
			print("Godot WebSocket connected!")
			
		while _ws.get_available_packet_count() > 0:
			var packet = _ws.get_packet()
			var text = packet.get_string_from_utf8()
			var p = JSON.parse_string(text)
			if typeof(p) == TYPE_DICTIONARY:
				var rem_id = ""
				if p.has("u") and typeof(p.u) == TYPE_DICTIONARY and p.u.size() > 0:
					rem_id = p.u.keys()[0]
				elif p.has("i") and typeof(p.i) == TYPE_DICTIONARY and p.i.size() > 0:
					rem_id = p.i.keys()[0]
				
				if rem_id != "" and rem_id != local_id:
					_peer_cache[rem_id] = p
					_peer_last_seen[rem_id] = Time.get_unix_time_from_system()
					if not _known_pids.has(rem_id):
						_known_pids.append(rem_id)
						_missing_counts[rem_id] = 0
					
					_emit_aggregated_state()
					
	elif state == WebSocketPeer.STATE_CLOSED:
		if _ws_connected:
			_ws_connected = false
			print("Godot WebSocket closed.")
			
	poll += delta
	_peer_scan_timer += delta
	if poll >= (INTERVAL if not _ws_connected else 5.0) + randf_range(0.0, 0.05):
		poll = 0.0
		var io_state = _io()
		if not io_state.is_empty():
			network_updated.emit(io_state)

func _emit_aggregated_state():
	var res = {"u": {}, "i": {}, "e": {}, "_pids": _known_pids.duplicate()}
	for pid in _known_pids:
		if _peer_cache.has(pid):
			_merge_peer(res, _peer_cache[pid], pid)
	
	if res.u.is_empty(): return
	_first_load_done = true
	_last_good_state = res
	network_updated.emit(res)

func get_local_id() -> String:
	return local_id

func send_state(u_data: Dictionary, i_data: Dictionary):
	_io({
		"u": { local_id: u_data },
		"i": { local_id: i_data }
	})

var _event_queue: Array = []

func push_event(type: String, data: Dictionary = {}):
	var e = {"type": type, "ts": Time.get_unix_time_from_system()}
	e.merge(data)
	_event_queue.append(e)

func _io(data: Dictionary = {}) -> Dictionary:
	var final_path = PEER_DIR + "peer_" + local_id + ".json"
	if !data.is_empty():
		var current_peer_data = _peer_cache.get(local_id, {})
		for key in current_peer_data:
			if not data.has(key): data[key] = current_peer_data[key]
		
		# Incluir eventos pendientes
		if !_event_queue.is_empty():
			data["e"] = _event_queue.duplicate()
			_event_queue.clear()
		else:
			data.erase("e") # Limpiar eventos antiguos del archivo
			
		data["ts"] = Time.get_datetime_string_from_system()
		data["v"] = "1.0"
		var tmp = final_path + ".tmp"
		var f = FileAccess.open(tmp, FileAccess.WRITE)
		if f:
			f.store_string(JSON.stringify(data))
			f.close()
			if FileAccess.file_exists(final_path): DirAccess.remove_absolute(final_path)
			DirAccess.rename_absolute(tmp, final_path)
		return {}

	# Optimización en Memoria vía WebSockets
	if _ws_connected:
		var current_time = Time.get_unix_time_from_system()
		var to_remove = []
		for pid in _known_pids:
			if _peer_cache.has(pid) and current_time - _peer_last_seen[pid] > 10.0:
				to_remove.append(pid)
		for pid in to_remove:
			_known_pids.erase(pid)
			_peer_cache.erase(pid)
			_peer_last_seen.erase(pid)
			
		var res = {"u": {}, "i": {}, "e": {}, "_pids": _known_pids.duplicate()}
		for pid in _known_pids:
			if _peer_cache.has(pid): _merge_peer(res, _peer_cache[pid], pid)
		if res.u.is_empty(): return _last_good_state
		_first_load_done = true
		_last_good_state = res
		return res

	# Fallback a lectura de disco (si no hay WS)
	if _peer_scan_timer >= 1.5 or _known_pids.is_empty():
		_peer_scan_timer = 0.0
		var found_now = []
		var dir = DirAccess.open(PEER_DIR)
		if dir:
			dir.list_dir_begin()
			var fn = dir.get_next()
			while fn != "":
				if fn.ends_with(".json"):
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
	
	var res = {"u": {}, "i": {}, "e": {}, "_pids": _known_pids.duplicate()}
	for pid in _known_pids:
		var path = PEER_DIR + "peer_" + pid + ".json"
		var f = FileAccess.open(path, FileAccess.READ)
		if f:
			var txt = f.get_as_text()
			f.close()
			if txt.strip_edges() != "":
				var p = JSON.parse_string(txt)
				if p is Dictionary:
					_peer_cache[pid] = p
					_peer_last_seen[pid] = Time.get_unix_time_from_system()
		if _peer_cache.has(pid): _merge_peer(res, _peer_cache[pid], pid)

	for pcid in _peer_cache.keys():
		if !_known_pids.has(pcid):
			_peer_cache.erase(pcid)
			_peer_last_seen.erase(pcid)

	if res.u.is_empty(): return _last_good_state
	_first_load_done = true
	_last_good_state = res
	return res

func _merge_peer(target: Dictionary, peer_data: Dictionary, pid: String):
	for uid in peer_data.get("u", {}): target.u[uid] = peer_data.u[uid]
	for iid in peer_data.get("i", {}): target.i[iid] = peer_data.i[iid]
	if peer_data.has("e"): target.e[pid] = peer_data.e
