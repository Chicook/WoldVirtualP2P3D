# Desarrollo 2.6.7 — chat restaurado y SMTPLC sobre la base completa de la 2.6.4

Trabajo sobre el árbol del 2026-10-28
(`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_267f0a1c`), rama `DevQoderIA`.
**Estado de la release: construida y probada en local; NO publicada.** No hay tag ni *release* en
GitHub: publicar sigue requiriendo confirmación del dueño (R16 de `REGLAS_DE_ACTUALIZACION.md`).

---

## Objetivo

Recuperar en una sola versión **todo lo que la 2.6.5 y la 2.6.6 dejaron por el camino** —el chat de
texto, voz y webcam, los amigos, el perfil persistente, el reset total y las autopruebas— y sumarle
el sistema de seguridad **SMTPLC** que introdujo la 2.6.5, sin tocar el PCK ni el motor.

## Por qué faltaba el chat

La 2.6.5 y la 2.6.6 se compilaron desde `actualizacion_022321c8`, un linaje que **nunca tuvo** la
carpeta `Chat/`, `FriendsStore`, `PerfilUsuario`, `SesionUnicaGuarda`, `ReinicioCuenta` ni las
autopruebas. El árbol completo era `actualizacion_52bf0d80` (2.6.4). La 2.6.7 parte de ese árbol
completo y le añade **sólo** SMTPLC y el cambio de versión:

```
diff -rq --exclude=bin --exclude=obj --exclude=godot_exe.zip --exclude=wvp3d.pck \
     actualizacion_52bf0d80/src actualizacion_267f0a1c/src
→ FormularioUsuarioWindow.xaml.cs differ
→ Sólo en 2.6.7: VSC#/Seguridad/SMTPLC
→ Services/WebNodoService.cs differ
→ Visor3D.csproj differ
```

## Qué se hace

| Área | Cambio | Estado |
|---|---|---|
| Base | Copia íntegra de `actualizacion_52bf0d80/src` (2.6.4): chat texto/voz/webcam, amigos, chat privado, perfil por PC, sello de sesión única, reset total, `estado.json` y las cuatro autopruebas | Sin cambios |
| Seguridad SMTPLC | Carpeta `VSC#/Seguridad/SMTPLC/` con los 10 ficheros de la rama Antigravity (`SmtplcSecurityService`, `VmDetector`, `VpnDetector`, `LocationFingerprinter`, `LocationAccountLedger`, `SmtplcModels`, `SmtplcNativeMethods`, `SmtplcDiagnostics` y sus dos README) | Integrado |
| Registro | `FormularioUsuarioWindow` pasa a `async` y llama a `EvaluateRegistrationAsync(nombre, _hardwareHash)` **antes** de crear el UUID; si la evaluación deniega, muestra `DenialTitle`/`DenialReason` y reactiva el botón. Tras `SesionUnicaGuarda.SellarDespuesDeRegistro(_uuid)` anota la cuenta con `CommitRegistration(_uuid, nombre, evaluacion, _hardwareHash)` | Implementado |
| Barrera de una cuenta | Se conserva `PerfilUsuario.TieneIdentidad` como última barrera dentro del formulario (la 2.6.4 la tenía; SMTPLC no la sustituye) | Sin cambios |
| Portal | El fallback empotrado anuncia `DMWoldVirtualP2P3Dv2.6.7.exe` y su URL de descarga (`Services/WebNodoService.cs`) | Implementado |
| Versión | `AssemblyName` = `DMWoldVirtualP2P3Dv2.6.7`; `Version`/`AssemblyVersion`/`FileVersion` = `2.6.7`/`2.6.7.0` (`VSC#/Visor3D.csproj`) | Implementado |
| Bienvenida y presencia | Sin cambios respecto a la 2.6.4: `BordeEstadoRed`, `TxtEstadoRed`, `TxtDetalleRed`, `BtnBuscarRed`, `BtnUsarNodoRed` y `BtnAcceder` («Acceder») siguen en `MainWindow.xaml` y la búsqueda de nodos sigue en `ActualizarEstadoRedAsync` | Sin cambios |
| PCK y motor | `wvp3d.pck` (537.836.524 B, SHA-256 `9d5c15e7…a69ac94`) y `godot_exe.zip` (86.155.888 B) copiados sin modificar desde `actualizacion_022321c8/src/VSC#`; no se reexportó el mundo | Sin cambios |

