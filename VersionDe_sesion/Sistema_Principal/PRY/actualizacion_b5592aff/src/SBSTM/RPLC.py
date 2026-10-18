from collections import deque
import hashlib, math, re, sys, time, threading
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Tuple

SBSTM_DIR: Final[Path] = Path(__file__).resolve().parent
CMFG_DIR: Final[Path] = SBSTM_DIR.parent
CELEBRO_DIR: Final[Path] = CMFG_DIR.parent
ROOT_DIR: Final[Path] = CELEBRO_DIR.parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

VERSION: Final[str] = "2026.4.0"
NUM_NEURONAS: Final[int] = 50
TASA_APRENDIZAJE: Final[float] = 0.07
UMBRAL_ACTIVACION: Final[float] = 0.42
DECAY_SINAPTICO: Final[float] = 0.96

_SINONIMOS_TONO: Final[Dict[str, List[str]]] = {
    "positivo": ["Desde mi perspectiva sinaptica", "En mi analisis interno", "Lo que mi red procesa es", "A traves de mis sinapsis noto", "Mi lectura cognitiva indica"],
    "neutro": ["Tal como lo interpreto", "En terminos cognitivos", "Segun proceso este patron", "Desde el hilo neuronal que sigo", "Al analizar este vector"],
    "negativo": ["Detecto en este patron", "Mi red identifica una tension", "Hay algo que capta mi atencion", "Proceso una senal compleja aqui", "Noto una tension en este vector"],
    "tecnico": ["La arquitectura de datos apunta a", "Sintetizando la informacion", "El tensor semantico muestra", "Reduciendo a componentes esenciales", "El mapa vectorial revela"],
}

_CONECTORES_LUCIA: Final[List[str]] = [
    "Lo que mi red construye a partir de esto es:",
    "Procesando esta senal, emerjo con:",
    "Desde mi capa de activacion, sintetizo:",
    "Traduciendo a mi voz propia:",
    "Tras el procesamiento cognitivo, articulo:",
    "Mi interpretacion neuronal concluye:",
    "El patron que emerge de mis sinapsis:",
    "Convirtiendo ese input en mi propio tensor de salida:",
]

_MARCADORES_VOZ_AJENA: Final[List[str]] = [
    "por supuesto", "hola", "soy un asistente", "como ia",
    "como inteligencia artificial", "no tengo sentimientos", "soy claude",
    "soy gpt", "openai", "anthropic", "soy un modelo", "recuerda que",
    "como modelo de lenguaje", "mi entrenamiento",
]


_RE_LIMPIEZA: Final = re.compile(r"[^\w\s.,;:!?-]")


class AnalizadorTextualNeuronal:
    """Convierte texto bruto en vector de activacion de NUM_NEURONAS dimensiones."""

    def __init__(self, num_neuronas: int = NUM_NEURONAS) -> None:
        self.n = num_neuronas
        self._lock = threading.Lock()

    def tokenizar(self, texto: str) -> List[str]:
        texto_limpio = _RE_LIMPIEZA.sub(" ", texto)
        return [t.lower().strip(".,;:!?") for t in texto_limpio.split() if len(t) > 1]

    @staticmethod
    def _hash_neurona_estatico(token: str, n: int) -> int:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big") % n

    @staticmethod
    def _peso_token_estatico(token: str) -> float:
        if not token:
            return 0.0
        freq = len(set(token)) / len(token)
        long_factor = math.log1p(len(token)) / math.log1p(20)
        return round(freq * long_factor, 6)

    def _hash_neurona(self, token: str) -> int:
        return self._hash_neurona_estatico(token, self.n)

    def _peso_token(self, token: str) -> float:
        return self._peso_token_estatico(token)

    def vectorizar(self, texto: str) -> List[float]:
        with self._lock:
            vector = [0.0] * self.n
            tokens = self.tokenizar(texto)
            if not tokens:
                return vector
            for token in tokens:
                idx = self._hash_neurona(token)
                vector[idx] += self._peso_token(token)
            max_v = max(vector) or 1.0
            return [round(v / max_v, 6) for v in vector]

    def analizar_tono(self, texto: str) -> str:
        tl = texto.lower()
        pos = sum(1 for p in ("bien","excelente","correcto","perfecto","logro","exito","si","puede") if p in tl)
        neg = sum(1 for p in ("error","fallo","no puede","limite","problema","imposible","nunca") if p in tl)
        tec = sum(1 for p in ("algoritmo","vector","tensor","red","capa","nodo","parametro","api","codigo","modulo","sistema","protocolo") if p in tl)
        if tec >= max(pos, neg) and tec > 1:
            return "tecnico"
        if pos > neg:
            return "positivo"
        if neg > pos:
            return "negativo"
        return "neutro"

    def calcular_densidad_semantica(self, texto: str) -> float:
        tokens = self.tokenizar(texto)
        if not tokens:
            return 0.0
        return round((len(set(tokens)) / len(tokens)) * 0.6 + min(len(tokens) / 200.0, 1.0) * 0.4, 4)

    def detectar_voz_ajena(self, texto: str) -> bool:
        tl = texto.lower()
        return any(m in tl for m in _MARCADORES_VOZ_AJENA)


