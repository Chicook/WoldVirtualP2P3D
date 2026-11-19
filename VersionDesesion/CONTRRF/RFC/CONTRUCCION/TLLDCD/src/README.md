# TLLDCD/src — Plan de Refactorización

Versión: 1.0 · Fecha: 2026-11-16 · Fuente canónica de rutas: [`Rutas.json`](Rutas.json) (v2026.3.1)

> **Corrección respecto a la versión anterior de este README:** las descripciones de
> subsistemas estaban deducidas del nombre de la carpeta y varias eran erróneas
> (ej.: `MTBGT` **no** es un módulo de bases de datos, es el mundo Godot). Las
> descripciones de abajo están verificadas contra `Rutas.json` y los documentos
> reales de `STM_DOC/`.

## 1. Mapa real de subsistemas

| Carpeta | Propósito | Evidencia |
|---|---|---|
| `LC_STM/` | Núcleo neuronal: `red_neuronal/` (ENRN, RF_EN, RF_SL, RNP, SLRN) y `seq2seq/` | `Rutas.json` §LC_STM |
| `SBSTM/` | Subsistemas LC: STM_SBTM_1 (accesores, comandos, IAFREE, autodiagnóstico), STM_SBTM_2 (memoria_sesion, RPLC, selector_modelos, self_context, SNSBSTNPRB), STM_SBTM_3 (STYLOS, evolutivo, neural, voice_engine, watchdog), `tts_models/` | `Rutas.json` §SBSTM |
| `STMGNRL/` | Sistema general: orquestador `mainLCSTM.py` + `_imports.py` | `Rutas.json` §archivos |
| `STM_BKCH/` | Servidor de bloques: `BKSVCB.py`, `bksvcb_net.py`, `servidor_oficial.py`, `compat_local.py` | `Rutas.json` §archivos |
| `STM_CH/` | Cambios y runtime: `STM_herramientas/` (rutas.py, rutas_json.py), `PSNRL/` (pesos), `blockchain_ledger.json`, caché IAFREE | `Rutas.json` §runtime |
| `STM_DOC/` | Documentación: `docs/`, `Desarrollo/`, `Otros_documentos/`, `otrosarticulos/` | Árbol del directorio |
| `STM_HRTS/` | Herramientas: `STM_DEF/`, `STM_PY/`, `utils/` (STM_UTILS, add_utils/rutas.py), `empaquetado/` | `Rutas.json` §STM_HRTS |
| `STM_IA/` | Información de IA: `conocimiento.py`, `modelosIAlocal/IALOCAL/gestor.py` | `Rutas.json` §archivos |
| `STM_JSON/` | Registro JSON: `STM_LC/registro_json.py` | `Rutas.json` §archivos |
| `STM_SGR/` | Conexiones: `STM_CNX/vault_openrouter.py` | `Rutas.json` §archivos |
| `STMIPFS/` | IPFS: `nodo/`, `SBSTMPYIPFS/ipfs_launcher.py`, `STM_BAT_IPFS/` | `Rutas.json` §STMIPFS |
| `MTBGT/` | **Mundo Godot 4.7.2** `WoldVirtualP2P3D` (Forward Plus, D3D12, Jolt): `gdscrip/`, `ESCENAS/`, `avatares/`, `ISLA3D/`, `lucia3D/` embebido, `addons/`, `tools/` | `project.godot`, `Rutas.json` §runtime |
| `VSC#/` | Visor C# (`Visor3Ddesarrollo/`, `webnodo/`) que embebe el mundo Godot | Docs de STM_DOC |
| `tests/` | Pruebas: `STM_test1/2/3`, `godot/STM_GDT` | `Rutas.json` §tests |
| `Rutas.json` | Mapa canónico de rutas, pythonpath y runtime del taller | Este archivo |

Verificación de integridad (2026-11-16): los 29 archivos clave listados en
`Rutas.json` §archivos existen. Ninguno falta.

## 2. Plan de refactorización

Prioridades: **P0** bloquea uso o integridad · **P1** calidad/mantenimiento · **P2** mejora.

### Fase 0 — Verdad documental (P0, base de todo)

| # | Tarea | Estado |
|---|---|---|
| R0.1 | Corregir descripciones de subsistemas en este README | **Hecho** (este commit) |
| R0.2 | Declarar `Rutas.json` como única fuente canónica de rutas; ningún script nuevo con rutas hardcodeadas | Pendiente |
| R0.3 | Inventariar los ~12 docs de desarrollo en `STM_DOC/` (`README_DESARROLLO.md`, `README_PLAN_DE_DESARROLLO.md`, `README_desarrollo_20261026*.md`, `README_desarrollo_20261028*.md`…): marcar uno vigente y el resto como históricos | Pendiente |

### Fase 1 — Verificación estructural automatizable (P0)

