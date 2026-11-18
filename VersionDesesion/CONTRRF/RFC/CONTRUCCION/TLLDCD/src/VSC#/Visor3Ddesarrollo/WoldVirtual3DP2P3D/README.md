# WoldVirtualP2P3D · Vista preliminar 2.9.3

Reconstrucción pequeña e independiente para comprobar el alta DAO y la conexión con Lucía anfitriona. No modifica el visor 2.9.2 ni copia sus dependencias a esta carpeta.

## Módulos

- `Servidor/Modulos/Blockchain`: cadena local SHA-256 con prueba de trabajo; mina el bloque de inicio y un bloque por alta.
- `Servidor/Modulos/Dao`: conexión preliminar, alta, heartbeat y listado de participantes presentes. Lucía permanece como anfitriona en el origen de la sede.
- `Servidor/Modulos/Tuneles`: intenta Cloudflare Quick Tunnel y luego OpenSSH/localhost.run; informa de URL y estado.
- `Servidor/Modulos/IPC`: buzón JSON local por archivos compartidos entre Godot y el servidor; evita el socket de loopback. Los invitados remotos continúan por HTTPS a través del túnel.

La conexión local entre visor y servidor usa un buzón JSON por archivos compartidos, sin socket loopback. La conexión con otros usuarios sigue siendo cliente-anfitrión a través del endpoint HTTPS publicado por Lucía. No incluye todavía ICE/WebRTC ni una malla de transporte P2P directa; esa fase requiere negociación NAT y queda fuera de esta vista preliminar.

## Compilar

Desde la raíz del repositorio ejecuta `VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\CS\scripts\Compilar_2.9.3.ps1`. El preset está centralizado en `.dev\CS\config` y el script exporta desde una copia temporal aislada. Los paquetes NuGet, temporales, cachés, exportación y runtime de Godot se guardan bajo `CONTRUCCION\.dev\CS`. Se reutilizan Godot 4.7.2 y la plantilla Windows que ya están instalados; solo se copian a `.dev\CS`.

## Abrir

Después de compilar, ejecuta `VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\CS\scripts\Preparar_y_Abrir_Previa.ps1`. El visor arranca el servidor local. La blockchain de prueba se escribe en `.dev\CS\runtime\datos`.

Para desactivar el túnel mientras se prueba solo en local, configura `WVP_DISABLE_TUNNEL=1` antes de abrir. En una instalación publicada, la cadena se conserva en `%LOCALAPPDATA%\WoldVirtualP2P3D\2.9.3`.

La carpeta de cuenta `AppData\Local\WoldVirtualP2P3D\user` no forma parte de este prototipo; se revisará después del flujo de conexión para conservar las cuentas sin mantener ese directorio durante la sesión.




