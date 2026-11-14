# Hoja de ruta de modularidad — `src/LC_STM/RedNeuronal`

**Fecha:** 2026-11-13  
**Ámbito:** `VersionDe_sesion/CONTRRF/CONTRUCCION/Refactorizacion/src/LC_STM/RedNeuronal`  
**Estado:** cierre de la primera tanda de modularización de `RF_SL` (1_1, 1_2 y 1_3) y guía para las siguientes importaciones.  
**Regla de oro:** este documento es una guía; no autoriza por sí mismo a modificar módulos. Cada intervención debe limitarse al archivo acordado y declarar su alcance.

---

## 0. Resumen ejecutivo

La refactorización de `RF_SL` ha consolidado un patrón que funciona:

1. **Un módulo especializado autocontenido** por familia algorítmica (`RF_SL_SBRTM_RF_SL1_x/RF_SL_SBRTM_RF_SL1_x_1.py`).
2. **Un módulo puente legado** (`RFSL1/RF_SL1_x.py`) que importa la implementación nueva y conserva la API histórica.
3. **Una base compartida** (`RF_SL_SBRTM_RF_rfsl_base/RF_SL_SNRTM__rfsl_base1.py`) importada, nunca redefinida.
4. **Fallbacks de importación por ruta** para que los módulos funcionen como script, por ruta, como paquete de primer nivel y como subpaquete profundo.
5. **Verificación numérica y de contrato** antes de dar un módulo por terminado.

Las siguientes importaciones deben repetir este patrón, no improvisar uno nuevo. La deuda pendiente más importante es terminar `RF_SL1_4`…`RF_SL1_10`, ordenar las referencias a la carpeta base renombrada y convertir estas verificaciones en tests automáticos.

---

## 1. Objetivos de la modularidad

| Objetivo | Criterio medible |
|---|---|
| Fuente única de verdad | Cada clase/función compartida se define una sola vez |
| Compatibilidad | `RFSL1.RF_SL1_x` expone la misma API pública que antes |
| Importabilidad | El módulo funciona como script, por ruta, top-level y paquete profundo |
| Aislamiento | Un módulo especializado no importa módulos de proyecto, solo stdlib + NumPy |
| Determinismo | Semillas explícitas; misma entrada + semilla ⇒ misma salida |
| Verificabilidad | Sintaxis, import, ajuste, predicción, serialización y estabilidad comprobados |
| Trazabilidad | Docstring, versión, dependencias y limitaciones declaradas |
| Reversibilidad | Un cambio se puede revertir sin tocar consumidores |

---

## 2. Principios rectores

### 2.1. Fuente única de verdad (SSOT)

Una clase compartida vive en **un** archivo. Los demás la importan.

- Correcto: `RFSL1/RF_SL1_2.py` importa `SupportVectorMachineOptimizer` desde `RF_SL_SBRTM_RF_SL1_2`.
- Incorrecto: volver a pegar la clase con pequeñas variaciones.

### 2.2. Dependencias en una sola dirección

```
RF_SL_SBRTM_RF_rfsl_base        (nivel 0: sin dependencias de proyecto)
        ▲
        │
RF_SL_SBRTM_RF_SL1_x            (nivel 1: importa base)
        ▲
        │
RFSL1/RF_SL1_x                  (nivel 2: importa módulo especializado)
        ▲
        │
RFSL1/__init__.py               (nivel 3: fachada del paquete)
```

Nunca un módulo de nivel 0 importa uno de nivel 2. Nunca un `__init__` importa a un consumidor suyo.

### 2.3. Módulos hoja autocontenidos

Los módulos `RF_SL_SBRTM_RF_*/…_1.py` deben poder importarse sin el resto del proyecto:

- Solo `numpy`, `logging`, `math`, `pickle`, `time`, `typing`, `collections`.
- La base se importa con fallback; si no existe, una base local mínima de último recurso.
- Nada de imports de `RFSL1`, `RF_EN`, `ENRN`, etc.

### 2.4. Compatibilidad hacia atrás

El módulo puente conserva:

- nombre de clase,
- firma del constructor,
- métodos públicos,
- atributos “privados” usados históricamente (`_kernel_type`, `_trees`, `_n_trees`, `_oob_score`, `_is_fitted`, `_convergence_history`, `_timer_train`…).

La implementación puede cambiar; el contrato no.

### 2.5. Fallback explícito, nunca silencioso

Todo fallback debe:

- intentar primero la vía normal (import relativo),
- caer a carga por ruta solo si el contexto lo exige,
- registrar/dejar rastro cuando sea un error real,
- no tragarse excepciones de lógica (solo `ImportError`/`ValueError` de contexto).

### 2.6. Determinismo y semillas

- `seed` explícito en constructores.
- `np.random.default_rng(seed)`, no `np.random.*` global.
- Los tests comparan dos ejecuciones con la misma semilla.
- Las particiones train/validación usan el RNG interno.

### 2.7. Validación en la frontera

Todo método público que recibe datos valida:

- `X` 2D, no vacío, mismo número de features,
- `y` con longitud correcta y forma coherente (1D/2D, ±1 o etiquetas),
- `NaN`/`Inf` tratados o rechazados de forma explícita,
- dimensiones de parámetros coherentes con el modelo.

### 2.8. API pequeña y documentada

Cada clase expone lo necesario y documenta:

- propósito,
- parámetros,
- formas de entrada/salida,
- algoritmo,
- limitaciones,
- ejemplo mínimo.

### 2.9. Pruebas antes que “ya funciona”

Un módulo no se considera terminado porque importe. Debe pasar la matriz de pruebas de la sección 11.

### 2.10. Cambios pequeños y verificables

Una intervención = un archivo = un objetivo. Si hay que tocar otro archivo, se declara y se justifica antes.

---

## 3. Mapa de arquitectura actual

```
RedNeuronal/
├── CELEBRO/                      (pendiente de revisión)
├── ENRN/                         (neuronas de entrada; patrón SBRTM_IMPORT)
├── RF_EN/                        (refuerzo; patrón SBRTM)
└── RF_SL/
    ├── RFSL1/                    (fachada legada: 10 optimizadores)
    │   ├── __init__.py
    │   ├── _rfsl_base.py
    │   ├── RF_SL1_1.py           ✅ importa SL1_1
    │   ├── RF_SL1_2.py           ✅ importa SL1_2
    │   ├── RF_SL1_3.py           ✅ importa SL1_3
    │   └── RF_SL1_4.py … 1_10    ⏳ pendientes
    ├── RF_SL_SBRTM_IMPORT/
    │   └── RF_SL_SBRTM__init__1.py   (utilidades + neuronas de importación)
    ├── RF_SL_SBRTM_RF_rfsl_base/
    │   └── RF_SL_SNRTM__rfsl_base1.py (base + árbol + neuronas genéricas)
    ├── RF_SL_SBRTM_RF_SL1_1/     ✅ Gradient Boosting
    ├── RF_SL_SBRTM_RF_SL1_2/     ✅ SVM / kernels
    ├── RF_SL_SBRTM_RF_SL1_3/     ✅ Random Forest + TabM
    └── (futuras) RF_SL_SBRTM_RF_SL1_4 … SL1_10
```

### 3.1. Nota sobre renombrados

La carpeta base pasó de `RF_SL_SBRTM_RF` a `RF_SL_SBRTM_RF_rfsl_base`. Mientras queden referencias al nombre antiguo:

- los módulos nuevos deben apuntar al nombre nuevo,
- los fallbacks pueden probar ambos nombres,
- `RF_SL1_1.py` registra un alias temporal (`RF_SL_SBRTM_RF` → `RF_SL_SBRTM_RF_rfsl_base`) para no romper `_rfsl_base.py`,
- el alias es **deuda técnica**: debe desaparecer cuando `_rfsl_base.py` apunte al nombre definitivo.

---

## 4. Capas, responsabilidades y contratos

### 4.1. Nivel 0 — Base compartida

**Archivo:** `RF_SL_SBRTM_RF_rfsl_base/RF_SL_SNRTM__rfsl_base1.py`

Responsabilidades:

- `NeuronaMemoriaBase` y utilidades de memoria/estadísticas.
- Primers numéricos comunes (`TreeBuilder`, `OptimizadorAdam` si aplica).
- Cero imports de proyecto.
- Cero efectos secundarios al importar (no entrenar, no leer ficheros, no configurar logging global).

Contrato:

- No cambiar firmas existentes sin versión mayor.
- Cualquier clase nueva debe ser genérica, no específica de un optimizador.

### 4.2. Nivel 1 — Módulo especializado

**Archivo:** `RF_SL_SBRTM_RF_SL1_x/RF_SL_SBRTM_RF_SL1_x_1.py`

Responsabilidades:

- Implementación real del algoritmo.
- Varias neuronas especializadas si aportan valor (p. ej. SVM dual / RFF / Nyström; bosque / TabM).
- Funciones de fábrica, evaluación, benchmark y serialización.
- Docstring con algoritmo, referencias y limitaciones.

Contrato:

- `input_size`, `output_size`, `nombre`, `seed` como mínimo.
- Métodos: `fit`, `predict`, `evaluate`, `params_count`, `obtener_estadisticas`, `verificar_estabilidad`, `save`, `load`.
- `__all__` explícito.
- `demo()` ejecutable con `python módulo.py`.
- No importa `RFSL1` ni otros consumidores.

### 4.3. Nivel 2 — Módulo puente legado

**Archivo:** `RFSL1/RF_SL1_x.py`

Responsabilidades:

- Importar la implementación nueva.
- Exponer el nombre histórico (`GradientBoostingOptimizer`, `SupportVectorMachineOptimizer`, `RandomForestOptimizer`…).
- Conservar métodos/atributos usados por consumidores.
- No reimplementar el algoritmo.

Contrato:

