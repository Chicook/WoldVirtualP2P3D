# 🐛 INSTRUCCIONES PARA DIAGNOSTICAR EL CIERRE DE SESIÓN

## 📋 **PROBLEMA ACTUAL**
El botón "Cerrar Sesión" en el visor no funciona según el usuario. Las modificaciones anteriores no han tenido efecto.

## 🔧 **CAMBIO IMPLEMENTADO**
He agregado **instrumentación de depuración detallada** en el código para entender exactamente qué está sucediendo cuando se hace clic en "Cerrar Sesión".

## 🚀 **PASOS PARA PROBAR**

### **1. Compilar el proyecto**
```bash
dotnet build "d:\WCVcoinMTB\WoldVirtual\WoldVirtual3Dp2p\Capa3_Visor\VisorSingularity.csproj"
```

### **2. Ejecutar el visor**
- Ejecuta el visor normalmente desde Visual Studio o el ejecutable
- Inicia sesión como lo haces habitualmente

### **3. Probar el cierre de sesión**
1. **Haz clic en el botón "Cerrar Sesión"** en la interfaz del visor
2. **Observa cuidadosamente** qué sucede:
   - ¿La interfaz cambia?
   - ¿Aparece algún mensaje de error?
   - ¿El visor se congela o se cierra?
   - ¿Qué dice el texto en la parte inferior (TxtFooterStatus)?

### **4. Recopilar evidencia**
**Después de hacer clic**, busca estos archivos:

#### **Archivo principal de logs:**
```
[Directorio del ejecutable]\debug_logout_trace.log
```

#### **Archivo de logs local original:**
```
[Directorio del ejecutable]\visor_debug_overlap.log
```

### **5. Compartir resultados**
Por favor, comparte **TODA** esta información:

1. **¿Qué viste exactamente después de hacer clic?**
   - Ejemplo: "Nada cambió, todo sigue igual"
   - Ejemplo: "Apareció un mensaje de error: 'Error al cerrar sesión: ...'"
   - Ejemplo: "El visor se congeló por 5 segundos y luego volvió a la normalidad"

2. **El contenido COMPLETO de `debug_logout_trace.log`** (si existe)

3. **Cualquier mensaje de error** que aparezca en la interfaz

4. **¿El botón se deshabilitó temporalmente?** (debería deshabilitarse por 1 segundo)

## 🔍 **QUÉ ESTAMOS BUSCANDO**

### **Secuencia esperada de logs:**
```
[HH:mm:ss.fff] 🚀 BtnCerrarSesion_Click INICIADO - Punto de instrumentación 1
[HH:mm:ss.fff] 📌 Parámetros: sender=Button, e=RoutedEventArgs
[HH:mm:ss.fff] 🔄 Estableciendo _ignoreGodotExit = true
[HH:mm:ss.fff] ✅ Set _ignoreGodotExit = true for logout (valor actual: True)
[HH:mm:ss.fff] 🔧 Llamando a CleanupWithTimeout()
[HH:mm:ss.fff] ⏱️ CleanupWithTimeout INICIADO - Punto de instrumentación 11
... más logs de Cleanup y ForceKillGodotProcesses ...
[HH:mm:ss.fff] 🎉 Cierre de sesión completado exitosamente
```

### **Posibles escenarios:**

#### **Escenario A: No se ven logs**
- **Significado**: El botón no está vinculado al evento `BtnCerrarSesion_Click`
- **Solución**: Verificar el XAML del botón

#### **Escenario B: Logs se detienen en algún punto**
- **Significado**: Hay una excepción que no se está manejando
- **Solución**: Revisar el stack trace en los logs

#### **Escenario C: Logs completos pero interfaz no cambia**
- **Significado**: Las funciones `HideDashboardShowWizard()` o `UpdateInterfaceAfterLogout()` no funcionan
- **Solución**: Instrumentar esas funciones específicamente

## ⚠️ **SI NO HAY LOGS**

1. **Verifica la compilación**: Asegúrate de ejecutar la versión más reciente
2. **Busca el archivo**: Revisa el directorio donde está el ejecutable `.exe`
3. **Prueba múltiples veces**: Haz clic en "Cerrar Sesión" 2-3 veces
4. **Revisa permisos**: Asegúrate de que la aplicación puede escribir archivos

## 📞 **INFORMACIÓN CRÍTICA QUE NECESITO**

Por favor, responde con **TODOS** estos detalles:

1. **¿Hiciste clic en el botón?** (Sí/No)
2. **¿Qué sucedió inmediatamente después?**
3. **¿Apareció algún mensaje en la parte inferior de la ventana?**
4. **¿Pudiste encontrar el archivo `debug_logout_trace.log`?**
5. **Si existe el archivo, ¿puedes compartir su contenido COMPLETO?**

## 🎯 **OBJETIVO**
Entender **exactamente** en qué punto falla el cierre de sesión para implementar una solución precisa y efectiva.

---

**Nota**: Esta instrumentación es temporal y se eliminará una vez que resolvamos el problema. Los logs contienen emojis para facilitar la identificación de diferentes etapas del proceso.