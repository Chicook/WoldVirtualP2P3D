# DevCodexIA - Bitacora tecnica

Fecha: 2026-06-27  
Repositorio analizado: `D:\WCVcoinMTB`

Este documento resume el trabajo realizado hoy por DevCodexIA sobre el repositorio `D:\WCVcoinMTB` y deja una seccion de pendientes basada en el analisis del estado actual del codigo. La prioridad principal fue reducir deuda tecnica sin romper funcionalidad existente.

## Regla operativa importante

No crear, editar ni proponer `.gitignore`.

Se verifico el arbol `D:\WCVcoinMTB` con busqueda recursiva y no se encontro ningun `.gitignore`. Esta restriccion queda marcada aqui para evitar repetir la discusion en futuras sesiones.

## Estado de compilacion

Comando ejecutado:

```powershell
dotnet build D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\VisorSingularity.csproj
```

Resultado:

```text
Compilacion correcta.
0 Advertencia(s)
0 Errores
Tiempo transcurrido 00:00:02.16
```

## Trabajo realizado hoy

### 1. Estabilidad global de la aplicacion

Se creo el servicio `GlobalExceptionHandler` en:

```text
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\Services\GlobalExceptionHandler.cs
```

Responsabilidades principales:

| Area | Resultado |
|---|---|
| Excepciones de UI WPF | Captura `DispatcherUnhandledException` y evita cierres abruptos cuando sea recuperable. |
| Excepciones no observadas | Captura `TaskScheduler.UnobservedTaskException` y marca la excepcion como observada. |
| Excepciones de dominio | Captura `AppDomain.CurrentDomain.UnhandledException`. |
| Diagnostico | Escribe logs en `%AppData%\WoldVirtualP2P\logs\global_exceptions.log`. |

Tambien se integro en el arranque de la aplicacion desde:

```text
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\App.xaml.cs
```

### 2. Autocorreccion en tiempo de ejecucion

Se creo el servicio `RuntimeSelfHealer` en:

```text
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\Services\RuntimeSelfHealer.cs
```

Responsabilidades principales:

| Chequeo | Accion |
|---|---|
| Directorios criticos | Recrea carpetas necesarias bajo `%AppData%\WoldVirtualP2P`. |
| Peers corruptos | Elimina `peer_*.json` vacios o con JSON invalido. |
| Espacio en disco | Avisa si queda menos de 100 MiB disponibles. |
| Locks IPFS obsoletos | Limpia `repo.lock` y `api` cuando estan huerfanos. |
| Observabilidad | Emite `OnHealAction` para que la UI pueda mostrar actividad del autocorrector. |
| Logs | Escribe en `%AppData%\WoldVirtualP2P\logs\selfheal_log.txt`. |

El ciclo se inicializa en `OnStartup` y se detiene en `OnExit`, evitando dejar tareas vivas despues del cierre de la app.

### 3. Integracion con la UI principal

Se actualizo:

```text
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\MainWindow.xaml.cs
```

Cambios principales:

| Area | Mejora |
|---|---|
| Notificaciones internas | La ventana principal se suscribe a `RuntimeSelfHealer.OnHealAction`. |
| Inicio/cierre | La suscripcion se libera durante el cierre para evitar fugas de eventos. |
| Visor Godot | El escaneo de ventana de Godot paso a un flujo asincrono con `ScanForGodotWindowAsync`. |
| HTTP bridge | Se extrajeron helpers como `RestartHttpBridge`, `CloseHttpBridge` y `ServeMetamaskPageAsync`. |
| UDP chat | Se separo `ListenUdpChatLoopAsync` para reducir ejecuciones innecesarias con `Task.Run`. |
| Bloqueos | Se redujo uso de `Thread.Sleep`, `ContinueWith` y wrappers asincronos redundantes. |

La intencion fue mantener el comportamiento existente, pero reduciendo bloqueo de UI, duplicacion y riesgo de tareas no observadas.

### 4. Sincronizacion de peers

Se refactorizo:

```text
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\PeerSyncService.cs
```

Cambios principales:

| Area | Mejora |
|---|---|
| Eventos de filesystem | Se reemplazo `ContinueWith` por flujo `async` mas legible. |
| Bucles internos | Se eliminaron wrappers `Task.Run` innecesarios alrededor de metodos ya asincronos. |
| Cierre | Se agrego manejo mas explicito de fallos durante parada/cierre. |

### 5. Tunnel y P2P/IPFS

Se refactorizaron componentes de IPFS/P2P:

```text
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\p2pipfsCS\EphemeralTunnelRunner.cs
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\p2pipfsCS\IpfsManager.cs
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\p2pipfsCS\P2PWebNode.cs
```

Cambios principales:

| Archivo | Mejora |
|---|---|
| `EphemeralTunnelRunner.cs` | Se sustituyo el patron `ContinueWith` para timeout por `Task.Delay` y `Task.WhenAny`. |
| `IpfsManager.cs` | Se extrajeron `TryKillProcess` y `TryDeleteFile` para evitar silencios opacos al limpiar procesos/locks. |
| `P2PWebNode.cs` | Se movieron constantes compartidas, se redujo duplicacion en subida de ZIPs y se agregaron helpers de filtrado. |
| `P2PWebNode.cs` | Se agregaron helpers como `CreateZipStreamContent`, `AddZipFileToForm`, `ShouldSkipFile` y `ShouldSkipDirectory`. |

El objetivo fue mejorar legibilidad y mantenibilidad sin tocar el contrato publico que usa la UI.

### 6. Estado global y cuotas

Se refactorizo:

```text
D:\WCVcoinMTB\WoldVirtual\Estado_Global\QuotaManager.cs
```

Cambios principales:

| Area | Mejora |
|---|---|
| Lectura de recursos | Se extrajo `ReadRuntimeResourceUsage`. |
| RAM Lucia | Se separo la lectura de RAM asociada a procesos Lucia. |
| Errores | Se sustituyeron silencios por trazas de diagnostico cuando aplica. |
| Limpieza | Se eliminaron imports no usados. |

### 7. Limpieza de proyecto y dependencias

Se actualizo:

```text
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\VisorSingularity.csproj
```

Estado actual relevante:

| Area | Estado |
|---|---|
| SDK | `Microsoft.NET.Sdk` con `TargetFramework` `net8.0-windows`. |
| WPF | `UseWPF` activo. |
| Compilacion por defecto | `EnableDefaultCompileItems` activo. |
| Dependencias | Se mantienen `NAudio`, `OpenCvSharp4.Windows`, `System.Drawing.Common` y `System.Management`. |
| AForge | Se elimino la referencia no usada a `AForge.Video.DirectShow`. |
| NoWarn | Se retiro la supresion innecesaria que quedaba asociada al proyecto. |

## Analisis en profundidad

### Salud actual

| Dimension | Estado |
|---|---|
| Compilacion | Correcta, sin advertencias ni errores en `VisorSingularity.csproj`. |
| Riesgo funcional | Bajo en lo cambiado hoy, porque los refactors fueron conservadores y se mantuvieron contratos publicos. |
| Observabilidad | Mejoro con logs globales, logs de autocorreccion y menos `catch` totalmente opacos. |
| Deuda async | Mejoro, pero quedan puntos que conviene tratar con cuidado. |
| Deuda arquitectonica | Sigue concentrada sobre todo en `MainWindow.xaml.cs` y `P2PWebNode.cs`. |
| Higiene de artefactos generados | Sigue siendo el foco mas delicado porque hay `bin/obj` versionados y no se debe usar `.gitignore`. |

### Hallazgos principales

| Hallazgo | Impacto | Observacion |
|---|---|---|
| `MainWindow.xaml.cs` concentra demasiadas responsabilidades | Alto | Gestiona UI, wallet, puente HTTP, Godot, chat, audio/video, P2P y ciclo de vida. Es funcional, pero dificil de mantener. |
| Persisten `catch` silenciosos | Medio/alto | Se redujeron algunos, pero aun aparecen en `MainWindow.xaml.cs`, `P2PWebNode.cs`, `SharedModels.cs` e `IslandStateManager.cs`. |
| Hay `async void` fuera de casos ideales | Medio | Los handlers WPF pueden ser `async void`, pero `LaunchAndEmbedGodot` deberia migrar a `Task` si no depende estrictamente de una firma de evento. |
| `P2PWebNode.cs` aun mezcla varias capas | Medio | Publicacion IPFS, proxy local, gateway probing, empaquetado ZIP y tunnel viven juntos. |
| Artefactos generados aparecen en Git | Medio | `bin/obj` y archivos `*_wpftmp` aparecen en estado de trabajo. No se resolvera con `.gitignore` por restriccion explicita. |
| Datos runtime en el arbol | Medio | `WoldVirtual\Estado_Global\peers\peer_ChicookDirector.json` aparece modificado; conviene separar datos vivos de codigo versionable. |
| Falta una red minima de pruebas automaticas | Medio | La compilacion pasa, pero no hay una barrera clara contra regresiones de P2P, IPFS, self-healing y UI lifecycle. |

## Pendiente

### P0 - Reducir riesgo sin cambiar comportamiento

