# Visor Wold Virtual P2P 3D (WPF + Godot) — Estado y Plan (DevTraeIA)

Este documento refleja el estado real del repositorio y define un plan de implementación y corrección de errores enfocado en el síntoma crítico: pantalla negra en el área embebida de Godot dentro del visor WPF.

## Estado actual (lo que ya existe)

### Proyectos y piezas principales
- Visor WPF: `Capa3_Visor/CapaVisor3D` (app `VisorSingularity`)
- Servidor WPF: `Capa3_Visor/ServidorVirtualCS`
- Embed de Godot en WPF: `Capa3_Visor/CapaVisor3D/GodotHwndHost.cs`
- Lanzamiento + detección de ventana Godot: `Capa3_Visor/CapaVisor3D/Services/GodotLauncherService.cs`
- Resolución de rutas (project + exe Godot): `Capa3_Visor/CapaVisor3D/Services/GodotProjectLocator.cs`
- Orquestación de sesión: `Capa3_Visor/CapaVisor3D/Services/MetaverseSessionController.cs`

### UI actual (XAML)
El XAML del visor no es un “wizard separado + viewport” como una maqueta; es un conjunto de pantallas en la misma ventana con `Visibility`:
- `GridPcRegistration` (registro hardware)
- `GridUserRegistration` (registro usuario)
- `GridLoginScreen` (login por ZIP/credenciales)
- `GridMainViewer` (visor principal + área 3D)

En `GridMainViewer`, el área de render 3D se define así:
- Contenedor visible: un `Border` con fondo negro.
- Placeholder destino: `Grid x:Name="GodotPlaceholder"` donde se inserta el `GodotHwndHost`.

Archivo: `Capa3_Visor/CapaVisor3D/MainWindow.xaml`

### Flujo real de embebido (code-behind)
El flujo de “entrar al metaverso” actual hace lo siguiente:
1. Muestra `GridMainViewer`.
2. Llama a `LaunchAndEmbedGodot(wallet, user, island, scenePath)`.
3. Limpia `GodotPlaceholder.Children`.
4. Lanza proceso Godot (con args, driver `opengl3`, resolución inicial calculada).
5. Escanea ventanas del proceso, elige un HWND.
6. Crea `GodotHwndHost(godotHwnd)` y lo agrega a `GodotPlaceholder.Children`.

Archivo: `Capa3_Visor/CapaVisor3D/MainWindow.xaml.cs`

### Red P2P y servicios ya integrados
Dentro del visor ya hay infraestructura bastante avanzada:
- Puente HTTP local (MetaMask) puerto `8080` para login/registro.
- WebNode local y publicación de puerto WS en `Estado_Global/ws_port.txt`.
- Sincronización LAN (peers) y broadcast al WS para consumo por Godot.
- Chat UDP (`UdpChatService`) y UI de chat.
- Telemetría de red (`NetworkTelemetryService`).

## Problema crítico (síntoma)
La zona 3D del visor queda negra cuando debería verse Godot embebido.

## Hallazgos técnicos (evidencia directa del código)

### 1) Selección de HWND de Godot potencialmente incorrecta
`GodotLauncherService.ScanForGodotWindow(...)` elige la ventana con una condición muy amplia:
- Acepta className `"Engine"` o “cualquier ventana cuyo título no contenga Console/Select”.
Esto puede seleccionar una ventana no-render (auxiliar) o una ventana incorrecta del proceso.

Archivo: `Capa3_Visor/CapaVisor3D/Services/GodotLauncherService.cs`

### 2) ErrorDataReceived no está conectado
Se redirige `StandardError` y se llama `BeginErrorReadLine()`, pero no se subscribe a `process.ErrorDataReceived`.
Consecuencia: se pierden errores críticos de Godot (render, argumentos, fallos de escena) y el diagnóstico queda ciego.

Archivo: `Capa3_Visor/CapaVisor3D/Services/GodotLauncherService.cs`

### 3) Dependencia de timing/layout al cambiar pantallas
`GridMainViewer` se muestra y, en el mismo salto de UI, se lanza Godot.
Aunque la resolución se clampa a mínimo, el host WPF puede estar aún estabilizando layout al insertar el `HwndHost`.

Archivo: `Capa3_Visor/CapaVisor3D/MainWindow.xaml.cs`

### 4) Señales de corrupción de encoding en UI/strings
Hay segmentos con texto “mojibake” (`Ã¢â€`, etc.) en el code-behind, que indica problemas de codificación del archivo o contenido pegado con encoding incorrecto.
No necesariamente causa pantalla negra, pero sí es un bug real que afecta UX y mantenimiento.

