extends SceneTree

## Valida un GLB de personaje: árbol de nodos, huesos, skin, morph targets,
## animaciones y clips. Sirve para comprobar que el rig exportado desde Blender
## trae lo que el módulo espera (Skeleton3D + skin + morph BOCA).
##
##   godot --headless --path . --script res://lucia3D/_herramientas/validar_rig.gd \
##         -- res://lucia3D/GLTF_lucIA/AreaDeTrabajo/LucIA3D/LucIA_rig.glb

func _initialize() -> void:
	var ruta := "res://lucia3D/GLTF_lucIA/AreaDeTrabajo/LucIA3D/LucIA_rig.glb"
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		ruta = args[0]
	if not ResourceLoader.exists(ruta):
		print("NO EXISTE: ", ruta)
		quit()
		return
	var escena: PackedScene = load(ruta)
	var raiz: Node = escena.instantiate()
	root.add_child(raiz)
	await process_frame

	print("=== ÁRBOL ===")
	_arbol(raiz, 0)

	print("\n=== MALLAS ===")
	for n in _todos(raiz):
		if n is MeshInstance3D:
			var mi: MeshInstance3D = n
			var m: Mesh = mi.mesh
			if m == null:
				continue
			print("MeshInstance3D '", mi.name, "' transform=", mi.transform)
			print("  superficies=", m.get_surface_count(), " aabb=", m.get_aabb(), " blend_shapes=", m.get_blend_shape_count())
			for b in m.get_blend_shape_count():
				print("     morph[", b, "] '", m.get_blend_shape_name(b), "'")
			print("  skin=", "SI" if mi.skin else "NO", " skeleton=", mi.skeleton)
			if mi.skin:
				print("  skin binds=", mi.skin.get_bind_count())

	print("\n=== ESQUELETOS ===")
	var hay := false
	for n in _todos(raiz):
		if n is Skeleton3D:
			hay = true
			var s: Skeleton3D = n
			print("Skeleton3D '", s.name, "' huesos=", s.get_bone_count())
			for b in s.get_bone_count():
				var rest := s.get_bone_rest(b)
				print("  [%2d] %-24s padre=%2d  rest.o=%s  rest.basis_scale=%s" % [
					b, s.get_bone_name(b), s.get_bone_parent(b), rest.origin, rest.basis.get_scale()])
	if not hay:
		print("(sin Skeleton3D)")

	print("\n=== ANIMACIONES ===")
	for n in _todos(raiz):
		if n is AnimationPlayer:
			var ap: AnimationPlayer = n
			print("AnimationPlayer '", ap.name, "' root=", ap.root_node, " autoplay='", ap.autoplay, "'")
			for ln in ap.get_animation_library_list():
				var lib := ap.get_animation_library(ln)
				for an in lib.get_animation_list():
					var a: Animation = lib.get_animation(an)
					print("  clip '", an, "' len=", a.length, " loop=", a.loop_mode, " tracks=", a.get_track_count())
					for t in mini(a.get_track_count(), 12):
						print("     track ", t, " tipo=", a.track_get_type(t), " path=", a.track_get_path(t), " keys=", a.track_get_key_count(t))

	print("\n=== ASSETS EXTERNOS ===")
	for n in _todos(raiz):
		if n is MeshInstance3D and n.mesh:
			if n.mesh.resource_path != "":
				print("malla externa: ", n.mesh.resource_path)
	quit()

func _arbol(n: Node, nivel: int) -> void:
	var extra := ""
	if n is Node3D:
		var n3: Node3D = n
		extra = "  pos=%s scale=%s" % [n3.position, n3.scale]
	print("  ".repeat(nivel), n.name, " [", n.get_class(), "]", extra)
	for c in n.get_children():
		_arbol(c, nivel + 1)

func _todos(n: Node) -> Array:
	var res: Array = [n]
	for c in n.get_children():
		res.append_array(_todos(c))
	return res
