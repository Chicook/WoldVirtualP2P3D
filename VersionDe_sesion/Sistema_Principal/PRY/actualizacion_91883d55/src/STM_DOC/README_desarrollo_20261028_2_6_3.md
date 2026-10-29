# Desarrollo 2.6.3 — reset automático al arrancar si el PC no tiene cuenta utilizable

Trabajo sobre el árbol del 2026-10-28
(`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_52bf0d80`), rama `DevQoderIA`.
**Estado de la release: publicada como v2.6.3 el 2026-10-28.** Tag `v2.6.3` sobre el commit
`94afc4a` de `DevQoderIA`, marcada *Latest*, con `exe` + `release.json` + `SHA256SUMS` verificados
por API. La v2.6.2 sigue publicada como release anterior.

---

## Causa del problema

`PerfilUsuario.TieneIdentidad` (`Seguridad/PerfilUsuario.cs:40`) consideraba registrado el PC con
que existiera **cualquiera** de estos restos: `user\user_profile.json`, `credentials.json` o el
sello `Seguridad\pc_sello.json`. Con esa señal:

- `MostrarPantallaBienvenida()` ocultaba «Crear cuenta» (`MainWindow.xaml.cs:482-483`).
- `OnCrearCuentaClicked()` bloqueaba el registro (`MainWindow.xaml.cs:522-532`).
- Pero el login exige usuario **y** `passwordHash` (`ValidarCredenciales`, `MainWindow.xaml.cs:2965`)
  y después el archivo «La Llave».

Un perfil truncado, una llave suelta, un sello de una instalación anterior o una carpeta de datos
copiada de otro PC dejaban el arranque sin salida: ni «Crear cuenta» ni forma de entrar. En el motor
pasaba lo mismo al revés: `Boot.gd` entraba directo a la isla si `user://registro.cfg` tenía avatar y
nick, aunque el visor no tuviera cuenta.

## Cambios

| Área | Cambio | Estado |
|---|---|---|
| Diagnóstico | `PerfilUsuario.Diagnosticar(out motivo, baseDir?)` clasifica el arranque en `SinIdentidad`, `Completa` (usuario + `passwordHash`, las dos credenciales que acepta el login) o `Incompleta` (restos sin acceso) (`Seguridad/PerfilUsuario.cs:9-121`) | Implementado |
| Arranque | `ArranqueCuenta.AsegurarCicloRegistro()` se ejecuta tras `MigrarSiProcede()` en `App.xaml.cs:83`: cuenta completa intacta; restos → `ReinicioCuenta.EjecutarSiProcede("auto-incompleta-…")`; sin identidad → sólo se archiva el estado del motor | Implementado |
| Archivo | `ReinicioCuenta` acepta `baseDir`/`godotDir` para pruebas y añade `LimpiarEstadoGodot(motivo, …)`, que archiva `registro.cfg`, sesión P2P, avatar y carrusel en `respaldo_cuenta\<fecha>-<motivo>` y escribe `reset_flag.txt` (`Seguridad/Seguridad_sesion_unica/ReinicioCuenta.cs:59-151`) | Implementado |
| Motor | `Boot.gd:46-54` ya borraba `registro.cfg` al ver `reset_flag.txt`; no se tocó el proyecto Godot | Sin cambios |
| Autoprueba | `--cuenta-selftest` sobre directorios temporales: 7 diagnósticos, archivo de restos, cuenta completa intacta y limpieza del motor (`Services/CuentaSelfTest.cs`) | Implementado (12/12) |
| Portal | El fallback empotrado anuncia `DMWoldVirtualP2P3Dv2.6.3.exe` y su URL (`Services/WebNodoService.cs:64-66`) | Implementado |
| Versión | `AssemblyName` = `DMWoldVirtualP2P3Dv2.6.3`; `Version`/`AssemblyVersion`/`FileVersion` = `2.6.3`/`2.6.3.0` (`VSC#/Visor3D.csproj:24,27-29`) | Implementado |

Decisiones de diseño:

- **No se toca una cuenta completa.** El diagnóstico exige usuario y hash, no la mera existencia del
  fichero; cualquier equipo capaz de iniciar sesión conserva su cuenta, su llave y su sello.
- **Se archiva, no se borra.** Todo va a `respaldo_cuenta\<fecha>` en `%LOCALAPPDATA%\WoldVirtualP2P3D`
  y el sello de cuenta única se mueve junto al resto, de modo que el PC queda libre para registrar.
- **Sin identidad no se escribe en el perfil local.** Sólo se archiva el estado antiguo del motor para
  que el carrusel y el registro de nick arranquen de cero; el perfil local queda como estaba (vacío).
- **Las pruebas nunca tocan el perfil real.** `Diagnosticar`, `EjecutarSiProcede` y
  `LimpiarEstadoGodot` aceptan rutas; la autoprueba usa `%TEMP%\wvp3d_cuenta_selftest_<guid>` y lo
  borra al terminar.

