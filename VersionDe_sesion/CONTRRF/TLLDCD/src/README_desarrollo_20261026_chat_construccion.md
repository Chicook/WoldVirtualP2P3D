# README de Desarrollo — Sesión 2026-10-26 (continuación)

## WoldVirtualP2P3D · CONTRRF / TLLDCD

> **Rama de trabajo:** `DevQoderIA`
> **Repositorio:** `https://github.com/Chicook/WoldVirtualP2P3D.git`
> **Alcance:** `src/` — visor C# (`VSC#`) y mundo Godot (`MTBGT/WoldVirtualP2P3D`).
> **Documento hermano:** [`README_desarrollo_20261026.md`](README_desarrollo_20261026.md) cubre los 7 bloques previos de la jornada (cuenta única, llave de hardware, barrera de login, animaciones, foco, optimización de texturas y retirada de `test_user_data`). Este archivo **no repite** ese contenido: documenta el resto del trabajo del día, con prioridad en el sistema de terreno y construcción.
> **Estado del árbol:** cambios sin commit. No se ha publicado binario, PCK ni OTA.

---

## 1. Resumen ejecutivo

| Bloque | Subsistema | Qué se hizo | Estado |
|---|---|---|---|
| Chat de texto, voz y webcam | `VSC#` (WPF) | Relay WebSocket, cliente, audio NAudio, webcam AForge, panel acoplado y proxy `/chat` | Implementado y validado con selftest sin interfaz (24/24). Sin prueba entre dos máquinas |
| Amigos y chat privado | `VSC#` (WPF) | Código de amigo, solicitudes, lista local, ventana de conversación privada | Implementado y validado en el mismo selftest (24/24). Sin prueba entre dos máquinas |
| Clic de avatar y foco de teclado | `VSC#` + Godot | Selección por rayo, liberación al perder foco, reenvío de teclado y resaltado del chat | Implementado y validado en headless (25/25). Sin prueba visual dentro del visor embebido |
| Explorador y registro de isla | Godot | Botones «Explorador de islas» y «Registra tu isla», propiedad persistente por UUID | Implementado y validado en headless (23/23). Sin prueba real de dos instancias |
| Edición de terreno | Godot | Horneado por isla, pincel de 4 herramientas, normales, colisión trimesh, formato `WVPT` | Implementado y validado en headless (84/84). Sin prueba real de dos máquinas |
| Construcción de prims | Godot | 5 primitivas, rezado, selección, transformación, color, duplicado, borrado, red y persistencia | Implementado y validado en headless (84/84). Sin prueba real de dos máquinas |
| Integración en el mundo | Godot | Nodo `Constructor` en `ISLA3Dblock.tscn`, registro desde `ChunkManager`, bloqueo del avatar | Sonda de escena OK y humo del mundo OK |

**Validación global:** compilación C# con 0 errores y 0 avisos; suites headless con 0 fallos. **No** se ha probado el flujo completo entre dos máquinas, ni la latencia del túnel, ni la interfaz WPF en uso real.

---

## 2. El túnel: qué existe realmente

La petición hablaba de conectar la construcción al «túnel SSH del sistema». La auditoría del código **no encuentra ningún túnel SSH**: no hay cliente SSH, ni reenvío de puertos, ni credenciales de ese tipo. Lo que existe es un túnel **HTTP/HTTPS** que publica el visor:

```
Anfitrión (Windows)                                  Invitado
┌──────────────────────────────────────┐
│ Godot  WS 8911  ◄── WebNodo ─────────┼──► túnel HTTPS público ──► wss://host/...
│ Chat   WS 8920  ◄── WebNodo /chat ───┘    (cloudflared, serveo,
└──────────────────────────────────────┘     localhost.run, …)
```

