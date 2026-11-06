# Cuarentena R-01 — 2026-11-06

Ejecución de WP-0 (limpieza de los cuatro marcadores de R-01). Principio: **mover, no borrar la evidencia**.
Nada se ha compilado, abierto ni ejecutado; sólo lectura de hash y movimiento de ficheros.

Carpeta de cuarentena: `STM_DOC/rescate_zona_20261105/cuarentena_r01_20261106/`
(excluida de commits junto con el resto de `rescate_zona_20261105/`, igual que las copias `.orig`).

## Ficheros movidos (evidencia preservada)

| original | sha256 | tamaño | mecanismo | nueva ubicación |
|---|---|---|---|---|
| `MTBGT/WoldVirtualP2P3D/SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/public/fonts/fa-brand-400.orc` | `89adac5ba294c6545debf8d6255a20602354d04f71809c267ae4997f1cc3bb89` | 30.627 B | A5-1 | `cuarentena_r01_20261106/fa-brand-400.orc` |
| `STM_HRTS/opencode/init` | `8f79baa43b4a51520842a206a83005a09a4a0434c07c8979dd1c426b2ed6fa1c` | 32.436 B | A5-2 | `cuarentena_r01_20261106/opencode_init` |

Ambos sha256 coinciden con los documentados en la auditoría (A5-1 y A5-2). El `init` movido tiene 34 saltos
de línea y 32.436 B (la línea 35 sin salto final = 31.751 caracteres ofuscados), consistente con lo medido.

## Trigger neutralizado (no es un fichero movido, es una edición)

| fichero | cambio | mecanismo |
|---|---|---|
| `STM_HRTS/opencode/package.json` | eliminado el script `"start": "node init && ./opencode.bat"` (quedaba el único `node init` del árbol) | A5-2 |

La consola se sigue pudiendo abrir por las vías legítimas que no pasan por `node init`:
`lanzar_opencode.bat` y `opencode.bat` ejecutan `opencode.exe` directamente.

## Evidencia ya inertizada (no movida: ya estaba en la zona de rescate)

| fichero | sha256 | mecanismo | estado |
|---|---|---|---|
| `STM_DOC/rescate_zona_20261105/duplicados_utils_flat/transport.py` | `45f1e5c405d1253b0014a17619581d31e1b94fdca8733519d84b9795a460f53a` | A1-1 | copia de evidencia, nunca importada (`grep -rn "transport" --include=*.py` = 0) |

## Resultado de la verificación (2026-11-06)

Sobre el árbol activo **excluyendo `STM_DOC/`** (documentación y archivo de evidencia):

| marcador | resultado |
|---|---|
| `runOn: folderOpen` | 0 coincidencias |
| `allowAutomaticTasks` | 0 coincidencias |
| `*.orc` | 0 ficheros |
| `transport.py` | 0 ficheros |

Detalle de la medición: `find . -name "*.orc"` → 0 fuera de `STM_DOC/`; `find . -name "transport.py"` → 0
fuera de `STM_DOC/`; `grep -rn "runOn\|allowAutomaticTasks"` en ficheros de texto fuera de `STM_DOC/` → 0
(las únicas coincidencias restantes son la documentación y binarios: `opencode.exe`, DLL de xUnit y
`libAvaloniaNative.dylib`, que son falsos positivos por búsqueda binaria).

## Qué queda abierto (no es parte de esta casilla)

- **R-01b**: desofuscar las dos cargas JS e inspeccionar la transacción de Ethereum en sandbox aislada,
  auditar `d510acd` / `3caf0e7` (PR #47) y anunciar el alcance a las máquinas expuestas.
- **Replantación por merge**: `DevChatGPTIA`, `DevCursorIA`, `DevDeepSeekHarnessIA` y `DevDevinIA` siguen
  llevando el snapshot con `.orc` y `transport.py`; no fusionarlas.
- El criterio de aceptación de la hoja de ruta se cumple para el árbol activo de la zona; la promoción a
  `main` sigue siendo decisión del dueño (R16).
