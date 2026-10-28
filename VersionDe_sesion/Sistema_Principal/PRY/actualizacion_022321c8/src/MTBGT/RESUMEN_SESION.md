# RESUMEN DE SESIÓN — WoldVirtualP2P3D (metaverso)

Fecha: 2026-10-18.
Proyecto: `C:\Users\User\Desktop\UserAnimados\MTBGT\WoldVirtualP2P3D`.
Motor: Godot 4.7.2. Avatares en Blender 5.2 (bases MakeHuman + rig Mixamo 65 huesos).

---

## 1. Lo desarrollado hoy

### 1.1 Carrusel de avatares (3 chicas / 3 hombres)

- Orden definitivo: `AVMJ1, AVMJ2, AVH1, AVH2, AVMJ3, AVH3` (contador `1 / 6`). `AVMJ4` queda fuera del carrusel (archivos en disco).
- **AVMJ3 restilizada** para dejar de ser clon de AVMJ2: regenerada desde `AVMJ2.blend` con pelo rubio `(0.66, 0.50, 0.24)`, top teal `(0.05, 0.36, 0.33)` y pantalón claro `(0.78, 0.74, 0.64)`. Conserva las 5 acciones. Limitación: misma cara/base Ch22; una cara distinta exige base MPFB nueva + re-rig Mixamo.
- Todos los avatares comparten las 5 acciones (`paradoMJ1_1`, `caminarMJ1_2`, `correrMJ1_3`, `left_StrafeMJ1_4`, `rightstrafeMJ1_5`) y el script `AVMJ1Ch3D.gd`.

### 1.2 El avatar elegido llega al portal y a la isla

- `ChunkManager.set_player_avatar(scene_path)`: sustituye `USERBASE` por el avatar elegido **antes** de `add_child`, conservando `transform` (spawn y=41.95).
- `Boot.gd` llama `set_player_avatar()` al instanciar portal e isla.
- `AVMJ1Ch3D.gd`: `current_animation` (0 idle, 1 andar, 2 correr; strafes usan 1) y `fija_estado_remoto(estado, delta)` para réplicas.

### 1.3 Clones remotos con el avatar correcto (bug "error curioso")

Problema: al entrar con un avatar, los demás peers veían el avatar base en vez del elegido.

- `PlayerSync.gd`: `_rutas` (peer_id → ruta de avatar), `_ensure_proxy()` instancia el avatar del peer, `enable_control=false`, `es_clon_remoto=true`, sin cámara, y reconstruye el clon si el peer cambia de avatar.
- Ruta validada con prefijo `res://SLCAV/AVATARESCONANIMACION/`.
- Cámaras del clon se liberan **después** de `add_child` (evita `Node not found: "Camera3D"` de `@onready`).
- `userbaseh_1.gd`: setup de cámara protegido con `if not es_clon_remoto:`; `_update_camera` con `is_instance_valid(camera)`.

### 1.4 Portal moderno + entorno de estación espacial

- Shaders nuevos: `portal_energy.gdshader` (remolino aditivo), `portal_ring.gdshader` (anillo metálico con bandas animadas), `grid_floor.gdshader` (rejilla con desvanecido), `hangar_panel.gdshader` (paneles con costuras y variación por celda).
- `portal_visual.gd`: orbes orbitando, pulso de luz, intensidad de membrana.
- `entornodeprueba.tscn` reescrito: doble anillo, membrana, plataforma, aro de suelo, 3 orbes, luces, entorno oscuro con glow/niebla, rejilla; `Area3D` del portal en `(0, 0, -5)`.
- `estacion.gd` (hangar): paredes con colisión, techo, costillas, vigas, tiras de luz + 8 OmniLight, zócalos emisivos, pilares, acentos y compuerta. Suelo ampliado a `(24, 1, 28)`.

### 1.5 Rótulos y bienvenida

- Junto al portal (`Label3D`): `GRACIAS POR ENTRAR A WOLD VIRTUAL 3D`, `CREA TU ISLA PROPIA`, `Cruza el portal`.
- Banner de llegada (`Boot._mostrar_bienvenida()`), se desvanece a los ~6 s:
  - `GRACIAS POR ENTRAR A WOLD VIRTUAL 3D` — 20 px.
  - `FELICIDADES, CREASTE TU ISLA` — 30 px.
  - `BIENVENIDO, <nick>` / `BIENVENIDA, <nick>` — 24 px, según avatar (`AVMJ` → BIENVENIDA).

### 1.6 Correcciones

- `registro.gd:51`: parámetro sin uso renombrado `_new_text`.
- `ChunkManager.gd:232`: división entera corregida (`int(float(index) / float(islands_per_row))`).
- BOM eliminado de `entornodeprueba.tscn` (provocaba `Parse Error: Expected '['`).
- `PlayerSync.gd`: borrado de cámara del clon reubicado tras `add_child`.

### 1.7 Verificación

- Tests headless: isla/avatar 14/14, clones remotos 9/9, portal 13/13, rótulos/saludo 9/9.
- `portal_cruzado` dispara con cuerpo real (HITS=1).
- `--headless --import` y arranque con `--quit-after` → EXIT=0 sin errores.
- Capturas revisadas: portal, hangar y pila de rótulos.

