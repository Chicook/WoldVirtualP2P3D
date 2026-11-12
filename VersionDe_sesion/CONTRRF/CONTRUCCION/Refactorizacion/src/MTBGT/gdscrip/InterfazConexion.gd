# ==============================================================================
# InterfazConexion.gd  — Godot 4 · GDScript
# Controlador de la Interfaz UI para Conexión con ServidorNeuronal (BLOK1)
# ==============================================================================
class_name InterfazConexion
extends Control

# Referencias a nodos UI
@onready var line_host: LineEdit = %LineHost
@onready var line_port: LineEdit = %LinePort
@onready var btn_conectar: Button = %BtnConectar
@onready var btn_desconectar: Button = %BtnDesconectar
@onready var lbl_estado: Label = %LblEstado
@onready var lbl_latencia: Label = %LblLatencia
@onready var opt_modo: OptionButton = %OptModo
@onready var btn_inferencia: Button = %BtnInferencia
@onready var btn_diagnostico: Button = %BtnDiagnostico
@onready var btn_sanar: Button = %BtnSanar
@onready var btn_limpiar: Button = %BtnLimpiar
@onready var txt_log: RichTextLabel = %TxtLog
@onready var lbl_accion: Label = %LblAccion

# Instancia del cliente de red
var servidor: Servidor3D = null

# Modos del Pipeline BLOK1 soportados
const MODOS = [
	"cinematica",
	"auto",
	"continuo",
	"discreto",
	"normalizado",
	"navegacion",
	"riesgo",
	"distribuido",
	"xavier",
	"basico"
]

func _ready() -> void:
	_inicializar_cliente_servidor()
	_configurar_interfaz()
	_log("[color=cyan][SISTEMA][/color] Interfaz base de conexión inicializada.")

func _inicializar_cliente_servidor() -> void:
	servidor = Servidor3D.new()
	servidor.name = "ClienteServidor3D"
	add_child(servidor)
	
	# Conexión de señales del cliente Servidor3D
	servidor.conectado.connect(_on_servidor_conectado)
	servidor.desconectado.connect(_on_servidor_desconectado)
	servidor.accion_neuronal.connect(_on_accion_neuronal)
	servidor.diagnostico_recibido.connect(_on_diagnostico_recibido)
	servidor.error_servidor.connect(_on_error_servidor)
	servidor.respuesta_recibida.connect(_on_respuesta_recibida)

func _configurar_interfaz() -> void:
	# Poblar selector de modos
	opt_modo.clear()
	for m in MODOS:
		opt_modo.add_item(m)
	opt_modo.selected = 0
	
	# Estado inicial de botones
	btn_desconectar.disabled = true
	btn_inferencia.disabled = true
	btn_diagnostico.disabled = true
	btn_sanar.disabled = true
	
	# Conectar eventos de botones UI
	btn_conectar.pressed.connect(_on_btn_conectar_pressed)
	btn_desconectar.pressed.connect(_on_btn_desconectar_pressed)
	btn_inferencia.pressed.connect(_on_btn_inferencia_pressed)
	btn_diagnostico.pressed.connect(_on_btn_diagnostico_pressed)
	btn_sanar.pressed.connect(_on_btn_sanar_pressed)
	btn_limpiar.pressed.connect(func(): txt_log.clear())

func _log(texto: String) -> void:
	var hora = Time.get_time_string_from_system()
	txt_log.append_text("[%s] %s\n" % [hora, texto])

# ---------------------------------------------------------------------------
# Handlers de UI
# ---------------------------------------------------------------------------
func _on_btn_conectar_pressed() -> void:
	var h = line_host.text.strip_edges()
	var p = line_port.text.to_int()
	if h.is_empty() or p <= 0:
		_log("[color=red][ERROR][/color] Host o puerto inválido.")
		return
		
	servidor.host = h
	servidor.puerto = p
	lbl_estado.text = "Conectando..."
	lbl_estado.modulate = Color.YELLOW
	btn_conectar.disabled = true
	_log("[color=yellow][RED][/color] Intentando conectar a ws://%s:%d ..." % [h, p])
	servidor.conectar_al_servidor()

