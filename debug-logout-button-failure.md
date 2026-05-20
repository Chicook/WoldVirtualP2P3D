# Debug Session: logout-button-failure

## 🐛 **PROBLEMA**
El botón "CERRAR SESIÓN" en el visor WPF no funciona. A pesar de múltiples intentos de corrección, el evento click no se dispara o no completa su ejecución.

## 📋 **INFORMACIÓN DE SESIÓN**
- **Session ID**: logout-button-failure
- **Start Time**: 2026-05-20
- **Issue**: Botón de cerrar sesión no responde a clics
- **User Report**: "nada de lo que has hecho funciona sigue sin funcionar el boton de cerrar sesion"
- **Status**: [OPEN]

## 🔍 **HIPÓTESIS FALSABLES**

### **H1: El botón no está habilitado (IsEnabled = false)**
- **Evidencia esperada**: Logs muestran `IsEnabled=False` en `BtnCerrarSesion_Click`
- **Punto de observación**: Inicio de `BtnCerrarSesion_Click`
- **Posible causa**: Lógica de habilitación/deshabilitación incorrecta

### **H2: El panel padre (PanLeftSidebar) no es visible**
- **Evidencia esperada**: Logs muestran `PanLeftSidebar.Visibility=Collapsed` o `IsVisible=False`
- **Punto de observación**: Inicio de `BtnCerrarSesion_Click`
- **Posible causa**: Panel oculto por defecto o lógica de visibilidad incorrecta

### **H3: Elementos superpuestos bloquean el clic**
- **Evidencia esperada**: Evento `PreviewMouseDown` se dispara pero `Click` no
- **Punto de observación**: Comparación entre `PreviewMouseDown` y `BtnCerrarSesion_Click`
- **Posible causa**: Otros controles con mayor `ZIndex` o `Background` transparente

### **H4: Problema de enrutamiento de eventos WPF**
- **Evidencia esperada**: Eventos de mouse no se propagan correctamente
- **Punto de observación**: Captura de eventos en diferentes niveles del árbol visual
- **Posible causa**: Manejo incorrecto de eventos `Handled` o `Preview` events

### **H5: El botón no está correctamente vinculado en tiempo de ejecución**
- **Evidencia esperada**: Ningún log de `BtnCerrarSesion_Click` aparece
- **Punto de observación**: Ausencia de logs del evento click
- **Posible causa**: Problema con DataContext o binding de eventos

## 🛠️ **INSTRUMENTACIÓN IMPLEMENTADA**

### **1. Instrumentación en `BtnCerrarSesion_Click`**
- Verificación de `IsEnabled`, `Visibility`, `IsVisible` del botón
- Verificación del estado de `PanLeftSidebar`
- 10 puntos de instrumentación (logout-1 a logout-10)

### **2. Nuevo Evento `PreviewMouseDown`**
- Añadido `PreviewMouseDown="BtnCerrarSesion_PreviewMouseDown"` al XAML
- Función `BtnCerrarSesion_PreviewMouseDown()` para capturar eventos de bajo nivel
- Registro de posición del clic y estado del evento

### **3. Mejora en `HideDashboardShowWizard()`**
- Convertida a función `async` con `await Task.Delay(100)`
- Uso de `Dispatcher.InvokeAsync` para mejor manejo de asincronía

### **4. Corrección de Error de Sintaxis**
- Eliminado `}` extra después de `HideDashboardShowWizard()`

## 📊 **PUNTOS DE OBSERVACIÓN**

### **Punto O1**: Entrada a `BtnCerrarSesion_Click`
- **Propósito**: Confirmar si el evento click se dispara
- **Métrica**: Presencia de logs "🚀 BtnCerrarSesion_Click INICIADO"

### **Punto O2**: Estado del botón y panel
- **Propósito**: Verificar condiciones de interactividad
- **Métrica**: Valores de `IsEnabled`, `Visibility`, `IsVisible`

### **Punto O3**: Evento `PreviewMouseDown`
- **Propósito**: Determinar si eventos de mouse llegan al botón
- **Métrica**: Presencia de logs "🎯 BtnCerrarSesion_PreviewMouseDown DISPARADO"

### **Punto O4**: Ejecución de `HideDashboardShowWizard`
- **Propósito**: Verificar si la transición de interfaz ocurre
- **Métrica**: Logs de "👁️ HideDashboardShowWizard INICIADO"

## 🚀 **PASOS DE REPRODUCCIÓN**

