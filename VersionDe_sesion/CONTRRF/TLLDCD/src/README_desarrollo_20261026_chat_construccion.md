# README de Desarrollo — Sesión 2026-10-26 (continuación)

## WoldVirtualP2P3D · CONTRRF / TLLDCD

> **Rama de trabajo:** `DevQoderIA`
> **Repositorio:** `https://github.com/Chicook/WoldVirtualP2P3D.git`
> **Alcance:** `src/` — visor C# (`VSC#`) y mundo Godot (`MTBGT/WoldVirtualP2P3D`).
> **Documento hermano:** [`README_desarrollo_20261026.md`](README_desarrollo_20261026.md) cubre los 7 bloques previos de la jornada (cuenta única, llave de hardware, barrera de login, animaciones, foco, optimización de texturas y retirada de `test_user_data`). Este archivo **no repite** ese contenido: documenta el resto del trabajo del día, con prioridad en el sistema de terreno y construcción.
> **Estado del árbol:** correcciones de la 2.5.8 sin commit al empezar esta edición. Binarios publicados el 2026-10-26: 2.5.6 (§9), 2.5.7 (§10) y 2.5.8 (§11). El OTA entre versiones sigue sin ejecutar.

---

## 1. Resumen ejecutivo

| Bloque | Subsistema | Qué se hizo | Estado |
|---|---|---|---|
| Chat de texto, voz y webcam | `VSC#` (WPF) | Relay WebSocket, cliente, audio NAudio, webcam AForge, panel acoplado y proxy `/chat` | Implementado y validado con selftest sin interfaz (24/24). Sin prueba entre dos máquinas |
| Amigos y chat privado | `VSC#` (WPF) | Código de amigo, solicitudes, lista local, ventana de conversación privada | Implementado y validado en el mismo selftest (24/24). Sin prueba entre dos máquinas |
| Control de avatar y foco de teclado | `VSC#` + Godot | Control desde el arranque, liberación al perder foco, recuperación al volver, reenvío de teclado y resaltado del chat | Implementado y validado en headless (35/35). Sin prueba E2E del foco en el visor embebido |
| Explorador y registro de isla | Godot | Botones «Explorador de islas» y «Registra tu isla», propiedad persistente por UUID | Implementado y validado en headless (23/23). Sin prueba real de dos instancias |
| Edición de terreno | Godot | Horneado por isla, pincel de 4 herramientas, normales, colisión trimesh, formato `WVPT` | Implementado y validado en headless (85/85) y con capturas visuales (9/9). Sin prueba real de dos máquinas |
| Construcción de prims | Godot | 5 primitivas, rezado, selección, transformación, color, duplicado, borrado, red y persistencia | Implementado y validado en headless (85/85) y con capturas visuales (9/9). Sin prueba real de dos máquinas |
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

### 3.3 Control de avatar y foco de teclado

- Desde la 2.5.8 el avatar responde a las flechas y a WASD **desde el arranque**: `control_avatar` vale `true` por defecto en los tres controladores (`userbase.gd`, `userbaseh_1.gd`, `AVMJ1Ch3D.gd`). La 2.5.7 exigía un clic previo, lo que dejaba al personaje inmóvil hasta que el jugador lo seleccionaba.
- El control se suelta solo al perder el foco (abrir el chat, pulsar micrófono/cámara, cambiar de ventana) y mientras `construccion_activa` está marcado. Al recuperar el foco se devuelve el control **sin otro clic**, salvo que el modo construcción siga activo.
- Un clic izquierdo sobre el cuerpo sigue lanzando un rayo desde la cámara y devuelve el control; un clic fuera ya **no** lo quita.
- En WPF, [`GodotHwndHost.cs`](VSC%23/GodotHwndHost.cs) devuelve el teclado a Godot con `WM_PARENTNOTIFY` y no reenvía teclas mientras se escribe en un `TextBox`.
- El cuadro de texto del chat se resalta con borde turquesa al recibir el foco.

