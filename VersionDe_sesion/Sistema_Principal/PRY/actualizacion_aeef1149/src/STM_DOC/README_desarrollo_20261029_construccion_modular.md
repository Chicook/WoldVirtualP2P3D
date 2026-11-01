# Construcción modular, rutas centralizadas y visor 2.7.1

La 2.7.1 no toca el carrusel, las shape keys ni la red: cambia **cómo se construye y se edita** el
mundo y **dónde vive cada ruta** del árbol. Todo lo de la 2.7.0 sigue igual y las nueve herramientas
del panel conservan el orden histórico, con las dos nuevas al final, así que ningún guion que pulse
un índice fijo se rompe.

Rutas relativas a `VersionDe_sesion/CONTRRF/TLLDCD/src/` (en lo que sigue, `<src/>`).

## 1. Qué se ha hecho

| Área | Antes (2.7.0) | Ahora (2.7.1) |
|---|---|---|
| Deshacer | sólo «deshacer isla» (todo o nada) | pila **por pasos** por isla, con rehacer, `Ctrl+Z`/`Ctrl+Y` y botones que se habilitan según la pila |
| Pincel | un incremento fijo por clic | **a tiempo real** mientras se mantiene pulsado, con paso clampizado al delta de fotograma |
| Herramientas de terreno | 6 | 8: se añaden **Rugosidad** y **Revertir** |
| Colisión tras un trazo | malla completa con *debounce* de 0,5 s | **sólo las caras sucias**, cada 0,12 s y completa al soltar |
| Tamaño de un prim | uniforme | uniforme **o por eje** (X/Y/Z) |
| Rejilla | fija en 0,5 m | casilla + **paso configurable** 0,1–2,0 m |
| Copias del progreso | no había | **inventario** en `user://inventario/` |
| `Construccion.gd` | un solo fichero | 3 módulos en `gdscrip/construccion/` con responsabilidades separadas |
| Rutas del árbol | cada módulo reconstruía `Path(__file__)…` | **`STM_HRTS/rutas.py`** es la única fuente; `STM_CH` delega |

## 2. El sistema de construcción, pieza a pieza

| Fichero | Responsabilidad |
|---|---|
| `gdscrip/Construccion.gd` | entrada del modo (`B`), selección, rez, permisos, RPC y sincronización por bloques de 6000 B |
| `gdscrip/TerrenoEditable.gd` | malla editable por isla, pincel, máscara de arena, instantáneas y colisión incremental |
| `gdscrip/ConstructorPanel.gd` | panel: 9 herramientas, radio, fuerza, color, tamaño por ejes, rejilla, paso, historial e inventario |
| `gdscrip/construccion/HistorialEdicion.gd` | pila de deshacer/rehacer por isla (48 acciones), sin saber qué contiene cada entrada |
| `gdscrip/construccion/InventarioConstruccion.gd` | copias del terreno (blob en base64) y de los objetos, con índice de metadatos |
| `gdscrip/construccion/ContornoIsla.gd` | mayor círculo de tierra firme alrededor de un punto, medido con 24 rayos verticales |

El contrato del historial es deliberadamente tonto: `Construccion` empuja diccionarios
(`{"isla", "terreno": [antes, después]}` para un trazo; `{"isla", "prims": [antes, después]}` para
objetos) y el módulo sólo los mueve entre las dos pilas y descarta los más antiguos. Así el formato de
las acciones puede crecer sin tocar el historial.

Una isla no puede registrarse dos veces ni con el mismo nodo bajo dos índices: compartirían terreno y
colisión. `registrar_isla()` lo rechaza y lo deja en el log.

## 3. Terreno: herramientas y garantías

- **Ocho herramientas**: subir, bajar, suavizar, aplanar, mover, playa, rugosidad y revertir.
  Límites de altura 0,0–0,95 m sobre la geometría base y playa a 1 m sobre el agua
  (`MARGEN_PLAYA_M`), sin cambios respecto a la 2.7.0.
- **Rugosidad** usa un ruido determinista ligado a la posición del vértice: la misma isla y el mismo
  trazo dan el mismo relieve, y no hay acumulación aleatoria entre pasadas.