---

## 2. Hoja de ruta — Carrusel diverso y avatares únicos (PENDIENTE)

> **Estado: no implementado.** Hoy el carrusel (`gdscrip/SLAV.gd` + `SLAV.tscn`) muestra siempre los mismos 6 avatares (`AVMJ1, AVMJ2, AVH1, AVH2, AVMJ3, AVH3`, arrays en `SLAV.tscn:40-42`). Todo lo de abajo es trabajo pendiente.

### 2.1 Objetivo

Cada usuario debe terminar con **un avatar original** que no se repita, y el carrusel debe **cambiar de aspecto** entre sesiones. Regla de la fase de prueba: al elegir un personaje y cerrar el metaverso, **el siguiente arranque muestra los 5 restantes + 1 diferente**; los ya elegidos se guardan y viajan por IPFS en un JSON.

### 2.2 Fase demo (Godot, catálogo actual) — mecánica concreta

Punto de enganche (ya existe, solo hay que ampliarlo):

- `SLAV.gd:26 _ready()` instancia cada `avatar_scenes[i]` en el `Pivot`, levanta `avatar_names`/`playable_scenes` y llama `_apply_selection(true)`.
- `SLAV.gd:93 _confirm()` emite `avatar_confirmed(scene_path)`; `Boot.gd:46 _on_avatar_confirmed` guarda `_avatar_scene` y sigue a registro → portal → isla.
- `registro.gd:43-45` ya guarda el nick en `user://registro.cfg` (base para el `owner_uuid`/`nick` del JSON).

Trabajo a añadir:

1. **Fuente de datos del carrusel**: dejar de tener los 6 fijos escritos en `SLAV.tscn`. `SLAV.gd` debe recibir una lista dinámica (mismo formato `avatar_scenes`/`playable_scenes`/`avatar_names`) calculada al arrancar.
2. **Filtro "usados"**: al abrir el carrusel, leer la lista de avatares ya usados y **excluirlos** de las opciones ofrecidas.
3. **Relleno de huecos con variante nueva**: por cada usado excluido, insertar un avatar de repuesto (un `.tscn`/`.blend` nuevo del catálogo ampliado, o una variante recolor determinista del mismo modelo usando un `seed`). Así siempre se ven 6, pero distintos.
4. **Caché local**: escribir `user://avatares_usados.json` al confirmar (para sobrevivir a cierres inesperados) y mantenerlo como espejo local del JSON de IPFS.
5. **Catálogo agotado**: si no quedan libres, reutilizar los de `ultimo_uso` más antiguo y avisar en pantalla (p. ej. "reutilizando avatar libre hace más tiempo").
6. **`owner_uuid`**: generarlo en el primer registro (UUID v4 en `user://registro.cfg`) y guardarlo junto al avatar para reconocer al usuario al reconectar.
7. **Opción de expiración**: liberar avatares tras N días para demos multiusuario (no bloqueante para la demo).
8. **Primer sustituto = `AVMJ4`**: recuperar el `AVMJ4` huérfano como primera variante de relleno, pero **reestilizándolo con ropa distinta** (no reutilizar el mismo vestuario que `AVMJ1`/`AVMJ2`/`AVMJ3`, para que se note a simple vista). Parte de la base existente en disco y cambia solo colores/materiales de ropa; conserva las 5 acciones y `AVMJ1Ch3D.gd`.
9. **Avatar base estilizado al carrusel**: el avatar base (`userbaseh1` / hm1, hoy solo fallback/placeholder) también podría **estilizarse un poco** (colores/ropa) y entrar en el carrusel como una opción más. Requiere comprobar que tiene idle/acciones válidas (ver nota en §4: hm1 no trae `paradoMJ1_1`), así que primero hay que darle una acción de reposo o mapear la existente.
10. **Orden alterno chica/chico** (ver 2.2.1).

### 2.2.1 Orden del carrusel (PENDIENTE)

- Orden deseado: **alternando chica / chico** (p. ej. `AVMJ1, AVH1, AVMJ2, AVH2, AVMJ3, AVH3`), no agrupado como ahora (`AVMJ1, AVMJ2, AVH1, AVH2, AVMJ3, AVH3` en `SLAV.tscn:40-42` = chica, chica, chico, chico, chica, chico).
- Cambiar a la vez los tres arrays de `SLAV.tscn` (`avatar_scenes`, `playable_scenes`, `avatar_names`) en el mismo orden para no desincronizar índice ↔ escena ↔ nombre.
- Con el catálogo dinámico de 2.2 (punto 1), el orden alterno debe generarse también al vuelo (intercalar por género), no solo ser una permutación fija.

### 2.3 Persistencia en IPFS (fase de prueba) — cómo se guarda y se recupera

Pedido: al **cerrar el último** (salir del metaverso) se sube a IPFS el JSON de avatares escogidos; al **abrir de nuevo** se descarga y el carrusel muestra otros.

Infra ya disponible (lado LUCIA, no Godot todavía):