**Validación:** [`tools/probar_control_clic.gd`](MTBGT/WoldVirtualP2P3D/tools/probar_control_clic.gd) supera **35/35** comprobaciones en headless sobre `userbaseh1`, `AVMJ1Ch3D` y la cápsula. **No** se ha validado el foco real dentro del visor embebido con el túnel activo.

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
- En modo construcción se marca `construccion_activa` en el avatar, se pone `control_avatar = false` y se liberan las acciones `ui_*`; al salir se devuelve `control_avatar = true`. Los tres controladores de avatar (`userbase.gd`, `userbaseh_1.gd`, `AVMJ1Ch3D.gd`) ignoran el clic de selección mientras el modo está activo.
- **Humo del mundo:** al arrancar el mundo completo se observó `Generando isla 0 para el jugador 1` seguido de `[Construccion] Isla 0 preparada: 10920 vértices`, sin errores de construcción.

---

## 4. Validación ejecutada (2026-10-26)

| Comprobación | Comando | Resultado |
|---|---|---|
| Compilación del visor | `dotnet build VSC#/Visor3D.csproj -p:SkipGodotAssets=true -c Debug` | **0 errores, 0 avisos** (1,16 s incremental) |
| Chat, amigos y proxy | `DMWoldVirtualp2pCNXv2.5.6.exe --chat-selftest` | **24/24 OK, 0 fallos**; micrófonos=1, webcams=1; mismo binario publicado |
| Terreno y prims | `Godot --headless --path . --script res://tools/probar_construccion.gd` | **85 OK, 0 fallos**; pincel 6,75 ms, colisión 19,29 ms, blob 43 698 → 17 388 B |
| Control de avatar | `Godot --headless --path . --script res://tools/probar_control_clic.gd` | **35/35 OK, 0 fallos** |
| Registro de islas | `Godot --headless --path . --script res://tools/probar_registro_islas.gd` | **23/23 OK, 0 fallos** |
| Escena de construcción | `Godot --headless --path . --script res://tools/sonda_escena_construccion.gd` | `Constructor=true`, script `res://gdscrip/Construccion.gd`, **OK** |
| Humo del mundo | Arranque completo de `ISLA3Dblock.tscn` | Isla 0 registrada con 10 920 vértices, sin errores de construcción |
| Prueba de arranque del binario | `DMWoldVirtualp2pCNXv2.5.6.exe --startup-selftest` | **11/11 OK, exit 0**; PCK extraído = embebido; motor headless isla+WS 8911 sin `ERROR` |
| Descarga del portal | `GET http://127.0.0.1:3030/descargar` con el visor abierto | **200**, `Content-Length: 788176767`, `filename="DMWoldVirtualp2pCNXv2.5.6.exe"` |
| Asset publicado | `gh api repos/…/releases/tags/v2.5.6` | digest `sha256:b028d5…7633` = SHA-256 local |
| Compilación 2.5.7 | `dotnet publish Visor3D.csproj -c Release -r win-x64 --self-contained true -o E:/out_v257` | **0 errores, 0 avisos**; exe de 788 180 863 B |
| Chat con el binario 2.5.7 | `DMWoldVirtualp2pCNXv2.5.7.exe --chat-selftest` | **24/24 OK, 0 fallos**, exit 0 |
| Arranque del binario 2.5.7 | `DMWoldVirtualp2pCNXv2.5.7.exe --startup-selftest` | **11/11 OK, exit 0**; marcador `.extracted` = `2.5.7`; PCK extraído idéntico al embebido (`9a5e2a06…baf4f`) |
| Reinicio de cuenta | Arranque real de `DMWoldVirtualp2pCNXv2.5.7.exe` con la cuenta del 16:39 | Archivo en `respaldo_cuenta/20261026-170512`; `credentials.json`, `pc_sello.json`, `registro.cfg` y `p2p_session.json` ya no están en su sitio; marcador `reset_cuenta.txt` = `2.5.7` |
| Portal con la 2.5.7 | `GET /`, `/api/info?token=…` y `/descargar` con el visor abierto | Log: `release vigente → DMWoldVirtualp2pCNXv2.5.7.exe (751,7 MB)`; `/api/info` anuncia `2.5.7` y `751,7`; `/descargar` **200**, `Content-Length: 788180863`, `filename="DMWoldVirtualp2pCNXv2.5.7.exe"` |
| Asset 2.5.7 publicado | `gh api repos/…/releases/tags/v2.5.7` | digest `sha256:d21a1fab…e9fbe` = SHA-256 local; `release.json` `c1b85344…59ce` y `SHA256SUMS` `f575b7a0…376b` también coinciden; tag → commit `154a3a5` |