- **Revertir** devuelve altura y arena al estado original guardado en la instantánea de registro.
- **Instantáneas** (`instantanea()`/`restaurar_instantanea()`): el pincel toma una al pulsar y
  `_registrar_pincel` compara con la del soltar; sólo si hay diferencia se empuja un paso. Un trazo
  sin efecto no ensucia el historial.
- **Colisión incremental**: `_marcar_caras` anota las caras tocadas y `actualizar_colision_parcial()`
  reconstruye sólo esas. En la prueba sobre la isla sintética (73×73 vértices) un trazo refrescó
  **188 de 10 368 caras**; la colisión completa siguió costando ~9,8 ms.
- El formato binario `WVPT` v2 (alturas + máscara de arena) no cambia, así que los blobs guardados
  por la 2.7.0 se cargan tal cual.

## 4. Panel y atajos

| Acción | Cómo |
|---|---|
| Deshacer un paso / rehacer | `Ctrl+Z` / `Ctrl+Y` o los botones del panel |
| Deshacer la isla entera | botón *Deshacer isla* (el de siempre) |
| Mover, girar, altura, tamaño | flechas/WASD, `Q`/`E`, `RePág`/`AvPág`, `+`/`−` |
| Duplicar, borrar, salir del modo | `Ctrl+D`, `Supr`, `Esc` |
| Elegir la dimensión del tamaño | desplegable *Eje tamaño*: Uniforme, X, Y, Z |
| Cambiar el paso de la rejilla | deslizador *Paso*, 0,1–2,0 m (por defecto 0,5) |
| Guardar una copia del progreso | botón *Guardar en inventario* |

El tamaño por eje escribe el valor absoluto del eje elegido; en *Uniforme* escala tomando como
referencia el eje mayor, que es el comportamiento que ya tenía.

## 5. Red y autoridad

Sin cambios de protocolo: `WebSocketMultiplayerPeer` sobre TCP 8911, RPC fiable del anfitrión y
bloques de estado de 6000 B. Lo que cambia es que **el historial no se puede usar para saltarse los
permisos**: `_deshacer_paso()` y `_rehacer_paso()` pasan por la misma comprobación `_puedo_editar()`
que el resto de acciones y el anfitrión valida y replica la entrada. Un invitado sobre una isla ajena
no recibe los botones habilitados.

## 6. STM_HRTS: una sola fuente de rutas

`<src/>STM_HRTS/rutas.py` calcula todas las rutas desde su propia ubicación: raíces del árbol,
paquetes Python, proyecto Godot, visor C#, documentos, herramientas y artefactos de `STM_CH`. Ningún
otro módulo reconstruye rutas con `Path(__file__).parent…`.

| Comando | Qué hace |
|---|---|
| `python -m STM_HRTS rutas` | lista las rutas clave con marca `ok`/`FALTA` |
| `python -m STM_HRTS verificar` | comprueba que las rutas existen (código 1 si falta alguna) |
| `python -m STM_HRTS herramientas` | catálogo de `STM_HRTS/utils` con tipo, resumen y si necesita ventana |
| `python -m STM_HRTS ejecutar <nombre>` | lanza la herramienta con Godot y el proyecto correctos |

Las herramientas de prueba de Godot viven en `<src/>STM_HRTS/utils/` y se versionan con el proyecto,
pero **no entran en el PCK**: el preset de exportación excluye esa carpeta con `tools/`, como antes.

`STM_CH/rutas.py` conserva sólo lo que necesita en tiempo de ejecución (dónde está el árbol) y
delega el resto en `STM_HRTS`; la prueba `tests/test_hrts_rutas.py` comprueba que la delegación no
duplica constantes.

## 7. Mundo exportado y empaquetado

- `wvp3d.pck` exportado del árbol de este commit con Godot 4.7.2 headless:
  **1.053.081.932 B**, SHA-256 `8d42b2d3193ac575664fc53ea4d2ab49754687a9ccbb12d4b34aefe7019fdede`.
- Verificado con `verify_pck.py`: 536 entradas con el **MD5 de todas correcto**, **33 `.gdc` = los 33
  guiones** del árbol (0 sobrantes, 0 ausentes) y **4.261/4.261** identificadores y literales
  presentes.
