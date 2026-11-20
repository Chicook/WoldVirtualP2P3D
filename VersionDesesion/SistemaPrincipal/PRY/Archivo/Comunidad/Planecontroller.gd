# PlaneController.gd - Real plane - takeoff anywhere, fly to any island - Abuja to Miami
extends WoldVehicle

@export var takeoff_speed: float = 25.0
@export var lift_curve: float = 0.8

var is_flying: bool = false
var altitude: float = 0.0

func _physics_process(delta):
	super._physics_process(delta)
	if not is_occupied: return
	
	altitude = global_position.y
	var speed = linear_velocity.length()
	
	if speed > takeoff_speed and not is_flying:
		is_flying = true
		print("[PLANE] Takeoff! Speed %.1f Alt %.1f" % [speed, altitude])
	
	if is_flying:
		# Auto level
		var target_up = Vector3.UP
		var current_up = global_transform.basis.y
		var diff = current_up.cross(target_up)
		apply_torque(diff * 200 * delta)
		
		# World map - fly to any coordinate
		# Example: Abuja chunk (0,0) to Miami chunk (1000,1000)
		if Input.is_action_pressed("map_open"):
			# Open world map UI - select destination
			print("[PLANE] World map - current ", global_position, " fuel ", fuel)

func land_anywhere():
	# Raycast down - if ground < 20m, allow landing
	var space = get_world_3d().direct_space_state
	var query = PhysicsRayQueryParameters3D.create(global_position, global_position + Vector3.DOWN * 100)
	var result = space.intersect_ray(query)
	if result and result.position.distance_to(global_position) < 20:
		is_flying = false
		print("[PLANE] Landing at ", result.position)