Archivo: `Capa3_Visor/CapaVisor3D/MainWindow.xaml.cs`

## Plan de corrección (prioridad: que Godot se vea)

### Fase 0 — Reproducibilidad y diagnóstico mínimo (sin rediseñar UI)
- Capturar evidencias en logs del visor:
  - argumentos exactos de lanzamiento,
  - PID de Godot,
  - lista de ventanas candidatas detectadas (HWND, className, title, visible),
  - ventana elegida para embebido.
- Conectar `ErrorDataReceived` y volcar stderr al mismo canal de diagnóstico.
- Asegurar que el visor no “finge éxito” si no hay HWND válido.

Objetivo: saber si el problema es “no hay render” vs “se eligió mal la ventana” vs “render driver/scene”.

### Fase 1 — Fijar selección del HWND correcto (causa probable)
- Endurecer el filtro de ventana:
  - preferir ventanas top-level visibles del proceso,
  - preferir className esperado (por ejemplo `Godot`/`SDL_app`/`GLFW*` según build),
  - evitar ventanas tool/owner/auxiliares,
  - escoger la de mayor área si hay varias.
- Guardar (en log) className/título real observado en ejecución para ajustar el matcher.

Resultado esperado: el `GodotHwndHost` se parenta a la ventana correcta.

### Fase 2 — Robustez de embebido (DPI, resize, foco)
- Forzar un “layout settle” antes de insertar el `HwndHost`:
  - `UpdateLayout()` y una espera corta en Dispatcher antes de lanzar o antes de `Children.Add`.
- Reforzar resize:
  - llamar explícitamente a `ResizeToActualPixels()` tras el `Children.Add` y en `SizeChanged` del placeholder/contenedor.
- Revisar foco/teclado:
  - confirmar que el forward de mensajes no está anulando eventos o dejando el child sin input.

Resultado esperado: el canvas 3D no queda en 1x1 ni en tamaño incorrecto, y responde al resize/DPI.

### Fase 3 — Render driver y argumentos (fallback controlado)
- Validar si `--rendering-driver opengl3` es compatible con “reparenting” en el build actual de Godot.
- Implementar fallback automático:
  - si hay error de render en stderr o ventana no muestra contenido, reintentar con driver alternativo soportado por el build.
- Validar que el scenePath/args son correctos para el runtime actual de Godot.

Resultado esperado: incluso si un driver falla, el visor muestra Godot con otro.

### Fase 4 — Rediseño XAML (solo si todavía hay clipping/overlay/layout problemático)
El XAML actual ya es relativamente directo en el área 3D (un `Border` + `Grid GodotPlaceholder`).
El rediseño completo se deja como medida secundaria si se confirma que el problema proviene del layout (no del HWND/driver).

## Plan de corrección de errores (lista concreta)

### Bugs de alta prioridad
- Pantalla negra: corregir selección de HWND + capturar stderr + robustecer el ciclo de embebido.
- Diagnóstico incompleto: conectar `ErrorDataReceived` y registrar salida.

### Bugs de prioridad media
- Corruptelas de encoding en textos/strings del visor: normalizar a UTF-8 y corregir cadenas visibles.
- Inconsistencias de “estado UI” (barras ocultas/visibles) al entrar por login vs registro: consolidar activación de UI.

### Riesgos a vigilar
- Reparenting + OpenGL/Vulkan: ciertos drivers/builds pueden renderizar negro al ser reparentados.
- Multiplicidad de ventanas Godot (console, selector, debug): el selector de HWND debe ser determinista.

## Criterios de aceptación (definición de “arreglado”)
- El área `GodotPlaceholder` muestra el render de Godot de forma consistente tras entrar al metaverso.
- El render sobrevive a `resize` de ventana y a cambios de DPI sin degradarse a negro.
- Si Godot falla al iniciar/renderizar, el visor registra la causa (stderr) y da feedback claro (sin quedar “negro silencioso”).

## Checklist de pruebas
- Flujo registro: PC → usuario → MetaMask → entra al metaverso → se ve Godot.
- Flujo login: ZIP/credenciales → MetaMask → entra al metaverso → se ve Godot.
- Resize: maximizar, restaurar, cambiar proporción.
- DPI: ejecutar con escala 100% y >100% (si el sistema lo permite).
- Robustez: cerrar visor mientras Godot arranca y confirmar cierre limpio del proceso.

**Última actualización**: 2026-06-29
