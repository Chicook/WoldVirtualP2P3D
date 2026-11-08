# STM_RFC · README del sistema RFPRMN

Fecha: 2026-11-08 · **v2.1.0**. Todo lo descrito está implementado y verificado
por ejecución en `STM_RFPRMN/` (fachada `RFPRMN.py` + paquete
`STM_RFPRMN_stmDL/`).

Esta versión cierra los issues **#80** (fiabilidad del flujo de refactor) y
**#81** (seguridad de las operaciones de ficheros) y corrige el fallo de
descarga de modelos locales.

## 1. Lo implementado

### 1.1 Refactorización modular (tope 450 líneas por archivo)

El `RFPRMN.py` original (1813 líneas, ~75 funciones) se dividió sin cambiar
firmas ni comportamiento. Estado actual, **10 submódulos, ninguno por encima
de 450 líneas**:

| Archivo | Líneas | Contenido |
|---|---:|---|
| `RFPRMN.py` | 390 | `class RFPRMN` + menú/CLI (`--ayuda/--version/--estado/--presupuesto/--comando`) |
| `STM_RFPRMN_stmDL/__init__.py` | 399 | Registro perezoso PEP 562 (**133 símbolos**) + presupuesto + salud |
| `stm_base.py` | 273 | Estilo/UI, constantes, errores, rutas base, `atexit` de cachés |
| `stm_fs.py` | 443 | **Nuevo**: copia verificada, swap transaccional, borrado reportado, JSON atómico |
| `stm_fragmentos.py` | 125 | **Nuevo**: troceado por AST/heurística y solape de contexto |
| `stm_gestion.py` | 425 | fs + `refactorizar/enviar/actualizar` **transaccionales** |
| `stm_analisis.py` | 267 | `AnalisisArchivo` + plan + LucIA local |
| `stm_modelos.py` | 429 | Catálogo y selección de modelos (Ollama/OpenRouter) |
| `stm_descarga.py` | 165 | **Nuevo**: descarga GGUF atómica, reanudable y verificada |
| `stm_refactor.py` | 280 | Fragmentos + validación + `comando_ds_ialocal` |
| `stm_flujo.py` | 389 | `FlujoRefactorLucIA` (una sola definición de `ejecutar`) |
| `stm_registro.py` | 449 | Publicación del registro (md → pesos → IPFS) |

`from RFPRMN import X` y `RFPRMN().metodo()` siguen funcionando igual.

### 1.2 Issue #80 — flujo de refactor (`stm_flujo.py`)

| Punto del issue | Solución |
|---|---|
| 1. `ejecutar()` duplicado | Una única definición con `try/finally`; hay prueba que lo verifica por AST |
| 2. Fronteras inseguras | Los `.py` se cortan en **fronteras de sentencias de nivel superior** (AST): nunca se separa una cabecera de su cuerpo |
| 3. Solape real | Cada fragmento recibe la cola del fragmento **original** anterior; `quitar_solape()` elimina la repetición al ensamblar |
| 4. Truncamiento silencioso | Se elimina todo `[:LIMITE]`; si el resultado excede el tope se lanza `ErrorProyecto` y el original queda intacto |
| 5. `except ImportError: pass` | Imports explícitos en los tres módulos afectados: un fallo rompe el arranque con mensaje claro |
| 6. Rotación y limpieza | Los modelos fallidos se excluyen siempre; `_borrar_modelo_ollama()` devuelve `bool` en vez de mentir; el `finally` limpia el peso local |
| 7. Validación y recuperación | Se conserva el original de los fragmentos irrecuperables, el error se reinyecta en el reintento y se pide confirmación antes de aplicar un resultado parcial |

Además se corrigió la lectura de modelos usados (antes una regex capturaba
marcas de tiempo como `12:50`) y se reordenó `_asegurar_modelo_codigo()`:
**primero se reutiliza lo instalado en Ollama y solo se descarga si no hay nada**.

### 1.3 Issue #81 — gestión de ficheros (`stm_gestion.py` + `stm_fs.py`)

| Punto del issue | Solución |
|---|---|
| 1. Pérdida de datos | Ya no se borra el destino antes de copiar: copia a `.tmp`, verifica y luego intercambia |
| 2. Operaciones transaccionales | `reemplazar_directorio()` con rollback: si el intercambio falla se restaura el destino |
| 3. Verificación de copia | `verificar_copia()` compara **ruta relativa + tamaño + SHA-256**, no solo el número de ficheros |
| 4. Rutas y symlinks | `es_subruta()`/`rutas_se_solapan()` impiden copiar un directorio dentro de sí mismo; `symlinks=True` y recorridos sin seguir enlaces |
| 5. Borrado fiable | `eliminar_ruta()` enumera los restos y lanza `OSError` con la causa; se acabó el `ignore_errors` silencioso |
| 6. Log de envíos | `_registrar_envio()` escribe JSON **atómico** bajo bloqueo entre procesos y conserva el registro corrupto como `.corrupto` |
| 7. Versiones | Se verifica la nueva versión **antes** de purgar las anteriores; un fallo de limpieza se reporta y nunca deja PRY sin versión válida |
| 8. Mantenibilidad | Imports muertos eliminados, errores específicos y rutas críticas protegidas (`RAIZ`, `PRY`, `RFC`, `CONTRRF`, `TLLDCD` y la propia herramienta) |