## Política SMTPLC que ahora aplica el registro

Valores por defecto de `SmtplcPolicy` (`Seguridad/SMTPLC/SmtplcModels.cs`):

| Regla | Valor |
|---|---|
| Cuentas por ubicación | `MaxAccountsPerLocation = 1` |
| Enfriamiento entre cuentas | `CooldownMinutesBetweenAccounts = 4320` (72 h) |
| Bloqueo de máquinas virtuales | `BlockVirtualMachines = true`, umbral `0.50` |
| Bloqueo de VPN/proxy | `BlockVpnAndProxies = true`, umbral `0.40` |

El flag `HypervisorPresent` de `Win32_ComputerSystem` puntúa **0,25** desde la prueba del
2026-10-28 (antes 0,50): Windows lo activa con VBS, Credential Guard, Hyper-V, WSL2 o el sandbox,
también en equipos físicos, y con 0,50 marcaba «VM» por sí solo. Ahora sólo corrobora las demás
señales (modelo/fabricante, BIOS, OUI de MAC, controladores, procesos, registro); un invitado real
sigue superando el umbral por esas vías.

La ubicación se firma con IP pública WAN, MAC del gateway (ARP), hash del clúster Wi-Fi y
`MachineGuid`. La evaluación **no** abre el WebSocket del juego y no altera el sello de sesión única
si deniega: se ejecuta antes de escribir nada.

## Compilación

```
cd VersionDe_sesion/Sistema_Principal/PRY/actualizacion_267f0a1c/src/VSC#
"E:/Program Files/dotnet/dotnet.exe" build   -c Release -p:SkipGodotAssets=true   # 0 avisos, 0 errores
"E:/Program Files/dotnet/dotnet.exe" publish -c Release -r win-x64 --self-contained true
```

Resultado de `publish` (exit 0):

| Dato | Valor |
|---|---|
| Salida | `bin/Release/net8.0-windows/win-x64/publish/DMWoldVirtualP2P3Dv2.6.7.exe` |
| Tamaño | 788.303.737 B (≈751,8 MiB) |
| SHA-256 | `902d5f43c11c3afba286e83d66fc281810f4a0eeb02e0cc1ec886330a80fe71a` |
| `FileVersion` | `2.6.7.0` |
| `ProductVersion` | `2.6.7+5b8199af8cd06883163cba2292d67dbe65e96a14` (compilado sobre `DevQoderIA` `5b8199a`) |
| PDB | 158.960 B, junto al exe |

## Autopruebas del binario 2.6.7

Ejecutadas con `WOLD_RUNTIME_DIR=E:/areadetrabajo/wvp267/selftest_runtime` y
`APPDATA=E:/areadetrabajo/wvp267/selftest_appdata` (perfil de prueba), nunca sobre la cuenta real.

| Prueba | Comando | Resultado |
|---|---|---|
| Chat, amigos y franja | `DMWoldVirtualP2P3Dv2.6.7.exe --chat-selftest` | **26/26, 0 fallos**, exit 0; `micrófonos=1 webcams=1` |
| Cuenta, reset total y estado global | `… --cuenta-selftest` | **19/19, 0 fallos**, exit 0; `RESULTADO CUENTA: OK` |
| Red y portal | `… --red-selftest` | **7 líneas, 0 fallos**, exit 0 |
| Arranque, extracción y motor | `… --startup-selftest` | **15/15 OK**, exit 0; `.extracted` = `2.6.7`; motor 172,5 MiB; PCK 512,9 MiB e idéntico al embebido |

Matiz del arranque: la primera pasada, con el `APPDATA` de prueba **vacío**, dio 14/15
(`Motor arranca desde el PCK — exit=0 isla=False red=False`) porque el mundo no construye la isla
sin perfil de jugador; repetida con una **copia del perfil real** en el `APPDATA` de prueba, como en
la 2.6.4, dio **15/15** (`isla=True red=True errores=False`).

