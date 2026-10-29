# STM_LBR — el visor de WoldVirtualP2P3D en Linux

El paquete de Linux de la release (`WoldVirtualP2P3Dv2.7.1-linux.tar.gz`) ya no
lleva sólo el mundo de Godot: lleva **el visor completo adaptado a Linux**, la
misma versión 2.7.1 del exe de Windows (selector de avatares, shape keys,
animaciones de las 24 plazas y el sistema de construcción modular), recompilada
con Avalonia en lugar de WPF.

```
WoldVirtualP2P3Dv2.7.1/
├── woldvirtual-linux          visor completo: interfaz + motor Godot 4.7.2 + wvp3d.pck
├── woldvirtual-linux.sh       lanzador: arranca el visor o, con --motor, sólo el mundo
├── diagnostico.sh             informe del equipo + sondeo del visor (--comprobar)
├── woldvirtual-wine.sh        vía antigua: el exe de Windows bajo Wine
└── README.md
```

El motor y el mundo **ya no van sueltos**: van embebidos dentro de
`woldvirtual-linux`, igual que el exe de Windows lleva `godot_exe.zip` y
`wvp3d.pck` dentro. Se extraen la primera vez (≈1,2 GB) a
`~/.local/share/WoldVirtualP2P3D/runtime/<versión>/` y de ahí los lanza el visor.

## Qué trae el visor Linux

Siete pestañas, las mismas funciones del visor de Windows salvo las que dependen
de APIs exclusivas de Windows (ver «Qué no trae» más abajo):

| Pestaña | Qué hace |
|---|---|
| Cuenta | Registro local, desbloqueo con contraseña, recuperación con frase BIP-39 y perfil. |
| Mundo | Estado del motor, destino manual, lanzar como anfitrión o como invitado, consola del motor. |
| Portal | Portal WebNodo (puerto 3030, con reserva 3031-3040), URL pública del túnel y enlace de invitación. |
| Red P2P | Túnel, pares conectados y búsqueda de nodos en la LAN (baliza UDP 8912). |
| Chat | Relay local (8920), mensajes, presentes, amigos y privados. |
| Actualizar | Consulta de releases en GitHub, descarga verificada por SHA-256 del `.tar.gz` de Linux. |
| Diagnóstico | Versión, rutas, estado de cuenta, portal, túnel, chat, red, PID del motor y últimas 30 líneas del registro. |

Comparte con el exe de Windows el mismo núcleo de código (`Services`, `RedP2P`,
`Chat`, `Seguridad`, `STM_actualizar`), enlazado como archivos del proyecto, así
que la lógica de sesión, invitación y chat no está duplicada.

## La parte 3D también va dentro

| Pieza | Dónde viaja | Dónde queda al extraer |
|---|---|---|
| Motor `Godot_v4.7.2-stable_linux.x86_64` (146.414.384 B) | dentro de `woldvirtual-linux` (`godot_linux.zip`) | `~/.local/share/WoldVirtualP2P3D/runtime/<versión>/Servidor3D/` |
| Mundo `wvp3d.pck` (1.053.081.932 B, SHA-256 `8d42b2d3…019fdede`) | dentro de `woldvirtual-linux` (`wvp3d.pck`) | `~/.local/share/WoldVirtualP2P3D/runtime/<versión>/wvp3d.pck` |

La extracción ocurre la primera vez que se abre el mundo (o con el botón
**Preparar mundo 3D**), en segundo plano y con un marcador `.extracted` por
versión: al actualizar el visor se vuelve a extraer, y las versiones viejas del
runtime se borran salvo la última que arrancó bien. `WOLD_RUNTIME_DIR` redirige
la carpeta (pruebas y modo portable).

`woldvirtual-linux --extraer` hace lo mismo sin abrir ventana y escribe las rutas
como `MOTOR=…` y `PCK=…`; `woldvirtual-linux.sh --motor` lo usa cuando no
encuentra motor o mundo sueltos.

## Rutas en Linux

