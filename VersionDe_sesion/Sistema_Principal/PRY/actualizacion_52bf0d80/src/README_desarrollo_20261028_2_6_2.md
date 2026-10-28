# Desarrollo 2.6.2 — la vista local de la webcam vuelve a la franja del chat

Trabajo sobre el árbol del 2026-10-28
(`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_52bf0d80`), rama `DevQoderIA`.
**Estado de la release: publicada como v2.6.2 el 2026-10-28.** Tag `v2.6.2` sobre el commit
`d14e3b5` de `DevQoderIA`, marcada *Latest*, con `exe` + `release.json` + `SHA256SUMS` verificados
por API. La v2.6.1 sigue publicada como release anterior.

---

## Causa del fallo

`DetenerChatSesion()` limpiaba la franja con `PanelVideos.Children.Clear()`. El tile local
`MarcoCamLocal` está declarado **dentro** de `PanelVideos` en el XAML
(`VSC#/MainWindow.xaml:491`), así que ese `Clear()` lo expulsaba del árbol visual. Como
`DetenerChatSesion()` se ejecuta al principio de cada `IniciarChatSesion()`
(`VSC#/MainWindow.xaml.cs:1372`), el tile local desaparecía al entrar y ya no volvía:

- `AlternarCamaraChat()` ponía `MarcoCamLocal.Visibility = Visible` y la franja se mostraba
  (`MarcoVideosChat`), pero el `Image` ya no colgaba del panel → **franja visible sin imagen**.
- Los tiles remotos sí se añadían después del `Clear()`, por eso el fallo se notaba sobre todo en
  la vista local.

## Cambios

| Área | Cambio | Estado |
|---|---|---|
| Limpieza de la franja | `LimpiarTilesVideo(panel, preservar)` retira solo los tiles remotos y conserva el tile local (`MainWindow.xaml.cs:2810`); `DetenerChatSesion` la usa en `:1470` | Implementado |
| Encendido de cámara | Si el tile local no está en el panel se reinserta antes de mostrarlo (`MainWindow.xaml.cs:2687`), de modo que la vista se recupera aunque otra ruta lo hubiera quitado | Implementado |
| Regresión | `--chat-selftest` comprueba que la limpieza conserva la vista local (`Chat/ChatSelfTest.cs:38`) | Implementado (26/26) |
| Portal | El fallback empotrado anuncia ya `DMWoldVirtualP2P3Dv2.6.2.exe` y su URL (`Services/WebNodoService.cs:64-66`); antes seguía en 2.6.0 | Implementado |
| Versión | `AssemblyName` = `DMWoldVirtualP2P3Dv2.6.2`; `Version`/`AssemblyVersion`/`FileVersion` = `2.6.2`/`2.6.2.0` (`VSC#/Visor3D.csproj:24,27-29`) | Implementado |

**PCK:** no hay cambios en el proyecto Godot. Se reutiliza el PCK de la 2.6.1
(`537.836.524 B`, SHA-256 `9d5c15e7322cfce3d450e65341a23f6e82d01a008b760245a3e10e0d7a69ac94`),
verificado idéntico tras extraer el runtime de la 2.6.2. La versión nueva fuerza la re-extracción por
R1 aunque el mundo sea el mismo.

---

## Evidencia

| Prueba | Comando | Resultado |
|---|---|---|
| Chat y regresión de la franja | `DMWoldVirtualP2P3Dv2.6.2.exe --chat-selftest` | **26 comprobaciones, 0 fallos**, exit 0; incluye «la limpieza de tiles conserva la vista local del XAML»; `webcams=1` detectada |
| Red y portal | `DMWoldVirtualP2P3Dv2.6.2.exe --red-selftest` | **7 líneas, 0 fallos**, exit 0 |
| Arranque, extracción y motor | `DMWoldVirtualP2P3Dv2.6.2.exe --startup-selftest` con `APPDATA` aislado y `registro.cfg` de prueba | **15/15 OK**, exit 0; `runtime\2.6.2\`, `.extracted` = `2.6.2`; isla y WebSocket 8911; 0 `ERROR` |
| Portal | En la misma pasada, `GET /api/info` | `{"disponible":true,"nombre":"DMWoldVirtualP2P3Dv2.6.2.exe","tamano_mb":"751,8",…}` |
| PCK | `sha256sum` del PCK extraído y del fuente | Idénticos (`9d5c15e7…a69ac94`) |
| Compilación | `dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -o E:/out_v262` | **0 errores, 0 avisos** (solo NETSDK1057 de SDK preliminar); exe **788.230.009 B**, SHA-256 `bb176468c3d4d890f0f53742300cf32361844fbd64b2c2e0c8b9774e54647b6c` |
| `release.json` | 215 B | SHA-256 `9966950c21d5cf2f24f06132109097d564fa87fee3c9c379cef61541caea8ff7` |
| `SHA256SUMS` | 174 B | SHA-256 `320f74a30f86bcaa1c5649b4a3225e0860be30022fbd158b6a1760ca7db85fa9` |
| Extracción en disco | `%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.6.2\` | **718.695.417 B (≈685,4 MiB)** |
| Publicación | `gh release create v2.6.2` sobre `d14e3b5`, tres assets en el mismo gesto | `draft=false`, `prerelease=false`, *Latest* |
| Digests publicados | `gh api repos/…/releases/tags/v2.6.2 --jq '.assets[]'` | exe `bb176468…47b6c` (788.230.009 B), `release.json` `9966950c…`, `SHA256SUMS` `320f74a3…`; los tres coinciden con los locales |
| Descarga | `HEAD` de `…/download/v2.6.2/DMWoldVirtualP2P3Dv2.6.2.exe` | `200`, `Content-Length: 788230009`, `application/octet-stream` |

---

## Deuda abierta

- **Prueba visual** de la franja con una sesión autenticada y la cámara encendida: la regresión cubre
  la estructura del panel, no el render real de WPF.
- **Portal contra la release publicada**: `/api/info` se midió con el fallback local de la 2.6.2, no
  contra la release ya subida a GitHub.
- **Prueba entre dos equipos** de la webcam remota a través del túnel y del relay.
- **OTA real** desde GitHub y re-extracción del runtime en un equipo con la versión anterior.

*La 2.6.2 corrige la vista local de la webcam y mantiene todo lo de la 2.6.1; está publicada como
*Latest* desde el 2026-10-28.*
