# Desarrollo 2.6.1 — invitación con token, instancia única, islas sin dueño y webcams en el chat

Trabajo hecho sobre el árbol del 2026-10-27/28 (`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_52bf0d80`),
rama `DevQoderIA`. **Estado de la release: publicada como v2.6.1 el 2026-10-28** (tag sobre
`e98b4f4`, marcada *Latest*; asset `DMWoldVirtualP2P3Dv2.6.1.exe`, 788.230.009 B, SHA-256
`86d9cb6e1b8db4d21330d85b22d3e34168f591044ebd073ca8adb7be430a88fc`; `release.json` y
`SHA256SUMS` verificados por API). Sustituye a la v2.6.0 como release vigente.

> **Nota (2026-10-28):** la **2.6.2** corrige la vista local de la webcam de esta franja (el tile
> XAML se perdía al limpiar `PanelVideos`); ver
> [`README_desarrollo_20261028_2_6_2.md`](README_desarrollo_20261028_2_6_2.md).

---

## Cambios

| Área | Cambio | Estado |
|---|---|---|
| Nombre y versión | `AssemblyName` = `DMWoldVirtualP2P3Dv2.6.1`; `Version`/`AssemblyVersion`/`FileVersion` = `2.6.1`/`2.6.1.0` (`VSC#/Visor3D.csproj:24,27-29`) | Implementado |
| Acceso por invitación | El WebSocket del WebNodo exige `?invitacion=<token de sesión>` (32 hex en minúsculas) para el motor y para `/chat`; el token viaja en el enlace, en `--peer-url` y en `p2p_session.json` | Implementado; la LAN directa y el relay no pasan por esa puerta (limitación abajo) |
| Instancia única | La segunda ejecución enfoca la ventana ya abierta en lugar de mostrar otro login; `--reset-cuenta` con el visor abierto avisa y no reinicia | Implementado y probado en este PC |
| Islas sin dueño | Al desconectarse un jugador se retira su isla en todos los peers, se libera su índice y se conserva el registro del dueño para su vuelta; sin usuarios conectados no se instancia ninguna isla ajena | Implementado; prueba headless 7/7 |
| Chat con webcams | Franja horizontal de vídeos **dentro del marco del chat**, en la fila superior: vista local + un tile por emisor, con desplazamiento horizontal; se oculta sola si no hay cámara | Implementado; sin verificación visual con una sesión autenticada real |
| Animaciones de avatares | 24 avatares del carrusel y 16 GLB de `avtrnCRS` revisados con sus clips | Implementado (24/24 y 16/16) |
| PCK | Reexportado del árbol actual y copiado a `VSC#/wvp3d.pck` | Implementado |

---

## 1. El enlace de invitación ya no basta por sí solo

El anfitrión genera un **token de sesión** al arrancar (`VSC#/Services/WebNodoService.cs:132`,
`TokenInvitacion`, `Convert.ToHexString(RandomNumberGenerator.GetBytes(16))`). El proxy del WebNodo
lo exige en **todas** las peticiones WebSocket, antes de enrutar al motor o al relay del chat
(`WebNodoService.cs:595-601`): sin token, el handshake responde `403 Invitación no válida`.

El token se propaga por donde viaja la sesión:

- Enlace de invitación: `EnlaceInvitacion` añade `?host=<raíz>` si hace falta y `?invitacion=<token>`
  (`VSC#/MainWindow.xaml.cs:1053`).
- Arranque del motor: `UrlTunelConInvitacion` lo incorpora a `--peer-url` (`MainWindow.xaml.cs:1073,825`).
- Chat: `ResolverEndpointChat` añade `?invitacion=` a `wss://<anfitrión>/chat` (`MainWindow.xaml.cs:1521`).
- Sesión persistida: `p2p_session.json` incluye `invitacion` (`MainWindow.xaml.cs:1247`).
- Godot: `Red.resolver_url_ws` sólo lo añade a URLs `wss://`; la LAN directa `ws://<ip>:8911` queda
  intacta (`MTBGT/WoldVirtualP2P3D/gdscrip/Red.gd:153-168`). `ChunkManager.gd:60,317,1160` y
  `Sonda.gd:32` leen el token del objetivo y lo aplican también en la migración de anfitrión.

