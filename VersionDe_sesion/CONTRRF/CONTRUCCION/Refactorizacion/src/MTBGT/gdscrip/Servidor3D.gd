# ==============================================================================
# Servidor3D.gd  — Godot 4 · GDScript
# Cliente WebSocket para ServidorNeuronal (CELEBRO / BLOK1 / BASE_NEURONAL1)
#
# Protocolo: JSON sobre WebSocket RFC 6455  —  ws://host:puerto
#
# Tipos de petición admitidos por el servidor Python:
#   "inferencia"  → Pipeline ENRN → RF_EN  (devuelve accion[])
#   "entrenar"    → Motor RL + retropropagación sensorial
#   "p2p"         → Buffer IMPALA multi-actor
#   "diagnostico" → Salud completa de las 20 neuronas
#   "auto_sanar"  → Reinicialización quirúrgica de una neurona
#   "pesos"       → Estadísticas de módulos cargados
#
# Uso rápido desde cualquier nodo Godot 4:
#   var srv = Servidor3D.new()
#   add_child(srv)
#   await srv.conectar()
#   var resp = await srv.inferencia(estado, "cinematica")
#   print(resp.accion)
# ==============================================================================

class_name Servidor3D
extends Node

# ---------------------------------------------------------------------------
# Señales públicas
# ---------------------------------------------------------------------------

## Emitida cuando se establece la conexión con el servidor Python.
signal conectado()

## Emitida cuando se pierde la conexión (código, razón).
signal desconectado(codigo: int, razon: String)

## Emitida cuando llega cualquier respuesta del servidor (tipo, payload).
signal respuesta_recibida(tipo_respuesta: String, payload: Dictionary)

## Emitida al recibir una acción de inferencia neuronal.
signal accion_neuronal(accion: Array, diagnostico: Dictionary)

## Emitida al completar un paso de entrenamiento.
signal entrenamiento_completado(td_error: float, recompensa: float)

## Emitida al recibir diagnóstico de salud del servidor.
signal diagnostico_recibido(salud: Dictionary)

## Emitida si el servidor reporta un error.
signal error_servidor(mensaje: String)

# ---------------------------------------------------------------------------
# Parámetros de configuración
# ---------------------------------------------------------------------------

## Dirección del servidor Python (ServidorNeuronal).
@export var host: String = "127.0.0.1"

## Puerto del servidor Python.
@export var puerto: int = 8765

## Reconectar automáticamente si se pierde la conexión.
@export var auto_reconectar: bool = true

## Segundos entre reintentos de reconexión.
@export var intervalo_reconexion: float = 3.0

## ID único de este actor/nodo en el sistema P2P.
@export var actor_id: String = "godot_peer_3d"

## Modo neuronal por defecto para las peticiones de inferencia.
## Valores: "auto", "continuo", "discreto", "normalizado",
##          "navegacion", "cinematica", "riesgo", "distribuido", "xavier", "basico"
@export_enum("auto","continuo","discreto","normalizado","navegacion","cinematica","riesgo","distribuido","xavier","basico") \
	var modo_default: String = "cinematica"

## Dimensión del vector de estado que el servidor espera.
## Debe coincidir con BaseNeuronal1.input_size (default 10).
@export var input_size: int = 10

# ---------------------------------------------------------------------------
# Estado interno
# ---------------------------------------------------------------------------

## Instancia del cliente WebSocket de Godot 4.
var _ws: WebSocketPeer = WebSocketPeer.new()

## Estado de la conexión (ver _EstadoConexion).
var _estado: int = _EstadoConexion.DESCONECTADO

## URL completa del servidor.
var _url: String = ""

## Cola de peticiones pendientes (enviadas antes de que la conexión esté lista).
var _cola_pendiente: Array[Dictionary] = []

## Mapa de peticiones en vuelo: id_peticion → callback o señal
var _peticiones_vuelo: Dictionary = {}

## Contador de peticiones para IDs únicos.
var _contador_id: int = 0

## Timer de reconexión.
var _timer_reconexion: float = 0.0

## Métricas locales de rendimiento.
var metricas: Dictionary = {
	"inferencias": 0,
	"entrenamientos": 0,
	"p2p_enviados": 0,
	"errores": 0,
	"latencia_ms_ultima": 0.0,
}

# ---------------------------------------------------------------------------
# Enum de estados de la conexión
# ---------------------------------------------------------------------------

enum _EstadoConexion {
	DESCONECTADO  = 0,
	CONECTANDO    = 1,
	CONECTADO     = 2,
	ERROR         = 3,
}

# ---------------------------------------------------------------------------
# Propiedades públicas de solo lectura
# ---------------------------------------------------------------------------

