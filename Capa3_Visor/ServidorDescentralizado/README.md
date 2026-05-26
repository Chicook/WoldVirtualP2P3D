# Sistema de Servidor Descentralizado

## Descripción
Sistema de monitoreo y control de recursos del usuario para compartir capacidad de procesamiento, memoria, almacenamiento y ancho de banda en la red descentralizada Wold Virtual.

## Características Principales

### 1. Monitoreo de Recursos en Tiempo Real
- **CPU**: Porcentaje de uso y límites configurables
- **RAM**: Uso actual en bytes con límites personalizables
- **Disco**: Espacio utilizado con límites configurables
- **VRAM**: Memoria de video utilizada
- **Ancho de Banda**: Velocidad de red en bits por segundo

### 2. Límites Configurables
- Límite total máximo: 1GB (combinación de RAM, disco y VRAM)
- Límites individuales para cada tipo de recurso
- Control en tiempo real del uso de recursos

### 3. Interfaz de Usuario
- Barras de progreso visuales para cada recurso
- Indicadores de estado (listo, error, límite excedido)
- Controles para activar/desactivar el monitoreo
- Configuración de límites de recursos
- Vinculación de rigs de minería externos

### 4. Integración con IPFS
- Compartir datos de recursos vía IPFS
- Recuperar información de recursos compartidos
- URLs IPFS para acceso descentralizado

## Componentes del Sistema

### ResourceMonitor.cs
Clase principal para monitorear recursos del sistema:
- Monitoreo en tiempo real de CPU, RAM, disco, VRAM y red
- Configuración de límites de recursos
- Eventos para actualización de métricas y límites excedidos
- Métodos para iniciar/detener el monitoreo

### DecentralizedServerControl.xaml/.xaml.cs
Control de usuario WPF para la interfaz:
- Visualización de barras de progreso para cada recurso
- Indicadores de estado y etiquetas informativas
- Botones de control (Activar/Desactivar, Configurar, Vincular Rig)
- Integración con ResourceMonitor

### ResourceSettingsDialog.xaml/.xaml.cs
Diálogo para configuración de límites:
- Sliders para ajustar límites de CPU (porcentaje)
- Campos numéricos para RAM, disco, VRAM (MB)
- Campo para ancho de banda (Mbps)
- Verificación de límite total de 1GB

### MiningRigDialog.xaml/.xaml.cs
Diálogo para vincular rigs de minería:
- Configuración de dirección IP y puerto
- Selección de tipo de minería (CPU, GPU, Mixta)
- Límites de recursos para el rig
- Autenticación opcional

### IpfsResourceSharing.cs
Sistema para compartir recursos vía IPFS:
- Serialización de datos de recursos a JSON
- Publicación en red IPFS usando el sistema existente
- Recuperación de datos desde IPFS
- Generación de URLs IPFS

## Instalación y Configuración

### Requisitos Previos
1. .NET 8.0 o superior
2. Sistema operativo Windows 10/11
3. Acceso a red IPFS (local o pública)

### Integración en el Proyecto
Los archivos están configurados para incluirse automáticamente en el proyecto principal a través del archivo `.csproj`:

```xml
<ItemGroup>
    <Compile Include="..\ServidorDescentralizado\*.cs" />
</ItemGroup>

<ItemGroup>
    <Page Include="..\ServidorDescentralizado\*.xaml">
        <Generator>MSBuild:Compile</Generator>
        <SubType>Designer</SubType>
    </Page>
</ItemGroup>
```

## Uso del Sistema

### 1. Iniciar el Monitoreo
El monitoreo se inicia automáticamente cuando el usuario ingresa al metaverso a través del método `StartDecentralizedServer()` en `MainWindow.xaml.cs`.

### 2. Configurar Límites de Recursos
1. Hacer clic en el botón "Configurar" en el control del servidor descentralizado
2. Ajustar los sliders y campos según las necesidades
3. Verificar que el total no supere 1GB
4. Hacer clic en "Guardar"

