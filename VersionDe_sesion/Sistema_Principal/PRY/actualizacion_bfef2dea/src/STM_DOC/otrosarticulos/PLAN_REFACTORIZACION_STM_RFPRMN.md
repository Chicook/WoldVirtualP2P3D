# Plan de refactorización · `STM_RFPRMN` (RFPRMN v2.0.0)

**Fecha:** 2026-11-08 · **Alcance:** `VersionDe_sesion/CONTRRF/STM_RFC/STM_RFPRMN/`
**Estado:** investigación terminada. **No se ha modificado ningún archivo del módulo.**
Este documento es el único artefacto creado (en la raíz del repo porque el sandbox de esta
sesión deniega escrituras bajo `VersionDe_sesion/`; puedes moverlo a `STM_RFC/`).

---

## 0. Resumen ejecutivo

El comando **`ds ialocal` no llega a descargar nada**: muere antes, y cuando se le quitan
los dos primeros obstáculos aparece un tercero que sí es el que el usuario percibe como
«error en la descarga de modelos locales de código». La cadena es:

1. **`NameError` inmediato** — la división del `RFPRMN.py` original en 7 submódulos dejó
   **27 nombres sin importar** en `stm_flujo` (20), `stm_modelos` (3) y `stm_refactor` (4).
   `FlujoRefactorLucIA(...)` ni siquiera se construye. Lo peor: `except ImportError: pass`
   y un registro perezoso tolerante hacen que `--estado` diga **«OK»** en los 7 módulos.
2. **`FileNotFoundError: IAlocal.json`** — `CONFIG_IA_LOCAL` se resuelve contra
   `CONTRRF/RFC/src/STM_JSON/IAlocal.json`, y `RFC` **está vacío por diseño** (el propio
   comando `actualizar` lo vacía al final de cada ciclo). El `IAlocal.json` real vive en
   `Sistema_Principal/PRY/actualizacion_*/src/STM_JSON/`.
3. **Descarga rota y estéril** — `_descargar_peso_hf()` baja ~1 GB de HuggingFace **siempre**,
   antes de comprobar si ya hay un modelo en Ollama, escribe directamente sobre el archivo
   **final** (sin `.part`, sin reanudación, sin verificación), **acepta un archivo truncado
   como válido** (probado: 1 KB aceptado como modelo completo) y **el `.gguf` jamás se usa**:
   ningún camino del código lo carga ni hace `ollama create`. Encima el destino está dentro
   de `RFC/src`, el árbol que `actualizar` vacía y que luego se copia a `PRY`.

A eso se suma una **política destructiva**: tras cada refactor exitoso el flujo ejecuta
`ollama rm` sobre el modelo usado, de modo que la herramienta **consume la biblioteca de
modelos del usuario** (hoy tiene 6 instalados, entre ellos `qwen2.5-coder:7b`, 4,7 GB).

**Conclusión:** no es un bug puntual de red. Es un módulo con (a) imports perdidos en el
refactor, (b) rutas atadas a un árbol efímero, (c) un descargador a medio implementar que
duplica sin aprovechar `STM_IA/modelosIAlocal/IALOCAL/gestor.py`, y (d) cero pruebas.

---

## 1. Método de la investigación

| Actividad | Detalle |
|---|---|
| Lectura completa | 9 archivos, **3.175 líneas** (`RFPRMN.py` + 7 submódulos + `__init__.py`), más `README.md` del sistema |
| Análisis estático | `ruff 0.16.8` con `--select F821,F811,F401,E9` |
| Ejecución | `--version`, `--estado`, `--presupuesto`, `--comando "ia local"`, `--comando "ds ialocal"` |
| Sondas | resolución de rutas en runtime, selección de candidatos, API de Ollama, HEAD/Range contra HuggingFace, aceptación de GGUF truncado, ACL de `RFC` |
| Entorno | Python 3.14.7, `huggingface_hub` 1.32.0, Ollama con 6 modelos, HF accesible (HTTP 206 + `Accept-Ranges: bytes`) |

**Límite honesto:** esta sesión corre en un sandbox de **integridad baja**; las escrituras
bajo `VersionDe_sesion/` están denegadas (`WinError 5`) incluso siendo el workspace. Por eso
no ejecuté ciclos reales de `refactorizar`/`actualizar`/`ds ialocal` completos. Todo lo que
afirmo está reproducido con traza real o es lectura directa del código.

