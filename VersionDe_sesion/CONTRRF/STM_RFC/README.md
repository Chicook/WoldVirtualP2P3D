# STM_RFC · README del sistema RFPRMN

Fecha: 2026-11-08 · **v2.3.0**. Todo lo descrito está implementado y verificado
por ejecución en `STM_RFPRMN/` (fachada `RFPRMN.py` + paquete
`STM_RFPRMN_stmDL/`).

Esta versión cierra los issues **#80** (fiabilidad del flujo de refactor) y
**#81** (seguridad de las operaciones de ficheros), corrige el fallo de
descarga de modelos locales y resuelve las seis fases de la discusión #84:
**R1/R2** (rutas fuera de los árboles sincronizados), **R3** (conservar los
modelos del usuario), **R4** (dividir los módulos que estaban al tope),
**R5** (rutas configurables) y **R6** (registrar el GGUF en Ollama).

## 1. Lo implementado

### 1.1 Refactorización modular (tope 450 líneas por archivo)

El `RFPRMN.py` original (1813 líneas, ~75 funciones) se dividió sin cambiar
firmas ni comportamiento. Estado actual, **14 submódulos, ninguno por encima
de 450 líneas**:

| Archivo | Líneas | Contenido |
|---|---:|---|
| `RFPRMN.py` | 419 | `class RFPRMN` + menú/CLI (`--ayuda/--version/--estado/--presupuesto/--rutas/--configurar-rutas/--comando/--consumir-modelos`) |
| `STM_RFPRMN_stmDL/__init__.py` | 441 | Registro perezoso PEP 562 (**153 símbolos**) + presupuesto + salud |
| `stm_base.py` | 212 | Estilo/UI, constantes, errores, re-export de rutas, `atexit` de cachés |
| `stm_rutas.py` | 334 | Única fuente de rutas, cadena de configuración, guardián RFC/PRY y comandos `rutas` |
| `stm_fs.py` | 428 | Copia verificada, swap transaccional, borrado reportado, JSON atómico |
| `stm_fragmentos.py` | 132 | Troceado por AST/heurística, solape y constantes de refactor |
| `stm_gestion.py` | 412 | fs + `refactorizar/enviar/actualizar` **transaccionales** |
| `stm_analisis.py` | 280 | `AnalisisArchivo` + plan + LucIA local |
| `stm_modelos.py` | 428 | Política de modelos (ligero primero) y ciclo de vida |
| `stm_descarga.py` | 165 | Descarga GGUF atómica, reanudable y verificada |
| `stm_openrouter.py` | 149 | Respaldo con modelos gratuitos de OpenRouter |
| `stm_refactor.py` | 291 | Fragmentos + validación + `comando_ds_ialocal` |
| `stm_flujo.py` | 425 | `FlujoRefactorLucIA` (una sola definición de `ejecutar`) |
| `stm_registro.py` | 194 | Publicación del registro y limpieza |
| `stm_pesos.py` | 137 | Vectorización, cuantización y verificación de pesos |
| `stm_ipfs.py` | 156 | Subida a IPFS en cuatro niveles |

`from RFPRMN import X` y `RFPRMN().metodo()` siguen funcionando igual.

### 1.2 Rutas: una sola fuente de verdad (R1/R2/R5)

`stm_rutas.py` centraliza todas las rutas:

- **La herramienta no escribe bajo `CONTRRF/RFC` ni bajo `Sistema_Principal/PRY`.**
  `comprobar_ruta_segura()` lo impide y `es_zona_sincronizada()` lo consulta.
- **Cada dato tiene un sitio estable:** pesos en
  `STM_RFPRMN/.modelos/IAlocalDESCARGADA/`, registro en
  `STM_RFPRMN/registro_refactor.md`, configuración propia en
  `STM_RFPRMN/.config/`.

**R5 · rutas elegidas por el usuario.** `RFC_DIR` y `PRY_DIR` se resuelven por
este orden:

1. variables `RFPRMN_RFC_DIR` / `RFPRMN_PRY_DIR`,
2. `STM_RFPRMN/.config/rutas.json` (lo escribe `--configurar-rutas`),
3. las rutas oficiales del escritorio (compatibilidad),
4. el layout junto a la herramienta.