| Qué | Dónde |
|---|---|
| Perfil, cuenta, amigos, registro | `~/.local/share/WoldVirtualP2P3D/` (`PerfilUsuario.BaseDir`) |
| Motor y mundo extraídos | `~/.local/share/WoldVirtualP2P3D/runtime/<versión>/` |
| `user://` del motor | `~/.local/share/godot/app_userdata/WoldVirtualP2P3D/` |
| Actualizaciones descargadas | `~/.local/share/WoldVirtualP2P3D/actualizaciones/` |
| Registro del visor | `~/.local/state/woldvirtual/` |
| Prefix de Wine (vía antigua) | `~/.local/share/woldvirtual-p2p3d/wineprefix` |

`XDG_DATA_HOME` y `XDG_STATE_HOME` mandan si están definidos. No se reutiliza
ninguna carpeta de Windows.

## Uso

```bash
tar xzf WoldVirtualP2P3Dv2.7.1-linux.tar.gz
cd WoldVirtualP2P3Dv2.7.1
chmod +x woldvirtual-linux woldvirtual-linux.sh diagnostico.sh woldvirtual-wine.sh

./woldvirtual-linux --comprobar      # sin ventana: rutas, cuenta, portal, actualizaciones, LAN
./woldvirtual-linux --extraer        # extrae motor y mundo del visor y muestra las rutas
./woldvirtual-linux.sh               # el visor completo
./diagnostico.sh                     # informe del equipo para pegar tal cual
```

`woldvirtual-linux.sh` busca el visor junto a sí mismo y lo ejecuta; si no está,
cae al modo mundo directo. Todos los guiones aceptan `--ayuda`.

## Modo mundo directo

Para abrir sólo el mundo 3D sin el visor (por ejemplo, en un equipo que sólo va
a ser invitado):

```bash
./woldvirtual-linux.sh --motor -- --peer-url="<url de invitación>"
./woldvirtual-linux.sh --motor -- --client --ip=<ip> --port=<puerto>
./woldvirtual-linux.sh --pck /ruta/wvp3d.pck --godot /ruta/Godot_v4.7.2-stable_linux.x86_64
```

En este modo no hay túnel P2P automático ni relay de chat: la sesión remota se
pasa a mano. El mundo es neutro de plataforma; lo único que cambia es quién le
pasa los argumentos. Si no hay motor ni mundo sueltos junto al guión, el propio
guión pide al visor que los extraiga (`--extraer`) antes de arrancar.

## Qué no trae el visor Linux

| Pieza | Motivo |
|---|---|
| Chat de voz y webcam | Dependen de DirectShow/NAudio y AForge, que en Linux no existen. La pestaña Chat funciona por texto; no hay captura de audio ni de vídeo. |
| Huella SMTPLC de Windows | El registro de Windows lee WMI y claves `HKLM`. En Linux el identificador del equipo se deriva del `machine-id` del sistema; el formato es el mismo, la fuente no. |
| Motor incrustado en la ventana | En Windows el mundo se abre dentro de la UI WPF. En Linux se lanza como proceso aparte con su propia ventana. |
| Aplicar la actualización solo | Se descarga y se verifica, pero el `.tar.gz` se extrae a mano: el visor no puede reemplazar su propio binario mientras corre. |

## Vía antigua: el exe de Windows bajo Wine

`woldvirtual-wine.sh` sigue en la carpeta para quien quiera intentar el exe
original. Arranca con un prefix propio, prueba las estrategias de globalización
hasta que el runtime arranca y guarda la que funciona.

Por qué fallaba: .NET 8 inicializa la globalización cargando el ICU del sistema
antes de ejecutar una línea del visor, y el `icu.dll` de Wine reenvía los
símbolos a un `icuuc68` que no existe en ese paquete; el proceso muere con 127.
`DOTNET_SYSTEM_GLOBALIZATION_USENLS=1` (API de locale de `kernel32`) o
`DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` (sin datos de cultura) lo evitan.

Aun así, **WPF no existe en Linux**: la ventana puede no pintar o cerrarse, y no
hay arreglo desde estos guiones. Por eso la vía buena es el visor Avalonia; Wine
queda como recurso de diagnóstico.