Los logs de las autopruebas viven en `%LOCALAPPDATA%\WoldVirtualP2P3D\logs\`
(`cuenta-selftest.log`, `red-selftest.log`, `arranque-selftest.log`): `VisorLog` resuelve la carpeta
con `GetFolderPath(LocalApplicationData)`, que no obedece a la variable `LOCALAPPDATA`. Sólo se
escribieron logs; ni el perfil real ni el `user://` real se tocaron.

## Bienvenida con presencia P2P y nodo activo

La pantalla de la captura (2026-10-28) se mantiene: en `MainWindow.xaml` siguen `BordeEstadoRed`
(línea 93), `TxtEstadoRed` (101), `BtnBuscarRed` (114), `BtnUsarNodoRed` (123) y `BtnAcceder`
(«Acceder», 165). `ActualizarEstadoRedAsync` (`MainWindow.xaml.cs:599`) escucha la baliza UDP 8912
de `DescubrimientoP2P` y, si no hay nadie en la LAN, consulta `/api/p2p-status` del enlace; sin
nodos deja «○ Metaverso vacío: serás el primero».

Sonda en vivo al cerrar la 2.6.7 (mismo equipo):

| Comprobación | Resultado |
|---|---|
| Baliza UDP 8912 durante 5 s | **0 nodos**: sin paquetes `WOLDVIRTUAL_HOST` |
| Puertos 8911 / 3030 / 8912 a la escucha | **Ninguno**: no hay motor ni portal abiertos |
| `--red-selftest` (baliza inyectada, sin depender de otro equipo) | **1 nodo detectado** y los paquetes ajenos ignorados |

Conclusión de la sonda: ahora mismo no hay ningún nodo activo, así que la bienvenida mostraría
«Metaverso vacío: serás el primero»; la detección en sí queda probada por la autoprueba.

## Prueba de registro con SMTPLC: aprobación y denegación

Arnés fuera del repositorio en `E:/areadetrabajo/wvp267/smtplc_test/` (`SmtplcHarness.csproj` +
`Program.cs`, `net8.0-windows`, `System.Management 8.0.0`). Compila **los mismos** `.cs` de
`VSC#/Seguridad/SMTPLC/` del snapshot y crea cada libro mayor en
`%TEMP%\smtplc_prueba_<guid>\<caso>\ledger.dat`, así que el libro real
(`%LOCALAPPDATA%\WoldVirtualP2P3D\security\smtplc_location_ledger.dat`) nunca se abre: al terminar
la prueba esa carpeta **no existe**.

`dotnet run -c Release` sobre el hardware real de este equipo (MSI MS-7C95, Ryzen 5 5500):

| # | Caso | Resultado observado | Veredicto |
|---|---|---|---|
| 1 | Registro en hardware físico, `SmtplcPolicy` por defecto | `IsAllowed=True`, `Code=Allowed`; VM `IsVm=False` confianza `0,25`; VPN confianza `0,00`; firma con gateway `94:00:B0:7F:3A:97` y cluster `AF3603D0…9465371` | **Aprobado** |
| 1b | `CommitRegistration` tras crear el UUID | el libro mayor pasa a tener **1** cuenta en esa ubicación | **Anotado** |
| 2 | Segunda cuenta en la misma ubicación (cuota `1`) | `MultipleAccountsInSameLocation`, «Límite de Cuentas por Ubicación Alcanzado», motivo con `'cuenta_aprobada'` | **Denegado** |
| 2b | Cuenta en conflicto en `ConflictingAccounts` | `cuenta_aprobada` presente | **Correcto** |
| 3 | Cuota 2 y enfriamiento 72 h con una cuenta previa | `LocationCooldownActive`, «Tiempo restante aproximado: 72 horas» | **Denegado** |
| 4 | Anti-VM con `VmConfidenceThreshold=0.0` | `VmDetected`, «Entorno Virtualizado No Permitido»; **el libro mayor no se crea** | **Denegado** |
| 5 | Anti-VPN con `VpnConfidenceThreshold=0.0` | `VpnOrProxyDetected`, «Conexión VPN / Proxy Detectada»; **el libro mayor no se crea** | **Denegado** |
| 6 | `GenerateFullAuditReport` | informe de la aprobación con `[APROBADO]` y de la denegación con `[DENEGADO]` | **Correcto** |