## Devuelve true si el WebSocket está actualmente conectado y listo.
var esta_conectado: bool:
	get: return _estado == _EstadoConexion.CONECTADO

# ===========================================================================
# Ciclo de vida del nodo
# ===========================================================================

func _ready() -> void:
	_url = "ws://%s:%d" % [host, puerto]
	print("[Servidor3D] Configurado → %s  actor_id=%s  modo=%s" % [_url, actor_id, modo_default])


func _process(delta: float) -> void:
	# Bombear el WebSocket en cada frame
	_ws.poll()

	var estado_ws := _ws.get_ready_state()

	match _estado:
		_EstadoConexion.CONECTANDO:
			if estado_ws == WebSocketPeer.STATE_OPEN:
				_estado = _EstadoConexion.CONECTADO
				print("[Servidor3D] ✓ Conexión establecida con %s" % _url)
				# Vaciar cola de peticiones pendientes
				for paquete in _cola_pendiente:
					_enviar_json(paquete)
				_cola_pendiente.clear()
				emit_signal("conectado")

			elif estado_ws == WebSocketPeer.STATE_CLOSED:
				_manejar_desconexion()

		_EstadoConexion.CONECTADO:
			if estado_ws == WebSocketPeer.STATE_CLOSED:
				_manejar_desconexion()
			else:
				# Procesar todos los mensajes disponibles
				while _ws.get_available_packet_count() > 0:
					var pkt := _ws.get_packet()
					if pkt.size() > 0:
						_procesar_respuesta(pkt.get_string_from_utf8())

		_EstadoConexion.DESCONECTADO:
			if auto_reconectar:
				_timer_reconexion += delta
				if _timer_reconexion >= intervalo_reconexion:
					_timer_reconexion = 0.0
					print("[Servidor3D] Intentando reconectar con %s ..." % _url)
					conectar_al_servidor()

		_EstadoConexion.ERROR:
			if auto_reconectar:
				_timer_reconexion += delta
				if _timer_reconexion >= intervalo_reconexion:
					_timer_reconexion = 0.0
					_estado = _EstadoConexion.DESCONECTADO


# ===========================================================================
# API PÚBLICA DE CONEXIÓN
# ===========================================================================

## Inicia la conexión WebSocket con el ServidorNeuronal Python.
## Devuelve true si el intento se inició, false si ya está conectado.
func conectar_al_servidor() -> bool:
	if _estado == _EstadoConexion.CONECTADO:
		push_warning("[Servidor3D] Ya conectado a %s" % _url)
		return false

	_url = "ws://%s:%d" % [host, puerto]
	var err := _ws.connect_to_url(_url)
	if err != OK:
		push_error("[Servidor3D] Error al iniciar conexión: %d" % err)
		_estado = _EstadoConexion.ERROR
		return false

	_estado = _EstadoConexion.CONECTANDO
	print("[Servidor3D] Conectando a %s ..." % _url)
	return true


## Coroutine conveniente — await srv.conectar() hasta que se reciba la señal conectado().
func conectar() -> void:
	conectar_al_servidor()
	if not esta_conectado:
		await conectado


## Cierra la conexión limpiamente.
func desconectar_del_servidor() -> void:
	_ws.close(1000, "cierre_normal")
	_estado = _EstadoConexion.DESCONECTADO
	print("[Servidor3D] Desconectado voluntariamente.")


# ===========================================================================
# API PÚBLICA NEURONAL — 6 PETICIONES DEL ServidorNeuronal Python
# ===========================================================================

## --- 1. INFERENCIA SENSORIOMOTORA -------------------------------------------
## Envía un vector de estado al servidor y recibe la acción neuronal.
##
## @param estado       Array[float] de longitud input_size (default 10)
## @param modo         Modo neuronal ("auto", "cinematica", "navegacion", etc.)
## @param callback     Callable(resp: Dictionary) opcional. Si se omite, usa señal.
## @returns            id de la petición (String)
func inferencia(estado: Array, modo: String = "", callback: Callable = Callable()) -> String:
	if modo.is_empty():
		modo = modo_default
	var paquete := {
		"id":     _nuevo_id(),
		"tipo":   "inferencia",
		"estado": _normalizar_estado(estado),
		"modo":   modo,
	}
	metricas["inferencias"] += 1
	return _enviar_peticion(paquete, callback)


