# Plan de Desarrollo - WoldVirtual P2P 3D
## Análisis del Estado Actual (26 de mayo de 2026)

### Problemas Identificados en el README Principal:

1. **Panel IPFS/P2P aparece antes de tiempo**: El panel superior derecho `P2PNodeBar` aparece durante el registro de avatar en Godot, cuando debería aparecer solo después de pulsar "INICIAR SESIÓN".

2. **Sincronización de ubicaciones para nuevos usuarios**: Cuando un usuario se conecta, necesita asignársele una ubicación al lado de la isla anfitriona o la más próxima según el protocolo ya implementado en Godot.

3. **Script de compilación automática**: Falta un script que compile todo automáticamente al descomprimir el proyecto en otra máquina.

4. **Completitud del ZIP compartido por IPFS**: Necesidad de asegurar que todos los archivos necesarios se incluyan en el ZIP que se comparte por IPFS.

### Cosas que NO se deben tocar (según instrucciones):
- El espacio del IPFS ya está arreglado
- No modificar la lógica core existente que funciona
- Mantener el estilo cyberpunk y la arquitectura actual

## Plan de Desarrollo Detallado

### Fase 1: Corrección del Panel IPFS/P2P (Prioridad Alta)

**Problema**: El `P2PNodeBar` aparece durante `RegistroAV.tscn` en Godot.

**Solución propuesta**:
1. **Instrumentar con trazas**: Añadir logs específicos en `MainWindow.xaml.cs` para rastrear:
   - `ActivateMetaverseUi()` llamadas
   - `StartP2PWebNode()` activación
   - Cambios de visibilidad de `P2PNodeBar`

2. **Verificar binario actual**: Confirmar que se ejecuta la versión más reciente del visor.

3. **Implementar handshake determinista**:
   - Crear señal específica desde Godot (`AVATAR_REGISTRATION_COMPLETE`)
   - Sincronizar con evento `GridMainViewer` en WPF
   - Desacoplar activación del panel de cualquier lógica genérica

**Archivos a modificar**:
- `Capa3_Visor/CapaVisor3D/MainWindow.xaml.cs`
- `WoldVirtual/woldvirtual/scene/MTC/RegistroAV.gd`
- `WoldVirtual/woldvirtual/gdscrip/ChunkManager.gd`

### Fase 2: Asignación de Ubicaciones para Nuevos Usuarios

**Requisito**: Cuando un usuario se conecta, asignarle ubicación al lado de la isla anfitriona o la más próxima según protocolo existente.

**Análisis del protocolo actual**:
Según el README, existe:
- `WorldManager.gd`: Spawnea islas y usuarios, asigna slots
- `IslandStateSync.gd`: Sincronización de estado de islas
- `Estado_Global/peers/`: Archivos JSON con información de peers

**Implementación**:
1. **Extender `WorldManager.gd`**:
   - Añadir método `assign_nearby_location(host_island_id, new_user_id)`
   - Usar grid de posiciones predefinidas alrededor de islas
   - Respetar protocolo de spacing existente

2. **Integrar con sistema de peers**:
   - Actualizar `peer_*.json` con coordenadas asignadas
   - Sincronizar con `IslandStateManager.cs` en C#

3. **Protocolo de ubicaciones**:
   - Radio base: 10 unidades desde centro de isla anfitriona
   - Ángulos: 0°, 90°, 180°, 270° para primeras conexiones
   - Expansión radial para múltiples usuarios

**Archivos a modificar**:
- `WoldVirtual/woldvirtual/gdscrip/WorldManager.gd`
- `WoldVirtual/woldvirtual/gdscrip/IslandStateSync.gd`
- `WoldVirtual/Estado_Global/IslandStateManager.cs`
- `WoldVirtual/woldvirtual/gdscrip/NetworkLayer.gd`

### Fase 3: Script de Compilación Automática

**Requisito**: Script que compile todo al descomprimir el proyecto en otra máquina.

**Implementación**:
1. **Script PowerShell `build-all.ps1`**:
   - Verificar requisitos (.NET 8, Godot ejecutable)
   - Compilar proyecto WPF: `dotnet build Capa3_Visor\CapaVisor3D\VisorSingularity.csproj`
   - Verificar estructura de archivos Godot
   - Generar reporte de compilación

2. **Script de verificación `check-dependencies.ps1`**:
   - Verificar .NET SDK instalado
   - Verificar Godot ejecutable en `WoldVirtual/servidorinterno/`
   - Verificar permisos de escritura
   - Verificar puertos disponibles

3. **Documentación de despliegue**:
   - Instrucciones paso a paso
   - Solución de problemas comunes
   - Requisitos mínimos del sistema

**Archivos a crear**:
- `build-all.ps1` (en raíz del proyecto)
- `check-dependencies.ps1`
- `DEPLOYMENT_GUIDE.md`

### Fase 4: Completitud del ZIP para IPFS

**Requisito**: Asegurar que todos los archivos necesarios se incluyan en el ZIP compartido por IPFS.

**Análisis actual**:
- `P2PWebNode.cs`: Genera ZIP del repositorio
- `IpfsPublisher.cs`: Publica en IPFS
- Necesidad de lista completa de archivos esenciales

**Implementación**:
1. **Extender `P2PWebNode.cs`**:
   - Añadir método `GenerateCompleteZip()` con lista explícita
   - Incluir todos los archivos del README más:
     - `WoldVirtual/servidorinterno/Godot_v4.6.2-stable_mono_win64.exe`
     - `Capa3_Visor/CapaVisor3D/bin/` (si existe compilado)
     - `www/` directorio completo
     - `IAs/` documentación

