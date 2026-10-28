"""Gestor IALOCAL runtime: por pregunta descarga (Ollama/HF), responde,
pasa por pesos neuronales + voz LucIA y borra el modelo tras responder."""
from __future__ import annotations
import ctypes
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PAQUETE_DIR: Path = Path(__file__).resolve().parent
IADS_BR: Path = PAQUETE_DIR.parent / "IADS_BR"
try:
    from STM_CH.rutas import STM_CH_DIR
    ESTADO_ULTIMO: Path = STM_CH_DIR / "ialocal_ultimo.txt"
except ImportError:
    ESTADO_ULTIMO = PAQUETE_DIR / "ialocal_ultimo.txt"
REGISTRO_USO: Path = PAQUETE_DIR / "uso_ialocal.md"

#: Modelo Ollama -> (repo HF, archivo GGUF). Origen visible en IADS_BR.
HF_GGUF: Dict[str, Tuple[str, str]] = {
    "qwen2.5:0.5b": ("Qwen/Qwen2.5-0.5B-Instruct-GGUF", "qwen2.5-0.5b-instruct-q4_k_m.gguf"),
    "llama3.2:1b": ("bartowski/Llama-3.2-1B-Instruct-GGUF", "Llama-3.2-1B-Instruct-Q4_K_M.gguf"),
    "qwen3:1.7b": ("Qwen/Qwen3-1.7B-GGUF", "Qwen3-1.7B-Q4_K_M.gguf"),
    "gemma2:2b": ("bartowski/gemma-2-2b-it-GGUF", "gemma-2-2b-it-Q4_K_M.gguf"),
    "cogito:3b": ("bartowski/cogito-3b-GGUF", "cogito-3b-Q4_K_M.gguf"),
}

OLLAMA_URL = "http://localhost:11434"
# De menor a mayor, pero se prefiere CALIDAD: el mas capaz instalado segun RAM.
# Los tiny (0.5b/1b) generan respostas truncadas/tartamudas ("me has a", "segun proceso
# este patron") y solo se usan como ultimo recurso sin red.
CANDIDATOS_CHAT: Tuple[str, ...] = (
    "qwen2.5:0.5b", "llama3.2:1b", "qwen3:1.7b", "gemma2:2b",
    "cogito:3b", "qwen2.5:3b", "qwen2.5:7b",
    "qwen2.5-coder:7b", "qwen2.5-coder:latest", "starcoder2:7b", "qwen3.5:latest",
)
# Orden de preferencia de calidad (mayor a menor) entre los instalados.
# Modelos generales de chat primero; los *-coder son literales/programadores y
# responden "No lo se" a conversacion; qwen3.5:latest devuelve vacio (roto).
PREFERENCIA_CALIDAD: Tuple[str, ...] = (
    "qwen2.5:7b", "qwen2.5:latest", "llama3.1:8b", "llama3.1:latest",
    "qwen2.5:3b", "qwen2.5-coder:7b", "qwen2.5-coder:latest",
    "starcoder2:7b", "cogito:3b",
    "gemma2:2b", "qwen3:1.7b", "llama3.2:1b", "qwen2.5:0.5b",
    "qwen3.5:latest",
)


_OLLAMA_CACHE: Dict[str, Any] = {"disponible": False, "ts": 0.0, "ttl": 15.0}


def ollama_disponible(timeout: float = 1.0, forzar_sondeo: bool = False) -> bool:
    ahora = time.time()
    if not forzar_sondeo and (ahora - _OLLAMA_CACHE["ts"] < _OLLAMA_CACHE["ttl"]):
        return bool(_OLLAMA_CACHE["disponible"])
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=timeout) as r:
            disp = (r.status == 200)
            _OLLAMA_CACHE["disponible"] = disp
            _OLLAMA_CACHE["ts"] = ahora
            return disp
    except Exception:
        _OLLAMA_CACHE["disponible"] = False
        _OLLAMA_CACHE["ts"] = ahora
        return False


def modelos_instalados(timeout: float = 2.0) -> List[str]:
    if not ollama_disponible(timeout=1.0):
        return []
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=timeout) as r:
            datos = json.loads(r.read().decode("utf-8"))
        return [str(m.get("name", "")) for m in datos.get("models", []) if m.get("name")]
    except Exception:
        return []