### 3. Vincular Rig de Minería
1. Hacer clic en el botón "Vincular Rig"
2. Ingresar la dirección IP y puerto del rig
3. Seleccionar el tipo de minería
4. Configurar los límites de recursos
5. Hacer clic en "Conectar"

### 4. Compartir Recursos vía IPFS
1. Asegurarse de que el monitoreo esté activo
2. Los datos se comparten automáticamente a intervalos regulares
3. Obtener la URL IPFS desde los logs de depuración

## Estructura de Datos

### ResourceMetrics
```csharp
public class ResourceMetrics
{
    public DateTime Timestamp { get; set; }
    public double CpuPercent { get; set; }
    public long RamBytes { get; set; }
    public long DiskBytes { get; set; }
    public long VramBytes { get; set; }
    public long BandwidthBps { get; set; }
    // ... límites y propiedades calculadas
}
```

### DecentralizedResourceData
```json
{
  "timestamp": "2026-05-26T12:00:00Z",
  "nodeId": "DSN-ABCD1234",
  "resources": {
    "cpu": {
      "currentPercent": 15.5,
      "limitPercent": 20.0,
      "isLimitExceeded": false
    },
    "memory": {
      "currentBytes": 134217728,
      "limitBytes": 268435456,
      "isLimitExceeded": false
    }
    // ... otros recursos
  },
  "totalUsageBytes": 402653184,
  "isSharingEnabled": true,
  "miningRig": {
    "address": "192.168.1.100",
    "port": 3333,
    "miningType": "GPU"
  }
}
```

## Eventos y Callbacks

### OnMetricsUpdated
Se dispara cada vez que se actualizan las métricas de recursos:
```csharp
resourceMonitor.OnMetricsUpdated += (metrics) => {
    // Actualizar UI con las nuevas métricas
};
```

### OnResourceLimitExceeded
Se dispara cuando se excede un límite de recurso:
```csharp
resourceMonitor.OnResourceLimitExceeded += (resourceName, usagePercent) => {
    // Notificar al usuario o tomar acción correctiva
};
```

## Consideraciones de Seguridad

### Límites de Recursos
- El sistema impone un límite total de 1GB para proteger al usuario
- Los límites individuales son configurables pero validados
- Se notifica al usuario cuando se exceden los límites

### Privacidad
- Los datos compartidos incluyen solo métricas de recursos
- No se comparte información personal del usuario
- El usuario controla qué recursos compartir

### Red IPFS
- Los datos se comparten de forma descentralizada
- Acceso controlado a través de URLs IPFS
- Integración con el sistema existente de Wold Virtual

## Solución de Problemas

### Problemas Comunes

1. **Monitoreo no inicia**
   - Verificar que el daemon IPFS esté ejecutándose
   - Comprobar permisos del sistema
   - Revisar logs de depuración

2. **Límites no se aplican**
   - Verificar configuración de límites
   - Comprobar que el monitoreo esté activo
   - Revisar eventos de límites excedidos

3. **Error al compartir vía IPFS**
   - Verificar conexión a red IPFS
   - Comprobar configuración del gateway
   - Revisar logs de error

### Logs de Depuración
Los mensajes de depuración se muestran en la salida de consola con prefijos:
- `[DecentralizedServerControl]`: Control de interfaz
- `[ResourceMonitor]`: Monitoreo de recursos
- `[IpfsSharing]`: Compartición IPFS

## Contribución

### Estructura del Código
- Seguir convenciones de nomenclatura de C#
- Usar comentarios XML para documentación
- Mantener coherencia con el estilo existente

### Pruebas
- Probar cambios en entorno de desarrollo
- Verificar integración con sistema existente
- Validar límites y seguridad

## Licencia
Este sistema es parte del proyecto Wold Virtual y se distribuye bajo los mismos términos y condiciones.

## Contacto
Para preguntas o soporte, contactar al equipo de desarrollo de Wold Virtual.