# STM_RFC · README del sistema RFPRMN

Fecha: 2026-11-08 · **v2.2.0**. Todo lo descrito está implementado y verificado
por ejecución en `STM_RFPRMN/` (fachada `RFPRMN.py` + paquete
`STM_RFPRMN_stmDL/`).

Esta versión cierra los issues **#80** (fiabilidad del flujo de refactor) y
**#81** (seguridad de las operaciones de ficheros), corrige el fallo de
descarga de modelos locales y resuelve las fases **R1/R2** (rutas fuera de los
árboles sincronizados) y **R3** (los modelos del usuario ya no se borran por
defecto) de la discusión #84.

## 1. Lo implementado

### 1.1 Refactorización modular (tope 450 líneas por archivo)

El `RFPRMN.py` original (1813 líneas, ~75 funciones) se dividió sin cambiar
firmas ni comportamiento. Estado actual, **11 submódulos, ninguno por encima
de 450 líneas**:

| Archivo | Líneas | Contenido |
|---|---:|---|
| `RFPRMN.py` | 400 | `class RFPRMN` + menú/CLI (`--ayuda/--version/--estado/--presupuesto/--comando/--consumir-modelos`) |
| `STM_RFPRMN_stmDL/__init__.py` | 413 | Registro perezoso PEP 562 (**142 símbolos**) + presupuesto + salud |
| `stm_base.py` | 212 | Estilo/UI, constantes, errores, re-export de rutas, `atexit` de cachés |
| `stm_rutas.py` | 219 | **Nuevo**: única fuente de rutas, cadena de configuración y guardián RFC/PRY |
| `stm_fs.py` | 428 | Copia verificada, swap transaccional, borrado reportado, JSON atómico |
| `stm_fragmentos.py` | 125 | Troceado por AST/heurística y solape de contexto |
| `stm_gestion.py` | 412 | fs + `refactorizar/enviar/actualizar` **transaccionales** |
| `stm_analisis.py` | 280 | `AnalisisArchivo` + plan + LucIA local |
| `stm_modelos.py` | 448 | Catálogo y selección de modelos (Ollama/OpenRouter) |
| `stm_descarga.py` | 165 | Descarga GGUF atómica, reanudable y verificada |
| `stm_refactor.py` | 291 | Fragmentos + validación + `comando_ds_ialocal` |
| `stm_flujo.py` | 420 | `FlujoRefactorLucIA` (una sola definición de `ejecutar`) |
| `stm_registro.py` | 449 | Publicación del registro (md → pesos → IPFS) |

`from RFPRMN import X` y `RFPRMN().metodo()` siguen funcionando igual.

### 1.2 Rutas: una sola fuente de verdad (R1/R2)

`stm_rutas.py` centraliza todas las rutas y aplica dos invariantes:

- **La herramienta no escribe bajo `CONTRRF/RFC` ni bajo `Sistema_Principal/PRY`.**
  `comprobar_ruta_segura()` lo impide y `es_zona_sincronizada()` lo consulta.
  Esos árboles se sincronizan y `actualizar` los vacía al final de cada ciclo.
- **Cada dato tiene un sitio estable:**

| Dato | Ruta |
|---|---|
| Pesos GGUF descargados | `STM_RFPRMN/.modelos/IAlocalDESCARGADA/` |
| Registro de refactor | `STM_RFPRMN/registro_refactor.md` |
| Configuración propia | `STM_RFPRMN/.config/IAlocal.json` |

La configuración de IA local se busca en esta cadena, en orden:

1. `RFPRMN_IALOCAL_JSON` (variable de entorno),
2. `PRY/actualizacion_*/src/STM_JSON/IAlocal.json` (donde vive de verdad),
3. `RFC/src/STM_JSON/IAlocal.json` (layout heredado),
4. `STM_RFPRMN/.config/IAlocal.json`.

Así `ds ialocal` funciona aunque `RFC` esté vacío tras un `actualizar` (antes
degradaba siempre al diagnóstico local). El registro heredado de `RFC/src` se
sigue leyendo para no perder el historial de modelos usados.

