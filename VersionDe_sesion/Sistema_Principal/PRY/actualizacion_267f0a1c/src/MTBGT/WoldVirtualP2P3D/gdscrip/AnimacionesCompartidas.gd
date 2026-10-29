class_name AnimacionesCompartidas
extends RefCounted
## Presta las cinco animaciones de los avatares principales a los que vienen sin
## ninguna.
##
## Las plazas 9-24 del catalogo son mallas GLB con esqueleto Mixamo y cero clips:
## sus animaciones viajaban dentro de los `*_anim.glb`, que pesaban lo mismo que
## el modelo y ya no se distribuyen. Aqui se copian los clips de AVH1 sobre el
## AnimationPlayer del avatar, porque todos los exports comparten el mismo
## esqueleto de 65 huesos y solo cambia el prefijo (`mixamorig:`,
## `mixamorig12:`, `mixamorig7:`...), que se quita para emparejarlos.

const REFERENCIA := "res://gltfimport/avatares/AVH1.gltf"
## Nombres que esperan el AnimationTree de las escenas Ch3D.
const CLIPS: Array[String] = [
	"paradoMJ1_1",
	"caminarMJ1_2",
	"correrMJ1_3",
	"left_StrafeMJ1_4",
	"rightstrafeMJ1_5",
]

static var _clips: Dictionary = {}


## Deja las cinco animaciones en el avatar. Devuelve cuantas ha anadido: 0 si ya
## las traia o si no hay esqueleto donde aplicarlas.
static func asegurar(avatar: Node) -> int:
	var reproductor := _reproductor(avatar)
	var faltan := 0
	for nombre in CLIPS:
		if not reproductor.has_animation(nombre):
			faltan += 1
	if faltan == 0:
		return 0
	var esqueletos := avatar.find_children("*", "Skeleton3D", true, false)
	if esqueletos.is_empty():
		return 0
	var huesos := _mapa_huesos(esqueletos[0] as Skeleton3D)
	var prefijo := String(_raiz(reproductor).get_path_to(esqueletos[0]))
	var clips := _referencia()
	var puestas := 0
	for nombre in CLIPS:
		if reproductor.has_animation(nombre) or not clips.has(nombre):
			continue
		_anadir(reproductor, nombre, _retarget(clips[nombre], huesos, prefijo))
		puestas += 1
	if puestas > 0:
		_refrescar_arbol(avatar)
	return puestas


## En Godot 4 los clips cuelgan de una AnimationLibrary, no del reproductor.
static func _anadir(reproductor: AnimationPlayer, nombre: String, anim: Animation) -> void:
	var libreria: AnimationLibrary = null
	if reproductor.has_animation_library(""):
		libreria = reproductor.get_animation_library("")
	if libreria == null:
		libreria = AnimationLibrary.new()
		reproductor.add_animation_library("", libreria)
	libreria.add_animation(nombre, anim)


static func _arbol(avatar: Node) -> AnimationTree:
	var arboles := avatar.find_children("*", "AnimationTree", true, false)
	return arboles[0] as AnimationTree if not arboles.is_empty() else null


## El AnimationTree ya se ha configurado con los clips que habia al entrar al
## arbol (ninguno, en estas mallas), asi que hay que reiniciarlo para que vuelva
## a resolver los nombres. El toggle es obligatorio: el setter ignora el valor
## repetido.
static func _refrescar_arbol(avatar: Node) -> void:
	var arbol := _arbol(avatar)
	if arbol == null or not arbol.active or not arbol.is_inside_tree():
		return
	arbol.active = false
	arbol.active = true


## AnimationPlayer que usa el AnimationTree (`../AnimationPlayer` en las escenas
## Ch3D). Si la malla venia sin reproductor se crea donde el arbol lo espera;
## crearlo en otro sitio dejaria el arbol sin clips.
static func _reproductor(avatar: Node) -> AnimationPlayer:
	var arbol := _arbol(avatar)
	if arbol:
		var esperado := arbol.get_node_or_null(arbol.anim_player)
		if esperado is AnimationPlayer:
			return esperado as AnimationPlayer
		if esperado == null:
			var ruta := String(arbol.anim_player)
			var padre: Node = arbol.get_node_or_null(NodePath(ruta.get_base_dir()))
			var nuevo := AnimationPlayer.new()
			nuevo.name = ruta.get_file()
			(padre if padre else avatar).add_child(nuevo)
			return nuevo
	var encontrados := avatar.find_children("*", "AnimationPlayer", true, false)
	if not encontrados.is_empty():
		return encontrados[0] as AnimationPlayer
	var suelto := AnimationPlayer.new()
	suelto.name = "AnimationPlayer"
	avatar.add_child(suelto)
	return suelto


## Nodo desde el que cuelgan las rutas de pista del reproductor.
static func _raiz(reproductor: AnimationPlayer) -> Node:
	var raiz := reproductor.get_node_or_null(reproductor.root_node)
	return raiz if raiz else reproductor.get_parent()


static func _referencia() -> Dictionary:
	if not _clips.is_empty():
		return _clips
	var escena := (load(REFERENCIA) as PackedScene).instantiate()
	var reproductor := _reproductor(escena)
	for nombre in CLIPS:
		if reproductor.has_animation(nombre):
			_clips[nombre] = reproductor.get_animation(nombre).duplicate(true)
	escena.free()
	return _clips


static func _mapa_huesos(esqueleto: Skeleton3D) -> Dictionary:
	var mapa := {}
	for indice in esqueleto.get_bone_count():
		var hueso := esqueleto.get_bone_name(indice)
		mapa[_normalizar(hueso)] = hueso
	return mapa


## `mixamorig12_Hips` y `mixamorig_Hips` son el mismo hueso con otro prefijo de
## export, asi que se comparan sin el.
static func _normalizar(hueso: String) -> String:
	var nombre := hueso.to_lower()
	if nombre.begins_with("mixamorig"):
		var corte := nombre.find("_")
		nombre = nombre.substr(corte + 1) if corte >= 0 else nombre.substr(9)
	return nombre


## Copia el clip apuntando a los huesos del avatar destino. Las pistas que no
## corresponden a ningun hueso (por ejemplo las que animan un nodo suelto) se
## descartan: el esqueleto es lo unico que comparten los exports.
static func _retarget(clip: Animation, huesos: Dictionary, prefijo: String) -> Animation:
	var copia := clip.duplicate(true) as Animation
	for indice in range(copia.get_track_count() - 1, -1, -1):
		var hueso := String(copia.track_get_path(indice).get_subname(0))
		var destino: String = huesos.get(_normalizar(hueso), "")
		if destino.is_empty():
			copia.remove_track(indice)
		else:
			copia.track_set_path(indice, NodePath(prefijo + ":" + destino))
	return copia