- Si se sustituye un rango de líneas, el archivo debe seguir compilando y importando.
- Si quedan métodos huérfanos de una clase, se conserva una **subclase** con el mismo nombre.
- `save/load` deben serializar el modelo completo, no solo el estado lineal antiguo.
- `evaluate` puede delegar en la implementación nueva si devuelve un superconjunto de claves.

### 4.4. Nivel 3 — Fachada de paquete

**Archivo:** `RFSL1/__init__.py`

Responsabilidades:

- Importar optimizadores y utilidades compartidas.
- Exponer `__all__`.
- No definir clases de algoritmo.

Regla: si una utilidad ya vive en `RF_SL_SBRTM_IMPORT`, se importa; no se redefine.

---

## 5. Convenciones de nombres

| Elemento | Convención | Ejemplo |
|---|---|---|
| Carpeta especializada | `RF_SL_SBRTM_RF_SL{optimizador}` | `RF_SL_SBRTM_RF_SL1_4` |
| Módulo especializado | `RF_SL_SBRTM_RF_SL{optimizador}_1.py` | `RF_SL_SBRTM_RF_SL1_4_1.py` |
| Módulo puente | `RF_SL1_{n}.py` | `RF_SL1_4.py` |
| Clase principal | `Neurona<Algoritmo>` | `NeuronaSVMNucleo` |
| Adaptador legado | `<NombreHistorico>Optimizer` | `RandomForestOptimizer` |
| Base | `NeuronaMemoriaBase` | — |
| Fábrica | `crear_neurona(tipo, ...)` | — |
| Serialización | `guardar_modelo` / `cargar_modelo` | — |
| Demo | `demo()` | — |
| Versión | `__version__ = "2026.x.y"` | — |

Reglas:

- Sin acentos ni `ñ` en nombres de archivo.
- Nombres de clase en PascalCase; funciones y variables en snake_case.
- Evitar sufijos ambiguos (`_v2`, `_nuevo`, `_final`); usar versión del módulo.
- Un módulo = una familia algorítmica; no mezclar SVM con boosting.

---

## 6. Plantillas de archivos

### 6.1. Cabecera de módulo especializado

```python
"""RF_SL_SBRTM_RF_SL1_4_1.py
Neuronas especializadas en <algoritmo> (RF_SL · SBRTM · RF · 2026).
=============================================================================

<Qué implementa, qué mejora respecto al módulo legado, algoritmos usados>

Referencias
-----------
- <paper/repositorio 1>
- <paper/repositorio 2>

Uso
---
    from RF_SL_SBRTM_RF_SL1_4_1 import NeuronaX

    modelo = NeuronaX(input_size=4, output_size=1)
    modelo.fit(X, y)
    print(modelo.evaluate(X, y))
"""

from __future__ import annotations

import logging
import math
import pickle
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)
__version__ = "2026.1.0"
```

### 6.2. Constantes de configuración

```python
LUCIA_RF_CONFIG: Dict[str, Any] = {
    "precision": "float64",
    "random_seed": 2026,
    "learning_rate": 0.01,
    "epochs": 100,
    "batch_size": 64,
}
```

- Un solo diccionario por módulo.
- No mutarlo desde fuera; los constructores copian valores.
- Documentar unidades y rangos.

### 6.3. Base importada con fallback

```python
try:
    from ..RF_SL_SBRTM_RF_rfsl_base.RF_SL_SNRTM__rfsl_base1 import (
        NeuronaMemoriaBase,
    )
except (ImportError, ValueError):
    import importlib.util as _ilu
    import os as _os
    import sys as _sys

    _CLAVE = "_rf_snrtm_base_import"
    _mod = _sys.modules.get(_CLAVE)
    if _mod is None:
        _dir_rf_sl = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        for _carpeta in ("RF_SL_SBRTM_RF_rfsl_base", "RF_SL_SBRTM_RF"):
            _ruta = _os.path.join(_dir_rf_sl, _carpeta,
                                  "RF_SL_SNRTM__rfsl_base1.py")
            if not _os.path.exists(_ruta):
                continue
            _spec = _ilu.spec_from_file_location(_CLAVE, _ruta)
            if _spec is None or _spec.loader is None:
                continue
            _mod = _ilu.module_from_spec(_spec)
            _sys.modules[_CLAVE] = _mod
            _spec.loader.exec_module(_mod)
            break
    if _mod is None:
        raise ImportError("No se encontró la base RF_SL_SBRTM_RF_rfsl_base")
    NeuronaMemoriaBase = _mod.NeuronaMemoriaBase
```

Reglas:

- Cachear por clave en `sys.modules`.
- Probar primero el nombre nuevo de carpeta y después el antiguo.
- Si no se encuentra, **fallar con mensaje claro**; no continuar con una base inventada salvo que el módulo sea de nivel 0.

### 6.4. Módulo puente legado