El invitado que entra por enlace lo **adopta** (`MainWindow.xaml.cs:1037`) y puede volver a
compartirlo; el portal conserva el enlace cuando se abrió desde una invitación
(`WebNodoService.cs:260`). Una URL de portal abierta en limpio no expone el token a propósito.

**Limitación declarada:** el token protege la ruta pública (túnel y proxy `/chat`). Una conexión
LAN directa a `ws://<ip>:8911` o al relay `:8920` no atraviesa el WebNodo y no pasa por la puerta.
No es un fallo del control: esas rutas no son la vía de invitación.

## 2. Una sola ventana con sesión

`VSC#/Services/InstanciaUnica.cs` toma un mutex con nombre por proceso
(`Local\WoldVirtualP2P3D.<nombre>`, `InstanciaUnica.cs:43-64`) y, si ya está tomado, trae al frente la
ventana existente: 30 intentos cada 200 ms esperando el `MainWindowHandle`, `ShowWindow(SW_RESTORE)`,
adjunción de entrada al hilo en primer plano (`AttachThreadInput`), `BringWindowToTop` y
`SetForegroundWindow` (`InstanciaUnica.cs:67-108`). `App.xaml.cs:43-57` sale con código 0 tras
enfocar; con `--reset-cuenta` muestra un aviso y no reinicia la cuenta.

## 3. Sin dueño presente no queda isla

En la desconexión de un peer, el anfitrión retira su isla en todos los peers con
`_despawn_island` (`ChunkManager.gd:921-938`, invocado desde `ChunkManager.gd:700-712`), libera su
índice para reutilizarlo y **conserva** `island_owners` / `_islas_por_uuid` para que el mismo UUID
recupere su isla al volver (`_adoptar_isla`, `_drop_fake_key`). Las plazas de avatar de IDs muertos
se liberan con `_limpiar_turnos_obsoletos` (`ChunkManager.gd:214-224`).

Una isla sólo se instancia por `_register_player`/`_spawn_island_for_player` para jugadores
conectados; cargar `user://islas_registro.cfg` sólo rellena mapas de dueño. Por eso, al arrancar sin
nadie más conectado, el mundo contiene únicamente la isla del jugador local.

## 4. Chat: webcams dentro del marco

`VSC#/MainWindow.xaml:482-500` añade `MarcoVideosChat` en la fila superior del panel de chat, con un
`ScrollViewer` horizontal y `PanelVideos`; `MarcoCamLocal` muestra la vista previa local (160×90).
`ActualizarFranjaVideos` (`MainWindow.xaml.cs:2783-2797`) decide la visibilidad de la franja según
haya o no vídeo, y `OcultarTileVideo`/`QuitarTileVideo` (`MainWindow.xaml.cs:2799-2815`) la refrescan
cuando una cámara se detiene o el emisor se va.

---

## Evidencia

