# WoldVirtualP2P3D: El Santuario de la Soberanía Digital y la Economía Cooperativa Extrema
En un contexto global marcado por el endurecimiento radical de las normativas financieras —como el cierre definitivo del periodo de transición de la ley MiCA en Europa—, el ecosistema cripto tradicional se encuentra en un callejón sin salida. La asfixia regulatoria, las exigencias de licencias bancarias millonarias y la persecución a gigantes centralizados están obligando a creadores, programadores y estudios independientes a buscar un refugio. En esta coyuntura histórica, **WoldVirtualP2P3D** no nace como un proyecto cripto especulativo más, sino como la infraestructura definitiva de resistencia: un territorio virtual tridimensional, soberano e inexpugnable.
## 🏛️ La Regla de Oro: 1 Usuario, 1 Isla, 1 Nodo, 1 Servidor
Frente al modelo de los metaversos comerciales que replican el monopolio corporativo y la especulación inmobiliaria, WoldVirtualP2P3D automatiza los principios del **cooperativismo extremo** directamente en su código. Su pilar fundamental es de una igualdad matemática absoluta: **1 Usuario = 1 Isla = 1 Nodo = 1 Servidor**.
Aquí no existen los privilegios de administrador ni los rascacielos corporativos. Si un gran exchange, un desarrollador consagrado o un usuario amateur desean formar parte del ecosistema, deben hacerlo bajo las mismas condiciones exactas: levantando su propio nodo doméstico. La red se estructura como una malla (mesh) descentralizada, distribuida a través de **túneles SSH efímeros y encriptados**, lo que vuelve al tráfico de datos y a la propia arquitectura de la plataforma invisibles e indestructibles frente a la censura estatal o los bloqueos de DNS.
## 🎭 El Camuflaje del Emprendimiento "Builder-to-Peer" (B2P)
Al carecer de dueños, juntas directivas o sedes fiscales, el metaverso se transforma en el mayor santuario de emprendimiento anónimo del mundo. Los creadores pueden integrarse y "camuflarse" a través de dinámicas nativas que protegen su derecho legítimo a comerciar sin la necesidad de registrar empresas en el mundo físico:
 * **Vendors 3D y Activos Volumétricos:** Los diseñadores venden herramientas, ropa o estructuras directamente desde sus islas. Su identidad real queda blindada tras su clave privada.
 * **Economía Circular Pura:** En WoldVirtualP2P3D está prohibido el uso de dinero fiat directo, pasarelas P2P tradicionales y *stablecoins* (vulnerables a la congelación gubernamental). El comercio del token nativo, **WCVcoin**, se realiza única y exclusivamente contra criptomonedas puras descentralizadas (como Bitcoin, Ethereum o BNB) a través de un **Dex3D** interno.
 * **La Cola Dinámica:** Cada transacción está sujeta a una tasa fija de 0,001 WCVcoin y a un reparto del 50% que alimenta de forma matemática al usuario anterior de la red (Wallet 1). La riqueza no se acumula en un intermediario; se redistribuye para sostener la liquidez común.
## 🎮 Una Consola P2P para Estudios de Videojuegos Indies
El visor en tiempo de ejecución, desarrollado con la potencia de **Godot** y el alto rendimiento de **C#**, expande las fronteras del metaverso al integrar un **motor de creación de videojuegos sin código**. Inspirado en los míticos *Logic Bricks* de Blender y los *Blueprints* de Unreal, permite a los usuarios conectar nodos visuales gráficos (Sensores y Actuadores) en el espacio tridimensional para programar mecánicas directamente "in-game".
La única condición inquebrantable es que **todo el contenido debe ser estrictamente 3D**, manteniendo la coherencia espacial y física del avatar. Esto permite a los pequeños estudios independientes:
 1. **Eliminar costes de servidor:** El juego no se compila ni se sube a tiendas centralizadas como Steam (que confiscan el 30% de las ventas). El juego vive en la propia isla del creador, corriendo en su propio hardware local de coste cero.
 2. **Monetizar mediante Assets de Blender:** El acceso a la experiencia es libre; la economía radica en la compra de los activos 3D (armas, llaves, vehículos) necesarios para interactuar y avanzar en el escenario, adquiridos mediante WCVcoin de billetera a billetera.