---

## 2. Mapa actual del módulo

### 2.1 Archivos

| Archivo | Líneas | Responsabilidad real |
|---|---:|---|
| `RFPRMN.py` | 390 | Fachada `class RFPRMN` (~35 métodos) + CLI + `__all__` derivado del registro |
| `stmDL/__init__.py` | 375 | Registro perezoso PEP 562 de **116 símbolos** + re-exports tolerantes + presupuesto de líneas |
| `stm_base.py` | 283 | Estilo ANSI, mensajes, errores, **rutas globales**, `atexit` de cachés |
| `stm_gestion.py` | 428 | fs (`copiar`/`borrar`/`eliminar`), `refactorizar`, `enviar`, `actualizar`, crear carpeta/archivo |
| `stm_analisis.py` | 262 | `AnalisisArchivo`, plan, `_cargar_configuracion_ia_local`, `consultar_ia_local` |
| `stm_modelos.py` | 433 | HuggingFace + Ollama + OpenRouter + registro `.md` de modelos usados |
| `stm_refactor.py` | 257 | Fragmentos, validación, `comando_ds_ialocal`, fallback OpenRouter |
| `stm_flujo.py` | 298 | `FlujoRefactorLucIA` (5 fases) + menú + shell |
| `stm_registro.py` | 449 | `registro.md` → pesos v2 → IPFS en 4 niveles → limpieza |

### 2.2 Flujo del comando averiado

```
RFPRMN.main("--comando ds ialocal")
  └─ stm_refactor.comando_ds_ialocal        (pide ruta, lee archivo)
      └─ FlujoRefactorLucIA.__init__        ← ✖ NameError (analizar_archivo_local)
          └─ ejecutar() → _ejecutar_fases()
              ├─ plan_y_confirmacion()      ← ✖ NameError (consultar_ia_local)
              ├─ asegurar_ia()              ← ✖ NameError (_cargar_configuracion_ia_local)
              │   ├─ _cargar_configuracion_ia_local()  ← ✖ FileNotFoundError IAlocal.json
              │   └─ _asegurar_modelo_codigo()
              │       ├─ _descargar_peso_hf()          ← 1 GB a RFC/src, sin usar
              │       └─ _descargar_modelo_ollama()    ← pull del primer candidato no instalado
              ├─ generar_fragmentos()       ← ✖ NameError (LINEAS_POR_FRAGMENTO)
              ├─ refactorizar_fragmento()   ← ✖ NameError (_generar_fragmento)
              ├─ ensamblar()                ← ✖ NameError (_validar_refactor)
              └─ registrar()                ← ✖ NameError (_registrar_refactor_md)
```

### 2.3 Dependencias externas

Ollama `http://localhost:11434` (`/api/tags`, `/api/pull`, `/api/chat`, `/api/delete`,
binario `ollama` en PATH) · HuggingFace (`huggingface_hub.hf_hub_url` + `urlopen`) ·
OpenRouter (`OPENROUTER_API_KEY` vía `STM_SGR.vault_openrouter` o `.env`) · IPFS
(`IPFSManager`, `127.0.0.1:5001`, `ipfs.exe`).

---

## 3. Reproducción del fallo (evidencia)

### 3.1 `ds ialocal` no arranca

```
$ python RFPRMN.py --comando "ds ialocal"
Archivo al cual hay que refactorizar: <ruta>
  File "...\stm_refactor.py", line 220, in comando_ds_ialocal
    return FlujoRefactorLucIA(ruta, contenido, consultor).ejecutar()
NameError: name 'FlujoRefactorLucIA' is not defined
```

### 3.2 Con los imports inyectados, falla la configuración

```
asegurar_ia -> FileNotFoundError: [Errno 2] No such file or directory:
  '...\CONTRRF\RFC\src\STM_JSON\IAlocal.json'
```

`--estado` dice «OK» en los 7 módulos porque los `NameError` son de ejecución, no de import:

```
? stm_flujo     OK ? 298 líneas   ← falso positivo
```

### 3.3 Con la configuración real, falla el destino de la descarga

```
asegurar_ia -> ErrorProyecto: No se pudo descargar el peso HF
  ([WinError 5] Acceso denegado: '...\CONTRRF\RFC\src')
```