func _on_btn_desconectar_pressed() -> void:
	_log("[color=orange][RED][/color] Desconectando...")
	servidor.desconectar()

func _on_btn_inferencia_pressed() -> void:
	var modo_sel = opt_modo.get_item_text(opt_modo.selected)
	# Vector sensorial demo de 10 dimensiones con valores aleatorios suaves
	var estado_test: Array = []
	for i in range(servidor.input_size):
		estado_test.append(snapped(randf_range(-1.0, 1.0), 0.001))
	
	_log("[color=light_blue][INFERENCIA][/color] Solicitando modo: [b]%s[/b] ..." % modo_sel)
	servidor.inferencia(estado_test, modo_sel)

func _on_btn_diagnostico_pressed() -> void:
	_log("[color=magenta][DIAGNÓSTICO][/color] Solicitando estado de salud de BLOK1...")
	servidor.diagnostico()

func _on_btn_sanar_pressed() -> void:
	_log("[color=coral][AUTO-SANACIÓN][/color] Enviando comando de auto-sanación...")
	servidor.auto_sanar("EN1")

# ---------------------------------------------------------------------------
# Handlers de Señales de Servidor3D
# ---------------------------------------------------------------------------
func _on_servidor_conectado() -> void:
	lbl_estado.text = "CONECTADO"
	lbl_estado.modulate = Color.GREEN
	btn_conectar.disabled = true
	btn_desconectar.disabled = false
	btn_inferencia.disabled = false
	btn_diagnostico.disabled = false
	btn_sanar.disabled = false
	_log("[color=green][✓ ÉXITO][/color] Conectado exitosamente con ServidorNeuronal (BLOK1).")

func _on_servidor_desconectado(codigo: int, razon: String) -> void:
	lbl_estado.text = "DESCONECTADO"
	lbl_estado.modulate = Color.RED
	lbl_latencia.text = "Latencia: -- ms"
	btn_conectar.disabled = false
	btn_desconectar.disabled = true
	btn_inferencia.disabled = true
	btn_diagnostico.disabled = true
	btn_sanar.disabled = true
	_log("[color=red][✕ DESCONECTADO][/color] Código: %d | Razón: '%s'" % [codigo, razon])
	if codigo == 1006 or codigo == -1:
		_log("[color=yellow][AYUDA][/color] El servidor no está en ejecución. Asegúrate de ejecutar el archivo [b]INICIAR_SERVIDOR_PYTHON.bat[/b].")

func _on_accion_neuronal(accion: Array, diagnostico: Dictionary) -> void:
	var modo = diagnostico.get("modo", "N/A")
	var enrn = diagnostico.get("neurona_enrn", "N/A")
	var rfen = diagnostico.get("neurona_rfen", "N/A")
	var lat = diagnostico.get("latencia_ms", 0.0)
	lbl_latencia.text = "Latencia: %.3f ms" % lat
	lbl_accion.text = "Acción: %s" % str(accion)
	_log("[color=green][INFERENCIA OK][/color] Modo: %s | ENRN: %s | RF_EN: %s | Latencia: %.3f ms\n  -> Acción: %s" % [
		modo, enrn, rfen, lat, str(accion)
	])

func _on_diagnostico_recibido(salud: Dictionary) -> void:
	var diag_neuronal = salud.get("diagnostico_neuronal", {})
	var san = diag_neuronal.get("sanidad", {})
	var estado_glob = san.get("estado_global", "DESCONOCIDO")
	var anomalias = san.get("anomalias", [])
	var color_tag = "green" if estado_glob == "OK" else "red"
	_log("[color=%s][SALUD BLOK1][/color] Estado: [b]%s[/b] | Anomalías: %d" % [
		color_tag, estado_glob, anomalias.size()
	])

func _on_error_servidor(mensaje: String) -> void:
	_log("[color=red][ERROR SERVIDOR][/color] %s" % mensaje)

func _on_respuesta_recibida(tipo: String, payload: Dictionary) -> void:
	if tipo == "auto_sanar":
		_log("[color=coral][SANACIÓN][/color] Neurona %s sanada: %s" % [
			payload.get("neurona", ""), str(payload.get("sanado_exitoso", false))
		])
