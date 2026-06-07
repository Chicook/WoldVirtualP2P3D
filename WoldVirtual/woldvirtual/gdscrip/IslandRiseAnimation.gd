## IslandRiseAnimation.gd
## Nodo temporal que anima la isla emergiendo desde el lecho marino.
## Se añade como hijo de la propia isla, ejecuta la animación y luego
## se autodestruye. Al terminar, emite la señal [finished].
##
## Uso:
##   var anim = IslandRiseAnimation.new()
##   island_node.add_child(anim)
##   anim.play(target_y)
##   anim.finished.connect(mi_callback)
extends Node
class_name IslandRiseAnimation

# ─── Señal ─────────────────────────────────────────────────────────────────────
signal finished

# ─── Parámetros de la animación ────────────────────────────────────────────────
## Y de inicio: profundidad del lecho marino (muy por debajo del océano)
@export var seabed_depth     : float = -160.0
## Duración total del ascenso en segundos
@export var rise_duration    : float =  4.2
## Amplitud máxima de la vibración tectónica (metros)
@export var shake_intensity  : float =  0.35
## Frecuencia de la vibración (ciclos por segundo)
@export var shake_frequency  : float = 18.0
## Pausa dramática (segundos) tras tocar la superficie antes de emitir finished
@export var splash_pause     : float =  0.3

# ─── Estado interno ────────────────────────────────────────────────────────────
var _target_y   : float  = 0.0
var _elapsed    : float  = 0.0
var _running    : bool   = false
var _island     : Node3D = null   # padre Node3D (la isla)

# Posición XZ original de la isla (para resetear el shake)
var _origin_x   : float  = 0.0
var _origin_z   : float  = 0.0

# ─── API ───────────────────────────────────────────────────────────────────────
func play(target_y: float) -> void:
	_island   = get_parent() as Node3D
	if !is_instance_valid(_island):
		push_warning("IslandRiseAnimation: el padre no es un Node3D.")
		finished.emit()
		queue_free()
		return

	_target_y  = target_y
	_origin_x  = _island.global_position.x
	_origin_z  = _island.global_position.z
	_elapsed   = 0.0
	_running   = true

	# Hundir la isla en el lecho marino
	_island.global_position.y = seabed_depth
	set_process(true)

# ─── Loop ──────────────────────────────────────────────────────────────────────
func _ready() -> void:
	set_process(false)

func _process(delta: float) -> void:
	if !_running: return
	if !is_instance_valid(_island):
		_end_animation()
		return

	_elapsed += delta
	var t      : float = clamp(_elapsed / rise_duration, 0.0, 1.0)
	var ease_t : float = _ease_out_cubic(t)

	# ── Posición Y ──────────────────────────────────────────────────────────────
	_island.global_position.y = lerpf(seabed_depth, _target_y, ease_t)

	# ── Vibración tectónica (amortiguada) ───────────────────────────────────────
	if t < 0.88:
		var envelope  : float = _shake_envelope(t)
		var shake_amp : float = shake_intensity * envelope
		# Desplazamiento senoidal en X y Z independientes
		var sx : float = sin(_elapsed * shake_frequency * TAU) * shake_amp
		var sz : float = cos(_elapsed * shake_frequency * TAU * 0.73) * shake_amp
		_island.global_position.x = _origin_x + sx
		_island.global_position.z = _origin_z + sz
	else:
		# Restaurar XZ exacto cuando el shake termina
		_island.global_position.x = _origin_x
		_island.global_position.z = _origin_z

	# ── Fin del ascenso ─────────────────────────────────────────────────────────
	if t >= 1.0:
		_island.global_position = Vector3(_origin_x, _target_y, _origin_z)
		_running = false
		set_process(false)
		# Pausa dramática antes de notificar
		await get_tree().create_timer(splash_pause).timeout
		_end_animation()

func _end_animation() -> void:
	finished.emit()
	queue_free()

# ─── Curvas de easing ──────────────────────────────────────────────────────────
## Ease-out cúbico: rápido al principio, frenazo suave al llegar
static func _ease_out_cubic(t: float) -> float:
	var u := 1.0 - t
	return 1.0 - (u * u * u)

## Envolvente del shake: máxima intensidad al inicio, cero al 88%
static func _shake_envelope(t: float) -> float:
	# t normalizado a [0,1] respecto al 88% del recorrido
	var t_norm := t / 0.88
	return pow(1.0 - t_norm, 2.0)