Resultado final del arnés: **11/11 comprobaciones OK**, `RESULTADO SMTPLC: OK`, exit 0.

### Defecto encontrado y corregido

La primera pasada (2026-10-28) dio **6 fallos**: todos los casos, incluido el de aprobación,
salían denegados con `VmDetected`. Causa: este PC es físico pero tiene `HypervisorPresent=True`
(VBS/Hyper-V de Windows); `VmDetector` puntuaba ese flag aislado con 0,50, `IsVm` se calcula con
`>= 0,40` y el umbral por defecto es `0,50`, de modo que **ningún equipo con VBS podía registrar
cuenta**. Corrección en `Seguridad/SMTPLC/VmDetector.cs`: el flag aislado pasa a 0,25 y se documenta
como señal corroborante. Tras la corrección el arnés sale verde y `dotnet build -c Release` del
visor da **0 avisos y 0 errores**.

**Aviso de vigencia:** el exe publicado `DMWoldVirtualP2P3Dv2.6.7.exe`
(SHA-256 `902d5f43…a80fe71a`) se compiló **antes** de esta corrección, así que en un PC con
VBS/Hyper-V activo sigue denegando el registro. La corrección va incluida en la **2.6.8**
(`DMWoldVirtualP2P3Dv2.6.8.exe`, ver [`README_desarrollo_20261028_2_6_8.md`](README_desarrollo_20261028_2_6_8.md)).
La v2.6.7 publicada no se retoca: el tag `v2.6.7` queda sobre `aecbc84`.

## Seguridad de las pruebas

- Perfil real intacto: `%LOCALAPPDATA%\WoldVirtualP2P3D\` (cuenta, sello, estado) y
  `%APPDATA%\Godot\app_userdata\WoldVirtualP2P3D\` (registro, avatar, islas, inventario).
- Las pruebas usaron directorios temporales o el `APPDATA`/`WOLD_RUNTIME_DIR` aislados; la copia del
  perfil real sólo se leyó.
- No se borró ni se fusionó ninguna rama `respaldo/*` ni `backup/*`.

## Pendiente

| Tarea | Estado |
|---|---|
| Publicar la `v2.6.7` (tag, release con `exe` + `release.json` + `SHA256SUMS`) | **Pendiente de confirmación (R16)** |
| OTA real 2.6.4/2.6.6 → 2.6.7 en el PC real | Sin prueba real |
| Registro real con SMTPLC aprobando en hardware físico (sin VM ni VPN) y denegando en VM/VPN | **Probado el 2026-10-28 con arnés de código real: 11/11**, aprobación con política por defecto y denegaciones por cuota, enfriamiento, VM y VPN. Corregido el falso positivo de `HypervisorPresent` (ver arriba). El exe publicado, sin embargo, es anterior a la corrección |
| Recompilar y publicar una versión que incluya la corrección de `VmDetector` | **Compilada el 2026-10-28 como 2.6.8** (`DMWoldVirtualP2P3Dv2.6.8.exe`, SHA-256 `6ab640d1…b554`, autopruebas 19/19, 7/7, 15/15 y chat sin fallos); publicación pendiente de confirmación |
| Sesión real entre dos máquinas (chat, voz, webcam, construcción) sobre la 2.6.7 | Sin prueba real |
| Firma de código | Planificado |

## Propagación

Este árbol es la fuente que se fusiona en `main` y en las ramas `Dev*` para que la restauración del
chat no se pierda. La rama de integración se crea **desde `main`** y sólo añade este snapshot y su
documentación, de modo que el merge no reintroduce los borrados del flujo RFPRMN en `DevQoderIA`
(esa rama recibe el commit por *cherry-pick*).