```python
try:
    from ..RF_SL_SBRTM_RF_SL1_4.RF_SL_SBRTM_RF_SL1_4_1 import (
        NeuronaX,
        XOptimizer as _XOptimizerBase,
        cargar_modelo,
        crear_neurona,
        guardar_modelo,
    )
except (ImportError, ValueError):
    # Carga por ruta (script / top-level / spec)
    ...


class XOptimizer(_XOptimizerBase):
    """API histórica de RF_SL1_4 sobre la implementación nueva."""

    # Solo métodos/atributos de compatibilidad; no reimplementar el algoritmo.
```

### 6.5. `__all__`

```python
__all__ = [
    "NeuronaMemoriaBase",
    "NeuronaX",
    "XOptimizer",
    "crear_neurona",
    "guardar_modelo",
    "cargar_modelo",
    "demo",
    "LUCIA_RF_CONFIG",
]
```

Regla: todo nombre de `__all__` debe existir; test obligatorio.

### 6.6. Demo

```python
if __name__ == "__main__":  # pragma: no cover
    demo()
```

- `demo()` no debe requerir argumentos.
- Debe terminar con `exit 0`.
- Salida en ASCII para evitar problemas de consola Windows.
- Tiempo objetivo: menos de 15-20 s.

---

## 7. Patrones de importación

### 7.1. Orden de intentos

Para cualquier import de proyecto:

1. Import relativo correcto (`from ..X.Y import Z`).
2. Carga por ruta con `importlib.util.spec_from_file_location`.
3. Solo si el módulo es la base mínima: definición local de emergencia.

Nunca:

- `sys.path.append` permanente sin comprobar duplicados,
- cargar el mismo archivo dos veces con nombres distintos sin cachear,
- silenciar `ImportError` sin registrar/dejar rastro.

### 7.2. Import por ruta: claves únicas

Usar claves estables y específicas:

```python
_CLAVE = "_rf_sl1_4_import"
```

Evitar nombres genéricos (`"modulo"`, `"base"`, `"x"`) que puedan colisionar en `sys.modules`.

### 7.3. Script / top-level

Si el archivo se ejecuta como script o se importa sin paquete padre:

- registrar un paquete sintético (`RF_SL`, `RF_SL.RFSL1`) con `__path__`,
- asignar `__package__` y `__path__`,
- registrar el módulo actual como paquete,
- añadir la carpeta padre a `sys.path`.

Patrón ya aplicado en `RFSL1/__init__.py` y `RFSL1/RF_SL1_1.py`.

### 7.4. Import circular

Reglas:

- El nivel superior no importa al inferior.
- La base no importa a nadie.
- Si A importa B y B importa A, mover la parte compartida a un tercer módulo.
- Si es inevitable, usar import perezoso dentro de la función, nunca a nivel de módulo.
- Documentar el ciclo y por qué existe.

### 7.5. Alias por carpeta renombrada

Mientras exista deuda de nombres:

- registrar el alias en `sys.modules` antes del import problemático,
- apuntar el alias al `__path__` nuevo,
- precargar el submódulo para compartir la misma clase,
- marcar el alias con `# TODO(deuda): eliminar cuando ...`.

---

## 8. Procedimiento para sustituir un rango de líneas

Este es el procedimiento que se ha seguido y debe repetirse.

### Paso 0 — Inventario

- Leer el archivo completo.
- Localizar el rango exacto y comprobar que empieza/termina en fronteras lógicas.
- Identificar si el rango deja métodos huérfanos (clase que continúa).
- Localizar consumidores (`grep` de la clase/función).

### Paso 1 — Diseñar el destino

- Decidir si se sustituye por:
  - import + clase alias,
  - import + subclase de compatibilidad,
  - solo import (si no quedan métodos).
- Si quedan métodos dentro de una clase, **siempre** dejar una cabecera de clase que los reciba.

### Paso 2 — Escribir el bloque

- Import con fallback.
- Cabecera de clase si aplica.
- Comentario que explique qué se elimina y por qué.
- No dejar imports sin usar si se pueden evitar.

### Paso 3 — Preservar el resto

- Copiar el resto del archivo **literalmente**.
- No reindentar métodos que ya estaban indentados.
- No cambiar nombres de clases auxiliares.
- No eliminar clases no relacionadas.

### Paso 4 — Verificar sintaxis

```powershell
python -m py_compile RFSL1/RF_SL1_4.py
```

O en memoria:

```python
compile(open(ruta, encoding="utf-8").read(), ruta, "exec")
```

### Paso 5 — Verificar importación

- paquete profundo,
- paquete RFSL1 completo,
- top-level (`sys.path = RF_SL`),
- carga por ruta (`spec_from_file_location`),
- ejecución como script.

### Paso 6 — Verificar comportamiento

- instanciar,
- `fit` con datos sintéticos,
- `predict` / `predict_proba`,
- `evaluate`,
- `save`/`load` en instancia nueva,
- `params_count`, `obtener_estadisticas`, `verificar_estabilidad`.

### Paso 7 — Verificar no duplicación

```python
assert "class NeuronaMemoriaBase" not in src
assert "class SupportVectorMachineOptimizer" not in src
```

Y escaneo AST de nombres duplicados.

### Paso 8 — Verificar consumidores

