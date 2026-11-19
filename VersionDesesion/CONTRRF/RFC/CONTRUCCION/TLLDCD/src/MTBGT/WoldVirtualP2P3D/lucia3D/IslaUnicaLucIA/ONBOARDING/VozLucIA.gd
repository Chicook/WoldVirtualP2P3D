extends Node
## Voz oficial de LucIA para el alta de la DAO.
##
## Reproduce el WAV pregrabado con el sintetizador del sistema general
## (`voz_lucia.py`: gTTS es-ES + DSP 1.16x). Si una frase no está pregrabada,
## avisa al llamador para que use la voz nativa al momento y la sintetiza en
## segundo plano para dejarla en caché (`user://voz_lucia`).

const DIR_FIJA := "res://lucia3D/IslaUnicaLucIA/ONBOARDING/voz"
const DIR_CACHE := "user://voz_lucia"
const RUTA_SCRIPT := "res://lucia3D/GLTF_lucIA/celebro_3D/puente_3D/voz_lucia.py"

var _reproductor: AudioStreamPlayer
var _python := ""
var _cola: Array[String] = []
var _sintetizando := false
var _pid := -1
var _destino := ""
var _texto_pendiente := ""
var _limite_voz := 0
var _guion := ""


func _ready() -> void:
	_reproductor = AudioStreamPlayer.new()
	_reproductor.name = "ReproductorVozLucIA"
	add_child(_reproductor)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(DIR_CACHE))
	_python = _buscar_python()
	_guion = _buscar_guion()


## Devuelve true si ya estaba disponible el audio oficial y se está oyendo.
func decir(texto: String) -> bool:
	if _reproductor == null:
		return false
	callar()
	var ruta := _ruta_wav(texto)
	if ruta.is_empty():
		if not _python.is_empty() and not _guion.is_empty():
			_texto_pendiente = texto
			_limite_voz = Time.get_ticks_msec() + 30_000
			_pedir_sintesis(texto)
		return false
	print("[VozLucIA] voz oficial: ", ruta.get_file())
	var audio := _cargar(ruta)
	if audio == null:
		return false
	_reproductor.stream = audio
	_reproductor.play()
	return true


func _process(_delta: float) -> void:
	if not _sintetizando:
		return
	if _pid > 0 and not OS.is_process_running(_pid):
		_sintetizando = false
		if not _texto_pendiente.is_empty():
			var ruta := _ruta_wav(_texto_pendiente)
			if not ruta.is_empty() and Time.get_ticks_msec() < _limite_voz:
				decir(_texto_pendiente)
			elif _cola.is_empty():
				_texto_pendiente = ""
		_siguiente()


func _ruta_wav(texto: String) -> String:
	var nombre := texto.sha256_text() + ".wav"
	var fija := DIR_FIJA + "/" + nombre
	if ResourceLoader.exists(fija):
		return fija
	var cache := DIR_CACHE + "/" + nombre
	if FileAccess.file_exists(cache):
		return cache
	return ""


func _cargar(ruta: String) -> AudioStream:
	if ruta.begins_with("res://"):
		return load(ruta) as AudioStream
	return AudioStreamWAV.load_from_file(ruta)


## True mientras el WAV oficial sigue reproduciéndose.
func esta_hablando() -> bool:
	return (_reproductor != null and _reproductor.playing) \
			or (not _texto_pendiente.is_empty() and Time.get_ticks_msec() < _limite_voz)


func callar() -> void:
	_texto_pendiente = ""
	_cola.clear()
	if _reproductor != null:
		_reproductor.stop()


func _pedir_sintesis(texto: String) -> void:
	if _python.is_empty() or _cola.has(texto):
		return
	_cola.append(texto)
	_siguiente()


func _siguiente() -> void:
	if _sintetizando or _cola.is_empty():
		return
	var texto: String = _cola.pop_front()
	if not _ruta_wav(texto).is_empty():
		_siguiente()
		return
	_destino = ProjectSettings.globalize_path(
			DIR_CACHE + "/" + texto.sha256_text() + ".wav")
	if _guion.is_empty():
		return
	_pid = OS.create_process(_python, [_guion, "--texto", texto, "--salida", _destino])
	if _pid <= 0:
		return
	_sintetizando = true


func _buscar_guion() -> String:
	var local := ProjectSettings.globalize_path(RUTA_SCRIPT)
	if FileAccess.file_exists(local):
		return local
	var cursor := OS.get_executable_path().get_base_dir()
	while not cursor.is_empty():
		var candidato := cursor.path_join("TLLDCD/src/MTBGT/WoldVirtualP2P3D/" + RUTA_SCRIPT.trim_prefix("res://"))
		if FileAccess.file_exists(candidato):
			return candidato
		var padre := cursor.get_base_dir()
		if padre == cursor:
			break
		cursor = padre
	return ""


func _buscar_python() -> String:
	var entorno := OS.get_environment("WVP_PYTHON")
	if not entorno.is_empty() and FileAccess.file_exists(entorno):
		return entorno
	for inicio in [OS.get_executable_path().get_base_dir(), ProjectSettings.globalize_path("res://")]:
		var cursor: String = inicio
		while not cursor.is_empty():
			for relativa in [".dev/.python/python.exe", ".dev/venv/Scripts/python.exe"]:
				var candidato := cursor.path_join(relativa)
				if FileAccess.file_exists(candidato):
					return candidato
			var padre := cursor.get_base_dir()
			if padre == cursor:
				break
			cursor = padre
	var raiz := ProjectSettings.globalize_path("res://")
	for relativa in [
		"../../../../.dev/.python/python.exe",
		"../../../../.dev/venv/Scripts/python.exe",
		"LC_STM/python/python.exe",
		"LC_STM/python/pythonw.exe",
	]:
		var ruta := raiz.path_join(relativa).simplify_path()
		if FileAccess.file_exists(ruta):
			return ruta
	return ""
