r"""LC_constructor — primer comando automático de LucIA (``crear carpeta``).

Recibe de la máquina de comandos una orden como::

    Ruta donde crear: E:\...\LCtrabajando
    Nombre de la carpeta: src

y la ejecuta pasando por la red neuronal completa de ``LCBS_NEURONAL``
(ENRN -> RF_EN y salud de las familias) y por la fachada ``RFPRMN.py``.
Acepta texto etiquetado (una o varias líneas), dict o JSON; la CLI responde
en texto legible, no en JSON.

Acciones disponibles:
- ``crear todo``          : ejecuta las tres siguientes en secuencia (explícito).
- ``crear carpeta``       : ``LCtrabajando/src`` con **toda** la jerarquía de
  carpetas detectada en ``TLLDCD/src`` (solo carpetas, sin archivos).  Es la
  acción por defecto de la CLI cuando no se pasan argumentos.
- ``crear red neuronal``  : ``LCtrabajando/src/LC_STM/RedNeuronal`` y sus
  6 familias.  Se invoca con ``python LC_constructor.py red``.
- ``crear mtbgt``         : ``LCtrabajando/src/MTBGT`` con sus carpetas;
  los archivos quedan para una fase posterior.  Se invoca con
  ``python LC_constructor.py mtbgt``.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

__version__ = "0.9.1"

_DIR_MODULO = Path(__file__).resolve().parent
if str(_DIR_MODULO) not in sys.path:
    sys.path.insert(0, str(_DIR_MODULO))

import RFPRMN as _RFPRMN  # noqa: E402
from STM_LC_CONSTRUCTOR_MD import (  # noqa: E402
    COMANDO_CARPETA,
    COMANDO_MTBGT,
    COMANDO_RED,
    COMANDO_TODO,
    DIM_ENTRADA,
    DIM_SALIDA,
    NOMBRE_MTBGT_PREDETERMINADO,
    NOMBRE_PREDETERMINADO,
    NOMBRE_RED_PREDETERMINADO,
    SUBCARPETAS_MTBGT,
    SUBCARPETAS_RED,
    SUBCARPETAS_SRC,
    SUBCARPETAS_SRC_BASE,
    InterpreteOrden,
    cargar_lcbs_neuronal,
    cargar_modulo_red,
    crear_jerarquia,
    descubrir_jerarquia_src,
    descubrir_subcarpetas_src,
    localizar_lcbs_neuronal,
    localizar_red_neuronal,
    obtener_clase_constructiva,
    silencio,
)
from STM_LC_CONSTRUCTOR_MD import (  # noqa: E402
    RUTA_FUENTE_PREDETERMINADA as _RUTA_FUENTE_MD1,
)
from STM_LC_CONSTRUCTOR_MD import (  # noqa: E402
    interpretar_orden as _interpretar_orden,
)

RFPRMN = _RFPRMN.RFPRMN


def _resolver_contrrf() -> Path:
    """Localiza ``CONTRRF`` a partir del módulo o del entorno."""
    entorno = os.environ.get("LC_CONTRRF", "").strip()
    if entorno:
        candidata = Path(entorno).expanduser()
        if (candidata / "CONTRUCCION").is_dir():
            return candidata
    for base in (_DIR_MODULO, *_DIR_MODULO.parents):
        for relativa in (Path("CONTRRF"),
                         Path("VersionDe_sesion") / "CONTRRF"):
            candidata = base / relativa
            if (candidata / "CONTRUCCION").is_dir():
                return candidata
    return _DIR_MODULO.parents[1]


def _resolver_ruta_trabajo() -> Path:
    """Directorio de salida: ``CONTRRF/CONTRUCCION/LCtrabajando``."""
    entorno = os.environ.get("LC_TRABAJO", "").strip()
    if entorno:
        return Path(entorno).expanduser()
    return _resolver_contrrf() / "CONTRUCCION" / "LCtrabajando"


_RUTA_TRABAJO = _resolver_ruta_trabajo()

#: Ruta que usa el comando cuando no se indica. El nombre y las subcarpetas
#: viven en ``STM_MD2`` junto al resto de valores por comando.
RUTA_PREDETERMINADA = str(_RUTA_TRABAJO)

#: Segunda acción: ``LCtrabajando/src/LC_STM/RedNeuronal`` y sus familias.
RUTA_RED_PREDETERMINADA = str(_RUTA_TRABAJO / "src" / "LC_STM")

#: Tercera acción: ``LCtrabajando/src/MTBGT`` solo con carpetas por ahora.
RUTA_MTBGT_PREDETERMINADA = str(_RUTA_TRABAJO / "src" / "MTBGT")
#: Sin archivos de momento: el ``project.godot`` queda para una fase posterior.
ARCHIVOS_MTBGT: tuple[str, ...] = ()

#: Modo limpio: crea solo carpetas, pero conserva el cálculo de LCBS_NEURONAL.
#: Poner False solo si se quiere evitar por completo la carga de la red.
USAR_RED_NEURONAL = True

#: Fuente oficial de la estructura de carpetas.
RUTA_FUENTE_PREDETERMINADA = str(_RUTA_FUENTE_MD1)


def _rutas_predeterminadas() -> dict[str, str]:
    """Rutas actuales de cada comando (respetan ``runtime.lc_trabajando``)."""
    return {
        COMANDO_CARPETA: RUTA_PREDETERMINADA,
        COMANDO_RED: RUTA_RED_PREDETERMINADA,
        COMANDO_MTBGT: RUTA_MTBGT_PREDETERMINADA,
        COMANDO_TODO: RUTA_PREDETERMINADA,
    }


def interpretar_orden(orden: str | Mapping[str, Any]) -> dict[str, Any]:
    """Convierte texto, JSON o dict de la máquina en una orden normalizada.

    Delega en ``STM_MD2`` con las rutas actuales, de modo que respeta
    ``runtime.lc_trabajando`` sin duplicar las reglas del parser.
    """
    return _interpretar_orden(orden, _rutas_predeterminadas())


class ConstructorLucIA:
    """Ejecuta las órdenes de construcción de LucIA.

    ``maquina`` permite inyectar una fachada RFPRMN ya construida (pruebas).
    """

    COMANDOS = (COMANDO_CARPETA, COMANDO_RED, COMANDO_MTBGT, COMANDO_TODO)

    def __init__(self, ruta_red: str | Path | None = None,
                 maquina: Any | None = None) -> None:
        self.ruta_red = ruta_red
        self.rfprmn = maquina if maquina is not None else RFPRMN()
        self._red: Any | None = None

    # -- neuronas ---------------------------------------------------------
    def _crear_constructiva(self, ruta: Path, nombre: str,
                            subcarpetas: tuple[str, ...]) -> Any:
        """Instancia la neurona constructiva con la orden ya normalizada."""
        modulo = cargar_modulo_red(self.ruta_red)
        clase = obtener_clase_constructiva()
        neurona = modulo.NeuronaEntradaXavier(DIM_ENTRADA, DIM_SALIDA)
        creativa = modulo.NeuronaEntradaXavier.NeuronaCreativa(neurona)
        return clase(creativa, self.rfprmn, str(ruta), nombre, subcarpetas)

    def _metricas_red(self, constructiva: Any, texto: str, nombre: str,
                      subcarpetas: tuple[str, ...]) -> dict[str, Any]:
        """Calcula impulso, entropía y afinidades de la orden."""
        datos: dict[str, Any] = {
            "familia": "ENRN.EN2_RN", "neurona": "NeuronaEntradaXavier",
            "dim_entrada": DIM_ENTRADA, "dim_salida": DIM_SALIDA,
        }
        try:
            datos["impulso"] = round(float(constructiva.impulso_creativo()), 6)
            datos["entropia"] = round(float(constructiva.entropia(texto)), 6)
            similitudes = {
                sub: round(float(constructiva.similitud(nombre, sub)), 6)
                for sub in subcarpetas
            }
            datos["similitudes"] = similitudes
            if similitudes:
                datos["afinidad_maxima"] = max(similitudes.values())
        except Exception as error:  # noqa: BLE001 - métrica diagnóstica
            datos["error"] = f"{type(error).__name__}: {error}"
        return datos

    def _calcular_red_general(self, constructiva: Any,
                              texto: str) -> dict[str, Any]:
        """Pasa la orden por LCBS_NEURONAL: ENRN -> RF_EN + salud global."""
        vector = constructiva.vector(texto)
        datos: dict[str, Any] = {"modulo": "LCBS_NEURONAL"}
        try:
            modulo = cargar_lcbs_neuronal()
            with silencio():
                if self._red is None:
                    self._red = modulo.RedNeuronal(
                        input_size=int(vector.size), output_size=4,
                        latente_size=16, seed=2026)
                accion, diagnostico = self._red.procesar(vector, modo="xavier")
                salud = self._red.salud()
        except Exception as error:  # noqa: BLE001 - se reporta sin romper
            datos.update({"ok": False,
                          "error": f"{type(error).__name__}: {error}"})
            return datos
        datos.update({
            "ok": True,
            "version": getattr(modulo, "__version__", ""),
            "familias": list(getattr(modulo.RedNeuronal, "FAMILIAS", ())),
            "salud": {familia: bool(info.get("ok"))
                      for familia, info in salud.items()},
            "accion": [round(float(valor), 6) for valor in accion],
            "diagnostico": {clave: valor for clave, valor in diagnostico.items()
                            if isinstance(valor, (int, float, str, bool))},
        })
        return datos

    def _crear_solo_carpetas(self, base: Path, nombre: str,
                             subcarpetas: tuple[str, ...]) -> dict[str, Any]:
        """Crea la jerarquía sin red neuronal y resume los pasos por nivel."""
        resultado = crear_jerarquia(str(base), nombre, subcarpetas, self.rfprmn)
        if resultado.get("ok"):
            raiz = resultado["raiz"]
            niveles = list(dict.fromkeys(
                Path(sub).parts[0] for sub in subcarpetas if Path(sub).parts))
            resultado["pasos"] = [
                {"paso": 1, "carpeta": Path(raiz).name, "ruta": raiz},
                *({"paso": numero, "carpeta": nivel,
                   "ruta": str(Path(raiz) / nivel)}
                  for numero, nivel in enumerate(niveles, start=2)),
            ]
        return resultado

    # -- API pública ------------------------------------------------------
    def crear_carpeta(self, ruta: str | Path = "",
                      nombre: str = NOMBRE_PREDETERMINADO,
                      subcarpetas: Iterable[str] | None = None,
                      archivos: Iterable[str] | None = None) -> dict[str, Any]:
        """Crea ``ruta/nombre`` y, si es ``src``, su jerarquía completa.

        Sin ``ruta`` usa ``RUTA_PREDETERMINADA`` y sin ``nombre`` usa
        ``NOMBRE_PREDETERMINADO``.  Si ``subcarpetas`` es ``None`` y el nombre
        es ``src`` se usa ``SUBCARPETAS_SRC``, toda la jerarquía de carpetas de
        ``TLLDCD/src``; en otro caso sólo la raíz.
        ``archivos`` permite crear ficheros vacíos dentro de la raíz.
        """
        ruta_texto = str(ruta or "").strip().strip("\"'") or RUTA_PREDETERMINADA
        base = Path(os.path.expandvars(os.path.expanduser(ruta_texto))).resolve()
        nombre = str(nombre or NOMBRE_PREDETERMINADO).strip()
        if subcarpetas is None:
            subcarpetas = (
                descubrir_subcarpetas_src(RUTA_FUENTE_PREDETERMINADA)
                if nombre.lower() == NOMBRE_PREDETERMINADO else ())
        elif isinstance(subcarpetas, str):
            subcarpetas = InterpreteOrden.Campos.dividir_subcarpetas(subcarpetas)
        else:
            subcarpetas = tuple(str(s).strip() for s in subcarpetas
                                if str(s).strip())

        resultado = self._crear_solo_carpetas(base, nombre, subcarpetas)
        if USAR_RED_NEURONAL:
            try:
                # Para la red se usan los nombres de primer nivel: el cálculo
                # matemático no necesita recorrer 1200 rutas anidadas.
                subcarpetas_red = tuple(dict.fromkeys(
                    Path(s).parts[0] for s in subcarpetas if Path(s).parts))
                constructiva = self._crear_constructiva(
                    base, nombre, subcarpetas_red)
                texto_orden = " ".join((str(base), nombre, *subcarpetas_red))
                red_general = self._calcular_red_general(
                    constructiva, texto_orden)
                metricas = self._metricas_red(
                    constructiva, texto_orden, nombre, subcarpetas_red)
            except Exception as error:  # noqa: BLE001 - la creación ya ocurrió
                red_general = {"ok": False,
                               "error": f"{type(error).__name__}: {error}"}
                metricas = {}
        else:
            red_general = {"ok": True, "omitida": True,
                           "motivo": "modo solo carpetas (red desactivada)"}
            metricas = {}
        resultado.update({
            "comando": COMANDO_CARPETA,
            "ruta": str(base),
            "nombre": nombre,
            "subcarpetas": list(subcarpetas),
            "red_general": red_general,
            "neurona_entrada": metricas,
            "rfprmn": {"version": getattr(_RFPRMN, "__version__", "")},
        })
        archivos_creados: list[str] = []
        if archivos is not None and resultado.get("ok"):
            if isinstance(archivos, str):
                archivos = (archivos,)
            try:
                for nombre_archivo in archivos:
                    archivos_creados.append(
                        self.rfprmn.crear_archivo(resultado["raiz"],
                                                  str(nombre_archivo)))
            except Exception as error:  # noqa: BLE001 - resultado degradado
                resultado["ok"] = False
                resultado["error"] = f"{type(error).__name__}: {error}"
        resultado["archivos"] = archivos_creados
        if not red_general.get("ok"):
            resultado["advertencia"] = (
                "La red general no pudo calcular; la jerarquía se creó igualmente.")
        return resultado

    def crear_red_neuronal(
        self, ruta: str | Path = "",
        nombre: str = NOMBRE_RED_PREDETERMINADO,
        subcarpetas: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Segunda acción: crea ``LC_STM/RedNeuronal`` con sus seis familias."""
        resultado = self.crear_carpeta(
            ruta or RUTA_RED_PREDETERMINADA,
            nombre or NOMBRE_RED_PREDETERMINADO,
            SUBCARPETAS_RED if subcarpetas is None else subcarpetas)
        resultado["comando"] = COMANDO_RED
        return resultado

    def comando_crear_red_neuronal(
        self, ruta: str | Path = "",
        nombre: str = NOMBRE_RED_PREDETERMINADO,
        subcarpetas: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Alias de la segunda acción con sus valores predeterminados."""
        return self.crear_red_neuronal(ruta, nombre, subcarpetas)

    def crear_mtbgt(
        self, ruta: str | Path = "",
        subcarpetas: Iterable[str] | None = None,
        archivos: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Tercera acción: ``MTBGT`` con sus carpetas (sin archivos por ahora)."""
        ruta_texto = str(ruta or RUTA_MTBGT_PREDETERMINADA).strip().strip("\"'")
        root = Path(os.path.expandvars(
            os.path.expanduser(ruta_texto))).resolve()
        resultado = self.crear_carpeta(
            root.parent, root.name,
            SUBCARPETAS_MTBGT if subcarpetas is None else subcarpetas,
            ARCHIVOS_MTBGT if archivos is None else archivos)
        resultado["comando"] = COMANDO_MTBGT
        resultado["ruta_mtbgt"] = str(root)
        return resultado

    def comando_crear_mtbgt(
        self, ruta: str | Path = "",
        subcarpetas: Iterable[str] | None = None,
        archivos: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Alias de la tercera acción con sus valores predeterminados."""
        return self.crear_mtbgt(ruta, subcarpetas, archivos)

    def crear_todo(self) -> dict[str, Any]:
        """Secuencia completa: ``src``, ``RedNeuronal`` y ``MTBGT``."""
        src = self.crear_carpeta()
        red = self.crear_red_neuronal()
        mtbgt = self.crear_mtbgt()
        acciones = [src, red, mtbgt]
        return {
            "ok": all(accion.get("ok") for accion in acciones),
            "comando": COMANDO_TODO,
            "acciones": acciones,
            "total": sum(int(accion.get("total", 0)) for accion in acciones),
        }

    def comando_crear_todo(self) -> dict[str, Any]:
        """Alias de la secuencia completa."""
        return self.crear_todo()

    def comando_crear_carpeta(self, ruta: str | Path = "",
                              nombre: str = NOMBRE_PREDETERMINADO,
                              subcarpetas: Iterable[str] | None = None) -> dict[str, Any]:
        """Alias del comando con la ruta y el nombre predeterminados."""
        return self.crear_carpeta(ruta, nombre, subcarpetas)

    def ejecutar(self, orden: str | Mapping[str, Any]) -> dict[str, Any]:
        """Interpreta y ejecuta una orden completa de la máquina de comandos."""
        datos = interpretar_orden(orden)
        if datos.get("error"):
            return {"ok": False, "comando": datos.get("comando", "crear carpeta"),
                    "error": datos["error"]}
        comando = datos.get("comando", "crear carpeta")
        if comando not in self.COMANDOS:
            return {"ok": False, "comando": comando,
                    "error": f"Comando no soportado: {comando!r}. "
                             f"Disponibles: {', '.join(self.COMANDOS)}"}
        if comando == COMANDO_TODO:
            return self.crear_todo()
        if comando == COMANDO_MTBGT:
            return self.crear_mtbgt(
                datos.get("ruta") or RUTA_MTBGT_PREDETERMINADA,
                datos.get("subcarpetas"))
        if comando == COMANDO_RED:
            return self.crear_red_neuronal(
                datos.get("ruta") or RUTA_RED_PREDETERMINADA,
                datos.get("nombre") or NOMBRE_RED_PREDETERMINADO,
                datos.get("subcarpetas"))
        return self.crear_carpeta(datos.get("ruta") or RUTA_PREDETERMINADA,
                                  datos.get("nombre") or NOMBRE_PREDETERMINADO,
                                  datos.get("subcarpetas"))


_CONSTRUCTOR: ConstructorLucIA | None = None


def obtener_constructor() -> ConstructorLucIA:
    """Constructor compartido (carga perezosa de la red y de RFPRMN)."""
    global _CONSTRUCTOR
    if _CONSTRUCTOR is None:
        _CONSTRUCTOR = ConstructorLucIA()
    return _CONSTRUCTOR


def ejecutar_orden(orden: str | Mapping[str, Any]) -> dict[str, Any]:
    """Atajo: interpreta y ejecuta una orden con el constructor compartido."""
    return obtener_constructor().ejecutar(orden)


def crear_carpeta(ruta: str | Path = "",
                  nombre: str = NOMBRE_PREDETERMINADO,
                  subcarpetas: Iterable[str] | None = None) -> dict[str, Any]:
    """Atajo programático; sin ruta usa ``RUTA_PREDETERMINADA``."""
    return obtener_constructor().crear_carpeta(ruta, nombre, subcarpetas)


def comando_crear_carpeta(ruta: str | Path = "",
                          nombre: str = NOMBRE_PREDETERMINADO,
                          subcarpetas: Iterable[str] | None = None) -> dict[str, Any]:
    """Alias con la ruta y el nombre predeterminados."""
    return crear_carpeta(ruta, nombre, subcarpetas)


def crear_red_neuronal(ruta: str | Path = "",
                       nombre: str = NOMBRE_RED_PREDETERMINADO,
                       subcarpetas: Iterable[str] | None = None) -> dict[str, Any]:
    """Atajo de la segunda acción; sin ruta usa ``RUTA_RED_PREDETERMINADA``."""
    return obtener_constructor().crear_red_neuronal(ruta, nombre, subcarpetas)


def comando_crear_red_neuronal(
    ruta: str | Path = "", nombre: str = NOMBRE_RED_PREDETERMINADO,
    subcarpetas: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Alias de la segunda acción con sus valores predeterminados."""
    return crear_red_neuronal(ruta, nombre, subcarpetas)


def crear_mtbgt(ruta: str | Path = "",
                subcarpetas: Iterable[str] | None = None,
                archivos: Iterable[str] | None = None) -> dict[str, Any]:
    """Atajo de la tercera acción; crea ``MTBGT`` solo con carpetas."""
    return obtener_constructor().crear_mtbgt(ruta, subcarpetas, archivos)


def comando_crear_mtbgt(
    ruta: str | Path = "", subcarpetas: Iterable[str] | None = None,
    archivos: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Alias de la tercera acción con sus valores predeterminados."""
    return crear_mtbgt(ruta, subcarpetas, archivos)


def crear_todo() -> dict[str, Any]:
    """Ejecuta la secuencia completa: ``src``, ``RedNeuronal`` y ``MTBGT``."""
    return obtener_constructor().crear_todo()


def comando_crear_todo() -> dict[str, Any]:
    """Alias de la secuencia completa."""
    return crear_todo()


def formatear_resultado(resultado: Mapping[str, Any]) -> str:
    """Devuelve el informe de terminal (texto legible, sin JSON)."""
    acciones = resultado.get("acciones")
    if acciones:
        partes = [formatear_resultado(accion) for accion in acciones]
        estado = "OK" if resultado.get("ok") else "CON ERRORES"
        partes.append(
            f"Resultado global: {estado} · {resultado.get('total', 0)} carpetas")
        return "\n".join(partes)
    ancho = 74
    comando = resultado.get("comando", COMANDO_CARPETA)
    lineas = ["=" * ancho, f" LC_constructor · comando {comando}", "=" * ancho]
    if not resultado.get("ok"):
        lineas.append(f"ERROR: {resultado.get('error', 'desconocido')}")
        if resultado.get("ruta"):
            lineas.append(f"Ruta: {resultado['ruta']}")
        if resultado.get("nombre"):
            lineas.append(f"Carpeta: {resultado['nombre']}")
        lineas.append("=" * ancho)
        return "\n".join(lineas)
    red = resultado.get("red_general") or {}
    entrada = resultado.get("neurona_entrada") or {}
    diagnostico = red.get("diagnostico") or {}
    lineas.extend([
        f"Ruta           : {resultado.get('ruta_mtbgt') or resultado.get('ruta', '')}",
        f"Carpeta        : {resultado.get('nombre', '')}",
    ])
    if not red.get("omitida"):
        lineas.append(
            f"Red general    : LCBS_NEURONAL v{red.get('version', '?')}")
        salud = red.get("salud") or {}
        if salud:
            estados = " | ".join(
                f"{familia}={'OK' if ok else 'ERR'}"
                for familia, ok in salud.items())
            lineas.append(f"Familias       : {estados}")
        if red.get("ok"):
            lineas.extend([
                f"Modo           : {diagnostico.get('modo', '?')} "
                f"({diagnostico.get('neurona_enrn', '?')} -> "
                f"{diagnostico.get('neurona_rfen', '?')})",
                f"Accion         : {red.get('accion', [])}",
                f"Latencia       : {diagnostico.get('latencia_ms', 0):.3f} ms",
                f"Normas         : estado={diagnostico.get('norma_estado', 0):.4f} "
                f"latente={diagnostico.get('norma_latente', 0):.4f} "
                f"accion={diagnostico.get('norma_accion', 0):.4f}",
            ])
        else:
            lineas.append(f"Red general    : ERROR {red.get('error', '')}")
        if entrada:
            lineas.append(
                f"Neurona entrada: impulso={entrada.get('impulso', '?')} "
                f"entropia={entrada.get('entropia', '?')}")
    lineas.append(f"Jerarquia      : {resultado.get('total', 0)} carpetas")
    archivos = resultado.get("archivos") or []
    if archivos:
        lineas.append(
            "Archivos       : " + ", ".join(Path(a).name for a in archivos))
    for paso in resultado.get("pasos", []):
        lineas.append(f"  {paso.get('paso', '?'):>2}. {paso.get('carpeta', '')}")
    if resultado.get("advertencia"):
        lineas.append(f"AVISO          : {resultado['advertencia']}")
    estado = "OK" if red.get("ok") else "OK (creación; red general con error)"
    lineas.extend([f"Estado         : {estado}", "=" * ancho])
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI: por argumentos o con los valores predeterminados."""
    argumentos = list(sys.argv[1:] if argv is None else argv)
    pausa = "--pausa" in argumentos
    argumentos = [argumento for argumento in argumentos if argumento != "--pausa"]
    if argumentos:
        resultado = ejecutar_orden(" ".join(argumentos))
    else:
        resultado = crear_carpeta()
    print(formatear_resultado(resultado))
    if pausa or (not argumentos and sys.stdin.isatty()):
        try:
            input("\nPulsa Enter para cerrar...")
        except EOFError:
            pass
    return 0 if resultado.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ARCHIVOS_MTBGT",
    "COMANDO_CARPETA",
    "COMANDO_MTBGT",
    "COMANDO_RED",
    "COMANDO_TODO",
    "NOMBRE_MTBGT_PREDETERMINADO",
    "NOMBRE_PREDETERMINADO",
    "NOMBRE_RED_PREDETERMINADO",
    "RFPRMN",
    "RUTA_FUENTE_PREDETERMINADA",
    "RUTA_MTBGT_PREDETERMINADA",
    "RUTA_PREDETERMINADA",
    "RUTA_RED_PREDETERMINADA",
    "SUBCARPETAS_MTBGT",
    "SUBCARPETAS_RED",
    "SUBCARPETAS_SRC",
    "SUBCARPETAS_SRC_BASE",
    "USAR_RED_NEURONAL",
    "ConstructorLucIA",
    "__version__",
    "cargar_lcbs_neuronal",
    "cargar_modulo_red",
    "comando_crear_carpeta",
    "comando_crear_mtbgt",
    "comando_crear_red_neuronal",
    "comando_crear_todo",
    "crear_carpeta",
    "crear_mtbgt",
    "crear_red_neuronal",
    "crear_todo",
    "descubrir_jerarquia_src",
    "descubrir_subcarpetas_src",
    "ejecutar_orden",
    "formatear_resultado",
    "interpretar_orden",
    "localizar_lcbs_neuronal",
    "localizar_red_neuronal",
    "main",
    "obtener_constructor",
]
