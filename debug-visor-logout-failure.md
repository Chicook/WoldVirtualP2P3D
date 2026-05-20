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

## 🎯 Plan de Acción - INSTRUCCIONES PARA EL USUARIO

### 🔧 **Paso 1: Ejecutar el visor con instrumentación**
1. Compila y ejecuta el visor normalmente
2. Inicia sesión como lo haces normalmente
3. **Haz clic en el botón "Cerrar Sesión"** cuando estés listo para probar

### 📊 **Paso 2: Recopilar evidencia**
Los logs se guardarán automáticamente en:
- **Archivo local**: `debug_logout_trace.log` (en el mismo directorio del ejecutable)
- **Consola de depuración**: Salida de Debug.WriteLine

### 🔍 **Paso 3: Proporcionar evidencia**
Por favor, después de hacer clic en "Cerrar Sesión", comparte:
1. **¿Qué sucedió exactamente?** (ej: "nada cambió", "se congeló", "apareció un error")
2. **El contenido del archivo** `debug_logout_trace.log` (si existe)
3. **Cualquier mensaje de error** que aparezca en la interfaz

### 🎯 **Qué estamos verificando:**
- ✅ **H1**: ¿Se ejecuta `BtnCerrarSesion_Click`? (log "🚀 BtnCerrarSesion_Click INICIADO")
- ✅ **H2**: ¿Se establece `_ignoreGodotExit = true`? (log "✅ Set _ignoreGodotExit = true")
- ✅ **H3**: ¿Se llama a `CleanupWithTimeout`? (log "🔧 Llamando a CleanupWithTimeout()")
- ✅ **H4**: ¿Se completa el flujo? (log "🎉 Cierre de sesión completado exitosamente")

### ⚠️ **Si no ves logs:**
1. Verifica que el visor se esté ejecutando desde la compilación más reciente
2. Revisa el directorio del ejecutable para el archivo `debug_logout_trace.log`
3. Intenta hacer clic en "Cerrar Sesión" varias veces para ver si hay algún patrón

## 📝 Log Analysis
*Esperando evidencia del usuario*

**Estado actual**: Instrumentación implementada y lista para recopilar evidencia de tiempo de ejecución.

**Próximo paso**: El usuario debe:
1. Compilar y ejecutar el visor
2. Iniciar sesión normalmente
3. Hacer clic en "Cerrar Sesión"
4. Compartir los logs resultantes

## 🛠️ Fix Implementation
*Dependerá de la evidencia recopilada*

**Posibles soluciones basadas en hipótesis:**
- **H1 (botón no vinculado)**: Corregir XAML del botón
- **H2 (proceso no termina)**: Mejorar método Kill() o usar API nativa
- **H3 (múltiples instancias)**: Búsqueda más exhaustiva de procesos
- **H4 (flag mal manejado)**: Mejor sincronización del flag
- **H5 (problemas de hilos)**: Usar Dispatcher.Invoke correctamente

## ✅ Verification
*Después de implementar el fix*

**Pasos de verificación:**
1. Ejecutar visor con fix
2. Probar cierre de sesión
3. Verificar logs post-fix
4. Confirmar que la interfaz vuelve al Wizard

## 🧹 Cleanup Summary
*Después de confirmar que el fix funciona*

**Acciones de limpieza:**
1. Remover regiones de depuración (`#region debug-point`)
2. Simplificar función `SendDebugLog` (remover logging local extra)
3. Remover archivos de depuración temporales
4. Actualizar documentación si es necesario

---

## 🚦 Session Status: [OPEN]
**Next Action**: Instrumentar puntos de observación para recopilar evidencia de tiempo de ejecución