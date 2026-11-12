"""Modulo autocontenido de creacion de codigo por seccion (SBTM_EN3_RN).

Unifica la subrutina NeuronaCodigo en una clase importable con clases anidadas:

- Matematica : codificacion LeCun (FNV-1a + bolsa de tokens fan_in), proyeccion
               forward, similitud coseno, impulso LeCun, entropia Shannon,
               afinidad lenguaje y divergencia KL entre proyecciones.
- Maquina    : carga perezosa de STM_RFPRMN_stmDL, orquestacion de
               analizar / planificar / crear-archivo / elegir / entrenar
               estructuras de codigo por seccion.

La clase envuelve una neurona LeCun (NeuronaEntradaLeCun) y delega toda la
matematica en su arquitectura (fan_in, forward, ratio_varianza) en tiempo de
ejecucion, sin importar RFPRMN hasta que se invoca un metodo de Maquina.

Diferencias respecto a sbrtm_EN2_RN2 (Xavier):
  - Dimension del espacio semantico: fan_in (solo entrada, sin fan_out).
  - Impulso: ratio varianza_real / (1/fan_in) en lugar de ratio Xavier.
  - Funciones fusionadas: vector+proyectar en un solo recorrido cuando es
    posible (evita doble normalizacion); similitud_batch vectorizada.
  - Nuevas metricas: divergencia_kl, centroide, dispersion, ranking.
"""

import math
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Cache del paquete RFPRMN (singleton de modulo)
# ---------------------------------------------------------------------------
_PAQUETE_RFPRMN: Optional[Any] = None


def _localizar_rfprmn() -> str:
    """Sube el arbol de directorios buscando RFPRMN.py + STM_RFPRMN_stmDL/."""
    import os as _os
    d = _os.path.dirname(_os.path.abspath(__file__))
    while True:
        for rel in ("", "STM_RFPRMN", "STM_RFC/STM_RFPRMN"):
            cand = d if not rel else _os.path.join(d, rel)
            if (_os.path.isfile(_os.path.join(cand, "RFPRMN.py")) and
                    _os.path.isdir(_os.path.join(cand, "STM_RFPRMN_stmDL"))):
                return cand
        padre = _os.path.dirname(d)
        if padre == d:
            return ""
        d = padre


