extends Area3D
## Portal genérico: al entrar un CharacterBody3D avisa con portal_cruzado.
## El Boot del metaverso escucha y carga la isla. Si la zona se ejecuta
## suelta (sin Boot), cambia a target_scene como alternativa.
signal portal_cruzado
@export var target_scene: String = "res://ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn"

func _ready() -> void:
	monitoring = true
	body_entered.connect(_on_body_entered)

func _on_body_entered(body: Node3D) -> void:
	if not (body is CharacterBody3D):
		return
	portal_cruzado.emit()
	# Solo cambia de escena en uso suelto (nadie escuchando la señal).
	if portal_cruzado.get_connections().is_empty() and target_scene != "":
		get_tree().call_deferred("change_scene_to_file", target_scene)
