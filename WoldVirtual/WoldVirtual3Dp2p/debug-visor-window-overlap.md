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

## 📊 Logs Collected
**Evidencia 1:** La ventana tiene dimensiones 1600x950 (nuestros cambios funcionaron)
**Evidencia 2:** GodotPlaceholder tiene dimensiones 0x0 al cargar (normal porque PanViewportContainer está Collapsed)
**Evidencia 3:** Los logs de GodotEmbedder.cs muestran: `Resize: widthPx = 1266, heightPx = 790`
**Evidencia 4:** Esto es aproximadamente 79% del ancho y 83% del alto de la ventana

**Análisis:**
1. **DPI Scaling:** Las dimensiones 1266x790 sugieren scaling de DPI (~1.25x)
2. **Layout Issue:** GodotPlaceholder no está llenando todo el espacio disponible
3. **Superposición:** Si Godot se renderiza a 1266x790 pero otros elementos están posicionados incorrectamente, podría haber superposición

**Hipótesis confirmada/refutada:**
- ✅ **H1a confirmada:** GodotPlaceholder tiene dimensiones incorrectas (1266x790 vs espacio disponible)
- 🔄 **H1b pendiente:** Necesito verificar si Godot respeta los límites del Grid
- 🔄 **H1c pendiente:** Necesito verificar si elementos del wizard permanecen visibles

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