**PCK:** no hay cambios en el proyecto Godot. Se reutiliza el PCK de la 2.6.1/2.6.2
(`537.836.524 B`, SHA-256 `9d5c15e7322cfce3d450e65341a23f6e82d01a008b760245a3e10e0d7a69ac94`),
verificado idéntico tras extraer el runtime de la 2.6.3. La versión nueva fuerza la re-extracción por
R1 aunque el mundo sea el mismo.

---

## Evidencia

| Prueba | Comando | Resultado |
|---|---|---|
| Cuenta al arrancar | `DMWoldVirtualP2P3Dv2.6.3.exe --cuenta-selftest` | **12 comprobaciones, 0 fallos**, exit 0: 7 diagnósticos (vacío → `SinIdentidad`; llave o sello sueltos → `Incompleta`; credenciales sin hash → `Incompleta`; JSON corrupto → `Incompleta`; credenciales con hash → `Completa`; perfil con hash → `Completa`), restos archivados con ≥3 ficheros en `respaldo_cuenta`, `reset_flag.txt` escrito, cuenta completa intacta y motor limpio sólo sin cuenta |
| Chat y franja | `DMWoldVirtualP2P3Dv2.6.3.exe --chat-selftest` | **26 comprobaciones, 0 fallos**, exit 0; `micrófonos=1 webcams=1` |
| Red y portal | `DMWoldVirtualP2P3Dv2.6.3.exe --red-selftest` | **7 líneas, 0 fallos**, exit 0 |
| Arranque, extracción y motor | `DMWoldVirtualP2P3Dv2.6.3.exe --startup-selftest` con `WOLD_RUNTIME_DIR` y `APPDATA` aislados | **15/15 OK**, exit 0; `runtime\2.6.3\`, `.extracted` = `2.6.3`; motor `exit=0`, `isla=True`, `red=True`, `errores=False` con un perfil copiado al `APPDATA` de prueba. Sin `registro.cfg` el motor abre el carrusel y la misma pasada da 14/15 (falla sólo «Motor arranca desde el PCK»), igual que en las versiones anteriores |
| Portal | En la misma pasada, `GET /api/info` | `{"disponible":true,"nombre":"DMWoldVirtualP2P3Dv2.6.3.exe","tamano_mb":"—",…}` (el fallback local; el portal lo refresca contra GitHub al arrancar) |
| PCK | `sha256sum` del PCK fuente | `9d5c15e7…a69ac94`, idéntico al extraído por el runtime |
| Compilación | `dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -o E:/out_v263` | **0 errores, 0 avisos** (solo NETSDK1057 de SDK preliminar); exe **788.242.297 B**, SHA-256 `9794cdb4446285015b78859c9e90f1b0583a32b4a221c6f5b2934a3ef5b03e62` |
| `release.json` | 215 B | SHA-256 `16f113b144d717ae0f1996b514585e8dd356cede057c4ae6a3e7c22043fb1ee1` |
| `SHA256SUMS` | 174 B | SHA-256 `abb37c5a5fa9ff2e82f182f8e20f00248e0f7a0ed318875a5bfe8681e4168cdb` |
| Extracción en disco | `WOLD_RUNTIME_DIR` de prueba | **718.695.417 B (≈685,4 MiB)** |
| Publicación | `git tag v2.6.3` sobre `94afc4a`, `gh release create v2.6.3` con los tres assets | `draft=false`, `prerelease=false`, *Latest* |
| Digests publicados | `gh api repos/…/releases/tags/v2.6.3 --jq '.assets[]'` | exe `9794cdb4…b03e62` (788.242.297 B), `release.json` `16f113b1…`, `SHA256SUMS` `abb37c5a…`; los tres coinciden con los locales |
| Descarga | `HEAD` de `…/download/v2.6.3/DMWoldVirtualP2P3Dv2.6.3.exe` | `200`, `Content-Length: 788242297`, `application/octet-stream` |

---

## Deuda abierta

- **Prueba real del reset**: la autoprueba cubre el diagnóstico y el archivado sobre directorios
  temporales, no un PC físico con restos a medias ni una carpeta copiada de otro equipo.
- **Prueba visual del ciclo completo**: tras el reset, el recorrido bienvenida → crear cuenta →
  carrusel → nick no se ha completado con una sesión gráfica real en esta versión.
- **OTA real** desde GitHub y re-extracción del runtime en un equipo con la versión anterior.
- **Portal contra la release publicada**: `/api/info` se midió con el fallback local de la 2.6.3, no
  contra la release ya subida a GitHub.
- **Firma de código**: la 2.6.3 se publica sin firmar, como las anteriores.

*La 2.6.3 añade el diagnóstico de cuenta al arrancar y mantiene todo lo de la 2.6.2; está publicada
como *Latest* desde el 2026-10-28.*
