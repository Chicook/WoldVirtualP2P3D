extends ECSSystem
class_name ProxySystem

var ProxyCompScript = preload("res://woldvirtual/ecs/components/ProxyComponent.gd")
var SpatialCompScript = preload("res://woldvirtual/ecs/components/SpatialComponent.gd")
var NetCompScript = preload("res://woldvirtual/ecs/components/NetworkStateComponent.gd")

func process_entity(entity: ECSEntity, _delta: float):
	if entity.has_component(ProxyCompScript) and entity.has_component(SpatialCompScript):
		var proxy = entity.get_component(ProxyCompScript)
		var spatial = entity.get_component(SpatialCompScript)
		
		# Find local player position from registry
		var player_pos = Vector3.ZERO
		var registry = get_parent()
		if registry is ECSRegistry:
			for e in registry.entities:
				if is_instance_valid(e) and e.has_component(NetCompScript):
					var net = e.get_component(NetCompScript)
					if net.is_local:
						var p_spatial = e.get_component(SpatialCompScript)
						if p_spatial: player_pos = p_spatial.position
						break
		
		proxy.distance_to_player = spatial.position.distance_to(player_pos)
		
		# LOD Logic
		var old_lod = proxy.lod_level
		if proxy.distance_to_player > proxy.visibility_range:
			proxy.lod_level = 2 # Hidden
		elif proxy.distance_to_player > 800.0:
			proxy.lod_level = 1 # Low
		else:
			proxy.lod_level = 0 # High
			
		if old_lod != proxy.lod_level:
			_apply_lod(entity, proxy.lod_level)

func _apply_lod(entity: ECSEntity, level: int):
	var parent = entity.get_parent()
	if !is_instance_valid(parent) or !(parent is Node3D): return
	
	match level:
		0: # High
			parent.show()
			_toggle_shadows(parent, true)
		1: # Low
			parent.show()
			_toggle_shadows(parent, false)
		2: # Hidden
			parent.hide()

func _toggle_shadows(node: Node, enabled: bool):
	for child in node.get_children():
		if child is GeometryInstance3D:
			child.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if enabled else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_toggle_shadows(child, enabled)