| Pendiente | Motivo | Propuesta segura |
|---|---|---|
| Convertir `LaunchAndEmbedGodot` de `async void` a `Task` | Evita excepciones no observadas y mejora control de flujo. | Crear `LaunchAndEmbedGodotAsync` y dejar wrappers de evento minimos si hacen falta. |
| Eliminar `catch` silenciosos restantes | Los errores se pierden y dificultan diagnostico. | Centralizar helpers de log por modulo y cambiar silencios por trazas no intrusivas. |
| Separar cierre de recursos UI/P2P | Hay cierres con multiples `try/catch`. | Crear metodos `TryStop...` por recurso con logs contextuales. |
| Documentar politica para `bin/obj` sin `.gitignore` | Hay artefactos generados versionados. | Definir una regla operativa: no tocar `.gitignore`; limpiar o versionar artefactos solo bajo decision explicita. |

### P1 - Refactor arquitectonico por capas

| Pendiente | Motivo | Propuesta segura |
|---|---|---|
| Extraer `MetamaskBridgeService` desde `MainWindow.xaml.cs` | Reduce duplicacion HTTP y deja UI mas pequena. | Mover `HttpListener`, pagina fallback y ciclo start/stop a un servicio interno. |
| Extraer `GodotHostService` | El arranque/incrustacion de Godot no deberia vivir mezclado con login, chat y P2P. | Mover scan de ventana, embed y cierre a una clase con API clara. |
| Extraer `VoiceChatService` | El flujo de audio/video puede estabilizarse mejor fuera de la ventana. | Separar captura, UDP, estado de botones y cancelacion. |
| Dividir `P2PWebNode` | Aun combina demasiadas responsabilidades. | Separar `IpfsPublisher`, `GatewayProbeService`, `ZipPackageBuilder` y `LocalProxyServer`. |
| Centralizar rutas AppData | Se repiten rutas `%AppData%\WoldVirtualP2P`. | Crear una clase `RuntimePaths` o `AppRuntimePaths`. |

### P2 - Calidad sostenida

| Pendiente | Motivo | Propuesta segura |
|---|---|---|
| Pruebas de humo automatizadas | El build pasa, pero no valida flujos criticos. | Crear pruebas pequenas para self-healer, filtrado ZIP, parseo peer JSON y calculo de cuotas. |
| Logs estructurados | Hay logs por archivo, pero no una estrategia comun. | Estandarizar prefijos/contextos sin meter dependencias pesadas. |
| Reducir literales magicos | Puertos, rutas, nombres de archivos y thresholds estan repartidos. | Mover a constantes por dominio o a opciones inmutables. |
| Revisar datos runtime versionados | Evita cambios accidentales en datos vivos. | Separar datos de usuario/peer mediante carpeta runtime documentada, sin `.gitignore`. |
| Revisar scripts de preparacion local | Hay scripts utiles en `scripts\`. | Documentar flujo recomendado de ejecucion local y limpieza controlada. |

## Orden recomendado para continuar

1. Atacar primero los `catch` silenciosos restantes en `MainWindow.xaml.cs` y `P2PWebNode.cs`.
2. Convertir `LaunchAndEmbedGodot` a flujo `Task` sin cambiar llamadas externas.
3. Extraer `MetamaskBridgeService` desde `MainWindow.xaml.cs`.
4. Extraer `GodotHostService` desde `MainWindow.xaml.cs`.
5. Separar responsabilidades grandes de `P2PWebNode.cs`.
6. Crear pruebas de humo de servicios puros antes de tocar mas UI.
7. Definir politica explicita para artefactos generados sin crear `.gitignore`.

## Archivos fuente tocados o creados hoy

```text
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\App.xaml.cs
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\MainWindow.xaml.cs
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\PeerSyncService.cs
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\VisorSingularity.csproj
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\Services\GlobalExceptionHandler.cs
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\Services\RuntimeSelfHealer.cs
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\p2pipfsCS\EphemeralTunnelRunner.cs
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\p2pipfsCS\IpfsManager.cs
D:\WCVcoinMTB\Capa3_Visor\CapaVisor3D\p2pipfsCS\P2PWebNode.cs
D:\WCVcoinMTB\WoldVirtual\Estado_Global\QuotaManager.cs
```

## Notas de seguridad para futuras sesiones

| Regla | Razon |
|---|---|
| No crear `.gitignore` | Peticion explicita del propietario del repositorio. |
| No hacer `git reset --hard` | Hay cambios de usuario y artefactos generados en el arbol. |
| No limpiar `bin/obj` sin permiso | Estan apareciendo como versionados o modificados; borrarlos puede ser destructivo para el estado actual. |
| Mantener refactors pequenos | El proyecto mezcla WPF, Godot, IPFS, P2P y runtime data; los cambios grandes tienen alto riesgo. |
| Verificar con build tras cada bloque | `dotnet build VisorSingularity.csproj` es la barrera minima actual. |