```bash
python RFPRMN.py --rutas              # ver rutas activas y su origen
python RFPRMN.py --configurar-rutas   # elegir carpetas (quedan guardadas)
```

Desde la shell interactiva son los comandos `rutas` y `configurar rutas`.

La configuración de IA local se busca en: `RFPRMN_IALOCAL_JSON` →
`PRY/actualizacion_*/src/STM_JSON` → `RFC/src` heredado → `.config`. Así
`ds ialocal` funciona aunque `RFC` esté vacío tras un `actualizar`.

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

La lectura de modelos usados ya no usa una regex sobre todo el texto (capturaba
marcas de tiempo como `12:50`): solo cuentan las cabeceras `## archivo — modelo`.

### 1.4 Issue #81 — gestión de ficheros (`stm_gestion.py` + `stm_fs.py`)

| Punto del issue | Solución |
|---|---|
| 1. Pérdida de datos | Ya no se borra el destino antes de copiar: copia a `.tmp`, verifica e intercambia |
| 2. Operaciones transaccionales | `reemplazar_directorio()` con rollback: si el intercambio falla se restaura el destino |
| 3. Verificación de copia | `verificar_copia()` compara **ruta relativa + tamaño + SHA-256** |
| 4. Rutas y symlinks | `es_subruta()`/`rutas_se_solapan()` impiden copiar un directorio dentro de sí mismo; `symlinks=True` |
| 5. Borrado fiable | `eliminar_ruta()` enumera los restos y lanza `OSError` con la causa |
| 6. Log de envíos | JSON **atómico** bajo bloqueo; el registro corrupto se conserva como `.corrupto` |
| 7. Versiones | Se verifica la nueva versión **antes** de purgar las anteriores |
| 8. Mantenibilidad | Imports muertos eliminados, errores específicos y rutas críticas protegidas |

### 1.5 Descarga de modelos (`stm_descarga.py`)

- Escritura en `<archivo>.part` y `os.replace` **solo** al terminar.
- Reanudación con `Range` si hay un `.part` previo.
- Reintentos con espera creciente y `timeout` por bloque.
- Validación de cabecera `GGUF` y tamaño mínimo: **un truncado ya no pasa**.
- Sin dependencia de `huggingface_hub`.

### 1.6 Modelos: el más ligero, y sin borrar lo tuyo (R3/R6)

**Siempre el modelo de código más ligero.** Los candidatos (configuración de
`IAlocal.json` más las familias de respaldo) se ordenan por número de
parámetros y:

1. se reutiliza el **más ligero ya instalado** (sin descargar nada);
2. si no hay ninguno, se descarga el más ligero que quepa en la RAM
   (con menos de 6 GB no se baja un 7B);
3. si `ollama pull` falla, se descarga el GGUF verificado y se **registra en
   Ollama con `ollama create`** (antes se bajaba ~1 GB que nunca se usaba).

**R3 · tus modelos no se borran.** Por defecto no se ejecuta `ollama rm` ni al
terminar ni al rotar por fallo: el modelo se excluye de la sesión y se anota.
El comportamiento antiguo se recupera con `--consumir-modelos` o
`RFPRMN_CONSUMIR_MODELOS=1`.

Ejemplo real en este equipo (tiene `qwen2.5-coder:7b` instalado):

```
› Modelo reutilizado (misma familia): qwen2.5-coder:7b
```

**Respaldo OpenRouter: desactivado por defecto.** Queda como opción pendiente
de configuración: la IA local es el camino normal y `stm_openrouter` solo se
usa si se activa de forma explícita.

```bash
python RFPRMN.py --openrouter --comando "ds ialocal"   # solo esta ejecución
# o bien, en STM_RFPRMN/.config/opciones.json:
#   { "openrouter": true }
# o con la variable RFPRMN_OPENROUTER=1
```

Si no está configurado, el flujo informa y termina sin hacer ninguna llamada
de red ni pedir la clave:

### 1.7 Publicación del registro al actualizar

