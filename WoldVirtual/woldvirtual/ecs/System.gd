extends Node
class_name ECSSystem

func _process(delta: float) -> void:
	var registry = get_parent() # Assuming parent is the ECSRegistry
	if registry is ECSRegistry:
		# Iterate backwards or filter to handle invalid entities safely
		var i = registry.entities.size() - 1
		while i >= 0:
			var entity = registry.entities[i]
			if not is_instance_valid(entity):
				registry.entities.remove_at(i)
				i -= 1
				continue
			
			process_entity(entity, delta)
			i -= 1

func process_entity(_entity: ECSEntity, _delta: float):
	pass
