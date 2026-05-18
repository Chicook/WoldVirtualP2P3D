extends Node

const STATUS_PATH = "res://Estado_Global/vram_status.json"
const POLL_INTERVAL = 2.0

var poll_timer: float = 0.0

func _process(delta: float) -> void:
	poll_timer += delta
	if poll_timer >= POLL_INTERVAL:
		poll_timer = 0.0
		_update_status()

func _update_status():
	var vram = Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED)
	var ram = OS.get_static_memory_usage()
	
	var data = {
		"vram": vram,
		"ram": ram,
		"ts": Time.get_unix_time_from_system()
	}
	
	var f = FileAccess.open(STATUS_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(data))
		f.close()
