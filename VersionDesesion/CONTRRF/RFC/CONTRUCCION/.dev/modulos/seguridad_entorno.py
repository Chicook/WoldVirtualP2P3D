"""Módulo de Seguridad y Contención del Entorno (.dev/modulos/seguridad_entorno.py)
WoldVirtualP2P3D · Arquitectura de Aislamiento Local y Zero Trust de Entorno.

Proporciona:
- ValidadorFronteraSegura: Garantiza contención estricta dentro de REPO_ROOT (E:\\WoldVirtualP2P3D).
- GestorVenvSeguro: Control de integridad del intérprete local (.dev/.python y .dev/venv).
- Decoradores de seguridad operacional:
    * @asegurar_frontera: Intercepta llamadas y aborta cualquier path traversal o escape.
    * @requiere_venv_activo: Valida que la ejecución use intérpretes contenidos en .dev.
    * @auditar_operacion_entorno: Registra telemetría y auditoría en .dev/.auditoria_entorno.log.
"""
from __future__ import annotations

import functools
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from .rutas import (
    DEV_DIR,
    PYTHON_EXE,
    REPO_ROOT,
    VENV_DIR,
    VENV_PYTHON,
    asegurar_ruta_en_repositorio,
    validar_frontera_carpetas,
)

F = TypeVar("F", bound=Callable[..., Any])

ARCHIVO_AUDITORIA_ENTORNO: Path = DEV_DIR / ".auditoria_entorno.log"


class ValidadorFronteraSegura:
    """Validador singleton que garantiza la estricta contención de todas las
    operaciones de archivos, rutas y procesos dentro del árbol de directorios de WoldVirtualP2P3D."""

    _instancia: Optional["ValidadorFronteraSegura"] = None

    def __new__(cls) -> "ValidadorFronteraSegura":
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
            cls._instancia._inicializado = False
        return cls._instancia

    def __init__(self) -> None:
        if getattr(self, "_inicializado", False):
            return
        self.raiz_canonica: Path = REPO_ROOT.resolve()
        self.dev_canonico: Path = DEV_DIR.resolve()
        self._inicializado = True

    def verificar_ruta(self, ruta: Path | str) -> bool:
        """Verifica si la ruta provista se ubica de forma segura dentro de la raíz."""
        return asegurar_ruta_en_repositorio(ruta)

    def exigir_frontera(self, ruta: Path | str, descripcion: str = "Ruta") -> Path:
        """Valida la ruta y lanza PermissionError si intenta escapar de la frontera canónica."""
        p = Path(ruta).resolve()
        if not self.verificar_ruta(p):
            mensaje = (
                f"[VIOLACIÓN DE FRONTERA] {descripcion} intenta escapar de la raíz canónica: "
                f"'{p}' no está contenida en '{self.raiz_canonica}'"
            )
            self._registrar_alerta_seguridad(mensaje)
            raise PermissionError(mensaje)
        return p

    def auditar_todo_el_arbol(self) -> Tuple[bool, List[str]]:
        """Realiza un escaneo integral de los directorios clave del sistema."""
        return validar_frontera_carpetas()

    def _registrar_alerta_seguridad(self, mensaje: str) -> None:
        """Registra un evento de advertencia o infracción de frontera en el log de auditoría."""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            linea = f"[{timestamp}] [ALERTA_SEGURIDAD_FRONTERA] {mensaje}\n"
            with open(ARCHIVO_AUDITORIA_ENTORNO, "a", encoding="utf-8") as f:
                f.write(linea)
        except Exception:
            pass


class GestorVenvSeguro:
    """Administra y valida los entornos virtuales e intérpretes de Python aislados dentro de .dev."""

    @staticmethod
    def obtener_interprete_seguro(estricto: bool = False) -> Path:
        """Devuelve el intérprete canónico preferido ubicado dentro de .dev (.dev/venv o .dev/.python).
        Si estricto=True, lanza RuntimeError si no se encuentra un intérprete contenido en .dev."""
        if VENV_PYTHON.is_file():
            return VENV_PYTHON
        if PYTHON_EXE.is_file():
            return PYTHON_EXE
        if estricto:
            raise RuntimeError(
                f"[VIOLACIÓN DE AISLAMIENTO ZERO TRUST] No se localizó un intérprete de Python contenido en .dev "
                f"({VENV_PYTHON} o {PYTHON_EXE}). Ejecución bloqueada por política de aislamiento estricto."
            )
        return Path(sys.executable)

    @staticmethod
    def es_interprete_contenido(interprete: Optional[Path | str] = None) -> bool:
        """Verifica si el intérprete en uso o provisto reside estrictamente dentro de .dev."""
        path_interp = Path(interprete or sys.executable).resolve()
        dev_res = DEV_DIR.resolve()
        return dev_res in path_interp.parents

    @staticmethod
    def verificar_integridad_entorno() -> Dict[str, Any]:
        """Diagnóstico de contención y aislamiento del entorno Python."""
        interp_activo = Path(sys.executable).resolve()
        es_contenido = GestorVenvSeguro.es_interprete_contenido(interp_activo)
        tiene_venv = VENV_PYTHON.is_file()
        tiene_python_embebido = PYTHON_EXE.is_file()

        return {
            "interprete_activo": str(interp_activo),
            "es_contenido_en_dev": es_contenido,
            "tiene_venv": tiene_venv,
            "tiene_python_embebido": tiene_python_embebido,
            "interprete_sugerido": str(GestorVenvSeguro.obtener_interprete_seguro()),
        }


