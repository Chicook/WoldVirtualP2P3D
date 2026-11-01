# Visor completo para Linux (2.7.1)

Hasta la 2.7.0 el asset de Linux de la release era sólo el mundo: Godot 4.7.2 más
`wvp3d.pck` y unos guiones para arrancarlo. La 2.7.1 añade el **visor completo
adaptado a Linux**, la misma versión que el exe de Windows recompilada con
Avalonia 11 sobre `net8.0`. Las dos plataformas comparten el núcleo de sesión,
red, chat y actualización; sólo cambia la capa de ventana.

Rutas relativas a `VersionDe_sesion/CONTRRF/TLLDCD/src/` (en lo que sigue, `<src/>`).

## 1. Qué se ha hecho

| Área | Antes (2.7.0) | Ahora (2.7.1) |
|---|---|---|
| Interfaz en Linux | ninguna: sólo el mundo por guión | **7 pestañas Avalonia**: Cuenta, Mundo, Portal, Red P2P, Chat, Actualizar, Diagnóstico |
| Cuenta | registro sólo desde el exe WPF | registro, desbloqueo, BIP-39 y reinicio de cuenta en Linux, con el mismo formato de ficheros |
| Portal y túnel | guión que arrancaba Godot a mano | portal WebNodo, túnel P2P, enlace de invitación y `p2p_session.json` desde la UI |
| Chat | no había | relay local en 8920, presentes, amigos y privados de texto |
| Actualizaciones | se bajaban a mano | consulta de releases, elección del `.tar.gz` de Linux y verificación SHA-256 |
| Diagnóstico | `diagnostico.sh` | pestaña con rutas, estados, PID del motor y últimas 30 líneas del registro, más `--comprobar` sin ventana |
| Parte 3D (motor + PCK) | sueltos en `motor/` y `mundo/` dentro del tar | **embebidos en el visor** y extraídos a `runtime/<versión>/` al primer arranque |
| Paquete | motor + mundo + guiones | **+ binario `woldvirtual-linux`** y `woldvirtual-linux.sh` como lanzador del visor |

## 2. Arquitectura: un núcleo, dos carcasas

`<src/>VSC#/VisorLinux/VisorLinux.csproj` no copia código: **enlaza** los ficheros
del visor de Windows con `<Compile Include="../…" Link="…"/>`.

| Enlazado (común) | Propio de Linux (`VisorLinux/`) |
|---|---|
| `Services/WebNodoService.cs`, `DescubrimientoP2P.cs`, `RateLimiter.cs`, `VisorLog.cs` | `Linux/RutasLinux.cs` — motor, PCK y `user://` en Linux |
| `RedP2P/*.cs` | `Linux/LanzadorMundo.cs` — Godot como proceso aparte y `p2p_session.json` |
| `Chat/ChatProtocol.cs`, `ChatRelayServer.cs`, `ChatClient.cs`, `FriendsStore.cs` | `Linux/RegistroPcUnico.cs` — sello de equipo desde `/etc/machine-id` |
| `STM_actualizar/ReleaseInfo.cs`, `UpdateChecker.cs`, `UpdateDownloader.cs` | `Linux/ActualizadorLinux.cs` — releases y verificación del paquete Linux |
| `Seguridad/PerfilUsuario.cs`, `EstadoGlobal.cs`, `Bip39.cs`, `PasswordHasher.cs` | `Linux/CuentaLinux.cs`, `ReinicioCuenta.cs`, `InstanciaUnica.cs`, `ComprobacionLocal.cs` |
| | `Vistas/*.cs` — ventana Avalonia en C#, sin XAML |

Lo que **no** se enlaza es lo atado a Win32: `App*`, `MainWindow`, `GodotHwndHost`,
SMTPLC, voz y webcam (NAudio, AForge) y WMI. `Visor3D.csproj` excluye
`VisorLinux\**`, así que el exe de Windows no cambia de contenido por este
proyecto.