- Daemon Kubo: `src/STMIPFS/SBSTMPYIPFS/ipfs_launcher.py` (gestor de arranque/salud) y `src/STMIPFS/STM_BAT_IPFS/arrancar_daemon.bat`.
- API local Kubo: `http://127.0.0.1:5001`; gateway `http://127.0.0.1:8080` (`ipfs_launcher.py:37-38`).

Flujo a implementar (Godot):

1. **Al cerrar la app** (`NOTIFICATION_WM_CLOSE_REQUEST` en `Boot.gd`, con fallback en `_notification`):
   - Volcar `user://avatares_usados.json` a disco.
   - Subir a IPFS con pin: `ipfs add --pin <ruta>` → devuelve `CID`.
   - Guardar el `CID` en un **fichero puntero** local `user://ipfs_avatares.cid` (sin esto, el siguiente arranque no sabe qué CID pedir).
   - Opcional: `ipfs pin add <CID>` explícito para que no lo recoja el `repo gc`.
2. **Al arrancar** (`Boot.gd._ready()` / inicio del carrusel):
   - Leer `user://ipfs_avatares.cid`; si existe, `ipfs cat <CID>` → JSON.
   - Fusionar con `user://avatares_usados.json` (por `avatar_id` + `ultimo_uso`) y alimentar el filtro de 2.2.
   - Si no hay CID o el daemon está caído, seguir solo con la caché local (sin bloquear el arranque).
3. **Orden de llamada en `Boot.gd`**: la descarga debe ocurrir **antes** de `_mostrar_carrusel()` (que hoy es lo primero en `_ready`, `Boot.gd:27`); mover a un paso `_preparar_catalogo()` previo.

Dos vías de integración con Kubo (elegir una):

- **A (recomendada para la prueba): CLI** — `OS.execute("ipfs", ["add", "--pin", ruta], salida, true)` y `OS.execute("ipfs", ["cat", cid], ...)`. Simple, usa el binario que ya existe y no requiere multipart.
- **B (robusta a futuro): API HTTP** — `HTTPRequest` a `POST /api/v0/add?pin=true` (multipart/form-data) y `POST /api/v0/cat?arg=<cid>`. Más portable si el daemon corre en otra máquina/P2P, pero hay que construir el cuerpo multipart a mano.

Consideraciones:

- **Daemon**: comprobar `POST /api/v0/id` antes de subir/bajar; si no responde, no romper la sesión (solo log).
- **Cierre forzado**: `NOTIFICATION_WM_CLOSE_REQUEST` no llega en `kill -9`; por eso también se escribe la caché local **al confirmar** (2.2.4), no solo al cerrar.
- **Rutas largas/Windows**: usar nombres cortos para el JSON temporal (el repo ya sufrió límites de 345 caracteres en rutas IPFS de otra versión); el JSON va suelto, no dentro de rutas profundas.
- **Concurrencia**: si dos usuarios suben a la vez, cada uno escribe su propio JSON+CID; fusionar por `avatar_id` evita perder elecciones (conflicto = gana `ultimo_uso` más reciente).

### 2.4 Estructura JSON propuesta (ampliada)

```json
{
  "version": 1,
  "actualizado": "2026-10-18T13:20:00",
  "puntero_previo": "bafybeicid...",
  "avatares": {
    "AVMJ1": {
      "owner_uuid": "8f3c4d2a-...",
      "nick": "Alicia",
      "estado": "usado",
      "fecha_alta": "2026-10-18T12:00:00",
      "ultimo_uso": "2026-10-18T13:20:00",
      "seed": 182734,
      "shapes": {}
    }
  }
}
```

- `estado`: `libre` | `reservado` | `usado`.
- `seed`: semilla de la variante recolor (generación reproducible → mismo avatar siempre).
- `shapes`: valores de shape keys de Blender elegidos por el usuario (ver 2.6); vacío hasta que exista el editor de retoque.
- `puntero_previo`: CID del JSON anterior → permite reconstruir la cadena de historial en IPFS sin servicio central.

### 2.5 Fase visor 3D en C# + red P2P (objetivo final)

Regla pedida: en el visor C# **cada usuario verá 6 personajes diferentes**. Hoja de ruta detallada del visor en `VersionDe_sesion/Sistema_Principal/PRY/actualizacion_86bea3a9/src/VSC#/README.md`.

- **Servicio de asignación**: al registrarse, el usuario pide un avatar libre y recibe un `avatar_id` reservado de forma atómica (evita que dos peers reciban el mismo por carrera).
- **Catálogo creciente**: los 6 del visor no son siempre los mismos; se amplía con variantes generadas.
- **Replicación**: el mensaje de spawn P2P lleva `avatar_id` + personalización (incluye `seed` y `shapes`); todos los peers instancian el mismo avatar para ese usuario.
- **Persistencia**: el mismo JSON de 2.4 (o BD) guarda `avatar_id`, `owner_uuid`, `nick`, `estado`, `fecha_alta`, `ultimo_uso`, `seed` y `shapes`.
- **"1 avatar original por usuario"**: el `owner_uuid` se fija en el primer registro; al reconectar se le devuelve el mismo avatar y nunca se reasigna mientras exista.
- **Cierre de sesión**: el visor C# hace flush del JSON (o POST al servicio) con `ultimo_uso` y estado antes de salir.
- **Generación reproducible**: colores/pelo/ropa/altura derivados de un `seed` guardado en JSON → mismo avatar siempre, sin duplicados.

