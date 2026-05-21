extends ECSSystem
class_name InterpolationSystem

var SpatialCompScript = preload("res://woldvirtual/ecs/components/SpatialComponent.gd")
var NetCompScript = preload("res://woldvirtual/ecs/components/NetworkStateComponent.gd")

func process_entity(entity: ECSEntity, _delta: float):
	if entity.has_component(SpatialCompScript) and entity.has_component(NetCompScript):
		var spatial = entity.get_component(SpatialCompScript)
		var net = entity.get_component(NetCompScript)
		
		if net.is_local: return 
		
		var target_pos = Vector3(
			net.raw_data.get("x", spatial.position.x),
			net.raw_data.get("y", spatial.position.y),
			net.raw_data.get("z", spatial.position.z)
		)
		var target_rot = net.raw_data.get("r", spatial.rotation)
		
		if spatial.position.distance_to(target_pos) > 100.0:
			spatial.position = target_pos
		else:
			spatial.position = spatial.position.lerp(target_pos, 0.15)
		
		spatial.rotation = lerp_angle(spatial.rotation, target_rot, 0.15)
		
		var parent = entity.get_parent()
		if is_instance_valid(parent) and parent is Node3D:
			parent.global_position = spatial.position
			parent.global_rotation.y = spatial.rotation
