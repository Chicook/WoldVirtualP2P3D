# STM_RFC · README del sistema RFPRMN

Fecha: 2026-10-14. Todo lo descrito está implementado y verificado por
ejecución en `STM_RFPRMN/` (fachada `RFPRMN.py` + paquete `STM_RFPRMN_stmDL/`).

## 1. Lo implementado

### 1.1 Refactorización modular (tope 450 líneas por archivo)

`RFPRMN.py` original (1813 líneas, ~75 funciones) dividido sin cambiar
firmas ni comportamiento:

| Archivo | Líneas | Contenido |
|---|---|---|
| `RFPRMN.py` | 390 | `class RFPRMN` (~35 métodos que delegan) + menú/CLI (`--ayuda/--version/--estado/--presupuesto/--comando`) + `__all__` de compatibilidad |
| `STM_RFPRMN_stmDL/__init__.py` | 375 | `RegistroRFPRMN` (carga perezosa PEP 562, 116 símbolos) + `verificar_presupuesto/modulos_estado/informe_salud` |
| `stm_base.py` | 274 | Estilo/UI, constantes, errores, rutas oficiales, `atexit` de limpieza |
| `stm_gestion.py` | 416 | fs + `refactorizar/enviar/actualizar/crear_*`, borrado con reintentos |
| `stm_analisis.py` | 262 | `AnalisisArchivo` + plan + LucIA local |
| `stm_modelos.py` | 433 | HF/Ollama/OpenRouter |
| `stm_refactor.py` | 257 | Fragmentos + validación + `comando_ds_ialocal` |
| `stm_flujo.py` | 298 | `FlujoRefactorLucIA` intacta |
| `stm_registro.py` | 448 | Publicación del registro (ver 1.4) |

`from RFPRMN import X` y `RFPRMN().metodo()` siguen funcionando igual.

### 1.2 Rutas oficiales fijas

`stm_base.py`: `RUTA_RFC_OFICIAL = .../VersionDe_sesion/CONTRRF/RFC` y
`RUTA_PRY_OFICIAL = .../VersionDe_sesion/Sistema_Principal/PRY`.
`refactorizar` copia `PRY/<actualizacion>/src → RFC/src` verificado por
conteo; `actualizar` versiona `RFC → PRY/actualizacion_*`, purga
anteriores y vacía RFC. Corregidos dos desplazamientos de nivel
(`STM_RFPRMN_stmDL/` + `STM_RFC/`) que mandaban a la rama heredada
`Construccion/...`.

### 1.3 Compatibilidad consola Windows (cp1252)

Las 7 impresiones de cajas/paneles Unicode (`_caja/_panel`) usan
`_imprimir_seguro()`; antes el menú crasheaba al arrancar.

### 1.4 Publicación del registro al actualizar

`stm_registro_json/envios.json` → `registro.md` en lenguaje natural
→ borrado del json → pesos neuronales v2 (vector global 64 + vector por
sección + cuantizado int8) → subida IPFS en 4 niveles
(IPFSManager → API `127.0.0.1:5001` → `ipfs.exe` del sistema → CID
`QmLocal` local) → borrado de md y pesos. Directorio limpio.
Utilidades: `vista_previa()`, `verificar_pesos()`, `similitud_coseno()`,
`url_pasarela()`. **Verificado con CID real**:
`QmQ5bjYVr6Xxyjy5xPNPUZxsBecMaRhmMTGJubDwbHLvjq` (vía cli).

### 1.5 Bytecode fuera de los árboles sincronizados

`sys.pycache_prefix` apunta a `STM_RFPRMN/.pycache_rfprmn` (antes al
pycache de `STM_CH` dentro de `RFC/src`, lo que ensuciaba el sincronizado
e impedía vaciar RFC). `eliminar_ruta()` reintenta 4 veces con espera
ante bloqueos de Windows + prefijo `\\?\`. `limpiar_caches()` borra
`__pycache__/` y `.pycache_rfprmn/` al publicar; el gancho `atexit`
los borra al salir de CUALQUIER ejecución.

## 2. Deuda técnica generada

- D1. `stm_gestion` (416) y `stm_registro` (448) rozan el tope; el
  próximo cambio en ellos exige extraer un submódulo nuevo.
- D2. Rutas oficiales absolutas cableadas (`RUTA_*_OFICIAL`): no portable
  fuera de este equipo. Falla a derivado si no existen.
- D3. Vectores por hash SHA-256, no embeddings semánticos reales
  (deterministas y verificables, pero sin significado vectorial).
- D4. `__init__.py` con re-exports tolerantes (`try/except`): puede
  ocultar errores de import de backends pesados.
- D5. Sin pruebas automatizadas: la verificación es manual
  (`py_compile` + ciclos reales + `verificar_presupuesto()`).
- D6. `limpiar_caches()` en `publicar` es redundante con el `atexit`;
  se conserva para feedback visible en sesión interactiva.

## 3. Deuda preexistente detectada (no introducida aquí)

- P1. `IPFSManager` de `STM_BKCH/compat_local.py` es un shim no-op
  (CIDs `QmLocal…` sin daemon). La subida real solo ocurre por
  API/CLI si hay daemon o binario accesible.
- P2. `SBSTM/IALOCAL.py:239` llama a `mgr.subir_pesos_neuronales()` /
  `mgr.add()`, que no existen en `IPFSManager`.
- P3. `stm_flujo.py` conserva el `def ejecutar` duplicado del original
  (gana la segunda definición; funciona, pero confunde).
- P4. `actualizar()` rama heredada usa `ORIGEN/DESTINO` legacy
  (`Construccion/...`); solo se alcanza fuera del layout actual.

## 4. Tareas pendientes

1. Sustituir vectores por hash por embeddings reales si aparece
   dependencia admitida (p. ej. modelo local ya descargado).
2. Migrar `RUTA_*_OFICIAL` a configuración (`IAlocal.json` o `.env`)
   para portabilidad.
3. Dividir `stm_gestion`/`stm_registro` antes de añadir funciones
   (límite 450).
4. Añadir suite mínima de pruebas (presupuesto, paridad de símbolos
   vía AST, ciclo `publicar` con json sintético).
5. Resolver P2 (métodos inexistentes en `IALOCAL.py`) y P3 (duplicado
   `ejecutar`) cuando se toque ese código.
6. Asegurar daemon IPFS en arranque si se quieren CIDs reales siempre
   (hoy depende de que esté corriendo).
7. Eliminar D6 si se prefiere limpieza solo por `atexit`.