Consecuencia práctica: un arreglo en `RedP2P`, `Chat` o la cuenta se compila en
las dos plataformas sin duplicar lógica, y un cambio de plataforma se ve de un
vistazo porque vive en `Linux/`.

## 3. Los módulos Linux, pieza a pieza

| Fichero | Responsabilidad |
|---|---|
| `Linux/RutasLinux.cs` | resuelve motor y PCK (primero en el runtime extraído, luego sueltos en `motor/` y `mundo/`) y `user://` (`$XDG_DATA_HOME/godot/app_userdata/WoldVirtualP2P3D`); admite `WOLD_MOTOR`, `WOLD_PCK` y `WOLD_GODOT_USER_DIR` |
| `Linux/RuntimeLinux.cs` | extrae el motor y el PCK embebidos en el propio binario a `runtime/<versión>/` con marcador `.extracted`, permiso 0755 y limpieza de versiones viejas |
| `Linux/LanzadorMundo.cs` | arranca el motor con `--main-pack` y, tras `--`, `--client/--ip/--port/--peer-url`; escribe `p2p_session.json` y reenvía la salida a la consola de la UI |
| `Linux/CuentaLinux.cs` | cuenta local con los mismos ficheros que Windows (`user/user_profile.json`, `credentials.json`), para poder mover un perfil entre equipos |
| `Linux/RegistroPcUnico.cs` | sello `pc_sello.json` firmado con HMAC-SHA256; la huella sale de `/etc/machine-id` (o `/var/lib/dbus/machine-id`) en vez de WMI |
| `Linux/ReinicioCuenta.cs` | reinicio de la base local: **archiva**, nunca borra, credenciales, perfil, llave, semilla, sello y el registro del jugador en Godot |
| `Linux/InstanciaUnica.cs` | una sola ventana por instalación con fichero de bloqueo exclusivo |
| `Linux/ActualizadorLinux.cs` | releases de GitHub, elección del `.tar.gz`/`.tgz` que lleve «linux» en el nombre, versión = máx(tag, nombre del asset), descarga y verificación por `digest` o tamaño exacto |
| `Linux/ComprobacionLocal.cs` | `--comprobar`: rutas, cuenta, portal, `/api/p2p-status`, consulta de releases y baliza LAN, sin abrir ventana |

Las pestañas están partidas en ficheros parciales de la misma clase
(`Vistas/VentanaPrincipal.{Cuenta,Mundo,Portal,Red,Chat,Actualizar,Diagnostico}.cs`)
y un latido de UI (`Latido()`) refresca portal, red, chat, motor y diagnóstico.

## 4. Rutas, puertos y plataforma

| Qué | Valor en Linux |
|---|---|
| Perfil y cuenta | `~/.local/share/WoldVirtualP2P3D/` (`PerfilUsuario.BaseDir`) |
| Runtime extraído (motor + PCK) | `~/.local/share/WoldVirtualP2P3D/runtime/<versión>/` (`WOLD_RUNTIME_DIR` lo cambia) |
| `user://` del motor | `~/.local/share/godot/app_userdata/WoldVirtualP2P3D/` |
| Actualizaciones | `~/.local/share/WoldVirtualP2P3D/actualizaciones/` |
| Registro del visor | `~/.local/state/woldvirtual/` |
| Portal WebNodo | 3030, reserva 3031-3040; `+100` si el puerto está ocupado |
| P2P / túnel | 7890 local, balizas UDP 8912, Godot WS 8911 |
| Chat | relay 8920 (siguientes +10 si está ocupado) |

`XDG_DATA_HOME` y `XDG_STATE_HOME` mandan si están definidos. No se lee ni se
escribe ninguna carpeta de Windows.

El motor se lanza como proceso aparte porque en Linux no se puede incrustar una
ventana ajena como hace `GodotHwndHost` en Windows. La línea de órdenes es la
misma que inyecta el visor WPF, así que el mundo no distingue quién lo arranca.

