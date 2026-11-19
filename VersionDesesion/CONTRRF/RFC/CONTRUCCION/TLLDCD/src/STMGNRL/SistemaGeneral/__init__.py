"""STMGNRL SistemaGeneral"""
import os
import sys
from pathlib import Path

# [ES] Confinamiento de Bytecode hacia .dev/pycache
# [EN] Bytecode confinement into .dev/pycache
_DEV_PYCACHE = Path(__file__).resolve().parents[4] / ".dev" / "pycache"
try:
    _DEV_PYCACHE.mkdir(parents=True, exist_ok=True)
    sys.pycache_prefix = str(_DEV_PYCACHE)
    os.environ["PYTHONPYCACHEPREFIX"] = str(_DEV_PYCACHE)
except Exception:
    pass