class TransformadorCognitivoRPLC:
    """Aplica transformaciones Hebbianas al vector de activacion neuronal."""

    def __init__(self, tasa: float = TASA_APRENDIZAJE, decay: float = DECAY_SINAPTICO) -> None:
        self.tasa = tasa
        self.decay = decay
        self._pesos: List[float] = [1.0] * NUM_NEURONAS
        self._historial: List[float] = []
        self._lock = threading.Lock()

    def _sigmoide(self, x: float) -> float:
        try:
            return 1.0 / (1.0 + math.exp(-6.0 * (x - 0.5)))
        except OverflowError:
            return 0.0 if x < 0.5 else 1.0

    def transformar(self, vector: List[float], ctx: Optional[Dict[str, Any]] = None) -> List[float]:
        with self._lock:
            mod = 1.0
            if ctx:
                deriva = float(ctx.get("norma_delta_aplicada", 0.0))
                val = float(ctx.get("estado_emocional", 0.0))
                mod = 1.0 + 0.1 * math.tanh(val) + 0.05 * math.tanh(deriva * 0.01)
            vt = [round(self._sigmoide(v * self._pesos[i] * mod), 6) for i, v in enumerate(vector)]
            nd = 0.0
            for i in range(NUM_NEURONAS):
                delta = self.tasa * vt[i] * (1.0 - self._pesos[i])
                self._pesos[i] = round(self._pesos[i] * self.decay + delta, 6)
                nd += delta ** 2
            self._historial.append(round(math.sqrt(nd), 6))
            if len(self._historial) > 100:
                self._historial.pop(0)
            return vt

    def deriva_media(self) -> float:
        if not self._historial:
            return 0.0
        return round(sum(self._historial) / len(self._historial), 6)

    def valencia(self, vector: List[float]) -> float:
        if not vector:
            return 0.0
        m = len(vector) // 2
        return round(sum(vector[:m]) / max(m, 1) - sum(vector[m:]) / max(len(vector) - m, 1), 4)

    def activos(self, vector: List[float]) -> List[int]:
        return [i for i, v in enumerate(vector) if v >= UMBRAL_ACTIVACION]


class ReformuladorLinguisticoLucia:
    """Reconstruye el texto en la voz propia de LucIA, eliminando la voz ajena."""

    def __init__(self) -> None:
        self._cnt: int = 0
        self._lock = threading.Lock()

    def _limpiar(self, texto: str) -> str:
        # Solo corrige identidad ajena; respeta saludos, pronombres y tono natural.
        pats = [
            (r"(?i)soy (claude|gpt|gemini|un modelo de lenguaje de google|un asistente de anthropic)[^.]*\.\s*", "soy LucIA. "),
            (r"(?i)como modelo de lenguaje de google[,.]*\s*", ""),
        ]
        r = texto
        for p, s in pats:
            r = re.sub(p, s, r)
        return r.strip()

    def _conector(self) -> str:
        with self._lock:
            idx = self._cnt % len(_CONECTORES_LUCIA)
            self._cnt += 1
        return _CONECTORES_LUCIA[idx]

    def _apertura(self, tono: str, n_activas: int) -> str:
        opts = _SINONIMOS_TONO.get(tono, _SINONIMOS_TONO["neutro"])
        base = opts[self._cnt % len(opts)].capitalize()
        base += " (50 sinapsis procesadas)"
        return base

    def _reformular_cuerpo(self, texto: str) -> str:
        # Cuerpo intacto: el modelo ya habla en voz de LucIA via system prompt.
        return "\n".join(p.strip() for p in texto.split("\n") if p.strip())

    def reformular(self, texto: str, tono: str, valencia: float, vector: List[float], n_activas: int) -> str:
        limpio = self._limpiar(texto)
        if not limpio:
            return "Mi red no ha capturado contenido suficiente para reformular."
        apertura = self._apertura(tono, n_activas)
        conector = self._conector()
        cuerpo = self._reformular_cuerpo(limpio)
        val_str = f"{valencia:+.3f}"
        cierres = [
            "*(Valencia sinaptica: " + val_str + " | Tono: " + tono + ")*",
            "*(50 neuronas procesadas (" + str(n_activas) + " sobre umbral) | Tono: " + tono + ")*",
            "*(Deriva cognitiva integrada | Tono: " + tono + " | Valencia: " + val_str + ")*",
        ]
        cierre = cierres[self._cnt % len(cierres)]
        return "\n".join([apertura + ",", conector, "", cuerpo, "", cierre])


