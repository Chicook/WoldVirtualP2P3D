extends Node
class_name ECSEntity

var components: Dictionary = {}

func add_component(comp: ECSComponent):
	components[comp.get_script().get_path()] = comp

func get_component(script: Script) -> ECSComponent:
	return components.get(script.get_path())

func has_component(script: Script) -> bool:
	return components.has(script.get_path())