## --- 2. ENTRENAMIENTO RL + RETROPROPAGACIÓN SENSORIAL ----------------------
## Envía una transición (s, a, r, s', done) para entrenar las neuronas.
##
## @param estado            Array[float] estado actual
## @param accion            int o float — acción tomada
## @param recompensa        float — señal de recompensa
## @param siguiente_estado  Array[float] estado siguiente
## @param terminado         bool — fin de episodio
## @param modo              Modo neuronal para seleccionar el buffer correcto
## @param callback          Callable opcional
func entrenar(
		estado: Array,
		accion: Variant,
		recompensa: float,
		siguiente_estado: Array,
		terminado: bool = false,
		modo: String = "continuo",
		callback: Callable = Callable()) -> String:

	var paquete := {
		"id":               _nuevo_id(),
		"tipo":             "entrenar",
		"actor_id":         actor_id,
		"estado":           _normalizar_estado(estado),
		"accion":           accion,
		"recompensa":       recompensa,
		"siguiente_estado": _normalizar_estado(siguiente_estado),
		"terminado":        terminado,
		"modo":             modo,
	}
	metricas["entrenamientos"] += 1
	return _enviar_peticion(paquete, callback)


## --- 3. DEPOSITAR EXPERIENCIA P2P (Buffer IMPALA) --------------------------
## Envía una transición directamente al buffer IMPALA multi-actor.
##
## @param estado, accion, recompensa, siguiente_estado, terminado  — transición
## @param probabilidad_accion   float — importancia muestral (default 1.0)
## @param callback              Callable opcional
func p2p_experiencia(
		estado: Array,
		accion: Variant,
		recompensa: float,
		siguiente_estado: Array,
		terminado: bool = false,
		probabilidad_accion: float = 1.0,
		callback: Callable = Callable()) -> String:

	var paquete := {
		"id":                  _nuevo_id(),
		"tipo":                "p2p",
		"actor_id":            actor_id,
		"estado":              _normalizar_estado(estado),
		"accion":              accion,
		"recompensa":          recompensa,
		"siguiente_estado":    _normalizar_estado(siguiente_estado),
		"terminado":           terminado,
		"probabilidad_accion": probabilidad_accion,
	}
	metricas["p2p_enviados"] += 1
	return _enviar_peticion(paquete, callback)


## --- 4. DIAGNÓSTICO INTEGRAL DE SALUD -------------------------------------
## Solicita el estado de las 20 neuronas (pesos, derivas, sesgo Q).
func diagnostico(callback: Callable = Callable()) -> String:
	var paquete := {
		"id":   _nuevo_id(),
		"tipo": "diagnostico",
	}
	return _enviar_peticion(paquete, callback)


## --- 5. AUTO-SANACIÓN QUIRÚRGICA DE UNA NEURONA ---------------------------
## Pide al servidor que reinicialice una neurona destabilizada.
##
## @param nombre_neurona   p.ej. "EN9", "RFEN6"
func auto_sanar(nombre_neurona: String, callback: Callable = Callable()) -> String:
	var paquete := {
		"id":      _nuevo_id(),
		"tipo":    "auto_sanar",
		"neurona": nombre_neurona,
	}
	return _enviar_peticion(paquete, callback)


## --- 6. ESTADÍSTICAS DE MÓDULOS NEURONALES CARGADOS -----------------------
func analisis_pesos(callback: Callable = Callable()) -> String:
	var paquete := {
		"id":   _nuevo_id(),
		"tipo": "pesos",
	}
	return _enviar_peticion(paquete, callback)


# ===========================================================================
# HELPERS DE ALTO NIVEL (combinan peticiones frecuentes)
# ===========================================================================

## Inferencia + entrenamiento en un único step del bucle de juego.
## Infiere la acción, la ejecuta en el entorno y envía feedback de recompensa.
##
## @param estado_actual      Vector sensorial del frame actual
## @param recompensa         Recompensa obtenida por la acción anterior
## @param estado_anterior    Estado del frame anterior (para el par de entrenamiento)
## @param accion_anterior    Acción tomada en el frame anterior
## @param terminado          Si el episodio terminó
## @param modo               Modo neuronal
## @param cb_inferencia      Callable(resp) opcional para la respuesta de inferencia
func step_completo(
		estado_actual: Array,
		recompensa: float,
		estado_anterior: Array = [],
		accion_anterior: Variant = 0,
		terminado: bool = false,
		modo: String = "",
		cb_inferencia: Callable = Callable()) -> void:

	# Entrenar con la transición del frame anterior si hay estado previo
	if estado_anterior.size() > 0:
		entrenar(estado_anterior, accion_anterior, recompensa, estado_actual, terminado, modo if not modo.is_empty() else "continuo")

	# Inferir la acción para el frame actual
	inferencia(estado_actual, modo, cb_inferencia)