- [`Red.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/Red.gd) resuelve el destino por argumentos, `p2p_session.json`, beacon LAN y túneles HTTP (comentarios en las líneas 134-135). El puerto del mundo es `8911`.
- [`WebNodoService.cs`](VSC%23/Services/WebNodoService.cs) publica ese WebSocket y separa la ruta `/chat` hacia el relay local del chat (puerto `8920`); el resto va al motor Godot.
- El sistema de construcción **usa el mismo WebSocket 8911**: no abre puerto, canal ni credencial nuevos. Por tanto sí está conectado al túnel del sistema, pero por WebSocket sobre HTTP, no por SSH.
- **Consecuencia:** si el túnel o el WebNodo caen, caen el mundo, la construcción y el chat a la vez. Un túnel SSH exigiría diseñar host, autenticación y reenvío; **no está implementado** y no se ha simulado.

---

## 3. Trabajo realizado

### 3.1 Chat de texto, voz y webcam (`VSC#`)

Implementado en [`VSC#/Chat/`](VSC%23/Chat) y acoplado a la derecha del visor. El detalle de diseño está en [`VSC#/README.md`](VSC%23/README.md), secciones 7 a 9; aquí queda el resumen verificable.

| Archivo | Responsabilidad |
|---|---|
| [`ChatProtocol.cs`](VSC%23/Chat/ChatProtocol.cs) | Límites y tramas: texto JSON; audio/vídeo binario `[tipo][id emisor][payload]`. |
| [`ChatRelayServer.cs`](VSC%23/Chat/ChatRelayServer.cs) | Relay WebSocket del anfitrión (8920-8929), máximo 16 clientes, ping/pong, límites de tamaño y tasa. |
| [`ChatClient.cs`](VSC%23/Chat/ChatClient.cs) | Cliente `ClientWebSocket`, recepción de texto y medios, reconexión gobernada por `MainWindow`. |
| [`ChatVoice.cs`](VSC%23/Chat/ChatVoice.cs) | Micrófono NAudio a 16 kHz, PCM16 mono, tramas de 20 ms y mezcla de voces remotas. |
| [`ChatWebcam.cs`](VSC%23/Chat/ChatWebcam.cs) | Captura DirectShow (AForge), 320×180, JPEG calidad 55, ~4 fps. |
| [`Services/WebNodoService.cs`](VSC%23/Services/WebNodoService.cs) | Enruta `WS /chat` al relay y el resto a `ws://localhost:8911`. |
| [`MainWindow.xaml.cs`](VSC%23/MainWindow.xaml.cs) | Arranque del relay, conexión, panel, estados de micrófono/cámara, tiles de vídeo y reconexión. |

**Funcionamiento:** cada visor levanta su propio relay, de modo que cualquiera puede asumir el rol de anfitrión tras una migración. Si el visor es anfitrión de la sesión se conecta a su relay local; si no, a `wss://<anfitrión>/chat`. Micrófono y webcam solo se activan al pulsar sus botones.

**Límites asumidos:** sin autenticación (quien tenga el enlace público entra, con 16 clientes y límites de tasa como única protección); sin selector de dispositivo; sin transcodificación de audio; eco sin auriculares; el vídeo se reenvía a todos y el ancho de banda crece con cada par.

### 3.2 Amigos y chat privado (`VSC#`)

| Archivo | Responsabilidad |
|---|---|
| [`Chat/ChatProtocol.cs`](VSC%23/Chat/ChatProtocol.cs) | `uid` normalizado y código de amigo de 8 caracteres derivado con SHA-256. |
| [`Chat/ChatRelayServer.cs`](VSC%23/Chat/ChatRelayServer.cs) | Resuelve el destino por `uid` o por código y entrega solo a esa persona; 20 acciones sociales cada 10 s. |
| [`Chat/ChatClient.cs`](VSC%23/Chat/ChatClient.cs) | Envía y recibe `friend_req`, `friend_ok`, `friend_no`, `dm` y sus avisos de fallo. |
| [`Chat/FriendsStore.cs`](VSC%23/Chat/FriendsStore.cs) | Persistencia local en `%LocalAppData%\WoldVirtualP2P3D\user\friends_<uid>.json`. |
| [`PrivateChatWindow.xaml(.cs)`](VSC%23/PrivateChatWindow.xaml.cs) | Ventana de conversación privada con estado en línea e historial en memoria. |
| [`MainWindow.xaml(.cs)`](VSC%23/MainWindow.xaml.cs) | Panel de amigos, código copiable, alta por código, solicitudes, no leídos y apertura del privado. |

**Límites asumidos:** no hay servidor central ni cola offline; la lista de amigos es local al equipo y es JSON plano sin cifrar; el historial privado se pierde al cerrar; el relay no comprueba la amistad (solo enruta); un perfil sin `uuid` cae a un hash del alias.

### 3.3 Clic de avatar y foco de teclado

- El avatar ya no se mueve por tener el foco la ventana: **hay que hacer clic sobre él**. Un clic izquierdo lanza un rayo desde la cámara y activa `control_avatar`; un clic fuera lo deselecciona y lo detiene.
- Al perder el foco (abrir el chat, pulsar micrófono/cámara, cambiar de ventana) se suelta el control, se anula la velocidad horizontal y se liberan las acciones `ui_*` para que una flecha retenida no mueva al personaje.
- En WPF, [`GodotHwndHost.cs`](VSC%23/GodotHwndHost.cs) devuelve el teclado a Godot con `WM_PARENTNOTIFY` y no reenvía teclas mientras se escribe en un `TextBox`.
- El cuadro de texto del chat se resalta con borde turquesa al recibir el foco.

**Validación:** [`tools/probar_control_clic.gd`](MTBGT/WoldVirtualP2P3D/tools/probar_control_clic.gd) supera **25/25** comprobaciones en headless sobre `userbaseh1`, `AVMJ1Ch3D` y la cápsula. **No** se ha validado visualmente dentro del visor embebido.

### 3.4 Explorador y registro de isla (Godot)

- [`TeleportPanel.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/TeleportPanel.gd) renombra el botón a **«Explorador de islas»** (sigue respondiendo a <kbd>T</kbd>) y añade **«Registra tu isla»** justo al lado. La lista marca `TU ISLA`, `TU ISLA (sin registrar)` o `registrada`.
- [`ChunkManager.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/ChunkManager.gd) vincula un UUID estable de instalación ([`Identidad.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/Identidad.gd)) al índice de isla y lo persiste en `user://islas_registro.cfg`. Al reconectar, `_claim_island()` recupera la misma isla; el spawn es idempotente y la posición guardada solo se restaura si pertenece a esa isla.
- El botón de registro guarda la isla ya asignada; **no crea una isla adicional**. La señal `isla_registrada` actualiza la etiqueta y la lista.

**Validación:** [`tools/probar_registro_islas.gd`](MTBGT/WoldVirtualP2P3D/tools/probar_registro_islas.gd) supera **23/23** comprobaciones (persistencia, rechazo de índices ajenos, renombrado y visibilidad de ambos botones). **Límite conocido:** si otra máquina actúa como anfitrión sin el registro previo ni una isla con ese UUID ya instanciada, no puede validar la propiedad y asigna una isla nueva. No hay almacenamiento compartido entre anfitriones.

### 3.5 Edición de terreno (Godot)

Núcleo en [`TerrenoEditable.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/TerrenoEditable.gd), orquestado por [`Construccion.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/Construccion.gd) y activado con <kbd>B</kbd>.

- **Horneado único por isla:** `bake_mesh_from_current_blend_shape_mix()` convierte el morph en geometría real y deja una malla propia por instancia. Antes se captura el material de superficie (`surface_override` → `material_override` → material de la malla original), porque el horneado lo descarta.
- **Geometría medida:** **10 920 vértices y 64 272 índices** por isla; rango base de altura `0,0–0,5584 m`. Los límites del pincel son `0,0–0,95 m`.
- **Pincel:** radio en metros, caída *smoothstep*, cuatro herramientas (subir, bajar, suavizar, aplanar). Recalcula normales con el producto vectorial de la cara y reconstruye el `ArrayMesh`.
- **Colisión:** `ConcavePolygonShape3D.set_faces` con las 64 272 caras. Se regenera con *debounce* de 0,5 s tras el último cambio para no repetirla en cada fotograma.
- **Formato propio `WVPT` v1:** magia + versión `u16` + recuento `u32` + hash `s64` de la geometría base + alturas `float32`. `cargar()` rechaza magia, versión, recuento o hash incorrectos y avisa si la geometría base cambió.
- **Persistencia:** `user://construccion/terreno_<idx>_<uuid>.bin` y `prims_<idx>_<uuid>.json`. Al salir se guarda lo pendiente que este peer pueda escribir.

**Rendimiento medido en headless (2026-10-26):** paso de pincel con 29 vértices afectados en **6,75 ms**; reconstrucción de colisión en **19,29 ms**; blob de terreno de **43 698 B** que comprime a **17 388 B** con zstd. El coste del pincel es lineal con el total de vértices, no con el radio.

### 3.6 Construcción y edición de prims (Godot)

- Catálogo procedural en [`Prims.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/Prims.gd): **cubo, esfera, cilindro, cono y toro**, con paleta de 8 colores, tamaños por defecto y serialización JSON segura (sin `Vector3` ni `Color`).
- **Rezado** desde la cámara sobre la superficie; **selección** con clic; movimiento con flechas/WASD; altura con <kbd>RePág</kbd>/<kbd>AvPág</kbd>; rotación de 15° con <kbd>Q</kbd>/<kbd>E</kbd>; escala proporcional con <kbd>+</kbd>/<kbd>−</kbd>; duplicado con <kbd>Ctrl</kbd>+<kbd>D</kbd>; borrado con <kbd>Supr</kbd>. Rejilla de 0,5 m (1 m con <kbd>Shift</kbd>).
- Panel en [`ConstructorPanel.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/ConstructorPanel.gd): herramienta, radio, fuerza, tipo, color, escala, snap y estado de la isla. Se coloca debajo de la barra del explorador para no taparlo.
- **Autoridad:** solo el dueño de la isla edita. El anfitrión valida `island_owners` (peer id/UUID), difunde por RPC fiable y los clientes suben su estado al entrar. El estado viaja troceado en bloques de **6000 B** con zstd.
- **Permisos:** seleccionar o esculpir una isla ajena se rechaza con aviso; el cliente no aplica cambios optimistas sobre islas que no puede guardar.
- **Límites:** sin deshacer/rehacer ni selección múltiple; las prims no tienen física propia; la colisión del cilindro/cono es aproximada y el toro usa trimesh; la colisión del terreno va 0,5 s por detrás durante el trazo.

### 3.7 Integración en el mundo

- [`ISLA3Dblock.tscn`](MTBGT/WoldVirtualP2P3D/ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn) monta un nodo `Constructor` con `Construccion.gd`.
- [`ChunkManager.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/ChunkManager.gd) llama a `registrar_isla()` justo después de crear cada isla, tanto en el anfitrión como en los clientes.
- En modo construcción se marca `construccion_activa` en el avatar, se pone `control_avatar = false` y se liberan las acciones `ui_*`. Los tres controladores de avatar (`userbase.gd`, `userbaseh_1.gd`, `AVMJ1Ch3D.gd`) ignoran el clic de selección mientras el modo está activo.
- **Humo del mundo:** al arrancar el mundo completo se observó `Generando isla 0 para el jugador 1` seguido de `[Construccion] Isla 0 preparada: 10920 vértices`, sin errores de construcción.

---

## 4. Validación ejecutada (2026-10-26)

| Comprobación | Comando | Resultado |
|---|---|---|
| Compilación del visor | `dotnet build VSC#/Visor3D.csproj -p:SkipGodotAssets=true -c Debug` | **0 errores, 0 avisos** (1,16 s incremental) |
| Chat, amigos y proxy | `DMWoldVirtualp2pCNXv2.5.6.exe --chat-selftest` | **24/24 OK, 0 fallos**; micrófonos=1, webcams=1; mismo binario publicado |
| Terreno y prims | `Godot --headless --path . --script res://tools/probar_construccion.gd` | **84 OK, 0 fallos**; pincel 6,75 ms, colisión 19,29 ms, blob 43 698 → 17 388 B |
| Clic de avatar | `Godot --headless --path . --script res://tools/probar_control_clic.gd` | **25/25 OK, 0 fallos** |
| Registro de islas | `Godot --headless --path . --script res://tools/probar_registro_islas.gd` | **23/23 OK, 0 fallos** |
| Escena de construcción | `Godot --headless --path . --script res://tools/sonda_escena_construccion.gd` | `Constructor=true`, script `res://gdscrip/Construccion.gd`, **OK** |
| Humo del mundo | Arranque completo de `ISLA3Dblock.tscn` | Isla 0 registrada con 10 920 vértices, sin errores de construcción |
| Prueba de arranque del binario | `DMWoldVirtualp2pCNXv2.5.6.exe --startup-selftest` | **11/11 OK, exit 0**; PCK extraído = embebido; motor headless isla+WS 8911 sin `ERROR` |
| Descarga del portal | `GET http://127.0.0.1:3030/descargar` con el visor abierto | **200**, `Content-Length: 788176767`, `filename="DMWoldVirtualp2pCNXv2.5.6.exe"` |
| Asset publicado | `gh api repos/…/releases/tags/v2.5.6` | digest `sha256:b028d5…7633` = SHA-256 local |

**No ejecutado (y por tanto no acreditado):**

- Sesión real de dos máquinas con construcción, chat, voz y webcam a través del túnel.
- Latencia, pérdida de paquetes y reconexión del túnel HTTP.
- Interacción visual completa en el visor WPF embebido (foco, clic y resaltado).
- OTA de punta a punta 2.5.5 → 2.5.6 en un equipo con la versión anterior.
- Prueba de migración de anfitrión con permisos de construcción y chat.

---

## 5. Pendientes priorizados

### P0 — Antes de considerar la función terminada

1. **Prueba de dos máquinas para construcción:** pincel, rezado, permisos, guardado, recarga y migración de anfitrión.
2. **Prueba de dos máquinas para chat:** texto, voz, webcam, amigos, privados y reconexión tras migración.
3. **Prueba visual del visor embebido:** clic sobre el avatar, flechas, foco del chat y resaltado.
4. **Checklist de release:** completar [`REGLAS_DE_ACTUALIZACION.md`](../../../../REGLAS_DE_ACTUALIZACION.md) §7 antes de generar PCK, binario u OTA.

### P1 — Producto

5. **Deshacer/rehacer y selección múltiple** en construcción; hoy un error de pincel solo se corrige esculpiendo de nuevo.
6. **Colisión incremental del terreno** (o malla reducida/índice espacial) para que el avatar no atraviese el suelo durante el trazo.
7. **Colisión exacta y física de prims**; hoy el cilindro/cono son aproximados y ninguna prim tiene cuerpo físico propio.
8. **Persistencia de permisos tras migración de anfitrión:** el nuevo host debe reconocer al dueño sin obligarle a reconectarse.
9. **Chat:** autenticación/acceso, cola offline, sincronización de amigos entre equipos, historial privado persistente y selector de micrófono/cámara.
10. **InputMap:** las teclas de construcción (`B`, `Q`, `E`, `+`, `−`, `Supr`) siguen cableadas; conviene definir acciones semánticas.

### P2 — Mantenimiento y deuda

11. **Formato de terreno v2:** deltas incrementales, versión explícita y estrategia de migración si cambia la geometría base.
12. **Transferencia delta:** hoy se envía el estado completo al entrar; con muchas islas el coste crece.
13. **Almacenamiento compartido/backup:** los archivos viven en `user://construccion/` de cada peer, sin respaldo ni cifrado.
14. **Dividir `Construccion.gd`** (1 196 líneas): terreno, prims, red y UI en módulos separados.
15. **Deuda previa del proyecto:** texturas duplicadas, textura de terreno 4K, estructura de carpetas, erratas de nombres y controladores de avatar triplicados (ver [`README.md`](MTBGT/WoldVirtualP2P3D/README.md) y [`README_DESARROLLO.md`](README_DESARROLLO.md)).

---

## 6. Deuda técnica generada

1. **Monolito de construcción:** `Construccion.gd` concentra entrada, red, persistencia, UI y edición. Funciona, pero es difícil de probar por partes y de revisar.
2. **Pincel O(n):** cada paso recorre los 10 920 vértices. Con mallas más densas o varias islas editándose a la vez, el coste subirá; no hay índice espacial ni LOD de edición.
3. **Colisión diferida:** 19,29 ms por reconstrucción y un *debounce* de 0,5 s. Durante el trazo el avatar puede caer a través del terreno.
4. **Estado completo por red:** el blob medido es pequeño (17,4 KB comprimido), pero se reenvía entero; no hay delta por prim ni control de versión por objeto.
5. **Dependencia de la geometría base:** si el GLTF de la isla cambia, el hash invalida las alturas guardadas (se avisa y se descartan). No hay migración automática.
6. **Persistencia local y frágil:** `user://construccion/` no se comparte, no se respalda y no está cifrado; un fallo de disco o un cambio de UUID deja la isla sin cargar.
7. **Permisos dependientes del registro:** tras una migración, el anfitrión puede no reconocer al dueño hasta que este vuelva a registrarse; el estado ajeno queda en solo lectura.
8. **Prims sin física ni colisión exacta:** el toro usa trimesh; el resto, formas aproximadas. No hay cuerpos rígidos ni interacción.
9. **UI acoplada:** el panel usa posiciones fijas debajo de la barra del explorador y comparte escena con el modo construcción; cambios de layout pueden solaparlo.
10. **Chat sin autenticación:** el relay acepta cualquier cliente con el enlace; los límites de 16 clientes y de tasa son la única protección. Los amigos y privados son locales y sin cola offline.
11. **Dependencia total del túnel HTTP:** mundo, construcción y chat comparten WebNodo. No hay túnel SSH ni ruta alternativa; si el túnel cae, todo cae.
12. **Pruebas solo headless:** las suites validan lógica, formatos y permisos, pero no red real, latencia, túnel ni interfaz. No hay CI que las ejecute.
13. **Documentación dispersa:** conviven `README_DESARROLLO.md`, `README_desarrollo_20261026.md`, este archivo, `MTBGT/.../README.md` y `VSC#/README.md`; mantenerlos sincronizados es deuda explícita.

---

## 7. Archivos nuevos y modificados

### Godot (`MTBGT/WoldVirtualP2P3D`)

| Archivo | Tipo | Cambio |
|---|---|---|
| [`gdscrip/TerrenoEditable.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/TerrenoEditable.gd) | Nuevo | Horneado, pincel, normales, colisión, formato `WVPT`. |
| [`gdscrip/Prims.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/Prims.gd) | Nuevo | Catálogo, mallas, materiales y serialización de prims. |
| [`gdscrip/Construccion.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/Construccion.gd) | Nuevo | Modo, entrada, edición, permisos, red y persistencia. |
| [`gdscrip/ConstructorPanel.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/ConstructorPanel.gd) | Nuevo | Panel de construcción. |
| [`gdscrip/Identidad.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/Identidad.gd) | Nuevo | UUID estable de instalación. |
| [`ESCENAS/.../ISLA3Dblock.tscn`](MTBGT/WoldVirtualP2P3D/ESCENAS/sceneOPTM/constructor/chunk3DBLOCK/ISLA3Dblock.tscn) | Modificado | Nodo `Constructor`. |
| [`gdscrip/ChunkManager.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/ChunkManager.gd) | Modificado | Registro de islas y llamada a `registrar_isla()`. |
| [`gdscrip/TeleportManager.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/TeleportManager.gd) y [`TeleportPanel.gd`](MTBGT/WoldVirtualP2P3D/gdscrip/TeleportPanel.gd) | Modificados | Explorador, botón de registro y señal `isla_registrada`. |
| `gdscrip/userbase.gd`, `.../userbaseh_1.gd`, `.../AVMJ1Ch3D.gd` | Modificados | Clic de selección y bloqueo en modo construcción. |
| [`tools/probar_construccion.gd`](MTBGT/WoldVirtualP2P3D/tools/probar_construccion.gd) | Nuevo | Suite de 84 comprobaciones. |
| [`tools/probar_control_clic.gd`](MTBGT/WoldVirtualP2P3D/tools/probar_control_clic.gd) | Nuevo | Suite de 25 comprobaciones. |
| [`tools/probar_registro_islas.gd`](MTBGT/WoldVirtualP2P3D/tools/probar_registro_islas.gd) | Nuevo | Suite de 23 comprobaciones. |
| [`tools/sonda_escena_construccion.gd`](MTBGT/WoldVirtualP2P3D/tools/sonda_escena_construccion.gd) | Nuevo | Comprueba el montaje del nodo `Constructor`. |
| [`README.md`](MTBGT/WoldVirtualP2P3D/README.md) | Modificado | Sección 10, deuda de construcción y roadmap. |

### Visor C# (`VSC#`)

| Archivo | Tipo | Cambio |
|---|---|---|
| `Chat/ChatProtocol.cs`, `ChatRelayServer.cs`, `ChatClient.cs`, `ChatVoice.cs`, `ChatWebcam.cs`, `FriendsStore.cs` | Nuevos | Transporte, audio, vídeo, amigos y persistencia. |
| [`PrivateChatWindow.xaml`](VSC%23/PrivateChatWindow.xaml) y [`.xaml.cs`](VSC%23/PrivateChatWindow.xaml.cs) | Nuevos | Ventana de chat privado. |
| [`MainWindow.xaml`](VSC%23/MainWindow.xaml) y [`MainWindow.xaml.cs`](VSC%23/MainWindow.xaml.cs) | Modificados | Panel de chat/amigos, arranque, reconexión y resaltado. |
| [`GodotHwndHost.cs`](VSC%23/GodotHwndHost.cs) | Modificado | Reenvío de teclado y foco con `WM_PARENTNOTIFY`. |
| [`Services/WebNodoService.cs`](VSC%23/Services/WebNodoService.cs) | Modificado | Ruta `/chat` hacia el relay. |
| [`Visor3D.csproj`](VSC%23/Visor3D.csproj) | Modificado | NAudio 2.3.0, AForge.Video 2.2.5 y AForge.Video.DirectShow 2.2.5. |
| [`README.md`](VSC%23/README.md) | Modificado | Secciones 7, 8 y 9 (chat, clic y amigos). |

---

## 8. Cómo usarlo

### Construcción (Godot)

1. Entrar en el mundo y pulsar <kbd>B</kbd> o el botón **«Construcción (B)»**.
2. Elegir herramienta en el panel: Seleccionar, Subir, Bajar, Suavizar o Aplanar.
3. Arrastrar con el botón izquierdo sobre el terreno de la propia isla para esculpir.
4. Con **Seleccionar**, hacer clic en una prim; después mover, rotar, escalar, duplicar o borrar.
5. Elegir tipo y color en el panel y pulsar **Rezar** para crear una prim nueva.
6. Salir con <kbd>B</kbd> o <kbd>Esc</kbd>. El avatar queda libre; hay que volver a hacer clic sobre él para caminar.

> El terreno y las prims solo se pueden editar en la isla propia. En islas ajenas el panel muestra el estado en tono de aviso y rechaza la edición.

### Pruebas

```bash
# C# (desde src/)
E:/Program\ Files/dotnet/dotnet.exe build "VSC#/Visor3D.csproj" -p:SkipGodotAssets=true -c Debug

# Selftest del chat (el ejecutable compilado)
"VSC#/bin/Debug/net8.0-windows/win-x64/DMWoldVirtualp2pCNXv2.5.6.exe" --chat-selftest

# Prueba de arranque previa a publicar
"VSC#/bin/Debug/net8.0-windows/win-x64/DMWoldVirtualp2pCNXv2.5.6.exe" --startup-selftest

# Godot (desde MTBGT/WoldVirtualP2P3D)
"C:/Users/User/Desktop/Godot_v4.7.2-stable_win64_console.exe" --headless --path . \
  --script res://tools/probar_construccion.gd
```

---

## 9. Publicación v2.5.6 (2026-10-26)

Binario y metadatos subidos a la release existente [`v2.5.6`](https://github.com/Chicook/WoldVirtualP2P3D/releases/tag/v2.5.6):

| Dato | Valor |
|---|---|
| Asset | `DMWoldVirtualp2pCNXv2.5.6.exe` |
| Tamaño | 788 176 767 B (751,7 MiB) |
| SHA-256 | `b028d58745e2d9b8b4f13854e4c2ed6746412a2a5cf0f0e47e251d49c1157633` |
| PCK embebido | `wvp3d_v256.pck`, 537 803 740 B (512,9 MiB), exportado 2026-10-26 16:16 |
| `release.json` | version `2.5.6`, tag `v2.5.6`, exe y URL del asset nuevo |
| `SHA256SUMS` | exe + `release.json` |
| Prueba de arranque | 11/11 OK, exit 0 |

Decisiones y límites que deben quedar escritos:

1. **El asset viejo no se borra.** La release v2.5.6 ya contenía `DMWoldVirtualp2pCNXv2.5.5.exe` (11 descargas al publicar). Se **añadió** el binario nuevo y se reemplazaron sólo los metadatos. `UpdateChecker.ElegirAsset` ordena los `.exe` por la versión del nombre, así que elige `2.5.6`.
2. **El tag no se mueve.** `v2.5.6` sigue apuntando al commit `46b0ca5`; moverlo o renombrarlo está prohibido por [`REGLAS_DE_ACTUALIZACION.md`](../../../../REGLAS_DE_ACTUALIZACION.md) §8.2. El código fuente de este binario vive en la rama `DevQoderIA`.
3. **El motor se validó desde el PCK.** La prueba lanza el Godot extraído con `--headless --main-pack`, exige `exit=0`, isla preparada, WebSocket 8911 activo y **cero** líneas `ERROR`/`SCRIPT ERROR`.
4. **Corrección incluida en el PCK:** `gdscrip/Personalizacion.gd` calculaba la altura del avatar con `global_transform` antes de entrar en el árbol, lo que emitía `ERROR: Condition "!is_inside_tree()"` y dejaba la escala a cero. Ahora compone transformaciones locales; por eso el PCK se reexportó antes de compilar.
5. **Límite no acreditado:** no se ejecutó el OTA 2.5.5 → 2.5.6 en un equipo con la versión anterior, ni una sesión de dos máquinas. La descarga del portal y el asset sí se comprobaron.

---

## 10. Reglas para continuar esta fase

1. **No publicar** binario, PCK ni OTA sin completar el checklist de [`REGLAS_DE_ACTUALIZACION.md`](../../../../REGLAS_DE_ACTUALIZACION.md) §7.
2. **No afirmar** que existe túnel SSH: el sistema usa túneles HTTP/WebSocket. Si se quiere SSH, es trabajo pendiente con diseño propio.
3. **No dar por probada** la red de construcción ni el chat entre dos máquinas hasta ejecutar esa prueba y conservar el log.
4. **Commitear solo fuentes** (C#, GDScript, XAML, Markdown, configuración); nunca `.exe`, `.dll`, `.zip`, `.pck` ni datos de usuario.
5. **No borrar ni realinear** ramas de otros agentes; hay sesiones concurrentes sobre el mismo repositorio.
6. **Mantener la documentación con evidencia:** código y logs mandan; las etiquetas de estado deben distinguir «implementado», «validado en headless» y «probado en red real».

---

## 11. Referencias

- [`README_desarrollo_20261026.md`](README_desarrollo_20261026.md) — primeros 7 bloques de la jornada.
- [`README_DESARROLLO.md`](README_DESARROLLO.md) — auditoría amplia del estado de `src/`.
- [`MTBGT/WoldVirtualP2P3D/README.md`](MTBGT/WoldVirtualP2P3D/README.md) — arquitectura del mundo Godot, sección 10 de construcción.
- [`VSC#/README.md`](VSC%23/README.md) — arquitectura del visor, secciones 7 a 9 de chat, clic y amigos.
- [`HOJA_DE_RUTA.md`](HOJA_DE_RUTA.md) — hoja de ruta general del proyecto.

---

*Documento generado el 2026-10-26 a partir del código y de las ejecuciones de prueba de la sesión. El binario 2.5.6 se publicó el mismo día; ver §9.*
