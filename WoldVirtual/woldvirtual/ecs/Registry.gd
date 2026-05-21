extends Node
class_name ECSRegistry

var entities: Array[ECSEntity] = []

func create_entity() -> ECSEntity:
	var e = ECSEntity.new()
	add_child(e)
	entities.append(e)
	return e

func register_node_as_entity(node: Node) -> ECSEntity:
	var e = ECSEntity.new()
	node.add_child(e)
	entities.append(e)
	return e

func remove_entity(e: ECSEntity):
	entities.erase(e)
	if is_instance_valid(e):
		e.queue_free()

func cleanup_invalid_entities():
	var i = entities.size() - 1
	while i >= 0:
		if not is_instance_valid(entities[i]):
			entities.remove_at(i)
		i -= 1