## Construye un vector de estado a partir de las propiedades de un KinematicBody3D / CharacterBody3D.
## Adapta según tu propia arquitectura de entidad.
##
## @param body              Nodo con transform.origin, linear_velocity, etc.
## @param objetivo_pos      Vector3 — posición del objetivo / waypoint
## @param extra             Array[float] adicional (health, ammo, signal flags, etc.)
## @returns                 Array[float] de longitud input_size
func construir_estado_desde_cuerpo(body: Node3D, objetivo_pos: Vector3 = Vector3.ZERO, extra: Array = []) -> Array:
	var pos    : Vector3 = body.global_transform.origin
	var rot    : Vector3 = body.global_transform.basis.get_euler()
	var vel    : Vector3 = Vector3.ZERO
	if body.has_method("get_velocity"):
		vel = body.get_velocity()

	var distancia : float = pos.distance_to(objetivo_pos) if objetivo_pos != Vector3.ZERO else 0.0
	var direccion : Vector3 = (objetivo_pos - pos).normalized() if distancia > 0.001 else Vector3.ZERO

	var estado_base : Array = [
		_normalizar_escalar(pos.x,  -100.0, 100.0),
		_normalizar_escalar(pos.y,    -10.0,  50.0),
		_normalizar_escalar(pos.z,  -100.0, 100.0),
		_normalizar_escalar(vel.x,   -20.0,  20.0),
		_normalizar_escalar(vel.y,   -20.0,  20.0),
		_normalizar_escalar(vel.z,   -20.0,  20.0),
		_normalizar_escalar(rot.y,    -PI,    PI  ),
		_normalizar_escalar(distancia, 0.0,  200.0),
		_normalizar_escalar(direccion.x, -1.0, 1.0),
		_normalizar_escalar(direccion.z, -1.0, 1.0),
	]

	# Agregar extras y recortar/rellenar hasta input_size
	for v in extra:
		estado_base.append(float(v))

	return _normalizar_estado(estado_base)


# ===========================================================================
# PROCESAMIENTO DE RESPUESTAS DEL SERVIDOR
# ===========================================================================

func _procesar_respuesta(raw: String) -> void:
	var json := JSON.new()
	var err := json.parse(raw)
	if err != OK:
		push_error("[Servidor3D] JSON inválido recibido: %s" % raw.left(120))
		metricas["errores"] += 1
		return

	var resp : Dictionary = json.data
	var tipo : String = str(resp.get("tipo_respuesta", "desconocido"))
	var id   : String = str(resp.get("id", ""))

	# Redirigir al callback registrado (si existe)
	if id != "" and _peticiones_vuelo.has(id):
		var cb : Callable = _peticiones_vuelo[id]
		_peticiones_vuelo.erase(id)
		if cb.is_valid():
			cb.call(resp)

	# Emitir señal genérica
	emit_signal("respuesta_recibida", tipo, resp)

	# Emitir señales especializadas
	match tipo:
		"inferencia":
			var accion : Array = resp.get("accion", [])
			metricas["latencia_ms_ultima"] = float(resp.get("latencia_total_ms", 0.0))
			emit_signal("accion_neuronal", accion, resp)

		"entrenamiento":
			var td_error   : float = float(resp.get("td_error",   0.0))
			var recompensa : float = float(resp.get("recompensa", 0.0))
			emit_signal("entrenamiento_completado", td_error, recompensa)

		"diagnostico":
			var diag_neuronal : Dictionary = resp.get("diagnostico_neuronal", {})
			var sanidad       : Dictionary = diag_neuronal.get("sanidad", {})
			emit_signal("diagnostico_recibido", sanidad)
			_imprimir_diagnostico(resp)

		"p2p_experiencia":
			pass  # Silencioso; maneja el buffer internamente en el servidor

		"auto_sanar":
			var exito : bool = bool(resp.get("sanado_exitoso", false))
			var n     : String = str(resp.get("neurona", "?"))
			print("[Servidor3D] auto_sanar '%s' → %s" % [n, "OK ✓" if exito else "FALLIDO ✗"])

		"analisis_pesos":
			print("[Servidor3D] Pesos: ENRN=%s  RF_EN=%s" % [
				resp.get("modulos_enrn_cargados", "?"),
				resp.get("modulos_rfen_cargados", "?")])

		"error", _:
			if resp.has("error"):
				metricas["errores"] += 1
				emit_signal("error_servidor", str(resp.get("error", "sin detalle")))
				push_warning("[Servidor3D] Error del servidor: %s" % resp.get("error", ""))


# ===========================================================================
# MÉTODOS PRIVADOS DE INFRAESTRUCTURA
# ===========================================================================