## 🎯 Conclusión: El Arca de Noé de la Libertad Digital
Si el viejo mundo reacciona persiguiendo la vía democrática —incluso llegando a ilegalizar los movimientos políticos digitales—, la respuesta de la comunidad no será la protesta pasiva, sino la **desconexión económica**. Una huelga fiscal masiva apoyada en esta tecnología colapsaría la recaudación estatal por falta de un sujeto jurídico al que embargar.
El objetivo definitivo de **WoldVirtualP2P3D** es demostrar que las leyes de los hombres no pueden derogar las leyes de la matemática. Mientras el marco regulatorio tradicional intenta asfixiar el libre mercado de la Web3, este metaverso cooperativo emerge como un organismo vivo y autónomo. Un ecosistema donde el software sigue procesando relevos, bloque a bloque y nodo a nodo, garantizando un espacio de libertad, entretenimiento y soberanía económica para las generaciones del futuro.
 
 # WoldVirtual P2P 3D

README de plan de desarrollo y coordinacion de ramas.

Fecha de auditoria: 2026-05-23  
Ultima actualizacion tecnica: **2026-06-29** (rama `DevCursorIA` / plan `DevAntigravityIA`)

## Avances del ciclo (2026-06-29)

Durante esta jornada se consolido la capa P2P del visor C# y su integracion con Godot, pasando de un prototipo de sincronizacion JSON local a una arquitectura de estado firmada, con handshake, limites de confianza y bootstrap hacia Internet.

### Identidad y wallet (`NodeIdentity`)

| Pieza | Archivo | Estado |
|-------|---------|--------|
| DID `did:wv:node:<hash>` sin doble prefijo | `Capa3_Visor/CapaVisor3D/Identity/NodeIdentity.cs` | Hecho |
| Clave privada DPAPI (`node.key`) | mismo | Hecho |
| Vinculacion MetaMask (`BindWallet`, `GetBindingProof`) | mismo + `node.wallet` cifrado | Hecho |
| Validacion firma simulada / extensible Nethereum | `Identity/MetaMaskValidator.cs` | Hecho |

### Handshake y modelo de confianza P2P

| Pieza | Archivo | Estado |
|-------|---------|--------|
| Protocolo handshake v1.0 (request/response, binding proof) | `Services/HandshakeProtocol.cs` | Hecho |
| Integracion UDP: handshake tras cada `HELLO` (LAN + semillas) | `PeerSyncService.cs` | Hecho |
| Estado solo de peers con handshake previo | `PeerSyncService.cs` | Hecho |
| Rate limit 5 actualizaciones/s por peer | `Services/PeerRateLimiter.cs` | Hecho |
| Bloqueo temporal de IP (60 s) tras directory traversal | `PeerSyncService.cs` | Hecho |
| Firma ECDSA + anti-replay `seq` + Vector Clock | `PeerSyncService.cs`, `ConflictResolver.cs` | Hecho |
| Esquema peer ampliado (`seq`, `vc`, `sig`, `pubkey`) | `Identity/peer.schema.json` | Hecho |

### Consenso, bootstrap y recuperacion

| Pieza | Archivo | Estado |
|-------|---------|--------|
| Vector Clock y resolucion LWW / autoría de isla | `Services/VectorClock.cs`, `ConflictResolver.cs` | Hecho |
| Catch-up post-particion (`HELLO`, `SYNC_REQ`, `SYNC_RESP`) | `Services/CatchupProtocol.cs` | Hecho |
| Bootstrap semillas IPNS + cache local | `Services/BootstrapPeerService.cs` | Hecho |
| Purga peer a 60 s + evento `peer_expired` por WebSocket | `PeerSyncService.cs`, `NetworkLayer.gd` | Hecho |

### Transporte local C# ↔ Godot

| Pieza | Archivo | Estado |
|-------|---------|--------|
| Servidor WebSocket local (`P2PWebNode`, puerto dinamico) | `p2pipfsCS/P2PWebNode.cs` | Hecho |
| Publicacion puerto en `Estado_Global/ws_port.txt` | `MetaverseSessionController.cs` | Hecho |
| Cliente WS con reconexion automatica cada 3 s | `WoldVirtual/woldvirtual/gdscrip/NetworkLayer.gd` | Hecho |
| Retiro de avatar remoto al recibir `peer_expired` | `NetworkLayer.gd` | Hecho |

### Servicios WPF y telemetria