### 1.3 Issue #80 — flujo de refactor (`stm_flujo.py`)

| Punto del issue | Solución |
|---|---|
| 1. `ejecutar()` duplicado | Una única definición con `try/finally`; hay prueba que lo verifica por AST |
| 2. Fronteras inseguras | Los `.py` se cortan en **fronteras de sentencias de nivel superior** (AST): nunca se separa una cabecera de su cuerpo |
| 3. Solape real | Cada fragmento recibe la cola del fragmento **original** anterior; `quitar_solape()` elimina la repetición al ensamblar |
| 4. Truncamiento silencioso | Se elimina todo `[:LIMITE]`; si el resultado excede el tope se lanza `ErrorProyecto` y el original queda intacto |
| 5. `except ImportError: pass` | Imports explícitos: un fallo rompe el arranque con mensaje claro |
| 6. Rotación y limpieza | Los modelos fallidos se excluyen siempre; `_borrar_modelo_ollama()` devuelve `bool`; el `finally` limpia el peso local |
| 7. Validación y recuperación | Se conserva el original de los fragmentos irrecuperables, el error se reinyecta en el reintento y se pide confirmación antes de aplicar un resultado parcial |

Además, la lectura de modelos usados ya no se hace con una regex sobre todo el
texto (capturaba marcas de tiempo como `12:50`): ahora solo cuentan las
cabeceras `## archivo — modelo` que escribe el propio registro.

### 1.4 Issue #81 — gestión de ficheros (`stm_gestion.py` + `stm_fs.py`)

| Punto del issue | Solución |
|---|---|
| 1. Pérdida de datos | Ya no se borra el destino antes de copiar: copia a `.tmp`, verifica e intercambia |
| 2. Operaciones transaccionales | `reemplazar_directorio()` con rollback: si el intercambio falla se restaura el destino |
| 3. Verificación de copia | `verificar_copia()` compara **ruta relativa + tamaño + SHA-256**, no solo el número de ficheros |
| 4. Rutas y symlinks | `es_subruta()`/`rutas_se_solapan()` impiden copiar un directorio dentro de sí mismo; `symlinks=True` y recorridos sin seguir enlaces |
| 5. Borrado fiable | `eliminar_ruta()` enumera los restos y lanza `OSError` con la causa; se acabó el `ignore_errors` silencioso |
| 6. Log de envíos | `_registrar_envio()` escribe JSON **atómico** bajo bloqueo entre procesos y conserva el registro corrupto como `.corrupto` |
| 7. Versiones | Se verifica la nueva versión **antes** de purgar las anteriores; un fallo de limpieza se reporta |
| 8. Mantenibilidad | Imports muertos eliminados, errores específicos y rutas críticas protegidas |

### 1.5 Descarga de modelos (`stm_descarga.py`)

- Escritura en `<archivo>.part` y `os.replace` **solo** al terminar.
- Reanudación con `Range` si hay un `.part` previo (reinicia si el servidor no
  admite rangos).
- Reintentos con espera creciente y `timeout` por bloque.
- Validación de cabecera mágica `GGUF` y tamaño mínimo: **un archivo truncado
  ya no se acepta como completo**.
- Sin dependencia de `huggingface_hub` (se construye la URL canónica).
- Antes de descargar se **reutiliza lo que ya está instalado en Ollama**.

### 1.6 Política de modelos (R3)

**Por defecto los modelos del usuario se conservan.** El flujo:

- elige un modelo no usado, priorizando los instalados;
- si falla, lo **excluye** de la sesión y sigue con otro (sin `ollama rm`);
- al terminar con éxito, **no borra nada** y lo indica por pantalla.

Para recuperar el comportamiento antiguo hay que pedirlo explícitamente:

```bash
python RFPRMN.py --consumir-modelos --comando "ds ialocal"
# o
set RFPRMN_CONSUMIR_MODELOS=1     # PowerShell: $env:RFPRMN_CONSUMIR_MODELOS="1"
```

### 1.7 Publicación del registro al actualizar