## Envía el paquete JSON por WebSocket (encola si aún no está conectado).
func _enviar_peticion(paquete: Dictionary, callback: Callable) -> String:
	var id : String = str(paquete.get("id", ""))
	if callback.is_valid():
		_peticiones_vuelo[id] = callback

	if _estado == _EstadoConexion.CONECTADO:
		_enviar_json(paquete)
	else:
		_cola_pendiente.append(paquete)
		if _estado == _EstadoConexion.DESCONECTADO:
			conectar_al_servidor()

	return id


func _enviar_json(paquete: Dictionary) -> void:
	var texto := JSON.stringify(paquete)
	var err   := _ws.send_text(texto)
	if err != OK:
		push_error("[Servidor3D] Error enviando mensaje WebSocket: %d" % err)
		metricas["errores"] += 1


func _manejar_desconexion() -> void:
	var codigo : int    = _ws.get_close_code()
	var razon  : String = _ws.get_close_reason()
	_estado = _EstadoConexion.DESCONECTADO
	_timer_reconexion = 0.0
	print("[Servidor3D] Desconectado — código=%d  razón='%s'" % [codigo, razon])
	emit_signal("desconectado", codigo, razon)


func _nuevo_id() -> String:
	_contador_id += 1
	return "req_%d_%d" % [_contador_id, Time.get_ticks_msec()]


## Ajusta el vector de estado a exactamente input_size elementos (rellena o recorta).
func _normalizar_estado(estado: Array) -> Array:
	var resultado := estado.duplicate()
	while resultado.size() < input_size:
		resultado.append(0.0)
	if resultado.size() > input_size:
		resultado = resultado.slice(0, input_size)
	# Asegurar que todos sean float
	for i in range(resultado.size()):
		resultado[i] = float(resultado[i])
	return resultado


## Normaliza un escalar a rango [-1, 1] dado un rango conocido.
func _normalizar_escalar(valor: float, minv: float, maxv: float) -> float:
	if maxv == minv:
		return 0.0
	return clampf((valor - minv) / (maxv - minv) * 2.0 - 1.0, -1.0, 1.0)


func _imprimir_diagnostico(resp: Dictionary) -> void:
	var diag     := resp.get("diagnostico_neuronal", {})
	var sanidad  := diag.get("sanidad", {}) as Dictionary
	var srv_met  := resp.get("servidor_metricas", {}) as Dictionary
	print("[Servidor3D] ══ DIAGNÓSTICO NEURONAL ══")
	print("  Estado global  : %s"   % sanidad.get("estado_global", "?"))
	print("  Anomalías      : %s"   % (sanidad.get("anomalias", []) as Array).size())
	print("  Inferencias    : %s"   % srv_met.get("total_inferencias", "?"))
	print("  Entrenamientos : %s"   % srv_met.get("total_entrenamientos", "?"))
	print("  Latencia prom. : %.3f ms" % float(srv_met.get("latencia_promedio_ms", 0.0)))


# ===========================================================================
# EJEMPLO DE USO INLINE — SceneTree Demo
# Descomenta el bloque _demo_*() y llámalo desde _ready() para pruebas rápidas.
# ===========================================================================

## Demo: conecta, infiere y entrena durante 3 steps, luego solicita diagnóstico.
## Uso:  await _demo_conexion_completa()
func _demo_conexion_completa() -> void:
	print("[Servidor3D-Demo] Iniciando demo de conexión completa …")

	# 1. Conectar
	conectar_al_servidor()
	await conectado
	print("[Servidor3D-Demo] ✓ Conectado.")

	# 2. Inferencia simple
	var estado_demo : Array = []
	for i in range(input_size):
		estado_demo.append(randf_range(-1.0, 1.0))

	var resp_inf := {}
	await inferencia(estado_demo, "cinematica", func(r): resp_inf = r)
	# Espera a que llegue la señal
	await get_tree().create_timer(0.3).timeout
	print("[Servidor3D-Demo] Inferencia → accion=%s" % str(resp_inf.get("accion", [])))

	# 3. 3 pasos de entrenamiento
	for paso in range(3):
		var siguiente : Array = []
		for i in range(input_size):
			siguiente.append(randf_range(-1.0, 1.0))
		entrenar(estado_demo, 0, randf_range(-1.0, 1.0), siguiente, false, "continuo")
		estado_demo = siguiente
		await get_tree().create_timer(0.1).timeout

	print("[Servidor3D-Demo] 3 pasos de entrenamiento enviados.")

	# 4. Diagnóstico de salud
	diagnostico()
	await get_tree().create_timer(0.3).timeout

	print("[Servidor3D-Demo] Demo completa. Métricas locales: %s" % str(metricas))
