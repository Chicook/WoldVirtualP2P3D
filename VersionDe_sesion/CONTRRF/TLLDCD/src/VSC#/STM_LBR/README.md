# STM_LBR — arranque de WoldVirtualP2P3D en Linux

Creado el 2026-10-29 a raíz de este intento real en wine-cachyos 10.0:

```
wine /home/meme/Descargas/DMWoldVirtualP2P3Dv2.6.8.exe
0024:err:module:find_forwarded_export module not found for forward
      'icuuc68.u_charsToUChars_68' used by L"C:\windows\system32\icu.dll"
Cannot get symbol u_charsToUChars from libicuuc
Error: 127
```

## Antes de nada: con qué se compila el visor

**Con .NET, no con Godot.** El visor es un WPF `net8.0-windows` publicado con
`dotnet publish -c Release -r win-x64 --self-contained true`: un único exe que
lleva dentro el runtime de .NET. Godot **no compila nada**; va empaquetado como
recurso embebido del exe y se extrae al arrancar:

| Pieza | Dentro del exe | En disco al arrancar |
|---|---|---|
| Motor | `godot_exe.zip` → `Godot_v4.7.2-stable_win64.exe` | `%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\<versión>\Servidor3D\` |
| Mundo | `wvp3d.pck` (1.053.081.932 B, SHA-256 `8d42b2d3…019fdede`) | `%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\<versión>\wvp3d.pck` |

El motor se lanza como `Godot_v4.7.2-stable_win64.exe --main-pack "<pck>" -- <args de red>`.
Ese detalle es el que hace posible la vía nativa de más abajo: **el mundo es
neutro de plataforma**, sólo es de Windows la carcasa WPF.

## Por qué falla bajo Wine

.NET 8 inicializa la globalización cargando el ICU del sistema antes de ejecutar
una sola línea del visor. El `icu.dll` de Wine reenvía los símbolos a `icuuc68`,
que no existe en ese paquete, y el proceso muere con 127. No es un fallo del
visor: no llega a arrancar.

La salida es decirle a .NET que no use ICU. Hay dos vías y cuál funciona depende
de la compilación de Wine:

- `DOTNET_SYSTEM_GLOBALIZATION_USENLS=1` → usa las API de locale de `kernel32` (Wine las tiene).
- `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` → sin datos de cultura (fechas y números en formato invariante).

## Qué hay en esta carpeta

| Archivo | Para qué |
|---|---|
| `woldvirtual-wine.sh` | Arranca el exe bajo Wine con un prefix propio, prueba las estrategias de globalización hasta que el runtime arranca y guarda la que funciona. Con `--motor` lanza el mundo 3D bajo Wine saltándose la UI WPF. |
| `woldvirtual-linux.sh` | Arranca el mundo con **Godot de Linux nativo** + `wvp3d.pck`. Busca motor y mundo, avisa si el tamaño o la huella no son los publicados y admite `--dry-run` y `--verificar`. |
| `diagnostico.sh` | Informe del equipo (distro, Wine, ICU, exe, ruta nativa) y sondeo real del runtime con cada estrategia. Pensado para pegar tal cual. |

Los tres aceptan `--ayuda`. Ningún guión toca el prefix de Wine del usuario:
usan `~/.local/share/woldvirtual-p2p3d/wineprefix` salvo que se indique
`--prefix` o `WOLD_WINEPREFIX`. Los registros van a `~/.local/state/woldvirtual/`.

## Uso

```bash
cd VersionDe_sesion/CONTRRF/TLLDCD/src/VSC#/STM_LBR
chmod +x *.sh

./diagnostico.sh                                   # qué falla en este equipo
./woldvirtual-wine.sh --exe ~/Descargas/DMWoldVirtualP2P3Dv2.7.1.exe
./woldvirtual-linux.sh --pck /ruta/wvp3d.pck --godot /ruta/Godot_v4.7.2-stable_linux.x86_64
./woldvirtual-linux.sh -- --peer-url="<url de invitación>"   # entrar en la sesión de otro PC
```

En el paquete de Linux de la release (`WoldVirtualP2P3Dv2.7.1-linux.tar.gz`) el
motor y el mundo ya vienen dentro: `motor/Godot_v4.7.2-stable_linux.x86_64` y
`mundo/wvp3d.pck`, y `woldvirtual-linux.sh` los encuentra solo porque están junto
al guión. Si se usan estos ficheros sueltos del repositorio, el `wvp3d.pck` se
copia de un PC con el visor instalado
(`%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\<versión>\wvp3d.pck`) o del árbol de
compilación (`CONTRRF/TLLDCD/src/VSC#/wvp3d.pck`, no versionado), y Godot 4.7.2
para Linux se baja de godotengine.org/download/linux/
(`Godot_v4.7.2-stable_linux.x86_64.zip`).

## Qué funciona en Linux y qué no

| Parte | Estado |
|---|---|
| Runtime .NET bajo Wine | **Arreglable**: con NLS o globalización invariante el fallo de ICU desaparece. |
| Interfaz WPF bajo Wine | **No soportada**. WPF sólo existe en Windows; puede no pintar o cerrarse. No hay arreglo desde esta carpeta. |
| Registro, SMTPLC, perfil | **Sólo Windows.** SMTPLC consulta WMI (`Win32_ComputerSystem`, `Win32_BIOS`, `Win32_DiskDrive`) y claves de `HKLM`; Wine implementa WMI sólo en parte, así que el resultado del registro bajo Wine está **sin verificar**. |
| Webcam | **No bajo Wine**: Wine no expone cámaras por DirectShow. El visor ya no se limita a decir «no hay webcam», ahora explica que está bajo Wine (arreglo en `Chat/ChatWebcam.cs`). |
| Mundo 3D (Godot + `wvp3d.pck`) | **Sí en Linux nativo**: es la vía real. Sin la carcasa C# no hay túnel P2P automático ni relay de chat; el mundo arranca en modo local y la sesión remota se pasa a mano con `--peer-url=` / `--client --ip= --port=`. |

## Qué se ha probado

- **Probado (Windows, con dobles de `wine` y `godot`)**: 9 casos — ICU roto agota
  las tres estrategias y sale 127 con las instrucciones; runtime correcto acepta
  la primera estrategia y la guarda; `wineboot` roto avisa y sigue; `--dry-run`;
  modo `--motor`; búsqueda de motor y mundo; aviso de tamaño y huella distintos;
  paso de argumentos de red con y sin `--`; sondeos del diagnóstico con Wine
  correcto y con ICU roto. Sintaxis revisada con `bash -n`.
- **Pendiente: validación en un Linux real.** Estos guiones no se han ejecutado
  en wine-cachyos; falta confirmar allí qué estrategia levanta el runtime y si
  la ventana WPF llega a pintar. `./diagnostico.sh` es el paso que da esa
  respuesta y su informe es lo que hay que pegar de vuelta.

## Alcance

Estos guiones no forman parte del exe de Windows: son ficheros externos que
viven en `STM_LBR/` y que desde la 2.6.9 se publican también como el asset de
Linux de la release (hoy `WoldVirtualP2P3Dv2.7.1-linux.tar.gz`). El arreglo de la
webcam de la sesión de la 2.6.9 sí es código del visor (`Chat/ChatWebcam.cs`) y
**sí** va dentro de `DMWoldVirtualP2P3Dv2.7.1.exe`; no estaba en el de la 2.6.8.