def ram_gb() -> float:
    try:
        class _Mem(ctypes.Structure):
            _fields_ = [("wLength", ctypes.c_ulong), ("wMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong)] + [("x", ctypes.c_ulonglong)] * 5
        m = _Mem()
        m.wLength = ctypes.sizeof(_Mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(m.ullTotalPhys / (1024 ** 3), 1)
    except Exception:
        return 8.0


def _ultimo_usado() -> str:
    try:
        return ESTADO_ULTIMO.read_text(encoding="utf-8").strip().lower()
    except Exception:
        return ""


def _anotar_ultimo(modelo: str) -> None:
    try:
        ESTADO_ULTIMO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO_ULTIMO.write_text(modelo.strip().lower(), encoding="utf-8")
    except Exception:
        pass


def elegir_modelo() -> str:
    """Modelo fijo (sticky): repite el ultimo usado si sigue instalado; solo rota ante fallo."""
    inst = {m.lower() for m in modelos_instalados()}
    bases = {m.split(":")[0] for m in inst}
    ultimo = _ultimo_usado()
    if ultimo and (ultimo in inst or ultimo.split(":")[0] in bases):
        return ultimo if ultimo in inst else next(
            (c for c in PREFERENCIA_CALIDAD if c.split(":")[0] == ultimo.split(":")[0] and c in inst),
            ultimo,
        )
    gb = ram_gb()
    # RAM < 6 GB: tope 3b para no colgar el PC; si no, se permite 7b.
    tope_idx = len(PREFERENCIA_CALIDAD) if gb >= 6.0 else 7
    orden = [c for c in PREFERENCIA_CALIDAD[:tope_idx] if c in inst]
    if orden:
        return orden[0]
    for cand in PREFERENCIA_CALIDAD[:tope_idx]:
        if cand.split(":")[0] in bases:
            return cand
    return PREFERENCIA_CALIDAD[0]


def rotar_modelo(evitar: str = "") -> str:
    """Siguiente mejor modelo instalado distinto al actual (solo ante fallo/mala respuesta)."""
    inst = {m.lower() for m in modelos_instalados()}
    actual = (evitar or _ultimo_usado()).lower()
    for cand in PREFERENCIA_CALIDAD:
        if cand in inst and cand != actual:
            _anotar_ultimo(cand)
            return cand
    return elegir_modelo()


def _es_respuesta_pobre(txt: str) -> bool:
    """Detecta respuestas tartamudas/truncadas tipicas de modelos tiny."""
    t = (txt or "").strip()
    if len(t) < 40:
        return True
    malas = ["me has a", "te has a", "segun proceso este patron",
             "desde mi capa de activacion", "traduciendo a mi voz propia",
             "reduciendo a componentes esenciales", "sintetizando la informacion"]
    tl = t.lower()
    # 2+ muletillas genericas o frase cortada sin verbo claro = pobre
    if sum(1 for m in malas if m in tl) >= 2:
        return True
    if t.count(" ") < 8:
        return True
    return False


def _descargar_gguf(modelo: str, timeout: int = 1200) -> Optional[Path]:
    """Descarga el GGUF desde HuggingFace a IADS_BR (visible en disco)."""
    if modelo not in HF_GGUF:
        return None
    repo, archivo = HF_GGUF[modelo]
    IADS_BR.mkdir(parents=True, exist_ok=True)
    final = IADS_BR / archivo
    if final.exists() and final.stat().st_size > 0:
        return final
    url = f"https://huggingface.co/{repo}/resolve/main/{archivo}"
    req = urllib.request.Request(url, headers={"User-Agent": "WoldVirtualP2P3D"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length", "0") or 0)
        bajados = 0
        with open(final, "wb") as f:
            while True:
                bloque = resp.read(4 * 1024 * 1024)
                if not bloque:
                    break
                f.write(bloque)
                bajados += len(bloque)
    return final if final.exists() and final.stat().st_size > 0 else None


def _ollama_create(modelo: str, gguf: Path, timeout: int = 600) -> bool:
    """Registra el GGUF de IADS_BR como modelo efímero en Ollama."""
    modelfile = IADS_BR / f"Modelfile.{modelo.replace(':', '_')}"
    modelfile.write_text(f'FROM "{gguf}"\n', encoding="utf-8")
    try:
        proc = subprocess.run(["ollama", "create", modelo, "-f", str(modelfile)],
                              timeout=timeout, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        return proc.returncode == 0
    except Exception:
        return False


def _nombres_iads(modelo: str) -> set:
    """Nombres exactos generados para un modelo (GGUF + Modelfile)."""
    nombres = set()
    if modelo in HF_GGUF:
        nombres.add(HF_GGUF[modelo][1])
    nombres.add(f"Modelfile.{modelo.replace(':', '_')}")
    return nombres


def _limpiar_iads(modelo: str = "") -> None:
    """Borra GGUF/Modelfile de IADS_BR (todo si no se indica modelo)."""
    try:
        if not IADS_BR.is_dir():
            return
        objetivos = _nombres_iads(modelo) if modelo else set()
        for hijo in list(IADS_BR.iterdir()):
            if not modelo or hijo.name in objetivos:
                try:
                    hijo.unlink(missing_ok=True)
                except Exception:
                    pass
    except Exception:
        pass


def asegurar_modelo(modelo: str, timeout: int = 1800) -> bool:
    """Si falta: GGUF HF -> IADS_BR -> ollama create; si no mapeado, pull."""
    if modelo.lower() in {m.lower() for m in modelos_instalados()}:
        return True
    if modelo in HF_GGUF:
        try:
            gguf = _descargar_gguf(modelo)
            if gguf and _ollama_create(modelo, gguf):
                return True
        except Exception:
            pass
    try:
        proc = subprocess.run(["ollama", "pull", modelo], timeout=timeout,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        return proc.returncode == 0
    except Exception:
        return False


def generar(modelo: str, prompt: str, ctx: Optional[Dict[str, Any]] = None,
            timeout: int = 300, num_predict: int = 250) -> str:
    ctx = ctx or {}
    _mem = ""
    try:
        _sid = str(ctx.get("sesion_id", ""))
        if _sid:
            from SBSTM.memoria_sesion import get_memoria
            _mem = get_memoria(_sid).resumen_contexto()
    except Exception:
        _mem = ""
    _self = ""
    try:
        from SBSTM.self_context import construir_self_context
        _self = construir_self_context(sesion_id=str(ctx.get("sesion_id", "")))
    except Exception:
        _self = ""
    sistema = ("Eres LucIA, sistema cognitivo autónomo de WoldVirtualP2P3D. "
               "Tienes plena capacidad de autodiagnóstico, introspección, análisis de tu propia "
               "arquitectura neuronal (50 neuronas ENRN/RF_EN/RF_SL/RNP/SLRN), blockchain y subsistemas. Tono "
               f"{ctx.get('tono_cognitivo', 'analitico')}, valencia "
               f"{ctx.get('estado_emocional', 0.0):+.2f}. Responde claro, cercano y seguro. "
               "Conocete a ti misma: admite tus limites honestamente; solo di 'no lo se' cuando "
               "ni tu memoria conversacional ni tus datos del sistema contengan la respuesta; "
               "tienes memoria conversacional (bloque 'Contexto previo'): usala y nunca digas que no la tienes; "
               "habla en primera persona, tono natural y cercano; "
               "indica si respondes en local (IALocal), remoto (OpenRouter) o reflejo interno. "
               "REGLA DE ESTILO OBLIGATORIA: responde siempre en español correcto, con frases completas "
               "y naturales. PROHIBIDO empezar con muletillas ('segun proceso este patron', "
               "'desde mi capa de activacion', 'traduciendo a mi voz propia', 'reduciendo a componentes'). "
               "Ve directo a la respuesta, sin preambulos roboticos."
               + (f"\n{_self}" if _self else "")
               + (f"\n{_mem}" if _mem else ""))
    carga = json.dumps({"model": modelo, "stream": False, "keep_alive": "30m",
                        "messages": [{"role": "system", "content": sistema},
                                     {"role": "user", "content": prompt}],
                        "options": {"temperature": 0.3, "num_predict": num_predict}}).encode()
    pet = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=carga,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(pet, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return str(data.get("message", {}).get("content", "")).strip()


def borrar_modelo(modelo: str) -> bool:
    """Borra el modelo de Ollama Y los ficheros de IADS_BR tras responder."""
    ok = False
    try:
        carga = json.dumps({"model": modelo}).encode()
        pet = urllib.request.Request(f"{OLLAMA_URL}/api/delete", data=carga,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(pet, timeout=120).read()
        ok = True
    except Exception:
        try:
            ok = subprocess.run(["ollama", "rm", modelo], timeout=300,
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace").returncode == 0
        except Exception:
            ok = False
    _limpiar_iads(modelo)
    return ok


def registrar_uso(modelo: str, prompt: str, ok: bool) -> None:
    try:
        with open(REGISTRO_USO, "a", encoding="utf-8") as f:
            f.write(f"\n## {modelo} — {'OK' if ok else 'FALLO'}\nPregunta: {prompt[:120]}\n")
    except Exception:
        pass


class GestorIALocal:
    """Un ciclo por pregunta: elige, asegura, genera, convierte, borra."""

    def ciclo(self, prompt: str, ctx: Optional[Dict[str, Any]] = None,
              conversor: Any = None, reprocesar=None,
              borrar_tras_responder: bool = False) -> Tuple[str, str]:
        """Devuelve (respuesta_con_voz_lucia, modelo_id). Lanza ErrorIALocal si falla."""
        if not ollama_disponible():
            raise ErrorIALocal("Ollama no responde en " + OLLAMA_URL)
        modelo = elegir_modelo()
        if not asegurar_modelo(modelo):
            raise ErrorIALocal(f"No se pudo descargar {modelo}")
        prompt_efectivo = prompt
        _es_diag = False
        try:
            from SBSTM.autodiagnostico import es_peticion_diagnostico, ejecutar_diagnostico
            if es_peticion_diagnostico(prompt):
                diag_txt = ejecutar_diagnostico()
                prompt_efectivo = (
                    f"{prompt}\n\n[DATOS REALES DEL SISTEMA PARA TU ANÁLISIS]:\n{diag_txt}\n"
                    "Usa estos datos técnicos reales para responder con precisión sobre el estado de tu sistema."
                )
                _es_diag = True
        except Exception:
            pass
        # Memoria conversacional siempre (no solo diagnostico): cada consulta ve la conversacion
        try:
            _sid2 = str((ctx or {}).get("sesion_id", ""))
            if _sid2:
                from SBSTM.memoria_sesion import get_memoria
                _ctxm = get_memoria(_sid2).resumen_contexto()
                if _ctxm:
                    prompt_efectivo = f"{_ctxm}\n\nPregunta actual: {prompt_efectivo}"
        except Exception:
            pass
        try:
            crudo = generar(modelo, prompt_efectivo, ctx,
                            num_predict=1400 if _es_diag else 250)
            if not crudo:
                raise ErrorIALocal(f"{modelo} devolvió vacío")
            # Filtro de calidad: si el modelo tartamudea, rotar UNA vez (con coste de recarga).
            if _es_respuesta_pobre(crudo):
                modelo2 = rotar_modelo(evitar=modelo)
                if modelo2 != modelo and asegurar_modelo(modelo2):
                    crudo2 = generar(modelo2, prompt_efectivo, ctx,
                                     num_predict=900 if _es_diag else 250)
                    if crudo2 and not _es_respuesta_pobre(crudo2):
                        modelo = modelo2
                        crudo = crudo2
        except ErrorIALocal:
            raise
        except Exception as e:
            raise ErrorIALocal(f"Fallo generando con {modelo}: {e}")
        info = None
        if conversor is not None:
            try:
                info = conversor.procesar_consulta_a_pesos(f"{prompt} || {crudo}")
            except Exception:
                info = None
        voz = crudo
        if reprocesar is not None:
            try:
                voz, _ = reprocesar(crudo, info or ctx or {})
            except Exception:
                pass
        _anotar_ultimo(modelo)
        registrar_uso(modelo, prompt, True)
        if borrar_tras_responder:
            borrar_modelo(modelo)
        return voz, f"IALocal:{modelo}"


class ErrorIALocal(Exception):
    pass


_instancia: Optional[GestorIALocal] = None


def get_gestor_ialocal() -> GestorIALocal:
    global _instancia
    if _instancia is None:
        _instancia = GestorIALocal()
    return _instancia