**No ejecutado (y por tanto no acreditado):**

- Sesión real de dos máquinas con construcción, chat, voz y webcam a través del túnel.
- Latencia, pérdida de paquetes y reconexión del túnel HTTP.
- Interacción visual completa en el visor WPF embebido (foco, clic y resaltado).
- OTA de punta a punta 2.5.7 → 2.5.8 en un equipo con la versión anterior.
- Prueba de migración de anfitrión con permisos de construcción y chat.

---

## 5. Pendientes priorizados

### P0 — Antes de considerar la función terminada

1. **Prueba de dos máquinas para construcción:** pincel, rezado, permisos, guardado, recarga y migración de anfitrión.
2. **Prueba de dos máquinas para chat:** texto, voz, webcam, amigos, privados y reconexión tras migración.
3. **Prueba E2E del visor embebido:** flechas sin clic, foco del chat, recuperación al volver y resaltado.
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
| [`Seguridad/Seguridad_sesion_unica/ReinicioCuenta.cs`](VSC%23/Seguridad/Seguridad_sesion_unica/ReinicioCuenta.cs) | Nuevo | Reinicio único por versión de la base de usuarios local, con archivo en `respaldo_cuenta\`. |
| [`App.xaml.cs`](VSC%23/App.xaml.cs) | Modificado | Llama a `ReinicioCuenta` antes de WebNodo y del extractor. |
| [`README.md`](VSC%23/README.md) | Modificado | Secciones 7, 8 y 9 (chat, clic y amigos). |

---

## 8. Cómo usarlo

### Construcción (Godot)

1. Entrar en el mundo y pulsar <kbd>B</kbd> o el botón **«Construcción (B)»**.
2. Elegir herramienta en el panel: Seleccionar, Subir, Bajar, Suavizar o Aplanar.
3. Arrastrar con el botón izquierdo sobre el terreno de la propia isla para esculpir.
4. Con **Seleccionar**, hacer clic en una prim; después mover, rotar, escalar, duplicar o borrar.
5. Elegir tipo y color en el panel y pulsar **Rezar** para crear una prim nueva.
6. Salir con <kbd>B</kbd> o <kbd>Esc</kbd>. El avatar recupera el control y camina con las flechas o WASD sin otro clic.

> El terreno y las prims solo se pueden editar en la isla propia. En islas ajenas el panel muestra el estado en tono de aviso y rechaza la edición.

### Pruebas

```bash
# C# (desde src/)
E:/Program\ Files/dotnet/dotnet.exe build "VSC#/Visor3D.csproj" -p:SkipGodotAssets=true -c Debug

# Selftest del chat (el ejecutable compilado)
"VSC#/bin/Debug/net8.0-windows/win-x64/DMWoldVirtualp2pCNXv2.5.8.exe" --chat-selftest

# Prueba de arranque previa a publicar
"VSC#/bin/Debug/net8.0-windows/win-x64/DMWoldVirtualp2pCNXv2.5.8.exe" --startup-selftest

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

## 10. Publicación v2.5.7 (2026-10-26)

