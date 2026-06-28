# Plan de Desarrollo: Metaverso Descentralizado con Godot

**Proyecto:** WoldVirtualP2P3D
**Autor del plan:** DevCursorIA (experto en OpenSimulator, visores y metaversos)
**Fecha:** 2026-06-27
**Versión del plan:** v1.0
**Motor objetivo:** Godot 4.6.2 (mono) + C# (.NET 8) + visor WPF
**Ámbito:** Capa 3D (`WoldVirtual/`) y su integración con el visor (`Capa3_Visor/`)

---

## 1. Propósito de este documento

Este README es el **plan maestro de desarrollo** de la capa de metaverso 3D de
WoldVirtualP2P3D, escrito desde la perspectiva de quien ha trabajado con
OpenSimulator y con visores de mundos virtuales. No es documentación de una sola
funcionalidad: es la hoja de ruta técnica para llevar la capa 3D desde el
**prototipo funcional actual** hasta una **beta P2P estable y mantenible**.

Combina tres entradas:

1. La **auditoría real del repositorio** (estado verificado del código Godot/C#).
2. Las **mejores prácticas actuales (2026)** de creación de metaversos con Godot.
3. Las **lecciones de OpenSimulator** como referencia de un metaverso
   descentralizado real y maduro (regiones, grid, hypergrid, separación
   simulador/servicios, protocolo visor-simulador).

El plan respeta las reglas del proyecto: archivos de 200-300 líneas, funciones
completas, modularidad por responsabilidades y progreso incremental sin merges
masivos.

---

## 2. Resumen ejecutivo

WoldVirtualP2P3D es un metaverso descentralizado cuyo principio rector es
**1 Usuario = 1 Isla = 1 Nodo = 1 Servidor**. La capa 3D ya tiene una base
sólida en Godot 4.6:

- Arquitectura **ECS propia** (Registry, Entity, Component, System) con sistemas
  de interpolación, salida de red y proxy/LOD.
- Un **orquestador** (`ChunkManager.gd`) que cablea red, mundo, avatar, cámara y
  UI en tiempo de ejecución.
- **Streaming de islas** y spawn de avatares locales/remotos desde estado
  fusionado (`WorldManager.gd`).
- **Sincronización P2P basada en ficheros JSON** (`NetworkLayer.gd`) más un relé
  UDP LAN desde el visor WPF.
- Controladores de **avatar, cámara (TPV/FPV/cinemática)**, gestor de
  **rendimiento adaptativo** y **entorno día/noche**.
- Integración real **Godot ↔ WPF** mediante embebido HWND, argumentos CLI,
  ficheros compartidos y UDP localhost para chat/voz.

El diagnóstico central es claro: **la base existe y funciona, pero la
sincronización del mundo no usa una capa de red real**. El transporte es
intercambio de ficheros JSON + UDP, no networking en motor. El objetivo del
ciclo es **profesionalizar el transporte, unificar el modelo de estado,
consolidar avatares/contenido y endurecer la seguridad**, sin romper el
prototipo que hoy arranca.

---

## 3. Estado actual auditado (línea base verificada)

### 3.1 Lo que YA funciona

| Área | Estado | Evidencia |
|------|--------|-----------|
| Motor Godot 4.6.2 mono | Operativo | Runtime embebido en `servidorinterno/` |
| ECS propio | Operativo | `ecs/Registry.gd`, `ecs/systems/*`, `ecs/components/*` |
| Orquestación runtime | Operativo | `gdscrip/ChunkManager.gd` |
| Streaming de islas | Operativo | `gdscrip/WorldManager.gd`, `scene/islachunk3D.tscn` |
| Avatar local + remotos | Operativo | `gdscrip/userbase3d.gd`, `users/userbase/UserBase3D.tscn` |
| Cámara TPV/FPV/cinemática | Operativo | `gdscrip/CameraController.gd` |
| Rendimiento adaptativo | Operativo | `gdscrip/PerformanceManager.gd` |
| Sync P2P por ficheros | Operativo (no ideal) | `gdscrip/NetworkLayer.gd` |
| Chat/voz Godot↔WPF | Operativo | `gdscrip/ChatUI.gd` + visor WPF (UDP 50007/50008) |
| Embebido en visor WPF | Operativo | `Capa3_Visor/CapaVisor3D/GodotHwndHost.cs` |

### 3.2 Deuda técnica y huecos detectados

1. **Sin transporte de red real en el motor.** No hay ENet, WebRTC,
   `MultiplayerSynchronizer` ni `MultiplayerSpawner`. El mundo se sincroniza
   leyendo/escribiendo `Estado_Global/peers/peer_<id>.json` cada ~1.5 s.
2. **Doble esquema de estado.** Los modelos C# (`SharedModels.cs`) usan claves
   `users`/`islands`; los ficheros vivos de Godot/WPF usan claves cortas
   `u`/`i`. No hay una única fuente de verdad.
3. **Código huérfano o desconectado.** `IPCManager.gd` y `SocialUI.gd` no están
   en ninguna escena; `IslandStateSync.gd` está en escena pero el orquestador no
   lo usa (lo sustituyó `NetworkLayer.gd`); falta `CopilotHelper.gd`.
4. **`EnvironmentManager` sin cablear** a los NodePaths `Sol`/`WorldEnvironment`
   de la escena: día/noche y render premium pueden quedar parcialmente inertes.
5. **Rutas frágiles.** `ChatUI.gd` fija la ruta
   `/root/EscenaPrincipal/Metaverso3D/ChunkManager`; si el visor lanza
   `N3DWoldVirtualMT.tscn` directo, el enrutado de burbujas de chat puede fallar.
6. **C# del proyecto Godot sin ensamblar.** Los `.cs` bajo
   `WoldVirtual/Estado_Global/` no tienen `.csproj` ni nodo que los instancie:
   son librería conceptual, no código de runtime Godot.
7. **Seguridad de identidad débil.** El flujo acepta wallet/firma sin
   verificación criptográfica fuerte; IDs de peer influyen en nombres de fichero
   con saneamiento mínimo.

---

## 4. Principios de diseño (inspirados en OpenSimulator)

OpenSimulator es el metaverso descentralizado de referencia. Sus decisiones de
arquitectura, probadas desde 2007, guían este plan:

### 4.1 Separación simulador / servicios

OpenSim divide el sistema en **simulador** (escena de la región: avatares,
objetos, física, terreno) y **servicios de grid** (assets, inventario, cuentas,
presencia). En WoldVirtualP2P3D esto se traduce en:

- **Simulador = nodo Godot** del usuario (su isla, su física, sus avatares
  visibles).
- **Servicios = capa P2P** distribuida (estado de presencia, catálogo de islas,
  identidad/wallet, descubrimiento de peers).

La regla "1 Usuario = 1 Isla = 1 Nodo = 1 Servidor" es, de hecho, una versión
**radicalmente descentralizada** del modelo "standalone" de OpenSim, donde cada
nodo hospeda su región y participa en la malla.

### 4.2 Región como unidad de mundo

En OpenSim la **región** es la unidad de streaming y de autoridad. Aquí la
**isla** cumple ese papel: es la unidad de carga/descarga, de propiedad y de
autoridad del estado. Cada isla debe poder cargarse, descargarse y sincronizarse
de forma independiente.

### 4.3 Protocolo dual: tiempo real + fiable

OpenSim usa **UDP** para lo urgente (movimiento de avatares y objetos) y **HTTP**
para lo pesado y fiable (assets, inventario, teleports). WoldVirtualP2P3D debe
adoptar el mismo patrón con tecnología Godot:

- **Canal no fiable / rápido** para posición y animación de avatares.
- **Canal fiable** para eventos discretos (chat, teleports, transacciones,
  altas/bajas de islas) y para el snapshot de estado a los que llegan tarde.

### 4.4 Interoperabilidad estilo hypergrid

El **hypergrid** de OpenSim permite saltar entre mundos manteniendo avatar e
inventario. El equivalente aquí es el **teleport entre islas/nodos** con
identidad y assets portables. Diseñar desde el principio pensando en portabilidad
evita lock-in y prepara el "grid de grids".

### 4.5 Contenido portable y archivable

OpenSim define formatos OAR (regiones) e IAR (inventario) para mover contenido
entre instalaciones. WoldVirtualP2P3D debe estandarizar **paquetes de isla** y
**paquetes de avatar/asset** (glTF/glb + manifiesto) para distribución P2P.

---

## 5. Mejores prácticas Godot adoptadas (resumen)

Estas prácticas, recogidas de la documentación y comunidad Godot 2026, son la
base técnica del plan. Se detallan en las secciones siguientes:

- **Streaming asíncrono**: nunca cargar escenas grandes de forma síncrona; usar
  `ResourceLoader.load_threaded_request()` + `load_threaded_get_status()`.
- **Origen flotante / coordenadas grandes**: evitar jitter más allá de ~5000 m
  con world-shift o "Large World Coordinates" (doble precisión).
- **HLOD con `VisibilityRange`**: sustituir mallas lejanas por proxies/impostores
  sin nodo LOD dedicado; `MultiMeshInstance3D` para vegetación densa.
- **Replicación nativa**: `MultiplayerSynchronizer` para estado continuo y `@rpc`
  para eventos; nunca mezclar ambos en la misma propiedad.
- **Autoridad clara**: `set_multiplayer_authority(id)` y guardas
  `if not is_multiplayer_authority(): return` en lógica crítica.
- **Tick moderado e interpolación**: 20-30 Hz de sincronización, cuantización de
  `Vector3`, interpolación para suavizar movimiento.
- **Late-joiners**: enviar snapshot completo del estado del mundo al conectar.
- **UGC con cautela**: `GLTFDocument`/`GLTFState` para importar en runtime, con
  validación de seguridad (Godot no aísla scripts por defecto).

> **Nota de continuación:** este documento sigue en bloques incrementales
> (arquitectura objetivo, roadmap por fases, networking P2P, avatares/UGC,
> seguridad, testing/CI, métricas y checklist). Cada bloque respeta el límite de
> 200-300 líneas y se añade desde la última línea escrita.

---

## 6. Arquitectura técnica objetivo

La meta no es reescribir, sino **evolucionar la base actual** hacia capas
limpias y desacopladas. Se proponen cinco capas:

```text
┌─────────────────────────────────────────────────────────────┐
│  CAPA 5 · PRESENTACIÓN / VISOR                                │
│  WPF (lanzador + identidad cripto) · UI Godot (HUD, chat)     │
├─────────────────────────────────────────────────────────────┤
│  CAPA 4 · SIMULACIÓN (Godot)                                  │
│  ChunkManager · WorldManager · ECS · Avatar · Cámara · Física │
├─────────────────────────────────────────────────────────────┤
│  CAPA 3 · ESTADO DEL MUNDO (modelo único)                     │
│  Esquema versionado de peer/isla/avatar · validación · merge  │
├─────────────────────────────────────────────────────────────┤
│  CAPA 2 · TRANSPORTE / RED                                    │
│  Abstracción de transporte: File-sync ▸ ENet LAN ▸ WebRTC P2P │
├─────────────────────────────────────────────────────────────┤
│  CAPA 1 · IDENTIDAD Y SEGURIDAD                               │
│  DID local · wallet · firma · saneamiento · anti-replay       │
└─────────────────────────────────────────────────────────────┘
```

### 6.1 Capa de simulación (Godot)

Mantiene y refuerza lo que ya existe. Cambios clave:

- **Desacoplar el orquestador.** `ChunkManager.gd` no debe conocer detalles del
  transporte: debe hablar con una **interfaz de red** (ver 6.3) y con el
  **modelo de estado** (ver 6.2), no con rutas de ficheros.
- **ECS como única vía de estado espacial.** Toda entidad sincronizable (avatar,
  isla, objeto) pasa por `Registry` con sus componentes; los sistemas
  (`InterpolationSystem`, `NetworkOutputSystem`, `ProxySystem`) son los únicos
  que leen/escriben datos de red.
- **Física por isla.** Activar física/IA solo en la isla activa y su radio
  inmediato; desactivar el resto (práctica de mundo abierto Godot).

### 6.2 Capa de estado del mundo (modelo único)

Resolver el **doble esquema** es prioritario. Se define un **contrato único**
versionado, válido tanto para C# como para GDScript:

```jsonc
// peer.schema.json (v2) — fuente única de verdad
{
  "v": 2,                       // versión de protocolo (entero, obligatorio)
  "peerId": "string",           // ID saneado, sin separadores de ruta
  "ts": 0,                       // timestamp monotónico (anti-replay)
  "sig": "string",              // firma de la wallet sobre el payload
  "users":   { "<uid>": { "x":0,"y":0,"z":0,"rot":0,"island":"","voice":false } },
  "islands": { "<iid>": { "name":"","owner":"","gx":0,"gz":0,"online":true } },
  "events":  [ { "type":"", "data":{}, "ts":0 } ],
  "caps":    [ "chat", "voice", "trade" ]   // capacidades del nodo
}
```

Reglas del modelo:

- **Una sola definición** de claves; los alias cortos `u`/`i` se eliminan o se
  mapean en una única capa de (de)serialización.
- **Validación obligatoria** antes de fusionar: esquema, versión, tipos.
- **Saneamiento de `peerId`** antes de construir cualquier ruta de fichero.
- **Límites**: tamaño máximo de JSON, frecuencia de escritura, nº de peers
  activos, longitud de `events`.
- **Anti-replay**: `ts` monotónico o nonce por peer; descartar lo viejo.

### 6.3 Capa de transporte (abstracción + evolución)

El corazón del plan. Se introduce una **interfaz de transporte** que oculta el
mecanismo concreto, permitiendo evolucionar sin tocar simulación:

```gdscript
# ITransport (contrato conceptual)
class_name ITransport
func start(local_id: String) -> void: pass
func stop() -> void: pass
func broadcast_state(state: Dictionary) -> void: pass   # no fiable / rápido
func send_event(peer_id: String, ev: Dictionary) -> void: pass  # fiable
func request_snapshot(peer_id: String) -> void: pass    # late-joiners
signal state_received(peer_id: String, state: Dictionary)
signal event_received(peer_id: String, ev: Dictionary)
signal peer_joined(peer_id: String)
signal peer_left(peer_id: String)
```

Implementaciones, en orden de adopción:

1. **`FileSyncTransport`** — envuelve el `NetworkLayer.gd` actual (ficheros JSON).
   Es el punto de partida: cero regresiones, mismo comportamiento, pero detrás de
   la interfaz. Permite testear el resto del sistema desde ya.
2. **`ENetTransport`** — `ENetMultiplayerPeer` para **LAN / listen-server**.
   Da el salto a tiempo real en red local: la beta LAN objetivo. Usa
   `MultiplayerSynchronizer` para posición y `@rpc` para eventos.
3. **`WebRTCTransport`** — `WebRTCMultiplayerPeer` (malla) para **P2P real**
   atravesando NAT, con señalización descentralizada (relés Nostr / servidor de
   señalización propio). Es el destino "internet abierto" coherente con el
   manifiesto P2P del proyecto.

> Decisión de arquitectura: **una sola interfaz, tres backends**. El proyecto
> puede correr file-sync hoy, ENet en LAN mañana y WebRTC en producción sin
> reescribir la simulación.

### 6.4 Capa de identidad y seguridad

- **DID local**: seed local + clave pública + wallet vinculada + rotación.
- **Firma de payload**: cada `broadcast_state`/`send_event` va firmado; el
  receptor verifica `sig` contra la wallet declarada antes de fusionar.
- **Secretos fuera de `res://`** y fuera de rutas versionadas.
- **Modo demo aislado**: la firma simulada solo en builds dev, nunca en release.

---

## 7. Mejores prácticas Godot (detalle técnico)

### 7.1 Streaming de islas sin tirones

Sustituir cualquier carga síncrona por carga en hilo, con lookahead:

```gdscript
# Patrón recomendado (resumen): pedir → sondear → instanciar diferido
func request_island_async(path: String, epoch: int) -> void:
    ResourceLoader.load_threaded_request(path)
    _pending[path] = epoch        # etiqueta para descartar resultados obsoletos

func _process(_dt: float) -> void:
    for path in _pending.keys():
        var status := ResourceLoader.load_threaded_get_status(path)
        if status == ResourceLoader.THREAD_LOAD_LOADED:
            var res := ResourceLoader.load_threaded_get(path)
            if _pending[path] == _current_epoch:   # epoch evita "islas fantasma"
                call_deferred("_instantiate_island", res)
            _pending.erase(path)
```

Reglas:

- **Nunca** bloquear en `_ready`; sondear en `_process`.
- **Etiquetar por epoch**: al teleportar o cambiar de isla, invalidar cargas en
  vuelo para no instanciar geometría que ya no toca.
- **Cap de concurrencia** (4-8 peticiones) para no saturar discos lentos.
- **Descargar islas previas** al alejarse: el streaming arregla tirones, no la
  memoria.

### 7.2 Origen flotante / coordenadas grandes

Para un mundo de muchas islas separadas, el jitter de coma flotante aparece más
allá de ~5000-8000 m. Dos opciones (elegir una):

- **World-shift**: cuando el avatar supera un umbral de distancia al origen,
  trasladar la raíz del mundo en sentido opuesto para devolver al avatar a
  `(0,0,0)`. Requiere reubicar entidades y física de forma coherente.
- **Large World Coordinates** (doble precisión): activar en *Project Settings*;
  soporte nativo del motor, más simple, con coste de compatibilidad de algunos
  recursos/plugins. **Recomendado** si no hay bloqueos de plugins.

### 7.3 HLOD y rendimiento

- `visibility_range_begin` / `visibility_range_end` en `MeshInstance3D` para
  intercambiar detalle por proxies/impostores según distancia de cámara.
- `MultiMeshInstance3D` para vegetación/props repetidos (batch de draw calls).
- Occlusion culling horneado para zonas densas; culling por distancia para campo
  abierto.
- Integrar esto con el `ProxySystem.gd` ya existente (LOD por distancia) para que
  el ECS gobierne visibilidad y sombras.
- Mantener el `PerformanceManager.gd` como capa adaptativa global (SSAO/SSIL/glow
  /SDFGI según FPS y VRAM), coherente con la restricción de bajo consumo del
  `project.godot` (low_memory, atlas de sombras pequeño).

> **Nota de continuación:** sigue el roadmap por fases, el plan de networking P2P
> detallado, avatares/UGC, seguridad, testing/CI, métricas y checklist.

---

## 8. Roadmap por fases

Cada fase tiene objetivo, tareas, criterios de aceptación y entregables. El orden
prioriza **estabilizar antes que ampliar** y **no romper el prototipo**.

### Fase 0 · Estabilización y limpieza (crítica)

**Objetivo:** dejar la capa 3D limpia, sin código muerto y con rutas robustas.

Tareas:

- Eliminar o reactivar el código huérfano: decidir destino de `IPCManager.gd`,
  `SocialUI.gd`, `IslandStateSync.gd`; recuperar o borrar `CopilotHelper.gd`.
- Cablear `EnvironmentManager` a los NodePaths reales `Sol` y `WorldEnvironment`.
- Robustecer rutas: `ChatUI.gd` debe resolver `ChunkManager` por grupo o por
  búsqueda, no por ruta absoluta fija.
- Documentar el mapa real de escenas y scripts (este documento + diagrama).

Criterios de aceptación:

- Godot abre `EscenaPrincipal.tscn` y `N3DWoldVirtualMT.tscn` sin errores de
  ruta en consola.
- No quedan scripts referenciados que falten ni nodos que apunten a scripts
  inexistentes.
- Día/noche y entorno premium responden (o se documenta por qué se desactivan).

Entregables: capa 3D saneada + diagrama de escenas actualizado.

### Fase 1 · Modelo de estado único (crítica)

**Objetivo:** una sola fuente de verdad para peer/isla/avatar.

Tareas:

- Definir `peer.schema.json` v2 (sección 6.2) y documentarlo.
- Crear (de)serializador único: una capa que mapee el modelo a disco/red y
  viceversa, eliminando el doble esquema `u`/`i` vs `users`/`islands`.
- Implementar validador de esquema (versión, tipos, límites) usado **antes** de
  cualquier merge, tanto en GDScript como en C#.
- Sanear `peerId` y aplicar límites (tamaño, frecuencia, nº de peers).

Criterios de aceptación:

- Un peer malformado **no** se fusiona ni se escribe.
- Un `peerId` con separadores de ruta no puede escapar de `peers/`.
- C# y Godot interpretan exactamente las mismas claves.

Entregables: esquema v2 + validadores + migración del formato actual.

### Fase 2 · Abstracción de transporte + `FileSyncTransport` (alta)

**Objetivo:** introducir la interfaz `ITransport` sin cambiar el comportamiento.

Tareas:

- Definir `ITransport` (sección 6.3) y sus señales.
- Implementar `FileSyncTransport` envolviendo `NetworkLayer.gd` actual.
- Hacer que `ChunkManager.gd` consuma `ITransport` en vez de tocar ficheros.
- Pruebas de que el comportamiento P2P por ficheros es idéntico al actual.

Criterios de aceptación:

- El juego corre exactamente igual que hoy, pero el orquestador ya no conoce el
  mecanismo de transporte.
- Cambiar de implementación de transporte no requiere tocar simulación.

Entregables: interfaz + backend file-sync + orquestador desacoplado.

### Fase 3 · `ENetTransport` y beta LAN (alta)

**Objetivo:** tiempo real en red local con networking nativo de Godot.

Tareas:

- Implementar `ENetTransport` (`ENetMultiplayerPeer`, modo listen-server o malla
  LAN).
- Migrar posición/rotación de avatar a `MultiplayerSynchronizer` (20-30 Hz,
  cuantizado) y eventos a `@rpc`.
- Definir autoridad: cada avatar es autoridad de su dueño
  (`set_multiplayer_authority`), guardas en lógica crítica.
- Snapshot completo a late-joiners al conectar.
- Interpolación en remotos (reutilizar `InterpolationSystem.gd`).

Criterios de aceptación:

- Dos PCs en LAN ven moverse a sus avatares en tiempo real, fluido, sin los
  ~1.5 s de latencia del file-sync.
- Un tercer cliente que entra tarde recibe el estado completo del mundo.
- La lógica crítica no la puede dictar un cliente no autoritativo.

Entregables: backend ENet + beta LAN jugable.

### Fase 4 · `WebRTCTransport` y P2P real (media-alta)

**Objetivo:** P2P atravesando NAT, coherente con el manifiesto descentralizado.

Tareas:

- Implementar `WebRTCTransport` (`WebRTCMultiplayerPeer`, malla completa).
- Señalización descentralizada: relés Nostr o servidor de señalización propio
  efímero (encaja con los túneles SSH/IPFS ya presentes en el visor).
- Estrategia NAT: STUN/TURN o relé propio; opt-in explícito para exposición.
- Reconexión, heartbeat y manejo de caída de peers.

Criterios de aceptación:

- Dos nodos en redes domésticas distintas establecen conexión directa o
  relayada sin port-forwarding manual.
- La activación de red pública es una decisión explícita del usuario.

Entregables: backend WebRTC + guía de despliegue P2P.

### Fase 5 · Avatares y contenido (UGC) (media)

**Objetivo:** avatares portables y carga segura de contenido 3D en runtime.

Tareas (detalladas en sección 10):

- Importación runtime glTF/glb (`GLTFDocument`/`GLTFState`).
- Soporte VRM opcional (addon V-Sekai) para avatares humanoides estándar.
- Paquete de avatar (modelo + manifiesto) portable entre nodos (estilo IAR).
- Validación de seguridad del contenido importado (sección 9).

Criterios de aceptación:

- Un usuario carga su avatar glTF/VRM sin reiniciar.
- El contenido externo pasa validación antes de instanciarse.

Entregables: pipeline de avatar/UGC + formato de paquete.

### Fase 6 · Teleport entre islas y "grid de grids" (media)

**Objetivo:** portabilidad estilo hypergrid entre nodos.

Tareas:

- Formalizar teleport entre islas locales (ya esbozado en `TeleportUI.gd`) y
  entre **nodos remotos**.
- Transferencia de identidad/assets al cruzar (handshake + verificación).
- Catálogo de islas descubribles en la malla.

Criterios de aceptación:

- Un avatar salta de su isla a la de otro nodo manteniendo identidad y avatar.

Entregables: protocolo de teleport inter-nodo + catálogo.

### Fase 7 · Economía 3D in-world (media-baja)

**Objetivo:** soporte de la economía WCVcoin dentro del mundo.

Tareas:

- Vendors 3D y assets volumétricos comprables (coherente con el README raíz).
- Integración del Dex3D y la "cola dinámica" como eventos firmados del modelo.
- Anti-fraude: toda transacción es evento fiable, firmado y verificado.

Criterios de aceptación:

- Una compra de asset entre wallets se refleja en el mundo de forma consistente
  y verificable.

Entregables: capa de comercio in-world conectada al modelo de estado.

---

## 9. Plan de networking P2P (núcleo del proyecto)

El proyecto es P2P por definición. Esta sección concentra las decisiones de red.

### 9.1 Topología

- **Malla (mesh)** como destino: cada nodo conecta con los demás de su vecindad
  (avatares/islas próximos), no un servidor central. `WebRTCMultiplayerPeer`
  construye malla completa de forma nativa.
- **Vecindad por interés**: un nodo no necesita el estado de todo el mundo, solo
  de las islas/avatares en su radio de interés (AOI, *area of interest*). Esto
  limita el coste de la malla y escala mejor.

### 9.2 Reparto de datos por canal (lección OpenSim)

| Dato | Canal | Frecuencia | Mecanismo Godot |
|------|-------|-----------|-----------------|
| Posición/rotación avatar | No fiable | 20-30 Hz | `MultiplayerSynchronizer` |
| Animación/estado avatar | No fiable | 10-20 Hz | sync cuantizado |
| Chat | Fiable | evento | `@rpc("reliable")` |
| Voz | No fiable | stream | canal dedicado / UDP |
| Teleport | Fiable | evento | `@rpc` + handshake |
| Alta/baja isla | Fiable | evento | `@rpc` + modelo |
| Transacción WCV | Fiable + firma | evento | `@rpc` + verificación |
| Snapshot mundo | Fiable | al conectar | `request_snapshot` |

### 9.3 Optimización de ancho de banda

- **Cuantizar `Vector3`** (truncar decimales): ahorra 50%+ de banda.
- **Delta-sync**: enviar solo lo que cambia.
- **AOI**: no replicar entidades fuera del radio de interés.
- **Tick moderado**: 20-30 Hz; interpolar en cliente para suavizar.

### 9.4 Resiliencia

- **Heartbeat** y detección de peers caídos (el `NetworkLayer.gd` ya cuenta
  ausencias: reutilizar la idea con timeouts de red real).
- **Reconexión** automática con backoff.
- **Anti-replay** por `ts` monotónico/nonce.
- **Late-joiners**: snapshot completo al entrar.

### 9.5 Pruebas de red realistas

- **Nunca** validar solo en localhost (0 ms). Usar un simulador de latencia
  (~150 ms) para detectar bugs de sincronización.
- Probar pérdida de paquetes y reordenamiento.
- Probar 2, luego N nodos; medir banda por nodo.

---

## 10. Avatares y contenido generado por el usuario (UGC)

### 10.1 Importación en runtime

Godot tiene soporte de primera clase para glTF 2.0 en runtime:

```gdscript
# Importar un avatar/asset glTF en tiempo de ejecución
var doc := GLTFDocument.new()
var state := GLTFState.new()
state.base_path = "user://avatars/"     # para resolver texturas externas
var err := doc.append_from_file("user://avatars/model.glb", state)
if err == OK:
    var root := doc.generate_scene(state)
    add_child(root)
```

- Preferir **`.glb`** (binario): más pequeño y rápido que `.gltf`.
- **VRM** (addon V-Sekai) para avatares humanoides estándar con shader MToon;
  compatible con VRoid Studio/Blender y tiendas de avatares.
- **ZIP** (`ZIPReader`/`ZIPPacker`) para empaquetar avatar + texturas + manifiesto
  como un único paquete portable (coherente con la distribución por ZIP que ya
  usa el visor).

### 10.2 Paquete de avatar/asset portable

Inspirado en IAR/OAR de OpenSim. Un paquete = ZIP con:

```text
avatar_<id>.zip
├── manifest.json     // id, autor (wallet), versión, hash, capacidades
├── model.glb         // malla + esqueleto + animaciones
├── textures/         // si no están embebidas
└── signature.bin     // firma de la wallet sobre el hash del paquete
```

Esto permite mover avatares y assets entre nodos manteniendo autoría y
verificabilidad, base para el comercio 3D y el teleport inter-nodo.

### 10.3 Seguridad del contenido importado (crítico)

Godot prioriza rendimiento sobre aislamiento: **no ejecuta scripts de recursos
externos de forma segura por defecto**. Reglas:

- **Nunca** cargar `.pck`/recursos que puedan contener scripts desde fuentes no
  confiables sin escaneo.
- Importar **solo datos** (glTF/glb, imágenes, audio), no escenas con lógica.
- Considerar herramientas como *Godot Safe Resource Loader* para detectar
  recursos maliciosos, o *godot-sandbox* para aislar ejecución si se permite
  lógica de terceros.
- Validar **hash y firma** del paquete antes de instanciar.
- Limitar polígonos, tamaño de textura y nº de nodos por asset (presupuesto de
  recursos por avatar/objeto), reforzando el `QuotaManager.cs` existente.

> **Nota de continuación:** sigue seguridad de identidad/red, testing/CI,
> métricas de éxito, riesgos y checklist operativo.

---

## 11. Seguridad de identidad y red

La seguridad no es una fase final: se diseña desde el principio (capa 1).

### 11.1 Identidad descentralizada (DID)

- **Seed local** → par de claves; la **clave pública** es la identidad del nodo.
- **Wallet vinculada** mediante firma; el nodo demuestra control de la wallet.
- **Rotación y revocación** documentadas: qué pasa si se compromete una clave.
- Secretos **fuera del repositorio** y fuera de rutas `res://` versionadas.

### 11.2 Verificación de firma (obligatoria)

- Todo estado/evento entrante trae `sig`; se verifica contra la wallet declarada
  **antes** de fusionar o de lanzar acciones.
- El visor no debe entrar al mundo como usuario autenticado con firma inválida.
- El **modo demo** (firma simulada) queda marcado y aislado, nunca en release.

### 11.3 Endurecimiento del transporte

- **Saneamiento estricto** de IDs antes de usarlos en rutas o nombres.
- **CORS restringido** y endpoints mínimos en cualquier servidor local/HTTP.
- **Rate limiting** y logs estructurados en endpoints expuestos.
- Exposición pública (túneles/WebRTC público) **opt-in explícito**.
- Descargas de binarios externos (cloudflared, Kubo) con **verificación de hash
  /versión** fijada.

### 11.4 Validación de contenido

- Hash + firma de paquetes de avatar/asset antes de instanciar.
- Presupuesto de recursos por asset (polígonos, texturas, nodos).
- Importar datos, no lógica; aislar si se permite lógica de terceros.

---

## 12. Testing, CI y calidad

Coherente con las reglas del proyecto (build verde, tests > 90%, CI/CD).

### 12.1 Pruebas de la capa 3D

- **Unitarias (C#)**: validación de esquema de peer, saneamiento de `peerId`,
  (de)serialización del modelo único, parsing de callbacks de wallet, quotas.
- **GDScript (GUT)**: lógica de `WorldManager` (slot de isla), `ProxySystem`
  (LOD por distancia), `InterpolationSystem` (lerp correcto), validación de
  estado entrante.
- **Smoke test Godot headless**: arrancar `--headless` y verificar que la escena
  principal carga sin errores críticos.
- **Pruebas de red con latencia simulada** (~150 ms) y pérdida de paquetes.

### 12.2 Script de verificación único

Un solo comando que valide todo (estilo `scripts/verify.ps1`):

```powershell
# Verificación integral de la capa 3D
dotnet build --no-restore                 # compila C# sin tocar artefactos
# (ejecutar tests unitarios C#)
# (ejecutar tests GUT de GDScript)
# Godot headless smoke test:
#   .\WoldVirtual\servidorinterno\Godot_v4.6.2-stable_mono_win64_console.exe `
#     --headless --path .\WoldVirtual --quit
# (verificar que git no quedó sucio tras build)
```

### 12.3 CI/CD

- Pipeline que ejecute el script de verificación en cada cambio.
- Build reproducible y verde como condición de integración.
- Integración por **lotes pequeños y verificables**, sin merges masivos entre
  ramas de trabajo (política del proyecto).

### 12.4 Estándares de código (reglas del proyecto)

- **200-300 líneas** por archivo; funciones completas, sin código a medias.
- Una sola definición por interfaz/tipo (sin duplicados).
- Imports limpios; sin `console.log`/prints de depuración en release.
- Aprovechar la fortaleza de cada lenguaje: **GDScript** para lógica de escena y
  gameplay, **C#** para servicios, estado, validación y rendimiento.

---

## 13. Métricas de éxito

Objetivos medibles del ciclo (referencia: estado actual ~82%).

| Métrica | Estado actual | Objetivo del ciclo |
|---------|---------------|--------------------|
| Latencia de sincronización de avatar | ~1.5 s (file-sync) | < 100 ms (ENet LAN) |
| FPS en isla activa (hardware medio) | adaptativo | ≥ 60 estable |
| Esquemas de estado | 2 (C# vs Godot) | 1 (modelo único) |
| Código huérfano en capa 3D | ≥ 4 scripts | 0 |
| Cobertura de tests | baja/sin CI | > 90% del núcleo crítico |
| Transportes intercambiables | 0 (acoplado) | 3 (file/ENet/WebRTC) |
| Verificación de firma | parcial/none | obligatoria |
| Late-joiners | no soportado | snapshot completo |
| Carga de avatar runtime | no | glTF/VRM funcional |

---

## 14. Riesgos principales y mitigación

| Riesgo | Impacto | Mitigación |
|--------|---------|-----------|
| Reescritura masiva rompe el prototipo | Alto | Interfaz `ITransport` + `FileSyncTransport` primero; cero regresiones |
| NAT bloquea P2P real | Alto | STUN/TURN o relé propio; señalización descentralizada; opt-in |
| Doble esquema persiste | Alto | Fase 1 bloquea avances hasta unificar el modelo |
| Seguridad de identidad débil | Alto | Verificación de firma obligatoria antes de cualquier acción |
| UGC malicioso | Alto | Importar solo datos; hash/firma; sandbox si hay lógica |
| Banda de la malla escala mal | Medio | AOI, cuantización, delta-sync, tick moderado |
| Jitter en mundo grande | Medio | Coordenadas grandes o world-shift |
| Artefactos/runtime en git ensucian diffs | Medio | Política de repo (sin tratar aquí el .gitignore) |
| Acoplamiento UI↔red en visor | Medio | Servicios dedicados; UI consume eventos, no red |

> **Nota:** la limpieza de artefactos de build se gestiona según la política
> general del repositorio; este plan no define reglas de exclusión de ficheros.

---

## 15. Secuencia recomendada (resumen accionable)

1. **Fase 0** — Saneamiento de la capa 3D (huérfanos, rutas, entorno).
2. **Fase 1** — Modelo de estado único + validadores (desbloquea todo lo demás).
3. **Fase 2** — `ITransport` + `FileSyncTransport` (desacople sin regresiones).
4. **Fase 3** — `ENetTransport` → **beta LAN en tiempo real**.
5. **Fase 4** — `WebRTCTransport` → **P2P real** atravesando NAT.
6. **Fase 5** — Avatares/UGC glTF/VRM con validación.
7. **Fase 6** — Teleport inter-nodo (grid de grids).
8. **Fase 7** — Economía 3D in-world.

En paralelo y de forma continua: **testing/CI**, **seguridad de identidad** y
**documentación** del modelo y los protocolos.

---

## 16. Checklist operativo

### Antes de empezar cada tarea

- [ ] La tarea encaja en una fase del roadmap.
- [ ] No rompe el arranque actual del prototipo.
- [ ] Archivos planificados dentro del límite 200-300 líneas.

### Durante el desarrollo

- [ ] Funciones completas, sin dejar lógica a medias.
- [ ] Modelo de estado único (sin reintroducir esquemas duplicados).
- [ ] Lógica crítica protegida por autoridad en red.
- [ ] Sin secretos en `res://` ni en control de versiones.

### Antes de integrar

- [ ] `dotnet build` compila sin tocar artefactos.
- [ ] Smoke test Godot headless pasa.
- [ ] Tests del núcleo crítico en verde.
- [ ] Pruebas de red con latencia simulada (si toca transporte).
- [ ] Integración en lote pequeño y verificable.

---

## 17. Glosario (puente OpenSimulator ↔ WoldVirtualP2P3D)

| OpenSimulator | WoldVirtualP2P3D | Notas |
|---------------|------------------|-------|
| Región | Isla | Unidad de mundo, streaming y autoridad |
| Simulador (OpenSim.exe) | Nodo Godot del usuario | Escena, física, avatares visibles |
| Servicios de grid (ROBUST) | Capa P2P distribuida | Presencia, catálogo, identidad |
| Standalone | 1 Usuario = 1 Isla = 1 Nodo | Cada nodo hospeda su región |
| Hypergrid | Teleport inter-nodo | Portabilidad de avatar/assets |
| Protocolo UDP visor | Canal no fiable (posición) | Tiempo real |
| Capabilities HTTP | Canal fiable (eventos) | Chat, teleport, transacciones |
| OAR (región) | Paquete de isla (ZIP) | Contenido archivable/portable |
| IAR (inventario) | Paquete de avatar/asset (ZIP) | Con manifiesto + firma |

---

## 18. Referencias técnicas

- **Godot — Multiplayer de alto nivel**: `ENetMultiplayerPeer`,
  `MultiplayerSynchronizer`, `MultiplayerSpawner`, `@rpc`, autoridad.
- **Godot — WebRTC**: `WebRTCMultiplayerPeer`, `WebRTCPeerConnection`,
  `WebRTCDataChannel`; señalización (SDP/ICE) y malla P2P.
- **Godot — Mundo abierto**: `ResourceLoader.load_threaded_request`,
  `VisibilityRange`, `MultiMeshInstance3D`, coordenadas grandes / origen
  flotante; plugins de chunking (Open World Database, Chunx).
- **Godot — UGC en runtime**: `GLTFDocument`/`GLTFState`, `FBXDocument`,
  `ZIPReader`/`ZIPPacker`; addon VRM (V-Sekai) + MToon; aislamiento de recursos.
- **OpenSimulator**: arquitectura simulador/servicios, regiones, ROBUST,
  hypergrid, protocolo visor (UDP + capabilities HTTP), formatos OAR/IAR.

---

## 19. Mantenimiento de este documento

- Este plan vive en `IAs/DevCursorIA/` como hoja de ruta de la capa 3D.
- Se actualiza por bloques incrementales de 200-300 líneas, añadiendo desde la
  última línea escrita (regla del proyecto), nunca reescribiendo todo de golpe.
- Cada fase completada debe reflejarse en las secciones 8, 13 y 16.
- Las decisiones de arquitectura (sección 6) son la referencia estable; los
  detalles de implementación pueden evolucionar con el código.

**Fin del plan v1.0.**
