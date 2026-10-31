# Desarrollo 2.6.4 — reset total único y registro directo si el PC está vacío

Trabajo sobre el árbol del 2026-10-28
(`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_52bf0d80`), rama `DevQoderIA`.
**Estado de la release: publicada como v2.6.4 el 2026-10-28.** Tag `v2.6.4` sobre el commit
`5f23b8c` de `DevQoderIA`, marcada *Latest*, con `exe` + `release.json` + `SHA256SUMS` verificados
por API. La v2.6.3 sigue publicada como release anterior.

---

## Objetivo

Que la 2.6.4 **borre por completo la base de datos local una sola vez**, para que el usuario recorra
el registro entero, y que **a partir de ahí la persistencia se quede** en esta y en futuras
versiones. Además, si el PC no tiene nada de lo necesario, el visor debe **saltar directamente al
ciclo de registro completo** en lugar de mostrar una bienvenida que no lleva a ninguna parte.

## Qué se hace

| Área | Cambio | Estado |
|---|---|---|
| Reset total | `ReinicioCuenta.EjecutarResetTotal(version, baseDir?, godotDir?)` archiva **todo** el perfil local salvo `runtime`, `logs`, `respaldo_cuenta` y `cloudflared.exe`, y **todo** el `user://` del motor salvo las cachés (`logs`, `shader_cache`, `vulkan`, `objectdb_snapshots`) (`Seguridad/Seguridad_sesion_unica/ReinicioCuenta.cs`) | Implementado |
| Marcador permanente | `reset_total.txt` (además de `reset_cuenta.txt`) impide repetir el reset en esta ni en futuras versiones; sin él se reintentaría en el siguiente arranque | Implementado |
| Migración | `PerfilUsuario.MigrarSiProcede()` sólo se ejecuta si no se hizo el reset total, así que una cuenta antigua no vuelve a entrar por la puerta de atrás (`App.xaml.cs:83-86`) | Implementado |
| Estado global | `Seguridad/EstadoGlobal.cs` escribe `%LOCALAPPDATA%\WoldVirtualP2P3D\estado.json` en cada arranque con las cinco piezas necesarias (`credenciales`, `perfil`, `llave`, `sello`, `motor`), el estado del equipo (`vacio`/`incompleto`/`completo`) y la acción (`registro-completo`/`reparar`/`acceso`) | Implementado |
| Registro directo | `MainWindow` recibe `equipoVacio` y, si es cierto y no hay identidad, abre `RegistroWindow` en `OnLoaded` mediante `AbrirRegistroInicial()` (una sola vez por ejecución) | Implementado |
| Guarda de seguridad | El barrido local nunca archiva en bloque el directorio del motor si éste vive dentro de la raíz de pruebas; el motor tiene su propio barrido selectivo | Implementado |
| Motor Godot | Sin cambios: `Boot.gd` ya borraba `registro.cfg` al ver `reset_flag.txt`, y `EjecutarResetTotal` escribe ese flag con la versión | Sin cambios |
| Autoprueba | `--cuenta-selftest` pasa de 12 a **19** comprobaciones: cinco del reset total y dos del estado global (`Services/CuentaSelfTest.cs`) | Implementado (19/19) |
| Portal | El fallback empotrado anuncia `DMWoldVirtualP2P3Dv2.6.4.exe` y su URL (`Services/WebNodoService.cs`) | Implementado |
| Versión | `AssemblyName` = `DMWoldVirtualP2P3Dv2.6.4`; `Version`/`AssemblyVersion`/`FileVersion` = `2.6.4`/`2.6.4.0` (`VSC#/Visor3D.csproj:24,27-29`) | Implementado |

Decisiones de diseño:

- **Se archiva, no se borra.** Todo termina en
  `%LOCALAPPDATA%\WoldVirtualP2P3D\respaldo_cuenta\reset-total-<fecha>\{local,godot}`. Si un fichero
  crítico no se pudo mover, **no se escribe el marcador**: el reset se reintenta en el próximo
  arranque en lugar de dejar un estado a medias.
- **El runtime no se toca.** `runtime`, `logs`, `cloudflared.exe` y las cachés del motor sobreviven;
  así el arranque no re-extrae 685 MiB ni pierde los diagnósticos.
- **La persistencia es definitiva.** El marcador es permanente y no se borra al registrar: el
  registro nuevo se queda en `credentials.json`, `user_profile.json`, `llave_acceso.json`, etc.
- **Referencia `Estado_Global`.** Del repositorio de referencia
  (`Jaldvox/WoldVirtual3Dp2p`, carpeta `WoldVirtual/Estado_Global`) se toma **sólo la idea**: un
  `estado.json` versionado (`v`, `ts`) que resume el estado global. Allí está implementado en C# y
  JSON (`GlobalConfig.cs`, `SessionManager.cs`, `SharedModels.cs`, `estado.json`), no en GDScript;
  aquí se adapta al visor con claves legibles y sin identidad dentro del fichero. No se copia
  código del proyecto de referencia ni se toca el PCK.
- **Las pruebas nunca tocan el perfil real.** `EjecutarResetTotal` y `EstadoGlobal.Actualizar`
  aceptan rutas; la autoprueba usa `%TEMP%\wvp3d_cuenta_selftest_<guid>` y lo borra al terminar.
  **No se ha lanzado el visor sin bandera de autoprueba en este PC**, porque ese arranque ejecutaría
  el reset total real.

