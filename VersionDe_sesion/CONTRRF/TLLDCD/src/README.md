# Taller de código fuente — `TLLDCD/src`

> Documento vivo del taller. Última revisión: 2026-11-13.
> Fuente única de rutas: [`Rutas.json`](Rutas.json).
> Cargador y validador: [`rutas_json.py`](STM_CH/STM_herramientas/rutas_json.py).

Este README describe la **estructura oficial actual**, la **deuda técnica** que
queda después de la reorganización y un **plan de corrección por fases** que no
rompe la organización nueva.

---

## 1. Regla de oro

1. **Las rutas se declaran en `Rutas.json`**, no se reparten por el código.
2. Cada subsistema es un paquete con su `__init__.py` y una o varias **carpetas
   de sección**. No debe haber módulos `.py` sueltos en la raíz de un
   subsistema, salvo su `__init__.py`.
3. El código nuevo entra en la sección que le corresponde, no en la raíz.
4. Si un módulo se mueve, primero se actualiza `Rutas.json`, después los
   imports y, por último, se retiran los puentes de compatibilidad.
5. Las rutas del JSON son **relativas a `Rutas.json`**. Nunca absolutas.

---

## 2. Estructura actual

```text
TLLDCD/src/
├── Rutas.json                         ← fuente única de rutas
├── README.md                          ← este documento
├── LC_STM/
│   ├── __init__.py
│   ├── red_neuronal/
│   │   ├── ENRN/  RF_EN/  RF_SL/  RNP/  SLRN/
│   └── seq2seq/
├── SBSTM/
│   ├── __init__.py                    ← compatibilidad de rutas históricas
│   └── SistemasLC/
│       ├── __init__.py
│       ├── STM_SBTM_1/                ← comandos, accesores, IAFREE, autodiagnóstico
│       ├── STM_SBTM_2/                ← memoria, perfil, RPLC, SNSBSTNPRB, IALOCAL legado
│       ├── STM_SBTM_3/                ← STYLOS, voz, watchdog, subsistemas
│       └── tts_models/                ← datos de voz
├── STMGNRL/
│   ├── __init__.py
│   └── SistemaGeneral/                ← mainLCSTM.py, _imports.py
├── STM_BKCH/
│   ├── __init__.py
│   └── stm_bkch1/                     ← BKSVCB.py, compat_local.py, servidor_oficial.py
├── STM_CH/
│   ├── __init__.py
│   ├── STM_herramientas/              ← rutas.py, rutas_json.py
│   ├── PSNRL/                         ← datos runtime
│   └── pycache/                       ← caché runtime
├── STM_HRTS/
│   ├── __init__.py
│   ├── STM_DEF/                       ← seguridad y definición
│   ├── STM_PY/                        ← entrada Python
│   ├── utils/
│   │   ├── add_utils/                 ← rutas canónicas, sincronización
│   │   └── STM_UTILS/                 ← generadores y herramientas
│   ├── empaquetado/
│   ├── docs/
│   ├── opencode/
│   ├── _aux/                          ← material auxiliar/legado
│   └── _archivo_ipfs/                 ← archivo histórico IPFS
├── STM_IA/
│   ├── __init__.py
│   └── STM_Informacion/
│       ├── conocimiento.py
│       └── modelosIAlocal/
│           └── IALOCAL/               ← gestor runtime de LucIA
├── STM_JSON/
│   ├── __init__.py
│   └── STM_LC/                        ← registro_json.py
├── STM_SGR/
│   ├── __init__.py
│   └── STM_CNX/                       ← vault_openrouter.py
├── STMIPFS/
│   ├── __init__.py
│   ├── nodo/
│   ├── SBSTMPYIPFS/
│   └── STM_BAT_IPFS/
├── STM_DOC/                           ← documentación y artículos
├── MTBGT/                             ← proyecto Godot (aplicación aparte)
├── VSC#/                              ← visor C# y nodo web
└── tests/
    ├── __init__.py
    ├── STM_test1/  STM_test2/  STM_test3/
    ├── test_voces/                      ← audios y diagnósticos de voz
    └── godot/STM_GDT/
```

### Convención de secciones