### 2.6 Shape keys de Blender → Godot (retoque del avatar) — PENDIENTE

Objetivo: una vez elegido el avatar, el usuario puede **retocarlo** (cara/cuerpo/nariz/ojos/edad/musculatura...) desde el propio metaverso para hacerlo más original. **Solo para avatares**: el terreno/islas no se editan con shape keys (ver 2.7).

Cómo funciona la tubería:

1. **Blender → glTF**: los shape keys (morph targets) viven en la **malla**, no en el esqueleto; se exportan activando la opción de morph targets del exportador glTF. Límite práctico de glTF: se pueden exportar muchos, pero conviene ceñirse a los que se van a exponer (10-30) para no inflar el `.glb`.
2. **Importación en Godot**: al importar, cada shape key aparece como **blend shape** de la `MeshInstance3D`. API: `MeshInstance3D.get_blend_shape_count()` y `set_blend_shape_value(i, valor)` (0..1). No requieren tocar el `AnimationTree` ni las acciones del rig Mixamo: son estáticos y el usuario los ajusta una vez.
3. **UI de retoque**: en `registro.tscn` (o un paso nuevo "Personalizar" tras el carrusel) montar sliders por grupo (`Edad`, `Musculatura`, `Nariz`, `Ojos`, `Boca`, `Altura facial`...), cada uno ligado a un `set_blend_shape_value`.
4. **Guardado**: los valores van al campo `shapes` del JSON de 2.4 (añadir a `user://avatares_usados.json` y subir a IPFS con el mismo flujo de 2.3).
5. **Replicación P2P**: el mensaje de spawn debe incluir `shapes`; en `PlayerSync.gd` (`_ensure_proxy`/`_net_position`) aplicar `set_blend_shape_value` a cada clon remoto para que los demás vean el retoque.
6. **Reaplicar al cargar**: al reconectar, leer `shapes` del JSON y aplicar sobre el avatar del usuario y sobre su clon.

Sobre `.blend` vs `glTF` (importante):

- Godot **no** lee `.blend` de forma nativa: al importar un `.blend` **llama a Blender y lo convierte a glTF por dentro** (requiere Blender instalado y su ruta configurada en el editor). En el juego exportado, el `.blend` no existe: solo van los recursos importados.
- Por eso, uses `.blend` o `.glb`, el camino real siempre es glTF: los morph targets deben sobrevivir esa exportación en ambos casos.
- Recomendado: **exportar tú el `.glb` explícito** con morph targets activados, y versionar eso. Es reproducible y no depende de Blender al importar ni en CI.

Requisitos/riesgos a verificar antes de implementar:

- Los `.blend` actuales de los avatares (`AVMJ*`/`AVH*`) deben **tener** shape keys reales (bases MakeHuman suelen traerlas; hay que comprobar que sobrevivieron a la conversión/import).
- El exportador Godot `.blend` debe incluir morph targets; si se pierden, exportar a `.glb` explícito y usar ese como `playable_scene`.
- Coste: cada shape key activa deforma la malla por CPU/GPU; limitar el número expuesto.
- Guardar `shapes` también en el clon remoto solo si el avatar remoto es de la misma familia (mismos índices de blend shape); si no coincide, ignorar silenciosamente.

### 2.7 Editor de islas por usuario (PENDIENTE)

Aclaración: los **shape keys son solo para avatares**. El terreno/islas **no** se editan con morph targets (no se pueden crear en runtime y pesan demasiado). Para islas se usan otras técnicas.

Contexto actual (lo que ya existe):

- Cada isla es una **copia** de la plantilla `$ISLA3DCHUNK` (`ISLA3Dblock.tscn`: nodos `ISLA3DCHUNK`, `Oceano3D`, `USERBASE`) instanciada en `ChunkManager.gd:244 _spawn_island_for_player`.
- Se colocan en una **rejilla serpentina** de 10 por fila (`islands_per_row`, `chunk_size 199.5`) con filas alternando dirección (`ChunkManager.gd:232-241`).
- El dueño de cada isla ya se conoce en todos los peers: `island_owners[index] = [id, nick]` (`ChunkManager.gd:229`); el servidor guarda `active_islands` (`peer_id -> index`).
- Hoy la isla es **geometría estática idéntica**: no hay nada por-usuario. Ahí entra el editor.

Modelo de datos: **base reproducible + delta de ediciones**

- La isla se genera a partir de un `seed` (mismo `seed` ⇒ misma isla base en todos los peers, no hace falta enviar geometría).
- Sobre esa base, cada usuario guarda un **delta** = lista de operaciones. Fichero por isla: `isla_{index}.json` con:
  - `seed`, `version`.
  - `heightmap`: textura/array de alturas editada (ver terraformar). Opcional si se usan bloques.
  - `props[]`: objetos colocados → `{ "asset_id", "pos", "rot", "scale", "color" }`.
  - `paint[]`: capas de material/vertex color pintadas (bioma).
  - `agua`, `cielo`: parámetros del `Oceano3D` (nivel, color, olas).
