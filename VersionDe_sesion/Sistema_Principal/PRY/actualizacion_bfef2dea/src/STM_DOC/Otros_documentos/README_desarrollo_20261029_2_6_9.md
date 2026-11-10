# Desarrollo 2.6.9 — webcam fiable, arranque sin ICU bajo Wine y mundo para Linux

Trabajo sobre el árbol del 2026-10-29
(`VersionDe_sesion/Sistema_Principal/PRY/actualizacion_267f0a1c`), rama `DevQoderIA`.
**Estado: publicada como v2.6.9 el 2026-10-29 y recompilada el mismo día con tres arreglos.**
Tag `v2.6.9` sobre `f1e57ee` de `main` (merge del PR #36), marcada *Latest*, con `exe`,
`WoldVirtualP2P3Dv2.6.9-linux.tar.gz`, `release.json` y `SHA256SUMS` verificados por API. El
responsable pidió **mantener el nombre `DMWoldVirtualP2P3Dv2.6.9.exe`** y sustituir los assets en
lugar de subir una 2.6.10: el exe y `SHA256SUMS` se reemplazaron el 2026-10-29, con el mismo tag,
nombre y URL. La v2.6.8 sigue publicada como release anterior. Todo lo de la 2.6.8 sigue dentro: los
ficheros que cambian son `Chat/ChatWebcam.cs`, `Services/StartupSelfTest.cs`,
`Services/WebNodoService.cs`, `Visor3D.csproj`, `Seguridad/SMTPLC/VmDetector.cs`, el nuevo
`RuntimeCleaner.cs`, `App.xaml.cs` y `MainWindow.xaml.cs`; el motor y el `wvp3d.pck` son los mismos
de la 2.6.1 a la 2.6.8.

---

## Objetivo

1. Que la cámara del chat funcione en equipos donde la 2.6.8 elegía un dispositivo virtual sin
   tramas.
2. Que el `.exe` de Windows **arranque bajo Wine** en vez de morir con `Error: 127` por ICU.
3. Ofrecer el mundo 3D en **Linux nativo**, sin Wine.
4. Que `--startup-selftest` no dependa del perfil de Godot del equipo.

## Qué cambia respecto a la 2.6.8

| Área | Cambio | Fichero |
|---|---|---|
| Webcam | Puntúa los dispositivos antes de abrir (hardware PnP +100, software `@device:sw:` −100, nombres virtuales −60, IR/profundidad −40), exige la **primera trama** en 1500 ms, conmuta al siguiente candidato (hasta 3), vigila caídas de 6 s y explica el motivo cuando no hay imagen (Wine, permiso de privacidad, cámara virtual sin tramas) | `VSC#/Chat/ChatWebcam.cs` |
| ICU / Wine | `System.Globalization.UseNls = true` en `runtimeconfig.json`; .NET deja de cargar el ICU del sistema y usa las API NLS de `kernel32` (Wine las implementa) sin perder `es-ES` | `VSC#/Visor3D.csproj` |
| Arranque | `--startup-selftest` crea un perfil de Godot de usar y tirar en `%TEMP%` (`registro.cfg` con avatar y nick) y fuerza `--server`; deja de depender del perfil real y de un `p2p_session.json` ajeno | `VSC#/Services/StartupSelfTest.cs` |
| Portal | El fallback empotrado anuncia `DMWoldVirtualP2P3Dv2.6.9.exe` y su URL | `VSC#/Services/WebNodoService.cs:64-66` |
| Versión | `AssemblyName` = `DMWoldVirtualP2P3Dv2.6.9`; `Version`/`AssemblyVersion`/`FileVersion` = `2.6.9`/`2.6.9.0` | `VSC#/Visor3D.csproj:24,27-29` |
| Umbral de VM | `VmDetector.UmbralVm = 0,50`, el mismo que `SmtplcPolicy.VmConfidenceThreshold`: antes el detector marcaba desde 0,40 y una sola señal débil bloqueaba el registro | `VSC#/Seguridad/SMTPLC/VmDetector.cs` |
| Recolector de runtimes | Tras un arranque correcto borra las carpetas de versiones anteriores, conservando la vigente y la última buena; sólo actúa si la carpeta padre se llama `runtime` | `VSC#/RuntimeCleaner.cs`, `App.xaml.cs`, `MainWindow.xaml.cs` |
| Reintento del release | Tres consultas con espera 5 s × intento; si falla, libera el pestillo para que un `Start()` posterior reintente | `VSC#/Services/WebNodoService.cs` |
| Linux | `STM_LBR/` con `woldvirtual-linux.sh`, `woldvirtual-wine.sh`, `diagnostico.sh` y `README.md`; buscan el motor y el mundo en `./motor/` y `./mundo/` del paquete (o en la carpeta padre) | `VSC#/STM_LBR/` |
| Chat, amigos, perfiles, reset total, bienvenida, SMTPLC, motor y PCK | Sin cambios | — |

## ICU bajo Wine: la configuración exacta

El fallo original es del runtime, no del visor:

```
0024:err:module:find_forwarded_export module not found for forward
      'icuuc68.u_charsToUChars_68' used by L"C:\windows\system32\icu.dll"
Cannot get symbol u_charsToUChars from libicuuc
Error: 127
```

.NET 8 inicializa la globalización con el ICU del sistema antes de ejecutar una sola línea del
visor. El `icu.dll` de Wine reenvía a un `icuuc68` que ese paquete no tiene y el proceso muere con
127. La propiedad que lo evita va **fuera** de `PropertyGroup`, en su propio `ItemGroup`
(`VSC#/Visor3D.csproj:35-46`):

```xml
<!--
  Sin esto, .NET 8 carga el ICU del sistema al arrancar. Bajo Wine el icu.dll
  reenvía a un icuuc68 que no existe y el proceso muere con código 127 antes
  de ejecutar código propio. Con System.Globalization.UseNls .NET usa las API
  de locale de kernel32 (que Wine sí implementa) y en Windows conserva la
  cultura es-ES: fechas 29/10/2026, decimales con coma y orden alfabético.
  No se usa InvariantGlobalization: en modo invariante `new CultureInfo("es-ES")`
  lanza CultureNotFoundException y las fechas pasan a formato MM/dd/yyyy.
-->
<ItemGroup>
  <RuntimeHostConfigurationOption Include="System.Globalization.UseNls" Value="true" />
</ItemGroup>
```

**Por qué NLS y no `InvariantGlobalization`.** Se probaron las dos con un proyecto desechable
(`E:/areadetrabajo/icu_test`) ejecutando `es-ES`:

| Configuración | Decimal | Fecha | `"AÑO".ToUpper()` | `ToString("0.0")` |
|---|---|---|---|---|
| Por defecto (ICU) | `1,5` | `29/10/2026` | `AÑO` | `536,0` |
| `System.Globalization.UseNls=true` | `1,5` | `29/10/2026` | `AÑO` | `536,0` |
| `InvariantGlobalization=true` | `1.5` | `10/29/2026` | `AÑO` | `536.0` |

Con `InvariantGlobalization` la propia construcción falla:
`System.Globalization.CultureNotFoundException … es-ES is an invalid culture identifier`. El visor
usa orden alfabético de cultura (`StringComparer.CurrentCultureIgnoreCase`,
`MainWindow.xaml.cs:2345,2362`) y un decimal con coma (`ToString("0.0")`,
`MainWindow.xaml.cs:964`), así que el modo invariante cambiaría lo que ve el usuario. `UseNls`
conserva ambos. La clave queda dentro del exe publicado (`runtimeconfig.json` embebido, verificable
buscando `System.Globalization.UseNls` en el binario) y no hay `InvariantGlobalization` en él.

**Efecto en Linux.** Con `UseNls`, el runtime arranca bajo Wine; lo que sigue sin funcionar bajo
Wine es la ventana WPF (WPF sólo existe en Windows) y la webcam (Wine no expone DirectShow). Por eso
la vía real en Linux es el paquete nativo de la sección siguiente.

## Linux nativo: qué se puede compilar y qué no

El visor es `net8.0-windows` con `UseWPF=true`: **no existe un binario Linux del visor**. Lo que sí
es neutro de plataforma es el mundo: Godot 4.7.2 + `wvp3d.pck`. El paquete de Linux lleva el motor
oficial y el mundo, y los guiones de `STM_LBR/` los arrancan:

| Pieza | Comando / origen |
|---|---|
| Motor | `https://godotengine.org/download/linux/` → `Godot_v4.7.2-stable_linux.x86_64.zip` (SHA-256 `cadd3204…c35329e4`); dentro va el ELF de 146.414.384 B |
| Mundo | `wvp3d.pck` del árbol (`SHA-256 9d5c15e7…7a69ac94`), el mismo que empotra el `.exe` |
| Arranque | `./STM_LBR/woldvirtual-linux.sh` → `Godot_v4.7.2-stable_linux.x86_64 --main-pack <pck> -- <args>` |
| Sesión remota | `-- --peer-url="<url>"` o `-- --client --ip=<host> --port=<puerto>` |

```bash
tar -xzf WoldVirtualP2P3Dv2.6.9-linux.tar.gz
cd WoldVirtualP2P3Dv2.6.9-linux
chmod +x STM_LBR/*.sh motor/Godot_v4.7.2-stable_linux.x86_64
./STM_LBR/woldvirtual-linux.sh --dry-run
./STM_LBR/woldvirtual-linux.sh --verificar
./STM_LBR/woldvirtual-linux.sh
```

El paquete se genera con `E:/areadetrabajo/wvp269/empaquetar_linux.py`, que calcula `SHA256SUMS` y
empaqueta con modos fijos (0755 en `motor/`, `*.sh` y directorios; 0644 en el resto). Sin ese
`tarfile` explícito los directorios salían con modo 0644 y en Linux no se podía ni entrar en ellos.

## Compilación de Windows

```
cd VersionDe_sesion/Sistema_Principal/PRY/actualizacion_267f0a1c/src/VSC#
"E:/Program Files/dotnet/dotnet.exe" publish -c Release -r win-x64 --self-contained true \
  -p:PublishSingleFile=true -o E:/out_v269/publish
```

| Dato | Valor |
|---|---|
| Salida | `E:/areadetrabajo/wvp269/release_269b/build/DMWoldVirtualP2P3Dv2.6.9.exe` |
| Tamaño | 788.316.025 B (≈751,8 MiB) |
| SHA-256 | `e7e27212921807b735cdca98f6a1995ef96492ae456a8316b8fd5469596d84d8` |
| `FileVersion` | `2.6.9.0` |
| `ProductVersion` | `2.6.9+fb9e7348cc5234fa85c7c988f59d442ccbff13a6` |
| Errores / avisos | 0 / 0 (sólo el aviso `NETSDK1057` de SDK preliminar) |

## Autopruebas del binario 2.6.9

Ejecutadas con `WOLD_RUNTIME_DIR=E:/areadetrabajo/wvp269/selftest_runtime`. El perfil de Godot ya
no se toca: `--startup-selftest` usa el suyo en `%TEMP%`.

| Prueba | Comando | Resultado |
|---|---|---|
| Chat, amigos, relay y franja | `… --chat-selftest` | **26 comprobaciones, 0 fallos**, exit 0; `micrófonos=1 webcams=2` |
| Cuenta, reset total y estado global | `… --cuenta-selftest` | **19/19, 0 fallos**, exit 0; `RESULTADO CUENTA: OK` |
| Red y portal | `… --red-selftest` | **7 líneas, 0 fallos**, exit 0 |
| Arranque, extracción y motor | `… --startup-selftest` | **17/17, 0 fallos**, exit 0; `.extracted` = `2.6.9`; PCK 512,9 MiB íntegro; `isla=True red=True errores=False` |

Las dos comprobaciones nuevas del arranque son «Umbral de VM unificado (0,50)» (detector y política
coinciden) y «Recolector de runtimes (conserva vigente y anterior)»: crea `2.6.7`, `2.6.8` y `2.6.9`
en `%TEMP%`, purga y exige que sólo desaparezca la más antigua.

Informes: `%TEMP%\woldvirtual_chat_selftest.log`, `%LOCALAPPDATA%\WoldVirtualP2P3D\logs\cuenta-selftest.log`,
`…\red-selftest.log` y `…\arranque-selftest.log`.

**Arranque: por qué se cambió la prueba.** La primera pasada dio 14/15: «Motor arranca desde el
PCK» falló con `exit=0 isla=False red=False` porque el motor leyó el `user://p2p_session.json` real,
se puso en modo cliente remoto y nunca abrió la isla ni el 8911. Con un perfil aislado y un
`registro.cfg` de prueba pasaba 15/15 (era la deuda que la 2.6.1 ya había documentado) y ahora da
17/17 con las dos comprobaciones nuevas. La prueba crea ese perfil por sí misma y no toca el del
equipo.

## Pruebas de globalización

| Prueba | Resultado |
|---|---|
| Clave en `runtimeconfig.json` publicado | `"System.Globalization.UseNls": true` |
| Clave dentro del `.exe` | encontrada en el offset 635.357.489; `InvariantGlobalization` no aparece |
| Formato `es-ES` en ejecución real | el log del portal anota `release vigente → … (751,8 MB)`, con **coma decimal** |
| Fechas y orden alfabético | cubiertos por el sondeo `icu_test` (tabla de arriba) |

## El binario 2.6.9 contiene todo el 2.6.8

| Comprobación | Resultado |
|---|---|
| Ficheros de código distintos | 8 (`ChatWebcam.cs`, `StartupSelfTest.cs`, `WebNodoService.cs`, `Visor3D.csproj`, `VmDetector.cs`, `RuntimeCleaner.cs`, `App.xaml.cs`, `MainWindow.xaml.cs`); el resto, igual |
| `wvp3d.pck` | `9d5c15e7322cfce3d450e65341a23f6e82d01a008b760245a3e10e0d7a69ac94`, idéntico al del árbol, al del `runtime\2.6.8\` instalado y al extraído del exe 2.6.9 |
| Motor | `ab1824f85bfd8e0e4128182c000c4003a3e042245b2967848d089b2a04b22424` (180.858.888 B), idéntico al del `runtime\2.6.8\` y extraído del exe 2.6.9 |
| Autopruebas | chat 26/0, cuenta 19/19, red 7/7, arranque 17/17 — iguales o mejores que la 2.6.8 |
| Licencia y mundo | `godot_exe.zip` sin tocar (`ef472613f249c1123f17655417aeade55a628c59994be0c4befd508bb9ca6137`) |

## Paquete de Linux

| Dato | Valor |
|---|---|
| Nombre | `WoldVirtualP2P3Dv2.6.9-linux.tar.gz` |
| Tamaño | 552.727.606 B (≈527,1 MiB) |
| SHA-256 | `33de816826dd7f6e50908ac9b2c7d91516476c33e2fa571276e0faa33885594f` |
| Contenido | `motor/Godot_v4.7.2-stable_linux.x86_64`, `mundo/wvp3d.pck`, `STM_LBR/` (3 guiones + README), `LEEME.md`, `LICENSE-godot.txt`, `SHA256SUMS` |
| Verificación hecha | extraído y `sha256sum -c SHA256SUMS` 8/8 OK; `bash -n` en los tres guiones; `--dry-run` y `--verificar` resuelven `../motor` y `../mundo` y confirman la huella del PCK |
| Pendiente | ejecutarlo en una distro Linux real (`./diagnostico.sh` da el informe) |

## Estado de la release

Publicada el 2026-10-29 como *Latest*:

| Dato | Valor |
|---|---|
| Tag | `v2.6.9` sobre `f1e57ee` de `main` (merge del PR #36 desde `DevQoderIA`) |
| Release | `https://github.com/Chicook/WoldVirtualP2P3D/releases/tag/v2.6.9` |
| `digest` del exe (API) | `sha256:e7e27212921807b735cdca98f6a1995ef96492ae456a8316b8fd5469596d84d8` (coincide con el SHA-256 local) |
| `digest` del tar.gz (API) | `sha256:33de816826dd7f6e50908ac9b2c7d91516476c33e2fa571276e0faa33885594f` |
| `release.json` | `9f402c533a14c7ccb1b694a38a88b1fd16d4c6776a607e42d8bc1dae9fdd9c47`, 215 B |
| `SHA256SUMS` | `afc3efc27f912e1b1007bcd7b997329bb30b4d7eb6e74e9a4ca1ee87a1f75bf9`, 276 B (tres líneas: exe, `release.json` y tar.gz) |
| Descargas | las cuatro responden `200`: exe `Content-Length` 788.316.025, tar.gz 552.727.606, `release.json` 215, `SHA256SUMS` 276 |

El artefacto se subió desde `E:/out_v269/release/`, una ruta sin `#`: `gh release create` lanzado
desde el repo raíz con `-R`, porque una ruta con `#` (`src/VSC#/…`) se corta en `VSC`.

## Recompilación del mismo 2.6.9 (2026-10-29)

El responsable pidió **conservar el nombre `DMWoldVirtualP2P3Dv2.6.9.exe`** para el binario que
incluye los tres arreglos posteriores a la primera publicación. Se compiló desde el commit
`fb9e734` y se sustituyeron el exe y `SHA256SUMS` con `gh release upload v2.6.9 --clobber`; el tag,
el nombre, la URL, `release.json` y el tar.gz de Linux no cambiaron.

| Comprobación | Resultado |
|---|---|
| Recompilación | `dotnet publish … -p:PublishSingleFile=true` → 788.316.025 B, SHA-256 `e7e27212…6d84d8`, `ProductVersion 2.6.9+fb9e7348…` |
| Autopruebas del artefacto subido | chat 0 fallos, cuenta 19/19, red 7/7, arranque **17/17** con `runtime\2.6.9` |
| `digest` del exe por API | `sha256:e7e27212921807b735cdca98f6a1995ef96492ae456a8316b8fd5469596d84d8`, 788.316.025 B |
| `digest` de `SHA256SUMS` por API | `sha256:afc3efc27f912e1b1007bcd7b997329bb30b4d7eb6e74e9a4ca1ee87a1f75bf9`, 276 B; su descarga coincide con ese hash |
| Sin cambios | `release.json` (`9f402c53…d9c47`, `size_mb` sigue 751,8) y `WoldVirtualP2P3Dv2.6.9-linux.tar.gz` (`33de8168…885594f`) |
| Descargas | las cuatro responden `200` con el `Content-Length` nuevo del exe (788.316.025) y el resto igual |

Esto es una excepción puntual a **R2** (un binario nuevo exige `<Version>` nueva) autorizada por el
responsable; la regla sigue vigente para la próxima compilación, que debe subir versión. El exe
anterior (`1fdbd356…e83ac8b`) deja de ser reproducible desde el tag, porque el tag apunta a
`f1e57ee` y este binario se compiló desde `fb9e734`.
