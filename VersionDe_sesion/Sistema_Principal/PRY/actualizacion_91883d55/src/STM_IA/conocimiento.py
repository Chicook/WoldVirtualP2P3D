"""Base de conocimiento especifico para LucIA (STM_IA).

Documentos .md/.json en STM_IA/conocimiento/.
Busqueda por palabras clave con puntuacion simple, sin dependencias.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

CONOCIMIENTO_DIR: Path = Path(__file__).resolve().parent / "conocimiento"

_STOP = frozenset(
    "el la los las un una de del en y o que se su con por para como mas "
    "pero sus este esta estos estas ese esa eso aqui hay son fue eran "
    "the and for with from".split()
)


def _tokens(texto: str) -> List[str]:
    toks = re.findall(r"[a-záéíóúñü0-9]{3,}", (texto or "").lower())
    return [t for t in toks if t not in _STOP]


def palabras_clave(texto: str, top_n: int = 5) -> List[str]:
    """Palabras clave de un texto, ordenadas por frecuencia."""
    conteo: Dict[str, int] = {}
    for t in _tokens(texto):
        conteo[t] = conteo.get(t, 0) + 1
    return sorted(conteo, key=lambda k: conteo[k], reverse=True)[: max(1, top_n)]


_DOCS_CACHE: List[Dict[str, Any]] = []
_DOCS_MTIME_HASH: float = 0.0


def _obtener_mtime_total() -> float:
    if not CONOCIMIENTO_DIR.exists():
        return 0.0
    mt = 0.0
    try:
        for p in CONOCIMIENTO_DIR.rglob("*"):
            if p.is_file() and p.suffix in (".md", ".json"):
                mt += p.stat().st_mtime
    except Exception:
        pass
    return mt


def _cargar_documentos() -> List[Dict[str, Any]]:
    global _DOCS_CACHE, _DOCS_MTIME_HASH
    mtime_actual = _obtener_mtime_total()
    if _DOCS_CACHE and mtime_actual == _DOCS_MTIME_HASH:
        return _DOCS_CACHE

    docs: List[Dict[str, Any]] = []
    if not CONOCIMIENTO_DIR.exists():
        return docs
    for p in sorted(CONOCIMIENTO_DIR.rglob("*")):
        if not p.is_file() or p.suffix not in (".md", ".json"):
            continue
        try:
            if p.suffix == ".json":
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    txt = str(data.get("texto", ""))
                    docs.append({
                        "fuente": str(p.relative_to(CONOCIMIENTO_DIR)),
                        "titulo": str(data.get("titulo", p.stem)),
                        "texto": txt,
                        "tokens": set(_tokens(txt)),
                    })
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("texto"):
                            txt = str(item.get("texto", ""))
                            docs.append({
                                "fuente": str(p.relative_to(CONOCIMIENTO_DIR)),
                                "titulo": str(item.get("titulo", p.stem)),
                                "texto": txt,
                                "tokens": set(_tokens(txt)),
                            })
            else:
                texto = p.read_text(encoding="utf-8", errors="replace")
                titulo = p.stem
                for linea in texto.splitlines()[:5]:
                    if linea.startswith("#"):
                        titulo = linea.lstrip("# ").strip() or titulo
                        break
                docs.append({
                    "fuente": str(p.relative_to(CONOCIMIENTO_DIR)),
                    "titulo": titulo,
                    "texto": texto,
                    "tokens": set(_tokens(texto)),
                })
        except Exception:
            continue
    _DOCS_CACHE = docs
    _DOCS_MTIME_HASH = mtime_actual
    return _DOCS_CACHE


def buscar(consulta: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Devuelve los top_k fragmentos mas relevantes con fuente y puntuacion."""
    q = _tokens(consulta)
    if not q:
        return []
    q_set = set(q)
    resultados: List[Dict[str, Any]] = []
    for doc in _cargar_documentos():
        toks = doc.get("tokens")
        if toks is None:
            toks = set(_tokens(doc.get("texto", "")))
            doc["tokens"] = toks
        coincid = len(q_set & toks)
        if not coincid:
            continue
        resultados.append({
            "fuente": doc["fuente"],
            "titulo": doc["titulo"],
            "fragmento": doc["texto"][:500],
            "puntuacion": round(coincid / len(q_set), 3),
        })
    resultados.sort(key=lambda r: r["puntuacion"], reverse=True)
    return resultados[: max(1, top_k)]


def contexto_para_prompt(consulta: str, top_k: int = 2) -> str:
    """Texto listo para anteponer al prompt del modelo, con fuentes."""
    res = buscar(consulta, top_k=top_k)
    if not res:
        return ""
    partes = ["Conocimiento relevante:"]
    for r in res:
        partes.append(f"- [{r['titulo']} | {r['fuente']}]: {r['fragmento'][:300]}")
    return "\n".join(partes)


def listar_fuentes() -> List[str]:
    return sorted({d["fuente"] for d in _cargar_documentos()})
