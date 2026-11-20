"""Motor de deteccion estatica de STM_DEF.

Analiza texto, ficheros y lineas de comandos buscando el patron del dropper
"EtherHiding" y de los loaders ofuscados con obfuscator.io. Es pura logica sin
efectos secundarios: no descarga, no ejecuta y no borra nada — exactamente lo
contrario del malware que persigue.
"""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from . import SRC_DIR, iocs
from .modelos import ALTA, BAJA, MEDIA, Hallazgo, puntuar, clasificar

#: Tamano maximo de fichero que se inspecciona (los droppers son diminutos).
LIMITE_BYTES = 512 * 1024
#: Longitud maxima del fragmento guardado como evidencia.
LARGO_FRAGMENTO = 160

# --- umbrales de la heuristica de entropia --------------------------------
# Conservadores a proposito: solo deben saltar con cargas empaquetadas/ofuscadas,
# nunca con codigo o texto normal. Se miden sobre el texto ya decodificado.
UMBRAL_ENTROPIA = 6.0        # bits/caracter (minificado/cifrado suele superar 6)
UMBRAL_LARGO_TEXTO = 1500    # no se aplica a ficheros pequenos
UMBRAL_LINEA_LARGA = 800     # longitud de la linea mas larga
UMBRAL_SIMBOLOS = 0.35       # fraccion de caracteres no alfanumericos
UMBRAL_IMPRIMIBLE = 0.75     # fraccion minima de caracteres imprimibles

#: Directorios que nunca se recorren (artefactos, dependencias, caches).
DIRS_IGNORADOS = frozenset({
    ".git", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".vs", ".idea", "bin", "obj", "dist", "build", ".mypy_cache",
})

#: Fichero de allowlist de rutas (una por linea, ``#`` comenta).
ALLOWLIST_PATH: Path = Path(__file__).resolve().parent / "rutas_ignoradas.txt"

#: Rutas que contienen los IOC de forma documental o de prueba (falsos positivos).
IGNORADOS_POR_DEFECTO: Tuple[str, ...] = (
    "tests/test_stm_def.py",
)

#: Extensiones de codigo ejecutable: nunca deberian silenciarse por allowlist.
EXTENSIONES_EJECUTABLES = frozenset({".py", ".pyw", ".js", ".mjs", ".cjs", ".ps1", ".bat", ".cmd", ".sh"})


def entradas_allowlist() -> Tuple[str, ...]:
    """Rutas declaradas en la allowlist, tal cual (sin resolver ni validar).

    Suma las de por defecto con las de ``rutas_ignoradas.txt`` (relativas a
    ``src/``, ``#`` comenta).
    """
    relativas = list(IGNORADOS_POR_DEFECTO)
    if ALLOWLIST_PATH.is_file():
        for linea in ALLOWLIST_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            limpio = linea.split("#", 1)[0].strip()
            if limpio:
                relativas.append(limpio)
    return tuple(relativas)


def rutas_ignoradas() -> Tuple[Path, ...]:
    """Rutas del taller excluidas del escaneo (fixtures y documentacion).

    Sirve para que el barrido no se delate con sus propias muestras sin
    renunciar a la deteccion real: por precaucion, el codigo ejecutable solo
    puede silenciarse si vive dentro de ``tests/`` (fixtures).
    """
    rutas: List[Path] = []
    for relativa in entradas_allowlist():
        candidata = (SRC_DIR / relativa).resolve()
        ejecutable = candidata.suffix.lower() in EXTENSIONES_EJECUTABLES
        if ejecutable and "tests" not in candidata.parts:
            continue  # nunca se silencia codigo ejecutable fuera de pruebas
        rutas.append(candidata)
    return tuple(rutas)