1. **Compilar proyecto**: `dotnet build "d:\WCVcoinMTB\WoldVirtual\WoldVirtual3Dp2p\Capa3_Visor\VisorSingularity.csproj"`
2. **Ejecutar visor**: Desde Visual Studio o ejecutable
3. **Iniciar sesión**: Completar wizard de inicio de sesión
4. **Hacer clic en "CERRAR SESIÓN"**: En panel izquierdo del dashboard
5. **Recopilar logs**: Buscar `debug_logout_trace.log` y `visor_debug_overlap.log`

## 📝 **EVIDENCIA RECOPILADA**

### **Evidencia E1**: Logs de `BtnCerrarSesion_Click`
- **Estado**: **NO ENCONTRADO**
- **Ubicación esperada**: `debug_logout_trace.log`
- **Contenido clave**: Secuencia de logs de logout-1 a logout-10
- **Análisis**: **El evento `BtnCerrarSesion_Click` NO se está disparando**. Los logs muestran múltiples ejecuciones del visor pero NINGÚN registro del evento click.

### **Evidencia E2**: Logs de `PreviewMouseDown`
- **Estado**: **NO ENCONTRADO**
- **Ubicación esperada**: `debug_logout_trace.log`
- **Contenido clave**: Logs de evento de bajo nivel
- **Análisis**: **El evento `PreviewMouseDown` tampoco se está disparando**. Esto sugiere que los eventos de mouse no están llegando al botón.

### **Evidencia E3**: Estado de interfaz post-clic
- **Estado**: **Pendiente (necesita confirmación del usuario)**
- **Observación visual**: ¿Vuelve al wizard? ¿Mensajes de estado?
- **Análisis**: Basado en los logs, es probable que la interfaz NO cambie después del clic.

### **Evidencia E4**: Logs de ejecución del visor
- **Estado**: **ENCONTRADO**
- **Ubicación**: `debug_logout_trace.log` y `visor_debug_overlap.log`
- **Contenido clave**: 
  - El visor se inicia correctamente múltiples veces
  - El dashboard se muestra (`EnterDashboard called`)
  - Godot se ejecuta (`Godot Process ID`)
  - El visor se cierra (`BtnClose_Click called` o `MainWindow_Closed called`)
- **Análisis**: **El visor funciona correctamente excepto por el botón de cierre de sesión**. Esto confirma que el problema está aislado al botón específico.

## 🔧 **PLAN DE ACCIÓN**

### **Fase 1: Recopilación de Evidencia**
1. Usuario ejecuta visor y prueba cierre de sesión
2. Usuario comparte logs y observaciones visuales

### **Fase 2: Análisis de Evidencia**
1. Determinar qué hipótesis se confirman/falsan
2. Identificar causa raíz basada en logs

### **Fase 3: Implementación de Fix**
1. Solución mínima basada en evidencia
2. Verificación con logs post-fix

### **Fase 4: Confirmación y Limpieza**
1. Usuario confirma funcionamiento
2. Limpieza de instrumentación

## ⚠️ **RIESGOS Y MITIGACIÓN**

### **R1**: Logs no se generan
- **Mitigación**: Verificar permisos de escritura, rutas de archivo

### **R2**: Problema intermitente
- **Mitigación**: Múltiples intentos, captura de estado exacto

### **R3**: Causa multifactorial
- **Mitigación**: Instrumentación granular, análisis sistemático

## 📋 **INSTRUCCIONES PARA EL USUARIO**

### **Prueba 1: Verificación básica**
1. Compila y ejecuta el visor
2. Inicia sesión normalmente
3. Haz clic en "CERRAR SESIÓN"
4. **Comparte**: ¿Qué ves? ¿La interfaz cambió?

### **Prueba 2: Recopilación de logs**
1. Busca `debug_logout_trace.log` en el directorio del ejecutable
2. Busca `visor_debug_overlap.log` en el mismo directorio
3. **Comparte**: Contenido COMPLETO de ambos archivos (si existen)

### **Prueba 3: Diagnóstico interactivo**
1. Haz clic 3 veces en el botón con 2 segundos entre clics
2. Observa si el botón se deshabilita temporalmente
3. **Comparte**: ¿El botón responde visualmente?

## 🔄 **ESTADO ACTUAL**
- **Fase**: 1 (Recopilación de Evidencia)
- **Status**: [OPEN]
- **Última acción**: Corrección de error de sintaxis y mejora de instrumentación
- **Próximo paso**: Usuario prueba y comparte evidencia

---
**Nota**: Este archivo se actualizará con evidencia y análisis a medida que avance la depuración.