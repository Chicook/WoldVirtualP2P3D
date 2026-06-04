# Plan de trabajo DevCodex

Fecha de analisis: 2026-06-04  
Rama activa: DevCodex  
Proyecto: WoldVirtual P2P 3D

## Resumen ejecutivo

El proyecto esta en estado de prototipo funcional local: el visor WPF en .NET 8 compila, el proyecto Godot abre en modo headless y existe una integracion real entre WPF, Godot, estado JSON, UDP local, webcam, voz, IPFS/Kubo y tuneles publicos. La base es prometedora, pero el estado actual mezcla codigo fuente, caches, binarios generados, runtime de Godot, estado local de usuario y artefactos de build dentro de git. Eso aumenta mucho el coste de mantenimiento y hace dificil distinguir cambios reales de ruido.

La prioridad de DevCodex deberia ser estabilizar el proyecto antes de ampliar features: higiene de repositorio, contrato de estado P2P, seguridad basica de identidad/wallet, separacion de responsabilidades en WPF/P2P y una primera capa de pruebas automatizadas. Restriccion importante: no eliminar `WoldVirtual/.godot`, porque forma parte del funcionamiento esperado del proyecto actual.

## Evidencia verificada

- Rama actual: `DevCodex`.
- Ramas locales detectadas: `main`, `DevAntigravityIA`, `DevCodex`.
- Ultimo historial visible: merges recientes desde `DevAntigravityIA`.
- Build .NET verificado:
  - `dotnet build Capa3_Visor\ServidorVirtualCS\ServidorVirtualCS.csproj --no-restore`: correcto, 0 warnings, 0 errors.
  - `dotnet build Capa3_Visor\CapaVisor3D\VisorSingularity.csproj --no-restore`: correcto, 0 warnings, 0 errors.
- Godot verificado:
  - `WoldVirtual\servidorinterno\Godot_v4.6.2-stable_mono_win64_console.exe --headless --path WoldVirtual --quit`: arranca sin errores criticos en consola.
- Estado local antes de crear este plan:
  - `WoldVirtual/woldvirtual/scene/MTC/users3D/current_user.json` modificado solo en `timestamp`.
  - `WoldVirtualP2P3D.lnk` modificado.
  - `WoldVirtual/Estado_Global/peers/peer_chicook.json` sin rastrear.
- Nota: la compilacion posterior modifico artefactos rastreados en `bin/obj`; se intento revertir solo esos artefactos, pero la accion fue rechazada por permisos de usuario.

## Diagnostico por areas

### 1. Salud funcional

Fortalezas:

- Los dos proyectos WPF compilan limpios con .NET 8.
- Godot abre en modo headless con el runtime incluido.
- La integracion principal esta materializada: WPF lanza Godot, puente MetaMask local, UDP chat/voz, peers JSON y nodo P2P/IPFS.
- Existe README tecnico amplio con flujo de ejecucion, arquitectura y estado funcional.

Riesgos:

- El README aun menciona `DevAntigravity` como rama de trabajo, mientras la rama real es `DevCodex`.
- No hay CI ni pruebas automatizadas visibles.
- Las verificaciones manuales modifican `bin/obj` porque esos directorios estan versionados.

### 2. Higiene de repositorio

Fortalezas:

- El codigo fuente principal esta localizado y es facil identificar capas: `Capa3_Visor`, `WoldVirtual`, `Estado_Global`.
- Los assets 3D y el runtime Godot estan disponibles localmente, lo que favorece ejecucion offline.

Riesgos:

- No existe `.gitignore` en la raiz.
- Hay 790 archivos rastreados por git.
- Al menos 502 archivos rastreados estan bajo `bin/obj`.
- Al menos 63 archivos rastreados estan bajo `WoldVirtual/.godot`. Esta carpeta no debe eliminarse; cualquier cambio futuro debe tratarla como dependencia funcional del proyecto.
- El repo pesa aproximadamente:
  - `WoldVirtual`: 460.03 MB.
  - `Capa3_Visor`: 397.26 MB.