def _maquina() -> Any:
    """Importa una sola vez el paquete STM_RFPRMN_stmDL (singleton de modulo)."""
    global _PAQUETE_RFPRMN
    if _PAQUETE_RFPRMN is None:
        import importlib
        import sys as _sys
        try:
            _PAQUETE_RFPRMN = importlib.import_module("STM_RFPRMN_stmDL")
        except ImportError:
            raiz = _localizar_rfprmn()
            if raiz and raiz not in _sys.path:
                _sys.path.insert(0, raiz)
            _PAQUETE_RFPRMN = importlib.import_module("STM_RFPRMN_stmDL")
        # Precarga los submodulos que usan las neuronas
        importlib.import_module("STM_RFPRMN_stmDL.stm_creacion")
        importlib.import_module("STM_RFPRMN_stmDL.stm_analisis")
        importlib.import_module("STM_RFPRMN_stmDL.stm_mn")
    return _PAQUETE_RFPRMN


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------
class NeuronaCodigo:
    """Subrutina que crea archivos de codigo vacio por seccion con RFPRMN.

    Uso rapido::

        lecun = NeuronaEntradaLeCun(64, 32)
        codigo = NeuronaCodigo(lecun)
        print(codigo.analizar_afinidades())     # tabla coseno previa
        codigo.crear_archivo_en("LC_STM")       # crea un .py vacio
        codigo.construir()                      # pipeline completo
    """

    # ------------------------------------------------------------------
    # Configuracion de secciones y lenguajes
    # ------------------------------------------------------------------
    CARPETAS: List[str] = [
        "LC_STM", "MTBGT", "SBSTM", "STM_BKCH", "STM_CH",
        "STM_DOC", "STM_JSON", "STM_SGR",
        "STMGNRL", "STMIPFS", "tests", "VSC#",
    ]

    LENGUAJES: Dict[str, Dict[str, str]] = {
        "python":   {"ext": ".py",   "desc": "python script module logic state machine learning"},
        "csharp":   {"ext": ".cs",   "desc": "csharp visual studio code class component interface"},
        "gdscript": {"ext": ".gd",   "desc": "gdscript godot game scene node visual script"},
        "json":     {"ext": ".json", "desc": "json data config storage document serialization"},
        "markdown": {"ext": ".md",   "desc": "markdown documentation readme text guide"},
    }

    _LENGUAJE_DEFECTO: Dict[str, str] = {
        "LC_STM": "python", "MTBGT": "python", "SBSTM": "python",
        "STM_BKCH": "python", "STM_CH": "python", "STM_DOC": "markdown",
        "STM_JSON": "json", "STM_SGR": "python", "STMGNRL": "python",
        "STMIPFS": "python", "tests": "python", "VSC#": "csharp",
    }

    RUTA_SRC: str = (
        r"E:\WoldVirtualP2P3D\VersionDe_sesion"
        r"\CONTRRF\CONTRUCCION\LCtrabajando\src"
    )

    def __init__(self, neurona: Any) -> None:
        self._neurona = neurona

    # ==================================================================
    # MATEMATICA LECUN
    # Funciones fusionadas para evitar recorridos redundantes.
    # ==================================================================
    class Matematica:
        """Codificacion y proyeccion LeCun de texto en vectores semanticos.

        Diferencias respecto a la version Xavier (EN2):
          - ``fan_in`` = ``neurona.input_size`` (dimension unica de LeCun).
          - ``impulso_codigo`` usa ratio varianza_real / (1/fan_in).
          - ``similitud_batch`` vectoriza el calculo coseno sobre N textos.
          - ``divergencia_kl`` mide distancia entre distribuciones softmax.
          - ``centroide`` y ``dispersion`` caracterizan el espacio semantico.
        """

        # ----------------------------------------------------------
        # Hash FNV-1a con cache LRU (compartido con EN2, misma funcion)
        # ----------------------------------------------------------
        @staticmethod
        @lru_cache(maxsize=8192)
        def hash_token(token: str) -> int:
            """Hash FNV-1a determinista de 32 bits para un token."""
            h = 2166136261
            for c in str(token):
                h = ((h ^ ord(c)) * 16777619) & 0xFFFFFFFF
            return h

        # ----------------------------------------------------------
        # Vector + proyeccion fusionados
        # ----------------------------------------------------------
        @classmethod
        def vector(cls, neurona: Any, texto: str) -> np.ndarray:
            """Bolsa de tokens normalizada en el espacio LeCun (dim = fan_in).

            Matematica:
              v[hash(t) % fan_in] += sign(hash(t))   para cada token t
              v_norm = v / ||v||_2
            """
            n = max(1, int(neurona.input_size))   # fan_in en LeCun
            v = np.zeros(n, dtype=np.float64)
            for token in str(texto).split():
                h = cls.hash_token(token)
                v[h % n] += 1.0 if h >= 0 else -1.0
            norma = float(np.linalg.norm(v))
            if norma > 0.0:
                v /= norma
            return v

        @classmethod
        def proyectar(cls, neurona: Any, texto: str) -> np.ndarray:
            """Proyeccion LeCun: forward(vector_bag_of_tokens).reshape(-1).

            Fusiona vector + forward en una sola llamada para evitar
            la re-normalizacion intermedia cuando el texto ya fue hasheado.
            """
            if neurona.pesos is None:
                neurona.inicializar_pesos()
            return np.asarray(
                neurona.forward(cls.vector(neurona, texto))
            ).reshape(-1)

        # ----------------------------------------------------------
        # Similitud coseno (escalar y batch vectorizado)
        # ----------------------------------------------------------
        @classmethod
        def similitud(cls, neurona: Any, a: str, b: str) -> float:
            """Coseno entre las proyecciones LeCun de dos textos.

            cos(θ) = (Pa · Pb) / (‖Pa‖ · ‖Pb‖ + ε)
            """
            va = cls.proyectar(neurona, a).astype(np.float64)
            vb = cls.proyectar(neurona, b).astype(np.float64)
            den = float(np.linalg.norm(va) * np.linalg.norm(vb)) + 1e-12
            return float(np.dot(va, vb) / den)

        @classmethod
        def similitud_batch(
            cls,
            neurona: Any,
            referencia: str,
            candidatos: List[str],
        ) -> np.ndarray:
            """Coseno vectorizado entre ``referencia`` y cada candidato.

            Mucho mas eficiente que N llamadas a ``similitud`` porque
            apila las proyecciones en una matriz y hace el producto con
            una sola operacion matricial.

            Returns
            -------
            np.ndarray  shape (len(candidatos),)
                Puntuaciones coseno en el mismo orden que ``candidatos``.
            """
            if not candidatos:
                return np.array([], dtype=np.float64)
            vr = cls.proyectar(neurona, referencia).astype(np.float64)
            M = np.vstack([
                cls.proyectar(neurona, c).astype(np.float64)
                for c in candidatos
            ])                                        # (N, output_size)
            normas = np.linalg.norm(M, axis=1, keepdims=True) + 1e-12
            M_norm = M / normas
            nr = float(np.linalg.norm(vr)) + 1e-12
            return (M_norm @ (vr / nr)).astype(np.float64)

        # ----------------------------------------------------------
        # Impulso LeCun (temperatura de decision)
        # ----------------------------------------------------------
        @classmethod
        def impulso_codigo(cls, neurona: Any) -> float:
            """Temperatura LeCun en [0.2, 0.9] para guiar la eleccion de lenguaje.

            Matematica LeCun (distinta de Xavier):
              var_esp  = 1 / fan_in
              ratio    = varianza_real / var_esp
              desvio   = |log(max(ratio, 1e-6))|
              T        = clip(0.2 + 0.7 * min(desvio, 1.0),  0.2,  0.9)

            ratio ~ 1  →  equilibrio LeCun  →  eleccion determinista (T bajo)
            ratio ≠ 1  →  desequilibrio     →  eleccion exploratoria  (T alto)
            """
            if neurona.pesos is None:
                neurona.inicializar_pesos()
            ratio = neurona._ratio_varianza()
            desvio = abs(math.log(max(ratio, 1e-6)))
            return float(np.clip(0.2 + 0.7 * min(desvio, 1.0), 0.2, 0.9))

        # ----------------------------------------------------------
        # Entropia de Shannon normalizada
        # ----------------------------------------------------------
        @classmethod
        def entropia(cls, neurona: Any, texto: str) -> float:
            """Entropia de Shannon normalizada de la proyeccion LeCun (∈ [0, 1]).

            Matematica:
              z  = proyectar(texto)
              p  = softmax(z) = exp(z - max(z)) / sum(...)
              H  = -Σ p_i log(p_i) / log(N)      (normalizado a [0,1])
            """
            z = cls.proyectar(neurona, texto).astype(np.float64)
            e = np.exp(z - np.max(z))
            p = e / (e.sum() + 1e-12)
            p = p[p > 1e-12]
            if p.size == 0:
                return 0.0
            return float(-(p * np.log(p)).sum() / max(math.log(p.size), 1e-12))

        # ----------------------------------------------------------
        # Divergencia KL entre dos proyecciones (metrica adicional)
        # ----------------------------------------------------------
        @classmethod
        def divergencia_kl(cls, neurona: Any, a: str, b: str) -> float:
            """Divergencia KL(P_a || P_b) entre distribuciones softmax.

            Matematica:
              KL(P||Q) = Σ P_i log(P_i / Q_i)   (asimetrica)

            Util para medir cuanto difiere la distribucion semantica de
            ``a`` respecto a la de ``b`` desde el punto de vista de ``a``.
            """
            def _softmax(texto: str) -> np.ndarray:
                z = cls.proyectar(neurona, texto).astype(np.float64)
                e = np.exp(z - np.max(z))
                return e / (e.sum() + 1e-12)

            p = _softmax(a)
            q = _softmax(b)
            q = np.where(q < 1e-12, 1e-12, q)
            mask = p > 1e-12
            if not mask.any():
                return 0.0
            return float(np.sum(p[mask] * np.log(p[mask] / q[mask])))

        # ----------------------------------------------------------
        # Centroide y dispersion del espacio semantico
        # ----------------------------------------------------------
        @classmethod
        def centroide(
            cls,
            neurona: Any,
            textos: List[str],
        ) -> np.ndarray:
            """Vector medio de las proyecciones LeCun de una lista de textos.

            Util para representar el 'centro semantico' de un conjunto de
            secciones o descripciones.
            """
            if not textos:
                n = max(1, int(neurona.output_size))
                return np.zeros(n, dtype=np.float64)
            M = np.vstack([
                cls.proyectar(neurona, t).astype(np.float64)
                for t in textos
            ])
            return M.mean(axis=0)

        @classmethod
        def dispersion(cls, neurona: Any, textos: List[str]) -> float:
            """Varianza media de las proyecciones respecto al centroide.

            Matematica: σ² = (1/N) Σ ||p_i - μ||²_2
            Mide cuan disperso es el espacio semantico de las secciones.
            """
            if len(textos) < 2:
                return 0.0
            mu = cls.centroide(neurona, textos)
            M = np.vstack([
                cls.proyectar(neurona, t).astype(np.float64)
                for t in textos
            ])
            diffs = M - mu
            return float(np.mean(np.sum(diffs ** 2, axis=1)))

        # ----------------------------------------------------------
        # Ranking por afinidad (fusiona similitud_batch + argsort)
        # ----------------------------------------------------------
        @classmethod
        def ranking(
            cls,
            neurona: Any,
            referencia: str,
            candidatos: List[str],
        ) -> List[Tuple[str, float]]:
            """Lista de candidatos ordenados de mayor a menor afinidad coseno.

            Fusiona ``similitud_batch`` + ``argsort`` en un solo paso.

            Returns
            -------
            List[Tuple[str, float]]
                Lista de (candidato, puntuacion) ordenada desc.
            """
            if not candidatos:
                return []
            scores = cls.similitud_batch(neurona, referencia, candidatos)
            orden = np.argsort(scores)[::-1]
            return [(candidatos[i], float(scores[i])) for i in orden]

    # ==================================================================
    # MAQUINA DE COMANDOS RFPRMN
    # ==================================================================
    class Maquina:
        """Orquestacion de RFPRMN para crear archivos de codigo por seccion."""

        @staticmethod
        def analizar_seccion(ruta: str) -> Dict[str, Any]:
            """Analisis estatico + plan de refactor de un archivo existente."""
            import os as _os
            from pathlib import Path
            pkg = _maquina()
            objetivo = Path(_os.path.expanduser(str(ruta))).resolve()
            analisis = pkg.stm_analisis.analizar_archivo_local(objetivo)
            return {
                "ruta": str(objetivo),
                "analisis": analisis.a_dict(),
                "plan": pkg.stm_analisis.crear_plan_refactorizacion(analisis),
            }

        @staticmethod
        def plan_seccion(
            descripcion: str,
            ruta: str,
            lenguaje: str = "python",
        ) -> str:
            """Diagnostico/plan que propone la estructura del archivo a crear."""
            return _maquina().stm_creacion.diagnosticar(descripcion, ruta, lenguaje)

        @staticmethod
        def crear_archivo(
            neurona: Any,
            ruta_carpeta: str,
            nombre: str,
            lenguaje: str = "",
        ) -> Dict[str, Any]:
            """Crea un archivo vacio en ``ruta_carpeta/nombre`` via RFPRMN.

            Usa ``RFPRMN().crear_archivo()`` (API no interactiva) y registra
            el impulso LeCun del momento de creacion.
            """
            try:
                impulso = NeuronaCodigo.Matematica.impulso_codigo(neurona)
                pkg = _maquina()
                ruta_final = pkg.stm_mn.RFPRMN().crear_archivo(
                    ruta_carpeta, nombre, lenguaje)
                return {
                    "ok": True,
                    "ruta": ruta_final,
                    "nombre": nombre,
                    "lenguaje": lenguaje,
                    "impulso": impulso,
                }
            except Exception as error:  # noqa: BLE001
                return {"ok": False, "error": f"{type(error).__name__}: {error}"}

        @staticmethod
        def elegir_lenguaje(
            neurona: Any,
            carpeta: str,
            lenguajes: Dict[str, Dict[str, str]],
        ) -> Tuple[str, float]:
            """Elige el lenguaje mas afin a ``carpeta`` por similitud_batch LeCun.

            Fusiona la comparacion de todos los lenguajes en una sola
            llamada vectorizada (``similitud_batch``).

            Returns
            -------
            Tuple[str, float]
                (nombre_lenguaje, puntuacion_coseno)
            """
            candidatos = list(lenguajes.keys())
            descs = [lenguajes[l]["desc"] for l in candidatos]
            scores = NeuronaCodigo.Matematica.similitud_batch(
                neurona, carpeta, descs)
            idx = int(np.argmax(scores))
            return candidatos[idx], float(scores[idx])

        @staticmethod
        def entrenar_seccion(ruta: str = "") -> Dict[str, Any]:
            """Envia el archivo creado a la red neuronal (comando lc entrenar)."""
            try:
                return _maquina().stm_mn.RFPRMN().lc_entrenar(ruta)
            except Exception as error:  # noqa: BLE001
                return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    # ==================================================================
    # API DE INSTANCIA (delega en Matematica y Maquina)
    # ==================================================================

    # -- Propiedades de solo lectura ------------------------------------
    @property
    def maquina(self) -> Any:
        """Paquete STM_RFPRMN_stmDL cargado de forma perezosa."""
        return _maquina()

    @property
    def impulso(self) -> float:
        """Temperatura LeCun actual derivada del ratio de varianza."""
        return self.Matematica.impulso_codigo(self._neurona)

    # -- Matematica (delegacion directa) --------------------------------
    def vector(self, texto: str) -> np.ndarray:
        """Bolsa de tokens LeCun normalizada para ``texto``."""
        return self.Matematica.vector(self._neurona, texto)

    def proyectar(self, texto: str) -> np.ndarray:
        """Proyeccion LeCun de ``texto`` (forward de la neurona)."""
        return self.Matematica.proyectar(self._neurona, texto)

    def similitud(self, a: str, b: str) -> float:
        """Coseno entre las proyecciones LeCun de ``a`` y ``b``."""
        return self.Matematica.similitud(self._neurona, a, b)

    def similitud_batch(
        self, referencia: str, candidatos: List[str]
    ) -> np.ndarray:
        """Coseno vectorizado entre ``referencia`` y cada candidato."""
        return self.Matematica.similitud_batch(self._neurona, referencia, candidatos)

    def impulso_codigo(self) -> float:
        """Temperatura LeCun en [0.2, 0.9]."""
        return self.impulso

    def entropia(self, texto: str) -> float:
        """Entropia Shannon normalizada de la proyeccion LeCun de ``texto``."""
        return self.Matematica.entropia(self._neurona, texto)

    def divergencia_kl(self, a: str, b: str) -> float:
        """Divergencia KL(P_a || P_b) entre distribuciones softmax LeCun."""
        return self.Matematica.divergencia_kl(self._neurona, a, b)

    def centroide(self, textos: List[str]) -> np.ndarray:
        """Vector medio de las proyecciones de ``textos``."""
        return self.Matematica.centroide(self._neurona, textos)

    def dispersion(self, textos: List[str]) -> float:
        """Varianza media respecto al centroide del conjunto ``textos``."""
        return self.Matematica.dispersion(self._neurona, textos)

    def ranking(
        self, referencia: str, candidatos: List[str]
    ) -> List[Tuple[str, float]]:
        """Candidatos ordenados de mayor a menor afinidad coseno."""
        return self.Matematica.ranking(self._neurona, referencia, candidatos)

    def afinidad_lenguaje(self, carpeta: str, lenguaje: str) -> float:
        """Coseno entre la carpeta y la descripcion semantica del lenguaje."""
        desc = self.LENGUAJES.get(lenguaje, {}).get("desc", lenguaje)
        return self.similitud(carpeta, desc)

    # -- Orquestacion (delegacion a Maquina) ----------------------------
    def analizar_seccion(self, ruta: str) -> Dict[str, Any]:
        """Analisis estatico + plan de refactor de un archivo existente."""
        return self.Maquina.analizar_seccion(ruta)

    def plan_seccion(
        self, descripcion: str, ruta: str, lenguaje: str = "python"
    ) -> str:
        """Plan/diagnostico de la estructura del archivo a crear."""
        return self.Maquina.plan_seccion(descripcion, ruta, lenguaje)

    def crear_archivo_en(
        self,
        carpeta: str,
        lenguaje: Optional[str] = None,
        nombre_archivo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Crea un archivo vacio en ``RUTA_SRC/carpeta`` via RFPRMN.

        Si ``lenguaje`` es None, lo elige automaticamente por similitud_batch
        (mas eficiente que N llamadas escalares).
        """
        from pathlib import Path
        try:
            if lenguaje:
                lang, score = lenguaje, self.afinidad_lenguaje(carpeta, lenguaje)
            else:
                lang, score = self.Maquina.elegir_lenguaje(
                    self._neurona, carpeta, self.LENGUAJES)
            ext = self.LENGUAJES.get(lang, {}).get("ext", ".py")
            nombre = nombre_archivo or (
                f"{carpeta.lower().replace('#', 'sharp')}{ext}")
            ruta_carpeta = str(Path(self.RUTA_SRC) / carpeta)
            res = self.Maquina.crear_archivo(
                self._neurona, ruta_carpeta, nombre, lang)
            res.update({"carpeta": carpeta, "afinidad": score})
            return res
        except Exception as error:  # noqa: BLE001
            return {"ok": False, "carpeta": carpeta,
                    "error": f"{type(error).__name__}: {error}"}

    def crear_archivos(
        self,
        lenguajes_forzados: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Crea un archivo vacio en cada carpeta de la estructura.

        Usa ``similitud_batch`` para elegir lenguajes de forma vectorizada
        (una sola pasada por carpeta en lugar de N cosenos escalares).
        """
        forzados = lenguajes_forzados or {}
        resultados: List[Dict[str, Any]] = []
        fallos: List[Dict[str, Any]] = []
        for carpeta in self.CARPETAS:
            lang = forzados.get(carpeta)
            res = self.crear_archivo_en(carpeta, lenguaje=lang)
            (resultados if res.get("ok") else fallos).append(res)
        return {
            "ok": len(fallos) == 0,
            "total": len(self.CARPETAS),
            "creados": len(resultados),
            "fallos": len(fallos),
            "archivos": resultados,
            "errores": fallos,
        }

    def analizar_afinidades(self) -> List[Dict[str, Any]]:
        """Tabla de afinidades coseno LeCun carpeta × lenguaje (dry-run).

        Vectoriza el calculo de afinidades con ``similitud_batch`` para
        minimizar el numero de forward passes de la neurona.
        """
        tabla: List[Dict[str, Any]] = []
        nombres = list(self.LENGUAJES.keys())
        descs = [self.LENGUAJES[l]["desc"] for l in nombres]
        for carpeta in self.CARPETAS:
            scores = self.Matematica.similitud_batch(
                self._neurona, carpeta, descs)
            puntajes = {nombres[i]: round(float(scores[i]), 4)
                        for i in range(len(nombres))}
            elegido = nombres[int(np.argmax(scores))]
            tabla.append({
                "carpeta": carpeta,
                "elegido": elegido,
                "ext": self.LENGUAJES[elegido]["ext"],
                "puntajes": puntajes,
                "entropia": round(self.Matematica.entropia(
                    self._neurona, carpeta), 4),
                "impulso": round(self.Matematica.impulso_codigo(
                    self._neurona), 4),
            })
        return tabla

    def dispersion_secciones(self) -> Dict[str, float]:
        """Metricas de cohesion y dispersion del espacio semantico de carpetas.

        Returns
        -------
        Dict[str, float]
            ``dispersion``  : varianza media respecto al centroide.
            ``entropia_media``: entropia media sobre todas las secciones.
            ``impulso``     : temperatura LeCun actual.
        """
        return {
            "dispersion": self.Matematica.dispersion(
                self._neurona, self.CARPETAS),
            "entropia_media": float(np.mean([
                self.Matematica.entropia(self._neurona, c)
                for c in self.CARPETAS
            ])),
            "impulso": self.Matematica.impulso_codigo(self._neurona),
        }

    def entrenar_seccion(self, ruta: str = "") -> Dict[str, Any]:
        """Envia un archivo creado a la red neuronal (lc entrenar)."""
        return self.Maquina.entrenar_seccion(ruta)

    def construir(
        self,
        lenguajes_forzados: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Pipeline completo: analiza afinidades y crea todos los archivos.

        Paso 1 — analizar_afinidades() : tabla coseno (dry-run, sin escritura).
        Paso 2 — crear_archivos()       : emite 'crear archivo' en cada carpeta.
        """
        analisis = self.analizar_afinidades()
        creacion = self.crear_archivos(lenguajes_forzados)
        metricas = self.dispersion_secciones()
        return {
            "ok": creacion.get("ok"),
            "analisis": analisis,
            "creacion": creacion,
            "metricas": metricas,
        }

    # -- Representacion -------------------------------------------------
    def __str__(self) -> str:
        n = getattr(self._neurona, "nombre", "LeCun")
        fi = getattr(self._neurona, "input_size", "?")
        fo = getattr(self._neurona, "output_size", "?")
        return f"NeuronaCodigo({n}, fan_in={fi}, fan_out={fo})"

    def __repr__(self) -> str:
        return self.__str__()


# ---------------------------------------------------------------------------
# Exportaciones
# ---------------------------------------------------------------------------
__all__ = ["NeuronaCodigo"]