def allowlist_obsoleta() -> Tuple[str, ...]:
    """Entradas de la allowlist que ya no existen en el arbol.

    Una entrada que apunta a una ruta inexistente no protege de nada: si el
    fichero se movio, el barrido vuelve a delatarse con sus propios IOC. Es lo
    que ocurrio el 2026-11-07 al mover la documentacion a ``STM_DOC/`` mientras
    la allowlist seguia nombrando ``README_DESARROLLO.md`` en la raiz de
    ``src/``: 26 hallazgos ALTA y, por el hook ``arranque``, el visor bloqueado.

    Se denuncia en vez de silenciarse, para que el siguiente movimiento de
    ficheros lo detecte el CI y no el usuario al abrir el visor.
    """
    return tuple(r for r in entradas_allowlist() if not (SRC_DIR / r).exists())


def hallazgos_allowlist() -> List[Hallazgo]:
    """Convierte la allowlist obsoleta en hallazgos MEDIA (bloquean el CI)."""
    return [
        Hallazgo(
            id="config.allowlist_obsoleta",
            severidad=MEDIA,
            descripcion="entrada de allowlist que no existe: una ruta movida deja el barrido sin proteccion",
            origen=str(SRC_DIR / relativa),
        )
        for relativa in allowlist_obsoleta()
    ]


#: Extensiones con texto analizable.
EXTENSIONES_TEXTO = frozenset({
    ".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".json", ".orc", ".txt",
    ".ps1", ".psm1", ".bat", ".cmd", ".sh", ".gd", ".cs", ".yaml", ".yml",
    ".toml", ".md", ".html", ".htm", ".xml", ".env", ".cfg", ".ini", ".pth",
})

#: Severidad de cada patron de comando.
_SEVERIDAD_COMANDO: Dict[str, str] = {
    "cmd.node": MEDIA,
    "cmd.nodeinit": ALTA,
    "cmd.pwshhidden": MEDIA,
    "cmd.curlpipe": ALTA,
}

_FRAGMENTOS_JS: Tuple[str, ...] = (
    r"\bfunction\b", r"=>", r"\bvar\b", r"\brequire\s*\(", r"\bmodule\.exports\b",
    r"\bconst\b", r"\blet\b",
)


def _recortar(texto: str) -> str:
    limpio = " ".join(texto.strip().split())
    return limpio[:LARGO_FRAGMENTO]


def analizar_texto(texto: str, origen: str = "") -> List[Hallazgo]:
    """Devuelve los hallazgos de un texto, sin repetir el mismo patron.

    De cada patron se guarda la primera coincidencia (linea y fragmento) y se
    cuenta cuantas veces aparece, para no ahogar el informe en ruido.
    """
    encontrados: Dict[str, Hallazgo] = {}
    conteo: Dict[str, int] = {}
    for numero, linea in enumerate(texto.splitlines(), start=1):
        for patron, regex in iocs.REGEX_COMPILADAS:
            coincidencia = regex.search(linea)
            if coincidencia is None:
                continue
            conteo[patron.id] = conteo.get(patron.id, 0) + 1
            if patron.id not in encontrados:
                encontrados[patron.id] = Hallazgo(
                    id=patron.id,
                    severidad=patron.severidad,
                    descripcion=patron.descripcion,
                    origen=origen,
                    linea=numero,
                    fragmento=_recortar(linea),
                )
    resultado: List[Hallazgo] = []
    for id_, hallazgo in encontrados.items():
        if conteo[id_] > 1:
            hallazgo = Hallazgo(
                id=hallazgo.id, severidad=hallazgo.severidad,
                descripcion=hallazgo.descripcion, origen=hallazgo.origen,
                linea=hallazgo.linea, fragmento=hallazgo.fragmento,
                repeticiones=conteo[id_],
            )
        resultado.append(hallazgo)
    return resultado


def parece_javascript(texto: str) -> bool:
    """Heuristica: el texto tiene pinta de JavaScript aunque no lo parezca."""
    import re
    marcas = sum(1 for patron in _FRAGMENTOS_JS if re.search(patron, texto))
    return marcas >= 2


# -------------------------------------------------------- entropia / ofuscacion
def entropia_shannon(texto: str) -> float:
    """Entropia de Shannon en bits por caracter (0 = uniforme, ~8 = aleatorio)."""
    if not texto:
        return 0.0
    total = len(texto)
    frecuencias = Counter(texto)
    return -sum((n / total) * math.log2(n / total) for n in frecuencias.values())