- Guardar el delta (no toda la malla) es lo que hace barato el P2P y el almacenamiento.

Formas de editar el relieve (elegir según el tipo de isla):

1. **Terraformar con heightmap** (recomendado): el terreno es una malla subdividida cuyo desplazamiento en Y lo da una **heightmap**. El usuario "pinta" altura con un pincel; se guarda la heightmap en el delta.
   - Aplicación: `ShaderMaterial` que lee la heightmap y desplaza vértices (barato, GPU), o regenerar la malla con `SurfaceTool`/`ArrayMesh`.
   - P2P: se comparte **la heightmap**, no los vértices → muy ligero.
2. **Editar vértices con `MeshDataTool`** (sculpt libre): se lee la malla, se mueven vértices y se reescribe. Más costoso y más datos a sincronizar; útil si hace falta detalle irregular.
3. **Colocar/quitar bloques** (voxel-like, encaja con `chunk3DBLOCK`): el delta es una lista de `(x, y, z) -> tipo_bloque`. Levantar/poner/romper = añadir/quitar entradas. Ideal para "construir tu isla" estilo cajas, y trivial de replicar.

Construir y decorar (build mode):

- **Inventario de assets** (árboles, casas, rocas…): mostrar catálogo y colocar con el ratón.
- Gizmo de **traslación/rotación/escala**; guardar la transformación en `props[]`.
- Render eficiente: `MultiMeshInstance3D`/`GridMap` para muchos objetos repetidos.
- Pintado de **materiales/bioma** en capas (vertex color o blend de texturas) → `paint[]`.

UI de edición:

- Panel con **modos**: `Terraformar`, `Construir`, `Pintar`, `Ajustes (agua/cielo)`.
- Pincel con radio/fuerza (y simetría opcional).
- **Undo/redo**: pila de operaciones (cada acción = una op del delta) para deshacer sin recargar.
- Entrada/salida del modo edición (tecla `B` o botón), bloqueando el movimiento del avatar mientras se edita.

Autoridad y red P2P (clave):

- **Solo el dueño edita**: comprobar `island_owners[index][0] == multiplayer.get_unique_id()` (o que seas el servidor). El resto ve la isla en **solo lectura**. Opción futura: invitar colaboradores.
- Las ediciones se envían como **operaciones** (deltas), no como estado completo: `rpc("_aplicar_edicion_isla", index, operacion)` con `{tipo, datos}`.
- **Late joiners**: al entrar, además de `_spawn_island_for_player` (`ChunkManager.gd:224`), el servidor/peer dueño envía el **delta** de cada isla (`seed` + ops) para reproducirla. Punto de enganche: justo después de `add_child(new_island)` en `ChunkManager.gd:246`.
- **Reconexión**: al reclamar isla (`_claim_island` / `_adopt_or_register`, `ChunkManager.gd:97/104`), cargar el `isla_{index}.json` y reaplicar las ops tras generar la base.
- Las ops deben ser **deterministas e idempotentes** (reordenar/aplicar dos veces no debe romper la isla).

Persistencia (mismo espíritu que los avatares, ver 2.3):

- Guardar `isla_{index}.json` (delta) localmente y, al cerrar, subirlo a IPFS (`ipfs add --pin`) con puntero `user://ipfs_isla_{index}.cid`.
- Al abrir o al reclamar la isla, `ipfs cat <CID>` para recuperar el delta.
- Alternativa/integración: registrar el CID en la cadena ligera existente (`src/STM_CH/blockchain_ledger.json`) para historial de cambios por isla.
- Catálogo de assets referenciado por `asset_id` estable (no por ruta), para que el delta siga siendo válido aunque se reorganicen carpetas.

Rendimiento y límites:

- Limitar altura/radio del pincel y la densidad de altura de la heightmap (p. ej. 256×256 por isla).
- No replicar la operación de edición más de X veces por segundo: **agrupar** cambios del pincel en un "trazo" y enviar al soltar el botón.
- Con bloques, `GridMap`/`MultiMesh` para no crear miles de nodos.

### 2.8 Checklist pendiente