`RFC` está vacío (`Get-ChildItem CONTRRF\RFC` → nada) y `RFC/src` **no existe**. El código
hace `dest.mkdir(parents=True, exist_ok=True)` para **recrear `RFC/src`** y meter ahí el
modelo: contamina el árbol sincronizado que `actualizar` debe vaciar.

### 3.4 Un archivo truncado se acepta como modelo completo

```
archivo truncado: 1024 bytes
  Peso ya presente (sin descarga): ...\qwen2.5-coder-1.5b-instruct-q4_k_m.gguf (1024 bytes)
ACEPTADO COMO VALIDO (bug): True
```

### 3.5 Lo que sí funciona (para no romperlo)

`--version`, `--ayuda`, `--presupuesto` (0 módulos > 450), `--estado` (informativo), y
`ia local` (degrada con elegancia ante config ausente). `stm_registro` y `stm_gestion` no
tienen nombres indefinidos.

---

## 4. Inventario de defectos

### 4.1 Bloqueantes

| ID | Ubicación | Síntoma | Causa raíz |
|---|---|---|---|
| **BLQ-1** | `stm_flujo.py:8-13` | `NameError` al construir el flujo (20 nombres) | El split no trasladó los imports: `ConsultorIA`, `analizar_archivo_local`, `consultar_ia_local`, `crear_plan_refactorizacion`, `_pedir_extra_o_diagnostico`, `_cargar_configuracion_ia_local`, `_asegurar_modelo_codigo`, `_liberar_ollama`, `_borrar_modelo_ollama`, `LINEAS_POR_FRAGMENTO`, `_generar_fragmento`, `LIMITE_LINEAS_REFACTOR`, `_validar_refactor`, `_registrar_refactor_md`, `_fallback_openrouter` |
| **BLQ-2** | `stm_refactor.py:98,220,228,239` | `NameError` en `_refactorizar_con_modelo`, `comando_ds_ialocal`, `_fallback_openrouter` | Faltan `_cargar_configuracion_ia_local`, `FlujoRefactorLucIA`, `_refactorizar_con_openrouter` |
| **BLQ-3** | `stm_modelos.py:103,229,377` | `NameError` en `_modelos_ollama_instalados` y `_asegurar_modelo_codigo`; `AnalisisArchivo` sin importar | Idem; el efecto es que Ollama **siempre parece vacío** → fuerza descarga |
| **BLQ-4** | `stm_base.py:171,267-271` | `FileNotFoundError` de `IAlocal.json` | `SRC_DIR` = `CONTRRF/RFC/src`, que `actualizar` vacía; el `IAlocal.json` real está en `PRY/actualizacion_*/src/STM_JSON/` |
| **BLQ-5** | `stm_base.py:171` → `stm_modelos.py:21,37` | La herramienta **recrea `RFC/src`** para modelos/registro | `DIR_MODELOS_LOCAL` y `REGISTRO_REFACTOR_MD` cuelgan de `SRC_DIR`; viola el invariante «RFC se vacía» |

### 4.2 Altos (rompen la descarga o el usuario)

