# Debug Session: visor-window-overlap
**Status:** [OPEN]
**Created:** 2026-05-19
**Issue:** Las ventanas del visor se superponen, especialmente la ventana de Godot que tapa otros elementos del visor.

## 🎯 Problem Statement
El usuario reporta que:
1. Los cambios anteriores (aumentar dimensiones de ventanas) no resolvieron el problema
2. Las ventanas siguen en el mismo sitio
3. La ventana de Godot tapa cosas del visor
4. Los cambios no sirvieron de nada

## 🔍 Hypotheses
1. **H1: Z-order incorrecto** - La ventana de Godot tiene un z-order más alto que otros elementos y se superpone
2. **H2: Layout incorrecto** - El Grid/StackPanel no está organizando correctamente las ventanas
3. **H3: Godot viewport no respeta límites** - El contenedor de Godot no está limitado al área designada
4. **H4: Sidebar vs Viewport conflicto** - Cuando el sidebar está visible, el viewport no se ajusta
5. **H5: Wizard steps no se ocultan correctamente** - Los pasos del wizard permanecen visibles detrás del viewport

## 📋 Evidence Collection Plan
1. ✅ Instrumentar MainWindow.xaml.cs para registrar eventos de visibilidad
   - Agregada función LogDebug()
   - Agregados logs en EnterDashboard()
   - Agregados logs en GodotPlaceholder.SizeChanged
2. Instrumentar GodotEmbedder.cs para registrar dimensiones y posición
3. Ejecutar aplicación y registrar secuencia de eventos
4. Capturar estado de visibilidad de cada componente
5. Analizar dimensiones reales vs esperadas

### 3. Evidencia Recolectada (Logs)

**Logs de `visor_debug_overlap.log` (después de instrumentación):**
- `MainWindow constructor started`
- `InitializeComponent completed`
- `MainWindow_Loaded started`
- `Hardware fingerprint: ...`
- `Window dimensions on load: Width=1600, Height=950, ActualWidth=1600, ActualHeight=950`
- `GodotPlaceholder dimensions on load: ActualWidth=0, ActualHeight=0`
- `EnterDashboard called - isNewRegistration: True`
- `Window dimensions: Width=1600, Height=950`
- `Grid dimensions: ActualWidth=1600, ActualHeight=950`
- `Sidebar HIDDEN - Width: 0, Visibility: Collapsed (giving full space to Godot viewport)`
- `PanSidebar dimensions: ActualWidth=0, ActualHeight=845`
- `Viewport container shown - Visibility: Visible`
- `PanViewportContainer dimensions: ActualWidth=1600, ActualHeight=845`
- `GodotPlaceholder dimensions: ActualWidth=1600, ActualHeight=845`
- `Main Grid column 1 width: 1*`
- `Window client area: 1600x950`
- `GodotPlaceholder SizeChanged - ActualWidth=1600, ActualHeight=845`
- `ColSidebar Width=0, GridUnitType=Star`
- `PanViewportContainer dimensions: ActualWidth=1600, ActualHeight=845`
- `Step1_PC visibility: Collapsed, dimensions: ActualWidth=0, ActualHeight=0`
- `DPI: X=1.25, Y=1.25`
- `Godot resized to: 2000x1056`

**Logs de `visor_debug.log` (GodotEmbedder):**
- `Resize: widthPx = 1266, heightPx = 790` (¡Esto es lo que Godot recibe!)

### 4. Análisis de la Evidencia

1.  **Dimensiones de WPF correctas**: Los logs de `visor_debug_overlap.log` muestran que `PanViewportContainer` y `GodotPlaceholder` tienen `ActualWidth=1600` y `ActualHeight=845` (1600x950 - 60px header - 45px footer = 1600x845). Esto es lo esperado después de ocultar el sidebar.
2.  **Factor DPI**: Los logs muestran `DPI: X=1.25, Y=1.25`. Esto indica un escalado del 125%.
3.  **Cálculo de redimensionamiento**: En `MainWindow.xaml.cs`, se calcula `_viewer.Resize((int)(GodotPlaceholder.ActualWidth * dpi.X), (int)(GodotPlaceholder.ActualHeight * dpi.Y))`.
    -   `1600 * 1.25 = 2000`
    -   `845 * 1.25 = 1056.25` (redondeado a 1056)
    -   Los logs confirman: `Godot resized to: 2000x1056`.
4.  **Discrepancia en `GodotEmbedder`**: A pesar de que `MainWindow.xaml.cs` envía `2000x1056`, `GodotEmbedder.cs` recibe `1266x790`.