- `RFSL1/__init__.py`
- `build_model("...")`
- `train_all_models` si aplica
- SBRTM si importa el módulo

### Paso 9 — Documentar

- Añadir la entrada al registro de cambios (sección 23).
- Actualizar la tabla de estado (sección 19).

---

## 9. Compatibilidad y deprecación

### 9.1. Reglas de compatibilidad

| Elemento | Se puede cambiar | Requiere adaptador |
|---|---|---|
| Nombre de clase pública | No | Sí |
| Firma del constructor | No sin versión mayor | Sí |
| Método público | No eliminar | Sí |
| Atributo privado usado fuera | No sin aviso | Sí |
| Tipo de retorno | No sin aviso | Sí |
| `__all__` | Añadir sí; quitar no | Sí |

### 9.2. Deprecación

Cuando un método deba desaparecer:

1. Mantenerlo funcionando.
2. Añadir `warnings.warn(..., DeprecationWarning, stacklevel=2)`.
3. Documentar la alternativa.
4. Fijar una versión objetivo de eliminación.
5. Solo entonces eliminarlo.

### 9.3. Métodos lineales heredados

En clases como `RandomForestOptimizer` o `SupportVectorMachineOptimizer` existen métodos históricos (`backward`, `update_weights`, `apply_gradient`, `train_step`) que ya no gobiernan el modelo real.

Regla:

- Se conservan por compatibilidad.
- Deben documentar que son una capa heredada.
- No deben usarse para afirmar que el modelo entrena por gradiente si no es cierto.
- Si se puede, delegar en la implementación real o devolver un resultado coherente.

---

## 10. Contratos de calidad numérica

### 10.1. Gradientes

Si el modelo entrena por retropropagación:

- comprobar gradiente analítico vs diferencias finitas,
- error relativo < `1e-5` (objetivo `1e-7`),
- probar al menos una perturbación por parámetro,
- guardar el test en el módulo de pruebas o en el script de verificación.

### 10.2. Estabilidad

- Comprobar `np.isfinite` en parámetros y predicciones.
- Evitar divisiones por cero (`np.maximum(..., eps)`).
- Evitar `exp` de valores grandes (clip).
- Documentar el rango esperado de `gamma`, `C`, `learning_rate`, etc.

### 10.3. Reproducibilidad

- Misma semilla ⇒ mismos resultados numéricos (tolerancia `1e-10`).
- No usar `np.random` global.
- No depender del orden de `dict` no ordenado.

### 10.4. Rendimiento

- Evitar bucles Python sobre muestras cuando exista una operación vectorizada.
- Para kernels, cachear la matriz Gram si `n` es pequeño.
- Para datasets grandes, ofrecer una vía aproximada (RFF, Nyström, submuestreo).
- Medir con `benchmark_modelo` antes de declarar una mejora.

---

## 11. Matriz de pruebas obligatoria

Cada módulo nuevo debe pasar, como mínimo:

| # | Prueba | Criterio |
|---|---|---|
| 1 | Sintaxis | `compile` sin errores |
| 2 | Import paquete profundo | OK |
| 3 | Import top-level | OK |
| 4 | Import por ruta (`spec`) | OK |
| 5 | Ejecución como script | `exit 0` |
| 6 | `__all__` | Todos los nombres existen |
| 7 | Sin definiciones duplicadas | Escaneo AST |
| 8 | `fit` | Sin excepciones |
| 9 | `predict` forma correcta | `(n,)`, `(n,1)` o `(n,C)` según contrato |
| 10 | `evaluate` | Métricas finitas y razonables |
| 11 | `save`/`load` | Predicciones idénticas en instancia nueva |
| 12 | `params_count` | Entero ≥ 0 |
| 13 | `obtener_estadisticas` | Diccionario con claves documentadas |
| 14 | `verificar_estabilidad` | `estable is True` o problemas justificados |
| 15 | Determinismo | Dos ejecuciones con misma semilla |
| 16 | Entradas inválidas | `ValueError`/`RuntimeError` claro |
| 17 | Un solo registro | Clases no definidas en el puente |
| 18 | Consumidores | `build_model` y paquete funcionan |

### 11.1. Script de importación (plantilla)

```python
import importlib.util
import sys

RUTA = r"...\RF_SL_SBRTM_RF_SL1_4_1.py"
spec = importlib.util.spec_from_file_location("m", RUTA)
m = importlib.util.module_from_spec(spec)
sys.modules["m"] = m
spec.loader.exec_module(m)
print(m.__version__, m.tipos_disponibles())
```

### 11.2. Script de comportamiento (plantilla)

```python
import numpy as np

rng = np.random.default_rng(0)
X = rng.normal(size=(100, 3))
y = (X @ np.array([1.0, -2.0, 0.5])).reshape(-1, 1)

modelo = crear_neurona("tipo", input_size=3, output_size=1, seed=7)
modelo.fit(X, y)
met = modelo.evaluate(X, y)
assert np.isfinite(met["mse"])
assert modelo.params_count() >= 0
```

