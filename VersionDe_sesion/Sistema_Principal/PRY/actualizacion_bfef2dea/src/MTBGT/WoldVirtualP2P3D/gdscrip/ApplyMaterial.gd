extends Node3D

@export var material_to_apply: Material

func _ready():
    # Retrasar la aplicación un frame para asegurar que la escena importada cargó
    call_deferred("_apply_to_all", self)

func _apply_to_all(node: Node):
    pass
    #if node is MeshInstance3D:
    #    print("Applying material to: ", node.name)
    #    node.material_override = material_to_apply
    #for child in node.get_children():
    #    _apply_to_all(child)
