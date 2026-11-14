"""Interpretación de órdenes de LucIA (STM_MD2).

Convierte texto etiquetado, JSON o dict en la orden normalizada que ejecuta
``LC_constructor``: comando, ruta, nombre y subcarpetas. No crea carpetas ni
carga la red neuronal: es la mitad «parser» del constructor.

Las rutas predeterminadas se inyectan desde el consumidor
(``LC_constructor``) para que respeten ``runtime.lc_trabajando``; sin
inyección se usan cadenas vacías y el destino lo decide quien ejecuta.

La clase anidada ``InterpreteOrden.Campos`` reúne las funciones de extracción
y de alias para no repetirlas en el consumidor.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Comandos y valores predeterminados
# ---------------------------------------------------------------------------

COMANDO_CARPETA = "crear carpeta"
COMANDO_RED = "crear red neuronal"
COMANDO_MTBGT = "crear mtbgt"
COMANDO_TODO = "crear todo"

COMANDOS: tuple[str, ...] = (
    COMANDO_CARPETA, COMANDO_RED, COMANDO_MTBGT, COMANDO_TODO,
)

#: Nombre que usa el comando cuando no se indica.
NOMBRE_PREDETERMINADO = "src"

#: Segunda acción: ``LCtrabajando/src/LC_STM/RedNeuronal`` y sus familias.
NOMBRE_RED_PREDETERMINADO = "RedNeuronal"
SUBCARPETAS_RED: tuple[str, ...] = (
    "CELEBRO", "ENRN", "RF_EN", "RF_SL", "RNP", "SLRN",
)

#: Tercera acción: ``LCtrabajando/src/MTBGT`` solo con carpetas por ahora.
NOMBRE_MTBGT_PREDETERMINADO = "MTBGT"
SUBCARPETAS_MTBGT: tuple[str, ...] = (
    ".godot", "addons", "AreaDeTrabajo", "gdscrip", "gdshader", "scene",
)

#: Nombre y subcarpetas por comando. La ruta se inyecta aparte.
_DEFAULTS: dict[str, tuple[str, tuple[str, ...] | None]] = {
    COMANDO_CARPETA: (NOMBRE_PREDETERMINADO, None),
    COMANDO_RED: (NOMBRE_RED_PREDETERMINADO, SUBCARPETAS_RED),
    COMANDO_MTBGT: (NOMBRE_MTBGT_PREDETERMINADO, SUBCARPETAS_MTBGT),
    COMANDO_TODO: (NOMBRE_PREDETERMINADO, None),
}


class InterpreteOrden:
    """Normaliza órdenes de LucIA recibidas como texto, JSON o dict.

    Parameters
    ----------
    rutas : Mapping[str, str], opcional
        Ruta predeterminada de cada comando (``COMANDO_CARPETA``, ...).
        Se lee en cada llamada, de modo que el consumidor puede cambiar su
        configuración sin recrear el intérprete.
    """

    class Campos:
        """Extracción de campos y normalización de alias."""

        #: Campos etiquetados de las órdenes en texto.
        PATRONES: tuple[tuple[str, re.Pattern[str]], ...] = (
            ("ruta", re.compile(
                r"(?i)(?:^|[\s,;])(?:ruta)\s*"
                r"(?:donde\s+crear|de\s+creaci[oó]n)?\s*[:=]\s*")),
            ("nombre", re.compile(
                r"(?i)(?:^|[\s,;])(?:nombre)\s*"
                r"(?:de\s+la\s+carpeta|de\s+carpeta)?\s*[:=]\s*")),
            ("subcarpetas", re.compile(
                r"(?i)(?:^|[\s,;])(?:subcarpetas?|jerarqu[ií]a)\s*[:=]\s*")),
        )

        #: Prefijo que identifica el comando al inicio del texto.
        PREFIJO_COMANDO = re.compile(
            r"(?is)^\s*(?:comando\s+)?"
            r"(crear\s+mtbgt|mtbgt|crear\s+godot|godot"
            r"|crear\s+todo|todo|crear\s+secuencia|secuencia"
            r"|crear\s+red\s+neuronal|red\s+neuronal|red_neuronal|red"
            r"|crear\s+carpeta|crear_carpeta)\b"
        )

        @staticmethod
        def dividir_subcarpetas(valor: str) -> tuple[str, ...]:
            """Separa nombres por comas, punto y coma, barras o saltos."""
            partes = re.split(r"[,;|\n]+", valor)
            return tuple(parte.strip().strip("\"'")
                         for parte in partes if parte.strip())

        @classmethod
        def normalizar_subcarpetas(cls, valor: Any) -> tuple[str, ...] | None:
            """Convierte ``subcarpetas`` a una tupla de nombres limpios."""
            if valor is None:
                return None
            if isinstance(valor, str):
                return cls.dividir_subcarpetas(valor)
            if isinstance(valor, Iterable):
                return tuple(str(item).strip().strip("\"'")
                             for item in valor if str(item).strip())
            return None

        @classmethod
        def extraer(cls, texto: str) -> dict[str, str]:
            """Extrae los campos etiquetados aunque vengan en una línea."""
            marcas: list[tuple[int, int, str]] = []
            for campo, patron in cls.PATRONES:
                for coincidencia in patron.finditer(texto):
                    marcas.append(
                        (coincidencia.start(), coincidencia.end(), campo))
            marcas.sort(key=lambda marca: marca[0])
            campos: dict[str, str] = {}
            for indice, (_inicio, fin, campo) in enumerate(marcas):
                siguiente = len(texto)
                for inicio_siguiente, _fin, _otro in marcas[indice + 1:]:
                    if inicio_siguiente >= fin:
                        siguiente = inicio_siguiente
                        break
                valor = texto[fin:siguiente].strip().strip("\"'").strip()
                if valor and campo not in campos:
                    campos[campo] = valor
            return campos

        @staticmethod
        def normalizar_comando(comando: Any) -> str:
            """Unifica los alias (``red``, ``red_neuronal``, ...)."""
            limpio = re.sub(r"(?i)^\s*comando\s+", "",
                            str(comando).strip().lower())
            limpio = re.sub(r"\s+", " ",
                            limpio.replace("_", " ")).strip()
            if limpio in ("red", "red neuronal", "crear red", COMANDO_RED):
                return COMANDO_RED
            if limpio in ("mtbgt", "crear mtbgt", "godot", "crear godot",
                          COMANDO_MTBGT):
                return COMANDO_MTBGT
            if limpio in ("todo", "crear todo", "secuencia", "crear secuencia",
                          COMANDO_TODO):
                return COMANDO_TODO
            if limpio in ("src", "crear src", COMANDO_CARPETA):
                return COMANDO_CARPETA
            return limpio

    def __init__(self, rutas: Mapping[str, str] | None = None) -> None:
        self.rutas: dict[str, str] = dict(rutas or {})

    # -- resolución de valores predeterminados ----------------------------
    def predeterminados(
        self, comando: str,
    ) -> tuple[str, str, tuple[str, ...] | None]:
        """Ruta, nombre y subcarpetas predeterminadas de cada acción."""
        nombre, subcarpetas = _DEFAULTS.get(
            comando, _DEFAULTS[COMANDO_CARPETA])
        return self.rutas.get(comando, ""), nombre, subcarpetas

    def comando_de_texto(self, texto: str) -> str:
        """Comando indicado al principio del texto (por defecto ``carpeta``)."""
        coincidencia = self.Campos.PREFIJO_COMANDO.match(texto)
        if coincidencia is None:
            return COMANDO_CARPETA
        return self.Campos.normalizar_comando(coincidencia.group(1))

    @staticmethod
    def error(mensaje: str) -> dict[str, Any]:
        """Estructura de error común al interpretar una orden."""
        return {"comando": COMANDO_CARPETA, "ruta": "", "nombre": "",
                "subcarpetas": None, "error": mensaje}

    # -- normalización ----------------------------------------------------
    def normalizar_orden(self, datos: Mapping[str, Any]) -> dict[str, Any]:
        """Normaliza una orden recibida como diccionario."""
        comando = self.Campos.normalizar_comando(
            datos.get("comando") or datos.get("accion")
            or datos.get("orden") or COMANDO_CARPETA)
        ruta_def, nombre_def, sub_def = self.predeterminados(comando)
        ruta = (datos.get("ruta") or datos.get("ruta_donde_crear")
                or datos.get("ruta_crear") or datos.get("path") or ruta_def)
        nombre = (datos.get("nombre") or datos.get("nombre_carpeta")
                  or datos.get("nombre_de_la_carpeta") or datos.get("carpeta")
                  or nombre_def)
        subcarpetas = self.Campos.normalizar_subcarpetas(
            datos.get("subcarpetas") or datos.get("jerarquia")
            or datos.get("carpetas"))
        if subcarpetas is None and sub_def is not None:
            subcarpetas = sub_def
        return {
            "comando": comando,
            "ruta": str(ruta).strip().strip("\"'"),
            "nombre": str(nombre).strip().strip("\"'"),
            "subcarpetas": subcarpetas,
        }

    def interpretar(self, orden: str | Mapping[str, Any]) -> dict[str, Any]:
        """Convierte texto, JSON o dict en una orden normalizada.

        Acepta ``Ruta donde crear:`` y ``Nombre de la carpeta:`` en una o
        varias líneas, además de la forma corta ``crear carpeta <ruta> [nombre]``.
        """
        if isinstance(orden, Mapping):
            return self.normalizar_orden(orden)
        texto = str(orden or "").strip()
        if not texto:
            return self.error("Orden vacía: no hay comando que ejecutar.")
        if texto.startswith("{"):
            try:
                datos = json.loads(texto)
            except json.JSONDecodeError as error:
                return self.error(f"JSON no válido: {error}")
            if not isinstance(datos, Mapping):
                return self.error("El JSON de la orden debe ser un objeto.")
            return self.normalizar_orden(datos)

        comando = self.comando_de_texto(texto)
        ruta_def, nombre_def, sub_def = self.predeterminados(comando)
        campos = self.Campos.extraer(texto)
        if campos:
            if (comando == COMANDO_CARPETA
                    and self.Campos.PREFIJO_COMANDO.match(texto) is None):
                nombre_clave = str(campos.get("nombre", "")).strip().lower()
                ruta_clave = Path(str(campos.get("ruta", ""))).name.lower()
                if nombre_clave == NOMBRE_RED_PREDETERMINADO.lower():
                    comando = COMANDO_RED
                elif (nombre_clave == NOMBRE_MTBGT_PREDETERMINADO.lower()
                      or ruta_clave == NOMBRE_MTBGT_PREDETERMINADO.lower()):
                    comando = COMANDO_MTBGT
                if comando != COMANDO_CARPETA:
                    ruta_def, nombre_def, sub_def = self.predeterminados(
                        comando)
            return {
                "comando": comando,
                "ruta": (campos.get("ruta") or ruta_def).strip().strip("\"'"),
                "nombre": (campos.get("nombre")
                           or nombre_def).strip().strip("\"'"),
                "subcarpetas": (
                    self.Campos.normalizar_subcarpetas(
                        campos.get("subcarpetas")) or sub_def),
            }

        coincidencia = self.Campos.PREFIJO_COMANDO.match(texto)
        if coincidencia is None:
            return self.error(
                "No reconozco la orden. Usa 'crear carpeta' o "
                "'crear red neuronal' con 'Ruta donde crear:' y "
                "'Nombre de la carpeta:'.")
        resto = texto[coincidencia.end():].strip()
        if not resto:
            return {"comando": comando, "ruta": ruta_def,
                    "nombre": nombre_def, "subcarpetas": sub_def}
        try:
            partes = shlex.split(resto, posix=False)
        except ValueError:
            partes = resto.split()
        ruta = partes[0].strip().strip("\"'") if partes else ruta_def
        nombre = (partes[1].strip().strip("\"'")
                  if len(partes) > 1 else nombre_def)
        return {"comando": comando, "ruta": ruta, "nombre": nombre,
                "subcarpetas": sub_def}

    def __call__(self, orden: str | Mapping[str, Any]) -> dict[str, Any]:
        """Permite usar la instancia como función."""
        return self.interpretar(orden)


def interpretar_orden(
    orden: str | Mapping[str, Any],
    rutas: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Atajo: normaliza una orden con las rutas indicadas.

    ``LC_constructor`` pasa sus rutas actuales para que el resultado respete
    ``runtime.lc_trabajando``; sin ``rutas`` el destino queda vacío.
    """
    return InterpreteOrden(rutas).interpretar(orden)


__all__ = [
    "COMANDOS",
    "COMANDO_CARPETA",
    "COMANDO_MTBGT",
    "COMANDO_RED",
    "COMANDO_TODO",
    "NOMBRE_MTBGT_PREDETERMINADO",
    "NOMBRE_PREDETERMINADO",
    "NOMBRE_RED_PREDETERMINADO",
    "SUBCARPETAS_MTBGT",
    "SUBCARPETAS_RED",
    "InterpreteOrden",
    "interpretar_orden",
]