**Conclusión del análisis:**
El problema no es el cálculo en `MainWindow.xaml.cs` ni el DPI en sí. El problema es que la función `_viewer.Resize()` en `GodotEmbedder.cs` está recibiendo valores diferentes a los que se le envían. Esto sugiere que hay un problema en la comunicación entre WPF y el componente `GodotEmbedder`, o que `GodotEmbedder` está haciendo su propio escalado o ajuste.

**Revisando `GodotEmbedder.cs`:**
```csharp
public void Resize(int widthPx, int heightPx)
{
    Log($"Resize: widthPx = {widthPx}, heightPx = {heightPx}"); // Aquí se loguea 1266x790
    if (_containerHwnd == IntPtr.Zero || widthPx < 1 || heightPx < 1) return;
    
    bool ok1 = MoveWindow(_containerHwnd, 0, 0, widthPx, heightPx, true);
    Log($"Resize: MoveWindow(_containerHwnd) = {ok1}");
}
```
El log `Resize: widthPx = {widthPx}, heightPx = {heightPx}` es el primero en `GodotEmbedder.cs`. Si este log muestra `1266x790`, significa que esos son los valores que *recibe* la función `Resize`.

Esto es muy extraño, ya que `MainWindow.xaml.cs` claramente loguea que está *enviando* `2000x1056`.

**Posibles causas de la discrepancia:**
1.  **Conversión implícita o truncamiento**: Aunque se envía `int`, podría haber algún tipo de conversión o truncamiento intermedio.
2.  **Múltiples llamadas a `Resize`**: Podría haber otra llamada a `_viewer.Resize` con valores diferentes que no estamos viendo en los logs actuales.
3.  **Problema de threading/sincronización**: Si `_viewer.Resize` se llama desde un hilo diferente o hay un retraso, podría haber un estado inconsistente.
4.  **Error en la función `Log` de `GodotEmbedder`**: Poco probable, pero posible.

### 5. Plan de Instrumentación (Actualizado)

Para entender por qué `GodotEmbedder.cs` recibe `1266x790` cuando se le envía `2000x1056`, necesito instrumentar `GodotEmbedder.cs` más a fondo.

**Acciones:**
1.  **Agregar logs en `GodotEmbedder.cs`** para verificar los valores de `widthPx` y `heightPx` *inmediatamente* al inicio de la función `Resize`.
2.  **Verificar si hay otras llamadas a `_viewer.Resize`** en el código.

**Archivos a instrumentar:**
-   `d:\WCVcoinMTB\WoldVirtual\WoldVirtual3Dp2p\Capa3_Visor\GodotEmbedder.cs`

**Puntos de instrumentación:**
-   **Dentro de `GodotEmbedder.cs` en la función `Resize`**:
    -   Loguear `widthPx` y `heightPx` al inicio de la función.
    -   Loguear el valor de `_containerHwnd`.
    -   Loguear el resultado de `MoveWindow`.

### 6. Evidencia a Recolectar

-   Logs de `GodotEmbedder.cs` mostrando los valores de `widthPx` y `heightPx` recibidos, el estado de `_containerHwnd` y el resultado de `MoveWindow`.

### 7. Análisis de la Evidencia (futuro)

-   Comparar los valores recibidos en `GodotEmbedder.cs` con los valores enviados desde `MainWindow.xaml.cs`.
-   Determinar si `MoveWindow` está fallando o si los valores de entrada son incorrectos.
-   Identificar si hay otras llamadas a `_viewer.Resize` que estén sobrescribiendo los valores.

### 8. Solución Propuesta (futura, basada en análisis)

-   Ajustar el cálculo de redimensionamiento o la lógica de `GodotEmbedder.cs` para asegurar que Godot se redimensione a las dimensiones correctas (2000x1056 en este caso, o las dimensiones completas del `GodotPlaceholder` en píxeles físicos).
-   Asegurar que el z-order sea correcto y que Godot no se superponga con otros elementos.

## 🔧 Fixes Applied
*No fixes applied yet*

## 📈 Progress
- [x] Step 1: Create debug session file
- [ ] Step 2: List falsifiable hypotheses
- [ ] Step 3: Instrument code for evidence collection
- [ ] Step 4: Run application and collect logs
- [ ] Step 5: Analyze evidence
- [ ] Step 6: Implement fix
- [ ] Step 7: Verify fix
- [ ] Step 8: Clean up instrumentation
- [ ] Step 9: Document root cause
- [ ] Step 10: User confirmation
- [ ] Step 11: Session closure

## 🎯 Root Cause Analysis
*Pending*

## 📝 Notes
El usuario quiere que "la del metaverso no tape nada" - la ventana de Godot/3D no debe superponerse con otros elementos del visor.