def ratio_imprimible(texto: str) -> float:
    """Fraccion de caracteres imprimibles (el tabulador y los saltos cuentan)."""
    if not texto:
        return 1.0
    imprimibles = sum(1 for c in texto if c.isprintable() or c in "\t\r\n")
    return imprimibles / len(texto)


def ratio_simbolos(texto: str) -> float:
    """Fraccion de caracteres que no son letras, digitos ni espacios."""
    if not texto:
        return 0.0
    simbolos = sum(1 for c in texto if not c.isalnum() and not c.isspace())
    return simbolos / len(texto)


def linea_mas_larga(texto: str) -> int:
    """Longitud de la linea mas larga (los empaquetadores suelen usar una sola)."""
    return max((len(linea) for linea in texto.splitlines()), default=0)


def analizar_entropia(texto: str, origen: str = "") -> List[Hallazgo]:
    """Heuristica contra cargas *desconocidas* empaquetadas u ofuscadas.

    No depende de los IOC conocidos: mide la *forma* del codigo (entropia alta,
    una linea gigantesca, exceso de simbolos). Asi el sistema sigue protegiendo
    aunque el atacante cambie de dominio o de cartera C2. Solo salta en textos
    largos y legibles, por lo que no confunde binarios ni codigo normal.
    """
    if len(texto) < UMBRAL_LARGO_TEXTO:
        return []
    if ratio_imprimible(texto) < UMBRAL_IMPRIMIBLE:
        return []  # binario o ilegible: no es el vector de este ataque
    entropia = entropia_shannon(texto)
    linea_max = linea_mas_larga(texto)
    simbolos = ratio_simbolos(texto)
    alta_entropia = entropia >= UMBRAL_ENTROPIA
    linea_sospechosa = linea_max >= UMBRAL_LINEA_LARGA and simbolos >= UMBRAL_SIMBOLOS
    if not (alta_entropia or linea_sospechosa):
        return []
    severidad = ALTA if alta_entropia else MEDIA
    return [Hallazgo(
        id="heur.entropia", severidad=severidad,
        descripcion=(
            "posible carga empaquetada u ofuscada "
            f"(entropia {entropia:.2f} b/c, linea max. {linea_max}, simbolos {simbolos:.0%})"
        ),
        origen=origen, linea=0,
        fragmento=_recortar(texto[:LARGO_FRAGMENTO]),
    )]


def analizar_fichero(ruta: Path, limite: int = LIMITE_BYTES) -> List[Hallazgo]:
    """Analiza un fichero: contenido + camuflaje por extension y por nombre."""
    ruta = Path(ruta)
    try:
        if not ruta.is_file() or ruta.stat().st_size > limite:
            return []
        datos = ruta.read_bytes()
    except OSError:
        return []
    if b"\x00" in datos[:4096]:
        return []  # binario: no es el vector de este ataque
    texto = datos.decode("utf-8", errors="replace")
    hallazgos = analizar_texto(texto, origen=str(ruta))
    hallazgos.extend(analizar_entropia(texto, origen=str(ruta)))

    sufijo = ruta.suffix.lower()
    if sufijo in iocs.EXTENSIONES_ANOMALAS and parece_javascript(texto):
        hallazgos.append(Hallazgo(
            id="js.camuflaje", severidad=ALTA,
            descripcion=f"JavaScript camuflado dentro de un fichero '{sufijo}'",
            origen=str(ruta), linea=1,
            fragmento=_recortar(texto[:LARGO_FRAGMENTO]),
        ))
    if ruta.name.lower() in iocs.NOMBRES_CAMUFLAJE:
        hallazgos.append(Hallazgo(
            id="js.nombre_camuflaje", severidad=BAJA,
            descripcion="nombre de fichero usado como camuflaje por el ataque",
            origen=str(ruta), linea=0, fragmento=ruta.name,
        ))
    return hallazgos