### 11.3. Script de serialización (plantilla)

```python
import os
import numpy as np

ruta = "modelo_tmp.pkl"
try:
    modelo.save(ruta)
    otro = cargar_modelo(ruta)
    assert np.allclose(modelo.predict(X[:5]), otro.predict(X[:5]))
finally:
    if os.path.exists(ruta):
        os.remove(ruta)
```

---

## 12. Documentación mínima por módulo

Cada archivo debe incluir:

1. **Docstring de módulo** con:
   - propósito,
   - algoritmos,
   - referencias (si aplica),
   - ejemplo de uso,
   - limitaciones.
2. **Docstring de clase** con:
   - parámetros,
   - formas de entrada/salida,
   - supuestos.
3. **Docstrings de métodos públicos**.
4. **Comentarios** en decisiones no obvias (por qué cuantiles, por qué WSS3, por qué ridge).
5. **Registro de versión** (`__version__`).
6. **`__all__`**.

---

## 13. Logging y errores

### 13.1. Logging

- `logger = logging.getLogger(__name__)`.
- No configurar `basicConfig` dentro de módulos.
- `INFO` para hitos de entrenamiento; `DEBUG` para detalles.
- No loguear dentro de bucles de gradiente por defecto.

### 13.2. Errores

| Situación | Excepción |
|---|---|
| Datos con forma incorrecta | `ValueError` |
| Modelo no ajustado | `RuntimeError` |
| Configuración incompatible | `ValueError` |
| Fichero inexistente al cargar | `FileNotFoundError` |
| Import de base no disponible | `ImportError` con ruta |
| Cálculo numérico singular | resolver con `lstsq`/ridge; si no, `RuntimeError` |

Nunca devolver `NaN` silencioso; si se detecta, lanzar o sanear explícitamente.

---

## 14. Serialización y versionado

### 14.1. Serialización

- `save`/`load` deben serializar el **modelo completo**, no solo hiperparámetros.
- Usar `pickle` con `protocol=pickle.HIGHEST_PROTOCOL`.
- Validar con `isinstance` al cargar.
- No serializar objetos no serializables (lambdas, generadores, conexiones).

### 14.2. Versionado

- `__version__` semántico: `2026.MAYOR.MENOR`.
- Cambio de contrato ⇒ subir mayor.
- Nueva neurona o mejora compatible ⇒ subir menor.
- Documentar en el registro de cambios (sección 23).

---

## 15. Revisión antes de terminar (checklist)

### Archivo especializado

- [ ] Docstring completo y `__version__`.
- [ ] Solo stdlib + NumPy.
- [ ] Base importada con fallback.
- [ ] Validación de entrada.
- [ ] Determinismo con `seed`.
- [ ] `__all__` correcto.
- [ ] Demo ejecutable.
- [ ] `save`/`load` completos.
- [ ] Pruebas de la sección 11 ejecutadas.

### Archivo puente

- [ ] Importa la implementación nueva (con fallback).
- [ ] No redefine el algoritmo.
- [ ] Conserva nombre, constructor, métodos y atributos históricos.
- [ ] Si quedan métodos de clase, hay subclase con el mismo nombre.
- [ ] `save`/`load` serializan el modelo completo.
- [ ] `evaluate` devuelve superconjunto o delega.
- [ ] `build_model` y consumidores funcionan.
- [ ] Sin duplicados locales.

### Paquete

- [ ] `__init__` importa sin ciclos.
- [ ] `__all__` resuelve.
- [ ] Import completo del paquete probado.
- [ ] No hay definiciones de algoritmo en `__init__`.

---

## 16. Hoja de ruta por fases

### Fase 0 — Congelación e inventario (0,5 día)

- [ ] Listar todos los módulos de `RFSL1` y su estado.
- [ ] Identificar consumidores por clase.
- [ ] Anotar deuda técnica (carpeta base, alias, imports antiguos).

**Salida:** tabla de estado (sección 19) actualizada.

### Fase 1 — Saneamiento de base (0,5 día)

- [ ] Decidir el nombre definitivo de la carpeta base.
- [ ] Actualizar `_rfsl_base.py` a ese nombre.
- [ ] Eliminar el alias temporal de `RF_SL1_1.py`.
- [ ] Verificar `RFSL1` completo y SBRTM.

**Riesgo:** alto si se toca sin probar; hacerlo en un solo commit pequeño.

### Fase 2 — Completar optimizadores RF_SL (5-8 días)

Orden recomendado, de menor a mayor complejidad:

| Orden | Legado | Carpeta destino | Notas |
|---|---|---|---|
| 1 | `RF_SL1_9.py` (Linear Regression) | `RF_SL_SBRTM_RF_SL1_9` | Base lineal, buen primer caso |
| 2 | `RF_SL1_8.py` (Logistic Regression) | `RF_SL_SBRTM_RF_SL1_8` | Clasificación binaria/multiclase |
| 3 | `RF_SL1_7.py` (KNN) | `RF_SL_SBRTM_RF_SL1_7` | Distancias, cache, aproximaciones |
| 4 | `RF_SL1_6.py` (Naive Bayes) | `RF_SL_SBRTM_RF_SL1_6` | Probabilidades, suavizado |
| 5 | `RF_SL1_5.py` (Decision Tree) | `RF_SL_SBRTM_RF_SL1_5` | Reutilizar `TreeBuilder`/CART |
| 6 | `RF_SL1_4.py` (Neural Network) | `RF_SL_SBRTM_RF_SL1_4` | MLP, optimizadores, regularización |
| 7 | `RF_SL1_10.py` (Integrated) | `RF_SL_SBRTM_RF_SL1_10` | Integra los anteriores; último |

Cada uno:

- [ ] Crear carpeta y módulo especializado.
- [ ] Implementar 1-3 neuronas y fábrica.
- [ ] Verificar con la matriz de pruebas.
- [ ] Sustituir el rango del puente legado.
- [ ] Probar consumidores.
- [ ] Actualizar estado y changelog.

### Fase 3 — Consolidar importaciones SBRTM (1-2 días)

- [ ] Revisar `RF_SL_SBRTM_IMPORT/RF_SL_SBRTM__init__1.py`.
- [ ] Evitar que `RFSL1/__init__.py` dependa de un módulo con lógica de importación pesada.
- [ ] Separar utilidades de modelos de las neuronas de importación.
- [ ] Documentar la API pública.

### Fase 4 — Pruebas automatizadas y CI (2-3 días)

- [ ] Convertir los scripts de verificación en tests (`pytest` o runner propio).
- [ ] Matriz de importación (paquete, top-level, ruta, script).
- [ ] Tests numéricos de gradientes.
- [ ] Tests de serialización.
- [ ] Test de determinismo.
- [ ] Umbral de cobertura acordado.

### Fase 5 — Extender el patrón a otras ramas (5-10 días)

- [ ] `ENRN` (neuronas de entrada).
- [ ] `RF_EN` (refuerzo).
- [ ] `CELEBRO` (base neuronal).
- [ ] Unificar convenciones de nombres y fallbacks.
- [ ] Evitar duplicar `NeuronaMemoriaBase` en cada rama.

### Fase 6 — Documentación y deprecación (2 días)

- [ ] Documentar API pública por rama.
- [ ] Marcar métodos obsoletos.
- [ ] Guía de migración para consumidores.
- [ ] Índice de módulos y ejemplos.

---

## 17. Priorización (impacto vs riesgo)

| Tarea | Impacto | Riesgo | Prioridad |
|---|---|---|---|
| Saneamiento carpeta base | Alto | Medio | P0 |
| `RF_SL1_9` y `1_8` | Alto | Bajo | P0 |
| `RF_SL1_7`, `1_6`, `1_5` | Medio | Bajo | P1 |
| `RF_SL1_4`, `1_10` | Alto | Medio | P1 |
| Tests automatizados | Alto | Bajo | P1 |
| Consolidar `SBRTM_IMPORT` | Medio | Medio | P2 |
| Extender a `RF_EN`/`ENRN` | Alto | Alto | P2 |
| Documentación final | Medio | Bajo | P3 |

---

## 18. Riesgos y mitigaciones

| Riesgo | Señal | Mitigación |
|---|---|---|
| Import circular | `ImportError` al importar paquete | Romper con base independiente o import perezoso |
| Duplicación silenciosa | Dos `class X` en el proyecto | Escaneo AST + revisión |
| Regresión de API | Consumidor falla | Matriz de compatibilidad + tests |
| Fallback que oculta errores | Todo “funciona” pero usa copia antigua | Logging + test de identidad de clase |
| Carpeta renombrada | `FileNotFoundError` | Probar ambos nombres y actualizar referencias |
| Serialización incompleta | `load` produce modelo no entrenado | Serializar objeto completo |
| Datos no deterministas | Resultados distintos con misma semilla | RNG local + tests |
| Lentitud | `fit` de minutos | Vectorizar, histogramas, aproximaciones |
| Métricas engañosas | `r2` alto con fuga de datos | Validación separada, OOB, CV |

---

## 19. Estado actual conocido

| Módulo legado | Módulo especializado | Estado | Observaciones |
|---|---|---|---|
| `RF_SL1_1.py` | `RF_SL_SBRTM_RF_SL1_1` | ✅ | Subclase + import; alias base temporal |
| `RF_SL1_2.py` | `RF_SL_SBRTM_RF_SL1_2` | ✅ | Import directo; `SVMClassifier` legado conservado |
| `RF_SL1_3.py` | `RF_SL_SBRTM_RF_SL1_3` | ✅ | Subclase; `save/load` completo |
| `RF_SL1_4.py` | — | ⏳ | Pendiente |
| `RF_SL1_5.py` | — | ⏳ | Pendiente |
| `RF_SL1_6.py` | — | ⏳ | Pendiente |
| `RF_SL1_7.py` | — | ⏳ | Pendiente |
| `RF_SL1_8.py` | — | ⏳ | Pendiente |
| `RF_SL1_9.py` | — | ⏳ | Pendiente |
| `RF_SL1_10.py` | — | ⏳ | Pendiente |
| `_rfsl_base.py` | `RF_SL_SBRTM_RF_rfsl_base` | ⚠️ | Referencia al nombre antiguo en algunos puntos |
| `RFSL1/__init__.py` | — | ✅ | Fachada con utilidades importadas |