| Prueba | Comando | Resultado |
|---|---|---|
| Token de invitación en Godot | `godot --headless --path . --script res://tools/probar_red_invitacion.gd` | **7/7 OK, exit 0** (`== red/invitación, fallos=0 ==`) |
| Islas sin dueño | `godot --headless --path . --script res://tools/probar_islas_fantasma.gd` | **7/7 OK, exit 0** (sin usuarios no hay islas; retirada, índice libre, registro conservado) |
| Animaciones del carrusel | `godot --headless --path . --script res://tools/validar_avatares.gd` | **24 avatares, 0 con fallo** (65–67 huesos, 5–7 clips) |
| Animaciones de los GLB | `godot --headless --path . --script res://tools/validar_anim_glb.gd` | **16 modelos, 0 con fallo** |
| Chat (incluye rechazo sin token) | `DMWoldVirtualP2P3Dv2.6.1.exe --chat-selftest` | **25 comprobaciones, 0 fallos**, exit 0 |
| Red | `DMWoldVirtualP2P3Dv2.6.1.exe --red-selftest` | **7 líneas, 0 fallos**, exit 0 |
| Arranque, extracción, portal y motor | `DMWoldVirtualP2P3Dv2.6.1.exe --startup-selftest` con `APPDATA` aislado y un `registro.cfg` de prueba | **15/15 OK**, exit 0; `.extracted` = `2.6.1`; motor: isla 0 y WebSocket 8911, 0 `ERROR` |
| Instancia única | Ver §2 del procedimiento: visor minimizado con el foco en otra aplicación | La segunda ejecución sale con **código 0 en ~1,05 s**; queda **un solo proceso**; la ventana se restaura y el handle en primer plano **coincide** con el de la primera instancia |
| PCK | `godot --headless --path . --import` + `--export-pack "Windows Desktop" wvp3d.pck` | **537.836.524 B**, SHA-256 `9d5c15e7322cfce3d450e65341a23f6e82d01a008b760245a3e10e0d7a69ac94`, exportado el 2026-10-28 00:12 y copiado a `VSC#/wvp3d.pck` (mismo hash) |
| PCK embebido | `sha256sum` del PCK extraído en `runtime\2.6.1\` | Idéntico al PCK exportado (mismo SHA-256) |
| Compilación | `dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -o E:/out_v261` con el .NET de `E:` | **0 errores, 0 avisos** (sólo el aviso NETSDK1057 de SDK preliminar); exe **788.230.009 B**, SHA-256 `86d9cb6e1b8db4d21330d85b22d3e34168f591044ebd073ca8adb7be430a88fc` |
| Extracción en disco | Medición de `%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.6.1\` | **718.695.417 B (≈685,4 MiB)**; `.extracted` = `2.6.1`; PCK extraído con el mismo SHA-256 que el exportado |
| Publicación | `gh release create v2.6.1 --target e98b4f4 --latest` + `gh api …/releases/tags/v2.6.1` | tag `v2.6.1`, `draft=false`, `prerelease=false`, *Latest*; digests por API iguales a los locales (`86d9cb6e…a88fc` exe, `54a8dd8d…5d8cf4` `release.json`); URL de descarga **200** con `Content-Length` 788.230.009 |

### Sensibilidad de `--startup-selftest` al perfil de Godot (comprobada)

La primera pasada de la 2.6.1 dio **14/15**: falló «Motor arranca desde el PCK» (`exit=0 isla=False
red=False`) porque no existía `user://registro.cfg` y el motor se quedaba en el carrusel esperando la
sonda, sin llegar a instanciar la isla ni abrir el 8911. **No es una regresión del PCK**: el PCK de la
2.6.0, ejecutado en el mismo equipo y estado, produce exactamente el mismo recorte del log. Con un
`APPDATA` aislado y un perfil de prueba, la misma ejecución pasa **15/15**. La prueba debería aislar
ese estado en lugar de depender del perfil del equipo (deuda, ver §9 de `REGLAS_DE_ACTUALIZACION.md`).

---

## Deuda abierta

- **Publicación de la v2.6.1**: resuelta el 2026-10-28 (tag `v2.6.1` sobre `e98b4f4`, *Latest*,
  assets verificados). Queda por observar el portal de la 2.6.1 anunciando por `/api/info` el asset
  ya publicado y el OTA real desde GitHub.
- **Prueba visual del chat** con una sesión autenticada y dos cámaras; la suite headless no valida
  disposición de la interfaz.
- **Prueba real entre dos equipos** del enlace con token (túnel y `/chat`) y de la instancia única
  fuera de este PC.
- **OTA real** desde GitHub y re-extracción del runtime en un equipo con la versión anterior (§7 de
  las reglas).
- **El aislamiento de `--startup-selftest`** sigue pendiente: depende de `p2p_session.json` y de
  `registro.cfg`.

*La 2.6.1 está compilada, probada y publicada como release v2.6.1 (2026-10-28). Las pruebas
pendientes son las de dos equipos, la visual del chat y el OTA real; no bloquean la publicación.*