- Archivos pesados destacados:
  - Godot runtime: 164.96 MB.
  - OpenCvSharpExtern duplicado en Debug, Release y publish: 65.20 MB cada copia.
  - `cloudflared.exe` duplicado en outputs: 51 MB por copia.
  - assets FBX/texturas entre 9 MB y 33 MB.

Impacto:

- Diffs con mucho ruido.
- Builds que ensucian el working tree.
- Repositorio dificil de clonar, revisar y versionar.
- Mayor riesgo de conflictos binarios.

### 3. Arquitectura WPF

Fortalezas:

- `MainWindow.xaml.cs` orquesta de forma efectiva el flujo completo.
- Se integran piezas complejas: WMI, registro, MetaMask, Godot HWND, chat UDP, voz, webcam, overlay y peer sync.

Riesgos:

- `Capa3_Visor/CapaVisor3D/MainWindow.xaml.cs` tiene 1485 lineas y demasiadas responsabilidades.
- `MainWindow.xaml` tiene 359 lineas y concentra wizard, visor, chat, P2P y webcam.
- El password de registro se valida, pero no se observa persistencia segura ni uso posterior claro.
- El callback `/confirm` recibe `wallet` y `signature`, pero no valida criptograficamente la firma antes de lanzar Godot.

### 4. P2P, tuneles e IPFS

Fortalezas:

- `P2PWebNode.cs` ofrece servidor HTTP local, landing de descarga, proxy IPFS, estado y tuneles.
- Kubo/IPFS se puede preparar y publicar desde el propio visor.
- Hay fallback de exposicion publica con Cloudflare Quick Tunnel y SSH inverso.

Riesgos:

- `P2PWebNode.cs` tiene 1037 lineas y mezcla servidor HTTP, tuneles, empaquetado, proxy, IPFS y UI status.
- Se descargan ejecutables externos (`cloudflared`, Kubo) en runtime sin verificacion explicita de hash/firma.
- SSH inverso usa `StrictHostKeyChecking=no`.
- Kubo configura `Access-Control-Allow-Origin` como `*`.
- No se observa rate limiting, autenticacion ni validacion de firma en endpoints publicos.

### 5. Sincronizacion de peers y estado global

Fortalezas:

- Existe una sincronizacion LAN por UDP (`PeerSyncService`) y persistencia compartida por `peer_*.json`.
- `IslandStateManager` usa locks y escritura atomica con temporales.
- Godot fusiona estado de usuarios/islas y mantiene cache de peers.

Riesgos:

- `PeerSyncService` escribe `peer_{remoteId}.json` usando IDs derivados del JSON remoto sin saneamiento fuerte.
- La validacion de peer es minima: en Godot basta con que exista `u` como diccionario en una ruta, y en otra ruta se fusionan diccionarios sin validar esquema.
- No hay firma, DID, versionado estricto ni control de replay.
- `current_user.json` contiene wallet y datos de usuario dentro de una ruta del proyecto versionada.
- El estado runtime (`Estado_Global/peers`) aparece como untracked, senal de que falta una politica clara de datos locales.

### 6. Dependencias y plataforma

Fortalezas:

- Target claro: `net8.0-windows`, WPF, Godot 4.6.2 mono.
- Dependencias de audio/video explicitas: NAudio, AForge, OpenCvSharp.

Riesgos:

- `OpenCvSharp4.Windows` esta en version `4.13.0.20260602`, muy reciente y pesada.
- `System.Drawing.Common` en .NET 10.0.8 dentro de app `net8.0-windows` conviene revisarlo por compatibilidad y necesidad real.
- Hay outputs y dependencias duplicadas en Debug, Release y publish dentro del repo.

## Objetivos DevCodex

