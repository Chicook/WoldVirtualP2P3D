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
**Observación 1:** Los logs no se generaron porque la aplicación no llegó a ejecutar EnterDashboard()
**Observación 2:** EnterDashboard() solo se llama después de completar el wizard de 4 pasos o después de autenticación exitosa
**Observación 3:** El usuario reporta que Godot ya está tapando elementos, lo que sugiere que el viewport ya está activo

**Hipótesis revisada:**
1. **H1a:** GodotPlaceholder tiene dimensiones incorrectas desde el inicio
2. **H1b:** El contenedor de Godot no respeta los límites del Grid
3. **H1c:** Hay elementos del wizard que permanecen visibles y Godot se superpone sobre ellos

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