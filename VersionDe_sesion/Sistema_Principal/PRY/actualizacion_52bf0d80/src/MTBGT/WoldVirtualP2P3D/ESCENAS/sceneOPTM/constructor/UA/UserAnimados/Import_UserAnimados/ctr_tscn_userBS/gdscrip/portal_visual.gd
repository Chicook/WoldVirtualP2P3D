extends Node3D
## Animación del portal holográfico: orbes en órbita, luz pulsante y
## membrana energética que respira.

@export var orb_speed := 0.9
@export var orb_radius := 1.95
@export var orb_height := 1.8
@export var pulse_speed := 2.0
@export var light_min := 2.2
@export var light_max := 3.6
@export var membrane_min := 1.05
@export var membrane_max := 1.55

var _t := 0.0
var _orbs: Array[Node3D] = []

@onready var _membrane: MeshInstance3D = get_node_or_null("Membrana")
@onready var _light: OmniLight3D = get_node_or_null("Luz")


func _ready() -> void:
	for child in get_children():
		if child is Node3D and String(child.name).begins_with("Orbe"):
			_orbs.append(child as Node3D)


func _process(delta: float) -> void:
	_t += delta
	var total := maxi(_orbs.size(), 1)
	for i in _orbs.size():
		var ang := _t * orb_speed + TAU * float(i) / float(total)
		_orbs[i].position = Vector3(
			cos(ang) * orb_radius,
			orb_height + sin(ang) * orb_radius * 0.72,
			0.35
		)
	var pulse := 0.5 + 0.5 * sin(_t * pulse_speed)
	if _light != null:
		_light.light_energy = lerpf(light_min, light_max, pulse)
	if _membrane != null:
		var mat := _membrane.get_active_material(0) as ShaderMaterial
		if mat != null:
			mat.set_shader_parameter("intensity", lerpf(membrane_min, membrane_max, pulse))
