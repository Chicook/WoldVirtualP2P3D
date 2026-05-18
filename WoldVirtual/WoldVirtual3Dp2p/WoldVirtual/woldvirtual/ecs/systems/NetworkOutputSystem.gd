extends ECSSystem
class_name NetworkOutputSystem

var SpatialCompScript = preload("res://woldvirtual/ecs/components/SpatialComponent.gd")
var NetCompScript = preload("res://woldvirtual/ecs/components/NetworkStateComponent.gd")

func process_entity(entity: ECSEntity, _delta: float):
	if entity.has_component(SpatialCompScript) and entity.has_component(NetCompScript):
		var net = entity.get_component(NetCompScript)
		if !net.is_local: return
		
		var spatial = entity.get_component(SpatialCompScript)
		var parent = entity.get_parent()
		
		if is_instance_valid(parent) and parent is Node3D:
			# Update component from real node position
			spatial.position = parent.global_position
			spatial.rotation = parent.global_rotation.y
			
			# Sync to network state for I/O
			net.raw_data["x"] = spatial.position.x
			net.raw_data["y"] = spatial.position.y
			net.raw_data["z"] = spatial.position.z
			net.raw_data["r"] = spatial.rotation
			net.raw_data["t"] = Time.get_unix_time_from_system()
			net.last_timestamp = net.raw_data["t"]
