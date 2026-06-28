# Plan de Ejecución Segura — Capa 3D (Godot/C#)

**Proyecto:** WoldVirtualP2P3D
**Autor del plan:** DevCursorIA
**Fecha:** 2026-06-28
**Versión:** v1.0
**Complementa a:** `PLAN_DESARROLLO_METAVERSO_GODOT.md` (plan maestro v1.0)

---

## 0. Para qué sirve este documento

El plan maestro define **qué** construir y en **qué orden** (arquitectura,
fases 0-7, networking, UGC, seguridad). Este documento define **cómo ejecutarlo
sin romper el código que hoy arranca**: tareas atómicas ancladas a archivos
reales, con criterios de "no regresión", puntos de reversión y puertas de
verificación antes de cada integración.

Regla rectora: **cada cambio debe poder revertirse en un solo paso y dejar el
prototipo arrancando igual que antes.** Si una tarea no cumple esto, se divide.

---

## 1. Inventario real de la capa 3D (verificado)

Archivos GDScript activos en `WoldVirtual/woldvirtual/`:

| Grupo | Archivos | Rol |
|-------|----------|-----|
| Orquestación | `gdscrip/ChunkManager.gd` | Cablea red, mundo, avatar, cámara, UI |
| Mundo | `gdscrip/WorldManager.gd` | Streaming de islas, spawn de avatares |
| Red (actual) | `gdscrip/NetworkLayer.gd` | Sync P2P por ficheros JSON |
| Avatar | `gdscrip/AvatarController.gd`, `gdscrip/userbase3d.gd` | Control y representación |
| Cámara | `gdscrip/CameraController.gd` | TPV/FPV |
| Cinemática | `gdscrip/CinematicIntroController.gd`, `gdscrip/IslandRiseAnimation.gd` | Intro de arranque |
| Entorno | `gdscrip/EnvironmentManager.gd` | Día/noche, render |
| Rendimiento | `gdscrip/PerformanceManager.gd` | Ajuste adaptativo |
| UI | `gdscrip/ChatUI.gd`, `WalletUI.gd`, `TeleportUI.gd`, `SocialUI.gd` | HUD |
| Registro | `gdscrip/RegistroAV.gd` | Alta de avatar/usuario |
| IPC | `gdscrip/IPCManager.gd` | Comunicación con visor |
| ECS | `ecs/Registry.gd`, `ecs/Entity.gd`, `ecs/Component.gd`, `ecs/System.gd` | Núcleo ECS |
| ECS · componentes | `ecs/components/{Spatial,Island,Network,Proxy}*.gd` | Datos de entidad |
| ECS · sistemas | `ecs/systems/{Interpolation,NetworkOutput,Proxy}System.gd` | Lógica de entidad |
| Escenas | `scene/MTC/N3DWoldVirtualMT.tscn`, `scene/islachunk3D.tscn`, `users/userbase/UserBase3D.tscn` | Escenas raíz |

Estado huérfano confirmado (ver plan maestro §3.2): `IPCManager.gd`,
`SocialUI.gd` y `IslandStateSync.gd` no están cableados por el orquestador.

---

## 2. Reglas de no-regresión (obligatorias)

Antes de tocar cualquier archivo de la tabla anterior:

1. **Punto de reversión.** Confirmar `git status` limpio (salvo estado de
   runtime). Cada tarea se entrega en un único commit reversible.
2. **Arranque verde primero.** El prototipo debe abrir `N3DWoldVirtualMT.tscn`
   sin errores rojos en consola ANTES y DESPUÉS del cambio.
3. **Cambio aditivo por defecto.** Preferir añadir un script/función nuevos sobre
   modificar uno crítico. Lo nuevo se activa con un **flag** apagado por defecto.
4. **Sin tocar firmas públicas en caliente.** Si una función la llama otro
   script (p. ej. `ChunkManager` → `CinematicIntroController.begin`), no se
   cambia su firma; se añade sobrecarga o parámetro opcional con valor seguro.
5. **Límite 200-300 líneas** por archivo; funciones completas, sin lógica a
   medias (regla del proyecto).
6. **Una responsabilidad por archivo.** Si un cambio mezcla red + UI, se parte.