| ID | Ubicación | Problema |
|---|---|---|
| **ALT-1** | `stm_modelos.py:362-390` | Descarga **incondicional** de ~1 GB antes de mirar Ollama: sin red, sin espera, el comando muere aunque `qwen2.5-coder:7b` esté instalado |
| **ALT-2** | `stm_modelos.py:168-223` | El `.gguf` descargado **nunca se consume**: no hay `ollama create` ni carga con llama.cpp. Es 1 GB de basura por ejecución |
| **ALT-3** | `stm_modelos.py:201` | Escritura directa sobre `final`: una descarga interrumpida deja un archivo parcial que luego pasa por «ya presente» (`size > 0`) |
| **ALT-4** | `stm_modelos.py:178,183-190` | `.part` es código muerto: nunca se escribe y el umbral de adopción es `1000*1024*1024` (1.048.576.000 B) fijo |
| **ALT-5** | `stm_modelos.py:191-215` | Sin `Range`/reanudación, sin `Content-Length` verificado, sin SHA-256/ETag, `timeout=120` de lectura, sin reintentos |
| **ALT-6** | `stm_flujo.py:229` | Tras un refactor **exitoso** ejecuta `ollama rm` del modelo: consume la biblioteca del usuario |
| **ALT-7** | `stm_flujo.py:172-173`, `stm_flujo.py:248`, `stm_base.py:217-221`, `RFPRMN.py:341` | `_borrar_peso_local()` en `finally`, en `cerrar()`, en `atexit` y al `KeyboardInterrupt`: garantiza re-descargar 1 GB cada vez |
| **ALT-8** | `stm_flujo.py:183`, `stm_modelos.py:377` | `FileNotFoundError`/`OSError` no se envuelven; `except (ErrorProyecto, ValueError)` lo deja escapar con traceback |
| **ALT-9** | `stm_modelos.py:254-282` | Si falta `IAlocal.json` cae a una lista fija que **excluye** el `qwen2.5-coder:3b` configurado y **añade** `deepseek-coder:6.7b`/`codellama:7b` (no instalados, ~4 GB cada uno) |
| **ALT-10** | `stm_modelos.py:379-390` | Si `/api/tags` falla, `instalados` queda vacío y descarga el primer candidato aunque haya modelos |
| **ALT-11** | `stm_flujo.py:146-148` + `stm_refactor.py:133-168` | Refactor por fragmentos con `num_predict: 800` → truncados → validación 80 % falla → rotación → `ollama rm` → cascada destructiva |
| **ALT-12** | `stm_flujo.py:161-173` | `def ejecutar` **duplicado** (gana el segundo); el primero es un stub con docstring |

### 4.3 Medios

| ID | Ubicación | Problema |
|---|---|---|
| **MED-1** | todos | `try: from .stm_x import (...) except ImportError: pass`: un nombre mal escrito borra **toda** la línea de imports y el módulo sigue «importable» |
| **MED-2** | `__init__.py:318-375` | Los re-exports tolerantes (`except Exception: pass`) ocultan fallos de backend |
| **MED-3** | `__init__.py:20-69` | Registro de 116 símbolos mantenido a mano; no se valida contra el código |
| **MED-4** | `stm_modelos.py:351-359` | Regex de modelos usados captura marcas de tiempo (`2026-11-08T12:50:52`, `12:50.`) → ensucia el conjunto de exclusión |
| **MED-5** | `stm_base.py:274-275` | `RUTA_RFC_OFICIAL`/`RUTA_PRY_OFICIAL` cableadas a `C:\Users\User\Desktop\WoldVirtualP2P3D_v0.0.01LCV1` (deuda D2 del README): hoy degrada por suerte al fallback |
| **MED-6** | `RFPRMN.py:315-342` vs `stm_flujo.py:268-294` | Dos shells distintas: `main()` sin args usa la de `stm_flujo` (sin `estado/presupuesto/ayuda`); `ejecutar_interactiva()` de la fachada nunca se llama |
| **MED-7** | `stm_modelos.py:174` | `huggingface_hub` es dependencia dura no declarada (el módulo no tiene `requirements.txt` ni `pyproject.toml`) |
| **MED-8** | `stm_refactor.py:243` | `modelo_or if 'modelo_or' in dir() else ...` — construcción frágil en el `except` |

### 4.4 Deuda estructural

| ID | Tema |
|---|---|
| **DEU-1** | `stm_registro` (449), `stm_modelos` (433) y `stm_gestion` (428) están pegados al tope de 450: cualquier arreglo exige dividir primero |
| **DEU-2** | Cero pruebas automatizadas para el módulo (el `tests/` del proyecto no lo cubre) |
| **DEU-3** | Sin verificación de integridad del modelo (tamaño/hash/GGUF magic) |
| **DEU-4** | Sin `--dry-run`; el refactor sobrescribe el archivo **in situ** sin copia de seguridad |
| **DEU-5** | `_validar_refactor` compara nombres, no cuerpos: un refactor semánticamente roto puede pasar |
| **DEU-6** | Duplicación de descargador: `stm_modelos._descargar_peso_hf` vs `STM_IA/modelosIAlocal/IALOCAL/gestor.py::_descargar_gguf` (este último sí hace `ollama create`) |

---

## 5. Arquitectura objetivo

### 5.1 Principios

1. **Una sola fuente de rutas** (`stm_rutas.py`). Ninguna otra función compone rutas.
2. **Regla de oro:** la herramienta **no escribe nada** bajo `CONTRRF/RFC` ni bajo
   `Sistema_Principal/PRY`. Modelos, caché y registro van bajo `STM_RFPRMN/`.