La 2.5.6 no cambiaba lo que ve un equipo que ya tenía datos: seguía entrando con la
cuenta anterior y, si arrancaba un ejecutable viejo (`bin\Debug\...v2.5.5.exe`,
`bin\Release\...v2.5.5.exe` o `Lanzar.bat` con una build anterior), Godot usaba
`runtime\2.5.5\wvp3d.pck` y reaparecía el error de `Personalizacion.gd`. La 2.5.7 añade
el reinicio de la base de usuarios local y fuerza un `runtime\2.5.7\` propio.

| Dato | Valor |
|---|---|
| Release | [`v2.5.7`](https://github.com/Chicook/WoldVirtualP2P3D/releases/tag/v2.5.7), tag sobre el commit `154a3a5` |
| Asset | `DMWoldVirtualp2pCNXv2.5.7.exe` |
| Tamaño | 788 180 863 B (751,7 MiB) |
| SHA-256 local | `d21a1fab652711cc154a3b49ad808bfd284125f9630d0e1564cc2cdc857e9fbe` |
| PCK embebido | Sin cambios: 537 803 740 B (512,9 MiB), SHA-256 `9a5e2a06662e937dd5f89ca7e240a858fe96fb0acd521009a6c1e7cd6d0baf4f` |
| `release.json` | version `2.5.7`, tag `v2.5.7`, exe y URL del asset nuevo, `size_mb` 751.7; SHA-256 `c1b85344…59ce` |
| `SHA256SUMS` | exe + `release.json`; SHA-256 `f575b7a0…376b` |
| Verificación por API | Los tres `digest` de `gh api …/releases/tags/v2.5.7` coinciden con los locales |
| Prueba de arranque | 11/11 OK, exit 0 |
| Chat | 24/24 OK, exit 0 |
| Portal | `release vigente → DMWoldVirtualp2pCNXv2.5.7.exe (751,7 MB)`; `/descargar` 200 con 788 180 863 B |

### 10.1 Qué hace el reinicio de cuenta

`ReinicioCuenta.EjecutarSiProcede()` se llama en `App.OnStartup`, después de las pruebas
automáticas y antes de WebNodo y del extractor. Se ejecuta **una vez por versión**: el
marcador `%LOCALAPPDATA%\WoldVirtualP2P3D\reset_cuenta.txt` guarda la versión que ya lo hizo.

Archiva —no borra— en `%LOCALAPPDATA%\WoldVirtualP2P3D\respaldo_cuenta\<fecha>\`:

- **Críticos** (sin ellos el PC deja de estar registrado): `credentials.json`,
  `user\user_profile.json`, `user\llave_acceso.json`, `Seguridad\pc_sello.json`.
- **Resto de `user\`:** `semilla_wallet.json`, `hardware_id.json`, `friends_*.json`,
  `p2p_session.json`.
- **Godot:** `registro.cfg`, `p2p_session.json`, `session_host.txt`, `islas_registro.cfg`,
  `isla_propiedad.cfg`, `avatar_hash.json`, `avatar.sha256`, `sesion_islas_snapshot.json`
  y la carpeta `carrusel\`.
- Escribe `reset_flag.txt` en el `user://` de Godot como red de seguridad para que
  `Boot.gd` borre un `registro.cfg` que se hubiera quedado bloqueado.