---

## 3. Mecanismo de feature flags (clave para no romper)

Para introducir comportamiento nuevo sin riesgo, se centraliza un único punto de
configuración. Patrón propuesto (archivo nuevo, no invasivo):

```gdscript
# res://woldvirtual/gdscrip/FeatureFlags.gd  (autoload, ~80-120 líneas)
extends Node
## Flags de activación gradual. TODO nuevo subsistema arranca en false.
var use_transport_layer  : bool = false   # Fase 2: ITransport
var use_enet_transport   : bool = false   # Fase 3: ENet LAN
var use_state_schema_v2  : bool = false   # Fase 1: modelo único
var use_runtime_avatars  : bool = false   # Fase 5: glTF/VRM
func is_on(flag: String) -> bool:
    return flag in self and bool(get(flag))
```

Regla: el código viejo sigue siendo la ruta por defecto. Lo nuevo vive detrás de
un `if FeatureFlags.is_on("..."):`. Activar un flag es una decisión explícita y
reversible. Así un subsistema a medias **nunca** bloquea el arranque.

---

## 4. Backlog accionable por sprints

Cada tarea: objetivo, archivos, cómo NO romper, verificación. Tamaño de tarea
pensado para un solo lote pequeño y verificable.

### Sprint A · Saneamiento sin riesgo (mapea a Fase 0 del plan maestro)

**A1 — Documentar el grafo real de escenas/scripts.**
- Archivos: solo lectura + nuevo `IAs/DevCursorIA/MAPA_ESCENAS.md`.
- No rompe: documentación, cero código.
- Verificación: el mapa lista cada nodo de `N3DWoldVirtualMT.tscn` y su script.

**A2 — Robustecer la ruta de `ChunkManager` en `ChatUI.gd`.**
- Archivo: `gdscrip/ChatUI.gd`.
- Cómo NO romper: añadir resolución por grupo (`get_tree().get_first_node_in_group("chunk_manager")`)
  con *fallback* a la ruta absoluta actual; registrar `ChunkManager` en ese
  grupo en su `_ready` (cambio aditivo).
- Verificación: el chat funciona lanzando la escena directa y embebida.

**A3 — Decidir destino del código huérfano.**
- Archivos: `IPCManager.gd`, `SocialUI.gd`, `IslandStateSync.gd`.
- Cómo NO romper: NO borrar de golpe; marcar con cabecera `## [HUÉRFANO -
  pendiente decisión]` y mover la decisión a A-siguiente. Borrado solo cuando se
  confirme que ninguna escena lo referencia (`grep` del nombre del script).
- Verificación: `grep` muestra cero referencias antes de cualquier borrado.

**A4 — Cablear `EnvironmentManager` a NodePaths reales.**
- Archivo: `gdscrip/EnvironmentManager.gd` + escena.
- Cómo NO romper: usar `get_node_or_null` y salir limpio si falta el nodo
  (degradación elegante, nunca crash).
- Verificación: día/noche responde o loguea "entorno no disponible" sin error.

### Sprint B · Modelo de estado único (mapea a Fase 1)

**B1 — Definir `peer.schema.json` v2 y validador.**
- Archivos: `IAs/DevCursorIA/peer.schema.v2.json` (doc) + validador GDScript/C#.
- Cómo NO romper: el validador es **solo lectura** al principio (loguea, no
  rechaza). Detrás de `use_state_schema_v2`.
- Verificación: pasa el formato actual sin falsos positivos.

**B2 — (De)serializador único u/i ↔ users/islands.**
- Archivos: nuevo `gdscrip/StateCodec.gd` (~200-250 líneas).
- Cómo NO romper: `NetworkLayer.gd` sigue leyendo/escribiendo igual; el codec se
  usa solo cuando el flag está activo. Conversión bidireccional con tests.
- Verificación: round-trip `decode(encode(x)) == x` para muestras reales.

**B3 — Saneamiento de `peerId` antes de construir rutas.**
- Archivo: función util compartida + uso en `NetworkLayer.gd`.
- Cómo NO romper: aplicar saneamiento solo a IDs nuevos; IDs existentes válidos
  no cambian de nombre de fichero.