3. **Descarga atómica y verificada:** `.part` → `Range` → SHA-256 → `os.replace`.
4. **Nada de descargas especulativas:** primero se pregunta a Ollama; HF solo si de verdad
   se va a usar el GGUF.
5. **Fallo ruidoso:** cero `except ImportError: pass`; cero re-exports tolerantes.
6. **Compatibilidad de símbolos:** los 116 nombres públicos y la fachada `RFPRMN` se
   conservan (contrato con `from RFPRMN import X`).

### 5.2 Reparto propuesto

```
STM_RFPRMN/
  RFPRMN.py                 390 → ~300   fachada + CLI (sin __all__ manual)
  .modelos/                             ← nuevo: GGUF/.part/caché FUERA de RFC
  STM_RFPRMN_stmDL/
    __init__.py             375 → ~120   registro derivado por AST + smoke test real
    stm_base.py             283 → ~200   estilo, mensajes, errores
    stm_rutas.py            nuevo ~150   ÚNICA fuente de rutas + guardián RFC/PRY
    stm_fs.py               nuevo ~120   escribirible/eliminar/copiar/contar
    stm_gestion.py          428 → ~240   refactorizar/enviar/actualizar
    stm_analisis.py         262 → 262    análisis + config IA
    stm_refactor.py         257 → ~230   fragmentos + validación
    stm_flujo.py            298 → ~230   máquina de estados (imports explícitos)
    stm_modelos.py          433 → ~170   política de selección (sin red)
    stm_descarga.py         nuevo ~220   HF atómica + reanudable + verificada
    stm_ollama.py           nuevo ~200   cliente /api/tags,pull,create,delete,ps,chat
    stm_openrouter.py       nuevo ~140   fallback OR
    stm_pesos.py            nuevo ~160   vector/cuantización/similitud
    stm_ipfs.py             nuevo ~150   subida en 4 niveles
    stm_registro.py         449 → ~150   publicar + limpiar
```

16 módulos, todos por debajo de 450 líneas con margen.

### 5.3 Cadena de configuración propuesta

```
1) STM_RFPRMN/.env / variable de entorno RFPRMN_IALOCAL_JSON
2) PRY/actualizacion_*/src/STM_JSON/IAlocal.json   (la más reciente)
3) CONTRRF/RFC/src/STM_JSON/IAlocal.json           (legado, solo lectura)
4) defaults en código (endpoint localhost:11434, sin modelos forzados)
```

Si no hay configuración, **no se inventan candidatos**: se informa y se aborta con mensaje
accionable. Nunca se descarga un modelo que no esté en `models_available`.

### 5.4 Descarga HF (nueva `stm_descarga.py`)

```
final = DIR_MODELOS / nombre
part  = final.with_suffix(final.suffix + ".part")
1. Si final existe → validar GGUF magic ("GGUF") + tamaño > 0 + SHA-256 si hay sidecar → listo.
2. Si part existe → GET con Range: bytes=<tamaño>-  (206) y append; si 200, reiniciar.
3. Escritura por bloques de 4 MB con flush + os.fsync; timeout de socket 60 s por bloque,
   reintentos exponenciales (3) reanudando desde el byte actual.
4. Al terminar: comparar tamaño con Content-Length/Range total y SHA-256 con el ETag
   (HF publica el sha256 del objeto LFS en el ETag) → si no cuadra, borrar y error.
5. os.replace(part, final) — atómico.
6. Consumir de verdad: `ollama create <modelo> -f Modelfile` o eliminar la descarga HF.
```

Decisión pendiente (ver §10): **¿GGUF efímero con `ollama create` (patrón `gestor.py`) o
solo `ollama pull`?** La recomendación es *Ollama-only por defecto*, y GGUF solo como
respaldo cuando el modelo no exista en la librería de Ollama.

---

## 6. Plan por fases

> Todas las fases van en la rama `development`, con `git add <archivo>` nominal (nunca `-A`).

### F0 · Línea base (30 min)

- `git status` limpio, `ruff check --select F821 .` documentado (27), `--presupuesto` OK.
- Guardar salida de `--estado` y `--version` como referencia.
- **Aceptación:** informe de estado en el commit del plan.

### F1 · Reparar imports y silencios (1-2 h) — *desbloquea el comando*