### 1.4 Descarga de modelos

`stm_descarga.descargar_gguf()` sustituye a la descarga directa sobre el
archivo final:

- escritura en `<archivo>.part` y `os.replace` **solo** al terminar;
- reanudación con `Range` si hay un `.part` previo (reinicia si el servidor no
  admite rangos);
- reintentos con espera creciente y `timeout` por bloque;
- validación de cabecera mágica `GGUF` y tamaño mínimo: **un archivo truncado
  ya no se acepta como completo**;
- deja de depender de `huggingface_hub` (se construye la URL canónica).

### 1.5 Publicación del registro al actualizar

`stm_registro_json/STM_RFC/envios.json` → `registro.md` en lenguaje natural →
borrado del json → pesos neuronales v2 (vector global 64 + vector por sección +
cuantizado int8) → subida IPFS en 4 niveles (IPFSManager → API
`127.0.0.1:5001` → `ipfs.exe` del sistema → CID `QmLocal` local) → borrado de
md y pesos. Utilidades: `vista_previa()`, `verificar_pesos()`,
`similitud_coseno()`, `url_pasarela()`.

### 1.6 Rutas, bytecode y consola

- `RUTA_RFC_OFICIAL`/`RUTA_PRY_OFICIAL` son rutas fijas con *fallback* al
  layout real (deuda D2, ver §3).
- `sys.pycache_prefix` apunta a `STM_RFPRMN/.pycache_rfprmn`; el gancho
  `atexit` limpia `__pycache__` y esa carpeta al salir.
- Las impresiones de cajas/paneles usan `_imprimir_seguro()` para consolas
  cp1252.

## 2. Pruebas

Suite propia del módulo (60 pruebas, sin red y sin Ollama):

```bash
cd VersionDe_sesion/CONTRRF/STM_RFC/STM_RFPRMN
python -m pytest tests -q -p no:cacheprovider
# en equipos con sandbox de integridad baja, además: -p no:tmpdir
# y RFPRMN_TEST_TMP=<carpeta escribible>
```

| Archivo | Cobertura |
|---|---|
| `tests/test_fragmentos.py` | Cortes válidos, cobertura sin huecos, `try/except`, solape |
| `tests/test_flujo.py` | Un solo `ejecutar`, sin F821, ensamblado sin truncar, rotación y limpieza |
| `tests/test_fs.py` | Verificación por huella, swap con rollback, borrado, JSON atómico, bloqueo |
| `tests/test_gestion.py` | Protección de rutas críticas, registro atómico y recuperación de JSON corrupto |
| `tests/test_descarga.py` | Reanudación con `Range`, rechazo de truncados, no repetir descargas |

## 3. Deuda técnica

- **D1**. `stm_registro` (449) sigue pegado al tope: el próximo cambio exige
  extraer `stm_pesos`/`stm_ipfs`. `stm_fs` (443) y `stm_modelos` (429) también
  están cerca.
- **D2**. `RUTA_*_OFICIAL` cableadas a una ruta de escritorio: no portable.
- **D3**. Vectores por hash SHA-256, no embeddings semánticos reales.
- **D4**. El registro de símbolos de `__init__.py` se mantiene a mano; las
  pruebas cubren los símbolos usados, pero no hay generación automática.
- **D5**. Los constructores de `stm_descarga`/`stm_fs` siguen usando `except
  OSError` amplio en las rutas de limpieza (deliberado: no deben romper el flujo).
- **D6**. La configuración de IA local (`IAlocal.json`) se resuelve contra
  `CONTRRF/RFC/src`, que `actualizar` vacía: si RFC está vacío se avisa y se
  degrada al diagnóstico local. **Pendiente**: leerla de `PRY/actualizacion_*`.

## 4. Deuda preexistente detectada (no introducida aquí)

- **P1**. `IPFSManager` de `STM_BKCH/compat_local.py` es un shim no-op.
- **P2**. `SBSTM/IALOCAL.py:239` llama a métodos que no existen en `IPFSManager`.
- **P4**. `actualizar()` rama heredada usa `ORIGEN/DESTINO` legacy.

## 5. Tareas pendientes

1. Migrar `CONFIG_IA_LOCAL` a `PRY/actualizacion_*/src/STM_JSON/IAlocal.json`
   (D6), que es donde vive de verdad.
2. Mover pesos y `registro_refactor.md` fuera de `RFC/src` (a
   `STM_RFPRMN/.modelos`), para no ensuciar el árbol sincronizado.
3. Decidir la política de borrado de modelos: hoy el flujo exitoso ejecuta
   `ollama rm`; valorar conservarlos por defecto.
4. Dividir `stm_registro` antes de añadir funciones (D1).
5. Sustituir los vectores por hash por embeddings reales (D3).
6. Resolver P1/P2 y eliminar la rama heredada P4.