- Verificación: un `peerId` con `../` o separadores no escapa de `peers/`.

### Sprint C · Abstracción de transporte (mapea a Fase 2)

**C1 — Definir contrato `ITransport`.**
- Archivo: nuevo `gdscrip/transport/ITransport.gd` (contrato + señales).
- Cómo NO romper: es solo una interfaz; nadie la consume aún.

**C2 — `FileSyncTransport` envolviendo `NetworkLayer.gd`.**
- Archivo: nuevo `gdscrip/transport/FileSyncTransport.gd`.
- Cómo NO romper: delega 1:1 en `NetworkLayer.gd`; comportamiento idéntico.

**C3 — `ChunkManager` consume `ITransport` (tras flag).**
- Archivo: `gdscrip/ChunkManager.gd`.
- Cómo NO romper: con `use_transport_layer=false` usa el camino actual; con
  `true` usa `FileSyncTransport`. Ambos caminos coexisten un ciclo.
- Verificación: con flag ON el juego corre **exactamente igual** que con OFF.

### Sprint D · ENet LAN (mapea a Fase 3, solo tras C verde)

**D1 — `ENetTransport` (listen-server/malla LAN).**
- Archivo: nuevo `gdscrip/transport/ENetTransport.gd`.
- Cómo NO romper: nuevo backend detrás de `use_enet_transport`; file-sync sigue
  siendo el predeterminado hasta validar dos PCs en LAN.
- Verificación: 2 PCs ven movimiento en < 100 ms; al apagar el flag, vuelve a
  file-sync sin tocar más código.

> Fases 4-7 (WebRTC, UGC, teleport inter-nodo, economía) heredan el mismo patrón:
> backend/subsistema nuevo + flag apagado + verificación de dos caminos.

---

## 5. Puerta de verificación por tarea (checklist breve)

Antes de dar una tarea por hecha:

- [ ] `git status` solo muestra los archivos de la tarea.
- [ ] El prototipo arranca sin errores rojos (escena directa y embebida).
- [ ] El comportamiento anterior sigue disponible con el flag en OFF.
- [ ] Archivos nuevos/modificados dentro de 200-300 líneas.
- [ ] Sin secretos en `res://` ni prints de depuración en caliente.
- [ ] Reversión probada: revertir el commit deja todo como antes.

---

## 6. Estrategia de reversión (rollback)

- **Nivel 1 — Flag:** apagar el `FeatureFlags` correspondiente desactiva lo nuevo
  sin tocar código. Primer recurso ante cualquier anomalía.
- **Nivel 2 — Commit:** cada tarea es un commit atómico; `git revert <hash>`
  restaura el estado previo de forma trazable.
- **Nivel 3 — Archivo:** para scripts críticos, conservar la versión previa hasta
  cerrar el sprint (validado en la práctica con la cinemática de intro).

---

## 7. Orden de ejecución recomendado

1. **Sprint A** (saneamiento aditivo) — riesgo casi nulo, prepara el terreno.
2. **Sprint B** (modelo único, en modo solo-lectura primero) — desbloquea red.
3. **Sprint C** (`ITransport` + file-sync) — desacople sin regresiones.
4. **Sprint D** (ENet LAN) — primer salto de tiempo real, tras C verde.
5. Continuar con Fases 4-7 del plan maestro con el mismo patrón flag + rollback.

En paralelo y continuo: documentación del modelo, pruebas del núcleo y revisión
de que el arranque sigue verde.

---

## 8. Relación con el plan maestro

| Este plan (ejecución) | Plan maestro (estrategia) |
|-----------------------|---------------------------|
| Sprint A | Fase 0 · Estabilización |
| Sprint B | Fase 1 · Modelo de estado único |
| Sprint C | Fase 2 · `ITransport` + file-sync |
| Sprint D | Fase 3 · ENet LAN |
| Patrón flag+rollback | §14 Riesgos / §16 Checklist |

Este documento es el **cómo seguro**; el plan maestro es el **qué y por qué**.
Ambos se mantienen por bloques incrementales de 200-300 líneas (regla del
proyecto), añadiendo desde la última línea escrita.

**Fin del plan de ejecución segura v1.0.**
