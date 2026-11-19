extends Node
## Reposo procedural de LucIA mientras no esté importado su rig animado.
##
## El `.blend` llega en pose de bind (T). Este nodo busca el Skeleton3D y baja
## los brazos a una postura natural, con una respiración leve. Cuando el rig
## animado (`LucIA_rig.glb`) esté importado, este nodo se puede quitar: su
## AnimationPlayer manda.

const BRAZO_ABAJO := 1.15
const RESPIRACION := 0.02

var _esqueleto: Skeleton3D
var _indice_pecho := -1
var _base_pecho := Quaternion.IDENTITY
var _tiempo := 0.0


func _ready() -> void:
	await get_tree().process_frame
	_esqueleto = _buscar(get_parent())
	if _esqueleto == null:
		print("[LuciaPose] sin Skeleton3D: se deja la pose original")
		return
	_aplicar_reposo()


func _buscar(nodo: Node) -> Skeleton3D:
	if nodo is Skeleton3D:
		return nodo
	for hijo in nodo.get_children():
		var encontrado := _buscar(hijo)
		if encontrado != null:
			return encontrado
	return null


## Baja los brazos y deja las piernas rectas. Los nombres son los de Mixamo.
func _aplicar_reposo() -> void:
	for i in _esqueleto.get_bone_count():
		var nombre := _esqueleto.get_bone_name(i).to_lower()
		if nombre.contains("leftarm") and not nombre.contains("fore"):
			_esqueleto.set_bone_pose_rotation(i, Quaternion(Vector3(0, 0, 1), -BRAZO_ABAJO))
		elif nombre.contains("rightarm") and not nombre.contains("fore"):
			_esqueleto.set_bone_pose_rotation(i, Quaternion(Vector3(0, 0, 1), BRAZO_ABAJO))
		elif nombre.contains("leftforearm"):
			_esqueleto.set_bone_pose_rotation(i, Quaternion(Vector3(0, 0, 1), -0.25))
		elif nombre.contains("rightforearm"):
			_esqueleto.set_bone_pose_rotation(i, Quaternion(Vector3(0, 0, 1), 0.25))
		elif nombre.contains("spine1") or nombre.contains("chest"):
			_indice_pecho = i
			_base_pecho = _esqueleto.get_bone_pose_rotation(i)
	print("[LuciaPose] reposo aplicado a %d huesos" % _esqueleto.get_bone_count())


func _process(delta: float) -> void:
	if _esqueleto == null or _indice_pecho < 0:
		return
	_tiempo += delta
	var respiracion := sin(_tiempo * 1.4) * RESPIRACION
	_esqueleto.set_bone_pose_rotation(
		_indice_pecho,
		_base_pecho * Quaternion(Vector3(1, 0, 0), respiracion))