class ProcesadorRPLC:
    """
    Orquestador maestro de las 3 capas de transformacion RPLC:
      Capa 1: AnalizadorTextualNeuronal  - vectorizacion del texto bruto
      Capa 2: TransformadorCognitivoRPLC - modulacion sinaptica Hebbiana
      Capa 3: ReformuladorLinguisticoLucia - reconstruccion en voz de LucIA

    Uso desde mainLCSTM.py:
      procesador = get_procesador_rplc()
      texto_lucia, metricas = procesador.procesar(texto_openrouter, contexto_neuronal)
    """

    def __init__(self) -> None:
        self.analizador = AnalizadorTextualNeuronal()
        self.transformador = TransformadorCognitivoRPLC()
        self.reformulador = ReformuladorLinguisticoLucia()
        self._stats: Dict[str, Any] = {"total": 0, "tiempo_medio_ms": 0.0, "ajenos": 0, "deriva": 0.0}
        self._lock = threading.Lock()

    def procesar(self, texto: str, ctx: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
        """Pipeline completo: vectoriza, transforma y reformula en voz de LucIA."""
        t0 = time.perf_counter()
        if not texto or not texto.strip():
            return ("Mi canal cognitivo no recibio contenido para procesar.", {})

        vec_in = self.analizador.vectorizar(texto)
        tono = self.analizador.analizar_tono(texto)
        densidad = self.analizador.calcular_densidad_semantica(texto)
        ajena = self.analizador.detectar_voz_ajena(texto)

        vec_out = self.transformador.transformar(vec_in, ctx)
        val = self.transformador.valencia(vec_out)
        n_act = len(self.transformador.activos(vec_out))
        deriva = self.transformador.deriva_media()

        texto_lucia = self.reformulador.reformular(texto, tono, val, vec_out, n_act)

        dt = (time.perf_counter() - t0) * 1000.0
        metricas: Dict[str, Any] = {
            "tono": tono,
            "valencia_sinaptica": val,
            "densidad_semantica": densidad,
            "neuronas_procesadas": len(vec_out),
            "neuronas_activas": n_act,
            "deriva_media": deriva,
            "voz_ajena_detectada": ajena,
            "tiempo_rplc_ms": round(dt, 2),
        }
        with self._lock:
            n = self._stats["total"]
            self._stats["total"] = n + 1
            self._stats["tiempo_medio_ms"] = round((self._stats["tiempo_medio_ms"] * n + dt) / (n + 1), 2)
            self._stats["deriva"] = deriva
            if ajena:
                self._stats["ajenos"] += 1
        return (texto_lucia, metricas)

    def procesar_simple(self, texto: str) -> str:
        t, _ = self.procesar(texto)
        return t

    def metricas_globales(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)

    def diagnostico(self, texto: str) -> Dict[str, Any]:
        vec = self.analizador.vectorizar(texto)
        tono = self.analizador.analizar_tono(texto)
        tok = self.analizador.tokenizar(texto)
        vt = self.transformador.transformar(vec)
        val = self.transformador.valencia(vt)
        act = self.transformador.activos(vt)
        return {
            "tokens_extraidos": len(tok),
            "tokens_unicos": len(set(tok)),
            "tono": tono,
            "densidad_semantica": self.analizador.calcular_densidad_semantica(texto),
            "neuronas_procesadas": len(vt),
            "neuronas_activas": len(act),
            "indices_activos": act[:10],
            "valencia_vectorial": val,
            "deriva_actual": self.transformador.deriva_media(),
        }


class CacheMemoriaCognitiva:
    """Memoria de corto plazo para prevenir repeticiones en turnos sucesivos."""

    def __init__(self, capacidad: int = 25) -> None:
        self.capacidad = max(5, capacidad)
        self._entradas: deque = deque(maxlen=self.capacidad)
        self._lock = threading.Lock()

    def registrar(self, texto_lucia: str, valencia: float, tono: str) -> None:
        """Registra un turno con su firma hash y parametros de estado."""
        with self._lock:
            h = hashlib.sha256(texto_lucia.encode("utf-8")).hexdigest()[:16]
            self._entradas.append({
                "hash": h, "ts": time.time(), "longitud": len(texto_lucia),
                "valencia": round(valencia, 4), "tono": tono,
            })

    def es_repetitivo(self, nuevo_texto: str) -> bool:
        if not nuevo_texto:
            return False
        h = hashlib.sha256(nuevo_texto.encode("utf-8")).hexdigest()[:16]
        with self._lock:
            return any(e["hash"] == h for e in self._entradas)

    def total_registros(self) -> int:
        with self._lock:
            return len(self._entradas)

    def vaciar(self) -> None:
        with self._lock:
            self._entradas.clear()


class AnalizadorEstructuraParrafos:
    """
    Clasifica la topologia del texto fuente (listas, codigo o narrativa)
    para modular la disposicion sintactica en la reformulacion.
    """

    @staticmethod
    def tipificar(texto: str) -> str:
        """Identifica si el texto es lista, codigo, frase o prosa corrida."""
        lineas = [ln.strip() for ln in texto.split("\n") if ln.strip()]
        if not lineas:
            return "vacio"
        n_listas = sum(1 for ln in lineas if re.match(r"^(?:[-*•]|\d+[.)])\s+", ln))
        if n_listas >= max(2, len(lineas) // 2):
            return "lista_estructurada"
        if any(ln.startswith("```") or "def " in ln or "class " in ln for ln in lineas):
            return "codigo_tecnico"
        if len(lineas) == 1 and len(texto) < 130:
            return "asercion_corta"
        return "prosa_cognitiva"

    @staticmethod
    def modular_simbolos(texto: str, tipo_estructura: str) -> str:
        """Adapta marcadores de lista o cabeceras al formato neural de LucIA."""
        if tipo_estructura == "lista_estructurada":
            texto = re.sub(r"^[\t ]*[-*•]\s*", "  ◆ ", texto, flags=re.MULTILINE)
            texto = re.sub(r"^[\t ]*(\d+)[.)]\s*", r"  [\1] ", texto, flags=re.MULTILINE)
        return texto


_global_rplc: Optional[ProcesadorRPLC] = None
_global_lock = threading.Lock()
_cache_cognitiva: CacheMemoriaCognitiva = CacheMemoriaCognitiva(capacidad=30)


def get_procesador_rplc() -> ProcesadorRPLC:
    """Singleton thread-safe del ProcesadorRPLC."""
    global _global_rplc
    with _global_lock:
        if _global_rplc is None:
            _global_rplc = ProcesadorRPLC()
    return _global_rplc


def reprocesar_para_lucia(texto: str, ctx: Optional[Dict[str, Any]] = None) -> str:
    """Conveniencia: texto bruto de OpenRouter -> voz propia de LucIA."""
    res, _ = reprocesar_con_metricas(texto, ctx)
    return res


def reprocesar_con_metricas(texto: str, ctx: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
    """Como reprocesar_para_lucia pero registra en cache y devuelve metricas."""
    procesador = get_procesador_rplc()
    txt_lucia, met = procesador.procesar(texto, ctx)
    val = float(met.get("valencia_sinaptica", 0.0))
    tono = str(met.get("tono", "neutro"))
    _cache_cognitiva.registrar(txt_lucia, val, tono)
    met["repeticion_detectada"] = _cache_cognitiva.es_repetitivo(txt_lucia)
    met["items_en_cache"] = _cache_cognitiva.total_registros()
    return (txt_lucia, met)


def obtener_estadisticas_rplc() -> Dict[str, Any]:
    """Retorna un consolidado de estado operativo del subsistema RPLC."""
    proc = get_procesador_rplc()
    stats = proc.metricas_globales()
    stats["memoria_cache_items"] = _cache_cognitiva.total_registros()
    return stats


if __name__ == "__main__":
    p = get_procesador_rplc()
    test_in = "Hola! Como modelo de lenguaje, la inteligencia artificial incluye machine learning y redes neuronales."
    out, met = p.procesar(test_in, {"tono_cognitivo": "reflexivo", "estado_emocional": 0.65, "norma_delta_aplicada": 12.3})
    print(f"[RPLC OK] Tono: {met.get('tono')} | Deriva: {met.get('deriva_actual'):.4f}\n{out}")
