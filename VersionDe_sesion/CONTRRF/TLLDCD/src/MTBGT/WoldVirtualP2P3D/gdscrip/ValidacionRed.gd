extends RefCounted
## Validación compartida de los argumentos que llegan por RPC any_peer.
##
## PlayerSync y Construccion reciben datos de cualquier peer conectado y los
## tratan como hostiles: esta es la única copia de las reglas con las que se
## sanean. El orden que siguen los llamantes es siempre el mismo: primero se
## rechaza entero lo no finito (un NaN/Inf nunca se aplica ni se retransmite),
## después se acota a los rangos que la propia casa ya usa y por último se
## consume una ficha del cubo de tokens del peer que llama.
##
## Sin estado global: el cubo guarda sus fichas en un Dictionary del llamante
## (uno por tipo de RPC), así cada sistema lleva sus propios cubos. Se carga
## por ruta, como el resto de la casa:
## const ValRed = preload("res://gdscrip/ValidacionRed.gd")

## Nick: el LineEdit.max_length de SLAV (su NICK_MINIMO es 3).
const NICK_MAX := 16
## Escala de prim por eje: el clamp repetido en Construccion y Prims.
const ESCALA_MIN := 0.15
const ESCALA_MAX := 40.0
## Pincel de terreno: los deslizadores «Radio» y «Fuerza» de ConstructorPanel.
const RADIO_PINCEL_MIN := 2.0
const RADIO_PINCEL_MAX := 30.0
const FUERZA_PINCEL_MIN := 0.2
const FUERZA_PINCEL_MAX := 4.0
## Un trazo nunca avanza más que el PASO_MAXIMO de Construccion.
const DT_PINCEL_MAX := 0.1
## Herramientas que viajan en el pincel: SUBIR..REVERTIR de TerrenoEditable.
const HERRAMIENTA_MIN := 0
const HERRAMIENTA_MAX := 7
## Tope de prims por isla: cada prim crea cuerpo, malla y colisión (3 nodos);
## 1000 acota memoria y escena sin tocar construcciones manuales realistas.
const PRIMS_MAX_POR_ISLA := 1000
## Cubo del pincel: el emisor legítimo envía cada PASO_PINCEL..PASO_MAXIMO
## (0.05..0.1 s), es decir 10..20 RPC/s; la recarga iguala ese máximo y la
## capacidad da unos 2 s de ráfaga.
const CUBO_PINCEL_CAPACIDAD := 40.0
const CUBO_PINCEL_RECARGA := 20.0
## Cubo del rez: rezar es un clic humano; 2/s sostenidos sobran y la ráfaga
## de 10 cubre los pegados legítimos.
const CUBO_REZ_CAPACIDAD := 10.0
const CUBO_REZ_RECARGA := 2.0


## true si el valor no es NaN ni infinito.
static func es_finito(valor: float) -> bool:
	return is_finite(valor)


## true si los tres ejes no son NaN ni infinitos.
static func vec3_es_finito(v: Vector3) -> bool:
	return es_finito(v.x) and es_finito(v.y) and es_finito(v.z)


## true si los cuatro componentes no son NaN ni infinitos.
static func color_es_finito(c: Color) -> bool:
	return es_finito(c.r) and es_finito(c.g) and es_finito(c.b) and es_finito(c.a)


## Acota un número a [minimo, maximo]. El llamante ya rechazó lo no finito:
## clampf propaga NaN, así que aquí no se sanea, solo se recorta.
static func acotar_f(valor: float, minimo: float, maximo: float) -> float:
	return clampf(valor, minimo, maximo)


## Acota cada eje a [minimo, maximo] (el Vector3.clamp que usa la casa).
static func acotar_vec3(v: Vector3, minimo: Vector3, maximo: Vector3) -> Vector3:
	return v.clamp(minimo, maximo)


## Cubo de tokens por clave (un peer) dentro del Dictionary del llamante.
## estado[clave] = [tokens: float, ultimo_s: float]; la primera vez el cubo
## empieza lleno. En cada intento se recarga con el tiempo transcurrido (un
## delta negativo cuenta como 0) sin pasar de la capacidad: si quedan fichas
## para el coste, se descuenta y devuelve true; si no, guarda lo recargado
## y devuelve false.
static func cubo_intentar(estado: Dictionary, clave: int, capacidad: float, recarga_por_s: float, ahora_s: float, coste: float = 1.0) -> bool:
	if not estado.has(clave):
		estado[clave] = [capacidad, ahora_s]
	var registro: Array = estado[clave]
	var tokens := float(registro[0])
	var ultimo := float(registro[1])
	var transcurrido := maxf(ahora_s - ultimo, 0.0)
	tokens = minf(capacidad, tokens + transcurrido * recarga_por_s)
	var instante := ultimo + transcurrido
	if tokens >= coste:
		estado[clave] = [tokens - coste, instante]
		return true
	estado[clave] = [tokens, instante]
	return false