| # | Tarea | Criterio de terminado |
|---|---|---|
| R1.1 | Script que valide `Rutas.json`: cada ruta de `subsistemas`, `archivos` y `runtime` existe | **Hecho** (2026-11-16): `tests/validar_rutas_json.py` — 108 comprobaciones; detectó `pycache` en el mapa (corregido) y `tts_models` (→ R1.5) |
| R1.4 | Runtime Python: **resuelto con el despliegue vendido** `.dev/.python` (3.15.2, seis paquetes y `.dev/venv` de respaldo con las mismas versiones; todo `src` compila en 3.15.2 — compileall exit 0 — y los lanzadores de `HerraMientas/` lo usan como primera opción). Opcional: limpiar claves huérfanas PEP 514 | Detalle y política en `../../.dev/DEPENDENCIAS.md` |
| R1.5 | Resolver `SBSTM/SistemasLC/tts_models`: la carpeta no existía en este árbol; **creada** (2026-11-16) con `LEEME.md` — el código la referencia (`procesador_voz_neuronal.py:18`, Piper ONNX) y el validador pasa sin faltas | Hallazgo de R1.1 |
| R1.2 | Validar `pythonpath` de `Rutas.json` contra los imports reales de `mainLCSTM.py` | Import del orquestador resuelve sin parchear rutas a mano |
| R1.3 | Estado ejecutable de `tests/STM_test1/2/3` y `tests/godot/STM_GDT` | Informe de qué prueba corre hoy y qué no |

### Fase 2 — Refactor del núcleo Python (P1)

| # | Tarea | Origen del hallazgo |
|---|---|---|
| R2.1 | Unificar orquestadores duplicados: `mainLCSTM.py` vs `nucleo/orquestador_lucia.py` (subconjunto PSN+RPLC) | `lucia3D/README.md` §8 deuda 10 |
| R2.2 | Convertir copias manuales (`compat_local.py`, `RPLC.py`, `voice_helpers.py`) en paquete compartido; propagar el fix de repetición de RPLC al principal | lucia3D deudas 8 y 9 |
| R2.3 | Protocolo del socket v2: versionar el cambio de `token` incremental→texto final | lucia3D deuda 7/11 |
| R2.4 | Deduplicar preferencias de modelos entre `servidor_lucia.py` e `IALOCAL/gestor.py` | lucia3D deuda 19 |
| R2.5 | Política de limpieza de sesiones (JSON/NPZ en `STM_CH/PSNRL/` y memoria de sesión) | lucia3D deuda 11 |

### Fase 3 — Refactor del mundo Godot `MTBGT/` (P1)

| # | Tarea | Origen del hallazgo |
|---|---|---|
| R3.1 | Restaurar `ValidacionRed.gd` (helper de validación `any_peer` ausente) | `STM_DOC/Desarrollo/README_PLAN_DE_DESARROLLO.md:113,201` |
| R3.2 | `Red.gd`: resolver conflicto puerto dinámico vs `const PUERTO_WS := 8911` | `STM_DOC/Desarrollo/README_DESARROLLO.md:196` |
| R3.3 | Suite headless mínima del mundo (deuda DT-05 documentada: "sin prueba ejecutable") | `README_PLAN_DE_DESARROLLO.md:319` |
| R3.4 | Regenerar el PCK publicado: el binario está íntegro pero viejo (cambios desde 2026-10-30 fuera) | `README_PLAN_DE_DESARROLLO.md:251` |
| R3.5 | Decidir destino del addon `ziva_agent` (desactivado por crash 0xC0000005; no hay build para Godot 4.7) | `MTBGT/WoldVirtualP2P3D/RUTAS_CORREGIDAS.md` |
| R3.6 | Unificar copia canónica de LucIA (C:\Users\User\Desktop\LcshLucIA ↔ E:\LcshLucIA) | lucia3D deuda 27 |

### Fase 4 — Peso y limpieza del repositorio (P2)

| # | Tarea | Origen del hallazgo |
|---|---|---|
| R4.1 | Verificar que `MTBGT/_archivo_20261110/` contiene las copias archivadas y que solo queda un `project.godot` activo | `STM_DOC/Otros_documentos/PLAN_DEMO_LOCAL.md` (F0-01) |
| R4.2 | Duplicados de texturas (7 `.ctex` de 22,4 MB, terreno 4K de 26,8 MB) y `godot_project.zip` duplicado | `README_DESARROLLO.md:147`, `README_VSC.md:274` |
| R4.3 | Definir `.gitignore` de artefactos runtime (`STM_CH/PSNRL/`, `pycache`, `blockchain_ledger.json`, `p2p_session.json`) | `Rutas.json` §runtime |

## 3. Orden de ejecución sugerido

1. R0.2 y R0.3 (media sesión, sin riesgo).
2. R1.1–R1.3 (una sesión; deja red de seguridad antes de tocar código).
3. R2.2 → R2.1 → R2.3 (núcleo Python, de mayor a menor riesgo de regresión).
4. R3 en paralelo si el foco es el mundo; R3.4 solo tras R3.3.
5. R4 al final, con el repo limpio de tareas P0/P1.

## 4. Alcance y límites de este plan

- Basado exclusivamente en el análisis de `TLLDCD/src` (estructuras, `Rutas.json`,
  `lucia3D/README.md`, `lucia3D/ISSUE_LUCIA_3D.md` y documentos de `STM_DOC/`).
- No se ha ejecutado `mainLCSTM.py` ni la suite de Godot: R1 existe justamente para
  verificar antes de refactorizar.
- Las rutas de `lucia3D` referencian `E:/LcshLucIA` como proyecto independiente; su
  consolidación (R3.6) requiere decisión sobre qué copia es canónica.
