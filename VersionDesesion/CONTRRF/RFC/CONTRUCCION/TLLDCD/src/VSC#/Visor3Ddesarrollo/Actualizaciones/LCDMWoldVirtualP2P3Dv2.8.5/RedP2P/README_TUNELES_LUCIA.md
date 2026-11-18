# Integración de Túneles SSH Efímeros con LucIA

## Resumen

Este documento describe la integración de los túneles SSH efímeros con el sistema de validación de conexión de LucIA en WoldVirtualP2P3D.

## Arquitectura

### Componentes

1. **LucIARecepcion.gd** (Godot)
   - Recibe al jugador antes del carrusel
   - Genera link de validación de conexión
   - Escribe `user://validacion_conexion.json` cuando el usuario pulsa "Validar conexión"
   - Lee `user://validacion_resultado.json` para verificar el resultado

2. **LucIAValidacionManager.cs** (C#)
   - Monitorea el directorio `user://` de Godot
   - Detecta creación/modificación de `validacion_conexion.json`
   - Inicia túnel SSH efímero usando `P2PTunnelManager`
   - Escribe `validacion_resultado.json` con el resultado

3. **P2PTunnelManager.cs** (C#)
   - Gestiona túneles SSH inversos efímeros
   - Usa localhost.run o serveo.net
   - Publica URL pública accesible desde Internet

4. **MainWindow.xaml.cs** (C#)
   - Inicia `LucIAValidacionManager` al arrancar
   - Recibe eventos de validación completada

## Flujo de Validación de Conexión

### 1. Usuario Nuevo (sin cuenta)

```
Usuario abre visor → LucIARecepcion muestra formulario
                      ↓
Usuario introduce nick → LucIA llama a /alta-cuenta
                      ↓
Blockchain genera hash único → LucIA guarda cuenta.json
                      ↓
LucIA pasa al carrusel → Usuario elige avatar
                      ↓
Usuario entra al mundo
```

### 2. Usuario Existente (con cuenta)

```
Usuario abre visor → LucIARecepcion detecta cuenta.json
                      ↓
LucIA muestra link de validación
                      ↓
Usuario pulsa "Validar conexión"
                      ↓
LucIA escribe validacion_conexion.json
                      ↓
LucIAValidacionManager detecta archivo
                      ↓
Inicia túnel SSH efímero
                      ↓
Túnel obtiene URL pública
                      ↓
LucIAValidacionManager escribe validacion_resultado.json
                      ↓
LucIA lee resultado y actualiza UI
                      ↓
Usuario pulsa "Entrar al mundo"
                      ↓
LucIA pasa al carrusel → Usuario entra al mundo
```

### 3. Usuario Antiguo (cuenta legacy)

```
Usuario abre visor → LucIARecepcion detecta registro.cfg antiguo
                      ↓
LucIA muestra botón "Migrar mi cuenta antigua"
                      ↓
Usuario pulsa migrar → LucIA llama a /migrar-cuenta
                      ↓
Blockchain genera hash único → LucIA descarga .zip
                      ↓
LucIA guarda cuenta.json → Muestra link de validación
                      ↓
Flujo igual a usuario existente
```

## Archivos de Comunicación

### validacion_conexion.json

Escrito por LucIA cuando el usuario solicita validación:

```json
{
  "cuenta_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
  "token": "0123456789abcdef...",
  "timestamp": "1699999999.999",
  "expira": "1700003599"
}
```

### validacion_resultado.json

Escrito por LucIAValidacionManager después de procesar:

```json
{
  "exito": true,
  "mensaje": "Conexión validada correctamente. Túnel: https://abc123.lhr.life",
  "timestamp": 1699999999
}
```

## Configuración

### Directorio user:// de Godot

**Windows**: `%APPDATA%\Godot\app_userdata\WoldVirtualP2P3D\`

**Linux**: `~/.local/share/godot/app_userdata/WoldVirtualP2P3D/`

### Puerto del Túnel SSH

Por defecto: `8545` (configurable en `P2PTunnelManager`)

### Hosts de Túnel SSH

1. **localhost.run** (prioridad 1)
   - URL: `https://[random].lhr.life`
   - Sin autenticación
   - Máximo 1 túnel por IP

2. **serveo.net** (fallback)
   - URL: `https://[random].serveo.net`
   - Sin autenticación
   - Máximo 1 túnel por IP

## Uso

### Iniciar el Visor con Validación LucIA

```csharp
// En App.xaml.cs, MainWindow ya inicia automáticamente el gestor
var mainWindow = new MainWindow(initialConnectionUrl, estadoGlobal.FaltaTodo);
mainWindow.Show();
```

### Probar Manualmente

1. Iniciar el visor C#
2. Godot arranca y muestra LucIA
3. LucIA genera `validacion_conexion.json`
4. LucIAValidacionManager detecta el archivo
5. Inicia túnel SSH
6. Escribe `validacion_resultado.json`
7. LucIA lee el resultado y actualiza UI

## Seguridad

### Validación de Token

- Token SHA-256 generado con: `cuenta_hash + "|" + timestamp`
- Expira en 1 hora (configurable)
- Validación antes de iniciar túnel

### Rate Limiting

- 10 requests por IP por minuto (configurable en servidor blockchain)
- Previene abuso de creación de cuentas

### Una Cuenta por PC

- Máximo 1 cuenta por huella de máquina (UUID)
- Máximo 1 cuenta por ubicación física (ubicacion_hash)
- Enforzado por servidor blockchain

## Troubleshooting

### El túnel no se inicia

**Síntoma**: Timeout esperando túnel SSH

**Causas posibles**:
- OpenSSH no instalado en Windows
- Firewall bloqueando conexiones salientes
- localhost.run/serveo.net caídos

**Solución**:
- Verificar que `C:\Windows\System32\OpenSSH\ssh.exe` existe
- Deshabilitar firewall temporalmente para pruebas
- Revisar logs en consola del visor

### validacion_conexion.json no se detecta

**Síntoma**: LucIA espera respuesta pero nada sucede

**Causas posibles**:
- Directorio user:// incorrecto
- Permisos de escritura insuficientes
- FileSystemWatcher no iniciado

**Solución**:
- Verificar ruta en `LucIAValidacionManager.GodotUserDir`
- Verificar permisos en %APPDATA%\Godot\app_userdata\
- Revisar logs en consola del visor

### Token expirado

**Síntoma**: LucIA muestra "Token de validación expirado"

**Causa**: Pasó más de 1 hora desde que se generó el token

**Solución**: Usuario debe pulsar "Validar conexión" nuevamente

## Futuras Mejoras

- [ ] Persistencia de túneles activos en sesiones posteriores
- [ ] Autenticación de túneles SSH con claves
- [ ] Métricas de rendimiento de túneles
- [ ] Fallback a WebRTC si túnel SSH falla
- [ ] UI de estado de túnel en el visor
- [ ] Notificaciones push cuando el túnel está listo

## Referencias

- [P2PTunnelManager.cs](./P2PTunnelManager.cs) - Gestor de túneles SSH
- [LucIAValidacionManager.cs](./LucIAValidacionManager.cs) - Gestor de validación
- [LuciaRecepcion.gd](../../MTBGT/WoldVirtualP2P3D/gdscrip/LuciaRecepcion.gd) - Recepción LucIA en Godot
- [bksvcb_net.py](../../STM_BKCH/bksvcb_net.py) - Servidor blockchain con seguridad
