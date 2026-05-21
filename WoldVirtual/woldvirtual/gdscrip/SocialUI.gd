extends Control

@onready var manager: Node3D = get_node("../../ChunkManager")

func _ready():
	# Glassmorphism Style
	var panel = $Panel
	var sb = StyleBoxFlat.new()
	sb.bg_color = Color(0.1, 0.1, 0.2, 0.6)
	sb.set_corner_radius_all(20)
	panel.add_theme_stylebox_override("panel", sb)

func _on_wave_pressed():
	if manager.network:
		manager.network.push_event("wave")
		print("Social -> Waving to peers")

func _on_jump_pressed():
	if manager.network:
		manager.network.push_event("jump")
		print("Social -> Jumping")