- [ ] Definir catálogo ampliado y variantes nuevas (avatares 7+): `.tscn`/`.blend`, thumbnail, `avatar.cfg` con género/nombre/colores.
- [ ] Recuperar `AVMJ4` como primer sustituto **con ropa distinta** (reestilizar colores/materiales, conservar acciones).
- [ ] Estilizar el avatar base (`userbaseh1`/hm1) y añadirlo al carrusel (darle acción de reposo válida).
- [ ] Reordenar el carrusel alternando **chica/chico** (los 3 arrays de `SLAV.tscn` en el mismo orden).
- [ ] `SLAV.gd`: catálogo dinámico (dejar de leer los 6 fijos de `SLAV.tscn`).
- [ ] Caché local `user://avatares_usados.json` (escritura al confirmar).
- [ ] Filtro "usados" + lógica "5 restantes + 1 diferente" (relleno con variante/`seed`).
- [ ] Caso de catálogo agotado (reutilizar `ultimo_uso` más antiguo + aviso en pantalla).
- [ ] `owner_uuid` (UUID v4) en `user://registro.cfg` en el primer registro.
- [ ] Subida a IPFS al cerrar: `ipfs add --pin` + escritura de `user://ipfs_avatares.cid` (vía A o B de 2.3).
- [ ] Descarga al arrancar: leer CID → `ipfs cat` → fusionar con caché → antes de `_mostrar_carrusel()` en `Boot.gd`.
- [ ] Manejo de daemon caído / cierre forzado (no bloquear; caer a caché local).
- [ ] Shape keys: verificar que los `.blend` traen morph targets y que Godot las importa; exportar `.glb` explícito.
- [ ] UI de retoque (sliders por grupo) tras el carrusel en `registro.tscn`.
- [ ] Campo `shapes` en el JSON + replicación en el spawn P2P de `PlayerSync.gd`.
- [ ] Servicio de asignación atómica para el visor C# (reserva por `owner_uuid`).
- [ ] Flush del JSON al cerrar sesión y recuperación del mismo avatar al reconectar.
- [ ] Generación determinista por `seed` para variantes sin duplicados.
- [ ] Pruebas: dos usuarios simultáneos nunca reciben el mismo avatar; reconexión devuelve el propio con sus `shapes`.
- [ ] Editor de islas: modelo `isla_{index}.json` (seed + delta: heightmap/props/paint).
- [ ] Terraformar con heightmap (shader de desplazamiento o `SurfaceTool`) o bloques (`GridMap`).
- [ ] Build mode: inventario de assets + gizmo; guardar `props[]` (asset_id, pos, rot, scale).
- [ ] Pintado de bioma/vertex color → `paint[]`; ajustes de `Oceano3D` y cielo.
- [ ] UI de edición (modos, pincel radio/fuerza, undo/redo, entrada con `B`).
- [ ] Autoridad: solo el dueño (`island_owners[index][0]`) edita; resto solo lectura.
- [ ] P2P: replicar **operaciones** (no estado completo) vía `rpc`; enviar delta a late joiners tras `_spawn_island_for_player` (`ChunkManager.gd:246`).
- [ ] Recuperar delta al reclamar isla (`_claim_island`/`_adopt_or_register`) y reaplicar ops deterministas.
- [ ] Persistencia del delta en IPFS (`isla_{index}.json` + puntero CID), con `asset_id` estable.

---

## 3. Deuda técnica generada hoy

### 3.1 Avatares y catálogo

1. **AVMJ3 no es un avatar nuevo**: reutiliza la base Ch22 (misma cara y mallas); solo cambia colores de pelo/ropa. Duplica assets en disco sin aportar diversidad facial real.
2. **`AVMJ4` huérfano**: sigue en disco pero fuera del carrusel. Decisión (ver 2.2.8): **reincorporarlo como primer sustituto con ropa distinta**, no borrarlo.
3. **Falta de metadatos**: no existe `.cfg`/JSON por avatar con género, nombre y colores; el género se infiere del nombre de archivo.

### 3.2 Integración del avatar elegido

4. **Orden obligatorio no protegido**: `ChunkManager.set_player_avatar()` debe llamarse antes de `add_child()`; si se llama después, `@onready userbase` (`ChunkManager.gd:12`) y la caché `TeleportManager._userbase` (`TeleportManager.gd:20`) apuntan al nodo liberado. La API no lo valida.
5. **`old.free()` inmediato** (`ChunkManager.gd:44`): cualquier referencia externa al `USERBASE` original queda colgada; hoy solo se salva por el orden de llamada.
6. **Fallback silencioso**: si el avatar del peer no existe en el cliente, `PlayerSync` muestra `userbaseh1` sin avisar (`PlayerSync.gd:93-97`) → cada peer ve un avatar distinto para el mismo jugador.
7. **Validación por prefijo**: solo se comprueba `res://SLCAV/AVATARESCONANIMACION/`; no hay lista blanca de avatares permitidos.

### 3.3 Clones remotos

8. **Doble instanciación al entrar**: `_ready` pre-crea proxies con `userbaseh1` (`PlayerSync.gd:27`) y el primer RPC los reconstruye (~100 ms), provocando parpadeo con el avatar equivocado.
9. **Índice sin comprobar**: `_net_position` accede a `_proxies[sender]` (`PlayerSync.gd:136`) sin verificar que `_ensure_proxy` haya podido crear el nodo; si `instantiate()` falla, error de índice.
10. **Solape de un frame al reconstruir**: el clon viejo se renombra y `queue_free()` (`PlayerSync.gd:87-88`), pero sigue en el árbol hasta el final del frame mientras el nuevo ya se añade; con cambios de avatar repetidos puede haber duplicados visuales momentáneos.
11. **Strafes remotos no replicados**: `_estado_propio` mapea estados 6/7 a andar (`PlayerSync.gd:153`) y `fija_estado_remoto` no distingue izquierda/derecha.
12. **Etiqueta de nick fija** en `y=2.1` (`PlayerSync.gd:124`): avatares de distinta altura pueden solapar el texto.