def asegurar_frontera(func: F) -> F:
    """Decorador que inspecciona exhaustivamente los argumentos posicionales y nombrados de tipo Path o str.
    Garantiza que ninguna ruta escape fuera de REPO_ROOT ni mediante path traversal.
    NUNCA suprime excepciones de validación de frontera."""
    validador = ValidadorFronteraSegura()

    def _inspeccionar(valor: Any, desc: str) -> None:
        if isinstance(valor, Path):
            validador.exigir_frontera(valor, desc)
        elif isinstance(valor, str):
            # Filtrar cadenas vacías o textos largos no relacionados con rutas
            if not valor or "\n" in valor or "\r" in valor or len(valor) > 1024:
                return
            # Si contiene separadores, traversal o indicadores de ruta
            es_candidato_ruta = any(c in valor for c in ("\\", "/", ":", ".."))
            if es_candidato_ruta:
                try:
                    candidato = Path(valor)
                    # Si es relativa, resolverla contra REPO_ROOT para validar contención
                    if not candidato.is_absolute():
                        candidato = (REPO_ROOT / candidato).resolve()
                    validador.exigir_frontera(candidato, desc)
                except PermissionError:
                    # NUNCA suprimir violaciones de frontera de seguridad
                    raise
                except (ValueError, OSError):
                    # Ignorar cadenas no interpretables como rutas sintácticas
                    pass
        elif isinstance(valor, (list, tuple)):
            for i, elem in enumerate(valor):
                _inspeccionar(elem, f"{desc}[{i}]")
        elif isinstance(valor, dict):
            for k, elem in valor.items():
                _inspeccionar(elem, f"{desc}['{k}']")

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Inspeccionar todos los argumentos posicionales
        for idx, arg in enumerate(args):
            _inspeccionar(arg, f"Parámetro {idx} en '{func.__name__}'")

        # Inspeccionar todos los argumentos nombrados (kwargs)
        for k, v in kwargs.items():
            _inspeccionar(v, f"Parámetro kwarg '{k}' en '{func.__name__}'")

        resultado = func(*args, **kwargs)

        # Si el resultado es un Path o str de ruta, validarlo también
        if isinstance(resultado, Path):
            validador.exigir_frontera(resultado, f"Resultado Path devuelto por '{func.__name__}'")
        elif isinstance(resultado, str) and any(c in resultado for c in ("\\", "/", "..")):
            _inspeccionar(resultado, f"Resultado str devuelto por '{func.__name__}'")

        return resultado

    return wrapper  # type: ignore[return-value]


def requiere_venv_activo(advertir_solo: bool = True) -> Callable[[F], F]:
    """Decorador que verifica que la función se ejecute dentro del entorno aislado de .dev."""
    def decorador(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            es_seguro = GestorVenvSeguro.es_interprete_contenido()
            if not es_seguro:
                msg = (
                    f"[AVISO_ENTORNO] '{func.__name__}' ejecutada fuera del entorno .dev "
                    f"(Intérprete: {sys.executable}). Intérprete recomendado: {GestorVenvSeguro.obtener_interprete_seguro()}"
                )
                if advertir_solo:
                    print(msg, file=sys.stderr)
                else:
                    raise RuntimeError(msg)
            return func(*args, **kwargs)
        return wrapper  # type: ignore[return-value]
    return decorador


def auditar_operacion_entorno(nombre_operacion: Optional[str] = None) -> Callable[[F], F]:
    """Decorador que registra el inicio, fin, duración y resultado de cualquier operación crítica en .dev."""
    def decorador(func: F) -> F:
        op_nombre = nombre_operacion or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            t_inicio_iso = datetime.now(timezone.utc).isoformat()
            excepcion_ocurrida: Optional[Exception] = None
            resultado = None

            try:
                resultado = func(*args, **kwargs)
                return resultado
            except Exception as ex:
                excepcion_ocurrida = ex
                raise
            finally:
                duracion_ms = (time.perf_counter() - t0) * 1000.0
                estado = "FALLO" if excepcion_ocurrida else "EXITO"
                detalle_error = f" | Error: {excepcion_ocurrida}" if excepcion_ocurrida else ""
                log_entry = (
                    f"[{t_inicio_iso}] [AUDITORIA] Op='{op_nombre}' Estado={estado} "
                    f"Duracion={duracion_ms:.2f}ms{detalle_error}\n"
                )
                try:
                    with open(ARCHIVO_AUDITORIA_ENTORNO, "a", encoding="utf-8") as f:
                        f.write(log_entry)
                except Exception:
                    pass

        return wrapper  # type: ignore[return-value]
    return decorador
