extends Node3D
## Isla Única LucIA: futura DAO del metaverso y sede de LucIA.
##
## Reglas de la isla:
## - Vive siempre en el origen (0,0,0) del mundo, en planta; la altura la marca
##   el terreno del GLB igual que en las islas de ChunkManager.
## - No participa del reparto de islas de ChunkManager (no tiene índice, no se
##   reclama y no se retira al desconectarse nadie), así que nunca se duplica.
## - Es el único nodo del grupo `isla_unica_lucia`; una copia accidental se
##   descarta al arrancar.
## - Su malla es IslaUnicaLucIA.glb. Si Godot aún no ha importado el GLB, se
##   levanta una plataforma de respaldo para no dejar el mundo sin suelo.

const GRUPO := "isla_unica_lucia"
const RUTA_GLB := "res://lucia3D/IslaUnicaLucIA/IslaUnicaLucIA.glb"
const RUTA_DATOS := "res://lucia3D/IslaUnicaLucIA/DAO/dao_metaverso.json"
## Mismo desplazamiento vertical que `ISLA3DCHUNK` en ISLA3Dblock.tscn: el GLB
## comparte el terreno de las islas de ChunkManager, y sin él la meseta quedaría
## 10 m por encima del resto del archipiélago.
const OFFSET_ISLA := -9.75
## Altura de la meseta del GLB ya desplazada; coincide con la superficie de las
## islas de jugador (~40, con el mar en ~39).
const ALTURA_MESETA := 40.2

@export var id_dao: String = "woldvirtual.dao.metaverso"
@export var es_sede_lucia: bool = true
@export var activa: bool = true

var datos_dao: Dictionary = {}
var malla_cargada := false


func _ready() -> void:
	if not _es_la_unica():
		return
	add_to_group(GRUPO)
	global_position = Vector3.ZERO
	rotation = Vector3.ZERO
	if not activa:
		return
	_cargar_datos()
	_cargar_malla()


func _es_la_unica() -> bool:
	for nodo in get_tree().get_nodes_in_group(GRUPO):
		if nodo != self and is_instance_valid(nodo):
			push_warning("IslaUnicaLucIA duplicada: se descarta esta instancia.")
			queue_free()
			return false
	return true


func _cargar_datos() -> void:
	if not FileAccess.file_exists(RUTA_DATOS):
		push_warning("Sin carta DAO en " + RUTA_DATOS + "; se usan valores por defecto.")
		return
	var crudo = JSON.parse_string(FileAccess.get_file_as_string(RUTA_DATOS))
	if crudo is Dictionary:
		datos_dao = crudo
		var carta := str(datos_dao.get("id", ""))
		if not carta.is_empty() and carta != id_dao:
			push_warning("Carta DAO '%s' distinta de id_dao '%s'." % [carta, id_dao])
	else:
		push_warning("La carta DAO no es un JSON válido.")


func _cargar_malla() -> void:
	if not ResourceLoader.exists(RUTA_GLB):
		push_warning("IslaUnicaLucIA.glb sin importar todavía; se usa plataforma provisional.")
		_plataforma_respaldo()
		return
	var recurso: Resource = load(RUTA_GLB)
	if not (recurso is PackedScene):
		push_warning("IslaUnicaLucIA.glb no se cargó como escena; se usa plataforma provisional.")
		_plataforma_respaldo()
		return
	var malla := (recurso as PackedScene).instantiate() as Node3D
	malla.name = "MallaIsla"
	malla.position = Vector3(0.0, OFFSET_ISLA, 0.0)
	add_child(malla)
	malla_cargada = true
	# Los nodos `-col` del GLB ya traen colisión al importarse; si el import no
	# la generó, se construye aquí para que la isla nunca quede sin suelo.
	if _cuerpo_colision(malla) == null:
		_colision_trimesh(malla)


func _cuerpo_colision(raiz: Node) -> CollisionObject3D:
	for hijo in raiz.get_children():
		if hijo is CollisionObject3D:
			return hijo as CollisionObject3D
		var encontrado := _cuerpo_colision(hijo)
		if encontrado != null:
			return encontrado
	return null


func _colision_trimesh(raiz: Node) -> void:
	for hijo in raiz.get_children():
		if hijo is MeshInstance3D and (hijo as MeshInstance3D).mesh != null:
			(hijo as MeshInstance3D).create_trimesh_collision()
		_colision_trimesh(hijo)


func _plataforma_respaldo() -> void:
	var plataforma := MeshInstance3D.new()
	plataforma.name = "PlataformaRespaldo"
	var malla := CylinderMesh.new()
	malla.top_radius = 90.0
	malla.bottom_radius = 90.0
	malla.height = 4.0
	plataforma.mesh = malla
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.16, 0.24, 0.2)
	material.roughness = 0.9
	plataforma.material_override = material
	plataforma.position = Vector3(0.0, ALTURA_MESETA - 2.0, 0.0)
	add_child(plataforma)

	var cuerpo := StaticBody3D.new()
	cuerpo.name = "ColisionRespaldo"
	cuerpo.position = plataforma.position
	var forma := CollisionShape3D.new()
	var cilindro := CylinderShape3D.new()
	cilindro.radius = 90.0
	cilindro.height = 4.0
	forma.shape = cilindro
	cuerpo.add_child(forma)
	add_child(cuerpo)


## Punto donde se sienta el núcleo de LucIA cuando sea su sede.
func sede_lucia() -> Marker3D:
	if not es_sede_lucia:
		return null
	return get_node_or_null("SedeLucIA") as Marker3D


## Plaza con las estaciones del proceso de registro de la DAO.
func plaza_registro():
	return get_node_or_null("PlazaRegistroDAO")


func es_unica() -> bool:
	return is_in_group(GRUPO)