| Subsistema | Sección oficial | Paquete Python |
|---|---|---|
| `SBSTM` | `SistemasLC` | `SBSTM.SistemasLC` |
| `STMGNRL` | `SistemaGeneral` | `STMGNRL.SistemaGeneral` |
| `STM_BKCH` | `stm_bkch1` | `STM_BKCH.stm_bkch1` |
| `STM_CH` | `STM_herramientas` | `STM_CH.STM_herramientas` |
| `STM_IA` | `STM_Informacion` | `STM_IA.STM_Informacion` |
| `STM_JSON` | `STM_LC` | `STM_JSON.STM_LC` |
| `STM_SGR` | `STM_CNX` | `STM_SGR.STM_CNX` |
| `STMIPFS` | `nodo`, `SBSTMPYIPFS`, `STM_BAT_IPFS` | `STMIPFS.<sección>` |
| `LC_STM` | `red_neuronal`, `seq2seq` | `LC_STM.<sección>` |
| `tests` | `STM_test1/2/3`, `godot` | `tests.<sección>` |

Los `__init__.py` de las raíces (`SBSTM`, `STMGNRL`, `STM_BKCH`, `STM_IA`,
`STM_JSON`, `STM_SGR`, `STM_CH`) amplían `__path__` hacia su sección. Eso
mantiene funcionando imports históricos como `SBSTM.memoria_sesion` o
`STM_CH.rutas`, pero **es un puente temporal**, no el destino final.

---

## 3. Contrato de rutas

`Rutas.json` contiene:

- `raices`: `src`, `tllcd`, `contrrf`, `version`, `repo`.
- `subsistemas`: raíz, sección oficial y subsecciones.
- `archivos`: módulos y puntos de entrada clave.
- `runtime`: `LCtrabajando`, `PSNRL`, ledger, caché, `STM_RFC`, `RFPRMN`.
- `pythonpath`: entradas recomendadas para `sys.path`.

### Uso desde código

```python
from STM_CH.STM_herramientas.rutas_json import cargar, obtener, resolver, validar

main_lcstm = obtener("archivos.mainLCSTM")
lc_trabajando = obtener("runtime.lc_trabajando")
rutas = cargar()
informe = validar()          # valida las rutas de código declaradas
```

### Validación por terminal

```powershell
python -m STM_CH.STM_herramientas.rutas_json
python -m STM_CH.STM_herramientas.rutas_json --runtime
```

`rutas.py` de `STM_HRTS/utils/add_utils` ya consume `Rutas.json` para
`CONOCIMIENTO_DIR`, `IALOCAL_DIR`, `PAQUETE_*`, `STM_CH_DIR`, `PSNRL_DIR`,
`LEDGER_PATH` y `CACHE_IAFREE`, con los cálculos anteriores como respaldo.

---

## 4. Deuda técnica actual

