extends SceneTree
## Genera animaciones de LucIA a partir de las de AVH1 corrigiendo la pose de
## reposo: Qdestino = Qrest_destino * (Qrest_origen^-1 * Qorigen).
## Así los huesos de LucIA giran igual que los del avatar sin romperse.

const ORIGEN := "res://gltfimport/avatares/AVH1.gltf"
const LUCIA := "res://lucia3D/GLTF_lucIA/AreaDeTrabajo/LucIA3D/LucIA_rig.glb"
const DESTINO := "user://animaciones_avatar.tres"

const MAPA := {
	"paradoMJ1_1": "lucia_parado",
	"caminarMJ1_2": "lucia_caminar",
	"correrMJ1_3": "lucia_correr",
	"left_StrafeMJ1_4": "lucia_strafe_izq",
	"rightstrafeMJ1_5": "lucia_strafe_der",
}


func _init() -> void:
	var origen := _cargar(ORIGEN)
	var lucia := _cargar(LUCIA)
	var jugador := _jugador(origen)
	var sk_origen := _sk(origen)
	var sk_lucia := _sk(lucia)
	if jugador == null or sk_origen == null or sk_lucia == null:
		print("[gen] faltan nodos")
		quit(1)
		return
	var rests := {}
	for i in sk_origen.get_bone_count():
		var nombre := str(sk_origen.get_bone_name(i))
		if not nombre.begins_with("mixamorig_"):
			continue
		var base := nombre.substr("mixamorig_".length())
		var destino := _hueso(sk_lucia, "mixamorig8_" + base)
		if destino < 0:
			continue
		rests[nombre] = {
			"q_origen": sk_origen.get_bone_rest(i).basis.get_rotation_quaternion(),
			"q_lucia": sk_lucia.get_bone_rest(destino).basis.get_rotation_quaternion(),
		}
	var libreria := AnimationLibrary.new()
	for original in MAPA.keys():
		if not jugador.has_animation(original):
			continue
		var anim := jugador.get_animation(original).duplicate(true) as Animation
		for i in range(anim.get_track_count() - 1, -1, -1):
			var tipo := anim.track_get_type(i)
			if tipo == Animation.TYPE_POSITION_3D or tipo == Animation.TYPE_SCALE_3D:
				anim.remove_track(i)
				continue
			var ruta := str(anim.track_get_path(i))
			var hueso := ruta.get_slice(":", 1)
			if not rests.has(hueso):
				anim.remove_track(i)
				continue
			anim.track_set_path(i, NodePath(ruta.replace("mixamorig_", "mixamorig8_")))
			if tipo != Animation.TYPE_ROTATION_3D:
				continue
			var q_origen_rest: Quaternion = rests[hueso]["q_origen"]
			var q_lucia_rest: Quaternion = rests[hueso]["q_lucia"]
			for k in anim.track_get_key_count(i):
				var q_origen: Quaternion = anim.track_get_key_value(i, k)
				var delta := q_origen_rest.inverse() * q_origen
				anim.track_set_key_value(i, k, (q_lucia_rest * delta).normalized())
		anim.loop_mode = Animation.LOOP_LINEAR
		libreria.add_animation(str(MAPA[original]), anim)
		print("[gen] ", original, " -> ", MAPA[original], " pistas=", anim.get_track_count(), " dur=", anim.length)
	var error := ResourceSaver.save(libreria, DESTINO)
	print("[gen] guardado error=", error, " clips=", libreria.get_animation_list())
	quit(0 if error == OK else 1)


func _cargar(ruta: String) -> Node:
	var p := load(ruta) as PackedScene
	var n := p.instantiate()
	get_root().add_child(n)
	return n


func _sk(n: Node) -> Skeleton3D:
	for s in n.find_children("*", "Skeleton3D", true, false):
		return s as Skeleton3D
	return null


func _jugador(n: Node) -> AnimationPlayer:
	for s in n.find_children("*", "AnimationPlayer", true, false):
		return s as AnimationPlayer
	return null


func _hueso(sk: Skeleton3D, nombre: String) -> int:
	for i in sk.get_bone_count():
		if str(sk.get_bone_name(i)) == nombre:
			return i
	return -1
