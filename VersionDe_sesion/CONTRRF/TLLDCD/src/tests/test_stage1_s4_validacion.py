"""Tests de validación de entradas any_peer — Etapa 1, H6 + M21 (Crew S4).

Verifica sobre las fuentes GDScript que todo RPC any_peer trata sus
argumentos como hostiles, en el orden del diseño (s4-design.md): primero se
rechaza entero lo no finito (NaN/Inf nunca se aplica ni se retransmite),
después se acota a los rangos que la propia casa ya usa, y por último se
consume una ficha del cubo de tokens por peer y se respeta el tope de
prims por isla. El helper compartido ValidacionRed.gd es la única casa de
las constantes de límite.

Nota de nombre: el encargo de W5 nombra este fichero
test_stage1_s4_validacion.py; la nota de diseño lo llama
test_s4_validacion_red.py. El líder integra con el nombre que prefiera.

Runtime GDScript: NO PROBADO (sin binario Godot en el portátil); como el
resto de la casa (test_h2_h3_red.py), esto son asertos sobre las fuentes.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
GD_DIR = SRC_DIR / "MTBGT" / "WoldVirtualP2P3D" / "gdscrip"

HELPER = GD_DIR / "ValidacionRed.gd"
PLAYERSYNC = GD_DIR / "PlayerSync.gd"
CONSTRUCCION = GD_DIR / "Construccion.gd"

CONSTANTES = {
    "NICK_MAX": "16",
    "ESCALA_MIN": "0.15",
    "ESCALA_MAX": "40.0",
    "RADIO_PINCEL_MIN": "2.0",
    "RADIO_PINCEL_MAX": "30.0",
    "FUERZA_PINCEL_MIN": "0.2",
    "FUERZA_PINCEL_MAX": "4.0",
    "DT_PINCEL_MAX": "0.1",
    "HERRAMIENTA_MIN": "0",
    "HERRAMIENTA_MAX": "7",
    "PRIMS_MAX_POR_ISLA": "1000",
    "CUBO_PINCEL_CAPACIDAD": "40.0",
    "CUBO_PINCEL_RECARGA": "20.0",
    "CUBO_REZ_CAPACIDAD": "10.0",
    "CUBO_REZ_RECARGA": "2.0",
}


def _leer(path: Path) -> str:
    assert path.is_file(), f"no encontrado: {path}"
    return path.read_text(encoding="utf-8")


def _cuerpo(texto: str, nombre: str) -> str:
    """Cuerpo de una función GDScript: de su línea `func` a la siguiente
    declaración de nivel superior (func/@rpc/const/var/enum o separador)."""
    lineas = texto.splitlines()
    inicio = next(
        i
        for i, l in enumerate(lineas)
        if re.match(rf"^(?:static )?func {re.escape(nombre)}\b", l)
    )
    cuerpo = [lineas[inicio]]
    for linea in lineas[inicio + 1:]:
        if re.match(r"^((?:static )?func |@rpc|const |var |enum )", linea) or linea.startswith("# ---"):
            break
        cuerpo.append(linea)
    return "\n".join(cuerpo)


# ---------------------------------------------------------------------------
# Helper compartido ValidacionRed.gd
# ---------------------------------------------------------------------------

def test_helper_existe_con_api_y_constantes_exactas():
    """ValidacionRed.gd existe, es RefCounted y define la API y los límites
    exactos del diseño H6/M21 (una sola casa para todas las cotas)."""
    contenido = _leer(HELPER)
    assert contenido.splitlines()[0] == "extends RefCounted"
    for nombre, valor in CONSTANTES.items():
        assert f"const {nombre} := {valor}" in contenido, f"falta {nombre}"
    assert "static func es_finito(valor: float) -> bool" in contenido
    assert "return is_finite(valor)" in contenido
    assert "static func vec3_es_finito(v: Vector3) -> bool" in contenido
    assert "static func color_es_finito(c: Color) -> bool" in contenido
    assert "static func acotar_f(valor: float, minimo: float, maximo: float) -> float" in contenido
    assert "static func acotar_vec3(v: Vector3, minimo: Vector3, maximo: Vector3) -> Vector3" in contenido
    assert (
        "static func cubo_intentar(estado: Dictionary, clave: int, capacidad: float, "
        "recarga_por_s: float, ahora_s: float, coste: float = 1.0) -> bool"
    ) in contenido


def test_helper_cubo_empieza_lleno_recarga_acotada_y_delta_negativo_cero():
    """El cubo de tokens: primera vez lleno, recarga con tope en la capacidad
    y un reloj que retrocede no regala fichas (H6/M21, freno por peer)."""
    contenido = _leer(HELPER)
    cuerpo = _cuerpo(contenido, "cubo_intentar")
    assert "estado[clave] = [capacidad, ahora_s]" in cuerpo
    assert "maxf(ahora_s - ultimo, 0.0)" in cuerpo
    assert "minf(capacidad, tokens + transcurrido * recarga_por_s)" in cuerpo
    assert "if tokens >= coste:" in cuerpo


def test_helper_es_la_unica_casa_de_las_constantes():
    """Ningún consumidor redefine los límites: PlayerSync y Construccion los
    leen siempre como ValRed.<CONSTANTE> tras cargar el helper por ruta."""
    helper = _leer(HELPER)
    for ruta in (PLAYERSYNC, CONSTRUCCION):
        contenido = _leer(ruta)
        assert re.search(
            r'const ValRed :?= preload\("res://gdscrip/ValidacionRed\.gd"\)', contenido
        ), f"{ruta.name} no carga el helper por ruta"
        for nombre in CONSTANTES:
            assert not re.search(rf"^const {nombre}\b", contenido, re.M), (
                f"{ruta.name} redefine {nombre}: el helper deja de ser la única casa"
            )
    assert "ValRed.NICK_MAX" in _leer(PLAYERSYNC)
    assert "const PRIMS_MAX_POR_ISLA := 1000" in helper


# ---------------------------------------------------------------------------
# PlayerSync.gd — _net_position (H6)
# ---------------------------------------------------------------------------

def test_net_position_descarta_no_finitos_antes_de_aplicar():
    """Un paquete con pos o rot_y no finitos se descarta entero ANTES de
    crear el clon, fijar el objetivo o aplicar la rotación (H6)."""
    cuerpo = _cuerpo(_leer(PLAYERSYNC), "_net_position")
    guarda = "if not ValRed.vec3_es_finito(pos) or not ValRed.es_finito(rot_y):"
    assert guarda in cuerpo
    i_guarda = cuerpo.index(guarda)
    assert i_guarda < cuerpo.index("_ensure_proxy(sender, ruta_efectiva, pers)")
    assert i_guarda < cuerpo.index("_targets[sender] = pos")
    assert i_guarda < cuerpo.index("proxy.rotation.y = rot_y")


def test_net_position_nick_acotado_y_estado_acotado():
    """El nick se trunca a ValRed.NICK_MAX antes de llegar a la etiqueta y el
    estado de animación se acota a 0..3, los valores de la casa (H6)."""
    cuerpo = _cuerpo(_leer(PLAYERSYNC), "_net_position")
    assert "var nick_ok := nick.left(ValRed.NICK_MAX)" in cuerpo
    assert 'label.text = nick_ok if nick_ok != ""' in cuerpo
    assert "_estados[sender] = clampi(estado, 0, 3)" in cuerpo


def test_net_position_freno_avatar_menor_de_2s():
    """Cambios de avatar de un mismo peer más rápidos que 2000 ms se ignoran:
    se mantiene la ruta vigente y no se reconstruye el clon (H6)."""
    contenido = _leer(PLAYERSYNC)
    assert "const AVATAR_ESPERA_MS := 2000" in contenido
    assert "var _avatar_t: Dictionary = {}" in contenido
    cuerpo = _cuerpo(contenido, "_net_position")
    assert "_ruta_avatar_validada(sender, avatar_path)" in cuerpo
    assert cuerpo.index("_ruta_avatar_validada") < cuerpo.index("_ensure_proxy(sender")
    freno = _cuerpo(contenido, "_ruta_avatar_validada")
    assert "if pedida == \"\" or pedida == vigente:" in freno
    assert "ahora - int(_avatar_t[sender]) < AVATAR_ESPERA_MS" in freno
    assert "return vigente" in freno
    assert "_avatar_t[sender] = ahora" in freno
    assert "_avatar_t.erase(id)" in _cuerpo(contenido, "_remove_proxy")
    assert "_avatar_t.clear()" in _cuerpo(contenido, "_clear_all_proxies")


# ---------------------------------------------------------------------------
# Construccion.gd — RPCs de edición (M21)
# ---------------------------------------------------------------------------

def test_solicitar_pincel_rechaza_no_finitos_y_herramienta_fuera_de_rango():
    """_solicitar_pincel descarta centro/delta/radio/fuerza/dt no finitos y
    herramientas fuera de 0..7 antes de tocar el terreno (M21)."""
    cuerpo = _cuerpo(_leer(CONSTRUCCION), "_solicitar_pincel")
    assert "_validar_remitente(idx, remitente)" in cuerpo
    for fragmento in (
        "not ValRed.vec3_es_finito(centro)",
        "not ValRed.vec3_es_finito(delta)",
        "not ValRed.es_finito(radio)",
        "not ValRed.es_finito(fuerza)",
        "not ValRed.es_finito(dt)",
        "herramienta < ValRed.HERRAMIENTA_MIN",
        "herramienta > ValRed.HERRAMIENTA_MAX",
    ):
        assert fragmento in cuerpo, f"falta rechazo: {fragmento}"
    assert cuerpo.index("not ValRed.vec3_es_finito(centro)") < cuerpo.index(
        "terreno.aplicar_pincel("
    )


def test_solicitar_pincel_acota_antes_de_aplicar_y_retransmitir():
    """Radio, fuerza y dt se acotan a los rangos de la casa; el centro, que
    viaja en coordenadas de mundo, se acota respecto al centro de la isla
    destino (origen_isla ± RADIO_ISLA). SOLO los
    valores acotados se aplican y se retransmiten a los demás peers (M21)."""
    cuerpo = _cuerpo(_leer(CONSTRUCCION), "_solicitar_pincel")
    assert "radio = ValRed.acotar_f(radio, ValRed.RADIO_PINCEL_MIN, ValRed.RADIO_PINCEL_MAX)" in cuerpo
    assert "fuerza = ValRed.acotar_f(fuerza, ValRed.FUERZA_PINCEL_MIN, ValRed.FUERZA_PINCEL_MAX)" in cuerpo
    assert "dt = ValRed.acotar_f(dt, 0.0, ValRed.DT_PINCEL_MAX)" in cuerpo
    assert "centro.x = ValRed.acotar_f(centro.x, origen_isla.x - RADIO_ISLA, origen_isla.x + RADIO_ISLA)" in cuerpo
    assert "centro.z = ValRed.acotar_f(centro.z, origen_isla.z - RADIO_ISLA, origen_isla.z + RADIO_ISLA)" in cuerpo
    assert "origen_isla" in cuerpo  # acotado relativo a la isla, no al origen del mundo
    i_acota = cuerpo.index("radio = ValRed.acotar_f")
    assert i_acota < cuerpo.index("terreno.aplicar_pincel(")
    assert i_acota < cuerpo.index('rpc_id(peer, "_pincel_remoto"')


def test_solicitar_pincel_consulta_cubo_por_peer_antes_de_aplicar():
    """El cubo del pincel (40 fichas, recarga 20/s) se consulta con la clave
    del remitente y sin ficha no se aplica ni se retransmite (M21)."""
    contenido = _leer(CONSTRUCCION)
    assert "var _cubo_pincel: Dictionary = {}" in contenido
    cuerpo = _cuerpo(contenido, "_solicitar_pincel")
    assert (
        "ValRed.cubo_intentar(_cubo_pincel, remitente, ValRed.CUBO_PINCEL_CAPACIDAD,"
    ) in cuerpo
    assert "ValRed.CUBO_PINCEL_RECARGA" in cuerpo
    assert cuerpo.index("cubo_intentar") < cuerpo.index("terreno.aplicar_pincel(")


def test_host_crear_prim_rechaza_no_finitos_y_acota_posicion_y_escala():
    """La puerta del anfitrión descarta pos/rot/escala/color no finitos y
    acota la posición a la isla (±95, y 0..140) y la escala a 0.15..40 con
    las constantes del helper (M21)."""
    cuerpo = _cuerpo(_leer(CONSTRUCCION), "_host_crear_prim")
    assert "not ValRed.vec3_es_finito(pos)" in cuerpo
    assert "not ValRed.vec3_es_finito(rot)" in cuerpo
    assert "not ValRed.vec3_es_finito(esc)" in cuerpo
    assert "not ValRed.color_es_finito(color)" in cuerpo
    assert (
        "pos = ValRed.acotar_vec3(pos, Vector3(-RADIO_ISLA, 0.0, -RADIO_ISLA),"
    ) in cuerpo
    assert "Vector3(RADIO_ISLA, 140.0, RADIO_ISLA))" in cuerpo
    assert "Vector3(ValRed.ESCALA_MIN, ValRed.ESCALA_MIN, ValRed.ESCALA_MIN)" in cuerpo
    assert "Vector3(ValRed.ESCALA_MAX, ValRed.ESCALA_MAX, ValRed.ESCALA_MAX)" in cuerpo
    assert cuerpo.index("not ValRed.vec3_es_finito(pos)") < cuerpo.index(
        "_prims[idx][id] = datos"
    )


def test_solicitar_rez_consulta_cubo_y_difunde_lo_almacenado():
    """_solicitar_rez consume una ficha del cubo de rez por remitente y, tras
    crear, difunde los datos ALMACENADOS (ya acotados), no los crudos del
    solicitante (M21)."""
    contenido = _leer(CONSTRUCCION)
    assert "var _cubo_rez: Dictionary = {}" in contenido
    cuerpo = _cuerpo(contenido, "_solicitar_rez")
    assert "_validar_remitente(idx, remitente)" in cuerpo
    assert (
        "ValRed.cubo_intentar(_cubo_rez, remitente, ValRed.CUBO_REZ_CAPACIDAD,"
    ) in cuerpo
    assert "ValRed.CUBO_REZ_RECARGA" in cuerpo
    assert cuerpo.index("cubo_intentar") < cuerpo.index("_host_crear_prim(")
    assert "_difundir_prim_creado(idx, id)" in cuerpo
    assert 'rpc("_prim_creado"' not in cuerpo


def test_tope_prims_por_isla_en_la_puerta_del_anfitrion():
    """Con la isla en el tope (1000 prims) _host_crear_prim devuelve 0 antes
    de asignar id ni almacenar nada: enforcement solo en la puerta única
    del anfitrión, con el conteo del propio Dictionary de la isla (M21)."""
    cuerpo = _cuerpo(_leer(CONSTRUCCION), "_host_crear_prim")
    tope = "if _prims[idx].size() >= ValRed.PRIMS_MAX_POR_ISLA:"
    assert tope in cuerpo, (
        "falta el tope de prims por isla en _host_crear_prim "
        "(inserción de W3 pendiente de integrar por el líder)"
    )
    assert cuerpo.index("if not _prims.has(idx):") < cuerpo.index(tope)
    assert cuerpo.index(tope) < cuerpo.index("_prims[idx][id] = datos")


def test_regiones_s1_intactas_sin_validacionred():
    """Las regiones de S1 (_es_mi_isla/_validar_remitente y vecinas) no se
    tocan en S4: ninguna llama al helper nuevo."""
    contenido = _leer(CONSTRUCCION)
    for nombre in ("_es_mi_isla", "_puede_guardar", "_puedo_editar", "_validar_remitente"):
        assert "ValRed" not in _cuerpo(contenido, nombre), f"S1 tocada en {nombre}"


def test_solicitar_prim_tambien_valida_la_edicion_en_vivo():
    """La edición en vivo de un prim ya creado (_solicitar_prim ->
    _aplicar_cambio_red) rechaza no finitos y acota la escala igual que
    la creación (M21). Era un hueco detectado por W5 como xfail estricto;
    el líder lo cerró al integrar por ser vía alcanzable desde any_peer."""
    contenido = _leer(CONSTRUCCION)
    cuerpos = _cuerpo(contenido, "_solicitar_prim") + _cuerpo(
        contenido, "_aplicar_cambio_red"
    )
    assert "ValRed.vec3_es_finito(pos)" in cuerpos
    assert "ValRed.ESCALA_MAX" in cuerpos