## 5. Compilación y publicación

```bash
cd "<src/>VSC#"
dotnet publish VisorLinux/VisorLinux.csproj -c Release -r linux-x64 \
  --self-contained true -p:PublishSingleFile=true \
  -p:IncludeNativeLibrariesForSelfExtract=true \
  -o VisorLinux/publish/linux-x64
```

Sale un único ELF x86-64 de **1.221.369.510 B** con las nativas de Skia y HarfBuzz dentro y, como
recursos embebidos, `godot_linux.zip` (79.135.021 B) y `wvp3d.pck` (1.053.081.932 B): la parte 3D
viaja dentro del visor igual que en el exe de Windows. No hace falta instalar .NET en la máquina
destino. El binario **no se versiona** (regla R17: nada de binarios en los commits); se copia al
árbol del paquete en `E:/areadetrabajo/wvp271/linux/WoldVirtualP2P3Dv2.7.1/`.

Los dos recursos se embeben con `EmbeddedResource` (`Condition="'$(SkipGodotAssets)' != 'true'"`),
así que una compilación de pruebas sin los 1,2 GB se hace con `-p:SkipGodotAssets=true` y el visor
queda igual, sólo sin la parte 3D dentro.

Al arrancar, `RuntimeLinux` extrae ambos a `~/.local/share/WoldVirtualP2P3D/runtime/<versión>/`
(origen: `WOLD_RUNTIME_DIR` si está definido): el motor a `Servidor3D/` con permiso 0755
(`File.SetUnixFileMode`) y el PCK en la raíz del runtime. Un marcador `.extracted` con la versión
evita repetir la faena —la segunda pasada tardó 0,1 s— y al actualizar se borran los runtimes
antiguos salvo el último que arrancó bien (`.arranque_ok`).

## 6. El paquete de la release

```bash
cd E:/areadetrabajo/wvp271
python build_tar.py linux/WoldVirtualP2P3Dv2.7.1 WoldVirtualP2P3Dv2.7.1-linux.tar.gz
```

`build_tar.py` arma `WoldVirtualP2P3Dv2.7.1/` con dueño `0/0`, sin nombres, PAX y
gzip nivel 6, y marca **0755** los `.sh` y el propio `woldvirtual-linux`; el resto va a 0644. El
paquete resultante tiene **1.110.302.810 B**, SHA-256
`cd80474417e6891e366f96ab006e0b3385e981517ea218abc1d40d22cd280d1a`, y lleva sólo cuatro ficheros y la
carpeta: `README.md` (0644), `diagnostico.sh`, `woldvirtual-linux`, `woldvirtual-linux.sh` y
`woldvirtual-wine.sh` (0755). El PCK va dentro del binario, no como fichero aparte, así que el peso
del tar es casi el del PCK comprimido (1.053.081.932 B) más el visor.

`woldvirtual-linux.sh` pasa a ser el lanzador del visor: lo busca junto a sí
mismo y lo ejecuta con los argumentos que reciba. El modo mundo directo queda
detrás de `--motor` (o `--godot`/`--pck`), y `woldvirtual-wine.sh` se mantiene
como vía de diagnóstico del exe de Windows.

## 7. Qué no trae y por qué

| Pieza | Motivo |
|---|---|
| Chat de voz y webcam | NAudio y AForge dependen de DirectShow, que en Linux no existe. El chat de texto sí funciona. |
| Huella SMTPLC de Windows | SMTPLC lee WMI (`Win32_ComputerSystem`, `Win32_BIOS`, `Win32_DiskDrive`) y claves `HKLM`. En Linux el identificador se deriva de `/etc/machine-id`; el formato del sello es el mismo, la fuente no. |
| Motor incrustado en la ventana | No hay `HwndHost` en Avalonia/Linux; el mundo va como proceso aparte con su ventana. |
| Aplicar la actualización solo | Se descarga y se verifica, pero un proceso no puede reemplazar su propio binario mientras corre: el `.tar.gz` se extrae a mano. |
| Firma Authenticode del binario | Sin equivalente en Linux; la integridad se comprueba por SHA-256 del paquete. |