| Pieza | Archivo | Estado |
|-------|---------|--------|
| Orquestacion de sesion extraida de `MainWindow` | `Services/MetaverseSessionController.cs` | Hecho |
| UDP chat, lanzador Godot, huella hardware | `UdpChatService.cs`, `GodotLauncherService.cs`, `HardwareFingerprintService.cs` | Hecho |
| Metricas P2P thread-safe + reconexion tunel con backoff | `NetworkTelemetryService.cs`, `P2PWebNode.MonitorTunnelAsync` | Hecho |
| Wallet de sesion pasada al arrancar `PeerSync` | `MainWindow.xaml.cs` → `MetaverseSessionController` | Hecho |

### Embebido de Godot y UI del Visor

| Pieza | Archivo | Estado |
|-------|---------|--------|
| Captura de stderr y logs detallados del proceso Godot | `GodotLauncherService.cs` | Hecho |
| Selección determinista de HWND (filtro por clase "Engine" y área) | `GodotLauncherService.cs` | Hecho |
| Resolución de pantalla negra (estabilización de layout previo al embebido) | `MainWindow.xaml.cs` | Hecho |
| Posicionamiento correcto del overlay de la Webcam pegado al chat | `MainWindow.xaml.cs` | Pendiente |

### Calidad

- Suite de tests automatizada: **39/39 en verde** (`Capa3_Visor/VisorSingularity.Tests/`)
  - `IdentityTests`, `ConsensusTests`, `BootstrapTests`, `HandshakeTests`, `PeerRateLimiterTests`
- Plan detallado alineado: `IAs/DevAntigravityIA/PLANDEVANTIGRAVITY.md`

### Pendiente inmediato (siguiente iteracion)

- **Colocación correcta de la webcam:** Resolver la discrepancia de coordenadas entre el `HwndSource` (hijo de Godot) y la ventana WPF para que el recuadro de la cámara quede anclado visualmente a la barra del chat (`BorderBottomLoginBar`).
- Fase intermedia **Memory-Mapped Files** para posiciones de avatar volatiles (latencia < 5 ms, seccion 2.4 del plan)
- Interfaz formal `INodeIdentity` y verificacion Ethereum real con Nethereum
- Tests de payloads firmados incorrectos sobre socket UDP real
- Ampliar manejo Godot de eventos WS mas alla de `peer_expired`

---

Situacion observada directamente en `d:\WCVcoinMTB`:

- Ramas locales activas: `main`, `DevAntigravityIA`, `DevCodexIA`, `DevTraeIA`.
- HEAD actual durante la auditoria: `DevTraeIA`.
- Arbol git limpio al iniciar la revision.
- Diferencias reales entre ramas activas: casi solo datos runtime (`peer_*.json`, `current_user.json`), no cambios estructurales fuertes.
- Base funcional existente:
  - Visor WPF en `Capa3_Visor/CapaVisor3D`
  - Motor Godot en `WoldVirtual`
  - Estado global en `WoldVirtual/Estado_Global`
  - Nodo P2P del visor en `Capa3_Visor/CapaVisor3D/p2pipfsCS`
- Tamano funcional del codebase auditado: 342 archivos entre C#, GDScript, XAML, escenas y JSON.

Conclusion operativa:

- El repositorio esta en fase de prototipo funcional integrado.
- La prioridad ya no es anadir mas features aisladas, sino ordenar contratos, separar runtime de fuente, reducir deuda tecnica y estabilizar el camino hacia una integracion multi-rama limpia.

## Deuda tecnica prioritaria

### DT-01. Artefactos generados versionados

Se observan `bin/`, `obj/`, ejecutables generados y librerias compiladas dentro del repo.

Impacto:

- ensucia diffs
- aumenta el peso del repositorio
- dificulta saber que es fuente y que es build
- favorece ejecuciones contra binarios viejos

### DT-02. Datos runtime versionados

Se observan archivos de estado vivos dentro del repo, por ejemplo:

- `WoldVirtual/Estado_Global/peers/peer_ChicookDirector.json`
- `WoldVirtual/woldvirtual/scene/MTC/users3D/current_user.json`

Impacto:

- genera divergencia artificial entre ramas
- mezcla sesion local con codigo fuente
- complica integraciones y validacion

### DT-03. Orquestacion demasiado concentrada en `MainWindow.xaml.cs`

El visor concentra UI, login, bridge HTTP, embebido Godot, listeners UDP, arranque P2P y parte del control de sesion.

**Progreso 2026-06-29:** extraccion parcial a `MetaverseSessionController`, `UdpChatService`, `GodotLauncherService` y `HardwareFingerprintService`. La UI principal sigue siendo grande; queda deuda de ViewModels.

