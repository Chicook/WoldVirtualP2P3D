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

---

## Plan de Desarrollo: Interconexión de Islas "Desde el Lecho Marino"

#### **Objetivo Principal:**
Permitir que las islas de diferentes usuarios (`1 usuario "pc-visor" = 1 isla 3D`) aparezcan unidas visualmente desde el lecho marino, creando un mundo continuo y navegable.

#### **Fase 0: Análisis y Diseño de Concepto (Teórico)**
1.  **Definir "Unidas desde el Lecho Marino":**
    *   **Visual:** ¿Implica un modelo 3D de "lecho marino" que conecta las islas? ¿Cómo se gestiona la topología (malla, hexágonos, etc.)?
    *   **Físico:** ¿Los avatares pueden caminar/nadar entre islas a través de este lecho marino? ¿Cómo afecta a la física y la navegación?
    *   **Lógico:** ¿Cómo se determina qué islas son "vecinas" y cómo se gestionan las transiciones de datos entre ellas?
2.  **Modelo de Datos de Islas Conectadas:**
    *   Extender `PeerSchema.cs` para incluir coordenadas espaciales de la isla (ej. `Vector3 Position`, `float RotationY`).
    *   Añadir un identificador de "tipo de lecho marino" o "bioma" para la conexión visual.
    *   Considerar un sistema de "puertos" o "puntos de conexión" definidos por el usuario en cada isla.
3.  **Estrategia de Carga/Descarga:**
    *   ¿Se cargan las islas adyacentes completas o solo sus "bordes" de conexión?
    *   ¿Cómo se gestiona la memoria y el rendimiento con múltiples islas cargadas?

#### **Fase 1: Extensión del Protocolo P2P para Geometría de Islas**
1.  **Modificar `PeerSchema.cs`:**
    *   Añadir campos para la posición 3D de la isla (ej. `IslandPositionX`, `IslandPositionY`, `IslandPositionZ`).
    *   Añadir campos para la orientación de la isla (ej. `IslandRotationY`).
    *   Añadir un campo `IslandBiomeType` para definir el tipo de conexión visual (arena, roca, coral, etc.).
2.  **Actualizar `PeerSyncService.cs`:**
    *   Asegurar que los nuevos datos de posición/orientación/bioma de la isla se sincronicen entre peers.
    *   Implementar lógica para detectar "islas adyacentes" basándose en las coordenadas sincronizadas.
3.  **Actualizar `MetaverseSessionController.cs`:**
    *   Gestionar el estado espacial de la isla local y las islas de los peers.
    *   Proveer una API para que Godot consulte las islas adyacentes y sus propiedades.

#### **Fase 2: Implementación en Godot - Renderizado de Conexiones**
1.  **Modificar `NetworkLayer.gd`:**
    *   Recibir y procesar los datos de posición y bioma de las islas adyacentes desde el WebSocket.
    *   Desarrollar una lógica para instanciar "conectores de lecho marino" entre la isla local y las islas adyacentes.
2.  **Desarrollar Lógica de "Lecho Marino" en Godot:**
    *   Crear un sistema de "chunks de conexión" o "mallas de lecho marino" que se generen dinámicamente entre islas.
    *   Implementar shaders y materiales para el renderizado del lecho marino según el `IslandBiomeType`.
    *   Asegurar que las transiciones visuales y físicas entre la isla y el lecho marino sean fluidas.
3.  **Ajustar `ChunkManager.gd`:**
    *   Extender la lógica de carga/descarga de chunks para incluir los chunks de conexión del lecho marino.
    *   Optimizar la gestión de recursos para evitar sobrecarga al renderizar múltiples islas y sus conexiones.
4.  **Navegación y Física:**
    *   Asegurar que el avatar pueda moverse sin problemas entre la isla y el lecho marino, y entre islas adyacentes.
    *   Considerar la implementación de zonas de "agua" en el lecho marino con física de natación.

#### **Fase 3: Integración en WPF - Gestión de Múltiples Islas**
1.  **Actualizar `MainWindow.xaml.cs` y UI:**
    *   Si es necesario, modificar la UI para mostrar un mapa simplificado o una lista de islas conectadas.
    *   Implementar eventos o comandos para que el usuario pueda interactuar con las islas adyacentes (ej. teletransporte, vista previa).
2.  **Gestión de Estado de Sesión:**
    *   Asegurar que el `MetaverseSessionController` pueda manejar el estado de múltiples islas y sus conexiones de manera coherente.

#### **Fase 4: Pruebas y Optimización**
1.  **Pruebas de Conectividad:**
    *   Verificar que las islas se detectan y conectan correctamente a través del lecho marino.
    *   Probar la sincronización de posición y estado entre usuarios en diferentes islas conectadas.
2.  **Pruebas Visuales:**
    *   Asegurar que el renderizado del lecho marino sea continuo y estéticamente agradable.
    *   Verificar que no haya artefactos visuales o clipping al moverse entre islas.
3.  **Pruebas de Rendimiento:**
    *   Optimizar la carga de recursos y el renderizado para mantener un framerate aceptable con múltiples islas.
    *   Identificar y resolver cuellos de botella en la red o el motor de renderizado.
4.  **Pruebas de Navegación:**
    *   Confirmar que el movimiento del avatar entre islas y a través del lecho marino es fluido y sin errores.

**Última actualización**: 2026-06-29