- El PCK crece 15.588 B frente al de la 2.7.0: son los guiones nuevos y los cambios de los tres
  ficheros de construcción; las texturas no se han tocado.
- Visor: `DMWoldVirtualP2P3Dv2.7.1.exe`, **1.303.560.057 B**, SHA-256
  `9d780c6fc870b62f1042865d10125bfad63336a0f391452b14ba65b0fae11b3d`.
- Paquete de Linux: `WoldVirtualP2P3Dv2.7.1-linux.tar.gz`, **1.110.302.810 B**, SHA-256
  `cd80474417e6891e366f96ab006e0b3385e981517ea218abc1d40d22cd280d1a` (visor completo adaptado a Linux
  con el motor Godot 4.7.2 y `wvp3d.pck` **dentro del binario**, más `STM_LBR/`). Detalle en
  `README_desarrollo_20261029_visor_linux.md`.

### Publicación

Release **v2.7.1** publicada el 2026-10-29 (`Latest`), tag sobre `261864b` de `DevQoderIA`. Cuatro
assets, con el `digest` que devuelve la API igual al SHA-256 local (comprobado con
`gh api repos/…/releases/tags/v2.7.1`):

| Asset | Bytes | SHA-256 |
|---|---|---|
| `DMWoldVirtualP2P3Dv2.7.1.exe` | 1.303.560.057 | `9d780c6fc870b62f1042865d10125bfad63336a0f391452b14ba65b0fae11b3d` |
| `WoldVirtualP2P3Dv2.7.1-linux.tar.gz` | 1.110.302.810 | `cd80474417e6891e366f96ab006e0b3385e981517ea218abc1d40d22cd280d1a` |
| `release.json` | 216 | `5032e44c9634ff0e63107f9505efb068e1247f330b61eb20c90ab93df4b9eff1` |
| `SHA256SUMS` | 276 | `fb6a4383d857db996137f02b390b92f23a5db42afcb3b6e3cce2ec5aad04e1ff` |

El `.tar.gz` y el `SHA256SUMS` se sustituyeron el mismo 2026-10-29 con
`gh release upload --clobber`, por petición expresa del dueño: el tar publicado al crear la release
(1.070.016.595 B, `0945fb3961290898e457a3654a9397c1825b306910e51cfcbd702e5685a31c41`) sólo llevaba el
mundo y ahora lleva el visor completo con la parte 3D dentro. Es la excepción a R2 documentada; el exe
y `release.json` no se tocaron.

## 8. Pruebas ejecutadas (evidencia)

Godot 4.7.2 headless sobre el árbol de `E:/areadetrabajo/wvp270/godot` (idéntico a este commit más
los assets no versionados; comparación SHA-1 fichero a fichero sin diferencias fuera de los seis
ficheros de construcción, que ya estaban copiados). Cada suite con `APPDATA` aislado.

| Prueba | Qué cubre | Resultado |
|---|---|---|
| `probar_construccion.gd` | pincel, límites, rugosidad determinista, revertir, colisión parcial, undo/redo de objetos y trazos, escala por ejes, paso, inventario, permisos, aislamiento | **233 OK, 0 fallos** |
| `validar_avatares.gd` | 24 avatares: huesos, 5 clips, `AnimationTree` en movimiento | **24 avatares, 0 fallos** |
| `validar_personalizacion.gd` | 24 avatares reales: deformación, altura, idempotencia | **24 avatares, 0 fallos** |
| `validar_ch3d.gd` | 16 escenas Ch3D remodeladas | **16 escenas, 0 fallos** |
| `validar_shapekeys_reales.gd` | 7 expresiones sobre `AVH1.gltf` real | **0 fallos** (media 16,9 mm, máx. 23,5 mm) |
| `probar_selector.gd` / `probar_shapekeys.gd` | selector y shape keys de la 2.7.0 | **0 fallos** |
| `probar_turnos.gd`, `probar_carrusel.gd`, `probar_carrusel_ocupado.gd` | reserva y recorrido de las 24 plazas | **0 fallos** |
| `probar_red.gd`, `probar_red_invitacion.gd` | rol, invitación (con `--client --peer-url=…?invitacion=…`) | **0 fallos** |
| `probar_sonda_anfitrion.gd` + `probar_sonda_invitado.gd` | sonda de plazas (dos procesos) | **0 fallos**, anfitrión atendió **1** sonda |
| `probar_ganchos.gd`, `probar_flujo_portal.gd`, `probar_islas_fantasma.gd`, `probar_registro_islas.gd`, `probar_control_clic.gd`, `probar_cambio_avatar.gd` | resto de suites | **0 fallos** |
| `pytest` (`<src/>tests`) | STM_HRTS, comandos, perfil, memoria, voz, regresión | **82 pruebas** |