Si algún fichero crítico no se puede mover, **no escribe el marcador**: el siguiente
arranque reintenta y el aviso queda en `logs\visor-<fecha>.log` con el prefijo `[cuenta]`.
No toca `runtime\`, `logs\`, `cloudflared.exe`, `internal_storage\` ni el PCK.

Efecto visible: la pantalla de bienvenida vuelve a ofrecer **«Crear cuenta»**
(`MainWindow.MostrarPantallaBienvenida` sólo la oculta si existen perfil y llave) y el motor
arranca en carrusel + registro de nick. La semilla de la wallet anterior queda en el
respaldo; la cuenta nueva genera otra.

### 10.2 Por qué es una versión nueva y no un reemplazo de la 2.5.6

Recompilar bajo la etiqueta `v2.5.6` habría dejado a los equipos ya actualizados con el
`runtime\2.5.6\` extraído antes (R1), y borrar o mover un tag publicado está prohibido
(R4, §8.2). La 2.5.7 es un tag nuevo, el actualizador elige la versión mayor del nombre
del asset y el primer arranque extrae `runtime\2.5.7\`.

### 10.3 Diagnóstico del informe «siguen los mismos errores»

Los logs del 2026-10-26 lo sitúan en un ejecutable viejo, no en el binario publicado:

- `logs\godot2026-10-26T16.40.54.log` contiene el error de `Personalizacion.gd:841/842`,
  **no** muestra `[OptimizadorAvatares]` y su PCK es el de la 2.5.5 (537 728 852 B).
- `logs\godot2026-10-26T16.44.33.log` arranca con el PCK nuevo, registra
  `OptimizadorAvatares`, prepara la isla 0 con 10 920 vértices y **no tiene ningún `ERROR`**.
- `runtime\2.5.6\wvp3d.pck` (16:24) es idéntico al embebido en la 2.5.6
  (`9a5e2a06…baf4f`), así que el binario publicado sí llevaba la corrección.
- `bin\Debug\...DMWoldVirtualp2pCNXv2.5.5.exe` (15:28) y
  `bin\Release\...DMWoldVirtualp2pCNXv2.5.5.exe` (14:59) siguen existiendo, y
  `Lanzar.bat` compila y ejecuta la configuración **Debug**. Cualquiera de los dos
  resuelve `runtime\2.5.5\`.

Para arrancar la versión nueva hay que ejecutar el `.exe` publicado (o el de
`E:\out_v257\`), no `Lanzar.bat` ni un `bin\...v2.5.5.exe`.

### 10.4 Límite no acreditado

No se ejecutó el OTA 2.5.6 → 2.5.7 en un equipo distinto ni una sesión de dos máquinas.
El reinicio de cuenta sí se ejecutó en este equipo y su resultado quedó archivado.

---

## 11. Publicación v2.5.8 (2026-10-26)

La 2.5.6 introdujo el control de avatar por clic para que el teclado del chat no
moviera al personaje, pero el avatar arrancaba bloqueado: el usuario lo percibió como
«los avatares no andan en esta actualización». La 2.5.8 devuelve el control desde el
arranque, lo suelta solo al perder el foco o entrar en construcción y lo recupera sin
otro clic. El chat, los amigos, el reinicio de cuenta de la 2.5.7 y la construcción no
cambian de comportamiento.

| Dato | Valor |
|---|---|
| Release | [`v2.5.8`](https://github.com/Chicook/WoldVirtualP2P3D/releases/tag/v2.5.8), tag sobre el commit de publicación de esta rama |
| Asset | `DMWoldVirtualp2pCNXv2.5.8.exe` |
| Tamaño | 788.180.863 B (751,7 MiB) |
| SHA-256 local | `44dea928130f65977f71746a7579d9f2255edb7271b4e85f219af09ee3b1f609` |
| PCK embebido | 537.803.820 B (512,9 MiB), SHA-256 `6456b82b81fb5daa93bc1537b82b4c4c4fbcf1ccdf123e01b3b2ecc0cd0ca2ec`; exportado del árbol de este commit el 2026-10-26 17:27 |
| `release.json` | version `2.5.8`, tag `v2.5.8`, exe y URL del asset nuevo, `size_mb` 751.7; SHA-256 `f33f6c07a655fa5a7695cf7ab0413d00247d9df836dfabcd9600e50be5353747` |
| `SHA256SUMS` | exe + `release.json`; SHA-256 `ce25ea61c1a0a021a0fae0f2eec630d624117b13b2ce8bb20ec686a4e04c5cb3` |
| Prueba de arranque | **11/11 OK**, exit 0; marcador `.extracted` = `2.5.8`; PCK extraído idéntico al embebido |
| Chat | **24/24 OK**, exit 0 |
| Control de avatar | **35/35 OK**, exit 0 |
| Construcción | **85/85 OK**, exit 0 |
| Prueba visual | **9/9 OK** y 10 capturas de terreno y prims; herramienta local no versionada para no desalinear el PCK |

### 11.1 Qué cambia en el PCK y en el visor

- **Godot:** `control_avatar := true` en `userbase.gd`, `userbaseh_1.gd` y
  `AVMJ1Ch3D.gd`; `NOTIFICATION_APPLICATION_FOCUS_IN` recupera el control salvo con
  `construccion_activa`; un clic fuera del cuerpo ya no lo quita;
  `Construccion._bloquear_avatar()` devuelve el control al salir.
- **Pruebas:** `probar_control_clic.gd` pasa de 25 a **35** comprobaciones y
  `probar_construccion.gd` de 84 a **85**.
- **C#:** solo cambian `<Version>`, `<AssemblyVersion>`, `<FileVersion>`,
  `<AssemblyName>` y la descripción del `.csproj`, más `ExeNameFallback` y
  `ExeUrlFallback` de `WebNodoService`.
- **PCK:** la 2.5.7 reutilizó el PCK de la 2.5.6 (`9a5e2a06…baf4f`); la 2.5.8 lleva uno
  nuevo (`6456b82b…0ca2ec`) porque los controladores de avatar han cambiado. Se exportó a
  las 17:27:11; el único cambio posterior del árbol es una comprobación añadida a
  `tools/probar_construccion.gd` (17:27:32), que no forma parte del mundo empaquetado.

### 11.2 Por qué es una versión nueva y no un reemplazo

Recompilar bajo el tag `v2.5.7` habría dejado a los equipos ya actualizados con
`runtime\2.5.7\` extraído antes (R1), y mover o renombrar un tag publicado está
prohibido (R4, §8.2). La 2.5.8 es un tag nuevo: el actualizador elige la versión mayor
del nombre del asset y el primer arranque extrae `runtime\2.5.8\`.

### 11.3 Límite no acreditado

No se ejecutó el OTA 2.5.7 → 2.5.8 en un equipo distinto ni una sesión de dos máquinas
con chat o construcción. La verificación de los tres `digest` con `gh api` y la prueba
del portal con el binario en ejecución se anotan en el commit de documentación posterior
a la publicación.

---

## 12. Reglas para continuar esta fase

1. **No publicar** binario, PCK ni OTA sin completar el checklist de [`REGLAS_DE_ACTUALIZACION.md`](../../../../REGLAS_DE_ACTUALIZACION.md) §7.
2. **No afirmar** que existe túnel SSH: el sistema usa túneles HTTP/WebSocket. Si se quiere SSH, es trabajo pendiente con diseño propio.
3. **No dar por probada** la red de construcción ni el chat entre dos máquinas hasta ejecutar esa prueba y conservar el log.
4. **Commitear solo fuentes** (C#, GDScript, XAML, Markdown, configuración); nunca `.exe`, `.dll`, `.zip`, `.pck` ni datos de usuario.
5. **No borrar ni realinear** ramas de otros agentes; hay sesiones concurrentes sobre el mismo repositorio.
6. **Mantener la documentación con evidencia:** código y logs mandan; las etiquetas de estado deben distinguir «implementado», «validado en headless» y «probado en red real».

---

## 13. Referencias

- [`README_desarrollo_20261026.md`](README_desarrollo_20261026.md) — primeros 7 bloques de la jornada.
- [`README_DESARROLLO.md`](README_DESARROLLO.md) — auditoría amplia del estado de `src/`.
- [`MTBGT/WoldVirtualP2P3D/README.md`](MTBGT/WoldVirtualP2P3D/README.md) — arquitectura del mundo Godot, sección 10 de construcción.
- [`VSC#/README.md`](VSC%23/README.md) — arquitectura del visor, secciones 7 a 9 de chat, clic y amigos.
- [`HOJA_DE_RUTA.md`](HOJA_DE_RUTA.md) — hoja de ruta general del proyecto.

---

*Documento generado el 2026-10-26 a partir del código y de las ejecuciones de prueba de la sesión. Binarios publicados el mismo día: 2.5.6 (ver §9), 2.5.7 (ver §10) y 2.5.8 (ver §11).*