- Imports explícitos en `stm_flujo`, `stm_refactor`, `stm_modelos` (los 27 nombres).
- Eliminar el `def ejecutar` duplicado (`stm_flujo:161`).
- Sustituir `except ImportError: pass` por imports normales; si un backend pesado debe ser
  opcional, aislarlo en una función con `import` local y error explícito.
- `--estado` pasa a hacer **smoke test real** (resolver N símbolos por módulo).
- **Aceptación:** `ruff F821` = 0 · `ds ialocal` llega a pedir el archivo y al plan sin
  `NameError` · `--estado` detecta un módulo roto a propósito (prueba manual).

### F2 · Rutas y configuración (3-4 h) — *elimina el `FileNotFoundError`*

- Nuevo `stm_rutas.py`: `DIR_MODELOS`, `DIR_CACHE`, `REGISTRO_MD`, `CONFIG_IA` con la
  cadena de §5.3 y **guardián**: si una ruta cae bajo `RFC_DIR`/`PRY_DIR`, se corrige y se
  avisa (o se lanza error en modo estricto).
- `stm_base` deja de exponer rutas compuestas; mantiene alias por compatibilidad.
- **Aceptación:** `IAlocal.json` se encuentra en el layout actual (RFC vacío) · ninguna
  escritura bajo `CONTRRF/` en un ciclo completo · prueba `test_rutas.py`.

### F3 · Descarga robusta (4-6 h) — *el núcleo del encargo*

- `stm_descarga.py` según §5.4 + `stm_ollama.py` (cliente único).
- Descarga **perezosa**: solo si la política decide que hace falta.
- Mensajes de progreso con MB/%, velocidad y tiempo restante; cancelable con Ctrl+C sin
  dejar basura (conserva `.part`).
- **Aceptación:** pruebas con `urlopen` simulado: (a) corte a mitad → `.part` conservado;
  (b) reintento → `Range` desde el byte correcto; (c) hash falso → error y borrado;
  (d) GGUF truncado → rechazado; (e) sin red → error claro en < 10 s.

### F4 · Política de modelos (3-4 h) — *deja de destruir y de re-descargar*

- Candidatos **solo** desde `IAlocal.json`; sin lista fija de respaldo.
- Preferir instalados; nunca `pull` si hay uno válido; nunca `ollama rm` sin
  `--consumir-modelos` explícito (por defecto **se conservan**).
- Registro de usados en JSON (`modelos_usados.json`) en vez de parsear el `.md`.
- **Aceptación:** con `qwen2.5-coder:7b` instalado y la config real, `ds ialocal` **no
  descarga nada** y **no borra nada**.

### F5 · Presupuesto, registro y suite (2-3 h)

- Dividir `stm_registro` → `stm_pesos` + `stm_ipfs` + `stm_registro`; `stm_gestion` →
  `stm_fs` + `stm_gestion`.
- `__init__.py`: registro derivado por AST del código real; eliminar re-exports tolerantes.
- Suite `tests/test_rfprmn_*.py` (§8) y actualización del `README.md` del sistema (deuda
  D1, P3 y las nuevas).
- **Aceptación:** `pytest` verde · `--presupuesto` con holgura (máx. < 300 líneas) ·
  paridad de símbolos 116/116.

### F6 · Cierre (1 h)

- README: sección «Descarga de modelos» con el flujo real y la política de borrado.
- Revisión de `git diff`, commit en español, push a `development`.

**Estimación total: 15-20 h** de trabajo efectivo, con F1+F2+F3 (≈9-12 h) como mínimo
viable para que «la descarga de modelos locales de código» funcione.

---

## 7. Presupuesto de líneas

| Antes | Líneas | Después | Líneas |
|---|---:|---|---:|
| `stm_registro` | 449 | `stm_registro` | ~150 |
| `stm_modelos` | 433 | `stm_modelos` | ~170 |
| `stm_gestion` | 428 | `stm_gestion` | ~240 |
| `RFPRMN.py` | 390 | `RFPRMN.py` | ~300 |
| `__init__.py` | 375 | `__init__.py` | ~120 |
| `stm_flujo` | 298 | `stm_flujo` | ~230 |
| `stm_base` | 283 | `stm_base` | ~200 |
| resto | 519 | + 8 módulos nuevos | ~1.240 |
| **total** | **3.175** | **total** | **~3.600** |

