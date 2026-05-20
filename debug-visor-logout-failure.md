# Debug Session: visor-logout-failure

## 📋 Session Information
- **Session ID**: visor-logout-failure
- **Start Time**: 2026-05-20
- **Issue**: Botón de cerrar sesión no funciona en el visor
- **User Report**: "nada no funciona el boton de cerrar sesion nada de lo que hiciste afecto en lo mas minimo al visor"

## 🎯 Problem Description
El usuario reporta que el botón de cerrar sesión en el visor no funciona. A pesar de las modificaciones implementadas anteriormente (mejoras en el manejo de eventos, desuscripción de eventos Exited, mejor logging), el problema persiste completamente.

## 🔍 Hypotheses (Falsifiable)
1. **H1: El botón no está correctamente vinculado al evento click** - El manejador de eventos `BtnCerrarSesion_Click` no se está ejecutando cuando se hace clic en el botón
2. **H2: El proceso Godot no se está terminando correctamente** - Los métodos `Kill()` o `WaitForExit()` no están funcionando como se espera
3. **H3: Hay múltiples instancias de Godot ejecutándose** - Solo se está terminando una instancia pero hay otras en segundo plano
4. **H4: El flag `_ignoreGodotExit` no se está manejando correctamente** - Hay una condición de carrera o el valor no se está propagando correctamente
5. **H5: Problemas de sincronización entre hilos** - El dispatcher de WPF no está manejando correctamente las llamadas entre hilos

## 📊 Evidence Collection Plan
1. **Instrumentar `BtnCerrarSesion_Click`** para verificar si se ejecuta
2. **Instrumentar `CleanupWithTimeout`** para verificar el flujo de limpieza
3. **Instrumentar `ForceKillGodotProcesses`** para verificar la terminación de procesos
4. **Instrumentar el evento `Exited`** para verificar si se dispara
5. **Verificar estado del flag `_ignoreGodotExit`** en diferentes puntos

## 🔧 Instrumentation Points
- [x] Punto 1: Entrada a `BtnCerrarSesion_Click` (logout-1)
- [x] Punto 2: Establecimiento de `_ignoreGodotExit = true` (logout-2, logout-3)
- [x] Punto 3: Llamada a `CleanupWithTimeout` (cleanup-timeout-1 a cleanup-timeout-4)
- [x] Punto 4: Llamada a `ForceKillGodotProcesses` (ya instrumentada)
- [x] Punto 5: Evento `Exited` del proceso Godot (manejado en LaunchGodot)
- [x] Punto 6: Restablecimiento de `_ignoreGodotExit = false` (logout-8)

## 🎯 Plan de Acción
1. **Ejecutar el visor** y hacer clic en el botón "Cerrar Sesión"
2. **Monitorear logs** en el servidor de depuración (http://localhost:3001/logs)
3. **Analizar evidencia** para determinar cuál hipótesis es correcta
4. **Implementar fix** basado en evidencia de tiempo de ejecución
5. **Verificar solución** con logs post-fix

## 📝 Log Analysis
*Pre-fix logs will be recorded here*

## 🛠️ Fix Implementation
*Fix details will be recorded here*

## ✅ Verification
*Post-fix verification results will be recorded here*

## 🧹 Cleanup Summary
*Cleanup actions will be recorded here*

---

## 🚦 Session Status: [OPEN]
**Next Action**: Instrumentar puntos de observación para recopilar evidencia de tiempo de ejecución