2. **Lista de verificación**:
   - [ ] Proyecto Godot completo
   - [ ] Ejecutable Godot
   - [ ] Código fuente WPF
   - [ ] Assets 3D y texturas
   - [ ] Scripts y configuraciones
   - [ ] Documentación

3. **Validación automática**:
   - Script que verifica integridad del ZIP
   - Checksum de archivos críticos
   - Reporte de archivos faltantes

**Archivos a modificar**:
- `Capa3_Visor/CapaVisor3D/p2pipfsCS/P2PWebNode.cs`
- `Capa3_Visor/CapaVisor3D/p2pipfsCS/IpfsPublisher.cs`

## Cronograma de Implementación

### Semana 1: Correcciones Críticas
- **Día 1-2**: Instrumentación y diagnóstico del panel IPFS
- **Día 3-4**: Implementación de handshake determinista
- **Día 5**: Pruebas y validación

### Semana 2: Funcionalidad de Ubicaciones
- **Día 1-2**: Extensión de `WorldManager.gd`
- **Día 3-4**: Integración con sistema de peers
- **Día 5**: Pruebas multiusuario

### Semana 3: Automatización
- **Día 1-2**: Scripts de compilación
- **Día 3-4**: Completitud del ZIP para IPFS
- **Día 5**: Documentación y pruebas finales

## Consideraciones Técnicas

### 1. Compatibilidad con Sistema Existente:
- Mantener formato JSON de `Estado_Global`
- Respetar protocolo UDP del chat (puertos 50007/50008)
- No romper integración WPF-Godot

### 2. Performance:
- Asignación de ubicaciones debe ser O(1) para nuevos usuarios
- ZIP generation no debe bloquear UI principal
- Scripts de compilación optimizados para velocidad

### 3. Seguridad:
- Validar inputs en asignación de ubicaciones
- Sanitizar paths en generación de ZIP
- Mantener firmas SHA-256 del hardware

### 4. UX/UI:
- Panel IPFS visible solo cuando corresponde
- Feedback visual durante asignación de ubicación
- Mensajes claros en scripts de compilación

## Métricas de Éxito

### Corrección Panel IPFS:
- [ ] Panel no visible durante `RegistroAV.tscn`
- [ ] Panel visible inmediatamente después de "INICIAR SESIÓN"
- [ ] Sin regresiones en otras funcionalidades

### Asignación de Ubicaciones:
- [ ] Nuevos usuarios aparecen cerca de isla anfitriona
- [ ] Protocolo de spacing respetado
- [ ] Coordenadas persistidas en `peer_*.json`
- [ ] Sincronización correcta entre nodos

### Scripts de Automatización:
- [ ] `build-all.ps1` compila proyecto completo
- [ ] `check-dependencies.ps1` reporta problemas
- [ ] ZIP contiene todos los archivos necesarios
- [ ] Documentación clara y completa

## Archivos Clave del Proyecto

### WPF (.NET 8):
- `Capa3_Visor/CapaVisor3D/MainWindow.xaml` - UI principal
- `Capa3_Visor/CapaVisor3D/MainWindow.xaml.cs` - Lógica principal
- `Capa3_Visor/CapaVisor3D/GodotHwndHost.cs` - Embebido Godot
- `Capa3_Visor/CapaVisor3D/p2pipfsCS/P2PWebNode.cs` - Nodo P2P

### Godot (4.6.2):
- `WoldVirtual/woldvirtual/gdscrip/WorldManager.gd` - Gestión mundo
- `WoldVirtual/woldvirtual/gdscrip/NetworkLayer.gd` - Red
- `WoldVirtual/woldvirtual/scene/MTC/RegistroAV.gd` - Registro avatar
- `WoldVirtual/woldvirtual/gdscrip/IslandStateSync.gd` - Sincronización

### Estado Global (C#):
- `WoldVirtual/Estado_Global/IslandStateManager.cs`
- `WoldVirtual/Estado_Global/SessionManager.cs`
- `WoldVirtual/Estado_Global/QuotaManager.cs`

## Próximos Pasos Inmediatos

1. **Diagnóstico profundo del panel IPFS**:
   - Añadir logs con timestamps
   - Capturar estado de visibilidad en cada transición
   - Verificar eventos de Godot que disparan activación

2. **Revisar protocolo de ubicaciones existente**:
   - Analizar `WorldManager.gd` actual
   - Documentar grid de posiciones
   - Identificar puntos de extensión

3. **Crear estructura base para scripts**:
   - Plantilla PowerShell con manejo de errores
   - Funciones de verificación comunes
   - Sistema de logging unificado

4. **Auditar generación de ZIP actual**:
   - Listar archivos incluidos/excluidos
   - Identificar dependencias críticas
   - Definir criterios de completitud

## Notas Finales

Este plan se basa en el estado actual del repositorio descrito en el README principal (versión 23 de mayo de 2026). Las implementaciones respetarán:

- Arquitectura existente de 3 capas (WPF, Godot, Estado_Global)
- Protocolos de comunicación actuales (UDP, JSON, HTTP local)
- Estilo visual cyberpunk establecido
- Integración WPF-Godot mediante `HwndHost`

Todas las modificaciones serán incrementales y compatibles con versiones anteriores, asegurando que el prototipo funcional actual siga operativo durante el desarrollo.