## 8. Verificación

**Verificado (Windows, 2026-10-29):**

- `VisorLinux` compila sin advertencias ni errores y publica el ELF x86-64
  autocontenido de **1.221.369.510 B** (cabecera `7f 45 4c 46`), SHA-256
  `e452cdf9b2447348e7e95c723ab772908071be004341b255f2249854ac82b200`.
- La extracción de la parte 3D se probó con la publicación **win-x64 del mismo
  código** (`dotnet … --extraer` con `WOLD_RUNTIME_DIR` redirigido a una carpeta
  temporal): el PCK extraído coincide con el publicado
  (`8d42b2d3…019fdede`), el motor sale byte a byte idéntico al original
  (`8d106cbe…4953f71e`) y el marcador `.extracted` se escribe; la segunda pasada
  tarda 0,1 s y no vuelve a copiar.
- `woldvirtual-linux --comprobar` pasa en Windows: motor y PCK encontrados
  (sueltos o embebidos), línea `runtime:` con la ruta y el estado de extracción,
  portal WebNodo arriba con `/api/p2p-status`, consulta de releases correcta y
  baliza LAN escuchada.
- La consulta de actualizaciones elige `WoldVirtualP2P3Dv2.7.1-linux.tar.gz` con
  versión local 2.7.0 y no propone nada con 2.7.1.
- La ventana arranca con título «Wold Virtual P2P 3D - visor Linux 2.7.1» y
  responde.
- `Visor3D.csproj` (WPF) sigue compilando sin errores tras excluir `VisorLinux\**`.
- Los guiones del paquete pasan `bash -n`; el tar
  (`1.110.302.810 B`, SHA-256 `cd804744…cd280d1a`) lleva sólo `README.md`
  (0644) y los tres guiones más el visor en 0755, sin `motor/` ni `mundo/`
  sueltos, y el visor extraído del tar coincide byte a byte con el publicado.
- **No verificable desde este equipo:** Git Bash de Windows devuelve `-x` falso
  para cualquier archivo, así que la delegación del lanzador en el visor, el
  permiso 0755 que `RuntimeLinux` pone al motor extraído y la búsqueda por `-x`
  no se pueden ejecutar aquí; se apoyan en los permisos del tar, que sí están
  comprobados.

**Pendiente: ejecución en un Linux real.** En este equipo no hay WSL ni máquina
Linux, así que el ELF no se ha ejecutado bajo Linux. Falta confirmar en la
distro de destino que la ventana Avalonia pinta, que el motor arranca desde la
pestaña Mundo y que el chat conecta. `./diagnostico.sh` y
`./woldvirtual-linux --comprobar` son los dos pasos que dan esa respuesta.

## 9. Deuda conocida

1. **Validación en Linux real** (lo anterior). Es el único punto que separa esto
   de «publicado y probado».
2. **Voz y webcam en Linux**: si se quieren, dependen de PipeWire/GStreamer, no
   de DirectShow; sería una capa nueva, no un arreglo del código enlazado.
3. **Autoactualización**: hoy se descarga y verifica, pero se aplica a mano.
4. **Sustitución del asset publicado**: hecha el 2026-10-29 por petición expresa
   del dueño (excepción a R2): `WoldVirtualP2P3Dv2.7.1-linux.tar.gz`
   (1.110.302.810 B, `cd804744…cd280d1a`) y `SHA256SUMS`
   (`fb6a4383…ad04e1ff`) subidos con `--clobber`; el exe y `release.json` no se
   tocaron y los cuatro `digest` de la API coinciden con los locales.