Crece ~13 %, pero se eliminan ~200 líneas muertas (imports, `.part` inalcanzable, re-exports)
y cada módulo queda con un tope sano.

---

## 8. Estrategia de pruebas

Sin red, sin Ollama real y sin tocar `RFC`/`PRY`: todo con `tmp_path` y dobles.

| Archivo | Casos |
|---|---|
| `test_rfprmn_imports.py` | `ruff`/`symtable` sin F821 · cada símbolo de `_REGISTRO` resuelve a un atributo real · `__all__` = 116 · ningún módulo supera 450 |
| `test_rfprmn_rutas.py` | Config desde PRY con RFC vacío · guardián: `DIR_MODELOS` nunca bajo `RFC_DIR`/`PRY_DIR` · sin config → error accionable |
| `test_rfprmn_descarga.py` | `urlopen` falso: corte → `.part`; reanudación con `Range`; hash/tamaño incorrectos → error; GGUF truncado → rechazo; `os.replace` final |
| `test_rfprmn_modelos.py` | Candidatos solo de `IAlocal.json` · preferir instalados · `/api/tags` caído no provoca `pull` · no borra modelos |
| `test_rfprmn_flujo.py` | `FlujoRefactorLucIA` con consultor inyectado y generador falso: éxito, no-op, irreparable, rotación, fallback |
| `test_rfprmn_registro.py` | Idas y vueltas de pesos, `similitud_coseno`, cuantización, CID sintético |

Comando de verificación: `python -m pytest tests/test_rfprmn_*.py -q` (aislado del `tests/`
de 98 pruebas, que no debe tocarse).

---

## 9. Compatibilidad

- Los **116 símbolos** de `RegistroRFPRMN.nombres()` y `RFPRMN().metodo()` se mantienen;
  los módulos nuevos son detalle interno.
- `from RFPRMN import X` sigue funcionando (la fachada re-exporta explícitamente).
- `__version__` sube a `2.1.0`.
- Nombres de comando (`ds ialocal`, `ia local`, `refactorizar`…) intactos.

---

## 10. Decisiones abiertas (necesito tu criterio)

1. **Estrategia de modelo:** ¿Ollama-only (recomendado: reutiliza tus 6 modelos y no baja
   nada) o GGUF efímero con `ollama create` como en `IALOCAL/gestor.py` (permite modelos
   que no están en la librería, a cambio de ~1 GB y más latencia)? ¿O híbrido: GGUF solo
   como respaldo?
2. **Borrado de modelos:** hoy el flujo exitoso hace `ollama rm`. ¿Lo convertimos en opt-in
   (`--consumir-modelos`) y por defecto **conservar**? Mi recomendación: conservar.
3. **Registro de refactor:** `registro_refactor.md` está dentro de `RFC/src`. ¿Lo movemos a
   `STM_RFPRMN/registro_refactor.md` (mi recomendación) o lo dejamos viajar con el código?
4. **Alcance:** ¿F1+F2+F3 ya (mínimo que arregla la descarga) y F4-F5 después, o el paquete
   completo de una vez?

---

## Anexo A · Comandos de verificación

```powershell
cd E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\STM_RFC\STM_RFPRMN
python -m ruff check --select F821 --no-cache .     # debe ser "All checks passed"
python RFPRMN.py --version
python RFPRMN.py --estado
python RFPRMN.py --presupuesto                       # exit 0
python -m pytest tests\test_rfprmn_*.py -q           # tras F5
```

## Anexo B · Inventario de nombres indefinidos (ruff F821)

`stm_flujo` (20): `ConsultorIA`, `analizar_archivo_local`, `consultar_ia_local`,
`crear_plan_refactorizacion` (×2), `_pedir_extra_o_diagnostico` (×2),
`_cargar_configuracion_ia_local`, `_asegurar_modelo_codigo`, `_liberar_ollama`,
`_borrar_modelo_ollama` (×2), `LINEAS_POR_FRAGMENTO`, `_generar_fragmento`,
`LIMITE_LINEAS_REFACTOR` (×2), `_validar_refactor`, `_registrar_refactor_md`,
`_fallback_openrouter`.

`stm_modelos` (3): `AnalisisArchivo`, `_cargar_configuracion_ia_local` (×2).
`stm_refactor` (4): `_cargar_configuracion_ia_local` (×2), `FlujoRefactorLucIA`,
`_refactorizar_con_openrouter`.