| ID | Zona | Síntoma | Riesgo | Solución | Prioridad |
|---|---|---|---|---|---|
| DT-01 | Raíces de subsistema | Los `__init__.py` raíz amplían `__path__` para que sigan funcionando imports planos (`SBSTM.accesores`, `STM_CH.rutas`). | Se pueden cargar dos instancias del mismo módulo y ocultar imports incorrectos. | Migrar todos los imports a la ruta explícita de sección y retirar los `__path__` cuando el grep no encuentre rutas planas. | Alta |
| DT-02 | `STMGNRL/SistemaGeneral` | `mainLCSTM.py` y `_imports.py` aún calculan varias raíces con `Path(__file__).parents[...]`. | Al mover el árbol, las rutas se desfasan otra vez. | Sustituir por `rutas_json.obtener("raices.*")` y `runtime.*`, manteniendo el cálculo actual como fallback. | Alta |
| DT-03 | `SBSTM/SistemasLC` | Varios módulos usan `parents[3]`, `parents[4]`, `parents[5]` tras dos mudanzas. | Un nuevo movimiento rompe `LCtrabajando`, `PSNRL` o `tts_models`. | Cambiar esos cálculos por claves de `Rutas.json` (`subsistemas.SBSTM.*`, `runtime.*`). | Alta |
| DT-04 | `IALOCAL` | Hay dos implementaciones: `SBSTM/SistemasLC/STM_SBTM_2/IALOCAL.py` (flujo legado) y `STM_IA/STM_Informacion/modelosIAlocal/IALOCAL/gestor.py` (runtime usado por `_imports`). | Confusión sobre cuál es la vigente y duplicación de mantenimiento. | Documentar `STM_IA.../gestor.py` como runtime oficial; mantener el legado solo mientras `BKSVCB` lo use; después moverlo a `_aux` o eliminarlo. | Alta |
| DT-05 | `SBSTM/SistemasLC/STM_SBTM_2` | `split_tool.py` es una herramienta de migración con rutas antiguas. | Código muerto y rutas falsas. | Mover a `STM_HRTS/_aux` o borrar cuando nadie lo importe. | Media |
| DT-06 | `tests/STM_test*` | Muchos tests hacían `SRC_DIR = Path(__file__).resolve().parents[1]`; al moverlos a `tests/STM_testN`, eso apunta a `tests`, no a `src`. | Los tests de rutas y los `sys.path` fallan. | Cambiar a `parents[2]`, actualizar comprobaciones a las secciones nuevas y añadir un `conftest.py` raíz de tests. | Alta |
| DT-07 | `STM_HRTS` | `_aux/`, `_archivo_ipfs/` y `opencode/` no están clasificados como secciones oficiales. | Material histórico mezclado con código activo. | Decidir si son archivo, herramientas o documentación; mover a `_aux` o `docs` y reflejarlo en `Rutas.json` solo si se usan. | Media |
| DT-08 | `MTBGT` | El proyecto Godot contiene `lucia3D/GLTF_lucIA` y `lucia3D/LcshLucIA`, dos copias de la misma familia. | Refactorizar rutas Python dentro de Godot puede romper escenas. | Tratar `MTBGT` como aplicación externa: no mover sus archivos; si se toca, hacerlo con plan de Godot y backup. | Media |
| DT-09 | `STM_CH` | `PSNRL/` y `pycache/` son datos runtime dentro de `src`. | Se mezclan artefactos con código versionado. | Mantenerlos fuera del control de versiones o moverlos a una carpeta runtime declarada en `Rutas.json`; no borrarlos sin backup. | Media |
| DT-10 | `VSC#/Visor3Ddesarrollo/webnodo` | Hay Python (`fallback.py`) dentro del árbol C#. | Difícil saber si pertenece al visor o a pruebas. | Documentar su dueño; si es herramienta, mover a `tools/` o `tests/godot`; si es del visor, dejar y marcar como auxiliar. | Baja |
| DT-11 | `Rutas.json` | La validación por defecto omite `runtime` porque `LCtrabajando` puede no existir en según qué entorno. | Una ruta runtime rota no se detecta en CI. | Marcar claves runtime como `requeridas: true/false` y validar las requeridas; usar `--runtime` para la comprobación completa. | Media |
| DT-12 | `mainLCSTM` | `SBSTM_DIR` apunta a `src/SBSTM`, aunque la sección real es `src/SBSTM/SistemasLC`. | Solo afecta a `sys.path`/diagnóstico, pero induce a error. | Cambiar a `SBSTM_DIR = obtener("subsistemas.SBSTM.seccion")` o eliminarlo si no se usa. | Baja |

---

## 5. Plan de corrección sin romper la organización

### Fase 0 — Congelar y medir

- No mover carpetas sin actualizar `Rutas.json` en el mismo cambio.
- Añadir un test de humo que importe:
  - `SBSTM.SistemasLC`
  - `STMGNRL.SistemaGeneral.mainLCSTM`
  - `STM_BKCH.stm_bkch1.BKSVCB`
  - `STM_IA.STM_Informacion.modelosIAlocal.IALOCAL.gestor`
  - `STM_CH.STM_herramientas.rutas`
- Ejecutar `python -m STM_CH.STM_herramientas.rutas_json`.

### Fase 1 — `Rutas.json` como fuente de verdad

1. Migrar `mainLCSTM.py` y `_imports.py` a `rutas_json.obtener(...)` para raíces y `RFPRMN`.
2. Migrar los cálculos de `SBSTM` (`SBSTM_DIR`, `LCtrabajando`, `PSNRL`, `tts_models`) a claves del JSON.
3. Migrar `BKSVCB`, `compat_local`, `IALOCAL`, `SGR` y `STMIPFS` cuando toque.
4. Mantener siempre el valor calculado como **fallback** si el JSON falta.

### Fase 2 — Imports explícitos

1. Buscar imports planos:
   ```powershell
   Get-ChildItem -Recurse -Filter *.py |
       Select-String -Pattern "from SBSTM\.(?!SistemasLC)|import SBSTM\."
   ```
2. Cambiarlos a `SBSTM.SistemasLC.STM_SBTM_n.<modulo>`.
3. Hacer lo mismo con `STM_CH.rutas` → `STM_CH.STM_herramientas.rutas`, etc.
4. No retirar los `__path__` todavía: primero debe quedar el grep limpio y los tests en verde.

