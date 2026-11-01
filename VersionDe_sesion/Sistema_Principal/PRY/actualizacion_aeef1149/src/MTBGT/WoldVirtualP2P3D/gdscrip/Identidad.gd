extends RefCounted
## Identidad local estable y vínculo con la isla registrada.
## El id de peer cambia en cada conexión; este UUID sobrevive a reinicios y es
## lo que permite al anfitrión reconocer al mismo jugador y devolverle su isla.

const RUTA := "user://registro.cfg"
const SECCION_IDENTIDAD := "identidad"
const SECCION_ISLA := "isla"


## Devuelve el UUID local y lo crea la primera vez. Nunca reescribe uno válido.
static func asegurar_identidad(ruta: String = RUTA) -> String:
	var cfg := _cargar(ruta)
	var uuid := str(cfg.get_value(SECCION_IDENTIDAD, "uuid", "")).strip_edges()
	if uuid_valido(uuid):
		return uuid
	uuid = Crypto.new().generate_random_bytes(16).hex_encode()
	cfg.set_value(SECCION_IDENTIDAD, "uuid", uuid)
	cfg.save(ruta)
	return uuid


static func leer_identidad(ruta: String = RUTA) -> String:
	var cfg := _cargar(ruta)
	var uuid := str(cfg.get_value(SECCION_IDENTIDAD, "uuid", "")).strip_edges()
	return uuid if uuid_valido(uuid) else ""


## El UUID solo identifica si tiene la forma exacta que genera este script.
static func uuid_valido(uuid: String) -> bool:
	return uuid.length() == 32 and uuid.is_valid_hex_number()


## Guarda la isla propia sin tocar nick, avatar, posición ni otras secciones.
static func guardar_mi_isla(indice: int, uuid: String, ruta: String = RUTA) -> bool:
	if indice < 0 or not uuid_valido(uuid):
		return false
	var cfg := _cargar(ruta)
	cfg.set_value(SECCION_ISLA, "indice", indice)
	cfg.set_value(SECCION_ISLA, "owner_uuid", uuid)
	cfg.set_value(SECCION_ISLA, "registrada_en", Time.get_datetime_string_from_system(true, true))
	return cfg.save(ruta) == OK


## -1 si no hay vínculo o si pertenece a otra identidad local.
static func leer_mi_isla(uuid: String, ruta: String = RUTA) -> int:
	if not uuid_valido(uuid):
		return -1
	var cfg := _cargar(ruta)
	if str(cfg.get_value(SECCION_ISLA, "owner_uuid", "")) != uuid:
		return -1
	return int(cfg.get_value(SECCION_ISLA, "indice", -1))


static func _cargar(ruta: String) -> ConfigFile:
	var cfg := ConfigFile.new()
	cfg.load(ruta)
	return cfg
