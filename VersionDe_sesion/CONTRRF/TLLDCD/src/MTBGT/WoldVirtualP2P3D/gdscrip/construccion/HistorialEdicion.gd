extends RefCounted
## Pila de deshacer/rehacer por isla.
##
## El historial no sabe qué contiene una acción: solo la guarda, la mueve entre
## la pila de hechas y la de deshechas y descarta las más antiguas. Construccion
## es quien interpreta cada entrada (`terreno`, `prim_crear`, ...). Así el
## formato de las acciones puede crecer sin tocar este módulo.

## Suficiente para varios trazos y ediciones sin crecer sin límite: una
## instantánea de terreno de una isla ocupa ~90 KB.
const MAXIMO := 48

var _hechas := {}    # idx -> Array de Dictionary (la última es la más reciente)
var _deshechas := {} # idx -> Array de Dictionary (la última es la más reciente)


func empujar(idx: int, accion: Dictionary) -> void:
	if idx < 0 or accion.is_empty():
		return
	var pila: Array = _hechas.get(idx, [])
	pila.append(accion)
	while pila.size() > MAXIMO:
		pila.pop_front()
	_hechas[idx] = pila
	# Una acción nueva invalida el rehacer: la rama futura ya no existe.
	_deshechas.erase(idx)


func puede_deshacer(idx: int) -> bool:
	return not (_hechas.get(idx, []) as Array).is_empty()


func puede_rehacer(idx: int) -> bool:
	return not (_deshechas.get(idx, []) as Array).is_empty()


## Saca la última acción y la deja lista para rehacer. {} si no hay nada.
func deshacer(idx: int) -> Dictionary:
	var pila: Array = _hechas.get(idx, [])
	if pila.is_empty():
		return {}
	var accion: Dictionary = pila.pop_back()
	_hechas[idx] = pila
	var rehacer: Array = _deshechas.get(idx, [])
	rehacer.append(accion)
	_deshechas[idx] = rehacer
	return accion


func rehacer(idx: int) -> Dictionary:
	var pila: Array = _deshechas.get(idx, [])
	if pila.is_empty():
		return {}
	var accion: Dictionary = pila.pop_back()
	_deshechas[idx] = pila
	var hechas: Array = _hechas.get(idx, [])
	hechas.append(accion)
	_hechas[idx] = hechas
	return accion


## Cuántas acciones hay en cada pila (la UI muestra el estado de los botones).
func profundidad(idx: int) -> Dictionary:
	return {
		"deshacer": (_hechas.get(idx, []) as Array).size(),
		"rehacer": (_deshechas.get(idx, []) as Array).size(),
	}


func limpiar(idx: int) -> void:
	_hechas.erase(idx)
	_deshechas.erase(idx)


func vaciar() -> void:
	_hechas.clear()
	_deshechas.clear()