## Con qué se compila cada cosa

| Pieza | Compilación |
|---|---|
| Exe de Windows | .NET 8 WPF `net8.0-windows`, `dotnet publish -c Release -r win-x64 --self-contained true`. Godot no compila nada: va como recurso embebido (`godot_exe.zip`, `wvp3d.pck`) y se extrae al arrancar. |
| Visor Linux | .NET 8 con Avalonia 11 `net8.0`, `dotnet publish -c Release -r linux-x64 --self-contained true -p:PublishSingleFile=true`. Skia y HarfBuzz van dentro del binario, y también `godot_linux.zip` + `wvp3d.pck` como recursos embebidos (`-p:SkipGodotAssets=true` compila la UI sin ellos). Proyecto: `src/VSC#/VisorLinux/`. |
| Mundo | El mismo `wvp3d.pck` en las dos plataformas. |

## Qué se ha probado

- **Verificado (Windows, 2026-10-29)**
  - `VisorLinux` compila sin advertencias ni errores y publica un ELF x86-64
    autocontenido de 1.221.369.510 B (cabecera `7f 45 4c 46`), con el motor y el
    PCK dentro.
  - La extracción de la parte 3D se probó con la publicación de Windows del
    mismo código (`--extraer` con `WOLD_RUNTIME_DIR` redirigido): el PCK sale con
    la huella publicada (`8d42b2d3…019fdede`), el motor byte a byte idéntico y el
    marcador `.extracted` escrito; la segunda pasada tarda 0,1 s.
  - `woldvirtual-linux --comprobar` pasa en Windows: motor y PCK encontrados,
    línea `runtime:` con ruta y estado, portal WebNodo arriba con
    `/api/p2p-status`, consulta de releases correcta, baliza LAN escuchada.
  - La consulta de actualizaciones elige `WoldVirtualP2P3Dv2.7.1-linux.tar.gz`
    cuando la versión local es 2.7.0, y no propone nada con la 2.7.1.
  - La ventana arranca con título «Wold Virtual P2P 3D - visor Linux 2.7.1» y
    responde.
  - El proyecto WPF de Windows sigue compilando después de excluir `VisorLinux\**`.
  - Los guiones del paquete revisados con `bash -n`.
  - El tar del paquete guarda los permisos esperados: `woldvirtual-linux` y los
    tres `.sh` en 0755; este README en 0644. No lleva `motor/` ni `mundo/`
    sueltos, y el visor extraído del tar coincide byte a byte con el publicado.
- **No verificable desde este equipo:** Git Bash de Windows devuelve `-x` falso
  para cualquier archivo (montaje sin bits POSIX), así que aquí no se puede
  ejercitar la rama que delega en el visor, el permiso 0755 que se pone al motor
  extraído ni la búsqueda del motor por `-x`. Esas ramas se apoyan en los
  permisos del tar y en `File.SetUnixFileMode`, que sí están comprobados.
- **Pendiente: ejecución en un Linux real.** No hay WSL ni máquina Linux en este
  equipo, así que el binario ELF no se ha ejecutado aquí. Falta confirmar en
  wine-cachyos (o la distro que se use) que la ventana Avalonia pinta, que la
  extracción deja el motor ejecutable, que el motor arranca desde la pestaña
  Mundo y que el chat conecta. `./diagnostico.sh` y
  `./woldvirtual-linux --comprobar` son los dos pasos que dan esa respuesta; su
  salida es lo que hay que pegar de vuelta.

## Alcance

`STM_LBR/` es la carpeta de referencia de estos guiones; el paquete publicado se
arma desde `E:/areadetrabajo/wvp271/linux/`. El código del visor Linux vive en
`src/VSC#/VisorLinux/` y **no** entra en el exe de Windows: `Visor3D.csproj`
excluye esa carpeta. El arreglo de webcam de la 2.6.9 y todo lo de la 2.7.x son
código compartido y sí van dentro de `DMWoldVirtualP2P3Dv2.7.1.exe`.