### 3.4 Interfaz, textos y entorno

13. **Textos y tamaños hardcodeados** en español y en píxeles (banner 20/30/24 px, offsets `-520..520`): sin i18n ni adaptación a resoluciones estrechas.
14. **Saludo por heurística de ruta**: `Boot._saludo()` usa `.contains("AVMJ")`; se rompe si se renombran escenas o se añaden familias nuevas.
15. **Mensaje duplicado** en dos sitios: `Label3D` del portal y banner de `Boot.gd`; cada cambio hay que hacerlo dos veces.
16. **Sin guarda en `_mostrar_bienvenida()`**: si `mi_isla_lista` se emitiera más de una vez (reconexión/reinstancia futura), se apilarían capas y tweens.
17. **Escena procedural**: `estacion.gd` y `portal_visual.gd` generan geometría y luces por código (no editables en el editor), sin LOD/oclusión; 8 OmniLight + shaders aditivos pueden pesar en equipos modestos y no se probó el renderer Compatibility.
18. **Colisión del portal ajustada a mano** `(3.6, 3.4, 1.2)` con `y=1.7`: si se escala el portal o el avatar, el cruce puede fallar sin aviso.

### 3.5 Proceso y pruebas

19. **Sin suite permanente**: los tests de hoy fueron scripts temporales borrados (`_smoketest`, `_proxytest`, `_wtest`, etc.); no hay CI ni pruebas de regresión.
20. **Sin persistencia del avatar**: el elegido no se guarda; al reabrir, el carrusel vuelve a empezar (base del pendiente de avatares únicos).
21. **Riesgo de BOM**: `entornodeprueba.tscn` se corrompió al editarlo con PowerShell; el flujo de importación no detecta el BOM antes de fallar.
22. **Nick leído en dos sitios** (`Boot` y `PlayerSync` leen `user://registro.cfg` por separado); si el registro no se completó, el banner queda sin nick.

## 4. Notas técnicas

- Los clones remotos se reconstruyen si cambia el avatar del peer; el nodo viejo se renombra `RemotePlayer_removed_%d` antes de `queue_free` para evitar colisiones de nombre.
- `userbaseh1` (hm1) no tiene `paradoMJ1_1`: no sirve para el carrusel, solo como fallback/placeholder (para meterlo al carrusel hay que darle acción de reposo, ver 2.2.9).
- PowerShell 5.1: `Set-Content -Encoding utf8` añade BOM y rompe `.tscn`; usar `System.Text.UTF8Encoding($false)`.
- `registro.gd` guarda el nick en `user://registro.cfg` y lo emite en `registro_completado`; `Boot` lo usa para el saludo.
- **Godot y `.blend`**: Godot no lee `.blend` de forma nativa; al importar llama a Blender y lo convierte a glTF. Para morph targets (shape keys) y control del import, exportar `.glb` explícito.
- **Shape keys = avatares, no terreno**: el terreno editable se hace con heightmap + shader, `ArrayMesh`/`MeshDataTool` o bloques (ver 2.7); nunca con morph targets.
- **Visor C# "wold virtual p2p 3d"**: hoja de ruta detallada en `src/VSC#/README.md` (basado en Singularity, ENet 8910, paridad con Godot).
- **Ficheros duplicados en C: y F:**: `RESUMEN_SESION.md` y el `README.md` se mantienen iguales en ambas rutas; al editar uno, sincronizar el otro.

---

## 5. Hoja de ruta — Reducir el tamaño del proyecto (3.20 GB) sin perder calidad

Medición real de `VersionDe_sesion/CONTRRF/TLLDCD/src/MTBGT/WoldVirtualP2P3D` = **3.44 GB (3.20 GiB)**.

### 5.1 Diagnóstico (medido, ordenado por peso)

Por carpeta:

| Carpeta | Tamaño | Qué es |
|---|---|---|
| `SLCAV/AVATARESCONANIMACION/IMPBLEND` | 2345 MB | `.blend` de avatares + texturas embebidas |
| `.godot` | 536.6 MB | caché de importación (`.ctex`), **regenerable** |
| `imbld/texturas` | 388.9 MB | packs de texturas 4K descargados |
| `ESCENAS` | 10.1 MB | escenas/recursos del mundo |
| `gdscrip` / `gdshader` | ~0 MB | código |

Por tipo de archivo:

| Patrón | Nº | Tamaño | Nota |
|---|---|---|---|
| `*.blend` | 11 | 849.2 MB | **fuentes** (trabajo en Blender) |
| `*.blend1` | 9 | 844.7 MB | **backups automáticos de Blender (duplicados puros)** |
| `*.bak` | 3 | 270.7 MB | backups del editor (2 son `.blend.opencode.bak`) |
| `*.ctex` | 91 | 452.1 MB | dentro de `.godot` (regenerable) |
| `*.png` | 85 | 472 MB | texturas de avatar + capturas |
| `*.zip` | 2 | 194 MB | packs de texturas |
| `*.exr` | 4 | 82.9 MB | mapas 4K de los packs |