`stm_registro_json/STM_RFC/envios.json` → `registro.md` en lenguaje natural →
borrado del json → pesos neuronales v2 (vector global 64 + vector por sección +
cuantizado int8) → subida IPFS en 4 niveles (IPFSManager → API
`127.0.0.1:5001` → `ipfs.exe` del sistema → CID `QmLocal` local) → borrado de
md y pesos. Utilidades: `vista_previa()`, `verificar_pesos()`,
`similitud_coseno()`, `url_pasarela()`.

### 1.8 Bytecode y consola

- `sys.pycache_prefix` apunta a `STM_RFPRMN/.pycache_rfprmn`; el gancho
  `atexit` limpia `__pycache__` y esa carpeta al salir.
- Las impresiones de cajas/paneles usan `_imprimir_seguro()` para consolas
  cp1252; los mensajes de la cadena de configuración usan separadores ASCII por
  el mismo motivo.

## 2. Pruebas

Suite propia del módulo (**82 pruebas**, sin red, sin Ollama y sin tocar
RFC/PRY):

```bash
cd VersionDe_sesion/CONTRRF/STM_RFC/STM_RFPRMN
python -m pytest tests -q -p no:cacheprovider
# en equipos con sandbox de integridad baja, además: -p no:tmpdir
# y RFPRMN_TEST_TMP=<carpeta escribible>
```

| Archivo | Cobertura |
|---|---|
| `tests/test_rutas.py` | Nada se escribe bajo RFC/PRY, cadena de configuración, predicados |
| `tests/test_modelos.py` | Registro de usados, borrado de pesos seguro, política R3 |
| `tests/test_fragmentos.py` | Cortes válidos, cobertura sin huecos, `try/except`, solape |
| `tests/test_flujo.py` | Un solo `ejecutar`, sin F821, ensamblado sin truncar, rotación y limpieza |
| `tests/test_fs.py` | Verificación por huella, swap con rollback, borrado, JSON atómico, bloqueo |
| `tests/test_gestion.py` | Protección de rutas críticas, registro atómico y recuperación de JSON corrupto |
| `tests/test_descarga.py` | Reanudación con `Range`, rechazo de truncados, no repetir descargas |

## 3. Deuda técnica

- **D1**. `stm_registro` (449) y `stm_modelos` (448) están pegados al tope: el
  próximo cambio en ellos exige extraer `stm_pesos`/`stm_ipfs`.
- **D2**. `RUTA_*_OFICIAL` cableadas a una ruta de escritorio (R5): no portable.
- **D3**. Vectores por hash SHA-256, no embeddings semánticos reales.
- **D4**. El registro de símbolos de `__init__.py` se mantiene a mano.
- **D5**. Las rutas de limpieza de `stm_fs`/`stm_descarga` usan `except OSError`
  amplio a propósito: no deben romper el flujo por un temporal bloqueado.
- **D6 (cerrada)**. Antes la configuración y los pesos vivían en `RFC/src`, que
  `actualizar` vacía. Ahora los resuelve `stm_rutas` (§1.2).

## 4. Deuda preexistente detectada (no introducida aquí)

- **P1**. `IPFSManager` de `STM_BKCH/compat_local.py` es un shim no-op.
- **P2**. `SBSTM/IALOCAL.py:239` llama a métodos que no existen en `IPFSManager`.
- **P4**. `actualizar()` rama heredada usa `ORIGEN/DESTINO` legacy.

## 5. Tareas pendientes

1. **R4**: dividir `stm_registro` y `stm_modelos` antes de añadir funciones (D1).
2. **R5**: mover `RUTA_*_OFICIAL` a configuración (D2).
3. **R6**: cerrar el camino GGUF — hoy se descarga verificado pero no se
   registra con `ollama create`, así que solo vale como aviso; decidir entre
   implementarlo o retirarlo.
4. Sustituir los vectores por hash por embeddings reales (D3).
5. Resolver P1/P2 y eliminar la rama heredada P4.
6. Añadir la suite a un job de CI en la raíz del repositorio (hoy no existe
   `.github/workflows/`).