Autopruebas del visor ya compilado, con `WOLD_RUNTIME_DIR` en una carpeta temporal:

| Prueba | Resultado |
|---|---|
| `--startup-selftest` | **RESULTADO ARRANQUE: OK** (17 comprobaciones): recursos embebidos, `runtime\.extracted` = `2.7.1`, PCK extraído = embebido, portal, `/api/info` anuncia `DMWoldVirtualP2P3Dv2.7.1.exe`, baliza 8912, umbral de VM, recolector y **motor arrancando desde el PCK** (`isla=True red=True errores=False`) |
| `--chat-selftest` | **fallos=0** |
| `--cuenta-selftest` | **RESULTADO CUENTA: OK** |
| `--red-selftest` | **RESULTADO RED: 7 líneas, 0 fallos** |

Nota operativa: la primera pasada de `--startup-selftest` falló *la comprobación del motor* porque en
ese momento corrían otras dos suites de Godot en el mismo equipo y compartían los puertos 8911/8912.
Repetida en solitario, 17/17. La prueba no mata procesos ajenos; conviene ejecutarla sin otras
instancias del mundo abiertas.

## 9. Qué no se ha podido probar

- **Captura visual con ventana** del panel nuevo: esta máquina ha ejecutado todo en headless. Las
  suites `probar_cara.gd`, `probar_cuerpo.gd` y `probar_personalizacion.gd` hacen `save_png` del
  viewport y en headless el rasterizador es *dummy* (`Parameter "t" is null`); es una limitación
  previa, no una regresión. `capturar_construccion.gd` no se ha vuelto a ejecutar con ventana.
- **OTA de punta a punta**: hace falta un equipo con la 2.7.0 instalada para actualizar → relanzar →
  comprobar la re-extracción. En esta sesión no se ha hecho.
- **Dos máquinas reales** para deshacer/rehacer en red: la prueba cubre el host y el rechazo de
  permisos, no una sesión entre dos PCs.
- **Linux**: el paquete se regenera con el motor 4.7.2 de Linux y el PCK nuevo, pero no se ejecuta
  aquí (no hay Linux en esta máquina). `woldvirtual-linux.sh --verificar` comprueba la huella.
- `probar_registro.gd` sigue sin poder ejecutarse: necesita `importblend/hm1.blend`, que no está en
  el árbol de fuentes.

## 10. Checklist de §7

| Casilla | Estado |
|---|---|
| PCK fresco del árbol de este commit | **Sí** — SHA-256 `8d42b2d3…019fdede`, 536 entradas íntegras |
| Versión sincronizada (csproj, tag, asset, `release.json`) | **Sí**, los cuatro planos en `2.7.1` |
| Compila self-contained single-file | **Sí** — `dotnet publish -c Release -r win-x64` |
| Cero binarios en el commit | **Sí** — `.pck`/`.zip`/`.exe` siguen ignorados |
| Arranque limpio con re-extracción | **Sí** — `--startup-selftest` 17/17 |
| El motor arranca desde el PCK | **Sí** — `isla=True red=True` |
| Portal anuncia la release vigente | **Sí** — `/api/info` → `DMWoldVirtualP2P3Dv2.7.1.exe` |
| OTA de punta a punta | **No** — pendiente de un equipo con la 2.7.0 |
| Digests comprobados por API | **Sí** — ver §7 |
| Docs en el mismo commit | **Sí** |
