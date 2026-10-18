# WoldVirtualP2P3D 🌐

> **WoldVirtual3Dp2p_DEMO_actualizacion_b5592aff** — Metaverso P2P 3D con sistema cognitivo LucIA

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v0.0.01__actualizacion__b5592aff-blue)](CHANGELOG.md)
[![Godot 4.7](https://img.shields.io/badge/Godot-4.7-478cbf?logo=godot-engine&logoColor=white)](https://godotengine.org)
[![IPFS](https://img.shields.io/badge/IPFS-Kubo-65c2cb?logo=ipfs)](https://docs.ipfs.tech)
[![Tamaño](https://img.shields.io/badge/tama%C3%B1o-752%20MB-lightgrey)](#)

## Sesión 2026-10-16 — metaverso WoldVirtualP2P3D (verificado en ejecución Godot 4.7.2)

Rama principal: `WoldVirtualP2P3Dv0001LCV1`. Release: `v0.0.02_1_actualizacion_86bea3a9`
(tag + asset `v0.0.02_1_actualizacion_86bea3a9.zip` con el proyecto Godot jugable de rutas cortas).
Código: `VersionDe_sesion/Sistema_Principal/PRY/actualizacion_86bea3a9/src/MTBGT/WoldVirtualP2P3D/`.

- **Arranque en 4 fases** (`gdscrip/Boot.gd`): registro con avatar (nick en `user://registro.cfg`) → zona del portal (se cruza andando) → ventana "Conectando a la red P2P..." → isla al llegar `ChunkManager.mi_isla_lista`.
- **Avatar humanoide hm1** sustituye a la cápsula (`ISLA3Dblock.tscn`): cámara orbital con retardo, sprint AltGr, `snap_camera()` tras teleporte/spawn.
- **Panel de islas**: `Isla {nombre} ({uuid6})`, etiqueta superior sin solapes; nicks únicos (`Ana#2`) y visibles en todos los peers (`island_owners` viaja en el RPC de spawn).
- **Clones remotos** (`PlayerSync.gd`): avatar hm1 real con nick y animación replicada (idle/andar/correr/aire), sin cápsulas.
- **Avisos del analizador** corregidos; accesos entre scripts por señal/`call()`/`get()`.
- Detalle en `src/MTBGT/RESUMEN_SESION.md` (qué se hizo, deuda técnica y hoja de ruta del selector de avatares).

Limitaciones conocidas: release con zips automáticos gigantes (500 MB) y rutas de 345 caracteres en bloques IPFS → usar el asset adjunto, no el zip automático; `owner_names` se pierde parcialmente al migrar de anfitrión; réplicas sin strafe.

## Hoja de ruta — Metaverso WoldVirtualP2P3D (2026-10-18)

> Detalle completo en `VersionDe_sesion/CONTRRF/TLLDCD/src/MTBGT/RESUMEN_SESION.md`
> (secciones 2.1 a 2.8). Aquí se resume lo pendiente y **cómo se implementa**.
> Nota clave de diseño: los **shape keys son solo para avatares**; el terreno/islas
> se editan con otras técnicas (no con morph targets).

### A. Visor C# "wold virtual p2p 3d" (basado en Singularity)

Carpeta: `VersionDe_sesion/Sistema_Principal/PRY/actualizacion_86bea3a9/src/VSC#/` (ver su `README.md`). Estado: pendiente.

- **Fase 0 — decisiones**: motor (recomendado **Godot 4 C#**, reutiliza escenas/`AnimationTree` de hm1; alternativa Silk.NET+OpenGL), red **ENet puerto 8910** (hablar directo con el mundo Godot, sin pasarela), avatares importados desde hm1 (glTF/FBX) con sus 8 animaciones.
- **Fase 1 — núcleo y conexión**: ventana 3D + cliente ENet → handshake `_claim_island` con nick; recibir `pos/rot/nick/estado` de cada avatar y mostrar cápsulas de color (paridad con `PlayerSync.gd`); enviar estado propio a ~10 Hz.
- **Fase 2 — mundo e islas**: pedir la rejilla (`chunk_size 199.5`, 10 por fila, serpentina) y la lista `(índice, nick, uuid6)`; render terreno/océano; panel `Isla {nick} ({uuid})` + teleporte (`SPAWN_HEIGHT 45` + `snap_camera`).
- **Fase 3 — avatar completo**: hm1 con esqueleto + `AnimationTree` (8 estados), cámara orbital con retardo (`follow_speed 6.0`), entrada invertida 180° (hm1 mira a +Z), sprint AltGr, clones remotos con nick.
- **Fase 4 — flujo de entrada**: registro (nick ≥ 3 letras) → zona del portal (`Area3D`) → ventana "Conectando a la red P2P..." hasta `mi_isla_lista` (paridad con `Boot.gd`).
- **Fase 5 — paridad y cierre**: matriz de paridad Godot ↔ C# (mismos RPC, nombres e uuids deterministas `WVP3D-isla-{n}`); prueba cruzada Godot ↔ C# en la misma isla; release versionada `vX.Y.Z_actualizacion_<id>`.

### B. Carrusel diverso y avatares únicos (fase demo, Godot)

Estado: no implementado. Hoy el carrusel (`gdscrip/SLAV.gd` + `SLAV.tscn`) muestra siempre los mismos 6 (`AVMJ1, AVMJ2, AVH1, AVH2, AVMJ3, AVH3`).

- **Catálogo dinámico**: dejar de leer los 6 fijos de `SLAV.tscn`; `SLAV.gd` calcula la lista al arrancar.
- **Filtro "usados"**: excluir los avatares ya elegidos; rellenar cada hueco con una variante nueva (rec color determinista por `seed`).
- **Regla "5 restantes + 1 diferente"**: al elegir y cerrar, el siguiente arranque ofrece los otros 5 + 1 distinto.
- **`owner_uuid`** (UUID v4) en el primer registro (`user://registro.cfg`) para reconocer al usuario.
- **Cambios de catálogo pedidos**:
  - **`AVMJ4`** (huérfano en disco) → recuperarlo como **primer sustituto, con ropa distinta** (reestilizar colores/materiales, conservar las 5 acciones).
  - **Avatar base (`userbaseh1`/hm1)** → **estilizarlo un poco y añadirlo al carrusel** (darle antes una acción de reposo válida; hm1 no trae `paradoMJ1_1`).
  - **Orden del carrusel** → **alternar chica/chico** (p. ej. `AVMJ1, AVH1, AVMJ2, AVH2, AVMJ3, AVH3`), no agrupado; cambiar los 3 arrays de `SLAV.tscn` en el mismo orden.

### C. Persistencia en IPFS (avatares e islas)

Pedido: al cerrar se sube el JSON de avatares elegidos a IPFS; al abrir se descarga y el carrusel muestra otros.

- **Infra existente**: daemon Kubo (`src/STMIPFS/SBSTMPYIPFS/ipfs_launcher.py`, `src/STMIPFS/STM_BAT_IPFS/arrancar_daemon.bat`), API `http://127.0.0.1:5001`, gateway `:8080`.
- **Al cerrar** (`NOTIFICATION_WM_CLOSE_REQUEST` en `Boot.gd`): volcar `user://avatares_usados.json` → `ipfs add --pin` → guardar el CID en puntero `user://ipfs_avatares.cid`.
- **Al arrancar**: leer el puntero → `ipfs cat <CID>` → fusionar con la caché local **antes** de `_mostrar_carrusel()` (hoy es lo primero en `_ready`).
- **Vías**: CLI `OS.execute("ipfs", [...])` (recomendada, simple) o API HTTP `HTTPRequest` (`/api/v0/add`, `/api/v0/cat`).
- **Robustez**: daemon caído → seguir con caché local; cierre forzado → escribir la caché **al confirmar** también.
- **JSON** (`version: 1`): por avatar `owner_uuid`, `nick`, `estado` (`libre`/`reservado`/`usado`), `fecha_alta`, `ultimo_uso`, `seed`, `shapes`, y `puntero_previo` (CID anterior) para historial sin servidor central.

### D. Shape keys de Blender → Godot (retoque del avatar)

- **Blender → glTF**: los morph targets viven en la **malla**; se exportan activando esa opción. Ceñirse a 10-30 expuestos para no inflar el `.glb`.
- **Import en Godot**: cada shape key = **blend shape** de la `MeshInstance3D`; API `get_blend_shape_count()` / `set_blend_shape_value(i, valor)` (0..1). No tocan el `AnimationTree` ni el rig Mixamo.
- **UI de retoque**: en `registro.tscn` (o paso "Personalizar" tras el carrusel) con sliders por grupo (`Edad`, `Musculatura`, `Nariz`, `Ojos`, `Boca`, `Altura facial`...).
- **Guardado**: valores en el campo `shapes` del JSON (mismo flujo IPFS de C).
- **Replicación P2P**: el spawn lleva `shapes`; en `PlayerSync.gd` aplicar `set_blend_shape_value` a cada clon remoto.
- **Ojo con `.blend`**: Godot **no** lee `.blend` de forma nativa; llama a Blender y lo convierte a glTF por dentro. Para control y para no depender de Blender al importar, **exportar `.glb` explícito** con morph targets.

### E. Editor de islas por usuario (a gusto de cada uno)

Contexto real (`ChunkManager.gd`): cada isla es una copia de `$ISLA3DCHUNK` (`ISLA3Dblock.tscn`) en rejilla serpentina de 10 por fila (`islands_per_row`, `chunk_size 199.5`), con dueño conocido en todos los peers (`island_owners[index] = [id, nick]`, `ChunkManager.gd:229`).

- **Modelo**: **base reproducible por `seed`** + **delta de ediciones** (`isla_{index}.json`: `heightmap`, `props[]`, `paint[]`, `agua/cielo`). Se guarda el delta, no la geometría → barato en P2P.
- **Relieve**: (1) **heightmap** con shader de desplazamiento — recomendado (se comparte la textura, no los vértices); (2) `MeshDataTool` para sculpt; (3) **bloques voxel** (`GridMap`), que encaja con `chunk3DBLOCK`.
- **Construir/decorar**: inventario de assets + gizmo → `props[]` (`asset_id`, `pos`, `rot`, `scale`); `MultiMesh`/`GridMap` para evitar miles de nodos.
- **UI**: modos Terraformar / Construir / Pintar / Ajustes, pincel con radio/fuerza, undo/redo, entrada con `B`.
- **Autoridad/P2P**: **solo el dueño edita** (resto solo lectura); se replican **operaciones** por `rpc`, no el estado completo; a late-joiners se envía el delta justo después de `add_child(new_island)` (`ChunkManager.gd:246`); al reclamar isla (`_claim_island`/`_adopt_or_register`) se reaplica el delta.
- **Persistencia**: delta en IPFS (`isla_{index}.json` + puntero CID) o registrar el CID en `src/STM_CH/blockchain_ledger.json`; `asset_id` estable.
- **Rendimiento**: limitar radio/altura del pincel, agrupar el trazo y enviarlo al soltar el botón.

## Actualización general del sistema — 2026-09-25 (verificada en ejecución)

> Lo anterior a esta sección describe el árbol heredado `LC/` (referencia histórica).
> El árbol vivo actual es `VersionDe_sesion/CONTRRF/` y todo lo verificado abajo
> se probó arrancando el sistema de verdad (4/4 subsistemas en verde + inferencia real).

### Nuevo layout

```text
VersionDe_sesion/
├── CONTRRF/
│   ├── TLLDCD/
│   │   ├── src/                        # árbol de trabajo (único módulo en raíz: STMGNRL/mainLCSTM.py)
│   │   │   ├── STMGNRL/mainLCSTM.py    # orquestador (449 líneas, límite 450)
│   │   │   ├── SBSTM/                  # sesión P2P, IAFREE, STYLOS, RPLC, voz, selector_modelos, accesores
│   │   │   ├── STM_BKCH/               # BKSVCB + bksvcb_net + compat_local (shims PSNRCV/IPFS)
│   │   │   ├── STM_SGR/vault_openrouter.py  # key cifrada, s/n sin desvelarla, solo :free
│   │   │   ├── STM_CH/                 # TODO el runtime (pycache, PSNRL/, ledger, cachés) + rutas.limpiar()
│   │   │   ├── STM_JSON/               # registro central de los 5 JSON (canónicos + volátiles)
│   │   │   ├── STM_HRTS/               # pyproject.toml + registro_hrts.py + CI
│   │   │   ├── STM_IA/                 # IAlocalDESCARGADA + registro_refactor.md
│   │   │   ├── STM_DOC/                # README del sistema, desarrollo.md, memoria.md
│   │   │   ├── STMIPFS/                # launcher Kubo + bat_runner + repo .ipfs
│   │   │   └── LC_STM/red_neuronal/    # 50 neuronas (ENRN/RF_EN/RF_SL/RNP/SLRN, ≤450 líneas c/u)
│   │   └── STM_RFC/RFPRMN.py           # herramienta de proyecto (enviar/refactorizar/actualizar/ia local/ds ialocal)
│   └── RFC/                            # zona de entrega (se vacía al actualizar)
└── Sistema_Principal/PRY/              # versiones actualizacion_<id> (solo la última)
```

### Arranque verificado (responde `s`, sale con `salir`)

```powershell
python VersionDe_sesion/CONTRRF/TLLDCD/src/STMGNRL/mainLCSTM.py
# [1/4] BKSVCB ACTIVA · [2/4] PSNRCV OK 50 sinapsis · [3/4] Ledger->Pesos
# [4/4] Sesión ACOPLADA · [JSON] 4/5 · [HRTS] woldvirtualp2p3d 0.0.1
python VersionDe_sesion/CONTRRF/TLLDCD/STM_RFC/RFPRMN.py   # herramienta interactiva
```

### Flujo de entrega (todo verificado con conteo de ficheros, 614/614)

`enviar` (src→RFC, bidireccional, registra en `envios.json`, verifica antes de borrar) →
`refactorizar` (PRY/última/src→RFC/src) → `actualizar` (RFC→PRY/`actualizacion_<id>`, purga viejas, vacía RFC).

### Seguridad

Vault con key cifrada embebida: la terminal solo pregunta
`¿Desea confirmar conexión con OpenRouter a modelos IA free? s/n` y muestra
`sk-o...****`. Filtro duro a modelos `:free`. `.env` ignorado por git;
rotar la key si se expuso (ver `STM_DOC/README.md` D3).

### Deuda técnica y hoja de ruta (Actualizado tras sesión interactiva 2026-10-12)

A partir de las respuestas de autodiagnóstico obtenidas de LucIA en consola interactiva (`mainLCSTM.py`), se desprenden los siguientes puntos críticos en desarrollo y pendientes:

1. **Diagnóstico e Introspección del Estado Interno**:
   - LucIA actualmente responde que no puede consolidar por sí misma un resumen completo y fidedigno del estado global de su sistema cuando se le pregunta en lenguaje natural.
   - *Pendiente*: Inyectar dinámicamente en el contexto del prompt (`system prompt` o contexto sináptico) un volcado estructurado del estado de los subsistemas (bloques de blockchain, estado de IPFS, modelos activos, telemetría y sinapsis) para que pueda responder a preguntas de autodiagnóstico sin alucinaciones ni bloqueos.

2. **Resolución de Truncamiento en Respuestas Largas (Telemetría / Servidores)**:
   - Al solicitar análisis exhaustivos de telemetría y arquitectura, la salida de los modelos locales pequeños (`qwen2.5:0.5b`, `llama3.2:1b`) se corta abruptamente por el límite de tokens (`num_predict: 400` en `gestor.py`).
   - *Pendiente*: Implementar mecanismo de continuación automática o paginación/streaming cuando la respuesta exceda el límite de tokens, ampliando el buffer o permitiendo re-enganche conversacional.

3. **Conexión a OpenRouter y Gestión del Vault de Credenciales**:
   - Al preguntar sobre OpenRouter, LucIA confunde la plataforma con modelados estáticos (`LSTM-Word2Vec`, `ConvLSTM`) en lugar de reconocer su integración nativa con el catálogo `:free` de OpenRouter.
   - Cuando el vault arranca sin clave (`Vault sin key provisionada. Modo local/reflejo`), el sistema cae automáticamente a inferencia local vía Ollama.
   - *Pendiente*: Alinear el prompt de sistema para que LucIA reconozca su conector `IAFREE` y la lista de modelos remotos disponibles; documentar y facilitar la provisión de la key en el vault `STM_SGR/vault_openrouter.py`.

4. **Robustez en Decodificación de Subprocesos (Solucionado)**:
   - Se corrigió el error `UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f` en `_readerthread` de Windows al forzar `encoding='utf-8'` y `errors='replace'` en todas las invocaciones de `subprocess.run` (Ollama e IPFS).

5. **Motor de Voz Neuronal Oficial Integrado**:
   - Se fijó la voz oficial de LucIA (18 años, es-ES peninsular) mediante síntesis con DSP cálido (resampling 1.16x, realce en medios y compresión sedosa), integrada en `voice_engine.py` y monitorizada al inicio de `mainLCSTM.py`.

---

Plataforma distribuida de computación cognitiva neuronal, consenso blockchain inmutable y persistencia descentralizada IPFS, con inferencia híbrida (modelos locales vía Ollama/LM Studio y catálogo gratuito de OpenRouter), motor de voz neuronal y diseño de terminal interactiva cyber-bioluminiscente.

---

## Estado actual verificable de LucIA

> **Fuente factual:** `LC/ARCHITECTURE_CHANGELOG.json` y las comprobaciones estructurales ejecutadas por `LC.compatibility`. Esta sección distingue entre código presente, capacidad parcialmente integrada y comportamiento validado de extremo a extremo.

- **Versión de arquitectura:** `2026.3.1-refactor-2`.
- **Cambios registrados:** 7.
- **Capacidades registradas:** 8.
- **Estado operativo de LucIA:** observacional y reportorial. LucIA puede leer el manifiesto, diagnosticar el estado y comunicar limitaciones, pero no modifica por sí misma el código ni la configuración.
- **Último cierre conocido:** el cierre informa correctamente `refactor parcial_omitido` cuando HRCTRC omite módulos vivos. El conteo observado más reciente fue de 5 omisiones.

### Capacidades verificadas

- `imports.compatibility`: resuelve aliases heredados hacia módulos activos sin cargar respaldos de `CHG`.
- `diagnostics.factual-context`: inyecta el manifiesto factual en el contexto de LucIA y evita inventar changelogs.
- `diagnostics.closure-status`: el resumen de cierre distingue entre refactor aplicado, parcial omitido y fallido, e informa el número de omisiones.

### Capacidades parciales

- `runtime.local-ai-config`: `LC/modelosIAlocal/IAlocal.json` existe y define Ollama, LM Studio y modo offline; todavía no está verificado el failover automático completo.
- `blockchain.transaction-safety`: las transacciones pendientes se confirman después de minar y persistir el bloque; no están validados todos los escenarios de reorg, fork y concurrencia.
- `session.ollama-config`: `SNSBSTNPRB` lee y normaliza la configuración de Ollama; faltan pruebas de timeout, TLS, autenticación y extremos de configuración.
- `purger.path-safety`: `logger` y `CHG_DIR` están definidos en las partes del purgador; faltan pruebas de carga, dry-run y auditoría prolongada.

### Capacidad bloqueada

`live-module-refactor` permanece en estado `blocked`. HRCTRC no aplica refactors a módulos vivos sin una prueba previa aprobada. En el último cierre fueron omitidos:

- `LC/celebro/BKSVCB.py`
- `LC/celebro/CMFG/SBSTM/INTEGRACIONRF.py`
- `LC/celebro/CMFG/SBSTM/SNSBSTNPRB.py`
- `LC/celebro/CMFG/ipfs_manager.py`
- `LC/celebro/red_neuronal/RF_EN/RFEN1_RN_4.py`

Estas omisiones son deliberadas: no deben describirse como refactors aplicados hasta superar sus pruebas y el mecanismo de aprobación correspondiente.

### Comprobaciones actuales

- `compatibility_layer`: **OK**.
- `local_ai_config`: **OK** como comprobación de presencia y estructura básica; no equivale a una prueba end-to-end.
- `transaction_safety_fix`: **OK** como comprobación de la implementación presente; no cubre todavía todos los escenarios de consenso.
- `architecture_tests_available`: **OK**; existen pruebas de arquitectura.
- `architecture_tests_verified`: **PENDIENTE**; el arranque de LucIA no ejecuta automáticamente toda la suite.
- `purgador_logger`: **OK**.

No se deben afirmar como implementados o verificados, sin pruebas adicionales, WAL, `fsync`, reorg automático, cron seguro, mitigación CVE, balanceo entre backends, validación completa de JSON Schema ni tests end-to-end.

---

## Pendientes de desarrollo y plan de cierre

El orden siguiente prioriza observabilidad y seguridad antes de desbloquear módulos vivos.

### Fase 0 — Línea base reproducible

1. Ejecutar la suite de arquitectura en el entorno real con todas sus dependencias.
2. Guardar el resultado, duración, versión de Python y dependencias utilizadas.
3. Separar en los informes `tests disponibles`, `tests ejecutados` y `tests aprobados`.
4. Hacer que el cierre de LucIA marque `architecture_tests_verified=OK` únicamente cuando exista un resultado válido de esa ejecución.

**Criterio de cierre:** informe reproducible y verificable; ningún diagnóstico debe afirmar que la suite pasa si no se ha ejecutado.

### Fase 1 — Configuración y failover de IA local

1. Validar `IAlocal.json` contra un esquema versionado.
2. Implementar health-check real para Ollama y LM Studio con timeout explícito.
3. Definir la política de selección: backend primario, fallback, modo offline y recuperación.
4. Registrar en el diagnóstico qué backend está vivo y cuál fue utilizado.
5. Probar reinicio, backend inexistente, timeout, respuesta inválida y recuperación posterior.

**Criterio de cierre:** una prueba end-to-end demuestra la transición Ollama → LM Studio → offline sin intervención manual y sin perder el contexto de sesión.

### Fase 2 — Endurecimiento de la sesión Ollama

1. Validar endpoint, modelo, timeout, TLS, autenticación y `keep_alive`.
2. Rechazar configuraciones incompletas con mensajes accionables.
3. Definir qué parámetros pueden cambiarse en caliente y cuáles requieren reinicio.
4. Añadir pruebas de endpoint caído, modelo inexistente y respuesta lenta.

**Criterio de cierre:** `SNSBSTNPRB` informa una configuración normalizada y falla de forma controlada ante cada error previsto.

### Fase 3 — Seguridad transaccional y persistencia

1. Añadir recuperación del mempool después de reinicio.
2. Diseñar persistencia atómica de transacciones pendientes y bloques.
3. Probar doble gasto, concurrencia, reinicio durante persistencia y bloques huérfanos.
4. Definir y probar la política de reorg/fork antes de declarar esa capacidad verificada.
5. Medir la latencia y el comportamiento ante errores de disco.

**Criterio de cierre:** las pruebas demuestran que no se pierden transacciones pendientes ni se confirman estados que no estén persistidos.

### Fase 4 — Purgador seguro y auditable

1. Añadir modo `dry-run` antes de cualquier purga programada.
2. Validar que cada ruta objetivo permanezca dentro del directorio permitido.
3. Probar directorios vacíos, archivos bloqueados, enlaces, rutas inexistentes y grandes volúmenes.
4. Centralizar el logger y conservar auditoría más allá de la rotación corta.
5. Registrar en el informe qué se eliminó, qué se omitió y por qué.

**Criterio de cierre:** una ejecución de prueba no destructiva y una ejecución controlada producen informes completos y no permiten salir del ámbito autorizado.

### Fase 5 — Desbloqueo progresivo de módulos vivos

Aplicar el mismo ciclo a cada módulo, uno por uno:

1. Capturar el comportamiento actual con pruebas de contrato.
2. Crear una prueba de regresión específica para el cambio.
3. Ejecutar el refactor en una copia o rama aislada.
4. Comparar imports, interfaces, estado persistido y rendimiento.
5. Aprobar el resultado antes de permitir que HRCTRC lo aplique al sistema vivo.
6. Mantener rollback y registrar el resultado en el manifiesto.

Orden recomendado: `INTEGRACIONRF.py`, `SNSBSTNPRB.py`, `BKSVCB.py`, `ipfs_manager.py` y, por último, `RFEN1_RN_4.py`.

**Criterio de cierre:** cada módulo tiene pruebas aprobadas, rollback documentado y aparece como `verified` o `partial` con evidencia; nunca se cambia a `verified` solo porque el proceso terminó sin excepción.

### Fase 6 — Diagnóstico y documentación continua

1. Actualizar `LC/ARCHITECTURE_CHANGELOG.json` en cada cambio real.
2. Mantener el diagnóstico de LucIA alineado con los logs de cierre.
3. No registrar como capacidad verificada una función que solo esté definida en configuración.
4. Conservar la diferencia entre estado estructural, prueba unitaria y prueba end-to-end.

**Criterio de cierre:** el manifiesto, el cierre de sesión, los tests y este README describen el mismo estado.

---

## Diseño y capacidades declaradas del sistema

La sección siguiente describe la arquitectura y las funciones previstas o integradas en el código. Para conocer qué está verificado actualmente, prevalece siempre la sección [Estado actual verificable de LucIA](#estado-actual-verificable-de-lucia) y el manifiesto `LC/ARCHITECTURE_CHANGELOG.json`.

El proyecto ha evolucionado desde una estructura heredada hacia una arquitectura modular, unificada y optimizada bajo el paquete central **`LC`** (*LucIA Cognitive*):

### 1. 🧠 Red Neuronal Distribuida (50 Neuronas Activas)
Se estructuraron e integraron 50 neuronas activas organizadas en 5 subsistemas especializados (`LC/celebro/red_neuronal/`):
- **ENRN (10 neuronas)**: *Entrada Recurrente No Lineal*. Manejo de percepción sensorial, codificación y transformaciones no lineales primarias (`EN1_RN.py` a `EN10_RN.py`).
- **RF_SL (10 neuronas)**: *Aprendizaje Supervisado y Residual*. Procesamiento y regularización supervisada (`RFSL1_1.py` a `RFSL1_10.py`).
- **RF_EN (10 neuronas)**: *Retroalimentación y Refuerzo Dinámico*. Modulación adaptativa y aprendizaje por refuerzo continuo (`RFEN1_RN_1.py` a `RFEN1_RN_10.py`).
- **RNP (10 neuronas)**: *Plasticidad Sináptica y Memoria Asociativa*. Métodos adaptativos de gradientes, compuertas de atención y retención (`RN11.py` a `RN14_PuertasAtencion.py`).
- **SLRN (10 neuronas)**: *Optimizadores y Convergencia Sináptica Temporal*. Algoritmos de convergencia y optimización adaptativa (`SL11.py` a `SL12.py`).

### 2. ⛓️ Blockchain Neuronal y Consenso PoNL (`BKSVCB.py`)
- Servidor blockchain inmutable con consenso **PoNL** (*Proof of Neural Learning*).
- Estructura criptográfica con hashing doble SHA-256, cálculo de árbol de transacciones (**Merkle Root**) y dificultad de minado ajustable.
- **Transducción Ledger ➔ Pesos**: Al arrancar, transforma el historial de transacciones y bloques del `blockchain_ledger.json` en tensores sinápticos activos en memoria.
- **Persistencia en cada bloque**: Registro de transacciones neuronales (prompts, respuestas, deltas de pesos y firmas del modelo).
- **Servidor HTTP JSON-RPC / REST** embebido (puerto por defecto `8545`) para consulta de bloques, minado y estado del consenso.

### 3. 🌐 Persistencia Descentralizada IPFS (`CMFG/ipfs_manager.py`)
- Gestor de conexión al nodo IPFS Kubo RPC (`http://127.0.0.1:5001`).
- Mapeo y registro de CIDs en `ipfs_manifest.json`.
- Checkpoints atómicos: al finalizar sesión o minar bloques, se realiza el pinning automático del estado neuronal y el ledger blockchain a IPFS con recuperación de hash de contenido (CID).

### 4. ⚡ Transducción y Dinámica de Pesos Vivos (`CMFG/PSNRCV.py` y `pesos_vivos.py`)
- **Motor Matemático de Alta Precisión**:
  - Ortogonalización polar **Muon Newton-Schulz 5 (NS-5)**.
  - Estimación espectral de gradiente **GSNR** (*Gradient Signal-to-Noise Ratio*).
  - Cálculo de **Entropía de Shannon** para medir diversidad sináptica y dispersión de información.
  - Detección autónoma de deriva, saturación de gradientes y corrección dinámica de tensores.
- Persistencia local en tiempo real dentro del directorio `LC/celebro/PSNRL/`.

### 5. 🤖 SubSistema de Inferencia Gratuita y Modelos Locales (`IAFREE.py` e `IAlocal.json`)
- **IAFREE**: Conector inteligente a la API de OpenRouter enfocado exclusivamente en modelos sin costo (`:free`), como `google/gemma-4-31b-it:free`, `nvidia/nemotron-3-super-120b-a12b:free`, `qwen/qwen3.8-27b:free`, entre otros.
  - Rotación y failover automático ante códigos HTTP 429 (*Rate Limit*) o 404.
  - Inyección de contexto cognitivo de las 50 neuronas activas en los prompts.
  - Registro de consumo con balance garantizado en `$0.00 USD`.
- **Modelos Locales**: Configuración en `LC/modelosIAlocal/IAlocal.json` para integración sin conexión con servidores Ollama / LM Studio locales.

### 6. 🎨 Motor de Estilos Visuales y Terminal Cyber-Bioluminiscente (`STYLOS.py`)
- Sistema de diseño de consola estilo *Cyber-Bioluminiscente* (Electric Cyan `#00F5FF`, Violeta Neón `#9D00FF`, Ámbar Solar `#FFAA00`, Esmeralda Vivo `#00E676`).
- Renderizado de cajas y tarjetas con bordes redondeados Unicode (`╭─╮╰─╯│`).
- Formateo enriquecido de Markdown con resaltado de sintaxis, listas y tablas.
- Banners de telemetría de turno en vivo (duración en ms, modelo activo, deriva Muon, CID de IPFS y transacciones pendientes).

### 7. 🗣️ Motor de Síntesis de Voz Neuronal (`voice_engine.py`)
- Voz neuronal oficial `es-ES-ElviraNeural` (vía Microsoft Edge/Speech Services o fallback por `System.Speech`).
- Modulador prosódico y de expresividad juvenil espontánea.
- Sanitización de texto para locución limpia (filtrado de markdown, enlaces y código).
- Cancelación y parada instantánea mediante `winmm.dll (MCI)` sin bloquear la interfaz.

### 8. 🎛️ Orquestador Central Unificado (`mainLCSTM.py`)
- Punto de entrada maestro del sistema cognitivo.
- Carga segura de variables de entorno desde `.env`.
- Inicialización coordinada de los subsistemas:
  1. *Blockchain BKSVCB*
  2. *Conversor PSNRCV (50 neuronas)*
  3. *Transducción Ledger ➔ Pesos*
  4. *Sesión y subsistema IAFREE*
- Bucle interactivo por turnos con comandos integrados (`estado`, `modelos`, `minar`, `modelo <id>`, `ayuda`, `salir`).
- Protocolo de cierre ordenado con minado de transacciones pendientes y sincronización final a IPFS.

---

## 📁 Estructura del Directorio

```text
WoldVirtualP2P3D_v0.0.01LCV1/
├── .env                       # Credenciales locales (ignorado por git)
├── .gitignore                  # Reglas de exclusión de git
├── README.md                  # Descripción del proyecto y avances
└── LC/
    ├── mainLCSTM.py           # Orquestador maestro del sistema LucIA
    ├── modelosIAlocal/
    │   └── IAlocal.json       # Configuración de endpoints locales (Ollama/LM Studio)
    └── celebro/
        ├── __init__.py        # Exportaciones del núcleo cognitivo y catálogo neuronal
        ├── BKSVCB.py          # Servidor blockchain, bloques y consenso PoNL
        ├── blockchain_ledger.json # Ledger histórico de bloques y transacciones
        ├── PSNRL/             # Checkpoints locales de pesos sinápticos activos
        ├── CMFG/              # Celebro Model & Feed Gateway
        │   ├── ipfs_manager.py    # Conexión Kubo RPC y subida a IPFS (pin confirmado, 500 entradas + spill)
        │   ├── neural_math.py     # Motor matemático único: Muon NS-5, SOAP, GSNR, Shannon, SemanticEncoderSHA
        │   ├── PSNRCV.py          # Conversor de diálogos a pesos (trust-ratio por neurona, importlib)
        │   ├── pesos_vivos.py     # Monitor de telemetría sináptica en terminal
        │   └── SBSTM/             # SubSistema de Sesión, Voz, Estilos y LLM Free
        │       ├── IAFREE.py          # Inferencia $0.00 vía OpenRouter :free (caché disco, backoff exp.)
        │       ├── RPLC.py            # Filtro y procesador de voz/tono propio
        │       ├── SNSBSTNPRB.py      # Gestor de sesión P2P (peers + sincronizar_ledger)
        │       ├── STYLOS.py          # Motor visual de terminal ANSI / Unicode
        │       └── voice_engine.py    # Síntesis TTS juvenil con interrupción MCI
        └── red_neuronal/      # Paquete con las 50 neuronas activas
            ├── common/          # bases.py, init_utils.py, buffers.py (compartidos)
            ├── ENRN/          # 10 neuronas de entrada recurrente
            ├── RF_SL/         # 10 neuronas de aprendizaje supervisado
            ├── RF_EN/         # 10 neuronas de refuerzo (+ _bases/_buffers/_optimizers/_serializers)
            ├── RNP/           # 10 neuronas de plasticidad y optimizadores
            └── SLRN/          # 10 neuronas de convergencia temporal
```

---

## 🚀 Requisitos e Inicio Rápido

### Requisitos Previos
- **Python 3.10+** (verificado en 3.14).
- Dependencias: `numpy` (voz `edge-tts` opcional).
- Nodo **IPFS Kubo** en `http://127.0.0.1:5001` (opcional, hay fallback local).
- **Sin clave manual:** la API de OpenRouter va cifrada dentro del propio sistema
  (`STM_SGR/vault_openrouter.py`). Al arrancar solo se pregunta
  `¿Desea confirmar conexión con OpenRouter a modelos IA free? s/n` y la key
  nunca se muestra (`sk-o...****`). Solo modelos `:free`.
  Opcional: override con `OPENROUTER_VAULT_PW` o `OPENROUTER_API_KEY` en entorno.

### Ejecución
Para iniciar el orquestador maestro interactivo:
```bash
python LC/mainLCSTM.py
```

### Comandos en la Consola de LucIA
- `estado` / `status`: Muestra la tarjeta integral de salud (bloques, neuronas activas, deriva Muon, costo $0.00).
- `modelos` / `free`: Lista los modelos gratuitos disponibles en el catálogo de OpenRouter.
- `modelo <nombre_o_id>`: Selecciona un modelo específico para inferencia.
- `minar` / `mine`: Fuerza el minado inmediato de transacciones sinápticas pendientes en un nuevo bloque.
- `pin`: Sube PSNRL a IPFS (solo borra local con pin confirmado; resto queda `pendiente_pin`).
- `restaurar <CID>`: Recupera pesos desde IPFS (daemon > CLI > vault > manifiesto).
- `benchmark`: Mide latencia (1 llamada corta por modelo, timeout 10 s).
- `exportar-pesos`: Checkpoint manual de las 50 neuronas en PSNRL.
- `ayuda` / `help`: Muestra el panel interactivo de ayuda de comandos.
- `salir` / `exit`: Consolida el estado, mina el bloque final y sincroniza con IPFS.

### P2P mínimo
`SesionNeuronalP2P.agregar_peer(url)` + `sincronizar_ledger()` adoptan la cadena más larga vía `GET /blocks` del puerto 8545 (+reintentos). Variable `LUCIA_BKS_PORT` configura el puerto.

### Tests y CI
```bash
pip install -e .[dev]
python -m pytest LC/celebro/test -q --timeout=60
```
CI en `.github/workflows/ci.yml` (py3.10/11/12, ubuntu+windows).

---

## 📌 Pendientes Prioritarios de LucIA (2026)

1. **Sistema Automatizado de Refactorización**:
   - Automatización del pipeline de pruebas y transiciones seguras entre `construccion/`, `RFC/` y las versiones finales en `PRY/` sin omisiones manuales.
2. **Contexto Consciente de Capacidades**:
   - Evitar respuestas de desconocimiento en autodiagnóstico inyectando métricas vivas de `mainLCSTM.py` (50 neuronas, blockchain PoNL, IPFS y estado de memoria).
3. **Manejo de Respuestas Extensas sin Cortes**:
   - Control dinámico de tokens y soporte de streaming o continuidad ante explicaciones técnicas amplias.
4. **Provisionamiento asistido del Vault OpenRouter**:
   - Asistente para cargar la clave cifrada cuando el usuario desee alternar entre modelos locales e inferencia remota `:free`. 


   Viewed README.md:1-200
Viewed README.md:200-335
Edited README.md
Edited README.md

El archivo principal [README.md](file:///c:/Users/User/Desktop/WoldVirtualP2P3D_v0.0.01LCV1/README.md) ha sido actualizado incorporando la **deuda técnica y los pendientes directos detectados durante las respuestas de LucIA en la consola interactiva**:

---

### 📋 Principales pendientes reflejados en el [README.md](file:///c:/Users/User/Desktop/WoldVirtualP2P3D_v0.0.01LCV1/README.md):

1. **Contexto Consciente de Capacidades y Autodiagnóstico**:
   - *Hallazgo en terminal:* LucIA respondió en el turno 6: *"Lo siento, pero no puedo realizar un resumen del estado actual de mi sistema..."*.
   - *Acción pendiente:* Inyectar un volcado estructurado del estado de los subsistemas (50 neuronas, bloques minados en blockchain PoNL, persistencia IPFS y memoria de sesión) directamente en el prompt del sistema para que responda con conocimiento factual de su arquitectura interna.

2. **Resolución de Truncamiento en Respuestas Largas**:
   - *Hallazgo en terminal:* Al solicitar análisis detallados de telemetría y servidores (turnos 3 y 4), la respuesta se cortó a mitad de frase debido al límite de tokens (`num_predict: 400`).
   - *Acción pendiente:* Implementar un mecanismo de continuación automática o streaming por fragmentos en [gestor.py](file:///c:/Users/User/Desktop/WoldVirtualP2P3D_v0.0.01LCV1/VersionDe_sesion/CONTRRF/TLLDCD/RFC/src/STM_IA/modelosIAlocal/IALOCAL/gestor.py) para que no interrumpa explicaciones técnicas extensas.

3. **Alineación con OpenRouter y Conector `IAFREE`**:
   - *Hallazgo en terminal:* Cuando se le consultó sobre OpenRouter, al no tener clave configurada en el vault (`Vault sin key provisionada. Modo local/reflejo`), LucIA alucinó modelos locales estáticos (`LSTM-Word2Vec`, `ConvLSTM`) en lugar de reconocer su subsistema `IAFREE`.
   - *Acción pendiente:* Facilitar el aprovisionamiento de la API key en el vault y alinear el prompt para que distinga claramente entre inferencia local (Ollama) y el catálogo remoto gratuito `:free`.

4. **Sistema Automatizado de Refactorización**:
   - Mantener el plan de automatización de transiciones y pruebas seguras entre `construccion/`, `RFC/` y las versiones en `Sistema_Principal/PRY/`.

5. **Soluciones ya consolidadas en el informe**:
   - Corrección del error de codificación `UnicodeDecodeError` en Windows (`utf-8` / `replace`).
   - Registro de la **Voz Neuronal Oficial de LucIA (18 años / es-ES / DSP 1.16x)** fijada e integrada en [voice_engine.py](file:///c:/Users/User/Desktop/WoldVirtualP2P3D_v0.0.01LCV1/VersionDe_sesion/CONTRRF/TLLDCD/RFC/src/SBSTM/voice_engine.py) y monitorizada en [mainLCSTM.py](file:///c:/Users/User/Desktop/WoldVirtualP2P3D_v0.0.01LCV1/VersionDe_sesion/CONTRRF/TLLDCD/RFC/src/STMGNRL/mainLCSTM.py).