Conclusión: **~1.09 GB son copias/backups** (`*.blend1` + `*.bak`) y **~536 MB son caché regenerable**.

### 5.2 Fase 1 — Borrar duplicados y backups (ganancia inmediata ~1.09 GB)

- Borrar todo `*.blend1` (844.7 MB) y `*.bak` (270.7 MB): son copias automáticas, no afectan al proyecto ni a la calidad.
- Desactivar en Blender: `Preferences → Save & Load → Save Versions = 0` (y auto-guardado de temporales off) para que no se vuelvan a crear.
- Añadir a `.gitignore`: `*.blend1`, `*.bak`, `*.blend.opencode.bak`.
- Reversible en cualquier momento desde el `.blend` de origen. Riesgo: ninguno.

### 5.3 Fase 2 — Excluir lo regenerable del repo y del release (~536 MB)

- `.godot/` **no** debe versionarse ni empaquetarse: se regenera con `godot --headless --import`.
- Añadir `.godot/` a `.gitignore` (si no está) y a los filtros de export del preset.
- El PCK final lleva los recursos ya importados y comprimidos; la caché `.godot/imported` no viaja.

### 5.4 Fase 3 — Texturas de terreno (`imbld/texturas`, 388.9 MB)

- De los 2 packs 4K (`stony_dirt_path_4k`, `rocky_terrain_02_4k`): conservar solo los mapas que use el shader; borrar los `.zip` (194 MB) tras extraer.
- Bajar resolución: `diff/nor` 4K → 2K; `disp/spec` → 1K si a la distancia de cámara no se nota.
- Convertir `.exr` (82.9 MB) a PNG 16-bit o WebP cuando no haga falta rango HDR; para runtime, KTX2/BC.
- Purgar los mapas no referenciados.

### 5.5 Fase 4 — Texturas de avatar (`*.png` 472 MB) y `.blend` (849 MB)

- Normal maps 4K/8K (`Ch22/Ch23/Ch31`, ~21-23 MB c/u, además duplicados en `AVMJR` y `AVHMB`): reducir a 2K y **deduplicar** los que se repiten entre avatares.
- No **empaquetar** texturas dentro del `.blend`: `File → External Data → Unpack Resources`; mantenerlas externas y en 2K.
- Separar **fuente** (`.blend`, edición en Blender) de **runtime** (recurso importado / `.glb`). Los `.blend` no necesitan vivir dentro de `res://`; si se versionan, con Git LFS y fuera de la carpeta del proyecto Godot.
- Al guardar en Blender: `Compress` activado y purgar imágenes/huérfanas (`Outliner → Orphan Data → Purge`).

### 5.6 Fase 5 — Compresión en el import de Godot (afecta a `.godot` y al build)

- Normal maps: importar como **VRAM Compressed** (BC/S3TC/ETC2), **nunca** lossless → `.ctex` mucho menores.
- Diffuse: VRAM comprimido o WebP; tope 2K donde no se vea de cerca.
- Ajustar el import por textura (Size limit / Compress Mode) y reimportar (`--headless --import`); medir `.godot/imported` antes/después.

### 5.7 Fase 6 — Fuera del proyecto (imágenes de sesión/capturas)

- Mover capturas y PNG de referencia (no son assets) a una carpeta aparte; no van al repo ni al release.

### 5.8 Fase 7 — Release y export

- Filtros del preset de export: excluir `*.blend`, `*.blend1`, `*.bak`, `imbld/`, `.godot/` y capturas.
- **PCK comprimido** (Embed PCK + zstd) y asset adjunto con rutas cortas (como la release actual `v0.0.02_1_actualizacion_86bea3a9`).
- Git LFS para binarios que sí deban versionarse (`.blend`, `.glb`, texturas) para no engordar el histórico.

### 5.9 Fase 8 — Verificación (no perder calidad ni logros)

- Medir antes/después: tamaño de carpeta, `.godot/imported` y PCK final.
- `godot --headless --import` y arranque `--quit-after` → **EXIT=0**.
- Repetir tests headless (isla/avatar 14/14, clones remotos 9/9, portal 13/13, rótulos/saludo 9/9).
- Comparar capturas (portal, avatares, isla) antes/después para confirmar que no hay pérdida visible.

### 5.10 Objetivo cuantificado

| Etapa | Tamaño estimado |
|---|---|
| Actual | 3.20 GiB |
| Tras Fase 1 (borrar backups) | ~2.15 GiB |
| Tras Fase 2 (no versionar `.godot`) | ~1.6 GiB local (release mucho menor) |
| Tras Fases 3-5 (texturas + import) | ~1.1-1.3 GiB |
| **Meta** | **~1.2 GiB (−60 %) sin pérdida visible** |

Todos los logros (carrusel, portal, islas P2P, clones, shaders) se conservan: solo se eliminan duplicados, caché regenerable y resolución de texturas sobrante.