`stm_registro_json/STM_RFC/envios.json` → `registro.md` en lenguaje natural →
borrado del json → pesos neuronales v2 (`stm_pesos`: vector global 64 + vector
por sección + cuantizado int8) → subida IPFS en 4 niveles (`stm_ipfs`:
IPFSManager → API `127.0.0.1:5001` → `ipfs.exe` → CID `QmLocal`) → borrado de
md y pesos. Utilidades: `vista_previa()`, `verificar_pesos()`,
`similitud_coseno()`, `url_pasarela()`.

### 1.8 Bytecode y consola

- `sys.pycache_prefix` apunta a `STM_RFPRMN/.pycache_rfprmn`; el `atexit`
  limpia `__pycache__` y esa carpeta al salir.
- Las cajas/paneles usan `_imprimir_seguro()` para consolas cp1252, y los
  mensajes de la cadena de configuración usan separadores ASCII.

## 2. Pruebas

Suite propia del módulo (**107 pruebas**, sin red, sin Ollama y sin tocar
RFC/PRY):

```bash
cd VersionDe_sesion/CONTRRF/STM_RFC/STM_RFPRMN
python -m pytest tests -q -p no:cacheprovider
# en equipos con sandbox de integridad baja, además: -p no:tmpdir
# y RFPRMN_TEST_TMP=<carpeta escribible>
```

| Archivo | Cobertura |
|---|---|
| `tests/test_rutas.py` | Nada se escribe bajo RFC/PRY, cadena de configuración, R5 (guardar/validar rutas) |
| `tests/test_modelos.py` | Registro de usados, política R3, «el más ligero», R6 (`ollama create`) |
| `tests/test_openrouter.py` | Respaldo desactivado por defecto y activación explícita (entorno/archivo) |
| `tests/test_fragmentos.py` | Cortes válidos, cobertura sin huecos, `try/except`, solape |
| `tests/test_flujo.py` | Un solo `ejecutar`, sin F821, ensamblado sin truncar, rotación y limpieza |
| `tests/test_fs.py` | Verificación por huella, swap con rollback, borrado, JSON atómico, bloqueo |
| `tests/test_gestion.py` | Protección de rutas críticas, registro atómico y recuperación de JSON corrupto |
| `tests/test_descarga.py` | Reanudación con `Range`, rechazo de truncados, no repetir descargas |

## 3. Deuda técnica

- **D1 (mitigada)**. `stm_fs` y `stm_modelos` quedan en 428 líneas: el próximo
  cambio grande exige dividirlos.
- **D2 (cerrada por R5)**. Las rutas oficiales ya no son obligatorias: manda lo
  que elija el usuario (`.config/rutas.json` o entorno).
- **D3**. Vectores por hash SHA-256, no embeddings semánticos reales.
- **D4**. El registro de símbolos de `__init__.py` se mantiene a mano (441
  líneas); conviene generarlo por AST.
- **D5**. Las rutas de limpieza de `stm_fs`/`stm_descarga` usan `except OSError`
  amplio a propósito: no deben romper el flujo por un temporal bloqueado.
- **D6 (cerrada por R1/R2)**. La configuración y los pesos ya no viven en
  `RFC/src`.

## 4. Deuda preexistente detectada (no introducida aquí)

- **P1**. `IPFSManager` de `STM_BKCH/compat_local.py` es un shim no-op.
- **P2**. `SBSTM/IALOCAL.py:239` llama a métodos que no existen en `IPFSManager`.
- **P4**. `actualizar()` rama heredada usa `ORIGEN/DESTINO` legacy.

## 5. Tareas pendientes

1. Sustituir los vectores por hash por embeddings reales (D3).
2. **Configurar el respaldo OpenRouter** si se quiere usar (hoy desactivado):
   clave en el Vault de STM_SGR o `.env`, y `openrouter: true` en
   `.config/opciones.json` o `RFPRMN_OPENROUTER=1`.
3. Generar el registro de símbolos por AST y adelgazar `__init__.py` (D4).
4. Dividir `stm_fs` y `stm_modelos` antes de añadir funciones (D1).
5. Resolver P1/P2 y eliminar la rama heredada P4.
6. Añadir la suite a un job de CI en la raíz (hoy no hay `.github/workflows/`).