### Fase 3 — Tests

1. `SRC_DIR = Path(__file__).resolve().parents[2]` en `tests/STM_test*`.
2. Añadir `tests/conftest.py` que ponga `src` en `sys.path`.
3. Actualizar comprobaciones de archivos a sus secciones (`SBSTM/SistemasLC/...`).
4. Ejecutar `pytest` por secciones, no todo de golpe.

### Fase 4 — Limpieza

- Mover `split_tool.py` y material de migración a `_aux`.
- Decidir el destino de `_aux`, `_archivo_ipfs` y `opencode`.
- Documentar la copia legado de `IALOCAL`; retirarla cuando `BKSVCB` use la oficial.
- Revisar `MTBGT` y `VSC#` con un plan específico, sin tocarlos en el mismo cambio que el código Python.

### Fase 5 — Retirar puentes

Solo cuando:

- `python -m ...rutas_json` devuelva `ok`.
- El grep de imports planos esté vacío.
- El smoke test de imports pase.
- Los tests de rutas pasen.

Entonces se pueden quitar los `__path__` de los `__init__.py` raíz y dejar
únicamente los paquetes de sección.

---

## 6. Comandos de verificación

Ejecutar desde `TLLDCD/src` (o con `PYTHONPATH` apuntando a `src`).

```powershell
# 1. JSON válido y rutas de código existentes
python -m STM_CH.STM_herramientas.rutas_json

# 2. Incluyendo runtime (puede faltar LCtrabajando en un clon limpio)
python -m STM_CH.STM_herramientas.rutas_json --runtime

# 3. Compilación de todo el taller (sin MTBGT), desde src
@'
from pathlib import Path
raiz = Path(".").resolve()
err = 0
for p in raiz.rglob("*.py"):
    if "MTBGT" in p.parts:
        continue
    try:
        compile(p.read_text(encoding="utf-8-sig"), str(p), "exec")
    except Exception as e:
        err += 1
        print("ERR", p, e)
print("errores:", err)
'@ | python -

# 4. Humo de imports
python -c "import SBSTM, STMGNRL.SistemaGeneral.mainLCSTM, STM_BKCH.stm_bkch1.BKSVCB, STM_IA.STM_Informacion.modelosIAlocal.IALOCAL.gestor, STM_CH.STM_herramientas.rutas"
```

### Estado de la última verificación

- `Rutas.json`: **válido**.
- Rutas de código revisadas: **97**, faltantes: **0**.
- Archivos Python compilados (sin `MTBGT`): **208**, errores: **0**.
- Imports de humo y `LucIAConstructor`: **OK**.
- Pendiente principal: tests (`DT-06`) y migración completa de imports planos (`DT-01`).

---

## 7. Checklist para añadir o mover un módulo

- [ ] ¿Está dentro de la sección correcta?
- [ ] ¿La sección tiene `__init__.py`?
- [ ] ¿Actualicé `Rutas.json` con la ruta nueva?
- [ ] ¿Actualicé los imports de los consumidores?
- [ ] ¿Mantuve un fallback si el cambio es de rutas?
- [ ] ¿Pasé el validador de `Rutas.json`?
- [ ] ¿Compila el archivo y el paquete?
- [ ] ¿El smoke test de imports sigue pasando?
- [ ] ¿El cambio no toca `MTBGT`/`VSC#` sin un plan aparte?

---

## 8. Lo que no se debe hacer

- No crear módulos `.py` en la raíz de un subsistema.
- No meter rutas absolutas en `Rutas.json`.
- No mover una carpeta y dejar imports viejos “para luego”.
- No borrar `_aux`, `PSNRL`, `pycache`, `MTBGT` o `VSC#` sin backup y sin
  revisar quién los usa.
- No retirar los `__init__.py` de compatibilidad antes de que el grep de
  imports planos esté limpio.

---

## 9. Relación con `LC_constructor`

`LC_constructor` vive fuera de `TLLDCD/src`, en:

```text
CONTRRF/STM_RFC/STM_RFPRMN/LC_constructor.py
```

Su ruta está declarada en `Rutas.json` como `archivos.LC_constructor` y
`runtime.rfprmn_dir`. LucIA lo carga mediante `_imports.importar_constructor()`
y `LucIAConstructor`; la reorganización de `TLLDCD/src` no debe cambiar ese
contrato. Si algún día se mueve, se actualiza `Rutas.json` y el importador,
nunca una ruta suelta en `mainLCSTM.py`.