1. Reducir ruido de git y separar fuente, runtime, assets, build outputs y estado local.
2. Convertir el protocolo de peers JSON en un contrato versionado, validado y firmable.
3. Extraer responsabilidades grandes de `MainWindow.xaml.cs` y `P2PWebNode.cs`.
4. Introducir pruebas de unidad y validacion automatica minima.
5. Documentar una ruta clara desde prototipo local hasta beta LAN/publica.

## Plan por fases

### Fase 0 - Baseline limpio

Prioridad: critica.

Tareas:

- Crear `.gitignore` raiz para:
  - `**/bin/`
  - `**/obj/`
  - `WoldVirtual/Estado_Global/peers/`
  - `WoldVirtual/woldvirtual/scene/MTC/users3D/current_user.json`
  - caches, logs, temporales y publishes.
- Decidir politica para binarios grandes:
  - Mantener runtime Godot en repo solo si es requisito offline explicito.
  - Mover outputs generados fuera de git.
  - Evaluar Git LFS para assets grandes reales.
- Mantener intacta la generacion ZIP actual hasta tener pruebas de regresion especificas; es una pieza imprescindible para la distribucion P2P.
- Hacer un commit solo de higiene, sin tocar logica funcional.
- Actualizar README para `DevCodex` y separar bitacora historica de estado actual.

Criterios de aceptacion:

- Ejecutar `dotnet build` no deja cambios en git.
- Ejecutar Godot headless no rompe ni elimina `WoldVirtual/.godot`.
- `git status` tras build muestra solo cambios fuente intencionados.

### Fase 1 - Contrato de estado P2P

Prioridad: critica.

Tareas:

- Definir `peer.schema.json` con version, peerId, timestamp, users, islands, voiceState y capabilities.
- Crear modelos C# compartidos para peer state y validadores.
- Crear validador equivalente en GDScript o centralizar validacion en C# antes de escribir a disco.
- Sanear IDs de peer antes de construir paths.
- Limitar tamano de peer JSON, frecuencia de escritura y numero de peers activos.
- Anadir proteccion anti-replay con timestamp monotono o nonce por peer.

Criterios de aceptacion:

- Un peer remoto malformado no se escribe a disco.
- Un peer con ID con separadores de ruta no puede escapar de `Estado_Global/peers`.
- Godot no fusiona estados sin version/esquema valido.

### Fase 2 - Identidad, wallet y firma

Prioridad: alta.

Tareas:

- Eliminar o aislar el fallback de firma simulada de `metamask.html` para builds no dev.
- Verificar en C# que la firma recibida corresponde a la wallet esperada.
- Definir DID local: seed local + clave publica + wallet vinculada + rotacion.
- Persistir secretos fuera del repo y fuera de rutas `res://`.
- Documentar recuperacion, revocacion y migracion de identidad.

Criterios de aceptacion:

- El visor no lanza Godot como usuario autenticado si la firma es invalida.
- El modo demo queda marcado y aislado.
- Los datos locales de usuario no aparecen como cambios versionados.

### Fase 3 - Refactor de orquestacion WPF

Prioridad: alta.

Tareas:

- Extraer de `MainWindow.xaml.cs`:
  - `HardwareRegistrationService`
  - `WalletBridgeService`
  - `GodotLauncherService`
  - `UdpChatBridge`
  - `VoiceChatService`
  - `WebcamOverlayService`
  - `MetaverseSessionController`
- Mantener `MainWindow.xaml.cs` como coordinador de UI, no como backend completo.
- Mover constantes de puertos, rutas y flags a configuracion tipada.

Criterios de aceptacion:

- `MainWindow.xaml.cs` baja de 1485 lineas a menos de 600.
- Los servicios principales tienen pruebas unitarias basicas.
- El flujo visible no cambia.

### Fase 4 - Refactor de nodo P2P/IPFS

Prioridad: alta.

Tareas:

- Dividir `P2PWebNode.cs` en:
  - `LocalHttpNodeServer`
  - `TunnelManager`
  - `CloudflaredProvider`
  - `SshReverseTunnelProvider`
  - `ZipDistributionService`
  - `IpfsGatewayProxy`
  - `NodeStatusReporter`
- Anadir validacion de descargas externas por hash/version fijada.
- Hacer opt-in explicito para tuneles publicos.
- Restringir CORS y endpoints expuestos.
- Anadir rate limiting y logs estructurados.

Criterios de aceptacion:

- La activacion de tunel publico requiere decision explicita del usuario.
- Descargas externas tienen version/hashes auditables.
- El servidor local puede testearse sin levantar tunel ni IPFS.

### Fase 5 - Pruebas y CI local

Prioridad: media-alta.

Tareas:

- Crear proyecto `Capa3_Visor.Tests` con xUnit/NUnit.
- Tests iniciales:
  - validacion de peer schema.
  - saneamiento de peerId.
  - calculo de paths de Godot.
  - parsing de callback de wallet.
  - quotas y resource planner.
- Crear script PowerShell `scripts/verify.ps1`:
  - `dotnet build --no-restore`
  - tests
  - Godot headless smoke test
  - chequeo de git limpio tras build.
- Preparar CI cuando exista remoto compatible.

Criterios de aceptacion:

- Una sola orden verifica build y smoke tests.
- Los cambios de protocolo tienen tests.
- El repo no queda sucio tras la verificacion.

### Fase 6 - Producto beta LAN

Prioridad: media.

Tareas:

- Definir modo LAN como objetivo beta antes de red publica.
- Mejorar telemetria local: peers activos, ultima firma, version de protocolo, latencia UDP.
- UX de errores: puertos ocupados, Godot no encontrado, MetaMask no valida, webcam ocupada.
- Documentar instalacion offline y restauracion de identidad.

Criterios de aceptacion:

- Dos PCs en LAN pueden sincronizar peers con logs comprensibles.
- Los errores frecuentes tienen mensajes accionables.
- La beta LAN no depende de tuneles publicos.

## Backlog priorizado

P0:

- Crear `.gitignore` y limpiar artefactos versionados.
- Sacar `current_user.json` y `Estado_Global/peers` del flujo versionado.
- Sanear IDs remotos antes de escribir `peer_*.json`.
- Desactivar firma simulada fuera de modo dev.

P1:

- Validar firma wallet en backend.
- Definir schema versionado de peers.
- Refactor inicial de `MainWindow.xaml.cs`.
- Refactor inicial de `P2PWebNode.cs` sin reemplazar la generacion ZIP.

P2:

- Tests unitarios.
- Script `scripts/verify.ps1`.
- Documentacion de protocolo y seguridad.
- Politica de assets grandes y runtime Godot.

P3:

- CI.
- Beta LAN.
- Opt-in de red publica con seguridad endurecida.

## Riesgos principales

1. Seguridad de identidad: hoy el flujo acepta parametros de callback y firma sin verificacion criptografica visible.
2. Escritura de peers: IDs remotos influyen en nombres de archivo y el esquema se valida poco.
3. Ruido de git: builds modifican artefactos rastreados, lo que puede ocultar cambios reales.
4. Exposicion publica: tuneles y CORS amplio abren superficie antes de tener auth/rate limiting.
5. Mantenibilidad: dos archivos concentran demasiada logica para evolucionar sin regresiones.

## Siguiente paso recomendado

Empezar por Fase 0 y Fase 1 en commits pequenos:

1. Commit `chore: add repository hygiene rules`.
2. Commit `docs: align DevCodex status and roadmap`.
3. Commit `fix: sanitize peer ids before writing peer files`.
4. Commit `test: add peer state validation tests`.

Este orden reduce ruido primero y despues ataca el riesgo real del protocolo, sin frenar el prototipo funcional que ya compila y abre.