def analizar_comando(argv: Sequence[str]) -> List[Hallazgo]:
    """Analiza una linea de comandos buscando ejecucion de codigo remoto."""
    linea = " ".join(str(parte) for parte in argv)
    hallazgos: List[Hallazgo] = []
    for id_, regex, descripcion in iocs.REGEX_COMANDO:
        coincidencia = regex.search(linea)
        if coincidencia is not None:
            hallazgos.append(Hallazgo(
                id=id_, severidad=_SEVERIDAD_COMANDO.get(id_, MEDIA),
                descripcion=descripcion, origen="comando", linea=0,
                fragmento=_recortar(linea),
            ))
    return hallazgos


def es_escaneable(ruta: Path) -> bool:
    """Decide si merece la pena abrir un fichero en un barrido de arbol."""
    if ruta.name.lower() in iocs.NOMBRES_CAMUFLAJE:
        return True
    return ruta.suffix.lower() in EXTENSIONES_TEXTO


def escanear_arbol(
    raices: Iterable[Path],
    ignorar: Iterable[Path] = (),
    limite_ficheros: int = 20000,
) -> List[Hallazgo]:
    """Recorre uno o varios arboles y analiza los ficheros relevantes.

    Se autoexcluye el propio paquete STM_DEF (contiene muestras de los IOC en
    sus pruebas y no debe delatarse a si mismo) y respeta la allowlist de
    ``rutas_ignoradas.txt`` (fixtures y documentacion del ataque).
    """
    from . import STM_DEF_DIR

    excluidos = [Path(p).resolve() for p in ignorar]
    excluidos.append(STM_DEF_DIR.resolve())
    excluidos.extend(rutas_ignoradas())
    hallazgos: List[Hallazgo] = []
    vistos = 0
    for raiz in raices:
        raiz = Path(raiz)
        if raiz.is_file():
            if es_escaneable(raiz):
                hallazgos.extend(analizar_fichero(raiz))
            continue
        if not raiz.is_dir():
            continue
        for ruta in raiz.rglob("*"):
            if ruta.is_dir():
                continue
            if any(parte in DIRS_IGNORADOS for parte in ruta.parts):
                continue
            resuelto = ruta.resolve()
            if any(resuelto == exc or exc in resuelto.parents for exc in excluidos):
                continue
            if not es_escaneable(ruta):
                continue
            vistos += 1
            if vistos > limite_ficheros:
                return hallazgos
            hallazgos.extend(analizar_fichero(ruta))
    return hallazgos


def resumen(hallazgos: List[Hallazgo]) -> Dict[str, object]:
    """Cuenta hallazgos por severidad y calcula el veredicto."""
    por_severidad: Dict[str, int] = {}
    for hallazgo in hallazgos:
        por_severidad[hallazgo.severidad] = por_severidad.get(hallazgo.severidad, 0) + 1
    puntos = puntuar(hallazgos)
    return {
        "total": len(hallazgos),
        "por_severidad": por_severidad,
        "puntos": puntos,
        "veredicto": clasificar(puntos),
    }


def es_comprometido(hallazgos: List[Hallazgo]) -> bool:
    """True si la puntuacion alcanza al menos severidad MEDIA."""
    return clasificar(puntuar(hallazgos)) in (ALTA, MEDIA)


__all__ = [
    "analizar_texto", "analizar_fichero", "analizar_comando", "escanear_arbol",
    "es_escaneable", "parece_javascript", "resumen", "es_comprometido",
    "rutas_ignoradas", "entradas_allowlist", "allowlist_obsoleta",
    "hallazgos_allowlist", "entropia_shannon", "ratio_imprimible", "ratio_simbolos",
    "linea_mas_larga", "analizar_entropia",
    "LIMITE_BYTES", "DIRS_IGNORADOS", "EXTENSIONES_TEXTO",
    "ALLOWLIST_PATH", "IGNORADOS_POR_DEFECTO", "EXTENSIONES_EJECUTABLES",
]