Impacto:

- baja mantenibilidad
- alto riesgo de regresiones
- dificil de testear por modulo

### DT-04. Sync legacy y sync actual coexistiendo

Conviven piezas como `NetworkLayer.gd`, `IslandStateSync.gd` y logica C# de estado sin un contrato unico y estable.

**Progreso 2026-06-29:** `NetworkLayer.gd` consume estado por WebSocket local con fallback a disco; `PeerSyncService` firma y valida estado P2P; catch-up y handshake unifican el transporte UDP. `IslandStateSync.gd` sigue como legacy.

Impacto:

- doble fuente de verdad
- mas complejidad de integracion
- deuda funcional en la sincronizacion multipeer

### DT-05. P2P del visor incompleto como red real

Existe distribucion por ZIP, HTTP local, tuneles e integracion con IPFS, pero no existe todavia una capa P2P completa del metaverso para estado, presencia y consistencia entre nodos.

**Progreso 2026-06-29:** capa P2P LAN operativa en UDP 50099 con handshake, firmas, vector clock, catch-up, bootstrap IPNS, rate limiting y puente WS a Godot. Falta memory-mapped sync y mesh completa fuera de LAN/semillas.

Impacto:

- el reparto del visor existe
- el reparto del estado del mundo aun no esta cerrado

### DT-06. Ausencia de pipeline de calidad

No hay solucion `.sln`, no hay CI visible, no hay suite de tests automatizada y no hay control fuerte sobre formato/encoding.

**Progreso 2026-06-29:** suite `VisorSingularity.Tests` con 39 tests unitarios en verde (identidad, consenso, bootstrap, handshake, rate limit). CI y `.sln` siguen pendientes.

Impacto:

- poca trazabilidad
- menor confianza en cambios cruzados entre ramas
- mas coste al integrar

## Objetivo del siguiente ciclo

Pasar de "prototipo local funcional" a "base integrable y mantenible" en cuatro frentes:

1. estabilizar el repositorio
2. aislar responsabilidades tecnicas
3. consolidar el transporte y la sincronizacion
4. preparar una integracion posterior sobre `main` sin deuda acumulada

## Politica de trabajo entre ramas

Este plan asume estas reglas:

- No hacer merge directo entre ramas de trabajo.
- Cada rama entrega piezas acotadas y verificables.
- `main` actua como rama de integracion, no como rama de experimentacion.
- Los archivos runtime no deben volver a ser el factor principal de divergencia entre ramas.
- La documentacion de plan debe mantenerse identica en todas las ramas activas.

## Plan de implementacion distribuido por ramas

### `main`

Rol:

- base de integracion
- referencia estable de build
- control de calidad del proyecto

Entregables:

1. definir la linea base de compilacion valida del visor
2. fijar la politica de que solo entra codigo integrable y sin basura de runtime
3. centralizar changelog tecnico del ciclo
4. validar que las ramas de trabajo entregan piezas compatibles

Pendientes:

- introducir `.gitignore` coherente para artefactos generados
- separar datos de sesion local del codigo fuente
- crear solucion `.sln` para el visor
- preparar estructura minima para CI y smoke build

Criterio de cierre:

- `main` debe poder compilar de forma repetible
- `main` no debe arrastrar `peer_*.json` o `current_user.json` como diferencia estructural

### `DevCodexIA`

Rol:

- saneamiento del repositorio
- consolidacion de estructura
- reduccion de deuda tecnica transversal

Entregables:

1. limpieza de artefactos versionados (`bin`, `obj`, ejecutables de salida, residuos de build)
2. normalizacion de estructura y nombres
3. separacion clara entre fuente, runtime, assets y resultados compilados
4. unificacion de encoding a UTF-8 sin corrupciones visibles
5. inventario de codigo legacy o duplicado

Pendientes concretos:

- mover datos runtime a rutas no versionadas o plantillas base
- revisar coexistencia de `IslandStateSync.gd` y `NetworkLayer.gd`
- revisar carpetas y binarios que no deben vivir en control de versiones
- documentar mapa real del repo despues de la limpieza

Dependencias:

- ninguna fuerte para empezar
- su salida desbloquea trabajo mas seguro para el resto

Criterio de cierre:

- repo mas pequeno y legible
- menos ruido en diffs
- estructura apta para automatizacion posterior

### `DevAntigravityIA`