### 19.1. Deuda técnica registrada

1. `_rfsl_base.py` aún puede resolver el nombre antiguo de carpeta según el contexto.
2. `RF_SL1_1.py` contiene un alias temporal de carpeta.
3. Varios adaptadores conservan `apply_gradient`/`train_step` que no gobiernan el modelo real.
4. La serialización de los adaptadores antiguos se ha corregido solo en 1_1, 1_2 y 1_3.
5. No hay tests automatizados; la verificación es manual por scripts.
6. La carpeta `RF_SL_SBRTM_IMPORT` mezcla utilidades y neuronas de importación.

---

## 20. Criterios de aceptación (Definition of Done)

Un módulo se considera terminado cuando:

- [ ] Compila.
- [ ] Importa en los cuatro contextos.
- [ ] No redefine clases compartidas.
- [ ] Pasa la matriz de pruebas (sección 11).
- [ ] Tiene demo `< 20 s`.
- [ ] Tiene `__all__` completo.
- [ ] `save`/`load` funcionan en instancia nueva.
- [ ] El puente legado conserva la API.
- [ ] `build_model` y consumidores funcionan.
- [ ] La tabla de estado y el changelog están actualizados.
- [ ] No se ha tocado ningún otro archivo sin declararlo.

---

## 21. Anexo A — Comandos útiles

### Compilar un módulo

```powershell
python -m py_compile RFSL1/RF_SL1_4.py
```

### Importar como paquete profundo

```powershell
python -c "import sys; sys.path.insert(0, r'...\src'); import LC_STM.RedNeuronal.RF_SL.RFSL1.RF_SL1_4 as m; print(m.__file__)"
```

### Importar como top-level

```powershell
python -c "import sys; sys.path.insert(0, r'...\RF_SL'); import RFSL1.RF_SL1_4 as m; print(m.__file__)"
```

### Importar por ruta

```powershell
python -c "import importlib.util as u; s=u.spec_from_file_location('x', r'...\RF_SL1_4.py'); m=u.module_from_spec(s); s.loader.exec_module(m); print(m.__file__)"
```

### Buscar duplicados

```powershell
Select-String -Path ...\*.py -Pattern "^class NeuronaMemoriaBase" -Recurse
```

### Ejecutar demo

```powershell
python RF_SL_SBRTM_RF_SL1_4\RF_SL_SBRTM_RF_SL1_4_1.py
```

---

## 22. Anexo B — Plantilla de registro de cambio

```markdown
### [2026-11-14] RF_SL1_4 modularizado

- **Archivo puente:** `RFSL1/RF_SL1_4.py`
- **Módulo nuevo:** `RF_SL_SBRTM_RF_SL1_4/RF_SL_SBRTM_RF_SL1_4_1.py`
- **Rango sustituido:** líneas 13-165
- **Clases importadas:** `NeuralNetworkOptimizer`, `NeuronaMLP`, ...
- **Compatibilidad:** constructor, `fit`, `predict`, `save/load`
- **Verificación:** matriz 1-18
- **Riesgos:** ninguno detectado
- **Pendiente:** tests automatizados
```

---

## 23. Anexo C — Registro de decisiones (ADR resumido)

| Fecha | Decisión | Motivo | Consecuencia |
|---|---|---|---|
| 2026-11-12 | Base única en `RF_SL_SBRTM_RF_rfsl_base` | Evitar duplicación | Todos los módulos nuevos la importan |
| 2026-11-13 | Módulos especializados autocontenidos | Importables en cualquier contexto | Fallbacks por ruta |
| 2026-11-13 | Puentes con subclase, no copia | Conservar API sin duplicar | Métodos huérfanos se conservan |
| 2026-11-13 | `save/load` con pickle completo | Evitar modelos “vacíos” al cargar | Serialización más pesada pero correcta |
| 2026-11-13 | Verificación manual por scripts | No había CI | Deuda: convertir a tests |
| 2026-11-13 | Alias temporal de carpeta | No romper `_rfsl_base` durante la migración | Deuda: eliminar al estabilizar |

---

## 24. Nota final

La modularidad no consiste en mover código de sitio, sino en **fijar contratos**:

- qué se define y dónde,
- quién puede importar a quién,
- qué API se conserva,
- cómo se comprueba que sigue funcionando.

Si una siguiente importación no puede responder estas cuatro preguntas, todavía no está lista para modularizarse.

**Siguiente acción recomendada:** Fase 1 (saneamiento de la carpeta base) y, en paralelo, `RF_SL1_9` como primer caso de la Fase 2.