**PCK:** no hay cambios en el proyecto Godot. Se reutiliza el PCK de la 2.6.1/2.6.2/2.6.3
(`537.836.524 B`, SHA-256 `9d5c15e7322cfce3d450e65341a23f6e82d01a008b760245a3e10e0d7a69ac94`). La
versión nueva fuerza la re-extracción por R1 aunque el mundo sea el mismo.

---

## Evidencia

| Prueba | Comando | Resultado |
|---|---|---|
| Cuenta, reset total y estado global | `DMWoldVirtualP2P3Dv2.6.4.exe --cuenta-selftest` | **19 comprobaciones, 0 fallos**, exit 0: 7 diagnósticos; restos archivados; cuenta completa intacta; motor limpio sin cuenta; reset total vacía la base de usuario y el estado del jugador, conserva `runtime`, `logs`, `cloudflared.exe`, `shader_cache` y `logs` del motor, deja ≥6 ficheros en `respaldo_cuenta`, **no se repite** y la cuenta nueva persiste; `estado.json` → `vacio/registro-completo` sin nada y `completo/acceso` con la cuenta |
| Chat y franja | `DMWoldVirtualP2P3Dv2.6.4.exe --chat-selftest` | **26 comprobaciones, 0 fallos**, exit 0; `micrófonos=1 webcams=1` |
| Red y portal | `DMWoldVirtualP2P3Dv2.6.4.exe --red-selftest` | **7 líneas, 0 fallos**, exit 0 |
| Arranque, extracción y motor | `DMWoldVirtualP2P3Dv2.6.4.exe --startup-selftest` con `WOLD_RUNTIME_DIR` y `APPDATA` aislados | **15/15 OK**, exit 0; `runtime\2.6.4\`, `.extracted` = `2.6.4`; PCK extraído = embebido (512,9 MiB), motor 172,5 MiB; motor `exit=0`, `isla=True`, `red=True`, `errores=False` con un perfil copiado al `APPDATA` de prueba |
| Portal | En la misma pasada, `GET /api/info` | `{"disponible":true,"nombre":"DMWoldVirtualP2P3Dv2.6.4.exe","tamano_mb":"—",…}` (el fallback local; el portal lo refresca contra GitHub al arrancar) |
| PCK | `sha256sum` del PCK fuente | `9d5c15e7…a69ac94`, idéntico al extraído por el runtime |
| Compilación | `dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -o E:/out_v264` | **0 errores, 0 avisos** (solo NETSDK1057 de SDK preliminar); exe **788.250.489 B**, SHA-256 `8ec5d19cb5f14cc3be0a7d2e00cdf9ef9e2e65366411315f14d2defd88576b9f` |
| `release.json` | 215 B | SHA-256 `e5c12374b613c2923955defca223c5ce3513a145690078097b05cff40b080065` |
| `SHA256SUMS` | 174 B | SHA-256 `61329a80e77a179672c8c838a50482c17b20dbc254a686142de36ff5dc042cd0` |
| Publicación | `git tag v2.6.4` sobre `5f23b8c`, `gh release create v2.6.4` con los tres assets | `draft=false`, `prerelease=false`, *Latest*, publicada el 2026-10-28T01:25:52Z |
| Digests publicados | `gh api repos/…/releases/tags/v2.6.4 --jq '.assets[]'` | exe `8ec5d19c…576b9f` (788.250.489 B), `release.json` `e5c12374…`, `SHA256SUMS` `61329a80…`; los tres coinciden con los locales |
| Descarga | `HEAD` de `…/download/v2.6.4/DMWoldVirtualP2P3Dv2.6.4.exe` | `200`, `Content-Length: 788250489`, `application/octet-stream` |

Incidencia corregida durante las pruebas: la primera autoprueba dio **1 fallo** porque el test anida
el directorio del motor dentro de la raíz de usuario y el barrido local lo archivaba en bloque,
llevándose `shader_cache`. Se añadió la guarda descrita arriba y la pasada quedó en **19/19**.

---

## Deuda abierta

- **Primer arranque real del borrado único**: la autoprueba cubre el archivado y el marcador sobre
  directorios temporales, pero el reset total no se ha ejecutado en un PC físico para no borrar el
  perfil real de este equipo antes de que el dueño lo decida.
- **Prueba visual del registro directo**: `AbrirRegistroInicial()` está cubierto por compilación y
  por el estado global (19/19), pero no se ha visto la ventana abrirse sola en un PC vacío real.
- **Ciclo completo tras el reset**: hardware → usuario → semilla → verificación → llave → carrusel
  → nick con una sesión gráfica real.
- **OTA real** desde GitHub (2.6.3 → 2.6.4) y re-extracción del runtime en un equipo con la versión
  anterior.
- **Portal contra la release publicada**: `/api/info` se midió con el fallback local de la 2.6.4, no
  contra la release ya subida a GitHub.
- **Firma de código**: la 2.6.4 se publica sin firmar, como las anteriores.

*La 2.6.4 añade el reset total único, el estado global versionado y el registro directo en equipo
vacío; mantiene todo lo de la 2.6.3 y está publicada como *Latest* desde el 2026-10-28.*