Rol:

- arquitectura
- contratos tecnicos
- seguridad y modelo de evolucion del sistema

Entregables:

1. ~~definir contrato unico de identidad del nodo~~ **Hecho** (`NodeIdentity`, wallet binding, tests)
2. ~~especificar handshake entre visor, nodo y capa de estado~~ **Hecho** (`HandshakeProtocol` + integracion UDP)
3. ~~definir modelo de confianza y validacion entre peers~~ **Hecho** (firmas, `seq`, rate limit, bloqueo IP)
4. bajar a diseno la evolucion desde JSON local a sincronizacion distribuida — **en curso** (WS hecho; memory-mapped pendiente)
5. ~~fijar criterios de consistencia, bootstrap y recuperacion~~ **Hecho** (vector clock, catch-up, IPNS, purga 60 s)

Pendientes concretos:

- interfaz formal `INodeIdentity`
- verificacion Ethereum real (Nethereum)
- fase intermedia memory-mapped files (seccion 2.4)
- tests de ataque sobre socket UDP real

Dependencias:

- necesita la limpieza basica de `DevCodexIA` para trabajar con menos ruido
- su salida define interfaces para `DevTraeIA`

Criterio de cierre:

- decisiones de arquitectura cerradas y accionables
- contratos suficientemente concretos para implementacion

### `DevTraeIA`

Rol:

- transporte
- servicios de red
- endurecimiento del nodo del visor
- preparacion del camino hacia sincronizacion real

Entregables:

1. extraer listeners y transporte de `MainWindow.xaml.cs` a servicios dedicados
2. formalizar heartbeat, reconexion y manejo de peers
3. endurecer `P2PWebNode.cs` para uso mas estable
4. preparar discovery local y pool de conexiones
5. reducir acoplamiento entre UI WPF y red del visor

Pendientes concretos:

- encapsular UDP actual en una capa reutilizable
- extraer logica de inicio/parada del nodo P2P a servicios
- instrumentar timeouts, reintentos y estados de conexion
- definir capa de eventos para que la UI consuma estado sin conocer la red en detalle
- preparar compatibilidad futura con cache, chunks o discovery real

Dependencias:

- consume contratos definidos por `DevAntigravityIA`
- se beneficia de la limpieza estructural de `DevCodexIA`

Criterio de cierre:

- transporte desacoplado del visor
- nodo P2P mas predecible
- menos logica de red dentro de la UI principal

## Secuencia recomendada

### Fase 1. Higiene y estabilizacion

Responsables:

- `DevCodexIA`
- `main`

Objetivo:

- limpiar repo
- separar runtime
- fijar baseline de compilacion

### Fase 2. Contratos y arquitectura

Responsable principal:

- `DevAntigravityIA`

Objetivo:

- cerrar definiciones de identidad, handshake, estado y seguridad

### Fase 3. Implementacion del transporte

Responsable principal:

- `DevTraeIA`

Objetivo:

- convertir la red actual en modulos mantenibles y reutilizables

### Fase 4. Integracion sobre `main`

Responsable:

- `main` como rama receptora

Objetivo:

- integrar por lotes pequenos, verificables y sin merge masivo entre ramas de trabajo

## Riesgos a vigilar

- seguir versionando datos de sesion y artefactos compilados
- continuar ampliando `MainWindow.xaml.cs` en vez de dividir responsabilidades
- introducir nueva funcionalidad de red sin contrato previo
- intentar integrar ramas por volumen en vez de por entregables pequenos
- seguir usando JSON locales como sustituto indefinido de una capa de sincronizacion real

## Definition of done del ciclo

El ciclo se considera bien encaminado cuando se cumpla todo esto:

- README alineado en todas las ramas activas — **en curso** (actualizado 2026-06-29)
- repo saneado de artefactos generados y runtime innecesario — pendiente
- contratos tecnicos base cerrados — **mayormente hecho** (falta memory-mapped y Nethereum)
- transporte desacoplado del visor principal — **parcial** (`MetaverseSessionController`, servicios extraidos)
- `main` listo para recibir integraciones pequenas sin merge cruzado entre ramas de trabajo — pendiente

## Estado de sincronizacion de este README

Este README debe mantenerse identico en:

- `main`
- `DevCodexIA`
- `DevAntigravityIA`
- `DevTraeIA`

La sincronizacion entre ramas debe hacerse sin merge, mediante aplicacion explicita del mismo cambio documental.
